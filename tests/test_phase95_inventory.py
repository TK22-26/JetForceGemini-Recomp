import copy
import unittest
import struct
from types import SimpleNamespace
from unittest.mock import patch
from scripts.phase95_inventory import (inventory, eligible, capacity_collection_verified,
                                       health_upgrade_collection_verified,
                                       health_refill_collection_verified, weapon_stats)
from scripts.phase95_observation import ObservationError


class InventoryTests(unittest.TestCase):
    def test_weapon_stats_validate_original_counter_offsets(self):
        memory = bytearray(0x400000)
        for code, load in ((0x47868, 0x944304F4),
                           (0x478A4, 0x8C430474),
                           (0x478E0, 0x8C4304B4)):
            struct.pack_into(">5I", memory, code, 0x0480000C, 0x28810010,
                             0x1020000A, 0x3C0E8010, 0x8DCED7D4)
            struct.pack_into(">I", memory, code + 0x1C, load)
        game = 0x10000
        struct.pack_into(">I", memory, game + 0x474, 8)
        struct.pack_into(">I", memory, game + 0x4B4, 2)
        struct.pack_into(">H", memory, game + 0x4F4, 1)
        with patch("scripts.phase95_inventory.inventory",
                   return_value={"game_pointer": 0x80010000, "character": 1}):
            result = weapon_stats(memory, {"sequence": 1, "player": 0x80001000})
            self.assertEqual((result["shots"][0], result["hits"][0],
                              result["kills"][0]), (8, 2, 1))
            memory[0x478E0 + 0x1C] ^= 1
            with self.assertRaises(ObservationError):
                weapon_stats(memory, {"sequence": 1, "player": 0x80001000})

    def fixture(self):
        state = {"character": 1, "owned_mask": 1, "ammo": [50] * 16,
                 "capacity": [100] * 16, "flags_hex": bytes(144).hex()}
        pickup = {"weapon": 0, "kind": 0xE7, "capacity_increment": 20,
                  "capacity_limit": 999, "collected": False, "flag": 199}
        return state, pickup

    def test_unowned_capacity_pickup_is_ineligible(self):
        state, pickup = self.fixture()
        self.assertTrue(eligible(pickup, state))
        pickup["weapon"] = 6
        self.assertFalse(eligible(pickup, state))

    def test_capacity_limit_and_existing_flag(self):
        state, pickup = self.fixture()
        pickup["capacity_limit"] = 110
        self.assertFalse(eligible(pickup, state))
        pickup["capacity_limit"] = 999
        pickup["collected"] = True
        self.assertFalse(eligible(pickup, state))

    def test_full_ammo_requires_an_actual_deficit(self):
        state, pickup = self.fixture()
        pickup["kind"] = 0xE8
        self.assertTrue(eligible(pickup, state))
        state["ammo"][0] = 100
        self.assertFalse(eligible(pickup, state))

    def test_collection_needs_both_exact_capacity_change_and_new_flag(self):
        before, pickup = self.fixture()
        after = copy.deepcopy(before)
        after["capacity"][0] += 20
        self.assertFalse(capacity_collection_verified(before, after, pickup))
        flags = bytearray(144)
        flags[199 // 8] |= 1 << (199 % 8)
        after["flags_hex"] = flags.hex()
        self.assertTrue(capacity_collection_verified(before, after, pickup))
        after["capacity"][0] -= 1
        self.assertFalse(capacity_collection_verified(before, after, pickup))

    def test_wrong_character_cannot_pass(self):
        before, pickup = self.fixture()
        after = copy.deepcopy(before)
        after["character"] = 2
        self.assertFalse(capacity_collection_verified(before, after, pickup))

    def test_health_upgrade_requires_flag_capacity_and_full_heal(self):
        before = {"character": 1, "health_upgrades": 6, "health_capacity_raw": 8704,
                  "health_raw": 7680, "flags_hex": bytes(144).hex()}
        pickup = {"kind": 0xE9, "eligible": True, "flag": 47}
        after = copy.deepcopy(before)
        after.update(health_upgrades=7, health_capacity_raw=9984, health_raw=9984)
        self.assertFalse(health_upgrade_collection_verified(before, after, pickup))
        flags = bytearray(144)
        flags[47 // 8] |= 1 << (47 % 8)
        after["flags_hex"] = flags.hex()
        self.assertTrue(health_upgrade_collection_verified(before, after, pickup))
        after["health_raw"] -= 256
        self.assertFalse(health_upgrade_collection_verified(before, after, pickup))
        after["health_raw"] += 256
        after["health_capacity_raw"] -= 256
        self.assertFalse(health_upgrade_collection_verified(before, after, pickup))

    def test_health_refill_requires_exact_gain_and_actor_removal(self):
        before = {"character": 1, "health_upgrades": 6, "health_capacity_raw": 8704,
                  "health_raw": 8192}
        pickup = {"actor": 0x80005000, "name": "HealthPowerup", "kind": 0xA9,
                  "mode": 0, "respawn_delay": 0, "eligible": True}
        after = {**before, "health_raw": 8448, "health_pickups": [pickup]}
        self.assertFalse(health_refill_collection_verified(before, after, pickup))
        after["health_pickups"] = []
        self.assertTrue(health_refill_collection_verified(before, after, pickup))
        after["health_raw"] = 8704
        self.assertFalse(health_refill_collection_verified(before, after, pickup))
        after["health_raw"] = 8448
        pickup["respawn_delay"] = 60
        self.assertFalse(health_refill_collection_verified(before, after, pickup))

    def test_gemini_powerup_reads_guard_and_persistent_flag(self):
        memory = bytearray(0x400000)
        struct.pack_into(">9I", memory, 0x47C70, 0x00085100, 0x01485023, 0x000A5080,
                         0x3C098010, 0x8D29D7D4, 0x01485023, 0x000A5040, 0x012A1021, 0x2442015C)
        struct.pack_into(">7I", memory, 0x3B500, 0x00047080, 0x01C47023,
                         0x3C0F800A, 0x25EF1490, 0x000E7100, 0x03E00008, 0x01CF1021)
        struct.pack_into(">I", memory, 0x1068, 0x80002000)
        struct.pack_into(">I", memory, 0x104C, 0x80003000)
        struct.pack_into(">h", memory, 0x3006, 8704)
        struct.pack_into(">I", memory, 0xFD7D4, 0x80010000)
        memory[0x2001] = 1
        character = 0x10000 + 0x15C + 0x76
        struct.pack_into(">h", memory, character + 2, 6)
        struct.pack_into(">I", memory, 0xFEAA0, 0x80004000)
        struct.pack_into(">I", memory, 0x4000 + 104 * 32, 0x80005000)
        struct.pack_into(">I", memory, 0x5000 + 0x1F0, 0x27BDFF80)
        struct.pack_into(">I", memory, 0x5000 + 0x2B8, 0x15610015)
        struct.pack_into(">I", memory, 0x5000 + 0x5FC, 0xA44D0006)
        struct.pack_into(">I", memory, 0xAB24C + 59 * 4, 0x8000FFD0)
        struct.pack_into(">I", memory, 0xFFD0, 0x0C00147C)
        struct.pack_into(">h", memory, 0x6048, 61)
        struct.pack_into(">I", memory, 0x6068, 0x80007000)
        struct.pack_into(">h", memory, 0x7012, 0xE9)
        actor = SimpleNamespace(address=0x80006000, name="GeminiPowerup", position=(1, 2, 3))
        state = SimpleNamespace(front_mode=16, player=SimpleNamespace(address=0x80001000),
                                actors=[actor])
        with patch("scripts.phase95_inventory.decode", return_value=state):
            result = inventory(memory, {"sequence": 1, "player": 0x80001000})
            self.assertEqual(result["health_pickups"][0]["flag"], 47)
            self.assertTrue(result["health_pickups"][0]["eligible"])
            memory[0x10000 + 0x30 + 47 // 8] |= 1 << (47 % 8)
            self.assertFalse(inventory(memory, {"sequence": 1, "player": 0x80001000})[
                "health_pickups"][0]["eligible"])
            memory[0x5000 + 0x2B8] ^= 1
            with self.assertRaises(ObservationError):
                inventory(memory, {"sequence": 1, "player": 0x80001000})

    def test_health_powerup_eligibility_requires_health_deficit(self):
        memory = bytearray(0x400000)
        struct.pack_into(">9I", memory, 0x47C70, 0x00085100, 0x01485023, 0x000A5080,
                         0x3C098010, 0x8D29D7D4, 0x01485023, 0x000A5040, 0x012A1021, 0x2442015C)
        struct.pack_into(">7I", memory, 0x3B500, 0x00047080, 0x01C47023,
                         0x3C0F800A, 0x25EF1490, 0x000E7100, 0x03E00008, 0x01CF1021)
        struct.pack_into(">I", memory, 0x1068, 0x80002000)
        struct.pack_into(">I", memory, 0x104C, 0x80003000)
        struct.pack_into(">h", memory, 0x3006, 8704)
        struct.pack_into(">I", memory, 0xFD7D4, 0x80010000)
        memory[0x2001] = 1
        struct.pack_into(">h", memory, 0x10000 + 0x15C + 0x76 + 2, 6)
        struct.pack_into(">I", memory, 0xFEAA0, 0x80004000)
        struct.pack_into(">I", memory, 0x4000 + 104 * 32, 0x80005000)
        struct.pack_into(">I", memory, 0x5000 + 0x1F0, 0x27BDFF80)
        struct.pack_into(">I", memory, 0x5000 + 0x2B8, 0x15610015)
        struct.pack_into(">I", memory, 0x5000 + 0x5FC, 0xA44D0006)
        struct.pack_into(">I", memory, 0xAB24C + 59 * 4, 0x8000FFD0)
        struct.pack_into(">I", memory, 0xFFD0, 0x0C00147C)
        struct.pack_into(">h", memory, 0x6048, 61)
        struct.pack_into(">I", memory, 0x6068, 0x80007000)
        struct.pack_into(">h", memory, 0x7012, 0xA9)
        actor = SimpleNamespace(address=0x80006000, name="HealthPowerup", position=(1, 2, 3))
        state = SimpleNamespace(front_mode=16, player=SimpleNamespace(address=0x80001000),
                                actors=[actor])
        with patch("scripts.phase95_inventory.decode", return_value=state):
            self.assertFalse(inventory(memory, {"sequence": 1, "player": 0x80001000})[
                "health_pickups"][0]["eligible"])
            struct.pack_into(">h", memory, 0x3006, 8448)
            self.assertTrue(inventory(memory, {"sequence": 1, "player": 0x80001000})[
                "health_pickups"][0]["eligible"])
            struct.pack_into(">I", memory, 0x6088, 1)
            self.assertFalse(inventory(memory, {"sequence": 1, "player": 0x80001000})[
                "health_pickups"][0]["eligible"])

    def test_inventory_layout_and_profile_rejection(self):
        memory = bytearray(0x400000)
        struct.pack_into(">9I", memory, 0x47C70, 0x00085100, 0x01485023, 0x000A5080,
                         0x3C098010, 0x8D29D7D4, 0x01485023, 0x000A5040, 0x012A1021, 0x2442015C)
        struct.pack_into(">7I", memory, 0x3B500, 0x00047080, 0x01C47023, 0x3C0F800A,
                         0x25EF1490, 0x000E7100, 0x03E00008, 0x01CF1021)
        struct.pack_into(">I", memory, 0x1068, 0x80002000)
        struct.pack_into(">I", memory, 0x104C, 0x80003000)
        struct.pack_into(">h", memory, 0x3006, 1024)
        struct.pack_into(">I", memory, 0xFD7D4, 0x80010000)
        memory[0x2001] = 1
        character = 0x10000 + 0x15C + 0x76
        struct.pack_into(">H", memory, character + 0xA, 1)
        struct.pack_into(">H", memory, character + 0x14, 42)
        struct.pack_into(">H", memory, character + 0x34, 100)
        with patch("scripts.phase95_inventory.decode", return_value=SimpleNamespace(
                front_mode=16, player=SimpleNamespace(address=0x80001000), actors=[])):
            result = inventory(memory, {"sequence": 1, "player": 0x80001000})
            self.assertEqual((result["character"], result["ammo"][0], result["capacity"][0]), (1, 42, 100))
            self.assertEqual((result["health_raw"], result["health_capacity_raw"]), (1024, 1024))
            memory[0xA4FC4] = 1
            with self.assertRaises(ObservationError):
                inventory(memory, {"sequence": 1, "player": 0x80001000})
            memory[0xA4FC4] = 0
            memory[0x47C70] ^= 1
            with self.assertRaises(ObservationError):
                inventory(memory, {"sequence": 1, "player": 0x80001000})


if __name__ == "__main__":
    unittest.main()
