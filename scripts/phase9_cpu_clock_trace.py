"""Validate observations, not hardware accuracy, of the clock micro-ROM."""

def parse_trace(path):
    lines = path.read_text().splitlines()
    names = ["alu100", "alu1000", "cached100", "cached1000", "uncached100", "uncached1000"]
    if len(lines) != 8 or lines[0] != "case\tticks" or lines[-1] != "result\ttrue":
        raise ValueError("incomplete clock microtest")
    ticks = {}
    for line, name in zip(lines[1:-1], names):
        fields = line.split("\t")
        if len(fields) != 2 or fields[0] != name or not fields[1].isdigit():
            raise ValueError("invalid clock observation")
        value = int(fields[1])
        if not 0 < value <= 0xffffffff:
            raise ValueError("clock observation out of range")
        ticks[name] = value
    # Each additional iteration executes four instructions. This is an
    # aggregate slope, not proof of individual instruction latency.
    deltas = {kind: ticks[kind + "1000"] - ticks[kind + "100"]
              for kind in ("alu", "cached", "uncached")}
    if any(delta <= 0 for delta in deltas.values()):
        raise ValueError("non-increasing clock work measurement")
    return {"ticks": ticks, "delta_ticks_per_3600_instructions": deltas,
            "hardware_qualified": False}
