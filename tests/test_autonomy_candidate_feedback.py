import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.autonomy import candidate_feedback as feedback
from scripts.autonomy.candidate_native_retest import candidate_disposition, raw_frontier
from scripts.autonomy.job_store import JobSpec, JobStore
from scripts.autonomy.supervisor import SupervisorError, canonical_bytes, file_sha256


class CandidateFeedbackTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        self.state = self.repo / "state"
        self.state.mkdir()
        self.store = JobStore(self.state / "jobs.sqlite")
        self.addCleanup(self.store.close)
        self.pins = {"source_commit": "a" * 40, "tool_sha256": "b" * 64,
                     "rom_sha256": "c" * 64, "emulator_sha256": "d" * 64,
                     "native_sha256": "e" * 64}
        self.directory = self.state / "attempts/retest/0001"
        self.directory.mkdir(parents=True)
        self.baseline = self.write("baseline.json", {"complete": True})
        self.review = self.write("review.json", {"complete": True})
        self.old_trace = self.write("old.jsonl", {"trace": "baseline"})
        self.oracle_trace = self.write("oracle.jsonl", {"trace": "oracle"})
        self.implementation = {"job_id": "implementation", "source_commit": "a" * 40,
                               "pin_files": {"native": "frozen"}}
        self.write("packets/implementation.json", self.implementation)
        implementation_seal = self.write("attempts/implementation/0001/result.json",
                                         {"complete": True, "job_id": "implementation"})
        self.write("attempts/implementation/0001/tracked.patch", {"patch": "fixture"})
        self.seal("implementation", "packet:fixture", implementation_seal)
        self.context = {
            "baseline_id": "baseline", "candidate_commit": "f" * 40, "recipe": {},
            "baseline_packet": {"pin_files": self.implementation["pin_files"],
                                "source_export": "export", "native_target": 20},
            "baseline_update_count": 8, "baseline_seal": self.baseline,
            "review_seal": self.review, "native_trace": self.old_trace,
            "oracle_trace": self.oracle_trace, "implementation_packet": self.implementation}
        self.packet = {"job_id": "retest", "review_id": "review", "baseline_update_id": "baseline",
                       "candidate_commit": "f" * 40, "recipe": {},
                       "pin_files": self.implementation["pin_files"], "source_export": "export",
                       "target_retraces": 20, "target_updates": 8,
                       "baseline_result_sha256": file_sha256(self.baseline),
                       "review_result_sha256": file_sha256(self.review),
                       "native_trace_sha256": file_sha256(self.old_trace),
                       "oracle_trace_sha256": file_sha256(self.oracle_trace)}
        self.write("candidate-retest-packets/retest.json", self.packet)
        self.baseline_report = {"kind": "jfg-phase9-update-comparison", "scope": "prefix",
                                "requested_updates": 8, "match": False,
                                "first_divergence": {"update": 5}}
        self.candidate_report = copy.deepcopy(self.baseline_report)
        self.polls = {"kind": "jfg-phase95-input-poll-comparison", "scope": "prefix",
                      "requested_polls": 10, "shared_prefix_polls": 10, "first_input_mismatch": None}
        self.result = {"kind": "candidate-native-update-retest", "complete": True, "job_id": "retest",
                       "candidate_commit": "f" * 40, "candidate_only": True,
                       "alignment_validated": False, "parity_verified": False,
                       "packet_sha256": hashlib.sha256(canonical_bytes(self.packet)).hexdigest(),
                       "pins": self.pins}
        self.validate = patch.object(feedback, "validate")
        self.validate.start()
        self.addCleanup(self.validate.stop)
        self.verified = patch.object(feedback, "verified_context", return_value=self.context)
        self.verified.start()
        self.addCleanup(self.verified.stop)

    def write(self, relative, payload):
        path = self.state / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(canonical_bytes(payload))
        return path

    def seal(self, job_id, input_identity, path, prerequisites=()):
        pins = dict(self.pins)
        if job_id == "retest":
            pins["source_commit"] = "f" * 40
        self.store.enqueue(JobSpec(job_id, pins, (input_identity,), prerequisites,
                                   "fixture", 0, "json_complete"))
        # These tests independently cover sealed outcome validation; review lineage
        # itself is covered by the candidate/review integration tests.
        lease = self.store.lease_job(job_id, "test", ttl=60)
        self.store.start(job_id, lease["token"])
        self.store.verify(job_id, lease["token"])
        self.store.seal_artifact(job_id, lease["token"], path)
        self.store.pass_job(job_id, lease["token"])

    def prepare(self, *, tamper_result=None):
        data = {"comparison_sha256": ("candidate-comparison.json", self.candidate_report),
                "baseline_comparison_sha256": ("baseline-comparison.json", self.baseline_report),
                "input_poll_comparison_sha256": ("input-poll-comparison.json", self.polls),
                "native_trace_sha256": ("native/retrace-hashes.jsonl.updates.jsonl", {"trace": "baseline"}),
                "native_result_sha256": ("native/native-result.json", {"complete": True})}
        for key, (relative, payload) in data.items():
            path = self.write("attempts/retest/0001/" + relative, payload)
            self.result[key] = file_sha256(path)
        frontier = raw_frontier(self.baseline_report, self.candidate_report, 8)
        self.result.update(raw_frontier=frontier, input_prefix_match=self.polls["first_input_mismatch"] is None,
                           compared_polls=self.polls["shared_prefix_polls"])
        self.result["pins"] = dict(self.pins, source_commit="f" * 40)
        self.result["candidate_disposition"] = candidate_disposition(frontier, self.result["input_prefix_match"])
        if tamper_result:
            self.result.update(tamper_result)
        sealed = self.write("attempts/retest/0001/result.json", self.result)
        # Create sealed dummy predecessors solely for real ledger prerequisites.
        for predecessor in ("review", "baseline"):
            path = self.write(f"attempts/{predecessor}/0001/result.json",
                              {"complete": True, "job_id": predecessor})
            self.seal(predecessor, "fixture", path)
        self.seal("retest", "candidate-retest-packet:" + self.result["packet_sha256"],
                  sealed, ("review", "baseline"))

    def checked(self):
        return feedback.checked_outcome(self.store, self.repo, self.state, "retest")

    def test_unchanged_result_keeps_baseline_and_records_actual_trace_equality(self):
        self.prepare()
        facts, implementation, evidence = self.checked()
        self.assertEqual(facts["disposition"], "retained-no-frontier-gain")
        self.assertTrue(facts["candidate_update_trace_equals_baseline"])
        self.assertFalse(facts["candidate_promoted"])
        self.assertEqual(implementation["source_commit"], "a" * 40)
        self.assertEqual(len(evidence), 11)
        self.assertIn("competing hypotheses", feedback.task_for(facts))

    def test_fresh_context_handoff_preserves_legacy_facts_without_duplicate_review(self):
        self.prepare()
        with patch.object(feedback, "verified_context", return_value=self.context) as verify:
            expanded = feedback.checked_outcome_context(self.store, self.repo, self.state, "retest")
            verify.assert_called_once()
            self.assertIs(expanded[3], self.context)
            # A separate call is a new check, not a cache hit.
            legacy = self.checked()
            self.assertEqual(verify.call_count, 2)
        self.assertEqual(expanded[:3], legacy)

    def test_context_handoff_does_not_reuse_a_previous_supporting_file_check(self):
        self.prepare()
        feedback.checked_outcome_context(self.store, self.repo, self.state, "retest")
        (self.directory / "native/retrace-hashes.jsonl.updates.jsonl").write_text("changed")
        with self.assertRaisesRegex(SupervisorError, "supporting evidence"):
            feedback.checked_outcome_context(self.store, self.repo, self.state, "retest")

    def test_regression_is_research_not_an_implementation_retry(self):
        self.candidate_report["first_divergence"]["update"] = 3
        self.prepare()
        facts, _, _ = self.checked()
        self.assertEqual(facts["disposition"], "rejected-regression")
        self.assertIn("violated invariant", feedback.task_for(facts))

    def test_input_failure_takes_precedence_over_later_raw_frontier(self):
        self.candidate_report["first_divergence"]["update"] = 7
        self.polls["first_input_mismatch"] = {"poll": 2}
        self.prepare()
        facts, _, _ = self.checked()
        self.assertEqual(facts["disposition"], "rejected-input-mismatch")
        self.assertIn("Input equivalence failed", feedback.task_for(facts))

    def test_later_frontier_requires_integration_evidence_not_promotion(self):
        self.candidate_report["first_divergence"]["update"] = 7
        self.prepare()
        facts, _, _ = self.checked()
        self.assertIn("has not been promoted", feedback.task_for(facts))
        self.assertFalse(facts["parity_verified"])

    def test_sealed_disposition_cannot_contradict_evidence(self):
        self.prepare(tamper_result={"candidate_disposition": "retained-for-integration-review"})
        with self.assertRaisesRegex(SupervisorError, "contradicts"):
            self.checked()

    def test_tampered_supporting_trace_fails_before_queue(self):
        self.prepare()
        (self.directory / "native/retrace-hashes.jsonl.updates.jsonl").write_text("changed")
        with self.assertRaisesRegex(SupervisorError, "supporting evidence"), \
                patch.object(feedback, "enqueue_packet") as enqueue:
            feedback.queue_feedback(self.store, self.repo, self.state, None, "retest")
        enqueue.assert_not_called()

    def test_candidate_cannot_change_baseline_provenance(self):
        self.prepare()
        self.context["baseline_id"] = "unrelated"
        with self.assertRaisesRegex(SupervisorError, "lineage"):
            self.checked()

    def test_packet_is_read_only_and_queue_is_idempotent_across_restart(self):
        self.prepare()
        captured = []
        def enqueue(store, state, packet, agent):
            captured.append(packet)
            store.enqueue(JobSpec(packet["job_id"], self.pins, ("packet:fixture",),
                                  tuple(packet["prerequisites"]), "agent", 1, "json_complete"))
        with patch.object(feedback, "enqueue_packet", side_effect=enqueue):
            first = feedback.advance(self.store, self.repo, self.state, None)
            with JobStore(self.state / "jobs.sqlite") as reopened:
                second = feedback.advance(reopened, self.repo, self.state, None)
        self.assertEqual(first, [feedback.feedback_id("retest")])
        self.assertEqual(second, [])
        packet = captured[0]
        self.assertEqual(packet["kind"], "diagnose")
        self.assertEqual(packet["allowed_paths"], [])
        self.assertEqual(packet["validation"], [])
        self.assertEqual(packet["max_changed_files"], 0)
        self.assertEqual(packet["source_commit"], "a" * 40)
        self.assertEqual(len(packet["evidence_files"]), 12)

    def test_crash_between_fact_write_and_enqueue_resumes_same_packet(self):
        self.prepare()
        with patch.object(feedback, "enqueue_packet", side_effect=RuntimeError("killed")):
            with self.assertRaisesRegex(RuntimeError, "killed"):
                feedback.queue_feedback(self.store, self.repo, self.state, None, "retest")
        path = self.state / "candidate-feedback" / (feedback.feedback_id("retest") + ".json")
        before = path.read_bytes()
        with patch.object(feedback, "enqueue_packet"):
            feedback.queue_feedback(self.store, self.repo, self.state, None, "retest")
        self.assertEqual(path.read_bytes(), before)
        path.write_text("{}")
        with self.assertRaisesRegex(SupervisorError, "immutable facts"):
            feedback.queue_feedback(self.store, self.repo, self.state, None, "retest")

    def test_pause_and_budgets_prevent_work(self):
        for budget in (0, 17, True):
            with self.assertRaises(SupervisorError):
                feedback.advance(None, None, None, None, max_new_jobs=budget)
        (self.state / "PAUSED").touch()
        with patch.object(feedback, "checked_outcome") as checked:
            self.assertEqual(feedback.advance(self.store, self.repo, self.state, None), [])
            self.assertIsNone(feedback.queue_feedback(self.store, self.repo, self.state, None, "retest"))
            checked.assert_not_called()

    def test_scheduler_prioritizes_feedback_before_another_frontier_search(self):
        from scripts.autonomy.scheduler import advance_jobs
        with patch("scripts.autonomy.scheduler.advance_candidate_reviews", return_value=[]), \
                patch("scripts.autonomy.scheduler.advance_candidate_retests", return_value=[]), \
                patch("scripts.autonomy.branch_count_repair.advance", return_value=[]), \
                patch.object(feedback, "advance", return_value=["new-feedback"]) as transition, \
                patch("scripts.autonomy.scheduler.queue_frontier_next") as frontier:
            self.assertEqual(advance_jobs(self.store, self.repo, self.state, None), ["new-feedback"])
            transition.assert_called_once()
            frontier.assert_not_called()

    def test_legacy_length_failure_gets_one_format_only_recovery(self):
        self.prepare()
        original_id = feedback.feedback_id("retest")
        packet = {"job_id": original_id, "kind": "diagnose", "prerequisites": ["retest", "baseline"],
                  "source_commit": "a" * 40, "allowed_paths": [], "max_changed_files": 0,
                  "validation": [], "evidence_files": []}
        self.write("packets/" + original_id + ".json", packet)
        self.store.enqueue(JobSpec(original_id, self.pins,
                                   ("packet:" + hashlib.sha256(canonical_bytes(packet)).hexdigest(),),
                                   ("retest", "baseline"), "agent", 1, "json_complete"))
        lease = self.store.lease_job(original_id, "test", ttl=60)
        reason = "diagnosis needs a bounded hypothesis and next test"
        self.store.fail_job(original_id, lease["token"], reason, blocked=True)
        self.write(f"attempts/{original_id}/0001/result.json",
                   {"job_id": original_id, "complete": False, "stop_reason": reason})
        raw = {"classification": "insufficient_evidence", "alignment": "unvalidated",
               "first_supported_retrace": None, "confidence": "medium", "evidence": ["observed"],
               "hypothesis": "unproved", "next_test": "x" * 1001}
        original_path = self.write(f"attempts/{original_id}/0001/last-message.txt", raw)
        before = original_path.read_bytes()
        queued = []
        def enqueue(store, state, successor, agent):
            queued.append(successor)
            store.enqueue(JobSpec(successor["job_id"], self.pins, ("packet:fixture",),
                                  tuple(successor["prerequisites"]), "agent", 0, "json_complete"))
        with patch.object(feedback, "read_packet", return_value=packet), \
                patch.object(feedback, "enqueue_packet", side_effect=enqueue):
            first = feedback.queue_format_recovery(self.store, self.repo, self.state, None, original_id)
            second = feedback.queue_format_recovery(self.store, self.repo, self.state, None, original_id)
        self.assertEqual(first, original_id + "-format-v2")
        self.assertIsNone(second)
        self.assertEqual(self.store.job(original_id)["state"], "blocked")
        self.assertEqual(original_path.read_bytes(), before)
        self.assertEqual(queued[0]["retry_budget"], 0)
        self.assertEqual(queued[0]["timeout_seconds"], 120)
        self.assertEqual(queued[0]["diagnosis_contract"]["version"], 2)
        self.assertEqual(queued[0]["diagnosis_format_source"]["sha256"], file_sha256(original_path))
        self.assertIn("Do not reinvestigate", queued[0]["prompt"])


if __name__ == "__main__":
    unittest.main()
