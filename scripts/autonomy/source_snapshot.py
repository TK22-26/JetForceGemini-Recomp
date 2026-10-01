"""Freeze explicitly selected source changes without touching the user's index.

The detached commit is local build input, not an approved change or proof that
an existing executable was built from it. ROM/private trees are never captured.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import subprocess
import tempfile


SOURCE_ROOTS = {"src", "include", "cmake", "scripts", "tests", "config", "patches"}
SOURCE_FILES = {"CMakeLists.txt", "CMakePresets.json", ".gitattributes", ".gitignore"}
MAX_BYTES = 64 * 1024 * 1024


def git(repo: Path, *args: str, env=None, data=None) -> bytes:
    # Never inherit a caller's alternate worktree/index/object database.
    clean = {key: value for key, value in os.environ.items()
             if not key.upper().startswith("GIT_")}
    clean.update(GIT_OPTIONAL_LOCKS="0", GIT_LITERAL_PATHSPECS="1")
    clean.update(env or {})
    result = subprocess.run(["git", "-C", str(repo), *args], input=data,
                            capture_output=True, env=clean, timeout=60)
    if result.returncode:
        raise ValueError("source snapshot Git operation failed: " +
                         result.stderr.decode("utf-8", errors="replace")[:500])
    return result.stdout


def safe_path(relative: str) -> None:
    parts = relative.split("/")
    if (not relative or "\\" in relative or ":" in relative or
            PurePosixPath(relative).is_absolute() or
            PureWindowsPath(relative).is_reserved() or
            any(p in ("", ".", "..") or p.endswith((".", " ")) for p in parts) or
            any(p.lower() in (".git", "private", "generated") for p in parts) or
            (relative not in SOURCE_FILES and parts[0] not in SOURCE_ROOTS)):
        raise ValueError("snapshot path is outside public source scope: " + relative)


def describe(repo: Path, relative: str) -> dict:
    safe_path(relative)
    path = repo / relative
    if not path.resolve().is_relative_to(repo):
        raise ValueError("snapshot source escapes repository")
    for parent in (path, *path.parents):
        if parent == repo:
            break
        if parent.is_symlink() or (hasattr(parent, "is_junction") and parent.is_junction()):
            raise ValueError("snapshot source contains a link")
    if not path.exists():
        return {"path": relative, "sha256": None, "size": 0}
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("snapshot source is not a bounded regular file")
    data = path.read_bytes()
    return {"path": relative, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}


def private_output(repo: Path, output: Path) -> Path:
    output = output.resolve()
    if not output.is_relative_to(repo / "tools/private") or output.exists():
        raise ValueError("snapshot output must be a new private directory")
    return output


def capture(repo: Path, output: Path, paths: list[str]) -> dict:
    repo = repo.resolve(strict=True)
    output = private_output(repo, output)
    if not paths or len(paths) > 500 or len(paths) != len(set(paths)):
        raise ValueError("snapshot requires 1-500 unique explicit file paths")
    paths = sorted(paths)
    before = [describe(repo, path) for path in paths]
    if sum(item["size"] for item in before) > MAX_BYTES:
        raise ValueError("snapshot source exceeds byte budget")
    parent = git(repo, "rev-parse", "HEAD").decode().strip()
    index = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-path", "index")
                 .decode().strip())
    index_bytes = index.read_bytes() if index.exists() else None
    tracked = set(git(repo, "ls-files", "-z").decode().split("\0"))
    for item in before:
        if item["sha256"] is None and item["path"] not in tracked:
            raise ValueError("snapshot deletion is not a tracked source file")
    output.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="index-", dir=output) as directory:
        env = {"GIT_INDEX_FILE": str(Path(directory) / "index")}
        git(repo, "read-tree", parent, env=env)
        git(repo, "add", "-A", "--pathspec-from-file=-", "--pathspec-file-nul",
            env={**env, "GIT_LITERAL_PATHSPECS": "1"},
            data=("\0".join(paths) + "\0").encode())
        changed = [name for name in git(
            repo, "diff", "--cached", "--name-only", "--no-renames", "-z",
            parent, "--", env=env).decode().split("\0") if name]
        if not set(changed) <= set(paths):
            raise ValueError("snapshot index contains changes outside explicit paths")
        tree = git(repo, "write-tree", env=env).decode().strip()
        entries = git(repo, "ls-tree", "-r", "-z", tree).split(b"\0")
        blobs = {}
        for entry in entries:
            if not entry:
                continue
            header, name = entry.split(b"\t", 1)
            if name.decode() in paths:
                mode, kind, oid = header.decode().split()
                if mode not in ("100644", "100755") or kind != "blob":
                    raise ValueError("snapshot tree contains a non-regular source")
                blobs[name.decode()] = {"mode": mode, "blob": oid}
        stamp = git(repo, "show", "-s", "--format=%ct", parent).decode().strip()
        commit_env = {**env, "GIT_AUTHOR_NAME": "Autonomy Source Snapshot",
                      "GIT_AUTHOR_EMAIL": "autonomy-snapshot@localhost",
                      "GIT_COMMITTER_NAME": "Autonomy Source Snapshot",
                      "GIT_COMMITTER_EMAIL": "autonomy-snapshot@localhost",
                      "GIT_AUTHOR_DATE": "@" + stamp + " +0000",
                      "GIT_COMMITTER_DATE": "@" + stamp + " +0000"}
        commit = git(repo, "-c", "commit.gpgsign=false", "commit-tree", tree,
                     "-p", parent, env=commit_env,
                     data=b"Private source baseline; not reviewed or merged.\n").decode().strip()
    if before != [describe(repo, path) for path in paths]:
        raise ValueError("source changed while snapshot was captured")
    if (git(repo, "rev-parse", "HEAD").decode().strip() != parent or
            (index.read_bytes() if index.exists() else None) != index_bytes):
        raise ValueError("user HEAD or index changed during source capture")
    result = {"schema": 1, "kind": "private-source-snapshot", "source_commit": commit,
              "parent_commit": parent, "tree": tree, "selected_files": [
                  {**item, **blobs.get(item["path"], {"mode": None, "blob": None})}
                  for item in before], "changed_paths": changed,
              "build_closure_verified": False, "reviewed": False}
    # A private ref makes the source durable across Git GC; no branch is moved.
    ref = "refs/autonomy/source-snapshots/" + commit
    git(repo, "update-ref", ref, commit)
    result["private_ref"] = ref
    (output / "source-snapshot.json").write_text(json.dumps(result, indent=2) + "\n",
                                                  encoding="utf-8", newline="\n")
    verify(repo, output / "source-snapshot.json")
    return result


def verify(repo: Path, manifest: Path) -> dict:
    """Verify immutable commit contents, not current dirty working files."""
    record = json.loads(manifest.read_text(encoding="utf-8"))
    if (record.get("schema") != 1 or record.get("kind") != "private-source-snapshot" or
            record.get("build_closure_verified") is not False or
            record.get("reviewed") is not False):
        raise ValueError("invalid source snapshot manifest")
    commit = record["source_commit"]
    if (not isinstance(commit, str) or len(commit) not in (40, 64) or
            any(char not in "0123456789abcdef" for char in commit)):
        raise ValueError("invalid snapshot commit")
    if (git(repo, "rev-parse", commit + "^{tree}").decode().strip() != record["tree"] or
            git(repo, "rev-parse", commit + "^").decode().strip() != record["parent_commit"]):
        raise ValueError("snapshot commit identity changed")
    changed = [name for name in git(
        repo, "diff-tree", "--no-commit-id", "--name-only", "--no-renames",
        "-r", "-z", record["parent_commit"], commit).decode().split("\0") if name]
    if changed != record["changed_paths"]:
        raise ValueError("snapshot changed paths differ")
    files = record["selected_files"]
    names = [item["path"] for item in files]
    if (not 1 <= len(names) <= 500 or names != sorted(set(names)) or
            not set(changed) <= set(names)):
        raise ValueError("invalid snapshot selected files")
    entries = {}
    for entry in git(repo, "ls-tree", "-r", "-z", commit).split(b"\0"):
        if entry:
            header, name = entry.split(b"\t", 1)
            entries[name.decode()] = header.decode()
    for item in files:
        safe_path(item["path"])
        entry = entries.get(item["path"])
        if item["blob"] is None:
            if entry or item["sha256"] is not None or item["mode"] is not None:
                raise ValueError("snapshot deletion differs")
        elif entry != item["mode"] + " blob " + item["blob"]:
            raise ValueError("snapshot blob identity differs")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("paths", nargs="+", help="explicit public source files, never directories")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    result = capture(root, args.output, args.paths)
    print(json.dumps({"source_commit": result["source_commit"],
                      "changed_files": len(result["changed_paths"]),
                      "manifest": str(args.output / "source-snapshot.json")}))


if __name__ == "__main__":
    main()
