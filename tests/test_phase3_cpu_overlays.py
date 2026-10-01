from __future__ import annotations

import collections
import struct
import copy
import json
import os
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

from jsonschema import Draft202012Validator

from scripts.analyze_phase3_overlays import (
    ActiveOverlayRegistry,
    OverlayPointer,
    RomLayout,
    analyze_rom,
    analyze_hi_lo_sequences,
    apply_patch_word,
    classify_ort_target,
    counter_dict,
    lookup_active_overlay,
    parse_headers,
    parse_relocations,
    relocation_fields,
    tracked_overlay_fragment,
    validate_table_count_reconciliation,
    validate_public_overlay_aggregate,
    verify_tracked_overlay_fragment,
    validate_phase3_evidence,
)
from scripts.probe_n64recomp_cpu import (
    diagnostic_kind,
    locate_transfer_functions,
    render_config,
    select_manual_entry_section,
    verify_file_identity,
    verify_private_work_directory,
)


ROOT = Path(__file__).resolve().parents[1]


class CpuProbeTests(unittest.TestCase):
    def test_diagnostic_classification_fails_loudly_on_unknown_text(self) -> None:
        self.assertEqual(
            diagnostic_kind("No function found for jal target: synthetic"),
            "missing-direct-call-target",
        )
        self.assertEqual(
            diagnostic_kind("Failed to determine size of jump table"),
            "unbounded-jump-table",
        )
        self.assertEqual(
            diagnostic_kind("Unsupported reloc type synthetic"),
            "unsupported-elf-relocation",
        )
        self.assertEqual(
            diagnostic_kind("Unhandled branch in synthetic"),
            "out-of-range-branch",
        )
        with self.assertRaisesRegex(ValueError, "unrecognized"):
            diagnostic_kind("new diagnostic not covered by the aggregate model")

    def test_transfer_scan_finds_placeholder_and_indirect_calls(self) -> None:
        words = [
            0x0C000000,  # unresolved jal placeholder
            (25 << 21) | 8,  # jr t9
            (31 << 21) | 8,  # ordinary return: jr ra
            (25 << 21) | (31 << 11) | 9,  # jalr ra, t9
        ]
        rom = struct.pack(">4I", *words)
        context = {
            "section": [
                {
                    "name": ".synthetic",
                    "rom": 0,
                    "vram": 0x80000000,
                    "functions": [
                        {"name": "synthetic_fn", "vram": 0x80000000, "size": len(rom)}
                    ],
                }
            ]
        }
        placeholders, placeholder_sites, indirects, indirect_sites, details = (
            locate_transfer_functions(context, rom)
        )
        self.assertEqual(placeholders, ["synthetic_fn"])
        self.assertEqual(placeholder_sites, 1)
        self.assertEqual(indirects, ["synthetic_fn"])
        self.assertEqual(indirect_sites, 2)
        self.assertEqual(details[0]["indirect_transfer_sites"], 2)

    def test_private_entry_must_fit_one_executable_section(self) -> None:
        context = {
            "section": [
                {"name": ".synthetic", "vram": 0x1000, "size": 0x100}
            ]
        }
        selected = select_manual_entry_section(context, 0x1040, 0x20)
        self.assertEqual(selected["name"], ".synthetic")
        with self.assertRaisesRegex(ValueError, "outside every executable section"):
            select_manual_entry_section(context, 0x2000, 0x20)
        with self.assertRaisesRegex(ValueError, "outside every executable section"):
            select_manual_entry_section(context, 0x10F0, 0x20)

    def test_config_rendering_has_no_mutable_default_leak(self) -> None:
        first = render_config(
            Path("input.elf"),
            Path("generated"),
            stubs=["synthetic_fn"],
        )
        second = render_config(Path("input.elf"), Path("generated"))
        self.assertIn('"synthetic_fn"', first)
        self.assertNotIn("synthetic_fn", second)

    def test_identity_check_rejects_wrong_size_and_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            candidate = Path(directory) / "candidate.bin"
            candidate.write_bytes(b"synthetic")
            with self.assertRaisesRegex(ValueError, "size"):
                verify_file_identity(
                    candidate,
                    expected_size=10,
                    algorithm="sha1",
                    expected_digest="0" * 40,
                    label="synthetic input",
                )
            with self.assertRaisesRegex(ValueError, "digest"):
                verify_file_identity(
                    candidate,
                    expected_size=9,
                    algorithm="sha1",
                    expected_digest="0" * 40,
                    label="synthetic input",
                )

    def test_detailed_work_directory_must_be_ignored_inside_repository(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            with self.assertRaisesRegex(ValueError, "Git-ignored"):
                verify_private_work_directory(Path(directory))
        with tempfile.TemporaryDirectory() as directory:
            verify_private_work_directory(Path(directory))

    def test_shipped_config_has_only_pinned_n64recomp_contract(self) -> None:
        config = tomllib.loads((ROOT / "config" / "jfg.us.toml").read_text(encoding="utf-8"))
        self.assertEqual(set(config), {"input", "patches"})
        self.assertEqual(
            set(config["input"]),
            {
                "elf_path",
                "output_func_path",
                "functions_per_output_file",
                "single_file_output",
                "use_lookup_for_all_function_calls",
                "strict_patch_mode",
                "use_mdebug",
                "use_absolute_symbols",
                "unpaired_lo16_warnings",
                "allow_exports",
            },
        )
        self.assertNotIn("entrypoint", config["input"])
        self.assertNotIn("manual_funcs", config["input"])
        self.assertEqual(config["input"]["functions_per_output_file"], 1)
        self.assertIs(config["input"]["single_file_output"], False)
        self.assertIs(config["input"]["use_lookup_for_all_function_calls"], True)
        self.assertIs(config["input"]["strict_patch_mode"], True)
        self.assertEqual(set(config["patches"]), {"stubs", "ignored"})

    def test_pinned_n64recomp_parses_shipped_config_when_available(self) -> None:
        executable = ROOT / "tools" / "build" / "n64recomp-ffb39cda" / "N64Recomp"
        elf = ROOT / "tools" / "upstream" / "Jet-Force-Gemini" / "build" / "jfg.us.elf"
        if not executable.is_file() or not elf.is_file():
            self.skipTest("ignored pinned tool inputs are unavailable")
        directory = ROOT / "tools" / "results" / "phase3" / "config-test"
        directory.mkdir(parents=True, exist_ok=True)

        if os.name == "nt":
            def wsl_path(path: Path) -> str:
                resolved = path.resolve()
                return f"/mnt/{resolved.drive[0].lower()}{resolved.as_posix()[2:]}"

            command = [
                "wsl.exe",
                "--cd",
                str(directory),
                "--",
                wsl_path(executable),
                wsl_path(ROOT / "config" / "jfg.us.toml"),
                "--dump-context",
            ]
            completed = subprocess.run(command, capture_output=True, text=True)
        else:
            completed = subprocess.run(
                [str(executable), str(ROOT / "config" / "jfg.us.toml"), "--dump-context"],
                cwd=directory,
                capture_output=True,
                text=True,
            )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)


