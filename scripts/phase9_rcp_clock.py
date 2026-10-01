"""Validate paired read-only CPU/RCP observations, not a device cost model."""
from collections import Counter
from pathlib import Path
import re

HEADER = "event update count status mi_pending mi_mask sp_status dp_status vi_line".split()
HEX = re.compile(r"0x[0-9a-f]{8}\Z")


def summarize(path, queue_clock):
    lines = Path(path).read_text().splitlines()
    clock = Path(queue_clock).read_text().splitlines()
    if not 3 <= len(lines) <= 8194 or lines[0].split("\t") != HEADER or \
            lines[-1] != f"result\ttrue\t{len(lines) - 2}" or len(clock) != len(lines) or \
            clock[0] != "event\tframe\tupdate\tpoll\tvi\tcount\tepc\tcause" or clock[-1] != lines[-1]:
        raise ValueError("incomplete or unpaired RCP clock observations")
    exceptions = Counter()
    for line, cpu in zip(lines[1:-1], clock[1:-1]):
        fields, observed = line.split("\t"), cpu.split("\t")
        if len(fields) != len(HEADER) or len(observed) != 8 or \
                fields[:3] != [observed[0], observed[2], observed[5]] or \
                not fields[1].isdecimal() or not all(HEX.fullmatch(v) for v in fields[2:]):
            raise ValueError("RCP clock row malformed or reordered")
        values = dict(zip(HEADER[2:], map(lambda value: int(value, 16), fields[2:])))
        if values["mi_pending"] > 63 or values["mi_mask"] > 63 or values["sp_status"] > 0x7fff:
            raise ValueError("invalid RCP register readback")
        if fields[0] == "exception":
            if not values["status"] & 2:
                raise ValueError("exception observation without EXL")
            exceptions[f"0x{values['mi_pending']:02x}"] += 1
    return {"rows": len(lines) - 2, "exception_pending_masks": dict(sorted(exceptions.items())),
            "latency_model_qualified": False, "hardware_qualified": False}
