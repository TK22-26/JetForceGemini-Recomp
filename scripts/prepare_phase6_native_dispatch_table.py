"""Validate private Phase 6 identification and write a private build include."""
from __future__ import annotations
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

_TOP = {"schema_version", "kind", "source", "entrypoint_vram", "identified"}
_ENTRY = {"libultra", "vram", "generated_function", "in_generated_set"}
_HEX = re.compile(r"0x[0-9a-f]{8}\Z")
_FN = re.compile(r"fn_[0-9a-f_]+\Z")
# Values are written into a C++ string literal.  Restricting to public SDK C
# identifiers makes source injection impossible and keeps mappings private.
_SDK_NAME = re.compile(
    r"(?:(?:os|__os)[A-Za-z_][A-Za-z0-9_]*|bzero|bcopy|bcmp)\Z"
)
_BUILD_OUTPUT = re.compile(r"build(?:-.*)?\Z")


def fail(message: str) -> None:
    raise ValueError(message)


def validate(document: object) -> list[tuple[int, str]]:
    if not isinstance(document, dict) or set(document) != _TOP:
        fail("invalid identification schema")
    if document["schema_version"] != 1 or document["kind"] != "jfg-phase6-libultra-identification-detail":
        fail("unsupported identification")
    if document["entrypoint_vram"] != "0x80000400":
        fail("mismatched entrypoint")
    entries = document["identified"]
    if not isinstance(entries, list):
        fail("identified must be an array")
    result: list[tuple[int, str]] = []
    vrams: set[int] = set()
    names: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != _ENTRY:
            fail("invalid identified entry")
        name, vram, function, mapped = entry["libultra"], entry["vram"], entry["generated_function"], entry["in_generated_set"]
        if not isinstance(name, str) or not _SDK_NAME.fullmatch(name):
            fail("unsafe libultra name")
        if not isinstance(vram, str) or not _HEX.fullmatch(vram):
            fail("invalid vram")
        if not isinstance(mapped, bool):
            fail("invalid mapped flag")
        if mapped:
            if not isinstance(function, str) or not _FN.fullmatch(function):
                fail("mapped entry requires generated function")
        elif function is not None:
            fail("unmapped entry requires null generated function")
        value = int(vram, 16)
        if value in vrams or name in names:
            fail("duplicate vram or name")
        vrams.add(value)
        names.add(name)
        if mapped:
            result.append((value, name))
    if not result:
        fail("empty mapped identification")
    return sorted(result)


def output_is_inside_repo(output: Path, repo: Path) -> bool:
    """Compare normalized paths without confusing containment with policy errors."""
    try:
        return os.path.commonpath(
            (os.path.normcase(str(output)), os.path.normcase(str(repo)))
        ) == os.path.normcase(str(repo))
    except ValueError:
        return False


def validate_output_path(output: Path, repo: Path) -> None:
    if not output_is_inside_repo(output, repo):
        return

    relative_output = Path(os.path.relpath(output, repo))
    if not relative_output.parts or not _BUILD_OUTPUT.fullmatch(relative_output.parts[0]):
        fail("output inside repository must be a top-level build output")

    relative_text = relative_output.as_posix()
    ignored = subprocess.run(
        ["git", "-C", str(repo), "check-ignore", "--quiet", "--", relative_text],
        check=False,
    ).returncode == 0
    tracked = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "--error-unmatch", "--", relative_text],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0
    if not ignored or tracked:
        fail("output inside repository must be ignored and untracked")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--identification", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        output = args.output.resolve()
        repo = Path(__file__).resolve().parent.parent
        validate_output_path(output, repo)
        entries = validate(json.loads(args.identification.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"phase6 dispatch table: {error}", file=sys.stderr)
        return 1
    output.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(f'{{0x{vram:08x}U, "{name}"}},' for vram, name in entries)
    output.write_text("// Private build output; do not track.\n" + body + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
