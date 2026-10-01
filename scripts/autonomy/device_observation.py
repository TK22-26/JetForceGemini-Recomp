"""Qualify raw device ordering without inventing a common Count/retirement clock."""
from collections import Counter
import json
from pathlib import Path

from scripts import phase9_device_events as events, phase9_point_probe as points
from scripts.autonomy import point_interval_observation as intervals
from scripts.autonomy.point_plan import validate_probe
from scripts.compare_phase9_focus_rdram import _records_at, _snapshot
from scripts.phase95_bridge import digest
from scripts.phase95_poll_compare import compare as compare_polls

TRACES = {"native": "retrace-hashes.jsonl.updates.jsonl", "oracle": "update-hashes.jsonl"}
LIMITS = {"alignment_validated": False, "clock_alignment_validated": False,
          "retirement_validated": False, "completed_queue_operations_proved": False,
          "causal_fix_proved": False, "parity_verified": False}


def bind_instructions(event_rows, point_rows, side):
    """Exact per-engine correspondence; no ordinal shifts or address aliases."""
    instructions = [row for row in event_rows if row["phase"] == "instruction"]
    if not instructions or len(instructions) != len(point_rows):
        raise ValueError("device instruction/point hit counts differ")
    bound = []
    for event, point in zip(instructions, point_rows):
        invocation = point["completed_updates"] + 1 if side == "oracle" else point["update_candidate"]
        if (any(event[key] != point[key] for key in ("pc", "opcode", *events.REGISTERS)) or
                event["invocation"] != invocation or event["thread"] != point["m800a9e90"]):
            raise ValueError("device instruction/point raw context differs")
        bound.append({**point, "device_sequence": event["sequence"]})
    return bound


def qualify_side(directory, reference, probe, window, side):
    """Re-read manifests, raw streams and full snapshots on every invocation."""
    paths = [directory / f"{side}-result.json", reference / f"{side}-result.json",
             directory / TRACES[side], reference / TRACES[side],
             directory / "point-probe.tsv", directory / "device-events.tsv"]
    paths += [base / f"focus-update-{u}.rdram" for base in (directory, reference)
              for u in range(window[0], window[1] + 1)]
    before = {str(path.resolve()): digest(path) for path in paths}
    metadata, control = [json.loads(path.read_text()) for path in paths[:2]]
    keys = ["source_export", "input_sha256", "rom_sha256", "focused_update_range"]
    keys += (["execution_profile", "target_retraces", "initial_flash_sha256", "initial_pak_sha256"]
             if side == "native" else ["emulator_sha256", "config_sha256", "target_frame", "oracle_initial_flash_sha256"])
    if any(metadata.get(key) is None or metadata.get(key) != control.get(key) for key in keys):
        raise ValueError("device capture changed input/save/profile/window/target")
    for item in (metadata, control):
        if (item.get("exit_code") != 0 or item.get("completed_update_trace_complete") is not True or
                item.get("focused_update_capture_complete") is not True or
                item.get("probe_target_reached" if side == "native" else "trace_complete") is not True or
                any(value is False for key, value in item.items() if key.endswith("_trace_complete"))):
            raise ValueError("device capture or reference did not complete its declared contract")
    if (metadata["focused_update_range"] != list(window) or
            (side == "native" and metadata["execution_profile"] != "original-os-probe") or
            (side == "oracle" and (metadata.get("mupen_cpu_core_override") not in (0, 1) or
                                   metadata.get("preferred_n64_core_override") is not None))):
        raise ValueError("device capture engine/window is unqualified")
    pcs, words = ([int(value, 16) for value in probe[key]] for key in ("pcs", "words"))
    point = metadata.get("point_probe", {})
    declaration = metadata.get("device_events", {})
    spec = events.specification(True, pcs, window, side=side, qualified_engine=True)
    if (point.get("pcs") != pcs or point.get("words") != words or point.get("phase") != points.PHASE or
            point.get("complete") is not True or point.get("sha256") != digest(paths[4]) or
            declaration.get("complete") is not True or declaration.get("sha256") != digest(paths[5]) or
            any(declaration.get(key) != value for key, value in spec.items()) or
            any(declaration.get(key) is not False for key in
                ("clock_alignment_validated", "retirement_validated", "causal_fix_proved", "parity_verified"))):
        raise ValueError("device/point declarations or digests differ")
    event_rows = events.read(paths[5], spec["window"], side=side)["rows"]
    point_rows = points.read(paths[4], pcs, words, window, oracle=side == "oracle")
    raw = bind_instructions(event_rows, point_rows, side)
    if (point.get("events") != len(point_rows) or declaration.get("events") != len(event_rows) or
            declaration.get("phase_counts") != {phase: sum(r["phase"] == phase for r in event_rows)
                                                 for phase in sorted(events.PHASES)}):
        raise ValueError("device/point declared counts differ")
    if digest(paths[2]) != digest(paths[3]):
        raise ValueError("full update trace changed under device instrumentation")
    records = _records_at(paths[2], range(window[0], window[1] + 1))
    controls = _records_at(paths[3], range(window[0], window[1] + 1))
    opcodes, snapshots = None, []
    call = int(probe["call_pc"], 16) - 0x80000000
    expected_call = (0x0c000000 | ((int(probe["entry_pc"], 16) & 0x0fffffff) >> 2)).to_bytes(4, "big") + bytes(4)
    for update in records:
        memory, sha = _snapshot(directory, records[update])
        original, _ = _snapshot(reference, controls[update])
        if memory != original:
            raise ValueError("full focused RDRAM changed under device instrumentation")
        if memory[call:call + 8] != expected_call:
            raise ValueError("device call anchor is not the retained direct JAL/NOP")
        code = {pc: int.from_bytes(memory[pc - 0x80000000:pc - 0x80000000 + 4], "big") for pc in pcs}
        if opcodes is not None and code != opcodes:
            raise ValueError("device point instructions changed across snapshots")
        opcodes = code
        snapshots.append({"update": update, "sha256": sha})
    if any(row["opcode"] != opcodes[row["pc"]] for row in point_rows):
        raise ValueError("device point instruction differs from retained opcode")
    if before != {str(path.resolve()): digest(path) for path in paths}:
        raise ValueError("device evidence changed while being read")
    return raw, event_rows, {"files": before, "snapshots": snapshots,
        "instructions": len(raw), "events": len(event_rows), "opcodes": opcodes}


