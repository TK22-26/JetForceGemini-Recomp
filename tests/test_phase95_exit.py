import struct
import json
import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.phase95_exit import (Arrival, PAUSE_MODE, REGION_PROMPT, REQUESTED_LEVEL,
                                  cross, exit_objective, load_search_source)
from scripts.phase95_observation import ObservationError, FRONT_MODE


class ExitTests(unittest.TestCase):
    def test_arrival_requires_stable_expected_gameplay(self):
        arrival = Arrival(93)
        for mode, level, player in [(0, 93, None), (16, 92, "playerBoy"),
                                    (16, 93, None), (16, 93, "exit")]:
            self.assertFalse(arrival.accept(mode, level, player))
        self.assertFalse(arrival.accept(16, 93, "playerBoy"))
        self.assertFalse(arrival.accept(16, 93, "playerBoy"))
        self.assertTrue(arrival.accept(16, 93, "playerBoy"))

    def test_unavailable_sample_resets_arrival(self):
        arrival = Arrival(93)
        arrival.accept(16, 93, "playerBoy")
        arrival.accept(16, 93, None)
        self.assertFalse(arrival.accept(16, 93, "playerBoy"))
        self.assertFalse(arrival.accept(16, 93, "playerBoy"))

    def objective(self, low=93, high=255, gate=255, pointer=0x80002000):
        memory = bytearray(0x400000)
        struct.pack_into(">I", memory, 0x103C, pointer)
        struct.pack_into(">i", memory, 0xFB114, 92)
        memory[0x200A:0x200C] = bytes([low, high])
        memory[0x2014] = gate
        state = SimpleNamespace(front_mode=16, player=SimpleNamespace(position=(0, 0, 0)),
                                actors=[SimpleNamespace(name="exit", address=0x80001000,
                                                        position=(0, 0, 50))])
        with patch("scripts.phase95_exit.decode", return_value=state):
            return exit_objective(memory, {"sequence": 1, "player": 0x80003000})

    def test_destination_byte_order_and_sentinel(self):
        self.assertEqual(self.objective()["destination_level"], 93)
        self.assertEqual(self.objective(2, 1)["destination_level"], 258)

    def test_reject_world_gate_and_same_level(self):
        for arguments in ({"gate": 0}, {"low": 92}, {"pointer": 0}):
            with self.assertRaises(ObservationError):
                self.objective(**arguments)

    def test_inflight_exit_requires_sealed_search_and_absent_actor(self):
        memory = bytearray(0x400000)
        struct.pack_into(">i", memory, 0xFB114, 21)
        identity = {"id": "a" * 64, "source_level": 21,
                    "destination_level": 47, "world_gate": -1,
                    "position": [23, 74, 1115], "actor": 123}
        state = SimpleNamespace(front_mode=16,
                                player=SimpleNamespace(position=(14, -2, 1121)), actors=[])
        with patch("scripts.phase95_exit.decode", return_value=state):
            with self.assertRaises(ObservationError):
                exit_objective(memory, {"sequence": 1, "player": 1}, identity["id"])
            objective = exit_objective(memory, {"sequence": 1, "player": 1},
                                       identity["id"], identity)
        self.assertFalse(objective["exit_actor_present"])
        self.assertEqual(objective["destination_level"], 47)

    def test_search_source_must_seal_checkpoint_rdram(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkpoint = root / "checkpoint-c1.json"
            result = root / "search-result.json"
            checkpoint.write_text(json.dumps({"kind": "jfg-phase95-checkpoint",
                                              "rdram_sha256": "b" * 64}))
            result.write_text(json.dumps({"kind": "jfg-phase95-checkpoint-search",
                                          "completed": True, "replay_equal": True,
                                          "final_rdram_sha256": "b" * 64,
                                          "exit_identity": {"id": "a" * 64}}))
            self.assertEqual(load_search_source(result, checkpoint, "a" * 64)["id"],
                             "a" * 64)
            checkpoint.write_text(json.dumps({"kind": "jfg-phase95-checkpoint",
                                              "rdram_sha256": "c" * 64}))
            with self.assertRaisesRegex(ValueError, "does not seal"):
                load_search_source(result, checkpoint, "a" * 64)

    def test_cross_acknowledges_only_declared_region_change_prompt(self):
        class Worker:
            def __init__(self, root, requested=47):
                self.root = root
                self.requested = requested
                self.actions = []
                self.level = 21

            def observe(self):
                memory = bytearray(0x400000)
                memory[FRONT_MODE] = 16
                struct.pack_into(">i", memory, 0xFB114, self.level)
                struct.pack_into(">h", memory, REQUESTED_LEVEL, self.requested)
                if self.level == 21:
                    memory[REGION_PROMPT] = 1
                    memory[PAUSE_MODE] = 1
                return {"sequence": len(self.actions), "player": 1}, bytes(memory)

            def act(self, action):
                self.actions.append(action)
                if action.buttons == 0x8000:
                    self.level = 47

            def checkpoint(self, *_):
                pass

        with patch("scripts.phase95_exit.exit_objective", return_value={
                "source_level": 21, "destination_level": 47}), patch(
                "scripts.phase95_exit.decode", return_value=SimpleNamespace(
                    actors=[SimpleNamespace(address=1, name="playerBoy")])):
            with tempfile.TemporaryDirectory() as directory:
                worker = Worker(Path(directory))
                result = cross(worker, max_steps=5)
                self.assertTrue(result["completed"])
                self.assertEqual(result["region_prompt_presses"], 1)
                self.assertEqual([(a.frames, a.buttons) for a in worker.actions],
                                 [(60, 0), (12, 0x8000), (12, 0), (120, 0)])
            with tempfile.TemporaryDirectory() as directory:
                worker = Worker(Path(directory), requested=99)
                with self.assertRaisesRegex(ObservationError, "unrecognized"):
                    cross(worker, max_steps=5)
                self.assertEqual(len(worker.actions), 1)

    def test_cross_requires_arrival_and_seals_only_success(self):
        class Worker:
            def __init__(self, root, level):
                self.root, self.level = root, level
                self.actions, self.checkpoints = [], []

            def observe(self):
                memory = bytearray(0x400000)
                memory[FRONT_MODE] = 16
                struct.pack_into(">i", memory, 0xFB114, self.level)
                return {"sequence": len(self.actions), "player": 1}, bytes(memory)

            def act(self, action):
                self.actions.append(action)

            def checkpoint(self, operation, slot):
                self.checkpoints.append((operation, slot))

        for level in (47, 92):
            with tempfile.TemporaryDirectory() as directory, patch(
                    "scripts.phase95_exit.exit_objective", return_value={"destination_level": 47}), patch(
                    "scripts.phase95_exit.decode", return_value=SimpleNamespace(
                        actors=[SimpleNamespace(address=1, name="playerBoy")])):
                worker = Worker(Path(directory), level)
                if level == 47:
                    self.assertTrue(cross(worker, max_steps=3)["completed"])
                    self.assertEqual(worker.checkpoints, [("save", "e1")])
                else:
                    with self.assertRaisesRegex(ObservationError, "within budget"):
                        cross(worker, max_steps=3)
                    self.assertEqual(worker.checkpoints, [])
                    self.assertFalse((worker.root / "exit-result.json").exists())
                    self.assertEqual(json.loads((worker.root / "exit-failure.json").read_text())[
                        "classification"], "arrival_not_observed")
                self.assertEqual(len(worker.actions), 3)

    def test_declared_two_stage_exit_requires_intermediate_then_playable_arrival(self):
        class Worker:
            def __init__(self, root, levels):
                self.root, self.levels = root, levels
                self.actions, self.checkpoints = [], []

            def observe(self):
                memory = bytearray(0x400000)
                memory[FRONT_MODE] = 16
                struct.pack_into(">i", memory, 0xFB114,
                                 self.levels[min(len(self.actions), len(self.levels) - 1)])
                return {"sequence": len(self.actions), "player": 1}, bytes(memory)

            def act(self, action):
                self.actions.append(action)

            def checkpoint(self, operation, slot):
                self.checkpoints.append((operation, slot))

        with patch("scripts.phase95_exit.exit_objective", return_value={
                "source_level": 47, "destination_level": 199}), patch(
                "scripts.phase95_exit.decode", return_value=SimpleNamespace(
                    actors=[SimpleNamespace(address=1, name="playerBoy")])):
            with tempfile.TemporaryDirectory() as directory:
                worker = Worker(Path(directory), [47, 199, 21, 21, 21])
                result = cross(worker, max_steps=4, arrival_level=21)
                self.assertTrue(result["completed"])
                self.assertEqual(result["required_intermediate_level"], 199)
                self.assertTrue(result["final_observation"]["intermediate_seen"])
                self.assertEqual(worker.checkpoints, [("save", "e1")])
            with tempfile.TemporaryDirectory() as directory:
                worker = Worker(Path(directory), [47, 21, 21, 21, 21])
                with self.assertRaisesRegex(ObservationError, "within budget"):
                    cross(worker, max_steps=4, arrival_level=21)
                self.assertEqual(worker.checkpoints, [])


if __name__ == "__main__":
    unittest.main()
