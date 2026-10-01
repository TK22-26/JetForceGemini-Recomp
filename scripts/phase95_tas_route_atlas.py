"""Build a private, restartable endpoint atlas from the JP TAS state index.

This is an observation inventory, not a route proof or graph edge-coverage
producer. Different endpoint levels only bracket a possible transition; the
exact frame, intervening levels, requirements, and US/native parity are unknown.
"""

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import tempfile

from scripts.phase95_jp_observation import JPObservationError, PROFILE, decode


KIND = "jfg-phase95-jp-tas-route-atlas"
INDEX_KIND = "jfg-phase95-jp-tas-state-batch"
SCHEMA = 1
OUTPUT_NAME = "tas-route-atlas.json"
GRID_KIND = "jfg-phase95-jp-tas-sample-grid"


def _read_object(path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _validate_index(index):
    if (not isinstance(index, dict) or
            index.get("kind") != INDEX_KIND or index.get("schema") != SCHEMA or
            index.get("semantic_status") != "raw-unverified-jp" or
            type(index.get("movie_frames")) is not int or
            index["movie_frames"] < 1 or
            type(index.get("segments_total")) is not int or
            index["segments_total"] < 1 or
            not isinstance(index.get("entries"), list) or
            type(index.get("segments_extracted")) is not int or
            index["segments_extracted"] != len(index["entries"]) or
            len(index["entries"]) > index["segments_total"] or
            not isinstance(index.get("batch_plan_sha256"), str) or
            len(index["batch_plan_sha256"]) != 64 or
            any(char not in "0123456789abcdef"
                for char in index["batch_plan_sha256"]) or
            type(index.get("complete")) is not bool or
            type(index.get("batch_reported_complete")) is not bool):
        raise ValueError("invalid JP TAS state index")
    if index.get("complete") is True and (
            index.get("batch_reported_complete") is not True or
            len(index["entries"]) != index["segments_total"]):
        raise ValueError("index completion claim is inconsistent")


def _sample(entry, root, previous_frame, movie_frames, *, source=None):
    if not isinstance(entry, dict):
        raise ValueError("invalid index entry")
    frame = entry.get("frame")
    if type(frame) is not int or not previous_frame < frame < movie_frames:
        raise ValueError("state index frames must increase within movie")
    expected = entry.get("rdram_sha256")
    if not isinstance(expected, str) or len(expected) != 64 or any(
            char not in "0123456789abcdef" for char in expected):
        raise ValueError("invalid indexed RDRAM digest")
    raw_path = entry.get("rdram")
    if not isinstance(raw_path, str):
        raise ValueError("missing indexed RDRAM path")
    path = Path(raw_path).resolve()
    if not path.is_relative_to(root):
        raise ValueError("indexed RDRAM path leaves private batch root")
    data = path.read_bytes()
    if _sha256(data) != expected:
        raise ValueError(f"indexed RDRAM digest mismatch at frame {frame}")
    try:
        observation = decode(data, frame=frame)
    except JPObservationError as error:
        sample = {"frame": frame, "rdram": path.relative_to(root).as_posix(),
                  "rdram_sha256": expected, "profile": PROFILE,
                  "semantic_confidence": "unavailable at this sealed endpoint",
                  "observation_status": "unavailable",
                  "observation_error": str(error),
                  "front_mode": None, "level_id": None, "rng": None,
                  "actor_count": None, "actor_name_counts": None,
                  "actors": None, "player_resolution": "unavailable",
                  "player": None, "progression": None}
        if source is not None:
            sample["source"] = source
        return sample
    names = Counter(actor.name for actor in observation.actors)
    sample = {"frame": frame, "rdram": path.relative_to(root).as_posix(),
            "rdram_sha256": expected, "profile": observation.profile,
            "semantic_confidence": "JP resident-code-gated snapshot observation",
            "front_mode": observation.front_mode,
            "level_id": observation.level_id,
            "rng": observation.rng,
            "actor_count": observation.actor_count,
            "actor_name_counts": dict(sorted(names.items())),
            "actors": [{"name": actor.name, "yaw": actor.yaw,
                        "position": list(actor.position),
                        "snapshot_address": actor.address}
                       for actor in observation.actors],
            "player_resolution": observation.player_resolution,
            "player": ({"name": observation.player.name,
                        "position": list(observation.player.position),
                        "snapshot_address": observation.player.address}
                       if observation.player is not None else None),
            "progression": None}
    if source is not None:
        sample["source"] = source
    return sample


def _transitions(samples):
    return [{"from_frame": before["frame"], "to_frame": after["frame"],
             "from_level": before["level_id"], "to_level": after["level_id"],
             "exact_transition_frame": None,
             "confidence": "endpoint-bracket-only",
             "intermediate_levels_unknown": True,
             "graph_edge_covered": False}
            for before, after in zip(samples, samples[1:])
            if before["level_id"] is not None and after["level_id"] is not None
            and before["level_id"] != after["level_id"]]


def _load_grid(progress_path, index, batch_root):
    """Verify a separate sealed-grid lineage before reading its RAM samples."""
    progress_path = Path(progress_path).resolve()
    grid_root = progress_path.parent
    if progress_path.name != "sample-grid-progress.json":
        raise ValueError("expected sealed sample-grid progress file")
    if index.get("complete") is not True:
        raise ValueError("grid ingestion requires a complete endpoint index")
    batch_plan_bytes = (batch_root / "batch.json").read_bytes()
    if _sha256(batch_plan_bytes) != index["batch_plan_sha256"]:
        raise ValueError("source batch plan differs from endpoint index pin")
    batch_plan = json.loads(batch_plan_bytes)
    if not isinstance(batch_plan, dict) or not isinstance(batch_plan.get("pins"), dict):
        raise ValueError("invalid source batch plan")
    plan_path = grid_root / "sample-grid.json"
    plan_bytes = plan_path.read_bytes()
    plan = json.loads(plan_bytes)
    progress = _read_object(progress_path)
    plan_hash = _sha256(plan_bytes)
    endpoints = {item["frame"] for item in index["entries"]}
    if (not isinstance(plan, dict) or plan.get("kind") != GRID_KIND or
            plan.get("schema") != SCHEMA or
            plan.get("semantic_status") != "raw-unverified-jp" or
            not isinstance(plan.get("source_batch"), str) or
            Path(plan["source_batch"]).resolve() != batch_root or
            plan.get("source_batch_plan_sha256") != index["batch_plan_sha256"] or
            plan.get("movie_frames") != index["movie_frames"] or
            type(plan.get("spacing")) is not int or plan["spacing"] != 5000 or
            type(plan.get("interval")) is not int or plan["interval"] < 1 or
            type(plan.get("timeout")) is not int or plan["timeout"] < 1 or
            not isinstance(plan.get("targets"), list)):
        raise ValueError("grid plan differs from pinned batch or 5k grid")
    for key in ("sampler_sha256", "grid_script_sha256", "extractor_sha256"):
        value = plan.get(key)
        if not isinstance(value, str) or len(value) != 64 or any(
                char not in "0123456789abcdef" for char in value):
            raise ValueError(f"invalid sealed-grid {key}")
    expected_targets = [frame for frame in range(4999, index["movie_frames"], 5000)
                        if frame not in endpoints]
    if plan["targets"] != expected_targets:
        raise ValueError("grid targets differ from expected sealed 5k cells")
    if (progress.get("kind") != GRID_KIND or progress.get("schema") != SCHEMA or
            progress.get("semantic_status") != "raw-unverified-jp" or
            progress.get("grid_plan_sha256") != plan_hash or
            type(progress.get("targets_total")) is not int or
            progress["targets_total"] != len(expected_targets) or
            not isinstance(progress.get("entries"), list) or
            type(progress.get("samples_complete")) is not int or
            progress["samples_complete"] != len(progress["entries"]) or
            type(progress.get("complete")) is not bool or
            not isinstance(progress.get("errors"), list) or
            (progress["complete"] and
             (len(progress["entries"]) != len(expected_targets) or progress["errors"]))):
        raise ValueError("invalid or inconsistent sealed-grid progress")
    samples = []
    previous_grid_frame = -1
    for item in progress["entries"]:
        if not isinstance(item, dict):
            raise ValueError("invalid sealed-grid entry")
        frame = item.get("frame")
        if (type(frame) is not int or frame not in expected_targets or
                frame <= previous_grid_frame):
            raise ValueError("grid entry is outside ordered 5k targets")
        previous_grid_frame = frame
        attempt_text = item.get("attempt")
        if not isinstance(attempt_text, str):
            raise ValueError("missing sealed-grid attempt path")
        attempt = Path(attempt_text).resolve()
        if (not attempt.is_relative_to(grid_root) or
                attempt.parent != grid_root / "samples" / f"frame-{frame:06d}" or
                not attempt.name.startswith("attempt-")):
            raise ValueError("grid attempt path or frame lineage differs")
        result_path = attempt / "sample-result.json"
        result_bytes = result_path.read_bytes()
        if _sha256(result_bytes) != item.get("sample_result_sha256"):
            raise ValueError("sealed-grid sample result digest mismatch")
        result = json.loads(result_bytes)
        request = _read_object(attempt / "sample-request.json")
        prior = next((entry for entry in reversed(index["entries"])
                      if entry["frame"] < frame), None)
        prior_attempt = Path(prior["attempt"]).resolve() if prior else None
        if prior_attempt is not None and not prior_attempt.is_relative_to(batch_root):
            raise ValueError("grid predecessor leaves source batch root")
        if prior_attempt is not None:
            prior_result = _read_object(prior_attempt / "result.json")
            if (prior_result.get("complete") is not True or
                    prior_result.get("last") != prior["frame"] or
                    prior_result.get("continuation_sha256") !=
                        prior["continuation_sha256"]):
                raise ValueError("grid predecessor is not the sealed indexed segment")
        expected = {"kind": "jfg-phase95-jp-tas-frame-sample", "schema": 1,
                    "target_frame": frame, "capture_first": prior["frame"] + 1 if prior else 0,
                    "source_batch": str(batch_root),
                    "source_batch_plan_sha256": index["batch_plan_sha256"],
                    "sealed_predecessor": str(prior_attempt) if prior else None,
                    "sealed_predecessor_sha256":
                        prior["continuation_sha256"] if prior else None,
                    "interval": plan["interval"], "timeout": plan["timeout"],
                    "semantic_status": "raw-unverified-jp",
                    "sampler_sha256": plan.get("sampler_sha256"),
                    "capture_driver_sha256": batch_plan.get("driver_sha256"),
                    "capture_lua_sha256": batch_plan["pins"].get("script_sha256")}
        if (not isinstance(result, dict) or result.get("complete") is not True or
                any(result.get(key) != value or request.get(key) != value
                    for key, value in expected.items()) or
                result.get("rdram") != item.get("rdram") or
                result.get("rdram_sha256") != item.get("rdram_sha256") or
                result.get("continuation_sha256") != item.get("continuation_sha256")):
            raise ValueError("sealed-grid sample pins or lineage differ")
        captured_path = attempt / "capture" / "result.json"
        captured_bytes = captured_path.read_bytes()
        captured = json.loads(captured_bytes)
        if (result.get("capture_result_sha256") != _sha256(captured_bytes) or
                not isinstance(captured, dict) or captured.get("complete") is not True or
                captured.get("first") != expected["capture_first"] or
                captured.get("last") != frame or
                captured.get("resume_from") != expected["sealed_predecessor"] or
                captured.get("parent_continuation_sha256") !=
                    expected["sealed_predecessor_sha256"] or
                captured.get("continuation_sha256") != item["continuation_sha256"]):
            raise ValueError("sealed-grid capture result lineage differs")
        raw_path = Path(item["rdram"]).resolve()
        if raw_path != attempt / "capture" / "state-extract" / f"frame-{frame:06d}.rdram":
            raise ValueError("sealed-grid RDRAM path differs from capture")
        manifest = _read_object(raw_path.parent / "manifest.json")
        if (manifest.get("frame") != frame or
                manifest.get("kind") != "jfg-phase95-jp-tas-state-extract" or
                manifest.get("schema") != SCHEMA or
                manifest.get("semantic_status") != "raw-unverified-jp" or
                manifest.get("source_segment") != str(attempt / "capture") or
                manifest.get("source_result_sha256") != _sha256(captured_bytes) or
                manifest.get("source_state_sha256") != item["continuation_sha256"] or
                manifest.get("rdram_bytes") != 8 * 1024 * 1024 or
                manifest.get("rdram_sha256") != item["rdram_sha256"]):
            raise ValueError("sealed-grid extraction manifest differs")
        source = {"kind": "sealed-grid", "grid_plan_sha256": plan_hash,
                  "sample_result_sha256": item["sample_result_sha256"],
                  "continuation_sha256": item["continuation_sha256"]}
        samples.append(_sample(item, grid_root, -1, index["movie_frames"],
                               source=source))
    if progress.get("last_sampled_frame") != (previous_grid_frame if samples else None):
        raise ValueError("sealed-grid last sampled frame differs")
    provenance = {"grid_root": str(grid_root), "grid_plan_sha256": plan_hash,
                  "grid_progress_sha256": _sha256(progress_path.read_bytes()),
                  "source_batch_plan_sha256": index["batch_plan_sha256"],
                  "spacing": 5000, "targets_total": len(expected_targets),
                  "samples_complete": len(samples), "complete": progress["complete"],
                  "errors": progress["errors"]}
    return samples, provenance


def build_atlas(index_path, output_path=None, *, grid_progress_path=None):
    index_path = Path(index_path).resolve()
    root = index_path.parent
    output = Path(output_path).resolve() if output_path is not None else root / OUTPUT_NAME
    if not output.is_relative_to(root) or output == index_path:
        raise ValueError("atlas output must be a separate file within the private batch root")
    index_bytes = index_path.read_bytes()
    index = json.loads(index_bytes)
    _validate_index(index)
    endpoint_samples = []
    previous_frame = -1
    for entry in index["entries"]:
        sample = _sample(entry, root, previous_frame, index["movie_frames"])
        endpoint_samples.append(sample)
        previous_frame = sample["frame"]
    if index.get("last_extracted_frame") != (previous_frame if endpoint_samples else None):
        raise ValueError("state index last frame disagrees with entries")
    if index.get("complete") is True and previous_frame != index["movie_frames"] - 1:
        raise ValueError("complete index does not reach final movie frame")
    grid_samples, grid_provenance = ([], None)
    if grid_progress_path is not None:
        grid_samples, grid_provenance = _load_grid(grid_progress_path, index, root)
    samples = sorted((*endpoint_samples, *grid_samples), key=lambda item: item["frame"])
    if len({item["frame"] for item in samples}) != len(samples):
        raise ValueError("grid and batch samples overlap")
    transitions = _transitions(samples)
    atlas = {"kind": KIND, "schema": SCHEMA, "acceptance": False,
             "full_game_acceptance": False,
             "route_complete": index.get("complete") is True,
             "source_index": index_path.name,
             "source_index_sha256": _sha256(index_bytes),
             "batch_plan_sha256": index["batch_plan_sha256"],
             "movie_frames": index["movie_frames"],
             "segments_total": index["segments_total"],
             "segments_indexed": len(endpoint_samples),
             "last_sample_frame": samples[-1]["frame"] if samples else None,
             "semantic_profile": PROFILE,
             "semantic_confidence": "JP code-gated endpoint observations only",
             "grid_provenance": grid_provenance,
             "grid_complete": (grid_provenance["complete"]
                               if grid_provenance is not None else None),
             "samples": samples, "candidate_level_transitions": transitions,
             "limitations": [
                 "One TAS is one route, not full-game gameplay coverage.",
                 "Endpoint changes do not establish exact transitions or intermediate levels.",
                 "Equal endpoint levels do not prove the level stayed unchanged between samples.",
                 "Actor presence does not prove interaction, objective completion or reachability.",
                 "Undecodable transitional states are retained without semantic claims.",
                 "No US/native parity or graph-edge coverage is inferred.",
             ]}
    if output.exists():
        old = _read_object(output)
        if (old.get("kind") != KIND or old.get("schema") != SCHEMA or
                old.get("acceptance") is not False or
                old.get("full_game_acceptance") is not False or
                (old.get("route_complete") is True and not atlas["route_complete"]) or
                old.get("batch_plan_sha256") != atlas["batch_plan_sha256"] or
                old.get("movie_frames") != atlas["movie_frames"] or
                old.get("semantic_profile") != PROFILE or
                not isinstance(old.get("samples"), list) or
                any(sample not in samples for sample in old["samples"]) or
                old.get("candidate_level_transitions") != _transitions(old["samples"]) or
                (old.get("grid_provenance") is not None and
                 (not isinstance(old["grid_provenance"], dict) or
                  grid_provenance is None or
                  old["grid_provenance"].get("grid_plan_sha256") !=
                  grid_provenance["grid_plan_sha256"]))):
            raise ValueError("existing atlas is not a compatible resume prefix")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output.parent,
                                         prefix=f".{output.name}.", suffix=".tmp",
                                         delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(atlas, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return atlas


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--grid-progress", type=Path)
    args = parser.parse_args()
    print(json.dumps(build_atlas(args.index, args.output,
                                 grid_progress_path=args.grid_progress),
                     sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
