"""Bounded Goldwood east branch from the common level-47 checkpoint."""
import hashlib
import json
from pathlib import Path
import struct
import time

from scripts.phase95_branch48_finish import EAST_EXIT_48, finish
from scripts.phase95_bridge import Action
from scripts.phase95_goldwood_scenario import Stage
from scripts.phase95_navigation import navigate
from scripts.phase95_observation import decode, ObservationError
from scripts.phase95_surface_follow import follow


FIRST_ROUTE_WAYPOINTS = 43
UPPER_ROUTE_WAYPOINTS = 18


def run(worker, proposal, upper_proposal, finish_template):
    proposal = Path(proposal).resolve()
    raw_proposal = proposal.read_bytes()
    preserved = json.loads(raw_proposal)
    points = preserved.get("waypoints")
    if (preserved.get("kind") != "jfg-phase95-surface-proposal" or
            preserved.get("target_identity", {}).get("id") != EAST_EXIT_48 or
            not isinstance(points, list) or len(points) <= FIRST_ROUTE_WAYPOINTS + 1):
        raise ValueError("east branch requires the reviewed common-frontier proposal")
    upper_point = points[FIRST_ROUTE_WAYPOINTS + 1]
    upper_proposal = Path(upper_proposal).resolve()
    upper_raw = upper_proposal.read_bytes()
    upper = json.loads(upper_raw)
    upper_points = upper.get("waypoints")
    if (upper.get("kind") != "jfg-phase95-surface-proposal" or
            upper.get("target_identity", {}).get("id") != EAST_EXIT_48 or
            not isinstance(upper_points, list) or len(upper_points) <= UPPER_ROUTE_WAYPOINTS):
        raise ValueError("east branch requires the reviewed upper-deck route")
    finish_template = Path(finish_template).resolve()
    finish_digest = hashlib.sha256(finish_template.read_bytes()).hexdigest()
    objective = {"kind": "jfg-phase95-goldwood-east-scenario", "schema": 1,
                 "acceptance": False, "source_level": 47, "destination_level": 48,
                 "exit_id": EAST_EXIT_48, "source_route": str(proposal),
                 "source_route_sha256": hashlib.sha256(raw_proposal).hexdigest(),
                 "upper_route": str(upper_proposal),
                 "upper_route_sha256": hashlib.sha256(upper_raw).hexdigest(),
                 "ground_route": str(finish_template),
                 "ground_route_sha256": finish_digest,
                 "declared_stages": [
                     "closed-loop east route through waypoint 43",
                     "upper-deck jump at waypoint 44",
                     "neutral upper-deck settling and checkpoint",
                     "west-shift onto reviewed upper-deck route",
                     "upper-deck descent through waypoint 18",
                     "reviewed ground approach and stable level-48 crossing"],
                 "limitations": "alternate destination only; no encounter, pickup, death/retry, seeds or native parity"}
    (worker.root / "scenario-objective.json").write_text(json.dumps(objective, indent=2) + "\n")
    started = time.monotonic()
    stages = []

    def record(index, name, stage, result):
        metadata, memory = worker.observe()
        item = {"stage": index, "name": name, "result": result,
                "rdram_sha256": hashlib.sha256(memory).hexdigest(),
                "frame": metadata["frame"], "polls": metadata["polls"],
                "level": struct.unpack_from(">i", memory, 0xFB114)[0],
                "artifact_root": str(stage.root.relative_to(worker.root))}
        stages.append(item)
        with (worker.root / "scenario-stages.jsonl").open("a") as stream:
            stream.write(json.dumps(item) + "\n")
        print(json.dumps({"east_stage": name, "frame": item["frame"],
                          "level": item["level"]}), flush=True)
        return metadata, memory

    def player_context():
        metadata, memory = worker.observe()
        state = decode(memory, sequence=metadata["sequence"],
                       player_pointer=metadata["player"])
        if state.front_mode != 16 or state.player is None or \
                struct.unpack_from(">i", memory, 0xFB114)[0] != 47:
            raise ObservationError("east scenario lost level-47 player context")
        return state.player.position

    try:
        player_context()
        stage = Stage(worker, 0, "east-shared-route")
        result = follow(stage, exit_id=EAST_EXIT_48,
                        resume_proposal=proposal, resume_after=0,
                        max_waypoints=FIRST_ROUTE_WAYPOINTS, jump=True)
        if result["completed"] or result["waypoints_completed"] != FIRST_ROUTE_WAYPOINTS:
            raise ObservationError("east shared route did not reach its declared upper-deck frontier")
        record(0, "east-shared-route", stage, result)

        stage = Stage(worker, 1, "east-upper-jump")
        result = navigate(stage, "surface-waypoint", waypoint=upper_point,
                          radius=30, max_steps=8, precision=True, jump=True)
        position = player_context()
        if position[1] < upper_point[1] + 10:
            raise ObservationError("east jump did not reach the observed upper layer")
        record(1, "east-upper-jump", stage,
               {"navigation": result, "target": upper_point,
                "upper_layer_verified": True, "player_position": position})

        stage = Stage(worker, 2, "east-upper-settle")
        positions = []
        for _ in range(4):
            stage.act(Action(24))
            positions.append(player_context())
        if positions[-1][1] < upper_point[1] + 20:
            raise ObservationError("east upper deck did not remain supported after settling")
        stage.checkpoint("save", "e1")
        record(2, "east-upper-settle", stage,
               {"neutral_intervals": 4, "positions": positions,
                "checkpoint": stage.prefix + "e1"})

        stage = Stage(worker, 3, "east-upper-westshift")
        result = navigate(stage, "surface-waypoint", waypoint=upper_points[0],
                          radius=25, max_steps=12, precision=True)
        record(3, "east-upper-westshift", stage, result)

        stage = Stage(worker, 4, "east-upper-descent")
        result = follow(stage, exit_id=EAST_EXIT_48,
                        resume_proposal=upper_proposal, resume_after=0,
                        max_waypoints=UPPER_ROUTE_WAYPOINTS, jump=False)
        if result["waypoints_completed"] < UPPER_ROUTE_WAYPOINTS:
            raise ObservationError("east upper route stopped before declared ground approach")
        record(4, "east-upper-descent", stage, result)

        stage = Stage(worker, 5, "east-ground-crossing")
        result = finish(stage, route_template=finish_template)
        if not result["completed"] or result["crossing"]["destination_level"] != 48:
            raise ObservationError("east ground approach did not complete crossing")
        record(5, "east-ground-crossing", stage, result)
        summary = {**objective, "completed": True,
                   "elapsed_seconds": time.monotonic() - started,
                   "stages_completed": len(stages),
                   "final_level": stages[-1]["level"],
                   "final_rdram_sha256": stages[-1]["rdram_sha256"],
                   "intervention_count": 0, "native_comparison": "not_run"}
        (worker.root / "scenario-result.json").write_text(json.dumps(summary, indent=2) + "\n")
        return summary
    except BaseException as error:
        failure = {**objective, "completed": False, "stages_completed": len(stages),
                   "elapsed_seconds": time.monotonic() - started,
                   "classification": type(error).__name__, "detail": str(error)}
        (worker.root / "scenario-failure.json").write_text(json.dumps(failure, indent=2) + "\n")
        raise
