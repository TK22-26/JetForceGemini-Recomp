import json
from pathlib import Path
import tempfile
import time
import unittest

from scripts.navigation_map import load_snapshot, write_obj, write_svg


class NavigationMapTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name)
        self.mesh = {"schema": 1, "level": 35, "generation": 2,
                     "vertices": [[0, 0, 0], [100, 0, 0], [0, 0, 100]],
                     "triangles": [{"v": [0, 1, 2], "normal": [0, 1, 0]}]}
        self.live = {"schema": 1, "level": 35, "generation": 2, "mesh_ready": True,
                     "timestamp_ms": int(time.time() * 1000),
                     "player": {"position": [10, 0, 10], "health": 1024},
                     "exits": [{"position": [50, 0, 50], "destination_code": 0xff03}]}

    def save(self):
        (self.path / "mesh.json").write_text(json.dumps(self.mesh))
        (self.path / "live.json").write_text(json.dumps(self.live))

    def test_progression_is_safe_for_planning(self):
        self.live["progression"] = {'schema': 1, 'inventory': {'known': True, 'character': 1, 'red_key': False, 'weapons_mask': 4}, 'nodes': [{'address': 2148712448, 'position': [20, 0, 40], 'kind': 'npc', 'label': 'Magnus: Red key', 'action': 'talk', 'status': 'available', 'requirement': 'Talk to Magnus', 'reward': 'Red key', 'requirement_known': True, 'reward_item': 1, 'reward_weapon': -1, 'required_weapon': -1, 'spoken': 1, 'traversal': 'unknown'}]}
        self.save()
        mesh, live = load_snapshot(self.path)
        write_svg(self.path / "rewards.svg", mesh, live)
        self.assertIn("Magnus: Red key [available]", (self.path / "rewards.svg").read_text())
        node = self.live["progression"]["nodes"][0]
        for key, value in (("position", [0, 1]), ("traversal", "open"), ("required_weapon", 99)):
            previous = node[key]; node[key] = value; self.save()
            with self.assertRaises(ValueError): load_snapshot(self.path)
            node[key] = previous
        self.live["progression"]["inventory"]["known"] = False
        self.save()
        with self.assertRaises(ValueError): load_snapshot(self.path)

    def test_npc_offers_and_nested_requirements(self):
        self.live["progression"] = {"schema": 1, "inventory": {"known": False},
            "npc_catalog": {"known": True, "dialogue_groups": 45, "choice_tables": 19},
            "nodes": [{"address": 2148712448, "position": [20, 0, 40], "kind": "npc", "label": "Trader",
                "action": "talk", "status": "blocked", "requirement": "See offers", "reward": "Crowbar", "requirement_known": True,
                "reward_weapon": -1, "required_weapon": -1, "spoken": 1, "traversal": "unknown", "npc_catalog_known": True,
                "offers": [{"id": "7:0/1:0/2:0", "kind": "item", "reward": "Crowbar", "status": "blocked", "scope": "any_character",
                    "action": 5, "item": 21, "weapon": -1, "flag": -1, "destination": -1, "cost": 0, "consumed_items": [20],
                    "conditions": [{"domain": "prerequisite", "id": 3, "description": "Current character payment", "state": "missing"}]}]}]}
        self.save()
        mesh, live = load_snapshot(self.path)
        write_svg(self.path / "offers.svg", mesh, live)
        self.assertIn("Crowbar [blocked]", (self.path / "offers.svg").read_text())
        node = self.live["progression"]["nodes"][0]
        offer = node["offers"][0]
        for key, value in (("consumed_items", [27]), ("cost", -1), ("conditions", [None]), ("status", "complete")):
            previous = offer[key]; offer[key] = value; self.save()
            with self.assertRaises(ValueError): load_snapshot(self.path)
            offer[key] = previous
        node["offers"].append(offer); self.save()
        with self.assertRaises(ValueError): load_snapshot(self.path)

    def test_export_geometry_and_exit_preview(self):
        self.save()
        mesh, live = load_snapshot(self.path)
        write_obj(self.path / "map.obj", mesh)
        write_svg(self.path / "map.svg", mesh, live)
        self.assertIn("f 1 2 3", (self.path / "map.obj").read_text())
        self.assertIn("Exit 0: 0xff03", (self.path / "map.svg").read_text())

    def test_npcs_items_and_safe_svg_labels(self):
        self.live["npcs"] = [
            {"position": [20, 0, 40], "kind": "npc", "label": 'NPC <Guide> & "test"'},
            {"position": [40, 0, 40], "kind": "tribal", "label": "Tribal"}]
        self.live["markers"] = [
            {"position": [60, 0, 40], "kind": "weapon", "label": "Chest: Shotgun"}]
        self.save()
        mesh, live = load_snapshot(self.path)
        write_svg(self.path / "npcs.svg", mesh, live)
        svg = (self.path / "npcs.svg").read_text()
        self.assertIn("NPC &lt;Guide&gt; &amp;", svg)
        self.assertIn("Chest: Shotgun", svg)
        self.assertIn("#6495ed", svg)
        self.assertIn("#ffffff", svg)

    def test_reject_invalid_npcs(self):
        for entry in [
            {"position": [0, 0], "kind": "npc", "label": "Guide"},
            {"position": [0, 0, 0], "kind": "enemy", "label": "Drone"},
            {"position": [0, 0, 0], "kind": "npc", "label": "x" * 81}]:
            self.live["npcs"] = [entry]
            self.save()
            with self.assertRaises(ValueError):
                load_snapshot(self.path)
        self.live["npcs"] = [None] * 1025
        self.save()
        with self.assertRaises(ValueError):
            load_snapshot(self.path)

    def test_reject_stale_unless_offline_inspection(self):
        self.live["timestamp_ms"] = 1
        self.save()
        with self.assertRaisesRegex(ValueError, "stale"):
            load_snapshot(self.path)
        self.assertEqual(load_snapshot(self.path, allow_stale=True)[1]["level"], 35)

    def test_reject_old_map_during_transition(self):
        self.live["generation"] += 1
        self.save()
        with self.assertRaisesRegex(ValueError, "Room changed"):
            load_snapshot(self.path, allow_stale=True)

    def test_require_active_gameplay(self):
        for key, value in [("player", None), ("mesh_ready", False)]:
            before = self.live[key]
            self.live[key] = value
            self.save()
            with self.assertRaisesRegex(ValueError, "active player"):
                load_snapshot(self.path)
            self.live[key] = before

    def test_reject_invalid_room_identity_and_exit_code(self):
        self.mesh["generation"] = None
        self.save()
        with self.assertRaisesRegex(ValueError, "identity"):
            load_snapshot(self.path)
        self.mesh["generation"] = 2
        self.live["exits"][0]["destination_code"] = -1
        self.save()
        with self.assertRaisesRegex(ValueError, "destination code"):
            load_snapshot(self.path)

    def test_reject_nonfinite_and_out_of_range_geometry(self):
        self.mesh["vertices"][0][0] = float("nan")
        self.save()
        with self.assertRaisesRegex(ValueError, "coordinate"):
            load_snapshot(self.path)
        self.mesh["vertices"][0][0] = 0
        self.mesh["triangles"][0]["v"][2] = 3
        self.save()
        with self.assertRaisesRegex(ValueError, "indices"):
            load_snapshot(self.path)


if __name__ == "__main__":
    unittest.main()
