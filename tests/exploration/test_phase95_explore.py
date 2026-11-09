import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.phase95_explore import cell, search, search_priority
from scripts.phase95_observation import ObservationError


class MazeWorker:
    def __init__(self, root, stuck=False):
        self.root, self.stuck = root, stuck
        self.position = (0.0, 0.0, 0.0)
        self.sequence = 0
        self.states = {}

    def observe(self):
        memory = bytearray(0x400000)
        struct.pack_into(">fff", memory, 0, *self.position)
        return {"sequence": self.sequence, "player": 1}, bytes(memory)

    def checkpoint(self, operation, slot):
        if operation == "save":
            self.states[slot] = self.position
        else:
            self.position = self.states[slot]
        self.sequence += 1

    def act(self, action):
        x, y, z = self.position
        next_x, next_z = x + action.x, z + action.y
        crosses_wall = min(x, next_x) <= 60 <= max(x, next_x) and min(z, next_z) < 120
        if not self.stuck and not crosses_wall:
            self.position = (next_x, y, next_z)
        self.sequence += 1


def decoded(memory, **_):
    return SimpleNamespace(front_mode=16, actors=[], player=SimpleNamespace(
        position=struct.unpack_from(">fff", memory, 0), yaw=0))


class SearchTests(unittest.TestCase):
    def test_detour_priority_can_choose_outward_progress(self):
        self.assertGreater(search_priority(130, 3, 200, "distance"),
                           search_priority(120, 2, 0, "distance"))
        self.assertLess(search_priority(130, 3, 200, "detour"),
                        search_priority(120, 2, 0, "detour"))
        self.assertLess(search_priority(5000, 1, 0, "coverage"),
                        search_priority(1, 2, 1000, "coverage"))

    def run_search(self, worker, **kwargs):
        target = kwargs.pop("target", (120, 0, 0))
        with patch("scripts.phase95_explore.decode", side_effect=decoded), patch(
                "scripts.phase95_explore.inventory", return_value={}), patch(
                "scripts.phase95_explore.select_exit", return_value=(
                    SimpleNamespace(position=target), {"id": "test"})):
            return search(worker, "test", radius=kwargs.pop("radius", 1), **kwargs)

    def test_detour_can_temporarily_increase_distance(self):
        with tempfile.TemporaryDirectory() as directory:
            worker = MazeWorker(Path(directory))
            result = self.run_search(worker)
            self.assertTrue(result["replay_equal"])
            route = [json.loads(line) for line in (worker.root / "search-route.jsonl").read_text().splitlines()]
            self.assertGreater(route[0]["distance"], 120)
            self.assertEqual(worker.position, (120, 0, 0))
            self.assertIn("c1", worker.states)

    def test_coverage_mode_expands_first_branch_before_deeper_goalward_nodes(self):
        with tempfile.TemporaryDirectory() as directory:
            worker = MazeWorker(Path(directory))
            with patch("builtins.print") as printed:
                with self.assertRaisesRegex(ObservationError, "incomplete"):
                    self.run_search(worker, target=(600, 0, 0), mode="coverage",
                                    max_nodes=32, max_expansions=2)
            expansions = [json.loads(call.args[0]) for call in printed.call_args_list]
            self.assertEqual([item["node"] for item in expansions], [0, 1])

    def test_detour_mode_keeps_exact_selected_route(self):
        with tempfile.TemporaryDirectory() as directory:
            worker = MazeWorker(Path(directory))
            result = self.run_search(worker, mode="detour")
            self.assertTrue(result["replay_equal"])
            self.assertEqual(result["search_mode"], "detour")
            self.assertEqual(worker.position, (120, 0, 0))

    def test_exhaustion_is_not_unreachable_or_success(self):
        with tempfile.TemporaryDirectory() as directory:
            worker = MazeWorker(Path(directory), stuck=True)
            with self.assertRaisesRegex(ObservationError, "incomplete"):
                self.run_search(worker, max_nodes=2, max_expansions=1)
            self.assertFalse(json.loads((worker.root / "search-failure.json").read_text())["unreachable"])
            self.assertNotIn("c1", worker.states)

    def test_restore_mismatch_rejected(self):
        class Broken(MazeWorker):
            def checkpoint(self, operation, slot):
                super().checkpoint(operation, slot)
                if operation == "load":
                    self.position = (999, 0, 0)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ObservationError, "restore mismatch"):
                self.run_search(Broken(Path(directory)))

    def test_save_must_not_change_guest_state(self):
        class Broken(MazeWorker):
            def checkpoint(self, operation, slot):
                super().checkpoint(operation, slot)
                if operation == "save":
                    self.position = (1, 0, 0)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ObservationError, "changed guest state"):
                self.run_search(Broken(Path(directory)))

    def test_success_requires_replaying_the_full_selected_route(self):
        class Broken(MazeWorker):
            root_loads = 0
            replaying = False

            def checkpoint(self, operation, slot):
                super().checkpoint(operation, slot)
                if operation == "load" and slot == "a0000":
                    self.root_loads += 1
                    self.replaying = self.root_loads > 8

            def act(self, action):
                super().act(action)
                if self.replaying:
                    x, y, z = self.position
                    self.position = (x + 1, y, z)

        with tempfile.TemporaryDirectory() as directory:
            worker = Broken(Path(directory))
            with self.assertRaisesRegex(ObservationError, "failed exact replay"):
                self.run_search(worker)
            self.assertFalse((worker.root / "search-result.json").exists())
            self.assertNotIn("c1", worker.states)

    def test_cell_rejects_nonfinite_position(self):
        with self.assertRaises(ObservationError):
            cell((float("nan"), 0, 0), 0)

    def test_horizontal_exit_proximity_has_explicit_vertical_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            worker = MazeWorker(Path(directory))
            result = self.run_search(worker, target=(120, 76, 0),
                                     proximity="horizontal", max_vertical_gap=100)
            self.assertTrue(result["completed"])
            self.assertEqual(result["proximity"], "horizontal")
            self.assertEqual(worker.position, (120, 0, 0))
        with tempfile.TemporaryDirectory() as directory:
            worker = MazeWorker(Path(directory))
            with self.assertRaisesRegex(ObservationError, "incomplete"):
                self.run_search(worker, target=(120, 101, 0), proximity="horizontal",
                                max_vertical_gap=100, max_expansions=10)

    def test_near_exit_uses_finer_ordinary_input_moves(self):
        class FrameAwareWorker(MazeWorker):
            def act(self, action):
                x, y, z = self.position
                scale = action.frames / 60
                self.position = (x + action.x * scale, y, z + action.y * scale)
                self.sequence += 1

        with tempfile.TemporaryDirectory() as directory:
            worker = FrameAwareWorker(Path(directory))
            result = self.run_search(worker, target=(30, 0, 0),
                                     max_nodes=16, max_expansions=4)
            self.assertTrue(result["completed"])
            route = [json.loads(line) for line in
                     (worker.root / "search-route.jsonl").read_text().splitlines()]
            self.assertEqual(route[0]["action"]["frames"], 30)
            self.assertEqual(worker.position, (30, 0, 0))

    def test_jump_retry_crosses_obstacle_and_replays_every_action(self):
        class JumpWallWorker(MazeWorker):
            def act(self, action):
                x, y, z = self.position
                if action.buttons == 8 and action.x > 0:
                    self.position = (120.0, y, z)
                self.sequence += 1

        with tempfile.TemporaryDirectory() as directory:
            worker = JumpWallWorker(Path(directory))
            with patch("scripts.phase95_explore.jump_mask", return_value=8):
                result = self.run_search(worker, target=(120, 0, 0),
                                         max_nodes=32, max_expansions=1,
                                         jump=True)
            self.assertTrue(result["replay_equal"])
            self.assertTrue(result["jump_candidates"])
            route = [json.loads(line) for line in
                     (worker.root / "search-route.jsonl").read_text().splitlines()]
            self.assertEqual(len(route[0]["actions"]), 3)
            self.assertEqual(route[0]["actions"][1]["buttons"], 8)
            self.assertEqual(worker.position, (120, 0, 0))

    def test_jump_retry_tests_stalled_wall_far_from_exit(self):
        class DistantWallWorker(MazeWorker):
            def act(self, action):
                if action.buttons == 8 and action.x > 0:
                    self.position = (120.0, 0.0, 0.0)
                self.sequence += 1

        with tempfile.TemporaryDirectory() as directory:
            worker = DistantWallWorker(Path(directory))
            with patch("scripts.phase95_explore.jump_mask", return_value=8):
                with self.assertRaisesRegex(ObservationError, "incomplete"):
                    self.run_search(worker, target=(600, 0, 0), jump=True,
                                    max_nodes=32, max_expansions=1)
            trials = [json.loads(line) for line in
                      (worker.root / "search-trials.jsonl").read_text().splitlines()]
            self.assertTrue(any(item.get("stalled_jump_candidate") for item in trials))
            self.assertTrue(any(len(item["actions"]) == 3 for item in trials))
            self.assertTrue(any(item["position"][0] == 120.0 for item in trials))

    def test_jump_retry_keeps_small_new_spatial_frontier(self):
        class ShortJumpWorker(MazeWorker):
            def act(self, action):
                if action.buttons == 8 and action.x > 0:
                    self.position = (15.0, 0.0, 0.0)
                self.sequence += 1

        with tempfile.TemporaryDirectory() as directory:
            worker = ShortJumpWorker(Path(directory))
            with patch("scripts.phase95_explore.jump_mask", return_value=8):
                with self.assertRaisesRegex(ObservationError, "incomplete"):
                    self.run_search(worker, target=(600, 0, 0), jump=True,
                                    max_nodes=32, max_expansions=1)
            nodes = [json.loads(line) for line in
                     (worker.root / "search-nodes.jsonl").read_text().splitlines()]
            self.assertEqual(len(nodes), 2)
            self.assertEqual(nodes[1]["position"], [15.0, 0.0, 0.0])
            trials = [json.loads(line) for line in
                      (worker.root / "search-trials.jsonl").read_text().splitlines()]
            self.assertTrue(any(item.get("fine_jump_novel") and
                                not item["novel_cell"] for item in trials))

    def test_incidental_level_transition_is_logged_and_search_continues(self):
        class CrossingWorker(MazeWorker):
            def __init__(self, root):
                super().__init__(root)
                self.level = 0

            def observe(self):
                metadata, raw = super().observe()
                memory = bytearray(raw)
                struct.pack_into(">i", memory, 0xFB114, self.level)
                return metadata, bytes(memory)

            def checkpoint(self, operation, slot):
                super().checkpoint(operation, slot)
                if operation == "load":
                    self.level = 0

            def act(self, action):
                if action.y > 0:
                    self.level = 48
                else:
                    x, y, z = self.position
                    self.position = (x + action.x, y, z + action.y)
                self.sequence += 1

        with tempfile.TemporaryDirectory() as directory:
            worker = CrossingWorker(Path(directory))
            result = self.run_search(worker, target=(120, 0, 0),
                                     max_nodes=32, max_expansions=10)
            self.assertTrue(result["completed"])
            trials = [json.loads(line) for line in
                      (worker.root / "search-trials.jsonl").read_text().splitlines()]
            self.assertTrue(any(item.get("outcome") == "incidental-level-transition"
                                and item["observed_level"] == 48 for item in trials))

    def test_all_root_moves_auto_transition_requires_another_checkpoint(self):
        class AutoCrossWorker(MazeWorker):
            def __init__(self, root):
                super().__init__(root)
                self.level = 0

            def observe(self):
                metadata, raw = super().observe()
                memory = bytearray(raw)
                struct.pack_into(">i", memory, 0xFB114, self.level)
                return metadata, bytes(memory)

            def checkpoint(self, operation, slot):
                super().checkpoint(operation, slot)
                if operation == "load":
                    self.level = 0

            def act(self, action):
                self.level = 48
                self.sequence += 1

        with tempfile.TemporaryDirectory() as directory:
            worker = AutoCrossWorker(Path(directory))
            with self.assertRaisesRegex(ObservationError, "auto-transitions"):
                self.run_search(worker, target=(120, 0, 0),
                                max_nodes=32, max_expansions=10)
            failure = json.loads((worker.root / "search-failure.json").read_text())
            self.assertTrue(failure["source_auto_transition"])
            self.assertEqual(failure["observed_levels"], [48])
            self.assertEqual(failure["trials"], 8)
            self.assertFalse(failure["unreachable"])


if __name__ == "__main__":
    unittest.main()
