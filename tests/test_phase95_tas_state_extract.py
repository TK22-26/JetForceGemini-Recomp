import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

from scripts import phase95_tas_state_extract as state_extract


def synthetic_core():
    core = bytearray(state_extract.CORE_SIZE)
    core[:4] = bytes.fromhex("642b0001")
    core[4:12] = b"M64+SAVE"
    core[12:16] = bytes.fromhex("00010000")
    base = state_extract.RDRAM_OFFSET
    core[base + (0xA51B0 ^ 3)] = 3
    for address, value in ((0xFB114, 0x12345678),
                           (0xA33E4, 0x46509146),
                           (0x1BD150, 0x80123450)):
        core[base + address:base + address + 4] = value.to_bytes(4, "big")[::-1]
    return bytes(core)


class TasStateExtractTests(unittest.TestCase):
    def test_decode_word_order_and_header_checks(self):
        core = synthetic_core()
        rdram = state_extract.decode_rdram(core)
        self.assertEqual(len(rdram), state_extract.RDRAM_SIZE)
        self.assertEqual(rdram[0xA51B0], 3)
        self.assertEqual(rdram[0xFB114:0xFB118], bytes.fromhex("12345678"))
        self.assertEqual(rdram[0x1BD150:0x1BD154], bytes.fromhex("80123450"))
        with self.assertRaisesRegex(ValueError, "unsupported"):
            state_extract.decode_rdram(b"wrong" + core[5:])
        with self.assertRaisesRegex(ValueError, "unsupported"):
            state_extract.decode_rdram(core[:-1])

    def test_trace_requires_contiguous_final_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / "frames.tsv"
            trace.write_text("schema\t1\nprobe_status\tunverified-jp\n"
                "frame\tmovie_mode\tinput_polls_since_worker_start\t"
                "raw_0xA51B0_u8\traw_0xFB114_u32be\t"
                "raw_0xA33E4_u32be\traw_0x1BD150_u32be\n"
                "5\tPLAY\t1\t00\t00000000\t00000000\t00000000\n"
                "6\tPLAY\t2\t03\t12345678\t46509146\t80123450\n")
            self.assertEqual(state_extract.final_probes(trace, 5, 6),
                             ("03", "12345678", "46509146", "80123450"))
            with self.assertRaisesRegex(ValueError, "final frame"):
                state_extract.final_probes(trace, 5, 7)
            trace.write_text(trace.read_text().replace("6\tPLAY", "7\tPLAY"))
            with self.assertRaisesRegex(ValueError, "sequence"):
                state_extract.final_probes(trace, 5, 6)

    def _fixture(self, root):
        segment = root / "segment"
        (segment / "emulator" / "dll").mkdir(parents=True)
        dll = segment / "emulator" / "dll" / "libzstd.dll"
        dll.write_bytes(b"synthetic dll")
        state = segment / "continuation.State"
        with zipfile.ZipFile(state, "w") as archive:
            archive.writestr("Core.bin", b"synthetic compressed bytes")
        result = {"kind": "jfg-phase95-jp-tas-capture", "complete": True,
                  "exit_code": 0, "semantic_status": "raw-unverified-jp",
                  "first": 6, "last": 6, "captured_frames": 1,
                  "rom_sha1": state_extract.JP_ROM_SHA1,
                  "rom_sha256": state_extract.JP_ROM_SHA256,
                  "movie_sha256": state_extract.MOVIE_SHA256,
                  "movie_frames": state_extract.MOVIE_FRAMES,
                  "emulator_sha256": state_extract.BIZHAWK_291_EXE_SHA256,
                  "runtime_sha256": state_extract.BIZHAWK_291_RUNTIME_SHA256,
                  "continuation_sha256": state_extract.digest(state)}
        (segment / "result.json").write_text(json.dumps(result))
        (segment / "frames.tsv").write_text(
            "schema\t1\nprobe_status\tunverified-jp\n"
            "frame\tmovie_mode\tinput_polls_since_worker_start\t"
            "raw_0xA51B0_u8\traw_0xFB114_u32be\t"
            "raw_0xA33E4_u32be\traw_0x1BD150_u32be\n"
            "6\tPLAY\t2\t03\t12345678\t46509146\t80123450\n")
        return segment, dll

    def test_extract_writes_private_ram_and_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            segment, dll = self._fixture(Path(directory))
            with mock.patch.object(state_extract, "ZSTD_DLL_SHA256",
                                   state_extract.digest(dll)), \
                    mock.patch.object(state_extract, "decompress_core",
                                      return_value=synthetic_core()):
                manifest = state_extract.extract(segment)
            output = segment / "state-extract"
            self.assertEqual(manifest["frame"], 6)
            self.assertEqual(manifest["probe_values"],
                             ("03", "12345678", "46509146", "80123450"))
            self.assertEqual((output / "frame-000006.rdram").stat().st_size,
                             state_extract.RDRAM_SIZE)
            self.assertEqual(json.loads((output / "manifest.json").read_text()),
                             json.loads(json.dumps(manifest)))
            with self.assertRaises(FileExistsError):
                state_extract.extract(segment)

    def test_probe_mismatch_fails_before_output(self):
        with tempfile.TemporaryDirectory() as directory:
            segment, dll = self._fixture(Path(directory))
            trace = segment / "frames.tsv"
            trace.write_text(trace.read_text().replace("46509146", "DEADBEEF"))
            with mock.patch.object(state_extract, "ZSTD_DLL_SHA256",
                                   state_extract.digest(dll)), \
                    mock.patch.object(state_extract, "decompress_core",
                                      return_value=synthetic_core()):
                with self.assertRaisesRegex(ValueError, "live Lua probe"):
                    state_extract.extract(segment)
            self.assertFalse((segment / "state-extract").exists())


if __name__ == "__main__":
    unittest.main()
