import copy
import unittest

from scripts.autonomy.experiment_plan import contract, validate, validate_contract


class ExperimentPlanTests(unittest.TestCase):
    def setUp(self):
        self.context = contract([7, 10])
        self.plan = {"operation": "state-words", "hypothesis": "step differs", "alternative": "other input differs",
                     "reason": "read before state onset", "observations": [
                         {"label": "step", "address": "0x80000004", "width": 4}],
                     "prediction": {"label": "step", "update": 8, "relation": "different"}}

    def test_accepts_bounded_typed_read_and_explicit_unsupported_operation(self):
        self.assertEqual(validate(self.plan, self.context), self.plan)
        stopped = dict(self.plan, operation="needs-instrumentation", observations=[], prediction=None)
        validate(stopped, self.context)
        with self.assertRaises(ValueError):
            validate(dict(stopped, observations=self.plan["observations"]), self.context)

    def test_no_commands_paths_extra_fields_or_arbitrary_operations(self):
        for key, value in (("argv", ["python", "arbitrary.py"]), ("output", "C:/escape")):
            with self.assertRaises(ValueError):
                validate(dict(self.plan, **{key: value}), self.context)
        with self.assertRaises(ValueError):
            validate(dict(self.plan, operation="write-memory"), self.context)

    def test_addresses_widths_and_duplicate_labels_fail_closed(self):
        for key, value in (("address", "0xA0000004"), ("address", "0x80400000"),
                           ("address", "0x80000003"), ("width", True), ("width", 8),
                           ("label", "../code")):
            bad = copy.deepcopy(self.plan)
            bad["observations"][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate(bad, self.context)
        with self.assertRaises(ValueError):
            validate(dict(self.plan, observations=self.plan["observations"] * 2), self.context)

    def test_prediction_cannot_escape_window_or_name_unobserved_data(self):
        for key, value in (("update", 6), ("update", 11), ("update", True),
                           ("label", "unobserved"), ("relation", "parity")):
            bad = copy.deepcopy(self.plan)
            bad["prediction"][key] = value
            with self.assertRaises(ValueError):
                validate(bad, self.context)

    def test_schema_identity_and_observation_budget_are_enforced(self):
        for context in (dict(self.context, schema_sha256="0" * 64), contract([1, 17]), contract([True, 4])):
            with self.assertRaises(ValueError):
                validate_contract(context)
        with self.assertRaises(ValueError):
            validate(dict(self.plan, observations=self.plan["observations"] * 13), self.context)
        with self.assertRaises(ValueError):
            validate(dict(self.plan, reason="x" * 601), self.context)

    def test_history_rejects_renamed_split_or_repredicted_known_bytes(self):
        context = contract([7, 10], [self.plan])
        validate_contract(context)
        for address, width, update in (("0x80000004", 4, 8), ("0x80000004", 2, 9),
                                      ("0x80000006", 1, 10)):
            plan = dict(self.plan, observations=[{"label": "renamed", "address": address, "width": width}],
                        prediction={"label": "renamed", "update": update, "relation": "equal"})
            with self.assertRaisesRegex(ValueError, "previously measured"):
                validate(plan, context)

    def test_prediction_itself_must_add_information_not_an_unrelated_read(self):
        context = contract([7, 10], [self.plan])
        novel = {"label": "new_word", "address": "0x80000008", "width": 4}
        plan = dict(self.plan, observations=[*self.plan["observations"], novel])
        with self.assertRaisesRegex(ValueError, "previously measured"):
            validate(plan, context)
        plan["prediction"] = {"label": "new_word", "update": 8, "relation": "different"}
        validate(plan, context)

    def test_exhausted_round_budget_requires_different_method(self):
        context = contract([7, 10], [self.plan] * 3)
        validate_contract(context)
        plan = dict(self.plan, observations=[{"label": "step", "address": "0x80000008", "width": 4}])
        with self.assertRaisesRegex(ValueError, "budget exhausted"):
            validate(plan, context)
        validate(dict(plan, operation="needs-instrumentation", observations=[], prediction=None), context)
        with self.assertRaises(ValueError):
            validate_contract(contract([7, 10], [self.plan] * 4))

    def test_history_contract_rejects_bad_ranges_duplicates_and_boolean_round(self):
        context = contract([7, 10], [self.plan])
        for fields in ({"round": True}, {"round": 1}, {"prior_reads": []},
                       {"prior_reads": context["prior_reads"] * 2},
                       {"prior_reads": [{"address": "0x80000003", "width": 4}]},
                       {"prior_reads": [{"address": "0x80000004", "width": True}]}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                validate_contract(dict(context, **fields))


if __name__ == "__main__":
    unittest.main()
