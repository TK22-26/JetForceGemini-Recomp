import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.phase95_observation import ObservationError
from scripts.phase95_pickup_follow import follow


class PickupFollowTests(unittest.TestCase):
    def fixture(self, root, health_gain=256):
        memory = bytearray(0x100000)
        struct.pack_into(">i", memory, 0xFB114, 21)
        pickup = {"actor": 0x80005000, "name": "HealthPowerup",
                  "position": (40.0, 0.0, 0.0), "kind": 0xA9,
                  "mode": 0, "respawn_delay": 0, "eligible": True}
        before = {"character": 1, "health_upgrades": 6,
                  "health_capacity_raw": 8704, "health_raw": 8192,
                  "health_pickups": [pickup]}
        after = {**before, "health_raw": 8192 + health_gain,
                 "health_pickups": []}
        initial = SimpleNamespace(front_mode=16,
                                  player=SimpleNamespace(position=(0.0, 0.0, 0.0)))
        final = SimpleNamespace(front_mode=16,
                                player=SimpleNamespace(position=(40.0, 0.0, 0.0)))
        checkpoints = []
        worker = SimpleNamespace(root=root,
                                 observe=lambda: ({"sequence": 1, "player": 0x80001000}, memory),
                                 checkpoint=lambda operation, slot:
                                 checkpoints.append((operation, slot)))
        proposal = {"kind": "jfg-phase95-surface-proposal",
                    "waypoints": [(0.0, 0.0, 0.0), (40.0, 0.0, 0.0)]}
        return worker, checkpoints, before, after, initial, final, proposal

    def test_collection_requires_exact_health_gain_and_actor_removal(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            worker, checkpoints, before, after, initial, final, proposal = self.fixture(root)
            with patch("scripts.phase95_pickup_follow.decode",
                       side_effect=[initial, final]), \
                    patch("scripts.phase95_pickup_follow.inventory",
                          side_effect=[before, after]), \
                    patch("scripts.phase95_pickup_follow.terrain", return_value=None), \
                    patch("scripts.phase95_pickup_follow.propose", return_value=proposal), \
                    patch("scripts.phase95_pickup_follow.navigate",
                          return_value={"completed": True}):
                result = follow(worker, max_waypoints=1)
            self.assertTrue(result["completed"])
            self.assertEqual(result["checkpoint"], "e1")
            self.assertEqual(checkpoints, [("save", "e1")])
            self.assertTrue(json.loads((root / "pickup-progress.jsonl").read_text())[
                "collection_verified"])

    def test_actor_vanishing_without_one_unit_gain_is_not_collection(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            worker, checkpoints, before, after, initial, final, proposal = self.fixture(
                root, health_gain=0)
            with patch("scripts.phase95_pickup_follow.decode",
                       side_effect=[initial, final]), \
                    patch("scripts.phase95_pickup_follow.inventory",
                          side_effect=[before, after]), \
                    patch("scripts.phase95_pickup_follow.terrain", return_value=None), \
                    patch("scripts.phase95_pickup_follow.propose", return_value=proposal), \
                    patch("scripts.phase95_pickup_follow.navigate",
                          return_value={"completed": True}):
                with self.assertRaisesRegex(ObservationError, "vanished"):
                    follow(worker, max_waypoints=1)
            self.assertEqual(checkpoints, [])


if __name__ == "__main__":
    unittest.main()
