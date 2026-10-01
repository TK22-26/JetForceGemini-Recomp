import json
import tempfile
import unittest
from pathlib import Path

from scripts.compare_phase9_retrace_hashes import compare, load_trace


class RetraceValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "trace.jsonl"
        self.record = {
            "kind": "jfg-phase9-retrace-hash", "schema": 1, "retrace": 1,
            "front_mode": 0, "actor_count": 0, "rng_seed": "0x00000000",
            "player_actor": "0x00000000", "actor_list": "0x00000000",
            "player_sha256": None, "actor_table_sha256": None,
            "globals_sha256": "0" * 64, "camera_sha256": "1" * 64,
            "actors": [],
        }

    def write(self, record):
        header = {"kind": "jfg-phase9-retrace-hash-header", "schema": 1}
        self.path.write_text(json.dumps(header) + "\n" + json.dumps(record) + "\n")

    def test_valid_identical_streams(self):
        self.write(self.record)
        self.assertTrue(compare(self.path, self.path, 0)[1])

    def test_streaming_comparison_preserves_first_difference_and_tail_gaps(self):
        native = self.path.with_name("native.jsonl")
        oracle = self.path.with_name("oracle.jsonl")
        header = {"kind": "jfg-phase9-retrace-hash-header", "schema": 1}
        native.write_text("\n".join(json.dumps(item) for item in (
            header, self.record, dict(self.record, retrace=2),
            dict(self.record, retrace=3))) + "\n", encoding="utf-8")
        oracle.write_text("\n".join(json.dumps(item) for item in (
            header, dict(self.record, rng_seed="0x00000001"),
            dict(self.record, retrace=2))) + "\n", encoding="utf-8")
        report, match = compare(native, oracle, 0)
        self.assertFalse(match)
        self.assertEqual(report["first_divergence"]["retrace"], 1)
        self.assertEqual(report["first_divergence"]["components"], ["rng_seed"])
        self.assertEqual(report["compared_retraces"], 1)
        self.assertEqual(report["native_only_first"], 3)
        self.assertIsNone(report["oracle_only_first"])

    def test_streaming_offset_and_nonoverlap(self):
        self.write(self.record)
        report, match = compare(self.path, self.path, 0)
        self.assertTrue(match)
        self.assertEqual(len(report["final_sha256"]), 64)
        with self.assertRaisesRegex(ValueError, "no common retraces"):
            compare(self.path, self.path, 10)

    def test_identical_missing_fields_cannot_pass(self):
        for field in self.record.keys() - {"kind", "schema", "retrace"}:
            with self.subTest(field=field):
                self.write({k: v for k, v in self.record.items() if k != field})
                with self.assertRaises(ValueError):
                    compare(self.path, self.path, 0)

    def test_invalid_records(self):
        for field, value in (("retrace", True), ("front_mode", False),
                             ("actor_count", -1), ("rng_seed", "garbage"),
                             ("globals_sha256", "truncated"), ("actors", None)):
            with self.subTest(field=field):
                self.write(dict(self.record, **{field: value}))
                with self.assertRaises(ValueError):
                    load_trace(self.path)

    def test_non_object_record(self):
        self.write([])
        with self.assertRaises(ValueError):
            load_trace(self.path)

    def test_identical_gaps_or_reordered_frames_cannot_pass(self):
        for next_frame in (1, 0, 3):
            with self.subTest(next_frame=next_frame):
                self.write(self.record)
                with self.path.open("a") as stream:
                    stream.write(json.dumps(dict(self.record, retrace=next_frame)) + "\n")
                with self.assertRaises(ValueError):
                    compare(self.path, self.path, 0)

    def test_actor_state_is_required(self):
        for actor in ({"index": 0}, {"index": True, "address": "0x00000000", "sha256": None},
                      {"index": 0, "address": "0x00000000"},
                      {"index": 0, "address": "0x00000000", "sha256": "short"}):
            with self.subTest(actor=actor):
                self.write(dict(self.record, actors=[actor]))
                with self.assertRaises(ValueError):
                    compare(self.path, self.path, 0)


if __name__ == "__main__":
    unittest.main()
