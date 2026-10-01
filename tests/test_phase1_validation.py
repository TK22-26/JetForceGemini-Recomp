from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jsonschema import Draft202012Validator

import scripts.build_upstream as build_upstream
import scripts.compare_phase1_evidence as phase1_compare
from scripts.compare_phase1_evidence import compare_evidence, validate_aggregate_evidence
from scripts.parse_upstream_report import validate_report
from scripts.summarize_overlays import (
    OVERLAY_RECORD,
    OverlayRomLayout,
    load_private_overlay_layout,
    parse_overlay_table,
    safe_summary,
    summarize_overlay_text,
)
from scripts.validate_elf import (
    duplicate_export_count,
    map_consistency,
    parse_header,
    parse_map,
    parse_sections,
    parse_symbols,
    unexpected_section_overlaps,
)


HEADER = """\
ELF Header:
  Class:                             ELF32
  Data:                              2's complement, big endian
  Type:                              EXEC (Executable file)
  Machine:                           MIPS R3000
  Entry point address:               0x13579000
  Number of section headers:         4
"""

SECTIONS = """\
Section Headers:
  [Nr] Name              Type            Address  Off    Size   ES Flg Lk Inf Al
  [ 0]                   NULL            00000000 000000 000000 00      0   0  0
  [ 1] .text             PROGBITS        13579000 000100 000100 00  AX  0   0 16
  [ 2] .data             PROGBITS        13579100 000200 000040 00  WA  0   0 16
  [ 3] .symtab           SYMTAB          00000000 000240 000060 10      4   1  4
"""

SYMBOLS = """\
Symbol table '.symtab' contains 3 entries:
   Num:    Value  Size Type    Bind   Vis      Ndx Name
     0: 00000000     0 NOTYPE  LOCAL  DEFAULT  UND
     1: 13579000    16 FUNC    GLOBAL DEFAULT    1 entrypoint
     2: 13579100     4 OBJECT  GLOBAL DEFAULT    2 global_data
"""

MAP = """\
.text           0x13579000       0x100
                0x13579000                entrypoint
.data           0x13579100        0x40
                0x13579100                global_data
"""

ROM_SHA1 = "493ced9008dbe932d6e91179b68e8630cf23a023"
ROOT = Path(__file__).resolve().parents[1]

OVERLAY_LAYOUT = """\
segments:
  - name: before
    type: bin
    start: 0x100
  - name: overlay_1
    type: code
    start: 0x200
    vram: 0x1000
    bss_size: 0x10
    exclusive_ram_id: overlay_1
    subsegments:
      - [0x200, c, overlay_1]
      - [0x240, bin, overlay_1_reloc]
  - name: overlay_3
    type: code
    start: 0x280
    vram: 0x2000
    bss_size: 0x20
    exclusive_ram_id: overlay_3
    subsegments:
      - [0x280, c, overlay_3]
  - name: after
    type: bin
    start: 0x300
  - [0x400]
"""


def valid_report_document() -> dict[str, object]:
    return {
        "version": 2,
        "measures": {
            "total_code": "1000",
            "matched_code": "100",
            "matched_code_percent": 10.0,
            "total_data": "2000",
            "matched_data": "1500",
            "matched_data_percent": 75.0,
            "total_functions": 20,
            "matched_functions": 5,
            "matched_functions_percent": 25.0,
            "total_units": 8,
        },
        "categories": [
            {
                "id": "src",
                "name": "source",
                "measures": {"total_code": 1000, "matched_code": 100, "total_units": 7},
            },
            {
                "id": "overlays",
                "name": "Overlays",
                "measures": {"total_code": 800, "total_functions": 12, "total_units": 155},
            },
        ],
        "units": [
            {"name": "private/source-level-name", "functions": ["private-symbol-name"]}
        ],
    }


