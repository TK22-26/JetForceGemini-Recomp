from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from scripts.autonomy.job_store import JobSpec, JobStore
from scripts.autonomy.scheduler import (
    advance_update_diagnoses, advance_update_focus, advance_updates,
    advance_vi_boundaries,
    diagnostic_suffix_allows_extension, focus_pair_for_later_mismatch,
)
from scripts.autonomy.supervisor import SupervisorError, file_sha256, run_once
from scripts.autonomy.update_job import TOOL_FILES, queue_update, validate
from scripts.autonomy import execution_contract as execution
from scripts.autonomy.determinism_job import queue_determinism, TOOL_FILES as REPEAT_TOOL_FILES


def _trace(path: Path, *, seed: str = "0x00000000", oracle: bool = False) -> None:
    header = {"kind": "jfg-phase9-update-hash-header", "schema": 1}
    update = {"kind": "jfg-phase9-update-hash", "schema": 1, "update": 1,
              "front_mode": 0, "actor_count": 0, "actors": [], "rng_seed": seed,
              "actor_list": "0x00000000", "player_actor": "0x00000000",
              "player_sha256": None, "actor_table_sha256": None,
              "globals_sha256": "0" * 64, "camera_sha256": "1" * 64,
              "controller_polls": 1}
    update["emulator_frame" if oracle else "vi_retraces"] = 3
    path.write_text(json.dumps(header) + "\n" + json.dumps(update) + "\n",
                    encoding="utf-8")


