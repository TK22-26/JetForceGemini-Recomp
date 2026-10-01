import unittest

from scripts.phase95_native_replay import (
    replay_environment, validate_execution_target,
)


class ExecutionProfileTests(unittest.TestCase):
    def test_original_profile_removes_ambient_probe_and_output_flags(self):
        inherited = {"PATH": "system", "JFG_PHASE9_GUEST_OS_PROBE": "0",
                     "JFG_PHASE9_SI_COUNT_PROBE": "1",
                     "JFG_PHASE9_CONTROLLER_GUEST_INIT": "1",
                     "jfg_phase8_input_replay": "wrong-file",
                     "JFG_PHASE8_FRAME_CAPTURE": "outside-output"}
        before = dict(inherited)
        result = replay_environment(inherited, "original-os-probe")
        self.assertEqual(result, {
            "PATH": "system", "JFG_PHASE9_GUEST_OS_PROBE": "1",
            "JFG_PHASE9_GUEST_LEAF_PROBE": "1",
            "JFG_PHASE9_RENDERER_WRITEBACK_PROBE": "1"})
        self.assertEqual(inherited, before)

    def test_cooperative_profile_cannot_inherit_original_os(self):
        self.assertEqual(replay_environment(
            {"PATH": "system", "JFG_PHASE9_GUEST_OS_PROBE": "1"},
            "cooperative"), {"PATH": "system"})

    def test_legacy_environment_is_preserved_but_copied(self):
        source = {"JFG_PHASE9_SI_COUNT_PROBE": "1"}
        result = replay_environment(source, None)
        self.assertEqual(result, source)
        self.assertIsNot(result, source)

    def test_unknown_profile_is_not_implicitly_legacy(self):
        for profile in ("", "original-os", False, 1):
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                replay_environment({}, profile)

    def test_original_os_only_accepts_qualified_stop_modes(self):
        environment = replay_environment({}, "original-os-probe")
        validate_execution_target(environment, 3000, False)
        for target, poll_stop in ((3, False), (3000, True)):
            with self.subTest(target=target, poll_stop=poll_stop):
                with self.assertRaisesRegex(ValueError, "VI target"):
                    validate_execution_target(environment, target, poll_stop)
        with self.assertRaisesRegex(ValueError, "guest leaves"):
            validate_execution_target({"JFG_PHASE9_GUEST_OS_PROBE": "1"},
                                      3000, False)
        validate_execution_target({}, 3, True)

    def test_original_os_rejects_unimplemented_poll_hash_observer(self):
        for environment in (replay_environment({}, "original-os-probe"),
                            {"JFG_PHASE9_GUEST_OS_PROBE": "1",
                             "JFG_PHASE9_GUEST_LEAF_PROBE": "1"}):
            with self.subTest(environment=environment):
                with self.assertRaisesRegex(ValueError, "does not implement poll semantic hashes"):
                    validate_execution_target(environment, 4800, False, poll_hashes=True)
                validate_execution_target(environment, 4800, False, poll_hashes=False)
        validate_execution_target({}, 4800, False, poll_hashes=True)


if __name__ == "__main__":
    unittest.main()
