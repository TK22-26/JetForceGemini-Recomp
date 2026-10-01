#!/usr/bin/env python3
"""Convert a bounded BizHawk N64 input-log segment to JFG replay v2."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


HEADER = "jfg-phase8-input-v2"
MAX_EVENTS = 4096
BUTTON_BITS = (
    0,
    0,
    0,
    0,
    0x0800,
    0x0400,
    0x0200,
    0x0100,
    0x1000,
    0x2000,
    0x4000,
    0x8000,
    0x0008,
    0x0004,
    0x0002,
    0x0001,
    0x0020,
    0x0010,
)


class ConversionError(ValueError):
    """The input log or requested segment is invalid."""


@dataclass(frozen=True)
class Sample:
    buttons: int
    stick_x: int
    stick_y: int

    def neutral(self) -> bool:
        return self.buttons == 0 and self.stick_x == 0 and self.stick_y == 0


@dataclass(frozen=True)
class Event:
    first: int
    end: int
    sample: Sample


def parse_player_column(column: str) -> Sample:
    fields = column.split(",")
    if len(fields) != 3:
        raise ConversionError("invalid BizHawk controller column")
    try:
        stick_x = int(fields[0].strip())
        stick_y = int(fields[1].strip())
    except ValueError as error:
        raise ConversionError("invalid BizHawk analog value") from error
    buttons = fields[2]
    if len(buttons) != len(BUTTON_BITS) or not -128 <= stick_x <= 127 or not -128 <= stick_y <= 127:
        raise ConversionError("unsupported BizHawk controller value")
    mask = 0
    for marker, bit in zip(buttons, BUTTON_BITS, strict=True):
        if marker != ".":
            mask |= bit
    return Sample(mask, stick_x, stick_y)


def parse_log(path: Path) -> list[Sample]:
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as error:
        raise ConversionError(f"unable to read input log: {error}") from error
    if len(lines) < 2 or lines[0] != "[Input]" or not lines[1].startswith("LogKey:"):
        raise ConversionError("not a BizHawk input log")
    samples: list[Sample] = []
    for line_number, line in enumerate(lines[2:], start=3):
        if line == "[/Input]" and line_number == len(lines):
            break
        columns = line.split("|")
        if len(columns) < 4 or columns[0] != "":
            raise ConversionError(f"invalid input row at line {line_number}")
        samples.append(parse_player_column(columns[2]))
    if not samples:
        raise ConversionError("input log is empty")
    return samples


def load_prefix(path: Path | None) -> list[Event]:
    if path is None:
        return []
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as error:
        raise ConversionError(f"unable to read replay prefix: {error}") from error
    if not lines or lines[0] not in {"jfg-phase8-input-v1", HEADER}:
        raise ConversionError("invalid replay prefix header")
    has_connection = lines[0] == HEADER
    events: list[Event] = []
    for line in lines[1:]:
        fields = line.split(",")
        if len(fields) != (6 if has_connection else 5):
            raise ConversionError("invalid replay prefix record")
        offset = 1 if has_connection else 0
        if has_connection and fields[2] != "1":
            raise ConversionError("disconnected prefix events are unsupported")
        try:
            event = Event(
                int(fields[0]),
                int(fields[1]),
                Sample(int(fields[2 + offset], 16), int(fields[3 + offset]), int(fields[4 + offset])),
            )
        except ValueError as error:
            raise ConversionError("invalid replay prefix value") from error
        if event.first >= event.end or (events and event.first < events[-1].end):
            raise ConversionError("replay prefix is not strictly ordered")
        events.append(event)
    return events


def convert(
    samples: list[Sample], source_start: int, source_end: int,
    target_start: int, prefix: list[Event]
) -> list[Event]:
    if (
        source_start < 0
        or source_end <= source_start
        or source_end > len(samples)
        or target_start < 0
    ):
        raise ConversionError("invalid conversion interval")
    result = list(prefix)
    run_start = source_start
    current = samples[source_start]
    for frame in range(source_start + 1, source_end + 1):
        candidate = samples[frame] if frame < source_end else None
        if candidate == current:
            continue
        first = target_start + run_start - source_start
        end = target_start + frame - source_start
        if not current.neutral():
            event = Event(first, end, current)
            if result and event.first < result[-1].end:
                raise ConversionError("converted segment overlaps replay prefix")
            result.append(event)
        if frame < source_end:
            run_start = frame
            current = candidate
    if len(result) > MAX_EVENTS:
        raise ConversionError("converted replay exceeds the runtime event limit")
    return result


def write_replay(path: Path, events: list[Event]) -> None:
    rows = [HEADER]
    rows.extend(
        f"{event.first},{event.end},1,{event.sample.buttons:04x},"
        f"{event.sample.stick_x},{event.sample.stick_y}"
        for event in events
    )
    try:
        path.write_text("\n".join(rows) + "\n", encoding="ascii", newline="\n")
    except OSError as error:
        raise ConversionError(f"unable to write replay: {error}") from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-log", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-start", required=True, type=int)
    parser.add_argument("--source-end", required=True, type=int)
    parser.add_argument("--target-start", required=True, type=int)
    parser.add_argument("--prefix", type=Path)
    args = parser.parse_args()
    try:
        events = convert(
            parse_log(args.input_log), args.source_start, args.source_end,
            args.target_start, load_prefix(args.prefix)
        )
        write_replay(args.output, events)
    except ConversionError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
