#!/usr/bin/env python3
"""Build bounded Phase 9 scenario replays from an approved gameplay route."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


HEADER = "jfg-phase8-input-v2"
ROUTE_END = 29600
SAVE_COMMIT_INPUT_END = 29581
COMBAT_PROBE_PREFIX_END = 8100
COLD_BOOT_GAMEPLAY_END = 18000
COLD_BOOT_GAMEPLAY_ACTION_START = 18120


class RouteError(ValueError):
    """The source replay cannot produce the canonical Phase 9 route."""


@dataclass(frozen=True)
class Event:
    first: int
    last: int
    connected: int
    buttons: int
    stick_x: int
    stick_y: int

    def row(self) -> str:
        return (
            f"{self.first},{self.last},{self.connected},"
            f"{self.buttons:04x},{self.stick_x},{self.stick_y}"
        )


def load_replay(path: Path) -> list[Event]:
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except OSError as error:
        raise RouteError(f"unable to read source replay: {error}") from error
    if not lines or lines[0] != HEADER:
        raise RouteError("invalid source replay header")
    events: list[Event] = []
    for line in lines[1:]:
        fields = line.split(",")
        if len(fields) != 6:
            raise RouteError("invalid source replay record")
        try:
            event = Event(
                int(fields[0]),
                int(fields[1]),
                int(fields[2]),
                int(fields[3], 16),
                int(fields[4]),
                int(fields[5]),
            )
        except ValueError as error:
            raise RouteError("invalid source replay value") from error
        if (
            event.first < 0
            or event.first >= event.last
            or event.connected not in {0, 1}
            or not 0 <= event.buttons <= 0xFFFF
            or not -128 <= event.stick_x <= 127
            or not -128 <= event.stick_y <= 127
            or (events and event.first < events[-1].last)
        ):
            raise RouteError("invalid source replay ordering")
        events.append(event)
    if not events:
        raise RouteError("source replay is empty")
    return events


def route_prefix(source: list[Event], end: int) -> list[Event]:
    result: list[Event] = []
    for event in source:
        if event.first >= end:
            break
        result.append(
            Event(
                event.first,
                min(event.last, end),
                event.connected,
                event.buttons,
                event.stick_x,
                event.stick_y,
            )
        )
    return result


def canonical_route(source: list[Event]) -> list[Event]:
    result = route_prefix(source, ROUTE_END)
    if not result or result[-1].last < SAVE_COMMIT_INPUT_END:
        raise RouteError("source replay ends before the persistent-save route")
    return result


def cold_boot_to_gameplay_probe_route() -> list[Event]:
    """Create a new save, clear the intro gates, and enter Goldwood gameplay."""
    result = [
        Event(1820, 1840, 1, 0x1000, 0, 0),
        Event(2050, 2070, 1, 0x8000, 0, 0),
        Event(2600, 2620, 1, 0x8000, 0, 0),
        Event(3000, 3020, 1, 0x8000, 0, 0),
        Event(3200, 3204, 1, 0x0000, 0, -80),
        Event(3400, 3404, 1, 0x0000, 0, -80),
        Event(3600, 3604, 1, 0x0000, 0, -80),
        Event(3800, 3804, 1, 0x0000, 80, 0),
        Event(4000, 4004, 1, 0x0000, 80, 0),
        Event(4200, 4204, 1, 0x0000, 80, 0),
        Event(4400, 4404, 1, 0x0000, 80, 0),
        Event(4600, 4604, 1, 0x0000, 0, -80),
        Event(4800, 4820, 1, 0x8000, 0, 0),
    ]
    result.extend(Event(first, first + 10, 1, 0x8000, 0, 0)
                  for first in range(6600, 6760, 20))
    result.extend(
        (
            Event(7500, 7520, 1, 0x1000, 0, 0),
            Event(7900, 7920, 1, 0x1000, 0, 0),
            Event(8120, 8140, 1, 0x8000, 0, 0),
        )
    )
    # Character and cinematic gates do not all accept input during the same
    # update. Short, separated edges make the cold route deterministic without
    # holding A across a transition and accidentally hiding a missing gate.
    result.extend(Event(first, first + 10, 1, 0x8000, 0, 0)
                  for first in range(9000, COLD_BOOT_GAMEPLAY_END, 200))
    return result


def cold_boot_startup_cutscene_probe_route() -> list[Event]:
    """Confirm a new name, then leave the complete startup film unskipped."""
    return route_prefix(cold_boot_to_gameplay_probe_route(), 4820)


def cold_boot_ambassador_probe_route() -> list[Event]:
    """Reach Magnus only after the canonical cold boot has entered gameplay."""
    result = cold_boot_to_gameplay_probe_route()
    result.extend(
        (
            Event(COLD_BOOT_GAMEPLAY_ACTION_START, 18140, 1, 0x8000, 0, 0),
            Event(18200, 19000, 1, 0x0000, 0, 100),
            Event(19050, 19300, 1, 0x2010, 0, 100),
        )
    )
    return result


def cold_boot_ambassador_exit_route() -> list[Event]:
    """Dismiss Magnus with the mode-specific B edge, then advance with A."""
    result = cold_boot_ambassador_probe_route()
    result.extend(
        (
            Event(19700, 19760, 1, 0x4000, 0, 0),
            Event(20500, 20560, 1, 0x8000, 0, 0),
            Event(21300, 21360, 1, 0x8000, 0, 0),
        )
    )
    return result


def cold_boot_magnus_forest_combat_route() -> list[Event]:
    """Reach the forest-side Life Force door after the robust Magnus exit.

    The hint overlay does not expose a stable, fixed prompt-ready retrace.  A
    bounded combined A+B edge envelope is therefore used to drive every
    dialogue mode, followed by a quiet settling interval before movement.
    This route has been confirmed from an empty flash image through the dry
    right-hand forest fork and a real target/fire sequence at the door.
    """
    result = cold_boot_ambassador_probe_route()
    result.extend(
        Event(first, first + 12, 1, 0xC000, 0, 0)
        for first in range(19600, 25000, 100)
    )
    result.extend(
        (
            # Hub exit, hut approach, and the dry right-hand fork.
            Event(27900, 28300, 1, 0x0000, 20, 100),
            Event(28350, 28430, 1, 0x0000, 100, 0),
            Event(28480, 28780, 1, 0x0000, 0, 100),
            Event(29250, 29270, 1, 0x0000, 100, 0),
            Event(29320, 29720, 1, 0x0000, 0, 100),
            Event(29800, 29810, 1, 0x0000, 100, 0),
            Event(29860, 30100, 1, 0x0000, 0, 100),
            Event(30400, 30550, 1, 0x0000, 0, -100),
            Event(30800, 30805, 1, 0x0000, 100, 0),
            Event(30855, 31005, 1, 0x0000, 0, 100),
            Event(31100, 31200, 1, 0x0000, 0, 100),
            Event(31300, 31320, 1, 0x0000, 100, 0),
            Event(31370, 31570, 1, 0x0000, 0, 100),
            # Target and fire at the door-side encounter.
            Event(31600, 31620, 1, 0x8000, 0, 0),
            Event(31650, 31680, 1, 0x0010, 80, 40),
            Event(31700, 31740, 1, 0x2010, 80, 0),
            Event(31750, 32000, 1, 0x2010, 0, 0),
        )
    )
    return result


def cold_boot_post_ambassador_direction_probe_route(mode: str) -> list[Event]:
    """Calibrate camera-relative travel from the shared Magnus checkpoint."""
    result = cold_boot_ambassador_exit_route()
    if mode.startswith("diagonal-forward-"):
        stick_x = int(mode.removeprefix("diagonal-forward-"))
        result.append(Event(21900, 22300, 1, 0x0000, stick_x, 100))
    elif mode.startswith("diagonal-backward-"):
        stick_x = int(mode.removeprefix("diagonal-backward-"))
        result.append(Event(21900, 22100, 1, 0x0000, stick_x, -100))
    elif mode == "forward" or mode.startswith("forward-"):
        duration = 800 if mode == "forward" else int(mode.rpartition("-")[2])
        result.append(Event(21900, 21900 + duration, 1, 0x0000, 0, 100))
    elif mode == "backward" or mode.startswith("backward-"):
        duration = 800 if mode == "backward" else int(mode.rpartition("-")[2])
        result.append(Event(21900, 21900 + duration, 1, 0x0000, 0, -100))
    elif mode.startswith("target-backward"):
        stick_x = {
            "target-backward": 0,
            "target-backward-left": -40,
            "target-backward-right": 40,
        }[mode]
        result.append(Event(21900, 22300, 1, 0x0010, stick_x, -100))
    elif mode.startswith("camera-"):
        parts = mode.split("-")
        direction = parts[1]
        camera_retraces = int(parts[2])
        camera_button = {"left": 0x0002, "right": 0x0001}[direction]
        result.extend(
            (
                Event(
                    21900,
                    21900 + camera_retraces,
                    1,
                    camera_button,
                    0,
                    0,
                ),
                Event(21950 + camera_retraces, 22350 + camera_retraces,
                      1, 0x0000, 0, 100),
            )
        )
    else:
        forward_retraces = 400
        if "-forward-" in mode:
            mode, forward_text = mode.rsplit("-forward-", 1)
            forward_retraces = int(forward_text)
        base_mode, separator, duration_text = mode.rpartition("-")
        if separator and base_mode in {"turn-left", "turn-right"}:
            turn_retraces = int(duration_text)
            turn_mode = base_mode
        else:
            turn_retraces = 300
            turn_mode = mode
        stick_x = {"turn-left": -100, "turn-right": 100}[turn_mode]
        forward_first = 21950 + turn_retraces
        result.extend(
            (
                Event(21900, 21900 + turn_retraces, 1, 0x0000, stick_x, 0),
                Event(
                    forward_first,
                    forward_first + forward_retraces,
                    1,
                    0x0000,
                    0,
                    100,
                ),
            )
        )
    return result


def cold_boot_shoreline_direction_probe_route(mode: str) -> list[Event]:
    """Probe the second heading from the stable post-Magnus shoreline."""
    result = cold_boot_post_ambassador_direction_probe_route("turn-left-100")
    direction, duration_text = mode.rsplit("-", 1)
    turn_retraces = int(duration_text)
    stick_x = {"left": -100, "right": 100}[direction]
    forward_first = 22550 + turn_retraces
    result.extend(
        (
            Event(22500, 22500 + turn_retraces, 1, 0x0000, stick_x, 0),
            Event(forward_first, forward_first + 400, 1, 0x0000, 0, 100),
        )
    )
    return result


def cold_boot_door_alignment_probe_route(mode: str) -> list[Event]:
    """Align with the post-Magnus doorway from its stable left jamb."""
    result = cold_boot_post_ambassador_direction_probe_route(
        "diagonal-forward-20"
    )
    if mode == "strafe-left":
        result.append(Event(22350, 22650, 1, 0x0002, 0, 0))
    elif mode == "strafe-right":
        result.append(Event(22350, 22650, 1, 0x0001, 0, 0))
    else:
        base_mode, separator, duration_text = mode.rpartition("-")
        if separator and base_mode in {"turn-left", "turn-right"}:
            turn_retraces = int(duration_text)
            turn_mode = base_mode
        else:
            turn_retraces = 40
            turn_mode = mode
        stick_x = {"turn-left": -100, "turn-right": 100}[turn_mode]
        forward_first = 22400 + turn_retraces
        result.extend(
            (
                Event(22350, 22350 + turn_retraces, 1, 0x0000, stick_x, 0),
                Event(forward_first, forward_first + 300, 1, 0x0000, 0, 100),
            )
        )
    return result


def cold_boot_hub_entry_route() -> list[Event]:
    """Pass Magnus's doorway and reach the King Jeff hub from a fresh save."""
    return cold_boot_door_alignment_probe_route("turn-right-80")


