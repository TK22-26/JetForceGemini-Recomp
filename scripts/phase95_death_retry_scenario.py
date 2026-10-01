"""Complete natural Goldwood damage, death and retry from a sealed frontier."""
import argparse
import json
from pathlib import Path
import time

from scripts.phase95_bridge import Action, Worker
from scripts.phase95_death_probe import probe as death_probe
from scripts.phase95_navigation import distance
from scripts.phase95_observation import ObservationError
from scripts.phase95_retry_probe import observe


def run(worker):
    objective = {"kind": "jfg-phase95-goldwood-death-retry-scenario",
                 "schema": 1, "acceptance": False,
                 "source_level": 21,
                 "damage": "natural in-game damage with neutral input; exact source unverified",
                 "max_damage_intervals": 120, "post_zero_intervals": 30,
                 "retry_button": "A", "retry_press_frames": 12,
                 "completion": "zero health, input-triggered player loss, three stable level-21 playerBoy observations with restored health and relocated spawn",
                 "limitations": "checkpoint-resumed diagnostic; not a ten-seed Goldwood job"}
    (worker.root / "death-retry-objective.json").write_text(json.dumps(objective, indent=2) + "\n")
    started = time.monotonic()
    try:
        death = death_probe(worker, max_steps=120, unchanged_budget=30,
                            post_depletion_steps=30)
        if (not death["completed"] or not death["health_depleted_observed"] or
                len(death["after_zero"]) != 30 or
                death["after_zero"][-1]["health_raw"] != 0 or
                death["after_zero"][-1]["level"] != 21):
            raise ObservationError("natural damage did not reach stable zero-health frontier")
        worker.checkpoint("save", "d1")
        sealed = observe(worker, "retry", "zero-health-sealed")
        if sealed["health_raw"] != 0 or sealed["player_name"] != "playerBoy":
            raise ObservationError("retry frontier lost zero-health player")
        worker.act(Action(12, buttons=0x8000))
        pressed = observe(worker, "retry", "a-pressed")
        worker.act(Action(120))
        departed = observe(worker, "retry", "loading")
        if departed["player"] is not None:
            raise ObservationError("A retry did not leave the defeated player state")
        arrivals = []
        for index in range(10):
            worker.act(Action(120))
            current = observe(worker, "retry", f"arrival-{index + 1}")
            arrivals.append(current)
            if len(arrivals) >= 3 and all(
                    item["mode"] == 16 and item["level"] == 21 and
                    item["player_name"] == "playerBoy" and
                    item["health_raw"] is not None and item["health_raw"] > 0 and
                    distance(item["position"], sealed["position"]) > 100
                    for item in arrivals[-3:]):
                break
        else:
            raise ObservationError("retry did not restore a stable positive-health player")
        worker.checkpoint("save", "d2")
        worker.observe()
        summary = {**objective, "completed": True,
                   "elapsed_seconds": time.monotonic() - started,
                   "health_depleted_observed": True, "death_verified": True,
                   "retry_verified": True, "intervention_count": 0,
                   "death_frame": death["last_observation"]["frame"],
                   "zero_health_sealed_frame": sealed["frame"],
                   "retry_input_frame": pressed["frame"],
                   "player_absent_frame": departed["frame"],
                   "arrival_frames": [item["frame"] for item in arrivals[-3:]],
                   "verification_checkpoints": [
                       {"name": name, "frame": item["frame"],
                        "rdram_sha256": item["rdram_sha256"]}
                       for name, item in (
                           ("health-zero", death["last_observation"]),
                           ("zero-health-sealed", sealed),
                           ("retry-a-pressed", pressed),
                           ("player-departed", departed),
                           *((f"stable-arrival-{index}", item)
                             for index, item in enumerate(arrivals[-3:], 1)))],
                   "restored_health_raw": arrivals[-1]["health_raw"],
                   "respawn_position": arrivals[-1]["position"],
                   "frontier_checkpoint": "d2"}
        (worker.root / "death-retry-result.json").write_text(json.dumps(summary, indent=2) + "\n")
        return summary
    except BaseException as error:
        failure = {**objective, "completed": False,
                   "elapsed_seconds": time.monotonic() - started,
                   "classification": type(error).__name__, "detail": str(error)}
        (worker.root / "death-retry-failure.json").write_text(json.dumps(failure, indent=2) + "\n")
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    args = parser.parse_args()
    with Worker(args.output, args.emulator, args.rom,
                Path(__file__).with_name("phase95_bizhawk_bridge.lua"),
                args.rom_sha256) as worker:
        worker.observe()
        worker.import_checkpoint(args.checkpoint)
        run(worker)


if __name__ == "__main__":
    main()
