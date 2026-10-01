"""Discover candidate direct-call anchors from retained, pinned RDRAM only."""
import json
import re
from scripts.compare_phase9_focus_rdram import _records_at, _snapshot


def inventory(reference, window, diagnosis):
    targets = sorted({int(value,16) for value in re.findall(r"0x80[0-3][0-9a-f]{5}\b",json.dumps(diagnosis),re.I)})
    if len(targets) > 64:
        raise ValueError("point anchor target inventory exceeds budget")
    images = []
    for side,trace in (("native","retrace-hashes.jsonl.updates.jsonl"),("oracle","update-hashes.jsonl")):
        records = _records_at(reference/side/trace, range(window[0],window[1]+1))
        for update in range(window[0],window[1]+1):
            image,_ = _snapshot(reference/side,records[update])
            images.append(image)
    candidates = find_candidates(images, targets)
    return {"kind":"retained-direct-jal-nop-candidates","schema":1,"focus_updates":window,
            "candidates":candidates,"scope":"matching-instruction-bytes-not-yet-observed-call-execution",
            "alignment_validated":False,"parity_verified":False}


def find_candidates(images, targets):
    """Find the same direct JAL/NOP candidates without decoding every word.

    Targets are already bounded canonical RDRAM addresses. Search their exact
    big-endian JAL/NOP bytes, then enforce word alignment and compare the call,
    delay slot and entry instruction in *every* supplied image. No persistent
    cache or file-stat shortcut stands in for reading the current evidence.
    """
    first = images[0]
    candidates = []
    for target in targets:
        if target % 4:
            continue  # A JAL target is necessarily word aligned.
        call = 0x0c000000 | ((target & 0x0fffffff) >> 2)
        needle = call.to_bytes(4, "big") + bytes(4)
        entry = target - 0x80000000
        offset = first.find(needle)
        while offset != -1:
            # Preserve the original scanner's strict trailing bound/order.
            if offset >= len(first) - 8:
                break
            if offset % 4 == 0 and all(
                    image[offset:offset + 8] == first[offset:offset + 8] and
                    image[entry:entry + 4] == first[entry:entry + 4] for image in images):
                candidates.append({"entry_pc": f"0x{target:08x}", "call_pc": f"0x{0x80000000 + offset:08x}",
                                   "return_pc": f"0x{0x80000008 + offset:08x}", "call_opcode": f"0x{call:08x}",
                                   "delay_slot": "0x00000000", "entry_opcode": "0x" + first[entry:entry + 4].hex()})
                if len(candidates) > 64:
                    raise ValueError("point anchor candidate inventory exceeds budget")
            offset = first.find(needle, offset + 1)
    return sorted(candidates, key=lambda item: item["call_pc"])


def history_inventory(reference, window, diagnosis, history, calibration, calibration_pin):
    """Carry checked observations forward; never turn prose into call proof.

    The caller must independently validate history and runtime calibration.
    We still rescan *all* retained images: a previously observed call is not
    permission to invent instruction bytes or assume execution in a new span.
    """
    entries = []
    retained = []
    for item in history:
        observation, plan = item["observation"], item["plan"]
        qualified = observation.get("qualification", {}).get("passed") is True
        probe = plan.get("probe")
        if qualified and plan["operation"] in ("entry-gpr", "point-state", "interval-state"):
            entries.append(probe["entry_pc"])
        retained.append({
            "observation_id": item["observation_id"], "source": item["source"],
            "operation": plan["operation"], "probe": probe,
            "prediction": plan["prediction"],
            "prediction_observed": observation["prediction_observed"],
            "qualification": {key: value for key, value in observation.get("qualification", {}).items()
                              if key in ("passed", "scope", "reasons", "full_update_traces_unchanged")},
            "input_prefix_match": item["input_prefix_match"],
            "measurements": [{key: value for key, value in row.items() if key in (
                "update", "label", "address", "width", "pc", "register", "native", "oracle",
                       "equal", "clocks", "anchor_clocks")} for row in observation["observations"]]})
        if plan["operation"] == "device-events":
            # The full ordered events remain in the pinned observation. Do not
            # accidentally inline all raw event rows into the next point prompt.
            retained[-1]["measurements"] = [{"update": row["update"], **{
                side: {"phase_source_counts": row[side]["phase_source_counts"],
                       "first_sequence_exclusive": row[side]["first_sequence_exclusive"],
                       "last_sequence_exclusive": row[side]["last_sequence_exclusive"]}
                for side in ("native", "oracle")}} for row in observation["observations"]]
            retained[-1]["device_limits"] = {key: observation[key] for key in
                ("clock_alignment_validated", "retirement_validated", "completed_queue_operations_proved")}
        if plan["operation"] == "oracle-count-ledger":
            from scripts.phase9_oracle_count_ledger import project_observations
            retained[-1]["measurements"] = project_observations(observation["observations"])
    if calibration.get("qualification", {}).get("passed") is not True:
        raise ValueError("point planner calibration is not qualified")
    facts = inventory(reference, window, {"diagnosis": diagnosis, "qualified_prior_entries": entries})
    facts.update(schema=2, prior_observations=retained, runtime_calibration={
        "source": calibration_pin, "qualification": calibration["qualification"],
        "measurements": {side: [{key: value for key, value in row.items() if key in (
            "update", "thread", "entry_sp", "entry_poll", "return_poll", "entry_a0",
            "queue_valid_at_entry", "entry_policy", "counted_receives", "return_v0")}
            for row in rows] for side, rows in calibration["summaries"].items()},
        "alignment_validated": False, "causal_fix_proved": False, "parity_verified": False})
    return facts


def adds_candidates(previous, current):
    """A prose/context refresh alone must not spend another model attempt."""
    def pairs(facts):
        return {(row["entry_pc"], row["call_pc"]) for row in facts["candidates"]}
    return bool(pairs(current) - pairs(previous))
