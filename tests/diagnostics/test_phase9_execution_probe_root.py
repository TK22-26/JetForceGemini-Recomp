import unittest
import tomllib
import json
import tempfile
from pathlib import Path
from scripts.phase9_execution_probe_root import hook_rows, compare_bodies


class ExecutionProbeRootTests(unittest.TestCase):
    def symbols(self):
        return {"section": [{"rom": 4, "vram": 0x80000400, "functions": [
            {"name": "fixture", "vram": 0x80000400, "size": 8}]}]}

    def test_hooks_preserve_pc_words_and_delay_slot_sites(self):
        # jr ra plus its nop slot: both sites are independently generated.
        rows = list(hook_rows(self.symbols(), bytes.fromhex("0000000003e0000800000000")))
        hooks = tomllib.loads("[patches]\n" + "".join(rows))["patches"]["hook"]
        self.assertEqual([row["before_vram"] for row in hooks], [0x80000400, 0x80000404])
        self.assertIn("0x03e00008U", hooks[0]["text"])
        self.assertNotIn("extern", hooks[0]["text"])

    def test_bad_extents_and_duplicates_fail(self):
        for field, value in (("size", 0), ("size", 7), ("size", 16), ("vram", 0x80000401)):
            symbols = self.symbols()
            symbols["section"][0]["functions"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                list(hook_rows(symbols, bytes(12)))
        symbols = self.symbols()
        symbols["section"][0]["functions"] *= 2
        with self.assertRaises(ValueError):
            list(hook_rows(symbols, bytes(12)))

    def test_comparison_allows_only_hooks_and_indentation(self):
        with tempfile.TemporaryDirectory() as directory:
            control, observed = Path(directory) / "control", Path(directory) / "observed"
            control.mkdir()
            observed.mkdir()
            (control / "sources.json").write_text(json.dumps({
                "baseline_body_sources": ["body.c"], "alternate_entry_thunk_sources": []}))
            (control / "body.c").write_text("  value = 1;\n    // slot\n")
            hook = "jfg_phase9_execution_probe(0U, 0x80000000U, 0x00000000U, ctx);\n"
            (observed / "body.c").write_text("  value = 1;\n    " + hook + " // slot\n")
            self.assertTrue(compare_bodies(control, observed)["instruction_hooks_only"])
            (observed / "body.c").write_text("  value = 2;\n    " + hook + " // slot\n")
            self.assertFalse(compare_bodies(control, observed)["instruction_hooks_only"])
