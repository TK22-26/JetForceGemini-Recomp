"""Compose reviewed closed-loop south waypoints from the earlier level-47 fork.

This is not controller-input playback. Each waypoint uses the live observation
and bounded lookahead controller, with pinned proposals and frontier checks.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import time

from scripts.phase95_bridge import Action, Worker
from scripts.phase95_goldwood_scenario import Stage, run as run_south
from scripts.phase95_navigation import navigate
from scripts.phase95_observation import decode, ObservationError
from scripts.phase95_surface_follow import Segment, follow


SEGMENTS = (
    ("actor-prefix-a", "phase95-south-actor-prefix-20260922a", 0, 8, False, 8),
    ("actor-prefix-b", "phase95-south-actor-prefix-20260922b", 0, 20, False, 20),
    ("actor-prefix-c", "phase95-south-actor-prefix-20260922c", 0, 1, False, 1),
    ("south-jump", "phase95-south-jump-20260922a", 0, 1, True, 1),
    ("preserved-step", "phase95-south-preserved-route-20260922a", 1, 1, False, 2),
    ("correct-jump", "phase95-south-correct-jump-20260922a", 2, 1, True, 3),
    ("lower-route", "phase95-south-lower-route-20260922a", 0, 1, False, 2),
    ("lower-floor", "phase95-south-lower-floor-20260922a", 0, 13, False, 13),
    ("short-jump-a", "phase95-south-short-jump-20260922a", 13, 1, True, 14),
    ("short-jump-b", "phase95-south-short-jump-20260922b", 14, 8, True, 22),
    ("short-jump-c", "phase95-south-short-jump-20260922c", 22, 8, True, 30),
    ("short-jump-d", "phase95-south-short-jump-20260922d", 30, 8, True, 38),
    ("short-jump-e", "phase95-south-short-jump-20260922e", 38, 8, True, 46),
    ("short-jump-f", "phase95-south-short-jump-20260922f", 46, 8, True, 54),
    ("short-jump-g", "phase95-south-short-jump-20260922g", 54, 3, True, 57),
)


def validate_chain(settled_hash, endpoint_hashes, entry_hashes):
    if len(endpoint_hashes) != len(SEGMENTS) or len(entry_hashes) != len(SEGMENTS):
        raise ValueError("incomplete reviewed south lineage")
    for index, entry_hash in enumerate(entry_hashes):
        predecessor = settled_hash if index == 0 else endpoint_hashes[index - 1]
        if entry_hash != predecessor:
            raise ValueError(f"reviewed south segment {index} does not join its predecessor")


def run(worker, private_root, *, stop_after=None, start_segment=0):
    if type(start_segment) is not int or not 0 <= start_segment < len(SEGMENTS):
        raise ValueError("invalid south-prefix start segment")
    if stop_after is not None and (type(stop_after) is not int or
                                   not start_segment <= stop_after <= len(SEGMENTS)):
        raise ValueError("invalid bounded south-prefix stage limit")
    private_root = Path(private_root).resolve()
    settled_manifest = private_root / "phase95-level47-movement-20260907a/checkpoint-a1.json"
    expected_settled = json.loads(settled_manifest.read_text())["rdram_sha256"]
    proposal_paths = [private_root / name / "surface-proposal.json"
                      for _, name, *_ in SEGMENTS]
    endpoint_paths = [private_root / source / f"checkpoint-{last:04x}c1.json"
                      for _, source, _, _, _, last in SEGMENTS]
    endpoint_hashes = [json.loads(path.read_text())["rdram_sha256"]
                       for path in endpoint_paths]
    entry_hashes = [json.loads((private_root / source / "import-lineage.json")
                               .read_text())["checkpoint"]["rdram_sha256"]
                    for _, source, *_ in SEGMENTS]
    validate_chain(expected_settled, endpoint_hashes, entry_hashes)
    objective = {"kind": "jfg-phase95-goldwood-common-south", "schema": 1,
                 "acceptance": False, "source_level": 47,
                 "settle_intervals": 5 if start_segment == 0 else 0,
                 "settled_rdram_sha256": expected_settled,
                 "segments": [{"name": segment[0], "proposal": str(path),
                               "proposal_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                               "resume_after": segment[2],
                               "max_waypoints": segment[3], "jump": segment[4],
                               "expected_last_waypoint": segment[5],
                               "reviewed_endpoint": str(endpoint),
                               "reviewed_rdram_sha256": endpoint_hash,
                               "reviewed_entry_rdram_sha256": entry_hash}
                              for segment, path, endpoint, endpoint_hash, entry_hash in
                              zip(SEGMENTS, proposal_paths, endpoint_paths,
                                  endpoint_hashes, entry_hashes)],
                 "start_segment": start_segment, "stop_after": stop_after,
                 "completion": "fifteen observed prefix segments then the verified south encounter/pickup scenario",
                 "limitations": "reviewed route segments; not dynamic unknown-path discovery or native parity"}
    (worker.root / "common-south-objective.json").write_text(json.dumps(objective, indent=2) + "\n")
    started = time.monotonic()
    completed = []
    try:
        if start_segment == 0:
            for _ in range(5):
                worker.act(Action(120))
                worker.observe()
            metadata, memory = worker.observe()
            state = decode(memory, sequence=metadata["sequence"],
                           player_pointer=metadata["player"])
            if (hashlib.sha256(memory).hexdigest() != expected_settled or
                    state.front_mode != 16 or state.player is None or
                    struct.unpack_from(">i", memory, 0xFB114)[0] != 47):
                raise ObservationError("common south settle did not match reviewed frontier")
            worker.checkpoint("save", "a1")
            worker.observe()
        else:
            name = SEGMENTS[start_segment][1]
            lineage = json.loads((private_root / name / "import-lineage.json").read_text())
            expected = lineage["checkpoint"]["rdram_sha256"]
            metadata, memory = worker.observe()
            if hashlib.sha256(memory).hexdigest() != expected:
                raise ObservationError("resumed south prefix does not match reviewed segment entry")
        for index, ((name, _, resume_after, count, jump, expected_last), proposal) in \
                enumerate(zip(SEGMENTS, proposal_paths)):
            if index < start_segment:
                continue
            if stop_after is not None and index >= stop_after:
                break
            stage = Stage(worker, 8 + index, "common-" + name)
            # The earliest reviewed proposal predates actor-identity pinning.
            # Recompute from the byte-identical settled state and require its
            # selected prefix to match before accepting this segment.
            source = {} if index == 0 else {"resume_proposal": proposal,
                                             "resume_after": resume_after}
            if name == "correct-jump":
                # This reviewed waypoint ends on the lower layer by design.
                # Its original sealed checkpoint is stronger evidence than the
                # generic follower's vertical-proximity guard permits.
                reviewed = json.loads(proposal.read_text())
                transition = navigate(Segment(stage, 3), "surface-waypoint",
                                      waypoint=reviewed["waypoints"][3],
                                      radius=30, max_steps=8, precision=True,
                                      jump=True, short_jump=False)
                _, transition_memory = worker.observe()
                expected = json.loads((private_root / "phase95-south-correct-jump-20260922a"
                                       / "checkpoint-0003c1.json").read_text())["rdram_sha256"]
                if hashlib.sha256(transition_memory).hexdigest() != expected:
                    raise ObservationError("correct-jump transition differs from reviewed state")
                result = {"waypoints_completed": 3,
                          "reviewed_layer_transition": transition}
            else:
                result = follow(stage, actor_name="MrHints2",
                                max_waypoints=count, jump=jump, **source)
            if index == 0:
                generated = json.loads((stage.root / "surface-proposal.json").read_text())
                reviewed = json.loads(proposal.read_text())
                if generated["waypoints"][:count + 1] != reviewed["waypoints"][:count + 1]:
                    raise ObservationError("recomputed early south route differs from reviewed prefix")
            if name == "lower-route":
                # The second waypoint intentionally drops onto the lower
                # surface. The generic follower rejects that vertical error,
                # so make the layer change an explicit reviewed behavior.
                reviewed = json.loads(proposal.read_text())
                transition = navigate(Segment(stage, 2), "surface-waypoint",
                                      waypoint=reviewed["waypoints"][2],
                                      radius=30, max_steps=8, precision=True)
                _, transition_memory = worker.observe()
                expected = json.loads((private_root / "phase95-south-lower-route-20260922a"
                                       / "checkpoint-0002c1.json").read_text())["rdram_sha256"]
                if hashlib.sha256(transition_memory).hexdigest() != expected:
                    raise ObservationError("lower-floor transition differs from reviewed state")
                result = {"waypoints_completed": 2, "follow": result,
                          "lower_layer_transition": transition}
            if result["waypoints_completed"] != expected_last:
                raise ObservationError(f"south prefix {name} stopped before reviewed frontier")
            metadata, memory = worker.observe()
            if hashlib.sha256(memory).hexdigest() != endpoint_hashes[index]:
                raise ObservationError(f"south prefix {name} differs from reviewed endpoint")
            item = {"index": index, "name": name, "frame": metadata["frame"],
                    "polls": metadata["polls"],
                    "rdram_sha256": hashlib.sha256(memory).hexdigest(),
                    "waypoints_completed": result["waypoints_completed"],
                    "artifact_root": str(stage.root.relative_to(worker.root))}
            completed.append(item)
            with (worker.root / "common-south-stages.jsonl").open("a") as stream:
                stream.write(json.dumps(item) + "\n")
            print(json.dumps({"common_south_stage": name,
                              "frame": item["frame"]}), flush=True)
        if stop_after is not None:
            summary = {**objective, "completed": False, "diagnostic_stop": True,
                       "segments_completed": len(completed),
                       "elapsed_seconds": time.monotonic() - started}
            (worker.root / "common-south-result.json").write_text(json.dumps(summary, indent=2) + "\n")
            return summary
        south = run_south(worker, proposal_paths[-1], resume_after=57)
        summary = {**objective, "completed": south["completed"],
                   "segments_completed": len(completed),
                   "elapsed_seconds": time.monotonic() - started,
                   "final_level": south["final_level"],
                   "final_rdram_sha256": south["final_rdram_sha256"],
                   "intervention_count": 0}
        (worker.root / "common-south-result.json").write_text(json.dumps(summary, indent=2) + "\n")
        return summary
    except BaseException as error:
        failure = {**objective, "completed": False,
                   "segments_completed": len(completed),
                   "elapsed_seconds": time.monotonic() - started,
                   "classification": type(error).__name__, "detail": str(error)}
        (worker.root / "common-south-failure.json").write_text(json.dumps(failure, indent=2) + "\n")
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--stop-after", type=int)
    parser.add_argument("--start-segment", type=int, default=0)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    args = parser.parse_args()
    with Worker(args.output, args.emulator, args.rom,
                Path(__file__).with_name("phase95_bizhawk_bridge.lua"),
                args.rom_sha256) as worker:
        worker.observe()
        worker.import_checkpoint(args.checkpoint)
        run(worker, args.private_root, stop_after=args.stop_after,
            start_segment=args.start_segment)


if __name__ == "__main__":
    main()
