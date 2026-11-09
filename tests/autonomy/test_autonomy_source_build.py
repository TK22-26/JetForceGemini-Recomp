import json
from pathlib import Path
import unittest

from scripts.autonomy import source_build, source_snapshot
from scripts.autonomy.supervisor import file_sha256
from tests import test_autonomy_source_snapshot as fixtures


class SourceBuildTests(unittest.TestCase):
    setUp = fixtures.SourceSnapshotTests.setUp
    git = fixtures.SourceSnapshotTests.git
    write = fixtures.SourceSnapshotTests.write
    capture = fixtures.SourceSnapshotTests.capture

    def fixture(self):
        # Synthetic producer output tests validation only, not real compilation.
        self.write("src/main.cpp", "changed\n")
        snapshot = self.capture(["src/main.cpp"])
        out = self.repo / "tools/private/snapshot"
        source = self.repo / "tools/private/source"
        self.git("worktree", "add", "--detach", str(source), snapshot["source_commit"])
        build = self.repo / "tools/private/build"
        executable = build / "Release/test.exe"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"synthetic executable")
        (executable.parent / "test.dll").write_bytes(b"synthetic dependency")
        record = {"schema": 1, "complete": True, "build_closure_verified": False,
                  "source_commit": snapshot["source_commit"],
                  "source_snapshot_sha256": file_sha256(out / "source-snapshot.json"),
                  "executable_sha256": file_sha256(executable),
                  "commands": [["cmake", "-S", str(source), "-B", str(build)],
                               ["cmake", "--build", str(build)]],
                  "checks": [{"exit_code": 0, "stop_reason": None}] * 2}
        report = out / "build-result.json"
        report.write_text(json.dumps(record))
        for index in range(2):
            (out / f"build-{index}.guard.json").write_text(json.dumps({"schema": 1, "state": "finished"}))
            (out / f"build-{index}.stdout").write_text("synthetic log")
            (out / f"build-{index}.stderr").write_text("")
        return report, executable, source

    def test_binding_keeps_actual_source_and_rejects_changed_dll(self):
        report, executable, _ = self.fixture()
        binding = source_build.seal(self.repo, report, executable)
        result = source_build.validate(self.repo, binding, executable)
        self.assertNotEqual(result["source_commit"], self.parent)
        self.assertFalse(result["build_closure_verified"])
        executable.with_suffix(".dll").write_bytes(b"changed dependency")
        with self.assertRaisesRegex(ValueError, "runtime identity"):
            source_build.validate(self.repo, binding, executable)

    def test_cannot_seal_dirty_or_wrong_source(self):
        report, executable, source = self.fixture()
        (source / "src/main.cpp").write_text("unreviewed later edit")
        with self.assertRaisesRegex(ValueError, "worktree"):
            source_build.seal(self.repo, report, executable)

    def test_cannot_seal_incomplete_build_or_unfinished_guard(self):
        report, executable, _ = self.fixture()
        record = json.loads(report.read_text())
        record["checks"][1]["exit_code"] = 1
        report.write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, "both guarded commands"):
            source_build.seal(self.repo, report, executable)
        record["checks"][1]["exit_code"] = 0
        report.write_text(json.dumps(record))
        (report.parent / "build-1.guard.json").write_text('{"schema":1,"state":"guarded"}')
        with self.assertRaisesRegex(ValueError, "has not finished"):
            source_build.seal(self.repo, report, executable)

    def test_rejects_modified_report_after_sealing(self):
        report, executable, _ = self.fixture()
        binding = source_build.seal(self.repo, report, executable)
        report.write_text(report.read_text() + " ")
        with self.assertRaisesRegex(ValueError, "evidence changed"):
            source_build.validate(self.repo, binding, executable)

    def test_rejects_wrong_executable_or_source_snapshot(self):
        report, executable, _ = self.fixture()
        executable.write_bytes(b"other exe")
        with self.assertRaisesRegex(ValueError, "executable differs"):
            source_build.seal(self.repo, report, executable)
        (report.parent / "source-snapshot.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "snapshot changed"):
            source_build.seal(self.repo, report, executable)

    def test_cannot_overwrite_existing_build_seal(self):
        report, executable, _ = self.fixture()
        source_build.seal(self.repo, report, executable)
        with self.assertRaisesRegex(ValueError, "already sealed"):
            source_build.seal(self.repo, report, executable)


if __name__ == "__main__":
    unittest.main()
