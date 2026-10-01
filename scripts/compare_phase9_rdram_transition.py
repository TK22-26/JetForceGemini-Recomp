"""Summarize newly divergent RDRAM bytes across a focused update pair.

This is a diagnostic localization aid. Pre-existing memory differences can
still affect later game state, and no page is classified as a causal source.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scripts.compare_phase9_focus_rdram import (
    ACTOR_BYTES, RDRAM_BYTES, _record_at, compare as compare_focus,
)


PAGE_BYTES = 4096
MAX_PROBE_WORDS = 64
MAX_ACTOR_WORD_ROWS = 32


def summarize_actor_words(images: tuple[bytes, bytes, bytes, bytes],
                          actors: list[dict]) -> dict:
    """Bounded raw-word detail for newly different bytes in stable actor slots."""
    if any(len(image) != RDRAM_BYTES for image in images):
        raise ValueError("actor word detail requires four canonical RDRAM images")
    seen = set()
    seen_addresses = set()
    rows = []
    total = 0
    for actor in actors:
        index, address = actor.get("index"), actor.get("address")
        if (type(index) is not int or index < 0 or
                not isinstance(address, str) or not address.startswith("0x")):
            raise ValueError("invalid stable actor identity")
        try:
            guest_address = int(address, 16)
        except ValueError as error:
            raise ValueError("invalid stable actor address") from error
        base = guest_address & 0x1FFFFFFF
        if (not 0x80000000 <= guest_address <= 0x803FFE00 or
                guest_address % 4 or base + ACTOR_BYTES > RDRAM_BYTES or
                (index, address) in seen or base in seen_addresses):
            raise ValueError("invalid or duplicate stable actor region")
        seen.add((index, address))
        seen_addresses.add(base)
        for offset in range(0, ACTOR_BYTES, 4):
            start = base + offset
            words = [image[start:start + 4] for image in images]
            newly_different = [byte for byte in range(4)
                               if words[0][byte] == words[1][byte] and
                               words[2][byte] != words[3][byte]]
            if not newly_different:
                continue
            total += 1
            if len(rows) < MAX_ACTOR_WORD_ROWS:
                rows.append({
                    "index": index, "actor_address": address,
                    "word_offset": f"0x{offset:03x}",
                    "guest_address": f"0x{guest_address + offset:08x}",
                    "new_byte_offsets": newly_different,
                    "native_before": words[0].hex(),
                    "oracle_before": words[1].hex(),
                    "native_after": words[2].hex(),
                    "oracle_after": words[3].hex(),
                })
    return {"scope": "stable-actor-slots-raw-words-diagnostic-only",
            "total_newly_divergent_words": total,
            "reported_word_limit": MAX_ACTOR_WORD_ROWS,
            "first_newly_divergent_words": rows}


def stable_actor_slots(before: dict, after: dict) -> list[dict]:
    """Only slots retaining both their index and address span the transition."""
    old, new = before.get("actors"), after.get("actors")
    if not isinstance(old, list) or not isinstance(new, list):
        raise ValueError("actor trace is missing from focused transition")
    identities = {(actor["index"], actor["address"]) for actor in new}
    return [actor for actor in old
            if (actor["index"], actor["address"]) in identities]


def summarize_words(images: tuple[bytes, bytes, bytes, bytes],
                    addresses: tuple[int, ...]) -> list[dict]:
    """Read chosen guest words at both sides of a focused transition."""
    if len(addresses) > MAX_PROBE_WORDS:
        raise ValueError("too many focused word probes")
    if any(len(image) != RDRAM_BYTES for image in images):
        raise ValueError("focused word probe requires four canonical RDRAM images")
    rows = []
    for address in dict.fromkeys(addresses):
        if (type(address) is not int or address < 0x80000000 or
                address > 0x803FFFFC or address % 4 != 0):
            raise ValueError("focused word probe requires aligned KSEG0 addresses")
        offset = address & 0x1FFFFFFF
        words = [image[offset:offset + 4].hex() for image in images]
        rows.append({
            "address": f"0x{address:08x}",
            "native_before": words[0], "oracle_before": words[1],
            "native_after": words[2], "oracle_after": words[3],
            "matches_before": words[0] == words[1],
            "matches_after": words[2] == words[3],
            "newly_divergent": words[0] == words[1] and words[2] != words[3],
        })
    return rows


def summarize_transition(native_before: bytes, oracle_before: bytes,
                         native_after: bytes, oracle_after: bytes,
                         actor_regions: list[tuple[int, int]]) -> dict:
    if any(len(data) != RDRAM_BYTES for data in (
            native_before, oracle_before, native_after, oracle_after)):
        raise ValueError("RDRAM transition requires four canonical 4 MiB images")
    actor_mask = bytearray(RDRAM_BYTES)
    for start, end in actor_regions:
        if (type(start) is not int or type(end) is not int or
                start < 0 or end <= start or end > RDRAM_BYTES or
                end - start != ACTOR_BYTES):
            raise ValueError("invalid actor region in RDRAM transition")
        actor_mask[start:end] = b"\x01" * ACTOR_BYTES
    new_by_page = [0] * (RDRAM_BYTES // PAGE_BYTES)
    before_differences = after_differences = resolved_differences = 0
    new_actor = new_non_actor = 0
    for index, (n0, o0, n1, o1) in enumerate(zip(
            native_before, oracle_before, native_after, oracle_after)):
        was_different, is_different = n0 != o0, n1 != o1
        before_differences += was_different
        after_differences += is_different
        if was_different and not is_different:
            resolved_differences += 1
        elif not was_different and is_different:
            new_by_page[index // PAGE_BYTES] += 1
            if actor_mask[index]:
                new_actor += 1
            else:
                new_non_actor += 1
    pages = [{"physical_page": f"0x{index * PAGE_BYTES:06x}",
              "new_differing_bytes": count}
             for index, count in enumerate(new_by_page) if count]
    pages.sort(key=lambda item: (-item["new_differing_bytes"],
                                 item["physical_page"]))
    return {
        "before_differing_bytes": before_differences,
        "after_differing_bytes": after_differences,
        "resolved_differing_bytes": resolved_differences,
        "new_differing_bytes": new_actor + new_non_actor,
        "new_actor_bytes": new_actor,
        "new_non_actor_bytes": new_non_actor,
        "new_differing_pages": len(pages),
        "pages_by_new_difference_count": pages,
    }


def compare(native_dir: Path, oracle_dir: Path, *, native_before: int,
            oracle_before: int, native_after: int, oracle_after: int,
            word_addresses: tuple[int, ...] = ()) -> dict:
    native_dir, oracle_dir = Path(native_dir), Path(oracle_dir)
    focused = compare_focus(native_dir, oracle_dir,
                            native_before=native_before,
                            oracle_before=oracle_before,
                            native_after=native_after,
                            oracle_after=oracle_after)
    if (focused["before"]["semantic_state_match"] is not True or
            focused["after"]["semantic_state_match"] is not False):
        raise ValueError("focused pair is not a matched-to-mismatched transition")
    before_record = _record_at(
        native_dir / "retrace-hashes.jsonl.updates.jsonl", native_before)
    after_record = _record_at(
        native_dir / "retrace-hashes.jsonl.updates.jsonl", native_after)
    stable_actors = stable_actor_slots(before_record, after_record)
    actor_regions = []
    for actor in stable_actors:
        start = int(actor["address"], 16) & 0x1FFFFFFF
        actor_regions.append((start, start + ACTOR_BYTES))
    images = [directory / f"focus-update-{update}.rdram" for directory, update in (
        (native_dir, native_before), (oracle_dir, oracle_before),
        (native_dir, native_after), (oracle_dir, oracle_after))]
    image_data = tuple(path.read_bytes() for path in images)
    expected_images = (
        focused["before"]["native_rdram_sha256"],
        focused["before"]["oracle_rdram_sha256"],
        focused["after"]["native_rdram_sha256"],
        focused["after"]["oracle_rdram_sha256"],
    )
    if any(hashlib.sha256(image).hexdigest() != expected for image, expected in
           zip(image_data, expected_images)):
        raise ValueError("focused RDRAM image changed after validation")
    summary = summarize_transition(*image_data, actor_regions)
    report = {
        "kind": "jfg-phase9-rdram-transition-comparison", "schema": 1,
        "source_export": focused["source_export"],
        "input_sha256": focused["input_sha256"],
        "rom_sha256": focused["rom_sha256"],
        "focused_update_pair": {
            "native_before": native_before, "oracle_before": oracle_before,
            "native_after": native_after, "oracle_after": oracle_after,
        },
        "difference_scope": "canonical-RDRAM-bytes-diagnostic-only",
        "transition": summary,
        "actor_word_changes": summarize_actor_words(image_data, stable_actors),
        "stable_actor_slots": len(stable_actors),
        "unstable_actor_slots": len(before_record["actors"]) - len(stable_actors),
        "alignment_validated": False,
        "parity_verified": False,
    }
    if word_addresses:
        report["focused_word_probes"] = summarize_words(image_data, word_addresses)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native_dir", type=Path)
    parser.add_argument("oracle_dir", type=Path)
    parser.add_argument("--native-before", type=int, required=True)
    parser.add_argument("--oracle-before", type=int, required=True)
    parser.add_argument("--native-after", type=int, required=True)
    parser.add_argument("--oracle-after", type=int, required=True)
    parser.add_argument("--word", action="append", type=lambda value: int(value, 0),
                        default=[], help="probe an aligned KSEG0 word at both updates")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = compare(args.native_dir, args.oracle_dir,
                     native_before=args.native_before,
                     oracle_before=args.oracle_before,
                     native_after=args.native_after,
                     oracle_after=args.oracle_after,
                     word_addresses=tuple(args.word))
    rendered = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output:
        if args.output.exists():
            raise FileExistsError(args.output)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
