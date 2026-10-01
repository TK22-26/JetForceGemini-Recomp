#!/usr/bin/env python3
"""Stream a BizHawk BK2 into a compact, reproducible TAS route index.

This tool never reads a ROM or emits individual movie input rows. Frame numbers
are zero-based and intervals are half-open, matching the phase-8 replay format.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any


SCHEMA = "jfg-phase95-tas-index-v1"
EXPECTED_SHA1 = "15099233760B36E7AFAD7DA36B9464DA1512C4B1"
EXPECTED_VERSION = "2.9.1"
EXPECTED_GAME = "Star Twins (Japan)"
EXPECTED_CORE = "Mupen64Plus"
BUTTON_NAMES = (
    "A Up", "A Down", "A Left", "A Right", "DPad U", "DPad D",
    "DPad L", "DPad R", "Start", "Z", "B", "A", "C Up",
    "C Down", "C Left", "C Right", "L", "R",
)
LOG_FIELDS = (
    "#Reset", "Power",
    *(field for player in ("P1", "P2") for field in (
        f"#{player} X Axis", f"{player} Y Axis",
        *(f"{player} {button}" for button in BUTTON_NAMES),
    )),
)
MAX_SMALL_ENTRY = 1_000_000
MAX_INPUT_BYTES = 1_000_000_000
MAX_EVENTS = 100_000


class TasIndexError(ValueError):
    """The BK2 is malformed or does not describe the expected movie."""


def _decode(raw: bytes, description: str) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeError as error:
        raise TasIndexError(f"{description} is not UTF-8 text") from error


def _small_entry(archive: zipfile.ZipFile, name: str) -> str:
    info = archive.getinfo(name)
    if info.file_size > MAX_SMALL_ENTRY:
        raise TasIndexError(f"{name} is unexpectedly large")
    return _decode(archive.read(info), name)


def _header(text: str) -> dict[str, str]:
    header: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        key, separator, value = line.partition(" ")
        if not separator or not value.strip() or key in header:
            raise TasIndexError("malformed or duplicate BK2 header field")
        header[key] = value.strip()
    return header


def _validate_metadata(
    archive: zipfile.ZipFile, expected_sha1: str, expected_version: str,
) -> tuple[dict[str, str], dict[str, Any]]:
    names = [info.filename for info in archive.infolist()]
    if len(set(names)) != len(names):
        raise TasIndexError("BK2 contains duplicate entry names")
    for name in ("BizVersion.txt", "Header.txt", "SyncSettings.json", "Input Log.txt"):
        if name not in names:
            raise TasIndexError(f"BK2 is missing {name}")
    header = _header(_small_entry(archive, "Header.txt"))
    version = f"Version {expected_version}"
    checks = {
        "emuVersion": version,
        "OriginalEmuVersion": version,
        "Platform": "N64",
        "GameName": EXPECTED_GAME,
        "SHA1": expected_sha1.upper(),
        "Core": EXPECTED_CORE,
    }
    for key, expected in checks.items():
        actual = header.get(key)
        if (actual or "").upper() != expected.upper():
            raise TasIndexError(f"{key} mismatch: expected {expected!r}, got {actual!r}")
    if _small_entry(archive, "BizVersion.txt").strip() != version:
        raise TasIndexError("BizVersion.txt does not match expected emulator version")
    sync_text = _small_entry(archive, "SyncSettings.json")
    try:
        sync = json.loads(sync_text)
        settings = sync["o"]
        controllers = settings["Controllers"]
    except (ValueError, TypeError, KeyError) as error:
        raise TasIndexError("invalid N64 sync settings") from error
    if not isinstance(controllers, list) or len(controllers) != 4 or any(
        not isinstance(controller, dict) for controller in controllers
    ):
        raise TasIndexError("N64 sync settings must describe four controller ports")
    connections = [controller.get("IsConnected") for controller in controllers]
    if any(actual is not expected for actual, expected in zip(
        connections, (True, True, False, False), strict=True
    )):
        raise TasIndexError(f"unexpected controller connections: {connections!r}")
    if settings.get("VideoPlugin") != 5:
        raise TasIndexError("unexpected N64 video plugin")
    return header, {
        "controller_connected": connections,
        "controller_pak_types": [controller.get("PakType") for controller in controllers],
        "core_id": settings.get("Core"),
        "rsp_id": settings.get("Rsp"),
        "video_plugin_id": settings["VideoPlugin"],
        "disable_expansion_slot": settings.get("DisableExpansionSlot"),
        "sha256": hashlib.sha256(archive.read("SyncSettings.json")).hexdigest(),
    }


def _new_controls() -> dict[str, Any]:
    return {
        "active_frames": 0,
        "analog_x_nonzero_frames": 0,
        "analog_y_nonzero_frames": 0,
        "analog_x_min": None,
        "analog_x_max": None,
        "analog_y_min": None,
        "analog_y_max": None,
        "button_frames": {},
        "button_press_edges": {},
    }


def _update_controls(stats: dict[str, Any], axes: tuple[int, int], pressed: set[str], previous: set[str]) -> None:
    x, y = axes
    if x or y or pressed:
        stats["active_frames"] += 1
    stats["analog_x_nonzero_frames"] += int(x != 0)
    stats["analog_y_nonzero_frames"] += int(y != 0)
    for axis, value in (("x", x), ("y", y)):
        minimum, maximum = f"analog_{axis}_min", f"analog_{axis}_max"
        stats[minimum] = value if stats[minimum] is None else min(stats[minimum], value)
        stats[maximum] = value if stats[maximum] is None else max(stats[maximum], value)
    for button in pressed:
        counts = stats["button_frames"]
        counts[button] = counts.get(button, 0) + 1
    for button in pressed - previous:
        counts = stats["button_press_edges"]
        counts[button] = counts.get(button, 0) + 1


def _parse_controller(column: str, line_number: int) -> tuple[tuple[int, int], set[str]]:
    fields = column.split(",")
    if len(fields) != 3:
        raise TasIndexError(f"invalid controller column at input line {line_number}")
    try:
        axes = int(fields[0].strip()), int(fields[1].strip())
    except ValueError as error:
        raise TasIndexError(f"invalid analog value at input line {line_number}") from error
    buttons = fields[2]
    if any(not -128 <= value <= 127 for value in axes) or len(buttons) != len(BUTTON_NAMES):
        raise TasIndexError(f"unsupported controller value at input line {line_number}")
    if any(ord(marker) < 33 or ord(marker) > 126 for marker in buttons):
        raise TasIndexError(f"invalid button marker at input line {line_number}")
    return axes, {name for name, marker in zip(BUTTON_NAMES, buttons, strict=True) if marker != "."}


def _parse_row(raw: bytes, line_number: int) -> tuple[list[tuple[tuple[int, int], set[str]]], set[str]]:
    line = _decode(raw.rstrip(b"\r\n"), f"input line {line_number}")
    columns = line.split("|")
    if len(columns) != 5 or columns[0] or columns[-1] or len(columns[1]) != 2:
        raise TasIndexError(f"invalid input row at line {line_number}")
    flags = columns[1]
    if any(ord(marker) < 33 or ord(marker) > 126 for marker in flags):
        raise TasIndexError(f"invalid reset/power marker at line {line_number}")
    events = {name for name, marker in zip(("reset", "power"), flags, strict=True) if marker != "."}
    return [_parse_controller(column, line_number) for column in columns[2:4]], events


def _index_input(archive: zipfile.ZipFile, window_size: int) -> dict[str, Any]:
    info = archive.getinfo("Input Log.txt")
    if info.file_size > MAX_INPUT_BYTES:
        raise TasIndexError("Input Log.txt exceeds the safety limit")
    total = [_new_controls(), _new_controls()]
    windows: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    previous: list[set[str]] = [set(), set()]
    full_digest = hashlib.sha256()
    window_digest = hashlib.sha256()
    frame = 0
    with archive.open(info) as stream:
        first = stream.readline()
        second = stream.readline()
        if _decode(first.rstrip(b"\r\n"), "input header") != "[Input]":
            raise TasIndexError("Input Log.txt lacks [Input] header")
        key = _decode(second.rstrip(b"\r\n"), "LogKey")
        if not key.startswith("LogKey:") or tuple(key[7:].split("|")[:-1]) != LOG_FIELDS or not key.endswith("|"):
            raise TasIndexError("unsupported BizHawk N64 LogKey")
        window = {"start_frame": 0, "controllers": [_new_controls(), _new_controls()]}
        closed = False
        for line_number, raw in enumerate(stream, start=3):
            if raw.rstrip(b"\r\n") == b"[/Input]":
                if stream.read().strip():
                    raise TasIndexError("unexpected data after [/Input]")
                closed = True
                break
            samples, flags = _parse_row(raw, line_number)
            full_digest.update(raw)
            window_digest.update(raw)
            for port, (axes, buttons) in enumerate(samples):
                _update_controls(total[port], axes, buttons, previous[port])
                _update_controls(window["controllers"][port], axes, buttons, previous[port])
                previous[port] = buttons
            if flags:
                events.append({"frame": frame, "events": sorted(flags)})
                if len(events) > MAX_EVENTS:
                    raise TasIndexError("too many reset/power events")
            frame += 1
            if frame % window_size == 0:
                window["end_frame"] = frame
                window["input_sha256"] = window_digest.hexdigest()
                windows.append(window)
                window = {"start_frame": frame, "controllers": [_new_controls(), _new_controls()]}
                window_digest = hashlib.sha256()
    if not closed or frame == 0:
        raise TasIndexError("input log is empty or lacks [/Input]")
    if frame % window_size:
        window["end_frame"] = frame
        window["input_sha256"] = window_digest.hexdigest()
        windows.append(window)
    return {
        "frame_count": frame,
        "input_rows_sha256": full_digest.hexdigest(),
        "log_key_sha256": hashlib.sha256(key.encode("utf-8")).hexdigest(),
        "window_size": window_size,
        "reset_power_events": events,
        "controllers": total,
        "windows": windows,
    }


def index_movie(
    path: Path, *, window_size: int = 600, expected_sha1: str = EXPECTED_SHA1,
    expected_version: str = EXPECTED_VERSION, expected_frames: int | None = None,
) -> dict[str, Any]:
    """Validate and summarize the Japanese two-controller BK2 without a ROM."""
    if not 1 <= window_size <= 36_000:
        raise TasIndexError("window size must be between 1 and 36000 frames")
    if not re.fullmatch(r"[0-9a-fA-F]{40}", expected_sha1):
        raise TasIndexError("expected SHA-1 must be forty hexadecimal digits")
    if expected_frames is not None and expected_frames <= 0:
        raise TasIndexError("expected frame count must be positive")
    try:
        with zipfile.ZipFile(path) as archive:
            header, sync = _validate_metadata(archive, expected_sha1, expected_version)
            input_index = _index_input(archive, window_size)
    except (OSError, zipfile.BadZipFile, KeyError, EOFError) as error:
        raise TasIndexError(f"unable to read BK2: {error}") from error
    if expected_frames is not None and input_index["frame_count"] != expected_frames:
        raise TasIndexError(
            f"frame count mismatch: expected {expected_frames}, got {input_index['frame_count']}"
        )
    archive_digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                archive_digest.update(block)
    except OSError as error:
        raise TasIndexError(f"unable to hash BK2: {error}") from error
    return {
        "schema": SCHEMA,
        "source": {"filename": path.name, "archive_sha256": archive_digest.hexdigest()},
        "movie": {
            "game_name": header["GameName"],
            "rom_sha1": header["SHA1"].upper(),
            "emulator_version": expected_version,
            "original_emulator_version": header["OriginalEmuVersion"],
            "movie_version": header.get("MovieVersion"),
            "platform": header["Platform"],
            "core": header["Core"],
            "author": header.get("Author"),
            "rerecord_count": int(header["rerecordCount"]) if header.get("rerecordCount", "").isdigit() else None,
            "sync": sync,
        },
        "input": input_index,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bk2", type=Path, help="inner BizHawk .bk2 movie")
    parser.add_argument("--output", type=Path, help="JSON destination; stdout if omitted")
    parser.add_argument("--window-size", type=int, default=600)
    parser.add_argument("--expected-sha1", default=EXPECTED_SHA1)
    parser.add_argument("--expected-version", default=EXPECTED_VERSION)
    parser.add_argument("--expected-frames", type=int)
    args = parser.parse_args(argv)
    try:
        result = index_movie(
            args.bk2, window_size=args.window_size, expected_sha1=args.expected_sha1,
            expected_version=args.expected_version, expected_frames=args.expected_frames,
        )
        encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.write_text(encoded, encoding="utf-8", newline="\n")
        else:
            sys.stdout.write(encoded)
    except (TasIndexError, OSError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