def environment_evidence(environment_id: str) -> dict[str, object]:
    run = {
        "rom_sha1": ROM_SHA1,
        "elf": {
            "sha256": "a" * 64,
            "section_count": 10,
            "allocated_section_count": 7,
            "section_table_sha256": "b" * 64,
            "symbol_count": 20,
            "symbol_types": {"FUNC": 12, "OBJECT": 8},
            "symbol_bindings": {"GLOBAL": 14, "LOCAL": 6},
            "relocation_count": 3,
            "unexpected_section_overlap_count": 0,
            "conflicting_export_name_count": 0,
            "map": {
                "sha256": "3" * 64,
                "consistent": True,
                "section_checked_count": 7,
                "section_missing_count": 0,
                "section_mismatch_count": 0,
                "symbol_checked_count": 12,
                "symbol_missing_count": 8,
                "symbol_mismatch_count": 0,
            },
        },
        "report": {"report_sha256": "c" * 64},
        "overlays": {
            "rom_table": {
                "table_slot_count": 3,
                "populated_overlay_count": 2,
                "empty_overlay_count": 1,
                "dynamic_vram_overlay_count": 2,
                "fixed_vram_overlay_count": 0,
                "all_rom_ranges_in_bounds": True,
                "primary_relocation_bytes": 16,
                "relocation_entry_count": 2,
                "secondary_relocation_bytes": 8,
                "secondary_relocation_entry_count": 1,
            },
            "splat_layout": {
                "overlay_count": 2,
                "empty_slot_count": 1,
                "all_rom_ranges_well_formed": True,
                "all_synthetic_vram_ranges_nonoverlapping": True,
            },
        },
    }
    return {
        "schema_version": 1,
        "environment_id": environment_id,
        "environment": {"distribution": environment_id},
        "decomp_commit": "d" * 40,
        "input_rom_sha1": ROM_SHA1,
        "source": {
            "decomp_tree": "e" * 40,
            "requirements_sha256": "f" * 64,
            "submodules": {"tools/example": "1" * 40},
        },
        "tools": {
            "versions": {
                "git": "test",
                "make": "test",
                "gcc": "test",
                "readelf": "test",
                "mips_as": "test",
                "mips_ld": "test",
                "mips_objcopy": "test",
                "python": "test",
                "python_packages": {"synthetic": "1"},
            },
            "artifacts": {
                "ido_recomp_manifest_sha256": "2" * 64,
                "objdiff_cli_sha256": "3" * 64,
                "n64crc_sha256": "4" * 64,
            },
        },
        "builds_equivalent": True,
        "runs": [
            {"run": 1, **copy.deepcopy(run)},
            {"run": 2, **copy.deepcopy(run)},
        ],
    }


class ElfValidationTests(unittest.TestCase):
    def test_header_requires_32_bit_big_endian_mips_executable(self) -> None:
        header = parse_header(HEADER)
        self.assertEqual(header["entry_point"], 0x13579000)

        with self.assertRaisesRegex(ValueError, "big-endian"):
            parse_header(HEADER.replace("big endian", "little endian"))

    def test_section_overlap_is_detected_and_can_be_explicitly_allowed(self) -> None:
        sections = parse_sections(SECTIONS.replace("13579100", "13579080"))
        self.assertEqual(len(sections), 4)
        self.assertEqual(sections[0].section_type, "NULL")
        self.assertEqual(sections[-1].name, ".symtab")
        self.assertEqual(sections[-1].flags, "")
        overlaps = unexpected_section_overlaps(sections)
        self.assertEqual(len(overlaps), 1)
        self.assertEqual(
            unexpected_section_overlaps(
                sections,
                {frozenset((".text", ".data"))},
            ),
            [],
        )

    def test_only_conflicting_export_definitions_violate_uniqueness(self) -> None:
        symbols = parse_symbols(SYMBOLS)
        self.assertEqual(duplicate_export_count(symbols), 0)

        conflicting = parse_symbols(
            SYMBOLS.replace("contains 3 entries", "contains 4 entries")
            + "     3: 13579200    16 FUNC    GLOBAL DEFAULT    1 entrypoint\n"
        )
        self.assertEqual(duplicate_export_count(conflicting), 1)

        local_duplicate = parse_symbols(
            SYMBOLS.replace("contains 3 entries", "contains 4 entries")
            + "     3: 13579200    16 FUNC    LOCAL  DEFAULT    1 entrypoint\n"
        )
        self.assertEqual(duplicate_export_count(local_duplicate), 0)

    def test_symbol_sizes_accept_decimal_and_prefixed_hex(self) -> None:
        symbols = parse_symbols(SYMBOLS.replace("    16 FUNC", "  0x10 FUNC"))
        self.assertEqual(symbols[1].size, 16)

    def test_symbol_parser_checks_declared_entry_count_and_indices(self) -> None:
        with self.assertRaisesRegex(ValueError, "declared entry count"):
            parse_symbols(SYMBOLS.replace("contains 3 entries", "contains 4 entries"))
        with self.assertRaisesRegex(ValueError, "declared entry range"):
            parse_symbols(SYMBOLS.replace("     2:", "     3:"))

    def test_map_and_elf_consistency_detects_symbol_and_section_mismatch(self) -> None:
        sections = parse_sections(SECTIONS)
        symbols = parse_symbols(SYMBOLS)
        valid = map_consistency(sections, symbols, MAP)
        self.assertTrue(valid["consistent"])
        self.assertEqual(valid["coverage_verdict"], "complete")
        self.assertTrue(valid["coverage_complete"])
        self.assertEqual(valid["section_checked_count"], 2)
        self.assertEqual(valid["symbol_checked_count"], 2)

        invalid = map_consistency(sections, symbols, MAP.replace("0x13579100", "0x13579110"))
        self.assertFalse(invalid["consistent"])
        self.assertGreater(invalid["section_mismatch_count"], 0)
        self.assertGreater(invalid["symbol_mismatch_count"], 0)

        partial = map_consistency(
            sections,
            symbols,
            MAP.replace("                0x13579100                global_data\n", ""),
        )
        self.assertTrue(partial["consistent"])
        self.assertFalse(partial["coverage_complete"])
        self.assertEqual(partial["coverage_verdict"], "partial")
        self.assertEqual(
            partial["symbol_candidate_count"],
            partial["symbol_checked_count"] + partial["symbol_missing_count"],
        )

    def test_map_parser_handles_wrapped_output_section(self) -> None:
        sections, _ = parse_map(
            MAP + ".long_output_section\n                0x13579200        0x20\n"
        )
        self.assertEqual(sections[".long_output_section"], (0x13579200, 0x20))


