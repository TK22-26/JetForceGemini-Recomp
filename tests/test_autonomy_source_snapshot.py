from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from scripts.autonomy import source_snapshot as snapshot


class SourceSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name).resolve()
        self.git("init", "-q")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@localhost")
        self.write(".gitignore", "/tools/\n/roms/\n")
        self.write("src/main.cpp", "original\n")
        self.write("include/delete.h", "old\n")
        self.write("docs/scope.md", "user scope\n")
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        self.parent = self.git("rev-parse", "HEAD")

    def git(self, *args):
        return snapshot.git(self.repo, *args).decode().strip()

    def write(self, path, text):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")

    def capture(self, paths, name="snapshot"):
        output = self.repo / "tools/private" / name
        return snapshot.capture(self.repo, output, paths)

    def test_includes_working_bytes_new_files_and_deletions_without_touching_index(self):
        self.write("src/main.cpp", "staged\n")
        self.git("add", "src/main.cpp")
        self.write("src/main.cpp", "working\n")
        self.write("include/new.h", "new\n")
        self.write("docs/scope.md", "user edit untouched\n")
        (self.repo / "include/delete.h").unlink()
        before = self.git("status", "--porcelain")
        index = (self.repo / ".git/index").read_bytes()
        result = self.capture(["src/main.cpp", "include/new.h", "include/delete.h"])
        self.assertEqual(self.git("rev-parse", "HEAD"), self.parent)
        self.assertEqual(index, (self.repo / ".git/index").read_bytes())
        self.assertEqual(before, self.git("status", "--porcelain"))
        self.assertEqual(self.git("show", result["source_commit"] + ":src/main.cpp"), "working")
        self.assertEqual(self.git("show", result["source_commit"] + ":docs/scope.md"), "user scope")
        self.assertEqual(self.git("show", result["source_commit"] + ":include/new.h"), "new")
        self.assertFalse(result["build_closure_verified"])
        self.assertEqual(self.git("rev-parse", result["private_ref"]), result["source_commit"])

    def test_identical_capture_has_durable_identical_commit(self):
        self.write("src/main.cpp", "changed\n")
        a = self.capture(["src/main.cpp"], "a")
        b = self.capture(["src/main.cpp"], "b")
        self.assertEqual(a["source_commit"], b["source_commit"])

    def test_unchanged_source_is_a_valid_empty_delta(self):
        self.assertEqual(self.capture(["src/main.cpp"])["changed_paths"], [])

    def test_rejects_scope_escapes_private_paths_and_directories(self):
        for relative in ("../outside", "roms/game.z64", "tools/private/x", "src/generated/x",
                         "docs/scope.md", "src", "src/../docs/scope.md", "src/x:stream"):
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                self.capture([relative])

    def test_rejects_missing_untracked_path_and_existing_output(self):
        with self.assertRaisesRegex(ValueError, "not a tracked"):
            self.capture(["src/missing.cpp"])
        self.write("src/main.cpp", "changed\n")
        self.capture(["src/main.cpp"])
        with self.assertRaisesRegex(ValueError, "new private"):
            self.capture(["src/main.cpp"])

    def test_duplicate_and_oversize_files_rejected(self):
        with self.assertRaises(ValueError):
            self.capture(["src/main.cpp", "src/main.cpp"])
        with patch.object(snapshot, "MAX_BYTES", 2), self.assertRaises(ValueError):
            self.capture(["src/main.cpp"])

    def test_snapshot_survives_later_working_changes_but_not_manifest_tampering(self):
        self.write("src/main.cpp", "changed\n")
        self.capture(["src/main.cpp"])
        self.write("src/main.cpp", "later edit\n")
        manifest = self.repo / "tools/private/snapshot/source-snapshot.json"
        record = snapshot.verify(self.repo, manifest)
        record["selected_files"][0]["blob"] = "0" * 40
        manifest.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, "blob"):
            snapshot.verify(self.repo, manifest)

    def test_detects_source_mutation_while_capturing(self):
        real_git = snapshot.git
        def racing_git(repo, *args, **kwargs):
            result = real_git(repo, *args, **kwargs)
            if args[0] == "write-tree":
                self.write("src/main.cpp", "concurrent edit\n")
            return result
        with patch.object(snapshot, "git", racing_git), self.assertRaisesRegex(ValueError, "source changed"):
            self.capture(["src/main.cpp"])

    def test_external_index_environment_cannot_redirect_capture(self):
        self.write("src/main.cpp", "changed\n")
        with patch.dict("os.environ", {"GIT_INDEX_FILE": str(self.repo / "bad-index")}):
            self.capture(["src/main.cpp"])
        self.assertFalse((self.repo / "bad-index").exists())


if __name__ == "__main__":
    unittest.main()
