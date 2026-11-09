import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts import phase95_tas_sample_grid as grid


class TasSampleGridTests(unittest.TestCase):
    def test_grid_targets_skip_sealed_segment_endpoints(self):
        self.assertEqual(grid.grid_targets(40, 20, 5),
                         [4, 9, 14, 24, 29, 34])
        self.assertEqual(grid.grid_targets(12, 6, 3), [2, 8])
        with self.assertRaises(ValueError):
            grid.grid_targets(12, 6, 0)

    def test_concurrent_grid_lock_fails_without_deleting_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with grid.grid_lock(root):
                with self.assertRaisesRegex(RuntimeError, "another sample-grid"):
                    with grid.grid_lock(root):
                        pass
            self.assertTrue((root / "sample-grid.lock").exists())
            with grid.grid_lock(root):
                pass

    def _fixture(self, root, *, sealed=True):
        private = root / "private"
        private.mkdir()
        source = private / "batch"
        source.mkdir()
        (source / "batch.json").write_text("{}")
        (source / "batch-result.json").write_text(json.dumps({
            "kind": grid.batch.KIND, "schema": 1, "complete": sealed,
            "segments_total": 2, "segments_complete": 2 if sealed else 1,
            "last_complete_frame": 11 if sealed else 5}))
        pins = {"movie_frames": 12, "script_sha256": "synthetic-lua",
                "rom_sha1": "synthetic-rom", "rom_sha256": "synthetic-rom-sha",
                "movie_sha256": "synthetic-movie", "emulator_sha256": "synthetic-emulator",
                "runtime_sha256": "synthetic-runtime"}
        plan = {"pins": pins, "segment_frames": 6,
                "source_emulator": str(private / "source-emulator" / "EmuHawk.exe"),
                "driver_sha256": "synthetic-driver"}
        first = source / "segments" / "segment-000000-000005" / "attempt-0000"
        second = source / "segments" / "segment-000006-000011" / "attempt-0000"
        first.mkdir(parents=True)
        second.mkdir(parents=True)
        (first / "result.json").write_text(json.dumps({
            "last": 5, "continuation_sha256": "first-state"}))
        (second / "result.json").write_text(json.dumps({
            "last": 11, "continuation_sha256": "second-state"}))
        return private, source, plan, first, second

    def _fake_sample(self, batch_root, plan, first_state, *, fail_first=False):
        calls = []

        def create(attempt, source, target, *, interval, timeout):
            calls.append((attempt, target))
            attempt.mkdir()
            if fail_first and len(calls) == 1:
                (attempt / "sample-result.json").write_text(json.dumps({
                    "complete": False, "error": "synthetic failure"}))
                raise RuntimeError("synthetic failure")
            prior = first_state if target == 8 else None
            parent_hash = "first-state" if prior else None
            first = 6 if prior else 0
            request = {"kind": grid.sampler.KIND, "schema": 1,
                       "semantic_status": "raw-unverified-jp",
                       "target_frame": target, "capture_first": first,
                       "source_batch": str(batch_root),
                       "source_batch_plan_sha256": grid.capture.digest(
                           batch_root / "batch.json"),
                       "sealed_predecessor": str(prior) if prior else None,
                       "sealed_predecessor_sha256": parent_hash,
                       "sampler_sha256": grid.capture.digest(
                           Path(grid.sampler.__file__).resolve()),
                       "capture_driver_sha256": plan["driver_sha256"],
                       "capture_lua_sha256": plan["pins"]["script_sha256"],
                       "interval": interval, "timeout": timeout}
            capture_dir = attempt / "capture"
            capture_dir.mkdir()
            state = capture_dir / "continuation.State"
            state.write_bytes(f"state-{target}".encode())
            captured = {**plan["pins"], "complete": True,
                        "first": first, "last": target,
                        "resume_from": str(prior) if prior else None,
                        "parent_continuation_sha256": parent_hash,
                        "continuation_sha256": grid.capture.digest(state)}
            (capture_dir / "result.json").write_text(json.dumps(captured))
            extracted_dir = capture_dir / "state-extract"
            extracted_dir.mkdir()
            rdram = extracted_dir / f"frame-{target:06d}.rdram"
            rdram.write_bytes(b"synthetic RAM")
            result = {**request, "complete": True,
                      "capture_result_sha256": grid.capture.digest(
                          capture_dir / "result.json"),
                      "continuation_sha256": captured["continuation_sha256"],
                      "rdram": str(rdram), "rdram_sha256": "synthetic-rdram-sha"}
            (attempt / "sample-request.json").write_text(json.dumps(request))
            (attempt / "sample-result.json").write_text(json.dumps(result))
            return result

        return create, calls

    def _patches(self, private, plan, first, second):
        def select(segment, start, last, pins, previous):
            return first if start == 0 else second
        return (mock.patch.object(grid.sampler, "PRIVATE_ROOT", private),
                mock.patch.object(grid.state_batch, "validate_plan", return_value=plan),
                mock.patch.object(grid.batch, "_complete_attempt", side_effect=select),
                mock.patch.object(grid.capture, "validate_resume", return_value=None),
                mock.patch.object(grid.capture, "parse_trace", return_value={}),
                mock.patch.object(grid.state_batch, "validate_extract",
                                  return_value={"rdram_sha256": "synthetic-rdram-sha"}))

    def test_refuses_unsealed_batch_before_grid_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            private, source, plan, first, second = self._fixture(
                Path(directory), sealed=False)
            output = private / "grid"
            patches = self._patches(private, plan, first, second)
            with patches[0], patches[1], patches[2]:
                with self.assertRaisesRegex(ValueError, "not sealed"):
                    grid.run_grid(output, source, spacing=3)
            self.assertFalse(output.exists())

    def test_bounded_restart_and_idempotent_completed_samples(self):
        with tempfile.TemporaryDirectory() as directory:
            private, source, plan, first, second = self._fixture(Path(directory))
            output = private / "grid"
            fake, calls = self._fake_sample(source, plan, first)
            patches = self._patches(private, plan, first, second)
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], \
                    mock.patch.object(grid.sampler, "sample", side_effect=fake):
                first_run = grid.run_grid(output, source, spacing=3, max_jobs=1)
                self.assertEqual(first_run["samples_complete"], 1)
                self.assertFalse(first_run["complete"])
                second_run = grid.run_grid(output, source, spacing=3, max_jobs=1)
                self.assertEqual(second_run["samples_complete"], 2)
                self.assertTrue(second_run["complete"])
                third_run = grid.run_grid(output, source, spacing=3, max_jobs=0)
                self.assertTrue(third_run["complete"])
            self.assertEqual([target for _, target in calls], [2, 8])
            self.assertEqual(grid.state_batch.read_json(output / grid.LEDGER_NAME),
                             third_run)

    def test_failed_attempt_is_preserved_then_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            private, source, plan, first, second = self._fixture(Path(directory))
            output = private / "grid"
            fake, calls = self._fake_sample(source, plan, first, fail_first=True)
            patches = self._patches(private, plan, first, second)
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], \
                    mock.patch.object(grid.sampler, "sample", side_effect=fake):
                with self.assertRaisesRegex(RuntimeError, "synthetic failure"):
                    grid.run_grid(output, source, spacing=3, max_jobs=1)
                failed = output / "samples" / "frame-000002" / "attempt-0000"
                self.assertTrue(failed.exists())
                report = grid.run_grid(output, source, spacing=3, max_jobs=1)
                self.assertEqual(report["samples_complete"], 1)
                self.assertEqual(report["failed_attempts_seen"], 1)
                self.assertTrue((failed.parent / "attempt-0001").exists())

    def test_corrupt_completed_sample_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            private, source, plan, first, second = self._fixture(Path(directory))
            output = private / "grid"
            fake, calls = self._fake_sample(source, plan, first)
            patches = self._patches(private, plan, first, second)
            with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], \
                    mock.patch.object(grid.sampler, "sample", side_effect=fake):
                grid.run_grid(output, source, spacing=3, max_jobs=1)
                captured = (output / "samples" / "frame-000002" /
                            "attempt-0000" / "capture" / "result.json")
                captured.write_text(captured.read_text() + " ")
                with self.assertRaisesRegex(RuntimeError, "digest differ"):
                    grid.run_grid(output, source, spacing=3, max_jobs=0)
                self.assertEqual(len(calls), 1)
                self.assertEqual(len(grid.state_batch.read_json(
                    output / grid.LEDGER_NAME)["errors"]), 1)


if __name__ == "__main__":
    unittest.main()
