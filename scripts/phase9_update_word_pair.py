"""Capture and compare one guest word at every completed native/oracle update."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts import phase95_native_replay, phase95_oracle_replay
from scripts.phase9_poll_semantic_pair import (
    PRIVATE_ROOT, ROOT, _existing_side, _plan, write_json_atomic,
)
from scripts.phase95_bridge import digest, runtime_digest
from scripts.phase9_update_alignment import analyze as analyze_updates
from scripts.phase9_update_word import (
    compare as compare_word, read as read_word, validate_update_word,
)


KIND = "jfg-phase9-update-word-pair"
CAPABILITY_MARKER = b"JFG_PHASE9_UPDATE_WORD"


def native_capable(executable: Path) -> bool:
    tail = b""
    with Path(executable).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            joined = tail + chunk
            if CAPABILITY_MARKER in joined:
                return True
            tail = joined[-(len(CAPABILITY_MARKER) - 1):]
    return False


def _side(path: Path, side: str, plan: dict) -> dict | None:
    result = _existing_side(path, side, plan)
    if result is None:
        return None
    address = int(plan["update_word"], 16)
    rows = read_word(path / "update-word.tsv", address)
    if (result.get("update_word") != plan["update_word"] or
            result.get("update_word_trace_complete") is not True or
            result.get("update_word_trace_sha256") != digest(
                path / "update-word.tsv") or
            len(rows) != result.get("completed_update_count") or
            (side == "oracle" and
             result.get("vi_consumed_trace_complete") is not True)):
        raise ValueError(f"existing {side} update-word trace changed")
    return result


def run(output: Path, source: Path, executable: Path, emulator: Path,
        rom: Path, rom_sha256: str, *, address: int, target: int,
        timeout: int = 600) -> dict:
    output, source, executable, emulator, rom = (
        Path(value).resolve() for value in
        (output, source, executable, emulator, rom))
    private = PRIVATE_ROOT.resolve(strict=True)
    if (not output.is_relative_to(private) or output == private or
            output.is_relative_to(source) or source.is_relative_to(output) or
            output.is_relative_to(emulator.parent) or
            emulator.parent.is_relative_to(output)):
        raise ValueError("update-word output must be disjoint and private")
    for path in (source, executable, emulator, rom):
        if not path.exists():
            raise ValueError(f"missing update-word input: {path}")
    if not native_capable(executable):
        raise ValueError("native executable lacks update-word trace support")
    address = validate_update_word(address, True)
    plan = _plan(source, executable, emulator, rom, rom_sha256, target, timeout)
    plan.update(kind=KIND, update_word=f"0x{address:08x}",
                native_runtime_sha256=runtime_digest(executable.parent))
    plan["tool_sha256"].update({name: digest(ROOT / name) for name in (
        "scripts/phase9_update_word_pair.py",
        "scripts/phase9_update_word.py",
        "scripts/phase9_update_alignment.py",
        "scripts/compare_phase9_update_hashes.py")})
    if output.exists():
        path = output / "plan.json"
        if (not path.is_file() or
                json.loads(path.read_text(encoding="utf-8")) != plan):
            raise ValueError("existing update-word output has no matching plan")
    else:
        output.mkdir(parents=True)
        write_json_atomic(output / "plan.json", plan)
    native_dir, oracle_dir = output / "native", output / "oracle"
    if _side(native_dir, "native", plan) is None:
        phase95_native_replay.replay(
            source, native_dir, executable, rom, rom_sha256,
            target_retraces=target, timeout=timeout, update_hashes=True,
            poll_hashes=True, update_word=address)
        _side(native_dir, "native", plan)
    if _side(oracle_dir, "oracle", plan) is None:
        phase95_oracle_replay.replay(
            oracle_dir, emulator, rom, rom_sha256, source,
            target_frame=target, timeout=timeout, vi_trace=True,
            update_hashes=True, poll_hashes=True, domain_inventory=True,
            update_word=address)
        _side(oracle_dir, "oracle", plan)
    word_report = compare_word(native_dir / "update-word.tsv",
                               oracle_dir / "update-word.tsv", address)
    update_report = analyze_updates(
        native_dir / "retrace-hashes.jsonl.updates.jsonl",
        oracle_dir / "update-hashes.jsonl")
    for name, value in (("word-report.json", word_report),
                        ("update-alignment.json", update_report)):
        path = output / name
        if path.exists():
            if json.loads(path.read_text(encoding="utf-8")) != value:
                raise ValueError(f"existing {name} changed")
        else:
            write_json_atomic(path, value)
    result = {
        "kind": KIND, "schema": 1, "complete": True,
        "plan_sha256": digest(output / "plan.json"),
        "native_result_sha256": digest(native_dir / "native-result.json"),
        "oracle_result_sha256": digest(oracle_dir / "oracle-result.json"),
        "word_report_sha256": digest(output / "word-report.json"),
        "update_alignment_sha256": digest(output / "update-alignment.json"),
        "first_word_difference": word_report["first_difference"],
        "matching_update_prefix": update_report["matching_update_prefix"],
        "first_update_state_difference": update_report[
            "first_semantic_difference"],
        "alignment_validated": False, "parity_verified": False,
    }
    path = output / "pair-result.json"
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != result:
            raise ValueError("existing update-word pair result changed")
    else:
        write_json_atomic(path, result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    parser.add_argument("--address", type=lambda value: int(value, 0),
                        required=True)
    parser.add_argument("--target", type=int, default=1500)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.source, args.executable,
                         args.emulator, args.rom, args.rom_sha256,
                         address=args.address, target=args.target,
                         timeout=args.timeout), sort_keys=True))


if __name__ == "__main__":
    main()
