"""Recover a selected navigation continuation with exact per-action evidence checks."""
import argparse
import hashlib
import json
from pathlib import Path

from scripts.phase95_bridge import Action, Worker, digest
from scripts.phase95_exit import cross
from scripts.phase95_observation import ObservationError


def recover(worker, selected):
    actions = [Action(**item) for item in selected["actions"]]
    expected = selected["trajectory"]
    if not 1 <= len(actions) <= 8 or len(expected) != len(actions):
        raise ValueError("invalid selected continuation")
    for action in actions:
        action.validate()
        if not action.frames:
            raise ValueError("stop is not a replay action")
    for wanted in expected:
        checksum = wanted.get("sha256", "")
        if not isinstance(checksum, str) or len(checksum) != 64 or any(c not in "0123456789abcdef" for c in checksum):
            raise ValueError("invalid recovery digest")
        if any(type(wanted.get(key)) is not int or wanted[key] < 0
               for key in ("frame", "polls", "player")) or wanted["player"] > 0xFFFFFFFF:
            raise ValueError("invalid recovery counters")
    for index, (action, wanted) in enumerate(zip(actions, expected)):
        worker.act(action)
        metadata, memory = worker.observe()
        equal = hashlib.sha256(memory).hexdigest() == wanted["sha256"] and all(
            metadata[key] == wanted[key] for key in ("frame", "polls", "player"))
        with (worker.root / "recovery.jsonl").open("a") as stream:
            stream.write(json.dumps({"step": index, "equal": equal, "actual": metadata,
                                    "sha256": hashlib.sha256(memory).hexdigest()}) + "\n")
        if not equal:
            raise ObservationError("selected recovery differs from recorded trajectory")
    worker.checkpoint("save", "f1")
    worker.observe()
    (worker.root / "recovery-result.json").write_text(json.dumps({
        "kind": "jfg-phase95-selected-recovery", "acceptance": False,
        "steps": len(actions), "exact": True}) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--selected-journal", type=Path, required=True)
    parser.add_argument("--exit-id")
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    args = parser.parse_args()
    selected = json.loads(args.selected_journal.read_text().splitlines()[-1])
    with Worker(args.output, args.emulator, args.rom,
                Path(__file__).with_name("phase95_bizhawk_bridge.lua"), args.rom_sha256) as worker:
        worker.observe()
        worker.import_checkpoint(args.checkpoint)
        (worker.root / "recovery-source.json").write_text(json.dumps({
            "journal": str(args.selected_journal.resolve()), "sha256": digest(args.selected_journal),
            "selected": selected}, indent=2))
        recover(worker, selected)
        if args.exit_id:
            cross(worker, exit_id=args.exit_id)


if __name__ == "__main__":
    main()