def summarize_intervals(raw, event_rows, probe, window, selection, occurrence):
    if type(occurrence) is not int or not 1 <= occurrence <= 4096:
        raise ValueError("device interval requires a bounded selected occurrence")
    if ({side: bind_instructions(event_rows[side], rows, side) for side, rows in raw.items()} != raw):
        raise ValueError("device interval instruction binding changed")
    measured = intervals.measure(raw, probe, window, selection)
    output = []
    context_keys = ("pc", "m800a9e90", "r29_lo", "r29_hi", "r31_lo", "r31_hi", "controller_polls")
    for observation in measured["observations"]:
        prefixes = [observation["selected_events"][side][:occurrence] for side in TRACES]
        contexts = [[tuple(row[key] for key in context_keys) for row in rows] for rows in prefixes]
        if (any(len(rows) != occurrence for rows in prefixes) or
                contexts[0] != contexts[1]):
            raise ValueError("device selected raw caller/thread/input prefixes do not correspond")
        # Low-word call qualification alone must not alias two raw 64-bit links.
        for boundary in ("previous_return", "next_entry"):
            a, b = (observation["boundaries"][side][boundary] for side in TRACES)
            if any(a[k] != b[k] for k in context_keys):
                raise ValueError("device interval raw anchor contexts differ")
        sides = {}
        for side in TRACES:
            start = observation["selected_events"][side][occurrence - 1]
            end = observation["boundaries"][side]["next_entry"]
            first, last = start["device_sequence"], end["device_sequence"]
            if first >= last:
                raise ValueError("device selected boundary order is invalid")
            rows = event_rows[side][first:last - 1]  # strictly after start, before entry
            # Full raw GPR data remain in the pinned TSV. This projection never
            # labels an entry/successor as a retired instruction or completed call.
            fields = events.BASE[:17]
            sides[side] = {"first_sequence_exclusive": first, "last_sequence_exclusive": last,
                "start_context": start, "end_context": end,
                "phase_source_counts": dict(sorted(Counter(r["phase"] + ":" + r["source"] for r in rows).items())),
                "events": [{key: row[key] for key in fields} for row in rows]}
        output.append({"update": observation["update"], **sides,
                       "scope": "raw-local-events-after-selected-hook-before-next-entry"})
    return output


def measure(native, oracle, reference_native, reference_oracle, probe, window,
            selection, occurrence, *, input_report_path):
    validate_probe(probe)
    raw, event_rows, evidence = {}, {}, {}
    for side, directory, control in (("native", native, reference_native), ("oracle", oracle, reference_oracle)):
        raw[side], event_rows[side], evidence[side] = qualify_side(directory, control, probe, window, side)
    if evidence["native"]["opcodes"] != evidence["oracle"]["opcodes"]:
        raise ValueError("native/oracle device point opcodes differ")
    native_metadata = json.loads((native / "native-result.json").read_text())
    source = Path(native_metadata["source_export"])
    input_files = [source / name for name in ("controller.input", "export-manifest.json", "initial.flash", "initial.pak")]
    input_files += [native / "controller-polls.tsv", oracle / "checkpoints.tsv"]
    input_pins = {str(path.resolve()): digest(path) for path in input_files}
    inputs = compare_polls(Path(native_metadata["source_export"]), oracle, native, input_report_path,
                          prefix_polls=native_metadata["observed_controller_polls"])
    if inputs["first_input_mismatch"] is not None:
        raise ValueError("device delivered input prefix differs")
    observations = summarize_intervals(raw, event_rows, probe, window, selection, occurrence)
    # Re-pin all evidence, including the input report's backing files, after measurement.
    for side in TRACES:
        if any(digest(Path(path)) != sha for path, sha in evidence[side]["files"].items()):
            raise ValueError("device evidence changed during interval measurement")
    if input_pins != {str(path.resolve()): digest(path) for path in input_files}:
        raise ValueError("device input evidence changed during measurement")
    return {"kind": "jfg-device-event-observation", "schema": 1, "focus_updates": list(window),
        "observations": observations, "evidence": evidence, "input_evidence": input_pins,
        "input_prefix": {"polls": inputs["shared_prefix_polls"], "first_input_mismatch": None,
                         "initial_state": inputs["initial_state"]},
        "qualification": {"passed": True, "reasons": [], "full_update_traces_unchanged": True,
            "scope": "nonperturbing-raw-local-order-with-point-boundaries-not-common-clock-or-retirement"},
        "prediction_observation": None, "prediction_observed": None, **LIMITS}
