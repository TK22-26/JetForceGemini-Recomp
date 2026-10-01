from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts import phase95_tas_batch as batch


class Phase95TasBatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.emulator = self.base / "viewer" / "EmuHawk.exe"
        self.emulator.parent.mkdir()
        self.emulator.write_bytes(b"emulator")
        self.rom = self.base / "Star Twins (Japan).z64"
        self.rom.write_bytes(b"synthetic rom")
        self.movie = self.base / "movie.bk2"
        self.movie.write_bytes(b"synthetic movie")
        self.root = self.base / "batch"
        self.patches = [
            mock.patch.object(batch, "EXPECTED_MOVIE_FRAMES", 5),
            mock.patch.object(batch, "EXPECTED_MOVIE_SHA256", "movie-hash"),
            mock.patch.object(batch.capture_module, "JP_ROM_SHA256",
                              batch.capture_module.digest(self.rom)),
            mock.patch.object(batch.capture_module, "BIZHAWK_291_EXE_SHA256",
                              batch.capture_module.digest(self.emulator)),
            mock.patch.object(batch.capture_module, "BIZHAWK_291_RUNTIME_SHA256",
                              "runtime-hash"),
            mock.patch.object(batch.capture_module, "inspect_movie",
                              return_value={"frames": 5, "movie_sha256": "movie-hash"}),
            mock.patch.object(batch.capture_module, "sha1",
                              return_value=batch.capture_module.JP_ROM_SHA1),
            mock.patch.object(batch.capture_module, "runtime_digest",
                              return_value="runtime-hash"),
        ]
        for patch in self.patches:
            patch.start()
            self.addCleanup(patch.stop)

    def fake_capture(self, output: Path, emulator: Path, rom: Path, movie: Path, *,
                     first: int, last: int, interval: int, resume_from: Path | None,
                     timeout: int, full_rdram: bool) -> dict:
        self.calls.append((first, last, resume_from, output))
        output.mkdir()
        if getattr(self, "fail_on", None) == first:
            (output / "partial.txt").write_text("retained")
            self.fail_on = None
            raise RuntimeError("synthetic worker failure")
        pins = json.loads((self.root / "batch.json").read_text())["pins"]
        state = output / "continuation.State"
        state.write_bytes(f"state-{first}-{last}".encode())
        trace = "schema\t1\nprobe_status\tunverified-jp\n"
        trace += "frame\tmovie_mode\tinput_polls_since_worker_start\n"
        trace += "".join(f"{frame}\tPLAY\t0\n" for frame in range(first, last + 1))
        (output / "frames.tsv").write_text(trace, encoding="utf-8")
        result = {**pins, "complete": True, "first": first, "last": last,
                  "continuation_sha256": batch.capture_module.digest(state),
                  "resume_from": str(resume_from) if resume_from is not None else None,
                  "parent_continuation_sha256":
                      json.loads((resume_from / "result.json").read_text())["continuation_sha256"]
                      if resume_from is not None else None}
        (output / "result.json").write_text(json.dumps(result), encoding="utf-8")
        return result

    def test_restart_preserves_failed_attempt_and_resumes_contiguously(self) -> None:
        self.calls = []
        self.fail_on = 2
        with mock.patch.object(batch.capture_module, "capture", side_effect=self.fake_capture):
            with self.assertRaisesRegex(batch.BatchError, "stopped at"):
                batch.run_batch(self.root, self.emulator, self.rom, self.movie,
                                segment_frames=2, interval=1)
            self.assertEqual([call[:2] for call in self.calls], [(0, 1), (2, 3)])
            failed = self.calls[-1][3]
            self.assertEqual((failed / "partial.txt").read_text(), "retained")
            summary = json.loads((self.root / "batch-result.json").read_text())
            self.assertEqual(summary["failed_segment"], [2, 3])
            self.assertEqual(summary["segments_complete"], 1)
            result = batch.run_batch(self.root, self.emulator, self.rom, self.movie,
                                     segment_frames=2, interval=1)
        self.assertTrue(result["complete"])
        self.assertEqual(result["segments_complete"], 3)
        self.assertEqual([call[:2] for call in self.calls],
                         [(0, 1), (2, 3), (2, 3), (4, 4)])
        self.assertEqual(self.calls[2][2], self.calls[0][3])
        self.assertEqual(self.calls[3][2], self.calls[2][3])
        self.assertEqual(self.calls[2][3].name, "attempt-0001")
        self.assertTrue(failed.exists())

    def test_completed_batch_is_noop_and_rejects_changed_plan(self) -> None:
        self.calls = []
        with mock.patch.object(batch.capture_module, "capture", side_effect=self.fake_capture):
            batch.run_batch(self.root, self.emulator, self.rom, self.movie,
                            segment_frames=2, interval=1)
            batch.run_batch(self.root, self.emulator, self.rom, self.movie,
                            segment_frames=2, interval=1)
            self.assertEqual(len(self.calls), 3)
            with self.assertRaisesRegex(batch.BatchError, "plan or pinned"):
                batch.run_batch(self.root, self.emulator, self.rom, self.movie,
                                segment_frames=2, interval=2)
            with mock.patch.object(batch.capture_module, "runtime_digest",
                                   return_value="changed-runtime"):
                with self.assertRaisesRegex(batch.BatchError, "emulator runtime"):
                    batch.run_batch(self.root, self.emulator, self.rom, self.movie,
                                    segment_frames=2, interval=1)

    def test_rejects_tampered_complete_state_without_new_capture(self) -> None:
        self.calls = []
        with mock.patch.object(batch.capture_module, "capture", side_effect=self.fake_capture):
            batch.run_batch(self.root, self.emulator, self.rom, self.movie,
                            segment_frames=2, interval=1)
            state = self.calls[0][3] / "continuation.State"
            state.write_bytes(b"tampered")
            with self.assertRaisesRegex(batch.BatchError, "revalidation"):
                batch.run_batch(self.root, self.emulator, self.rom, self.movie,
                                segment_frames=2, interval=1)
        self.assertEqual(len(self.calls), 3)

    def test_rejects_stale_downstream_after_prior_attempt_is_rerun(self) -> None:
        self.calls = []
        with mock.patch.object(batch.capture_module, "capture", side_effect=self.fake_capture):
            batch.run_batch(self.root, self.emulator, self.rom, self.movie,
                            segment_frames=2, interval=1)
            first_result = self.calls[0][3] / "result.json"
            invalidated = json.loads(first_result.read_text())
            invalidated["complete"] = False
            first_result.write_text(json.dumps(invalidated))
            with self.assertRaisesRegex(batch.BatchError, "parent lineage"):
                batch.run_batch(self.root, self.emulator, self.rom, self.movie,
                                segment_frames=2, interval=1)
        self.assertEqual([call[:2] for call in self.calls],
                         [(0, 1), (2, 3), (4, 4), (0, 1)])
        self.assertTrue((self.calls[3][3] / "result.json").is_file())

    def test_rejects_output_inside_source_emulator(self) -> None:
        with self.assertRaisesRegex(batch.BatchError, "inside the source emulator"):
            batch.run_batch(self.emulator.parent / "batch", self.emulator,
                            self.rom, self.movie, segment_frames=2, interval=1)


if __name__ == "__main__":
    unittest.main()
