"""Describe the US pacing producer's counted receives, without inferring a fix.

The instruction-point capture is general. This analyzer is deliberately specific
to the inspected producer ABI, callsites and queue; it fails on ambiguous calls.
"""
import argparse
import hashlib
import json
from pathlib import Path

from scripts import phase9_point_probe as probe
from scripts.compare_phase9_focus_rdram import _records_at, _snapshot
from scripts.phase95_bridge import digest
from scripts.phase95_poll_compare import compare as compare_polls

PCS = (0x80054fbc, 0x8005502c, 0x80055034, 0x80055054, 0x8005505c,
       0x80055074, 0x800550f8, 0x80055110, 0x8005511c, 0x80055124,
       0x80055144, 0x80055154, 0x8005515c, 0x800457bc, 0x80096910, 0x80096f20)
WORDS = (0x800a9e90, 0x800feca8, 0x800fecac, 0x800feccc,
         0x800feb80, 0x800feb84, 0x800feb88, 0x800feb8c, 0x800feb90, 0x800feb94)
RETURNS = {0x80055034: "drain", 0x8005505c: "drain", 0x80055124: "minimum-wait",
           0x8005515c: "final-wait-not-counted"}
TRACE = {"native": "retrace-hashes.jsonl.updates.jsonl", "oracle": "update-hashes.jsonl"}


def summarize(rows, *, oracle, window):
    summaries = []
    for update in range(window[0], window[1] + 1):
        events = [row for row in rows if (row["completed_updates"] + 1 if oracle else row["update_candidate"]) == update]
        entries = [row for row in events if row["pc"] == 0x80054fbc]
        exits = [row for row in events if row["pc"] == 0x800457bc]
        if len(entries) != 1 or len(exits) != 1:
            raise ValueError(f"update {update}: producer entry/return is missing or ambiguous")
        entry, end = entries[0], exits[0]
        thread, sp = entry["m800a9e90"], entry["r29_lo"]
        if (entry["r31_lo"] != 0x800457bc or end["m800a9e90"] != thread or
                end["r29_lo"] != sp or end["r31_lo"] != 0x800457bc or
                not 0x80000000 <= thread <= 0x803ffffc or thread % 4 or
                not 0x80000030 <= sp <= 0x803ffffc or sp % 8):
            raise ValueError(f"update {update}: producer caller/thread/stack is unqualified")
        start_index, end_index = events.index(entry), events.index(end)
        if end_index <= start_index:
            raise ValueError("producer returned before its entry")
        body = [row for row in events[start_index + 1:end_index] if row["m800a9e90"] == thread]
        pending, receives, policy, saved_count = None, [], [], []
        for row in body:
            pc = row["pc"]
            if pc == 0x80096910:
                if row["r4_lo"] != 0x800feb80 or row["r31_lo"] not in RETURNS or pending is not None:
                    raise ValueError("unexpected/overlapping producer receive")
                if row["r29_lo"] != sp - 0x30 or row["r5_lo"] != 0:
                    raise ValueError("producer receive stack/output argument differs")
                pending = row
            elif pc in RETURNS:
                if pending is None or pending["r31_lo"] != pc or row["r29_lo"] != sp - 0x30 or row["r31_lo"] != pc:
                    raise ValueError("receive return lacks a thread/stack-matched call")
                kind = RETURNS[pc]
                mode = 0 if kind == "drain" else 1
                if pending["r6_lo"] != mode or row["r2_lo"] not in (0, 0xffffffff) or (mode and row["r2_lo"] != 0):
                    raise ValueError("receive mode/result is outside the inspected path")
                receives.append({"kind": kind, "return_pc": f"0x{pc:08x}", "mode": mode,
                                 "success": row["r2_lo"] == 0, "s0_before_increment": row["r16_lo"],
                                 "queue_valid_before": pending["m800feb88"], "queue_valid_after": row["m800feb88"],
                                 "queue_first_before": pending["m800feb8c"], "queue_first_after": row["m800feb8c"]})
                pending = None
            elif pc in (0x80055074, 0x800550f8, 0x80055110):
                policy.append({"pc": f"0x{pc:08x}", "s0": row["r16_lo"], "v1": row["r3_lo"],
                               "at": row["r1_lo"], "t6": row["r14_lo"], "t8": row["r24_lo"], "t9": row["r25_lo"],
                               "bytes_feca8": f"0x{row['m800feca8']:08x}", "bytes_fecac": f"0x{row['m800fecac']:08x}",
                               "word_feccc": row["m800feccc"]})
            elif pc == 0x80055144:
                saved_count.append(row["r3_lo"])
        if pending or len(saved_count) != 1 or not receives or receives[-1]["kind"] != "final-wait-not-counted" or sum(
                row["kind"] == "final-wait-not-counted" for row in receives) != 1:
            raise ValueError("producer observation has unfinished calls or a missing final wait/count save")
        if [item["pc"] for item in policy] != ["0x80055074", "0x800550f8", "0x80055110"]:
            raise ValueError("producer policy branch observations are missing or ambiguous")
        count, drained = 1, False
        for index, receive in enumerate(receives):
            if receive["s0_before_increment"] != count:
                raise ValueError("receive return S0 does not follow observed increments")
            if receive["kind"] == "drain":
                expected_pc = "0x80055034" if index == 0 else "0x8005505c"
                if drained or receive["return_pc"] != expected_pc:
                    raise ValueError("drain call sequence differs from the inspected path")
                drained = not receive["success"]
            elif not drained:
                raise ValueError("minimum/final wait preceded drain exhaustion")
            if receive["success"] and receive["kind"] != "final-wait-not-counted":
                count = (count + 1) & 255
        counted = sum(row["success"] and row["kind"] != "final-wait-not-counted" for row in receives)
        if saved_count[0] != ((1 + counted) & 255) or end["r2_lo"] != saved_count[0]:
            raise ValueError("observed producer result does not follow the inspected counted-receive path")
        summaries.append({"update": update, "thread": f"0x{thread:08x}", "entry_sp": f"0x{sp:08x}",
                          "entry_poll": entry["controller_polls"], "return_poll": end["controller_polls"],
                          "entry_a0": entry["r4_lo"], "queue_valid_at_entry": entry["m800feb88"],
                          "entry_policy": [entry[f"m{word:08x}"] for word in WORDS[1:4]],
                          "counted_receives": counted, "return_v0": end["r2_lo"],
                          "receives": receives, "policy_points": policy})
    return summaries


