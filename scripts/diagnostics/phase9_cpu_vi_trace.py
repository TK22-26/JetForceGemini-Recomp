"""Strict direct-VI observations. Retain measured intervals without fitting."""

# Support direct execution from any working directory after domain organization.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
    __package__ = "scripts"

from itertools import product


def parse_trace(path):
    lines = path.read_text().splitlines()
    if len(lines) not in (62, 386) or lines[0] != "v_sync\th_sync\tsample\tticks" or \
            lines[-1] != f"result\ttrue\t{len(lines) - 2}":
        raise ValueError("incomplete VI microtest")
    samples = (len(lines) - 2) // 12
    rows = []
    for line, expected in zip(lines[1:-1], product((261, 262, 525, 526, 624, 625), (3093, 3177), range(samples))):
        fields = line.split("\t")
        if len(fields) != 4 or not all(v.isdecimal() and int(v) <= 0xffffffff for v in fields):
            raise ValueError("malformed VI interval")
        values = list(map(int, fields))
        if tuple(values[:3]) != expected or not 0 < values[3] < 10000000:
            raise ValueError("invalid VI interval or reordered case")
        rows.append(dict(zip(("v_sync", "h_sync", "sample", "ticks"), values)))
    return {"cases": rows, "direct_vi_intervals_observed": True,
            "hardware_qualified": False, "period_model_qualified": False}
