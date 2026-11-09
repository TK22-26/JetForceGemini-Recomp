import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts import phase95_tas_state_batch as batch
from scripts import phase95_tas_state_extract as state_extract


class TasStateBatchTests(unittest.TestCase):
    def _root(self, path):
        root = path / "batch"
        root.mkdir()
        pins = {"rom_sha1": batch.capture.JP_ROM_SHA1,
                "rom_sha256": batch.capture.JP_ROM_SHA256,
                "movie_sha256": batch.capture.MOVIE_SHA256,
                "movie_frames": 4,
                "emulator_sha256": batch.capture.BIZHAWK_291_EXE_SHA256,
                "runtime_sha256": batch.capture.BIZHAWK_291_RUNTIME_SHA256,
                "script_sha256": "synthetic-script"}
        (root / "batch.json").write_text(json.dumps({
            "kind": batch.PLAN_KIND, "schema": 1,
            "semantic_status": "raw-unverified-jp", "segment_frames": 2,
            "pins": pins}))
        return root, pins

    def _attempt(self, root, pins, first, last, previous=None):
        segment = root / "segments" / f"segment-{first:06d}-{last:06d}"
        attempt = segment / "attempt-0000"
        attempt.mkdir(parents=True)
        state = attempt / "continuation.State"
        state.write_bytes(f"synthetic state {last}".encode())
        parent_hash = (batch.read_json(previous / "result.json")
                       ["continuation_sha256"] if previous else None)
        result = {**pins, "kind": "jfg-phase95-jp-tas-capture",
                  "semantic_status": "raw-unverified-jp", "complete": True,
                  "exit_code": 0, "first": first, "last": last,
                  "captured_frames": last - first + 1,
                  "resume_from": str(previous) if previous else None,
                  "parent_continuation_sha256": parent_hash,
                  "continuation_sha256": batch.capture.digest(state)}
        (attempt / "result.json").write_text(json.dumps(result))
        (attempt / "frames.tsv").write_text(
            "schema\t1\nprobe_status\tunverified-jp\n"
            "frame\tmovie_mode\tinput_polls_since_worker_start\t"
            "raw_0xA51B0_u8\traw_0xFB114_u32be\t"
            "raw_0xA33E4_u32be\traw_0x1BD150_u32be\n" +
            "".join(f"{frame}\tPLAY\t0\t00\t00000000\t00000000\t00000000\n"
                    for frame in range(first, last + 1)))
        return attempt

    @staticmethod
    def _fake_extract(attempt):
        result_path = attempt / "result.json"
        result = batch.read_json(result_path)
        frame = result["last"]
        output = attempt / "state-extract"
        output.mkdir()
        rdram_path = output / f"frame-{frame:06d}.rdram"
        rdram_path.write_bytes(bytes(state_extract.RDRAM_SIZE))
        manifest = {"kind": "jfg-phase95-jp-tas-state-extract",
                    "schema": 1, "semantic_status": "raw-unverified-jp",
                    "frame": frame, "source_segment": str(attempt),
                    "source_result_sha256": batch.capture.digest(result_path),
                    "source_state_sha256": result["continuation_sha256"],
                    "core_layout": "bizhawk-2.9.1-m64plus-v1.0",
                    "rdram_offset": state_extract.RDRAM_OFFSET,
                    "rdram_bytes": state_extract.RDRAM_SIZE,
                    "host_word_conversion": "byteswap-each-u32",
                    "zstd_dll_sha256": state_extract.ZSTD_DLL_SHA256,
                    "probe_values": ["00", "00000000", "00000000", "00000000"],
                    "probe_addresses": [p[0] for p in state_extract.PROBES],
                    "rdram_sha256": batch.capture.digest(rdram_path)}
        (output / "manifest.json").write_text(json.dumps(manifest))
        return manifest

    def test_partial_then_complete_idempotent_index(self):
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(batch, "MOVIE_FRAMES", 4), \
                mock.patch.object(state_extract, "extract",
                                  side_effect=self._fake_extract) as extraction:
            root, pins = self._root(Path(directory))
            first = self._attempt(root, pins, 0, 1)
            partial = batch.index_batch(root)
            self.assertFalse(partial["complete"])
            self.assertEqual(partial["segments_extracted"], 1)
            self.assertEqual(partial["entries"][0]["frame"], 1)
            self.assertEqual(extraction.call_count, 1)
            (root / "segments" / "segment-000002-000003" / "attempt-0000").mkdir(
                parents=True)
            still_partial = batch.index_batch(root)
            self.assertFalse(still_partial["complete"])
            self.assertEqual(extraction.call_count, 1)
            second_dir = root / "segments" / "segment-000002-000003"
            (second_dir / "attempt-0000").rmdir()
            self._attempt(root, pins, 2, 3, first)
            (root / "batch-result.json").write_text(json.dumps({
                "kind": batch.PLAN_KIND, "schema": 1, "complete": True,
                "segments_total": 2, "segments_complete": 2,
                "last_complete_frame": 3}))
            complete = batch.index_batch(root)
            self.assertTrue(complete["complete"])
            self.assertEqual(complete["segments_extracted"], 2)
            self.assertEqual(extraction.call_count, 2)
            again = batch.index_batch(root)
            self.assertTrue(again["complete"])
            self.assertEqual(extraction.call_count, 2)
            self.assertEqual(batch.read_json(root / batch.INDEX_NAME), again)

    def test_existing_extract_corruption_is_preserved_and_reported(self):
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(batch, "MOVIE_FRAMES", 4), \
                mock.patch.object(state_extract, "extract",
                                  side_effect=self._fake_extract) as extraction:
            root, pins = self._root(Path(directory))
            first = self._attempt(root, pins, 0, 1)
            batch.index_batch(root)
            rdram = first / "state-extract" / "frame-000001.rdram"
            with rdram.open("r+b") as stream:
                stream.write(b"X")
            corrupt_hash = batch.capture.digest(rdram)
            report = batch.index_batch(root)
            self.assertFalse(report["complete"])
            self.assertEqual(report["segments_extracted"], 0)
            self.assertEqual(len(report["errors"]), 1)
            self.assertEqual(batch.capture.digest(rdram), corrupt_hash)
            self.assertEqual(extraction.call_count, 1)

    def test_bad_plan_fails_before_index_write(self):
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(batch, "MOVIE_FRAMES", 4):
            root, pins = self._root(Path(directory))
            pins["movie_sha256"] = "wrong"
            plan = batch.read_json(root / "batch.json")
            plan["pins"] = pins
            (root / "batch.json").write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, "source pins"):
                batch.index_batch(root)
            self.assertFalse((root / batch.INDEX_NAME).exists())


if __name__ == "__main__":
    unittest.main()
