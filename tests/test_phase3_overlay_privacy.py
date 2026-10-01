from __future__ import annotations

import ast
import json
import tempfile
import tomllib
import unittest
from pathlib import Path

from scripts.analyze_phase3_overlays import (
    RomLayout,
    load_private_layout,
    verify_private_artifact_path,
)


ROOT = Path(__file__).resolve().parents[1]


def synthetic_layout() -> dict[str, int]:
    table_start = 0x1000
    return {
        "schema_version": 1,
        "main_relocation_start": 0,
        "overlay_reference_table_start": 4,
        "overlay_table_start": table_start,
        "overlay_data_start": table_start + 157 * 32,
        "main_text_size": 4,
        "main_data_size": 4,
    }


class OverlayPrivacyTests(unittest.TestCase):
    def test_layout_loader_rejects_trackable_repository_path(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / "layout.json"
            path.write_text(json.dumps(synthetic_layout()), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Git-ignored"):
                load_private_layout(path)

    def test_layout_loader_accepts_external_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "layout.json"
            path.write_text(json.dumps(synthetic_layout()), encoding="utf-8")
            layout = load_private_layout(path)
        self.assertIsInstance(layout, RomLayout)
        self.assertEqual(layout.main_text_size, 4)

    def test_detailed_output_must_be_external_or_git_ignored(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            with self.assertRaisesRegex(ValueError, "Git-ignored"):
                verify_private_artifact_path(Path(directory) / "details.json")
        verify_private_artifact_path(ROOT / "tools" / "results" / "details.json")

    def test_layout_requires_exact_typed_and_ordered_fields(self) -> None:
        wrong_type = synthetic_layout()
        wrong_type["main_text_size"] = True
        with self.assertRaisesRegex(ValueError, "integers"):
            RomLayout.from_json(wrong_type)

        extra = synthetic_layout()
        extra["private_note"] = 1
        with self.assertRaisesRegex(ValueError, "missing or unknown"):
            RomLayout.from_json(extra)

        unordered = synthetic_layout()
        unordered["overlay_reference_table_start"] = 0x2000
        with self.assertRaisesRegex(ValueError, "strictly ordered"):
            RomLayout.from_json(unordered)

    def test_overlay_tools_have_no_module_level_private_layout_constants(self) -> None:
        forbidden_suffixes = ("_START", "_END", "_OFFSET", "_BASE", "_ROM", "_SIZE")
        allowed = {"EXPECTED_ROM_SIZE"}

        def names(target: ast.expr) -> list[str]:
            if isinstance(target, ast.Name):
                return [target.id]
            if isinstance(target, (ast.Tuple, ast.List)):
                return [name for child in target.elts for name in names(child)]
            return []

        for relative in (
            "scripts/analyze_phase3_overlays.py",
            "scripts/summarize_overlays.py",
        ):
            source = (ROOT / relative).read_text(encoding="utf-8")
            tree = ast.parse(source)
            for statement in tree.body:
                targets: list[ast.expr] = []
                if isinstance(statement, ast.Assign):
                    targets = statement.targets
                elif isinstance(statement, ast.AnnAssign):
                    targets = [statement.target]
                for target in targets:
                    for name in names(target):
                        if name in allowed:
                            continue
                        looks_private = (
                            name.endswith(forbidden_suffixes)
                            or "COORD" in name
                            or "LAYOUT" in name
                            or "ENTRYPOINT" in name
                        )
                        self.assertFalse(
                            looks_private,
                            f"module-level private layout coordinate in {relative}: {name}",
                        )

    def test_tracked_evidence_and_config_omit_coordinate_fields(self) -> None:
        forbidden_keys = {
            "anomaly_inventory_sha256",
            "candidate_vram",
            "elf_header_value",
            "entrypoint",
            "main_data_size",
            "main_relocation_start",
            "main_text_size",
            "main_zero_padding_bytes",
            "manual_fallback_size",
            "overlay_data_start",
            "overlay_reference_table_start",
            "overlay_table_start",
            "rom_range",
            "rom_range_max",
            "rom_range_min",
            "synthetic_vram_range",
        }

        def keys(value: object) -> set[str]:
            if isinstance(value, dict):
                return set(value) | {
                    child_key
                    for child in value.values()
                    for child_key in keys(child)
                }
            if isinstance(value, list):
                return {child_key for child in value for child_key in keys(child)}
            return set()

        for relative in (
            "docs/upstream/phase1-build-evidence.json",
            "docs/feasibility/phase3-cpu-overlay-evidence.json",
            "schemas/phase1-build-evidence.schema.json",
            "schemas/phase3-cpu-overlay-evidence.schema.json",
        ):
            document = json.loads((ROOT / relative).read_text(encoding="utf-8"))
            leaked = forbidden_keys & keys(document)
            self.assertEqual(leaked, set(), f"coordinate fields in {relative}: {leaked}")

        config = tomllib.loads((ROOT / "config/jfg.us.toml").read_text(encoding="utf-8"))
        input_config = config.get("input")
        self.assertIsInstance(input_config, dict)
        if isinstance(input_config, dict):
            self.assertNotIn("entrypoint", input_config)
            self.assertNotIn("manual_funcs", input_config)


if __name__ == "__main__":
    unittest.main()
