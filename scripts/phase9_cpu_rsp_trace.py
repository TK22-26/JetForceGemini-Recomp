"""Strict direct-SP completion observations; no hardware latency claim."""
from itertools import product

HEADER = "type nops flags load_ticks start_ticks complete_ticks sp_status mi_pending".split()


def parse_trace(path):
    lines = path.read_text().splitlines()
    if len(lines) != 18 or lines[0].split("\t") != HEADER or lines[-1] != "result\ttrue\t16":
        raise ValueError("incomplete RSP microtest")
    rows = []
    for line, expected in zip(lines[1:-1], product((1, 2), (1, 8, 64, 256), (0, 2))):
        fields = line.split("\t")
        if len(fields) != 8 or not all(v.isdecimal() and int(v) <= 0xffffffff for v in fields):
            raise ValueError("malformed RSP observation")
        values = list(map(int, fields))
        if tuple(values[:3]) != expected or not 0 < values[3] or \
                not 0 < values[4] <= values[5] or values[6] & 3 != 3 or values[7] & 1 != 1:
            raise ValueError("RSP task did not complete with halt/broke/SP interrupt")
        rows.append(dict(zip(HEADER, values)))
    return {"cases": rows, "direct_completion_observed": True,
            "hardware_qualified": False, "latency_model_qualified": False}
