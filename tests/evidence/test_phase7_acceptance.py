from __future__ import annotations

import copy
import unittest

from scripts.validate_phase7_acceptance import (
    ROOT,
    load_json,
    validate_completion,
    validate_contract,
)


class Phase7AcceptanceTests(unittest.TestCase):
    def inputs(self) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        contract = load_json(ROOT / "config" / "phase7-acceptance.json")
        schema = load_json(ROOT / "schemas" / "phase7-acceptance.schema.json")
        dependency_lock = load_json(ROOT / "dependencies.lock.json")
        assert isinstance(contract, dict)
        assert isinstance(schema, dict)
        assert isinstance(dependency_lock, dict)
        return contract, schema, dependency_lock

    def test_current_complete_contract_validates(self) -> None:
        contract, schema, dependency_lock = self.inputs()
        self.assertEqual(
            validate_contract(
                contract,
                schema,
                dependency_lock,
                completion_summary_exists=True,
            ),
            [],
        )

    def test_completion_requires_every_gate_and_summary(self) -> None:
        contract, schema, dependency_lock = self.inputs()
        complete = copy.deepcopy(contract)
        complete["status"] = "complete"
        gates = complete["gates"]
        assert isinstance(gates, dict)
        gates["gameplay_compared"] = False
        errors = validate_contract(
            complete,
            schema,
            dependency_lock,
            completion_summary_exists=False,
        )
        self.assertIn(
            "Phase 7 cannot be complete while an acceptance gate is open", errors
        )
        self.assertIn("Phase 7 completion summary is absent", errors)

    def test_complete_contract_accepts_only_all_true_gates(self) -> None:
        contract, schema, dependency_lock = self.inputs()
        complete = copy.deepcopy(contract)
        complete["status"] = "complete"
        gates = complete["gates"]
        assert isinstance(gates, dict)
        for key in gates:
            gates[key] = True
        self.assertEqual(
            validate_contract(
                complete,
                schema,
                dependency_lock,
                completion_summary_exists=True,
            ),
            [],
        )

    def test_one_scene_or_one_real_task_is_not_m3(self) -> None:
        contract, schema, dependency_lock = self.inputs()
        invalid = copy.deepcopy(contract)
        scope = invalid["scope"]
        assert isinstance(scope, dict)
        scope["required_scenes"] = ["boot-title"]
        scope["minimum_real_task_count"] = 1
        errors = validate_contract(
            invalid,
            schema,
            dependency_lock,
            completion_summary_exists=False,
        )
        self.assertIn("both required Phase 7 scenes must remain in scope", errors)
        self.assertIn("Phase 7 requires real tasks from both scenes", errors)

    def test_visual_oracle_and_repetitions_cannot_be_weakened(self) -> None:
        contract, schema, dependency_lock = self.inputs()
        invalid = copy.deepcopy(contract)
        evidence = invalid["evidence_format"]
        assert isinstance(evidence, dict)
        evidence["private_artifact_policy"] = "tracked"
        evidence["pixel_comparison"] = "self-attested"
        evidence["pixel_comparator"] = "unreviewed.py"
        evidence["ssim_prefilter"] = "none"
        evidence["minimum_ssim_millionths"] = 100000
        evidence["minimum_foreground_iou_millionths"] = 100000
        evidence["maximum_mean_absolute_error_millionths"] = 1000000
        evidence["repeat_count"] = 1
        errors = validate_contract(
            invalid,
            schema,
            dependency_lock,
            completion_summary_exists=False,
        )
        self.assertIn("visual bodies must remain ignored and local", errors)
        self.assertIn(
            "visual acceptance requires an independent emulator oracle", errors
        )
        self.assertIn(
            "visual determinism requires at least three repetitions", errors
        )
        self.assertIn("the pinned Phase 7 pixel comparator is required", errors)
        self.assertIn("the structural SSIM prefilter policy is required", errors)
        self.assertIn("visual comparison thresholds cannot be weakened", errors)

    def test_dependency_pin_drift_is_rejected(self) -> None:
        contract, schema, dependency_lock = self.inputs()
        invalid = copy.deepcopy(contract)
        pins = invalid["pins"]
        assert isinstance(pins, dict)
        pins["rt64"] = "0" * 40
        self.assertIn(
            "pin mismatch for rt64",
            validate_contract(
                invalid,
                schema,
                dependency_lock,
                completion_summary_exists=False,
            ),
        )

    def test_premature_summary_is_rejected(self) -> None:
        contract, schema, dependency_lock = self.inputs()
        in_progress = copy.deepcopy(contract)
        in_progress["status"] = "in-progress"
        self.assertIn(
            "completion summary cannot exist while Phase 7 is in progress",
            validate_contract(
                in_progress,
                schema,
                dependency_lock,
                completion_summary_exists=True,
            ),
        )

    def test_completion_summary_is_reconciled(self) -> None:
        contract, _, _ = self.inputs()
        summary = load_json(ROOT / "evidence" / "phase7-completion.json")
        self.assertEqual(validate_completion(summary, contract), [])

        changed = copy.deepcopy(summary)
        isolation = changed["simulation_isolation"]
        assert isinstance(isolation, dict)
        hashes = isolation["scene_hashes"]
        assert isinstance(hashes, list) and isinstance(hashes[0], dict)
        hashes[0]["rt64"] = "0" * 64
        self.assertIn(
            "boot-title: simulation hashes differ",
            validate_completion(changed, contract),
        )


if __name__ == "__main__":
    unittest.main()
