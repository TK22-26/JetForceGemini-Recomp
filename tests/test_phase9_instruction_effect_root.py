import json
from pathlib import Path
import tempfile
import tomllib
import unittest

from scripts import phase9_instruction_effect_root as root


class EffectRootTests(unittest.TestCase):
    def symbols(self, words):
        return {"section": [{"rom": 4, "vram": 0x80000400, "functions": [
            {"name": "fixture", "vram": 0x80000400, "size": len(words) * 4}]}]}

    def test_pairs_and_dedicated_or_rejected_callbacks(self):
        words = [0x03e00008, 0, 0x42000018, 0x0000000c, 0x0000000d, 0x48000000]
        rom = bytes(4) + b"".join(w.to_bytes(4, "big") for w in words)
        sites = list(root.sites(self.symbols(words), rom))
        self.assertEqual([s["qualification"] for s in sites], [0, 0, 1, 2, 2, 2])
        rows = tomllib.loads("[patches]\n" + "".join(map(root.hooks, sites)))["patches"]["hook"]
        self.assertEqual(len(rows), 8)
        before = [s for s in rows if "before_vram" in s]
        after = [s for s in rows if "after_vram" in s]
        self.assertEqual([r["before_vram"] for r in before], list(range(0x80000400, 0x80000418, 4)))
        self.assertEqual([r["after_vram"] for r in after], [0x80000400, 0x80000404])
        for row in before:
            self.assertLess(row["text"].index("execution_probe"), row["text"].index("effect_entry"))

    def test_excluded_opcode_families(self):
        for primary in (18, 50, 54, 58, 62):
            self.assertEqual(root.qualification(primary << 26), 2)
        for word in (0x1000ffff, 0x40806000, 0x42000002, 0x0000000f, 0x46000000):
            self.assertEqual(root.qualification(word), 0)
        for word in (-1, 0x100000000, True):
            with self.assertRaises(ValueError):
                root.qualification(word)

    def test_invalid_extent_or_duplicate(self):
        for key, value in (("size", 0), ("size", 7), ("size", 16), ("vram", 0x80000401), ("size", True)):
            symbols = self.symbols([0, 0])
            symbols["section"][0]["functions"][0][key] = value
            with self.assertRaises(ValueError):
                list(root.sites(symbols, bytes(12)))
        symbols = self.symbols([0, 0])
        symbols["section"][0]["functions"] *= 2
        with self.assertRaises(ValueError):
            list(root.sites(symbols, bytes(12)))

    def test_comparison_preserves_execution_hooks_and_all_body_statements(self):
        with tempfile.TemporaryDirectory() as temporary:
            control, observed = [Path(temporary) / name for name in ("control", "observed")]
            manifest = {"baseline_body_sources": ["body.c"], "alternate_entry_thunk_sources": []}
            for base in (control, observed):
                base.mkdir()
                (base / "sources.json").write_text(json.dumps(manifest))
            execution = "    jfg_phase9_execution_probe(0U, 0x80000400U, 0x00000000U, ctx);\n"
            entry = "    jfg_phase9_instruction_effect_entry(0U, 0x80000400U, 0x00000000U, 0U, ctx);\n"
            effect = "    jfg_phase9_instruction_effect(0U, 0x80000400U, 0x00000000U, ctx);\n"
            (control / "body.c").write_text(execution + "    value = 1;\n")
            (observed / "body.c").write_text(execution + entry + " value = 1;\n" + effect)
            self.assertTrue(root.compare_bodies(control, observed)["instruction_effect_hooks_only"])
            for content in (entry + " value = 1;\n" + effect,
                            execution + entry + " value = 2;\n" + effect):
                (observed / "body.c").write_text(content)
                self.assertFalse(root.compare_bodies(control, observed)["instruction_effect_hooks_only"])
            (observed / "sources.json").write_text(json.dumps({**manifest, "alternate_entry_thunk_sources": ["new.c"]}))
            with self.assertRaises(ValueError):
                root.compare_bodies(control, observed)


if __name__ == "__main__":
    unittest.main()
