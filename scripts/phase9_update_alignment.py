"""Locate the first semantic difference at completed game-update boundaries.

Controller-poll and VI clocks can drift while guest updates still agree. This
report deliberately does not claim that the two runs consumed identical input
at the same update, or that their initial Controller Pak state is equivalent.
"""

from __future__ import annotations

import argparse
import hashlib
from itertools import zip_longest
import json
from pathlib import Path

from scripts.compare_phase9_retrace_hashes import describe_difference, semantic_digest
from scripts.compare_phase9_update_hashes import records


NATIVE_CLOCKS = ("controller_polls", "vi_retraces")
ORACLE_CLOCKS = ("controller_polls", "oracle_consumed_vi", "emulator_frame")


def _sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _clock(record: dict | None, keys: tuple[str, ...]) -> dict | None:
    if record is None:
        return None
    return {key: record.get(key) for key in keys}


def analyze(native: Path, oracle: Path) -> dict:
    native, oracle = Path(native), Path(oracle)
    report = {
        "kind": "jfg-phase9-update-alignment", "schema": 1,
        "native_sha256": _sha256(native), "oracle_sha256": _sha256(oracle),
        "matching_update_prefix": 0, "first_poll_clock_difference": None,
        "first_semantic_difference": None, "compared_updates": 0,
        "alignment_validated": False, "parity_verified": False,
        "caveat": "Equal update states do not prove equal input timing or initial Pak state.",
    }
    left, right = records(native), records(oracle)
    try:
        for index, (a, b) in enumerate(zip_longest(left, right), 1):
            if a is None or b is None:
                report["first_semantic_difference"] = {
                    "update": index, "reason": "missing-update",
                    "missing": "native" if a is None else "oracle",
                    "native_clock": _clock(a, NATIVE_CLOCKS),
                    "oracle_clock": _clock(b, ORACLE_CLOCKS),
                }
                break
            report["compared_updates"] = index
            if (report["first_poll_clock_difference"] is None and
                    a.get("controller_polls") != b.get("controller_polls")):
                report["first_poll_clock_difference"] = {
                    "update": index,
                    "native_polls": a.get("controller_polls"),
                    "oracle_polls": b.get("controller_polls"),
                }
            if semantic_digest(a) != semantic_digest(b):
                components, actors = describe_difference(a, b)
                report["first_semantic_difference"] = {
                    "update": index, "reason": "state-difference",
                    "components": components,
                    "actor_indices": [row["index"] for row in actors],
                    "native_clock": _clock(a, NATIVE_CLOCKS),
                    "oracle_clock": _clock(b, ORACLE_CLOCKS),
                }
                break
            report["matching_update_prefix"] = index
    finally:
        left.close()
        right.close()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native", type=Path)
    parser.add_argument("oracle", type=Path)
    args = parser.parse_args()
    print(json.dumps(analyze(args.native, args.oracle), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
