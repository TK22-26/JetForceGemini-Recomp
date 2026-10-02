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

    def test_export_geometry_and_exit_preview(self):
        self.save()
        mesh, live = load_snapshot(self.path)
        write_obj(self.path / "map.obj", mesh)
        write_svg(self.path / "map.svg", mesh, live)
        self.assertIn("f 1 2 3", (self.path / "map.obj").read_text())
        self.assertIn("Exit 0: 0xff03", (self.path / "map.svg").read_text())

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
