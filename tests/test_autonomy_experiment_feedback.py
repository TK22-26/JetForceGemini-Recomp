import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.autonomy import experiment_feedback as feedback, state_word_experiment as experiment
from scripts.autonomy.job_store import JobSpec, JobStore
from scripts.autonomy.supervisor import SupervisorError, canonical_bytes, file_sha256


class ExperimentFeedbackTests(unittest.TestCase):
    """Real ledger/seal tests; source/capture adapters are isolated fixtures."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        self.state = self.repo / "state"
        self.state.mkdir()
        self.store = JobStore(self.state / "jobs.sqlite")
        self.addCleanup(self.store.close)
        pin_files = {key: str(self.write(key, {"fixture": key})) for key in ("rom", "emulator", "native")}
        self.pins = {"source_commit": "a" * 40, "tool_sha256": "b" * 64,
                     **{key + "_sha256": file_sha256(Path(path)) for key, path in pin_files.items()}}
        self.plan_id = "plan"
        self.observation_id = experiment.identity("experiment-observe-", self.plan_id)
        self.plan = {"operation": "state-words", "hypothesis": "step differs", "alternative": "other operand",
                     "reason": "distinguish operands", "observations": [
                         {"label": "step", "address": "0x80000004", "width": 4}],
                     "prediction": {"label": "step", "update": 8, "relation": "different"}}
        for name in ("plan", "capture", "retest", "baseline"):
            seal = self.write(f"attempts/{name}/0001/result.json", {"complete": True, "job_id": name})
            self.seal(name, "fixture", seal)
        self.context = {
            "baseline_id": "baseline", "retest_id": "retest", "window": [7, 10], "history": [],
            "plan_id": self.plan_id,
            "baseline_packet": {"source_commit": "a" * 40, "pin_files": pin_files},
            "baseline_seal": self.state / "attempts/baseline/0001/result.json",
            "plan_seal": self.state / "attempts/plan/0001/result.json", "plan": self.plan,
            "plan_message": self.write("plan-message.json", self.plan),
            "diagnosis_message": self.write("diagnosis.json", {"hypothesis": "not proved"}),
            "diagnosis_packet": {"prerequisites": ["retest", "baseline"]},
            "native_trace": self.write("native.jsonl", {"fixture": "native"}),
            "oracle_trace": self.write("oracle.jsonl", {"fixture": "oracle"})}
        self.capture = {"capture_seal": self.state / "attempts/capture/0001/result.json"}
        self.measurement = {"schema": 1, "kind": "jfg-state-word-experiment", "plan": self.plan,
                            "focus_updates": [7, 10], "observations": [{"update": 8, "native": "00000003",
                            "oracle": "00000004", "equal": False, "label": "step"}],
                            "prediction_observed": True, "prediction_observation": {"update": 8},
                            "alignment_validated": False, "causal_fix_proved": False, "parity_verified": False}
        for method, value in (("plan_context", self.context), ("capture_context", self.capture),
                              ("measure", self.measurement)):
            patcher = patch.object(experiment, method, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def write(self, relative, payload):
        path = self.state / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(canonical_bytes(payload))
        return path

    def seal(self, job_id, identity, path, prerequisites=(), pins=None):
        self.store.enqueue(JobSpec(job_id, pins or self.pins, (identity,), prerequisites,
                                   "fixture", 0, "json_complete"))
        lease = self.store.lease_job(job_id, "fixture", ttl=60)
        self.store.start(job_id, lease["token"])
        self.store.verify(job_id, lease["token"])
        self.store.seal_artifact(job_id, lease["token"], path)
        self.store.pass_job(job_id, lease["token"])

    def prepare(self, *, result_patch=None, packet_patch=None, pins=None, prerequisites=None):
        packet = {"schema": 1, "job_id": self.observation_id, "plan_id": self.plan_id,
                  "capture_id": "capture", "plan_result": experiment.pin(self.context["plan_seal"]),
                  "capture_result": experiment.pin(self.capture["capture_seal"])}
        packet.update(packet_patch or {})
        self.write(f"experiment-packets/{self.observation_id}.json", packet)
        digest = hashlib.sha256(canonical_bytes(packet)).hexdigest()
        result = {**copy.deepcopy(self.measurement), "complete": True, "job_id": self.observation_id,
                  "packet_sha256": digest, "pins": pins or self.pins,
                  "plan_result": packet["plan_result"], "capture_result": packet["capture_result"]}
        result.update(result_patch or {})
        seal = self.write(f"attempts/{self.observation_id}/0001/result.json", result)
        self.seal(self.observation_id, "word-experiment:" + digest, seal,
                  prerequisites if prerequisites is not None else ("plan", "capture"), pins=pins)
        return seal

    def checked(self):
        return experiment.checked_observation(self.store, self.repo, self.state, self.observation_id)

    def enqueue(self, store, state, packet, agent):
        self.queued.append(packet)
        store.enqueue(JobSpec(packet["job_id"], self.pins, ("packet:fixture",),
                              tuple(packet["prerequisites"]), "agent", 0, "json_complete"))

    def test_recomputes_historical_observation_without_current_producer_requirement(self):
        self.prepare()
        with patch.object(experiment, "tool_sha", side_effect=AssertionError("historical producer")):
            checked = self.checked()
        self.assertTrue(checked["observation"]["prediction_observed"])
        self.assertFalse(checked["observation"]["causal_fix_proved"])

    def test_sealed_claim_contradicting_measurement_is_rejected(self):
        self.prepare(result_patch={"prediction_observed": False})
        with self.assertRaisesRegex(SupervisorError, "contradicts"):
            self.checked()

    def test_parity_claim_cannot_be_smuggled_into_a_sealed_measurement(self):
        self.prepare(result_patch={"parity_verified": True})
        with self.assertRaisesRegex(SupervisorError, "contradicts"):
            self.checked()

    def test_observation_cannot_change_source_pins_or_prerequisite_lineage(self):
        self.prepare(pins=dict(self.pins, source_commit="f" * 40))
        with self.assertRaisesRegex(SupervisorError, "baseline pins"):
            self.checked()

    def test_prerequisite_lineage_must_match_packet(self):
        self.prepare(prerequisites=("plan", "baseline"))
        with self.assertRaisesRegex(SupervisorError, "inputs changed"):
            self.checked()

    def test_unknown_packet_field_is_rejected_even_with_matching_seal(self):
        self.prepare(packet_patch={"argv": ["arbitrary"]})
        with self.assertRaisesRegex(SupervisorError, "packet identity"):
            self.checked()

    def test_changed_result_seal_prevents_followup(self):
        seal = self.prepare()
        seal.write_text("{}")
        with self.assertRaisesRegex(SupervisorError, "seal changed"), \
                patch.object(feedback, "enqueue_packet") as enqueue:
            feedback.queue_feedback(self.store, self.repo, self.state, None, self.observation_id)
        enqueue.assert_not_called()

    def test_read_only_followup_pins_history_and_is_restart_idempotent(self):
        self.prepare()
        self.queued = []
        with patch.object(feedback, "enqueue_packet", side_effect=self.enqueue):
            first = feedback.advance(self.store, self.repo, self.state, None)
            with JobStore(self.state / "jobs.sqlite") as restarted:
                second = feedback.advance(restarted, self.repo, self.state, None)
        self.assertEqual(first, [feedback.feedback_id(self.observation_id)])
        self.assertEqual(second, [])
        packet = self.queued[0]
        self.assertEqual(packet["kind"], "diagnose")
        self.assertEqual(packet["validation"], [])
        self.assertEqual(packet["allowed_paths"], [])
        self.assertEqual(packet["max_changed_files"], 0)
        self.assertEqual(packet["retry_budget"], 0)
        self.assertEqual(packet["prerequisites"], ["retest", "baseline", self.observation_id])
        facts = json.loads(Path(packet["evidence_files"][0]["path"]).read_text())
        self.assertEqual(facts["completed_word_rounds"], 1)
        self.assertEqual(facts["history"][0]["observations"], self.measurement["observations"])
        self.assertFalse(facts["causal_fix_proved"])

    def test_falsified_prediction_is_forwarded_as_negative_evidence(self):
        self.measurement["prediction_observed"] = False
        self.prepare()
        self.queued = []
        with patch.object(feedback, "enqueue_packet", side_effect=self.enqueue):
            feedback.queue_feedback(self.store, self.repo, self.state, None, self.observation_id)
        self.assertIn("Prediction observed: False", self.queued[0]["prompt"])

    def test_interrupted_publication_resumes_unchanged_facts(self):
        self.prepare()
        with patch.object(feedback, "enqueue_packet", side_effect=RuntimeError("interrupted")):
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                feedback.queue_feedback(self.store, self.repo, self.state, None, self.observation_id)
        path = self.state / "experiment-feedback" / (feedback.feedback_id(self.observation_id) + ".json")
        original = path.read_bytes()
        with patch.object(feedback, "enqueue_packet"):
            feedback.queue_feedback(self.store, self.repo, self.state, None, self.observation_id)
        self.assertEqual(path.read_bytes(), original)
        path.write_text("{}")
        with self.assertRaisesRegex(SupervisorError, "immutable facts"):
            feedback.queue_feedback(self.store, self.repo, self.state, None, self.observation_id)

    def test_predecessor_history_rejects_cross_baseline_measurements(self):
        self.prepare()
        context = dict(self.context, diagnosis_packet={"prerequisites": [self.observation_id]},
                       baseline_id="unrelated")
        with self.assertRaisesRegex(SupervisorError, "baseline or comparison window"):
            experiment.prior_history(self.store, self.repo, self.state, context)

    def test_history_propagates_measurements_not_only_the_model_hypothesis(self):
        self.prepare()
        context = dict(self.context, diagnosis_packet={"prerequisites": [self.observation_id]})
        history = experiment.prior_history(self.store, self.repo, self.state, context)
        contract = experiment.experiment_plan.contract(context["window"], [item["plan"] for item in history])
        self.assertEqual(contract["version"], 2)
        self.assertEqual(contract["round"], 2)
        self.assertEqual(contract["prior_reads"], [{"address": "0x80000004", "width": 4}])

    def test_pause_and_invalid_budgets_do_not_investigate(self):
        for budget in (True, 0, 17):
            with self.assertRaises(SupervisorError):
                feedback.advance(None, None, None, None, max_new_jobs=budget)
        (self.state / "PAUSED").touch()
        with patch.object(experiment, "checked_observation") as checked:
            self.assertEqual(feedback.advance(self.store, self.repo, self.state, None), [])
            self.assertIsNone(feedback.queue_feedback(self.store, self.repo, self.state, None, self.observation_id))
        checked.assert_not_called()

    def test_observation_restarts_after_publication_interruption_without_replaying(self):
        job_id = experiment.queue_observation(self.store, self.repo, self.state, self.context, "capture")
        first = self.store.lease_job(job_id, "first", ttl=60)
        with patch.object(self.store, "verify", side_effect=KeyboardInterrupt("simulated kill")):
            with self.assertRaises(KeyboardInterrupt):
                experiment.run_lease(self.store, first, self.repo, self.state)
        old_result = self.state / "attempts" / job_id / "0001/result.json"
        before = old_result.read_bytes()
        self.assertTrue(json.loads(before)["complete"])
        self.assertEqual(self.store.job(job_id)["state"], "running")
        self.store.reclaim_expired(now=first["lease_until"] + 1)
        second = self.store.lease_job(job_id, "second", now=first["lease_until"] + 2, ttl=60)
        with patch.object(experiment, "queue_update", side_effect=AssertionError("unexpected replay")), \
                patch.object(experiment, "run_once", side_effect=AssertionError("unexpected agent")):
            message = experiment.run_lease(self.store, second, self.repo, self.state)
        self.assertIn("sealed", message)
        self.assertEqual(self.store.job(job_id)["state"], "passed")
        self.assertEqual(self.store.job(job_id)["attempts"], 2)
        self.assertEqual(old_result.read_bytes(), before)
        self.assertEqual((old_result.parent.parent / "0002/result.json").read_bytes(), before)

    def test_capture_mutation_during_measurement_blocks_publication(self):
        job_id = experiment.queue_observation(self.store, self.repo, self.state, self.context, "capture")
        lease = self.store.lease_job(job_id, "fixture", ttl=60)
        with patch.object(experiment, "capture_context", side_effect=[self.capture, ValueError("changed snapshot")]):
            message = experiment.run_lease(self.store, lease, self.repo, self.state)
        self.assertIn("blocked", message)
        self.assertEqual(self.store.job(job_id)["state"], "blocked")
        report = json.loads((self.state / "attempts" / job_id / "0001/result.json").read_text())
        self.assertFalse(report["complete"])
        self.assertIsNone(self.store.job(job_id)["sealed_artifact"])

    def test_scheduler_prioritizes_measured_feedback_over_another_exploration(self):
        from scripts.autonomy.scheduler import advance_jobs
        with patch("scripts.autonomy.scheduler.advance_candidate_reviews", return_value=[]), \
                patch("scripts.autonomy.scheduler.advance_candidate_retests", return_value=[]), \
                patch("scripts.autonomy.branch_count_repair.advance", return_value=[]), \
                patch("scripts.autonomy.candidate_feedback.advance", return_value=[]), \
                patch.object(feedback, "advance", return_value=["new-feedback"]), \
                patch.object(experiment, "advance") as plan, \
                patch("scripts.autonomy.scheduler.queue_frontier_next") as frontier:
            self.assertEqual(advance_jobs(self.store, self.repo, self.state, None), ["new-feedback"])
        plan.assert_not_called()
        frontier.assert_not_called()


if __name__ == "__main__":
    unittest.main()
