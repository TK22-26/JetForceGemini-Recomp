"""Check a stationary, single-player Modern Aim-release native replay.

Run with JFG_DIAGNOSTIC_CAMERA_MOTION=1 and JFG_GAMEPLAY_TRACE. The fixture
must hold ground Aim to settle, release without moving/looking, and remain
idle for at least 40 source updates on an unobstructed route. The first return
update must be at most 50 ms. This is a trajectory contract, not a
visual, collision, multiplayer or whole-game acceptance test.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct


def floats(words):
    values = tuple(struct.unpack(">f", struct.pack(">I", word))[0] for word in words)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("non-finite camera observation")
    return values


def camera_position(words):
    """Invert the actual emitted orthonormal row-vector view transform."""
    m = floats(words)
    if len(m) != 16 or any(abs(m[i]) > 0.001 for i in (3, 7, 11)) or abs(m[15]-1) > 0.001:
        raise ValueError("camera observation is not an affine view")
    for row in range(3):
        for column in range(3):
            dot = sum(m[row*4+i]*m[column*4+i] for i in range(3))
            if abs(dot-(row == column)) > 0.002:
                raise ValueError("camera view basis is not orthonormal")
    return tuple(-sum(m[row*4+i]*m[12+i] for i in range(3)) for row in range(3))


def analyze(lines, minimum_releases=2, settle_frames=40):
    if minimum_releases < 1 or settle_frames < 6:
        raise ValueError("invalid qualification coverage")
    frames = []
    pending_normal = {}
    pending_start = set()
    pending_time = {}
    counts = {}
    lengths = {"pc-shoulder": 15, "pc-shoulder-camera": 7,
               "pc-aim-return-start": 5, "pc-aim-return": 10, "camera-emitted-pose": 54}
    for line in lines:
        cells = line.strip().split("\t")
        if len(cells) < 2 or cells[1] not in lengths:
            continue
        event = cells[1]
        if len(cells) != lengths[event]+2:
            raise ValueError("malformed "+event)
        words = [int(value, 16) for value in cells[2:]]
        counts[event] = counts.get(event, 0)+1
        if event == "pc-shoulder":
            # VI can advance between player update and camera emission. Pair
            # the ordered producer calls, not equal VI timestamps.
            frame = {"state": words, "views": [],
                     "started": words[1] in pending_start,
                     "seconds": pending_time.pop(words[1], None)}
            pending_start.discard(words[1])
            if words[1] in pending_normal:
                frame["normal"] = pending_normal.pop(words[1])
            frames.append(frame)
        elif event == "pc-shoulder-camera":
            pending_normal[words[1]] = floats(words[4:7])
        elif event == "pc-aim-return":
            pending_time[words[1]] = floats(words[2:3])[0]/60
        elif event == "pc-aim-return-start":
            if words[1] in pending_start:
                raise ValueError("duplicate return start")
            pending_start.add(words[1])
        elif frames:
            frames[-1]["views"].append((words[1], words[3], words[4],
                                       words[5], words[6:22], words[22:38]))
    ordered = []
    maximum_adapter_error = 0.0
    projections = []
    durations = []
    for index, frame in enumerate(frames):
        if not frame["views"]:
            if index == len(frames)-1:
                continue  # Clean close may interrupt the final unrendered update.
            raise ValueError("player update has no emitted camera")
        views = [(level, vp0, vp1, update, camera_position(matrix))
                 for level, vp0, vp1, update, matrix, _ in frame["views"]]
        level, vp0, vp1, update, point = views[0]
        if any((a, b, c, d) != (level, vp0, vp1, update) or math.dist(p, point) > 0.005
               for a, b, c, d, p in views):
            raise ValueError("ambiguous emitted camera for a player update")
        if "normal" in frame:
            error = math.dist(point, frame["normal"])
            maximum_adapter_error = max(error, maximum_adapter_error)
            if error > 0.01:
                raise ValueError("rendered camera differs from the final normal-camera adapter")
        projection = floats(frame["views"][0][5])
        if projection[0] <= 0 or projection[5] <= 0 or abs(projection[11]+1) > 0.001 or abs(projection[15]) > 0.001:
            raise ValueError("camera observation has no valid perspective projection")
        projections.append(projection)
        durations.append(frame["seconds"])
        state = frame["state"]
        ordered.append((state[0], state, level, point, frame["started"]))
    releases = []
    failures = []
    for index in range(1, len(ordered)):
        previous = ordered[index-1]
        current = ordered[index]
        vi, state, level, first, started = current
        if previous[1][1] != state[1] or previous[1][2] not in (10, 11) or state[2] != 0:
            continue
        window = ordered[index:index+settle_frames]
        if len(window) != settle_frames:
            failures.append("release lacks a complete settling window")
            continue
        body = floats(state[7:10])
        if previous[2] != level or previous[1][12:14] != state[12:14]:
            failures.append("release fixture changes level or view angle at release")
            continue
        if any(s[1] != state[1] or s[2] != 0 or scene != level or
               s[12:14] != state[12:14] or math.dist(floats(s[7:10]), body) > 0.01
               for _, s, scene, _, _ in window):
            failures.append("release fixture moves, looks, changes camera ownership or changes level")
            continue
        points = [previous[3]]+[row[3] for row in window]
        target = points[-1]
        distance = math.dist(points[0], target)
        if distance < 5:
            failures.append("release fixture has no meaningful camera displacement")
            continue
        steps = [math.dist(a, b) for a, b in zip(points, points[1:])]
        residuals = [math.dist(point, target) for point in points]
        monotonic = all(b <= a+0.02 for a, b in zip(residuals, residuals[1:]))
        changing = sum(step > 0.05 for step in steps)
        settled = max(math.dist(point, target) for point in points[-5:]) <= max(0.1, distance*0.005)
        direction = tuple((b-a)/distance for a, b in zip(points[0], target))
        deviations = []
        for point in points:
            delta = tuple(b-a for a, b in zip(points[0], point))
            along = sum(a*b for a, b in zip(delta, direction))
            deviations.append(math.sqrt(sum((a-along*b)**2 for a, b in zip(delta, direction))))
        path_error = max(deviations)/distance
        zoom = projections[index-1:index+settle_frames]
        projection_step = max(abs(b[k]/a[k]-1) for a, b in zip(zoom, zoom[1:]) for k in (0, 5))
        # This deliberately rejects a large first hop followed by a smooth tail,
        # and a bent/stalled recovery path even if distance to the end decreases.
        seconds = durations[index:index+settle_frames]
        rates = [step/distance/dt if dt is not None and dt > 0 else
                 (0 if step < 0.01 else math.inf) for step, dt in zip(steps, seconds)]
        first_interval_valid = seconds[0] is not None and 0 < seconds[0] <= 0.050001
        passed = (first_interval_valid and steps[0]/distance < 0.10 and max(rates) < 4.0 and
                  path_error < 0.01 and projection_step < 0.03 and
                  changing >= 6 and monotonic and settled and started)
        releases.append({"vi": vi, "distance": distance,
                         "first_step_fraction": steps[0]/distance,
                         "maximum_step_fraction": max(steps)/distance,
                         "maximum_step_rate_per_second": max(rates) if math.isfinite(max(rates)) else None,
                         "first_update_seconds": seconds[0],
                         "maximum_path_deviation_fraction": path_error,
                         "maximum_projection_step_fraction": projection_step,
                         "changing_updates": changing, "monotonic": monotonic,
                         "settled": settled, "return_started": started, "passed": passed})
        if not passed:
            failures.append("rendered return lurches, bends, changes projection abruptly, fails to settle, or was not armed")
    if len(releases) < minimum_releases:
        failures.append("insufficient qualified ground-Aim releases")
    return {"complete": not failures, "releases": releases, "failures": failures,
            "maximum_adapter_error": maximum_adapter_error, "event_counts": counts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--run-result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--minimum-releases", type=int, default=2)
    args = parser.parse_args()
    run = json.loads(args.run_result.read_text(encoding="utf-8"))
    if run.get("exit_code") != 0 or not run.get("close_window_pids") or run.get("forced_cleanup"):
        raise ValueError("native replay did not close normally")
    with args.trace.open(encoding="utf-8") as stream:
        result = analyze(stream, args.minimum_releases)
    with args.trace.open("rb") as stream:
        result["trace_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
    result["identity"] = run["identity"]
    args.output.write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result))
    return 0 if result["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
