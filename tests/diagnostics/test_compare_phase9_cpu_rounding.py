import json
from pathlib import Path
import tempfile
import unittest

from scripts.compare_phase9_cpu_rounding import compare
from scripts.phase95_bridge import digest


class CpuRoundingCompareTests(unittest.TestCase):
    def test_distinct_pinned_cores_adjudicate_tie(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = []
            for core, word, config in (("Mupen64Plus", 559, "d"),
                                       ("Ares64", 558, "e")):
                folder = root / core
                folder.mkdir()
                trace = folder / "cpu-rounding.tsv"
                trace.write_text("synthetic trace", encoding="utf-8")
                path = folder / "result.json"
                path.write_text(json.dumps({
                    "kind": "jfg-phase9-cpu-rounding-microtest",
                    "acceptance": False, "complete": True, "exit_code": 0,
                    "core": core, "trace_sha256": digest(trace),
                    "rom_sha256": "a" * 64, "emulator_sha256": "b" * 64,
                    "runtime_sha256": "c" * 64, "script_sha256": "f" * 64,
                    "config_sha256": config * 64,
                    "observed": {"operand_bits": "0x440ba000",
                                 "rounding_mode": 0,
                                 "converted_integer": word},
                }), encoding="utf-8")
                paths.append(path)
            report = compare(*paths)
            self.assertEqual(report["disposition"],
                             "mupen_oracle_semantics_conflict")
            self.assertFalse(report["mupen_agrees_with_manual"])
            self.assertTrue(report["ares_agrees_with_manual"])
            tampered = json.loads(paths[1].read_text())
            tampered["rom_sha256"] = "0" * 64
            paths[1].write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "rom_sha256"):
                compare(*paths)


if __name__ == "__main__":
    unittest.main()
