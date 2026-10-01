from pathlib import Path
import hashlib
import json
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from scripts.autonomy import research_cycle as cycle
from scripts.autonomy.supervisor import SupervisorError


class ResearchCycleTests(unittest.TestCase):
    def test_routing_hint_checks_seal_packet_schema_and_output_before_dispatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            module = cycle.experiment.experiment_plan
            plan = {"operation": "needs-instrumentation", "hypothesis": "A", "alternative": "B",
                    "reason": "needs execution", "observations": [], "prediction": None}
            message = state / "last-message.txt"
            message.write_text(json.dumps(plan))
            packet = {"kind": "plan-experiment", "prerequisites": ["diagnosis", "baseline"],
                      "experiment_contract": module.contract([7, 8])}
            digest = hashlib.sha256(cycle.canonical_bytes(packet)).hexdigest()
            job = {"spec": {"inputs": ["packet:" + digest], "prerequisites": packet["prerequisites"], "pins": {}}}
            result = {"packet_sha256": digest, "pins": {}, "experiment_plan_sha256": cycle.file_sha256(message),
                      "experiment_schema_sha256": cycle.file_sha256(module.SCHEMA_FILE)}
            with patch.object(cycle.experiment, "_sealed_result", return_value=(job, result, state / "result.json")), \
                    patch.object(cycle, "read_packet", return_value=packet):
                self.assertEqual(cycle._routing_plan(None, None, state, "plan", module, "plan-experiment"), (plan, packet))
                for key in ("packet_sha256", "experiment_plan_sha256", "experiment_schema_sha256"):
                    saved = result[key]
                    result[key] = "0" * 64
                    with self.subTest(key=key), self.assertRaisesRegex(SupervisorError, "provenance"):
                        cycle._routing_plan(None, None, state, "plan", module, "plan-experiment")
                    result[key] = saved
                message.write_text("changed after sealing")
                with self.assertRaisesRegex(SupervisorError, "provenance"):
                    cycle._routing_plan(None, None, state, "plan", module, "plan-experiment")

    @staticmethod
    def tail_store(depth, state="passed"):
        word = cycle.experiment.identity("experiment-plan-", "diagnosis")
        entry = cycle.experiment.identity("entry-plan-", word)
        point = cycle.experiment.identity("point-plan-", entry)
        interval = cycle.experiment.identity(cycle.interval_experiment.PLAN_PREFIX, point)
        ids = [word, entry, point, interval]
        store = MagicMock()
        store.status_projection.return_value = {"jobs": [{"job_id": value, "state": state if i == depth else "passed"}
                                                          for i, value in enumerate(ids[:depth + 1])]}
        return store, ids

    def test_tail_dispatches_next_lane_without_rewalking_earlier_contexts(self):
        executors = [cycle.experiment, cycle.entry_experiment, cycle.point_experiment, cycle.interval_experiment]
        from contextlib import ExitStack
        for depth in range(3):
            store, ids = self.tail_store(depth)
            store.job.return_value = {"state": "queued"}
            with self.subTest(depth=depth), tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
                stack.enter_context(patch.object(cycle, "_routing_plan", return_value=({"operation": "needs-instrumentation"}, {})))
                stack.enter_context(patch.object(cycle.point_experiment, "has_anchors", return_value=True))
                next_calls = [stack.enter_context(patch.object(executor, "next_job", return_value="successor")) for executor in executors]
                contexts = [stack.enter_context(patch.object(executor, "plan_context", side_effect=AssertionError("selected executor owns validation"))) for executor in executors]
                result = cycle._resume_tail(store, None, Path(temporary), None, "diagnosis")
                self.assertEqual(result["job_id"], "successor")
                next_calls[depth + 1].assert_called_once_with(store, None, Path(temporary), None, ids[depth])
                for index, called in enumerate(next_calls):
                    if index != depth + 1:
                        called.assert_not_called()
                for called in contexts:
                    called.assert_not_called()

    def test_tail_never_relaunches_active_or_failed_plan(self):
        for state in ("queued", "running", "failed", "blocked"):
            store, ids = self.tail_store(3, state)
            with self.subTest(state=state), patch.object(cycle, "_routing_plan") as hint, \
                    patch.object(cycle.interval_experiment, "next_job") as advance:
                result = cycle._resume_tail(store, None, None, None, "diagnosis")
            self.assertEqual(result["job_id"], ids[3])
            self.assertEqual(result["state"], state)
            hint.assert_not_called()
            advance.assert_not_called()

    def test_supported_tail_still_uses_the_full_executor_and_observation_feedback(self):
        store, ids = self.tail_store(3)
        store.job.return_value = {"state": "passed", "spec": {"inputs": ["interval-experiment:sealed"]}}
        with patch.object(cycle, "_routing_plan", return_value=({"operation": "interval-state"}, {})), \
                patch.object(cycle.interval_experiment, "next_job", return_value="measured") as advance:
            result = cycle._resume_tail(store, None, None, None, "diagnosis")
        self.assertEqual(result, {"observation_id": "measured"})
        advance.assert_called_once_with(store, None, None, None, ids[2])

    def test_terminal_tail_requires_full_validation_not_hint_reason(self):
        store, ids = self.tail_store(3)
        context = {"plan": {"operation": "needs-instrumentation", "reason": "qualified reason"}, "plan_seal": Path("sealed")}
        with patch.object(cycle, "_routing_plan", return_value=({"operation": "needs-instrumentation", "reason": "hint"}, {})), \
                patch.object(cycle.interval_experiment, "plan_context", return_value=context) as validate, \
                patch.object(cycle.interval_experiment, "queue_refresh", return_value=None), \
                patch.object(cycle.experiment, "pin", return_value={"sha256": "fixture"}):
            result = cycle._resume_tail(store, None, None, None, "diagnosis")
        self.assertEqual(result["reason"], "qualified reason")
        validate.assert_called_once_with(store, None, None, ids[3])

    def test_tail_queues_source_backed_refresh_only_after_full_validation(self):
        store, ids = self.tail_store(3)
        store.job.return_value = {"state": "queued"}
        checked = {"plan": {"operation": "needs-instrumentation"}}
        with patch.object(cycle, "_routing_plan", return_value=({"operation": "needs-instrumentation"}, {})), \
                patch.object(cycle.interval_experiment, "plan_context", return_value=checked) as validate, \
                patch.object(cycle.interval_experiment, "queue_refresh", return_value="refresh") as refresh:
            result = cycle._resume_tail(store, None, None, None, "diagnosis")
        validate.assert_called_once_with(store, None, None, ids[3])
        refresh.assert_called_once_with(store, None, None, None, checked)
        self.assertEqual(result["job_id"], "refresh")
        self.assertEqual(result["state"], "queued")
        self.assertFalse(result["parity_verified"])

    def test_tail_prefers_existing_operand_refresh_including_failure(self):
        for status in ("queued", "running", "failed", "blocked"):
            store, ids = self.tail_store(3)
            refreshed = ids[3] + cycle.interval_experiment.OPERAND_SUFFIX
            store.status_projection.return_value["jobs"].append({"job_id": refreshed, "state": status})
            with self.subTest(status=status), patch.object(cycle, "_routing_plan") as hint:
                result = cycle._resume_tail(store, None, None, None, "diagnosis")
            self.assertEqual((result["job_id"], result["state"]), (refreshed, status))
            hint.assert_not_called()

    def test_historical_point_without_history_facts_uses_existing_refresh_path(self):
        store, _ = self.tail_store(2)
        with patch.object(cycle, "_routing_plan", return_value=({"operation": "needs-instrumentation"}, {})), \
                patch.object(cycle.point_experiment, "has_anchors", return_value=False), \
                patch.object(cycle.interval_experiment, "next_job") as advance:
            self.assertIsNone(cycle._resume_tail(store, None, None, None, "diagnosis"))
        advance.assert_not_called()

    def test_tail_hint_cannot_override_executor_rejection(self):
        store, _ = self.tail_store(0)
        with patch.object(cycle, "_routing_plan", return_value=({"operation": "needs-instrumentation"}, {})), \
                patch.object(cycle.entry_experiment, "next_job", side_effect=SupervisorError("ancestor changed")):
            with self.assertRaisesRegex(SupervisorError, "ancestor changed"):
                cycle._resume_tail(store, None, None, None, "diagnosis")

    def test_failed_investigation_uses_single_bounded_completion_successor(self):
        from scripts.autonomy import research_completion
        store=MagicMock(); store.job.side_effect=[{"state":"blocked"},{"state":"queued"}]
        with tempfile.TemporaryDirectory() as temporary, patch.object(cycle.feedback,"queue_feedback"), \
                patch.object(research_completion,"successor",return_value="completion"):
            result=cycle.next_stage(store,None,Path(temporary),None,"observation")
        self.assertEqual(result["job_id"],"completion"); self.assertEqual(result["state"],"queued")
        store.job.side_effect=[{"state":"blocked"},{"state":"failed"}]
        with tempfile.TemporaryDirectory() as temporary, patch.object(cycle.feedback,"queue_feedback"), \
                patch.object(research_completion,"successor",return_value="completion"):
            result=cycle.next_stage(store,None,Path(temporary),None,"observation")
        self.assertEqual(result["job_id"],"completion"); self.assertEqual(result["state"],"failed")

    def test_dispatches_only_named_successors_and_honors_budget(self):
        transitions = [{"job_id": "diagnosis", "state": "queued"},
                       {"job_id": "plan", "state": "queued"},
                       {"job_id": "observation", "state": "queued"}]
        with patch.object(cycle, "JobStore"), patch.object(cycle, "next_stage", side_effect=transitions), \
                patch.object(cycle, "run_once", return_value="done") as worker:
            result = cycle.drive(None, Path("fixture"), None, "root", max_jobs=2, execute=True)
        self.assertEqual(result["job_id"], "observation")
        self.assertEqual(result["dispatched_jobs"], 2)
        self.assertEqual([call.kwargs["job_id"] for call in worker.call_args_list], ["diagnosis", "plan"])

    def test_running_failed_and_unsupported_stages_never_relaunch(self):
        for state in ("running", "blocked", "failed", "needs-instrumentation", "paused"):
            with self.subTest(state=state), patch.object(cycle, "JobStore"), \
                    patch.object(cycle, "next_stage", return_value={"job_id": "existing", "state": state}), \
                    patch.object(cycle, "run_once") as worker:
                result = cycle.drive(None, Path("fixture"), None, "root", execute=True)
                self.assertEqual(result["dispatched_jobs"], 0)
                worker.assert_not_called()

    def test_dry_run_queues_without_executing_and_validates_budgets(self):
        with patch.object(cycle, "JobStore"), \
                patch.object(cycle, "next_stage", return_value={"job_id": "queued", "state": "queued"}), \
                patch.object(cycle, "run_once") as worker:
            cycle.drive(None, Path("fixture"), None, "root")
            worker.assert_not_called()
        for budget in (True, 0, 17):
            with self.assertRaises(SupervisorError):
                cycle.drive(None, None, None, "root", max_jobs=budget)

    def test_pause_prevents_queueing(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            (state / "PAUSED").touch()
            with patch.object(cycle.feedback, "queue_feedback") as queue:
                self.assertEqual(cycle.next_stage(None, None, state, None, "root")["state"], "paused")
            queue.assert_not_called()

    def test_needs_instrumentation_is_explicit_not_a_pass(self):
        store = MagicMock()
        store.job.side_effect = [{"state": "passed"},
                                 {"state": "passed", "spec": {"inputs": ["packet:fixture"]}},
                                 {"state": "passed", "spec": {"inputs": ["packet:fixture"]}}]
        with tempfile.TemporaryDirectory() as temporary, \
                patch.object(cycle.feedback, "queue_feedback"), \
                patch.object(cycle.experiment, "next_job", return_value="plan"), \
                patch.object(cycle.experiment, "plan_context", return_value={
                    "plan": {"operation": "needs-instrumentation", "reason": "need instruction operands"},
                    "plan_seal": Path("fixture")}), \
                patch.object(cycle.entry_experiment, "next_job", return_value="entry-plan"), \
                patch.object(cycle.point_experiment, "next_job", return_value=None), \
                patch.object(cycle.entry_experiment, "plan_context", return_value={
                    "plan": {"operation": "needs-instrumentation", "reason": "need instruction operands"},
                    "plan_seal": Path("fixture")}), \
                patch.object(cycle.experiment, "pin", return_value={"sha256": "fixture"}):
            result = cycle.next_stage(store, None, Path(temporary), None, "root")
        self.assertEqual(result["state"], "needs-instrumentation")
        self.assertEqual(result["reason"], "need instruction operands")
        self.assertFalse(result["parity_verified"])

    def test_completed_observation_advances_to_its_own_followup(self):
        store = MagicMock()
        store.job.side_effect = [{"state": "passed"},
                                 {"state": "passed", "spec": {"inputs": ["word-experiment:fixture"]}},
                                 {"state": "queued"}]
        with tempfile.TemporaryDirectory() as temporary, \
                patch.object(cycle.feedback, "queue_feedback") as queue, \
                patch.object(cycle.experiment, "next_job", return_value="second-observation"):
            result = cycle.next_stage(store, None, Path(temporary), None, "root")
        self.assertEqual([call.args[-1] for call in queue.call_args_list], ["root", "second-observation"])
        self.assertEqual(result["job_id"], cycle.feedback.feedback_id("second-observation"))

    def test_point_observation_advances_to_measured_followup(self):
        store=MagicMock()
        store.job.side_effect=[{"state":"passed"},
            {"state":"passed","spec":{"inputs":["packet:word-plan"]}},
            {"state":"passed","spec":{"inputs":["packet:entry-plan"]}},
            {"state":"passed","spec":{"inputs":["point-experiment:observation"]}},
            {"state":"queued"}]
        unsupported={"plan":{"operation":"needs-instrumentation"}}
        with tempfile.TemporaryDirectory() as temporary, \
                patch.object(cycle.feedback,"queue_feedback") as queue, \
                patch.object(cycle.experiment,"next_job",return_value="word-plan"), \
                patch.object(cycle.experiment,"plan_context",return_value=unsupported), \
                patch.object(cycle.entry_experiment,"next_job",return_value="entry-plan"), \
                patch.object(cycle.entry_experiment,"plan_context",return_value=unsupported), \
                patch.object(cycle.point_experiment,"next_job",return_value="point-observe"):
            result=cycle.next_stage(store,None,Path(temporary),None,"root")
        self.assertEqual([call.args[-1] for call in queue.call_args_list],["root","point-observe"])
        self.assertEqual(result["job_id"],cycle.feedback.feedback_id("point-observe"))


if __name__ == "__main__":
    unittest.main()
