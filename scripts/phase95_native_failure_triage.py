"""Preserve and probe a failed Phase 9.5 native replay without an AI service.

The last flushed retrace is a useful *hint*, not proof of the first bad frame.
Prefix probes are tried in increasing order and the report distinguishes an
earliest tested failure from an exhaustive earliest failure.
"""
import argparse
import json
from pathlib import Path
import re
import shutil

from scripts.phase95_bridge import digest
from scripts.phase95_native_replay import replay


ASAN_ERROR = re.compile(r"ERROR: AddressSanitizer: ([A-Za-z0-9_-]+)")
PRESERVE = ("native-objective.json", "native-result.json", "stdout.log",
            "stderr.log", "progress.json", "retrace-hashes.jsonl")


def signature(run):
    """Use a stable process/ASan class, never a volatile stack address."""
    run = Path(run)
    result = json.loads((run / "native-result.json").read_text(encoding="utf-8"))
    code = result.get("exit_code")
    if type(code) is not int or code == 0:
        raise ValueError("source run has no nonzero native exit code")
    stderr = (run / "stderr.log").read_text(encoding="utf-8", errors="replace")
    asan = ASAN_ERROR.search(stderr)
    return {"exit_code_hex": f"0x{code & 0xffffffff:08x}",
            "asan_class": asan.group(1) if asan else None}


def last_flushed_retrace(path):
    """Ignore an interrupted final JSON line, but reject an invalid prefix."""
    if not path.is_file():
        return None
    last = None
    with path.open(encoding="utf-8", errors="replace") as stream:
        header = stream.readline()
        if not header:
            return None
        if json.loads(header).get("kind") != "jfg-phase9-retrace-hash-header":
            raise ValueError("unexpected retrace hash header")
        for line in stream:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                if not stream.read(1):
                    break
                raise ValueError("invalid interior retrace hash row") from None
            retrace = row.get("retrace")
            if (row.get("kind") != "jfg-phase9-retrace-hash" or
                    type(retrace) is not int or retrace != (last or 0) + 1):
                raise ValueError("noncontiguous retrace hash stream")
            last = retrace
    return last


def triage(source, failure_run, output, executable, rom, rom_sha256, *,
           max_trials=8, timeout=300, replay_fn=replay):
    source, failure_run, output, executable, rom = map(
        lambda path: Path(path).resolve(),
        (source, failure_run, output, executable, rom))
    if output.exists():
        raise FileExistsError(output)
    if type(max_trials) is not int or not 1 <= max_trials <= 64:
        raise ValueError("max_trials must be 1..64")
    if type(timeout) is not int or not 1 <= timeout <= 3600:
        raise ValueError("timeout must be 1..3600")
    manifest = json.loads((source / "export-manifest.json").read_text(encoding="utf-8"))
    original = json.loads((failure_run / "native-result.json").read_text(encoding="utf-8"))
    objective = json.loads((failure_run / "native-objective.json").read_text(encoding="utf-8"))
    if (manifest.get("kind") != "jfg-phase95-selected-input-export" or
            manifest.get("input_sha256") != digest(source / "controller.input") or
            (manifest.get("initial_state") or {}).get("flash_sha256") != digest(source / "initial.flash") or
            (manifest.get("initial_state") or {}).get("pak_sha256") != digest(source / "initial.pak") or
            objective.get("kind") != "jfg-phase95-native-selected-poll-replay" or
            objective.get("input_sha256") != manifest["input_sha256"] or
            objective.get("executable_sha256") != digest(executable) or
            objective.get("rom_sha256") != rom_sha256 or
            digest(rom) != rom_sha256 or
            objective.get("stop_mode") != "vi-retraces" or
            original.get("target_retraces") != objective.get("target_retraces")):
        raise ValueError("failure replay lineage or binary pins do not match")
    target = original["target_retraces"]
    if type(target) is not int or not 3 <= target <= manifest.get("oracle_final_frame", -1):
        raise ValueError("invalid failed retrace target")
    expected = signature(failure_run)
    last = last_flushed_retrace(failure_run / "retrace-hashes.jsonl")
    output.mkdir(parents=True)
    retained = output / "original"
    retained.mkdir()
    for name in PRESERVE:
        if (failure_run / name).is_file():
            shutil.copyfile(failure_run / name, retained / name)
    for name in ("controller.input", "export-manifest.json", "initial.flash", "initial.pak"):
        shutil.copyfile(source / name, output / name)
    artifacts = {name: digest(output / name) for name in
                 ("controller.input", "export-manifest.json", "initial.flash", "initial.pak")}
    original_artifacts = {path.name: digest(path) for path in retained.iterdir()}
    (output / "triage-objective.json").write_text(json.dumps({
        "kind": "jfg-phase95-native-failure-triage", "schema": 1,
        "source_export": str(source), "source_run": str(failure_run),
        "original_signature": expected, "original_target": target,
        "last_flushed_retrace": last, "executable_sha256": digest(executable),
        "rom_sha256": rom_sha256, "retained_sha256": artifacts,
        "original_run_sha256": original_artifacts,
        "max_trials": max_trials, "timeout_seconds_per_trial": timeout,
    }, indent=2) + "\n", encoding="utf-8")

    # A complete original stream proves the process survived its earlier
    # retraces, but not that separately stopped probes have identical behavior.
    # Include one retrace before the hint to check this boundary.
    start = max(3, (last or 3) - 1)
    if start > target:
        start = target
    if target - start + 1 <= max_trials:
        candidates = list(range(start, target + 1))
    else:
        candidates = [*range(start, start + max_trials - 1), target]
    rows = []
    for index, prefix in enumerate(candidates, 1):
        trial = output / f"trial-{index:02d}-retrace-{prefix}"
        error = None
        try:
            replay_fn(source, trial, executable, rom, rom_sha256,
                      timeout=timeout, target_retraces=prefix)
        except Exception as caught:
            error = str(caught)
        observed = None
        if (trial / "native-result.json").is_file():
            try:
                observed = signature(trial)
            except ValueError:
                pass
        row = {"retrace_target": prefix, "signature": observed,
               "same_failure": observed == expected, "error": error,
               "run": str(trial)}
        rows.append(row)
        with (output / "triage-trials.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row) + "\n")
        if row["same_failure"]:
            break
    first = next((row["retrace_target"] for row in rows if row["same_failure"]), None)
    tested = {row["retrace_target"] for row in rows}
    result = {"kind": "jfg-phase95-native-failure-triage-result", "schema": 1,
              "original_signature": expected, "original_target": target,
              "search_window_start": start,
              "first_reproduced_tested_prefix": first,
              "earliest_prefix_proven": first is not None and
                  all(frame in tested for frame in range(3, first)),
              "reproduced": first is not None, "trials": len(rows),
              "untested_prefix_count": target - 2 - len(tested),
              "limitations": "untested prefixes and changed stop boundaries are not cleared"}
    (output / "triage-result.json").write_text(json.dumps(result, indent=2) + "\n",
                                                encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("failure_run", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    parser.add_argument("--max-trials", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    print(json.dumps(triage(args.source, args.failure_run, args.output,
                            args.executable, args.rom, args.rom_sha256,
                            max_trials=args.max_trials, timeout=args.timeout)))


if __name__ == "__main__":
    main()
