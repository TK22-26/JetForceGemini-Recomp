from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

from scripts.autonomy.job_store import JobSpec, JobStore
from scripts.autonomy.candidate_native_retest import (
    TOOL_FILES, build_path, candidate_disposition, expand_command, queue_retest, raw_frontier,
    verified_context, worktree_path,
)
from scripts.autonomy.determinism_job import (
    TOOL_FILES as DETERMINISM_TOOL_FILES, queue_determinism,
)
from scripts.autonomy.poll_pair_job import (
    TOOL_FILES as POLL_PAIR_TOOL_FILES, queue as queue_poll_pair,
)
from scripts.autonomy.poll_lag_job import (
    TOOL_FILES as POLL_LAG_TOOL_FILES, call_phase_available,
)
from scripts.autonomy.candidate_review import _safe_archive_files
from scripts.autonomy.process_guard import real_python_executable
from scripts.autonomy.scheduler import (
    POLL_PAIR_PLAN_TOOLS,
    advance_candidate_reviews, advance_comparisons, advance_determinism,
    advance_diagnoses,
    advance_jobs, advance_poll_pairs, advance_poll_lags,
)
from scripts.autonomy.supervisor import (
    SupervisorError, bounded_command, canonical_bytes, enqueue_packet, file_sha256, no_api_key_env,
    queue_comparison, queue_divergence, read_diagnosis, read_packet,
    bounded_diagnosis_contract, BOUNDED_DIAGNOSIS_SCHEMA_FILE,
    require_chatgpt_login, run_once, tool_identity_sha256, validate_review_receipts,
)
from scripts.phase95_bridge import runtime_digest
from scripts.autonomy import execution_contract as execution


