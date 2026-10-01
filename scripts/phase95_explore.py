"""Bounded checkpoint graph search. Spatial pruning is heuristic, not reachability proof."""
import argparse
from dataclasses import asdict
import hashlib
import heapq
import json
import math
from pathlib import Path
import struct

from scripts.phase95_bridge import Action, Worker
from scripts.phase95_navigation import distance, jump_mask
from scripts.phase95_observation import decode, ObservationError
from scripts.phase95_world import inventory, select_exit


def cell(position, yaw, scale=60):
    if len(position) != 3 or not all(math.isfinite(value) for value in position):
        raise ObservationError("invalid exploration position")
    if type(scale) is not int or scale <= 0:
        raise ValueError("invalid exploration cell scale")
    return (*[math.floor(value / scale) for value in position], int(yaw) // 8192)


def search_priority(distance_to_exit, depth, outward_distance, mode):
    """Prefer measured exit progress, or a bounded outward detour on retry."""
    if mode == "coverage":
        return depth
    return (distance_to_exit + 5 * depth -
            (0.75 * outward_distance if mode == "detour" else 0))


def search(worker, exit_id, *, max_nodes=128, max_expansions=40, radius=65,
           proximity="3d", max_vertical_gap=None, jump=False,
           mode="distance"):
    if not 2 <= max_nodes <= 256 or not 1 <= max_expansions <= 100 or not 1 <= radius <= 100:
        raise ValueError("invalid exploration budget")
    if proximity not in ("3d", "horizontal") or (proximity == "horizontal" and
            (type(max_vertical_gap) not in (int, float) or
             not 1 <= max_vertical_gap <= 100)) or (proximity == "3d" and
            max_vertical_gap is not None):
        raise ValueError("invalid exploration proximity rule")
    if type(jump) is not bool:
        raise ValueError("jump search option must be boolean")
    if mode not in ("distance", "detour", "coverage"):
        raise ValueError("invalid exploration mode")

    def observe():
        metadata, memory = worker.observe()
        state = decode(memory, sequence=metadata["sequence"], player_pointer=metadata["player"] or None)
        if state.front_mode != 16 or state.player is None:
            raise ObservationError("exploration lost active player")
        return metadata, memory, state

    def observe_trial(expected_level):
        metadata, memory = worker.observe()
        observed_level = struct.unpack_from(">i", memory, 0xFB114)[0]
        if observed_level != expected_level:
            # A nearby exit can remove the departing actor before the hook's
            # player pointer changes. Classify the level transition first;
            # decoding that stale pointer would abort the whole search.
            return metadata, memory, None, observed_level
        state = decode(memory, sequence=metadata["sequence"],
                       player_pointer=metadata["player"] or None)
        if state.front_mode != 16 or state.player is None:
            raise ObservationError("exploration lost active player")
        return metadata, memory, state, observed_level

    metadata, memory, state = observe()
    level = struct.unpack_from(">i", memory, 0xFB114)[0]
    target_actor, identity = select_exit(memory, state.actors, level, exit_id)
    target = target_actor.position
    source_position = state.player.position
    jump_button = jump_mask(memory) if jump else None
    def gap(position):
        vertical = abs(position[1] - target[1])
        horizontal = math.hypot(position[0] - target[0], position[2] - target[2])
        near = (horizontal <= radius and vertical <= max_vertical_gap
                if proximity == "horizontal" else distance(position, target) <= radius)
        return (horizontal if proximity == "horizontal" else distance(position, target),
                vertical, near)

    objective = {"kind": "jfg-phase95-checkpoint-search", "acceptance": False,
                 "exit_identity": identity, "radius": radius, "max_nodes": max_nodes,
                 "max_expansions": max_expansions,
                 "proximity": proximity, "max_vertical_gap": max_vertical_gap,
                 "completion": ("player within horizontal radius and vertical tolerance of fixed exit landmark"
                                if proximity == "horizontal" else
                                "player within 3D radius of fixed exit landmark"),
                 "pruning": "60-unit spatial cells and eight yaw bins; "
                            "jump outcomes moving at least 10 units may use 15-unit cells; "
                            "incomplete search",
                 "action_policy": "60-frame moves; 30-frame moves within max(100, 4*radius); "
                                  "optional release/jump/settle trials near exit or "
                                  "after an ordinary move stalls below 20 horizontal units",
                 "jump_candidates": jump, "jump_button": jump_button}
    objective["search_mode"] = mode
    (worker.root / "search-objective.json").write_text(json.dumps(objective, indent=2))
    (worker.root / "world-inventory.json").write_text(json.dumps(inventory(memory, metadata["sequence"]), indent=2))
    nodes, visited, fine_visited, queue = [], set(), set(), []
    root_trials = 0
    root_transitions = []

    def add(parent, actions, metadata, memory, state):
        index = len(nodes)
        slot = f"a{index:04x}"
        worker.checkpoint("save", slot)
        saved, saved_memory, _ = observe()
        if saved_memory != memory or any(saved.get(key) != metadata.get(key)
                                         for key in ("frame", "polls", "player")):
            raise ObservationError("saving exploration node changed guest state")
        measured, vertical, _ = gap(state.player.position)
        node = {"id": index, "parent": parent, "slot": slot,
                "action": asdict(actions[0]) if actions and len(actions) == 1 else None,
                "depth": 0 if parent is None else nodes[parent]["depth"] + 1,
                "position": state.player.position, "yaw": state.player.yaw,
                "distance": measured, "vertical_gap": vertical,
                "sha256": hashlib.sha256(memory).hexdigest(),
                "counters": {key: metadata.get(key) for key in ("frame", "polls", "player")}}
        if actions and len(actions) > 1:
            node["actions"] = [asdict(action) for action in actions]
        nodes.append(node)
        visited.add(cell(state.player.position, state.player.yaw))
        fine_visited.add(cell(state.player.position, state.player.yaw, 15))
        outward = math.hypot(state.player.position[0] - source_position[0],
                             state.player.position[2] - source_position[2])
        priority = search_priority(node["distance"], node["depth"], outward, mode)
        heapq.heappush(queue, (priority, index))
        with (worker.root / "search-nodes.jsonl").open("a") as stream:
            stream.write(json.dumps(node) + "\n")
        return index

    def restore(node):
        worker.checkpoint("load", node["slot"])
        actual, raw, current = observe()
        if hashlib.sha256(raw).hexdigest() != node["sha256"] or any(
                actual.get(key) != value for key, value in node["counters"].items()):
            raise ObservationError("exploration checkpoint restore mismatch")
        return actual, raw, current

    def finish(index):
        route = []
        while nodes[index]["parent"] is not None:
            route.append(nodes[index])
            index = nodes[index]["parent"]
        route.reverse()
        restore(nodes[0])
        for node in route:
            actions = node.get("actions") or [node["action"]]
            for action in actions:
                worker.act(Action(**action))
                actual, raw, current = observe()
            if hashlib.sha256(raw).hexdigest() != node["sha256"] or any(
                    actual.get(key) != value for key, value in node["counters"].items()):
                raise ObservationError("selected exploration route failed exact replay")
            with (worker.root / "search-route.jsonl").open("a") as stream:
                stream.write(json.dumps({**node, "replayed_sequence": actual["sequence"]}) + "\n")
        worker.checkpoint("save", "c1")
        _, final_memory, _ = observe()
        result = {**objective, "completed": True, "route_steps": len(route),
                  "nodes": len(nodes), "replay_equal": True,
                  "final_rdram_sha256": hashlib.sha256(final_memory).hexdigest()}
        (worker.root / "search-result.json").write_text(json.dumps(result, indent=2))
        return result

    add(None, None, metadata, memory, state)
    directions = (
        (0, 60), (-60, 60), (60, 60), (-60, 0), (60, 0),
        (0, -60), (-60, -60), (60, -60))
    for expansion in range(max_expansions):
        if not queue:
            break
        _, index = heapq.heappop(queue)
        parent = nodes[index]
        if gap(parent["position"])[2]:
            return finish(index)
        print(json.dumps({"expansion": expansion, "node": index,
                          "distance": parent["distance"], "nodes": len(nodes)}), flush=True)
        frames = 30 if parent["distance"] <= max(100, 4 * radius) else 60
        candidates = [(Action(frames, x=x, y=y),) for x, y in directions]
        near_jump = jump and parent["distance"] <= max(160, 4 * radius)
        if near_jump:
            candidates.extend((Action(6), Action(12, buttons=jump_button, x=x, y=y),
                               Action(48, x=x, y=y)) for x, y in directions)
        for actions in candidates:
            if len(nodes) >= max_nodes:
                break
            if index == 0:
                root_trials += 1
            restore(parent)
            crossed_level = None
            for action in actions:
                worker.act(action)
                metadata, memory, state, observed_level = observe_trial(level)
                if state is None:
                    crossed_level = observed_level
                    break
            if crossed_level is not None:
                if index == 0:
                    root_transitions.append(crossed_level)
                with (worker.root / "search-trials.jsonl").open("a") as stream:
                    stream.write(json.dumps({
                        "parent": index, "actions": [asdict(item) for item in actions],
                        "sequence": metadata["sequence"],
                        "outcome": "incidental-level-transition",
                        "observed_level": crossed_level,
                        "near": False}) + "\n")
                continue
            measured, vertical, near = gap(state.player.position)
            novel = cell(state.player.position, state.player.yaw) not in visited
            movement = math.hypot(state.player.position[0] - parent["position"][0],
                                  state.player.position[2] - parent["position"][2])
            fine_jump_novel = (jump and len(actions) > 1 and movement >= 10 and
                               cell(state.player.position, state.player.yaw, 15)
                               not in fine_visited)
            stalled_jump = (jump and not near_jump and len(actions) == 1 and
                            movement < 20)
            if stalled_jump:
                action = actions[0]
                candidates.append((Action(6), Action(12, buttons=jump_button,
                                                   x=action.x, y=action.y),
                                   Action(48, x=action.x, y=action.y)))
            with (worker.root / "search-trials.jsonl").open("a") as stream:
                stream.write(json.dumps({"parent": index,
                    "action": asdict(actions[0]) if len(actions) == 1 else None,
                    "actions": [asdict(action) for action in actions],
                    "sequence": metadata["sequence"], "position": state.player.position,
                    "distance": measured, "vertical_gap": vertical,
                    "novel_cell": novel, "near": near,
                    "fine_jump_novel": fine_jump_novel,
                    "stalled_jump_candidate": stalled_jump}) + "\n")
            if novel or near or fine_jump_novel:
                child = add(index, actions, metadata, memory, state)
                if near:
                    return finish(child)
        if len(nodes) >= max_nodes:
            break
    if len(nodes) == 1 and root_trials > 0 and len(root_transitions) == root_trials:
        (worker.root / "search-failure.json").write_text(json.dumps({
            "kind": "jfg-phase95-search-incomplete", "nodes": 1,
            "reason": "source checkpoint auto-transitions before explored move",
            "search_mode": mode,
            "source_auto_transition": True,
            "observed_levels": sorted(set(root_transitions)),
            "trials": root_trials, "unreachable": False}) + "\n")
        raise ObservationError("source checkpoint auto-transitions; alternate source required")
    (worker.root / "search-failure.json").write_text(json.dumps({
        "kind": "jfg-phase95-search-incomplete", "nodes": len(nodes),
        "search_mode": mode,
        "reason": "bounded search exhausted", "unreachable": False}) + "\n")
    raise ObservationError("bounded exploration incomplete; not proof of unreachable exit")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--exit-id", required=True)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    parser.add_argument("--max-nodes", type=int, default=128)
    parser.add_argument("--max-expansions", type=int, default=40)
    parser.add_argument("--radius", type=int, default=65)
    parser.add_argument("--proximity", choices=("3d", "horizontal"), default="3d")
    parser.add_argument("--max-vertical-gap", type=int)
    parser.add_argument("--jump", action="store_true")
    parser.add_argument("--mode", choices=("distance", "detour", "coverage"),
                        default="distance")
    args = parser.parse_args()
    with Worker(args.output, args.emulator, args.rom,
                Path(__file__).with_name("phase95_bizhawk_bridge.lua"), args.rom_sha256) as worker:
        worker.observe()
        worker.import_checkpoint(args.checkpoint)
        search(worker, args.exit_id, max_nodes=args.max_nodes,
               max_expansions=args.max_expansions, radius=args.radius,
               proximity=args.proximity, max_vertical_gap=args.max_vertical_gap,
               jump=args.jump, mode=args.mode)


if __name__ == "__main__":
    main()
