import math
import struct
import unittest

from scripts.phase95_jp_observation import (
    ACTOR_COUNT, ACTOR_LIST, CANDIDATE_PLAYER_POINTER, JPObservationError,
    FRONT_MODE, LEVEL_WORD, RNG_SEED, RDRAM_SIZE, decode,
)


def fixture():
    memory = bytearray(RDRAM_SIZE)
    for offset, signature in (
            (0x588B4, bytes.fromhex("3C02800A904250C003E0000800000000")),
            (0x445BC, bytes.fromhex("3C0280108C42B02403E0000800000000")),
            (0x48C50, bytes.fromhex("3C01800A03E00008AC2432E4")),
            (0x48C68, bytes.fromhex("3C08800A8D0832E4")),
            (0x48CA0, bytes.fromhex("01694026AC2832E4"))):
        memory[offset:offset + len(signature)] = signature
    memory[FRONT_MODE] = 16
    struct.pack_into(">i", memory, LEVEL_WORD, 47)
    struct.pack_into(">I", memory, RNG_SEED, 0x2BEFAE0F)
    struct.pack_into(">II", memory, ACTOR_LIST, 0x80003000, 2)
    struct.pack_into(">I", memory, CANDIDATE_PLAYER_POINTER, 0x80004000)
    struct.pack_into(">III", memory, 0x3000, 0x80004000, 0x80004100,
                     0xDEADBEEF)  # stale slot beyond the declared count
    for actor, header, name, yaw, position in (
            (0x4000, 0x5000, b"playerBoy", 0x1234, (1.0, -2.0, 3.0)),
            (0x4100, 0x5100, b"exit", 0x4321, (4.0, 5.0, 6.0))):
        struct.pack_into(">H", memory, actor, yaw)
        struct.pack_into(">fff", memory, actor + 0x0C, *position)
        struct.pack_into(">I", memory, actor + 0x40, 0x80000000 + header)
        memory[header + 4:header + 4 + len(name)] = name
    return memory


class JPObservationTests(unittest.TestCase):
    def test_decodes_only_declared_actors_and_identifies_player(self):
        observation = decode(fixture(), frame=6000)
        self.assertEqual(observation.actor_table, 0x80003000)
        self.assertEqual(observation.actor_count, 2)
        self.assertEqual([actor.name for actor in observation.actors],
                         ["playerBoy", "exit"])
        self.assertEqual(observation.player.address, 0x80004000)
        self.assertEqual(observation.player.position, (1.0, -2.0, 3.0))
        self.assertEqual(observation.player.yaw, 0x1234)
        self.assertEqual(observation.player_resolution, "matched")
        self.assertFalse(observation.acceptance)
        self.assertEqual(observation.level_id, 47)
        self.assertEqual(observation.front_mode, 16)
        self.assertEqual(observation.rng, 0x2BEFAE0F)
        self.assertIsNone(observation.progression)
        self.assertIn("progression", observation.unverified_fields)
        self.assertNotIn("level_id", observation.unverified_fields)

    def test_player_candidate_must_agree_with_unique_named_actor(self):
        memory = fixture()
        struct.pack_into(">I", memory, CANDIDATE_PLAYER_POINTER, 0x80004100)
        observation = decode(memory, frame=6000)
        self.assertIsNone(observation.player)
        self.assertEqual(observation.player_resolution, "candidate_mismatch")
        self.assertEqual(len(observation.actors), 2)
        self.assertIn("player", observation.unverified_fields)
        memory = fixture()
        memory[0x5104:0x5104 + len(b"playerBoy")] = b"playerBoy"
        observation = decode(memory, frame=6000)
        self.assertIsNone(observation.player)
        self.assertEqual(observation.player_resolution, "multiple_named_players")

    def test_mode_dependent_nonpointer_candidate_keeps_actor_table(self):
        memory = fixture()
        struct.pack_into(">I", memory, CANDIDATE_PLAYER_POINTER, 8)
        observation = decode(memory, frame=59999)
        self.assertEqual(observation.actor_count, 2)
        self.assertEqual(observation.actors[0].name, "playerBoy")
        self.assertIsNone(observation.player)
        self.assertEqual(observation.candidate_player_pointer, 8)
        self.assertEqual(observation.player_resolution, "candidate_mismatch")

    def test_duplicate_and_invalid_actor_pointers_fail_closed(self):
        memory = fixture()
        struct.pack_into(">I", memory, 0x3004, 0x80004000)
        with self.assertRaisesRegex(JPObservationError, "duplicate"):
            decode(memory, frame=6000)
        memory = fixture()
        struct.pack_into(">I", memory, 0x3004, 0x807FFFF0)
        with self.assertRaisesRegex(JPObservationError, "out-of-range"):
            decode(memory, frame=6000)

    def test_bad_name_and_nonfinite_position_fail_closed(self):
        memory = fixture()
        memory[0x5104:0x5114] = b"X" * 16
        with self.assertRaisesRegex(JPObservationError, "unterminated"):
            decode(memory, frame=6000)
        memory = fixture()
        struct.pack_into(">f", memory, 0x400C, math.nan)
        with self.assertRaisesRegex(JPObservationError, "non-finite"):
            decode(memory, frame=6000)

    def test_shape_and_count_validation(self):
        with self.assertRaisesRegex(JPObservationError, "8 MiB"):
            decode(bytearray(0x400000), frame=0)
        with self.assertRaisesRegex(JPObservationError, "invalid frame"):
            decode(fixture(), frame=True)
        memory = fixture()
        struct.pack_into(">I", memory, ACTOR_COUNT, 1025)
        with self.assertRaisesRegex(JPObservationError, "count"):
            decode(memory, frame=0)

    def test_semantic_offsets_require_exact_jp_code_profile(self):
        for offset in (0x588B4, 0x445BC, 0x48C50, 0x48C68, 0x48CA0):
            memory = fixture()
            memory[offset] ^= 1
            with self.assertRaisesRegex(JPObservationError, "code profile mismatch"):
                decode(memory, frame=6000)

    def test_zero_actor_transition_keeps_verified_semantics(self):
        memory = fixture()
        struct.pack_into(">I", memory, ACTOR_COUNT, 0)
        struct.pack_into(">I", memory, CANDIDATE_PLAYER_POINTER, 8)
        observation = decode(memory, frame=40099)
        self.assertEqual(observation.actor_count, 0)
        self.assertEqual(observation.actor_table, 0x80003000)
        self.assertEqual(observation.actors, ())
        self.assertIsNone(observation.player)
        self.assertEqual(observation.player_resolution, "no_named_player")
        self.assertEqual(observation.level_id, 47)


if __name__ == "__main__":
    unittest.main()