def compare(native, oracle, reference_native, reference_oracle, *, input_report_path, window=(1907, 1910)):
    if input_report_path.exists():
        raise FileExistsError(input_report_path)
    sides = {"native": (native, reference_native), "oracle": (oracle, reference_oracle)}
    result = {"kind": "jfg-point-pacing-observation", "schema": 1, "focus_updates": list(window),
              "phase": probe.PHASE, "alignment_validated": False, "causal_fix_proved": False, "parity_verified": False,
              "qualification": {"passed": False, "reasons": []}, "summaries": {}, "evidence": {}}
    code, trace_pins = {}, {}
    for side, (directory, reference) in sides.items():
        metadata = json.loads((directory / ("native-result.json" if side == "native" else "oracle-result.json")).read_text())
        reference_metadata = json.loads((reference / ("native-result.json" if side == "native" else "oracle-result.json")).read_text())
        pin_keys = ["source_export", "input_sha256", "rom_sha256"]
        pin_keys += (["execution_profile", "target_retraces", "initial_flash_sha256", "initial_pak_sha256"]
                     if side == "native" else ["emulator_sha256", "config_sha256", "runtime_sha256", "target_frame", "oracle_initial_flash_sha256"])
        if any(metadata.get(key) is None or metadata.get(key) != reference_metadata.get(key) for key in pin_keys):
            raise ValueError("capture input/save/profile/target pins differ from reference")
        declaration = metadata.get("point_probe", {})
        if (declaration.get("pcs") != list(PCS) or declaration.get("words") != list(WORDS) or
                declaration.get("phase") != probe.PHASE or declaration.get("complete") is not True or
                metadata.get("focused_update_range") != list(window) or metadata.get("exit_code") != 0 or
                metadata.get("probe_target_reached" if side == "native" else "trace_complete") is not True or
                metadata.get("completed_update_trace_complete") is not True or
                metadata.get("focused_update_capture_complete") is not True or
                any(value is False for key, value in metadata.items() if key.endswith("_trace_complete")) or
                declaration.get("sha256") != digest(directory / "point-probe.tsv")):
            raise ValueError("pacing capture declaration/completion/hash differs")
        rows = probe.read(directory / "point-probe.tsv", PCS, WORDS, window, oracle=side == "oracle")
        trace_path, control_path = directory / TRACE[side], reference / TRACE[side]
        trace_sha, control_sha = digest(trace_path), digest(control_path)
        trace_pins.update({trace_path: trace_sha, control_path: control_sha})
        result["evidence"][side] = {"point_trace": digest(directory / "point-probe.tsv"),
                                   "update_trace": trace_sha,
                                   "reference_update_trace": control_sha, "snapshots": [],
                                   "result": digest(directory / ("native-result.json" if side == "native" else "oracle-result.json")),
                                   "reference_result": digest(reference / ("native-result.json" if side == "native" else "oracle-result.json"))}
        if trace_sha != control_sha:
            result["qualification"]["reasons"].append(side + "-full-update-trace-changed")
        side_codes = []
        records = _records_at(trace_path, range(window[0], window[1] + 1))
        # A byte-identical control has exactly the same parsed records. Reuse
        # only inside this call, still read both sets of snapshots, and rehash
        # both backing traces after all measurement (including input checks).
        controls = records if trace_sha == control_sha else _records_at(
            control_path, range(window[0], window[1] + 1))
        for update in range(window[0], window[1] + 1):
            image, _ = _snapshot(directory, records[update])
            control, _ = _snapshot(reference, controls[update])
            if image != control:
                result["qualification"]["reasons"].append(f"{side}-focused-rdram-{update}-changed")
            result["evidence"][side]["snapshots"].append({"update": update,
                "sha256": hashlib.sha256(image).hexdigest(), "reference_sha256": hashlib.sha256(control).hexdigest()})
            side_codes.append({pc: int.from_bytes(image[pc - 0x80000000:pc - 0x80000000 + 4], "big") for pc in PCS})
            # The enclosing producer is a direct JAL with a NOP slot.
            if image[0x457b4:0x457bc].hex() != "0c0153ef00000000":
                raise ValueError("producer callsite opcode/slot differs")
        if any(codes != side_codes[0] for codes in side_codes) or any(row["opcode"] != side_codes[0][row["pc"]] for row in rows):
            raise ValueError("executed point opcodes differ from retained instructions")
        code[side] = side_codes[0]
        try:
            result["summaries"][side] = summarize(rows, oracle=side == "oracle", window=window)
        except ValueError as error:
            result["qualification"]["reasons"].append(side + ": " + str(error))
    if code["native"] != code["oracle"]:
        raise ValueError("native/oracle point instructions differ")
    if len(result["summaries"]) == 2:
        for native_row, oracle_row in zip(result["summaries"]["native"], result["summaries"]["oracle"]):
            if any(native_row[key] != oracle_row[key] for key in ("update", "thread", "entry_sp", "entry_poll", "return_poll")):
                result["qualification"]["reasons"].append(f"invocation-{native_row['update']}-correspondence-differs")
    native_metadata = json.loads((native / "native-result.json").read_text())
    poll_report = compare_polls(Path(native_metadata["source_export"]), oracle, native, input_report_path,
                                prefix_polls=native_metadata["observed_controller_polls"])
    result["input_prefix"] = {"sha256": digest(input_report_path), "polls": poll_report["shared_prefix_polls"],
                              "first_input_mismatch": poll_report["first_input_mismatch"],
                              "initial_state": poll_report["initial_state"]}
    if poll_report["first_input_mismatch"] is not None:
        result["qualification"]["reasons"].append("delivered-input-prefix-differs")
    if any(digest(path) != sha for path, sha in trace_pins.items()):
        raise ValueError("pacing update trace changed during measurement")
    result["qualification"]["passed"] = not result["qualification"]["reasons"]
    result["qualification"]["scope"] = "local-producer-call-receive-history-not-global-alignment-or-device-cause"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("native", "oracle", "reference_native", "reference_oracle", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix(".input-polls.json").exists():
        raise FileExistsError(args.output)
    result = compare(args.native, args.oracle, args.reference_native, args.reference_oracle,
                     input_report_path=args.output.with_suffix(".input-polls.json"))
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"qualification": result["qualification"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