def cold_boot_jeff_hut_route() -> list[Event]:
    """Enter King Jeff's hut in the intended fresh-save story order."""
    return cold_boot_jeff_door_probe_route("right-10")


def cold_boot_hub_direction_probe_route(mode: str) -> list[Event]:
    """Calibrate the King Jeff hut heading after the confirmed hub load."""
    result = cold_boot_hub_entry_route()
    if mode == "forward" or mode.startswith("forward-"):
        forward_retraces = 600 if mode == "forward" else int(mode.split("-")[1])
        result.append(
            Event(23250, 23250 + forward_retraces, 1, 0x0000, 0, 100)
        )
    elif mode.startswith("diagonal-"):
        _, direction, magnitude_text, retraces_text = mode.split("-")
        stick_x = int(magnitude_text) * {"left": -1, "right": 1}[direction]
        forward_retraces = int(retraces_text)
        result.append(
            Event(23250, 23250 + forward_retraces, 1, 0x0000, stick_x, 100)
        )
    elif mode.startswith("camera-"):
        parts = mode.split("-")
        direction = parts[1]
        camera_retraces = int(parts[2])
        button = {"left": 0x0002, "right": 0x0001}[direction]
        forward_first = 23300 + camera_retraces
        result.extend(
            (
                Event(23250, 23250 + camera_retraces, 1, button, 0, 0),
                Event(forward_first, forward_first + 240, 1, 0x0000, 0, 100),
            )
        )
    else:
        direction, duration_text = mode.rsplit("-", 1)
        turn_retraces = int(duration_text)
        stick_x = {"left": -100, "right": 100}[direction]
        forward_first = 23300 + turn_retraces
        result.extend(
            (
                Event(23250, 23250 + turn_retraces, 1, 0x0000, stick_x, 0),
                Event(forward_first, forward_first + 400, 1, 0x0000, 0, 100),
            )
        )
    return result


def cold_boot_jeff_door_probe_route(mode: str) -> list[Event]:
    """Calibrate the short correction from the far bridge bank to Jeff's door."""
    result = cold_boot_hub_direction_probe_route("right-20")
    direction, duration_text = mode.rsplit("-", 1)
    turn_retraces = int(duration_text)
    stick_x = {"left": -100, "right": 100}[direction]
    forward_first = 23850 + turn_retraces
    result.extend(
        (
            Event(23800, 23800 + turn_retraces, 1, 0x0000, stick_x, 0),
            Event(forward_first, forward_first + 240, 1, 0x0000, 0, 100),
        )
    )
    return result


def cold_boot_jeff_approach_probe_route(mode: str) -> list[Event]:
    """Calibrate the interior heading from the hut entrance to King Jeff."""
    result = cold_boot_jeff_hut_route()
    if mode.startswith("strafe-"):
        _, direction, duration_text = mode.split("-")
        button = {"left": 0x0002, "right": 0x0001}[direction]
        result.append(
            Event(24400, 24400 + int(duration_text), 1, button, 0, 0)
        )
        return result
    parts = mode.split("-")
    direction = parts[0]
    turn_retraces = int(parts[1])
    forward_retraces = int(parts[2]) if len(parts) == 3 else 300
    stick_x = {"left": -100, "right": 100}[direction]
    forward_first = 24450 + turn_retraces
    result.extend(
        (
            Event(24400, 24400 + turn_retraces, 1, 0x0000, stick_x, 0),
            Event(
                forward_first,
                forward_first + forward_retraces,
                1,
                0x0000,
                0,
                100,
            ),
        )
    )
    return result


def cold_boot_jeff_dialogue_probe_route() -> list[Event]:
    """Approach King Jeff and exercise the explicit talk/advance edge."""
    result = cold_boot_jeff_approach_probe_route("strafe-right-80")
    result.append(Event(24600, 24620, 1, 0x8000, 0, 0))
    return result


def cold_boot_jeff_contact_probe_route(strafe_retraces: int) -> list[Event]:
    """Move around the central fire, then close the final gap to King Jeff."""
    result = cold_boot_jeff_approach_probe_route("right-5-100")
    result.extend(
        (
            Event(24600, 24600 + strafe_retraces, 1, 0x0001, 0, 0),
            Event(24800, 24820, 1, 0x8000, 0, 0),
        )
    )
    return result


