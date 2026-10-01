"""Read bounded engine events; clocks and instruction retirement stay unqualified."""
import csv
import re

BASE = ("sequence", "phase", "source", "invocation", "pc", "opcode", "previous_pc",
        "previous_opcode", "clock_raw", "clock_anchor_pc", "deadline_valid", "deadline",
        "status", "cause", "mi_pending", "mi_mask", "thread")
REGISTERS = tuple(f"r{i}_{part}" for i in range(32) for part in ("lo", "hi"))
PHASES = {"instruction", "successor", "thread-word-change", "dispatch", "state", "accept"}
SOURCES = {"none", "vi", "pi", "si", "compare", "sp", "dp", "ai", "check", "other"}
CLOCKS = {"native": "native-pre-instruction-count", "oracle": "oracle-lazy-count"}
MAX_ROWS = 65536


def specification(enabled, pcs, focus, *, side, qualified_engine):
    if type(enabled) is not bool:
        raise ValueError("device events require a boolean opt-in")
    if not enabled:
        return None
    if side not in CLOCKS or not qualified_engine or not pcs or focus is None or focus[1] >= 1000000:
        raise ValueError("device events require focused points and the explicit observation engine")
    return {"schema": 1, "clock_basis": CLOCKS[side],
            "window": [max(1, focus[0] - 1), focus[1] + 1],
            "pcs": list(pcs), "observation_only": True}


def summary(path, specification, *, side):
    try:
        report = read(path, specification["window"], side=side)
        rows = report.pop("rows")
        return {**report, "complete": True, "events": len(rows),
                "phase_counts": {phase: sum(row["phase"] == phase for row in rows) for phase in sorted(PHASES)},
                "error": None}
    except (OSError, ValueError) as error:
        return {"complete": False, "error": str(error), "events": None}


def read(path, window, *, side):
    if side not in CLOCKS or path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("device-event side or byte budget is invalid")
    first, last = window
    if (type(first) is not int or type(last) is not int or
            not 1 <= first <= last <= 1000000 or last - first > 17):
        raise ValueError("device-event window is invalid")
    lines = path.read_text(encoding="ascii").splitlines()
    if (not 4 <= len(lines) <= MAX_ROWS + 3 or
            lines[0] != f"jfg-phase9-device-events-v1\t{CLOCKS[side]}\t{first}\t{last}" or
            lines[-1] != f"result\ttrue\t{len(lines) - 3}"):
        raise ValueError("device-event header, footer or hit budget is invalid")
    reader = csv.DictReader(lines[1:-1], delimiter="\t")
    if tuple(reader.fieldnames or ()) != BASE + REGISTERS:
        raise ValueError("device-event columns differ")
    rows, previous = [], first
    for sequence, row in enumerate(reader, 1):
        if set(row) != set(BASE + REGISTERS) or any(value is None for value in row.values()):
            raise ValueError("device-event row is incomplete")
        for key in ("sequence", "invocation", "deadline_valid"):
            if not re.fullmatch(r"[0-9]+", row[key]):
                raise ValueError("device-event decimal is invalid")
            row[key] = int(row[key])
        if (row["sequence"] != sequence or not previous <= row["invocation"] <= last or
                row["phase"] not in PHASES or row["source"] not in SOURCES or
                row["deadline_valid"] not in (0, 1)):
            raise ValueError("device-event ordering, phase or source is invalid")
        for key in (*BASE[4:10], *BASE[11:], *REGISTERS):
            if not re.fullmatch(r"0x[0-9a-f]{8}", row[key]):
                raise ValueError("device-event hexadecimal word is invalid")
            row[key] = int(row[key], 16)
        if row["r0_lo"] or row["r0_hi"] or (not row["deadline_valid"] and row["deadline"]):
            raise ValueError("device-event zero register or absent deadline is invalid")
        previous = row["invocation"]
        rows.append(row)
    return {"schema": 1, "side": side, "clock_basis": CLOCKS[side], "window": list(window),
            "rows": rows, "clock_alignment_validated": False,
            "retirement_validated": False, "causal_fix_proved": False, "parity_verified": False}
