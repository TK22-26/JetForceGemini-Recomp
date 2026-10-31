from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts.prepare_generated_sources import (
    NORMALIZER_PATH,
    PreparationFailure,
    _relative_parts,
    prepare,
)


class GeneratedSourcePreparationTests(unittest.TestCase):
    def make_root(
        self, root: Path, *, normalizer_revision_digest: str | None = None
    ) -> None:
        (root / "include").mkdir()
        (root / "body").mkdir()
        (root / "wrappers").mkdir()
        (root / "support").mkdir()
        (root / "audit").mkdir()
        (root / "include" / "recomp.h").write_text("/* fixture */\n", encoding="utf-8")
        for relative in (
            "body/function.c",
            "wrappers/function.c",
            "support/support.c",
            "audit/link_smoke_registry.cpp",
        ):
            (root / relative).write_text("/* fixture */\n", encoding="utf-8")
        inventory = b"{}\n"
        (root / "symbol_inventory.json").write_bytes(inventory)
        manifest = {
            "version": 2,
            "n64recomp_include": "include",
            "baseline_body_sources": ["body/function.c"],
            "normal_wrapper_sources": ["wrappers/function.c"],
            "patch_sources": [],
            "game_patch_function_count": 0,
            "support_sources": ["support/support.c"],
            "link_smoke_sources": ["audit/link_smoke_registry.cpp"],
            "symbol_inventory": "symbol_inventory.json",
            "symbol_inventory_sha256": hashlib.sha256(inventory).hexdigest(),
            "normalizer_revision_sha256": normalizer_revision_digest
            or hashlib.sha256(NORMALIZER_PATH.read_bytes()).hexdigest(),
        }
        (root / "sources.json").write_text(json.dumps(manifest), encoding="utf-8")

    def make_v3_root(self, root: Path, *, inventory: bytes = b'{"sections":[]}\n') -> bytes:
        self.make_root(root)
        manifest_path = root / "sources.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.update(
            {
                "version": 3,
                "cpu_section_inventory": "cpu_section_inventory.json",
                "cpu_section_inventory_sha256": hashlib.sha256(inventory).hexdigest(),
            }
        )
        (root / "cpu_section_inventory.json").write_bytes(inventory)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return inventory

    def test_noncanonical_textual_paths_are_rejected(self) -> None:
        for value in (
            "body//function.c",
            "body/function.c/",
            "body/./function.c",
            "body/../function.c",
            "body\\function.c",
            "body/function.c;ignored.c",
            "$<TARGET_OBJECTS:unexpected>",
        ):
            with self.subTest(value=value):
                with self.assertRaises(PreparationFailure):
                    _relative_parts(value, "synthetic-role")

    def test_manifest_symlink_is_rejected_before_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            with mock.patch.object(Path, "is_symlink", return_value=True):
                with self.assertRaisesRegex(
                    PreparationFailure,
                    "source-manifest: symbolic-link-not-allowed",
                ):
                    prepare(root, root / "output")

    def test_stale_normalizer_revision_is_rejected_before_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.make_root(root, normalizer_revision_digest="0" * 64)
            output = root / "output"
            with self.assertRaisesRegex(
                PreparationFailure, "normalizer-revision: digest-mismatch"
            ):
                prepare(root, output, require_normalizer_revision=True)
            self.assertFalse(output.exists())

    def test_current_normalizer_revision_is_accepted_for_private_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.make_root(root)
            output = root / "output"
            prepare(root, output, require_normalizer_revision=True)
            self.assertTrue((output / "baseline-body.txt").is_file())

    def test_v3_cpu_inventory_is_digest_bound_and_copied(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            inventory = self.make_v3_root(root)
            output = root / "output"
            prepare(root, output, require_normalizer_revision=True)
            self.assertEqual((output / "cpu-section-inventory.json").read_bytes(), inventory)
            self.assertTrue((output / "cpu-inventory-source.txt").is_file())

    def test_v3_missing_or_mismatched_cpu_inventory_rejects_before_outputs(self) -> None:
        for label, mutate in (
            ("missing", lambda root: (root / "cpu_section_inventory.json").unlink()),
            ("mismatched", lambda root: (root / "cpu_section_inventory.json").write_bytes(b"{}\n")),
        ):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary_directory:
                root = Path(temporary_directory)
                self.make_v3_root(root)
                mutate(root)
                output = root / "output"
                with self.assertRaisesRegex(PreparationFailure, "cpu-section-inventory"):
                    prepare(root, output, require_normalizer_revision=True)
                self.assertFalse(output.exists())

    def test_malformed_normalizer_revision_is_rejected_before_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.make_root(root, normalizer_revision_digest="A" * 64)
            output = root / "output"
            with self.assertRaisesRegex(
                PreparationFailure, "normalizer-revision: invalid-digest"
            ):
                prepare(root, output, require_normalizer_revision=True)
            self.assertFalse(output.exists())

    def test_private_v1_manifest_is_rejected_before_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.make_root(root)
            manifest_path = root / "sources.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            del manifest["normalizer_revision_sha256"]
            manifest["version"] = 1
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            output = root / "output"
            with self.assertRaisesRegex(
                PreparationFailure, "normalizer-revision: required"
            ):
                prepare(root, output, require_normalizer_revision=True)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