class UpdateJobTests(unittest.TestCase):
    def test_entry_capture_uses_fixed_bounded_cli_and_keeps_frozen_profile(self):
        from scripts.autonomy.update_job import run_update_lease
        self.queue()
        with JobStore(self.state / "jobs.sqlite") as store:
            source_commit = store.job("alignment-fixture")["spec"]["pins"]["source_commit"]
            contract = {"profile": "original-os-probe", **{key: "0" * 64 for key in (
                "native_runtime_sha256", "oracle_runtime_sha256", "oracle_source_config_sha256", "oracle_config_sha256")}}
            parent = dict(self.alignment_packet, execution=contract, source_build={"fixture": "binding"})
            probe = {"entry_pc": "0x80000200", "call_pc": "0x80000100"}
            with patch("scripts.autonomy.update_job.source_build.validate", return_value={"source_commit": source_commit}), \
                    patch.object(execution, "capture", return_value=contract), \
                    patch.object(execution, "require_current"), \
                    patch("scripts.autonomy.update_job.bounded_command", side_effect=[(0, None), (-1, "fixture-stop")]) as command:
                queue_update(store, self.repo, self.state, job_id="entry-fixture", alignment_id="alignment-fixture",
                             alignment_result=self.alignment_result, alignment_packet=parent, native_target=10,
                             focus_pair={"native_before": 2, "oracle_before": 2, "native_after": 3, "oracle_after": 3},
                             entry_probe=probe)
                packet = json.loads((self.state / "update-packets/entry-fixture.json").read_text())
                self.assertEqual(packet["entry_probe"], probe)
                self.assertEqual(packet["focus_updates"], [1, 4])
                self.assertEqual(packet["source_commit"], source_commit)
                self.assertEqual(packet["timeout_seconds"], 660)
                lease = store.lease_job("entry-fixture", "fixture")
                result = run_update_lease(store, lease, self.repo, self.state)
            self.assertIn("failed", result)
            self.assertEqual(command.call_count, 2)
            for index, flag in ((0, "--entry-target"), (1, "--entry-pc")):
                argv = command.call_args_list[index].args[0]
                self.assertEqual(argv[argv.index(flag) + 1], probe["entry_pc"])
                self.assertIn("--entry-gpr", argv)
                self.assertEqual(argv[argv.index("--timeout") + 1], "300")
            native = command.call_args_list[0].args[0]
            self.assertEqual(native[native.index("--execution-profile") + 1], "original-os-probe")

    def test_point_capture_constructs_only_fixed_bounded_cli(self):
        from scripts.autonomy.update_job import run_update_lease
        self.queue()
        with JobStore(self.state/"jobs.sqlite") as store:
            commit=store.job("alignment-fixture")["spec"]["pins"]["source_commit"]
            contract={"profile":"original-os-probe",**{key:"0"*64 for key in (
                "native_runtime_sha256","oracle_runtime_sha256","oracle_source_config_sha256","oracle_config_sha256")}}
            parent=dict(self.alignment_packet,execution=contract,source_build={"fixture":"binding"})
            probe={"entry_pc":"0x80000200","call_pc":"0x80000100","pcs":["0x80000200","0x80000108"],"words":["0x800a9e90"]}
            with patch("scripts.autonomy.update_job.source_build.validate",return_value={"source_commit":commit}), \
                    patch.object(execution,"capture",return_value=contract),patch.object(execution,"require_current"), \
                    patch("scripts.autonomy.update_job.bounded_command",side_effect=[(0,None),(-1,"fixture-stop")]) as command:
                queue_update(store,self.repo,self.state,job_id="point-fixture",alignment_id="alignment-fixture",
                    alignment_result=self.alignment_result,alignment_packet=parent,native_target=10,
                    focus_pair={"native_before":2,"oracle_before":2,"native_after":3,"oracle_after":3},point_probe=probe)
                packet=json.loads((self.state/"update-packets/point-fixture.json").read_text())
                self.assertEqual(packet["point_probe"],probe)
                self.assertEqual(packet["timeout_seconds"],660)
                lease=store.lease_job("point-fixture","fixture")
                self.assertIn("failed",run_update_lease(store,lease,self.repo,self.state))
            self.assertEqual(command.call_count,2)
            for call in command.call_args_list:
                argv=call.args[0]
                self.assertEqual([argv[i+1] for i,x in enumerate(argv) if x=="--point-pc"],probe["pcs"])
                self.assertEqual([argv[i+1] for i,x in enumerate(argv) if x=="--point-word"],probe["words"])
                self.assertEqual(argv[argv.index("--timeout")+1],"300")
                self.assertNotIn("--poll-hashes",argv)

    def test_focus_frontier_moves_once_after_a_fix(self) -> None:
        prior = {"native_before": 1252, "native_after": 1253,
                 "oracle_before": 1248, "oracle_after": 1249}
        later = {"native_update": 1265, "oracle_update": 1261,
                 "reason": "semantic-mismatch"}
        moved = {"native_before": 1264, "native_after": 1265,
                 "oracle_before": 1260, "oracle_after": 1261}
        self.assertEqual(focus_pair_for_later_mismatch(later, prior), moved)
        self.assertIsNone(focus_pair_for_later_mismatch(later, moved))
        self.assertIsNone(focus_pair_for_later_mismatch(
            dict(later, reason="missing-update"), prior))
        self.assertIsNone(focus_pair_for_later_mismatch(
            dict(later, native_update=1277), prior))

    def test_only_complete_poll_anchored_suffix_can_extend_diagnostically(self) -> None:
        result = {"prefix_match": False, "input_prefix_match": True,
                  "parity_verified": False, "first_divergence": {"update": 568}}
        alignment = {
            "kind": "jfg-phase9-update-poll-alignment",
            "classification": "poll-anchored-semantic-resynchronization",
            "alignment_validated": False, "parity_verified": False,
            "first_raw_mismatch_update": 568,
            "native_suffix_exhausted": True, "first_later_mismatch": None,
            "matched_update_run": 23,
            "same_poll_anchor": {"controller_polls": 575,
                                 "native_update": 572, "oracle_update": 568}}
        self.assertTrue(diagnostic_suffix_allows_extension(result, alignment))
        for key, value in (("native_suffix_exhausted", False),
                           ("first_later_mismatch", {"native_update": 590}),
                           ("alignment_validated", True),
                           ("matched_update_run", 2)):
            changed = dict(alignment, **{key: value})
            self.assertFalse(diagnostic_suffix_allows_extension(result, changed))
        self.assertFalse(diagnostic_suffix_allows_extension(
            dict(result, input_prefix_match=False), alignment))

    def test_oracle_exhaustion_extends_only_a_verified_matching_suffix(self) -> None:
        result = {"prefix_match": False, "input_prefix_match": True,
                  "parity_verified": False, "first_divergence": {"update": 568}}
        alignment = {
            "kind": "jfg-phase9-update-poll-alignment",
            "classification": "poll-anchored-semantic-resynchronization",
            "alignment_validated": False, "parity_verified": False,
            "first_raw_mismatch_update": 568,
            "native_suffix_exhausted": False,
            "first_later_mismatch": {"reason": "oracle-stream-ended",
                                     "native_update": 875},
            "matched_update_run": 303,
            "same_poll_anchor": {"controller_polls": 575,
                                 "native_update": 572, "oracle_update": 568}}
        self.assertTrue(diagnostic_suffix_allows_extension(result, alignment))
        for later in ({"reason": "semantic-mismatch", "native_update": 875},
                      {"reason": "oracle-stream-ended", "native_update": 874},
                      {"reason": "oracle-stream-ended"}, None):
            self.assertFalse(diagnostic_suffix_allows_extension(
                result, dict(alignment, first_later_mismatch=later)))
        self.assertFalse(diagnostic_suffix_allows_extension(
            result, dict(alignment, native_suffix_exhausted=True)))

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        original = Path(__file__).resolve().parents[1]
        for relative in set(TOOL_FILES) | set(REPEAT_TOOL_FILES):
            target = self.repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original / relative, target)
        (self.repo / "README.md").write_text("fixture\n", encoding="utf-8")
        for args in (["git", "init", "-q", str(self.repo)],
                     ["git", "-C", str(self.repo), "config", "user.name", "Test"],
                     ["git", "-C", str(self.repo), "config", "user.email", "test@example.com"],
                     ["git", "-C", str(self.repo), "add", "scripts", "README.md"],
                     ["git", "-C", str(self.repo), "commit", "-qm", "fixture"]):
            subprocess.run(args, check=True, capture_output=True)
        private = self.repo / "tools" / "private"
        self.state = private / "autonomy"
        self.state.mkdir(parents=True)
        self.source = private / "selected-input"
        self.source.mkdir()
        (self.source / "controller.input").write_text(
            "jfg-phase8-input-v2\n0,900,1,0000,0,0\n", encoding="utf-8")
        (self.source / "initial.flash").write_bytes(b"flash")
        (self.source / "initial.pak").write_bytes(b"pak")
        (self.source / "export-manifest.json").write_text(json.dumps({
            "kind": "jfg-phase95-selected-input-export",
            "oracle_final_frame": 900,
            "controller_polls": 1, "native_mode": "replay-by-poll",
            "input_sha256": file_sha256(self.source / "controller.input"),
            "initial_state": {
                "flash_sha256": file_sha256(self.source / "initial.flash"),
                "pak_sha256": file_sha256(self.source / "initial.pak"),
            },
        }), encoding="utf-8")
        self.alignment_result = private / "alignment-result.json"
        self.alignment_result.write_text('{"complete":true}\n', encoding="utf-8")
        self.pin_files = {}
        for key in ("rom", "emulator", "native"):
            path = private / (key + ".fixture")
            path.write_text(key, encoding="utf-8")
            self.pin_files[key] = str(path)
        self.alignment_packet = {"source_export": str(self.source),
                                 "pin_files": self.pin_files}

    def queue(self) -> None:
        with JobStore(self.state / "jobs.sqlite") as store:
            source_commit = subprocess.run(
                ["git", "-C", str(self.repo), "rev-parse", "HEAD"],
                check=True, capture_output=True, text=True).stdout.strip()
            fixture_pins = {"source_commit": source_commit,
                            **{key: "0" * 64 for key in (
                                "tool_sha256", "rom_sha256", "emulator_sha256",
                                "native_sha256")}}
            store.enqueue(JobSpec("alignment-fixture", fixture_pins,
                                  ("fixture",), (), "fixture", 0, "file_sha256"))
            lease = store.lease_job("alignment-fixture", "test-owner")
            self.assertIsNotNone(lease)
            store.start("alignment-fixture", lease["token"])
            store.verify("alignment-fixture", lease["token"])
            store.seal_artifact("alignment-fixture", lease["token"],
                                self.alignment_result)
            store.pass_job("alignment-fixture", lease["token"])
            queue_update(store, self.repo, self.state, job_id="update-fixture",
                         alignment_id="alignment-fixture",
                         alignment_result=self.alignment_result,
                         alignment_packet=self.alignment_packet,
                         execution_profile=getattr(self, "execution_profile", None))

    def test_packet_is_pinned(self) -> None:
        self.queue()
        packet = json.loads((self.state / "update-packets" /
                             "update-fixture.json").read_text(encoding="utf-8"))
        validate(packet, self.repo)
        self.assertEqual((packet["native_target"], packet["oracle_target"]),
                         (600, 900))
        with JobStore(self.state / "jobs.sqlite") as store:
            job = store.job("update-fixture")
            self.assertEqual(job["spec"]["prerequisites"], ["alignment-fixture"])
            self.assertEqual(job["spec"]["resource"], "emulator:bizhawk")
        (self.source / "initial.pak").write_bytes(b"changed")
        with self.assertRaisesRegex(SupervisorError, "evidence changed"):
            validate(packet, self.repo)

    def run_fake(self, oracle_seed: str = "0x00000000",
                 alignment_override: dict | None = None, execution_profile=None,
                 crash_after_capture=False):
        if execution_profile is not None:
            self.execution_profile = execution_profile
            config = Path(self.pin_files["emulator"]).parent / "config.ini"
            config.write_text(json.dumps({"PreferredCores": {"N64": "Mupen64Plus"}}))
        self.queue()
        packet = json.loads((self.state / "update-packets/update-fixture.json").read_text())
        native_extra, oracle_extra = {}, {}
        self.commands = []
        if "execution" in packet:
            contract = packet["execution"]
            original = contract["profile"] == "original-os-probe"
            native_extra = {"execution_profile": contract["profile"],
                            "native_runtime_sha256": contract["native_runtime_sha256"],
                            "guest_os_probe": original, "guest_leaf_probe": original,
                            "renderer_writeback_probe": original,
                            "controller_guest_init_probe": False, "si_count_probe": False}
            oracle_extra = {"runtime_sha256": contract["oracle_runtime_sha256"],
                            "config_sha256": contract["oracle_config_sha256"]}

        def fake_bounded(command, cwd, stdout, stderr, deadline, heartbeat,
                         pause_file, **kwargs):
            heartbeat()
            self.commands.append(command)
            if "scripts.phase95_native_replay" in command:
                output = Path(command[4])
                output.mkdir()
                (output / "native-result.json").write_text(json.dumps({
                    **native_extra,
                    "exit_code": 0, "completed_update_trace": True,
                    "probe_target_reached": True, "completed_update_trace_complete": True,
                    "completed_update_count": 1, "source_export": str(self.source),
                    "target_retraces": 600,
                    "observed_controller_polls": 1,
                    "input_sha256": file_sha256(self.source / "controller.input"),
                    "initial_flash_sha256": file_sha256(self.source / "initial.flash"),
                    "initial_pak_sha256": file_sha256(self.source / "initial.pak"),
                    "rom_sha256": file_sha256(Path(self.pin_files["rom"])),
                    "executable_sha256": file_sha256(Path(self.pin_files["native"])),
                    "final_state_hash": "0" * 64,
                }), encoding="utf-8")
                _trace(output / "retrace-hashes.jsonl.updates.jsonl")
                (output / "retrace-hashes.jsonl").write_text("fixture VI trace\n")
                (output / "controller-polls.tsv").write_text(
                    "poll\tvi_retrace\tvi_frame\tfront_mode\tlevel_word\trng_seed\tbuttons\tx\ty\n"
                    "0\t2\t2\t0\t0\t0\t0\t0\t0\n", encoding="utf-8")
            else:
                output = Path(command[3])
                output.mkdir()
                (output / "oracle-result.json").write_text(json.dumps({
                    **oracle_extra,
                    "exit_code": 0, "completed_update_trace": True,
                    "trace_complete": True, "initial_flash_matches_candidate": True,
                    "completed_update_trace_complete": True,
                    "completed_update_count": 1, "source_export": str(self.source),
                    "target_frame": 900,
                    "input_sha256": file_sha256(self.source / "controller.input"),
                    "source_export_sha256": file_sha256(
                        self.source / "export-manifest.json"),
                    "oracle_initial_flash_sha256": file_sha256(
                        self.source / "initial.flash"),
                    "rom_sha256": file_sha256(Path(self.pin_files["rom"])),
                    "emulator_sha256": file_sha256(Path(self.pin_files["emulator"])),
                }), encoding="utf-8")
                _trace(output / "update-hashes.jsonl", seed=oracle_seed, oracle=True)
                (output / "checkpoints.tsv").write_text(
                    "input-poll\t3\tindex\t0\tbuttons\t0000\tstick\t0,0\tmode\t0\tlevel\t0\trng\t0\n",
                    encoding="utf-8")
            return 0, None

        with patch("scripts.autonomy.update_job.bounded_command",
                   side_effect=fake_bounded):
            if crash_after_capture:
                class SimulatedPowerLoss(BaseException):
                    pass
                with patch.object(JobStore, "pass_job", side_effect=SimulatedPowerLoss):
                    with self.assertRaises(SimulatedPowerLoss):
                        run_once(self.repo, self.state, Path(self.pin_files["native"]),
                                 require_auth=False)
                return
            elif alignment_override is None:
                outcome = run_once(self.repo, self.state,
                                   Path(self.pin_files["native"]), require_auth=False)
            else:
                with patch("scripts.autonomy.update_job.diagnose_poll_alignment",
                           return_value=alignment_override):
                    outcome = run_once(self.repo, self.state,
                                       Path(self.pin_files["native"]),
                                       require_auth=False)
        self.assertEqual(outcome, "update-fixture: completed-update prefix sealed")
        result = json.loads((self.state / "attempts" / "update-fixture" / "0001" /
                             "result.json").read_text(encoding="utf-8"))
        return outcome, result

    def test_original_os_worker_and_successors_keep_execution_contract(self):
        self.run_fake(execution_profile="original-os-probe")
        command = self.commands[0]
        self.assertEqual(command[command.index("--execution-profile") + 1], "original-os-probe")
        parent = json.loads((self.state / "update-packets/update-fixture.json").read_text())
        with JobStore(self.state / "jobs.sqlite") as store:
            self.assertEqual(advance_updates(store, self.repo, self.state), ["update-fixture-to-900"])
            self.assertEqual(advance_updates(store, self.repo, self.state), [])
            repeat_id = queue_determinism(store, self.repo, self.state,
                                          "update-fixture", runs=2, parallelism=2)
        successor = json.loads((self.state / "update-packets/update-fixture-to-900.json").read_text())
        repeats = json.loads((self.state / "determinism-packets" / (repeat_id + ".json")).read_text())
        self.assertEqual(successor["execution"], parent["execution"])
        self.assertEqual(repeats["execution"], parent["execution"])
        baseline_dir = self.state / "attempts/update-fixture/0001/native"
        def fake_repeat(command, *args, **kwargs):
            self.assertEqual(command[command.index("--execution-profile") + 1],
                             "original-os-probe")
            shutil.copytree(baseline_dir, Path(command[4]))
            return 0, None
        with patch("scripts.autonomy.determinism_job.bounded_command", side_effect=fake_repeat):
            self.assertEqual(run_once(self.repo, self.state, Path(self.pin_files["native"]),
                                      allow_agent=False, job_id=repeat_id),
                             repeat_id + ": 2 native repeats sealed")
        result = json.loads((self.state / "attempts" / repeat_id / "0001/result.json").read_text())
        self.assertTrue(result["deterministic"])

    def test_frozen_build_source_survives_worker_and_successor_instead_of_head(self):
        commit = subprocess.run(
            ["git", "-C", str(self.repo), "commit-tree", "HEAD^{tree}", "-p", "HEAD",
             "-m", "private source snapshot fixture"],
            capture_output=True, text=True, check=True).stdout.strip()
        binding = {"path": str(self.state / "synthetic-build.json"), "sha256": "1" * 64}
        self.alignment_packet["source_build"] = binding
        # Build validator itself has separate real-Git fixture coverage.
        with patch("scripts.autonomy.source_build.validate", return_value={"source_commit": commit}):
            self.run_fake(execution_profile="original-os-probe")
            with JobStore(self.state / "jobs.sqlite") as store:
                self.assertEqual(advance_updates(store, self.repo, self.state), ["update-fixture-to-900"])
            successor = json.loads((self.state / "update-packets/update-fixture-to-900.json").read_text())
            self.assertEqual(successor["source_commit"], commit)
            self.assertEqual(successor["source_build"], binding)
            successor["source_commit"] = subprocess.run(
                ["git", "-C", str(self.repo), "rev-parse", "HEAD"],
                capture_output=True, text=True, check=True).stdout.strip()
            with self.assertRaisesRegex(SupervisorError, "source differs"):
                validate(successor, self.repo)

    def test_diagnosis_uses_frozen_build_source_not_current_head(self):
        commit = subprocess.run(
            ["git", "-C", str(self.repo), "commit-tree", "HEAD^{tree}", "-p", "HEAD",
             "-m", "private source snapshot fixture"],
            capture_output=True, text=True, check=True).stdout.strip()
        self.alignment_packet["source_build"] = {
            "path": str(self.state / "synthetic-build.json"), "sha256": "1" * 64}
        with patch("scripts.autonomy.source_build.validate", return_value={"source_commit": commit}):
            self.run_fake("0x00000001", execution_profile="original-os-probe")
            with JobStore(self.state / "jobs.sqlite") as store:
                queued = advance_update_diagnoses(
                    store, self.repo, self.state, Path(self.pin_files["native"]))
                self.assertEqual(queued, ["update-fixture-diagnosis"])
                self.assertEqual(store.job(queued[0])["spec"]["pins"]["source_commit"], commit)
            packet = json.loads((self.state / "packets/update-fixture-diagnosis.json").read_text())
            self.assertEqual(packet["source_commit"], commit)

    def test_completed_original_os_capture_recovers_without_another_replay(self):
        self.run_fake(execution_profile="original-os-probe", crash_after_capture=True)
        with JobStore(self.state / "jobs.sqlite") as store:
            self.assertEqual(store.job("update-fixture")["state"], "verifying")
            store.reclaim_expired(now=time.time() + 1000)
        with patch("scripts.autonomy.update_job.expired_attempt_contained", return_value=True), \
                patch("scripts.autonomy.update_job.bounded_command",
                      side_effect=AssertionError("completed capture must not rerun")):
            outcome = run_once(self.repo, self.state, Path(self.pin_files["native"]),
                               allow_agent=False, job_id="update-fixture")
        self.assertEqual(outcome, "update-fixture: prior update comparison recovered")

    def test_runtime_dependency_change_creates_one_new_rebase(self):
        self.run_fake(execution_profile="original-os-probe")
        (Path(self.pin_files["native"]).parent / "new.dll").write_bytes(b"changed dependency")
        with JobStore(self.state / "jobs.sqlite") as store:
            queued = advance_updates(store, self.repo, self.state)
            self.assertEqual(len(queued), 1)
            self.assertTrue(queued[0].startswith("updates-rebase-"))
            self.assertEqual(advance_updates(store, self.repo, self.state), [])
        packet = json.loads((self.state / "update-packets" / (queued[0] + ".json")).read_text())
        execution.require_current(packet)
        self.assertEqual(packet["native_target"], 600)
        self.assertEqual(packet["execution"]["profile"], "original-os-probe")

    def test_worker_seals_matching_prefix_without_parity_claim(self) -> None:
        outcome, result = self.run_fake()
        self.assertEqual(outcome, "update-fixture: completed-update prefix sealed")
        self.assertTrue(result["prefix_match"])
        self.assertTrue(result["input_prefix_match"])
        self.assertEqual(result["compared_polls"], 1)
        self.assertFalse(result["parity_verified"])
        with JobStore(self.state / "jobs.sqlite") as store:
            self.assertEqual(store.job("update-fixture")["state"], "passed")
            queued = advance_updates(store, self.repo, self.state)
            self.assertEqual(queued, ["update-fixture-to-900"])
            self.assertEqual(advance_updates(store, self.repo, self.state), [])
            extension = store.job("update-fixture-to-900")
            self.assertEqual(extension["spec"]["prerequisites"], ["update-fixture"])
            packet = json.loads((self.state / "update-packets" /
                                 "update-fixture-to-900.json").read_text(encoding="utf-8"))
            self.assertEqual(packet["native_target"], 900)
            self.assertEqual(packet["oracle_target"], 900)

    def test_oracle_ended_resynchronization_queues_one_extension(self) -> None:
        alignment = {
            "kind": "jfg-phase9-update-poll-alignment", "schema": 1,
            "classification": "poll-anchored-semantic-resynchronization",
            "alignment_validated": False, "parity_verified": False,
            "first_raw_mismatch_update": 1,
            "native_suffix_exhausted": False,
            "first_later_mismatch": {"reason": "oracle-stream-ended",
                                     "native_update": 14},
            "matched_update_run": 8,
            "same_poll_anchor": {"controller_polls": 5,
                                 "native_update": 6, "oracle_update": 2},
        }
        _, result = self.run_fake("0x00000001", alignment)
        self.assertFalse(result["prefix_match"])
        self.assertFalse(result["parity_verified"])
        with JobStore(self.state / "jobs.sqlite") as store:
            queued = advance_updates(store, self.repo, self.state)
            self.assertEqual(queued, ["update-fixture-to-900"])
            self.assertEqual(advance_updates(store, self.repo, self.state), [])
            self.assertEqual(store.job(queued[0])["spec"]["prerequisites"],
                             ["update-fixture"])
        packet = json.loads((self.state / "update-packets" /
                             "update-fixture-to-900.json").read_text(
                                 encoding="utf-8"))
        self.assertEqual(packet["native_target"], 900)
        self.assertEqual(packet["oracle_target"], 900)

    def test_worker_seals_unresolved_mismatch_without_expanding(self) -> None:
        outcome, result = self.run_fake("0x00000001")
        self.assertEqual(outcome, "update-fixture: completed-update prefix sealed")
        self.assertFalse(result["prefix_match"])
        self.assertEqual(result["first_divergence"]["update"], 1)
        self.assertEqual(result["alignment_classification"],
                         "unresolved-update-mismatch")
        self.assertFalse(result["parity_verified"])
        with JobStore(self.state / "jobs.sqlite") as store:
            self.assertEqual(advance_updates(store, self.repo, self.state), [])
            queued = advance_update_diagnoses(
                store, self.repo, self.state, Path(self.pin_files["native"]))
            self.assertEqual(queued, ["update-fixture-diagnosis"])
            self.assertEqual(advance_update_diagnoses(
                store, self.repo, self.state, Path(self.pin_files["native"])), [])
            diagnosis = store.job(queued[0])
            self.assertEqual(diagnosis["spec"]["prerequisites"], ["update-fixture"])
        Path(self.pin_files["native"]).write_text("rebuilt-native", encoding="utf-8")
        with JobStore(self.state / "jobs.sqlite") as store:
            queued = advance_updates(store, self.repo, self.state)
            self.assertEqual(len(queued), 1)
            self.assertTrue(queued[0].startswith("updates-rebase-"))
            self.assertEqual(advance_updates(store, self.repo, self.state), [])
            successor = store.job(queued[0])
            self.assertEqual(successor["spec"]["prerequisites"], ["update-fixture"])
            self.assertEqual(successor["spec"]["pins"]["native_sha256"],
                             file_sha256(Path(self.pin_files["native"])))
            packet = json.loads((self.state / "update-packets" /
                                 (queued[0] + ".json")).read_text(encoding="utf-8"))
            self.assertEqual(packet["native_target"], 600)

    def test_later_mismatch_queues_one_bounded_focus_without_model(self) -> None:
        alignment = {
            "kind": "jfg-phase9-update-poll-alignment", "schema": 1,
            "classification": "poll-anchored-semantic-resynchronization",
            "alignment_validated": False, "parity_verified": False,
            "first_raw_mismatch_update": 1,
            "first_later_mismatch": {
                "native_update": 2, "oracle_update": 3,
                "reason": "semantic-mismatch"},
        }
        self.run_fake("0x00000001", alignment)
        with JobStore(self.state / "jobs.sqlite") as store:
            queued = advance_update_focus(store, self.repo, self.state)
            self.assertEqual(queued, ["update-fixture-focus"])
            self.assertEqual(advance_update_focus(store, self.repo, self.state), [])
            focus = store.job(queued[0])
            self.assertEqual(focus["spec"]["prerequisites"], ["update-fixture"])
        packet = json.loads((self.state / "update-packets" /
                             "update-fixture-focus.json").read_text(encoding="utf-8"))
        self.assertEqual(packet["focus_updates"], [1, 3])
        self.assertEqual(packet["focus_pair"], {
            "native_before": 1, "native_after": 2,
            "oracle_before": 2, "oracle_after": 3})
        self.assertEqual(packet["native_target"], 600)
        validate(packet, self.repo)
        packet["focus_updates"] = [1, 17]
        with self.assertRaisesRegex(SupervisorError, "focused update"):
            validate(packet, self.repo)

    def test_moved_focus_does_not_queue_stale_vi_boundary(self) -> None:
        old_alignment = {
            "kind": "jfg-phase9-update-poll-alignment", "schema": 1,
            "classification": "poll-anchored-semantic-resynchronization",
            "alignment_validated": False, "parity_verified": False,
            "first_raw_mismatch_update": 1,
            "first_later_mismatch": {
                "native_update": 2, "oracle_update": 3,
                "reason": "semantic-mismatch"},
        }
        self.run_fake("0x00000001", old_alignment)
        with JobStore(self.state / "jobs.sqlite") as store:
            self.assertEqual(advance_update_focus(store, self.repo, self.state),
                             ["update-fixture-focus"])
            lease = store.lease_job("update-fixture-focus", "test-owner")
            self.assertIsNotNone(lease)
            store.start("update-fixture-focus", lease["token"])
            store.verify("update-fixture-focus", lease["token"])
            attempt = self.state / "attempts" / "update-fixture-focus" / "0001"
            attempt.mkdir(parents=True)
            moved = dict(old_alignment, first_later_mismatch={
                "native_update": 5, "oracle_update": 6,
                "reason": "semantic-mismatch"})
            alignment_path = attempt / "update-alignment.json"
            alignment_path.write_text(json.dumps(moved), encoding="utf-8")
            result_path = attempt / "result.json"
            result_path.write_text(json.dumps({
                "complete": True,
                "oracle_vi_trace_sha256": "0" * 64,
                "focus_comparison_sha256": "0" * 64,
                "alignment_diagnostic_sha256": file_sha256(alignment_path),
            }), encoding="utf-8")
            store.seal_artifact("update-fixture-focus", lease["token"],
                                result_path)
            store.pass_job("update-fixture-focus", lease["token"])
            with patch("scripts.autonomy.scheduler.boundary_tool_sha256",
                       return_value="0" * 64):
                self.assertEqual(advance_vi_boundaries(
                    store, self.repo, self.state), [])



if __name__ == "__main__":
    unittest.main()
