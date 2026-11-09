import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.autonomy import interval_plan as plan, interval_observation as observation, interval_experiment as experiment
from scripts.autonomy import state_word_experiment as words, research_cycle as cycle
from scripts.autonomy.supervisor import SupervisorError, canonical_bytes, experiment_module
from scripts.autonomy.job_store import JobStore, JobSpec
from tests.test_autonomy_point_interval import PROBE, SELECT, trace


def proposal():
    return {"operation": "interval-state", "hypothesis": "extra sender", "alternative": "different draining",
            "reason": "distinguish histories", "probe": copy.deepcopy(PROBE), "selection": dict(SELECT),
            "prediction": {"kind": "event-count", "update": 8, "occurrence": None,
                           "register": None, "address": None, "relation": "different"}}


class IntervalPlanTests(unittest.TestCase):
    def test_valid_typed_count_register_word_and_unsupported(self):
        c = plan.contract([7, 8], "1" * 64)
        p = proposal()
        self.assertEqual(plan.validate(p, c), p)
        self.assertIs(experiment_module({"kind": "plan-interval"}), plan)
        for kind in ("register", "word"):
            p = proposal()
            p["prediction"].update(kind=kind, occurrence=1,
                register=2 if kind == "register" else None, address="0x800a9e90" if kind == "word" else None)
            plan.validate(p, c)
        plan.validate(dict(p, operation="needs-instrumentation", probe=None, selection=None, prediction=None), c)

    def test_invalid_commands_boundaries_and_selectors(self):
        for key, value in (("command", "run"), ("reason", "x" * 601), ("operation", "write")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                plan.validate(dict(proposal(), **{key: value}), plan.contract([7, 8], "1" * 64))
        for key, value in (("update", 7), ("occurrence", 1), ("register", True)):
            p = proposal(); p["prediction"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                plan.validate(p, plan.contract([7, 8], "1" * 64))
        for key, value in (("register", True), ("pc", "0x80000500"), ("value_lo", "0x1")):
            p = proposal(); p["selection"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                plan.validate(p, plan.contract([7, 8], "1" * 64))

    def test_existing_count_cannot_be_repeated_by_changing_update(self):
        p = proposal()
        known = [{key: p[key] for key in ("probe", "selection")}]
        c = plan.contract([7, 10], "1" * 64, known_counts=known)
        p["prediction"]["update"] = 9
        with self.assertRaisesRegex(ValueError, "repeats"):
            plan.validate(p, c)
        p["prediction"].update(kind="word", occurrence=1, address="0x800a9e90")
        plan.validate(p, c)  # A count does not pretend to have measured words.

    def test_history_budgets_and_value_recapture_guard(self):
        old = proposal(); p = proposal()
        p["prediction"].update(kind="register", occurrence=1, register=2)
        with self.assertRaisesRegex(ValueError, "repeats"):
            plan.validate(p, plan.contract([7, 8], "1" * 64, [old]))
        p["selection"]["value_lo"] = "0x80000404"
        with self.assertRaisesRegex(ValueError, "budget"):
            plan.validate(p, plan.contract([7, 8], "1" * 64, [old] * 3))
        for c in (plan.contract([7, 7], "1" * 64), plan.contract([7, 24], "1" * 64),
                  plan.contract([7, 8], "bad"), plan.contract([7, 8], "1" * 64, [old] * 4)):
            with self.assertRaises(ValueError):
                plan.validate_contract(c)


class IntervalObservationTests(unittest.TestCase):
    def raw(self):
        raw = {side: trace(side == "oracle") for side in ("native", "oracle")}
        for side, rows in raw.items():
            for row in rows:
                row.update(r2_lo=3 if side == "native" else 4, r2_hi=0, m80000004=8 if side == "native" else 9)
        return raw

    def test_count_and_qualified_register_prediction(self):
        p = proposal()
        result = observation.evaluate(self.raw(), p, [7, 8])
        self.assertTrue(result["qualification"]["passed"])
        self.assertTrue(result["prediction_observed"])
        self.assertFalse(result["completed_queue_operations_proved"])
        p["prediction"].update(kind="register", occurrence=1, register=2)
        result = observation.evaluate(self.raw(), p, [7, 8])
        self.assertEqual(result["prediction_observation"]["native"], "0x0000000000000003")
        self.assertTrue(result["prediction_observed"])

    def test_unmapped_overlay_return_is_inconclusive_not_a_value_difference(self):
        p = proposal(); p["prediction"].update(kind="word", occurrence=1, address="0x80000004")
        raw = self.raw()
        raw["native"][3]["r31_lo"] = 0x400260
        raw["oracle"][3]["r31_lo"] = 0x803011c0
        result = observation.evaluate(raw, p, [7, 8])
        self.assertFalse(result["qualification"]["passed"])
        self.assertIsNone(result["prediction_observed"])

    def test_changed_capture_or_missing_occurrence_is_inconclusive(self):
        p = proposal()
        result = observation.evaluate(self.raw(), p, [7, 8], reasons=["changed RDRAM"])
        self.assertIsNone(result["prediction_observed"])
        p["prediction"].update(kind="register", occurrence=3, register=2)
        self.assertFalse(observation.evaluate(self.raw(), p, [7, 8])["qualification"]["passed"])

    def test_reuse_requires_same_anchor_and_captured_points_and_words(self):
        probe = observation.registered_probe()
        self.assertTrue(observation.can_reuse(probe))
        for field in ("pcs", "words"):
            p = copy.deepcopy(probe); p[field].append("0x80000004")
            self.assertFalse(observation.can_reuse(p))
        p = copy.deepcopy(probe); p["call_pc"] = "0x80000100"
        self.assertFalse(observation.can_reuse(p))


class IntervalWorkflowTests(unittest.TestCase):
    def test_legacy_facts_remain_byte_compatible_without_static_inventory(self):
        context = {'point_runtime': {'binding': {'path': 'runtime', 'sha256': '1' * 64},
                                     'reference': {'capture_seal': Path('reference/result.json')}},
                   'window': [7, 8], 'diagnosis': {'next_test': 'branch'}}
        with patch.object(experiment.interval_observation, 'retained_counts', return_value=[]), \
                patch.object(experiment.point_experiment, 'history_facts', return_value={'old': 'facts'}), \
                patch.object(experiment.instruction_context, 'inventory', return_value={'sites': []}) as inventory:
            legacy = experiment.facts_for(context)
            self.assertEqual(legacy, {'schema': 1, 'kind': 'retained-interval-planner-facts',
                'point_facts': {'old': 'facts'}, 'retained_probe': observation.registered_probe(),
                'known_counts': [], 'runtime': context['point_runtime']['binding'],
                'alignment_validated': False, 'causal_fix_proved': False, 'parity_verified': False})
            inventory.assert_not_called()
            updated = experiment.facts_for(context, operands=True)
            self.assertEqual(updated, {**legacy, 'schema': 2, 'instruction_context': {'sites': []}})
            inventory.assert_called_once_with(Path('reference'), [7, 8], context['diagnosis'])

    def test_compact_context_validates_before_enqueue_and_preserves_full_facts(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary); state = repo / "tools/private/autonomy"; state.mkdir(parents=True)
            def write(name):
                path = state / name; path.write_text('{}'); return path
            runtime = {"binding": words.pin(write('runtime.json'))}
            context = {"entry_plan_id": "entry", "plan": {"operation": "needs-instrumentation"},
                "point_runtime": runtime, "window": [7, 8], "history": [], "baseline_id": "baseline",
                "baseline_packet": {"source_commit": "a" * 40,
                    "pin_files": {key: str(write(key)) for key in ('native', 'rom', 'emulator')}},
                "diagnosis": {"hypothesis": "ordering", "next_test": "observe queue before receive"}}
            for key in ('plan_seal', 'plan_message', 'diagnosis_message', 'baseline_seal'):
                context[key] = write(key)
            counts = [{"probe": copy.deepcopy(PROBE), "selection": dict(SELECT, value_lo=f'0x{0x80000400+i*4:08x}'),
                       "observations": [{"update": 8, "native": 1, "oracle": 1, "equal": True}]} for i in range(25)]
            facts = {"known_counts": counts, "retained_probe": PROBE,
                     "point_facts": {"candidates": [], "prior_observations": [],
                         "runtime_calibration": {"qualification": {"passed": True}, "measurements": {}}}}
            store = MagicMock(); store.status_projection.return_value = {"jobs": []}
            with patch.object(experiment.point_experiment, 'plan_context', return_value=context), \
                    patch.object(experiment, 'facts_for', return_value=facts), \
                    patch('scripts.autonomy.supervisor._git_ok', return_value='a' * 40), \
                    patch.object(experiment, 'enqueue_packet') as enqueue:
                experiment.queue_plan(store, repo, state, None, 'parent')
                packet = enqueue.call_args.args[2]
                self.assertLess(len(packet['prompt']), 18000)
                self.assertEqual(len(packet['experiment_contract']['known_counts']), 25)
                self.assertEqual(json.loads(experiment.facts_path(state, 'parent').read_text()), facts)
                enqueue.reset_mock()
                context['diagnosis']['hypothesis'] = 'x' * 25000
                with self.assertRaisesRegex(SupervisorError, 'prompt'):
                    experiment.queue_plan(store, repo, state, None, 'parent')
                enqueue.assert_not_called()

    def test_historical_point_proposal_does_not_fork_lane_after_refresh(self):
        base = words.identity('point-plan-', 'entry')
        store = MagicMock()
        store.status_projection.return_value = {'jobs': [{'job_id': name} for name in (base, base+'-history-v2')]}
        context = {'entry_plan_id': 'entry', 'plan': {'operation': 'needs-instrumentation'}}
        with tempfile.TemporaryDirectory() as temporary, \
                patch.object(experiment.point_experiment, 'plan_context', return_value=context), \
                patch.object(experiment, 'facts_for', side_effect=AssertionError('historical fork')):
            self.assertIsNone(experiment.queue_plan(store, None, Path(temporary), None, base))

    def test_retained_capture_path_never_launches_another_replay(self):
        store = MagicMock(); parent = "parent"; job = words.identity(experiment.PLAN_PREFIX, parent)
        store.status_projection.return_value = {"jobs": [{"job_id": job, "state": "passed"}]}
        with tempfile.TemporaryDirectory() as temporary, \
                patch.object(experiment, "plan_context", return_value={"plan": proposal()}), \
                patch.object(observation, "can_reuse", return_value=True), \
                patch.object(experiment, "queue_observation", return_value="observation") as queue, \
                patch.object(experiment.point_experiment, "ensure_capture", side_effect=AssertionError("duplicate replay")):
            self.assertEqual(experiment.next_job(store, None, Path(temporary), None, parent), "observation")
            self.assertIsNone(queue.call_args.args[-1])

    def test_new_points_use_pinned_capture_after_instruction_qualification(self):
        store = MagicMock(); job = words.identity(experiment.PLAN_PREFIX, 'parent')
        store.status_projection.return_value = {'jobs': [{'job_id': job, 'state': 'passed'}]}
        store.job.return_value = {'state': 'queued'}
        context = {'plan': proposal(), 'window': [7, 8],
                   'point_runtime': {'reference': {'capture_seal': Path('reference/result.json')}}}
        with tempfile.TemporaryDirectory() as temporary, \
                patch.object(experiment, 'plan_context', return_value=context), \
                patch.object(observation, 'can_reuse', return_value=False), \
                patch.object(experiment.point_observation, 'instruction_evidence') as instructions, \
                patch.object(experiment.point_experiment, 'ensure_capture', return_value='new-capture') as capture, \
                patch.object(experiment, 'queue_observation', side_effect=AssertionError('capture not complete')):
            self.assertEqual(experiment.next_job(store, None, Path(temporary), None, 'parent'), 'new-capture')
            instructions.assert_called_once()
            capture.assert_called_once()

    def test_changed_sealed_measurement_never_becomes_feedback_evidence(self):
        expected = {'complete': True, 'prediction_observed': False, 'parity_verified': False}
        altered = dict(expected, parity_verified=True)
        with patch.object(experiment, '_sealed_result', return_value=({'spec': {}}, altered, Path('result'))), \
                patch.object(experiment, 'inputs', return_value=(expected, {})):
            with self.assertRaisesRegex(SupervisorError, 'contradicts'):
                experiment.checked_observation(None, None, None, 'o')

    def test_unsupported_running_and_paused_do_not_repeat(self):
        store = MagicMock(); job = words.identity(experiment.PLAN_PREFIX, "parent")
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary)
            for status in ("running", "blocked", "failed"):
                store.status_projection.return_value = {"jobs": [{"job_id": job, "state": status}]}
                self.assertEqual(experiment.next_job(store, None, state, None, "parent"), job)
            store.status_projection.return_value = {"jobs": [{"job_id": job, "state": "passed"}]}
            with patch.object(experiment, "plan_context", return_value={"plan": {"operation": "needs-instrumentation"}}), \
                    patch.object(experiment, "queue_refresh", return_value=None), \
                    patch.object(experiment, "queue_plan", side_effect=AssertionError("retry")):
                self.assertEqual(experiment.next_job(store, None, state, None, "parent"), job)
            (state / "PAUSED").touch()
            self.assertIsNone(experiment.next_job(None, None, state, None, "parent"))
            self.assertEqual(experiment.advance(None, None, state, None), [])

    def test_measured_interval_advances_to_feedback_and_qualification_is_retained(self):
        store = MagicMock()
        store.job.side_effect = [{"state": "passed"},
            *[{"state": "passed", "spec": {"inputs": ["packet:plan"]}}] * 3,
            {"state": "passed", "spec": {"inputs": ["interval-experiment:observation"]}}, {"state": "queued"}]
        unsupported = {"plan": {"operation": "needs-instrumentation"}}
        with tempfile.TemporaryDirectory() as temporary, patch.object(cycle.feedback, "queue_feedback") as queue, \
                patch.object(cycle.experiment, "next_job", return_value="word"), \
                patch.object(cycle.experiment, "plan_context", return_value=unsupported), \
                patch.object(cycle.entry_experiment, "next_job", return_value="entry"), \
                patch.object(cycle.entry_experiment, "plan_context", return_value=unsupported), \
                patch.object(cycle.point_experiment, "next_job", return_value="point"), \
                patch.object(cycle.point_experiment, "plan_context", return_value=unsupported), \
                patch.object(cycle.interval_experiment, "next_job", return_value="interval-observation"):
            result = cycle.next_stage(store, None, Path(temporary), None, "root")
        self.assertEqual([call.args[-1] for call in queue.call_args_list], ["root", "interval-observation"])
        self.assertEqual(result["job_id"], cycle.feedback.feedback_id("interval-observation"))

    def test_cyclic_history_and_consumer_routing(self):
        with self.assertRaisesRegex(SupervisorError, "cyclic"):
            experiment.plan_context(None, None, None, "p", chain=("p",))
        store = MagicMock(); store.job.return_value = {"spec": {"inputs": ["interval-experiment:x"]}}
        with patch.object(experiment, "checked_observation", return_value={"checked": True}):
            self.assertEqual(words.checked_observation(store, None, None, "o"), {"checked": True})

    def test_analysis_child_is_guarded_and_sealed_with_a_real_ledger(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary); state = repo / "tools/private/autonomy"; state.mkdir(parents=True)
            pins = {"source_commit": "a" * 40, **{key: "b" * 64 for key in
                ("tool_sha256", "native_sha256", "rom_sha256", "emulator_sha256")}}
            with JobStore(state / "jobs.sqlite") as store:
                store.enqueue(JobSpec("o", pins, ("interval-experiment:fixture",), (), "analysis:interval-state", 1, "json_complete"))
                lease = store.lease_job("o", "test", ttl=120)

                def child(command, cwd, stdout, stderr, deadline, heartbeat, pause, *, guard_record):
                    self.assertEqual(command[1:4], ["-m", "scripts.autonomy.interval_experiment", "--measure-job"])
                    self.assertEqual(guard_record, state / 'attempts/o/0001/measurement.guard.json')
                    heartbeat()
                    output = Path(command[-1])
                    output.write_bytes(canonical_bytes({"complete": True, "job_id": "o", "pins": pins,
                                                        "qualification": {"passed": True}}))
                    return 0, None

                with patch.object(experiment, "tool_sha", return_value="b" * 64), \
                        patch.object(experiment, "bounded_command", side_effect=child):
                    self.assertIn("sealed", experiment.run_lease(store, lease, repo, state))
                self.assertEqual(store.job("o")["state"], "passed")


if __name__ == "__main__":
    unittest.main()
