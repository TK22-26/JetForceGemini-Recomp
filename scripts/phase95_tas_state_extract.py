"""Extract N64-order RDRAM from a pinned Japanese TAS continuation state.

Writes only inside an existing private capture segment. The Mupen64Plus
savestate layout is validated against that segment's live Lua RAM probes.
"""
from __future__ import annotations

import argparse
import array
import ctypes
import json
from pathlib import Path
import zipfile

from scripts.phase95_bridge import digest
from scripts.phase95_tas_capture import (
    BIZHAWK_291_EXE_SHA256, BIZHAWK_291_RUNTIME_SHA256,
    JP_ROM_SHA1, JP_ROM_SHA256, MOVIE_FRAMES, MOVIE_SHA256,
)


ZSTD_DLL_SHA256 = "fd57937ca9bbf5837af21e44d0f3017cf3f8a718205756c8e2441abc50afded4"
CORE_SIZE = 17_085_297
CORE_MAX_BYTES = 32 * 1024 * 1024
RDRAM_OFFSET = 0x1C0
RDRAM_SIZE = 0x800000
PROBES = ((0xA51B0, 1), (0xFB114, 4), (0xA33E4, 4), (0x1BD150, 4))


def decompress_core(compressed: bytes, dll: Path) -> bytes:
    if not compressed.startswith(bytes.fromhex("28b52ffd")) or \
            len(compressed) > CORE_MAX_BYTES:
        raise ValueError("Core.bin is not a bounded Zstandard frame")
    library = ctypes.CDLL(str(dll))
    library.ZSTD_decompressBound.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    library.ZSTD_decompressBound.restype = ctypes.c_ulonglong
    library.ZSTD_decompress.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                                        ctypes.c_void_p, ctypes.c_size_t]
    library.ZSTD_decompress.restype = ctypes.c_size_t
    library.ZSTD_isError.argtypes = [ctypes.c_size_t]
    library.ZSTD_isError.restype = ctypes.c_uint
    source = ctypes.create_string_buffer(compressed)
    bound = library.ZSTD_decompressBound(source, len(compressed))
    if not CORE_SIZE <= bound <= CORE_MAX_BYTES:
        raise ValueError("Zstandard output bound differs from pinned core")
    target = ctypes.create_string_buffer(CORE_SIZE)
    size = library.ZSTD_decompress(target, CORE_SIZE, source, len(compressed))
    if library.ZSTD_isError(size) or size != CORE_SIZE:
        raise ValueError("Zstandard core decompression failed or size differs")
    return target.raw[:size]


def decode_rdram(core: bytes) -> bytes:
    if len(core) != CORE_SIZE or core[:4] != bytes.fromhex("642b0001") or \
            core[4:12] != b"M64+SAVE" or \
            core[12:16] != bytes.fromhex("00010000"):
        raise ValueError("unsupported pinned Mupen64Plus core layout")
    if RDRAM_OFFSET + RDRAM_SIZE > len(core):
        raise ValueError("truncated RDRAM in core")
    words = array.array("I")
    if words.itemsize != 4:
        raise RuntimeError("host uint32 array size is not four bytes")
    words.frombytes(core[RDRAM_OFFSET:RDRAM_OFFSET + RDRAM_SIZE])
    # Mupen stores each N64 word in host byte order. On x86 Windows this is
    # little-endian; byteswap reconstructs the order BizHawk Lua reads.
    import sys
    if sys.byteorder == "little":
        words.byteswap()
    return words.tobytes()


