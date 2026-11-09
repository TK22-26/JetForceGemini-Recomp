import unittest

from scripts.autonomy.scheduler import (
    vi_boundary_diagnosis_facts, vi_boundary_diagnosis_id,
)
from scripts.autonomy.supervisor import SupervisorError


class ViDiagnosisFactsTests(unittest.TestCase):
    def reports(self):
        pair = {"native_before": 1264, "native_after": 1265,
                "oracle_before": 1260, "oracle_after": 1261}
        vi = {"kind": "jfg-phase9-vi-boundary-comparison",
              "focused_update_pair": pair, "hook_equivalence": "unvalidated",
              "alignment_validated": False, "parity_verified": False,
              "input_sha256": "a" * 64,
              "lead_in": {"native_consumptions": 2,
                          "oracle_consumptions": 2,
                          "first_relative_mismatch": None},
              "onset": {"native_consumptions": 2,
                        "oracle_consumptions": 2,
                        "first_relative_mismatch": {
                            "relative_consumption": 1,
                            "semantic_state_match": False}}}
        focus = {"kind": "jfg-phase9-focus-rdram-comparison",
                 "alignment_validated": False, "parity_verified": False,
                 "input_sha256": "a" * 64,
                 "before": {"native_update": 1264, "oracle_update": 1260,
                            "semantic_state_match": True,
                            "actor_byte_differences": []},
                 "after": {"native_update": 1265, "oracle_update": 1261,
                           "semantic_state_match": False,
                           "actor_byte_differences": [{"index": 11}]},
                 "controller_inputs_between": {"same_values": True}}
        transition = {"kind": "jfg-phase9-rdram-transition-comparison",
                      "focused_update_pair": pair,
                      "alignment_validated": False, "parity_verified": False,
                      "input_sha256": "a" * 64,
                      "actor_word_changes": {
                          "scope": "stable-actor-slots-raw-words-diagnostic-only",
                          "total_newly_divergent_words": 2,
                          "first_newly_divergent_words": [
                              {"index": 11, "word_offset": "0x0ec"},
                              {"index": 11, "word_offset": "0x0fc"}]},
                      "transition": {"new_actor_bytes": 3,
                                     "new_non_actor_bytes": 1989}}
        return vi, focus, transition

    def test_facts_reflect_equal_vi_counts_at_new_boundary(self):
        facts = vi_boundary_diagnosis_facts(*self.reports())
        self.assertEqual(facts["lead_in"]["native_consumptions"], 2)
        self.assertEqual(facts["lead_in"]["oracle_consumptions"], 2)
        self.assertIsNone(facts["lead_in"]["first_relative_mismatch"])
        self.assertEqual(facts["onset"]["first_relative_mismatch"][
            "relative_consumption"], 1)
        self.assertEqual(facts["before"]["actor_difference_count"], 0)
        self.assertEqual(facts["after"]["actor_difference_count"], 1)
        self.assertTrue(facts["controller_values_match"])
        self.assertEqual(facts["new_actor_bytes"], 3)
        self.assertEqual(facts["new_actor_word_count"], 2)
        self.assertEqual([row["word_offset"] for row in
                          facts["first_actor_word_offsets"]],
                         ["0x0ec", "0x0fc"])
        self.assertFalse(facts["alignment_validated"])
        self.assertFalse(facts["parity_verified"])

    def test_rejects_changed_report_identity_or_missing_counts(self):
        vi, focus, transition = self.reports()
        transition["focused_update_pair"] = {"native_after": 999}
        with self.assertRaises(SupervisorError):
            vi_boundary_diagnosis_facts(vi, focus, transition)
        vi, focus, transition = self.reports()
        vi["lead_in"].pop("oracle_consumptions")
        with self.assertRaises(SupervisorError):
            vi_boundary_diagnosis_facts(vi, focus, transition)

    def test_v2_identity_is_report_specific(self):
        first = vi_boundary_diagnosis_id("vi-boundary-example", "a" * 64)
        second = vi_boundary_diagnosis_id("vi-boundary-example", "b" * 64)
        self.assertNotEqual(first, second)
        self.assertIn("diagnosis-v2", first)


if __name__ == "__main__":
    unittest.main()
