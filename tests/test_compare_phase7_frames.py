from __future__ import annotations

import pathlib
import struct
import sys
import tempfile
import unittest
import zlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import compare_phase7_frames as comparator  # noqa: E402


def png(width: int, height: int, pixels: bytes) -> bytes:
    def chunk(kind: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body)) + kind + body +
            struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
        )

    rows = b"".join(
        b"\0" + pixels[row * width * 3 : (row + 1) * width * 3]
        for row in range(height)
    )
    return (
        b"\x89PNG\r\n\x1a\n" +
        chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) +
        chunk(b"IDAT", zlib.compress(rows)) +
        chunk(b"IEND", b"")
    )


def ppm(width: int, height: int, pixels: bytes) -> bytes:
    return f"P6\n{width} {height}\n255\n".encode("ascii") + pixels


class Phase7FrameComparisonTests(unittest.TestCase):
    def test_identical_images_pass(self) -> None:
        pixels = bytes(
            channel
            for y in range(16)
            for x in range(16)
            for channel in ((255, 80, 20) if 3 <= x < 13 and 3 <= y < 13 else (0, 0, 0))
        )
        result = comparator.compare(16, 16, pixels, 16, 16, pixels)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["metrics"]["ssim_8x8"], 1.0)
        self.assertEqual(result["metrics"]["foreground_iou"], 1.0)
        self.assertEqual(
            result["ssim_prefilter"]["kind"],
            "separable-gaussian-one-reference-pixel",
        )
        self.assertEqual(result["ssim_prefilter"]["sigma_output_pixels"], 1.0)

    def test_missing_foreground_fails(self) -> None:
        reference = bytes([255, 255, 255] * (16 * 16))
        candidate = bytes([0, 0, 0] * (16 * 16))
        result = comparator.compare(16, 16, reference, 16, 16, candidate)
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["metrics"]["foreground_iou"], 0.0)

    def test_structural_displacement_still_fails(self) -> None:
        reference = bytearray([0, 0, 0] * (32 * 32))
        candidate = bytearray([0, 0, 0] * (32 * 32))
        for y in range(8, 24):
            for x in range(4, 12):
                reference[(y * 32 + x) * 3 : (y * 32 + x + 1) * 3] = (
                    b"\xff\x80\x20"
                )
                candidate[(y * 32 + x + 16) * 3 :
                          (y * 32 + x + 17) * 3] = b"\xff\x80\x20"
        result = comparator.compare(
            32, 32, bytes(reference), 32, 32, bytes(candidate)
        )
        self.assertEqual(result["status"], "fail")
        self.assertLess(result["metrics"]["ssim_8x8"], 0.8)

    def test_png_and_ppm_decoders_are_strict(self) -> None:
        pixels = bytes([12, 34, 56] * 4)
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            png_path = root / "oracle.png"
            ppm_path = root / "candidate.ppm"
            png_path.write_bytes(png(2, 2, pixels))
            ppm_path.write_bytes(ppm(2, 2, pixels))
            self.assertEqual(comparator.read_png_rgb(png_path), (2, 2, pixels))
            self.assertEqual(comparator.read_ppm_rgb(ppm_path), (2, 2, pixels))
            corrupted = bytearray(png_path.read_bytes())
            corrupted[-1] ^= 1
            png_path.write_bytes(corrupted)
            with self.assertRaises(comparator.ComparisonError):
                comparator.read_png_rgb(png_path)


if __name__ == "__main__":
    unittest.main()
