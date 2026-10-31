from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_graphics_task_bridge import (
    ROOT,
    load_json,
    validate_manifest_document,
    validate_pins,
)


class GraphicsTaskBridgeEvidenceTests(unittest.TestCase):
    @staticmethod
    def private_probe(root: str, suffix: str) -> str:
        return "/" + root + "/" + "example" + "/" + suffix

    def load_manifest_and_schema(self) -> tuple[dict[str, object], dict[str, object]]:
        manifest = load_json(ROOT / "config" / "graphics-task-bridge.json")
        schema = load_json(ROOT / "schemas" / "graphics-task-bridge.schema.json")
        assert isinstance(manifest, dict)
        assert isinstance(schema, dict)
        return manifest, schema

    def test_manifest_and_pins_validate(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        dependency_lock = load_json(ROOT / "dependencies.lock.json")
        self.assertEqual(validate_manifest_document(manifest, schema), [])
        self.assertEqual(validate_pins(manifest, dependency_lock), [])

    def test_pin_mismatch_is_rejected(self) -> None:
        manifest, _ = self.load_manifest_and_schema()
        dependency_lock = load_json(ROOT / "dependencies.lock.json")
        invalid = copy.deepcopy(manifest)
        pins = invalid["pins"]
        assert isinstance(pins, dict)
        pins["rt64"] = "0" * 40
        self.assertIn("pin mismatch for rt64", validate_pins(invalid, dependency_lock))

    def test_visual_progress_cannot_be_self_asserted(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        bridge = invalid["bridge"]
        family = invalid["family_surface"]
        evidence = invalid["evidence"]
        assert isinstance(bridge, dict)
        assert isinstance(family, dict)
        assert isinstance(evidence, dict)
        bridge["visual_output_produced"] = True
        family["shared_base_visual_renderer_implemented"] = True
        family["real_task_full_surface_coverage"] = True
        family["rt64_adapter_implemented"] = True
        evidence["visual_output_validation"] = "established"
        errors = validate_manifest_document(invalid, schema)
        self.assertIn("semantic output cannot be relabeled as rendered pixels", errors)
        self.assertIn("visual renderer evidence remains unimplemented", errors)
        self.assertIn("RT64 adapter remains unimplemented", errors)
        self.assertIn("visual output validation remains unestablished", errors)

    def test_reviewed_aggregate_cannot_be_expanded_or_weakened(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        evidence = invalid["evidence"]
        assert isinstance(evidence, dict)
        evidence["real_task_count"] = 2
        evidence["referenced_memory_closure"] = "established-for-corpus"
        evidence["semantic_output_validation"] = "digest-match"
        evidence["completion_after_oracle"] = False
        errors = validate_manifest_document(invalid, schema)
        self.assertIn(
            "reviewed graphics aggregate covers exactly one private task", errors
        )
        self.assertIn(
            "reviewed private aggregate differs from the locked evidence", errors
        )

    def test_g2_graphics_fallback_cannot_be_downgraded(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        decision = invalid["decision"]
        assert isinstance(decision, dict)
        decision["g2_gate"] = "blocked"
        errors = validate_manifest_document(invalid, schema)
        self.assertIn(
            "G2 graphics requires the proven bounded native fallback", errors
        )

    def test_semantic_fallback_proof_cannot_be_downgraded(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        bridge = invalid["bridge"]
        family = invalid["family_surface"]
        assert isinstance(bridge, dict)
        assert isinstance(family, dict)
        bridge["native_adapter_path"] = "rt64"
        bridge["semantic_output_kind_distinct"] = False
        bridge["semantic_output_payload_comparison"] = "digest"
        family["custom_handler_translation_implemented"] = False
        errors = validate_manifest_document(invalid, schema)
        self.assertIn("G2 graphics path must remain project bounded semantic", errors)
        self.assertIn("bounded semantic fallback proof cannot be weakened", errors)
        self.assertIn("bounded custom translation proof cannot be weakened", errors)

    def test_private_body_cannot_be_added(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        evidence = invalid["evidence"]
        assert isinstance(evidence, dict)
        evidence["private_body_present"] = True
        self.assertIn(
            "tracked graphics bridge evidence cannot contain private bodies",
            validate_manifest_document(invalid, schema),
        )

    def test_surface_count_is_fixed(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        family = invalid["family_surface"]
        assert isinstance(family, dict)
        family["base_custom_handler_count"] = 8
        errors = validate_manifest_document(invalid, schema)
        self.assertIn("schema: contract violation", errors)

    def test_broker_oracle_and_completion_contract_cannot_be_weakened(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        for member, value in (
            ("memory_reads_brokered", False),
            ("all_declared_regions_must_be_observed", False),
            ("independent_output_oracle_required", False),
            ("backend_oracle_distinct_object_required", False),
            ("referenced_region_min_count", 0),
            ("referenced_region_max_count", 257),
            ("referenced_memory_max_bytes", 8388609),
            ("completion_policy", "fallible-signal-after-validation"),
            ("renderer_completion_sink_order", "prepare-before-oracle"),
        ):
            with self.subTest(member=member):
                invalid = copy.deepcopy(manifest)
                bridge = invalid["bridge"]
                assert isinstance(bridge, dict)
                bridge[member] = value
                self.assertIn(
                    "schema: contract violation",
                    validate_manifest_document(invalid, schema),
                )

    def test_private_path_is_rejected(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        decision = invalid["decision"]
        assert isinstance(decision, dict)
        hostile_value = "Inspect " + self.private_probe(
            "tmp", "private/graphics-task.bin"
        )
        decision["next_gate"] = hostile_value
        errors = validate_manifest_document(invalid, schema)
        self.assertIn("privacy: public-safe contract violation", errors)
        self.assertNotIn(hostile_value, "\n".join(errors))

    def test_integral_float_tokens_are_rejected(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        bridge = invalid["bridge"]
        assert isinstance(bridge, dict)
        bridge["active_program_max_bytes"] = 4096.0
        errors = validate_manifest_document(invalid, schema)
        self.assertIn("numbers: canonical integer contract violation", errors)

    def test_schema_errors_do_not_echo_hostile_keys_or_values(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        hostile_key = "private-path-" + self.private_probe("home", "sensitive")
        hostile_value = self.private_probe("home", "sensitive/body.bin")
        invalid[hostile_key] = hostile_value
        errors = validate_manifest_document(invalid, schema)
        rendered = "\n".join(errors)
        self.assertIn("schema: contract violation", errors)
        self.assertIn("privacy: public-safe contract violation", errors)
        self.assertNotIn(hostile_key, rendered)
        self.assertNotIn(hostile_value, rendered)

    def test_invalid_schema_fails_closed_without_echo(self) -> None:
        manifest, _ = self.load_manifest_and_schema()
        hostile_value = self.private_probe("home", "sensitive/schema")
        invalid_schema = {"type": 7, "description": hostile_value}
        errors = validate_manifest_document(manifest, invalid_schema)
        rendered = "\n".join(errors)
        self.assertIn("schema: invalid validation contract", errors)
        self.assertNotIn(hostile_value, rendered)

    def test_valid_but_unreviewed_schema_is_rejected(self) -> None:
        manifest, _ = self.load_manifest_and_schema()
        permissive_schema = {"$schema": "https://json-schema.org/draft/2020-12/schema"}
        errors = validate_manifest_document(manifest, permissive_schema)
        self.assertIn(
            "schema: reviewed validation contract differs from lock", errors
        )

    def test_programmatic_non_json_document_fails_closed(self) -> None:
        _, schema = self.load_manifest_and_schema()
        errors = validate_manifest_document({"unexpected": {"not-json"}}, schema)
        self.assertEqual(errors, ["document: non-JSON value"])

    def test_duplicate_dependency_identifiers_fail_closed(self) -> None:
        manifest, _ = self.load_manifest_and_schema()
        dependency_lock = load_json(ROOT / "dependencies.lock.json")
        assert isinstance(dependency_lock, dict)
        repositories = dependency_lock["repositories"]
        assert isinstance(repositories, list)
        duplicate_lock = copy.deepcopy(dependency_lock)
        duplicate_repositories = duplicate_lock["repositories"]
        assert isinstance(duplicate_repositories, list)
        duplicate_repositories.append(copy.deepcopy(repositories[0]))
        self.assertIn(
            "dependency lock contains duplicate repository identifiers",
            validate_pins(manifest, duplicate_lock),
        )

    def test_malformed_dependency_record_fails_closed(self) -> None:
        manifest, _ = self.load_manifest_and_schema()
        malformed_lock = {"repositories": [{"id": [], "commit": "ignored"}]}
        errors = validate_pins(manifest, malformed_lock)
        self.assertIn("dependency lock contains an invalid repository record", errors)
        self.assertIn("pin mismatch for rt64", errors)

    def test_duplicate_keys_and_nonstandard_numbers_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            duplicate = Path(directory) / "duplicate.json"
            nonstandard = Path(directory) / "nonstandard.json"
            duplicate.write_text('{"safe": 1, "safe": 2}', encoding="utf-8")
            nonstandard.write_text('{"safe": NaN}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate JSON object key"):
                load_json(duplicate)
            with self.assertRaisesRegex(ValueError, "non-standard JSON number"):
                load_json(nonstandard)

    def test_malformed_json_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            malformed = Path(directory) / "malformed.json"
            malformed.write_text('{"safe": ', encoding="utf-8")
            with self.assertRaises(json.JSONDecodeError):
                load_json(malformed)

    def test_reviewed_manifest_lock_rejects_narrative_changes(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        decision = invalid["decision"]
        assert isinstance(decision, dict)
        decision["next_gate"] = "Implement a renderer adapter and validate sanitized output."
        errors = validate_manifest_document(invalid, schema)
        self.assertIn(
            "current-pin graphics bridge manifest differs from the reviewed lock",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
