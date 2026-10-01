"""Read native ERET transfer boundaries, not globally aligned retirement."""
import csv
import re

BASE = ("sequence", "invocation", "pc", "opcode", "from_thread", "to_thread",
        "target_pc", "status", "count")
REGISTERS = tuple(f"r{i}" for i in range(32))
MAX_ROWS = 65536


def specification(enabled, device_spec):
    if type(enabled) is not bool or (enabled and (not isinstance(device_spec, dict) or
            device_spec.get("clock_basis") != "native-pre-instruction-count")):
        raise ValueError("ERET transfers require a boolean opt-in and native device capture")
    if not enabled:
        return None
    return {"schema": 1, "window": list(device_spec["window"]),
            "phase": "after-cpu-eret-state-before-host-handoff",
            "clock_basis": "native-count-at-eret-transfer", "observation_only": True}


def configure(environment, enabled, device_spec):
    spec = specification(enabled, device_spec)
    environment.pop("JFG_PHASE9_ERET_TRANSFERS", None)
    if enabled:
        environment["JFG_PHASE9_ERET_TRANSFERS"] = "1"
    return spec


def read(path, window):
    first, last = window
    if (type(first) is not int or type(last) is not int or
            not 1 <= first <= last <= 1000000 or last - first > 17 or
            path.stat().st_size > 64 * 1024 * 1024):
        raise ValueError("ERET transfer window or byte budget is invalid")
    lines = path.read_text(encoding="ascii").splitlines()
    if (not 3 <= len(lines) <= MAX_ROWS + 3 or
            lines[0] != f"jfg-native-eret-transfers-v1\t{first}\t{last}" or
            lines[-1] != f"result\ttrue\t{len(lines) - 3}"):
        raise ValueError("ERET transfer header, footer or row budget is invalid")
    reader = csv.DictReader(lines[1:-1], delimiter="\t")
    if tuple(reader.fieldnames or ()) != BASE + REGISTERS:
        raise ValueError("ERET transfer columns differ")
    rows, previous = [], first
    for sequence, row in enumerate(reader, 1):
        if set(row) != set(BASE + REGISTERS) or any(value is None for value in row.values()):
            raise ValueError("ERET transfer row is incomplete")
        for key in BASE[:2]:
            if not re.fullmatch(r"[0-9]+", row[key]):
                raise ValueError("ERET transfer decimal is invalid")
            row[key] = int(row[key])
        for key in BASE[2:] + REGISTERS:
            width = 16 if key in REGISTERS else 8
            if not re.fullmatch(r"0x[0-9a-f]{" + str(width) + "}", row[key]):
                raise ValueError("ERET transfer hexadecimal field is invalid")
            row[key] = int(row[key], 16)
        if (row["sequence"] != sequence or not previous <= row["invocation"] <= last or
                row["opcode"] != 0x42000018 or row["status"] & 6 or row["r0"] or
                not row["to_thread"] or any(row[key] % 4 for key in
                ("pc", "from_thread", "to_thread", "target_pc"))):
            raise ValueError("ERET transfer ordering or boundary is invalid")
        previous = row["invocation"]
        rows.append(row)
    return {"schema": 1, "window": list(window), "rows": rows,
            "clock_alignment_validated": False, "retirement_validated": False,
            "causal_fix_proved": False, "parity_verified": False}


def summary(path, spec):
    try:
        report = read(path, spec["window"])
        rows = report.pop("rows")
        return {**report, "complete": True, "events": len(rows), "error": None,
                "same_thread": sum(row["from_thread"] == row["to_thread"] for row in rows)}
    except (OSError, ValueError) as error:
        return {"complete": False, "events": None, "error": str(error)}
