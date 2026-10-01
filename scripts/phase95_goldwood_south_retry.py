"""Resume a sealed common-south frontier, reach a live ant, and retry death.

The imported checkpoint carries the entire selected-input lineage back through
the common level-47 south route. This command runs the new continuation in a
single BizHawk worker; it does not claim native parity or unknown-path coverage.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import time

from scripts.phase95_ant_death_route import approach
from scripts.phase95_bridge import Worker
from scripts.phase95_death_retry_scenario import run as run_retry
from scripts.phase95_export_inputs import export
from scripts.phase95_observation import ObservationError


def validate_source(checkpoint):
    checkpoint = Path(checkpoint).resolve()
    if checkpoint.name != "checkpoint-6e1.json":
        raise ValueError("south retry requires the sealed health-pickup checkpoint")
    root = checkpoint.parent
    source = json.loads(checkpoint.read_text(encoding="utf-8"))
    common = json.loads((root / "common-south-result.json").read_text(encoding="utf-8"))
    south = json.loads((root / "scenario-result.json").read_text(encoding="utf-8"))
    hash_value = source.get("rdram_sha256")
    if (source.get("kind") != "jfg-phase95-checkpoint" or
            source.get("schema") != 1 or
            common.get("kind") != "jfg-phase95-goldwood-common-south" or
            common.get("completed") is not True or
            common.get("segments_completed") != 15 or
            common.get("final_level") != 21 or
            south.get("kind") != "jfg-phase95-goldwood-south-scenario" or
            south.get("completed") is not True or
            south.get("stages_completed") != 7 or
            south.get("final_level") != 21 or
            hash_value != common.get("final_rdram_sha256") or
            hash_value != south.get("final_rdram_sha256")):
        raise ValueError("checkpoint is not the completed common-south pickup frontier")
    return {"checkpoint": str(checkpoint),
            "checkpoint_manifest_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
            "source_rdram_sha256": hash_value,
            "source_frame": source.get("observation", {}).get("frame"),
            "source_polls": source.get("observation", {}).get("polls")}


def run(worker, checkpoint, *, max_waypoints=50):
    if type(max_waypoints) is not int or not 1 <= max_waypoints <= 50:
        raise ValueError("max_waypoints must be 1..50")
    source = validate_source(checkpoint)
    metadata, memory = worker.observe()
    if (hashlib.sha256(memory).hexdigest() != source["source_rdram_sha256"] or
            struct.unpack_from(">i", memory, 0xFB114)[0] != 21 or
            metadata.get("frame") != source["source_frame"] or
            metadata.get("polls") != source["source_polls"]):
        raise ObservationError("imported south frontier does not match sealed checkpoint")
    objective = {"kind": "jfg-phase95-goldwood-south-retry", "schema": 1,
                 "acceptance": False, "source": source,
                 "max_ant_waypoints": max_waypoints,
                 "completion": "common-south pickup lineage, live-ant exposure route, natural zero health, input-triggered level-21 retry",
                 "limitations": "checkpoint-resumed branch; native parity and ten-seed variability unverified"}
    (worker.root / "south-retry-objective.json").write_text(json.dumps(objective, indent=2) + "\n")
    started = time.monotonic()
    try:
        ant = approach(worker, max_waypoints=max_waypoints)
        if not ant["completed"] or ant["live_ant_count"] < 1:
            raise ObservationError("ant exposure route lost live BlueAnt context")
        retry = run_retry(worker)
        if not (retry["completed"] and retry["death_verified"] and
                retry["retry_verified"]):
            raise ObservationError("natural death/retry was not verified")
        metadata, memory = worker.observe()
        result = {**objective, "completed": True,
                  "elapsed_seconds": time.monotonic() - started,
                  "ant_approach": ant, "death_retry": retry,
                  "verification_checkpoints": [
                      {"name": "south-pickup-frontier",
                       "frame": source["source_frame"],
                       "rdram_sha256": source["source_rdram_sha256"]},
                      {"name": "ant-exposure-frontier",
                       "frame": ant["frontier_frame"],
                       "rdram_sha256": ant["frontier_rdram_sha256"]},
                      *retry["verification_checkpoints"]],
                  "final_frame": metadata["frame"], "final_polls": metadata["polls"],
                  "final_rdram_sha256": hashlib.sha256(memory).hexdigest(),
                  "intervention_count": 0}
        (worker.root / "south-retry-result.json").write_text(json.dumps(result, indent=2) + "\n")
        return result
    except BaseException as error:
        failure = {**objective, "completed": False,
                   "elapsed_seconds": time.monotonic() - started,
                   "classification": type(error).__name__, "detail": str(error)}
        (worker.root / "south-retry-failure.json").write_text(json.dumps(failure, indent=2) + "\n")
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    parser.add_argument("--max-waypoints", type=int, default=50)
    parser.add_argument("--initial-flash", type=Path,
                        help="candidate initial FlashRAM for native replay export")
    parser.add_argument("--initial-pak", type=Path,
                        help="candidate initial Pak state for native replay export")
    args = parser.parse_args()
    if (args.initial_flash is None) != (args.initial_pak is None):
        parser.error("initial flash and pak must be supplied together")
    validate_source(args.checkpoint)
    with Worker(args.output, args.emulator, args.rom,
                Path(__file__).with_name("phase95_bizhawk_bridge.lua"),
                args.rom_sha256) as worker:
        worker.observe()
        worker.import_checkpoint(args.checkpoint)
        result = run(worker, args.checkpoint, max_waypoints=args.max_waypoints)
    selected = export(args.output, args.output / "selected-input",
                      initial_flash=args.initial_flash, initial_pak=args.initial_pak)
    print(json.dumps({"completed": result["completed"],
                      "final_frame": result["final_frame"],
                      "final_rdram_sha256": result["final_rdram_sha256"],
                      "selected_input_sha256": selected["input_sha256"],
                      "controller_polls": selected["controller_polls"]}))


if __name__ == "__main__":
    main()
