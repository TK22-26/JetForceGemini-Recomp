from __future__ import annotations

import argparse
import json
import re
import struct
from pathlib import Path


OLD_MODULE = struct.Struct("<QIIIII")
NEW_MODULE = struct.Struct("<QIIIIIIB3x")
SUITE = struct.Struct("<IHHI16s")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--lookup", type=Path, required=True)
    parser.add_argument("--candidate-ordinals", required=True)
    parser.add_argument("--context-seeds", default="1")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    args = parser.parse_args()

    payload = args.input.read_bytes()
    if payload[:8] != b"JFG2OVL3":
        raise SystemExit("not a V3 case")
    _version, _subjects, module_count, _guest, _token = SUITE.unpack_from(payload, 8)
    ordinals = [int(item) for item in args.candidate_ordinals.split(",")]
    seeds = [int(item) for item in args.context_seeds.split(",")]
    if len(seeds) == 1:
        seeds *= module_count
    if len(ordinals) != module_count or any(item <= 0 for item in ordinals):
        raise SystemExit("candidate ordinal count mismatch")
    seed_names = (
        "zero",
        "stack",
        "stack-and-frame",
        "stack-and-arguments",
        "stack-frame-and-arguments",
    )
    if len(seeds) != module_count or any(
        item < 0 or item >= len(seed_names) for item in seeds
    ):
        raise SystemExit("context seed count mismatch")

    entries: dict[int, list[int]] = {}
    pattern = re.compile(
        r"\{(\d+)u,\s*UINT32_C\(0x([0-9A-Fa-f]{8})\),"
    )
    for section_text, offset_text in pattern.findall(
        args.lookup.read_text(encoding="utf-8")
    ):
        entries.setdefault(int(section_text), []).append(int(offset_text, 16))

    cursor = 8 + SUITE.size
    body = bytearray(payload[:cursor])
    plan_modules: list[dict[str, object]] = []
    for ordinal, context_seed in zip(ordinals, seeds):
        token, section, base, text, reserved, size = OLD_MODULE.unpack_from(
            payload, cursor
        )
        cursor += OLD_MODULE.size
        offsets = entries.get(section, [])
        if ordinal > len(offsets):
            raise SystemExit("candidate ordinal is unavailable")
        function_offset = offsets[ordinal - 1]
        if function_offset >= text:
            raise SystemExit("candidate is outside module text")
        body.extend(
            NEW_MODULE.pack(
                token,
                section,
                base,
                text,
                reserved,
                size,
                function_offset,
                context_seed,
            )
        )
        body.extend(payload[cursor : cursor + size])
        cursor += size
        plan_modules.append(
            {
                "section": section,
                "function_offset": function_offset,
                "context_seed": seed_names[context_seed],
            }
        )
    body.extend(payload[cursor:])
    if args.output.exists() or args.plan.exists():
        raise SystemExit("output already exists")
    args.output.write_bytes(body)
    args.plan.write_text(
        json.dumps(
            {"schema_version": 1, "modules": plan_modules},
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
