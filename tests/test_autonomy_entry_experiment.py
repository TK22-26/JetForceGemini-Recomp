import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.autonomy import entry_plan, entry_observation as observation, entry_experiment as experiment
from scripts.autonomy import experiment_plan


class EntryPlanTests(unittest.TestCase):
    def setUp(self):
        self.plan = {"operation": "entry-gpr", "hypothesis": "argument differs", "alternative": "argument equal",
                     "reason": "observe consumption", "probe": {"entry_pc": "0x80000200", "call_pc": "0x80000100"},
                     "prediction": {"update": 8, "register": 5, "relation": "different"}}
        self.contract = entry_plan.contract([7, 8])

    def test_typed_read_and_explicit_unsupported_primitive(self):
        entry_plan.validate(self.plan, self.contract)
        entry_plan.validate(dict(self.plan, operation="needs-instrumentation", probe=None, prediction=None), self.contract)
        for key, value in (("argv", ["arbitrary"]), ("output", "escape")):
            with self.assertRaises(ValueError):
                entry_plan.validate(dict(self.plan, **{key: value}), self.contract)

    def test_invalid_pc_register_or_window_is_rejected(self):
        for field, value in (("entry_pc", "0x80000201"), ("call_pc", "0x803ffffc"), ("entry_pc", "0xa0000200")):
            plan = copy.deepcopy(self.plan)
            plan["probe"][field] = value
            with self.assertRaises(ValueError):
                entry_plan.validate(plan, self.contract)
        for field, value in (("register", True), ("register", 32), ("update", 9), ("relation", "parity")):
            plan = copy.deepcopy(self.plan)
            plan["prediction"][field] = value
            with self.assertRaises(ValueError):
                entry_plan.validate(plan, self.contract)

    def test_all_registers_measured_so_changing_prediction_does_not_authorize_repeat(self):
        context = entry_plan.contract([7, 8], [self.plan])
        plan = copy.deepcopy(self.plan)
        plan["prediction"]["register"] = 6
        with self.assertRaisesRegex(ValueError, "repeats"):
            entry_plan.validate(plan, context)
        plan["probe"]["call_pc"] = "0x80000120"
        with self.assertRaisesRegex(ValueError, "repeats"):
            entry_plan.validate(plan, context)
        plan["probe"]["entry_pc"] = "0x80000300"
        entry_plan.validate(plan, context)
        with self.assertRaisesRegex(ValueError, "round budget"):
            entry_plan.validate(plan, entry_plan.contract([7, 8], [self.plan] * 3))

    def test_mixed_history_keeps_independent_method_budgets(self):
        word = {"operation": "state-words", "observations": [{"label": "word", "address": "0x80000004", "width": 4}]}
        mixed = [word, self.plan]
        self.assertEqual(entry_plan.contract([7, 8], mixed)["round"], 2)
        self.assertEqual(experiment_plan.contract([7, 8], mixed)["round"], 2)
        self.assertEqual(experiment_plan.contract([7, 8], mixed)["prior_reads"], [{"address": "0x80000004", "width": 4}])


class EntryObservationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.plan = {"operation": "entry-gpr", "probe": {"entry_pc": "0x80000200", "call_pc": "0x80000100"},
                     "prediction": {"update": 8, "register": 5, "relation": "different"}}
        self.write_calls()

    def write_calls(self, *, wrong_ra=False, wrong_poll=False, duplicate=False, mismatch_args=False):
        for side in ("native", "oracle"):
            directory = self.directory / side
            directory.mkdir(exist_ok=True)
            oracle = side == "oracle"
            prefix = ["frame", "completed_updates", "controller_polls", "consumed_vi", "pc"] if oracle else [
                "update_candidate", "vi_retraces", "controller_polls", "target"]
            rows = {"args": ["\t".join(prefix + [f"a{i}" for i in range(4)])],
                    "gpr": ["\t".join(prefix + [f"r{i}_{part}" for i in range(32) for part in ("lo", "hi")])]}
            for update in ([7, 8, 8] if duplicate and oracle else [7, 8]):
                polls = update + 2 + (wrong_poll and oracle)
                clocks = [update * 3 + 30, update - 1, polls, update * 3] if oracle else [update, update * 3, polls]
                metadata = list(map(str, clocks)) + ["0x80000200"]
                registers = [0] * 32
                registers[5] = 4 if oracle and update == 8 else 3
                registers[31] = 0x8000010c if wrong_ra and oracle else 0x80000108
                args = [f"0x{value:08x}" for value in registers[4:8]]
                if mismatch_args and oracle:
                    args[1] = "0x00000009"
                rows["args"].append("\t".join(metadata + args))
                rows["gpr"].append("\t".join(metadata + [f"0x{(value if part == 'lo' else 0):08x}"
                                  for value in registers for part in ("lo", "hi")]))
            for kind, lines in rows.items():
                if oracle:
                    lines.append(f"result\ttrue\t{len(lines)-1}")
                (directory / f"entry-{kind}.tsv").write_text("\n".join(lines) + "\n")

    def measure(self, unchanged=True):
        return observation.measure(self.directory, self.plan, [7, 8], traces_unchanged=unchanged, instructions=[])

    def test_qualified_argument_delivery_preserves_raw_clocks_and_all_registers(self):
        report = self.measure()
        self.assertTrue(report["qualification"]["passed"])
        self.assertTrue(report["prediction_observed"])
        self.assertEqual(report["prediction_observation"]["native"], "0x0000000000000003")
        self.assertEqual(report["prediction_observation"]["oracle"], "0x0000000000000004")
        self.assertEqual(report["raw_calls"]["oracle"][1]["raw_clocks"]["completed_updates"], 7)
        self.assertEqual(report["raw_calls"]["native"][1]["raw_clocks"]["update_candidate"], 8)
        self.assertEqual(len(report["raw_calls"]["native"][1]["gpr"]), 32)
        self.assertFalse(report["alignment_validated"])
        self.assertFalse(report["causal_fix_proved"])
        self.assertFalse(report["parity_verified"])

    def test_changed_traces_make_prediction_inconclusive(self):
        report = self.measure(False)
        self.assertFalse(report["qualification"]["passed"])
        self.assertIsNone(report["prediction_observed"])

    def test_wrong_caller_poll_position_or_ambiguous_calls_are_inconclusive(self):
        for option in ("wrong_ra", "wrong_poll", "duplicate"):
            self.write_calls(**{option: True})
            with self.subTest(option=option):
                report = self.measure()
                self.assertFalse(report["qualification"]["passed"])
                self.assertIsNone(report["prediction_observed"])

    def test_argument_and_gpr_disagreement_fails_closed(self):
        self.write_calls(mismatch_args=True)
        with self.assertRaisesRegex(ValueError, "different calls"):
            self.measure()

    def test_missing_footer_and_bad_register_rejected(self):
        path = self.directory / "oracle/entry-gpr.tsv"
        original = path.read_text()
        path.write_text("\n".join(original.splitlines()[:-1]) + "\n")
        with self.assertRaisesRegex(ValueError, "footer"):
            self.measure()
        path.write_text(original.replace("0x00000003", "0x100000000"))
        with self.assertRaisesRegex(ValueError, "32-bit"):
            self.measure()

    def test_direct_jal_nop_instruction_qualification(self):
        image = bytearray(4 * 1024 * 1024)
        image[0x100:0x104] = (0x0c000080).to_bytes(4, "big")
        image[0x200:0x204] = (0x27bdfff8).to_bytes(4, "big")
        with patch.object(observation, "_records_at", return_value={7:{},8:{}}), \
                patch.object(observation, "_snapshot", side_effect=lambda *_: (bytes(image), "fixture")):
            rows = observation.instruction_evidence(self.directory, [7, 8], self.plan["probe"])
            self.assertEqual(len(rows), 2)
            image[0x104:0x108] = (1).to_bytes(4, "big")
            with self.assertRaisesRegex(ValueError, "NOP"):
                observation.instruction_evidence(self.directory, [7, 8], self.plan["probe"])
            image[0x104:0x108] = bytes(4)
            image[0x100:0x104] = (0x0c000081).to_bytes(4, "big")
            with self.assertRaisesRegex(ValueError, "JAL"):
                observation.instruction_evidence(self.directory, [7, 8], self.plan["probe"])


if __name__ == "__main__":
    unittest.main()
