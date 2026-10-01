"""Export the selected oracle controller-poll path through checkpoint restores.

This produces input-v2 in native replay-by-poll order. It does not establish
native/oracle initial-save equivalence or native state parity by itself.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


HEADER = "jfg-phase8-input-v2"
MAX_SAMPLES = 65536


class LineageError(ValueError):
    pass


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _checkpoint_polls(path):
    checkpoint = json.loads(path.read_text())
    if checkpoint.get("kind") != "jfg-phase95-checkpoint" or checkpoint.get("schema") != 1:
        raise LineageError(f"invalid checkpoint manifest: {path}")
    polls = checkpoint.get("observation", {}).get("polls")
    if type(polls) is not int or polls < 0:
        raise LineageError(f"invalid checkpoint poll count: {path}")
    return polls


def selected_polls(root, *, stop_slot=None, visited=None):
    """Return exact selected samples and source workers up to a saved slot/end."""
    root = Path(root).resolve()
    visited = set() if visited is None else visited
    if root in visited:
        raise LineageError("checkpoint lineage cycle")
    visited.add(root)
    poll_log = root / "input-polls.tsv"
    rows = poll_log.read_text().splitlines()
    if not rows or rows[0].split("\t")[:2] != ["schema", "1"]:
        raise LineageError(f"unsupported oracle poll log: {poll_log}")
    session = rows[0].split("\t")
    if len(session) != 4 or session[2] != "session" or not session[3]:
        raise LineageError(f"invalid oracle poll session: {poll_log}")
    samples = []
    workers = []
    imported = root / "import-lineage.json"
    if imported.exists():
        lineage = json.loads(imported.read_text())
        source = Path(lineage["source_manifest"]).resolve()
        if _digest(source) != lineage["source_manifest_sha256"]:
            raise LineageError("imported checkpoint manifest changed")
        if source.parent == root or not source.name.startswith("checkpoint-") or source.suffix != ".json":
            raise LineageError("invalid imported checkpoint path")
        slot = source.stem[len("checkpoint-"):]
        samples, workers = selected_polls(source.parent, stop_slot=slot, visited=visited)
        if len(samples) != _checkpoint_polls(source):
            raise LineageError("imported checkpoint poll count differs from lineage")
    checkpoints = {}
    imported_loads = 0
    for lineno, line in enumerate(rows[1:], 2):
        parts = line.split("\t")
        if parts[0] == "checkpoint":
            if len(parts) != 4 or parts[2] not in ("save", "load") or not parts[3]:
                raise LineageError(f"invalid checkpoint event at {poll_log}:{lineno}")
            _, _, operation, slot = parts
            if operation == "save":
                if slot in checkpoints:
                    raise LineageError(f"duplicate checkpoint save: {slot}")
                side = (root / f"checkpoint-{slot}.side").read_text().split()
                if len(side) != 3 or side[0] != session[3] or int(side[1]) != len(samples):
                    raise LineageError(f"checkpoint side poll count differs: {slot}")
                checkpoints[slot] = list(samples)
                if slot == stop_slot:
                    manifest = root / f"checkpoint-{slot}.json"
                    if len(samples) != _checkpoint_polls(manifest):
                        raise LineageError(f"checkpoint manifest poll count differs: {slot}")
                    return samples, [*workers, str(root)]
            elif slot == "f0" and imported.exists() and imported_loads == 0:
                side = (root / "checkpoint-f0.side").read_text().split()
                if len(side) != 3 or side[0] != session[3] or int(side[1]) != len(samples):
                    raise LineageError("imported side poll count differs")
                imported_loads += 1
            elif slot in checkpoints:
                samples = list(checkpoints[slot])
            else:
                raise LineageError(f"unresolved checkpoint load: {slot}")
            continue
        if len(parts) != 6:
            raise LineageError(f"invalid poll row at {poll_log}:{lineno}")
        try:
            poll, frame, sequence, buttons, x, y = map(int, parts)
        except ValueError as error:
            raise LineageError(f"noninteger poll row at {poll_log}:{lineno}") from error
        if (poll != len(samples) + 1 or frame < 0 or sequence < 0 or
                not 0 <= buttons <= 65535 or not -128 <= x <= 127 or
                not -128 <= y <= 127):
            raise LineageError(f"poll order or controller sample invalid at {poll_log}:{lineno}")
        samples.append((buttons, x, y))
        if len(samples) > MAX_SAMPLES:
            raise LineageError("selected poll path exceeds native replay event limit")
    if stop_slot is not None:
        raise LineageError(f"checkpoint save absent in poll log: {stop_slot}")
    if imported.exists() and imported_loads != 1:
        raise LineageError("imported checkpoint was not loaded exactly once")
    return samples, [*workers, str(root)]


def export(root, output, *, initial_flash=None, initial_pak=None):
    root = Path(root).resolve()
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    if (initial_flash is None) != (initial_pak is None):
        raise ValueError("initial flash and pak must be supplied together")
    if initial_flash is not None:
        initial_flash, initial_pak = Path(initial_flash), Path(initial_pak)
        if initial_flash.stat().st_size != 0x20000 or initial_pak.stat().st_size != 32:
            raise LineageError("initial flash or pak has unexpected size")
    if (root / "bridge-result.txt").read_text() != "stopped\n":
        raise LineageError("source worker did not stop cleanly")
    samples, workers = selected_polls(root)
    if not samples:
        raise LineageError("selected poll path is empty")
    observations = (root / "observations.jsonl").read_text().splitlines()
    if not observations:
        raise LineageError("source worker has no final observation")
    final = json.loads(observations[-1])
    frame = final.get("frame")
    if (type(frame) is not int or frame < len(samples) or
            final.get("polls") != len(samples)):
        raise LineageError("final observation does not match selected input path")
    output.mkdir(parents=True)
    replay = output / "controller.input"
    with replay.open("w", newline="\n") as stream:
        stream.write(HEADER + "\n")
        for index, (buttons, x, y) in enumerate(samples):
            # Replay-by-poll indexes records, not their retrace intervals.
            end = frame if index == len(samples) - 1 else index + 1
            stream.write(f"{index},{end},1,{buttons:04x},{x},{y}\n")
    initial = None
    if initial_flash is not None:
        shutil.copyfile(initial_flash, output / "initial.flash")
        shutil.copyfile(initial_pak, output / "initial.pak")
        initial = {"flash_source": str(initial_flash.resolve()),
                   "flash_sha256": _digest(output / "initial.flash"),
                   "pak_source": str(initial_pak.resolve()),
                   "pak_sha256": _digest(output / "initial.pak"),
                   "oracle_save_equivalence": "not_verified"}
    manifest = {"kind": "jfg-phase95-selected-input-export", "schema": 1,
                "acceptance": False, "source_worker": str(Path(root).resolve()),
                "lineage_workers": workers, "controller_polls": len(samples),
                "oracle_final_frame": frame,
                "input_sha256": _digest(replay), "native_mode": "replay-by-poll",
                "native_comparison": "not_run",
                "initial_state": initial,
                "limitations": "oracle/native initial-save equivalence, frame alignment, and state parity not yet verified"}
    (output / "export-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("worker", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--initial-flash", type=Path)
    parser.add_argument("--initial-pak", type=Path)
    args = parser.parse_args()
    print(json.dumps(export(args.worker, args.output,
                            initial_flash=args.initial_flash, initial_pak=args.initial_pak)))


if __name__ == "__main__":
    main()
