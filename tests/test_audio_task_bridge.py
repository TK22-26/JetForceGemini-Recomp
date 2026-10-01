from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_audio_task_bridge import (
    ROOT,
    load_json,
    validate_manifest_document,
    validate_pins,
)


class AudioTaskBridgeEvidenceTests(unittest.TestCase):
    @staticmethod
    def private_probe(root: str, suffix: str) -> str:
        return "/" + root + "/" + "example" + "/" + suffix

    def load_manifest_and_schema(self) -> tuple[dict[str, object], dict[str, object]]:
        manifest = load_json(ROOT / "config" / "audio-task-bridge.json")
        schema = load_json(ROOT / "schemas" / "audio-task-bridge.schema.json")
        assert isinstance(manifest, dict)
        assert isinstance(schema, dict)
        return manifest, schema

    def test_manifest_and_pins_validate(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        dependency_lock = load_json(ROOT / "dependencies.lock.json")
        self.assertEqual(validate_manifest_document(manifest, schema), [])
        self.assertEqual(validate_pins(manifest, dependency_lock), [])

    def test_pins_are_bound_to_dependency_lock(self) -> None:
        manifest, _ = self.load_manifest_and_schema()
        dependency_lock = load_json(ROOT / "dependencies.lock.json")
        invalid = copy.deepcopy(manifest)
        pins = invalid["pins"]
        assert isinstance(pins, dict)
        pins["n64recomp"] = "0" * 40
        self.assertIn("pin mismatch for n64recomp", validate_pins(invalid, dependency_lock))

    def test_real_second_variant_cannot_be_self_asserted(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        upstream = invalid["upstream_contract"]
        assert isinstance(upstream, dict)
        upstream["real_second_variant_executed"] = True
        errors = validate_manifest_document(invalid, schema)
        self.assertIn("real second audio variant remains unexecuted", errors)

    def test_reviewed_adapter_progress_cannot_be_removed(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        variants = invalid["variant_surface"]
        assert isinstance(variants, dict)
        variants["rsp_adapter_implemented"] = False
        errors = validate_manifest_document(invalid, schema)
        self.assertIn("audio variant aggregate differs from reviewed evidence", errors)

    def test_reviewed_primary_real_evidence_cannot_be_changed(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        evidence = invalid["evidence"]
        assert isinstance(evidence, dict)
        evidence["real_task_count"] = 0
        evidence["real_referenced_memory_closure"] = "not-established"
        evidence["real_output_validation"] = "not-established"
        evidence["private_output_oracle_compared"] = False
        errors = validate_manifest_document(invalid, schema)
        self.assertIn("primary real audio task aggregate differs from review", errors)
        self.assertIn("primary real audio proof aggregate differs from review", errors)

    def test_private_body_claim_is_rejected(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        evidence = invalid["evidence"]
        assert isinstance(evidence, dict)
        evidence["private_body_present"] = True
        errors = validate_manifest_document(invalid, schema)
        self.assertIn(
            "tracked audio bridge evidence cannot contain private bodies", errors
        )

    def test_secondary_search_aggregate_cannot_be_changed(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        evidence = invalid["evidence"]
        assert isinstance(evidence, dict)
        evidence["secondary_search_overlay_swap_task_count"] = 1
        errors = validate_manifest_document(invalid, schema)
        self.assertIn("primary real audio proof aggregate differs from review", errors)

    def test_installed_worker_aggregate_cannot_be_removed(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        evidence = invalid["evidence"]
        assert isinstance(evidence, dict)
        evidence["real_installed_worker_execution_passed"] = False
        errors = validate_manifest_document(invalid, schema)
        self.assertIn("primary real audio proof aggregate differs from review", errors)

    def test_g2_audio_decision_requires_generated_secondary_fallback(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        variants = invalid["variant_surface"]
        evidence = invalid["evidence"]
        assert isinstance(variants, dict)
        assert isinstance(evidence, dict)
        variants["secondary_generated_fail_closed_execution_passed"] = False
        evidence["secondary_fallback_completion_count"] = 1
        errors = validate_manifest_document(invalid, schema)
        self.assertIn(
            "audio variant aggregate differs from reviewed evidence", errors
        )
        self.assertIn(
            "secondary generated fallback aggregate differs from review", errors
        )

    def test_g2_audio_decision_cannot_be_downgraded(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        decision = invalid["decision"]
        assert isinstance(decision, dict)
        decision["g2_gate"] = "blocked"
        decision["remaining_blocker_count"] = 1
        errors = validate_manifest_document(invalid, schema)
        self.assertIn(
            "G2 audio requirement decision differs from reviewed evidence", errors
        )

    def test_variant_count_is_fixed(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        variants = invalid["variant_surface"]
        assert isinstance(variants, dict)
        variants["program_variant_count"] = 1
        self.assertIn("schema: contract violation", validate_manifest_document(invalid, schema))

    def test_private_path_is_rejected_without_echo(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        decision = invalid["decision"]
        assert isinstance(decision, dict)
        hostile = "Inspect " + self.private_probe("tmp", "audio/body.bin")
        decision["next_gate"] = hostile
        errors = validate_manifest_document(invalid, schema)
        self.assertIn("privacy: public-safe contract violation", errors)
        self.assertNotIn(hostile, "\n".join(errors))

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
        hostile = self.private_probe("home", "sensitive/schema")
        errors = validate_manifest_document(
            manifest, {"type": 7, "description": hostile}
        )
        self.assertIn("schema: invalid validation contract", errors)
        self.assertNotIn(hostile, "\n".join(errors))

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
        self.assertIn("pin mismatch for n64recomp", errors)

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
        decision["next_gate"] = "Integrate the audio adapter and validate output."
        errors = validate_manifest_document(invalid, schema)
        self.assertIn(
            "current-pin audio bridge manifest differs from the reviewed lock", errors
        )


if __name__ == "__main__":
    unittest.main()