def cold_boot_jeff_close_probe_route(forward_retraces: int) -> list[Event]:
    """Close the last face-to-face gap after circling King Jeff's fire."""
    result = cold_boot_jeff_approach_probe_route("right-5-100")
    result.extend(
        (
            Event(24600, 24620, 1, 0x0001, 0, 0),
            Event(24700, 24700 + forward_retraces, 1, 0x0000, 0, 100),
            Event(24900, 24920, 1, 0x8000, 0, 0),
        )
    )
    return result


def cold_boot_jeff_face_probe_route(mode: str) -> list[Event]:
    """Turn from the closest stable lateral contact toward King Jeff."""
    result = cold_boot_jeff_contact_probe_route(40)
    direction, duration_text = mode.split("-")
    turn_retraces = int(duration_text)
    stick_x = {"left": -100, "right": 100}[direction]
    forward_first = 24950 + turn_retraces
    result.extend(
        (
            Event(24900, 24900 + turn_retraces, 1, 0x0000, stick_x, 0),
            Event(forward_first, forward_first + 10, 1, 0x0000, 0, 100),
            Event(25200, 25220, 1, 0x8000, 0, 0),
        )
    )
    return result


def cold_boot_jeff_turn_action_probe_route(mode: str) -> list[Event]:
    """Face Jeff from the stable contact point before sending Action."""
    result = cold_boot_jeff_approach_probe_route("right-5-100")
    result.append(Event(24600, 24640, 1, 0x0001, 0, 0))
    direction, duration_text = mode.split("-")
    turn_retraces = int(duration_text)
    stick_x = {"left": -100, "right": 100}[direction]
    result.extend(
        (
            Event(24800, 24800 + turn_retraces, 1, 0x0000, stick_x, 0),
            Event(25000, 25020, 1, 0x8000, 0, 0),
        )
    )
    return result


def cold_boot_jeff_target_action_probe_route(
    stick_x: int = 0,
    target_retraces: int = 40,
) -> list[Event]:
    """Use targeting mode to face Jeff before sending Action."""
    result = cold_boot_jeff_contact_probe_route(40)
    result.extend(
        (
            Event(
                24900,
                24900 + target_retraces,
                1,
                0x0010,
                stick_x,
                0,
            ),
            Event(25000, 25020, 1, 0x8000, 0, 0),
        )
    )
    return result


def cold_boot_jeff_target_close_probe_route(
    stick_y: int = 100,
    move_retraces: int = 5,
) -> list[Event]:
    """Close the last few units after target mode has faced King Jeff."""
    if move_retraces <= 0 or move_retraces > 50:
        raise RouteError("King Jeff close movement must be 1..50 retraces")
    result = cold_boot_jeff_target_action_probe_route(100, 40)
    result.extend(
        (
            Event(25100, 25100 + move_retraces, 1, 0x0000, 0, stick_y),
            Event(25200, 25220, 1, 0x8000, 0, 0),
        )
    )
    return result


def cold_boot_jeff_hut_exit_probe_route(
    backward_retraces: int = 400,
) -> list[Event]:
    """Back out of Jeff's optional briefing and return to the hub."""
    result = cold_boot_jeff_hut_route()
    result.append(
        Event(24400, 24400 + backward_retraces, 1, 0x0000, 0, -100)
    )
    return result


def cold_boot_jeff_dialogue_exit_probe_route(
    backward_retraces: int = 150,
) -> list[Event]:
    """Complete King Jeff's briefing, then back out through the hut door."""
    if backward_retraces <= 0 or backward_retraces > 400:
        raise RouteError("King Jeff exit movement must be 1..400 retraces")
    result = cold_boot_jeff_target_close_probe_route(-100)
    result.append(
        Event(25300, 25300 + backward_retraces, 1, 0x0000, 0, -100)
    )
    return result


def cold_boot_jeff_dialogue_complete_probe_route() -> list[Event]:
    """Advance every King Jeff briefing page, then verify control restoration."""
    result = cold_boot_jeff_target_close_probe_route(-100)
    result.extend(
        Event(first, first + 12, 1, 0x8000, 0, 0)
        for first in range(25600, 29601, 400)
    )
    result.append(Event(30200, 30400, 1, 0x0000, 0, -100))
    return result


def cold_boot_jeff_post_dialogue_fire_probe_route() -> list[Event]:
    """Verify targeting and weapon fire after King Jeff restores control."""
    result = cold_boot_jeff_dialogue_complete_probe_route()
    result.extend(
        (
            Event(34000, 34200, 1, 0x0010, 0, 0),
            Event(34250, 34850, 1, 0x2010, 0, 0),
        )
    )
    return result


def cold_boot_jeff_post_dialogue_exit_probe_route(
    backward_retraces: int = 10,
) -> list[Event]:
    """Leave King Jeff's hut after the corrected briefing completes."""
    if backward_retraces <= 0 or backward_retraces > 600:
        raise RouteError("post-dialogue hut movement must be 1..600 retraces")
    result = cold_boot_jeff_dialogue_complete_probe_route()
    result.append(
        Event(34000, 34000 + backward_retraces, 1, 0x0000, 0, -100)
    )
    return result


def cold_boot_life_force_direction_probe_route(mode: str) -> list[Event]:
    """Calibrate the path around Jeff's hut toward Magnus's Life Force Door."""
    result = cold_boot_jeff_hut_exit_probe_route(150)
    parts = mode.split("-")
    direction = parts[0]
    turn_retraces = int(parts[1])
    forward_retraces = int(parts[2]) if len(parts) == 3 else 400
    stick_x = {"left": -100, "right": 100}[direction]
    forward_first = 24850 + turn_retraces
    result.extend(
        (
            Event(24800, 24800 + turn_retraces, 1, 0x0000, stick_x, 0),
            Event(
                forward_first,
                forward_first + forward_retraces,
                1,
                0x0000,
                0,
                100,
            ),
        )
    )
    return result


def cold_boot_life_force_door_probe_route(mode: str) -> list[Event]:
    """Follow the visible red Life Force Door indicator behind Jeff's hut."""
    result = cold_boot_life_force_direction_probe_route("left-40")
    if mode.startswith("strafe-"):
        _, direction, duration_text = mode.split("-")
        button = {"left": 0x0002, "right": 0x0001}[direction]
        strafe_retraces = int(duration_text)
        result.extend(
            (
                Event(25400, 25400 + strafe_retraces, 1, button, 0, 0),
                Event(
                    25450 + strafe_retraces,
                    25950 + strafe_retraces,
                    1,
                    0x0000,
                    0,
                    100,
                ),
            )
        )
        return result
    direction, duration_text = mode.split("-")
    turn_retraces = int(duration_text)
    stick_x = {"left": -100, "right": 100}[direction]
    forward_first = 25450 + turn_retraces
    result.extend(
        (
            Event(25400, 25400 + turn_retraces, 1, 0x0000, stick_x, 0),
            Event(forward_first, forward_first + 500, 1, 0x0000, 0, 100),
        )
    )
    return result


def cold_boot_life_force_candidate_probe_route(mode: str) -> list[Event]:
    """Turn from the open-water checkpoint toward the visible stone door."""
    result = cold_boot_life_force_direction_probe_route("left-20")
    direction, duration_text = mode.split("-")
    turn_retraces = int(duration_text)
    stick_x = {"left": -100, "right": 100}[direction]
    forward_first = 25450 + turn_retraces
    result.extend(
        (
            Event(25400, 25400 + turn_retraces, 1, 0x0000, stick_x, 0),
            Event(forward_first, forward_first + 150, 1, 0x0000, 0, 100),
        )
    )
    return result


def cold_boot_life_force_bridge_probe_route(strafe_retraces: int) -> list[Event]:
    """Align with and cross the bridge leading to the stone door."""
    result = cold_boot_life_force_candidate_probe_route("right-20")
    result.extend(
        (
            Event(25800, 25800 + strafe_retraces, 1, 0x0001, 0, 0),
            Event(
                25850 + strafe_retraces,
                26150 + strafe_retraces,
                1,
                0x0000,
                0,
                100,
            ),
        )
    )
    return result


