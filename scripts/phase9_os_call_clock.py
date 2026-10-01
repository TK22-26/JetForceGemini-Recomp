"""Classify bounded reference OS intervals; never install fitted costs."""
import argparse
import collections
import json
from pathlib import Path
import re

HEADER = ("id update thread kind queue block valid capacity output caller ticks "
          "exceptions switches result").split()
HEX = re.compile(r"0x[0-9a-f]{8}\Z")


def read(path):
    lines = Path(path).read_text().splitlines()
    if not 3 <= len(lines) <= 4098 or lines[0].split("\t") != HEADER:
        raise ValueError("invalid OS clock trace header or bounds")
    footer = lines[-1].split("\t")
    if len(footer) != 4 or footer[:2] != ["result", "true"] or \
            not all(value.isdecimal() for value in footer[2:]) or \
            int(footer[2]) != len(lines) - 2 or int(footer[3]) > 4096:
        raise ValueError("incomplete OS clock trace")
    rows, ids = [], set()
    for line in lines[1:-1]:
        fields = line.split("\t")
        if len(fields) != len(HEADER):
            raise ValueError("invalid OS clock row")
        row = dict(zip(HEADER, fields))
        for key in ("thread", "queue", "caller", "result"):
            if not HEX.fullmatch(row[key]):
                raise ValueError("invalid OS clock hex field")
        for key in ("thread", "queue", "caller"):
            address = int(row[key], 16)
            if not 0x80000000 <= address <= 0x803ffffc or address % 4:
                raise ValueError("invalid guest pointer")
        for key in set(HEADER) - {"thread", "queue", "caller", "result", "kind"}:
            if not row[key].isdecimal() or int(row[key]) > 0xffffffff:
                raise ValueError("invalid OS clock integer")
            row[key] = int(row[key])
        if row["id"] == 0 or row["id"] in ids or row["kind"] not in ("recv", "send") or \
                row["block"] not in (0, 1) or row["output"] not in (0, 1) or \
                not 0 <= row["valid"] <= row["capacity"] or row["capacity"] == 0:
            raise ValueError("invalid OS call identity or queue state")
        ids.add(row["id"])
        rows.append(row)
    return rows, int(footer[3])


def summarize(path):
    rows, unfinished = read(path)
    groups = collections.defaultdict(list)
    excluded = collections.Counter()
    for row in rows:
        would_wait = row["block"] == 1 and (
            row["valid"] == 0 if row["kind"] == "recv" else row["valid"] == row["capacity"])
        # No attempted subtraction of interruption/wait intervals: other
        # threads and device work can overlap, so the total is not CPU cost.
        if would_wait or row["exceptions"] or row["switches"]:
            excluded["wait_or_interrupt_or_context_switch"] += 1
            continue
        key = (row["kind"], row["block"], row["valid"], row["capacity"],
               row["output"], row["result"])
        groups[key].append(row["ticks"])
    return {"kind": "jfg-os-call-clock-observations", "acceptance": False,
            "cost_model_qualified": False, "completed": len(rows), "unfinished": unfinished,
            "excluded": dict(excluded), "uninterrupted_groups": [
                {"kind": key[0], "block": key[1], "valid": key[2], "capacity": key[3],
                 "output": key[4], "result": key[5], "samples": len(values),
                 "distinct_ticks": sorted(set(values))}
                for key, values in sorted(groups.items())]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize(args.trace), indent=2))
