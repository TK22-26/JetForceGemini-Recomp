"""Bounded pre-instruction GPR/RDRAM observation; not an alignment oracle."""
import csv
import re

PHASE = "before-instruction-after-native-exception-resumption-no-count-comparison"


def validate(pcs, words, focus, enabled):
    for values in (pcs, words):
        if (not isinstance(values, (list, tuple)) or len(values) > 16 or
                any(type(value) is not int or not 0x80000000 <= value <= 0x803ffffc or value % 4
                    for value in values) or len(set(values)) != len(values)):
            raise ValueError("point probe needs <=16 unique aligned KSEG0 PCs/words")
    if (words and not pcs) or (pcs and (focus is None or not enabled)):
        raise ValueError("point probe requires focused updates and qualified execution hooks")
    return tuple(pcs), tuple(words)


def specification(values):
    return ",".join(f"0x{value:08x}" for value in values)


def read(path, pcs, words, focus, *, oracle):
    if path.stat().st_size > 8_388_608:
        raise ValueError("point probe exceeds trace byte budget")
    lines = path.read_text(encoding="utf-8").splitlines()
    if oracle:
        if not lines or lines[-1] != f"result\ttrue\t{len(lines) - 2}":
            raise ValueError("point probe lacks complete oracle footer")
        lines = lines[:-1]
    if not 2 <= len(lines) <= 4097:
        raise ValueError("point probe has no events or exceeded hit budget")
    clocks = ("frame", "completed_updates", "controller_polls", "consumed_vi") if oracle else (
        "update_candidate", "vi_retraces", "controller_polls")
    values = ("pc", "opcode", *(f"r{i}_{part}" for i in range(32) for part in ("lo", "hi")),
              *(f"m{word:08x}" for word in words))
    reader = csv.DictReader(lines, delimiter="\t")
    if tuple(reader.fieldnames or ()) != clocks + values:
        raise ValueError("point probe header differs")
    rows, previous = [], {key: 0 for key in clocks}
    for row in reader:
        if set(row) != set(clocks + values) or any(value is None for value in row.values()):
            raise ValueError("point probe row is incomplete")
        for key in clocks:
            if not re.fullmatch(r"[0-9]+", row[key]):
                raise ValueError("point probe clock is invalid")
            row[key] = int(row[key])
            if row[key] < previous[key]:
                raise ValueError("point probe clock moved backwards")
        previous = {key: row[key] for key in clocks}
        for key in values:
            if not re.fullmatch(r"0x[0-9a-fA-F]{8}", row[key]):
                raise ValueError("point probe word is invalid")
            row[key] = int(row[key], 16)
        invocation = row["completed_updates"] + 1 if oracle else row["update_candidate"]
        if (row["pc"] not in pcs or not max(1, focus[0] - 1) <= invocation <= focus[1] + 1 or
                row["r0_lo"] != 0 or row["r0_hi"] != 0):
            raise ValueError("point probe escaped target/window or has invalid zero register")
        rows.append(row)
    return rows


def summary(path, pcs, words, focus, *, oracle):
    try:
        rows = read(path, pcs, words, focus, oracle=oracle)
        return {"complete": True, "events": len(rows), "error": None}
    except (OSError, ValueError) as error:
        return {"complete": False, "events": None, "error": str(error)}
