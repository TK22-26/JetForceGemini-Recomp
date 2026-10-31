import unittest
import struct
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from scripts.phase95_navigation import distance, jump_mask, navigate, navigation_candidates
from scripts.phase95_observation import ObservationError


class FakeWorker:
    def __init__(self, root, stuck=False):
        self.root = root
        self.position = (0.0, 0.0, 0.0)
        self.sequence = 0
        self.states = {}
        self.stuck = stuck

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
        if not self.stuck:
            x, y, z = self.position
            self.position = (x + action.x / 2, y, z + action.y / 2)
        self.sequence += 1


def fake_decode(memory, **_):
    return SimpleNamespace(front_mode=16,
        player=SimpleNamespace(position=struct.unpack_from(">fff", memory, 0)),
        actors=[SimpleNamespace(name="longwoodbridge", position=(0, 0, 90))])


class NavigationTests(unittest.TestCase):
    def test_precision_choices_preserve_original_and_add_short_inputs(self):
        candidates = navigation_candidates(precision=True)
        self.assertEqual(candidates[:8], navigation_candidates())
        self.assertEqual(len(candidates), 25)
        self.assertEqual({actions[0].frames for actions in candidates}, {6, 12, 24})
        self.assertEqual(candidates[-1][0].buttons, 0)
        self.assertEqual((candidates[-1][0].x, candidates[-1][0].y), (0, 0))

    def test_short_action_reaches_target_that_long_action_overshoots(self):
        class PreciseWorker(FakeWorker):
            def act(self, action):
                x, y, z = self.position
                self.position = (x + action.x * action.frames / 24, y,
                                 z + action.y * action.frames / 24)
                self.sequence += 1

        def observation(memory, **kwargs):
            state = fake_decode(memory, **kwargs)
            state.actors[0].position = (0, 0, 15)
            return state

        with tempfile.TemporaryDirectory() as directory, patch(
                "scripts.phase95_navigation.decode", side_effect=observation):
            result = navigate(PreciseWorker(Path(directory)), "longwoodbridge",
                              precision=True, max_steps=1, radius=1)
            self.assertTrue(result["completed"])

    def test_jump_candidates_have_release_and_bounded_actions(self):
        self.assertEqual(len(navigation_candidates()), 8)
        candidates = navigation_candidates(True, jump_button=0x8000)
        self.assertEqual(len(candidates), 24)
        for release, jump, travel in candidates[8:]:
            self.assertEqual(release.buttons, 0)
            self.assertEqual(jump.buttons, 0x8000)
            self.assertEqual(travel.buttons, 0)
            for action in (release, jump, travel):
                action.validate()
        self.assertTrue(all((actions[1].x, actions[1].y) ==
                            (actions[2].x, actions[2].y) for actions in candidates[8:16]))
        self.assertTrue(all((actions[2].x, actions[2].y) == (0, 0)
                            for actions in candidates[16:]))

    def test_long_only_jump_policy_preserves_older_reviewed_ledge_route(self):
        all_candidates = navigation_candidates(True, True, 0x0008)
        long_only = navigation_candidates(True, True, 0x0008, short_jump=False)
        self.assertEqual(long_only, all_candidates[:-8])
        self.assertEqual(len(long_only), 33)

    def test_jump_button_follows_pinned_active_control_mode(self):
        memory = bytearray(0x400000)
        struct.pack_into(">9I", memory, 0xA18B4, 0x2000, 0x8, 0x4, 0x8000,
                         0x4000, 0x2, 0x1, 0x8000, 0x4000)
        struct.pack_into(">9I", memory, 0xA18D8, 0x2000, 0x4000, 0x8000,
                         0x8, 0x4, 0x2, 0x1, 0x8, 0x4)
        struct.pack_into(">I", memory, 0xA18B0, 0x800A18B4)
        self.assertEqual(jump_mask(memory), 0x8000)
        struct.pack_into(">I", memory, 0xA18B0, 0x800A18D8)
        self.assertEqual(jump_mask(memory), 0x0008)
        self.assertEqual(navigation_candidates(True, jump_button=jump_mask(memory))[8][1].buttons,
                         0x0008)
        memory[0xA18D8] ^= 1
        with self.assertRaises(ObservationError):
            jump_mask(memory)

    def test_moving_actor_uses_live_position_for_completion(self):
        def moving_actor(memory, **_):
            position = struct.unpack_from(">fff", memory, 0)
            return SimpleNamespace(front_mode=16,
                player=SimpleNamespace(position=position),
                actors=[SimpleNamespace(name="MrHints2", address=0x80005000,
                                        position=(0.0, 0.0, 60.0 + position[2] / 2))])

        with tempfile.TemporaryDirectory() as directory, patch(
                "scripts.phase95_navigation.decode", side_effect=moving_actor):
            result = navigate(FakeWorker(Path(directory)), "MrHints2",
                              max_steps=2, radius=30)
            self.assertTrue(result["completed"])
            self.assertEqual(result["tracked_actor"], 0x80005000)
            self.assertEqual(result["distance"], 30.0)
            self.assertIn("live tracked actor", result["completion"])

    def test_jump_sequence_can_cross_synthetic_obstacle(self):
        class JumpWorker(FakeWorker):
            def act(self, action):
                if action.buttons == 0x8000:
                    self.position = (0.0, 0.0, 90.0)
                self.sequence += 1

        with tempfile.TemporaryDirectory() as directory, patch(
                "scripts.phase95_navigation.decode", side_effect=fake_decode):
            worker = JumpWorker(Path(directory))
            result = navigate(worker, "longwoodbridge", max_steps=1, radius=1,
                              jump=True, jump_button=0x8000)
            self.assertTrue(result["completed"])
            import json
            selected = json.loads((worker.root / "navigation-selected.jsonl").read_text())
            self.assertEqual(len(selected["actions"]), 3)
            self.assertEqual(selected["actions"][1]["buttons"], 0x8000)

    def test_intermediate_divergence_cannot_hide_at_matching_endpoint(self):
        class JumpWorker(FakeWorker):
            count = 0

            def act(self, action):
                self.count += 1
                if action.buttons == 0x8000:
                    self.position = (0.0, 0.0, 90.0)
                if self.count == 58:  # selected jump after 8 single + 16 triple trials
                    self.position = (1.0, 0.0, 90.0)
                if self.count == 59:
                    self.position = (0.0, 0.0, 90.0)
                self.sequence += 1

        with tempfile.TemporaryDirectory() as directory, patch(
                "scripts.phase95_navigation.decode", side_effect=fake_decode):
            worker = JumpWorker(Path(directory))
            with self.assertRaisesRegex(ObservationError, "exact continuation"):
                navigate(worker, "longwoodbridge", max_steps=1, radius=1,
                         jump=True, jump_button=0x8000)

    def test_vertical_separation_counts(self):
        self.assertEqual(distance((0, 100, 0), (0, 0, 0)), 100)

    def test_distance(self):
        self.assertEqual(distance((0, 0, 0), (3, 0, 4)), 5)

    def test_bad_state(self):
        with self.assertRaises(ValueError):
            distance((0, float("nan"), 0), (0, 0, 0))

    def test_reaches_on_last_allowed_action(self):
        with tempfile.TemporaryDirectory() as directory, patch(
                "scripts.phase95_navigation.decode", side_effect=fake_decode):
            worker = FakeWorker(Path(directory))
            result = navigate(worker, "longwoodbridge", max_steps=3, radius=1)
            self.assertTrue(result["completed"])
            self.assertEqual(result["steps"], 3)
            self.assertEqual(len((worker.root / "navigation-selected.jsonl").read_text().splitlines()), 3)

    def test_budget_exhaustion_is_not_success(self):
        with tempfile.TemporaryDirectory() as directory, patch(
                "scripts.phase95_navigation.decode", side_effect=fake_decode):
            worker = FakeWorker(Path(directory), stuck=True)
            with self.assertRaisesRegex(ObservationError, "budget exhausted"):
                navigate(worker, "longwoodbridge", max_steps=1, radius=1)
            self.assertFalse((worker.root / "navigation-result.json").exists())

    def test_selected_candidate_must_reproduce(self):
        class DivergentWorker(FakeWorker):
            count = 0

            def act(self, action):
                super().act(action)
                self.count += 1
                if self.count == 9:  # eight trials, then selected continuation
                    x, y, z = self.position
                    self.position = (x + 1, y, z)

        with tempfile.TemporaryDirectory() as directory, patch(
                "scripts.phase95_navigation.decode", side_effect=fake_decode):
            worker = DivergentWorker(Path(directory))
            with self.assertRaisesRegex(ObservationError, "exact continuation"):
                navigate(worker, "longwoodbridge", max_steps=1, radius=1)


if __name__ == "__main__":
    unittest.main()
