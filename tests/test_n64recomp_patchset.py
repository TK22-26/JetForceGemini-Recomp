from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SERIES_ROOT = ROOT / "patches" / "n64recomp"
SCRIPT_PATH = ROOT / "scripts" / "apply_n64recomp_patchset.py"
SPEC = importlib.util.spec_from_file_location("apply_n64recomp_patchset", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
APPLICATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(APPLICATOR)


def run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


class ApplicatorFixture:
    def __init__(self, root: Path) -> None:
        self.project = root / "project"
        self.target = root / "target"
        self.series = self.project / "patches" / "n64recomp" / "series"
        self.series.mkdir(parents=True)
        (self.project / "patches" / "n64recomp" / "LICENSE.upstream").write_bytes(
            (SERIES_ROOT / "LICENSE.upstream").read_bytes()
        )
        self.target.mkdir()
        run_git(self.target, "init", "-b", "main")
        (self.target / "a.txt").write_text("base-a\n", encoding="utf-8")
        (self.target / "b.txt").write_text("base-b\n", encoding="utf-8")
        run_git(self.target, "add", "a.txt", "b.txt")
        run_git(
            self.target,
            "-c",
            "user.name=Patch Test",
            "-c",
            "user.email=patch-test@example.invalid",
            "commit",
            "-m",
            "base",
        )
        self.commit = run_git(self.target, "rev-parse", "HEAD").stdout.strip()
        self.write_lock(self.commit)
        entries = []
        for index, file_name in enumerate(("a.txt", "b.txt"), start=1):
            changed = f"changed-{file_name[0]}\n"
            (self.target / file_name).write_text(changed, encoding="utf-8")
            patch_name = f"{index:04d}-change-{file_name[0]}.patch"
            patch_path = self.series / patch_name
            patch_path.write_text(
                run_git(self.target, "diff", "--", file_name).stdout,
                encoding="utf-8",
                newline="\n",
            )
            run_git(self.target, "restore", "--", file_name)
            entries.append(
                {
                    "file": patch_name,
                    "sha256": hashlib.sha256(patch_path.read_bytes()).hexdigest(),
                }
            )
        self.write_manifest(entries)

    def write_manifest(self, entries: list[dict[str, str]]) -> None:
        (self.project / "patches" / "n64recomp" / "series.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "dependency_id": "n64recomp",
                    "license": {
                        "file": "LICENSE.upstream",
                        "sha256": "d439b523a90a07f87182b0cf8fab9b09e385642f9f573b7ae67306d3fb68af88",
                    },
                    "patches": entries,
                }
            ),
            encoding="utf-8",
        )

    def write_lock(self, commit: str) -> None:
        (self.project / "dependencies.lock.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "repositories": [
                        {
                            "id": "n64recomp",
                            "url": "https://example.invalid/tool.git",
                            "commit": commit,
                            "license": "MIT",
                            "use": "test",
                            "recursive_submodules": {},
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    def manifest_entries(self) -> list[dict[str, str]]:
        manifest = json.loads(
            (self.project / "patches" / "n64recomp" / "series.json").read_text(
                encoding="utf-8"
            )
        )
        return manifest["patches"]


class N64RecompPatchSetTests(unittest.TestCase):
    def test_series_is_ordered_complete_and_bound_to_dependency_lock(self) -> None:
        manifest = json.loads((SERIES_ROOT / "series.json").read_text(encoding="utf-8"))
        paths, digest, payload = APPLICATOR._validated_series(ROOT)
        self.assertEqual([path.name for path in paths], [item["file"] for item in manifest["patches"]])
        self.assertEqual([path.name[:4] for path in paths], [f"{index:04d}" for index in range(1, len(paths) + 1)])
        self.assertRegex(digest, r"^[0-9a-f]{64}$")
        self.assertTrue(payload.startswith(b"diff --git "))
        lock = json.loads((ROOT / "dependencies.lock.json").read_text(encoding="utf-8"))
        dependency = next(item for item in lock["repositories"] if item["id"] == "n64recomp")
        self.assertEqual(APPLICATOR._locked_commit(ROOT, "n64recomp"), dependency["commit"])

    def test_series_patch_files_have_publication_clean_whitespace(self) -> None:
        for path in sorted((SERIES_ROOT / "series").glob("*.patch")):
            with self.subTest(patch=path.name):
                payload = path.read_bytes()
                self.assertTrue(payload.endswith(b"\n"), "patch must end with a newline")
                self.assertFalse(payload.endswith(b"\n\n"), "patch has a blank line at EOF")
                # Context/removal lines preserve the pinned upstream input verbatim.
                trailing = [
                    line_number
                    for line_number, line in enumerate(payload.splitlines(), start=1)
                    if line.startswith(b"+") and not line.startswith(b"+++") and line.endswith((b" ", b"\t"))
                ]
                self.assertEqual(trailing, [], "patch contains trailing whitespace")

    def test_series_contains_regressions_and_no_private_or_rom_derived_data(self) -> None:
        combined = "\n".join(path.read_text(encoding="utf-8") for path in sorted((SERIES_ROOT / "series").glob("*.patch")))
        for required in (
            "read_be_u32",
            "discarded_load",
            "N64Recomp.phase4_regressions",
            "target_section_offset",
            "emit_reserved_instruction",
            "SLJIT_ARGS2(W, P, 32)",
            "invalidate_stack",
            "DIVU32",
            "!tests/phase4_regression_test.cpp",
            "indirect_decision_sidecar_path",
            "exact-generated-callable-entry-set",
            "MaxIndirectDecisionSidecarBytes",
            "native-return",
            "active-native-return-continuation",
            "direct_calls",
            "checked-lookup-call",
            "resolved-generated-callable",
            "fail-closed-lookup-miss",
            "MaxDirectCallEmissions",
            "MaxDirectCallInstructionClassBytes",
            "instruction_class",
            "bgezal",
            "transfer_role",
            "direct-tail",
            "conditional-branch",
        ):
            self.assertIn(required, combined)
        self.assertNotRegex(combined, re.compile(r"[A-Za-z]:[\\/](?:Users|home)[\\/]"))
        self.assertNotRegex(combined, re.compile(r"/(?:home|Users)/"))
        self.assertNotRegex(combined, re.compile(r"\bfn_[0-9]{3}_[0-9]{4}\b"))
        self.assertNotIn("generated-callable-set-v1", combined)

    def test_applicator_accepts_clean_locked_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ApplicatorFixture(Path(directory))
            result = APPLICATOR.apply_patchset(fixture.project, fixture.target)
            self.assertEqual(result["status"], "applied")
            self.assertEqual(result["patch_count"], 2)
            self.assertRegex(result["patchset_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual((fixture.target / "a.txt").read_text(encoding="utf-8"), "changed-a\n")
            self.assertEqual((fixture.target / "b.txt").read_text(encoding="utf-8"), "changed-b\n")

    def test_applicator_rejects_wrong_pin(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ApplicatorFixture(Path(directory))
            fixture.write_lock("0" * 40)
            with self.assertRaisesRegex(APPLICATOR.PatchsetError, "wrong_base_commit"):
                APPLICATOR.apply_patchset(fixture.project, fixture.target)

    def test_applicator_rejects_missing_patch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ApplicatorFixture(Path(directory))
            (fixture.series / "0002-change-b.patch").unlink()
            with self.assertRaisesRegex(APPLICATOR.PatchsetError, "series_mismatch"):
                APPLICATOR.apply_patchset(fixture.project, fixture.target)

    def test_applicator_rejects_reordered_series(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ApplicatorFixture(Path(directory))
            fixture.write_manifest(list(reversed(fixture.manifest_entries())))
            with self.assertRaisesRegex(APPLICATOR.PatchsetError, "series_order_invalid"):
                APPLICATOR.apply_patchset(fixture.project, fixture.target)

    def test_applicator_rejects_tampered_patch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ApplicatorFixture(Path(directory))
            patch = fixture.series / "0001-change-a.patch"
            patch.write_text(patch.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            with self.assertRaisesRegex(APPLICATOR.PatchsetError, "patch_digest_mismatch"):
                APPLICATOR.apply_patchset(fixture.project, fixture.target)

    def test_applicator_rejects_dirty_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ApplicatorFixture(Path(directory))
            (fixture.target / "a.txt").write_text("dirty\n", encoding="utf-8")
            with self.assertRaisesRegex(APPLICATOR.PatchsetError, "dirty_target"):
                APPLICATOR.apply_patchset(fixture.project, fixture.target)

    def test_applicator_rejects_patch_changed_after_apply_check(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ApplicatorFixture(Path(directory))
            original_run = APPLICATOR._run_git_with_input
            mutated = False

            def mutate_after_check(target: Path, arguments: list[str], payload: bytes):
                nonlocal mutated
                result = original_run(target, arguments, payload)
                if (
                    not mutated
                    and arguments == ["apply", "--check", "--unidiff-zero", "-"]
                    and result.returncode == 0
                ):
                    mutated = True
                    patch = fixture.series / "0001-change-a.patch"
                    patch.write_text(
                        patch.read_text(encoding="utf-8").replace("+changed-a", "+tampered-a"),
                        encoding="utf-8",
                        newline="\n",
                    )
                    entries = fixture.manifest_entries()
                    entries[0]["sha256"] = hashlib.sha256(patch.read_bytes()).hexdigest()
                    fixture.write_manifest(entries)
                return result

            with mock.patch.object(APPLICATOR, "_run_git_with_input", side_effect=mutate_after_check):
                with self.assertRaisesRegex(APPLICATOR.PatchsetError, "series_changed_during_apply"):
                    APPLICATOR.apply_patchset(fixture.project, fixture.target)
            self.assertTrue(mutated)
            self.assertEqual((fixture.target / "a.txt").read_text(encoding="utf-8"), "base-a\n")

    def test_applicator_rejects_duplicate_manifest_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ApplicatorFixture(Path(directory))
            manifest_path = fixture.project / "patches" / "n64recomp" / "series.json"
            manifest_path.write_text(
                '{"schema_version":1,"schema_version":1,"dependency_id":"n64recomp","patches":[]}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(APPLICATOR.PatchsetError, "invalid_series_manifest"):
                APPLICATOR.apply_patchset(fixture.project, fixture.target)

    def test_applicator_rejects_boolean_version_and_unknown_members(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ApplicatorFixture(Path(directory))
            manifest_path = fixture.project / "patches" / "n64recomp" / "series.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["schema_version"] = True
            manifest["unexpected"] = "value"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(APPLICATOR.PatchsetError, "invalid_series_manifest"):
                APPLICATOR.apply_patchset(fixture.project, fixture.target)

    def test_applicator_rejects_duplicate_locked_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ApplicatorFixture(Path(directory))
            lock_path = fixture.project / "dependencies.lock.json"
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            lock["repositories"].append(dict(lock["repositories"][0]))
            lock_path.write_text(json.dumps(lock), encoding="utf-8")
            with self.assertRaisesRegex(APPLICATOR.PatchsetError, "invalid_dependency_lock"):
                APPLICATOR.apply_patchset(fixture.project, fixture.target)

    def test_applicator_rejects_symlinked_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ApplicatorFixture(Path(directory))
            manifest_path = fixture.project / "patches" / "n64recomp" / "series.json"
            real_is_reparse = APPLICATOR._is_reparse_point
            with mock.patch.object(
                APPLICATOR,
                "_is_reparse_point",
                side_effect=lambda path: path == manifest_path or real_is_reparse(path),
            ):
                with self.assertRaisesRegex(APPLICATOR.PatchsetError, "invalid_series_manifest"):
                    APPLICATOR.apply_patchset(fixture.project, fixture.target)

    def test_applicator_rejects_symlinked_patch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ApplicatorFixture(Path(directory))
            patch_path = fixture.series / "0001-change-a.patch"
            real_is_reparse = APPLICATOR._is_reparse_point
            with mock.patch.object(
                APPLICATOR,
                "_is_reparse_point",
                side_effect=lambda path: path == patch_path or real_is_reparse(path),
            ):
                with self.assertRaisesRegex(APPLICATOR.PatchsetError, "series_boundary_invalid"):
                    APPLICATOR.apply_patchset(fixture.project, fixture.target)

    def test_applicator_rejects_missing_altered_or_unreferenced_license(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ApplicatorFixture(Path(directory))
            license_path = fixture.project / "patches" / "n64recomp" / "LICENSE.upstream"
            license_path.unlink()
            with self.assertRaisesRegex(APPLICATOR.PatchsetError, "invalid_series_license"):
                APPLICATOR.apply_patchset(fixture.project, fixture.target)

        with tempfile.TemporaryDirectory() as directory:
            fixture = ApplicatorFixture(Path(directory))
            license_path = fixture.project / "patches" / "n64recomp" / "LICENSE.upstream"
            license_path.write_bytes(license_path.read_bytes() + b"\n")
            with self.assertRaisesRegex(APPLICATOR.PatchsetError, "license_digest_mismatch"):
                APPLICATOR.apply_patchset(fixture.project, fixture.target)

        with tempfile.TemporaryDirectory() as directory:
            fixture = ApplicatorFixture(Path(directory))
            manifest_path = fixture.project / "patches" / "n64recomp" / "series.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["license"]["file"] = "unreferenced-license.txt"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(APPLICATOR.PatchsetError, "invalid_series_manifest"):
                APPLICATOR.apply_patchset(fixture.project, fixture.target)

    def test_applicator_rejects_symlinked_license(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ApplicatorFixture(Path(directory))
            license_path = fixture.project / "patches" / "n64recomp" / "LICENSE.upstream"
            real_is_reparse = APPLICATOR._is_reparse_point
            with mock.patch.object(
                APPLICATOR,
                "_is_reparse_point",
                side_effect=lambda path: path == license_path or real_is_reparse(path),
            ):
                with self.assertRaisesRegex(APPLICATOR.PatchsetError, "invalid_series_license"):
                    APPLICATOR.apply_patchset(fixture.project, fixture.target)

    def test_applicator_rejects_symlinked_patch_ancestor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ApplicatorFixture(Path(directory))
            patch_root = fixture.project / "patches" / "n64recomp"
            real_root = fixture.project / "patches" / "n64recomp-real"
            patch_root.rename(real_root)
            try:
                patch_root.symlink_to(real_root, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory symlink creation unavailable: {exc}")
            with self.assertRaisesRegex(APPLICATOR.PatchsetError, "series_boundary_invalid"):
                APPLICATOR.apply_patchset(fixture.project, fixture.target)

    def test_applicator_rejects_windows_reparse_ancestor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ApplicatorFixture(Path(directory))
            patch_root = fixture.project / "patches" / "n64recomp"
            real_is_reparse = APPLICATOR._is_reparse_point
            with mock.patch.object(
                APPLICATOR,
                "_is_reparse_point",
                side_effect=lambda path: path == patch_root or real_is_reparse(path),
            ):
                with self.assertRaisesRegex(APPLICATOR.PatchsetError, "series_boundary_invalid"):
                    APPLICATOR.apply_patchset(fixture.project, fixture.target)

    def test_applicator_rejects_nonstandard_json_constant_and_entry_member(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = ApplicatorFixture(Path(directory))
            manifest_path = fixture.project / "patches" / "n64recomp" / "series.json"
            manifest_path.write_text(
                '{"schema_version":NaN,"dependency_id":"n64recomp","patches":[]}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(APPLICATOR.PatchsetError, "invalid_series_manifest"):
                APPLICATOR.apply_patchset(fixture.project, fixture.target)

            fixture = ApplicatorFixture(Path(directory) / "second")
            manifest_path = fixture.project / "patches" / "n64recomp" / "series.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["patches"][0]["unexpected"] = 1
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(APPLICATOR.PatchsetError, "invalid_series_manifest"):
                APPLICATOR.apply_patchset(fixture.project, fixture.target)


if __name__ == "__main__":
    unittest.main()
