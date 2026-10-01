from __future__ import annotations

import copy
import unittest

from scripts.validate_phase8_acceptance import (
    ROOT,
    load_json,
    validate_completion,
    validate_contract,
)


class Phase8AcceptanceTests(unittest.TestCase):
    def inputs(self) -> tuple[dict[str, object], dict[str, object]]:
        contract = load_json(ROOT / "config" / "phase8-acceptance.json")
        schema = load_json(ROOT / "schemas" / "phase8-acceptance.schema.json")
        assert isinstance(contract, dict)
        assert isinstance(schema, dict)
        return contract, schema

    def test_current_contract_validates_with_expected_summary_state(self) -> None:
        contract, schema = self.inputs()
        self.assertEqual(
            validate_contract(
                contract,
                schema,
                completion_summary_exists=contract.get("status") == "complete",
            ),
            [],
        )

    def test_complete_requires_all_gates_and_summary(self) -> None:
        contract, schema = self.inputs()
        contract["status"] = "complete"
        gates = contract["gates"]
        assert isinstance(gates, dict)
        gates["deterministic_replays_match"] = False
        errors = validate_contract(contract, schema, completion_summary_exists=False)
        self.assertIn(
            "Phase 8 cannot be complete while an acceptance gate is open", errors
        )
        self.assertIn("Phase 8 completion summary is absent", errors)

    def test_required_scenarios_and_thresholds_cannot_be_weakened(self) -> None:
        contract, schema = self.inputs()
        invalid = copy.deepcopy(contract)
        scope = invalid["scope"]
        assert isinstance(scope, dict)
        scope["required_scenarios"] = ["launch-to-title"]
        scope["required_input_replays"] = 1
        scope["minimum_audio_seconds"] = 1
        scope["maximum_unsupported_runtime_boundaries"] = 1
        errors = validate_contract(invalid, schema, completion_summary_exists=False)
        self.assertIn("all four Phase 8 scenarios must remain in order", errors)
        self.assertIn("Phase 8 requires at least three input replays", errors)
        self.assertIn("Phase 8 requires at least sixty seconds of audio", errors)
        self.assertIn("Phase 8 permits no unsupported runtime boundary", errors)

    def test_evidence_cannot_be_self_attested(self) -> None:
        contract, schema = self.inputs()
        invalid = copy.deepcopy(contract)
        evidence = invalid["evidence_format"]
        assert isinstance(evidence, dict)
        evidence["oracle"] = "native-self-attested"
        evidence["save_policy"] = "same-process"
        errors = validate_contract(invalid, schema, completion_summary_exists=False)
        self.assertIn("Phase 8 evidence policy changed: oracle", errors)
        self.assertIn("Phase 8 evidence policy changed: save_policy", errors)

    def test_premature_completion_summary_is_rejected(self) -> None:
        contract, schema = self.inputs()
        contract["status"] = "in-progress"
        self.assertIn(
            "completion summary cannot exist while Phase 8 is in progress",
            validate_contract(contract, schema, completion_summary_exists=True),
        )

    def test_completion_requires_repeat_journal_hashes(self) -> None:
        contract, _ = self.inputs()
        summary = load_json(ROOT / "evidence" / "phase8-completion.json")
        assert isinstance(summary, dict)
        scenarios = summary["scenarios"]
        assert isinstance(scenarios, list) and isinstance(scenarios[0], dict)
        scenarios[0].pop("repeat_journal_hashes")
        self.assertIn(
            "launch-to-title: deterministic journal hashes are invalid",
            validate_completion(summary, contract),
        )


if __name__ == "__main__":
    unittest.main()