def cold_boot_life_force_combat_probe_route(stick_x: int = 80) -> list[Event]:
    """Target and fire at the practice drones beside the Life Force Door."""
    result = cold_boot_life_force_drone_door_probe_route("right-20")
    result.extend(
        (
            Event(25600, 25620, 1, 0x8000, 0, 0),
            Event(25650, 25680, 1, 0x0010, stick_x, 40),
            Event(25700, 25740, 1, 0x2010, stick_x, 0),
            Event(25750, 26000, 1, 0x2010, 0, 0),
        )
    )
    return result


def cold_boot_life_force_magnus_probe_route(mode: str) -> list[Event]:
    """Approach Magnus at the locked door before engaging practice drones."""
    result = cold_boot_life_force_bridge_probe_route(20)
    direction, duration_text = mode.split("-")
    turn_retraces = int(duration_text)
    stick_x = {"left": -100, "right": 100}[direction]
    forward_first = 26250 + turn_retraces
    result.extend(
        (
            Event(26200, 26200 + turn_retraces, 1, 0x0000, stick_x, 0),
            Event(forward_first, forward_first + 150, 1, 0x0000, 0, 100),
        )
    )
    return result


def cold_boot_life_force_magnus_contact_probe_route(
    strafe_retraces: int,
) -> list[Event]:
    """Close the final gap to Magnus and send the in-world Action button."""
    result = cold_boot_life_force_drone_door_probe_route("right-20")
    result.extend(
        (
            Event(25600, 25600 + strafe_retraces, 1, 0x0001, 0, 0),
            Event(25700, 25720, 1, 0x0000, 0, 100),
            Event(25800, 25820, 1, 0x8000, 0, 0),
        )
    )
    return result


def cold_boot_life_force_drone_approach_probe_route(
    strafe_retraces: int,
) -> list[Event]:
    """Move laterally along the hut wall toward Magnus and the visible drone."""
    result = cold_boot_life_force_direction_probe_route("right-5-150")
    result.append(Event(25100, 25100 + strafe_retraces, 1, 0x0001, 0, 0))
    return result


def cold_boot_life_force_drone_forward_probe_route(
    forward_retraces: int,
) -> list[Event]:
    """Continue along the sandy path toward the visible green door."""
    result = cold_boot_life_force_direction_probe_route("right-5-150")
    result.append(
        Event(25100, 25100 + forward_retraces, 1, 0x0000, 0, 100)
    )
    return result


def cold_boot_life_force_drone_door_probe_route(mode: str) -> list[Event]:
    """Turn from the cleared hut corner toward the green Life Force Door."""
    result = cold_boot_life_force_drone_forward_probe_route(100)
    direction, duration_text = mode.split("-")
    turn_retraces = int(duration_text)
    stick_x = {"left": -100, "right": 100}[direction]
    forward_first = 25350 + turn_retraces
    result.extend(
        (
            Event(25300, 25300 + turn_retraces, 1, 0x0000, stick_x, 0),
            Event(forward_first, forward_first + 200, 1, 0x0000, 0, 100),
        )
    )
    return result


def controller_disconnect_route(source: list[Event]) -> list[Event]:
    result = route_prefix(source, SAVE_COMMIT_INPUT_END)
    if not result or result[-1].last < SAVE_COMMIT_INPUT_END:
        raise RouteError("source replay ends before the persistent-save route")
    # The canonical input is neutral after the save-confirmation input. Exercise
    # a real sampled disconnect/reconnect without replacing any route action.
    result.extend(
        (
            Event(29582, 29590, 0, 0x0000, 0, 0),
            Event(29590, 29598, 1, 0x0000, 0, 0),
        )
    )
    return result


def combat_probe_route(source: list[Event], *, targeting: bool = False) -> list[Event]:
    result = route_prefix(source, COMBAT_PROBE_PREFIX_END)
    result.extend(
        (
            Event(8120, 8140, 1, 0x8000, 0, 0),  # A: next weapon.
            Event(8200, 9000, 1, 0x0000, 0, 100),
            Event(
                9050,
                9300,
                1,
                0x2010 if targeting else 0x2000,
                0,
                100,
            ),
        )
    )
    return result


def post_dialogue_combat_probe_route(source: list[Event]) -> list[Event]:
    """Legacy diagnostic that reopens the Goldwood ambassador dialogue."""
    result = combat_probe_route(source, targeting=True)
    for first in range(9520, 10120, 60):
        result.append(Event(first, first + 10, 1, 0x8000, 0, 0))
    result.extend(
        (
            Event(10200, 11100, 1, 0x0000, 0, 100),
            Event(11200, 11700, 1, 0x2010, 0, 100),
        )
    )
    return result


def bypass_ambassador_probe_route(source: list[Event], *, right: bool) -> list[Event]:
    """Steer around the ambassador after the targeting branch closes dialogue."""
    result = combat_probe_route(source, targeting=True)
    stick_x = 35 if right else -35
    result.extend(
        (
            Event(9500, 9660, 1, 0x0000, stick_x, 95),
            Event(9660, 10800, 1, 0x0000, 0, 100),
            Event(10850, 11200, 1, 0x2010, 0, 0),
        )
    )
    return result


def dialogue_button_probe_route(source: list[Event], button: int) -> list[Event]:
    result = combat_probe_route(source, targeting=True)
    result.append(Event(9700, 9760, 1, button, 0, 0))
    return result


def ambassador_dialogue_exit_route(source: list[Event]) -> list[Event]:
    """Dismiss Magnus with the mode-specific B edge, then advance with A."""
    result = dialogue_button_probe_route(source, 0x4000)
    result.extend(
        (
            Event(10500, 10560, 1, 0x8000, 0, 0),
            Event(11300, 11360, 1, 0x8000, 0, 0),
        )
    )
    return result


def fire_sequence_probe_route(source: list[Event]) -> list[Event]:
    result = combat_probe_route(source, targeting=True)
    result.extend(
        (
            Event(9500, 9600, 1, 0x0010, 0, 0),
            Event(9600, 9620, 1, 0x2010, 0, 0),
            Event(9620, 9660, 1, 0x0010, 0, 0),
            Event(9660, 9680, 1, 0x2010, 0, 0),
            Event(9680, 9750, 1, 0x0010, 0, 0),
        )
    )
    return result


def pursue_combat_probe_route(source: list[Event]) -> list[Event]:
    result = ambassador_dialogue_exit_route(source)
    result.extend(
        (
            Event(15000, 15300, 1, 0x0000, 35, 100),
            Event(15300, 16000, 1, 0x0000, 0, 100),
            Event(16050, 16400, 1, 0x2010, 0, 0),
            Event(16500, 16850, 1, 0x0000, -85, 75),
            Event(16850, 17600, 1, 0x0000, 0, 100),
            Event(17650, 18000, 1, 0x2010, 0, 0),
            Event(18200, 18600, 1, 0x0000, -90, 75),
            Event(18600, 19700, 1, 0x0000, 0, 100),
            Event(19750, 20100, 1, 0x2010, 0, 0),
        )
    )
    return result


def hub_entry_probe_route(source: list[Event]) -> list[Event]:
    result = ambassador_dialogue_exit_route(source)
    result.extend(
        (
            Event(15000, 15300, 1, 0x0000, 35, 100),
            Event(15300, 16000, 1, 0x0000, 0, 100),
            Event(16050, 16400, 1, 0x2010, 0, 0),
            Event(16500, 16620, 1, 0x0000, -100, 0),
            Event(16620, 17300, 1, 0x0000, 0, 100),
        )
    )
    return result


def hub_after_magnus_probe_route(source: list[Event]) -> list[Event]:
    result = hub_entry_probe_route(source)
    result.append(Event(17600, 17660, 1, 0x8000, 0, 0))
    return result


def complete_magnus_probe_route(source: list[Event]) -> list[Event]:
    result = hub_entry_probe_route(source)
    for first in (17600, 18800, 20000, 21200, 22400, 23600, 25200):
        result.append(Event(first, first + 60, 1, 0x8000, 0, 0))
    return result


