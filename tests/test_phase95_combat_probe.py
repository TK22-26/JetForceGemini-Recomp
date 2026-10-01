import unittest

from scripts.phase95_combat_probe import candidates, effect
from scripts.phase95_observation import ObservationError


class CombatProbeTests(unittest.TestCase):
    def baseline(self):
        return {"level_number": 47, "target_address": 0x801C07F0,
                "galaxian_addresses": [0x801C07F0],
                "target_present": True, "target_candidate_health_raw": 256,
                "pistol_shots": 0, "pistol_hits": 0, "pistol_kills": 0,
                "pistol_ammo": 100}

    def test_candidates_are_bounded_ordinary_inputs(self):
        choices = candidates()
        self.assertEqual(len(choices), 35)
        self.assertEqual(choices[0][0], "neutral")
        for _, actions in choices:
            for action in actions:
                action.validate()

    def test_ammo_or_actor_removal_alone_cannot_prove_hit(self):
        before = self.baseline()
        after = {**before, "pistol_shots": 2, "pistol_ammo": 98,
                 "target_present": False, "target_candidate_health_raw": None,
                 "galaxian_addresses": []}
        self.assertFalse(effect(before, after)["target_hit_verified"])
        after["pistol_hits"] = 1
        self.assertTrue(effect(before, after)["target_hit_verified"])
        self.assertFalse(effect(before, after)["target_kill_verified"])
        after["pistol_kills"] = 1
        self.assertTrue(effect(before, after)["target_kill_verified"])
        self.assertTrue(effect(before, after)["encounter_kill_verified"])

    def test_other_group_member_kill_is_not_lost(self):
        before = {**self.baseline(), "galaxian_addresses": [0x801C07F0, 0x801C0AA0]}
        after = {**before, "galaxian_addresses": [0x801C07F0],
                 "pistol_shots": 1, "pistol_hits": 1, "pistol_kills": 1,
                 "pistol_ammo": 99}
        result = effect(before, after)
        self.assertTrue(result["encounter_kill_verified"])
        self.assertFalse(result["target_kill_verified"])

    def test_hit_counter_without_target_effect_is_insufficient(self):
        before = self.baseline()
        after = {**before, "pistol_shots": 1, "pistol_hits": 1,
                 "pistol_ammo": 99}
        self.assertFalse(effect(before, after)["target_hit_verified"])
        after["target_candidate_health_raw"] = 128
        self.assertTrue(effect(before, after)["target_hit_verified"])

    def test_context_change_and_counter_regression_rejected(self):
        before = self.baseline()
        with self.assertRaises(ObservationError):
            effect(before, {**before, "level_number": 48})
        with self.assertRaises(ObservationError):
            effect(before, {**before, "pistol_hits": -1})


if __name__ == "__main__":
    unittest.main()
