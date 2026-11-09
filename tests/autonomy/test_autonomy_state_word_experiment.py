import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from scripts.autonomy import state_word_experiment as experiment
from scripts.autonomy.supervisor import SupervisorError, canonical_bytes, file_sha256


class StateWordExperimentTests(unittest.TestCase):
    def test_context_handoff_dependency_changes_all_measurement_producer_identities(self):
        from scripts.autonomy import entry_experiment, point_experiment, interval_experiment
        original = experiment.file_sha256
        producers = (experiment, entry_experiment, point_experiment, interval_experiment)
        before = [module.tool_sha() for module in producers]
        with patch.object(experiment, 'file_sha256', side_effect=lambda path:
                '0' * 64 if Path(path).name == 'candidate_feedback.py' else original(path)):
            after = [module.tool_sha() for module in producers]
        self.assertTrue(all(left != right for left, right in zip(before, after)))

    def test_diagnosis_uses_fresh_outcome_context_and_still_checks_baseline_binding(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            message = state / 'last-message.txt'
            schema = state / 'schema.json'
            message.write_text('{}'); schema.write_text('{}')
            packet = {'kind': 'diagnose', 'prerequisites': ['retest', 'baseline'],
                      'source_commit': 'a' * 40, 'pin_files': {'native': 'frozen'}}
            digest = hashlib.sha256(canonical_bytes(packet)).hexdigest()
            job = {'spec': {'inputs': ['packet:' + digest], 'prerequisites': packet['prerequisites'], 'pins': {}}}
            result = {'packet_sha256': digest, 'pins': {}, 'diagnosis_sha256': file_sha256(message),
                      'diagnosis_schema_sha256': file_sha256(schema)}
            context = {'baseline': {'first_divergence': {'update': 7}}, 'baseline_update_count': 9,
                       'baseline_packet': {'execution': {'profile': 'original-os-probe'}, 'source_build': {}},
                       'baseline_id': 'baseline'}
            implementation = {key: packet[key] for key in ('source_commit', 'pin_files')}
            store = MagicMock()
            store.job.side_effect = lambda name: {'spec': {'inputs': [
                'candidate-retest-packet:x' if name == 'retest' else 'update-packet:x']}}
            with patch.object(experiment, '_sealed_result', return_value=(job, result, state / 'result.json')), \
                    patch.object(experiment, 'read_packet', return_value=packet), \
                    patch.object(experiment, 'read_diagnosis', return_value={'classification': 'insufficient_evidence'}), \
                    patch.object(experiment, 'diagnosis_schema_file', return_value=schema), \
                    patch.object(experiment, 'checked_outcome_context', return_value=(
                        {'baseline_id': 'baseline', 'review_id': 'review'}, implementation, [], context)) as outcome:
                checked = experiment.diagnosis_context(store, state, state, 'diagnosis')
                outcome.assert_called_once_with(store, state, state, 'retest')
                self.assertIs(checked['baseline_packet'], context['baseline_packet'])
                self.assertEqual(checked['window'], [5, 8])
                self.assertEqual(checked['retest_id'], 'retest')
                packet['source_commit'] = 'b' * 40
                digest = hashlib.sha256(canonical_bytes(packet)).hexdigest()
                job['spec']['inputs'] = ['packet:' + digest]
                result['packet_sha256'] = digest
                with self.assertRaisesRegex(SupervisorError, 'different baseline'):
                    experiment.diagnosis_context(store, state, state, 'diagnosis')

    @staticmethod
    def interval_history():
        return [{"observation_id": "interval-observe-fixture", "observation_seal": Path("interval/result.json"),
                 "plan": {"operation": "interval-state", "hypothesis": "checked earlier event",
                          "probe": {"entry_pc": "0x80054fbc", "call_pc": "0x800457b4"},
                          "selection": {"pc": "0x80096f20", "register": 4, "value_lo": "0x800feb80"},
                          "prediction": {"kind": "word", "update": 1908, "occurrence": 2,
                                         "register": None, "address": "0x800feb88", "relation": "different"}},
                 "observation": {"prediction_observed": False,
                                 "prediction_observation": {"update": 1908, "native": "0x00000001",
                                      "oracle": "0x00000001", "equal": True,
                                      "boundaries": {"native": {"register_dump": "raw-data" * 10_000}},
                                      "selected_events": [{"register_dump": "raw-data" * 10_000}]},
                                 "qualification": {"passed": True, "scope": "local-interval-only", "reasons": [],
                                                   "instruction_evidence": {"dump": "raw-data" * 10_000}},
                                 "completed_queue_operations_proved": False, "alignment_validated": False,
                                 "causal_fix_proved": False, "parity_verified": False}}]

    def test_planner_history_excludes_raw_traces_without_changing_evidence(self):
        history = self.interval_history()
        before = copy.deepcopy(history)
        rows = experiment.planner_history(history)
        self.assertLess(len(json.dumps(rows)), 1500)
        self.assertNotIn("raw-data", json.dumps(rows))
        self.assertEqual(rows[0]["measurement"], {"update": 1908, "native": "0x00000001",
                                                 "oracle": "0x00000001", "equal": True})
        self.assertFalse(rows[0]["prediction_observed"])
        self.assertEqual(rows[0]["qualification"], {"passed": True, "scope": "local-interval-only", "reasons": []})
        self.assertEqual(rows[0]["anchor"], history[0]["plan"]["probe"])
        self.assertEqual(rows[0]["selection"], history[0]["plan"]["selection"])
        for key in ("completed_queue_operations_proved", "alignment_validated", "causal_fix_proved", "parity_verified"):
            self.assertFalse(rows[0][key])
        self.assertEqual(history, before)

    def test_planner_history_keeps_inconclusive_and_missing_measurements(self):
        history = self.interval_history()
        observation = history[0]["observation"]
        observation["prediction_observed"] = None
        observation["qualification"].update(passed=False, reasons=["selected-event-prefixes-differ"])
        row = experiment.planner_history(history)[0]
        self.assertIsNone(row["prediction_observed"])
        self.assertTrue(row["measurement"]["equal"])
        self.assertFalse(row["qualification"]["passed"])
        self.assertEqual(row["qualification"]["reasons"], ["selected-event-prefixes-differ"])
        observation["prediction_observation"] = None
        self.assertIsNone(experiment.planner_history(history)[0]["measurement"])

    def test_queue_plan_bounds_history_before_validation_and_pins_complete_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            store = MagicMock()
            store.status_projection.return_value = {"jobs": []}
            context = {"baseline_packet": {"source_commit": "fixture", "pin_files": {}},
                       "diagnosis_seal": Path("diagnosis/result.json"), "diagnosis_message": Path("diagnosis/last-message.txt"),
                       "baseline_seal": Path("baseline/result.json"), "native_trace": Path("native/trace"),
                       "oracle_trace": Path("oracle/trace"), "window": [1907, 1910], "baseline_id": "baseline",
                       "diagnosis": {"next_test": "Need receive-path execution, not more completed-update words."}}
            history = self.interval_history()
            order = []
            def validate(packet, repo):
                self.assertLess(len(packet["prompt"]), 20_000)
                self.assertNotIn("raw-data", packet["prompt"])
                self.assertIn("0x800feb88", packet["prompt"])
                self.assertIn({"path": "interval/result.json", "sha256": "fixture"}, packet["evidence_files"])
                order.append("validated")
            with patch.object(experiment, "diagnosis_context", return_value=context), \
                    patch.object(experiment, "prior_history", return_value=history), \
                    patch.object(experiment, "pin", side_effect=lambda p: {"path": p.as_posix(), "sha256": "fixture"}), \
                    patch.object(experiment, "validate_packet", side_effect=validate), \
                    patch.object(experiment, "enqueue_packet", side_effect=lambda *args: order.append("enqueued")) as enqueue:
                expected = experiment.identity("experiment-plan-", "diagnosis")
                self.assertEqual(experiment.queue_plan(store, state, state, None, "diagnosis"), expected)
                self.assertEqual(order, ["validated", "enqueued"])
                enqueue.reset_mock()
                with patch.object(experiment, "validate_packet", side_effect=SupervisorError("prompt budget")):
                    with self.assertRaisesRegex(SupervisorError, "prompt budget"):
                        experiment.queue_plan(store, state, state, None, "diagnosis")
                enqueue.assert_not_called()

    def test_canonical_word_measurements_keep_clock_units_and_no_causal_claim(self):
        context = {"window": [7, 8], "plan": {
            "observations": [{"label": "step", "address": "0x80000004", "width": 4},
                             {"label": "override", "address": "0x80000008", "width": 1}],
            "prediction": {"label": "step", "update": 8, "relation": "different"}}}
        def record(path, update):
            return {"update": update, "controller_polls": update + 2,
                    **({"vi_retraces": update * 3} if "native" in path.parts else
                       {"oracle_consumed_vi": update * 3 + (update == 8), "emulator_frame": update * 3 + 30})}
        def snapshot(path, row):
            data = bytearray(16)
            data[4:8] = (4 if path.name == "oracle" and row["update"] == 8 else 3).to_bytes(4, "big")
            data[8] = 2
            return bytes(data), "fixture"
        with patch.object(experiment, "_records_at", side_effect=lambda path, updates: {update: record(path, update) for update in updates}), \
                patch.object(experiment, "_snapshot", side_effect=snapshot):
            result = experiment.measure(context, {"capture_seal": Path("fixture/result.json")})
        self.assertTrue(result["prediction_observed"])
        self.assertEqual(result["prediction_observation"]["native"], "00000003")
        self.assertEqual(result["prediction_observation"]["oracle"], "00000004")
        self.assertEqual(result["observations"][1]["native"], "02")
        self.assertIsNone(result["prediction_observation"]["clocks"]["native"]["oracle_consumed_vi"])
        self.assertFalse(result["alignment_validated"])
        self.assertFalse(result["causal_fix_proved"])
        self.assertFalse(result["parity_verified"])

    def test_next_job_does_not_relaunch_running_plan_or_finished_observation(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            plan = experiment.identity("experiment-plan-", "diagnosis")
            observed = experiment.identity("experiment-observe-", plan)
            store = MagicMock()
            store.status_projection.return_value = {"jobs": [{"job_id": plan, "state": "running"}]}
            with patch.object(experiment, "queue_plan") as queue, patch.object(experiment, "plan_context") as context:
                self.assertEqual(experiment.next_job(store, state, state, None, "diagnosis"), plan)
                queue.assert_not_called()
                context.assert_not_called()
                store.status_projection.return_value = {"jobs": [
                    {"job_id": plan, "state": "passed"}, {"job_id": observed, "state": "passed"}]}
                self.assertEqual(experiment.next_job(store, state, state, None, "diagnosis"), observed)
                context.assert_not_called()

    def test_matching_capture_is_reused_without_queueing_a_replay(self):
        store = MagicMock()
        store.status_projection.return_value = {"jobs": [{"job_id": "capture", "state": "passed"}]}
        store.job.return_value = {"spec": {"inputs": ["update-packet:fixture"]}}
        with patch.object(experiment, "capture_context", return_value={"capture_id": "capture"}), \
                patch.object(experiment, "queue_update") as queue:
            self.assertEqual(experiment.ensure_capture(store, None, None, {}), "capture")
            queue.assert_not_called()

    def test_unsupported_primitive_is_terminal_without_speculative_capture(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            plan = experiment.identity("experiment-plan-", "diagnosis")
            store = MagicMock()
            store.status_projection.return_value = {"jobs": [{"job_id": plan, "state": "passed"}]}
            with patch.object(experiment, "plan_context", return_value={"plan": {"operation": "needs-instrumentation"}}), \
                    patch.object(experiment, "ensure_capture") as capture:
                self.assertEqual(experiment.next_job(store, state, state, None, "diagnosis"), plan)
                capture.assert_not_called()

    def test_pause_and_invalid_budget_prevent_all_stages(self):
        for count in (0, 17, True):
            with self.assertRaises(SupervisorError):
                experiment.advance(None, None, None, None, max_new_jobs=count)
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            (state / "PAUSED").touch()
            self.assertIsNone(experiment.next_job(None, state, state, None, "diagnosis"))
            self.assertEqual(experiment.advance(None, state, state, None), [])

    def test_cyclic_or_overbudget_plan_history_stops_before_reading_evidence(self):
        for chain in (("plan",), tuple(str(i) for i in range(experiment.MAX_PLAN_CHAIN))):
            with self.subTest(chain=chain), self.assertRaisesRegex(SupervisorError, "cyclic or exceeds"), \
                    patch.object(experiment, "_sealed_result", side_effect=AssertionError("must reject first")):
                experiment.plan_context(None, None, None, "plan", chain=chain)


if __name__ == "__main__":
    unittest.main()
