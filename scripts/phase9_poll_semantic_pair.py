"""Run a pinned native/BizHawk poll-state diagnostic without any AI service.

Both producers use ordinary selected controller input. A completed pair is a
diagnostic artifact, not proof that poll hooks, initial Pak state, or gameplay
are aligned. Completed sides survive a restart; interrupted sides are retained
and require recovery rather than being overwritten.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

from scripts import phase95_native_replay, phase95_oracle_replay
from scripts.compare_phase9_poll_hashes import compare
from scripts.phase95_bridge import digest, runtime_digest


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = ROOT / "tools" / "private"
KIND = "jfg-phase9-poll-semantic-pair"


def write_json_atomic(path: Path, value: dict) -> None:
    encoded = json.dumps(value, sort_keys=True, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                     dir=path.parent, prefix=path.name + ".",
                                     suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(encoded)
    temporary.replace(path)


def _plan(source: Path, executable: Path, emulator: Path, rom: Path,
          rom_sha256: str, target: int, timeout: int) -> dict:
    manifest = json.loads((source / "export-manifest.json").read_text(encoding="utf-8"))
    if (manifest.get("kind") != "jfg-phase95-selected-input-export" or
            type(target) is not int or
            type(manifest.get("oracle_final_frame")) is not int or
            not 3 <= target <= manifest["oracle_final_frame"] or
            type(timeout) is not int or not 1 <= timeout <= 3600):
        raise ValueError("invalid selected-input target or timeout")
    input_sha = manifest.get("input_sha256")
    initial = manifest.get("initial_state") or {}
    if (input_sha != digest(source / "controller.input") or
            initial.get("flash_sha256") != digest(source / "initial.flash") or
            initial.get("pak_sha256") != digest(source / "initial.pak") or
            digest(rom) != rom_sha256):
        raise ValueError("source input, save, Pak, or ROM pin changed")
    return {"kind": KIND, "schema": 1, "acceptance": False,
            "source_export": str(source), "native_executable": str(executable),
            "emulator": str(emulator), "rom": str(rom),
            "rom_sha256": rom_sha256,
            "source_manifest_sha256": digest(source / "export-manifest.json"),
            "input_sha256": input_sha,
            "initial_flash_sha256": initial["flash_sha256"],
            "initial_pak_sha256": initial["pak_sha256"],
            "native_executable_sha256": digest(executable),
            "emulator_sha256": digest(emulator),
            "emulator_runtime_sha256": runtime_digest(emulator.parent),
            "target": target, "timeout_seconds_per_side": timeout,
            "tool_sha256": {name: digest(ROOT / name) for name in (
                "scripts/phase9_poll_semantic_pair.py",
                "scripts/compare_phase9_poll_hashes.py",
                "scripts/phase95_native_replay.py",
                "scripts/phase95_oracle_replay.py",
                "scripts/phase9_bizhawk_oracle.lua",
                "scripts/phase9_si_trace.py")}}


def _existing_side(path: Path, name: str, plan: dict) -> dict | None:
    if not path.exists():
        return None
    result_path = path / ("native-result.json" if name == "native"
                          else "oracle-result.json")
    if not result_path.is_file():
        raise ValueError(f"interrupted {name} capture retained at {path}")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    saveram_regions = result.get("mupen_saveram_regions")
    saveram_path = (path / "emulator" / "N64" / "SaveRAM" /
                    (Path(plan["rom"]).stem + ".SaveRAM"))
    if (result.get("source_export") != plan["source_export"] or
            result.get("rom_sha256") != plan["rom_sha256"] or
            result.get("input_sha256") != plan["input_sha256"] or
            result.get("poll_semantic_hashes") is not True or
            result.get("completed_update_trace") is not True or
            result.get("poll_semantic_hash_trace_complete") is not True or
            result.get("exit_code") != 0 or
            (name == "native" and (
                result.get("target_retraces") != plan["target"] or
                result.get("executable_sha256") != plan["native_executable_sha256"] or
                result.get("probe_target_reached") is not True)) or
            (name == "oracle" and (
                result.get("target_frame") != plan["target"] or
                result.get("emulator_sha256") != plan["emulator_sha256"] or
                result.get("runtime_sha256") != plan["emulator_runtime_sha256"] or
                result.get("domain_inventory") is not True or
                not isinstance(result.get("memory_domains"), list) or
                not isinstance(saveram_regions, dict) or
                saveram_regions.get("kind") !=
                    "jfg-phase9-mupen-saveram-regions" or
                saveram_regions.get("native_pak_equivalence_validated") is not False or
                not saveram_path.is_file() or
                saveram_regions.get("image_sha256") != digest(saveram_path) or
                result.get("trace_complete") is not True))):
        raise ValueError(f"existing {name} capture does not match pair plan")
    return result


def run(output: Path, source: Path, executable: Path, emulator: Path,
        rom: Path, rom_sha256: str, *, target: int, timeout: int = 600) -> dict:
    output, source, executable, emulator, rom = (
        Path(value).resolve() for value in
        (output, source, executable, emulator, rom))
    private = PRIVATE_ROOT.resolve(strict=True)
    if not output.is_relative_to(private) or output == private:
        raise ValueError("pair output must be under tools/private")
    if (output.is_relative_to(source) or source.is_relative_to(output) or
            output.is_relative_to(emulator.parent) or
            emulator.parent.is_relative_to(output)):
        raise ValueError("pair output must be disjoint from input directories")
    for path in (source, executable, emulator, rom):
        if not path.exists():
            raise ValueError(f"missing pair input: {path}")
    plan = _plan(source, executable, emulator, rom, rom_sha256, target, timeout)
    if output.exists():
        plan_path = output / "plan.json"
        if not plan_path.is_file() or json.loads(plan_path.read_text(
                encoding="utf-8")) != plan:
            raise ValueError("existing pair output has no matching plan")
    else:
        output.mkdir(parents=True)
        write_json_atomic(output / "plan.json", plan)
    native_dir, oracle_dir = output / "native", output / "oracle"
    native = _existing_side(native_dir, "native", plan)
    if native is None:
        phase95_native_replay.replay(
            source, native_dir, executable, rom, rom_sha256,
            target_retraces=target, timeout=timeout,
            poll_hashes=True, update_hashes=True)
        native = _existing_side(native_dir, "native", plan)
        if native is None:
            raise ValueError("native producer did not write a result")
    oracle = _existing_side(oracle_dir, "oracle", plan)
    if oracle is None:
        phase95_oracle_replay.replay(
            oracle_dir, emulator, rom, rom_sha256, source,
            target_frame=target, timeout=timeout,
            poll_hashes=True, update_hashes=True, domain_inventory=True)
        oracle = _existing_side(oracle_dir, "oracle", plan)
        if oracle is None:
            raise ValueError("oracle producer did not write a result")
    prefix = min(native["poll_semantic_hash_count"],
                 oracle["poll_semantic_hash_count"])
    if type(prefix) is not int or prefix < 1:
        raise ValueError("paired captures have no shared controller polls")
    comparison = compare(
        source, native_dir / "retrace-hashes.jsonl.polls.jsonl",
        oracle_dir / "poll-hashes.jsonl", prefix_polls=prefix)
    if (comparison["producer_provenance"].get("verified") is not True or
            comparison["state_scan_complete"] is not True or
            comparison["input_prefix_match"] is not True):
        raise ValueError("paired poll-state comparison is incomplete")
    comparison_path = output / "comparison.json"
    if comparison_path.exists():
        if json.loads(comparison_path.read_text(encoding="utf-8")) != comparison:
            raise ValueError("existing comparison changed")
    else:
        write_json_atomic(comparison_path, comparison)
    summary = {"kind": KIND, "schema": 1, "complete": True,
               "acceptance": False, "alignment_validated": False,
               "parity_verified": False, "plan_sha256": digest(output / "plan.json"),
               "native_result_sha256": digest(native_dir / "native-result.json"),
               "oracle_result_sha256": digest(oracle_dir / "oracle-result.json"),
               "comparison_sha256": digest(comparison_path),
               "shared_polls": prefix,
               "oracle_saveram_image_sha256": oracle[
                   "mupen_saveram_regions"]["image_sha256"],
               "native_pak_equivalence_validated": False,
               "first_semantic_mismatch": comparison["first_semantic_mismatch"],
               "mismatch_windows": comparison["first_mismatch_windows"],
               "reason_not_parity": comparison["caveat"]}
    result_path = output / "pair-result.json"
    if result_path.exists():
        if json.loads(result_path.read_text(encoding="utf-8")) != summary:
            raise ValueError("existing pair result changed")
    else:
        write_json_atomic(result_path, summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--rom-sha256", required=True)
    parser.add_argument("--target", type=int, required=True)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.source, args.executable,
                         args.emulator, args.rom, args.rom_sha256,
                         target=args.target, timeout=args.timeout)))


if __name__ == "__main__":
    main()
