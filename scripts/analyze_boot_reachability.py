"""Static direct-call boot-reachability analysis (Phase 6, native-boot path 1).

Computes the set of generated functions reachable from the boot entry via
direct calls, using the recompiler's `LOOKUP_FUNC(0x<vram>)` call convention
(`use_lookup_for_all_function_calls = true`). This narrows the libultra HLE
identification surface from every generated function to the ones the boot
actually reaches by direct call.

Scope and honesty:
- This is a LOWER BOUND. Indirect transfers (function pointers, jump tables)
  are runtime-computed and are not literals, so they are not followed here;
  they are covered by the Phase 4 indirect-lookup tables and traces, which a
  later pass folds in. The public summary states this explicitly.
- Function names and addresses are ROM-derived. The detailed reachable set is
  written only to a private (ignored) path; the public summary carries counts
  and digests only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

_SYMBOL_RE = re.compile(
    r'name\s*=\s*"(?P<name>fn_[0-9a-fA-F_]+)"\s*,\s*vram\s*=\s*'
    r"(?P<vram>0x[0-9A-Fa-f]+)(?:\s*,\s*size\s*=\s*(?P<size>0x[0-9A-Fa-f]+))?"
)
_LOOKUP_RE = re.compile(r"LOOKUP_FUNC\(\s*(0x[0-9A-Fa-f]+)\s*\)")


def _parse_symbols(symbols_path: Path) -> tuple[dict[int, str], dict[str, int], dict[int, int]]:
    vram_to_name: dict[int, str] = {}
    name_to_vram: dict[str, int] = {}
    name_to_size: dict[int, int] = {}
    text = symbols_path.read_text(encoding="utf-8")
    for match in _SYMBOL_RE.finditer(text):
        name = match.group("name")
        vram = int(match.group("vram"), 16)
        vram_to_name[vram] = name
        name_to_vram[name] = vram
        if match.group("size") is not None:
            name_to_size[vram] = int(match.group("size"), 16)
    return vram_to_name, name_to_vram, name_to_size


def _function_body_files(generated_root: Path) -> list[Path]:
    # The *_recomp.c files hold the instruction bodies (and the LOOKUP_FUNC
    # call sites); the thin fn_*.c wrappers merely call them.
    return sorted(generated_root.rglob("*_recomp.c"))


def _build_call_graph(
    body_files: list[Path], name_to_vram: dict[str, int]
) -> dict[str, set[int]]:
    edges: dict[str, set[int]] = {}
    for path in body_files:
        function = path.name[: -len("_recomp.c")]
        if function not in name_to_vram:
            continue
        targets: set[int] = set()
        for literal in _LOOKUP_RE.findall(path.read_text(encoding="utf-8")):
            targets.add(int(literal, 16))
        edges[function] = targets
    return edges


def _select_root(
    entry_vram: int, vram_to_name: dict[int, str]
) -> tuple[str | None, int | None]:
    if entry_vram in vram_to_name:
        return vram_to_name[entry_vram], entry_vram
    # No function starts exactly at the entry PC (the entry thunk sits just
    # below the first recompiled function); root at the first function at or
    # after the entry PC.
    later = sorted(v for v in vram_to_name if v >= entry_vram)
    if later:
        return vram_to_name[later[0]], later[0]
    return None, None


def analyze(
    generated_root: Path, symbols_path: Path, entry_vram: int
) -> dict[str, object]:
    vram_to_name, name_to_vram, _ = _parse_symbols(symbols_path)
    edges = _build_call_graph(_function_body_files(generated_root), name_to_vram)
    root_name, root_vram = _select_root(entry_vram, vram_to_name)

    reachable: set[str] = set()
    unresolved_targets: set[int] = set()
    edge_count = 0
    if root_name is not None:
        frontier = [root_name]
        reachable.add(root_name)
        while frontier:
            current = frontier.pop()
            for target_vram in sorted(edges.get(current, set())):
                edge_count += 1
                target_name = vram_to_name.get(target_vram)
                if target_name is None:
                    unresolved_targets.add(target_vram)
                    continue
                if target_name not in reachable:
                    reachable.add(target_name)
                    frontier.append(target_name)

    reachable_sorted = sorted(reachable, key=lambda n: name_to_vram.get(n, 0))
    detail = {
        "schema_version": 1,
        "kind": "jfg-phase6-boot-reachability-detail",
        "entry_vram": f"0x{entry_vram:08x}",
        "root_function": root_name,
        "root_vram": None if root_vram is None else f"0x{root_vram:08x}",
        "reachable_functions": reachable_sorted,
        "unresolved_direct_targets": sorted(
            f"0x{v:08x}" for v in unresolved_targets
        ),
    }
    return {
        "detail": detail,
        "total_functions": len(name_to_vram),
        "reachable_direct": len(reachable_sorted),
        "direct_call_edges": edge_count,
        "unresolved_direct_targets": len(unresolved_targets),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generated-root", required=True, type=Path)
    parser.add_argument("--symbols", required=True, type=Path)
    parser.add_argument("--entry-vram", default="0x80000400")
    parser.add_argument("--private-out", required=True, type=Path)
    parser.add_argument("--public-out", type=Path, default=None)
    arguments = parser.parse_args()

    try:
        entry_vram = int(arguments.entry_vram, 16)
    except ValueError:
        print("entry vram must be hex", file=sys.stderr)
        return 1

    result = analyze(arguments.generated_root, arguments.symbols, entry_vram)
    detail = result["detail"]
    detail_bytes = (
        json.dumps(detail, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    arguments.private_out.parent.mkdir(parents=True, exist_ok=True)
    arguments.private_out.write_bytes(detail_bytes)

    summary = {
        "schema_version": 1,
        "kind": "jfg-phase6-boot-reachability-summary",
        "analysis": "static-direct-call-lower-bound",
        "entry_vram": detail["entry_vram"],
        "root_vram": detail["root_vram"],
        "total_functions": result["total_functions"],
        "direct_call_reachable_functions": result["reachable_direct"],
        "direct_call_edges": result["direct_call_edges"],
        "unresolved_direct_targets": result["unresolved_direct_targets"],
        "note": (
            "Lower bound: indirect transfers (function pointers, jump tables) "
            "are not statically followed and are covered separately by the "
            "Phase 4 indirect-lookup tables and traces."
        ),
        "private_detail_sha256": hashlib.sha256(detail_bytes).hexdigest(),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if arguments.public_out is not None:
        arguments.public_out.parent.mkdir(parents=True, exist_ok=True)
        arguments.public_out.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
