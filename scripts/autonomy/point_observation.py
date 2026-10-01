"""Read-only instruction-point measurements, scoped to a qualified call span."""
from scripts import phase9_point_probe
from scripts.autonomy.entry_observation import instruction_evidence
from scripts.compare_phase9_focus_rdram import _records_at, _snapshot


def spans(rows, side, probe, window):
    result = {}
    entry, end = int(probe["entry_pc"],16), int(probe["call_pc"],16)+8
    for update in range(window[0], window[1]+1):
        selected = [row for row in rows if (row["completed_updates"]+1 if side == "oracle" else row["update_candidate"]) == update]
        entries = [i for i,row in enumerate(selected) if row["pc"] == entry]
        ends = [i for i,row in enumerate(selected) if row["pc"] == end]
        if len(entries) != 1 or len(ends) != 1 or entries[0] >= ends[0]:
            raise ValueError(f"{side}-invocation-{update}-missing-or-ambiguous-anchor")
        first, last = selected[entries[0]], selected[ends[0]]
        thread, stack = first["m800a9e90"], first["r29_lo"]
        if (not 0x80000000 <= thread <= 0x803ffffc or thread % 4 or
                not 0x80000000 <= stack <= 0x803ffff8 or stack % 8 or
                first["r31_lo"] != end or last["r31_lo"] != end or
                last["r29_lo"] != stack or last["m800a9e90"] != thread):
            raise ValueError(f"{side}-invocation-{update}-caller-stack-thread-differs")
        own = [row for row in selected[entries[0]:ends[0]+1] if row["m800a9e90"] == thread]
        result[update] = {"thread": thread, "stack": stack, "rows": own, "entry": first, "return": last}
    return result


def capture_evidence(directory, reference, probe, window, *, traces_unchanged):
    pcs, words = [int(x,16) for x in probe["pcs"]], [int(x,16) for x in probe["words"]]
    anchor = {key: probe[key] for key in ("entry_pc", "call_pc")}
    instructions = instruction_evidence(reference, window, anchor)
    if instruction_evidence(directory, window, anchor) != instructions:
        raise ValueError("point anchor instructions changed under instrumentation")
    raw, grouped, reasons = {}, {}, []
    if not traces_unchanged:
        reasons.append("full-update-traces-changed-under-instrumentation")
    opcodes = {}
    for side, trace in (("native", "retrace-hashes.jsonl.updates.jsonl"), ("oracle", "update-hashes.jsonl")):
        raw[side] = phase9_point_probe.read(directory / side / "point-probe.tsv", pcs, words, window, oracle=side == "oracle")
        code = []
        records = _records_at(directory / side / trace, range(window[0], window[1]+1))
        controls = _records_at(reference / side / trace, range(window[0], window[1]+1))
        for update in range(window[0], window[1]+1):
            image,_ = _snapshot(directory / side, records[update])
            control,_ = _snapshot(reference / side, controls[update])
            if image != control:
                reasons.append(f"{side}-focused-rdram-{update}-changed-under-instrumentation")
            code.append({pc:int.from_bytes(image[pc-0x80000000:pc-0x80000000+4],"big") for pc in pcs})
        if any(item != code[0] for item in code) or any(row["opcode"] != code[0][row["pc"]] for row in raw[side]):
            raise ValueError("executed point opcodes differ from retained instructions")
        opcodes[side] = code[0]
        try:
            grouped[side] = spans(raw[side], side, probe, window)
        except ValueError as error:
            reasons.append(str(error))
    if opcodes["native"] != opcodes["oracle"]:
        raise ValueError("native/oracle point instructions differ")
    return raw, grouped, reasons, instructions


def measure(directory, reference, plan, window, *, traces_unchanged):
    probe, prediction = plan["probe"], plan["prediction"]
    pcs = [int(x,16) for x in probe["pcs"]]
    raw, grouped, reasons, instructions = capture_evidence(directory, reference, probe, window, traces_unchanged=traces_unchanged)
    observations = []
    for update in range(window[0], window[1]+1):
        if len(grouped) != 2:
            break
        a,b = grouped["native"][update], grouped["oracle"][update]
        if any(a[key] != b[key] for key in ("thread", "stack")) or any(
                a[key]["controller_polls"] != b[key]["controller_polls"] for key in ("entry", "return")):
            reasons.append(f"invocation-{update}-anchor-correspondence-differs")
        pc = int(prediction["pc"],16)
        points = {side:[row for row in grouped[side][update]["rows"] if row["pc"] == pc] for side in grouped}
        values = {}
        if prediction["kind"] == "event-count":
            values = {side:len(rows) for side,rows in points.items()}
        else:
            index = prediction["occurrence"]-1
            if any(index >= len(rows) for rows in points.values()):
                reasons.append(f"invocation-{update}-predicted-occurrence-missing")
                continue
            # Anchor entry/return are uniquely identified independently of the
            # internal branch path. Other ordinal values need equal hook prefixes.
            if pc not in (int(probe["entry_pc"],16), int(probe["call_pc"],16)+8):
                prefixes = []
                for side in grouped:
                    rows = grouped[side][update]["rows"]
                    stop = next(i for i,row in enumerate(rows) if row is points[side][index])
                    prefixes.append([row["pc"] for row in rows[:stop+1]])
                if prefixes[0] != prefixes[1]:
                    reasons.append(f"invocation-{update}-value-hook-prefixes-differ")
            for side, rows in points.items():
                row = rows[index]
                if prediction["kind"] == "register":
                    reg = prediction["register"]
                    values[side] = f"0x{(row[f'r{reg}_hi']<<32)|row[f'r{reg}_lo']:016x}"
                else:
                    values[side] = f"0x{row['m'+prediction['address'][2:]]:08x}"
        observations.append({"update":update, "pc":prediction["pc"], **values,
            "equal":values["native"] == values["oracle"],
            "event_counts":{f"0x{site:08x}":{side:sum(row["pc"]==site for row in grouped[side][update]["rows"]) for side in grouped} for site in pcs},
            "anchor_clocks":{side:{boundary:{key:row[key] for key in row if key in (
                "frame","completed_updates","update_candidate","controller_polls","vi_retraces","consumed_vi")}
                for boundary,row in (("entry",grouped[side][update]["entry"]),("return",grouped[side][update]["return"]))} for side in grouped}})
    observed = next((row for row in observations if row["update"] == prediction["update"]),None)
    return {"kind":"jfg-point-state-experiment", "schema":1, "plan":plan, "focus_updates":window,
        "observations":observations, "raw_events":raw, "prediction_observation":observed,
        "prediction_observed":observed["equal"] == (prediction["relation"] == "equal") if not reasons and observed else None,
        "qualification":{"passed":not reasons, "reasons":reasons,
                         "scope":"anchored-thread-instruction-points-not-global-alignment", "instruction_evidence":instructions,
                         "full_update_traces_unchanged":traces_unchanged},
        "alignment_validated":False, "causal_fix_proved":False, "parity_verified":False}
