"""Tests for the Phase 6 static boot-reachability analysis (ROM-free).

The fixture is generated in a temporary directory at runtime rather than
tracked, so no generated-recompilation-looking source lives in the repo (the
analyzer only needs the `LOOKUP_FUNC(0x<vram>)` call sites and the
`*_recomp.c` naming, not the RECOMP_FUNC bodies real generation emits).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.analyze_boot_reachability import analyze

SYMBOLS = """[[section]]
name = "section_000"
funcs = [
    { name = "fn_000_1000", vram = 0x80000450, size = 0x00000040 },
    { name = "fn_000_1001", vram = 0x80000490, size = 0x00000040 },
    { name = "fn_000_1002", vram = 0x800004D0, size = 0x00000040 },
    { name = "fn_000_1003", vram = 0x80000510, size = 0x00000040 },
]
"""

# Minimal bodies: only the call sites matter to the analyzer.
BODIES = {
    "fn_000_1000_recomp.c": (
        "void body(unsigned char* rdram, void* ctx) {\n"
        "    LOOKUP_FUNC(0x80000490)(rdram, ctx);\n"
        "    LOOKUP_FUNC(0x800004D0)(rdram, ctx);\n"
        "}\n"
    ),
    "fn_000_1001_recomp.c": (
        "void body(unsigned char* rdram, void* ctx) {\n"
        "    LOOKUP_FUNC(0x80000510)(rdram, ctx);\n"
        "}\n"
    ),
    "fn_000_1002_recomp.c": (
        "void body(unsigned char* rdram, void* ctx) {\n"
        "    LOOKUP_FUNC(0x80999999)(rdram, ctx); /* unresolved external */\n"
        "}\n"
    ),
    "fn_000_1003_recomp.c": "void body(void) { /* leaf */ }\n",
}


class BootReachabilityAnalysis(unittest.TestCase):
    def _build_fixture(self, root: Path) -> tuple[Path, Path]:
        gen = root / "gen"
        gen.mkdir(parents=True, exist_ok=True)
        symbols = root / "symbols.toml"
        symbols.write_text(SYMBOLS, encoding="utf-8")
        for name, body in BODIES.items():
            (gen / name).write_text(body, encoding="utf-8")
        return gen, symbols

    def test_direct_call_reachability_from_entry(self) -> None:
        with tempfile.TemporaryDirectory(prefix="boot-reach-") as temp:
            gen, symbols = self._build_fixture(Path(temp))
            result = analyze(gen, symbols, 0x80000400)
        detail = result["detail"]
        self.assertEqual(detail["root_function"], "fn_000_1000")
        self.assertEqual(detail["root_vram"], "0x80000450")
        self.assertEqual(
            detail["reachable_functions"],
            ["fn_000_1000", "fn_000_1001", "fn_000_1002", "fn_000_1003"],
        )
        self.assertEqual(detail["unresolved_direct_targets"], ["0x80999999"])
        self.assertEqual(result["total_functions"], 4)
        self.assertEqual(result["reachable_direct"], 4)
        self.assertEqual(result["direct_call_edges"], 4)
        self.assertEqual(result["unresolved_direct_targets"], 1)

    def test_unreachable_function_is_excluded(self) -> None:
        with tempfile.TemporaryDirectory(prefix="boot-reach-") as temp:
            gen, symbols = self._build_fixture(Path(temp))
            result = analyze(gen, symbols, 0x80000510)
        self.assertEqual(
            result["detail"]["reachable_functions"], ["fn_000_1003"]
        )
        self.assertEqual(result["reachable_direct"], 1)


if __name__ == "__main__":
    unittest.main()
