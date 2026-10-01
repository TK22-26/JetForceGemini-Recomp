"""Render one sealed US-oracle checkpoint in an isolated diagnostic BizHawk.

The screenshot is for route inspection only. It does not advance gameplay,
produce controller input, or establish native/oracle parity.
"""

import argparse
import json
from pathlib import Path
import shutil
import time

from scripts.autonomy.supervisor import bounded_command
from scripts.phase95_bridge import (digest, isolate_n64_bindings, runtime_digest,
                                    validate_checkpoint)


PRIVATE_ROOT = Path(__file__).resolve().parents[1] / "tools" / "private"
SCRIPT = Path(__file__).with_suffix(".lua")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def capture(checkpoint: Path, output: Path, emulator: Path, rom: Path,
            rom_sha256: str, *, private_root: Path = PRIVATE_ROOT,
            command_runner=bounded_command) -> dict:
    checkpoint, output, emulator, rom = (Path(path).resolve() for path in
                                          (checkpoint, output, emulator, rom))
    private_root = Path(private_root).resolve()
    if not checkpoint.is_relative_to(private_root) or \
            not output.is_relative_to(private_root) or output.exists():
        raise ValueError("visual probe needs a fresh private output and checkpoint")
    if not emulator.is_file() or not rom.is_file() or digest(rom) != rom_sha256:
        raise ValueError("visual probe ROM or emulator pin mismatch")
    source = json.loads(checkpoint.read_text())
    identity = source.get("identity")
    if not isinstance(identity, dict) or identity.get("rom_sha256") != rom_sha256:
        raise ValueError("visual probe checkpoint ROM differs")
    source = validate_checkpoint(checkpoint, identity)
    if digest(emulator) != identity.get("emulator_sha256"):
        raise ValueError("visual probe emulator binary differs")
    output.mkdir(parents=True, exist_ok=False)
    isolated = output / "emulator"
    shutil.copytree(emulator.parent, isolated,
                    ignore=shutil.ignore_patterns("SaveRAM", "State", "States"))
    config = isolated / "config.ini"
    settings = json.loads(config.read_text(encoding="utf-8-sig"))
    for entry in settings.get("PathEntries", {}).get("Paths", []):
        configured = Path(entry.get("Path", ""))
        if configured.is_absolute() or ".." in configured.parts:
            raise ValueError("visual probe emulator path is not isolated")
    config.write_text(json.dumps(isolate_n64_bindings(settings), indent=2) + "\n",
                      encoding="utf-8")
    if (digest(config) != identity.get("config_sha256") or
            runtime_digest(isolated) != identity.get("runtime_sha256")):
        raise ValueError("visual probe emulator runtime differs")
    visual_environment = {
        "JFG_PHASE95_VISUAL_ROOT": str(output),
        "JFG_PHASE95_VISUAL_STATE": str(checkpoint.with_suffix(".State")),
    }
    # bounded_command starts an isolated child and owns its termination.
    code, reason = command_runner(
        [str(isolated / emulator.name), str(rom), f"--lua={SCRIPT}"],
        Path(__file__).resolve().parents[1], output / "stdout.log",
        output / "stderr.log", time.monotonic() + 180, lambda: None,
        output / "PAUSED", environment_overrides=visual_environment,
        memory_limit_bytes=8 * 1024**3, cpu_seconds=600,
        minimum_free_bytes=50 * 1024**3, output_tree=output,
        max_output_tree_bytes=4 * 1024**3)
    if code != 0 or reason is not None or \
            (output / "visual-status.txt").read_text() != "captured\n":
        raise RuntimeError(f"visual probe stopped: {reason or code}; see {output}")
    memory = output / "visual.rdram"
    picture = output / "visual.png"
    if memory.stat().st_size != 0x400000 or digest(memory) != source["rdram_sha256"]:
        raise ValueError("visual probe checkpoint RDRAM changed")
    with picture.open("rb") as stream:
        signature = stream.read(8)
    if picture.stat().st_size <= 100 or signature != PNG_SIGNATURE:
        raise ValueError("visual probe screenshot is not PNG")
    result = {"kind": "jfg-phase95-checkpoint-visual", "schema": 1,
              "acceptance": False, "read_only": True,
              "source_checkpoint": str(checkpoint),
              "source_checkpoint_sha256": digest(checkpoint),
              "source_rdram_sha256": source["rdram_sha256"],
              "emulator_sha256": digest(emulator), "rom_sha256": rom_sha256,
              "visual_script_sha256": digest(SCRIPT),
              "screenshot_sha256": digest(picture),
              "frame": source["observation"]["frame"]}
    (output / "visual-result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(capture(args.checkpoint, args.output, args.emulator,
                             args.rom, args.rom_sha256)))


if __name__ == "__main__":
    main()
