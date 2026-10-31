import hashlib
import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest

from scripts.phase95_jp_observation import (
    ACTOR_COUNT, ACTOR_LIST, CANDIDATE_PLAYER_POINTER, CODE_SIGNATURES,
    FRONT_MODE, LEVEL_WORD, RDRAM_SIZE, RNG_SEED,
)
from scripts.phase95_tas_route_atlas import build_atlas


def snapshot(level, *, actor=True):
    memory = bytearray(RDRAM_SIZE)
    for offset, signature in CODE_SIGNATURES:
        memory[offset:offset + len(signature)] = signature
    memory[FRONT_MODE] = 16
    struct.pack_into(">i", memory, LEVEL_WORD, level)
    struct.pack_into(">I", memory, RNG_SEED, 0x12345678 + level)
    struct.pack_into(">II", memory, ACTOR_LIST, 0x80003000, int(actor))
    if actor:
        struct.pack_into(">I", memory, 0x3000, 0x80004000)
        struct.pack_into(">I", memory, CANDIDATE_PLAYER_POINTER, 0x80004000)
        struct.pack_into(">fff", memory, 0x400C, 1.0, 2.0, 3.0)
        struct.pack_into(">I", memory, 0x4040, 0x80005000)
        memory[0x5004:0x5004 + len(b"playerBoy")] = b"playerBoy"
    return bytes(memory)


def write_index(root, levels, *, frames=None, complete=False):
    frames = frames or [99 + 100 * i for i in range(len(levels))]
    status = complete
    entries = []
    for frame, level in zip(frames, levels):
        path = root / f"frame-{frame:06d}.rdram"
        data = snapshot(level, actor=frame != 199)
        path.write_bytes(data)
        entries.append({"frame": frame, "rdram": str(path),
                        "rdram_sha256": hashlib.sha256(data).hexdigest()})
    index = {"kind": "jfg-phase95-jp-tas-state-batch", "schema": 1,
             "semantic_status": "raw-unverified-jp", "movie_frames": 300,
             "segments_total": 3, "segments_extracted": len(entries),
             "last_extracted_frame": frames[-1] if frames else None,
             "batch_plan_sha256": hashlib.sha256(b"synthetic batch plan").hexdigest(),
             "batch_reported_complete": status, "complete": status,
             "entries": entries}
    path = root / "tas-state-index.json"
    path.write_text(json.dumps(index), encoding="utf-8")
    return path


