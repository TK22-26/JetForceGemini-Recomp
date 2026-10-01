"""Qualify paired direct-call observations without moving update comparisons."""
import csv
import re

from scripts.compare_phase9_focus_rdram import _records_at, _snapshot

WORD = re.compile(r"0x[0-9a-fA-F]{1,8}\Z")


def table(path, *, oracle, gpr):
    if path.stat().st_size > 2_097_152:
        raise ValueError("entry trace exceeds bounded size")
    lines = path.read_text(encoding="utf-8").splitlines()
    if oracle:
        if len(lines) < 3 or lines[-1] != f"result\ttrue\t{len(lines) - 2}":
            raise ValueError("oracle entry trace has no complete footer")
        lines = lines[:-1]
    if not 2 <= len(lines) <= 1025:
        raise ValueError("entry trace has no calls or exceeded its hit budget")
    prefix = ("frame", "completed_updates", "controller_polls", "consumed_vi", "pc") if oracle else (
        "update_candidate", "vi_retraces", "controller_polls", "target")
    fields = tuple(f"r{i}_{part}" for i in range(32) for part in ("lo", "hi")) if gpr else (
        "a0", "a1", "a2", "a3")
    reader = csv.DictReader(lines, delimiter="\t")
    if tuple(reader.fieldnames or ()) != prefix + fields:
        raise ValueError("entry trace header differs from the qualified hook")
    result = []
    for row in reader:
        if set(row) != set(prefix + fields) or any(value is None for value in row.values()):
            raise ValueError("entry trace row is incomplete")
        for key in prefix[:-1]:
            if not re.fullmatch(r"[0-9]+", row[key]):
                raise ValueError("entry trace clock is not a nonnegative counter")
            row[key] = int(row[key])
        for key in (prefix[-1], *fields):
            if not WORD.fullmatch(row[key]):
                raise ValueError("entry trace register is not a 32-bit word")
            row[key] = int(row[key], 16)
        result.append(row)
    return result


def calls(directory, side, pc, window):
    oracle = side == "oracle"
    args = table(directory / side / "entry-args.tsv", oracle=oracle, gpr=False)
    gprs = table(directory / side / "entry-gpr.tsv", oracle=oracle, gpr=True)
    if len(args) != len(gprs):
        raise ValueError("entry argument/register call counts disagree")
    rows = []
    previous = 0
    for arguments, registers in zip(args, gprs):
        metadata = {key: value for key, value in arguments.items() if key not in ("a0", "a1", "a2", "a3")}
        if any(registers[key] != value for key, value in metadata.items()) or any(
                arguments[f"a{i}"] != registers[f"r{i+4}_lo"] for i in range(4)):
            raise ValueError("entry argument and GPR hooks captured different calls")
        invocation = registers["completed_updates"] + 1 if oracle else registers["update_candidate"]
        if (registers["pc" if oracle else "target"] != pc or invocation < previous or
                not max(1, window[0] - 1) <= invocation <= window[1] + 1):
            raise ValueError("entry trace escaped its target/window or changed call order")
        previous = invocation
        rows.append({"invocation_update": invocation, "raw_clocks": metadata,
                     "gpr": [f"0x{(registers[f'r{i}_hi'] << 32) | registers[f'r{i}_lo']:016x}"
                             for i in range(32)]})
    return rows


def instruction_evidence(directory, window, probe):
    pc, call_pc = int(probe["entry_pc"], 16), int(probe["call_pc"], 16)
    rows = []
    traces = (("native", "retrace-hashes.jsonl.updates.jsonl"), ("oracle", "update-hashes.jsonl"))
    records = {side: _records_at(directory / side / trace, range(window[0], window[1] + 1))
               for side, trace in traces}
    for update in range(window[0], window[1] + 1):
        opcodes = {}
        for side, trace in traces:
            record = records[side][update]
            image, _ = _snapshot(directory / side, record)
            offset = call_pc - 0x80000000
            call = int.from_bytes(image[offset:offset + 4], "big")
            slot = int.from_bytes(image[offset + 4:offset + 8], "big")
            target = ((call_pc + 4) & 0xf0000000) | ((call & 0x3ffffff) << 2)
            if call >> 26 != 3 or target != pc or slot != 0:
                raise ValueError("entry qualification requires a matching direct JAL and NOP slot")
            opcodes[side] = {"call": f"0x{call:08x}", "delay_slot": f"0x{slot:08x}",
                             "entry": image[pc - 0x80000000:pc - 0x80000000 + 4].hex()}
        if opcodes["native"] != opcodes["oracle"]:
            raise ValueError("entry instruction bytes differ across retained snapshots")
        rows.append({"update": update, **opcodes})
    return rows


def measure(directory, plan, window, *, traces_unchanged, instructions):
    pc = int(plan["probe"]["entry_pc"], 16)
    return_pc = int(plan["probe"]["call_pc"], 16) + 8
    raw = {side: calls(directory, side, pc, window) for side in ("native", "oracle")}
    reasons, rows = [], []
    if not traces_unchanged:
        reasons.append("full-update-traces-changed-under-instrumentation")
    for update in range(window[0], window[1] + 1):
        selected = {side: [row for row in raw[side] if row["invocation_update"] == update] for side in raw}
        if any(len(value) != 1 for value in selected.values()):
            reasons.append(f"invocation-{update}-requires-one-corresponding-call-per-side")
            continue
        native, oracle = selected["native"][0], selected["oracle"][0]
        if any(int(row["gpr"][31], 16) & 0xffffffff != return_pc for row in (native, oracle)):
            reasons.append(f"invocation-{update}-return-address-does-not-identify-callsite")
        if native["raw_clocks"]["controller_polls"] != oracle["raw_clocks"]["controller_polls"]:
            reasons.append(f"invocation-{update}-delivered-poll-position-differs")
        register = plan["prediction"]["register"]
        rows.append({"update": update, "register": register,
                     "native": native["gpr"][register], "oracle": oracle["gpr"][register],
                     "equal": native["gpr"][register] == oracle["gpr"][register],
                     "differing_registers": [index for index in range(32) if native["gpr"][index] != oracle["gpr"][index]],
                     "clocks": {"native": native["raw_clocks"], "oracle": oracle["raw_clocks"]}})
    prediction = plan["prediction"]
    observed = next((row for row in rows if row["update"] == prediction["update"]), None)
    return {"kind": "jfg-entry-gpr-experiment", "schema": 1, "plan": plan,
            "focus_updates": window, "observations": rows, "raw_calls": raw,
            "qualification": {"passed": not reasons, "reasons": reasons,
                              "scope": "direct-jal-nop-callsite-entry-not-global-alignment",
                              "full_update_traces_unchanged": traces_unchanged,
                              "instruction_evidence": instructions},
            "prediction_observation": observed,
            "prediction_observed": observed["equal"] == (prediction["relation"] == "equal") if not reasons and observed else None,
            "alignment_validated": False, "causal_fix_proved": False, "parity_verified": False}
