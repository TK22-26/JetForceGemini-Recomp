import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts.phase95_bridge import digest
from scripts.phase95_native_replay import (
    poll_completion, replay, validate_entry_fpu, validate_entry_gpr,
    validate_entry_memory,
    validate_entry_target, validate_instruction_probe,
)


class NativeReplayContractTests(unittest.TestCase):
    def test_si_count_probe_requires_guest_initialization(self):
        with mock.patch.dict("os.environ", {
                "JFG_PHASE9_SI_COUNT_PROBE": "1",
                "JFG_PHASE9_CONTROLLER_GUEST_INIT": "0"}):
            with self.assertRaisesRegex(ValueError, "requires original controller"):
                replay(None, None, None, None, None)

    def test_instruction_probe_requires_focused_updates(self):
        self.assertTrue(validate_instruction_probe(True, (1264, 1266)))
        self.assertFalse(validate_instruction_probe(False, None))
        for enabled, focus in ((True, None), ("yes", (1264, 1266))):
            with self.assertRaises(ValueError):
                validate_instruction_probe(enabled, focus)

    def test_entry_gpr_requires_entry_probe(self):
        self.assertTrue(validate_entry_gpr(True, 0x800743D0))
        self.assertFalse(validate_entry_gpr(False, None))
        for enabled, target in ((True, None), ("yes", 0x800743D0)):
            with self.assertRaises(ValueError):
                validate_entry_gpr(enabled, target)

    def test_entry_memory_requires_entry_probe(self):
        self.assertTrue(validate_entry_memory(True, 0x800743D0))
        self.assertFalse(validate_entry_memory(False, None))
        for enabled, target in ((True, None), ("yes", 0x800743D0)):
            with self.assertRaises(ValueError):
                validate_entry_memory(enabled, target)

    def test_entry_fpu_requires_entry_probe(self):
        self.assertTrue(validate_entry_fpu(True, 0x02F0084C))
        self.assertFalse(validate_entry_fpu(False, None))
        for enabled, target in ((True, None), ("yes", 0x02F0084C)):
            with self.assertRaises(ValueError):
                validate_entry_fpu(enabled, target)

    def test_entry_probe_requires_focused_aligned_dispatch_target(self):
        self.assertEqual(validate_entry_target(0x02F0084C, (1247, 1253)),
                         0x02F0084C)
        for target, focus in ((0, (1247, 1253)),
                              (0x02F0084D, (1247, 1253)),
                              (0x02F0084C, None),
                              (True, (1247, 1253))):
            with self.assertRaises(ValueError):
                validate_entry_target(target, focus)

    def test_retrace_target_does_not_imply_complete_poll_route(self):
        status = poll_completion(10881, 8883)
        self.assertFalse(status["input_route_complete"])
        self.assertEqual(status["missing_controller_polls"], 1998)
        self.assertEqual(status["post_eof_neutral_polls"], 0)

    def test_complete_and_post_eof_poll_counts(self):
        self.assertTrue(poll_completion(2, 2)["input_route_complete"])
        status = poll_completion(2, 5)
        self.assertTrue(status["input_route_complete"])
        self.assertEqual(status["post_eof_neutral_polls"], 3)
        self.assertEqual(status["missing_controller_polls"], 0)

    def test_invalid_counters_rejected(self):
        for declared, observed in ((0, 1), (2, -1), (True, 2), (2, False)):
            with self.assertRaises(ValueError):
                poll_completion(declared, observed)

    def test_poll_target_command_and_actual_retrace_are_recorded(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "controller.input").write_text(
                "jfg-phase8-input-v2\n0,1,1,1000,0,0\n1,12,1,0000,0,0\n")
            (source / "initial.flash").write_bytes(b"flash")
            (source / "initial.pak").write_bytes(b"pak")
            (source / "export-manifest.json").write_text(json.dumps({
                "kind": "jfg-phase95-selected-input-export",
                "input_sha256": digest(source / "controller.input"),
                "oracle_final_frame": 12, "controller_polls": 2,
                "initial_state": {
                    "flash_sha256": digest(source / "initial.flash"),
                    "pak_sha256": digest(source / "initial.pak"),
                },
            }))
            executable = root / "native.exe"
            executable.write_bytes(b"synthetic executable")
            rom = root / "rom.z64"
            rom.write_bytes(b"synthetic rom")
            commands = []

            class FakeProcess:
                pid = 123

                def __init__(self, command, **kwargs):
                    commands.append(command)
                    probe = {"kind": "jfg-phase8-native-probe",
                             "controller_samples": 2, "state_hash": "a" * 64}
                    if "--probe-polls" in command:
                        probe.update(status="poll-target", poll_target=2,
                                     vi_retraces=19)
                    else:
                        target = int(command[command.index("--probe-retraces") + 1])
                        probe.update(status="retrace-target", retrace_target=12,
                                     vi_retraces=target)
                    kwargs["stdout"].write((json.dumps(probe, separators=(",", ":")) + "\n").encode())
                    kwargs["stdout"].flush()
                    if kwargs["env"].get("JFG_PHASE9_UPDATE_HASHES") == "1":
                        record = {
                            "kind": "jfg-phase9-update-hash", "schema": 1,
                            "update": 1, "front_mode": 0, "actor_count": 0,
                            "rng_seed": "0x00000000", "player_actor": "0x00000000",
                            "actor_list": "0x00000000", "player_sha256": None,
                            "actor_table_sha256": None,
                            "globals_sha256": "0" * 64,
                            "camera_sha256": "1" * 64, "actors": [],
                        }
                        output = Path(kwargs["env"]["JFG_PHASE9_RETRACE_HASH"] +
                                      ".updates.jsonl")
                        output.write_text(json.dumps({
                            "kind": "jfg-phase9-update-hash-header", "schema": 1,
                        }) + "\n" + json.dumps(record) + "\n", encoding="utf-8")

                def wait(self, timeout):
                    return 0

            with mock.patch("scripts.phase95_native_replay.WorkerJob"), \
                    mock.patch("scripts.phase95_native_replay.subprocess.Popen", FakeProcess):
                result = replay(source, root / "output", executable, rom, digest(rom),
                                timeout=30, stop_by_polls=True)
            self.assertEqual(commands[0][-4:], ["--probe-polls", "2", "--watchdog-ms", "30000"])
            self.assertNotIn("--probe-retraces", commands[0])
            self.assertTrue(result["probe_target_reached"])
            self.assertEqual(result["actual_vi_retraces"], 19)
            self.assertEqual(result["target_controller_polls"], 2)
            self.assertIsNone(result["target_retraces"])
            self.assertEqual(result["post_eof_neutral_polls"], 0)
            with mock.patch("scripts.phase95_native_replay.WorkerJob"), \
                    mock.patch("scripts.phase95_native_replay.subprocess.Popen", FakeProcess):
                retrace_result = replay(source, root / "retrace-output", executable,
                                        rom, digest(rom), timeout=30)
            self.assertEqual(commands[1][-2:], ["--probe-retraces", "12"])
            self.assertTrue(retrace_result["probe_target_reached"])
            self.assertEqual(retrace_result["stop_mode"], "vi-retraces")
            with mock.patch("scripts.phase95_native_replay.WorkerJob"), \
                    mock.patch("scripts.phase95_native_replay.subprocess.Popen", FakeProcess):
                prefix_result = replay(source, root / "prefix-output", executable,
                                       rom, digest(rom), timeout=30,
                                       target_retraces=6, update_hashes=True)
            self.assertEqual(commands[2][-2:], ["--probe-retraces", "6"])
            self.assertEqual(prefix_result["target_retraces"], 6)
            self.assertEqual(prefix_result["oracle_final_frame"], 12)
            self.assertEqual(prefix_result["completed_update_count"], 1)
            self.assertTrue(prefix_result["completed_update_trace_complete"])

    def test_wrong_poll_probe_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "controller.input").write_text(
                "jfg-phase8-input-v2\n0,12,1,1000,0,0\n")
            (source / "initial.flash").write_bytes(b"flash")
            (source / "initial.pak").write_bytes(b"pak")
            (source / "export-manifest.json").write_text(json.dumps({
                "kind": "jfg-phase95-selected-input-export",
                "input_sha256": digest(source / "controller.input"),
                "oracle_final_frame": 12, "controller_polls": 2,
                "initial_state": {
                    "flash_sha256": digest(source / "initial.flash"),
                    "pak_sha256": digest(source / "initial.pak"),
                },
            }))
            executable = root / "native.exe"
            executable.write_bytes(b"synthetic executable")
            rom = root / "rom.z64"
            rom.write_bytes(b"synthetic rom")

            class FakeProcess:
                pid = 123

                def __init__(self, command, **kwargs):
                    probe = {"kind": "jfg-phase8-native-probe",
                             "status": "poll-target", "poll_target": 3,
                             "controller_samples": 3, "vi_retraces": 19}
                    kwargs["stdout"].write((json.dumps(probe, separators=(",", ":")) + "\n").encode())
                    kwargs["stdout"].flush()

                def wait(self, timeout):
                    return 0

            with mock.patch("scripts.phase95_native_replay.WorkerJob"), \
                    mock.patch("scripts.phase95_native_replay.subprocess.Popen", FakeProcess):
                with self.assertRaisesRegex(RuntimeError, "bounded target"):
                    replay(source, root / "output", executable, rom, digest(rom),
                           timeout=30, stop_by_polls=True)
            result = json.loads((root / "output" / "native-result.json").read_text())
            self.assertFalse(result["probe_target_reached"])


if __name__ == "__main__":
    unittest.main()