def sealed_grid_fixture(root, *, grid_samples=((4999, 48, True),),
                        grid_complete=False):
    batch_root, grid_root = root / "batch", root / "grid"
    batch_root.mkdir(exist_ok=True)
    grid_root.mkdir(exist_ok=True)
    batch_plan = {"kind": "jfg-phase95-jp-tas-capture-batch",
                  "driver_sha256": "d" * 64,
                  "pins": {"script_sha256": "e" * 64}}
    plan_bytes = json.dumps(batch_plan).encode()
    (batch_root / "batch.json").write_bytes(plan_bytes)
    batch_hash = hashlib.sha256(plan_bytes).hexdigest()
    endpoints = ((3999, 47), (7999, 48), (11999, 49), (14999, 50))
    index_entries = []
    for frame, level in endpoints:
        attempt = batch_root / "segments" / f"segment-{frame:06d}" / "attempt-0000"
        attempt.mkdir(parents=True, exist_ok=True)
        continuation = f"{frame:064x}"
        (attempt / "result.json").write_text(json.dumps({
            "complete": True, "last": frame,
            "continuation_sha256": continuation}))
        path = attempt / "state-extract" / f"frame-{frame:06d}.rdram"
        path.parent.mkdir(exist_ok=True)
        data = snapshot(level)
        path.write_bytes(data)
        index_entries.append({"frame": frame, "attempt": str(attempt),
                              "continuation_sha256": continuation,
                              "rdram": str(path),
                              "rdram_sha256": hashlib.sha256(data).hexdigest()})
    index = {"kind": "jfg-phase95-jp-tas-state-batch", "schema": 1,
             "semantic_status": "raw-unverified-jp", "movie_frames": 15000,
             "segments_total": 4, "segments_extracted": 4,
             "last_extracted_frame": 14999,
             "batch_plan_sha256": batch_hash,
             "batch_reported_complete": True, "complete": True,
             "entries": index_entries}
    index_path = batch_root / "tas-state-index.json"
    index_path.write_text(json.dumps(index))
    grid_plan = {"kind": "jfg-phase95-jp-tas-sample-grid", "schema": 1,
                 "semantic_status": "raw-unverified-jp",
                 "source_batch": str(batch_root),
                 "source_batch_plan_sha256": batch_hash,
                 "movie_frames": 15000, "spacing": 5000,
                 "interval": 5000, "timeout": 3600,
                 "targets": [4999, 9999],
                 "sampler_sha256": "a" * 64,
                 "grid_script_sha256": "b" * 64,
                 "extractor_sha256": "c" * 64}
    grid_plan_bytes = json.dumps(grid_plan).encode()
    (grid_root / "sample-grid.json").write_bytes(grid_plan_bytes)
    grid_plan_hash = hashlib.sha256(grid_plan_bytes).hexdigest()
    grid_entries = []
    for frame, level, decodable in grid_samples:
        prior = max((item for item in index_entries if item["frame"] < frame),
                    key=lambda item: item["frame"])
        attempt = grid_root / "samples" / f"frame-{frame:06d}" / "attempt-0000"
        extract = attempt / "capture" / "state-extract"
        extract.mkdir(parents=True, exist_ok=True)
        path = extract / f"frame-{frame:06d}.rdram"
        data = bytearray(snapshot(level))
        if not decodable:
            struct.pack_into(">I", data, ACTOR_COUNT, 9999)
        path.write_bytes(data)
        rdram_hash = hashlib.sha256(data).hexdigest()
        continuation = f"{frame:064x}"
        captured = {"complete": True, "first": prior["frame"] + 1,
                    "last": frame, "resume_from": prior["attempt"],
                    "parent_continuation_sha256": prior["continuation_sha256"],
                    "continuation_sha256": continuation}
        captured_bytes = json.dumps(captured).encode()
        (attempt / "capture" / "result.json").write_bytes(captured_bytes)
        captured_hash = hashlib.sha256(captured_bytes).hexdigest()
        (extract / "manifest.json").write_text(json.dumps({
            "kind": "jfg-phase95-jp-tas-state-extract", "schema": 1,
            "semantic_status": "raw-unverified-jp", "frame": frame,
            "source_segment": str(attempt / "capture"),
            "source_result_sha256": captured_hash,
            "source_state_sha256": continuation,
            "rdram_bytes": RDRAM_SIZE,
            "rdram_sha256": rdram_hash}))
        common = {"kind": "jfg-phase95-jp-tas-frame-sample", "schema": 1,
                  "target_frame": frame, "capture_first": prior["frame"] + 1,
                  "source_batch": str(batch_root),
                  "source_batch_plan_sha256": batch_hash,
                  "sealed_predecessor": prior["attempt"],
                  "sealed_predecessor_sha256": prior["continuation_sha256"],
                  "interval": 5000, "timeout": 3600,
                  "semantic_status": "raw-unverified-jp",
                  "sampler_sha256": "a" * 64,
                  "capture_driver_sha256": "d" * 64,
                  "capture_lua_sha256": "e" * 64}
        (attempt / "sample-request.json").write_text(json.dumps(common))
        result = {**common, "complete": True,
                  "capture_result_sha256": captured_hash,
                  "continuation_sha256": continuation,
                  "rdram": str(path), "rdram_sha256": rdram_hash}
        result_bytes = json.dumps(result).encode()
        (attempt / "sample-result.json").write_bytes(result_bytes)
        grid_entries.append({"frame": frame, "attempt": str(attempt),
                             "rdram": str(path), "rdram_sha256": rdram_hash,
                             "continuation_sha256": continuation,
                             "sample_result_sha256":
                                 hashlib.sha256(result_bytes).hexdigest()})
    progress = {"kind": grid_plan["kind"], "schema": 1,
                "semantic_status": "raw-unverified-jp",
                "grid_plan_sha256": grid_plan_hash, "targets_total": 2,
                "samples_complete": len(grid_entries),
                "last_sampled_frame": grid_entries[-1]["frame"] if grid_entries else None,
                "complete": grid_complete, "errors": [], "entries": grid_entries}
    progress_path = grid_root / "sample-grid-progress.json"
    progress_path.write_text(json.dumps(progress))
    return index_path, progress_path


