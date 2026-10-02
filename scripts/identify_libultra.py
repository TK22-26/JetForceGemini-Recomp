"""Identify libultra functions in the generated set (Phase 6, native-boot path 1).

Maintainer-approved facts-only use of the Jet Force Gemini decomp: this reads
the decomp's US symbol map purely as *facts* (libultra function name -> vram)
and cross-references those addresses against our own generated symbols.toml to
learn which generated `fn_` bodies are libultra functions. It copies no decomp
source, headers, or implementation — only the address facts, which it does not
even persist to a tracked file (the detailed mapping is ROM-derived and stays
private). The HLE implementations of these functions are authored independently
per docs/planning/phase6-acceptance.md; this tool only says *which addresses*
to intercept. Attribution for the consultation is recorded in
THIRD_PARTY_NOTICES.md.

libultra API names are the public N64 SDK contract, not decomp expression.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

# Boot-critical libultra surface: the thread/scheduler, message queues and
# events, timers, PI DMA, VI, RSP task, and SI controller entry points a boot
# reaches. These are public SDK API names.
BOOT_CRITICAL = frozenset({
    "osCreateThread", "osStartThread", "osStopThread", "osDestroyThread",
    "osYieldThread", "osSetThreadPri", "osGetThreadPri", "__osDispatchThread",
    "__osEnqueueThread", "__osDequeueThread", "__osPopThread",
    "osCreateMesgQueue", "osSendMesg", "osJamMesg", "osRecvMesg",
    "osSetEventMesg", "osGetTime", "osSetTime", "osSetTimer", "osStopTimer",
    "osCreatePiManager", "osPiStartDma", "osEPiStartDma", "osPiGetCmdQueue",
    "osViSetMode", "osViSwapBuffer", "osViSetEvent", "osViBlack",
    "osViSetSpecialFeatures", "osViGetCurrentFramebuffer", "osViGetNextFramebuffer",
    "osSpTaskLoad", "osSpTaskStartGo", "osSpTaskYield", "osSpTaskYielded",
    "osContInit", "osContStartReadData", "osContGetReadData", "osContStartQuery",
    "osContGetQuery", "osEepromProbe", "osEepromLongRead", "osEepromLongWrite",
    "osInitialize", "osGetCount", "osVirtualToPhysical", "osPhysicalToVirtual",
    "osInvalDCache", "osWritebackDCache", "osWritebackDCacheAll", "osInvalICache",
    "osSetIntMask", "osGetIntMask", "__osSetSR", "__osGetSR",
    # The live boot also reaches cartridge authentication, FlashRAM, and raw SI.
    # Their device operations must use the host implementations.
    "__osSiRawStartDma", "bzero", "osCic6105SendData", "osCic6105StartGetData",
    "osFlashAllErase", "osFlashClearStatus", "osFlashInit", "osFlashReInit",
    "osFlashReadArray", "osFlashReadId", "osFlashReadStatus", "osFlashSectorErase",
    "osFlashWriteArray", "osFlashWriteBuffer",
})

_DECOMP_SYMBOL_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<vram>0x[0-9A-Fa-f]+)"
)
_GENERATED_SYMBOL_RE = re.compile(
    r'name\s*=\s*"(?P<name>fn_[0-9a-fA-F_]+)"\s*,\s*vram\s*=\s*(?P<vram>0x[0-9A-Fa-f]+)'
)


def _parse_decomp_symbols(path: Path) -> dict[str, int]:
    names: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = _DECOMP_SYMBOL_RE.match(line)
        if match:
            names[match.group("name")] = int(match.group("vram"), 16)
    return names


def _parse_generated_symbols(path: Path) -> dict[int, str]:
    vram_to_fn: dict[int, str] = {}
    text = path.read_text(encoding="utf-8")
    for match in _GENERATED_SYMBOL_RE.finditer(text):
        vram_to_fn[int(match.group("vram"), 16)] = match.group("name")
    return vram_to_fn


def identify(
    decomp_symbols: dict[str, int], generated: dict[int, str]
) -> dict[str, object]:
    identified: list[dict[str, object]] = []
    for name in sorted(BOOT_CRITICAL):
        vram = decomp_symbols.get(name)
        if vram is None:
            continue
        generated_fn = generated.get(vram)
        identified.append({
            "libultra": name,
            "vram": f"0x{vram:08x}",
            "generated_function": generated_fn,
            "in_generated_set": generated_fn is not None,
        })
    mapped = [entry for entry in identified if entry["in_generated_set"]]
    entry_vram = decomp_symbols.get("entrypoint")
    detail = {
        "schema_version": 1,
        "kind": "jfg-phase6-libultra-identification-detail",
        "source": "jfg-decomp-us-symbol-map (facts-only, no source copied)",
        "entrypoint_vram": None if entry_vram is None else f"0x{entry_vram:08x}",
        "identified": identified,
    }
    return {
        "detail": detail,
        "boot_critical_names": len(BOOT_CRITICAL),
        "present_in_decomp": len(identified),
        "mapped_to_generated": len(mapped),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decomp-symbols", required=True, type=Path)
    parser.add_argument("--generated-symbols", required=True, type=Path)
    parser.add_argument("--private-out", required=True, type=Path)
    parser.add_argument("--public-out", type=Path, default=None)
    arguments = parser.parse_args()

    decomp_symbols = _parse_decomp_symbols(arguments.decomp_symbols)
    if not decomp_symbols:
        print("no decomp symbols parsed", file=sys.stderr)
        return 1
    generated = _parse_generated_symbols(arguments.generated_symbols)
    result = identify(decomp_symbols, generated)

    detail_bytes = (
        json.dumps(result["detail"], indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    arguments.private_out.parent.mkdir(parents=True, exist_ok=True)
    arguments.private_out.write_bytes(detail_bytes)

    summary = {
        "schema_version": 1,
        "kind": "jfg-phase6-libultra-identification-summary",
        "source": "jfg-decomp-us-symbol-map (facts-only)",
        "boot_critical_names": result["boot_critical_names"],
        "present_in_decomp": result["present_in_decomp"],
        "mapped_to_generated_functions": result["mapped_to_generated"],
        "entrypoint_vram": result["detail"]["entrypoint_vram"],
        "private_detail_sha256": hashlib.sha256(detail_bytes).hexdigest(),
        "note": (
            "Facts-only identification (libultra name -> vram -> generated fn). "
            "No decomp source copied; HLE implementations authored independently."
        ),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if arguments.public_out is not None:
        arguments.public_out.parent.mkdir(parents=True, exist_ok=True)
        arguments.public_out.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
