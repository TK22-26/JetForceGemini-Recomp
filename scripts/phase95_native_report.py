"""Report an exported oracle route's native replay outcome without hiding clock gaps."""
import argparse
import hashlib
import json
from pathlib import Path

from scripts.build_phase9_route_replays import load_replay


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def report(source, scenario, oracle, native, output):
    source, scenario, oracle, native, output = map(Path, (source, scenario, oracle, native, output))
    if output.exists():
        raise FileExistsError(output)
    manifest = json.loads((source / "export-manifest.json").read_text())
    scenario_result = json.loads((scenario / "scenario-result.json").read_text())
    oracle_result = json.loads((oracle / "oracle-result.json").read_text())
    if (manifest.get("input_sha256") != digest(source / "controller.input") or
            oracle_result.get("input_sha256") != manifest["input_sha256"] or
            not scenario_result.get("completed") or
            oracle_result.get("final_rdram_sha256") != scenario_result["final_rdram_sha256"]):
        raise ValueError("oracle replay or source input is not the verified scenario")
    if load_replay(source / "controller.input") != load_replay(native / "controller.input"):
        raise ValueError("native replay input differs from selected oracle input")
    initial = manifest.get("initial_state")
    if (initial is None or digest(source / "initial.flash") != initial["flash_sha256"] or
            digest(source / "initial.pak") != initial["pak_sha256"]):
        raise ValueError("exported initial save/pak differs from its manifest")
    native_objective = json.loads((native / "native-objective.json").read_text())
    if (native_objective.get("input_sha256") != manifest["input_sha256"] or
            native_objective.get("initial_flash_sha256") != initial["flash_sha256"] or
            native_objective.get("initial_pak_sha256") != initial["pak_sha256"]):
        raise ValueError("native launcher did not hash the declared initial copies")
    records = (native / "stdout.log").read_text().splitlines()
    probes = [json.loads(line) for line in records if line.startswith('{"kind":"jfg-phase8-native-probe"')]
    if len(probes) != 1 or probes[0].get("status") != "retrace-target":
        raise ValueError("native replay did not report one bounded target completion")
    probe = probes[0]
    if probe.get("vi_retraces") != manifest["oracle_final_frame"]:
        raise ValueError("native replay stopped before the declared frame target")
    trace = (oracle / "checkpoints.tsv").read_text().splitlines()
    flash_lines = [line.split("\t", 1)[1] for line in trace
                   if line.startswith("initial-flash-sha256\t")]
    if len(flash_lines) != 1 or flash_lines[0] != initial["flash_sha256"]:
        raise ValueError("oracle-visible initial flash differs from native candidate")
    polls = [line.split("\t") for line in trace if line.startswith("input-poll\t")]
    if (len(polls) != manifest["controller_polls"] or
            int(polls[-1][3]) + 1 != manifest["controller_polls"]):
        raise ValueError("oracle replay did not consume the declared poll path")
    stages = [json.loads(line) for line in
              (scenario / "scenario-stages.jsonl").read_text().splitlines()]
    oracle_kills = sum(stage["result"]["effect"]["kills"] for stage in stages[1:4])
    native_kills = probe["phase9_route"]["weapon_stat_kills"]
    native_polls = probe["controller_samples"]
    if (type(native_kills) is not int or type(native_polls) is not int or
            oracle_kills != 3):
        raise ValueError("missing or invalid combat/poll counters")
    result = {"kind": "jfg-phase95-native-differential-report", "schema": 1,
              "acceptance": False, "input_sha256": manifest["input_sha256"],
              "oracle_scenario": str(scenario.resolve()),
              "oracle_repeat": str(oracle.resolve()),
              "native_replay": str(native.resolve()),
              "frame_target": manifest["oracle_final_frame"],
              "native_reached_target": True,
              "oracle_controller_polls": len(polls),
              "native_controller_polls": native_polls,
              "oracle_weapon_kills": oracle_kills,
              "native_weapon_kills": native_kills,
              "native_state_hash": probe["state_hash"],
              "endpoint_counters_match": (native_polls == len(polls) and
                                          native_kills == oracle_kills),
              "native_parity_verified": False,
              "first_validated_divergence": None,
              "comparison_boundary": (
                  "Native VI-receive and BizHawk emulator-frame semantic hashes "
                  "are not aligned execution points; poll-count and combat "
                  "differences are validated at the declared endpoint, but an "
                  "earliest gameplay divergence is not yet established."),
              "initial_save_equivalence": initial["oracle_save_equivalence"],
              "oracle_flash_matches_candidate": True,
              "native_initial_copy": "launcher hashed isolated save/pak copies before native execution; oracle-visible FlashRAM matches candidate, pak equivalence remains unverified"}
    output.write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("scenario", type=Path)
    parser.add_argument("oracle", type=Path)
    parser.add_argument("native", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(report(args.source, args.scenario, args.oracle,
                            args.native, args.output)))


if __name__ == "__main__":
    main()