def reach_jeff_probe_route(source: list[Event]) -> list[Event]:
    result = complete_magnus_probe_route(source)
    result.append(Event(27500, 30200, 1, 0x0000, 0, 100))
    return result


def cross_hub_bridge_probe_route(source: list[Event]) -> list[Event]:
    result = reach_jeff_probe_route(source)
    result.extend(
        (
            Event(30600, 30850, 1, 0x0000, 85, 0),
            Event(30850, 32600, 1, 0x0000, 0, 100),
        )
    )
    return result


def strafe_hub_bridge_probe_route(
    source: list[Event], *, strafe_retraces: int = 300
) -> list[Event]:
    result = reach_jeff_probe_route(source)
    result.extend(
        (
            Event(30600, 30600 + strafe_retraces, 1, 0x0001, 0, 0),
            Event(30900, 32600, 1, 0x0000, 0, 100),
        )
    )
    return result


def bridge_heading_probe_route(source: list[Event], turn_retraces: int) -> list[Event]:
    result = reach_jeff_probe_route(source)
    result.extend(
        (
            Event(30600, 30640, 1, 0x0001, 0, 0),
            Event(30900, 30900 + turn_retraces, 1, 0x0000, 100, 0),
        )
    )
    return result


def bridge_landing_probe_route(source: list[Event]) -> list[Event]:
    result = reach_jeff_probe_route(source)
    result.extend(
        (
            Event(30600, 30640, 1, 0x0001, 0, 0),
            Event(30900, 31200, 1, 0x0000, 0, 100),
        )
    )
    return result


def island_direction_probe_route(source: list[Event], mode: str) -> list[Event]:
    result = bridge_landing_probe_route(source)
    directions = {
        "stick-left": (0x0000, -100, 0),
        "stick-right": (0x0000, 100, 0),
        "strafe-left": (0x0002, 0, 0),
        "strafe-right": (0x0001, 0, 0),
    }
    buttons, stick_x, stick_y = directions[mode]
    result.append(Event(31200, 31500, 1, buttons, stick_x, stick_y))
    return result


def bridge_guidance_probe_route(source: list[Event], mode: str) -> list[Event]:
    result = reach_jeff_probe_route(source)
    result.append(Event(30600, 30640, 1, 0x0001, 0, 0))
    guidance = {
        "c-left": (0x0002, 0),
        "c-right": (0x0001, 0),
        "stick-left": (0x0000, -20),
        "stick-right": (0x0000, 20),
    }
    buttons, stick_x = guidance[mode]
    result.append(Event(30900, 31300, 1, buttons, stick_x, 100))
    return result


def bridge_jump_probe_route(source: list[Event], mode: str) -> list[Event]:
    """Cross the far bridge edge with a jump toward the island ramp."""
    result = reach_jeff_probe_route(source)
    result.extend(
        (
            Event(30600, 30640, 1, 0x0001, 0, 0),
            Event(30900, 31050, 1, 0x0000, 20, 100),
        )
    )
    if mode == "pulse":
        for first in range(31050, 31300, 50):
            result.extend(
                (
                    Event(first, first + 10, 1, 0x8000, 20, 100),
                    Event(first + 10, first + 50, 1, 0x0000, 20, 100),
                )
            )
    else:
        stick_x = {"straight": 0, "right-20": 20, "right-40": 40}[mode]
        result.append(Event(31050, 31300, 1, 0x8000, stick_x, 100))
    return result


def island_path_probe_route(source: list[Event], mode: str) -> list[Event]:
    """Recover from the far-bank wall and look for King Jeff's hut path."""
    result = reach_jeff_probe_route(source)
    result.extend(
        (
            Event(30600, 30640, 1, 0x0001, 0, 0),
            Event(30900, 31200, 1, 0x0001, 0, 100),
        )
    )
    recoveries = {
        "strafe-left": (0x0002, 0, 0),
        "turn-left": (0x0000, -100, 0),
        "turn-right": (0x0000, 100, 0),
        "backward": (0x0000, 0, -100),
    }
    buttons, stick_x, stick_y = recoveries[mode]
    result.extend(
        (
            Event(31250, 31350, 1, buttons, stick_x, stick_y),
            Event(31400, 31900, 1, 0x0000, 0, 100),
        )
    )
    return result


def island_shore_probe_route(source: list[Event], mode: str) -> list[Event]:
    """Probe the sandy bank beside the island's crystal pickup."""
    result = island_path_probe_route(source, "turn-right")
    motions = {
        "strafe-left": (0x0002, 0, 0),
        "strafe-right": (0x0001, 0, 0),
        "forward-left": (0x0002, 0, 100),
        "jump-right": (0x8001, 0, 0),
    }
    buttons, stick_x, stick_y = motions[mode]
    result.append(Event(32000, 32350, 1, buttons, stick_x, stick_y))
    return result


def reach_jeff_hut_probe_route(source: list[Event]) -> list[Event]:
    result = island_shore_probe_route(source, "forward-left")
    result.append(Event(32400, 34000, 1, 0x0000, 0, 100))
    return result


def trigger_jeff_probe_route(source: list[Event]) -> list[Event]:
    result = reach_jeff_hut_probe_route(source)
    result.append(Event(34000, 34500, 1, 0x0000, 0, 100))
    return result


def jeff_hut_fire_probe_route(source: list[Event]) -> list[Event]:
    """Probe firing shortly after the King Jeff approach trigger."""
    result = trigger_jeff_probe_route(source)
    result.append(Event(35000, 35300, 1, 0x2010, 0, 0))
    return result


def jeff_dialogue_exit_fire_probe_route(source: list[Event]) -> list[Event]:
    """Advance King Jeff dialogue on distinct A edges, then target and fire."""
    result = trigger_jeff_probe_route(source)
    for first in range(35000, 39001, 400):
        result.append(Event(first, first + 12, 1, 0x8000, 0, 0))
    result.extend(
        (
            Event(40000, 40400, 1, 0x0010, 0, 0),
            Event(40450, 41050, 1, 0x2010, 0, 0),
        )
    )
    return result


def explore_turn_probe_route(source: list[Event], *, right: bool) -> list[Event]:
    result = pursue_combat_probe_route(source)
    result.extend(
        (
            Event(20300, 20800, 1, 0x0000, 100 if right else -100, 20),
            Event(20800, 21800, 1, 0x0000, 0, 100),
            Event(21850, 22200, 1, 0x2010, 0, 0),
        )
    )
    return result


def exterior_fire_probe_route(source: list[Event]) -> list[Event]:
    result = pursue_combat_probe_route(source)
    result.extend(
        (
            Event(20300, 20400, 1, 0x0010, 0, 0),
            Event(20400, 20420, 1, 0x2010, 0, 0),
            Event(20420, 20480, 1, 0x0010, 0, 0),
            Event(20480, 20500, 1, 0x2010, 0, 0),
            Event(20500, 20600, 1, 0x0010, 0, 0),
        )
    )
    return result


def shoreline_probe_route(source: list[Event], *, right: bool) -> list[Event]:
    result = pursue_combat_probe_route(source)
    result.append(Event(20300, 22200, 1, 0x0000, 100 if right else -100, 0))
    return result


