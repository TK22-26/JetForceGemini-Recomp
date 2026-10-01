#!/usr/bin/env python3
"""Compare a private emulator PNG oracle with an RT64 PPM readback.

The comparison normalizes the 4:3 N64 oracle into RT64's wider output by
scaling to equal height and centering horizontally. Raw RGB error and
foreground coverage are evaluated directly. SSIM uses a Gaussian prefilter
with a one-oracle-pixel sigma so different native/high-resolution rasterizers
are judged on scene structure instead of subpixel texture sampling. It
intentionally uses only the Python standard library so the acceptance result
does not depend on an untracked image package.
"""

from __future__ import annotations

import json
import math
import pathlib
import struct
import sys
import zlib


MINIMUM_SSIM = 0.80
MINIMUM_FOREGROUND_IOU = 0.80
MAXIMUM_MEAN_ABSOLUTE_ERROR = 0.06
FOREGROUND_THRESHOLD = 8
SSIM_BLOCK_SIZE = 8


class ComparisonError(ValueError):
    pass


def gaussian_blur(
    values: list[float],
    width: int,
    height: int,
    sigma: float,
) -> list[float]:
    if width <= 0 or height <= 0 or len(values) != width * height or sigma <= 0:
        raise ComparisonError("Gaussian prefilter arguments are invalid")
    radius = max(1, math.ceil(3.0 * sigma))
    kernel = [
        math.exp(-(offset * offset) / (2.0 * sigma * sigma))
        for offset in range(-radius, radius + 1)
    ]
    weight_sum = sum(kernel)
    kernel = [weight / weight_sum for weight in kernel]

    horizontal = [0.0] * len(values)
    for y in range(height):
        row = y * width
        for x in range(width):
            horizontal[row + x] = sum(
                kernel[index] * values[
                    row + max(0, min(width - 1, x + index - radius))
                ]
                for index in range(len(kernel))
            )

    output = [0.0] * len(values)
    for y in range(height):
        for x in range(width):
            output[y * width + x] = sum(
                kernel[index] * horizontal[
                    max(0, min(height - 1, y + index - radius)) * width + x
                ]
                for index in range(len(kernel))
            )
    return output


def _paeth(left: int, up: int, upper_left: int) -> int:
    prediction = left + up - upper_left
    left_distance = abs(prediction - left)
    up_distance = abs(prediction - up)
    upper_left_distance = abs(prediction - upper_left)
    if left_distance <= up_distance and left_distance <= upper_left_distance:
        return left
    if up_distance <= upper_left_distance:
        return up
    return upper_left


def read_png_rgb(path: pathlib.Path) -> tuple[int, int, bytes]:
    body = path.read_bytes()
    if not body.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ComparisonError("oracle is not a PNG image")
    cursor = 8
    width = height = channels = 0
    compressed = bytearray()
    saw_header = False
    saw_end = False
    while cursor < len(body):
        if cursor + 12 > len(body):
            raise ComparisonError("PNG chunk header is truncated")
        length = struct.unpack_from(">I", body, cursor)[0]
        kind = body[cursor + 4 : cursor + 8]
        data_start = cursor + 8
        data_end = data_start + length
        if data_end + 4 > len(body):
            raise ComparisonError("PNG chunk body is truncated")
        data = body[data_start:data_end]
        expected_crc = struct.unpack_from(">I", body, data_end)[0]
        if zlib.crc32(kind + data) & 0xFFFFFFFF != expected_crc:
            raise ComparisonError("PNG chunk CRC mismatch")
        cursor = data_end + 4
        if kind == b"IHDR":
            if saw_header or length != 13:
                raise ComparisonError("PNG has an invalid IHDR chunk")
            width, height, depth, color_type, compression, filtering, interlace = (
                struct.unpack(">IIBBBBB", data)
            )
            if width == 0 or height == 0 or depth != 8:
                raise ComparisonError("PNG dimensions or bit depth are unsupported")
            if color_type not in {2, 6}:
                raise ComparisonError("PNG must use RGB or RGBA pixels")
            if compression != 0 or filtering != 0 or interlace != 0:
                raise ComparisonError("PNG compression/filter/interlace mode is unsupported")
            channels = 3 if color_type == 2 else 4
            saw_header = True
        elif kind == b"IDAT":
            if not saw_header:
                raise ComparisonError("PNG IDAT precedes IHDR")
            compressed.extend(data)
        elif kind == b"IEND":
            saw_end = True
            break
    if not saw_header or not saw_end or not compressed:
        raise ComparisonError("PNG is missing required chunks")
    try:
        filtered = zlib.decompress(bytes(compressed))
    except zlib.error as error:
        raise ComparisonError("PNG image data does not decompress") from error
    row_bytes = width * channels
    if len(filtered) != height * (row_bytes + 1):
        raise ComparisonError("PNG decompressed size is invalid")
    previous = bytearray(row_bytes)
    rgb = bytearray(width * height * 3)
    source = 0
    destination = 0
    for _ in range(height):
        filter_type = filtered[source]
        source += 1
        raw = filtered[source : source + row_bytes]
        source += row_bytes
        reconstructed = bytearray(row_bytes)
        for index, value in enumerate(raw):
            left = reconstructed[index - channels] if index >= channels else 0
            up = previous[index]
            upper_left = previous[index - channels] if index >= channels else 0
            if filter_type == 0:
                predictor = 0
            elif filter_type == 1:
                predictor = left
            elif filter_type == 2:
                predictor = up
            elif filter_type == 3:
                predictor = (left + up) // 2
            elif filter_type == 4:
                predictor = _paeth(left, up, upper_left)
            else:
                raise ComparisonError("PNG uses an unknown row filter")
            reconstructed[index] = (value + predictor) & 0xFF
        for x in range(width):
            pixel = x * channels
            rgb[destination : destination + 3] = reconstructed[pixel : pixel + 3]
            destination += 3
        previous = reconstructed
    return width, height, bytes(rgb)


