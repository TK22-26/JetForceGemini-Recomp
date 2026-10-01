#!/usr/bin/env python3
"""Analyze a private Phase 8 raw PCM capture and its host timing events."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import signal


def read_events(path: Path) -> list[dict[str, int | str]]:
    events: list[dict[str, int | str]] = []
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            events.append(
                {
                    "wall_us": int(row["wall_us"]),
                    "event": row["event"],
                    "queued_bytes": int(row["queued_bytes"]),
                    "consumed_bytes": int(row["consumed_bytes"]),
                }
            )
    return events


def paired_pauses(events: list[dict[str, int | str]]) -> list[tuple[int, int, int]]:
    pauses: list[tuple[int, int, int]] = []
    pending: dict[str, int | str] | None = None
    for event in events:
        kind = event["event"]
        if kind in {"pause-low", "underrun"} and pending is None:
            pending = event
        elif kind == "resume" and pending is not None:
            pauses.append(
                (
                    int(pending["wall_us"]),
                    int(event["wall_us"]),
                    int(pending["consumed_bytes"]) // 4,
                )
            )
            pending = None
    return pauses


def insert_host_pauses(
    pcm: np.ndarray, pauses: list[tuple[int, int, int]], rate: int
) -> np.ndarray:
    chunks: list[np.ndarray] = []
    source_offset = 0
    for begin_us, end_us, source_frame in pauses:
        source_frame = min(max(source_frame, source_offset), len(pcm))
        chunks.append(pcm[source_offset:source_frame])
        pause_frames = max(0, round((end_us - begin_us) * rate / 1_000_000))
        if pause_frames:
            chunks.append(np.zeros((pause_frames, 2), dtype=np.int16))
        source_offset = source_frame
    chunks.append(pcm[source_offset:])
    return np.concatenate(chunks) if chunks else pcm


def spectrogram_image(pcm: np.ndarray, rate: int, title: str) -> Image.Image:
    mono = pcm.astype(np.float32).mean(axis=1)
    _, _, magnitude = signal.spectrogram(
        mono,
        fs=rate,
        window="hann",
        nperseg=1024,
        noverlap=768,
        mode="magnitude",
    )
    db = 20.0 * np.log10(np.maximum(magnitude, 1.0e-6))
    low, high = np.percentile(db, [3.0, 99.5])
    normalized = np.clip((db - low) / max(high - low, 1.0e-6), 0.0, 1.0)
    pixels = np.flipud((normalized * 255.0).astype(np.uint8))
    image = Image.fromarray(pixels, mode="L").resize(
        (1400, 420), resample=Image.Resampling.BILINEAR
    ).convert("RGB")
    canvas = Image.new("RGB", (1400, 452), "black")
    canvas.paste(image, (0, 32))
    ImageDraw.Draw(canvas).text((10, 9), title, fill="white")
    return canvas


def count_zero_runs(pcm: np.ndarray, minimum_frames: int) -> int:
    silent = np.all(pcm == 0, axis=1)
    padded = np.pad(silent.astype(np.int8), (1, 1))
    edges = np.diff(padded)
    starts = np.flatnonzero(edges == 1)
    ends = np.flatnonzero(edges == -1)
    return int(np.count_nonzero(ends - starts >= minimum_frames))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pcm", type=Path, help="stereo signed-16 LE raw PCM")
    parser.add_argument("--rate", type=int, required=True)
    parser.add_argument("--events", type=Path)
    parser.add_argument("--output-prefix", type=Path, required=True)
    args = parser.parse_args()

    raw = np.fromfile(args.pcm, dtype="<i2")
    if raw.size == 0 or raw.size % 2:
        raise SystemExit("PCM capture must contain complete stereo frames")
    pcm = raw.reshape((-1, 2))
    event_path = args.events or Path(str(args.pcm) + ".events.csv")
    events = read_events(event_path)
    pauses = paired_pauses(events)
    pause_ms = [(end - begin) / 1000.0 for begin, end, _ in pauses]
    pause_starts = [begin for begin, _, _ in pauses]
    pause_intervals_ms = [
        (right - left) / 1000.0
        for left, right in zip(pause_starts, pause_starts[1:])
    ]
    host_timeline = insert_host_pauses(pcm, pauses, args.rate)

    decoded_image = spectrogram_image(
        pcm, args.rate, "Decoded PCM (before SDL host timing)"
    )
    host_image = spectrogram_image(
        host_timeline, args.rate, "Estimated host timeline (device pauses inserted)"
    )
    combined = Image.new("RGB", (1400, 904), "black")
    combined.paste(decoded_image, (0, 0))
    combined.paste(host_image, (0, 452))
    image_path = Path(str(args.output_prefix) + ".spectrogram.png")
    image_path.parent.mkdir(parents=True, exist_ok=True)
    combined.save(image_path)

    summary = {
        "kind": "jfg-phase8-pcm-analysis",
        "sample_rate": args.rate,
        "decoded_frames": len(pcm),
        "decoded_seconds": len(pcm) / args.rate,
        "decoded_zero_runs_ge_5ms": count_zero_runs(
            pcm, max(1, args.rate // 200)
        ),
        "host_pause_count": len(pauses),
        "host_pause_total_ms": sum(pause_ms),
        "host_pause_max_ms": max(pause_ms, default=0.0),
        "host_pause_median_ms": float(np.median(pause_ms)) if pause_ms else 0.0,
        "host_pause_interval_median_ms": (
            float(np.median(pause_intervals_ms)) if pause_intervals_ms else 0.0
        ),
        "reported_underruns": sum(
            event["event"] == "underrun" for event in events
        ),
        "routine_host_skipping": len(pauses) >= 3,
        "spectrogram": str(image_path),
    }
    summary_path = Path(str(args.output_prefix) + ".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
