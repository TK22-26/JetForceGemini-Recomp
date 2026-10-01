"""Supervised file transport for a private, isolated Phase 9.5 BizHawk worker."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.autonomy.process_guard import WorkerJob


@dataclass(frozen=True)
class Action:
    frames: int = 1
    buttons: int = 0
    x: int = 0
    y: int = 0

    def validate(self) -> None:
        for value, lower, upper in ((self.frames, 0, 120),
                                    (self.buttons, 0, 65535),
                                    (self.x, -128, 127), (self.y, -128, 127)):
            if type(value) is not int or not lower <= value <= upper:
                raise ValueError("invalid bounded controller action")
        if self.frames == 0 and (self.buttons or self.x or self.y):
            raise ValueError("stop action must be neutral")

    def encode(self, session: str, sequence: int) -> str:
        self.validate()
        if not session or any(c not in "0123456789abcdef" for c in session):
            raise ValueError("invalid session")
        if type(sequence) is not int or sequence < 0:
            raise ValueError("invalid sequence")
        return (f"phase95-v1 {session} {sequence} {self.frames} "
                f"{self.buttons} {self.x} {self.y}\n")


def parse_ready(text: str, session: str, sequence: int) -> dict:
    parts = text.split()
    if len(parts) != 6 or parts[:2] != ["phase95-v1", session]:
        raise ValueError("invalid observation header/session")
    if any(not value.isascii() or not value.isdecimal() for value in parts[2:]):
        raise ValueError("invalid observation counters")
    seq, frame, polls, player = map(int, parts[2:])
    if seq != sequence or player > 0xFFFFFFFF:
        raise ValueError("stale observation or invalid player pointer")
    return dict(sequence=seq, frame=frame, polls=polls, player=player)


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def runtime_digest(root: Path) -> str:
    entries = [(path.relative_to(root).as_posix(), digest(path))
               for path in sorted(root.rglob("*"))
               if path.is_file() and path.suffix.lower() in (".exe", ".dll")]
    return hashlib.sha256(json.dumps(entries, separators=(",", ":")).encode()).hexdigest()


def isolate_n64_bindings(settings: dict) -> dict:
    """Remove physical host input only in a worker's private config copy."""
    isolated = json.loads(json.dumps(settings))
    name = "Nintendo 64 Controller"
    for category in ("AllTrollers", "AllTrollersAutoFire"):
        mapping = isolated.get(category, {}).get(name, {})
        for button in mapping:
            mapping[button] = ""
    for binding in isolated.get("AllTrollersAnalog", {}).get(name, {}).values():
        binding["Value"] = ""
        binding["ButtonBindPositive"] = None
        binding["ButtonBindNegative"] = None
    return isolated


def validate_checkpoint(path: Path, identity: dict) -> dict:
    checkpoint = json.loads(path.read_text())
    if checkpoint.get("kind") != "jfg-phase95-checkpoint" or checkpoint.get("schema") != 1:
        raise ValueError("unsupported checkpoint manifest")
    for key in ("rom_sha256", "runtime_sha256", "config_sha256", "script_sha256"):
        if not identity.get(key) or checkpoint.get("identity", {}).get(key) != identity[key]:
            raise ValueError(f"incompatible checkpoint {key}")
    for suffix in ("State", "side"):
        if digest(path.with_suffix("." + suffix)) != checkpoint.get("digests", {}).get(suffix):
            raise ValueError(f"checkpoint {suffix} digest mismatch")
    return checkpoint