class TASRouteAtlasTests(unittest.TestCase):
    def test_partial_resume_and_endpoint_only_transition(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            index_path = write_index(root, [47, 48])
            first = build_atlas(index_path)
            self.assertFalse(first["route_complete"])
            self.assertFalse(first["full_game_acceptance"])
            self.assertEqual(first["segments_indexed"], 2)
            self.assertEqual(first["samples"][0]["actor_name_counts"],
                             {"playerBoy": 1})
            self.assertEqual(first["samples"][1]["actor_count"], 0)
            self.assertEqual(first["candidate_level_transitions"], [{
                "from_frame": 99, "to_frame": 199,
                "from_level": 47, "to_level": 48,
                "exact_transition_frame": None,
                "confidence": "endpoint-bracket-only",
                "intermediate_levels_unknown": True,
                "graph_edge_covered": False}])
            index_path = write_index(root, [47, 48, 48], complete=True)
            second = build_atlas(index_path)
            self.assertTrue(second["route_complete"])
            self.assertFalse(second["full_game_acceptance"])
            self.assertEqual(second["samples"][:2], first["samples"])
            self.assertEqual(len(second["candidate_level_transitions"]), 1)
            encoded = (root / "tas-route-atlas.json").read_bytes()
            build_atlas(index_path)
            self.assertEqual((root / "tas-route-atlas.json").read_bytes(), encoded)

    def test_digest_and_frame_order_fail_closed(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            index_path = write_index(root, [47, 48])
            index = json.loads(index_path.read_text())
            index["entries"][1]["rdram_sha256"] = hashlib.sha256(
                b"wrong synthetic state").hexdigest()
            index_path.write_text(json.dumps(index))
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                build_atlas(index_path)
            self.assertFalse((root / "tas-route-atlas.json").exists())
            index["entries"][1]["rdram_sha256"] = hashlib.sha256(
                (root / "frame-000199.rdram").read_bytes()).hexdigest()
            index["entries"][1]["frame"] = 99
            index["last_extracted_frame"] = 99
            index_path.write_text(json.dumps(index))
            with self.assertRaisesRegex(ValueError, "frames must increase"):
                build_atlas(index_path)

    def test_resume_conflict_and_path_escape_rejected(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            index_path = write_index(root, [47])
            build_atlas(index_path)
            index_path = write_index(root, [48])
            with self.assertRaisesRegex(ValueError, "compatible resume prefix"):
                build_atlas(index_path)
            index = json.loads(index_path.read_text())
            index["entries"][0]["rdram"] = str(root.parent / "outside.rdram")
            index_path.write_text(json.dumps(index))
            with self.assertRaisesRegex(ValueError, "leaves private batch root"):
                build_atlas(index_path)

    def test_sealed_partial_grid_refines_bracket_and_keeps_acceptance_false(self):
        with TemporaryDirectory() as directory:
            index_path, progress_path = sealed_grid_fixture(Path(directory))
            first = build_atlas(index_path)
            self.assertEqual(first["candidate_level_transitions"][0]["to_frame"], 7999)
            atlas = build_atlas(index_path, grid_progress_path=progress_path)
            self.assertTrue(atlas["route_complete"])
            self.assertFalse(atlas["grid_complete"])
            self.assertFalse(atlas["full_game_acceptance"])
            self.assertEqual(atlas["grid_provenance"]["samples_complete"], 1)
            self.assertEqual(atlas["candidate_level_transitions"][0]["to_frame"], 4999)
            self.assertFalse(atlas["candidate_level_transitions"][0]["graph_edge_covered"])
            encoded = (index_path.parent / "tas-route-atlas.json").read_bytes()
            build_atlas(index_path, grid_progress_path=progress_path)
            self.assertEqual((index_path.parent / "tas-route-atlas.json").read_bytes(),
                             encoded)

    def test_undecodable_grid_state_is_retained_without_level_claim(self):
        with TemporaryDirectory() as directory:
            index_path, progress_path = sealed_grid_fixture(
                Path(directory), grid_samples=((4999, 48, False),),
                grid_complete=False)
            atlas = build_atlas(index_path, grid_progress_path=progress_path)
            grid_sample = next(item for item in atlas["samples"]
                               if item["frame"] == 4999)
            self.assertEqual(grid_sample["observation_status"], "unavailable")
            self.assertIsNone(grid_sample["level_id"])
            self.assertEqual(grid_sample["source"]["kind"], "sealed-grid")
            self.assertFalse(any(item["from_frame"] == 3999 and
                                 item["to_frame"] == 7999
                                 for item in atlas["candidate_level_transitions"]))

    def test_partial_grid_resumes_to_complete_without_promoting_acceptance(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            index_path, progress_path = sealed_grid_fixture(root)
            partial = build_atlas(index_path, grid_progress_path=progress_path)
            first_grid_sample = next(item for item in partial["samples"]
                                     if item["frame"] == 4999)
            index_path, progress_path = sealed_grid_fixture(
                root, grid_samples=((4999, 48, True), (9999, 49, True)),
                grid_complete=True)
            complete = build_atlas(index_path, grid_progress_path=progress_path)
            self.assertTrue(complete["grid_complete"])
            self.assertEqual(complete["grid_provenance"]["samples_complete"], 2)
            self.assertEqual(next(item for item in complete["samples"]
                                  if item["frame"] == 4999), first_grid_sample)
            self.assertFalse(complete["full_game_acceptance"])
            self.assertTrue(all(not item["graph_edge_covered"]
                                for item in complete["candidate_level_transitions"]))

    def test_grid_result_digest_and_lineage_fail_closed(self):
        with TemporaryDirectory() as directory:
            index_path, progress_path = sealed_grid_fixture(Path(directory))
            progress = json.loads(progress_path.read_text())
            progress["entries"][0]["sample_result_sha256"] = "0" * 64
            progress_path.write_text(json.dumps(progress))
            with self.assertRaisesRegex(ValueError, "sample result digest mismatch"):
                build_atlas(index_path, grid_progress_path=progress_path)
            self.assertFalse((index_path.parent / "tas-route-atlas.json").exists())

            progress["entries"][0]["sample_result_sha256"] = hashlib.sha256(
                (progress_path.parent / "samples" / "frame-004999" /
                 "attempt-0000" / "sample-result.json").read_bytes()).hexdigest()
            progress_path.write_text(json.dumps(progress))
            request_path = (progress_path.parent / "samples" / "frame-004999" /
                            "attempt-0000" / "sample-request.json")
            request = json.loads(request_path.read_text())
            request["sealed_predecessor_sha256"] = "0" * 64
            request_path.write_text(json.dumps(request))
            with self.assertRaisesRegex(ValueError, "sample pins or lineage differ"):
                build_atlas(index_path, grid_progress_path=progress_path)


if __name__ == "__main__":
    unittest.main()
