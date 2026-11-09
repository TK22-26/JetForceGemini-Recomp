"""Validate private original-OS queue probe semantics and retain raw timings."""

# Support direct execution from any working directory after domain organization.
if __package__ in (None, ""):
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))
    __package__ = "scripts"


def parse_trace(path):
    lines = path.read_text().splitlines()
    names = ["leaf", "empty_recv", "send", "recv_output", "refill", "full_send", "recv_discard"]
    expected_results = [0, 0xffffffff, 0, 0, 0, 0xffffffff, 0]
    expected_valid = [0, 0, 1, 0, 1, 1, 0]
    if len(lines) != 9 or lines[0] != "case\tticks\tresult\tvalid" or \
            lines[-1] != "result\ttrue\t1234":
        raise ValueError("incomplete or incorrect queue microtest")
    ticks = {}
    for line, name, result, valid in zip(lines[1:-1], names, expected_results, expected_valid):
        fields = line.split("\t")
        if len(fields) != 4 or fields[0] != name or fields[2] != f"0x{result:08x}" or \
                fields[3] != str(valid) or not fields[1].isdecimal() or \
                not 0 < int(fields[1]) <= 0xffffffff:
            raise ValueError("queue microtest semantics or timing malformed")
        ticks[name] = int(fields[1])
    return {"ticks_including_measurement_boundary": ticks, "queue_semantics_pass": True,
            "hardware_qualified": False, "covers_blocking_or_wakeup": False}
