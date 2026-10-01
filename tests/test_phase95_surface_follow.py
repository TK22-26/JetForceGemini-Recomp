import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.phase95_surface_follow import follow
from scripts.phase95_observation import ObservationError


class SurfaceFollowTests(unittest.TestCase):
    def test_named_actor_route_keeps_interaction_unverified(self):
        with TemporaryDirectory() as directory:
            memory = bytearray(0x100000)
            struct.pack_into(">i", memory, 0xFB114, 47)
            actor = SimpleNamespace(name="MrHints2", address=0x80005000,
                                    position=(100.0, 0.0, 0.0))
            initial = SimpleNamespace(front_mode=16, player=SimpleNamespace(position=(0.0, 0.0, 0.0)),
                                      actors=[actor])
            final = SimpleNamespace(front_mode=16, player=SimpleNamespace(position=(100.0, 0.0, 0.0)),
                                    actors=[actor])
            worker = SimpleNamespace(root=Path(directory),
                                     observe=lambda: ({"sequence": 1, "player": 0x80001000}, memory))
            proposal = {"waypoints": [(0.0, 0.0, 0.0), (40.0, 0.0, 0.0)]}
            with patch("scripts.phase95_surface_follow.decode", side_effect=[initial, initial, initial, final]), \
                    patch("scripts.phase95_surface_follow.terrain", return_value=None), \
                    patch("scripts.phase95_surface_follow.propose", return_value=proposal), \
                    patch("scripts.phase95_surface_follow.navigate", return_value={"completed": True}) as navigate:
                result = follow(worker, actor_name="MrHints2")
            self.assertTrue(result["actor_proximity_verified"])
            self.assertFalse(result["interaction_verified"])
            self.assertEqual(result["waypoints_completed"], 2)
            self.assertEqual(navigate.call_count, 2)
            self.assertEqual(navigate.call_args.kwargs["waypoint"], actor.position)

    def test_rejects_unreviewed_or_ambiguous_objective(self):
        with self.assertRaises(ValueError):
            follow(None)
        with self.assertRaises(ValueError):
            follow(None, exit_id="x", actor_name="MrHints2")
        with self.assertRaises(ValueError):
            follow(None, actor_name="Squadron")
        with self.assertRaises(ValueError):
            follow(None, actor_name="MrHints2", max_waypoints=0)
        with self.assertRaises(ValueError):
            follow(None, actor_name="MrHints2", approach=(10, 0, 0))
        with self.assertRaises(ValueError):
            follow(None, exit_id="x", approach=(float("nan"), 0, 0))

    def test_declared_exit_ground_approach_tightens_final_waypoint(self):
        with TemporaryDirectory() as directory:
            memory = bytearray(0x100000)
            struct.pack_into(">i", memory, 0xFB114, 47)
            actor = SimpleNamespace(name="LevelExit", address=0x80005000,
                                    position=(95.0, 60.0, 0.0))
            identity = {"source_level": 47, "id": "east48", "destination_level": 48}
            state = SimpleNamespace(front_mode=16,
                                    player=SimpleNamespace(position=(0.0, 0.0, 0.0)),
                                    actors=[actor])
            worker = SimpleNamespace(root=Path(directory),
                                     observe=lambda: ({"sequence": 1, "player": 0x80001000}, memory))
            proposal = {"kind": "jfg-phase95-surface-proposal",
                        "waypoints": [(0, 0, 0), (40, 0, 0), (80, 0, 0)]}
            with patch("scripts.phase95_surface_follow.decode", return_value=state), \
                    patch("scripts.phase95_surface_follow.select_exit", return_value=(actor, identity)), \
                    patch("scripts.phase95_surface_follow.terrain", return_value=None), \
                    patch("scripts.phase95_surface_follow.propose", return_value=proposal) as propose, \
                    patch("scripts.phase95_surface_follow.navigate", return_value={"completed": True}) as navigate:
                result = follow(worker, exit_id="east48", approach=(80, 0, 0))
            self.assertTrue(result["completed"])
            self.assertFalse(result["exit_crossed"])
            self.assertEqual(propose.call_args.kwargs["radius"], 12)
            self.assertEqual(propose.call_args.args[2], (80, 0, 0))
            self.assertEqual(navigate.call_args.kwargs["radius"], 15)
            self.assertEqual(json.loads((worker.root / "surface-proposal.json").read_text())
                             ["approach_point"], [80, 0, 0])

    def test_bounded_prefix_reports_resume_checkpoint_without_claiming_arrival(self):
        with TemporaryDirectory() as directory:
            memory = bytearray(0x100000)
            struct.pack_into(">i", memory, 0xFB114, 47)
            actor = SimpleNamespace(name="MrHints2", address=0x80005000,
                                    position=(100.0, 0.0, 0.0))
            initial = SimpleNamespace(front_mode=16, player=SimpleNamespace(position=(0.0, 0.0, 0.0)),
                                      actors=[actor])
            worker = SimpleNamespace(root=Path(directory),
                                     observe=lambda: ({"sequence": 1, "player": 0x80001000}, memory))
            proposal = {"waypoints": [(0.0, 0.0, 0.0), (40.0, 0.0, 0.0)]}
            with patch("scripts.phase95_surface_follow.decode", return_value=initial), \
                    patch("scripts.phase95_surface_follow.terrain", return_value=None), \
                    patch("scripts.phase95_surface_follow.propose", return_value=proposal), \
                    patch("scripts.phase95_surface_follow.navigate", return_value={"completed": True}):
                result = follow(worker, actor_name="MrHints2", max_waypoints=1)
            self.assertFalse(result["completed"])
            self.assertEqual(result["frontier_checkpoint"], "0001c1")
            self.assertNotIn("actor_proximity_verified", result)

    def test_resume_preserves_original_waypoint_indices(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "prior-proposal.json"
            actor = SimpleNamespace(name="MrHints2", address=0x80005000,
                                    position=(100.0, 0.0, 0.0))
            source.write_text(json.dumps({
                "kind": "jfg-phase95-surface-proposal",
                "target_identity": {"source_level": 47, "actor_name": "MrHints2",
                                    "actor": actor.address, "position": actor.position},
                "waypoints": [[0, 0, 0], [40, 0, 0], [80, 0, 0], [100, 0, 0]]}))
            memory = bytearray(0x100000)
            struct.pack_into(">i", memory, 0xFB114, 47)
            state = SimpleNamespace(front_mode=16, player=SimpleNamespace(position=(40.0, 0.0, 0.0)),
                                    actors=[actor])
            worker = SimpleNamespace(root=root / "next",
                                     observe=lambda: ({"sequence": 1, "player": 0x80001000}, memory))
            worker.root.mkdir()
            with patch("scripts.phase95_surface_follow.decode", return_value=state), \
                    patch("scripts.phase95_surface_follow.navigate", return_value={"completed": True}) as navigate:
                result = follow(worker, actor_name="MrHints2", max_waypoints=1,
                                resume_proposal=source, resume_after=1)
            self.assertEqual(result["waypoints_completed"], 2)
            self.assertEqual(result["frontier_checkpoint"], "0002c1")
            self.assertEqual(navigate.call_args.kwargs["waypoint"], [80, 0, 0])
            self.assertIsNotNone(result["source_route"]["sha256"])

    def test_preserved_proposal_can_start_at_verified_origin(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.json"
            actor = SimpleNamespace(name="Exit", address=0x80005000,
                                    position=(95.0, 60.0, 0.0))
            identity = {"source_level": 47, "id": "east48", "destination_level": 48}
            source.write_text(json.dumps({
                "kind": "jfg-phase95-surface-proposal", "target_identity": identity,
                "waypoints": [[0, 0, 0], [40, 0, 0], [80, 0, 0]]}))
            memory = bytearray(0x100000)
            struct.pack_into(">i", memory, 0xFB114, 47)
            state = SimpleNamespace(front_mode=16,
                                    player=SimpleNamespace(position=(0, 0, 0)),
                                    actors=[actor])
            worker = SimpleNamespace(root=root / "worker",
                                     observe=lambda: ({"sequence": 1, "player": 0x80001000}, memory))
            worker.root.mkdir()
            with patch("scripts.phase95_surface_follow.decode", return_value=state), \
                    patch("scripts.phase95_surface_follow.select_exit", return_value=(actor, identity)), \
                    patch("scripts.phase95_surface_follow.navigate", return_value={"completed": True}):
                result = follow(worker, exit_id="east48", max_waypoints=1,
                                resume_proposal=source, resume_after=0)
            self.assertFalse(result["completed"])
            self.assertEqual(result["waypoints_completed"], 1)
            self.assertEqual(result["source_route"]["resume_after"], 0)

    def test_wrong_vertical_layer_cannot_complete_surface_waypoint(self):
        with TemporaryDirectory() as directory:
            memory = bytearray(0x100000)
            struct.pack_into(">i", memory, 0xFB114, 47)
            actor = SimpleNamespace(name="MrHints2", address=0x80005000,
                                    position=(100.0, 0.0, 0.0))
            state = SimpleNamespace(front_mode=16, player=SimpleNamespace(position=(0.0, 0.0, 0.0)),
                                    actors=[actor])
            worker = SimpleNamespace(root=Path(directory),
                                     observe=lambda: ({"sequence": 1, "player": 0x80001000}, memory))
            proposal = {"waypoints": [(0.0, 0.0, 0.0), (40.0, 20.0, 0.0)]}
            with patch("scripts.phase95_surface_follow.decode", return_value=state), \
                    patch("scripts.phase95_surface_follow.terrain", return_value=None), \
                    patch("scripts.phase95_surface_follow.propose", return_value=proposal), \
                    patch("scripts.phase95_surface_follow.navigate", return_value={"completed": True}):
                with self.assertRaisesRegex(ObservationError, "wrong surface layer"):
                    follow(worker, actor_name="MrHints2", max_waypoints=1)
            mismatch = json.loads((worker.root / "surface-mismatch.json").read_text())
            self.assertEqual(mismatch["vertical_error"], 20.0)

    def test_final_checkpoint_pursues_live_actor_not_stale_route_coordinate(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "prior-proposal.json"
            actor = SimpleNamespace(name="MrHints2", address=0x80005000,
                                    position=(140.0, 0.0, 0.0))
            source.write_text(json.dumps({
                "kind": "jfg-phase95-surface-proposal",
                "target_identity": {"source_level": 47, "actor_name": "MrHints2",
                                    "actor": actor.address, "position": (100.0, 0.0, 0.0)},
                "waypoints": [[0, 0, 0], [40, 0, 0], [100, 0, 0]]}))
            memory = bytearray(0x100000)
            struct.pack_into(">i", memory, 0xFB114, 47)
            before = SimpleNamespace(front_mode=16,
                                     player=SimpleNamespace(position=(100.0, 0.0, 0.0)),
                                     actors=[actor])
            after = SimpleNamespace(front_mode=16,
                                    player=SimpleNamespace(position=(140.0, 0.0, 0.0)),
                                    actors=[actor])
            worker = SimpleNamespace(root=root / "next",
                                     observe=lambda: ({"sequence": 1, "player": 0x80001000}, memory))
            worker.root.mkdir()
            with patch("scripts.phase95_surface_follow.decode", side_effect=[before, before, after]), \
                    patch("scripts.phase95_surface_follow.navigate",
                          return_value={"completed": True}) as navigate:
                result = follow(worker, actor_name="MrHints2", max_waypoints=1,
                                resume_proposal=source, resume_after=2)
            self.assertTrue(result["completed"])
            self.assertTrue(result["actor_proximity_verified"])
            self.assertEqual(navigate.call_count, 1)
            self.assertEqual(navigate.call_args.args[1], "MrHints2")
            pursuits = [json.loads(line) for line in
                        (worker.root / "surface-actor-pursuit.jsonl").read_text().splitlines()]
            self.assertEqual([entry["distance"] for entry in pursuits], [40.0, 0.0])

    def test_selected_npc_dialogue_can_resume_stalled_waypoint(self):
        with TemporaryDirectory() as directory:
            memory = bytearray(0x100000)
            struct.pack_into(">i", memory, 0xFB114, 47)
            actor = SimpleNamespace(name="MrHints2", address=0x80005000,
                                    position=(100.0, 0.0, 0.0))
            initial = SimpleNamespace(front_mode=16,
                                      player=SimpleNamespace(position=(0.0, 0.0, 0.0)),
                                      actors=[actor])
            final = SimpleNamespace(front_mode=16,
                                    player=SimpleNamespace(position=(100.0, 0.0, 0.0)),
                                    actors=[actor])
            worker = SimpleNamespace(root=Path(directory),
                                     observe=lambda: ({"sequence": 1, "player": 0x80001000}, memory))
            proposal = {"waypoints": [(0.0, 0.0, 0.0), (100.0, 0.0, 0.0)]}
            with patch("scripts.phase95_surface_follow.decode",
                       side_effect=[initial, final, final]), \
                    patch("scripts.phase95_surface_follow.terrain", return_value=None), \
                    patch("scripts.phase95_surface_follow.propose", return_value=proposal), \
                    patch("scripts.phase95_dialogue.probe",
                          return_value={"active_then_idle": True}) as dialogue, \
                    patch("scripts.phase95_surface_follow.navigate",
                          side_effect=[ObservationError("navigation stalled; global routing needed"),
                                       {"completed": True}]) as navigate:
                result = follow(worker, actor_name="MrHints2")
            self.assertTrue(result["completed"])
            self.assertTrue(result["interaction_verified"])
            self.assertEqual(navigate.call_count, 2)
            self.assertEqual(dialogue.call_count, 1)
            self.assertEqual(result["dialogue_evidence"][0]["checkpoint"], "0101d1")
            completed = json.loads((worker.root / "surface-completed.jsonl").read_text())
            self.assertEqual(completed["checkpoint_slot"], "0201c1")


if __name__ == "__main__":
    unittest.main()