class SupervisorTests(unittest.TestCase):
    def test_expired_agent_budget_preserves_timeout_without_starting_snapshot(self):
        with JobStore(self.state / "jobs.sqlite") as store:
            enqueue_packet(store, self.state, self.packet(), self.fake_agent)
        with patch("scripts.autonomy.supervisor.time.monotonic", return_value=0) as clock, \
                patch("scripts.autonomy.supervisor.snapshot_candidate") as snapshot:
            def timed_out(*args, **kwargs):
                clock.return_value = 31
                return -1, "timeout"
            with patch("scripts.autonomy.supervisor.bounded_command", side_effect=timed_out):
                result = run_once(self.repo, self.state, self.fake_agent, require_auth=False)
        self.assertEqual(result, "candidate-1: failed (timeout)")
        snapshot.assert_not_called()
        saved = json.loads((self.state / "attempts/candidate-1/0001/result.json").read_text())
        self.assertFalse(saved["complete"])
        self.assertEqual(saved["stop_reason"], "timeout")
        self.assertIn("deadline exhausted", saved["candidate_snapshot_error"])
        self.assertNotIn("tracked_patch_sha256", saved)
        with JobStore(self.state / "jobs.sqlite") as store:
            self.assertNotEqual(store.job("candidate-1")["state"], "passed")

    def test_snapshot_failure_does_not_hide_existing_agent_failure(self):
        with JobStore(self.state / "jobs.sqlite") as store:
            enqueue_packet(store, self.state, self.packet(), self.fake_agent)
        with patch("scripts.autonomy.supervisor.bounded_command", return_value=(-1, "log limit")), \
                patch("scripts.autonomy.supervisor.snapshot_candidate", side_effect=SupervisorError("snapshot failed")):
            result = run_once(self.repo, self.state, self.fake_agent, require_auth=False)
        self.assertEqual(result, "candidate-1: failed (log limit)")
        saved = json.loads((self.state / "attempts/candidate-1/0001/result.json").read_text())
        self.assertEqual(saved["stop_reason"], "log limit")
        self.assertEqual(saved["candidate_snapshot_error"], "snapshot failed")
        self.assertFalse(saved["complete"])

    def test_otherwise_successful_agent_still_requires_valid_snapshot(self):
        with JobStore(self.state / "jobs.sqlite") as store:
            enqueue_packet(store, self.state, self.packet(), self.fake_agent)
        with patch("scripts.autonomy.supervisor.bounded_command", return_value=(0, None)), \
                patch("scripts.autonomy.supervisor.snapshot_candidate", side_effect=SupervisorError("snapshot failed")):
            result = run_once(self.repo, self.state, self.fake_agent, require_auth=False)
        self.assertEqual(result, "candidate-1: blocked (snapshot failed)")
        with JobStore(self.state / "jobs.sqlite") as store:
            self.assertEqual(store.job("candidate-1")["state"], "blocked")

    def test_tool_identity_ignores_windows_filename_case(self):
        with tempfile.TemporaryDirectory() as directory:
            upper = Path(directory) / "A" / "TOOL.EXE"
            lower = Path(directory) / "B" / "tool.exe"
            upper.parent.mkdir()
            lower.parent.mkdir()
            upper.write_bytes(b"identical executable")
            lower.write_bytes(b"identical executable")
            self.assertEqual(tool_identity_sha256(upper),
                             tool_identity_sha256(lower))

    def test_call_phase_probe_is_backward_compatible_but_rejects_mixed_traces(self):
        with tempfile.TemporaryDirectory() as directory:
            native = Path(directory) / "native.jsonl"
            oracle = Path(directory) / "oracle.jsonl"
            def write(path, row):
                path.write_text("{}\n" + json.dumps(row) + "\n",
                                encoding="utf-8")
            write(native, {"poll": 0})
            write(oracle, {"poll": 0})
            self.assertFalse(call_phase_available(native, oracle))
            write(native, {"controller_read_start_calls": 1,
                           "controller_get_data_calls": 0})
            with self.assertRaisesRegex(SupervisorError, "mixed"):
                call_phase_available(native, oracle)
            write(oracle, {"controller_read_start_calls": 1})
            with self.assertRaisesRegex(SupervisorError, "partial"):
                call_phase_available(native, oracle)
            write(oracle, {"controller_read_start_calls": 1,
                           "controller_get_data_calls": 0})
            self.assertTrue(call_phase_available(native, oracle))
            with oracle.open("a", encoding="utf-8") as stream:
                stream.write('{"poll":1}\n')
            with self.assertRaisesRegex(SupervisorError, "mixes"):
                call_phase_available(native, oracle)

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.state = self.root / "private"
        for args in (["git", "init", "-q", str(self.repo)],
                     ["git", "-C", str(self.repo), "config", "user.name", "Test"],
                     ["git", "-C", str(self.repo), "config", "user.email", "test@example.com"]):
            subprocess.run(args, check=True, capture_output=True)
        (self.repo / "README.md").write_text("fixture\n", encoding="utf-8")
        (self.repo / "scripts").mkdir()
        shutil.copyfile(Path(__file__).resolve().parents[1] / "scripts" /
                        "compare_phase9_retrace_hashes.py",
                        self.repo / "scripts" / "compare_phase9_retrace_hashes.py")
        for relative in (set(TOOL_FILES) | set(DETERMINISM_TOOL_FILES) |
                         set(POLL_PAIR_TOOL_FILES) | set(POLL_LAG_TOOL_FILES)):
            target = self.repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(__file__).resolve().parents[1] / relative,
                            target)
        subprocess.run(["git", "-C", str(self.repo), "add", "."],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "fixture"],
                       check=True, capture_output=True)
        self.commit = subprocess.check_output(
            ["git", "-C", str(self.repo), "rev-parse", "HEAD"], text=True).strip()
        self.pins = {}
        for key in ("rom", "emulator", "native"):
            path = self.root / (key + ".fixture")
            path.write_text(key, encoding="utf-8")
            self.pins[key] = str(path)
        self.fake_agent = self.root / "fake_agent.py"
        self.fake_agent.write_text(
            "import pathlib, sys\n"
            "prompt = sys.stdin.read()\n"
            "assert 'isolated worktree' in prompt\n"
            "assert 'independent CPU test' in prompt\n"
            "pathlib.Path('candidate.txt').write_text('fixed', encoding='utf-8')\n"
            "print('{}')\n", encoding="utf-8")

    def packet(self, job_id: str = "candidate-1") -> dict:
        return {
            "schema": 1, "job_id": job_id, "kind": "implement",
            "source_commit": self.commit, "pin_files": self.pins,
            "prompt": "Fix the synthetic defect.", "timeout_seconds": 30,
            "validation": [[sys.executable, "-c",
                            "from pathlib import Path; assert Path('candidate.txt').read_text() == 'fixed'"]],
            "prerequisites": [], "retry_budget": 1,
            "allowed_paths": ["candidate.txt"], "max_changed_files": 1,
            "evidence_files": [],
        }

    def queue(self, packet: dict) -> None:
        packet_path = self.root / "packet.json"
        packet_path.write_text(json.dumps(packet), encoding="utf-8")
        parsed = read_packet(packet_path, self.repo)
        with JobStore(self.state / "jobs.sqlite") as store:
            enqueue_packet(store, self.state, parsed, self.fake_agent)

    def seed_update_baseline(self, *, native_target: int = 10,
                             oracle_target: int = 15, execution_profile=None) -> None:
        native_extra, oracle_extra = {}, {}
        if execution_profile is not None:
            # Keep runtime roots separate from the candidate build/worktrees.
            for key in ("native", "emulator"):
                binary = self.root / (key + "-runtime") / (key + ".exe")
                binary.parent.mkdir()
                binary.write_bytes(key.encode())
                self.pins[key] = str(binary)
            (Path(self.pins["emulator"]).parent / "config.ini").write_text(
                json.dumps({"PreferredCores": {"N64": "Mupen64Plus"}}))
            contract = execution.capture(self.pins, execution_profile)
            original = execution_profile == "original-os-probe"
            native_extra = {"execution_profile": execution_profile,
                            "native_runtime_sha256": contract["native_runtime_sha256"],
                            "guest_os_probe": original, "guest_leaf_probe": original,
                            "renderer_writeback_probe": original,
                            "controller_guest_init_probe": False, "si_count_probe": False}
            oracle_extra = {"runtime_sha256": contract["oracle_runtime_sha256"],
                            "config_sha256": contract["oracle_config_sha256"]}
        export = self.repo / "tools" / "private" / "selected-export"
        export.mkdir(parents=True)
        for name in ("controller.input", "initial.flash", "initial.pak"):
            (export / name).write_bytes(name.encode("ascii"))
        (export / "export-manifest.json").write_text(json.dumps({
            "kind": "jfg-phase95-selected-input-export",
            "oracle_final_frame": max(20, oracle_target),
            "controller_polls": 1,
            "input_sha256": file_sha256(export / "controller.input"),
            "initial_state": {
                "flash_sha256": file_sha256(export / "initial.flash"),
                "pak_sha256": file_sha256(export / "initial.pak"),
            },
        }), encoding="utf-8")
        alignment = export / "alignment.json"
        alignment.write_text("{}", encoding="utf-8")
        packet = {
            "schema": 1, "job_id": "baseline-1", "source_commit": self.commit,
            "pin_files": self.pins, "source_export": str(export),
            "alignment_id": "alignment-1", "native_target": native_target,
            "oracle_target": oracle_target, "timeout_seconds": 900,
            "evidence_files": [
                {"path": str(path), "sha256": file_sha256(path)}
                for path in (export / "export-manifest.json",
                             export / "controller.input", export / "initial.flash",
                             export / "initial.pak", alignment)
            ],
        }
        if execution_profile is not None:
            packet["execution"] = contract
        packet_dir = self.state / "update-packets"
        packet_dir.mkdir(parents=True)
        (packet_dir / "baseline-1.json").write_bytes(canonical_bytes(packet))
        packet_sha = hashlib.sha256(canonical_bytes(packet)).hexdigest()
        pins = {"source_commit": self.commit, "tool_sha256": "0" * 64,
                **{key + "_sha256": file_sha256(Path(value))
                   for key, value in self.pins.items()}}
        with JobStore(self.state / "jobs.sqlite") as store:
            store.enqueue(JobSpec("baseline-1", pins,
                                  ("update-packet:" + packet_sha,), (),
                                  "emulator:bizhawk", 0, "json_complete"))
            lease = store.lease_job("baseline-1", "test")
            assert lease is not None
            store.start("baseline-1", lease["token"])
            attempt = self.state / "attempts" / "baseline-1" / "0001"
            native = attempt / "native"
            oracle = attempt / "oracle"
            native.mkdir(parents=True)
            oracle.mkdir()
            native_trace = native / "retrace-hashes.jsonl.updates.jsonl"
            (native / "retrace-hashes.jsonl").write_text(
                "synthetic VI trace", encoding="utf-8")
            oracle_trace = oracle / "update-hashes.jsonl"
            native_result = native / "native-result.json"
            native_result.write_text(json.dumps({
                **native_extra,
                "target_retraces": native_target, "completed_update_count": 8,
                "probe_target_reached": True,
                "completed_update_trace_complete": True,
                "executable_sha256": pins["native_sha256"],
                "input_sha256": file_sha256(export / "controller.input"),
                "initial_flash_sha256": file_sha256(export / "initial.flash"),
                "initial_pak_sha256": file_sha256(export / "initial.pak"),
                "final_state_hash": "a" * 64,
            }), encoding="utf-8")
            native_trace.write_text("native fixture", encoding="utf-8")
            oracle_trace.write_text("oracle fixture", encoding="utf-8")
            oracle_result = oracle / "oracle-result.json"
            oracle_result.write_text(json.dumps({
                **oracle_extra,
                "trace_complete": True,
                "initial_flash_matches_candidate": True,
                "rom_sha256": pins["rom_sha256"],
            }), encoding="utf-8")
            report = attempt / "update-comparison.json"
            report.write_text(json.dumps({
                "kind": "jfg-phase9-update-comparison", "scope": "prefix",
                "match": False, "first_divergence": {"update": 5},
                "requested_updates": 8, "compared_updates": 5,
            }), encoding="utf-8")
            result = attempt / "result.json"
            result.write_text(json.dumps({
                "complete": True, "job_id": "baseline-1", "kind": "update-execution",
                "packet_sha256": packet_sha, "pins": pins,
                "parity_verified": False, "input_prefix_match": True,
                "prefix_match": False, "first_divergence": {"update": 5},
                "native_result_sha256": file_sha256(native_result),
                "oracle_result_sha256": file_sha256(oracle_result),
                "native_trace_sha256": file_sha256(native_trace),
                "oracle_trace_sha256": file_sha256(oracle_trace),
                "comparison_sha256": file_sha256(report),
            }), encoding="utf-8")
            store.verify("baseline-1", lease["token"])
            store.seal_artifact("baseline-1", lease["token"], result)
            store.pass_job("baseline-1", lease["token"])

    def test_reviewed_candidate_queues_local_native_retest(self) -> None:
        self.reviewed_candidate_retest()

    def test_reviewed_candidate_keeps_original_os_profile(self) -> None:
        self.reviewed_candidate_retest(execution_profile="original-os-probe")

    def reviewed_candidate_retest(self, execution_profile=None) -> None:
        self.seed_update_baseline(execution_profile=execution_profile)
        packet = self.packet()
        packet["candidate_build"] = {
            "baseline_update_id": "baseline-1",
            "configure_argv": [str(self.root / "cmake.exe"), "-S", "{source}",
                               "-B", "{build}"],
            "build_argv": [str(self.root / "cmake.exe"), "--build", "{build}"],
            "executable": "Release/jfg-native-boot.exe",
            "build_inputs": [{"path": self.pins["native"],
                              "sha256": file_sha256(Path(self.pins["native"]))}],
            "timeout_seconds": 60,
        }
        self.queue(packet)
        self.assertEqual(run_once(self.repo, self.state, self.fake_agent,
                                  agent_prefix=[sys.executable, str(self.fake_agent)],
                                  require_auth=False), "candidate-1: candidate sealed")
        self.fake_agent.write_text(
            "import json, pathlib, sys\n"
            "sys.stdin.read()\n"
            "pathlib.Path(sys.argv[sys.argv.index('--output-last-message') + 1]).write_text(\n"
            " json.dumps({'verdict': 'approve', 'findings': [], 'confidence': 'medium'}),\n"
            " encoding='utf-8')\n", encoding="utf-8")
        with JobStore(self.state / "jobs.sqlite") as store:
            self.assertEqual(advance_candidate_reviews(
                store, self.repo, self.state, self.fake_agent), ["candidate-1-review"])
        self.assertEqual(run_once(self.repo, self.state, self.fake_agent,
                                  agent_prefix=[sys.executable, str(self.fake_agent)],
                                  require_auth=False),
                         "candidate-1-review: candidate sealed")
        review_attempt = self.state / "attempts/candidate-1-review/0001"
        review_result = json.loads((review_attempt / "result.json").read_text())
        validate_review_receipts(review_result, review_attempt)
        self.assertEqual(len(review_result["candidate_retest_evidence"]), 1)
        self.assertIn("Supervisor validation receipts", (review_attempt / "prompt.txt").read_text())
        with JobStore(self.state / "jobs.sqlite") as store:
            self.assertEqual(advance_jobs(store, self.repo, self.state,
                                          self.fake_agent),
                             ["candidate-1-review-native-retest"])
            self.assertEqual(queue_retest(store, self.repo, self.state,
                                          "candidate-1-review"),
                             "candidate-1-review-native-retest")
            queued = store.job("candidate-1-review-native-retest")
            self.assertEqual(queued["state"], "queued")
            self.assertEqual(queued["spec"]["resource"], "build:native")
            self.assertEqual(queued["spec"]["prerequisites"],
                             ["candidate-1-review", "baseline-1"])
            retest_packet = json.loads((self.state / "candidate-retest-packets" /
                                        "candidate-1-review-native-retest.json").read_text())
            self.assertEqual(retest_packet["target_retraces"], 10)
            self.assertEqual(retest_packet["target_updates"], 8)
            if execution_profile:
                self.assertEqual(retest_packet["execution"]["profile"], execution_profile)
            self.assertIsNotNone(verified_context(
                store, self.repo, self.state, "candidate-1-review"))
        call_count = 0
        executable = (build_path(self.state, "candidate-1-review-native-retest", 1) /
                      "Release" / "jfg-native-boot.exe")

        def fake_bounded(command, cwd, stdout, stderr, deadline, heartbeat,
                         pause_file, **kwargs):
            nonlocal call_count
            call_count += 1
            guard = kwargs["guard_record"]
            guard.write_text('{"state":"finished"}', encoding="utf-8")
            if call_count == 2:
                executable.parent.mkdir(parents=True)
                executable.write_bytes(b"synthetic candidate executable")
            if call_count == 3:
                self.assertEqual(command[command.index("--execution-profile") + 1],
                                 execution_profile or "cooperative")
                runtime_extra = {}
                if execution_profile:
                    runtime_extra = {
                        "execution_profile": execution_profile,
                        "native_runtime_sha256": runtime_digest(executable.parent),
                        "guest_os_probe": True, "guest_leaf_probe": True,
                        "renderer_writeback_probe": True,
                        "controller_guest_init_probe": False, "si_count_probe": False}
                native_dir = (self.state / "attempts" /
                              "candidate-1-review-native-retest" / "0001" / "native")
                native_dir.mkdir()
                manifest = json.loads((Path(retest_packet["source_export"]) /
                                       "export-manifest.json").read_text())
                (native_dir / "retrace-hashes.jsonl.updates.jsonl").write_text(
                    "synthetic trace", encoding="utf-8")
                (native_dir / "controller-polls.tsv").write_text(
                    "synthetic poll", encoding="utf-8")
                (native_dir / "native-result.json").write_text(json.dumps({
                    **runtime_extra,
                    "exit_code": 0, "probe_target_reached": True,
                    "completed_update_trace_complete": True,
                    "completed_update_count": 8,
                    "source_export": retest_packet["source_export"],
                    "target_retraces": 10,
                    "rom_sha256": file_sha256(Path(self.pins["rom"])),
                    "executable_sha256": file_sha256(executable),
                    "input_sha256": manifest["input_sha256"],
                    "initial_flash_sha256":
                        manifest["initial_state"]["flash_sha256"],
                    "initial_pak_sha256": manifest["initial_state"]["pak_sha256"],
                }), encoding="utf-8")
            return 0, None

        def fake_compare(native, oracle, target):
            self.assertEqual(target, 8)
            return {"kind": "jfg-phase9-update-comparison", "schema": 1,
                    "scope": "prefix", "requested_updates": 8,
                    "compared_updates": 7 if "candidate-1-review-native-retest" in str(native) else 5,
                    "match": False,
                    "first_divergence": {"update": 7 if
                                         "candidate-1-review-native-retest" in str(native)
                                         else 5}}

        def fake_poll_compare(source, oracle, native, output, **kwargs):
            report = {"first_input_mismatch": None, "shared_prefix_polls": 1}
            output.write_text(json.dumps(report), encoding="utf-8")
            return report

        with patch("scripts.autonomy.candidate_native_retest.bounded_command",
                   side_effect=fake_bounded), \
             patch("scripts.autonomy.candidate_native_retest.compare",
                   side_effect=fake_compare), \
             patch("scripts.autonomy.candidate_native_retest.compare_polls",
                   side_effect=fake_poll_compare), \
             patch("scripts.autonomy.candidate_native_retest.oracle_polls",
                   return_value=[{}]), \
             patch("scripts.autonomy.candidate_native_retest.native_polls",
                   return_value=[{}]):
            self.assertEqual(run_once(self.repo, self.state, self.fake_agent,
                                      allow_agent=False),
                             "candidate-1-review-native-retest: candidate native diagnostic sealed")
        self.assertEqual(call_count, 3)
        with JobStore(self.state / "jobs.sqlite") as store:
            self.assertEqual(store.job("candidate-1-review-native-retest")["state"],
                             "passed")
        result = json.loads((self.state / "attempts" /
                             "candidate-1-review-native-retest" / "0001" /
                             "result.json").read_text())
        self.assertEqual(result["raw_frontier"]["classification"], "moved-later")
        self.assertFalse(result["parity_verified"])
        self.assertFalse(result["build_closure_verified"])
        with JobStore(self.state / "jobs.sqlite") as store:
            Path(self.pins["rom"]).write_text("changed", encoding="utf-8")
            with self.assertRaises(SupervisorError):
                verified_context(store, self.repo, self.state, "candidate-1-review")

    def test_parallel_native_repeats_seal_without_an_agent(self) -> None:
        self.seed_update_baseline()
        with JobStore(self.state / "jobs.sqlite") as store:
            job_id = queue_determinism(store, self.repo, self.state,
                                       "baseline-1", runs=2, parallelism=2)
            self.assertEqual(queue_determinism(
                store, self.repo, self.state, "baseline-1", runs=2,
                parallelism=2), job_id)
        export = self.repo / "tools" / "private" / "selected-export"
        baseline_native = (self.state / "attempts" / "baseline-1" /
                           "0001" / "native")
        manifest = json.loads((export / "export-manifest.json").read_text())

        def fake_bounded(command, cwd, stdout, stderr, deadline, heartbeat,
                         pause_file, **kwargs):
            output = Path(command[4])
            output.mkdir(parents=True)
            for name in ("retrace-hashes.jsonl",
                         "retrace-hashes.jsonl.updates.jsonl"):
                shutil.copyfile(baseline_native / name, output / name)
            (output / "native-result.json").write_text(json.dumps({
                "exit_code": 0, "probe_target_reached": True,
                "completed_update_trace_complete": True,
                "target_retraces": 10, "completed_update_count": 8,
                "executable_sha256": file_sha256(Path(self.pins["native"])),
                "rom_sha256": file_sha256(Path(self.pins["rom"])),
                "input_sha256": manifest["input_sha256"],
                "initial_flash_sha256": manifest["initial_state"]["flash_sha256"],
                "initial_pak_sha256": manifest["initial_state"]["pak_sha256"],
                "final_state_hash": "a" * 64,
            }), encoding="utf-8")
            kwargs["guard_record"].write_text(
                '{"state":"finished"}', encoding="utf-8")
            return 0, None

        with patch("scripts.autonomy.determinism_job.bounded_command",
                   side_effect=fake_bounded):
            self.assertEqual(run_once(self.repo, self.state, self.fake_agent,
                                      allow_agent=False),
                             job_id + ": 2 native repeats sealed")
        with JobStore(self.state / "jobs.sqlite") as store:
            self.assertEqual(store.job(job_id)["state"], "passed")
        result = json.loads((self.state / "attempts" / job_id / "0001" /
                             "result.json").read_text())
        self.assertTrue(result["deterministic"])
        self.assertEqual(len(result["run_summaries"]), 2)
        self.assertFalse(result["parity_verified"])

        with JobStore(self.state / "jobs.sqlite") as store:
            changed_job = queue_determinism(store, self.repo, self.state,
                                            "baseline-1", runs=3,
                                            parallelism=2)

        def fake_changed(*args, **kwargs):
            outcome = fake_bounded(*args, **kwargs)
            run_dir = Path(args[0][4])
            if run_dir.name == "0003":
                (run_dir / "retrace-hashes.jsonl").write_text(
                    "different VI trace", encoding="utf-8")
            return outcome

        with patch("scripts.autonomy.determinism_job.bounded_command",
                   side_effect=fake_changed), \
             patch("scripts.autonomy.determinism_job.compare_retraces",
                   return_value=({"kind": "jfg-phase9-retrace-comparison",
                                  "match": False,
                                  "first_divergence": {"retrace": 3}}, False)), \
             patch("scripts.autonomy.determinism_job.compare_updates",
                   return_value={"kind": "jfg-phase9-update-comparison",
                                 "match": True}):
            self.assertEqual(run_once(self.repo, self.state, self.fake_agent,
                                      allow_agent=False),
                             changed_job + ": 3 native repeats sealed")
        changed_result = json.loads((self.state / "attempts" / changed_job /
                                     "0001" / "result.json").read_text())
        self.assertFalse(changed_result["deterministic"])
        self.assertEqual(changed_result["first_different_run"], 3)
        self.assertIsNotNone(changed_result["first_difference_sha256"])
        self.assertFalse(changed_result["parity_verified"])

    def test_scheduler_queues_one_current_partial_route_repeat_gate(self) -> None:
        self.seed_update_baseline()
        with JobStore(self.state / "jobs.sqlite") as store:
            queued = advance_determinism(store, self.repo, self.state,
                                         min_retraces=10)
            self.assertEqual(len(queued), 1)
            self.assertEqual(advance_determinism(
                store, self.repo, self.state, min_retraces=10), [])
            job = store.job(queued[0])
            self.assertEqual(job["state"], "queued")
            self.assertEqual(job["spec"]["resource"], "native:determinism")
            packet = json.loads((self.state / "determinism-packets" /
                                 (queued[0] + ".json")).read_text())
            self.assertEqual(packet["runs"], 100)
            self.assertEqual(packet["parallelism"], 4)

    def test_profile_baseline_cannot_fall_back_to_legacy_poll_jobs(self):
        self.seed_update_baseline(native_target=4800, oracle_target=7200,
                                  execution_profile="original-os-probe")
        with JobStore(self.state / "jobs.sqlite") as store:
            self.assertEqual(advance_poll_pairs(store, self.repo, self.state), [])
            with self.assertRaisesRegex(SupervisorError, "strict-update focus"):
                queue_poll_pair(store, self.repo, self.state, "baseline-1")

    def test_poll_pair_successor_is_model_free_and_sealed(self) -> None:
        self.state = self.repo / "tools" / "private" / "autonomy"
        self.seed_update_baseline(native_target=4800, oracle_target=4800)
        with JobStore(self.state / "jobs.sqlite") as store:
            queued = advance_jobs(store, self.repo, self.state, self.fake_agent)
            self.assertEqual(len(queued), 1)
            self.assertEqual(advance_poll_pairs(store, self.repo, self.state), [])
            job = store.job(queued[0])
            self.assertEqual(job["spec"]["resource"], "emulator:bizhawk")
            self.assertEqual(job["spec"]["prerequisites"], ["baseline-1"])
            packet_path = self.state / "poll-pair-packets" / (queued[0] + ".json")
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
            self.assertEqual(packet["target"], 1500)
            self.assertEqual(queue_poll_pair(store, self.repo, self.state,
                                             "baseline-1"), queued[0])

        def fake_bounded(command, cwd, stdout, stderr, deadline, heartbeat,
                         pause_file, **kwargs):
            self.assertEqual(command[1:3], ["-m", "scripts.phase9_poll_semantic_pair"])
            output = self.state / "attempts" / queued[0] / "0001" / "pair"
            for directory in (output, output / "native", output / "oracle"):
                directory.mkdir(parents=True, exist_ok=True)
            for relative in ("native/native-result.json", "oracle/oracle-result.json",
                             "native/retrace-hashes.jsonl.polls.jsonl",
                             "oracle/poll-hashes.jsonl"):
                (output / relative).write_text(
                    "{}\n" + json.dumps({
                        "controller_read_start_calls": 1,
                        "controller_get_data_calls": 0}) + "\n"
                    if relative.endswith(".jsonl") else "{}",
                    encoding="utf-8")
            source = Path(packet["source_export"])
            (output / "plan.json").write_text(json.dumps({
                "source_export": str(source), "target": 1500,
                "source_manifest_sha256": file_sha256(
                    source / "export-manifest.json"),
                "input_sha256": file_sha256(source / "controller.input"),
                "initial_flash_sha256": file_sha256(source / "initial.flash"),
                "initial_pak_sha256": file_sha256(source / "initial.pak"),
                "native_executable_sha256": file_sha256(
                    Path(self.pins["native"])),
                "emulator_sha256": file_sha256(Path(self.pins["emulator"])),
                "emulator_runtime_sha256": runtime_digest(
                    Path(self.pins["emulator"]).parent),
                "rom_sha256": file_sha256(Path(self.pins["rom"])),
                "tool_sha256": {name: file_sha256(self.repo / name)
                                for name in POLL_PAIR_PLAN_TOOLS},
            }), encoding="utf-8")
            (output / "comparison.json").write_text(json.dumps({
                "producer_provenance": {"verified": True},
                "input_prefix_match": True, "state_scan_complete": True,
            }), encoding="utf-8")
            (output / "pair-result.json").write_text(json.dumps({
                "complete": True,
                "comparison_sha256": file_sha256(output / "comparison.json"),
                "native_result_sha256": file_sha256(
                    output / "native" / "native-result.json"),
                "oracle_result_sha256": file_sha256(
                    output / "oracle" / "oracle-result.json"),
            }), encoding="utf-8")
            kwargs["guard_record"].write_text('{"state":"finished"}',
                                                 encoding="utf-8")
            return 0, None

        with (patch("scripts.autonomy.poll_pair_job.bounded_command",
                    side_effect=fake_bounded),
              patch("scripts.autonomy.poll_pair_job.pair.run", return_value={
                  "complete": True, "parity_verified": False,
                  "shared_polls": 659, "first_semantic_mismatch": {"poll": 16},
              })):
            outcome = run_once(self.repo, self.state, self.fake_agent,
                               require_auth=False, allow_agent=False)
        self.assertEqual(outcome, f"{queued[0]}: poll pair sealed")
        with JobStore(self.state / "jobs.sqlite") as store:
            job = store.job(queued[0])
            self.assertEqual(job["state"], "passed")
            result = json.loads(Path(job["sealed_artifact"]).read_text())
            self.assertTrue(result["complete"])
            self.assertFalse(result["alignment_validated"])
            self.assertFalse(result["parity_verified"])
            with patch("scripts.autonomy.scheduler.poll_pair_tool_sha256",
                       return_value="f" * 64):
                self.assertEqual(advance_poll_pairs(
                    store, self.repo, self.state), [])
            with patch("scripts.autonomy.scheduler.advance_poll_pairs",
                       side_effect=AssertionError("must analyze sealed pair first")):
                lag_ids = advance_jobs(store, self.repo, self.state,
                                       self.fake_agent)
            self.assertEqual(len(lag_ids), 1)
            self.assertTrue(lag_ids[0].startswith("poll-lag-"))
            self.assertEqual(advance_poll_lags(store, self.repo, self.state), [])
        pair_root = Path(result["pair_root"])
        with patch("scripts.autonomy.poll_lag_job.analyze", return_value={
                "kind": "jfg-phase9-poll-lag-analysis",
                "comparison_sha256": file_sha256(
                    pair_root / "comparison.json"),
                "compared_polls": 2,
                "mismatching_polls": 3, "unique_shift_match": 2,
                "ambiguous_shift_match": 0, "no_shift_match": 1,
                "alignment_validated": False, "parity_verified": False}), \
             patch("scripts.autonomy.poll_lag_job.analyze_call_phase",
                   return_value={
                       "kind": "jfg-phase9-poll-call-phase",
                       "polls_compared": 2,
                       "native_sha256": file_sha256(pair_root / "native" /
                           "retrace-hashes.jsonl.polls.jsonl"),
                       "oracle_sha256": file_sha256(pair_root / "oracle" /
                           "poll-hashes.jsonl"),
                       "same_call_phase": True, "hooks_observed": True,
                       "alignment_validated": False,
                       "parity_verified": False}):
            outcome = run_once(self.repo, self.state, self.fake_agent,
                               require_auth=False, allow_agent=False)
        self.assertEqual(outcome, f"{lag_ids[0]}: poll-lag report sealed")
        with JobStore(self.state / "jobs.sqlite") as store:
            job = store.job(lag_ids[0])
            self.assertEqual(job["state"], "passed")
            result = json.loads(Path(job["sealed_artifact"]).read_text())
            self.assertEqual(result["unique_shift_match"], 2)
            self.assertTrue(result["same_call_phase"])
            self.assertTrue(result["call_phase_hooks_observed"])
            self.assertFalse(result["alignment_validated"])
            diagnosis_ids = advance_jobs(store, self.repo, self.state,
                                         self.fake_agent)
            self.assertEqual(diagnosis_ids, [lag_ids[0] + "-diagnosis"])
            diagnosis = json.loads((self.state / "packets" /
                                    (diagnosis_ids[0] + ".json")).read_text())
            self.assertEqual(diagnosis["kind"], "diagnose")
            self.assertEqual(diagnosis["allowed_paths"], [])
            self.assertEqual(diagnosis["prerequisites"], lag_ids)
            self.assertTrue(any(item["path"].endswith("call-phase-report.json")
                                for item in diagnosis["evidence_files"]))

    def test_poll_pair_rejects_changed_input_evidence(self) -> None:
        self.seed_update_baseline(native_target=1500, oracle_target=1500)
        with JobStore(self.state / "jobs.sqlite") as store:
            queued = advance_poll_pairs(store, self.repo, self.state)[0]
        export = self.repo / "tools" / "private" / "selected-export"
        (export / "controller.input").write_bytes(b"changed")
        outcome = run_once(self.repo, self.state, self.fake_agent,
                           require_auth=False, allow_agent=False)
        self.assertIn("poll pair blocked", outcome)
        with JobStore(self.state / "jobs.sqlite") as store:
            self.assertEqual(store.job(queued)["state"], "blocked")

    def test_alignment_scheduler_skips_update_diagnosis(self) -> None:
        self.seed_update_baseline()
        packet = self.packet("update-diagnosis")
        packet["kind"] = "diagnose"
        packet["prerequisites"] = ["baseline-1"]
        self.queue(packet)
        with JobStore(self.state / "jobs.sqlite") as store:
            lease = store.lease_job("update-diagnosis", "test")
            assert lease is not None
            store.start("update-diagnosis", lease["token"])
            result = (self.state / "attempts" / "update-diagnosis" / "0001" /
                      "result.json")
            result.parent.mkdir(parents=True)
            result.write_text('{"complete":true}', encoding="utf-8")
            store.verify("update-diagnosis", lease["token"])
            store.seal_artifact("update-diagnosis", lease["token"], result)
            store.pass_job("update-diagnosis", lease["token"])
            self.assertEqual(advance_diagnoses(store, self.repo, self.state), [])

    def test_raw_frontier_never_claims_parity(self) -> None:
        old = {"match": False, "first_divergence": {"update": 5}}
        later = {"match": False, "first_divergence": {"update": 8}}
        report = raw_frontier(old, later, 10)
        self.assertEqual(report["classification"], "moved-later")
        self.assertFalse(report["parity_verified"])
        self.assertFalse(report["alignment_validated"])
        self.assertEqual(raw_frontier(later, old, 10)["classification"],
                         "regressed-earlier")
        self.assertEqual(raw_frontier(old, old, 10)["classification"],
                         "unchanged")
        with self.assertRaises(SupervisorError):
            raw_frontier(old, {"match": False, "first_divergence": None}, 10)

    def test_candidate_disposition_rejects_regressions_without_promoting_parity(self):
        self.assertEqual(candidate_disposition({"classification": "regressed-earlier"}, True),
                         "rejected-regression")
        self.assertEqual(candidate_disposition({"classification": "moved-later"}, False),
                         "rejected-input-mismatch")
        self.assertEqual(candidate_disposition({"classification": "unchanged"}, True),
                         "retained-no-frontier-gain")
        self.assertEqual(candidate_disposition({"classification": "moved-later"}, True),
                         "retained-for-integration-review")
        with self.assertRaises(SupervisorError):
            candidate_disposition({"classification": "passed"}, True)

    def test_review_receipts_reject_changed_logs_and_missing_check(self):
        directory = self.root / "receipt-test"
        directory.mkdir()
        check = {"argv": ["test"], "exit_code": 0, "stop_reason": None}
        receipt = {"check": check}
        for stream in ("stdout", "stderr"):
            path = directory / ("retest-0." + stream)
            path.write_text("passed" if stream == "stdout" else "")
            receipt[stream] = {"path": str(path), "sha256": file_sha256(path)}
        record = {"candidate_retest_validation": [check], "candidate_retest_evidence": [receipt]}
        validate_review_receipts(record, directory)
        with self.assertRaises(SupervisorError):
            validate_review_receipts(dict(record, candidate_retest_evidence=[]), directory)
        (directory / "retest-0.stdout").write_text("changed")
        with self.assertRaisesRegex(SupervisorError, "log receipt changed"):
            validate_review_receipts(record, directory)

    def test_candidate_build_command_expansion_is_bounded(self) -> None:
        self.assertEqual(expand_command(["cmake", "-S", "{source}", "-B", "{build}"],
                                        Path("source"), Path("build")),
                         ["cmake", "-S", "source", "-B", "build"])
        with self.assertRaises(SupervisorError):
            expand_command(["cmake", "{unknown}"], Path("source"), Path("build"))
        self.assertLess(len(str(worktree_path(self.state, "x" * 128, 1))),
                        len(str(self.state / "worktrees" / ("x" * 128) / "0001")))
        self.assertLess(len(str(build_path(self.state, "x" * 128, 1))),
                        len(str(self.state / "attempts" / ("x" * 128) / "0001" /
                                "build")))

    def test_pinned_candidate_seals_without_touching_main_checkout(self) -> None:
        self.queue(self.packet())
        outcome = run_once(self.repo, self.state, self.fake_agent,
                           agent_prefix=[sys.executable, str(self.fake_agent)],
                           require_auth=False)
        self.assertEqual(outcome, "candidate-1: candidate sealed")
        self.assertFalse((self.repo / "candidate.txt").exists())
        result_path = self.state / "attempts" / "candidate-1" / "0001" / "result.json"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertTrue(result["complete"])
        self.assertTrue(result["candidate_only"])
        self.assertTrue(result["requires_independent_review"])
        self.assertEqual(len(result["validation"]), 1)
        self.assertEqual(result["changed_paths"], ["candidate.txt"])
        self.assertEqual(len(result["untracked_zip_sha256"]), 64)
        with JobStore(self.state / "jobs.sqlite") as store:
            self.assertEqual(store.job("candidate-1")["state"], "passed")
            self.assertNotIn("Fix the synthetic defect", json.dumps(store.status_projection()))

    def test_sealed_candidate_gets_independent_read_only_review(self) -> None:
        self.queue(self.packet())
        self.assertEqual(run_once(self.repo, self.state, self.fake_agent,
                                  agent_prefix=[sys.executable, str(self.fake_agent)],
                                  require_auth=False),
                         "candidate-1: candidate sealed")
        self.fake_agent.write_text(
            "import json, pathlib, sys\n"
            "args = sys.argv\n"
            "prompt = sys.stdin.read()\n"
            "assert '--output-schema' in args\n"
            "assert 'reconstructed candidate commit' in prompt\n"
            "assert pathlib.Path('candidate.txt').read_text() == 'fixed'\n"
            "assert 'forced_login_method=\"chatgpt\"' in args\n"
            "pathlib.Path(args[args.index('--output-last-message') + 1]).write_text(\n"
            " json.dumps({'verdict': 'approve', 'findings': [], 'confidence': 'medium'}),\n"
            " encoding='utf-8')\n", encoding="utf-8")
        with JobStore(self.state / "jobs.sqlite") as store:
            self.assertEqual(advance_jobs(
                store, self.repo, self.state, self.fake_agent),
                ["candidate-1-review"])
            self.assertEqual(advance_candidate_reviews(
                store, self.repo, self.state, self.fake_agent), [])
        self.assertEqual(run_once(self.repo, self.state, self.fake_agent,
                                  agent_prefix=[sys.executable, str(self.fake_agent)],
                                  require_auth=False),
                         "candidate-1-review: candidate sealed")
        result_path = self.state / "attempts" / "candidate-1-review" / "0001" / "result.json"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertTrue(result["complete"])
        self.assertTrue(result["candidate_only"])
        self.assertFalse(result["requires_independent_review"])
        self.assertEqual(len(result["candidate_commit"]), 40)
        self.assertEqual(len(result["review_sha256"]), 64)
        self.assertEqual(result["changed_paths"], [])
        self.assertEqual(len(result["candidate_retest_validation"]), 1)
        self.assertEqual(result["candidate_retest_validation"][0]["exit_code"], 0)
        self.assertFalse((self.repo / "candidate.txt").exists())
        with JobStore(self.state / "jobs.sqlite") as store:
            self.assertEqual(store.job("candidate-1-review")["state"], "passed")

    def test_tampered_candidate_cannot_queue_review(self) -> None:
        self.queue(self.packet())
        run_once(self.repo, self.state, self.fake_agent,
                 agent_prefix=[sys.executable, str(self.fake_agent)],
                 require_auth=False)
        result_path = self.state / "attempts" / "candidate-1" / "0001" / "result.json"
        result_path.write_text(result_path.read_text(encoding="utf-8") + " ",
                               encoding="utf-8")
        with JobStore(self.state / "jobs.sqlite") as store:
            with self.assertRaisesRegex(SupervisorError, "seal is invalid"):
                advance_candidate_reviews(store, self.repo, self.state,
                                          self.fake_agent)
            self.assertNotIn("candidate-1-review",
                             {job["job_id"] for job in store.status_projection()["jobs"]})

    def test_review_reconstructs_tracked_patch(self) -> None:
        packet = self.packet()
        packet["allowed_paths"] = ["README.md"]
        packet["validation"] = [[sys.executable, "-c",
                                 "from pathlib import Path; assert Path('README.md').read_text() == 'fixed\\n'"]]
        self.fake_agent.write_text(
            "import pathlib, sys\n"
            "sys.stdin.read()\n"
            "pathlib.Path('README.md').write_text('fixed\\n', encoding='utf-8')\n",
            encoding="utf-8")
        self.queue(packet)
        self.assertEqual(run_once(self.repo, self.state, self.fake_agent,
                                  agent_prefix=[sys.executable, str(self.fake_agent)],
                                  require_auth=False),
                         "candidate-1: candidate sealed")
        self.fake_agent.write_text(
            "import json, pathlib, sys\n"
            "sys.stdin.read()\n"
            "assert pathlib.Path('README.md').read_text() == 'fixed\\n'\n"
            "args = sys.argv\n"
            "pathlib.Path(args[args.index('--output-last-message') + 1]).write_text(\n"
            " json.dumps({'verdict': 'reject', 'findings': ['Missing regression'],\n"
            " 'confidence': 'high'}), encoding='utf-8')\n", encoding="utf-8")
        with JobStore(self.state / "jobs.sqlite") as store:
            advance_candidate_reviews(store, self.repo, self.state, self.fake_agent)
        self.assertEqual(run_once(self.repo, self.state, self.fake_agent,
                                  agent_prefix=[sys.executable, str(self.fake_agent)],
                                  require_auth=False),
                         "candidate-1-review: candidate sealed")
        self.assertEqual((self.repo / "README.md").read_text(), "fixture\n")
        review_path = self.state / "attempts" / "candidate-1-review" / "0001" / "last-message.txt"
        self.assertEqual(json.loads(review_path.read_text())["verdict"], "reject")

    def test_malformed_review_fails_closed(self) -> None:
        self.queue(self.packet())
        run_once(self.repo, self.state, self.fake_agent,
                 agent_prefix=[sys.executable, str(self.fake_agent)],
                 require_auth=False)
        self.fake_agent.write_text(
            "import json, pathlib, sys\n"
            "sys.stdin.read()\n"
            "args = sys.argv\n"
            "pathlib.Path(args[args.index('--output-last-message') + 1]).write_text(\n"
            " json.dumps({'verdict': ['approve'], 'findings': [], 'confidence': 'low'}),\n"
            " encoding='utf-8')\n", encoding="utf-8")
        with JobStore(self.state / "jobs.sqlite") as store:
            advance_candidate_reviews(store, self.repo, self.state, self.fake_agent)
        self.assertIn("blocked", run_once(
            self.repo, self.state, self.fake_agent,
            agent_prefix=[sys.executable, str(self.fake_agent)], require_auth=False))
        with JobStore(self.state / "jobs.sqlite") as store:
            self.assertEqual(store.job("candidate-1-review")["state"], "blocked")

    def test_review_does_not_start_when_reconstructed_candidate_fails_retest(self) -> None:
        packet = self.packet()
        packet["validation"] = [[sys.executable, "-c",
                                 "from pathlib import Path; "
                                 "assert Path('candidate.txt').read_text() == 'fixed'; "
                                 "assert 'candidate-1-review' not in str(Path.cwd())"]]
        self.queue(packet)
        self.assertEqual(run_once(self.repo, self.state, self.fake_agent,
                                  agent_prefix=[sys.executable, str(self.fake_agent)],
                                  require_auth=False),
                         "candidate-1: candidate sealed")
        with JobStore(self.state / "jobs.sqlite") as store:
            advance_candidate_reviews(store, self.repo, self.state, self.fake_agent)
        outcome = run_once(self.repo, self.state, self.fake_agent,
                           agent_prefix=[sys.executable, str(self.fake_agent)],
                           require_auth=False)
        self.assertIn("candidate retest failed", outcome)
        attempt = self.state / "attempts" / "candidate-1-review" / "0001"
        self.assertFalse((attempt / "agent.guard.json").exists())
        result = json.loads((attempt / "result.json").read_text())
        self.assertFalse(result["complete"])
        self.assertNotEqual(result["candidate_retest_validation"][0]["exit_code"], 0)

    def test_candidate_archive_rejects_traversal(self) -> None:
        archive_path = self.root / "unsafe.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("../candidate.txt", "unsafe")
        with zipfile.ZipFile(archive_path) as archive:
            with self.assertRaisesRegex(SupervisorError, "unsafe path"):
                _safe_archive_files(archive, {"../candidate.txt"})

    def test_pin_drift_blocks_before_agent_launch(self) -> None:
        self.queue(self.packet())
        Path(self.pins["rom"]).write_text("changed", encoding="utf-8")
        outcome = run_once(self.repo, self.state, self.fake_agent,
                           agent_prefix=[sys.executable, str(self.fake_agent)],
                           require_auth=False)
        self.assertIn("blocked", outcome)
        self.assertFalse((self.state / "worktrees" / "candidate-1").exists())
        with JobStore(self.state / "jobs.sqlite") as store:
            self.assertEqual(store.job("candidate-1")["state"], "blocked")

    def test_bounded_evidence_list_supports_focused_diagnosis(self) -> None:
        evidence = self.root / "evidence.json"
        evidence.write_text("{}\n", encoding="utf-8")
        packet = self.packet()
        pin = {"path": str(evidence), "sha256": file_sha256(evidence)}
        packet["evidence_files"] = [pin] * 12
        packet_path = self.root / "packet.json"
        packet_path.write_text(json.dumps(packet), encoding="utf-8")
        self.assertEqual(len(read_packet(packet_path, self.repo)["evidence_files"]), 12)
        packet["evidence_files"].append(pin)
        packet_path.write_text(json.dumps(packet), encoding="utf-8")
        with self.assertRaisesRegex(SupervisorError, "short list"):
            read_packet(packet_path, self.repo)

    def test_out_of_scope_change_cannot_seal(self) -> None:
        packet = self.packet()
        packet["allowed_paths"] = ["src/"]
        self.queue(packet)
        outcome = run_once(self.repo, self.state, self.fake_agent,
                           agent_prefix=[sys.executable, str(self.fake_agent)],
                           require_auth=False)
        self.assertIn("outside packet scope", outcome)
        with JobStore(self.state / "jobs.sqlite") as store:
            self.assertEqual(store.job("candidate-1")["state"], "blocked")

    def test_pause_prevents_leasing(self) -> None:
        self.queue(self.packet())
        (self.state / "PAUSED").write_text("pause", encoding="utf-8")
        self.assertEqual(run_once(self.repo, self.state, self.fake_agent,
                                  require_auth=False), "paused")
        with JobStore(self.state / "jobs.sqlite") as store:
            self.assertEqual(store.job("candidate-1")["state"], "queued")

    def test_named_run_leases_exact_queued_packet(self) -> None:
        self.queue(self.packet("candidate-1"))
        self.queue(self.packet("candidate-2"))
        self.assertEqual(run_once(self.repo, self.state, self.fake_agent,
                                  agent_prefix=[sys.executable, str(self.fake_agent)],
                                  require_auth=False, job_id="candidate-2"),
                         "candidate-2: candidate sealed")
        with JobStore(self.state / "jobs.sqlite") as store:
            self.assertEqual(store.job("candidate-1")["state"], "queued")
            self.assertEqual(store.job("candidate-2")["state"], "passed")

    def test_named_agent_respects_zero_agent_cap(self) -> None:
        self.queue(self.packet())
        with self.assertRaisesRegex(SupervisorError, "disabled by the current cap"):
            run_once(self.repo, self.state, self.fake_agent,
                     require_auth=False, allow_agent=False,
                     job_id="candidate-1")
        with JobStore(self.state / "jobs.sqlite") as store:
            self.assertEqual(store.job("candidate-1")["state"], "queued")

    def test_expired_worktree_blocks_second_writer(self) -> None:
        self.queue(self.packet())
        with JobStore(self.state / "jobs.sqlite") as store:
            lease = store.lease_next("crashed-worker", ttl=10, now=1)
            assert lease is not None
            store.start("candidate-1", lease["token"], now=2)
            store.reclaim_expired(now=12)
        (self.state / "worktrees" / "candidate-1" / "0001").mkdir(parents=True)
        outcome = run_once(self.repo, self.state, self.fake_agent,
                           agent_prefix=[sys.executable, str(self.fake_agent)],
                           require_auth=False)
        self.assertIn("manual recovery needed", outcome)
        self.assertFalse((self.state / "worktrees" / "candidate-1" / "0002").exists())
        with JobStore(self.state / "jobs.sqlite") as store:
            self.assertEqual(store.job("candidate-1")["state"], "blocked")

    @unittest.skipUnless(os.name == "nt", "Windows crash guard recovery only")
    def test_expired_complete_candidate_is_sealed_without_second_agent(self) -> None:
        packet = self.packet()
        self.queue(packet)
        with JobStore(self.state / "jobs.sqlite") as store:
            first = store.lease_job("candidate-1", "crashed", now=1, ttl=10)
            assert first is not None
            store.start("candidate-1", first["token"], now=2)
            store.reclaim_expired(now=12)
            spec = store.job("candidate-1")["spec"]
        (self.state / "worktrees" / "candidate-1" / "0001").mkdir(parents=True)
        prior = self.state / "attempts" / "candidate-1" / "0001"
        prior.mkdir(parents=True)
        (prior / "agent.guard.json").write_text(
            json.dumps({"schema": 1, "state": "finished", "owner_pid": 99999999}),
            encoding="utf-8")
        (prior / "tracked.patch").write_bytes(b"")
        with zipfile.ZipFile(prior / "untracked.zip", "w") as archive:
            archive.writestr("candidate.txt", "fixed")
        (prior / "result.json").write_text(json.dumps({
            "schema": 1, "complete": True, "candidate_only": True,
            "job_id": "candidate-1", "packet_sha256": spec["inputs"][0].split(":", 1)[1],
            "pins": spec["pins"], "source_commit": packet["source_commit"],
            "agent_exit_code": 0, "stop_reason": None,
            "changed_paths": ["candidate.txt"],
            "validation": [{"argv": packet["validation"][0],
                            "exit_code": 0, "stop_reason": None}],
            "requires_independent_review": True,
            "tracked_patch_sha256": file_sha256(prior / "tracked.patch"),
            "untracked_zip_sha256": file_sha256(prior / "untracked.zip"),
        }), encoding="utf-8")
        self.assertEqual(run_once(self.repo, self.state, self.fake_agent,
                                  agent_prefix=[sys.executable, str(self.fake_agent)],
                                  require_auth=False),
                         "candidate-1: prior candidate recovered")
        self.assertFalse((self.state / "worktrees" / "candidate-1" / "0002").exists())
        with JobStore(self.state / "jobs.sqlite") as store:
            self.assertEqual(store.job("candidate-1")["state"], "passed")
            self.assertEqual(store.job("candidate-1")["attempts"], 2)

    @unittest.skipUnless(os.name == "nt", "Windows crash guard recovery only")
    def test_hard_killed_supervisor_retries_without_duplicate_completion(self) -> None:
        self.fake_agent.write_text(
            "import pathlib, sys, time\n"
            "sys.stdin.read()\n"
            "if pathlib.Path.cwd().name == '0001': time.sleep(30)\n"
            "else: pathlib.Path('candidate.txt').write_text('fixed')\n",
            encoding="utf-8")
        self.queue(self.packet())
        parent_code = (
            "from pathlib import Path\n"
            "import sys\n"
            "from scripts.autonomy.supervisor import run_once\n"
            "from scripts.autonomy.process_guard import real_python_executable\n"
            "run_once(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), "
            "agent_prefix=[real_python_executable(), sys.argv[3]], require_auth=False)\n"
        )
        parent = subprocess.Popen(
            [real_python_executable(), "-c", parent_code,
             str(self.repo), str(self.state), str(self.fake_agent)],
            cwd=str(Path(__file__).resolve().parents[1]),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            guard = self.state / "attempts" / "candidate-1" / "0001" / "agent.guard.json"
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if guard.is_file() and json.loads(guard.read_text()).get("state") == "guarded":
                    break
                time.sleep(0.05)
            else:
                result = guard.parent / "result.json"
                detail = result.read_text() if result.is_file() else "no result artifact"
                self.fail(f"first agent was never guarded (parent={parent.poll()}): {detail}")
            parent.kill()
            parent.wait(timeout=5)
            with JobStore(self.state / "jobs.sqlite") as store:
                lease_until = store.job("candidate-1")["lease_until"]
                store.reclaim_expired(now=lease_until + 1)
            outcome = run_once(self.repo, self.state, self.fake_agent,
                               agent_prefix=[real_python_executable(), str(self.fake_agent)],
                               require_auth=False)
            self.assertEqual(outcome, "candidate-1: candidate sealed")
            self.assertTrue((self.state / "worktrees" / "candidate-1" / "0001").exists())
            with JobStore(self.state / "jobs.sqlite") as store:
                self.assertEqual(store.job("candidate-1")["state"], "passed")
                self.assertEqual([item["outcome"] for item in
                                  store.attempt_history("candidate-1")],
                                 ["expired", "passed"])
        finally:
            if parent.poll() is None:
                parent.kill()
                parent.wait(timeout=5)

    def test_rejects_missing_validation_for_implementation(self) -> None:
        packet = self.packet()
        packet["validation"] = []
        packet_path = self.root / "invalid.json"
        packet_path.write_text(json.dumps(packet), encoding="utf-8")
        with self.assertRaisesRegex(SupervisorError, "require validation"):
            read_packet(packet_path, self.repo)

    def test_implementation_rejects_pinned_oracle_semantics_conflict(self) -> None:
        artifact = self.root / "adjudication.json"
        artifact.write_text(json.dumps({
            "kind": "jfg-phase9-cpu-rounding-adjudication",
            "disposition": "mupen_oracle_semantics_conflict",
            "observed_integers": {"Mupen64Plus": 559, "Ares64": 558},
        }), encoding="utf-8")
        packet = self.packet()
        packet["evidence_files"] = [{"path": str(artifact),
                                     "sha256": file_sha256(artifact)}]
        path = self.root / "conflict-implementation.json"
        path.write_text(json.dumps(packet), encoding="utf-8")
        with self.assertRaisesRegex(SupervisorError, "CPU semantics conflict"):
            read_packet(path, self.repo)
        packet["kind"] = "diagnose"
        packet["validation"] = []
        packet["allowed_paths"] = []
        packet["max_changed_files"] = 0
        path.write_text(json.dumps(packet), encoding="utf-8")
        self.assertEqual(read_packet(path, self.repo)["kind"], "diagnose")

    def test_candidate_build_recipe_is_explicit_and_pinned(self) -> None:
        manifest = self.root / "generated-closure.json"
        manifest.write_text("{}\n", encoding="utf-8")
        packet = self.packet()
        packet["candidate_build"] = {
            "baseline_update_id": "sealed-baseline",
            "configure_argv": ["cmake", "-S", "{source}", "-B", "{build}"],
            "build_argv": ["cmake", "--build", "{build}", "--target", "jfg-native-boot"],
            "executable": "Release/jfg-native-boot.exe",
            "build_inputs": [{"path": str(manifest), "sha256": file_sha256(manifest)}],
            "timeout_seconds": 1200,
        }
        path = self.root / "candidate-build-packet.json"
        path.write_text(json.dumps(packet), encoding="utf-8")
        self.assertEqual(read_packet(path, self.repo)["candidate_build"],
                         packet["candidate_build"])
        packet["candidate_build"]["executable"] = "../jfg.exe"
        path.write_text(json.dumps(packet), encoding="utf-8")
        with self.assertRaisesRegex(SupervisorError, "relative to private build"):
            read_packet(path, self.repo)
        packet["candidate_build"]["executable"] = "Release/jfg-native-boot.exe"
        manifest.write_text("changed\n", encoding="utf-8")
        path.write_text(json.dumps(packet), encoding="utf-8")
        with self.assertRaisesRegex(SupervisorError, "input changed"):
            read_packet(path, self.repo)

    def test_child_env_strips_api_keys(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sentinel",
                                     "CODEX_API_KEY": "sentinel"}):
            environment = no_api_key_env()
        self.assertNotIn("OPENAI_API_KEY", environment)
        self.assertNotIn("CODEX_API_KEY", environment)

    def test_agent_preflight_requires_chatgpt_even_with_api_key_present(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sentinel"}), \
                patch("scripts.autonomy.supervisor.subprocess.run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = "Logged in using API key"
            run.return_value.stderr = ""
            with self.assertRaisesRegex(SupervisorError, "signed in with ChatGPT"):
                require_chatgpt_login(self.fake_agent)
            self.assertNotIn("OPENAI_API_KEY", run.call_args.kwargs["env"])

    def test_agent_auth_failure_blocks_before_worktree_creation(self) -> None:
        self.queue(self.packet())
        with patch("scripts.autonomy.supervisor.require_chatgpt_login",
                   side_effect=SupervisorError("Codex CLI is not signed in with ChatGPT")):
            outcome = run_once(self.repo, self.state, self.fake_agent,
                               agent_prefix=[sys.executable, str(self.fake_agent)])
        self.assertIn("blocked", outcome)
        self.assertFalse((self.state / "worktrees" / "candidate-1").exists())
        with JobStore(self.state / "jobs.sqlite") as store:
            self.assertEqual(store.job("candidate-1")["state"], "blocked")

    def test_diagnosis_rejects_unaligned_code_claim(self) -> None:
        diagnosis = {
            "classification": "code_divergence", "alignment": "unvalidated",
            "first_supported_retrace": 12, "evidence": ["actor count differs"],
            "hypothesis": "actor allocation differs", "next_test": "align polls",
            "confidence": "medium",
        }
        path = self.root / "diagnosis.json"
        path.write_text(json.dumps(diagnosis), encoding="utf-8")
        with self.assertRaisesRegex(SupervisorError, "requires aligned"):
            read_diagnosis(path)
        diagnosis["classification"] = "capture_misalignment"
        path.write_text(json.dumps(diagnosis), encoding="utf-8")
        self.assertEqual(read_diagnosis(path)["classification"],
                         "capture_misalignment")

    def test_diagnosis_worker_seals_structured_output(self) -> None:
        packet = self.packet("structured-diagnosis")
        packet.update(kind="diagnose", validation=[], allowed_paths=[],
                      max_changed_files=0)
        self.fake_agent.write_text(
            "import json, pathlib, sys\n"
            "args = sys.argv\n"
            "assert '--output-schema' in args\n"
            "assert 'forced_login_method=\"chatgpt\"' in args\n"
            "assert 'isolated worktree' in sys.stdin.read()\n"
            "output = pathlib.Path(args[args.index('--output-last-message') + 1])\n"
            "output.write_text(json.dumps({\n"
            " 'classification': 'capture_misalignment', 'alignment': 'unvalidated',\n"
            " 'first_supported_retrace': 1, 'evidence': ['poll mismatch'],\n"
            " 'hypothesis': 'capture starts at different polls',\n"
            " 'next_test': 'compare first controller polls', 'confidence': 'medium'\n"
            "}), encoding='utf-8')\n",
            encoding="utf-8")
        self.queue(packet)
        outcome = run_once(self.repo, self.state, self.fake_agent,
                           agent_prefix=[sys.executable, str(self.fake_agent)],
                           require_auth=False)
        self.assertEqual(outcome, "structured-diagnosis: candidate sealed")
        attempt = self.state / "attempts" / "structured-diagnosis" / "0001"
        result = json.loads((attempt / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["diagnosis_sha256"],
                         file_sha256(attempt / "last-message.txt"))
        self.assertFalse(result["requires_independent_review"])

    def test_bounded_format_worker_uses_pinned_schema_and_preserves_evidence(self) -> None:
        original = {"classification": "insufficient_evidence", "alignment": "unvalidated",
                    "first_supported_retrace": None, "confidence": "medium",
                    "evidence": ["observed"], "hypothesis": "unproved", "next_test": "x" * 1001}
        source = self.root / "original-diagnosis.json"
        source.write_text(json.dumps(original))
        pin = {"path": str(source), "sha256": file_sha256(source)}
        packet = self.packet("bounded-format")
        packet.update(kind="diagnose", validation=[], allowed_paths=[], max_changed_files=0,
                      diagnosis_contract=bounded_diagnosis_contract(), diagnosis_format_source=pin,
                      evidence_files=[pin])
        self.fake_agent.write_text(
            "import json, pathlib, sys\n"
            "assert '1-1000 characters' in sys.stdin.read()\n"
            "assert pathlib.Path(sys.argv[sys.argv.index('--output-schema')+1]).name == 'diagnosis.bounded-v2.schema.json'\n"
            f"report=json.loads(pathlib.Path({str(source)!r}).read_text())\n"
            "report['next_test']='Same test, compactly described.'\n"
            "pathlib.Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_text(json.dumps(report))\n")
        self.queue(packet)
        outcome = run_once(self.repo, self.state, self.fake_agent,
                           agent_prefix=[sys.executable, str(self.fake_agent)], require_auth=False)
        self.assertEqual(outcome, "bounded-format: candidate sealed")
        attempt = self.state / "attempts/bounded-format/0001"
        result = json.loads((attempt / "result.json").read_text())
        self.assertEqual(result["diagnosis_schema_sha256"], file_sha256(BOUNDED_DIAGNOSIS_SCHEMA_FILE))
        self.assertEqual(read_diagnosis(attempt / "last-message.txt")["evidence"], original["evidence"])
        source.write_text("changed")
        with self.assertRaisesRegex(SupervisorError, "evidence file"):
            read_packet(self.state / "packets/bounded-format.json", self.repo)

    def test_experiment_planner_is_read_only_and_seals_typed_proposal(self):
        from scripts.autonomy.experiment_plan import contract, SCHEMA_FILE
        packet = self.packet("experiment-plan")
        packet.update(kind="plan-experiment", validation=[], allowed_paths=[], max_changed_files=0,
                      experiment_contract=contract([7, 10]))
        proposal = {"operation": "state-words", "hypothesis": "step differs", "alternative": "other input differs",
                    "reason": "read before state onset", "observations": [
                        {"label": "step", "address": "0x80000004", "width": 4}],
                    "prediction": {"label": "step", "update": 8, "relation": "different"}}
        self.fake_agent.write_text(
            "import pathlib,sys\n"
            "sys.stdin.read()\n"
            "assert sys.argv[sys.argv.index('-s')+1] == 'read-only'\n"
            "assert pathlib.Path(sys.argv[sys.argv.index('--output-schema')+1]).name == 'experiment.schema.json'\n"
            f"pathlib.Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_text({json.dumps(proposal)!r})\n")
        self.queue(packet)
        self.assertEqual(run_once(self.repo, self.state, self.fake_agent,
                                 agent_prefix=[sys.executable, str(self.fake_agent)], require_auth=False),
                         "experiment-plan: candidate sealed")
        attempt = self.state / "attempts/experiment-plan/0001"
        result = json.loads((attempt / "result.json").read_text())
        self.assertEqual(result["experiment_plan_sha256"], file_sha256(attempt / "last-message.txt"))
        self.assertEqual(result["experiment_schema_sha256"], file_sha256(SCHEMA_FILE))
        self.assertEqual(result["changed_paths"], [])
        self.assertFalse(result["requires_independent_review"])

    def test_entry_planner_is_read_only_and_selects_its_own_schema(self):
        from scripts.autonomy.entry_plan import contract, SCHEMA_FILE
        packet = self.packet("entry-plan")
        packet.update(kind="plan-entry", validation=[], allowed_paths=[], max_changed_files=0,
                      experiment_contract=contract([7, 10]))
        proposal = {"operation": "entry-gpr", "hypothesis": "argument differs", "alternative": "argument equal",
                    "reason": "observe consumer entry", "probe": {"entry_pc": "0x80000200", "call_pc": "0x80000100"},
                    "prediction": {"update": 8, "register": 5, "relation": "different"}}
        self.fake_agent.write_text(
            "import pathlib,sys\n"
            "sys.stdin.read()\n"
            "assert sys.argv[sys.argv.index('-s')+1] == 'read-only'\n"
            "assert pathlib.Path(sys.argv[sys.argv.index('--output-schema')+1]).name == 'entry_plan.schema.json'\n"
            f"pathlib.Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_text({json.dumps(proposal)!r})\n")
        self.queue(packet)
        self.assertEqual(run_once(self.repo, self.state, self.fake_agent,
                                 agent_prefix=[sys.executable, str(self.fake_agent)], require_auth=False),
                         "entry-plan: candidate sealed")
        attempt = self.state / "attempts/entry-plan/0001"
        result = json.loads((attempt / "result.json").read_text())
        self.assertEqual(result["experiment_plan_sha256"], file_sha256(attempt / "last-message.txt"))
        self.assertEqual(result["experiment_schema_sha256"], file_sha256(SCHEMA_FILE))
        self.assertEqual(result["changed_paths"], [])

    def test_point_planner_uses_read_only_typed_schema(self):
        from scripts.autonomy.point_plan import contract, SCHEMA_FILE
        packet = self.packet("point-plan")
        packet.update(kind="plan-point", validation=[], allowed_paths=[], max_changed_files=0,
                      experiment_contract=contract([7,10],"1"*64))
        proposal = {"operation":"point-state","hypothesis":"extra receive","alternative":"equal count","reason":"count events",
                    "probe":{"entry_pc":"0x80000200","call_pc":"0x80000100","pcs":["0x80000200","0x80000108"],"words":["0x800a9e90"]},
                    "prediction":{"kind":"event-count","pc":"0x80000200","update":8,"occurrence":None,"register":None,"address":None,"relation":"equal"}}
        self.fake_agent.write_text(
            "import pathlib,sys\n"
            "sys.stdin.read()\n"
            "assert sys.argv[sys.argv.index('-s')+1] == 'read-only'\n"
            "assert pathlib.Path(sys.argv[sys.argv.index('--output-schema')+1]).name == 'point_plan.schema.json'\n"
            f"pathlib.Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_text({json.dumps(proposal)!r})\n")
        self.queue(packet)
        self.assertEqual(run_once(self.repo,self.state,self.fake_agent,
            agent_prefix=[sys.executable,str(self.fake_agent)],require_auth=False),"point-plan: candidate sealed")
        attempt=self.state/"attempts/point-plan/0001"
        result=json.loads((attempt/"result.json").read_text())
        self.assertEqual(result["experiment_schema_sha256"],file_sha256(SCHEMA_FILE))
        self.assertEqual(result["changed_paths"],[])

    def test_point_prompt_preflight_recovery_launches_only_one_read_only_worker(self):
        from scripts.autonomy import point_prompt
        from scripts.autonomy.point_plan import contract
        packet = self.packet("point-preflight")
        rows = [{"update": index, "native_value": index, "oracle_value": index + 1,
                 "alignment_validated": False, "parity_verified": False,
                 "qualification_scope": "instruction observation only, not causal proof"}
                for index in range(160)]
        payloads = [contract([7, 10], "1" * 64), {"next_test": "ordering"},
                    {"operation": "needs-instrumentation"}, {"measurements": rows}]
        packet.update(kind="plan-point", validation=[], allowed_paths=[], max_changed_files=0,
                      retry_budget=0, experiment_contract=payloads[0],
                      prompt="".join(marker + json.dumps(value) for marker, value in zip(point_prompt.MARKERS, payloads)))
        proposal = {"operation": "needs-instrumentation", "hypothesis": "A", "alternative": "B",
                    "reason": "device ordering is outside this primitive", "probe": None, "prediction": None}
        self.fake_agent.write_text(
            "import pathlib,sys\n"
            "text=sys.stdin.read()\n"
            "assert '$point_rows' in text\n"
            "assert sys.argv[sys.argv.index('-s')+1] == 'read-only'\n"
            f"pathlib.Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_text({json.dumps(proposal)!r})\n")
        with JobStore(self.state / "jobs.sqlite") as store:
            enqueue_packet(store, self.state, packet, self.fake_agent)
        with patch("scripts.autonomy.supervisor.bounded_command") as launch:
            self.assertEqual(run_once(self.repo, self.state, self.fake_agent, require_auth=False),
                             "point-preflight: blocked (" + point_prompt.FAILURE + ")")
            launch.assert_not_called()
        original_bytes = (self.state / "packets/point-preflight.json").read_bytes()
        with JobStore(self.state / "jobs.sqlite") as store:
            _, replacement = point_prompt.failed_packet(store, self.repo, self.state, "point-preflight")
            enqueue_packet(store, self.state, replacement, self.fake_agent)
        new_id = "point-preflight" + point_prompt.SUFFIX
        self.assertEqual(run_once(self.repo, self.state, self.fake_agent,
            agent_prefix=[sys.executable, str(self.fake_agent)], require_auth=False, job_id=new_id),
            new_id + ": candidate sealed")
        with JobStore(self.state / "jobs.sqlite") as store:
            self.assertEqual(store.job("point-preflight")["state"], "blocked")
            self.assertEqual(store.job(new_id)["state"], "passed")
            self.assertEqual(store.job(new_id)["attempts"], 1)
        self.assertEqual((self.state / "packets/point-preflight.json").read_bytes(), original_bytes)

    def test_timeout_stops_child(self) -> None:
        code, reason = bounded_command(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            self.root, self.root / "out.txt", self.root / "err.txt",
            time.monotonic() + 0.5, lambda: None, self.root / "PAUSED")
        self.assertNotEqual(code, 0)
        self.assertEqual(reason, "timeout")

    def test_disk_reserve_stops_before_child_launch(self) -> None:
        marker = self.root / "launched.txt"
        code, reason = bounded_command(
            [sys.executable, "-c", "from pathlib import Path; "
             f"Path({str(marker)!r}).write_text('launched')"],
            self.root, self.root / "disk-out.txt", self.root / "disk-err.txt",
            time.monotonic() + 10, lambda: None, self.root / "PAUSED",
            minimum_free_bytes=shutil.disk_usage(self.root).free + 1)
        self.assertEqual((code, reason), (-1, "disk reserve"))
        self.assertFalse(marker.exists())

    def test_output_tree_limit_stops_guarded_child(self) -> None:
        tree = self.root / "bounded-tree"
        tree.mkdir()
        command = ("from pathlib import Path; import time; "
                   "Path('bounded-tree/blob').write_bytes(bytes(4096)); "
                   "time.sleep(10)")
        code, reason = bounded_command(
            [sys.executable, "-c", command], self.root,
            self.root / "tree-out.txt", self.root / "tree-err.txt",
            time.monotonic() + 8, lambda: None, self.root / "PAUSED",
            output_tree=tree, max_output_tree_bytes=1024)
        self.assertNotEqual(code, 0)
        self.assertEqual(reason, "output tree limit")

    def test_guarded_environment_rejects_nonvisual_override(self) -> None:
        with self.assertRaisesRegex(ValueError, "environment overrides"):
            bounded_command(
                [sys.executable, "-c", "pass"], self.root,
                self.root / "env-out.txt", self.root / "env-err.txt",
                time.monotonic() + 5, lambda: None, self.root / "PAUSED",
                environment_overrides={"OPENAI_API_KEY": "must-not-forward"})

    def test_divergence_intake_queues_read_only_diagnosis(self) -> None:
        header = {"kind": "jfg-phase9-retrace-hash-header", "schema": 1}
        record = {
            "kind": "jfg-phase9-retrace-hash", "schema": 1, "retrace": 1,
            "front_mode": 0, "actor_count": 0, "rng_seed": "0x00000000",
            "player_actor": "0x00000000", "actor_list": "0x00000000",
            "player_sha256": None, "actor_table_sha256": None,
            "globals_sha256": "0" * 64, "camera_sha256": "1" * 64,
            "actors": [],
        }
        native = self.root / "native.jsonl"
        oracle = self.root / "oracle.jsonl"
        native.write_text(json.dumps(header) + "\n" + json.dumps(record) + "\n",
                          encoding="utf-8")
        oracle.write_text(json.dumps(header) + "\n" +
                          json.dumps(dict(record, rng_seed="0x00000001")) + "\n",
                          encoding="utf-8")
        with JobStore(self.state / "jobs.sqlite") as store:
            report = queue_divergence(
                store, self.repo, self.state, self.fake_agent,
                job_id="first-rng", native_trace=native, oracle_trace=oracle,
                oracle_offset=0, pin_files=self.pins, timeout_seconds=30)
            self.assertEqual(report["first_divergence"]["retrace"], 1)
            self.assertEqual(store.job("first-rng")["state"], "queued")
        packet = json.loads((self.state / "packets" / "first-rng.json").read_text())
        self.assertEqual(packet["kind"], "diagnose")
        self.assertEqual(packet["max_changed_files"], 0)
        self.assertEqual(len(packet["evidence_files"]), 3)
        oracle.write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(SupervisorError, "evidence file"):
            read_packet(self.state / "packets" / "first-rng.json", self.repo)

    def test_queued_comparison_seals_mismatch_without_claiming_parity(self) -> None:
        header = {"kind": "jfg-phase9-retrace-hash-header", "schema": 1}
        record = {
            "kind": "jfg-phase9-retrace-hash", "schema": 1, "retrace": 1,
            "front_mode": 0, "actor_count": 0, "rng_seed": "0x00000000",
            "player_actor": "0x00000000", "actor_list": "0x00000000",
            "player_sha256": None, "actor_table_sha256": None,
            "globals_sha256": "0" * 64, "camera_sha256": "1" * 64,
            "actors": [],
        }
        native = self.root / "native.jsonl"
        oracle = self.root / "oracle.jsonl"
        native.write_text(json.dumps(header) + "\n" + json.dumps(record) + "\n",
                          encoding="utf-8")
        oracle.write_text(json.dumps(header) + "\n" +
                          json.dumps(dict(record, rng_seed="0x00000001")) + "\n",
                          encoding="utf-8")
        with JobStore(self.state / "jobs.sqlite") as store:
            queue_comparison(store, self.repo, self.state,
                             job_id="cmp-first-rng", native_trace=native,
                             oracle_trace=oracle, oracle_offset=0,
                             pin_files=self.pins, timeout_seconds=30)
        self.assertEqual(run_once(self.repo, self.state, self.fake_agent,
                                  require_auth=False),
                         "cmp-first-rng: raw comparison sealed")
        result = json.loads((self.state / "attempts" / "cmp-first-rng" / "0001" /
                             "result.json").read_text(encoding="utf-8"))
        self.assertTrue(result["complete"])
        self.assertFalse(result["match"])
        self.assertEqual(result["first_raw_divergence_retrace"], 1)
        self.assertFalse(result["alignment_validated"])
        self.assertFalse(result["parity_verified"])

        with JobStore(self.state / "jobs.sqlite") as store:
            queued = advance_comparisons(
                store, self.repo, self.state, self.fake_agent)
            self.assertEqual(queued, ["cmp-first-rng-diagnosis"])
            self.assertEqual(advance_comparisons(
                store, self.repo, self.state, self.fake_agent), [])
            self.assertEqual(store.job("cmp-first-rng-diagnosis")["state"], "queued")
        diagnosis_packet = json.loads((self.state / "packets" /
                                       "cmp-first-rng-diagnosis.json").read_text())
        self.assertEqual(diagnosis_packet["prerequisites"], ["cmp-first-rng"])
        self.assertEqual(diagnosis_packet["source_commit"], self.commit)
        self.assertEqual(diagnosis_packet["kind"], "diagnose")

    def test_scheduler_rejects_tampered_comparison(self) -> None:
        header = {"kind": "jfg-phase9-retrace-hash-header", "schema": 1}
        record = {
            "kind": "jfg-phase9-retrace-hash", "schema": 1, "retrace": 1,
            "front_mode": 0, "actor_count": 0, "rng_seed": "0x00000000",
            "player_actor": "0x00000000", "actor_list": "0x00000000",
            "player_sha256": None, "actor_table_sha256": None,
            "globals_sha256": "0" * 64, "camera_sha256": "1" * 64,
            "actors": [],
        }
        native = self.root / "native.jsonl"
        oracle = self.root / "oracle.jsonl"
        native.write_text(json.dumps(header) + "\n" + json.dumps(record) + "\n",
                          encoding="utf-8")
        oracle.write_text(json.dumps(header) + "\n" +
                          json.dumps(dict(record, rng_seed="0x00000001")) + "\n",
                          encoding="utf-8")
        with JobStore(self.state / "jobs.sqlite") as store:
            queue_comparison(store, self.repo, self.state,
                             job_id="cmp-tampered", native_trace=native,
                             oracle_trace=oracle, oracle_offset=0,
                             pin_files=self.pins, timeout_seconds=30)
        self.assertEqual(run_once(self.repo, self.state, self.fake_agent,
                                  require_auth=False),
                         "cmp-tampered: raw comparison sealed")
        report = self.state / "attempts" / "cmp-tampered" / "0001" / "comparison.json"
        report.write_text("{}", encoding="utf-8")
        with JobStore(self.state / "jobs.sqlite") as store:
            with self.assertRaisesRegex(SupervisorError, "bundle is inconsistent"):
                advance_comparisons(store, self.repo, self.state, self.fake_agent)
            self.assertFalse((self.state / "packets" /
                              "cmp-tampered-diagnosis.json").exists())

    @unittest.skipUnless(os.name == "nt", "Windows crash guard recovery only")
    def test_expired_complete_comparison_is_sealed_without_rerun(self) -> None:
        native = self.root / "native.jsonl"
        oracle = self.root / "oracle.jsonl"
        native.write_text("native", encoding="utf-8")
        oracle.write_text("oracle", encoding="utf-8")
        with JobStore(self.state / "jobs.sqlite") as store:
            queue_comparison(store, self.repo, self.state,
                             job_id="cmp-recover", native_trace=native,
                             oracle_trace=oracle, oracle_offset=0,
                             pin_files=self.pins, timeout_seconds=30)
            first = store.lease_job("cmp-recover", "crashed", now=1, ttl=10)
            assert first is not None
            store.start("cmp-recover", first["token"], now=2)
            store.reclaim_expired(now=12)
            pins = store.job("cmp-recover")["spec"]["pins"]
            packet_sha = store.job("cmp-recover")["spec"]["inputs"][0].split(":", 1)[1]
        prior = self.state / "attempts" / "cmp-recover" / "0001"
        prior.mkdir(parents=True)
        report = {"kind": "jfg-phase9-retrace-comparison", "schema": 1,
                  "match": False, "first_divergence": {"retrace": 1}}
        (prior / "comparison.json").write_text(json.dumps(report), encoding="utf-8")
        (prior / "comparator.guard.json").write_text(
            json.dumps({"schema": 1, "state": "finished", "owner_pid": 99999999}),
            encoding="utf-8")
        (prior / "result.json").write_text(json.dumps({
            "schema": 1, "complete": True, "kind": "comparison-execution",
            "job_id": "cmp-recover", "packet_sha256": packet_sha,
            "comparison_sha256": file_sha256(prior / "comparison.json"),
            "match": False, "alignment_validated": False,
            "parity_verified": False, "pins": pins,
        }), encoding="utf-8")
        self.assertEqual(run_once(self.repo, self.state, self.fake_agent,
                                  require_auth=False),
                         "cmp-recover: prior comparison recovered")
        self.assertFalse((self.state / "attempts" / "cmp-recover" / "0002" /
                          "comparison.json").exists())
        with JobStore(self.state / "jobs.sqlite") as store:
            self.assertEqual(store.job("cmp-recover")["state"], "passed")
            self.assertEqual(store.job("cmp-recover")["attempts"], 2)


if __name__ == "__main__":
    unittest.main()
