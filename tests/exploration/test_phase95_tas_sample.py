import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts import phase95_tas_sample as sample_module


class TasSampleTests(unittest.TestCase):
    def test_nearest_sealed_predecessor_and_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = {"pins": {"movie_frames": 6}, "segment_frames": 2}
            first = root / "segments" / "segment-000000-000001" / "attempt-0000"
            second = root / "segments" / "segment-000002-000003" / "attempt-0000"
            with mock.patch.object(sample_module.batch, "_complete_attempt",
                                   side_effect=[first, second]) as selected:
                self.assertEqual(sample_module.select_predecessor(root, plan, 5), second)
                self.assertEqual(selected.call_count, 2)
                self.assertEqual(selected.call_args.args[-1], first)
            with mock.patch.object(sample_module.batch, "_complete_attempt",
                                   return_value=None):
                with self.assertRaisesRegex(ValueError, "missing sealed predecessor"):
                    sample_module.select_predecessor(root, plan, 5)
            with mock.patch.object(sample_module.batch, "_complete_attempt") as selected:
                self.assertIsNone(sample_module.select_predecessor(root, plan, 0))
                selected.assert_not_called()

    def _fixture(self, root):
        private = root / "private"
        private.mkdir()
        batch_root = private / "batch"
        batch_root.mkdir()
        (batch_root / "batch.json").write_text("{}")
        emulator = private / "source" / "EmuHawk.exe"
        emulator.parent.mkdir()
        emulator.write_bytes(b"synthetic")
        rom = private / "rom"
        rom.write_bytes(b"synthetic")
        movie = private / "movie"
        movie.write_bytes(b"synthetic")
        pins = {"movie_frames": 6, "script_sha256": "synthetic-lua",
                "synthetic": "pin"}
        plan = {"pins": pins, "segment_frames": 2,
                "source_emulator": str(emulator),
                "source_rom": str(rom), "source_movie": str(movie),
                "driver_sha256": sample_module.capture.digest(
                    Path(sample_module.capture.__file__).resolve()),
                "batch_sha256": sample_module.capture.digest(
                    Path(sample_module.batch.__file__).resolve())}
        prior = private / "sealed" / "attempt-0000"
        prior.mkdir(parents=True)
        (prior / "result.json").write_text(json.dumps({
            "last": 3, "continuation_sha256": "parent-sha"}))
        return private, batch_root, plan, prior

    def test_sample_uses_one_isolated_capture_and_extract(self):
        with tempfile.TemporaryDirectory() as directory:
            private, batch_root, plan, prior = self._fixture(Path(directory))
            output = private / "sample"

            def fake_capture(path, emulator, rom, movie, **kwargs):
                self.assertEqual(path, output / "capture")
                self.assertEqual((kwargs["first"], kwargs["last"]), (4, 5))
                self.assertEqual(kwargs["resume_from"], prior)
                path.mkdir()
                (path / "result.json").write_text("{}")
                return {"complete": True, "first": 4, "last": 5,
                        "resume_from": str(prior),
                        "parent_continuation_sha256": "parent-sha",
                        "continuation_sha256": "child-sha"}

            def fake_extract(path):
                self.assertEqual(path, output / "capture")
                target = path / "state-extract"
                target.mkdir()
                (target / "frame-000005.rdram").write_bytes(b"synthetic")
                return {"frame": 5, "semantic_status": "raw-unverified-jp",
                        "rdram_sha256": "ram-sha"}

            with mock.patch.object(sample_module, "PRIVATE_ROOT", private), \
                    mock.patch.object(sample_module.state_batch, "validate_plan",
                                      return_value=plan), \
                    mock.patch.object(sample_module.batch, "_pins", return_value=plan["pins"]), \
                    mock.patch.object(sample_module, "select_predecessor", return_value=prior), \
                    mock.patch.object(sample_module.capture, "capture",
                                      side_effect=fake_capture) as captured, \
                    mock.patch.object(sample_module.state_extract, "extract",
                                      side_effect=fake_extract) as extracted:
                result = sample_module.sample(output, batch_root, 5)
            self.assertTrue(result["complete"])
            self.assertEqual(result["rdram_sha256"], "ram-sha")
            self.assertEqual(result["sealed_predecessor_sha256"], "parent-sha")
            self.assertEqual(captured.call_count, 1)
            self.assertEqual(extracted.call_count, 1)
            self.assertTrue((output / "sample-request.json").exists())
            self.assertEqual(json.loads((output / "sample-result.json").read_text()),
                             result)

    def test_failure_preserves_new_private_output(self):
        with tempfile.TemporaryDirectory() as directory:
            private, batch_root, plan, prior = self._fixture(Path(directory))
            output = private / "failed-sample"
            with mock.patch.object(sample_module, "PRIVATE_ROOT", private), \
                    mock.patch.object(sample_module.state_batch, "validate_plan",
                                      return_value=plan), \
                    mock.patch.object(sample_module.batch, "_pins", return_value=plan["pins"]), \
                    mock.patch.object(sample_module, "select_predecessor", return_value=prior), \
                    mock.patch.object(sample_module.capture, "capture",
                                      side_effect=RuntimeError("synthetic worker failure")):
                with self.assertRaisesRegex(RuntimeError, "synthetic worker failure"):
                    sample_module.sample(output, batch_root, 5)
            self.assertTrue(output.exists())
            self.assertFalse(json.loads((output / "sample-result.json").read_text())
                             ["complete"])
            with mock.patch.object(sample_module, "PRIVATE_ROOT", private):
                with self.assertRaises(FileExistsError):
                    sample_module.sample(output, batch_root, 5)

    def test_private_scope_and_invalid_target_fail_before_write(self):
        with tempfile.TemporaryDirectory() as directory:
            private, batch_root, plan, prior = self._fixture(Path(directory))
            with mock.patch.object(sample_module, "PRIVATE_ROOT", private), \
                    mock.patch.object(sample_module.state_batch, "validate_plan",
                                      return_value=plan):
                with self.assertRaisesRegex(ValueError, "tools/private"):
                    sample_module.sample(Path(directory) / "public", batch_root, 5)
                output = private / "invalid"
                with self.assertRaisesRegex(ValueError, "outside pinned movie"):
                    sample_module.sample(output, batch_root, 6)
                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
