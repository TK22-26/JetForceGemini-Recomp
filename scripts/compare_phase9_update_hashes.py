"""Compare completed guest-update state; never reinterpret VI records as updates."""
import argparse
import json
from itertools import zip_longest
from pathlib import Path

from scripts.compare_phase9_retrace_hashes import (
    describe_difference, semantic_digest, validate_state,
)


def records(path: Path):
    with path.open(encoding="utf-8") as stream:
        header = json.loads(next(stream, "null"))
        if header != {"kind": "jfg-phase9-update-hash-header", "schema": 1}:
            raise ValueError(f"invalid completed-update header: {path}")
        expected = 1
        for line in stream:
            record = json.loads(line)
            if (not isinstance(record, dict)
                    or record.get("kind") != "jfg-phase9-update-hash"
                    or type(record.get("schema")) is not int or record["schema"] != 1
                    or type(record.get("update")) is not int
                    or record["update"] != expected):
                raise ValueError(f"invalid or missing update {expected}: {path}")
            for key in ("controller_polls", "vi_retraces", "emulator_frame",
                        "oracle_consumed_vi"):
                if key in record and (type(record[key]) is not int or record[key] < 0):
                    raise ValueError(f"invalid {key} at update {expected}: {path}")
            if ("vi_retraces" in record or "emulator_frame" in record) and \
                    "controller_polls" not in record:
                raise ValueError(f"missing controller_polls at update {expected}: {path}")
            validate_state(record)
            yield record
            expected += 1
        if expected == 1:
            raise ValueError(f"empty completed-update stream: {path}")


def compare(native: Path, oracle: Path, updates: int | None = None):
    if updates is not None and updates < 1:
        raise ValueError("prefix update count must be positive")
    report = {"kind": "jfg-phase9-update-comparison", "schema": 1,
              "scope": "prefix" if updates is not None else "entire-stream",
              "requested_updates": updates, "compared_updates": 0, "match": False,
              "first_divergence": None}
    left, right = records(native), records(oracle)
    try:
        for index, (a, b) in enumerate(zip_longest(left, right), 1):
            if a is None or b is None:
                report["first_divergence"] = {"update": index, "reason": "missing-update",
                                               "missing": "native" if a is None else "oracle"}
                return report
            report["compared_updates"] = index
            if semantic_digest(a) != semantic_digest(b):
                components, actors = describe_difference(a, b)
                report["first_divergence"] = {"update": index, "components": components,
                                               "actor_differences": actors}
                return report
            if index == updates:
                report["match"] = True
                return report
        if updates is not None and report["compared_updates"] < updates:
            report["first_divergence"] = {"reason": "prefix-not-reached"}
        else:
            report["match"] = True
        return report
    finally:
        left.close()
        right.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native", type=Path)
    parser.add_argument("oracle", type=Path)
    parser.add_argument("--updates", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = compare(args.native, args.oracle, args.updates)
    rendered = json.dumps(report, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
