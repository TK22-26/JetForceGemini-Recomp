"""Extract and index completed Japanese TAS batch states without touching playback.

Safe to rerun during capture. Existing extracts are checked, never overwritten;
unfinished or failed attempts remain untouched. The index is private and is
marked complete only after the capture batch itself reports full completion.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import zipfile

from scripts import phase95_tas_capture as capture
from scripts import phase95_tas_state_extract as state_extract


KIND = "jfg-phase95-jp-tas-state-batch"
PLAN_KIND = "jfg-phase95-jp-tas-capture-batch"
INDEX_NAME = "tas-state-index.json"
MOVIE_FRAMES = capture.MOVIE_FRAMES


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"not a JSON object: {path}")
    return value


def write_json_atomic(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8")
    os.replace(temporary, path)


def segment_ranges(frames: int, size: int):
    for first in range(0, frames, size):
        yield first, min(first + size, frames) - 1


def validate_plan(root: Path) -> dict:
    plan = read_json(root / "batch.json")
    if plan.get("kind") != PLAN_KIND or plan.get("schema") != 1 or \
            plan.get("semantic_status") != "raw-unverified-jp":
        raise ValueError("not a pinned raw Japanese TAS batch plan")
    pins = plan.get("pins")
    expected = {"rom_sha1": capture.JP_ROM_SHA1,
                "rom_sha256": capture.JP_ROM_SHA256,
                "movie_sha256": capture.MOVIE_SHA256,
                "movie_frames": MOVIE_FRAMES,
                "emulator_sha256": capture.BIZHAWK_291_EXE_SHA256,
                "runtime_sha256": capture.BIZHAWK_291_RUNTIME_SHA256}
    if not isinstance(pins, dict) or any(pins.get(k) != v for k, v in expected.items()):
        raise ValueError("batch source pins differ from synchronized TAS")
    size = plan.get("segment_frames")
    if type(size) is not int or not 1 <= size <= capture.MAX_SEGMENT_FRAMES:
        raise ValueError("invalid batch segment size")
    return plan


def validate_extract(attempt: Path, frame: int, result: dict) -> dict:
    directory = attempt / "state-extract"
    manifest = read_json(directory / "manifest.json")
    if manifest.get("kind") != "jfg-phase95-jp-tas-state-extract" or \
            manifest.get("schema") != 1 or \
            manifest.get("semantic_status") != "raw-unverified-jp" or \
            manifest.get("frame") != frame or \
            manifest.get("source_segment") != str(attempt) or \
            manifest.get("source_result_sha256") != capture.digest(attempt / "result.json") or \
            manifest.get("source_state_sha256") != result["continuation_sha256"] or \
            manifest.get("core_layout") != "bizhawk-2.9.1-m64plus-v1.0" or \
            manifest.get("rdram_offset") != state_extract.RDRAM_OFFSET or \
            manifest.get("rdram_bytes") != state_extract.RDRAM_SIZE or \
            manifest.get("host_word_conversion") != "byteswap-each-u32" or \
            manifest.get("zstd_dll_sha256") != state_extract.ZSTD_DLL_SHA256:
        raise ValueError(f"existing extract manifest mismatch: {directory}")
    memory_path = directory / f"frame-{frame:06d}.rdram"
    if memory_path.stat().st_size != state_extract.RDRAM_SIZE or \
            capture.digest(memory_path) != manifest.get("rdram_sha256"):
        raise ValueError(f"existing extracted RDRAM digest mismatch: {memory_path}")
    expected_probes = state_extract.final_probes(
        attempt / "frames.tsv", result["first"], frame)
    rdram = memory_path.read_bytes()
    for index, (address, width) in enumerate(state_extract.PROBES):
        if rdram[address:address + width].hex().upper() != expected_probes[index]:
            raise ValueError(f"existing extract differs from live probe {index}")
    if (manifest.get("probe_values") != list(expected_probes) or
            manifest.get("probe_addresses") != [p[0] for p in state_extract.PROBES]):
        raise ValueError("existing extract probe provenance mismatch")
    return manifest


def _select_complete(segment: Path, first: int, last: int, pins: dict,
                     previous: Path | None) -> tuple[Path | None, int]:
    expected_parent = (read_json(previous / "result.json")["continuation_sha256"]
                       if previous is not None else None)
    expected_path = str(previous) if previous is not None else None
    complete = []
    failed = 0
    for attempt in sorted(segment.glob("attempt-*")) if segment.exists() else ():
        if not attempt.is_dir() or not attempt.name[8:].isdigit():
            raise ValueError(f"unexpected batch attempt path: {attempt}")
        result_path = attempt / "result.json"
        if not result_path.exists():
            continue  # In-progress or interrupted before result publication.
        try:
            result = read_json(result_path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue  # A concurrent writer may have this file open.
        if result.get("complete") is not True:
            failed += 1
            continue
        if result.get("first") != first or result.get("last") != last or \
                result.get("resume_from") != expected_path or \
                result.get("parent_continuation_sha256") != expected_parent or \
                any(result.get(k) != value for k, value in pins.items()):
            raise ValueError(f"completed attempt has wrong range, lineage or pins: {attempt}")
        capture.validate_resume(attempt, pins, last + 1)
        capture.parse_trace(attempt / "frames.tsv", first, last)
        complete.append(attempt)
    if len(complete) > 1:
        raise ValueError(f"multiple complete attempts in {segment}")
    return (complete[0] if complete else None), failed


def index_batch(root: Path) -> dict:
    root = Path(root).resolve()
    plan = validate_plan(root)
    pins = plan["pins"]
    ranges = list(segment_ranges(MOVIE_FRAMES, plan["segment_frames"]))
    entries = []
    errors = []
    failed_attempts = 0
    previous = None
    for first, last in ranges:
        segment = root / "segments" / f"segment-{first:06d}-{last:06d}"
        try:
            attempt, failed = _select_complete(segment, first, last, pins, previous)
            failed_attempts += failed
            if attempt is None:
                break  # The capture batch is sequential; later ranges cannot be trusted yet.
            directory = attempt / "state-extract"
            if not directory.exists():
                state_extract.extract(attempt)
            result = read_json(attempt / "result.json")
            extracted = validate_extract(attempt, last, result)
            entries.append({"frame": last, "segment": str(segment),
                            "attempt": str(attempt),
                            "rdram": str(directory / f"frame-{last:06d}.rdram"),
                            "rdram_sha256": extracted["rdram_sha256"],
                            "continuation_sha256": result["continuation_sha256"]})
            previous = attempt
        except (OSError, ValueError, KeyError, RuntimeError,
                zipfile.BadZipFile) as error:
            errors.append({"segment": str(segment), "error": str(error)})
            break
    batch_result_path = root / "batch-result.json"
    batch_reported_complete = False
    if batch_result_path.exists():
        try:
            batch_result = read_json(batch_result_path)
            batch_reported_complete = (batch_result.get("kind") == PLAN_KIND and
                batch_result.get("schema") == 1 and
                batch_result.get("complete") is True and
                batch_result.get("segments_total") == len(ranges) and
                batch_result.get("segments_complete") == len(ranges) and
                batch_result.get("last_complete_frame") == MOVIE_FRAMES - 1)
        except (OSError, ValueError, json.JSONDecodeError):
            pass  # The batch may be writing its summary concurrently.
    complete = (batch_reported_complete and len(entries) == len(ranges) and
                not errors and entries[-1]["frame"] == MOVIE_FRAMES - 1)
    index = {"kind": KIND, "schema": 1,
             "semantic_status": "raw-unverified-jp",
             "batch_plan_sha256": capture.digest(root / "batch.json"),
             "extractor_sha256": capture.digest(Path(state_extract.__file__).resolve()),
             "movie_frames": MOVIE_FRAMES, "segments_total": len(ranges),
             "segments_extracted": len(entries),
             "failed_attempts_seen": failed_attempts,
             "last_extracted_frame": entries[-1]["frame"] if entries else None,
             "batch_reported_complete": batch_reported_complete,
             "complete": complete, "errors": errors, "entries": entries}
    write_json_atomic(root / INDEX_NAME, index)
    return index


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch_root", type=Path)
    args = parser.parse_args()
    print(json.dumps(index_batch(args.batch_root)))


if __name__ == "__main__":
    main()