class OverlayRelocationTests(unittest.TestCase):
    @staticmethod
    def synthetic_layout_and_headers() -> tuple[RomLayout, bytes]:
        table_start = 0x1000
        data_start = table_start + 157 * 32
        layout = RomLayout(
            main_relocation_start=0,
            overlay_reference_table_start=4,
            overlay_table_start=table_start,
            overlay_data_start=data_start,
            main_text_size=4,
            main_data_size=4,
        )
        headers = bytearray()
        for slot in range(157):
            if slot < 155:
                values = (0, slot * 4, 4, 0, 0, 0, 0, -1, -1)
            else:
                values = (0, 0, 0, 0, 0, 0, 0, 0, 0)
            headers.extend(struct.pack(">iiiiiHHii", *values))
        return layout, bytes(headers)

    def test_synthetic_relocation_decoding_and_patching(self) -> None:
        info = (0x1234 << 8) | (4 << 4) | 0
        entries = parse_relocations(struct.pack(">II", 7, info))
        self.assertEqual(relocation_fields(entries[0]), (7, 0x1234, 4, 0))
        self.assertEqual(apply_patch_word(0x0C000000, 0x80123450, 4), 0x0C048D14)
        self.assertEqual(apply_patch_word(0, 0x80123450, 2), 0x80123450)
        self.assertEqual(apply_patch_word(0x3C010000, 0x8012F450, 5), 0x3C018013)
        self.assertEqual(apply_patch_word(0x24210000, 0x8012F450, 6), 0x2421F450)

    def test_hi16_pairing_models_reference_and_standalone_lo16_semantics(self) -> None:
        hi = (0, (5 << 4) | 1)
        lo = (0, (6 << 4) | 1)
        counts = analyze_hi_lo_sequences([hi, lo, lo])
        self.assertEqual(counts["paired_hi16_lo16_count"], 1)
        self.assertEqual(counts["standalone_lo16_count"], 1)
        self.assertEqual(counts["unpaired_hi16_count"], 0)

        mismatched_lo = (1, (6 << 4) | 0)
        counts = analyze_hi_lo_sequences([hi, mismatched_lo])
        self.assertEqual(counts["hi16_lo16_reference_mismatch_count"], 1)
        self.assertEqual(counts["hi16_lo16_same_patch_target_count"], 1)

        ordinary = (0, (4 << 4) | 1)
        counts = analyze_hi_lo_sequences([hi, ordinary, lo])
        self.assertEqual(counts["unpaired_hi16_count"], 1)
        self.assertEqual(counts["standalone_lo16_count"], 1)

    def test_reference_target_classes_are_explicit(self) -> None:
        self.assertEqual(classify_ort_target(3 << 20), "overlay")
        self.assertEqual(classify_ort_target(0xFFD << 20), "main-data")
        self.assertEqual(classify_ort_target(0xFFF << 20), "main-bss")
        self.assertEqual(classify_ort_target(0xD66 << 20), "anomalous")

    def test_header_parser_checks_pinned_population_ranges_and_callbacks(self) -> None:
        layout, table = self.synthetic_layout_and_headers()
        with mock.patch(
            "scripts.analyze_phase3_overlays.EXPECTED_ROM_SIZE", 0x10000
        ):
            headers = parse_headers(table, layout)
            self.assertEqual(len(headers), 157)
            self.assertEqual(sum(header.populated for header in headers), 155)

            malformed = bytearray(table)
            struct.pack_into(">i", malformed, 32 + 24, 5)
            with self.assertRaisesRegex(ValueError, "callback"):
                parse_headers(bytes(malformed), layout)

            overlapping = bytearray(table)
            struct.pack_into(">i", overlapping, 32 + 4, 0)
            with self.assertRaisesRegex(ValueError, "overlap"):
                parse_headers(bytes(overlapping), layout)

    def test_counter_and_active_lookup_helpers_are_deterministic(self) -> None:
        self.assertEqual(
            counter_dict(collections.Counter({3: 2, 1: 4})), {"1": 4, "3": 2}
        )
        self.assertEqual(
            lookup_active_overlay(0x1040, [("ovl-a", 0x1000, 0x100)]),
            ("ovl-a", 0x40),
        )
        self.assertIsNone(
            lookup_active_overlay(0x2000, [("ovl-a", 0x1000, 0x100)])
        )

    def test_per_table_diagnostic_counts_must_reconcile_before_omission(self) -> None:
        tables = {
            "main": collections.Counter({0: 1}),
            "primary": collections.Counter({1: 2}),
            "secondary": collections.Counter({0: 1, 1: 1}),
        }
        aggregate = collections.Counter({0: 2, 1: 3})
        totals = {"main": 1, "primary": 2, "secondary": 2}
        validate_table_count_reconciliation(tables, aggregate, totals, "synthetic")

        wrong_table = copy.deepcopy(tables)
        wrong_table["secondary"][1] += 1
        with self.assertRaisesRegex(ValueError, "do not match its table"):
            validate_table_count_reconciliation(
                wrong_table, aggregate, totals, "synthetic"
            )

        wrong_aggregate = collections.Counter({0: 1, 1: 4})
        with self.assertRaisesRegex(ValueError, "do not match the aggregate"):
            validate_table_count_reconciliation(
                tables, wrong_aggregate, totals, "synthetic"
            )

    def test_synthetic_rom_analysis_omits_private_layout_and_reversible_anomaly_fields(self) -> None:
        layout, table = self.synthetic_layout_and_headers()
        rom = bytearray(0x10000)
        rom[layout.overlay_table_start : layout.overlay_data_start] = table
        with (
            mock.patch("scripts.analyze_phase3_overlays.EXPECTED_ROM_SIZE", len(rom)),
            mock.patch("scripts.analyze_phase3_overlays.validate_public_overlay_aggregate"),
        ):
            aggregate, details = analyze_rom(bytes(rom), layout)
        self.assertEqual(aggregate["overlay_headers"]["populated_count"], 155)
        self.assertEqual(aggregate["reference_table"]["entry_count"], 1023)
        self.assertEqual(aggregate["relocations"]["paired_hi16_lo16_count"], 0)
        rendered = json.dumps(aggregate, sort_keys=True)
        self.assertNotIn("main_zero_padding_bytes", rendered)
        self.assertNotIn("anomaly_inventory_sha256", rendered)
        self.assertIs(details["safe"], aggregate)

    def test_registry_rejects_stale_pointer_after_same_base_reload(self) -> None:
        registry = ActiveOverlayRegistry()
        first = registry.publish("ovl-a", 0x10000000, 0x100)
        pointer = registry.resolve_address(0x10000040)
        self.assertEqual(pointer, OverlayPointer("ovl-a", first.generation, 0x40))
        assert pointer is not None
        self.assertEqual(registry.resolve_pointer(pointer), 0x10000040)

        registry.unpublish("ovl-a", first.generation)
        self.assertIsNone(registry.resolve_address(0x10000040))
        second = registry.publish("ovl-a", 0x10000000, 0x100)
        self.assertGreater(second.generation, first.generation)
        with self.assertRaisesRegex(ValueError, "stale"):
            registry.resolve_pointer(pointer)
        replacement = registry.resolve_address(0x10000040)
        assert replacement is not None
        self.assertEqual(registry.resolve_pointer(replacement), 0x10000040)

    def test_registry_rejects_overlap_at_publish_without_mutating_state(self) -> None:
        registry = ActiveOverlayRegistry()
        active = registry.publish("ovl-a", 0x10000000, 0x100)
        with self.assertRaisesRegex(ValueError, "overlap"):
            registry.publish("ovl-b", 0x10000010, 0x100)
        self.assertIsNone(registry.resolve_address(0x10000120))
        pointer = registry.resolve_address(0x10000020)
        self.assertEqual(pointer, OverlayPointer("ovl-a", active.generation, 0x20))

    def test_registry_rejects_stale_unpublish_and_out_of_range_pointer(self) -> None:
        registry = ActiveOverlayRegistry()
        active = registry.publish("ovl-a", 0x10000000, 0x100)
        with self.assertRaisesRegex(ValueError, "stale"):
            registry.unpublish("ovl-a", active.generation + 1)
        with self.assertRaisesRegex(ValueError, "outside"):
            registry.resolve_pointer(
                OverlayPointer("ovl-a", active.generation, active.text_size)
            )


