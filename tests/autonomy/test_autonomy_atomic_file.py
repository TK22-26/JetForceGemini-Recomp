import os
from pathlib import Path
import tempfile
import threading
import unittest

from scripts.autonomy.atomic_file import replace


class AtomicFileTests(unittest.TestCase):
    def test_replaces_complete_file_and_rejects_missing_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "record.json"
            source = Path(temporary) / "record.tmp"
            target.write_text("old")
            source.write_text("new")
            replace(source, target)
            self.assertEqual(target.read_text(), "new")
            with self.assertRaises(FileNotFoundError):
                replace(source, target)
            self.assertEqual(target.read_text(), "new")

    @unittest.skipUnless(os.name == "nt", "Windows file sharing contract")
    def test_short_reader_blocks_plain_replace_but_bounded_publish_succeeds(self):
        with tempfile.TemporaryDirectory() as temporary:
            target, source = Path(temporary) / "record.json", Path(temporary) / "record.tmp"
            target.write_text("old")
            source.write_text("new")
            reader = target.open("rb")
            try:
                with self.assertRaises(OSError) as failure:
                    source.replace(target)
                self.assertIn(failure.exception.winerror, (5, 32, 33))
                self.assertEqual(reader.read(), b"old")
                timer = threading.Timer(0.05, reader.close)
                timer.start()
                try:
                    replace(source, target)
                finally:
                    timer.join()
            finally:
                reader.close()
            self.assertEqual(target.read_text(), "new")
            self.assertFalse(source.exists())

    @unittest.skipUnless(os.name == "nt", "Windows file sharing contract")
    def test_persistent_reader_fails_closed_without_losing_previous_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            target, source = Path(temporary) / "record.json", Path(temporary) / "record.tmp"
            target.write_text("old")
            source.write_text("new")
            with target.open("rb"):
                with self.assertRaises(OSError):
                    replace(source, target, timeout=0.02)
            self.assertEqual(target.read_text(), "old")
            self.assertEqual(source.read_text(), "new")


if __name__ == "__main__":
    unittest.main()
