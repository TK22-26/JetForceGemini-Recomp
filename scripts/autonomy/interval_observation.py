"""Qualified predictions over all-thread intervals; raw PCs are never relocated."""
from pathlib import Path

from scripts import phase9_point_probe
from scripts.autonomy import point_interval_observation as interval, point_observation
from scripts.autonomy.supervisor import file_sha256, SupervisorError
from scripts.compare_phase9_point_pacing import PCS, WORDS


def registered_probe():
    return {"entry_pc": "0x80054fbc", "call_pc": "0x800457b4",
            "pcs": [f"0x{x:08x}" for x in PCS], "words": [f"0x{x:08x}" for x in WORDS]}


def can_reuse(probe):
    available = registered_probe()
    return (all(probe[key] == available[key] for key in ("entry_pc", "call_pc")) and
            all(set(probe[key]) <= set(available[key]) for key in ("pcs", "words")))


def registered_rows(runtime, window, probe=None):
    raw = {}
    for side in ("native", "oracle"):
        path = Path(runtime["record"][side]) / "point-probe.tsv"
        expected = runtime["calibration"]["evidence"][side]["point_trace"]
        if file_sha256(path) != expected:
            raise SupervisorError("registered interval trace changed before reading")
        rows = phase9_point_probe.read(path, PCS, WORDS, window, oracle=side == "oracle")
        if file_sha256(path) != expected:
            raise SupervisorError("registered interval trace changed while reading")
        raw[side] = rows if probe is None else [row for row in rows if f'0x{row["pc"]:08x}' in probe["pcs"]]
    return raw


def retained_counts(runtime, window):
    """Inventory countable A0-filtered hooks already present before call entry."""
    probe = registered_probe()
    raw = registered_rows(runtime, window)
    selectors = set()
    for side, rows in raw.items():
        calls = point_observation.spans(rows, side, probe, window)
        positions = {id(row): i for i, row in enumerate(rows)}
        for update in range(window[0] + 1, window[1] + 1):
            start = positions[id(calls[update - 1]["return"])]
            end = positions[id(calls[update]["entry"])]
            selectors.update((row["pc"], row["r4_lo"]) for row in rows[start + 1:end])
    if len(selectors) > 64:
        raise SupervisorError("retained interval count inventory exceeds budget")
    result = []
    for pc, value in sorted(selectors):
        selection = {"pc": f"0x{pc:08x}", "register": 4, "value_lo": f"0x{value:08x}"}
        measured = interval.measure(raw, probe, window, selection)
        compact_probe = {**probe, "pcs": list(dict.fromkeys([probe["entry_pc"], f'0x{int(probe["call_pc"],16)+8:08x}', selection["pc"]])),
                         "words": ["0x800a9e90"]}
        result.append({"probe": compact_probe, "selection": selection,
                       "observations": [{key: row[key] for key in ("update", "native", "oracle", "equal")}
                                        for row in measured["observations"]]})
    return result


def evaluate(raw, plan, window, *, reasons=(), instructions=None):
    reasons = list(reasons)
    try:
        measured = interval.measure(raw, plan["probe"], window, plan["selection"])
    except ValueError as error:
        reasons.append(str(error))
        measured = {"observations": []}
    prediction = plan["prediction"]
    observations = []
    for row in measured["observations"]:
        values = {side: row[side] for side in ("native", "oracle")}
        if prediction["kind"] != "event-count":
            index = prediction["occurrence"] - 1
            if any(index >= len(row["selected_events"][side]) for side in values):
                reasons.append(f'invocation-{row["update"]}-selected-occurrence-missing')
                continue
            # Ordinal alone is not call identity. Preserve raw overlay RA values
            # and reject unequal caller/thread/stack/poll prefixes, never alias them.
            keys = ("pc", "m800a9e90", "r29_lo", "r31_lo", "controller_polls")
            prefixes = [[tuple(event[key] for key in keys) for event in row["selected_events"][side][:index+1]]
                        for side in values]
            if prefixes[0] != prefixes[1]:
                reasons.append(f'invocation-{row["update"]}-selected-call-prefixes-differ')
            for side in values:
                event = row["selected_events"][side][index]
                if prediction["kind"] == "register":
                    reg = prediction["register"]
                    values[side] = f'0x{(event[f"r{reg}_hi"] << 32) | event[f"r{reg}_lo"]:016x}'
                else:
                    values[side] = f'0x{event["m" + prediction["address"][2:]]:08x}'
        observations.append({"update": row["update"], **values, "equal": values["native"] == values["oracle"],
                             "selected_event_counts": {side: row[side] for side in ("native", "oracle")},
                             "boundaries": row["boundaries"], "selected_events": row["selected_events"]})
    observed = next((row for row in observations if row["update"] == prediction["update"]), None)
    return {"kind": "jfg-interval-state-experiment", "schema": 1, "plan": plan, "focus_updates": window,
            "observations": observations, "raw_events": raw, "prediction_observation": observed,
            "prediction_observed": observed["equal"] == (prediction["relation"] == "equal") if observed and not reasons else None,
            "qualification": {"passed": not reasons, "reasons": reasons,
                              "scope": "all-thread-filtered-hooks-between-qualified-call-boundaries",
                              "instruction_evidence": instructions},
            "completed_queue_operations_proved": False, "alignment_validated": False,
            "causal_fix_proved": False, "parity_verified": False}
