"""Compare native/reference state at input polls without claiming clock parity."""
import argparse
import csv
import json
from pathlib import Path

from scripts.build_phase9_route_replays import load_replay
from scripts.phase95_bridge import digest


def oracle_polls(path):
    records = []
    for line in path.read_text().splitlines():
        if not line.startswith("input-poll\t"):
            continue
        parts = line.split("\t")
        if len(parts) != 14 or tuple(parts[i] for i in (2, 4, 6, 8, 10, 12)) != (
                "index", "buttons", "stick", "mode", "level", "rng"):
            raise ValueError("oracle input-poll trace lacks required state fields")
        x, y = parts[7].split(",")
        records.append({"poll": int(parts[3]), "frame": int(parts[1]),
                        "buttons": int(parts[5], 16), "x": int(x), "y": int(y),
                        "mode": int(parts[9]), "level": int(parts[11]),
                        "rng": int(parts[13])})
    return records


def native_polls(path):
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        expected = ("poll", "vi_retrace", "vi_frame", "front_mode",
                    "level_word", "rng_seed", "buttons", "x", "y")
        if tuple(reader.fieldnames or ()) != expected:
            raise ValueError("native input-poll trace schema mismatch")
        return [{key: int(value) for key, value in row.items()} for row in reader]


def discordance_windows(oracle_rows, native_rows, *, preview_limit=8):
    """Summarize same-index state disagreement; no clock alignment is implied."""
    fields = (("mode", "front_mode"), ("level", "level_word"),
              ("rng", "rng_seed"))
    summaries = {}
    for oracle_key, native_key in fields:
        windows = []
        start = None
        shared = min(len(oracle_rows), len(native_rows))
        for index in range(shared + 1):
            different = (index < shared and
                         oracle_rows[index][oracle_key] !=
                         native_rows[index][native_key])
            if different and start is None:
                start = index
            elif not different and start is not None:
                windows.append({"first_poll": start, "last_poll": index - 1,
                                "polls": index - start,
                                "oracle_first_frame": oracle_rows[start]["frame"],
                                "native_first_retrace":
                                    native_rows[start]["vi_retrace"]})
                start = None
        summaries[oracle_key] = {
            "mismatching_polls": sum(window["polls"] for window in windows),
            "windows": len(windows),
            "longest_window_polls": max((window["polls"] for window in windows),
                                        default=0),
            "first_windows": windows[:preview_limit],
        }
    return summaries


def transition_order(oracle_rows, native_rows):
    """Compare changed observed signatures, ignoring repeated poll samples.

    This is a localization hint, not a common execution-boundary alignment.
    """
    def compact(rows, mode, level, rng, clock):
        transitions = []
        previous = None
        for row in rows:
            signature = (row[mode], row[level], row[rng])
            if signature != previous:
                transitions.append({"poll": row["poll"], "clock": row[clock],
                                    "mode": signature[0], "level": signature[1],
                                    "rng": signature[2]})
                previous = signature
        return transitions

    oracle = compact(oracle_rows, "mode", "level", "rng", "frame")
    native = compact(native_rows, "front_mode", "level_word", "rng_seed",
                     "vi_retrace")
    fields = ("mode", "level", "rng")
    first = next((index for index in range(min(len(oracle), len(native)))
                  if any(oracle[index][key] != native[index][key]
                         for key in fields)), min(len(oracle), len(native)))
    mismatch = None
    resync = None
    if first < max(len(oracle), len(native)):
        mismatch = {"ordinal": first,
                    "prior_matched": ({"oracle": oracle[first - 1],
                                       "native": native[first - 1]}
                                      if first else None),
                    "oracle": oracle[first] if first < len(oracle) else None,
                    "native": native[first] if first < len(native) else None}
        # A brief insertion/deletion or phase shift can later resynchronize.
        for o_index in range(first, min(first + 32, len(oracle))):
            for n_index in range(first, min(first + 32, len(native))):
                if o_index == first and n_index == first:
                    continue
                if all(oracle[o_index][key] == native[n_index][key]
                       for key in fields):
                    resync = {"oracle_ordinal": o_index,
                              "native_ordinal": n_index,
                              "oracle": oracle[o_index], "native": native[n_index]}
                    break
            if resync is not None:
                break
    return {"oracle_transitions": len(oracle), "native_transitions": len(native),
            "first_unmatched_ordinal": mismatch,
            "nearby_exact_match_within_32_transitions": resync,
            "alignment_validated": False}