class Worker:
    """One owned process; unique output root; no access to shared saved games."""

    def __init__(self, root: Path, emulator: Path, rom: Path, script: Path,
                 expected_rom_sha256: str, timeout: float = 60):
        if digest(rom) != expected_rom_sha256:
            raise ValueError("ROM identity mismatch")
        if not 1 <= timeout <= 300:
            raise ValueError("invalid worker timeout")
        root = root.resolve()
        root.mkdir(parents=True, exist_ok=False)
        self.root, self.timeout = root, timeout
        self.session, self.sequence = uuid.uuid4().hex, 0
        self.observed = False
        self.pending_checkpoint = None
        self.process = None
        self.guard = None
        self.logs = []
        # Copy executable/runtime assets, never an existing worker's saves.
        isolated = root / "emulator"
        shutil.copytree(emulator.parent, isolated,
                        ignore=shutil.ignore_patterns("SaveRAM", "State", "States"))
        config = isolated / "config.ini"
        # Relative paths in the pinned config resolve inside this copied worker.
        settings = json.loads(config.read_text(encoding="utf-8-sig"))
        for entry in settings.get("PathEntries", {}).get("Paths", []):
            configured = Path(entry.get("Path", ""))
            if configured.is_absolute() or ".." in configured.parts:
                raise ValueError("absolute emulator data path is not isolated")
        settings = isolate_n64_bindings(settings)
        config.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
        manifest = dict(kind="jfg-phase95-worker", schema=1, session=self.session,
                        rom_sha256=expected_rom_sha256,
                        emulator_sha256=digest(isolated / emulator.name),
                        config_sha256=digest(config), script_sha256=digest(script),
                        runtime_sha256=runtime_digest(isolated),
                        acceptance=False, initial_save="fresh isolated worker")
        (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        self.identity = manifest
        env = os.environ.copy()
        env.update(JFG_PHASE95_ROOT=str(root), JFG_PHASE95_SESSION=self.session)
        self.logs = [(root / name).open("wb") for name in ("stdout.log", "stderr.log")]
        try:
            self.guard = WorkerJob(memory_limit_bytes=8 * 1024 * 1024 * 1024)
            self.process = subprocess.Popen(
                [str(isolated / emulator.name), str(rom.resolve()), f"--lua={script.resolve()}"],
                cwd=isolated, env=env, stdout=self.logs[0], stderr=self.logs[1],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.guard.assign(self.process)
        except BaseException:
            self.close()
            raise
        (root / "process.json").write_text(json.dumps({"pid": self.process.pid,
                                                      "session": self.session}))

    def observe(self) -> tuple[dict, bytes]:
        deadline = time.monotonic() + self.timeout
        ready = self.root / "ready.txt"
        while True:
            if self.process.poll() is not None:
                raise RuntimeError(f"oracle exited {self.process.returncode}; see {self.root}")
            if time.monotonic() >= deadline:
                raise TimeoutError("oracle observation timeout")
            try:
                # Windows can briefly deny access even after publication. Retry
                # this same observation, never resend input or restart the core.
                header = ready.read_text()
                memory = (self.root / "observation.rdram").read_bytes()
            except (FileNotFoundError, PermissionError):
                time.sleep(0.01)
                continue
            break
        metadata = parse_ready(header, self.session, self.sequence)
        if len(memory) != 0x400000:
            raise ValueError("incomplete RDRAM observation")
        if not self.observed:
            with (self.root / "observations.jsonl").open("a") as log:
                log.write(json.dumps({**metadata,
                    "rdram_sha256": hashlib.sha256(memory).hexdigest()}) + "\n")
        self.observed = True
        if self.pending_checkpoint is not None:
            slot, parent_sequence = self.pending_checkpoint
            stem = self.root / f"checkpoint-{slot}"
            seal = {"kind": "jfg-phase95-checkpoint", "schema": 1,
                    "identity": self.identity, "source_sequence": parent_sequence,
                    "observation": metadata,
                    "rdram_sha256": hashlib.sha256(memory).hexdigest(),
                    "digests": {suffix: digest(stem.with_suffix("." + suffix))
                                for suffix in ("State", "side")}}
            stem.with_suffix(".json").write_text(json.dumps(seal, indent=2) + "\n")
            self.pending_checkpoint = None
        return metadata, memory

    def act(self, action: Action) -> None:
        encoded = action.encode(self.session, self.sequence)
        self._submit(encoded)

    def checkpoint(self, operation: str, slot: str) -> None:
        if operation not in ("save", "load") or not 1 <= len(slot) <= 32 or any(
                char not in "0123456789abcdef" for char in slot):
            raise ValueError("invalid checkpoint request")
        parent_sequence = self.sequence
        self._submit(f"phase95-state {self.session} {self.sequence} {operation} {slot}\n")
        if operation == "save":
            self.pending_checkpoint = (slot, parent_sequence)

    def import_checkpoint(self, path: Path) -> None:
        """Import a sealed oracle state into this isolated worker, preserving lineage."""
        checkpoint = validate_checkpoint(path, self.identity)
        if not self.observed:
            raise RuntimeError("observe worker before checkpoint import")
        destination = self.root / "checkpoint-f0"
        if destination.with_suffix(".State").exists():
            raise ValueError("checkpoint import slot already used")
        shutil.copyfile(path.with_suffix(".State"), destination.with_suffix(".State"))
        side = path.with_suffix(".side").read_text().split()
        if len(side) != 3 or not all(value.isdecimal() for value in side[1:]):
            raise ValueError("invalid checkpoint side state")
        destination.with_suffix(".side").write_text(
            f"{self.session} {side[1]} {side[2]}\n", newline="\n")
        (self.root / "import-lineage.json").write_text(json.dumps({
            "source_manifest": str(path.resolve()), "source_manifest_sha256": digest(path),
            "checkpoint": checkpoint}, indent=2) + "\n")
        self.checkpoint("load", "f0")
        metadata, memory = self.observe()
        if hashlib.sha256(memory).hexdigest() != checkpoint["rdram_sha256"] or any(
                metadata[key] != checkpoint["observation"][key] for key in ("frame", "polls", "player")):
            raise RuntimeError("imported checkpoint state does not match sealed observation")

    def _submit(self, encoded: str) -> None:
        ready = self.root / "ready.txt"
        if not self.observed or not ready.exists() or (self.root / "command.txt").exists():
            raise RuntimeError("action requires an acknowledged observation")
        parse_ready(ready.read_text(), self.session, self.sequence)
        with (self.root / "actions.jsonl").open("a") as log:
            log.write(json.dumps({"sequence": self.sequence, "command": encoded}) + "\n")
        ready.unlink()
        temporary = self.root / "command.tmp"
        temporary.write_text(encoded, newline="\n")
        temporary.replace(self.root / "command.txt")
        self.sequence += 1
        self.observed = False

    def close(self) -> None:
        if self.process is not None and self.process.poll() is None:
            try:
                if (self.root / "ready.txt").exists():
                    if not self.observed:
                        self.observe()
                    self.act(Action(frames=0))
                    self.process.wait(timeout=5)
            except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
                pass
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
        for stream in self.logs:
            stream.close()
        if self.guard is not None:
            self.guard.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    parser.add_argument("--probe-frames", type=int, default=60)
    parser.add_argument("--checkpoint-probe", action="store_true")
    args = parser.parse_args()
    action = Action(args.probe_frames)
    action.validate()
    if action.frames == 0:
        parser.error("probe frames must be positive")
    with Worker(args.output, args.emulator, args.rom,
                Path(__file__).with_name("phase95_bizhawk_bridge.lua"),
                args.rom_sha256) as worker:
        first, _ = worker.observe()
        if args.checkpoint_probe:
            worker.act(Action(120))
            first, _ = worker.observe()
            worker.checkpoint("save", "01")
            worker.observe()
        worker.act(action)
        last, memory = worker.observe()
        if last["frame"] - first["frame"] != action.frames:
            raise RuntimeError("bounded frame action did not advance exactly")
        result = {"kind": "jfg-phase95-bridge-probe", "acceptance": False,
                  "first": first, "last": last, "exact_frame_step": True}
        if args.checkpoint_probe:
            worker.checkpoint("load", "01")
            restored, _ = worker.observe()
            worker.act(action)
            repeated, repeated_memory = worker.observe()
            result["restore_frame"] = restored["frame"]
            result["continuation_equal"] = memory == repeated_memory and all(
                last[key] == repeated[key] for key in ("frame", "polls", "player"))
            result["continuation_sha256"] = hashlib.sha256(memory).hexdigest()
            if not result["continuation_equal"]:
                (worker.root / "checkpoint-failure.json").write_text(json.dumps(result))
                raise RuntimeError("checkpoint continuation differs")
        (worker.root / "probe.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
