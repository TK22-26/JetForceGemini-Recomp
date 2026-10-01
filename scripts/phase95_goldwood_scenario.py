"""Run the bounded Goldwood south encounter and health-pickup route in one worker.

This checkpoint-resumed scenario is not the full Phase 9.5 milestone-B gate:
alternate destination, natural death/retry, ten seeds, and native parity remain.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import time

from scripts.phase95_bridge import Worker
from scripts.phase95_combat_probe import probe as combat_probe
from scripts.phase95_exit import cross
from scripts.phase95_inventory import weapon_stats
from scripts.phase95_observation import decode, ObservationError
from scripts.phase95_pickup_follow import follow as pickup_follow
from scripts.phase95_surface_follow import follow as surface_follow


SOUTH_EXIT_199 = "e92014a7926e1c617a936e5214b20075e306743472786ee373f7613f461bdd69"


class Stage:
    """Own one artifact directory and a disjoint hexadecimal checkpoint namespace."""
    def __init__(self, worker, index, name):
        self.worker, self.prefix = worker, f"{index:x}"
        self.root = worker.root / f"stage-{index:02d}-{name}"
        self.root.mkdir(exist_ok=False)

    def observe(self):
        return self.worker.observe()

    def act(self, action):
        return self.worker.act(action)

    def checkpoint(self, operation, slot):
        return self.worker.checkpoint(operation, self.prefix + slot)


def group_state(memory, metadata):
    state = decode(memory, sequence=metadata["sequence"],
                   player_pointer=metadata["player"])
    if state.front_mode != 16 or state.player is None or \
            struct.unpack_from(">i", memory, 0xFB114)[0] != 47:
        raise ObservationError("south encounter lost level-47 player context")
    doors = [actor for actor in state.actors if actor.name == "Ftechdoor"]
    if len(doors) != 1:
        raise ObservationError("south encounter requires one Ftechdoor")
    stats = weapon_stats(memory, metadata)
    return {"galaxian_addresses": sorted(actor.address for actor in state.actors
                                          if actor.name == "Galaxian4"),
            "door_actor": doors[0].address,
            "door_y": doors[0].position[1],
            "pistol_kills": stats["kills"][0]}


def run(worker, proposal, *, resume_after=57):
    if not 1 <= resume_after <= 256:
        raise ValueError("invalid preserved route frontier")
    objective = {"kind": "jfg-phase95-goldwood-south-scenario",
                 "acceptance": False, "source_route": str(Path(proposal).resolve()),
                 "source_route_sha256": hashlib.sha256(Path(proposal).read_bytes()).hexdigest(),
                 "resume_after": resume_after,
                 "declared_stages": [
                     "MrHints2 dialogue and live-actor route",
                     "three ordinary pistol kills and door opening",
                     "declared level-199 exit approach",
                     "level 199 intermediate then level 21 playerBoy arrival",
                     "exact one-unit HealthPowerup collection"],
                 "limitations": "one checkpoint-resumed route; not ten seeded jobs or native parity"}
    (worker.root / "scenario-objective.json").write_text(json.dumps(objective, indent=2) + "\n")
    stages = []
    started = time.monotonic()

    def record(index, name, stage, result):
        metadata, memory = worker.observe()
        item = {"stage": index, "name": name, "result": result,
                "rdram_sha256": hashlib.sha256(memory).hexdigest(),
                "frame": metadata["frame"], "polls": metadata["polls"],
                "player": metadata["player"],
                "level": struct.unpack_from(">i", memory, 0xFB114)[0],
                "artifact_root": str(stage.root.relative_to(worker.root))}
        stages.append(item)
        with (worker.root / "scenario-stages.jsonl").open("a") as stream:
            stream.write(json.dumps(item) + "\n")
        print(json.dumps({"scenario_stage": name, "level": item["level"],
                          "frame": item["frame"]}), flush=True)
        return metadata, memory

    try:
        stage = Stage(worker, 0, "hint-route")
        result = surface_follow(stage, actor_name="MrHints2", max_waypoints=8,
                                jump=True, resume_proposal=proposal,
                                resume_after=resume_after)
        if not (result["completed"] and result["actor_proximity_verified"] and
                result["interaction_verified"]):
            raise ObservationError("south hint route did not verify dialogue and proximity")
        metadata, memory = record(0, "hint-route", stage, result)
        initial_group = group_state(memory, metadata)
        if len(initial_group["galaxian_addresses"]) != 3 or initial_group["door_y"] > 5:
            raise ObservationError("south encounter baseline is not three actors behind a closed door")

        for index in range(1, 4):
            stage = Stage(worker, index, f"combat-{index}")
            result = combat_probe(stage)
            if not result["completed"] or not result["effect"]["encounter_kill_verified"]:
                raise ObservationError(f"combat stage {index} did not verify a Galaxian kill")
            metadata, memory = record(index, f"combat-{index}", stage, result)
            group = group_state(memory, metadata)
            if (len(group["galaxian_addresses"]) != 3 - index or
                    group["pistol_kills"] != initial_group["pistol_kills"] + index or
                    group["door_actor"] != initial_group["door_actor"]):
                raise ObservationError("south encounter group state differs from declared kill sequence")
        if group["door_y"] < initial_group["door_y"] + 60:
            raise ObservationError("three kills did not open the south door")

        stage = Stage(worker, 4, "south-exit-approach")
        result = surface_follow(stage, exit_id=SOUTH_EXIT_199,
                                max_waypoints=8, jump=True)
        if not result["completed"] or result["exit_crossed"]:
            raise ObservationError("south exit approach did not verify its landmark")
        record(4, "south-exit-approach", stage, result)

        stage = Stage(worker, 5, "south-crossing")
        result = cross(stage, exit_id=SOUTH_EXIT_199, arrival_level=21)
        if (not result["completed"] or result["required_intermediate_level"] != 199 or
                result["final_observation"]["player_name"] != "playerBoy"):
            raise ObservationError("south crossing did not verify the declared two-stage arrival")
        record(5, "south-crossing", stage, result)

        stage = Stage(worker, 6, "health-pickup")
        result = pickup_follow(stage, max_waypoints=16, jump=True)
        if not result["completed"]:
            raise ObservationError("south health pickup was not verified")
        record(6, "health-pickup", stage, result)

        summary = {**objective, "completed": True, "stages_completed": len(stages),
                   "elapsed_seconds": time.monotonic() - started,
                   "final_level": stages[-1]["level"],
                   "final_rdram_sha256": stages[-1]["rdram_sha256"],
                   "intervention_count": 0,
                   "native_comparison": "not_run"}
        (worker.root / "scenario-result.json").write_text(json.dumps(summary, indent=2) + "\n")
        return summary
    except BaseException as error:
        failure = {**objective, "completed": False, "stages_completed": len(stages),
                   "elapsed_seconds": time.monotonic() - started,
                   "classification": type(error).__name__, "detail": str(error)}
        (worker.root / "scenario-failure.json").write_text(json.dumps(failure, indent=2) + "\n")
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--destination", choices=("south21", "east48"), default="south21")
    parser.add_argument("--proposal", type=Path, required=True,
                        help="declared source route for the selected destination")
    parser.add_argument("--upper-proposal", type=Path,
                        help="reviewed upper-deck route for east48")
    parser.add_argument("--east-finish-template", type=Path,
                        help="reviewed ordinary-input ground route for east48")
    parser.add_argument("--resume-after", type=int, default=57)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    parser.add_argument("--regression-bundle", action="store_true",
                        help="after the scenario, generate selected inputs, oracle repeats and native report")
    parser.add_argument("--native-executable", type=Path)
    parser.add_argument("--initial-flash", type=Path)
    parser.add_argument("--initial-pak", type=Path)
    parser.add_argument("--oracle-repeats", type=int, default=3)
    args = parser.parse_args()
    if args.destination == "east48" and args.regression_bundle:
        parser.error("the current regression bundle covers south21 only")
    if args.destination == "east48" and not all((args.upper_proposal,
                                                  args.east_finish_template)):
        parser.error("east48 requires upper proposal and finish template")
    if args.regression_bundle and not all((args.native_executable,
                                           args.initial_flash, args.initial_pak)):
        parser.error("regression bundle requires native executable and candidate initial flash/pak")
    with Worker(args.output, args.emulator, args.rom,
                Path(__file__).with_name("phase95_bizhawk_bridge.lua"),
                args.rom_sha256) as worker:
        worker.observe()
        worker.import_checkpoint(args.checkpoint)
        if args.destination == "south21":
            run(worker, args.proposal, resume_after=args.resume_after)
        else:
            from scripts.phase95_goldwood_east_scenario import run as run_east
            run_east(worker, args.proposal, args.upper_proposal,
                     args.east_finish_template)
    if args.regression_bundle:
        from scripts.phase95_regression_bundle import bundle
        bundle(args.output, args.output / "regression", args.emulator,
               args.rom, args.rom_sha256, args.native_executable,
               args.initial_flash, args.initial_pak,
               repeats=args.oracle_repeats)


if __name__ == "__main__":
    main()
