import json
import tempfile
import unittest
from pathlib import Path
from scripts.compare_phase9_update_hashes import compare, records


class UpdateComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def trace(self, name, indices, seed="0x00000000"):
        path = self.root / name
        header = {"kind": "jfg-phase9-update-hash-header", "schema": 1}
        records = [{"kind": "jfg-phase9-update-hash", "schema": 1, "update": index,
                    "front_mode": 0, "actor_count": 0, "actors": [], "rng_seed": seed,
                    "actor_list": "0x00000000", "player_actor": "0x00000000",
                    "player_sha256": None, "actor_table_sha256": None,
                    "globals_sha256": "0" * 64, "camera_sha256": "1" * 64}
                   for index in indices]
        path.write_text("\n".join(json.dumps(r) for r in [header, *records]) + "\n")
        return path

    def test_exact_stream_and_explicit_prefix(self):
        a, b = self.trace("a", [1, 2]), self.trace("b", [1, 2, 3])
        self.assertFalse(compare(a, b)["match"])
        self.assertTrue(compare(a, b, 2)["match"])
        self.assertEqual(compare(a, b, 2)["scope"], "prefix")
        self.assertTrue(compare(a, a)["match"])
        self.assertFalse(compare(a, a, 3)["match"])

    def test_first_state_difference(self):
        a, b = self.trace("a", [1]), self.trace("b", [1], "0x00000001")
        report = compare(a, b)
        self.assertEqual(report["first_divergence"]["update"], 1)
        self.assertEqual(report["first_divergence"]["components"], ["rng_seed"])

    def test_malformed_identical_streams_rejected(self):
        for indices in ([], [2], [1, 3], [1, 1], [True]):
            with self.subTest(indices=indices):
                a = self.trace("a", indices)
                with self.assertRaises(ValueError):
                    compare(a, a)

    def test_vi_header_rejected(self):
        a = self.trace("a", [1])
        a.write_text(a.read_text().replace("update-hash", "retrace-hash"))
        with self.assertRaises(ValueError):
            compare(a, a)

    def test_poll_clock_metadata_is_validated_but_not_semantic_state(self):
        a, b = self.trace("a", [1]), self.trace("b", [1])
        left = a.read_text(encoding="utf-8").splitlines()
        right = b.read_text(encoding="utf-8").splitlines()
        native = json.loads(left[1])
        oracle = json.loads(right[1])
        native.update(controller_polls=3, vi_retraces=10)
        oracle.update(controller_polls=4, emulator_frame=13,
                      oracle_consumed_vi=11)
        a.write_text(left[0] + "\n" + json.dumps(native) + "\n", encoding="utf-8")
        b.write_text(right[0] + "\n" + json.dumps(oracle) + "\n", encoding="utf-8")
        self.assertTrue(compare(a, b)["match"])
        oracle["controller_polls"] = -1
        b.write_text(right[0] + "\n" + json.dumps(oracle) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "invalid controller_polls"):
            list(records(b))
        oracle["controller_polls"] = 4
        oracle["oracle_consumed_vi"] = -1
        b.write_text(right[0] + "\n" + json.dumps(oracle) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "invalid oracle_consumed_vi"):
            list(records(b))


if __name__ == "__main__":
    unittest.main()