class UpstreamReportTests(unittest.TestCase):
    def write_report(self, directory: str, document: object) -> Path:
        path = Path(directory) / "report.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    def test_report_parser_emits_aggregates_without_unit_details(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            summary = validate_report(self.write_report(directory, valid_report_document()))
        rendered = json.dumps(summary)
        self.assertEqual(summary["report_version"], 2)
        self.assertNotIn("private/source-level-name", rendered)
        self.assertNotIn("private-symbol-name", rendered)

    def test_report_parser_rejects_duplicate_categories(self) -> None:
        document = valid_report_document()
        categories = document["categories"]
        assert isinstance(categories, list)
        categories.append(categories[0])
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "duplicate category"):
                validate_report(self.write_report(directory, document))

    def test_report_parser_rejects_impossible_measure(self) -> None:
        document = valid_report_document()
        measures = document["measures"]
        assert isinstance(measures, dict)
        measures["matched_code"] = 1001
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "exceeds"):
                validate_report(self.write_report(directory, document))


class CrossEnvironmentEvidenceTests(unittest.TestCase):
    def test_two_distinct_equivalent_environments_produce_safe_summary(self) -> None:
        summary = compare_evidence(
            environment_evidence("ubuntu-22.04"),
            environment_evidence("ubuntu-24.04"),
        )
        self.assertTrue(summary["equivalent"])
        self.assertEqual(summary["environment_ids"], ["ubuntu-22.04", "ubuntu-24.04"])
        self.assertEqual(summary["elf"]["section_count"], 10)  # type: ignore[index]
        self.assertEqual(summary["elf"]["symbol_types"], {"FUNC": 12, "OBJECT": 8})  # type: ignore[index]
        self.assertEqual(summary["elf"]["relocation_count"], 3)  # type: ignore[index]
        self.assertNotIn("environment", summary)

    def test_invalid_symbol_category_totals_are_rejected(self) -> None:
        first = environment_evidence("ubuntu-22.04")
        for run in first["runs"]:  # type: ignore[index]
            run["elf"]["symbol_types"]["FUNC"] = 11  # type: ignore[index]
        with self.assertRaisesRegex(ValueError, "symbol type counts"):
            compare_evidence(first, environment_evidence("ubuntu-24.04"))

    def test_same_environment_id_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "distinct"):
            compare_evidence(
                environment_evidence("ubuntu-24.04"),
                environment_evidence("ubuntu-24.04"),
            )

    def test_cross_environment_output_mismatch_is_rejected(self) -> None:
        second = environment_evidence("ubuntu-24.04")
        runs = second["runs"]
        assert isinstance(runs, list)
        for run in runs:
            assert isinstance(run, dict)
            elf = run["elf"]
            assert isinstance(elf, dict)
            elf["sha256"] = "e" * 64
        summary = compare_evidence(environment_evidence("ubuntu-22.04"), second)
        self.assertFalse(summary["equivalent"])
        self.assertEqual(summary["verdict"], "divergent")
        self.assertIn("cross-environment-build-output", summary["divergence_reasons"])
        self.assertNotIn("elf", summary)
        validate_aggregate_evidence(summary)
        schema = json.loads(
            (ROOT / "schemas" / "phase1-build-evidence.schema.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator(schema).validate(summary)

    def test_map_format_hash_may_vary_when_semantics_match(self) -> None:
        second = environment_evidence("ubuntu-24.04")
        for run in second["runs"]:  # type: ignore[index]
            run["elf"]["map"]["sha256"] = "4" * 64  # type: ignore[index]
        summary = compare_evidence(environment_evidence("ubuntu-22.04"), second)
        hashes = summary["elf"]["map"]["sha256_by_environment"]  # type: ignore[index]
        self.assertEqual(len(set(hashes.values())), 2)

    def test_repeated_build_divergence_is_representable(self) -> None:
        second = environment_evidence("ubuntu-24.04")
        second["runs"][1]["elf"]["sha256"] = "9" * 64  # type: ignore[index]
        second["builds_equivalent"] = False
        summary = compare_evidence(environment_evidence("ubuntu-22.04"), second)
        self.assertFalse(summary["equivalent"])
        self.assertIn("ubuntu-24.04:repeated-build-output", summary["divergence_reasons"])

    def test_compare_cli_records_divergence_and_returns_failure(self) -> None:
        second = environment_evidence("ubuntu-24.04")
        for run in second["runs"]:  # type: ignore[index]
            run["elf"]["sha256"] = "9" * 64  # type: ignore[index]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first_path = root / "first.json"
            second_path = root / "second.json"
            output_path = root / "summary.json"
            first_path.write_text(
                json.dumps(environment_evidence("ubuntu-22.04")), encoding="utf-8"
            )
            second_path.write_text(json.dumps(second), encoding="utf-8")
            with mock.patch(
                "sys.argv",
                [
                    "compare_phase1_evidence.py",
                    str(first_path),
                    str(second_path),
                    "--output",
                    str(output_path),
                ],
            ):
                self.assertEqual(phase1_compare.main(), 1)
            self.assertFalse(json.loads(output_path.read_text())["equivalent"])

    def test_aggregate_environment_correspondence_is_enforced(self) -> None:
        summary = compare_evidence(
            environment_evidence("ubuntu-22.04"),
            environment_evidence("ubuntu-24.04"),
        )
        summary["elf"]["map"]["sha256_by_environment"] = {  # type: ignore[index]
            "ubuntu-22.04": "3" * 64,
            "ubuntu-99.99": "4" * 64,
        }
        with self.assertRaisesRegex(ValueError, "map hash environment IDs"):
            validate_aggregate_evidence(summary, require_success=True)

    def test_aggregate_overlay_byte_count_invariant_is_enforced(self) -> None:
        summary = compare_evidence(
            environment_evidence("ubuntu-22.04"),
            environment_evidence("ubuntu-24.04"),
        )
        summary["overlays"]["rom_table"]["primary_relocation_bytes"] = 15  # type: ignore[index]
        with self.assertRaisesRegex(ValueError, "relocation byte/count"):
            validate_aggregate_evidence(summary, require_success=True)

    def test_legacy_private_ranges_are_normalized_out_of_public_evidence(self) -> None:
        first = environment_evidence("ubuntu-22.04")
        for run in first["runs"]:  # type: ignore[index]
            rom_table = run["overlays"]["rom_table"]  # type: ignore[index]
            rom_table.pop("all_rom_ranges_in_bounds")
            rom_table.update({"rom_range_min": 100, "rom_range_max": 200})
            splat = run["overlays"]["splat_layout"]  # type: ignore[index]
            splat.pop("all_rom_ranges_well_formed")
            splat.pop("all_synthetic_vram_ranges_nonoverlapping")
            splat.update(
                {
                    "rom_range": {"start": 100, "end": 200},
                    "synthetic_vram_range": {"start": 300, "end": 400},
                }
            )
        summary = compare_evidence(first, environment_evidence("ubuntu-24.04"))
        overlays = summary["overlays"]  # type: ignore[index]
        rom_table = overlays["rom_table"]
        splat = overlays["splat_layout"]
        self.assertNotIn("rom_range_min", rom_table)
        self.assertNotIn("rom_range_max", rom_table)
        self.assertNotIn("rom_range", splat)
        self.assertNotIn("synthetic_vram_range", splat)

    def test_invalid_legacy_private_range_is_rejected(self) -> None:
        first = environment_evidence("ubuntu-22.04")
        for run in first["runs"]:  # type: ignore[index]
            rom_table = run["overlays"]["rom_table"]  # type: ignore[index]
            rom_table.pop("all_rom_ranges_in_bounds")
            rom_table.update({"rom_range_min": 200, "rom_range_max": 100})
        with self.assertRaisesRegex(ValueError, "legacy overlay ROM range"):
            compare_evidence(first, environment_evidence("ubuntu-24.04"))


class BuildUpstreamTests(unittest.TestCase):
    def test_submodule_pin_parser_requires_clean_initialized_status(self) -> None:
        with mock.patch.object(
            build_upstream,
            "capture",
            return_value=" " + "a" * 40 + " tools/example (heads/main)",
        ):
            self.assertEqual(
                build_upstream.submodule_pins(Path("synthetic")),
                {"tools/example": "a" * 40},
            )
        with mock.patch.object(
            build_upstream,
            "capture",
            return_value="-" + "a" * 40 + " tools/example",
        ):
            with self.assertRaisesRegex(RuntimeError, "not clean and initialized"):
                build_upstream.submodule_pins(Path("synthetic"))

    def test_build_once_is_synthetic_and_import_safe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            decomp = root / "decomp"
            results = root / "results"
            (decomp / "build").mkdir(parents=True)
            (decomp / "ver" / "splat").mkdir(parents=True)
            (decomp / ".venv" / "bin").mkdir(parents=True)
            results.mkdir()
            for name in ("jfg.us.z64", "jfg.us.elf", "jfg.us.map", "report.json"):
                (decomp / "build" / name).write_bytes(b"synthetic")
            (decomp / "ver" / "splat" / "jfg.us.yaml").write_text(
                "synthetic-layout", encoding="utf-8"
            )
            with (
                mock.patch.object(build_upstream, "run") as run_mock,
                mock.patch.object(
                    build_upstream, "digest", return_value=build_upstream.EXPECTED_ROM_SHA1
                ),
                mock.patch.object(build_upstream, "summarize", return_value={"elf": True}),
                mock.patch.object(
                    build_upstream, "validate_report", return_value={"report": True}
                ),
                mock.patch.object(
                    build_upstream, "summarize_rom", return_value={"rom": True}
                ),
                mock.patch.object(
                    build_upstream,
                    "summarize_overlay_text",
                    return_value={"layout": True},
                ),
            ):
                result = build_upstream.build_once(
                    decomp,
                    results,
                    1,
                    2,
                    OverlayRomLayout(0, 157 * OVERLAY_RECORD.size),
                )
            self.assertEqual(result["rom_sha1"], build_upstream.EXPECTED_ROM_SHA1)
            self.assertEqual(result["elf"], {"elf": True})
            self.assertEqual(run_mock.call_count, 3)


class OverlaySummaryTests(unittest.TestCase):
    def test_splat_summary_tracks_safe_counts_gaps_and_bounds(self) -> None:
        summary = summarize_overlay_text(
            OVERLAY_LAYOUT,
            expected_count=2,
            expected_slot_count=3,
        )
        self.assertEqual(summary["overlay_count"], 2)
        self.assertEqual(summary["empty_slot_count"], 1)
        self.assertTrue(summary["all_rom_ranges_well_formed"])
        self.assertTrue(summary["all_synthetic_vram_ranges_nonoverlapping"])
        self.assertNotIn("rom_range", summary)
        self.assertNotIn("synthetic_vram_range", summary)
        self.assertNotIn("records", summary)

    def test_private_overlay_layout_is_loaded_without_emitting_coordinates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "layout.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "overlay_table_start": 0,
                        "overlay_data_start": 157 * OVERLAY_RECORD.size,
                    }
                ),
                encoding="utf-8",
            )
            layout = load_private_overlay_layout(path)
        self.assertEqual(layout.table_start, 0)
        self.assertEqual(layout.data_start, 157 * OVERLAY_RECORD.size)

    def test_private_overlay_layout_rejects_unignored_repository_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "layout.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "overlay_table_start": 0,
                        "overlay_data_start": 157 * OVERLAY_RECORD.size,
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch(
                "scripts.summarize_overlays.private_input_is_safe",
                return_value=False,
            ):
                with self.assertRaisesRegex(ValueError, "Git-ignored"):
                    load_private_overlay_layout(path)

    def test_private_overlay_layout_rejects_invalid_shapes_and_ranges(self) -> None:
        valid = {
            "schema_version": 1,
            "overlay_table_start": 0,
            "overlay_data_start": 157 * OVERLAY_RECORD.size,
        }
        invalid_values = (
            {**valid, "extra": 1},
            {**valid, "schema_version": 2},
            {**valid, "overlay_table_start": True},
            {**valid, "overlay_data_start": valid["overlay_data_start"] + 4},
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "layout.json"
            for value in invalid_values:
                with self.subTest(value=value):
                    path.write_text(json.dumps(value), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        load_private_overlay_layout(path)

    def test_splat_summary_rejects_out_of_range_subsegment(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside"):
            summarize_overlay_text(
                OVERLAY_LAYOUT.replace("0x240", "0x280"),
                expected_count=2,
                expected_slot_count=3,
            )

    def test_splat_summary_rejects_unexpected_synthetic_vram_overlap(self) -> None:
        with self.assertRaisesRegex(ValueError, "overlap"):
            summarize_overlay_text(
                OVERLAY_LAYOUT.replace("vram: 0x2000", "vram: 0x1040"),
                expected_count=2,
                expected_slot_count=3,
            )

    def test_overlay_summary_contains_aggregates_but_no_per_overlay_rows(self) -> None:
        table = b"".join(
            (
                OVERLAY_RECORD.pack(0, 0, 0x20, 0x10, 0x08, 0x10, 0x08, -1, -1),
                OVERLAY_RECORD.pack(0, 0x20, 0x10, 0, 0x04, 0, 0, -1, -1),
                OVERLAY_RECORD.pack(0, 0, 0, 0, 0, 0, 0, -1, -1),
            )
        )
        records = parse_overlay_table(table, rom_size=0x1000, data_base=0x100)
        summary = safe_summary(table, records)
        self.assertEqual(summary["populated_overlay_count"], 2)
        self.assertEqual(summary["empty_overlay_count"], 1)
        self.assertEqual(summary["rom_overlap_pair_count"], 1)
        self.assertEqual(summary["primary_relocation_bytes"], 0x10)
        self.assertEqual(summary["relocation_entry_count"], 2)
        self.assertEqual(summary["secondary_relocation_bytes"], 0x08)
        self.assertEqual(summary["secondary_relocation_entry_count"], 1)
        self.assertTrue(summary["all_rom_ranges_in_bounds"])
        self.assertNotIn("rom_range_min", summary)
        self.assertNotIn("rom_range_max", summary)
        self.assertNotIn("records", summary)

    def test_overlay_relocation_sizes_are_bytes_and_require_entry_alignment(self) -> None:
        table = OVERLAY_RECORD.pack(0, 0, 0x20, 0x10, 0, 7, 0, -1, -1)
        with self.assertRaisesRegex(ValueError, "entry-aligned"):
            parse_overlay_table(table, rom_size=0x1000, data_base=0x100)

    def test_overlay_range_outside_rom_is_rejected(self) -> None:
        table = OVERLAY_RECORD.pack(0, 0xF0, 0x20, 0, 0, 0, 0, -1, -1)
        with self.assertRaisesRegex(ValueError, "outside"):
            parse_overlay_table(table, rom_size=0x200, data_base=0x100)


if __name__ == "__main__":
    unittest.main()