def compare(source, oracle, native, output, *, prefix_polls=None):
    source, oracle, native, output = map(Path, (source, oracle, native, output))
    if output.exists():
        raise FileExistsError(output)
    manifest = json.loads((source / "export-manifest.json").read_text())
    if manifest.get("input_sha256") != digest(source / "controller.input"):
        raise ValueError("selected input export changed")
    events = load_replay(source / "controller.input")
    if len(events) != manifest.get("controller_polls") or any(
            event.first != index or event.last != (
                manifest["oracle_final_frame"] if index == len(events) - 1 else index + 1)
            for index, event in enumerate(events)):
        raise ValueError("comparison requires one declared event per input poll")
    if prefix_polls is not None and (type(prefix_polls) is not int or
                                     not 1 <= prefix_polls <= len(events)):
        raise ValueError("invalid requested controller-poll prefix")
    o_manifest = json.loads((oracle / "oracle-result.json").read_text())
    n_manifest = json.loads((native / "native-result.json").read_text())
    if (o_manifest.get("input_sha256") != manifest["input_sha256"] or
            n_manifest.get("input_sha256") != manifest["input_sha256"] or
            not o_manifest.get("trace_complete") or
            not n_manifest.get("probe_target_reached") or
            not o_manifest.get("initial_flash_matches_candidate")):
        raise ValueError("poll traces do not belong to verified replays")
    initial_verified = None
    if prefix_polls is not None:
        initial = manifest.get("initial_state") or {}
        flash = initial.get("flash_sha256")
        pak = initial.get("pak_sha256")
        if (not isinstance(flash, str) or not isinstance(pak, str) or
                digest(source / "initial.flash") != flash or
                digest(source / "initial.pak") != pak or
                n_manifest.get("initial_flash_sha256") != flash or
                n_manifest.get("initial_pak_sha256") != pak or
                o_manifest.get("oracle_initial_flash_sha256") != flash):
            raise ValueError("prefix initial flash/Pak provenance is not verified")
        initial_verified = {"flash_matches_both": True,
                            "native_pak_matches_candidate": True,
                            "oracle_pak_equivalence": "not_verified"}
    oracle_rows = oracle_polls(oracle / "checkpoints.tsv")
    native_rows = native_polls(native / "controller-polls.tsv")
    required = len(events) if prefix_polls is None else prefix_polls
    if (prefix_polls is not None and
            (len(oracle_rows) < required or len(native_rows) < required)) or \
            (prefix_polls is None and len(oracle_rows) != len(events)) or any(
            row["poll"] != index for index, row in enumerate(oracle_rows)) or any(
            row["poll"] != index for index, row in enumerate(native_rows)):
        raise ValueError("input-poll trace has gaps or reordered samples")
    observed_oracle, observed_native = len(oracle_rows), len(native_rows)
    oracle_rows, native_rows = oracle_rows[:required], native_rows[:required]
    first_input_mismatch = None
    for system, rows in (("oracle", oracle_rows), ("native", native_rows)):
        for index, row in enumerate(rows):
            event = events[min(index, len(events) - 1)]
            for key, expected in (("buttons", event.buttons),
                                  ("x", event.stick_x), ("y", event.stick_y)):
                if row[key] != expected:
                    first_input_mismatch = {"system": system, "poll": index,
                                            "field": key, "observed": row[key],
                                            "expected": expected}
                    break
            if first_input_mismatch:
                break
        if first_input_mismatch:
            break
    first_schedule_mismatch = None
    first_state_mismatch = None
    for index, (o_row, n_row) in enumerate(zip(oracle_rows, native_rows)):
        if first_schedule_mismatch is None and o_row["frame"] != n_row["vi_retrace"]:
            first_schedule_mismatch = {"poll": index, "oracle_frame": o_row["frame"],
                                       "native_retrace": n_row["vi_retrace"]}
        if first_state_mismatch is None:
            state_fields = (("mode", "front_mode"), ("level", "level_word"),
                            ("rng", "rng_seed"))
            differences = {
                oracle_key: {"oracle": o_row[oracle_key], "native": n_row[native_key]}
                for oracle_key, native_key in state_fields
                if o_row[oracle_key] != n_row[native_key]
            }
            if differences:
                first_state_mismatch = {"poll": index, "oracle_frame": o_row["frame"],
                                        "native_retrace": n_row["vi_retrace"],
                                        "fields": differences}
    result = {"kind": "jfg-phase95-input-poll-comparison", "schema": 1,
              "acceptance": False, "input_sha256": manifest["input_sha256"],
              "scope": "prefix" if prefix_polls is not None else "declared-route",
              "requested_polls": prefix_polls,
              "initial_state": initial_verified,
              "oracle_polls": observed_oracle, "native_polls": observed_native,
              "shared_prefix_polls": min(len(oracle_rows), len(native_rows)),
              "first_input_mismatch": first_input_mismatch,
              "first_schedule_mismatch": first_schedule_mismatch,
              "first_observed_state_mismatch": first_state_mismatch,
              "observed_discordance_windows":
                  discordance_windows(oracle_rows, native_rows),
              "observed_transition_order": transition_order(oracle_rows, native_rows),
              "native_parity_verified": False,
              "first_validated_gameplay_divergence": None,
              "limitation": "Poll indices align input samples, but their VI/frame clocks differ; an observed state mismatch is not a validated common execution boundary."}
    output.write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("oracle", type=Path)
    parser.add_argument("native", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--polls", type=int,
                        help="compare a captured prefix of the declared poll route")
    args = parser.parse_args()
    print(json.dumps(compare(args.source, args.oracle, args.native, args.output,
                             prefix_polls=args.polls)))


if __name__ == "__main__":
    main()
