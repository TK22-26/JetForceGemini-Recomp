"""Turn a completed Phase 9.5 south scenario into a reproducible regression bundle."""
import argparse
import json
from pathlib import Path
import time

from scripts.phase95_export_inputs import export
from scripts.phase95_native_replay import replay as native_replay
from scripts.phase95_native_failure_triage import triage as native_failure_triage
from scripts.phase95_native_report import report as native_report
from scripts.phase95_oracle_replay import replay as oracle_replay
from scripts.phase95_poll_compare import compare as poll_compare
from scripts.phase95_repeat_audit import audit as repeat_audit


def bundle(scenario, output, emulator, rom, rom_sha256, executable,
           initial_flash, initial_pak, *, repeats=3, failure_trials=8):
    scenario, output = Path(scenario).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError(output)
    if type(repeats) is not int or not 1 <= repeats <= 10:
        raise ValueError("oracle repeat budget must be 1 through 10")
    if type(failure_trials) is not int or not 1 <= failure_trials <= 64:
        raise ValueError("native failure trial budget must be 1 through 64")
    source_result = json.loads((scenario / "scenario-result.json").read_text())
    if (source_result.get("kind") != "jfg-phase95-goldwood-south-scenario" or
            not source_result.get("completed") or
            source_result.get("stages_completed") != 7):
        raise ValueError("regression source is not a completed seven-stage south scenario")
    output.mkdir(parents=True)
    objective = {"kind": "jfg-phase95-regression-bundle", "schema": 1,
                 "acceptance": False, "scenario": str(scenario),
                 "oracle_repeats": repeats, "native_parity_required": True,
                 "comparison_policy": "report unresolved boundaries, never count mismatch as pass"}
    (output / "bundle-objective.json").write_text(json.dumps(objective, indent=2) + "\n")
    started = time.monotonic()

    def stage(name, result):
        with (output / "bundle-stages.jsonl").open("a") as stream:
            stream.write(json.dumps({"stage": name, "result": result}) + "\n")

    try:
        exported = export(scenario, output / "selected-input",
                          initial_flash=initial_flash, initial_pak=initial_pak)
        stage("selected-input", {"input_sha256": exported["input_sha256"],
                                 "polls": exported["controller_polls"]})
        roots = []
        source_stages = [json.loads(line) for line in
                         (scenario / "scenario-stages.jsonl").read_text().splitlines()]
        checkpoints = [source_stages[index]["frame"] for index in (0, 3, 5)]
        for index in range(repeats):
            root = output / f"oracle-repeat-{index + 1:02d}"
            result = oracle_replay(root, emulator, rom, rom_sha256,
                                   output / "selected-input", checkpoints=checkpoints)
            roots.append(root)
            stage(f"oracle-repeat-{index + 1:02d}",
                  {"final_rdram_sha256": result["final_rdram_sha256"],
                   "target_frame": result["target_frame"]})
        repeat_report = repeat_audit(scenario, roots, output / "frozen-repeat-audit.json")
        stage("frozen-repeat-audit", {"all_match": repeat_report["all_match"],
                                      "repeat_count": repeat_report["repeat_count"]})
        native = native_replay(output / "selected-input", output / "native",
                               executable, rom, rom_sha256, poll_trace=True)
        stage("native-replay", {"probe_target_reached": native["probe_target_reached"],
                                "final_state_hash": native["final_state_hash"]})
        differential = native_report(output / "selected-input", scenario,
                                     roots[0], output / "native",
                                     output / "native-report.json")
        stage("native-differential", {"endpoint_counters_match":
                                      differential["endpoint_counters_match"],
                                      "first_validated_divergence":
                                      differential["first_validated_divergence"]})
        polls = poll_compare(output / "selected-input", roots[0],
                             output / "native", output / "poll-comparison.json")
        stage("poll-comparison", {"shared_prefix_polls": polls["shared_prefix_polls"],
                                  "first_observed_state_mismatch":
                                  polls["first_observed_state_mismatch"],
                                  "first_validated_gameplay_divergence":
                                  polls["first_validated_gameplay_divergence"]})
        summary = {**objective, "completed": True,
                   "elapsed_seconds": time.monotonic() - started,
                   "input_sha256": exported["input_sha256"],
                   "oracle_repeats_match": repeat_report["all_match"],
                   "native_parity_verified": differential["native_parity_verified"],
                   "native_endpoint_counters_match": differential["endpoint_counters_match"],
                   "first_observed_poll_state_mismatch": polls["first_observed_state_mismatch"],
                   "first_validated_gameplay_divergence":
                       polls["first_validated_gameplay_divergence"]}
        (output / "bundle-result.json").write_text(json.dumps(summary, indent=2) + "\n")
        return summary
    except BaseException as error:
        triage_result = None
        triage_error = None
        if (output / "selected-input" / "export-manifest.json").is_file() and \
                (output / "native" / "native-result.json").is_file():
            try:
                triage_result = native_failure_triage(
                    output / "selected-input", output / "native",
                    output / "native-failure-triage", executable, rom, rom_sha256,
                    max_trials=failure_trials)
            except (OSError, ValueError, RuntimeError) as caught:
                triage_error = f"{type(caught).__name__}: {caught}"
        failure = {**objective, "completed": False,
                   "elapsed_seconds": time.monotonic() - started,
                   "classification": type(error).__name__, "detail": str(error),
                   "native_failure_triage": triage_result,
                   "native_failure_triage_error": triage_error}
        (output / "bundle-failure.json").write_text(json.dumps(failure, indent=2) + "\n")
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--initial-flash", type=Path, required=True)
    parser.add_argument("--initial-pak", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--failure-trials", type=int, default=8)
    args = parser.parse_args()
    print(json.dumps(bundle(args.scenario, args.output, args.emulator,
                            args.rom, args.rom_sha256, args.executable,
                            args.initial_flash, args.initial_pak,
                            repeats=args.repeats,
                            failure_trials=args.failure_trials)))


if __name__ == "__main__":
    main()
