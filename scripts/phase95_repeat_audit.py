"""Audit independent frozen-route oracle replays against declared stage hashes."""
import argparse
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(scenario, repeats, output):
    scenario, repeats, output = Path(scenario), [Path(root) for root in repeats], Path(output)
    if not repeats or output.exists():
        raise ValueError("supply new audit output and at least one repeat")
    if len({root.resolve() for root in repeats}) != len(repeats):
        raise ValueError("frozen-route repeats must use distinct worker roots")
    result = json.loads((scenario / "scenario-result.json").read_text())
    if not result.get("completed") or result.get("stages_completed") != 7:
        raise ValueError("source scenario did not complete the declared seven stages")
    stages = [json.loads(line) for line in
              (scenario / "scenario-stages.jsonl").read_text().splitlines()]
    if len(stages) != 7 or [stage["stage"] for stage in stages] != list(range(7)):
        raise ValueError("source stage ledger is incomplete")
    # These are distinct gameplay checkpoints, not merely startup or exit proximity.
    checked = [stages[index] for index in (0, 3, 5, 6)]
    if len({stage["frame"] for stage in checked}) != len(checked):
        raise ValueError("declared gameplay checkpoint frames overlap")
    source_sha = None
    pins = None
    details = []
    for root in repeats:
        oracle = json.loads((root / "oracle-result.json").read_text())
        if (oracle.get("kind") != "jfg-phase95-oracle-poll-replay" or
                oracle.get("exit_code") != 0 or not oracle.get("trace_complete") or
                oracle.get("target_frame") != stages[-1]["frame"] or
                oracle.get("input_clock") != "controller-poll"):
            raise ValueError(f"oracle repeat did not finish the same route: {root}")
        if source_sha is None:
            source_sha = oracle["input_sha256"]
        elif oracle["input_sha256"] != source_sha:
            raise ValueError("oracle repeats used different input files")
        current_pins = {key: oracle.get(key) for key in
                        ("source_export_sha256", "rom_sha256", "emulator_sha256",
                         "config_sha256", "runtime_sha256", "script_sha256")}
        if any(not value for value in current_pins.values()):
            raise ValueError("oracle repeat is missing provenance pins")
        if pins is None:
            pins = current_pins
        elif current_pins != pins:
            raise ValueError("oracle repeat pin set changed")
        comparisons = []
        for stage in checked:
            capture = root / f"checkpoint-{stage['frame']:06d}.rdram"
            observed = digest(capture)
            if observed != stage["rdram_sha256"]:
                raise ValueError(f"replay mismatch at stage {stage['stage']}: {root}")
            comparisons.append({"stage": stage["stage"], "name": stage["name"],
                                "frame": stage["frame"], "rdram_sha256": observed})
        if oracle["final_rdram_sha256"] != result["final_rdram_sha256"]:
            raise ValueError(f"replay final result differs: {root}")
        details.append({"root": str(root.resolve()), "checkpoints": comparisons,
                        "final_rdram_sha256": oracle["final_rdram_sha256"]})
    report = {"kind": "jfg-phase95-frozen-route-repeat-audit", "schema": 1,
              "acceptance": False, "scenario": str(scenario.resolve()),
              "scenario_sha256": digest(scenario / "scenario-result.json"),
              "input_sha256": source_sha, "repeat_count": len(details),
              "pin_set": pins,
              "checked_stage_indices": [0, 3, 5, 6], "all_match": True,
              "repeats": details,
              "limitations": "frozen-route repeats only; ten seeded exploration jobs and native parity remain open"}
    output.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("repeats", nargs="+", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.scenario, args.repeats, args.output)))


if __name__ == "__main__":
    main()
