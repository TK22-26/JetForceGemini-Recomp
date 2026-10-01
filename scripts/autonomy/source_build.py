"""Bind a guarded source-snapshot build to replay input identity.

This records a local build, not a hermetic toolchain/dependency attestation.
The existing candidate lane can then use the actual source commit as its base.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.autonomy.source_snapshot import git, verify as verify_snapshot
from scripts.autonomy.supervisor import file_sha256, _write_json_atomic
from scripts.phase95_bridge import runtime_digest


def pinned_file(repo, item):
    if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
        raise ValueError("invalid source-build evidence pin")
    path = Path(item["path"]).resolve(strict=True)
    if (not path.is_relative_to(repo.resolve() / "tools/private") or
            not path.is_file() or file_sha256(path) != item["sha256"]):
        raise ValueError("source-build evidence changed or is not private")
    return path


def pin(path):
    return {"path": str(path.resolve(strict=True)), "sha256": file_sha256(path)}


def build_context(repo, report_path):
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if (report.get("schema") != 1 or report.get("complete") is not True or
            report.get("build_closure_verified") is not False or
            not isinstance(report.get("commands"), list) or len(report["commands"]) != 2 or
            not isinstance(report.get("checks"), list) or len(report["checks"]) != 2 or
            any(check.get("exit_code") != 0 or check.get("stop_reason") is not None
                for check in report["checks"])):
        raise ValueError("source build did not complete both guarded commands")
    configure, build = report["commands"]
    for command in (configure, build):
        if (not isinstance(command, list) or not command or
                any(not isinstance(arg, str) for arg in command) or
                Path(command[0]).name.lower() not in ("cmake", "cmake.exe")):
            raise ValueError("source build requires recorded CMake argv")
    def argument(command, option):
        if command.count(option) != 1 or command.index(option) + 1 >= len(command):
            raise ValueError("source build command lacks explicit " + option)
        return command[command.index(option) + 1]
    source = Path(argument(configure, "-S")).resolve(strict=True)
    build_dir = Path(argument(configure, "-B")).resolve(strict=True)
    if (not source.is_relative_to(repo / "tools/private") or
            not build_dir.is_relative_to(repo / "tools/private") or
            source == build_dir or
            Path(argument(build, "--build")).resolve() != build_dir):
        raise ValueError("source build directories are not isolated private paths")
    snapshot_path = report_path.parent / "source-snapshot.json"
    if file_sha256(snapshot_path) != report.get("source_snapshot_sha256"):
        raise ValueError("source snapshot changed after build")
    snapshot = verify_snapshot(repo, snapshot_path)
    if snapshot["source_commit"] != report.get("source_commit"):
        raise ValueError("build source commit differs from snapshot")
    return report, source, build_dir


def seal(repo: Path, report_path: Path, executable: Path) -> dict:
    repo = repo.resolve(strict=True)
    report_path = pinned_file(repo, pin(report_path))
    target = report_path.parent / "source-build.json"
    if target.exists():
        raise ValueError("source build already sealed")
    report, source, build_dir = build_context(repo, report_path)
    executable = executable.resolve(strict=True)
    if (not executable.is_relative_to(build_dir) or
            file_sha256(executable) != report.get("executable_sha256") or
            git(source, "rev-parse", "HEAD").decode().strip() != report["source_commit"] or
            git(source, "status", "--porcelain", "--untracked-files=all").strip()):
        raise ValueError("source worktree or build executable differs from recorded build")
    evidence = [report_path, report_path.parent / "source-snapshot.json"]
    for index in range(2):
        guard = report_path.parent / f"build-{index}.guard.json"
        record = json.loads(guard.read_text())
        if record.get("schema") != 1 or record.get("state") != "finished":
            raise ValueError("source build child has not finished under its guard")
        evidence += [guard, report_path.parent / f"build-{index}.stdout",
                     report_path.parent / f"build-{index}.stderr"]
    result = {"schema": 1, "kind": "source-snapshot-build", "complete": True,
              "source_commit": report["source_commit"],
              "executable": str(executable), "executable_sha256": file_sha256(executable),
              "runtime_sha256": runtime_digest(executable.parent),
              "build_closure_verified": False, "evidence": [pin(path) for path in evidence]}
    _write_json_atomic(target, result)
    binding = pin(target)
    validate(repo, binding, executable)
    return binding


def validate(repo: Path, binding: dict, executable: Path) -> dict:
    path = pinned_file(repo, binding)
    record = json.loads(path.read_text(encoding="utf-8"))
    if (record.get("schema") != 1 or record.get("kind") != "source-snapshot-build" or
            record.get("complete") is not True or
            record.get("build_closure_verified") is not False or
            not isinstance(record.get("evidence"), list) or len(record["evidence"]) != 8):
        raise ValueError("invalid source-build record")
    evidence = [pinned_file(repo, item) for item in record["evidence"]]
    report, _, build_dir = build_context(repo.resolve(), evidence[0])
    if (evidence[1] != evidence[0].parent / "source-snapshot.json" or
            record["source_commit"] != report["source_commit"] or
            not executable.resolve().is_relative_to(build_dir) or
            executable.resolve() != Path(record["executable"]) or
            record["executable_sha256"] != report["executable_sha256"] or
            file_sha256(executable) != record["executable_sha256"] or
            runtime_digest(executable.parent) != record["runtime_sha256"]):
        raise ValueError("source-build runtime identity differs")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("executable", type=Path)
    args = parser.parse_args()
    print(json.dumps(seal(Path(__file__).resolve().parents[2], args.report, args.executable)))


if __name__ == "__main__":
    main()
