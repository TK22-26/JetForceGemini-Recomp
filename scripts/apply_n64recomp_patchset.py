#!/usr/bin/env python3
"""Verify and apply the locked N64Recomp patch series without shell expansion."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PATCH_NAME = re.compile(r"^(\d{4})-[a-z0-9][a-z0-9-]*\.patch$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_TIMEOUT_SECONDS = 60


class PatchsetError(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _is_reparse_point(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    file_attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISLNK(metadata.st_mode) or bool(file_attributes & reparse_attribute)


def _require_contained_path(
    project_root: Path, path: Path, invalid_reason: str, *, directory: bool = False
) -> Path:
    root = Path(os.path.abspath(project_root))
    candidate = Path(os.path.abspath(path))
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise PatchsetError(invalid_reason) from exc
    current = root
    if _is_reparse_point(current):
        raise PatchsetError(invalid_reason)
    for component in relative.parts:
        current = current / component
        if _is_reparse_point(current):
            raise PatchsetError(invalid_reason)
    try:
        resolved_root = root.resolve(strict=True)
        resolved_candidate = candidate.resolve(strict=True)
        resolved_candidate.relative_to(resolved_root)
        mode = candidate.stat(follow_symlinks=False).st_mode
    except (OSError, ValueError) as exc:
        raise PatchsetError(invalid_reason) from exc
    if directory:
        if not stat.S_ISDIR(mode):
            raise PatchsetError(invalid_reason)
    elif not stat.S_ISREG(mode):
        raise PatchsetError(invalid_reason)
    return candidate


def _read_contained_regular(project_root: Path, path: Path, invalid_reason: str) -> bytes:
    candidate = _require_contained_path(project_root, path, invalid_reason)
    try:
        return candidate.read_bytes()
    except OSError as exc:
        raise PatchsetError(invalid_reason) from exc


def _strict_json(project_root: Path, path: Path, invalid_reason: str) -> object:
    try:
        encoded = _read_contained_regular(project_root, path, invalid_reason)

        def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
            result: dict[str, object] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate key")
                result[key] = value
            return result

        return json.loads(
            encoded.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )
    except PatchsetError:
        raise
    except (OSError, ValueError, TypeError) as exc:
        raise PatchsetError(invalid_reason) from exc


def _run_git(target: Path, arguments: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(target), *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise PatchsetError("git_timeout") from exc
    except OSError as exc:
        raise PatchsetError("git_unavailable") from exc


def _run_git_with_input(
    target: Path, arguments: list[str], payload: bytes
) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ["git", "-C", str(target), *arguments],
            input=payload,
            check=False,
            capture_output=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise PatchsetError("git_timeout") from exc
    except OSError as exc:
        raise PatchsetError("git_unavailable") from exc


def _locked_commit(project_root: Path, dependency_id: str) -> str:
    lock = _strict_json(project_root, project_root / "dependencies.lock.json", "invalid_dependency_lock")
    if not isinstance(lock, dict) or type(lock.get("schema_version")) is not int or lock["schema_version"] != 1:
        raise PatchsetError("invalid_dependency_lock")
    allowed_lock_keys = {
        "$schema",
        "schema_version",
        "source_date_epoch",
        "github_actions",
        "repositories",
        "python_packages",
        "release_tools",
    }
    if not {"schema_version", "repositories"}.issubset(lock) or not set(lock).issubset(allowed_lock_keys):
        raise PatchsetError("invalid_dependency_lock")
    repositories = lock["repositories"]
    if not isinstance(repositories, list):
        raise PatchsetError("invalid_dependency_lock")
    matches = [item for item in repositories if isinstance(item, dict) and item.get("id") == dependency_id]
    if len(matches) != 1:
        raise PatchsetError("invalid_dependency_lock")
    dependency = matches[0]
    allowed_dependency_keys = {"id", "url", "commit", "license", "use", "recursive_submodules", "artifacts"}
    required_dependency_keys = {"id", "url", "commit", "license", "use", "recursive_submodules"}
    if not required_dependency_keys.issubset(dependency) or not set(dependency).issubset(allowed_dependency_keys):
        raise PatchsetError("invalid_dependency_lock")
    commit = dependency["commit"]
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise PatchsetError("invalid_dependency_lock")
    return commit


def _validated_series(project_root: Path) -> tuple[list[Path], str, bytes]:
    patch_root = project_root / "patches" / "n64recomp"
    series_dir = patch_root / "series"
    _require_contained_path(project_root, patch_root, "series_boundary_invalid", directory=True)
    _require_contained_path(project_root, series_dir, "series_boundary_invalid", directory=True)
    manifest = _strict_json(project_root, patch_root / "series.json", "invalid_series_manifest")
    if not isinstance(manifest, dict) or set(manifest) != {"schema_version", "dependency_id", "license", "patches"}:
        raise PatchsetError("invalid_series_manifest")
    dependency_id = manifest["dependency_id"]
    entries = manifest["patches"]
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1 or dependency_id != "n64recomp":
        raise PatchsetError("invalid_series_manifest")
    if not isinstance(entries, list) or not entries:
        raise PatchsetError("invalid_series_manifest")

    license_entry = manifest["license"]
    if not isinstance(license_entry, dict) or set(license_entry) != {"file", "sha256"}:
        raise PatchsetError("invalid_series_manifest")
    if license_entry["file"] != "LICENSE.upstream" or license_entry["sha256"] != "d439b523a90a07f87182b0cf8fab9b09e385642f9f573b7ae67306d3fb68af88":
        raise PatchsetError("invalid_series_manifest")
    license_payload = _read_contained_regular(
        project_root, patch_root / "LICENSE.upstream", "invalid_series_license"
    )
    if hashlib.sha256(license_payload).hexdigest() != license_entry["sha256"]:
        raise PatchsetError("license_digest_mismatch")

    paths: list[Path] = []
    payloads: list[bytes] = []
    names: list[str] = []
    aggregate = hashlib.sha256()
    aggregate.update(license_entry["file"].encode("utf-8"))
    aggregate.update(b"\0")
    aggregate.update(bytes.fromhex(license_entry["sha256"]))
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise PatchsetError("invalid_series_manifest")
        if set(entry) != {"file", "sha256"}:
            raise PatchsetError("invalid_series_manifest")
        name = entry.get("file")
        expected_hash = entry.get("sha256")
        if not isinstance(name, str) or not isinstance(expected_hash, str):
            raise PatchsetError("invalid_series_manifest")
        match = PATCH_NAME.fullmatch(name)
        if match is None or int(match.group(1)) != index or name != Path(name).name:
            raise PatchsetError("series_order_invalid")
        if SHA256.fullmatch(expected_hash) is None:
            raise PatchsetError("invalid_series_manifest")
        candidate_path = series_dir / name
        if not candidate_path.exists() and not _is_reparse_point(candidate_path):
            raise PatchsetError("series_mismatch")
        path = _require_contained_path(project_root, candidate_path, "series_boundary_invalid")
        payload = _read_contained_regular(project_root, path, "series_boundary_invalid")
        actual_hash = hashlib.sha256(payload).hexdigest()
        if actual_hash != expected_hash:
            raise PatchsetError("patch_digest_mismatch")
        names.append(name)
        paths.append(path)
        payloads.append(payload)
        aggregate.update(name.encode("utf-8"))
        aggregate.update(b"\0")
        aggregate.update(bytes.fromhex(actual_hash))

    try:
        actual_names = sorted(path.name for path in series_dir.iterdir() if path.suffix == ".patch")
    except OSError as exc:
        raise PatchsetError("series_mismatch") from exc
    if actual_names != names:
        raise PatchsetError("series_mismatch")
    return paths, aggregate.hexdigest(), b"".join(payloads)


def apply_patchset(project_root: Path, target: Path) -> dict[str, object]:
    patches, patchset_digest, patch_payload = _validated_series(project_root)
    locked_commit = _locked_commit(project_root, "n64recomp")

    head = _run_git(target, ["rev-parse", "--verify", "HEAD"])
    if head.returncode != 0:
        raise PatchsetError("invalid_target")
    if head.stdout.strip() != locked_commit:
        raise PatchsetError("wrong_base_commit")

    status = _run_git(
        target,
        ["status", "--porcelain=v1", "--untracked-files=all", "--ignore-submodules=none"],
    )
    if status.returncode != 0:
        raise PatchsetError("invalid_target")
    if status.stdout:
        raise PatchsetError("dirty_target")

    check = _run_git_with_input(
        target,
        ["apply", "--check", "--unidiff-zero", "-"],
        patch_payload,
    )
    if check.returncode != 0:
        raise PatchsetError("apply_check_failed")

    # Detect changes after the check. Even if files change after this second
    # validation, apply the original bytes held in memory rather than reopening
    # mutable patch paths.
    second_paths, second_digest, second_payload = _validated_series(project_root)
    if second_paths != patches or second_digest != patchset_digest or second_payload != patch_payload:
        raise PatchsetError("series_changed_during_apply")
    apply_result = _run_git_with_input(
        target,
        ["apply", "--unidiff-zero", "-"],
        patch_payload,
    )
    if apply_result.returncode != 0:
        raise PatchsetError("apply_failed")

    return {
        "status": "applied",
        "patch_count": len(patches),
        "patchset_sha256": patchset_digest,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args(argv)
    try:
        result = apply_patchset(args.project_root.resolve(), args.target.resolve())
    except PatchsetError as exc:
        result = {"status": "error", "reason": exc.reason}
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
