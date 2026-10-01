import json
from pathlib import Path
import tempfile
import unittest

from scripts.phase9_instruction_probe_root import BODY, PCS, create, digest


class InstructionProbeRootTests(unittest.TestCase):
    def test_private_copy_instruments_exact_guest_pcs_without_mutating_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source"
            body = source / BODY
            body.parent.mkdir(parents=True)
            original = '#include "funcs.h"\n' + "".join(
                f"    // 0x{pc:08X}: synthetic\n    ctx->r0 = 0;\n" for pc in PCS
            )
            body.write_text(original, encoding="utf-8")
            (source / "sources.json").write_text("{}", encoding="utf-8")
            result = create(source, base / "copy")
            text = (base / "copy" / BODY).read_text(encoding="utf-8")
            self.assertEqual(body.read_text(encoding="utf-8"), original)
            self.assertEqual(text.count("jfg_phase9_instruction_probe("),
                             len(PCS) + 1)
            for pc in PCS:
                self.assertIn(
                    f"jfg_phase9_instruction_probe(0x{pc:08X}U, rdram, ctx);\n"
                    f"    // 0x{pc:08X}:", text,
                )
            self.assertEqual(result["source_body_sha256"], digest(body))
            self.assertEqual(result["instrumented_body_sha256"],
                             digest(base / "copy" / BODY))
            self.assertFalse(json.loads((base / "copy" /
                                         "instruction-probe-manifest.json").read_text())[
                "acceptance"])

    def test_ambiguous_or_missing_marker_rejected_before_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source"
            body = source / BODY
            body.parent.mkdir(parents=True)
            body.write_text('#include "funcs.h"\n    // 0x80074440: only one\n',
                            encoding="utf-8")
            (source / "sources.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "absent or ambiguous"):
                create(source, base / "copy")
            self.assertFalse((base / "copy").exists())


if __name__ == "__main__":
    unittest.main()
