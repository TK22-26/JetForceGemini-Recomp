from collections import Counter
import unittest
from scripts.phase9_recover_task_helper import (validate_cfg, validate_pi_init,
    validate_loop_cfg, validate_thread_entry_reference, validate_returning_loop)


class HelperBoundaryTests(unittest.TestCase):
    def test_returning_leaf_loop(self):
        words = [0x24080001, 0x15000003, 0, 0x1000fffc, 0, 0x03e00008, 0xa0400000, 0, 0]
        self.assertEqual(validate_returning_loop(words, self.entry), Counter())
        for index, word in ((0, 0x0c000040), (1, 0x15000002), (3, 0x1000fffe),
                            (5, 0), (7, 1), (6, 0x10000001)):
            invalid = words.copy()
            invalid[index] = word
            with self.subTest(index=index), self.assertRaises(ValueError):
                validate_returning_loop(invalid, self.entry)

    def test_loop_with_dead_epilogue(self):
        words = [0x0c000040, 0, 0x1000fffd, 0, 0, 0x03e00008, 0x27bd0010, 0]
        self.assertEqual(validate_loop_cfg(words, self.entry, {self.callee}, 4), Counter({self.callee: 1}))
        for index, word in ((2, 0x10000001), (2, 0x1000fffe), (3, 0x10000001),
                            (4, 0x0c000040), (5, 0), (0, 0x0c000041)):
            invalid = words.copy()
            invalid[index] = word
            with self.subTest(index=index, word=word), self.assertRaises(ValueError):
                validate_loop_cfg(invalid, self.entry, {self.callee}, 4)

    def test_thread_entry_argument(self):
        words = [0x3c068000, 0, 0x24c60100, 0x0c000080, 0]
        validate_thread_entry_reference(words, 0x80000100, 0x80000200)
        for index, word in ((0, 0x3c078000), (1, 0x00003025), (3, 0x0c000081),
                            (4, 0x24060000), (1, 0x03e00008)):
            invalid = words.copy()
            invalid[index] = word
            with self.subTest(index=index), self.assertRaises(ValueError):
                validate_thread_entry_reference(invalid, 0x80000100, 0x80000200)

    def test_pi_helper_rejects_control_flow_and_wrong_extent(self):
        words = (0x24020001,) * 28 + (0x03e00008, 0)
        self.assertEqual(validate_pi_init(words), Counter())
        for invalid in (words[:-1], (0x0c000010,) + words[1:], words[:-1] + (1,)):
            with self.assertRaises(ValueError):
                validate_pi_init(invalid)

    entry = 0x80000000
    callee = 0x80000100

    def routine(self):
        # Original ROM-free CFG: optional call, converging at one return.
        return [0x27bdfff0, 0x10800003, 0, 0x0c000040, 0, 0x03e00008, 0]

    def test_closed_boundary(self):
        self.assertEqual(validate_cfg(self.routine(), self.entry, {self.callee}), Counter({self.callee: 1}))

    def test_reject_unowned_call(self):
        with self.assertRaises(ValueError):
            validate_cfg(self.routine(), self.entry, set())

    def test_reject_bad_instruction_branch_and_return(self):
        for index, word in ((0, 0xffffffff), (1, 0x1080fffe), (1, 0x10800000),
                            (1, 0x10800020), (4, 0x10000001), (0, 0x03e00008),
                            (5, 0x00000000)):
            words = self.routine()
            words[index] = word
            with self.subTest(index=index, word=word), self.assertRaises(ValueError):
                validate_cfg(words, self.entry, {self.callee})

    def test_reject_truncated_or_unaligned(self):
        for words, entry in (([], self.entry), (self.routine()[:-1], self.entry),
                             (self.routine(), self.entry + 1)):
            with self.assertRaises(ValueError):
                validate_cfg(words, entry, {self.callee})


class HelperOutputDirectoryTests(unittest.TestCase):
    """Exercise run's output policy before external tools or ROM bytes are needed."""

    def setUp(self):
        from pathlib import Path
        import tempfile
        from unittest.mock import patch
        from scripts import phase9_recover_task_helper as helper
        self.helper = helper
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.checkout = self.base / "checkout"
        self.private = self.checkout / "tools/private"
        self.private.mkdir(parents=True)
        self.elf, self.rom = self.base / "input.elf", self.base / "input.z64"
        self.elf.write_bytes(b"synthetic ELF fixture")
        self.rom.write_bytes(b"synthetic ROM fixture")
        self.enterContext(patch.object(helper, "ROOT", self.checkout))
        self.enterContext(patch.object(helper, "ROM_SHA256", helper.digest(self.rom.read_bytes())))
        self.inspect = self.enterContext(patch.object(helper, "inspect", side_effect=RuntimeError("ELF validation reached")))

    def invoke(self, output):
        return self.helper.run(output, self.elf, self.helper.digest(self.elf.read_bytes()), self.rom)

    def assert_admitted(self, output):
        with self.assertRaisesRegex(RuntimeError, "ELF validation reached"):
            self.invoke(output)
        self.inspect.assert_called_once()
        self.inspect.reset_mock()
        self.assertFalse(output.exists())

    def assert_rejected(self, output):
        with self.assertRaisesRegex(ValueError, "output directory"):
            self.invoke(output)
        self.inspect.assert_not_called()

    def test_external_and_legacy_private_outputs_are_admitted(self):
        for output in (self.base / "cache/helper-task", self.private / "helper-task"):
            with self.subTest(output=output):
                self.assert_admitted(output)

    def test_default_and_custom_windows_cache_outputs_are_admitted(self):
        from unittest.mock import patch
        from scripts.build_paths import windows_cache
        from pathlib import Path
        # Use a short synthetic base without creating it, including on Windows.
        short = Path(self.base.anchor) / "jfg-cache-fixture"
        with patch.dict("os.environ", {"LOCALAPPDATA": str(short)}):
            for cache in (windows_cache(self.checkout), windows_cache(self.checkout, short / "custom")):
                with self.subTest(cache=cache):
                    self.assert_admitted(cache / "w/0123456789ab/helper-task")

    def test_existing_external_and_private_directories_are_preserved(self):
        for output in (self.base / "cache", self.private / "helper-task"):
            output.mkdir()
            marker = output / "keep.txt"
            marker.write_text("keep")
            with self.subTest(output=output):
                self.assert_rejected(output)
                self.assertEqual(marker.read_text(), "keep")

    def test_existing_output_file_is_preserved(self):
        output = self.base / "already-used"
        output.write_text("keep")
        self.assert_rejected(output)
        self.assertEqual(output.read_text(), "keep")

    def test_checkout_destinations_outside_private_are_rejected(self):
        for output in (self.checkout / "src/generated", self.checkout / "build/helper-task",
                       self.checkout / "tools/private-lookalike/helper-task",
                       self.private / "../../src/generated"):
            with self.subTest(output=output):
                self.assert_rejected(output)
                self.assertFalse(output.exists())

    def symlink(self, link, target):
        try:
            link.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"directory symlinks unavailable: {error}")

    def test_external_alias_into_checkout_is_rejected(self):
        alias = self.base / "checkout-alias"
        self.symlink(alias, self.checkout)
        self.assert_rejected(alias / "src/generated")

    def test_dangling_output_link_is_preserved(self):
        output = self.base / "dangling-output"
        self.symlink(output, self.base / "missing-target")
        self.assert_rejected(output)
        self.assertTrue(output.is_symlink())


if __name__ == "__main__":
    unittest.main()