def _ppm_token(body: bytes, cursor: int) -> tuple[bytes, int]:
    while cursor < len(body):
        if body[cursor] == ord("#"):
            newline = body.find(b"\n", cursor)
            if newline < 0:
                raise ComparisonError("PPM comment is unterminated")
            cursor = newline + 1
        elif chr(body[cursor]).isspace():
            cursor += 1
        else:
            break
    start = cursor
    while cursor < len(body) and not chr(body[cursor]).isspace():
        cursor += 1
    if start == cursor:
        raise ComparisonError("PPM header is truncated")
    return body[start:cursor], cursor


def read_ppm_rgb(path: pathlib.Path) -> tuple[int, int, bytes]:
    body = path.read_bytes()
    cursor = 0
    magic, cursor = _ppm_token(body, cursor)
    width_token, cursor = _ppm_token(body, cursor)
    height_token, cursor = _ppm_token(body, cursor)
    maximum_token, cursor = _ppm_token(body, cursor)
    try:
        width = int(width_token)
        height = int(height_token)
        maximum = int(maximum_token)
    except ValueError as error:
        raise ComparisonError("PPM header contains a non-integer") from error
    if magic != b"P6" or width <= 0 or height <= 0 or maximum != 255:
        raise ComparisonError("PPM must be an 8-bit binary RGB image")
    if cursor >= len(body) or not chr(body[cursor]).isspace():
        raise ComparisonError("PPM header has no pixel separator")
    if body[cursor : cursor + 2] == b"\r\n":
        cursor += 2
    else:
        cursor += 1
    expected = width * height * 3
    pixels = body[cursor:]
    if len(pixels) != expected:
        raise ComparisonError("PPM pixel body size is invalid")
    return width, height, pixels


def normalize_reference(
    source_width: int,
    source_height: int,
    source: bytes,
    target_width: int,
    target_height: int,
) -> bytes:
    scale = min(target_height / source_height, target_width / source_width)
    scaled_width = max(1, round(source_width * scale))
    scaled_height = max(1, round(source_height * scale))
    x_origin = (target_width - scaled_width) // 2
    y_origin = (target_height - scaled_height) // 2
    output = bytearray(target_width * target_height * 3)
    for target_y in range(scaled_height):
        source_y = (target_y + 0.5) * source_height / scaled_height - 0.5
        y0 = max(0, min(source_height - 1, math.floor(source_y)))
        y1 = min(source_height - 1, y0 + 1)
        y_fraction = max(0.0, min(1.0, source_y - y0))
        for target_x in range(scaled_width):
            source_x = (target_x + 0.5) * source_width / scaled_width - 0.5
            x0 = max(0, min(source_width - 1, math.floor(source_x)))
            x1 = min(source_width - 1, x0 + 1)
            x_fraction = max(0.0, min(1.0, source_x - x0))
            output_offset = (
                (target_y + y_origin) * target_width + target_x + x_origin
            ) * 3
            for channel in range(3):
                top_left = source[(y0 * source_width + x0) * 3 + channel]
                top_right = source[(y0 * source_width + x1) * 3 + channel]
                bottom_left = source[(y1 * source_width + x0) * 3 + channel]
                bottom_right = source[(y1 * source_width + x1) * 3 + channel]
                top = top_left + (top_right - top_left) * x_fraction
                bottom = bottom_left + (bottom_right - bottom_left) * x_fraction
                output[output_offset + channel] = round(
                    top + (bottom - top) * y_fraction
                )
    return bytes(output)