def final_probes(path: Path, first: int, last: int) -> tuple[str, ...]:
    with path.open(encoding="utf-8") as stream:
        if stream.readline() != "schema\t1\n" or \
                stream.readline() != "probe_status\tunverified-jp\n":
            raise ValueError("capture trace schema mismatch")
        columns = stream.readline().rstrip("\n").split("\t")
        if columns != ["frame", "movie_mode", "input_polls_since_worker_start",
                       "raw_0xA51B0_u8", "raw_0xFB114_u32be",
                       "raw_0xA33E4_u32be", "raw_0x1BD150_u32be"]:
            raise ValueError("capture raw probe columns mismatch")
        current = first - 1
        final = None
        for line in stream:
            cells = line.rstrip("\n").split("\t")
            if len(cells) != len(columns) or int(cells[0]) != current + 1 or \
                    cells[1] not in ("PLAY", "FINISHED"):
                raise ValueError("capture frame sequence is invalid")
            current = int(cells[0])
            final = cells
    if current != last or final is None:
        raise ValueError("capture final frame missing")
    return tuple(final[3:])


def extract(segment: Path) -> dict:
    segment = Path(segment).resolve()
    output = segment / "state-extract"
    if output.exists():
        raise FileExistsError(output)
    result_path = segment / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if (result.get("kind") != "jfg-phase95-jp-tas-capture" or
            result.get("complete") is not True or result.get("exit_code") != 0 or
            result.get("semantic_status") != "raw-unverified-jp"):
        raise ValueError("source segment is not a complete raw JP TAS capture")
    pins = {"rom_sha1": JP_ROM_SHA1, "rom_sha256": JP_ROM_SHA256,
            "movie_sha256": MOVIE_SHA256, "movie_frames": MOVIE_FRAMES,
            "emulator_sha256": BIZHAWK_291_EXE_SHA256,
            "runtime_sha256": BIZHAWK_291_RUNTIME_SHA256}
    for key, expected in pins.items():
        if result.get(key) != expected:
            raise ValueError(f"source capture identity mismatch: {key}")
    first, frame = result.get("first"), result.get("last")
    if type(first) is not int or type(frame) is not int or \
            not 0 <= first <= frame < MOVIE_FRAMES or \
            result.get("captured_frames") != frame - first + 1:
        raise ValueError("source capture frame bounds mismatch")
    state_path = segment / "continuation.State"
    state_sha256 = digest(state_path)
    if state_sha256 != result.get("continuation_sha256"):
        raise ValueError("source continuation state hash mismatch")
    dll = segment / "emulator" / "dll" / "libzstd.dll"
    dll_sha256 = digest(dll)
    if dll_sha256 != ZSTD_DLL_SHA256:
        raise ValueError("Zstandard library differs from pinned BizHawk runtime")
    with zipfile.ZipFile(state_path) as archive:
        members = archive.infolist()
        core_members = [member for member in members if member.filename == "Core.bin"]
        if len(core_members) != 1 or core_members[0].file_size > CORE_MAX_BYTES or \
                core_members[0].compress_size > CORE_MAX_BYTES:
            raise ValueError("missing or oversized Core.bin")
        compressed = archive.read(core_members[0])
    core = decompress_core(compressed, dll)
    rdram = decode_rdram(core)
    observed = final_probes(segment / "frames.tsv", first, frame)
    for index, (address, width) in enumerate(PROBES):
        if rdram[address:address + width].hex().upper() != observed[index]:
            raise ValueError(f"savestate RDRAM differs from live Lua probe {index}")
    output.mkdir()
    destination = output / f"frame-{frame:06d}.rdram"
    destination.write_bytes(rdram)
    manifest = {"kind": "jfg-phase95-jp-tas-state-extract", "schema": 1,
                "semantic_status": "raw-unverified-jp", "frame": frame,
                "source_segment": str(segment),
                "source_result_sha256": digest(result_path),
                "source_state_sha256": state_sha256,
                "zstd_dll_sha256": dll_sha256,
                "core_layout": "bizhawk-2.9.1-m64plus-v1.0",
                "rdram_offset": RDRAM_OFFSET,
                "rdram_bytes": RDRAM_SIZE,
                "host_word_conversion": "byteswap-each-u32",
                "probe_addresses": [address for address, _ in PROBES],
                "probe_values": observed,
                "rdram_sha256": digest(destination)}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("segment", type=Path)
    args = parser.parse_args()
    print(json.dumps(extract(args.segment)))


if __name__ == "__main__":
    main()
