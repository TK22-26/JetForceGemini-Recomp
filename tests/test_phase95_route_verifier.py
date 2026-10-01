import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from scripts.phase95_bridge import digest
from scripts.phase95_route_verifier import (
    audit_oracle_runs, source_contract, verify,
)


class RouteVerifierTests(unittest.TestCase):
    def fixture(self, root):
        worker, source, oracle, native = (root / name for name in
                                          ("worker", "source", "oracle", "native"))
        for path in (worker, source, oracle, native):
            path.mkdir()
        rom, emulator, executable = (root / name for name in
                                     ("rom.z64", "EmuHawk.exe", "native.exe"))
        rom.write_bytes(b"rom")
        emulator.write_bytes(b"emulator")
        executable.write_bytes(b"native")
        stage_hash, final_hash = digest_bytes(b"stage"), digest_bytes(b"final")
        (worker / "bridge-result.txt").write_text("stopped\n")
        (worker / "observation.rdram").write_bytes(b"final")
        (worker / "manifest.json").write_text(json.dumps({
            "rom_sha256": digest(rom), "emulator_sha256": digest(emulator),
            "config_sha256": "c" * 64, "runtime_sha256": "r" * 64}))
        (worker / "observations.jsonl").write_text(
            json.dumps({"frame": 3, "polls": 1, "rdram_sha256": stage_hash}) + "\n" +
            json.dumps({"frame": 5, "polls": 2, "rdram_sha256": final_hash}) + "\n")
        (worker / "scenario-stages.jsonl").write_text(
            json.dumps({"stage": 0, "frame": 3, "rdram_sha256": stage_hash}) + "\n")
        scenario = worker / "scenario-result.json"
        scenario.write_text(json.dumps({"completed": True, "final_frame": 5,
                                        "final_rdram_sha256": final_hash,
                                        "verification_frames": [3]}))
        (source / "controller.input").write_text(
            "jfg-phase8-input-v2\n0,1,1,0000,0,0\n1,5,1,0000,0,0\n")
        (source / "initial.flash").write_bytes(b"flash")
        (source / "initial.pak").write_bytes(b"pak")
        (source / "export-manifest.json").write_text(json.dumps({
            "kind": "jfg-phase95-selected-input-export", "schema": 1,
            "source_worker": str(worker.resolve()),
            "input_sha256": digest(source / "controller.input"),
            "oracle_final_frame": 5, "controller_polls": 2,
            "initial_state": {"flash_sha256": digest(source / "initial.flash"),
                              "pak_sha256": digest(source / "initial.pak")}}))
        (oracle / "checkpoint-000003.rdram").write_bytes(b"stage")
        (oracle / "checkpoint-000005.rdram").write_bytes(b"final")
        (oracle / "checkpoints.tsv").write_text(
            "input-poll\t3\tindex\t0\ninput-poll\t5\tindex\t1\n")
        (oracle / "oracle-result.json").write_text(json.dumps({
            "kind": "jfg-phase95-oracle-poll-replay", "exit_code": 0,
            "trace_complete": True, "input_clock": "controller-poll",
            "input_sha256": digest(source / "controller.input"),
            "target_frame": 5, "initial_flash_matches_candidate": True,
            "oracle_initial_flash_sha256": digest(source / "initial.flash"),
            "source_export_sha256": digest(source / "export-manifest.json"),
            "rom_sha256": digest(rom), "emulator_sha256": digest(emulator),
            "config_sha256": "c" * 64, "runtime_sha256": "r" * 64,
            "script_sha256": "s" * 64,
            "final_rdram_sha256": final_hash}))
        (native / "controller.input").write_bytes((source / "controller.input").read_bytes())
        (native / "replay.flash").write_bytes(b"written flash")
        (native / "replay.pak").write_bytes(b"written pak")
        native_fields = {"kind": "jfg-phase95-native-selected-poll-replay",
                         "input_sha256": digest(source / "controller.input"),
                         "initial_flash_sha256": digest(source / "initial.flash"),
                         "initial_pak_sha256": digest(source / "initial.pak"),
                         "executable_sha256": digest(executable),
                         "rom_sha256": digest(rom), "target_retraces": 5}
        (native / "native-objective.json").write_text(json.dumps(native_fields))
        (native / "native-result.json").write_text(json.dumps({
            **native_fields, "exit_code": 0, "probe_target_reached": True,
            "observed_controller_polls": 3, "post_eof_neutral_polls": 1,
            "input_route_complete": True}))
        return source, scenario, oracle, native, emulator, rom, executable

    def test_generic_reuse_reports_mismatch_without_parity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, scenario, oracle, native, emulator, rom, exe = self.fixture(root)
            result = verify(source, scenario, root / "report", emulator, rom,
                            digest(rom), exe, repeats=1,
                            oracle_existing=[oracle], native_existing=native)
            self.assertTrue(result["oracle"]["all_match"])
            self.assertEqual(result["oracle"]["intermediate_checkpoint_count"], 1)
            self.assertFalse(result["endpoint_poll_counts_match"])
            self.assertFalse(result["native_parity_verified"])
            self.assertEqual(result["native_final_flash_sha256"], digest(native / "replay.flash"))

    def test_stale_source_final_memory_is_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, scenario, _, _, emulator, rom, exe = self.fixture(root)
            (scenario.parent / "observation.rdram").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "source scenario final state"):
                verify(source, scenario, root / "report", emulator, rom, digest(rom), exe)
            self.assertFalse((root / "report").exists())

    def test_changed_oracle_pin_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, scenario, oracle, _, emulator, rom, _ = self.fixture(root)
            contract = source_contract(source, scenario, emulator, rom, digest(rom))
            result_file = oracle / "oracle-result.json"
            result = json.loads(result_file.read_text())
            result["config_sha256"] = "changed"
            result_file.write_text(json.dumps(result))
            with self.assertRaisesRegex(ValueError, "provenance pins"):
                audit_oracle_runs(source, contract, [oracle])

    def test_ambiguous_frame_requires_selected_state_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, scenario, _, _, emulator, rom, _ = self.fixture(root)
            (scenario.parent / "scenario-stages.jsonl").unlink()
            rows = (scenario.parent / "observations.jsonl").read_text().splitlines()
            alternate = json.dumps({"frame": 3, "polls": 1,
                                    "rdram_sha256": digest_bytes(b"trial")})
            (scenario.parent / "observations.jsonl").write_text(
                "\n".join([rows[0], alternate, rows[1]]) + "\n")
            with self.assertRaisesRegex(ValueError, "missing or ambiguous"):
                source_contract(source, scenario, emulator, rom, digest(rom))
            selected = [{"frame": 3, "rdram_sha256": digest_bytes(b"stage")}]
            contract = source_contract(source, scenario, emulator, rom,
                                       digest(rom), extra_checkpoints=selected)
            self.assertEqual(contract["checkpoints"][0]["rdram_sha256"],
                             digest_bytes(b"stage"))

    def test_existing_native_input_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, scenario, oracle, native, emulator, rom, exe = self.fixture(root)
            (native / "controller.input").write_text("changed")
            with self.assertRaisesRegex(ValueError, "native replay does not match"):
                verify(source, scenario, root / "report", emulator, rom,
                       digest(rom), exe, repeats=1,
                       oracle_existing=[oracle], native_existing=native)
            failure = json.loads((root / "report" / "verification-failure.json").read_text())
            self.assertFalse(failure["completed"])

    def test_new_native_crash_invokes_failure_triage(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, scenario, oracle, native, emulator, rom, exe = self.fixture(root)

            def crashing_replay(source, output, *args, **kwargs):
                shutil.copytree(native, output)
                result_file = output / "native-result.json"
                result = json.loads(result_file.read_text())
                result["exit_code"] = 1
                result_file.write_text(json.dumps(result))
                raise RuntimeError("seeded native crash")

            with mock.patch("scripts.phase95_route_verifier.native_replay",
                            side_effect=crashing_replay), \
                    mock.patch("scripts.phase95_route_verifier.failure_triage",
                               return_value={"reproduced": True}) as triage:
                with self.assertRaisesRegex(RuntimeError, "seeded native crash"):
                    verify(source, scenario, root / "report", emulator, rom,
                           digest(rom), exe, repeats=1, oracle_existing=[oracle])
            triage.assert_called_once()
            failure = json.loads((root / "report" / "verification-failure.json").read_text())
            self.assertEqual(failure["native_failure_triage"], {"reproduced": True})


def digest_bytes(value):
    import hashlib
    return hashlib.sha256(value).hexdigest()


if __name__ == "__main__":
    unittest.main()
