from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "prepare_phase6_native_dispatch_table.py"


def document() -> dict[str, object]:
    return {
        "schema_version": 1,
        "kind": "jfg-phase6-libultra-identification-detail",
        "source": "synthetic",
        "entrypoint_vram": "0x80000400",
        "identified": [{
            "libultra": "osSendMesg",
            "vram": "0x80001000",
            "generated_function": "fn_000_0001",
            "in_generated_set": True,
        }],
    }


class TableTests(unittest.TestCase):
    def invoke(self, value: object) -> tuple[subprocess.CompletedProcess[str], str | None]:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            identification = directory / "in.json"
            output = directory / "out.inc"
            identification.write_text(json.dumps(value), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--identification", str(identification), "--output", str(output)],
                capture_output=True, text=True, check=False,
            )
            return result, output.read_text(encoding="utf-8") if output.exists() else None

    def test_mapped_entry_is_emitted_and_unmapped_entry_is_omitted(self) -> None:
        value = document()
        value["identified"].append({"libultra": "osRecvMesg", "vram": "0x80001004", "generated_function": None, "in_generated_set": False})
        result, output = self.invoke(value)
        self.assertEqual(result.returncode, 0)
        self.assertIn("osSendMesg", output)
        self.assertNotIn("osRecvMesg", output)

    def test_rejects_schema_names_duplicates_and_inconsistent_mapping(self) -> None:
        cases = []
        bad_schema = document(); bad_schema["extra"] = 1; cases.append(bad_schema)
        unsafe_name = document(); unsafe_name["identified"][0]["libultra"] = 'osX"};'; cases.append(unsafe_name)
        duplicate = document(); duplicate["identified"].append(duplicate["identified"][0].copy()); cases.append(duplicate)
        wrong_unmapped = document(); wrong_unmapped["identified"][0]["in_generated_set"] = False; cases.append(wrong_unmapped)
        wrong_mapped = document(); wrong_mapped["identified"][0]["generated_function"] = None; cases.append(wrong_mapped)
        for value in cases:
            with self.subTest(value=value):
                self.assertNotEqual(self.invoke(value)[0].returncode, 0)

    def test_rejects_wrong_entry_bad_types_and_empty_mapped_set(self) -> None:
        wrong_entry = document(); wrong_entry["entrypoint_vram"] = "0x80000450"
        bad_vram = document(); bad_vram["identified"][0]["vram"] = "80001000"
        bad_flag = document(); bad_flag["identified"][0]["in_generated_set"] = 1
        empty = document(); empty["identified"][0]["in_generated_set"] = False; empty["identified"][0]["generated_function"] = None
        for value in (wrong_entry, bad_vram, bad_flag, empty):
            with self.subTest(value=value):
                self.assertNotEqual(self.invoke(value)[0].returncode, 0)

    def test_rejects_output_in_tracked_source_location(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            identification = directory / "in.json"
            identification.write_text(json.dumps(document()), encoding="utf-8")
            output = ROOT / "tests" / "phase6-private-output.inc"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--identification", str(identification),
                 "--output", str(output)],
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())

    def test_allows_ignored_build_dash_output_without_leaking_it(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT, prefix="build-phase6-table-") as temporary:
            directory = Path(temporary)
            identification = directory / "in.json"
            output = directory / "phase6-private" / "native-dispatch-table.inc"
            identification.write_text(json.dumps(document()), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--identification", str(identification),
                 "--output", str(output)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output.exists())

    def test_rejects_unignored_in_repo_output_without_creating_it(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT, prefix="phase6-table-") as temporary:
            directory = Path(temporary)
            identification = directory / "in.json"
            output = directory / "native-dispatch-table.inc"
            identification.write_text(json.dumps(document()), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--identification", str(identification),
                 "--output", str(output)],
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())

    def test_allows_only_native_output_within_private_bootstrap_workspace(self) -> None:
        parent = ROOT / "tools" / "private" / "local-builds"
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent, prefix="dispatch-fixture-") as temporary:
            directory = Path(temporary)
            self.assertTrue(directory.resolve().is_relative_to(parent.resolve()))
            identification = directory / "in.json"
            identification.write_text(json.dumps(document()), encoding="utf-8")
            for subdir, accepted in (("native/phase6-private", True), ("other", False)):
                output = directory / subdir / "native-dispatch-table.inc"
                result = subprocess.run([sys.executable, str(SCRIPT), "--identification", str(identification),
                    "--output", str(output)], capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode == 0, accepted, result.stderr)
                self.assertEqual(output.exists(), accepted)


if __name__ == "__main__":
    unittest.main()
