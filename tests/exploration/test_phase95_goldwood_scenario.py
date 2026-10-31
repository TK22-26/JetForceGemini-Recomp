from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.phase95_goldwood_scenario import Stage, run
from scripts.phase95_observation import ObservationError


class FakeWorker:
    def __init__(self, root):
        self.root, self.level = root, 47
        self.saved = []

    def observe(self):
        memory = bytearray(0x100000)
        struct.pack_into(">i", memory, 0xFB114, self.level)
        return {"sequence": 1, "frame": 100, "polls": 50,
                "player": 0x80001000}, bytes(memory)

    def checkpoint(self, operation, slot):
        self.saved.append((operation, slot))


class ScenarioTests(unittest.TestCase):
    def test_stage_namespaces_checkpoint_slots(self):
        with TemporaryDirectory() as directory:
            worker = FakeWorker(Path(directory))
            stage = Stage(worker, 4, "test")
            stage.checkpoint("save", "a0")
            self.assertEqual(worker.saved, [("save", "4a0")])
            self.assertTrue(stage.root.is_dir())

    def test_one_command_sequence_records_all_predicates(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            route = root / "route.json"
            route.write_text("{}")
            worker = FakeWorker(root)
            group = [{"galaxian_addresses": list(range(3 - index)),
                      "door_actor": 10, "door_y": 78 if index == 3 else 0,
                      "pistol_kills": index} for index in range(4)]

            def surface(_stage, **kwargs):
                if "actor_name" in kwargs:
                    return {"completed": True, "actor_proximity_verified": True,
                            "interaction_verified": True}
                return {"completed": True, "exit_crossed": False}

            def crossing(_stage, **kwargs):
                worker.level = 21
                return {"completed": True, "required_intermediate_level": 199,
                        "final_observation": {"player_name": "playerBoy"}}

            with patch("scripts.phase95_goldwood_scenario.surface_follow",
                       side_effect=surface), patch(
                    "scripts.phase95_goldwood_scenario.group_state", side_effect=group), patch(
                    "scripts.phase95_goldwood_scenario.combat_probe", return_value={
                        "completed": True, "effect": {"encounter_kill_verified": True}}), patch(
                    "scripts.phase95_goldwood_scenario.cross", side_effect=crossing), patch(
                    "scripts.phase95_goldwood_scenario.pickup_follow",
                    return_value={"completed": True}):
                result = run(worker, route)
            self.assertTrue(result["completed"])
            self.assertEqual(result["stages_completed"], 7)
            self.assertEqual(result["final_level"], 21)
            self.assertEqual(len((root / "scenario-stages.jsonl").read_text().splitlines()), 7)
            self.assertTrue((root / "scenario-result.json").exists())

    def test_failed_combat_preserves_incomplete_scenario_artifact(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            route = root / "route.json"
            route.write_text("{}")
            worker = FakeWorker(root)
            with patch("scripts.phase95_goldwood_scenario.surface_follow", return_value={
                    "completed": True, "actor_proximity_verified": True,
                    "interaction_verified": True}), patch(
                    "scripts.phase95_goldwood_scenario.group_state", return_value={
                        "galaxian_addresses": [1, 2, 3], "door_actor": 10,
                        "door_y": 0, "pistol_kills": 0}), patch(
                    "scripts.phase95_goldwood_scenario.combat_probe", return_value={
                        "completed": False, "effect": {"encounter_kill_verified": False}}):
                with self.assertRaises(ObservationError):
                    run(worker, route)
            self.assertTrue((root / "scenario-failure.json").exists())
            self.assertFalse((root / "scenario-result.json").exists())


if __name__ == "__main__":
    unittest.main()
