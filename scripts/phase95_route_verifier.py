"""Scenario-neutral, bounded oracle/native verification of selected-input routes.

The source worker supplies observed RDRAM checkpoints. Native endpoint and
controller-poll results are reported separately; no unvalidated clock alignment
or Controller Pak equivalence is promoted into a parity claim.
"""
import argparse
import json
from pathlib import Path
import re
import time

from scripts.phase95_bridge import digest
from scripts.phase95_native_failure_triage import triage as failure_triage
from scripts.phase95_native_replay import replay as native_replay
from scripts.phase95_oracle_replay import replay as oracle_replay
from scripts.phase95_poll_compare import compare as poll_compare


ORACLE_PINS = ("source_export_sha256", "rom_sha256", "emulator_sha256",
               "config_sha256", "runtime_sha256", "script_sha256")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def source_contract(source, scenario_result, emulator, rom, rom_sha256,
                    extra_frames=(), extra_checkpoints=()):
    source, scenario_result = Path(source).resolve(), Path(scenario_result).resolve()
    manifest = _read(source / "export-manifest.json")
    result = _read(scenario_result)
    worker = Path(manifest.get("source_worker", "")).resolve()
    if (manifest.get("kind") != "jfg-phase95-selected-input-export" or
            manifest.get("schema") != 1 or worker != scenario_result.parent or
            result.get("completed") is not True or
            (worker / "bridge-result.txt").read_text(encoding="utf-8") != "stopped\n"):
        raise ValueError("export and completed source scenario do not share a worker")
    initial = manifest.get("initial_state") or {}
    if (manifest.get("input_sha256") != digest(source / "controller.input") or
            initial.get("flash_sha256") != digest(source / "initial.flash") or
            initial.get("pak_sha256") != digest(source / "initial.pak") or
            digest(rom) != rom_sha256):
        raise ValueError("selected route, initial state, or ROM pin changed")
    worker_manifest = _read(worker / "manifest.json")
    if (worker_manifest.get("rom_sha256") != rom_sha256 or
            worker_manifest.get("emulator_sha256") != digest(emulator)):
        raise ValueError("source worker used a different ROM or emulator")
    target = manifest.get("oracle_final_frame")
    if type(target) is not int or not 3 <= target <= 1_000_000:
        raise ValueError("invalid exported final frame")
    if type(extra_frames) not in (tuple, list) or any(
            type(frame) is not int or not 3 <= frame <= target
            for frame in extra_frames):
        raise ValueError("invalid requested checkpoint frame")
    observations = {}
    last = None
    with (worker / "observations.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            frame, hash_value = row.get("frame"), row.get("rdram_sha256")
            if type(frame) is not int or not isinstance(hash_value, str):
                raise ValueError("source observation lacks frame/RDRAM hash")
            observations.setdefault(frame, set()).add(hash_value)
            last = row
    if (last is None or last.get("frame") != target or
            last.get("polls") != manifest.get("controller_polls") or
            last.get("rdram_sha256") != result.get("final_rdram_sha256") or
            result.get("final_frame", target) != target or
            digest(worker / "observation.rdram") != last.get("rdram_sha256")):
        raise ValueError("source scenario final state differs from exported route")
    expected = {target: result["final_rdram_sha256"]}
    stages = worker / "scenario-stages.jsonl"
    if stages.is_file():
        for line in stages.read_text(encoding="utf-8").splitlines():
            stage = json.loads(line)
            frame, hash_value = stage.get("frame"), stage.get("rdram_sha256")
            if (type(frame) is not int or not 3 <= frame <= target or
                    not isinstance(hash_value, str) or
                    (frame in expected and expected[frame] != hash_value)):
                raise ValueError("source scenario stage checkpoint is invalid")
            expected[frame] = hash_value
    selected = [*extra_checkpoints,
                *(result.get("verification_checkpoints") or [])]
    for item in selected:
        if (not isinstance(item, dict) or
                type(item.get("frame")) is not int or
                not 3 <= item["frame"] <= target or
                not isinstance(item.get("rdram_sha256"), str) or
                SHA256.fullmatch(item["rdram_sha256"]) is None):
            raise ValueError("selected checkpoint requires frame and RDRAM SHA-256")
        frame, hash_value = item["frame"], item["rdram_sha256"]
        if (hash_value not in observations.get(frame, ()) or
                (frame in expected and expected[frame] != hash_value)):
            raise ValueError("selected checkpoint is not the observed source state")
        expected[frame] = hash_value
    frames = [*extra_frames, *(result.get("verification_frames") or [])]
    for frame in frames:
        if type(frame) is not int or not 3 <= frame <= target:
            raise ValueError("source scenario verification frame is invalid")
        if frame in expected:
            continue
        if frame not in observations or len(observations[frame]) != 1:
            raise ValueError(f"checkpoint frame {frame} is missing or ambiguous")
        hash_value = next(iter(observations[frame]))
        if frame in expected and expected[frame] != hash_value:
            raise ValueError("verification frame disagrees with declared scenario stage")
        expected[frame] = hash_value
    for frame, hash_value in expected.items():
        if hash_value not in observations.get(frame, ()):
            raise ValueError(f"checkpoint {frame} was not observed by source worker")
    return {"source_worker": str(worker), "scenario_result": str(scenario_result),
            "scenario_result_sha256": digest(scenario_result),
            "input_sha256": manifest["input_sha256"],
            "rom_sha256": rom_sha256,
            "emulator_sha256": worker_manifest["emulator_sha256"],
            "config_sha256": worker_manifest["config_sha256"],
            "runtime_sha256": worker_manifest["runtime_sha256"],
            "initial_flash_sha256": initial["flash_sha256"],
            "initial_pak_sha256": initial["pak_sha256"],
            "target_frame": target,
            "controller_polls": manifest["controller_polls"],
            "checkpoints": [{"frame": frame, "rdram_sha256": expected[frame]}
                            for frame in sorted(expected)]}


def audit_oracle_runs(source, contract, roots):
    if not roots or len(set(map(lambda path: str(Path(path).resolve()), roots))) != len(roots):
        raise ValueError("oracle repeats require distinct roots")
    pins = None
    details = []
    for root in roots:
        root = Path(root).resolve()
        oracle = _read(root / "oracle-result.json")
        if (oracle.get("kind") != "jfg-phase95-oracle-poll-replay" or
                oracle.get("exit_code") != 0 or
                oracle.get("trace_complete") is not True or
                oracle.get("input_clock") != "controller-poll" or
                oracle.get("input_sha256") != contract["input_sha256"] or
                oracle.get("target_frame") != contract["target_frame"] or
                oracle.get("initial_flash_matches_candidate") is not True or
                oracle.get("oracle_initial_flash_sha256") !=
                    contract["initial_flash_sha256"]):
            raise ValueError(f"oracle replay does not match source contract: {root}")
        current_pins = {key: oracle.get(key) for key in ORACLE_PINS}
        if (any(not value for value in current_pins.values()) or
                current_pins["source_export_sha256"] != digest(source / "export-manifest.json") or
                any(current_pins[key] != contract[key] for key in
                    ("rom_sha256", "emulator_sha256", "config_sha256",
                     "runtime_sha256"))):
            raise ValueError("oracle replay provenance pins are incomplete or stale")
        if pins is None:
            pins = current_pins
        elif pins != current_pins:
            raise ValueError("oracle repeat pin set changed")
        input_polls = []
        with (root / "checkpoints.tsv").open(encoding="utf-8") as stream:
            for line in stream:
                if line.startswith("input-poll\t"):
                    fields = line.rstrip("\n").split("\t")
                    if len(fields) < 4:
                        raise ValueError("malformed oracle input-poll row")
                    input_polls.append(int(fields[3]))
        if input_polls != list(range(contract["controller_polls"])):
            raise ValueError("oracle did not consume the full selected input path")
        for item in contract["checkpoints"]:
            capture = root / f"checkpoint-{item['frame']:06d}.rdram"
            if digest(capture) != item["rdram_sha256"]:
                raise ValueError(f"oracle checkpoint {item['frame']} differs: {root}")
        if oracle.get("final_rdram_sha256") != contract["checkpoints"][-1]["rdram_sha256"]:
            raise ValueError("oracle final RDRAM differs from source")
        details.append({"root": str(root),
                        "oracle_result_sha256": digest(root / "oracle-result.json"),
                        "final_rdram_sha256": oracle["final_rdram_sha256"]})
    return {"all_match": True, "repeat_count": len(details),
            "pin_set": pins, "repeats": details,
            "intermediate_checkpoint_count": len(contract["checkpoints"]) - 1}


def verify(source, scenario_result, output, emulator, rom, rom_sha256,
           executable, *, repeats=3, checkpoint_frames=(), checkpoint_states=(),
           oracle_existing=(), native_existing=None, timeout=1800):
    source, output, emulator, rom, executable = map(
        lambda path: Path(path).resolve(),
        (source, output, emulator, rom, executable))
    if output.exists():
        raise FileExistsError(output)
    if type(repeats) is not int or not 1 <= repeats <= 10:
        raise ValueError("repeats must be 1..10")
    if type(timeout) is not int or not 1 <= timeout <= 3600:
        raise ValueError("timeout must be 1..3600 seconds")
    if oracle_existing and len(oracle_existing) != repeats:
        raise ValueError("existing oracle roots must equal the declared repeat count")
    contract = source_contract(source, scenario_result, emulator, rom,
                               rom_sha256, checkpoint_frames, checkpoint_states)
    output.mkdir(parents=True)
    objective = {"kind": "jfg-phase95-generic-route-verification", "schema": 1,
                 "acceptance": False, "contract": contract,
                 "repeats_requested": repeats, "native_executable_sha256": digest(executable),
                 "rom_sha256": rom_sha256,
                 "alignment_status": "not_verified",
                 "native_pak_equivalence": "not_verified"}
    (output / "verification-objective.json").write_text(json.dumps(objective, indent=2) + "\n")
    started = time.monotonic()
    try:
        roots = [Path(path).resolve() for path in oracle_existing] if oracle_existing else []
        if not roots:
            for index in range(repeats):
                root = output / f"oracle-repeat-{index + 1:02d}"
                oracle_replay(root, emulator, rom, rom_sha256, source,
                              checkpoints=[item["frame"] for item in contract["checkpoints"]],
                              timeout=timeout)
                roots.append(root)
        oracle = audit_oracle_runs(source, contract, roots)
        (output / "oracle-repeat-audit.json").write_text(json.dumps(oracle, indent=2) + "\n")
        native_root = Path(native_existing).resolve() if native_existing else output / "native"
        if native_existing is None:
            native_replay(source, native_root, executable, rom, rom_sha256,
                          timeout=timeout, poll_trace=True)
        native = _read(native_root / "native-result.json")
        native_objective = _read(native_root / "native-objective.json")
        if (native.get("kind") != "jfg-phase95-native-selected-poll-replay" or
                digest(native_root / "controller.input") != contract["input_sha256"] or
                native_objective.get("input_sha256") != contract["input_sha256"] or
                native_objective.get("initial_flash_sha256") !=
                    contract["initial_flash_sha256"] or
                native_objective.get("initial_pak_sha256") !=
                    contract["initial_pak_sha256"] or
                native.get("input_sha256") != contract["input_sha256"] or
                native.get("initial_flash_sha256") != contract["initial_flash_sha256"] or
                native.get("initial_pak_sha256") != contract["initial_pak_sha256"] or
                native.get("executable_sha256") != objective["native_executable_sha256"] or
                native.get("rom_sha256") != rom_sha256 or
                native.get("target_retraces") != contract["target_frame"] or
                native.get("exit_code") != 0 or
                native.get("probe_target_reached") is not True):
            raise ValueError("native replay does not match bounded source contract")
        poll_report = None
        if (native_root / "controller-polls.tsv").is_file():
            poll_report = poll_compare(source, roots[0], native_root,
                                       output / "poll-comparison.json")
        result = {**objective, "completed": True,
                  "elapsed_seconds": time.monotonic() - started,
                  "oracle": oracle, "native_run": str(native_root),
                  "native_result_sha256": digest(native_root / "native-result.json"),
                  "native_final_flash_sha256": digest(native_root / "replay.flash"),
                  "native_final_pak_sha256": digest(native_root / "replay.pak"),
                  "native_reached_target": True,
                  "native_controller_polls": native.get("observed_controller_polls"),
                  "post_eof_neutral_polls": native.get("post_eof_neutral_polls"),
                  "input_route_complete": native.get("input_route_complete"),
                  "endpoint_poll_counts_match": (
                      native.get("observed_controller_polls") == contract["controller_polls"]),
                  "poll_comparison": poll_report,
                  "native_parity_verified": False,
                  "first_validated_gameplay_divergence": None,
                  "limitations": "native/oracle poll and update boundaries plus Pak equivalence remain unvalidated"}
        (output / "verification-result.json").write_text(json.dumps(result, indent=2) + "\n")
        return result
    except Exception as error:
        triage = None
        triage_error = None
        native_root = Path(native_existing).resolve() if native_existing else output / "native"
        if native_existing is None and (native_root / "native-result.json").is_file():
            try:
                triage = failure_triage(source, native_root, output / "native-failure-triage",
                                        executable, rom, rom_sha256)
            except (OSError, ValueError, RuntimeError) as caught:
                triage_error = f"{type(caught).__name__}: {caught}"
        failure = {**objective, "completed": False,
                   "elapsed_seconds": time.monotonic() - started,
                   "classification": type(error).__name__, "detail": str(error),
                   "native_failure_triage": triage,
                   "native_failure_triage_error": triage_error}
        (output / "verification-failure.json").write_text(json.dumps(failure, indent=2) + "\n")
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("scenario_result", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--checkpoint-frame", type=int, action="append", default=[])
    parser.add_argument("--checkpoint-state", action="append", default=[],
                        metavar="FRAME:SHA256",
                        help="select one observed RDRAM state when trials share a frame")
    parser.add_argument("--oracle-existing", type=Path, action="append", default=[])
    parser.add_argument("--native-existing", type=Path)
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    selected = []
    for value in args.checkpoint_state:
        frame, separator, hash_value = value.partition(":")
        if not separator or not frame.isdecimal() or SHA256.fullmatch(hash_value) is None:
            parser.error("checkpoint-state must be FRAME:lowercase-SHA256")
        selected.append({"frame": int(frame), "rdram_sha256": hash_value})
    result = verify(args.source, args.scenario_result, args.output,
                    args.emulator, args.rom, args.rom_sha256, args.executable,
                    repeats=args.repeats, checkpoint_frames=args.checkpoint_frame,
                    checkpoint_states=selected,
                    oracle_existing=args.oracle_existing,
                    native_existing=args.native_existing, timeout=args.timeout)
    print(json.dumps({"completed": result["completed"],
                      "oracle_repeats_match": result["oracle"]["all_match"],
                      "endpoint_poll_counts_match": result["endpoint_poll_counts_match"],
                      "native_parity_verified": result["native_parity_verified"]}))


if __name__ == "__main__":
    main()