class Phase3EvidenceTests(unittest.TestCase):
    @staticmethod
    def evidence() -> dict[str, object]:
        return json.loads(
            (ROOT / "docs" / "feasibility" / "phase3-cpu-overlay-evidence.json").read_text(
                encoding="utf-8"
            )
        )

    @classmethod
    def analyzer_aggregate(cls) -> dict[str, object]:
        overlays = cls.evidence()["overlays"]
        relocations = copy.deepcopy(overlays["relocations"])
        return {
            "schema_version": 1,
            "kind": "jfg-phase3-cpu-overlay-evidence",
            "privacy": "public-safe-aggregate-only",
            "overlay_headers": copy.deepcopy(overlays["headers"]),
            "reference_table": copy.deepcopy(overlays["reference_table"]),
            "relocations": relocations,
            "dependencies": copy.deepcopy(overlays["dependencies"]),
            "detailed_inventory_sha256": overlays["detailed_inventory_sha256"],
        }

    def test_public_evidence_matches_schema(self) -> None:
        schema = json.loads(
            (ROOT / "schemas" / "phase3-cpu-overlay-evidence.schema.json").read_text(
                encoding="utf-8"
            )
        )
        evidence = self.evidence()
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(evidence)

    def test_public_evidence_semantics_are_validated(self) -> None:
        validate_phase3_evidence(self.evidence())

    def test_public_cpu_evidence_omits_private_entry_coordinates(self) -> None:
        rendered = json.dumps(self.evidence()["cpu"], sort_keys=True).lower()
        self.assertNotIn("candidate_vram", rendered)
        self.assertNotIn("manual_fallback_size", rendered)

    def test_analyzer_public_aggregate_has_a_closed_shape_and_exact_transform(self) -> None:
        aggregate = self.analyzer_aggregate()
        validate_public_overlay_aggregate(aggregate)
        expected = copy.deepcopy(self.evidence()["overlays"])
        expected.pop("runtime_contract")
        self.assertEqual(tracked_overlay_fragment(aggregate), expected)

        forged_aggregate = copy.deepcopy(aggregate)
        forged_evidence = self.evidence()
        forged_aggregate["dependencies"]["self_overlay_reference_count"] += 1
        forged_evidence["overlays"]["dependencies"][
            "self_overlay_reference_count"
        ] += 1
        with self.assertRaisesRegex(ValueError, "reviewed canonical lock"):
            verify_tracked_overlay_fragment(forged_aggregate, forged_evidence)

        private_field = copy.deepcopy(aggregate)
        private_field["relocations"]["main_zero_padding_bytes"] = 12
        with self.assertRaisesRegex(ValueError, "unreviewed public fields"):
            validate_public_overlay_aggregate(private_field)

        private_text = copy.deepcopy(aggregate)
        private_text["detailed_inventory_sha256"] = (
            "C:" + "/Users" + "/private/result.json"
        )
        with self.assertRaisesRegex(ValueError, "unreviewed public text"):
            validate_public_overlay_aggregate(private_text)

    def test_semantic_validation_rejects_pin_and_arithmetic_drift(self) -> None:
        wrong_pin = copy.deepcopy(self.evidence())
        wrong_pin["pins"]["n64recomp"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "pin"):
            validate_phase3_evidence(wrong_pin)

        wrong_total = copy.deepcopy(self.evidence())
        wrong_total["overlays"]["relocations"]["total_entry_count"] += 1
        with self.assertRaisesRegex(ValueError, "do not sum"):
            validate_phase3_evidence(wrong_total)

        wrong_lo16_partition = copy.deepcopy(self.evidence())
        wrong_lo16_partition["overlays"]["relocations"]["standalone_lo16_count"] += 1
        with self.assertRaisesRegex(ValueError, "LO16 sequence"):
            validate_phase3_evidence(wrong_lo16_partition)

        mismatched_pair = copy.deepcopy(self.evidence())
        mismatched_pair["overlays"]["relocations"][
            "hi16_lo16_reference_mismatch_count"
        ] = 1
        with self.assertRaisesRegex(ValueError, "sequence safety"):
            validate_phase3_evidence(mismatched_pair)

    def test_semantic_validation_keeps_g2_and_runtime_integration_open(self) -> None:
        closed_gate = copy.deepcopy(self.evidence())
        closed_gate["cpu"]["coverage_gate"]["status"] = "complete"
        with self.assertRaisesRegex(ValueError, "G2"):
            validate_phase3_evidence(closed_gate)

        integrated = copy.deepcopy(self.evidence())
        integrated["overlays"]["runtime_contract"][
            "generated_code_integration_complete"
        ] = True
        with self.assertRaisesRegex(ValueError, "synthetic"):
            validate_phase3_evidence(integrated)


if __name__ == "__main__":
    unittest.main()
