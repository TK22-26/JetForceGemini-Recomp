from __future__ import annotations

import copy
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.validate_rsp_task_manifest import (
    ROOT,
    load_json,
    validate_manifest_document,
    validate_pins,
    validate_tracked_repository,
)


class RspTaskManifestTests(unittest.TestCase):
    def load_manifest_and_schema(self) -> tuple[dict[str, object], dict[str, object]]:
        manifest = load_json(ROOT / "config" / "rsp-task-manifest.json")
        schema = load_json(ROOT / "schemas" / "rsp-task-manifest.schema.json")
        assert isinstance(manifest, dict)
        assert isinstance(schema, dict)
        return manifest, schema

    def test_manifest_and_pins_validate(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        dependency_lock = load_json(ROOT / "dependencies.lock.json")
        self.assertEqual(validate_manifest_document(manifest, schema), [])
        self.assertEqual(validate_pins(manifest, dependency_lock), [])

    def test_executed_fallback_commit_is_bound_to_dependency_lock(self) -> None:
        manifest, _ = self.load_manifest_and_schema()
        dependency_lock = load_json(ROOT / "dependencies.lock.json")
        invalid = copy.deepcopy(manifest)
        graphics = invalid["graphics_path"]
        assert isinstance(graphics, dict)
        fallback = graphics["tested_fallback"]
        assert isinstance(fallback, dict)
        fallback["commit"] = "0" * 40
        errors = validate_pins(invalid, dependency_lock)
        self.assertIn("executed graphics fallback provenance is inconsistent", errors)

    def test_capture_binary_hashes_are_bound_to_dependency_lock(self) -> None:
        manifest, _ = self.load_manifest_and_schema()
        dependency_lock = load_json(ROOT / "dependencies.lock.json")
        invalid = copy.deepcopy(manifest)
        capture = invalid["capture_evidence"]
        assert isinstance(capture, dict)
        capture["emulator_package_sha256"] = "0" * 64
        capture["graphics_plugin_binary_sha256"] = "1" * 64
        errors = validate_pins(invalid, dependency_lock)
        self.assertIn("BizHawk package hash differs from dependency lock", errors)
        self.assertIn(
            "executed graphics plug-in hash differs from dependency lock", errors
        )

    def test_inspected_source_commit_is_bound_to_dependency_lock(self) -> None:
        manifest, _ = self.load_manifest_and_schema()
        dependency_lock = load_json(ROOT / "dependencies.lock.json")
        invalid = copy.deepcopy(manifest)
        graphics = invalid["graphics_path"]
        assert isinstance(graphics, dict)
        inspected = graphics["source_inspection_candidate"]
        scope = graphics["clean_room_scope"]
        assert isinstance(inspected, dict)
        assert isinstance(scope, dict)
        inspected["commit"] = "0" * 40
        scope["source_commit"] = "1" * 40
        errors = validate_pins(invalid, dependency_lock)
        self.assertIn("graphics source-inspection provenance is inconsistent", errors)
        self.assertIn("graphics clean-room scope provenance is inconsistent", errors)

    def test_private_capture_body_field_is_rejected(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        capture = invalid["capture_evidence"]
        assert isinstance(capture, dict)
        capture["body"] = "opaque"
        errors = validate_manifest_document(invalid, schema)
        self.assertTrue(any("forbidden private-body field" in item for item in errors))

    def test_schema_field_is_exact_and_privacy_scanned(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        invalid["$schema"] = " ".join(["AA", "BB", "CC", "DD", "EE", "FF"] * 2)
        errors = validate_manifest_document(invalid, schema)
        self.assertTrue(any("schema $schema" in item for item in errors))
        self.assertTrue(any("encoded-body" in item for item in errors))

    def test_case_variants_and_unc_private_details_are_rejected(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        probes = (
            "Inspect 0X89ABCDEF before continuing.",
            "Inspect FUNC_89ABCDEF before continuing.",
            "Inspect " + "\\\\HOST\\share\\capture" + " before continuing.",
            "Inspect /Home/Example/capture before continuing.",
        )
        for probe in probes:
            with self.subTest(probe=probe):
                invalid = copy.deepcopy(manifest)
                decision = invalid["decision"]
                assert isinstance(decision, dict)
                decision["next_gate"] = probe
                errors = validate_manifest_document(invalid, schema)
                self.assertTrue(any("private-path" in item for item in errors))

    def test_spaced_hex_body_in_safe_text_is_rejected(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        decision = invalid["decision"]
        assert isinstance(decision, dict)
        decision["next_gate"] = " ".join(
            ["AA", "BB", "CC", "DD", "EE", "FF"] * 2
        )
        errors = validate_manifest_document(invalid, schema)
        self.assertTrue(any("encoded-body" in item for item in errors))

    def test_digest_sized_chunks_and_generic_posix_paths_are_rejected(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        for probe in (
            ("a" * 64) + " " + ("b" * 64),
            "/tmp/private/capture.json",
            "/root/private/capture.json",
            "/var/folders/private/capture.json",
            "/workspace/private/capture.json",
        ):
            with self.subTest(probe=probe):
                invalid = copy.deepcopy(manifest)
                decision = invalid["decision"]
                assert isinstance(decision, dict)
                decision["next_gate"] = probe
                self.assertTrue(validate_manifest_document(invalid, schema))

    def test_self_consistent_attested_count_inflation_is_locked(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        inflated = 10**30
        capture = invalid["capture_evidence"]
        assert isinstance(capture, dict)
        records = capture["task_classes"]
        assert isinstance(records, list)
        for record in records:
            assert isinstance(record, dict)
            record["count"] = inflated
            record["unique_task_data_count"] = inflated
        capture["unique_task_count"] = inflated * len(records)
        audio = invalid["audio_path"]
        graphics = invalid["graphics_path"]
        assert isinstance(audio, dict)
        assert isinstance(graphics, dict)
        fallback = graphics["tested_fallback"]
        assert isinstance(fallback, dict)
        audio["representative_task_count"] = inflated
        audio["normal_exit_count"] = inflated
        fallback["representative_task_count"] = inflated
        errors = validate_manifest_document(invalid, schema)
        self.assertIn(
            "current-pin RSP manifest differs from the maintainer-reviewed lock",
            errors,
        )

    def test_integral_float_tokens_are_rejected(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        inventory = invalid["inventory"]
        assert isinstance(inventory, list)
        record = inventory[0]
        assert isinstance(record, dict)
        record["container_bytes"] = 384.0
        errors = validate_manifest_document(invalid, schema)
        self.assertTrue(any("canonical integer tokens" in item for item in errors))

    def test_duplicate_nested_task_class_id_is_rejected(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        capture = invalid["capture_evidence"]
        assert isinstance(capture, dict)
        records = capture["task_classes"]
        assert isinstance(records, list)
        records[1]["task_class"] = records[0]["task_class"]
        errors = validate_manifest_document(invalid, schema)
        self.assertTrue(any("duplicate task_class" in item for item in errors))

    def test_native_handler_flag_cannot_disable_gap_checks(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        graphics = invalid["graphics_path"]
        assert isinstance(graphics, dict)
        primary = graphics["primary"]
        fallback = graphics["tested_fallback"]
        assert isinstance(primary, dict)
        assert isinstance(fallback, dict)
        primary["native_handler_present"] = True
        fallback["representative_task_count"] = 1
        errors = validate_manifest_document(invalid, schema)
        self.assertIn(
            "graphics primary state differs from the pinned no-handler baseline", errors
        )
        self.assertIn(
            "graphics fallback count differs from captured graphics count", errors
        )

    def test_public_manifest_discloses_no_unbound_graphics_digest(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        capture = manifest["capture_evidence"]
        assert isinstance(capture, dict)
        fingerprint = capture["graphics_fingerprint"]
        assert isinstance(fingerprint, dict)
        self.assertEqual(fingerprint.get("digest_disclosed"), False)
        self.assertNotIn("value", fingerprint)
        self.assertNotIn("tracked_body_count", capture)
        self.assertEqual(
            capture.get("tracked_body_policy"), "defense-in-depth-git-index-scan"
        )
        self.assertEqual(validate_manifest_document(manifest, schema), [])

    def test_tracked_repository_scan_uses_actual_git_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(
                ["git", "init", "--quiet", str(root)],
                check=True,
                capture_output=True,
            )
            (root / "README.md").write_text("synthetic safe fixture\n", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(root), "add", "README.md"],
                check=True,
                capture_output=True,
            )
            self.assertEqual(validate_tracked_repository(root), [])
            (root / "synthetic.rom").write_bytes(b"synthetic test canary")
            subprocess.run(
                ["git", "-C", str(root), "add", "synthetic.rom"],
                check=True,
                capture_output=True,
            )
            errors = validate_tracked_repository(root)
            self.assertTrue(any("forbidden ROM-derived" in item for item in errors))

    def test_private_machine_path_is_rejected(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        decision = invalid["decision"]
        assert isinstance(decision, dict)
        decision["next_gate"] = "Read " + "C:" + "\\Users" + "\\Example\\capture.bin"
        errors = validate_manifest_document(invalid, schema)
        self.assertTrue(any("private-path" in item for item in errors))

    def test_native_graphics_gap_requires_task_path_tested_candidate(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        graphics = invalid["graphics_path"]
        assert isinstance(graphics, dict)
        fallback = graphics["tested_fallback"]
        assert isinstance(fallback, dict)
        fallback["status"] = "untested"
        errors = validate_manifest_document(invalid, schema)
        self.assertTrue(any("task-path-tested candidate" in item for item in errors))

    def test_native_handler_claim_cannot_disable_graphics_checks(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        graphics = invalid["graphics_path"]
        assert isinstance(graphics, dict)
        primary = graphics["primary"]
        fallback = graphics["tested_fallback"]
        assert isinstance(primary, dict)
        assert isinstance(fallback, dict)
        primary["native_handler_present"] = True
        fallback["status"] = "untested"

        errors = validate_manifest_document(invalid, schema)
        self.assertIn(
            "graphics primary state differs from the pinned no-handler baseline", errors
        )
        self.assertTrue(any("task-path-tested candidate" in item for item in errors))

    def test_graphics_gate_remains_blocked_without_render_output(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        decision = invalid["decision"]
        assert isinstance(decision, dict)
        decision["graphics_gate"] = "pass"
        errors = validate_manifest_document(invalid, schema)
        self.assertTrue(any("must remain blocked" in item for item in errors))

    def test_audio_counts_must_all_exit_normally(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        audio = invalid["audio_path"]
        assert isinstance(audio, dict)
        audio["normal_exit_count"] = 195
        errors = validate_manifest_document(invalid, schema)
        self.assertIn("audio representative tasks did not all exit normally", errors)

    def test_audio_path_requires_maintainer_attestation(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        audio = invalid["audio_path"]
        assert isinstance(audio, dict)
        audio["verification"] = "publicly-reproducible"
        errors = validate_manifest_document(invalid, schema)
        self.assertIn(
            "audio path evidence must remain explicitly maintainer-attested "
            "without a tracked regeneration harness",
            errors,
        )

    def test_audio_path_discloses_untracked_regeneration_harness(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        audio = invalid["audio_path"]
        assert isinstance(audio, dict)
        audio["regeneration_harness_tracked"] = True
        errors = validate_manifest_document(invalid, schema)
        self.assertIn(
            "audio path evidence must remain explicitly maintainer-attested "
            "without a tracked regeneration harness",
            errors,
        )

    def test_audio_count_must_match_private_capture_aggregate(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        audio = invalid["audio_path"]
        assert isinstance(audio, dict)
        audio["representative_task_count"] = 1
        audio["normal_exit_count"] = 1
        errors = validate_manifest_document(invalid, schema)
        self.assertIn(
            "audio representative count differs from captured audio count", errors
        )

    def test_capture_frame_and_unique_counts_are_ordered(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        capture = invalid["capture_evidence"]
        assert isinstance(capture, dict)
        records = capture["task_classes"]
        assert isinstance(records, list)
        audio = next(
            item
            for item in records
            if isinstance(item, dict) and item.get("task_class") == "audio"
        )
        audio["first_frame"] = 901
        audio["last_frame"] = 900
        audio["unique_ucode_count"] = 197
        errors = validate_manifest_document(invalid, schema)
        self.assertIn("audio: first frame exceeds last frame", errors)
        self.assertIn("audio: unique_ucode_count exceeds task count", errors)

    def test_graphics_count_must_match_private_capture_aggregate(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        graphics = invalid["graphics_path"]
        assert isinstance(graphics, dict)
        fallback = graphics["tested_fallback"]
        assert isinstance(fallback, dict)
        fallback["representative_task_count"] = 1
        errors = validate_manifest_document(invalid, schema)
        self.assertIn(
            "graphics fallback count differs from captured graphics count", errors
        )

    def test_audio_gate_remains_blocked_without_output_validation(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        decision = invalid["decision"]
        assert isinstance(decision, dict)
        decision["audio_gate"] = "pass"
        errors = validate_manifest_document(invalid, schema)
        self.assertTrue(any("audio gate must remain blocked" in item for item in errors))

    def test_no_overlay_disposition_must_have_zero_counts(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        inventory = invalid["inventory"]
        assert isinstance(inventory, list)
        boot = next(
            item
            for item in inventory
            if isinstance(item, dict) and item.get("id") == "boot-loader"
        )
        overlay = boot["overlay"]
        assert isinstance(overlay, dict)
        overlay["slot_count"] = 1
        errors = validate_manifest_document(invalid, schema)
        self.assertTrue(any("no-overlay disposition" in item for item in errors))

    def test_oversized_program_requires_overlay_disposition(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        inventory = invalid["inventory"]
        assert isinstance(inventory, list)
        audio = next(
            item
            for item in inventory
            if isinstance(item, dict) and item.get("id") == "audio-primary"
        )
        overlay = audio["overlay"]
        assert isinstance(overlay, dict)
        overlay["status"] = "none"
        errors = validate_manifest_document(invalid, schema)
        self.assertTrue(any("oversized program" in item for item in errors))


if __name__ == "__main__":
    unittest.main()
