import json
from pathlib import Path
import tempfile
import unittest

from scripts.phase95_bridge import digest
from scripts.phase95_native_failure_triage import (
    last_flushed_retrace, signature, triage,
)


class NativeFailureTriageTests(unittest.TestCase):
    def fixture(self, root):
        source, failed = root / "source", root / "failed"
        source.mkdir()
        failed.mkdir()
        executable, rom = root / "native.exe", root / "rom.z64"
        executable.write_bytes(b"native")
        rom.write_bytes(b"rom")
        (source / "controller.input").write_text(
            "jfg-phase8-input-v2\n0,1,1,0000,0,0\n1,14,1,0000,0,0\n")
        (source / "initial.flash").write_bytes(b"flash")
        (source / "initial.pak").write_bytes(b"pak")
        manifest = {"kind": "jfg-phase95-selected-input-export",
                    "input_sha256": digest(source / "controller.input"),
                    "oracle_final_frame": 14,
                    "initial_state": {
                        "flash_sha256": digest(source / "initial.flash"),
                        "pak_sha256": digest(source / "initial.pak")}}
        (source / "export-manifest.json").write_text(json.dumps(manifest))
        (failed / "native-objective.json").write_text(json.dumps({
            "kind": "jfg-phase95-native-selected-poll-replay",
            "input_sha256": manifest["input_sha256"],
            "executable_sha256": digest(executable),
            "rom_sha256": digest(rom), "stop_mode": "vi-retraces",
            "target_retraces": 14}))
        (failed / "native-result.json").write_text(json.dumps({
            "exit_code": 0xc0000005, "target_retraces": 14}))
        (failed / "stderr.log").write_text("access violation\n")
        (failed / "stdout.log").write_text("original stdout\n")
        rows = [{"kind": "jfg-phase9-retrace-hash-header", "schema": 1}]
        rows.extend({"kind": "jfg-phase9-retrace-hash", "schema": 1,
                     "retrace": frame} for frame in range(1, 9))
        (failed / "retrace-hashes.jsonl").write_text(
            "\n".join(json.dumps(row) for row in rows) + "\n")
        return source, failed, executable, rom

    def test_nonmonotonic_prefix_is_not_claimed_globally_earliest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, failed, executable, rom = self.fixture(root)
            targets = []

            def fake_replay(source, output, executable, rom, rom_sha256,
                            *, timeout, target_retraces):
                targets.append(target_retraces)
                output.mkdir()
                code = 0xc0000005 if target_retraces in (10, 14) else 0
                (output / "native-result.json").write_text(json.dumps({"exit_code": code}))
                (output / "stderr.log").write_text("access violation" if code else "")
                if code:
                    raise RuntimeError("synthetic crash")

            result = triage(source, failed, root / "bundle", executable, rom,
                            digest(rom), max_trials=5, replay_fn=fake_replay)
            self.assertEqual(targets, [7, 8, 9, 10])
            self.assertEqual(result["first_reproduced_tested_prefix"], 10)
            self.assertFalse(result["earliest_prefix_proven"])
            self.assertEqual((root / "bundle" / "controller.input").read_bytes(),
                             (source / "controller.input").read_bytes())
            self.assertEqual((root / "bundle" / "original" / "stdout.log").read_text(),
                             "original stdout\n")

    def test_full_target_is_reserved_when_hint_does_not_reproduce(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, failed, executable, rom = self.fixture(root)
            targets = []

            def fake_replay(source, output, executable, rom, rom_sha256,
                            *, timeout, target_retraces):
                targets.append(target_retraces)
                output.mkdir()
                code = 0xc0000005 if target_retraces == 14 else 0
                (output / "native-result.json").write_text(json.dumps({"exit_code": code}))
                (output / "stderr.log").write_text("access violation" if code else "")
                if code:
                    raise RuntimeError("synthetic crash")

            result = triage(source, failed, root / "bundle", executable, rom,
                            digest(rom), max_trials=2, replay_fn=fake_replay)
            self.assertEqual(targets, [7, 14])
            self.assertEqual(result["first_reproduced_tested_prefix"], 14)
            self.assertFalse(result["earliest_prefix_proven"])

    def test_changed_binary_is_rejected_before_artifact_creation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, failed, executable, rom = self.fixture(root)
            executable.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "pins"):
                triage(source, failed, root / "bundle", executable, rom, digest(rom))
            self.assertFalse((root / "bundle").exists())

    def test_partial_last_trace_row_is_ignored(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "trace.jsonl"
            path.write_text(json.dumps({"kind": "jfg-phase9-retrace-hash-header"}) +
                            "\n" + json.dumps({"kind": "jfg-phase9-retrace-hash",
                                               "retrace": 1}) + "\n{" )
            self.assertEqual(last_flushed_retrace(path), 1)

    def test_asan_class_is_part_of_signature(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "native-result.json").write_text(json.dumps({"exit_code": 1}))
            (root / "stderr.log").write_text(
                "==12==ERROR: AddressSanitizer: heap-use-after-free on address 0xabc\n")
            self.assertEqual(signature(root), {"exit_code_hex": "0x00000001",
                                               "asan_class": "heap-use-after-free"})


if __name__ == "__main__":
    unittest.main()