def compare(
    reference_width: int,
    reference_height: int,
    reference: bytes,
    candidate_width: int,
    candidate_height: int,
    candidate: bytes,
) -> dict[str, object]:
    normalized = normalize_reference(
        reference_width,
        reference_height,
        reference,
        candidate_width,
        candidate_height,
    )
    pixel_count = candidate_width * candidate_height
    absolute_error = 0.0
    squared_error = 0.0
    intersection = 0
    union = 0
    reference_gray: list[float] = []
    candidate_gray: list[float] = []
    for pixel in range(pixel_count):
        offset = pixel * 3
        reference_rgb = normalized[offset : offset + 3]
        candidate_rgb = candidate[offset : offset + 3]
        for channel in range(3):
            difference = (reference_rgb[channel] - candidate_rgb[channel]) / 255.0
            absolute_error += abs(difference)
            squared_error += difference * difference
        reference_foreground = max(reference_rgb) > FOREGROUND_THRESHOLD
        candidate_foreground = max(candidate_rgb) > FOREGROUND_THRESHOLD
        intersection += int(reference_foreground and candidate_foreground)
        union += int(reference_foreground or candidate_foreground)
        reference_gray.append(
            (0.2126 * reference_rgb[0] +
             0.7152 * reference_rgb[1] +
             0.0722 * reference_rgb[2]) / 255.0
        )
        candidate_gray.append(
            (0.2126 * candidate_rgb[0] +
             0.7152 * candidate_rgb[1] +
             0.0722 * candidate_rgb[2]) / 255.0
        )

    normalization_scale = min(
        candidate_height / reference_height,
        candidate_width / reference_width,
    )
    ssim_sigma = normalization_scale
    reference_structural = gaussian_blur(
        reference_gray, candidate_width, candidate_height, ssim_sigma)
    candidate_structural = gaussian_blur(
        candidate_gray, candidate_width, candidate_height, ssim_sigma)

    ssim_values: list[float] = []
    c1 = 0.01**2
    c2 = 0.03**2
    for y in range(0, candidate_height, SSIM_BLOCK_SIZE):
        for x in range(0, candidate_width, SSIM_BLOCK_SIZE):
            first: list[float] = []
            second: list[float] = []
            for block_y in range(y, min(y + SSIM_BLOCK_SIZE, candidate_height)):
                row = block_y * candidate_width
                for block_x in range(x, min(x + SSIM_BLOCK_SIZE, candidate_width)):
                    first.append(reference_structural[row + block_x])
                    second.append(candidate_structural[row + block_x])
            first_mean = sum(first) / len(first)
            second_mean = sum(second) / len(second)
            first_variance = sum(
                (value - first_mean) ** 2 for value in first
            ) / len(first)
            second_variance = sum(
                (value - second_mean) ** 2 for value in second
            ) / len(second)
            covariance = sum(
                (left - first_mean) * (right - second_mean)
                for left, right in zip(first, second)
            ) / len(first)
            ssim_values.append(
                ((2 * first_mean * second_mean + c1) *
                 (2 * covariance + c2)) /
                ((first_mean**2 + second_mean**2 + c1) *
                 (first_variance + second_variance + c2))
            )

    mean_absolute_error = absolute_error / (pixel_count * 3)
    mean_squared_error = squared_error / (pixel_count * 3)
    ssim = sum(ssim_values) / len(ssim_values)
    foreground_iou = intersection / union if union else 1.0
    passed = (
        ssim >= MINIMUM_SSIM and
        foreground_iou >= MINIMUM_FOREGROUND_IOU and
        mean_absolute_error <= MAXIMUM_MEAN_ABSOLUTE_ERROR
    )
    return {
        "schema_version": 1,
        "kind": "jfg-phase7-frame-comparison",
        "status": "pass" if passed else "fail",
        "reference_dimensions": [reference_width, reference_height],
        "candidate_dimensions": [candidate_width, candidate_height],
        "normalization": "fit-height-or-width-bilinear-centered-black",
        "ssim_prefilter": {
            "kind": "separable-gaussian-one-reference-pixel",
            "sigma_output_pixels": round(ssim_sigma, 9),
        },
        "metrics": {
            "ssim_8x8": round(ssim, 9),
            "foreground_iou": round(foreground_iou, 9),
            "mean_absolute_error": round(mean_absolute_error, 9),
            "psnr_db": None if mean_squared_error == 0 else round(
                -10.0 * math.log10(mean_squared_error), 6
            ),
        },
        "thresholds": {
            "minimum_ssim_8x8": MINIMUM_SSIM,
            "minimum_foreground_iou": MINIMUM_FOREGROUND_IOU,
            "maximum_mean_absolute_error": MAXIMUM_MEAN_ABSOLUTE_ERROR,
        },
    }


def main() -> int:
    if len(sys.argv) not in {3, 4}:
        print(
            "usage: compare_phase7_frames.py "
            "<emulator-oracle.png> <rt64-readback.ppm> [result.json]",
            file=sys.stderr,
        )
        return 2
    try:
        reference = read_png_rgb(pathlib.Path(sys.argv[1]))
        candidate = read_ppm_rgb(pathlib.Path(sys.argv[2]))
        result = compare(*reference, *candidate)
    except (OSError, ComparisonError) as error:
        print(f"frame comparison failed: {error}", file=sys.stderr)
        return 2
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if len(sys.argv) == 4:
        pathlib.Path(sys.argv[3]).write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
