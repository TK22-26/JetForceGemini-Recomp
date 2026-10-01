"""Read independently accounted oracle Count changes and pre-dispatch ERET.

Neither raw Count nor a lazy-update delta is a cross-engine retirement clock.
"""
import collections
import csv
import re

COUNT = ("sequence", "invocation", "reason", "pc", "anchor_before", "anchor_after",
         "count_before", "count_after", "operand", "status", "cause", "thread_word", "device_sequence")
ERET = ("sequence", "invocation", "pc", "target_pc", "count_before", "count_after",
        "anchor_before", "anchor_after", "status_before", "status_after", "epc_before", "epc_after",
        "llbit_before", "llbit_after", "thread_word_before", "thread_word_after", "previous_eret_thread_word",
        "device_sequence") + tuple(f"r{i}" for i in range(32))
REASONS = {"lazy", "idle", "write", "compare-up", "compare-down", "nmi-reset", "hard-reset"}
MAX_ROWS = 524288
MASK = 0xffffffff


def specification(update, device_spec, core):
    if update is None:
        return None
    if (type(update) is not int or not 1 <= update <= 1000000 or type(core) is not int or core != 1 or
            not isinstance(device_spec, dict) or device_spec.get("clock_basis") != "oracle-lazy-count" or
            not device_spec["window"][0] <= update <= device_spec["window"][1]):
        raise ValueError("CPU boundaries require one bounded update and explicit cached-interpreter device capture")
    return {"schema": 1, "update": update, "observation_only": True,
            "count_basis": "original-oracle-count-mutations", "eret_phase": "before-interrupt-dispatch"}


def configure(environment, spec):
    environment.pop("JFG_PHASE9_CPU_BOUNDARY_UPDATE", None)
    if spec is not None:
        environment["JFG_PHASE9_CPU_BOUNDARY_UPDATE"] = str(spec["update"])


def read(path, update):
    if type(update) is not int or not 1 <= update <= 1000000 or path.stat().st_size > 128 * 1024 * 1024:
        raise ValueError("CPU boundary window or byte budget is invalid")
    rows, previous_count, previous_device, previous_eret = [], None, 0, None
    counts = collections.Counter()
    with path.open(encoding="ascii", newline="") as stream:
        reader = csv.reader(stream, delimiter="\t")
        expected = (["jfg-oracle-cpu-boundaries-v1", str(update)], ["count-columns", *COUNT], ["eret-columns", *ERET])
        if any(next(reader, None) != line for line in expected):
            raise ValueError("CPU boundary header differs")
        for values in reader:
            if values and values[0] == "result":
                if values != ["result", "true", str(len(rows)), str(counts["count"]), str(counts["eret"])] or next(reader, None) is not None:
                    raise ValueError("CPU boundary footer or trailing content differs")
                return {"schema": 1, "update": update, "rows": rows,
                        "clock_alignment_validated": False, "retirement_validated": False,
                        "causal_fix_proved": False, "parity_verified": False}
            if not values or values[0] not in ("count", "eret") or len(rows) == MAX_ROWS:
                raise ValueError("CPU boundary row kind or budget differs")
            kind = values[0]; columns = COUNT if kind == "count" else ERET
            if len(values) != len(columns) + 1:
                raise ValueError("CPU boundary row width differs")
            row = dict(zip(columns, values[1:])); row["kind"] = kind
            for key in columns:
                if key == "reason":
                    if row[key] not in REASONS: raise ValueError("unknown Count reason")
                    continue
                decimal = key in ("sequence", "invocation", "device_sequence")
                width = 16 if key.startswith("r") and key[1:].isdigit() else 8
                pattern = r"[0-9]+" if decimal else r"0x[0-9a-f]{" + str(width) + "}"
                if not re.fullmatch(pattern, row[key]): raise ValueError("invalid CPU boundary number")
                row[key] = int(row[key], 10 if decimal else 16)
            if (row["sequence"] != len(rows) + 1 or row["invocation"] != update or
                    not previous_device <= row["device_sequence"] <= 65536 or
                    any(row[key] % 4 for key in ("pc", "anchor_before", "anchor_after"))):
                raise ValueError("CPU boundary ordering or alignment differs")
            previous_device = row["device_sequence"]
            if kind == "count":
                before, operand, reason = row["count_before"], row["operand"], row["reason"]
                expected_count = ((before + ((row["pc"] - row["anchor_before"]) & MASK) // 2) if reason == "lazy" else
                    before + operand if reason in ("idle", "compare-up") else
                    before - operand if reason == "compare-down" else operand) & MASK
                expected_anchor = row["pc"] if reason == "lazy" else row["anchor_before"]
                if ((previous_count is not None and before != previous_count) or row["count_after"] != expected_count or
                        row["anchor_after"] != expected_anchor or (reason == "lazy" and operand != 0) or
                        (reason in ("compare-up", "compare-down") and operand != 2) or
                        (reason == "idle" and (operand == 0 or operand % 4)) or
                        (reason == "nmi-reset" and operand != 0) or (reason == "hard-reset" and operand != 0x5000)):
                    raise ValueError("Count accounting or continuity differs")
                previous_count = row["count_after"]
            else:
                prior = rows[-1] if rows else {}
                if (prior.get("kind") != "count" or prior.get("reason") != "lazy" or
                        any(prior[key] != row[key] for key in ("pc", "count_before", "count_after", "anchor_before")) or
                        row["count_after"] != previous_count or row["status_before"] & 6 != 2 or
                        row["status_after"] != row["status_before"] & ~2 or
                        row["target_pc"] != row["epc_before"] or row["epc_after"] != row["epc_before"] or
                        row["anchor_after"] != row["target_pc"] or row["llbit_after"] != 0 or
                        row["llbit_before"] not in (0, 1) or row["r0"] != 0 or
                        (previous_eret is not None and row["previous_eret_thread_word"] != previous_eret)):
                    raise ValueError("ERET completion or associated Count update differs")
                previous_eret = row["thread_word_after"]
            counts[kind] += 1; rows.append(row)
    raise ValueError("CPU boundary footer is missing")


def summary(path, spec):
    try:
        result = read(path, spec["update"])
        rows = result.pop("rows")
        reasons = collections.Counter(row["reason"] for row in rows if row["kind"] == "count")
        return {**result, "complete": True, "events": len(rows), "error": None,
                "count_reasons": dict(sorted(reasons.items())),
                "eret_events": sum(row["kind"] == "eret" for row in rows)}
    except (OSError, ValueError) as error:
        return {"complete": False, "events": None, "error": str(error)}
