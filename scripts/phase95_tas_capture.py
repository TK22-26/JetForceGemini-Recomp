"""Run one bounded Japanese TAS capture in a private BizHawk 2.9.1 worker.

Each output directory is immutable. Resume from a completed prior segment's
savestate, or rerun any segment from movie frame zero after discarding only that
segment's output. Captured RAM probes are deliberately not semantic JP labels.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

from scripts.phase95_bridge import digest, runtime_digest


JP_ROM_SHA1 = "15099233760b36e7afad7da36b9464da1512c4b1"
JP_ROM_SHA256 = "7c62e7fe10747fa038b6854a7db8412d9152c33d75a0ba90b8a208f0ca5c1e07"
MOVIE_SHA256 = "e368d9256caaa9a432645febf7110ae193fd929b521283656962506d13848b9f"
BIZHAWK_291_EXE_SHA256 = "6ce622d4ed4e8460ce362cf35ef67dc70096fec2c9a174cbef6a3e5b04f18bcc"
BIZHAWK_291_RUNTIME_SHA256 = "a93fa6b10ad5f59e15af69766acc0b0e794c8da8ed928b07ddd5fba01c63c175"
MOVIE_FRAMES = 638_477
MAX_SEGMENT_FRAMES = 20_000
HEADER_RE = re.compile(r"^([^ ]+) (.*)$")


def sha1(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha1").hexdigest()


def inspect_movie(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if "Header.txt" not in names or "Input Log.txt" not in names:
            raise ValueError("expected a direct BK2 movie, not a wrapper archive")
        header = {}
        for line in archive.read("Header.txt").decode("utf-8-sig").splitlines():
            match = HEADER_RE.match(line)
            if match:
                header[match[1]] = match[2]
        if (header.get("SHA1", "").lower() != JP_ROM_SHA1 or
                header.get("emuVersion") != "Version 2.9.1" or
                header.get("Platform") != "N64" or
                header.get("Core") != "Mupen64Plus"):
            raise ValueError("movie is not the pinned Japanese BizHawk 2.9.1 TAS")
        count = 0
        with archive.open("Input Log.txt") as stream:
            for line in stream:
                if line.startswith(b"|"):
                    count += 1
        if not 1 <= count <= 1_000_000:
            raise ValueError("invalid movie input length")
        return {"frames": count, "header": header,
                "movie_sha256": digest(path)}


def validate_resume(previous: Path, expected: dict, first: int) -> tuple[Path, str]:
    result = json.loads((previous / "result.json").read_text())
    if not result.get("complete") or result.get("last") != first - 1:
        raise ValueError("resume source is incomplete or noncontiguous")
    for key in ("rom_sha1", "rom_sha256", "movie_sha256", "movie_frames",
                "emulator_sha256", "runtime_sha256", "script_sha256"):
        if result.get(key) != expected.get(key):
            raise ValueError(f"resume identity mismatch: {key}")
    state = previous / "continuation.State"
    if digest(state) != result.get("continuation_sha256"):
        raise ValueError("resume savestate digest mismatch")
    return state, result["continuation_sha256"]


def parse_trace(path: Path, first: int, last: int) -> dict:
    with path.open(encoding="utf-8") as stream:
        if stream.readline() != "schema\t1\n" or \
                stream.readline() != "probe_status\tunverified-jp\n":
            raise ValueError("invalid capture schema or probe labeling")
        columns = stream.readline().rstrip("\n").split("\t")
        if columns[:3] != ["frame", "movie_mode", "input_polls_since_worker_start"]:
            raise ValueError("invalid trace columns")
        previous = first - 1
        count = 0
        for line in stream:
            cells = line.rstrip("\n").split("\t")
            if len(cells) != len(columns) or int(cells[0]) != previous + 1:
                raise ValueError("missing or malformed capture frame")
            if cells[1] not in ("PLAY", "FINISHED"):
                raise ValueError("movie left playback")
            previous = int(cells[0])
            count += 1
    if previous != last or count != last - first + 1:
        raise ValueError("capture did not cover requested interval")
    return {"captured_frames": count, "last_movie_mode": cells[1]}


def capture(output: Path, emulator: Path, rom: Path, movie: Path, *,
            first: int, last: int, interval: int = 10_000,
            resume_from: Path | None = None, timeout: int = 3600,
            full_rdram: bool = False) -> dict:
    output, emulator, rom, movie = (Path(p).resolve() for p in
                                    (output, emulator, rom, movie))
    if output.exists():
        raise FileExistsError(output)
    if emulator.name.lower() != "emuhawk.exe" or not emulator.is_file():
        raise ValueError("expected a pinned BizHawk EmuHawk.exe")
    if not 1 <= interval <= MAX_SEGMENT_FRAMES or not 0 <= first <= last or \
            last - first + 1 > MAX_SEGMENT_FRAMES or timeout < 1:
        raise ValueError("invalid bounded capture request")
    movie_info = inspect_movie(movie)
    if movie_info["movie_sha256"] != MOVIE_SHA256 or \
            movie_info["frames"] != MOVIE_FRAMES:
        raise ValueError("movie bytes or length differ from the synchronized TAS")
    if last >= movie_info["frames"]:
        raise ValueError("capture extends beyond the movie")
    if sha1(rom) != JP_ROM_SHA1 or digest(rom) != JP_ROM_SHA256:
        raise ValueError("ROM does not match pinned movie ROM hashes")
    if first and resume_from is None or not first and resume_from is not None:
        raise ValueError("nonzero first frame requires a prior segment")
    script = Path(__file__).with_suffix(".lua").resolve()
    identity = {"rom_sha1": JP_ROM_SHA1, "rom_sha256": digest(rom),
                "movie_sha256": movie_info["movie_sha256"],
                "movie_frames": movie_info["frames"],
                "emulator_sha256": digest(emulator),
                "runtime_sha256": runtime_digest(emulator.parent),
                "script_sha256": digest(script)}
    if (identity["emulator_sha256"] != BIZHAWK_291_EXE_SHA256 or
            identity["runtime_sha256"] != BIZHAWK_291_RUNTIME_SHA256):
        raise ValueError("emulator runtime differs from synchronized BizHawk 2.9.1")
    state = None
    parent_continuation_sha256 = None
    if resume_from is not None:
        state, parent_continuation_sha256 = validate_resume(
            Path(resume_from).resolve(), identity, first)
    # Never use the viewer's writable directory, SaveRAM, or state directories.
    output.mkdir(parents=True)
    isolated = output / "emulator"
    shutil.copytree(emulator.parent, isolated,
                    ignore=shutil.ignore_patterns("SaveRAM", "State", "States",
                                                  "Movies", "*.SaveRAM",
                                                  "config.ini"))
    config = isolated / "config.ini"
    # The synchronized viewer used archive defaults, with no config.ini.
    # Discard any later viewer-generated config rather than inheriting a
    # mutable UI/core setting from the user's ongoing session.
    if config.exists():
        raise ValueError("isolated worker unexpectedly inherited config.ini")
    identity["worker_config_sha256"] = None
    manifest = {"kind": "jfg-phase95-jp-tas-capture", "schema": 1,
                "semantic_status": "raw-unverified-jp", "first": first,
                "last": last, "checkpoint_interval": interval,
                "checkpoint_artifact": "screenshot",
                "full_rdram": full_rdram,
                "source_emulator": str(emulator), "source_rom": str(rom),
                "source_movie": str(movie), "resume_from": str(resume_from)
                if resume_from is not None else None,
                "parent_continuation_sha256": parent_continuation_sha256,
                **identity}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    environment = os.environ.copy()
    environment.update(JFG_TAS_CAPTURE_ROOT=str(output),
                       JFG_TAS_CAPTURE_FIRST=str(first),
                       JFG_TAS_CAPTURE_LAST=str(last),
                       JFG_TAS_CAPTURE_PREVIOUS=str(first - 1),
                       JFG_TAS_CAPTURE_INTERVAL=str(interval),
                       JFG_TAS_CAPTURE_MOVIE_LENGTH=str(movie_info["frames"]))
    environment["JFG_TAS_CAPTURE_FULL_RDRAM"] = "1" if full_rdram else "0"
    if state is not None:
        environment["JFG_TAS_CAPTURE_RESUME_STATE"] = str(state)
    else:
        environment.pop("JFG_TAS_CAPTURE_RESUME_STATE", None)
    startup = None
    if os.name == "nt":
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = subprocess.SW_HIDE
    command = [str(isolated / emulator.name), f"--movie={movie}", str(rom),
               f"--lua={script}"]
    with (output / "stdout.log").open("wb") as stdout, \
            (output / "stderr.log").open("wb") as stderr:
        process = subprocess.Popen(command, cwd=isolated, env=environment,
                                   stdout=stdout, stderr=stderr,
                                   startupinfo=startup,
                                   creationflags=getattr(subprocess,
                                                         "CREATE_NO_WINDOW", 0))
        (output / "process.json").write_text(json.dumps({"pid": process.pid,
            "owned_worker": True}, indent=2) + "\n")
        try:
            exit_code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.terminate()  # Only this Popen-owned isolated process.
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=30)
            exit_code = -1
    result = {**manifest, "exit_code": exit_code, "complete": False}
    try:
        done = dict(line.split("\t", 1) for line in
                    (output / "done.tsv").read_text().splitlines())
        if done != {"schema": "1", "first": str(first), "last": str(last),
                    "movie_length": str(movie_info["frames"])}:
            raise ValueError("capture completion marker mismatch")
        result.update(parse_trace(output / "frames.tsv", first, last))
        result["continuation_sha256"] = digest(output / "continuation.State")
        result["complete"] = exit_code == 0
    except (FileNotFoundError, ValueError, OSError) as error:
        result["validation_error"] = str(error)
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    if not result["complete"]:
        raise RuntimeError(f"TAS capture failed or incomplete: {output}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--movie", type=Path, required=True)
    parser.add_argument("--first", type=int, default=0)
    parser.add_argument("--last", type=int, required=True)
    parser.add_argument("--interval", type=int, default=10_000)
    parser.add_argument("--resume-from", type=Path)
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--full-rdram", action="store_true")
    args = parser.parse_args()
    print(json.dumps(capture(args.output, args.emulator, args.rom, args.movie,
                             first=args.first, last=args.last,
                             interval=args.interval,
                             resume_from=args.resume_from,
                             timeout=args.timeout,
                             full_rdram=args.full_rdram)))


if __name__ == "__main__":
    main()
