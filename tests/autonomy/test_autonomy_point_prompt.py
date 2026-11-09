import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.autonomy import point_prompt as prompt, point_experiment as points, point_plan
from scripts.autonomy import research_cycle as cycle, interval_experiment
from scripts.autonomy.supervisor import SupervisorError, canonical_bytes, file_sha256


def render(values):
    return "Point planner prose. " + "".join(marker + json.dumps(value) for marker, value in zip(prompt.MARKERS, values)) + "\nDo not claim parity."


class PointPromptTests(unittest.TestCase):
    def test_prompt_validator_is_in_point_and_interval_producer_closures(self):
        helper = Path(prompt.__file__)
        with patch.object(points, "file_sha256", return_value="0" * 64):
            old_point, old_interval = points.tool_sha(), interval_experiment.tool_sha()
        with patch.object(points, "file_sha256", side_effect=lambda path: "1" * 64 if path == helper else "0" * 64):
            self.assertNotEqual(points.tool_sha(), old_point)
            self.assertNotEqual(interval_experiment.tool_sha(), old_interval)

    def test_lossless_nested_tables_preserve_nulls_clocks_order_and_qualification(self):
        rows = [{"update": index, "native": {"vi": index, "raw_ra": "00400260"},
                 "oracle": {"consumed_vi": index + 1, "raw_ra": "ffffffff803011c0"},
                 "prediction_observed": None, "alignment_validated": False,
                 "qualification": {"passed": False, "reasons": ["incompatible raw prefix"]}}
                for index in range(24)]
        values = [{"contract": "fixed"}, {"hypothesis": ' spaces and [brackets] " stay verbatim\n'},
                  {"probe": None}, {"candidates": [], "measurements": rows}]
        saved = copy.deepcopy(values)
        old = render(values)
        compact = prompt.compact(old)
        self.assertLess(len(compact), len(old))
        self.assertEqual(values, saved)
        self.assertEqual([prompt.untabulate(value) for _, _, value in prompt.parts(compact)], values)
        self.assertTrue(compact.endswith("Do not claim parity."))
        self.assertIn(prompt.NOTICE, compact)

    def test_heterogeneous_rows_do_not_invent_missing_values(self):
        value = [{"a": None, "b": 1}, {"b": 2}, {"a": False, "b": 3}]
        self.assertEqual(prompt.untabulate(prompt.tabulate(value)), value)
        self.assertIsInstance(prompt.tabulate(value), list)

    def test_unknown_prompt_and_reserved_fields_fail_closed(self):
        with self.assertRaisesRegex(SupervisorError, "expected evidence"):
            prompt.compact("unknown prompt")
        with self.assertRaisesRegex(SupervisorError, "reserved"):
            prompt.tabulate({prompt.TABLE: "ambiguous"})


class PointPromptRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name)
        self.state = self.repo / "tools/private/autonomy"
        self.state.mkdir(parents=True)
        self.parent_id = "entry"
        self.job_id = points.words.identity("point-plan-", self.parent_id)
        self.directory = self.state / "attempts" / self.job_id / "0001"
        self.directory.mkdir(parents=True)
        self.failure = {"attempt": 1, "candidate_only": True, "complete": False,
                        "job_id": self.job_id, "schema": 1, "stop_reason": prompt.FAILURE}
        self.failure_path = self.directory / "result.json"
        self.failure_path.write_bytes(canonical_bytes(self.failure))
        self.parent = {"plan_id": self.parent_id, "baseline_id": "baseline", "window": [7, 8], "history": [],
                       "diagnosis": {"next_test": "test ordering"}, "plan": {"operation": "needs-instrumentation"}}
        for key in ("plan_seal", "plan_message", "diagnosis_message", "baseline_seal"):
            path = self.state / (key + ".json")
            path.write_text("{}")
            self.parent[key] = path
        binding = self.state / "runtime.json"
        binding.write_text("{}")
        self.runtime = {"binding": points.words.pin(binding)}
        self.contract = point_plan.contract([7, 8], self.runtime["binding"]["sha256"])
        rows = [{"update": index, "native_value": index, "oracle_value": index + 1,
                 "input_prefix_match": True, "prediction_observed": False,
                 "qualification": {"passed": True, "scope": "local-observation-only"},
                 "alignment_validated": False, "parity_verified": False} for index in range(100)]
        self.facts = {"schema": 2, "candidates": [], "measurements": rows}
        facts_path = points.anchor_path(self.state, self.parent_id, history=True)
        facts_path.parent.mkdir()
        facts_path.write_bytes(canonical_bytes(self.facts))
        pins = {}
        for key in ("rom", "emulator", "native"):
            path = self.state / key
            path.write_text(key)
            pins[key] = str(path)
        self.parent["baseline_packet"] = {"source_commit": "2" * 40, "pin_files": pins}
        self.packet = {"schema": 1, "job_id": self.job_id, "kind": "plan-point",
            "source_commit": "2" * 40, "pin_files": pins, "experiment_contract": self.contract,
            "prompt": render([self.contract, self.parent["diagnosis"], self.parent["plan"], self.facts]),
            "timeout_seconds": 180, "validation": [], "prerequisites": [self.parent_id, "baseline"],
            "retry_budget": 0, "allowed_paths": [], "max_changed_files": 0,
            "evidence_files": [points.words.pin(path) for path in (
                self.parent["plan_seal"], self.parent["plan_message"], self.parent["diagnosis_message"],
                self.parent["baseline_seal"], facts_path)] + [self.runtime["binding"]]}
        self.packet_path = self.state / "packets" / (self.job_id + ".json")
        self.packet_path.parent.mkdir()
        self.packet_path.write_bytes(canonical_bytes(self.packet))
        self.job = {"state": "blocked", "attempts": 1, "sealed_artifact": None, "sealed_sha256": None,
            "spec": {"inputs": ["packet:" + hashlib.sha256(canonical_bytes(self.packet)).hexdigest()],
                "prerequisites": self.packet["prerequisites"], "pins": {"source_commit": "2" * 40,
                    **{key + "_sha256": file_sha256(Path(path)) for key, path in pins.items()}}}}
        self.attempt = {"number": 1, "outcome": "blocked", "detail": prompt.FAILURE,
                        "artifact": None, "artifact_sha256": None}
        self.store = MagicMock()
        self.store.job.return_value = self.job
        self.store.attempt_history.return_value = [self.attempt]
        self.store.status_projection.return_value = {"jobs": [{"job_id": self.job_id, "state": "blocked"}]}
        git = patch("scripts.autonomy.supervisor._git_ok", return_value="2" * 40)
        git.start()
        self.addCleanup(git.stop)

    def checked(self):
        return prompt.failed_packet(self.store, self.repo, self.state, self.job_id)

    def test_original_is_immutable_and_replacement_has_all_facts_and_failure_pins(self):
        original = self.packet_path.read_bytes()
        old, new = self.checked()
        self.assertGreater(len(old["prompt"]), prompt.MAX_PROMPT)
        self.assertLessEqual(len(new["prompt"]), prompt.MAX_PROMPT)
        self.assertEqual(new["prerequisites"], old["prerequisites"])
        self.assertNotIn(self.job_id, new["prerequisites"])
        self.assertEqual(new["evidence_files"][-2:], [points.words.pin(self.packet_path), points.words.pin(self.failure_path)])
        self.assertEqual(new["retry_budget"], 0)
        prompt.validate_recovery(self.store, self.repo, self.state, new)
        self.assertEqual(self.packet_path.read_bytes(), original)
        self.assertEqual(self.job["state"], "blocked")

    def test_changed_prompt_or_failure_cannot_be_repinned_into_recovery(self):
        _, packet = self.checked()
        packet["prompt"] += "invented finding"
        with self.assertRaisesRegex(SupervisorError, "differs"):
            prompt.validate_recovery(self.store, self.repo, self.state, packet)
        self.failure_path.write_text(json.dumps({**self.failure, "complete": True}))
        with self.assertRaisesRegex(SupervisorError, "receipt"):
            self.checked()

    def test_any_worker_artifact_or_worktree_disqualifies_recovery(self):
        for name in ("agent.jsonl", "agent.guard.json", "last-message.txt", "prompt.txt"):
            path = self.directory / name
            path.touch()
            with self.subTest(name=name), self.assertRaisesRegex(SupervisorError, "worker activity"):
                self.checked()
            path.unlink()
        (self.state / "worktrees" / self.job_id).mkdir(parents=True)
        with self.assertRaisesRegex(SupervisorError, "worker activity"):
            self.checked()

    def test_other_states_reasons_attempts_and_seals_are_not_retried(self):
        for key, value in (("state", "running"), ("state", "passed"), ("state", "failed"),
                           ("attempts", 2), ("sealed_artifact", "result")):
            saved = self.job[key]
            self.job[key] = value
            with self.subTest(key=key, value=value), self.assertRaisesRegex(SupervisorError, "unused preflight"):
                self.checked()
            self.job[key] = saved
        self.attempt["detail"] = "model timeout"
        with self.assertRaisesRegex(SupervisorError, "unused preflight"):
            self.checked()

    def test_packet_and_input_tampering_fail_before_queue(self):
        self.job["spec"]["inputs"] = ["packet:" + "0" * 64]
        with self.assertRaisesRegex(SupervisorError, "packet/pins"):
            self.checked()
        self.job["spec"]["inputs"] = ["packet:" + hashlib.sha256(canonical_bytes(self.packet)).hexdigest()]
        Path(self.packet["pin_files"]["native"]).write_text("changed")
        with self.assertRaisesRegex(SupervisorError, "packet/pins"):
            self.checked()

    def test_queue_rechecks_full_parent_and_preserves_original(self):
        with patch.object(points.entry_experiment, "plan_context", return_value=self.parent) as parent, \
                patch.object(points.point_runtime, "load", return_value=self.runtime), \
                patch.object(points, "history_facts", return_value=self.facts), \
                patch.object(points, "enqueue_packet") as enqueue:
            result = points.queue_prompt_recovery(self.store, self.repo, self.state, None, self.job_id)
            self.assertEqual(result, self.job_id + prompt.SUFFIX)
            parent.assert_called_once_with(self.store, self.repo, self.state, self.parent_id)
            prompt.validate_recovery(self.store, self.repo, self.state, enqueue.call_args.args[2])
            enqueue.reset_mock()
            self.parent["diagnosis"] = {"next_test": "changed evidence"}
            with self.assertRaisesRegex(SupervisorError, "parent evidence"):
                points.queue_prompt_recovery(self.store, self.repo, self.state, None, self.job_id)
            enqueue.assert_not_called()

    def test_pause_existing_successor_and_no_recursive_recovery(self):
        (self.state / "PAUSED").touch()
        self.assertIsNone(points.queue_prompt_recovery(self.store, self.repo, self.state, None, self.job_id))
        (self.state / "PAUSED").unlink()
        successor = self.job_id + prompt.SUFFIX
        for status in ("queued", "running", "blocked", "failed", "passed"):
            states = {self.job_id: "blocked", successor: status}
            self.store.status_projection.return_value = {"jobs": [{"job_id": key, "state": value} for key, value in states.items()]}
            self.assertEqual(points.preferred_plan_id(states, self.parent_id), successor)
            context = {"entry_plan_id": self.parent_id}
            self.assertTrue(interval_experiment._preferred_point(self.store, context, successor))
            self.assertFalse(interval_experiment._preferred_point(self.store, context, self.job_id))
            self.assertEqual(points.queue_prompt_recovery(self.store, self.repo, self.state, None, self.job_id), successor)
            self.assertIsNone(points.queue_prompt_recovery(self.store, self.repo, self.state, None, successor))

    def test_new_oversize_prompt_rejected_before_packet_publication(self):
        self.store.status_projection.return_value = {"jobs": []}
        self.parent["diagnosis"] = {"next_test": "x" * (prompt.MAX_PROMPT + 1)}
        with patch.object(points.entry_experiment, "plan_context", return_value=self.parent), \
                patch.object(points.point_runtime, "load", return_value=self.runtime), \
                patch.object(points, "history_facts", return_value=self.facts), \
                patch.object(points, "enqueue_packet") as enqueue:
            with self.assertRaisesRegex(SupervisorError, "prompt must"):
                points.queue_plan(self.store, self.repo, self.state, None, self.parent_id)
            enqueue.assert_not_called()

    def test_new_point_plan_uses_lossless_bounded_prompt_and_full_fact_pin(self):
        self.store.status_projection.return_value = {"jobs": []}
        with patch.object(points.entry_experiment, "plan_context", return_value=self.parent), \
                patch.object(points.point_runtime, "load", return_value=self.runtime), \
                patch.object(points, "history_facts", return_value=self.facts), \
                patch.object(points, "enqueue_packet") as enqueue:
            points.queue_plan(self.store, self.repo, self.state, None, self.parent_id)
            packet = enqueue.call_args.args[2]
        self.assertLessEqual(len(packet["prompt"]), prompt.MAX_PROMPT)
        self.assertEqual([prompt.untabulate(value) for _, _, value in prompt.parts(packet["prompt"])],
                         [self.contract, self.parent["diagnosis"], self.parent["plan"], self.facts])
        self.assertIn(points.words.pin(points.anchor_path(self.state, self.parent_id, history=True)), packet["evidence_files"])

    def test_completed_recovery_tail_advances_from_new_id_not_blocked_predecessor(self):
        diagnosis_id = "diagnosis"
        word = points.words.identity("experiment-plan-", diagnosis_id)
        entry = points.words.identity("entry-plan-", word)
        point = points.words.identity("point-plan-", entry)
        recovered = point + prompt.SUFFIX
        self.store.status_projection.return_value = {"jobs": [
            {"job_id": word, "state": "passed"}, {"job_id": entry, "state": "passed"},
            {"job_id": point, "state": "blocked"}, {"job_id": recovered, "state": "passed"}]}
        self.store.job.return_value = {"state": "queued"}
        with patch.object(cycle, "_routing_plan", return_value=({"operation": "needs-instrumentation"}, {})), \
                patch.object(points, "has_anchors", return_value=True), \
                patch.object(interval_experiment, "next_job", return_value="interval") as next_job:
            result = cycle._resume_tail(self.store, self.repo, self.state, None, diagnosis_id)
            self.assertEqual(result["job_id"], "interval")
            next_job.assert_called_once_with(self.store, self.repo, self.state, None, recovered)

    def test_blocked_tail_routes_only_to_recovery_validator(self):
        diagnosis_id = "diagnosis"
        word = points.words.identity("experiment-plan-", diagnosis_id)
        entry = points.words.identity("entry-plan-", word)
        point = points.words.identity("point-plan-", entry)
        self.store.status_projection.return_value = {"jobs": [
            {"job_id": word, "state": "passed"}, {"job_id": entry, "state": "passed"},
            {"job_id": point, "state": "blocked"}]}
        self.store.job.return_value = {"state": "queued"}
        with patch.object(points, "next_job", return_value=point + prompt.SUFFIX) as next_job:
            result = cycle._resume_tail(self.store, self.repo, self.state, None, diagnosis_id)
            self.assertEqual(result["job_id"], point + prompt.SUFFIX)
            self.assertFalse(result["parity_verified"])
            next_job.assert_called_once_with(self.store, self.repo, self.state, None, entry)


if __name__ == "__main__":
    unittest.main()
