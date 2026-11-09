import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace

from scripts import phase95_tas_followthrough as follow


class TasFollowthroughTests(unittest.TestCase):
    def test_disk_headroom_includes_worker_copy_ram_and_reserve(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            emulator = root / "emulator"
            emulator.mkdir()
            (emulator / "EmuHawk.exe").write_bytes(b"x" * 100)
            with mock.patch.object(follow.shutil, "disk_usage",
                                   return_value=SimpleNamespace(free=123456789)):
                budget = follow._disk_headroom(root, emulator, 256)
            self.assertEqual(budget["free"], 123456789)
            self.assertEqual(budget["required"],
                             256 * 1024 * 1024 + 200 +
                             2 * follow.state_extract.RDRAM_SIZE +
                             256 * 1024 * 1024)

    def _fixture(self, root, *, sealed):
        private = root / "private"
        private.mkdir()
        batch = private / "batch"
        batch.mkdir()
        (batch / "batch.json").write_text("{}")
        if sealed:
            (batch / "batch-result.json").write_text(json.dumps({
                "kind": follow.state_batch.PLAN_KIND, "schema": 1,
                "complete": True}))
        emulator = private / "emulator" / "EmuHawk.exe"
        emulator.parent.mkdir()
        emulator.write_bytes(b"synthetic emulator")
        plan = {"source_emulator": str(emulator),
                "pins": {"script_sha256": "synthetic-lua"}}
        return private, batch, plan

    def _stage_mocks(self, batch):
        def index(root):
            self.assertEqual(root, batch)
            (root / follow.state_batch.INDEX_NAME).write_text("{}")
            return {"complete": True, "segments_extracted": 2, "errors": []}

        def atlas(index_path, *args, **kwargs):
            self.assertEqual(index_path, batch / follow.state_batch.INDEX_NAME)
            self.assertEqual(kwargs["grid_progress_path"],
                             batch.parent / "follow" / "grid" / follow.grid.LEDGER_NAME)
            (batch / follow.atlas_module.OUTPUT_NAME).write_text("{}")
            ledger = kwargs["grid_progress_path"]
            return {"route_complete": True,
                    "grid_complete": getattr(self, "_last_grid_complete", False),
                    "grid_provenance": {"grid_progress_sha256":
                                        follow.capture.digest(ledger)}}

        def grid(output, root, **kwargs):
            self.assertEqual(root, batch)
            output.mkdir(parents=True, exist_ok=True)
            (output / follow.grid.LEDGER_NAME).write_text("{}")
            result = {"complete": kwargs["max_jobs"] == 0,
                    "samples_complete": 2 if kwargs["max_jobs"] == 0 else 1,
                    "targets_total": 2,
                    "jobs_started_this_invocation": kwargs["max_jobs"]}
            self._last_grid_complete = result["complete"]
            return result

        return index, atlas, grid

    def test_waits_without_touching_batch_or_starting_grid(self):
        with tempfile.TemporaryDirectory() as directory:
            private, batch, plan = self._fixture(Path(directory), sealed=False)
            output = private / "follow"
            with mock.patch.object(follow.sampler, "PRIVATE_ROOT", private), \
                    mock.patch.object(follow.state_batch, "validate_plan",
                                      return_value=plan), \
                    mock.patch.object(follow.grid, "run_grid") as grid_run:
                status = follow.run_followthrough(output, batch, wait_seconds=0)
                again = follow.run_followthrough(output, batch, wait_seconds=0)
            self.assertEqual(status["status"], "waiting-for-batch")
            self.assertFalse(status["complete"])
            self.assertEqual(status["full_game_acceptance"], False)
            self.assertEqual(again["status"], status["status"])
            grid_run.assert_not_called()
            self.assertTrue((output / follow.PLAN_NAME).exists())
            self.assertFalse((batch / follow.atlas_module.OUTPUT_NAME).exists())

    def test_grid_progress_refreshes_atlas_before_grid_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            private, batch, plan = self._fixture(Path(directory), sealed=True)
            output = private / "follow"
            index, atlas, grid = self._stage_mocks(batch)
            calls = []

            def progress(*args, **kwargs):
                calls.append(kwargs["max_jobs"])
                result = grid(*args, **kwargs)
                result["complete"] = len(calls) == 2
                result["samples_complete"] = len(calls)
                self._last_grid_complete = result["complete"]
                return result

            with mock.patch.object(follow.sampler, "PRIVATE_ROOT", private), \
                    mock.patch.object(follow.state_batch, "validate_plan",
                                      return_value=plan), \
                    mock.patch.object(follow.state_batch, "index_batch",
                                      side_effect=index), \
                    mock.patch.object(follow.grid, "run_grid", side_effect=progress), \
                    mock.patch.object(follow.atlas_module, "build_atlas",
                                      side_effect=atlas) as atlas_call, \
                    mock.patch.object(follow, "_disk_headroom",
                                      return_value={"free": 10, "required": 1}):
                status = follow.run_followthrough(
                    output, batch, wait_seconds=10, max_jobs=2, job_timeout=1)
            self.assertTrue(status["complete"])
            self.assertEqual(status["grid_samples_complete"], 2)
            self.assertEqual(status["jobs_started_this_invocation"], 2)
            self.assertEqual(calls, [1, 1])
            self.assertEqual(atlas_call.call_count, 2)

    def test_disk_budget_stops_cleanly_before_new_job(self):
        with tempfile.TemporaryDirectory() as directory:
            private, batch, plan = self._fixture(Path(directory), sealed=True)
            output = private / "follow"
            index, atlas, grid = self._stage_mocks(batch)

            def partial(*args, **kwargs):
                self.assertEqual(kwargs["max_jobs"], 0)
                result = grid(*args, **kwargs)
                result["complete"] = False
                result["samples_complete"] = 0
                self._last_grid_complete = False
                return result

            with mock.patch.object(follow.sampler, "PRIVATE_ROOT", private), \
                    mock.patch.object(follow.state_batch, "validate_plan",
                                      return_value=plan), \
                    mock.patch.object(follow.state_batch, "index_batch",
                                      side_effect=index), \
                    mock.patch.object(follow.grid, "run_grid", side_effect=partial), \
                    mock.patch.object(follow.atlas_module, "build_atlas",
                                      side_effect=atlas), \
                    mock.patch.object(follow, "_disk_headroom",
                                      return_value={"free": 0, "required": 123}):
                status = follow.run_followthrough(
                    output, batch, wait_seconds=10, max_jobs=2, job_timeout=1)
            self.assertEqual(status["status"], "insufficient-disk")
            self.assertEqual(status["jobs_started_this_invocation"], 0)
            self.assertEqual(status["disk_required_bytes"], 123)
            self.assertFalse(status["complete"])

    def test_stage_failure_is_recorded_without_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            private, batch, plan = self._fixture(Path(directory), sealed=True)
            output = private / "follow"
            with mock.patch.object(follow.sampler, "PRIVATE_ROOT", private), \
                    mock.patch.object(follow.state_batch, "validate_plan",
                                      return_value=plan), \
                    mock.patch.object(follow.state_batch, "index_batch",
                                      side_effect=ValueError("synthetic state error")):
                with self.assertRaisesRegex(ValueError, "synthetic state error"):
                    follow.run_followthrough(output, batch, wait_seconds=0)
            status = follow.state_batch.read_json(output / follow.STATUS_NAME)
            self.assertEqual(status["status"], "error")
            self.assertFalse(status["complete"])
            self.assertTrue((output / follow.PLAN_NAME).exists())

    def test_invalid_budget_and_public_output_fail_before_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            private, batch, plan = self._fixture(Path(directory), sealed=False)
            with mock.patch.object(follow.sampler, "PRIVATE_ROOT", private):
                with self.assertRaisesRegex(ValueError, "tools/private"):
                    follow.run_followthrough(Path(directory) / "public", batch,
                                             wait_seconds=0)
                output = private / "invalid"
                with self.assertRaisesRegex(ValueError, "bounded"):
                    follow.run_followthrough(output, batch, reserve_mib=1)
                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
