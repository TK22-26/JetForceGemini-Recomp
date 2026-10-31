import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.autonomy.point_interval_observation import measure, observe_registered
from scripts.autonomy.supervisor import file_sha256


PROBE = {"entry_pc": "0x80000200", "call_pc": "0x80000100",
         "pcs": ["0x80000200", "0x80000108", "0x80000300"], "words": ["0x800a9e90"]}
SELECT = {"pc": "0x80000300", "register": 4, "value_lo": "0x80000400"}


def row(pc, update, *, oracle=False, thread=0x80001000, value=0x80000400):
    return {"pc": pc, "m800a9e90": thread, "r29_lo": 0x80002000, "r31_lo": 0x80000108,
            "r4_lo": value, "controller_polls": update + 10,
            **({"completed_updates": update - 1} if oracle else {"update_candidate": update})}


def trace(oracle):
    return [row(0x80000200, 7, oracle=oracle),
            row(0x80000300, 7, oracle=oracle),  # Inside preceding call: excluded.
            row(0x80000108, 7, oracle=oracle),
            row(0x80000300, 8, oracle=oracle, thread=0x80003000),
            *([row(0x80000300, 8, oracle=True, thread=0x80003000)] if oracle else []),
            row(0x80000300, 8, oracle=oracle, value=0x80000404),  # Different queue: excluded.
            row(0x80000200, 8, oracle=oracle),
            row(0x80000300, 8, oracle=oracle),  # Inside next call: excluded.
            row(0x80000108, 8, oracle=oracle)]


class IntervalTests(unittest.TestCase):
    def test_other_threads_count_but_call_bodies_and_other_values_do_not(self):
        result = measure({side: trace(side == "oracle") for side in ("native", "oracle")}, PROBE, [7, 8], SELECT)
        observation = result["observations"][0]
        self.assertEqual((observation["native"], observation["oracle"]), (1, 2))
        self.assertEqual(observation["selected_events"]["native"][0]["m800a9e90"], 0x80003000)
        self.assertTrue(result["capture_qualification_required"])
        self.assertFalse(result["completed_queue_operations_proved"])
        self.assertFalse(result["causal_fix_proved"])
        self.assertFalse(result["alignment_validated"])

    def test_mismatched_polls_threads_stacks_and_callers_rejected(self):
        for key, value in (("controller_polls", 19), ("m800a9e90", 0x80003000),
                           ("r29_lo", 0x80004000), ("r31_lo", 0x80000110)):
            raw = {side: trace(side == "oracle") for side in ("native", "oracle")}
            raw["oracle"][-3][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                measure(raw, PROBE, [7, 8], SELECT)

    def test_missing_or_duplicate_anchor_fails(self):
        for change in ("missing", "duplicate"):
            raw = {side: trace(side == "oracle") for side in ("native", "oracle")}
            if change == "missing":
                del raw["oracle"][-3]
            else:
                raw["oracle"].insert(-3, raw["oracle"][-3].copy())
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "ambiguous"):
                measure(raw, PROBE, [7, 8], SELECT)

    def test_interval_order_and_backwards_input_rejected(self):
        raw = {side: trace(side == "oracle") for side in ("native", "oracle")}
        for side, rows in raw.items():
            rows[0]["controller_polls"] = rows[2]["controller_polls"] = 100
        with self.assertRaisesRegex(ValueError, "backwards"):
            measure(raw, PROBE, [7, 8], SELECT)
        raw = {side: trace(side == "oracle") for side in ("native", "oracle")}
        raw["native"] = raw["native"][3:] + raw["native"][:3]
        with self.assertRaisesRegex(ValueError, "order"):
            measure(raw, PROBE, [7, 8], SELECT)

    def test_same_side_boundary_thread_change_even_when_sides_agree_rejected(self):
        raw = {side: trace(side == "oracle") for side in ("native", "oracle")}
        for rows in raw.values():
            rows[-3]["m800a9e90"] = rows[-1]["m800a9e90"] = 0x80003000
        with self.assertRaisesRegex(ValueError, "between calls"):
            measure(raw, PROBE, [7, 8], SELECT)

    def test_arbitrary_overlay_return_addresses_are_retained_not_normalized(self):
        raw = {side: trace(side == "oracle") for side in ("native", "oracle")}
        raw["native"][3]["r31_lo"] = 0x00400260
        raw["oracle"][3]["r31_lo"] = 0x803011c0
        result = measure(raw, PROBE, [7, 8], SELECT)
        events = result["observations"][0]["selected_events"]
        self.assertNotEqual(events["native"][0]["r31_lo"], events["oracle"][0]["r31_lo"])
        self.assertFalse(result["alignment_validated"])

    def test_selection_and_window_bounds(self):
        raw = {side: trace(side == "oracle") for side in ("native", "oracle")}
        for key, value in (("register", True), ("register", 32), ("pc", "0x80000304"),
                           ("value_lo", "0x8000040"), ("arbitrary", "command")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                measure(raw, PROBE, [7, 8], dict(SELECT, **{key: value}))
        for window in ([7, 7], [8, 7], [0, 8], [1, 17], [True, 8]):
            with self.subTest(window=window), self.assertRaises(ValueError):
                measure(raw, PROBE, window, SELECT)


class RegisteredIntervalTests(unittest.TestCase):
    def observe(self, mutation=None):
        from scripts.autonomy import point_experiment, point_runtime
        from scripts import phase9_point_probe
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            seal = root / 'result.json'
            seal.write_text('{}')
            runtime = {'binding': {'path': 'registered', 'sha256': '1' * 64},
                       'record': {'calibration': {'path': 'calibrated', 'sha256': '2' * 64}},
                       'calibration': {'qualification': {'passed': True}, 'input_prefix': {'polls': 18}, 'evidence': {}}}
            for side in ('native', 'oracle'):
                directory = root / side
                directory.mkdir()
                path = directory / 'point-probe.tsv'
                path.write_text('retained bytes')
                runtime['record'][side] = str(directory)
                runtime['calibration']['evidence'][side] = {'point_trace': file_sha256(path)}
            checked = copy.deepcopy(runtime)
            if mutation == 'calibration':
                checked['calibration']['input_prefix']['polls'] = 99
            if mutation == 'before':
                (root / 'native/point-probe.tsv').write_text('changed')

            def read(path, *args, oracle):
                if mutation == 'during':
                    path.write_text('changed during parsing')
                return []

            context = {'point_runtime': runtime, 'window': [7, 8], 'plan_seal': seal}
            with patch.object(point_experiment, 'plan_context', return_value=context), \
                    patch.object(point_runtime, 'load', return_value=checked) as recheck, \
                    patch.object(phase9_point_probe, 'read', side_effect=read), \
                    patch('scripts.autonomy.point_interval_observation.measure', return_value={'observations': []}):
                result = observe_registered(None, root, root, 'plan', SELECT)
                recheck.assert_called_once_with(None, root, root, context)
                return result

    def test_adapter_rechecks_runtime_and_labels_engineering_not_autonomous_result(self):
        result = self.observe()
        self.assertTrue(result['qualification']['passed'])
        self.assertFalse(result['autonomous_plan_executed'])
        self.assertFalse(result['alignment_validated'])
        self.assertFalse(result['causal_fix_proved'])
        self.assertEqual(set(result['point_traces']), {'native', 'oracle'})

    def test_mutated_raw_capture_or_runtime_is_rejected(self):
        for mutation in ('before', 'during', 'calibration'):
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'changed'):
                self.observe(mutation)


if __name__ == "__main__":
    unittest.main()
