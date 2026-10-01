"""Count filtered instruction hooks between successive qualified call spans.

This does not pair arbitrary calls by ordinal, translate overlay return PCs,
or treat entry into osSendMesg as proof of a completed enqueue. Capture/input/
opcode/non-perturbation qualification belongs to the invoking capture adapter.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from scripts.autonomy.point_observation import spans


def measure(raw, probe, window, selection):
    """Previous caller return -> next callee entry, including other threads.

    Unlike the original point primitive, interval counts deliberately include
    scheduler/device threads. The boundary thread, stack, return addresses,
    and delivered-input poll labels must still correspond on both sides.
    """
    if (not isinstance(selection, dict) or set(selection) != {"pc", "register", "value_lo"} or
            selection["pc"] not in probe["pcs"] or type(selection["register"]) is not int or
            not 0 <= selection["register"] <= 31 or not isinstance(selection["value_lo"], str) or
            not re.fullmatch(r"0x[0-9a-f]{8}", selection["value_lo"])):
        raise ValueError("invalid bounded interval hook selector")
    if (not isinstance(window, (list, tuple)) or len(window) != 2 or
            any(type(value) is not int for value in window) or
            not 1 <= window[0] < window[1] <= 1_000_000 or window[1] - window[0] >= 16):
        raise ValueError("interval observation requires adjacent captured invocations")
    if set(raw) != {"native", "oracle"}:
        raise ValueError("interval observation requires both capture streams")
    grouped = {side: spans(rows, side, probe, window) for side, rows in raw.items()}
    positions = {side: {id(row): index for index, row in enumerate(rows)} for side, rows in raw.items()}
    pc, value = int(selection["pc"], 16), int(selection["value_lo"], 16)
    result = []
    for update in range(window[0] + 1, window[1] + 1):
        boundaries, events = {}, {}
        for side in raw:
            previous, current = grouped[side][update - 1], grouped[side][update]
            start, stop = previous["return"], current["entry"]
            if previous["thread"] != current["thread"] or previous["stack"] != current["stack"]:
                raise ValueError("interval boundary thread/stack changed between calls")
            first, last = positions[side][id(start)], positions[side][id(stop)]
            if first >= last:
                raise ValueError("interval call boundary order is invalid")
            if start["controller_polls"] > stop["controller_polls"]:
                raise ValueError("interval input counters moved backwards")
            boundaries[side] = {"thread": current["thread"], "stack": current["stack"],
                                "previous_return": start, "next_entry": stop}
            events[side] = [row for row in raw[side][first + 1:last]
                            if row["pc"] == pc and row[f'r{selection["register"]}_lo'] == value]
        a, b = boundaries["native"], boundaries["oracle"]
        if (any(a[key] != b[key] for key in ("thread", "stack")) or
                any(a[key]["controller_polls"] != b[key]["controller_polls"]
                    for key in ("previous_return", "next_entry"))):
            raise ValueError("paired interval boundaries do not correspond")
        result.append({"update": update, "native": len(events["native"]), "oracle": len(events["oracle"]),
                       "equal": len(events["native"]) == len(events["oracle"]),
                       "boundaries": boundaries, "selected_events": events})
    return {"kind": "jfg-point-interval-measurement", "schema": 1, "selection": selection,
            "focus_updates": list(window), "observations": result,
            "scope": "filtered-hook-count-between-previous-caller-return-and-next-entry-all-threads",
            "capture_qualification_required": True, "completed_queue_operations_proved": False,
            "alignment_validated": False, "causal_fix_proved": False, "parity_verified": False}


def observe_registered(store, repo, state, plan_id, selection):
    """Engineering qualification adapter using an existing calibrated capture.

    This is not a model-authored plan or a new accepted ledger observation.
    It proves that the missing interval primitive can consume existing traces
    before extending the autonomous planning/capture contract to request it.
    """
    from scripts.autonomy import point_experiment, point_runtime, state_word_experiment as words
    from scripts.autonomy.supervisor import file_sha256, SupervisorError
    from scripts import phase9_point_probe
    from scripts.compare_phase9_point_pacing import PCS, WORDS

    context = point_experiment.plan_context(store, repo, state, plan_id)
    runtime = context["point_runtime"]
    calibration = runtime["calibration"]
    probe = {"entry_pc": "0x80054fbc", "call_pc": "0x800457b4",
             "pcs": [f"0x{pc:08x}" for pc in PCS], "words": [f"0x{word:08x}" for word in WORDS]}
    raw, pins = {}, {}
    for side in ("native", "oracle"):
        path = Path(runtime["record"][side]) / "point-probe.tsv"
        expected = calibration["evidence"][side]["point_trace"]
        if file_sha256(path) != expected:
            raise SupervisorError("registered interval trace changed before measurement")
        raw[side] = phase9_point_probe.read(path, PCS, WORDS, context["window"], oracle=side == "oracle")
        if file_sha256(path) != expected:
            raise SupervisorError("registered interval trace changed during measurement")
        pins[side] = {"path": str(path), "sha256": expected}
    measurement = measure(raw, probe, context["window"], selection)
    # Independently repeat capture/source/input/non-perturbation qualification;
    # do not accept a previously checked report after its backing files changed.
    checked = point_runtime.load(store, repo, state, context)
    if (checked is None or checked["binding"] != runtime["binding"] or
            checked["calibration"] != calibration):
        raise SupervisorError("registered interval runtime changed during measurement")
    return {"kind": "engineering-point-interval-observation", "schema": 1,
            "plan_result": words.pin(context["plan_seal"]), "runtime": runtime["binding"],
            "calibration": runtime["record"]["calibration"], "point_traces": pins,
            "producer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "measurement": measurement,
            "qualification": {"passed": True,
                              "scope": "local-interval-hooks-not-completed-queue-operations-or-global-alignment",
                              "capture": calibration["qualification"], "input_prefix": calibration["input_prefix"]},
            "autonomous_plan_executed": False, "alignment_validated": False,
            "causal_fix_proved": False, "parity_verified": False}


def main():
    from scripts.autonomy.job_store import JobStore
    from scripts.autonomy.supervisor import canonical_bytes, _write_json_atomic

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--pc", required=True)
    parser.add_argument("--register", type=int, required=True)
    parser.add_argument("--value-lo", required=True)
    args = parser.parse_args()
    selection = {"pc": args.pc, "register": args.register, "value_lo": args.value_lo}
    repo = Path(__file__).resolve().parents[2]
    state = repo / "tools/private/autonomy"
    if (state / "PAUSED").exists():
        raise ValueError("interval observation is paused")
    with JobStore(state / "jobs.sqlite") as store:
        report = observe_registered(store, repo, state, args.plan, selection)
    # Content-addressed publication cannot overwrite an older observation.
    digest = hashlib.sha256(canonical_bytes(report)).hexdigest()
    path = state / "interval-calibration" / (digest + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != canonical_bytes(report):
        raise ValueError("retained interval report changed")
    if not path.exists():
        _write_json_atomic(path, report)
    print(json.dumps({"output": str(path), "sha256": digest, "qualification": report["qualification"],
                      "observations": [{key: row[key] for key in ("update", "native", "oracle", "equal")}
                                       for row in report["measurement"]["observations"]]}), flush=True)


if __name__ == "__main__":
    main()
