import unittest
import struct
from types import SimpleNamespace
from unittest.mock import patch
from scripts.phase95_dialogue import DialogueProbe, hint_state
from scripts.phase95_observation import ObservationError


class DialogueTests(unittest.TestCase):
    def memory_fixture(self):
        memory = bytearray(0x400000)
        struct.pack_into(">12I", memory, 0xFC80, 0x848B0048, 0, 0x256CFFFE,
                         0x2D8100AD, 0x10200205, 0x000C6080, 0x3C01800B,
                         0x002C0821, 0x8C2CB24C, 0, 0x01800008, 0)
        struct.pack_into(">I", memory, 0xFEAA0, 0x80002000)
        struct.pack_into(">I", memory, 0x2000 + 32 * 32, 0x80003000)
        struct.pack_into(">6I", memory, 0x3000, 0x27BDFFA8, 0xAFBF003C,
                         0xAFB10038, 0xAFB00034, 0x8C900068, 0x848E0000)
        struct.pack_into(">I", memory, 0xAB24C + 88 * 4, 0x80004000)
        struct.pack_into(">I", memory, 0x4000, 0x0C000CBA)
        struct.pack_into(">2I", memory, 0x5540, 0x3C078000, 0x8CE76000)
        struct.pack_into(">h", memory, 0x1048, 90)
        struct.pack_into(">I", memory, 0x1068, 0x80005000)
        actor = SimpleNamespace(address=0x80001000, name="KingBear", position=(1, 2, 3))
        state = SimpleNamespace(front_mode=16, actors=[actor], player=actor)
        return memory, state

    def test_named_npc_requires_matching_live_controller(self):
        memory, state = self.memory_fixture()
        with patch("scripts.phase95_dialogue.decode", return_value=state):
            result = hint_state(memory, 1, state.player.address, "KingBear")
            self.assertEqual((result["mode"], result["control"]), (0, 90))
            memory[0x4003] ^= 1
            with self.assertRaises(ObservationError):
                hint_state(memory, 1, state.player.address, "KingBear")

    def test_rejects_bad_profiles_context_and_private_state(self):
        for offset, value in ((0xFC80, 0), (0x3000, 0), (0x1048, 0xFF),
                              (0x5000, 19), (0x1068, 0), (0x5540, 0), (0x6000, 0x80)):
            with self.subTest(offset=offset):
                memory, state = self.memory_fixture()
                memory[offset] = value
                with patch("scripts.phase95_dialogue.decode", return_value=state):
                    with self.assertRaises(ObservationError):
                        hint_state(memory, 1, state.player.address, "KingBear")
        memory, state = self.memory_fixture()
        with patch("scripts.phase95_dialogue.decode", return_value=state):
            with self.assertRaises(ObservationError):
                hint_state(memory, 1, state.player.address, "unreviewed")
            state.player = None
            with self.assertRaises(ObservationError):
                hint_state(memory, 1, 0, "KingBear")

    def test_idle_without_conversation_is_not_completion(self):
        policy = DialogueProbe()
        for mode in (0, 1, 0, 0, 0, 2, 0, 0, 0):
            self.assertIsNotNone(policy.choose(mode, conversation_active=False))

    def test_active_to_stable_idle(self):
        policy = DialogueProbe()
        policy.choose(3, conversation_active=True)
        self.assertEqual(policy.choose(0, conversation_active=False).buttons, 0)
        self.assertIsNotNone(policy.choose(1, conversation_active=False))
        self.assertIsNone(policy.choose(0, conversation_active=False))

    def test_release_edges(self):
        policy = DialogueProbe()
        self.assertEqual(policy.choose(3, conversation_active=True).buttons, 0x8000)
        self.assertEqual(policy.choose(3, conversation_active=True).buttons, 0)

    def test_bad_mode(self):
        for value in (-1, 19, True):
            with self.assertRaises(ObservationError):
                DialogueProbe().choose(value, conversation_active=False)

    def test_only_selected_actor_is_active(self):
        memory, state = self.memory_fixture()
        with patch("scripts.phase95_dialogue.decode", return_value=state):
            self.assertFalse(hint_state(memory, 1, state.player.address, "KingBear")["conversation_active"])
            struct.pack_into(">I", memory, 0x6000, state.player.address)
            self.assertTrue(hint_state(memory, 1, state.player.address, "KingBear")["conversation_active"])


if __name__ == "__main__":
    unittest.main()