def write_replay(path: Path, events: list[Event]) -> None:
    if not events:
        raise RouteError("refusing to write an empty replay")
    for previous, current in zip(events, events[1:]):
        if current.first < previous.last:
            raise RouteError("generated replay overlaps")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        HEADER + "\n" + "\n".join(event.row() for event in events) + "\n",
        encoding="ascii",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--scenario",
        choices=(
            "canonical",
            "cold-boot-to-gameplay-probe",
            "cold-boot-startup-cutscene-probe",
            "cold-boot-ambassador-probe",
            "cold-boot-ambassador-exit-probe",
            "cold-boot-hub-entry-probe",
            "cold-boot-jeff-hut-probe",
            "cold-boot-post-ambassador-forward-probe",
            "cold-boot-post-ambassador-backward-probe",
            "cold-boot-post-ambassador-backward-100-probe",
            "cold-boot-post-ambassador-backward-200-probe",
            "cold-boot-post-ambassador-backward-300-probe",
            "cold-boot-post-ambassador-backward-400-probe",
            "cold-boot-post-ambassador-target-backward-probe",
            "cold-boot-post-ambassador-target-backward-left-probe",
            "cold-boot-post-ambassador-target-backward-right-probe",
            "cold-boot-post-ambassador-camera-left-40-probe",
            "cold-boot-post-ambassador-camera-left-80-probe",
            "cold-boot-post-ambassador-camera-left-120-probe",
            "cold-boot-post-ambassador-camera-right-40-probe",
            "cold-boot-post-ambassador-camera-right-80-probe",
            "cold-boot-post-ambassador-camera-right-120-probe",
            "cold-boot-post-ambassador-diagonal-backward-20-probe",
            "cold-boot-post-ambassador-diagonal-backward-40-probe",
            "cold-boot-post-ambassador-diagonal-backward--20-probe",
            "cold-boot-post-ambassador-diagonal-backward--40-probe",
            "cold-boot-post-ambassador-diagonal-forward-20-probe",
            "cold-boot-post-ambassador-diagonal-forward-40-probe",
            "cold-boot-post-ambassador-diagonal-forward-60-probe",
            "cold-boot-post-ambassador-diagonal-forward--20-probe",
            "cold-boot-post-ambassador-diagonal-forward--40-probe",
            "cold-boot-post-ambassador-diagonal-forward--60-probe",
            "cold-boot-shoreline-left-40-probe",
            "cold-boot-shoreline-right-40-probe",
            "cold-boot-shoreline-right-80-probe",
            "cold-boot-shoreline-right-120-probe",
            "cold-boot-shoreline-right-160-probe",
            "cold-boot-door-strafe-left-probe",
            "cold-boot-door-strafe-right-probe",
            "cold-boot-door-turn-left-probe",
            "cold-boot-door-turn-right-probe",
            "cold-boot-door-turn-right-80-probe",
            "cold-boot-door-turn-right-120-probe",
            "cold-boot-door-turn-right-160-probe",
            "cold-boot-door-turn-right-200-probe",
            "cold-boot-hub-forward-probe",
            "cold-boot-hub-forward-100-probe",
            "cold-boot-hub-forward-200-probe",
            "cold-boot-hub-forward-300-probe",
            "cold-boot-hub-forward-400-probe",
            "cold-boot-hub-diagonal-left-20-200-probe",
            "cold-boot-hub-diagonal-left-40-200-probe",
            "cold-boot-hub-diagonal-right-20-200-probe",
            "cold-boot-hub-diagonal-right-40-200-probe",
            "cold-boot-hub-left-40-probe",
            "cold-boot-hub-left-80-probe",
            "cold-boot-hub-right-40-probe",
            "cold-boot-hub-right-80-probe",
            "cold-boot-hub-right-5-probe",
            "cold-boot-hub-right-10-probe",
            "cold-boot-hub-right-15-probe",
            "cold-boot-hub-right-20-probe",
            "cold-boot-hub-right-30-probe",
            "cold-boot-hub-camera-left-40-probe",
            "cold-boot-hub-camera-right-40-probe",
            "cold-boot-hub-camera-right-80-probe",
            "cold-boot-hub-camera-right-120-probe",
            "cold-boot-jeff-door-left-5-probe",
            "cold-boot-jeff-door-left-10-probe",
            "cold-boot-jeff-door-right-5-probe",
            "cold-boot-jeff-door-right-10-probe",
            "cold-boot-jeff-door-right-20-probe",
            "cold-boot-jeff-approach-left-40-probe",
            "cold-boot-jeff-approach-right-20-probe",
            "cold-boot-jeff-approach-right-40-probe",
            "cold-boot-jeff-approach-right-60-probe",
            "cold-boot-jeff-approach-strafe-right-40-probe",
            "cold-boot-jeff-approach-strafe-right-41-probe",
            "cold-boot-jeff-approach-strafe-right-42-probe",
            "cold-boot-jeff-approach-strafe-right-43-probe",
            "cold-boot-jeff-approach-strafe-right-44-probe",
            "cold-boot-jeff-approach-strafe-right-80-probe",
            "cold-boot-jeff-approach-strafe-right-120-probe",
            "cold-boot-jeff-approach-strafe-right-160-probe",
            "cold-boot-jeff-approach-left-5-100-probe",
            "cold-boot-jeff-approach-left-10-100-probe",
            "cold-boot-jeff-approach-left-15-100-probe",
            "cold-boot-jeff-approach-right-5-100-probe",
            "cold-boot-jeff-approach-right-10-100-probe",
            "cold-boot-jeff-dialogue-probe",
            "cold-boot-jeff-contact-20-probe",
            "cold-boot-jeff-contact-40-probe",
            "cold-boot-jeff-contact-45-probe",
            "cold-boot-jeff-contact-50-probe",
            "cold-boot-jeff-contact-55-probe",
            "cold-boot-jeff-contact-60-probe",
            "cold-boot-jeff-contact-80-probe",
            "cold-boot-jeff-close-30-probe",
            "cold-boot-jeff-close-60-probe",
            "cold-boot-jeff-close-100-probe",
            "cold-boot-jeff-face-left-5-probe",
            "cold-boot-jeff-face-left-10-probe",
            "cold-boot-jeff-face-left-20-probe",
            "cold-boot-jeff-face-left-30-probe",
            "cold-boot-jeff-face-right-5-probe",
            "cold-boot-jeff-face-right-10-probe",
            "cold-boot-jeff-face-right-20-probe",
            "cold-boot-jeff-face-right-30-probe",
            "cold-boot-jeff-face-right-40-probe",
            "cold-boot-jeff-turn-action-left-40-probe",
            "cold-boot-jeff-turn-action-right-20-probe",
            "cold-boot-jeff-turn-action-right-40-probe",
            "cold-boot-jeff-turn-action-right-60-probe",
            "cold-boot-jeff-turn-action-right-80-probe",
            "cold-boot-jeff-target-action-probe",
            "cold-boot-jeff-target-action-left-20-probe",
            "cold-boot-jeff-target-action-left-40-probe",
            "cold-boot-jeff-target-action-right-20-probe",
            "cold-boot-jeff-target-action-right-40-probe",
            "cold-boot-jeff-target-close-probe",
            "cold-boot-jeff-target-close-15-probe",
            "cold-boot-jeff-target-close-25-probe",
            "cold-boot-jeff-target-close-35-probe",
            "cold-boot-jeff-target-close-backward-probe",
            "cold-boot-jeff-hut-exit-backward-probe",
            "cold-boot-jeff-hut-exit-backward-100-probe",
            "cold-boot-jeff-hut-exit-backward-150-probe",
            "cold-boot-jeff-hut-exit-backward-200-probe",
            "cold-boot-jeff-dialogue-exit-probe",
            "cold-boot-jeff-dialogue-complete-probe",
            "cold-boot-jeff-post-dialogue-fire-probe",
            "cold-boot-jeff-post-dialogue-exit-probe",
            "cold-boot-magnus-forest-combat-probe",
            "cold-boot-life-force-left-20-probe",
            "cold-boot-life-force-left-40-probe",
            "cold-boot-life-force-right-20-probe",
            "cold-boot-life-force-right-40-probe",
            "cold-boot-life-force-right-5-150-probe",
            "cold-boot-life-force-right-10-150-probe",
            "cold-boot-life-force-right-15-150-probe",
            "cold-boot-life-force-right-20-150-probe",
            "cold-boot-life-force-door-left-5-probe",
            "cold-boot-life-force-door-right-5-probe",
            "cold-boot-life-force-door-right-10-probe",
            "cold-boot-life-force-door-right-20-probe",
            "cold-boot-life-force-door-strafe-right-40-probe",
            "cold-boot-life-force-door-strafe-right-80-probe",
            "cold-boot-life-force-door-strafe-right-120-probe",
            "cold-boot-life-force-candidate-right-5-probe",
            "cold-boot-life-force-candidate-right-10-probe",
            "cold-boot-life-force-candidate-right-20-probe",
            "cold-boot-life-force-candidate-right-40-probe",
            "cold-boot-life-force-bridge-20-probe",
            "cold-boot-life-force-bridge-40-probe",
            "cold-boot-life-force-bridge-80-probe",
            "cold-boot-life-force-combat-probe",
            "cold-boot-life-force-combat-left-probe",
            "cold-boot-life-force-combat-neutral-probe",
            "cold-boot-life-force-combat-right-40-probe",
            "cold-boot-life-force-magnus-left-5-probe",
            "cold-boot-life-force-magnus-right-5-probe",
            "cold-boot-life-force-magnus-right-10-probe",
            "cold-boot-life-force-magnus-right-20-probe",
            "cold-boot-life-force-magnus-contact-20-probe",
            "cold-boot-life-force-magnus-contact-40-probe",
            "cold-boot-life-force-magnus-contact-60-probe",
            "cold-boot-life-force-drone-approach-40-probe",
            "cold-boot-life-force-drone-approach-80-probe",
            "cold-boot-life-force-drone-approach-120-probe",
            "cold-boot-life-force-drone-forward-100-probe",
            "cold-boot-life-force-drone-forward-200-probe",
            "cold-boot-life-force-drone-forward-300-probe",
            "cold-boot-life-force-drone-door-left-5-probe",
            "cold-boot-life-force-drone-door-right-5-probe",
            "cold-boot-life-force-drone-door-right-10-probe",
            "cold-boot-life-force-drone-door-right-20-probe",
            "cold-boot-post-ambassador-turn-left-probe",
            "cold-boot-post-ambassador-turn-right-probe",
            "cold-boot-post-ambassador-turn-left-60-probe",
            "cold-boot-post-ambassador-turn-left-100-probe",
            "cold-boot-post-ambassador-turn-left-110-probe",
            "cold-boot-post-ambassador-turn-left-115-probe",
            "cold-boot-post-ambassador-turn-left-120-probe",
            "cold-boot-post-ambassador-turn-left-125-probe",
            "cold-boot-post-ambassador-turn-left-130-probe",
            "cold-boot-post-ambassador-turn-left-140-probe",
            "cold-boot-post-ambassador-turn-left-180-probe",
            "cold-boot-post-ambassador-turn-left-220-probe",
            "cold-boot-post-ambassador-turn-left-260-probe",
            "cold-boot-post-ambassador-turn-left-140-forward-80-probe",
            "cold-boot-post-ambassador-turn-left-140-forward-120-probe",
            "cold-boot-post-ambassador-turn-left-140-forward-160-probe",
            "cold-boot-post-ambassador-turn-left-140-forward-200-probe",
            "controller-disconnect",
            "combat-probe",
            "combat-target-probe",
            "post-dialogue-combat-probe",
            "bypass-ambassador-left-probe",
            "bypass-ambassador-right-probe",
            "dialogue-a-probe",
            "dialogue-b-probe",
            "dialogue-z-probe",
            "dialogue-start-probe",
            "fire-sequence-probe",
            "pursue-combat-probe",
            "hub-entry-probe",
            "hub-after-magnus-probe",
            "complete-magnus-probe",
            "reach-jeff-probe",
            "cross-hub-bridge-probe",
            "strafe-hub-bridge-probe",
            "strafe-hub-bridge-40-probe",
            "strafe-hub-bridge-80-probe",
            "strafe-hub-bridge-120-probe",
            "bridge-heading-20-probe",
            "bridge-heading-40-probe",
            "bridge-heading-80-probe",
            "bridge-heading-160-probe",
            "island-stick-left-probe",
            "island-stick-right-probe",
            "island-strafe-left-probe",
            "island-strafe-right-probe",
            "bridge-guide-c-left-probe",
            "bridge-guide-c-right-probe",
            "bridge-guide-stick-left-probe",
            "bridge-guide-stick-right-probe",
            "bridge-jump-straight-probe",
            "bridge-jump-right-20-probe",
            "bridge-jump-right-40-probe",
            "bridge-jump-pulse-probe",
            "island-path-strafe-left-probe",
            "island-path-turn-left-probe",
            "island-path-turn-right-probe",
            "island-path-backward-probe",
            "island-shore-strafe-left-probe",
            "island-shore-strafe-right-probe",
            "island-shore-forward-left-probe",
            "island-shore-jump-right-probe",
            "reach-jeff-hut-probe",
            "trigger-jeff-probe",
            "jeff-hut-fire-probe",
            "jeff-dialogue-exit-fire-probe",
            "explore-left-probe",
            "explore-right-probe",
            "exterior-fire-probe",
            "shoreline-left-probe",
            "shoreline-right-probe",
        ),
        default="canonical",
    )
    arguments = parser.parse_args()
    source = load_replay(arguments.source)
    if arguments.scenario == "canonical":
        route = canonical_route(source)
    elif arguments.scenario == "cold-boot-to-gameplay-probe":
        route = cold_boot_to_gameplay_probe_route()
    elif arguments.scenario == "cold-boot-startup-cutscene-probe":
        route = cold_boot_startup_cutscene_probe_route()
    elif arguments.scenario == "cold-boot-ambassador-probe":
        route = cold_boot_ambassador_probe_route()
    elif arguments.scenario == "cold-boot-ambassador-exit-probe":
        route = cold_boot_ambassador_exit_route()
    elif arguments.scenario == "cold-boot-magnus-forest-combat-probe":
        route = cold_boot_magnus_forest_combat_route()
    elif arguments.scenario == "cold-boot-hub-entry-probe":
        route = cold_boot_hub_entry_route()
    elif arguments.scenario == "cold-boot-jeff-hut-probe":
        route = cold_boot_jeff_hut_route()
    elif arguments.scenario.startswith("cold-boot-post-ambassador-"):
        mode = arguments.scenario.removeprefix(
            "cold-boot-post-ambassador-"
        ).removesuffix("-probe")
        route = cold_boot_post_ambassador_direction_probe_route(mode)
    elif arguments.scenario.startswith("cold-boot-shoreline-"):
        mode = arguments.scenario.removeprefix(
            "cold-boot-shoreline-"
        ).removesuffix("-probe")
        route = cold_boot_shoreline_direction_probe_route(mode)
    elif arguments.scenario.startswith("cold-boot-door-"):
        mode = arguments.scenario.removeprefix(
            "cold-boot-door-"
        ).removesuffix("-probe")
        route = cold_boot_door_alignment_probe_route(mode)
    elif arguments.scenario.startswith("cold-boot-hub-"):
        mode = arguments.scenario.removeprefix(
            "cold-boot-hub-"
        ).removesuffix("-probe")
        route = cold_boot_hub_direction_probe_route(mode)
    elif arguments.scenario.startswith("cold-boot-jeff-door-"):
        mode = arguments.scenario.removeprefix(
            "cold-boot-jeff-door-"
        ).removesuffix("-probe")
        route = cold_boot_jeff_door_probe_route(mode)
    elif arguments.scenario.startswith("cold-boot-jeff-approach-"):
        mode = arguments.scenario.removeprefix(
            "cold-boot-jeff-approach-"
        ).removesuffix("-probe")
        route = cold_boot_jeff_approach_probe_route(mode)
    elif arguments.scenario == "cold-boot-jeff-dialogue-probe":
        route = cold_boot_jeff_dialogue_probe_route()
    elif arguments.scenario.startswith("cold-boot-jeff-contact-"):
        strafe_retraces = int(arguments.scenario.split("-")[4])
        route = cold_boot_jeff_contact_probe_route(strafe_retraces)
    elif arguments.scenario.startswith("cold-boot-jeff-close-"):
        forward_retraces = int(arguments.scenario.split("-")[4])
        route = cold_boot_jeff_close_probe_route(forward_retraces)
    elif arguments.scenario.startswith("cold-boot-jeff-face-"):
        mode = "-".join(arguments.scenario.split("-")[4:6])
        route = cold_boot_jeff_face_probe_route(mode)
    elif arguments.scenario.startswith("cold-boot-jeff-turn-action-"):
        mode = "-".join(arguments.scenario.split("-")[5:7])
        route = cold_boot_jeff_turn_action_probe_route(mode)
    elif arguments.scenario.startswith("cold-boot-jeff-target-action"):
        parts = arguments.scenario.split("-")
        if parts[5] == "probe":
            route = cold_boot_jeff_target_action_probe_route()
        else:
            stick_x = {"left": -100, "right": 100}[parts[5]]
            route = cold_boot_jeff_target_action_probe_route(
                stick_x, int(parts[6])
            )
    elif arguments.scenario.startswith("cold-boot-jeff-target-close"):
        stick_y = -100 if "backward" in arguments.scenario else 100
        parts = arguments.scenario.split("-")
        move_retraces = int(parts[5]) if parts[5].isdigit() else 5
        route = cold_boot_jeff_target_close_probe_route(
            stick_y, move_retraces
        )
    elif arguments.scenario.startswith("cold-boot-jeff-hut-exit-backward"):
        parts = arguments.scenario.split("-")
        backward_retraces = 400 if parts[6] == "probe" else int(parts[6])
        route = cold_boot_jeff_hut_exit_probe_route(backward_retraces)
    elif arguments.scenario == "cold-boot-jeff-dialogue-exit-probe":
        route = cold_boot_jeff_dialogue_exit_probe_route()
    elif arguments.scenario == "cold-boot-jeff-dialogue-complete-probe":
        route = cold_boot_jeff_dialogue_complete_probe_route()
    elif arguments.scenario == "cold-boot-jeff-post-dialogue-fire-probe":
        route = cold_boot_jeff_post_dialogue_fire_probe_route()
    elif arguments.scenario == "cold-boot-jeff-post-dialogue-exit-probe":
        route = cold_boot_jeff_post_dialogue_exit_probe_route()
    elif arguments.scenario.startswith("cold-boot-life-force-"):
        parts = arguments.scenario.split("-")
        if parts[4] == "door":
            mode = arguments.scenario.removeprefix(
                "cold-boot-life-force-door-"
            ).removesuffix("-probe")
            route = cold_boot_life_force_door_probe_route(mode)
        elif parts[4] == "candidate":
            mode = arguments.scenario.removeprefix(
                "cold-boot-life-force-candidate-"
            ).removesuffix("-probe")
            route = cold_boot_life_force_candidate_probe_route(mode)
        elif parts[4] == "bridge":
            strafe_retraces = int(parts[5])
            route = cold_boot_life_force_bridge_probe_route(strafe_retraces)
        elif parts[4] == "combat":
            stick_x = {
                "cold-boot-life-force-combat-probe": 80,
                "cold-boot-life-force-combat-left-probe": -80,
                "cold-boot-life-force-combat-neutral-probe": 0,
                "cold-boot-life-force-combat-right-40-probe": 40,
            }[arguments.scenario]
            route = cold_boot_life_force_combat_probe_route(stick_x)
        elif parts[4] == "magnus":
            if parts[5] == "contact":
                route = cold_boot_life_force_magnus_contact_probe_route(
                    int(parts[6])
                )
            else:
                mode = "-".join(parts[5:7])
                route = cold_boot_life_force_magnus_probe_route(mode)
        elif parts[4] == "drone":
            if parts[5] == "door":
                mode = "-".join(parts[6:8])
                route = cold_boot_life_force_drone_door_probe_route(mode)
            elif parts[5] == "forward":
                route = cold_boot_life_force_drone_forward_probe_route(
                    int(parts[6])
                )
            else:
                strafe_retraces = int(parts[6])
                route = cold_boot_life_force_drone_approach_probe_route(
                    strafe_retraces
                )
        else:
            mode = arguments.scenario.removeprefix(
                "cold-boot-life-force-"
            ).removesuffix("-probe")
            route = cold_boot_life_force_direction_probe_route(mode)
    elif arguments.scenario == "controller-disconnect":
        route = controller_disconnect_route(source)
    elif arguments.scenario == "combat-probe":
        route = combat_probe_route(source)
    elif arguments.scenario == "combat-target-probe":
        route = combat_probe_route(source, targeting=True)
    elif arguments.scenario == "post-dialogue-combat-probe":
        route = post_dialogue_combat_probe_route(source)
    elif arguments.scenario.startswith("bypass-ambassador-"):
        route = bypass_ambassador_probe_route(
            source, right=arguments.scenario == "bypass-ambassador-right-probe"
        )
    elif arguments.scenario.startswith("dialogue-"):
        probe_buttons = {
            "dialogue-a-probe": 0x8000,
            "dialogue-b-probe": 0x4000,
            "dialogue-z-probe": 0x2000,
            "dialogue-start-probe": 0x1000,
        }
        route = dialogue_button_probe_route(source, probe_buttons[arguments.scenario])
    elif arguments.scenario == "fire-sequence-probe":
        route = fire_sequence_probe_route(source)
    elif arguments.scenario == "pursue-combat-probe":
        route = pursue_combat_probe_route(source)
    elif arguments.scenario == "hub-entry-probe":
        route = hub_entry_probe_route(source)
    elif arguments.scenario == "hub-after-magnus-probe":
        route = hub_after_magnus_probe_route(source)
    elif arguments.scenario == "complete-magnus-probe":
        route = complete_magnus_probe_route(source)
    elif arguments.scenario == "reach-jeff-probe":
        route = reach_jeff_probe_route(source)
    elif arguments.scenario == "cross-hub-bridge-probe":
        route = cross_hub_bridge_probe_route(source)
    elif arguments.scenario.startswith("strafe-hub-bridge-"):
        strafe_retraces = {
            "strafe-hub-bridge-probe": 300,
            "strafe-hub-bridge-40-probe": 40,
            "strafe-hub-bridge-80-probe": 80,
            "strafe-hub-bridge-120-probe": 120,
        }[arguments.scenario]
        route = strafe_hub_bridge_probe_route(
            source, strafe_retraces=strafe_retraces
        )
    elif arguments.scenario.startswith("bridge-heading-"):
        turn_retraces = int(arguments.scenario.split("-")[2])
        route = bridge_heading_probe_route(source, turn_retraces)
    elif arguments.scenario.startswith("island-path-"):
        mode = arguments.scenario.removeprefix("island-path-").removesuffix(
            "-probe"
        )
        route = island_path_probe_route(source, mode)
    elif arguments.scenario.startswith("island-shore-"):
        mode = arguments.scenario.removeprefix("island-shore-").removesuffix(
            "-probe"
        )
        route = island_shore_probe_route(source, mode)
    elif arguments.scenario == "reach-jeff-hut-probe":
        route = reach_jeff_hut_probe_route(source)
    elif arguments.scenario == "trigger-jeff-probe":
        route = trigger_jeff_probe_route(source)
    elif arguments.scenario == "jeff-hut-fire-probe":
        route = jeff_hut_fire_probe_route(source)
    elif arguments.scenario == "jeff-dialogue-exit-fire-probe":
        route = jeff_dialogue_exit_fire_probe_route(source)
    elif arguments.scenario.startswith("island-"):
        mode = arguments.scenario.removeprefix("island-").removesuffix("-probe")
        route = island_direction_probe_route(source, mode)
    elif arguments.scenario.startswith("bridge-guide-"):
        mode = arguments.scenario.removeprefix("bridge-guide-").removesuffix(
            "-probe"
        )
        route = bridge_guidance_probe_route(source, mode)
    elif arguments.scenario.startswith("bridge-jump-"):
        mode = arguments.scenario.removeprefix("bridge-jump-").removesuffix(
            "-probe"
        )
        route = bridge_jump_probe_route(source, mode)
    elif arguments.scenario == "exterior-fire-probe":
        route = exterior_fire_probe_route(source)
    elif arguments.scenario.startswith("shoreline-"):
        route = shoreline_probe_route(
            source, right=arguments.scenario == "shoreline-right-probe"
        )
    else:
        route = explore_turn_probe_route(
            source, right=arguments.scenario == "explore-right-probe"
        )
    write_replay(arguments.output, route)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
