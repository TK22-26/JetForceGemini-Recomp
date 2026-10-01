"""Verify and bind the private Phase 6 native M2 and emulator run."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
EXPECTED_ROM_SHA1 = "493ced9008dbe932d6e91179b68e8630cf23a023"
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
MMIO_PATTERN = re.compile(r"([rw]):(0x[a-f0-9]{8})\Z")
SOURCE_CLOSURE = (
    "CMakeLists.txt",
    "include/jfg/boot/executor.hpp",
    "include/jfg/boot/hle.hpp",
    "include/jfg/boot/thread_scheduler.hpp",
    "include/jfg/boot/tlb.hpp",
    "include/jfg/boot/reference_cache.hpp",
    "include/jfg/boot/cpu_status.hpp",
    "include/jfg/boot/mi_interrupt_mask.hpp",
    "include/jfg/boot/sp_status.hpp",
    "include/jfg/boot/reference_sp_dma.hpp",
    "include/jfg/boot/reference_pi_dma.hpp",
    "include/jfg/boot/reference_compare.hpp",
    "include/jfg/boot/reference_si_dma.hpp",
    "include/jfg/boot/reference_event_commit.hpp",
    "include/jfg/boot/reference_flash_bus.hpp",
    "include/jfg/boot/reference_ai_dma.hpp",
    "include/jfg/runtime/save_device_runtime.hpp",
    "include/jfg/runtime/controller_pak.hpp",
    "src/runtime/save_device_runtime.cpp",
    "src/runtime/controller_pak.cpp",
    "include/jfg/runtime/cic_nus_6105.hpp",
    "src/runtime/cic_nus_6105.cpp",
    "include/jfg/boot/reference_pif_boot.hpp",
    "include/jfg/boot/guest_thread_transport.hpp",
    "include/jfg/runtime/cpu_operation_bridge.h",
    "src/app/jfg_native_boot_main.cpp",
    "src/boot/executor.cpp",
    "src/boot/hle.cpp",
    "src/boot/native_boot.cpp",
    "src/boot/thread_scheduler.cpp",
    "src/runtime/recomp_support/minimal_runtime.cpp",
    "scripts/prepare_phase6_native_dispatch_table.py",
    "scripts/verify_phase6_native_boot.py",
)


def canonical(document: object) -> bytes:
    return (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_address_sanitizer_instrumentation(executable: Path) -> str:
    payload = executable.read_bytes().lower()
    signatures = (
        (b"clang_rt.asan", "clang-rt-asan-runtime-reference"),
        (b"__asan_init", "asan-init-symbol"),
    )
    for signature, detector in signatures:
        if signature in payload:
            return detector
    raise ValueError("sanitized executable has no AddressSanitizer runtime binding")


def generated_inventory(root: Path) -> dict[str, object]:
    if not root.is_dir() or root.is_symlink():
        raise ValueError("generated root is unavailable or symbolic")
    entries: list[dict[str, object]] = []
    total = 0
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_symlink():
            raise ValueError("generated root contains a symbolic link")
        if not path.is_file():
            continue
        size = path.stat().st_size
        total += size
        entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size": size,
                "sha256": sha256_file(path),
            }
        )
    if not entries:
        raise ValueError("generated root inventory is empty")
    payload = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    return {
        "file_count": len(entries),
        "total_bytes": total,
        "inventory_sha256": hashlib.sha256(payload).hexdigest(),
        "symbol_inventory_sha256": sha256_file(root / "symbol_inventory.json"),
        "report_set_sha256": sha256_file(root / "report_set.json"),
    }


def repository_provenance() -> dict[str, object]:
    def git(*arguments: str) -> bytes:
        completed = subprocess.run(
            ["git", *arguments], cwd=ROOT, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, check=False, timeout=30,
        )
        if completed.returncode != 0 or completed.stderr:
            raise ValueError(f"git provenance command failed: {' '.join(arguments)}")
        return completed.stdout

    revision = git("rev-parse", "HEAD").decode("ascii").strip()
    status = git("status", "--porcelain=v1", "--untracked-files=all")
    return {
        "revision": revision,
        "worktree_clean": not status,
        "worktree_status_sha256": hashlib.sha256(status).hexdigest(),
    }


def source_closure() -> dict[str, str]:
    return {name: sha256_file(ROOT / name) for name in SOURCE_CLOSURE}


def parse_mmio_trace(result: dict[str, object]) -> tuple[list[dict[str, str]], str]:
    text = result.get("mmio_trace")
    if not isinstance(text, str) or not text:
        raise ValueError("native MMIO trace is absent")
    entries: list[dict[str, str]] = []
    for raw in text.split(","):
        match = MMIO_PATTERN.fullmatch(raw)
        if match is None:
            raise ValueError("native MMIO trace is malformed")
        entries.append(
            {"operation": "write" if match.group(1) == "w" else "read",
             "address": match.group(2)}
        )
    if len(entries) != result.get("mmio_accesses"):
        raise ValueError("native MMIO count does not match its trace")
    return entries, hashlib.sha256(text.encode("ascii")).hexdigest()


def run_native(
    executable: Path, rom: Path, expected_build_identity: str | None = None,
    expected_sanitizer: str = "none",
    environment: dict[str, str] | None = None,
) -> tuple[bytes, dict[str, object]]:
    completed = subprocess.run(
        [str(executable), "--rom", str(rom)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=60,
        env=environment,
    )
    if completed.returncode != 0 or completed.stderr:
        raise ValueError(
            f"native run failed: exit={completed.returncode} "
            f"stderr={completed.stderr.decode(errors='replace')!r}"
        )
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ValueError("native output is not one JSON document") from error
    expected = {
        "kind": "jfg-phase6-native-boot",
        "status": "stable-vi",
        "vi_retraces": 3,
        "vi_interrupts": 3,
        "vi_messages_delivered": 3,
        "rdram_bytes": 4 * 1024 * 1024,
        "unsupported_accesses": 0,
    }
    if any(result.get(key) != value for key, value in expected.items()):
        raise ValueError("native result does not clear the M2 gate")
    if result.get("sanitizer") != expected_sanitizer:
        raise ValueError("native result does not identify the expected instrumentation")
    integer_minimums = {
        "vi_frames": 3,
        "threads_created": 1,
        "mmio_accesses": 1,
        "journal_entries": 1,
    }
    if any(
        not isinstance(result.get(key), int) or result[key] < minimum
        for key, minimum in integer_minimums.items()
    ):
        raise ValueError("native result has an invalid counter")
    build_identity = result.get("build_identity")
    if not isinstance(build_identity, str) or not build_identity:
        raise ValueError("native result has no embedded build identity")
    if expected_build_identity is not None and build_identity != expected_build_identity:
        raise ValueError("native build identity does not match the configured build")
    if not isinstance(result.get("vi_queue"), str) or not re.fullmatch(
        r"0x[89a-f][0-9a-f]{7}", result["vi_queue"]
    ):
        raise ValueError("native VI queue identity is invalid")
    if any(
        not isinstance(result.get(key), str)
        or SHA256_PATTERN.fullmatch(result[key]) is None
        for key in ("state_hash", "journal_hash")
    ):
        raise ValueError("native deterministic digest is invalid")
    parse_mmio_trace(result)
    normalized = completed.stdout.replace(b"\r\n", b"\n")
    compact = (json.dumps(result, separators=(",", ":")) + "\n").encode()
    if normalized != compact:
        raise ValueError("native output is not canonical JSON")
    return normalized, result


def first_divergence(
    baseline_output: bytes,
    baseline: dict[str, object],
    output: bytes,
    result: dict[str, object],
    run_number: int,
) -> dict[str, object] | None:
    for key in sorted(set(baseline) | set(result)):
        if baseline.get(key) != result.get(key):
            return {
                "run": run_number,
                "domain": key,
                "expected": baseline.get(key),
                "actual": result.get(key),
            }
    if baseline_output != output:
        limit = min(len(baseline_output), len(output))
        offset = next(
            (index for index in range(limit)
             if baseline_output[index] != output[index]), limit
        )
        return {
            "run": run_number,
            "domain": "canonical_output",
            "byte_offset": offset,
            "expected_size": len(baseline_output),
            "actual_size": len(output),
        }
    return None


def verify_invalid_rom(
    executable: Path, environment: dict[str, str] | None = None
) -> None:
    with tempfile.TemporaryDirectory(prefix="jfg-phase6-invalid-") as temporary:
        invalid = Path(temporary) / "invalid.z64"
        invalid.write_bytes(bytes(32 * 1024 * 1024))
        completed = subprocess.run(
            [str(executable), "--rom", str(invalid)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=10,
            env=environment,
        )
    if completed.returncode != 2 or completed.stdout or completed.stderr:
        raise ValueError("invalid ROM did not fail safely and silently")


def validate_oracle(oracle: object, native: dict[str, object]) -> dict[str, object]:
    if not isinstance(oracle, dict):
        raise ValueError("emulator checkpoint is not an object")
    transitions = oracle.get("transition_frames")
    indices = oracle.get("first_indices")
    valid_counts = oracle.get("valid_counts")
    messages = oracle.get("message_values")
    first_start = oracle.get("first_start")
    first_end = oracle.get("first_end")
    if (
        oracle.get("kind") != "jfg-phase6-emulator-vi-checkpoint"
        or oracle.get("oracle") != "BizHawk-2.11.1"
        or oracle.get("queue_observation") != "first-index-and-message-slots-v1"
        or oracle.get("queue_address") != native["vi_queue"]
        or oracle.get("observed_retraces") != native["vi_retraces"]
        or oracle.get("rdram_bytes") != native["rdram_bytes"]
        or not isinstance(oracle.get("setup_frame"), int)
        or not isinstance(oracle.get("completion_frame"), int)
        or oracle["completion_frame"] <= oracle["setup_frame"]
        or not isinstance(oracle.get("queue_depth"), int)
        or oracle["queue_depth"] <= 0
        or not isinstance(first_start, int)
        or not isinstance(first_end, int)
        or not all(isinstance(values, list) and len(values) == 3 for values in
                   (transitions, indices, valid_counts, messages))
        or not all(isinstance(value, int) for value in transitions)
        or not all(isinstance(value, int) for value in indices)
        or not all(isinstance(value, str) for value in messages)
        or transitions != sorted(set(transitions))
        or len(set(messages)) != 1
        or not all(isinstance(value, int) and 0 <= value <= oracle["queue_depth"]
                   for value in valid_counts)
    ):
        raise ValueError("emulator/native checkpoint parity failed")
    expected_end = (first_start + 3) % oracle["queue_depth"]
    if first_end != expected_end or indices[-1] != expected_end:
        raise ValueError("emulator VI queue did not advance by three messages")
    return oracle


def write_stub_ledger(
    path: Path, entries: list[dict[str, str]], trace_sha256: str
) -> None:
    counts: Counter[tuple[str, str]] = Counter(
        (entry["address"], entry["operation"]) for entry in entries
    )
    addresses = sorted({entry["address"] for entry in entries})
    ledger = {
        "schema_version": 2,
        "kind": "jfg-phase6-native-stub-ledger",
        "scope": "supported-original-entry-to-stable-vi",
        "instrumentation": "page-guard-register-whitelist-v1",
        "default_disposition": "fail-closed-unsupported-register",
        "observed_unsupported_accesses": 0,
        "mmio_trace_sha256": trace_sha256,
        "entries": [
            {
                "address": address,
                "reads": counts[(address, "read")],
                "writes": counts[(address, "write")],
                "disposition": "deterministic-register-shadow",
            }
            for address in addresses
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(ledger))


def verify(
    executable: Path,
    rom: Path,
    oracle_path: Path,
    private_out: Path,
    public_out: Path,
    repeat: int,
    generated_root: Path,
    identification: Path,
    bizhawk_executable: Path,
    oracle_probe: Path,
    expected_build_identity: str | None = None,
    stub_ledger_out: Path | None = None,
    require_clean: bool = False,
    sanitized_executable: Path | None = None,
    sanitizer_runtime: Path | None = None,
) -> dict[str, object]:
    if repeat < 2:
        raise ValueError("repeat count must be at least two")
    rom_sha1 = hashlib.sha1(rom.read_bytes()).hexdigest()
    if rom_sha1 != EXPECTED_ROM_SHA1:
        raise ValueError("unsupported ROM identity")

    outputs: list[bytes] = []
    results: list[dict[str, object]] = []
    for _ in range(repeat):
        output, result = run_native(executable, rom, expected_build_identity)
        outputs.append(output)
        results.append(result)
    for index in range(1, len(outputs)):
        divergence = first_divergence(
            outputs[0], results[0], outputs[index], results[index], index + 1
        )
        if divergence is not None:
            raise ValueError(
                "native determinism first divergence: "
                + json.dumps(divergence, sort_keys=True)
            )
    native_result = results[0]
    verify_invalid_rom(executable)
    sanitizer_result: dict[str, object] | None = None
    sanitizer_provenance: dict[str, object] | None = None
    if sanitized_executable is not None:
        if sanitizer_runtime is None or not sanitizer_runtime.is_file():
            raise ValueError("sanitized execution requires its explicit runtime")
        sanitizer_detector = verify_address_sanitizer_instrumentation(
            sanitized_executable
        )
        sanitized_environment = os.environ.copy()
        sanitized_environment["PATH"] = (
            str(sanitizer_runtime.resolve().parent)
            + os.pathsep
            + sanitized_environment.get("PATH", "")
        )
        _, sanitizer_result = run_native(
            sanitized_executable, rom, expected_sanitizer="address",
            environment=sanitized_environment,
        )
        verify_invalid_rom(sanitized_executable, sanitized_environment)
        equal_fields = (
            "status", "vi_retraces", "vi_frames", "vi_interrupts",
            "vi_messages_delivered", "vi_queue", "threads_created",
            "rdram_bytes", "mmio_accesses", "unsupported_accesses",
            "mmio_trace", "journal_entries", "state_hash", "journal_hash",
        )
        if any(sanitizer_result.get(key) != native_result.get(key)
               for key in equal_fields):
            raise ValueError("sanitized original-entry run diverged from native run")
        sanitizer_provenance = {
            "sanitizer": "address",
            "instrumentation_detector": sanitizer_detector,
            "executable_sha256": sha256_file(sanitized_executable),
            "executable_bytes": sanitized_executable.stat().st_size,
            "runtime_sha256": sha256_file(sanitizer_runtime),
            "runtime_bytes": sanitizer_runtime.stat().st_size,
            "embedded_build_identity": sanitizer_result["build_identity"],
            "passed": True,
            "invalid_rom_safe": True,
        }
    oracle = validate_oracle(
        json.loads(oracle_path.read_text(encoding="utf-8")), native_result
    )
    repository = repository_provenance()
    if require_clean and not repository["worktree_clean"]:
        raise ValueError("trusted native evidence requires a clean worktree")
    mmio_entries, mmio_trace_sha256 = parse_mmio_trace(native_result)
    provenance = {
        "executable_sha256": sha256_file(executable),
        "executable_bytes": executable.stat().st_size,
        "embedded_build_identity": native_result["build_identity"],
        "generated_root": generated_inventory(generated_root),
        "libultra_identification_sha256": sha256_file(identification),
        "bizhawk_executable_sha256": sha256_file(bizhawk_executable),
        "oracle_probe_sha256": sha256_file(oracle_probe),
        "oracle_checkpoint_sha256": sha256_file(oracle_path),
        "source_closure": source_closure(),
        "repository": repository,
    }
    if sanitizer_provenance is not None:
        provenance["sanitized_original_entry"] = sanitizer_provenance
    private = {
        "schema_version": 2,
        "kind": "jfg-phase6-native-boot-private-evidence",
        "rom_sha1": rom_sha1,
        "native_runs": [
            {
                "run": index + 1,
                "output_sha256": hashlib.sha256(output).hexdigest(),
                "state_hash": result["state_hash"],
                "journal_hash": result["journal_hash"],
            }
            for index, (output, result) in enumerate(zip(outputs, results))
        ],
        "native_result": native_result,
        "mmio_ledger": {
            "instrumentation": "page-guard-register-whitelist-v1",
            "trace_sha256": mmio_trace_sha256,
            "entries": mmio_entries,
        },
        "emulator_checkpoint": oracle,
        "provenance": provenance,
        "determinism": {
            "state_hash_equal": True,
            "journal_hash_equal": True,
            "canonical_outputs_bit_identical": True,
            "first_divergence": None,
            "tolerance": "zero",
        },
        "comparison": {
            "stable_vi": True,
            "retrace_count_equal": True,
            "rdram_size_equal": True,
            "queue_identity_equal": True,
            "emulator_queue_transitions_observed": True,
            "invalid_rom_safe": True,
        },
        "sanitizer": sanitizer_provenance,
    }
    private_bytes = canonical(private)
    private_out.parent.mkdir(parents=True, exist_ok=True)
    private_out.write_bytes(private_bytes)

    public = {
        "schema_version": 2,
        "kind": "jfg-phase6-native-boot-summary",
        "status": "stable-vi",
        "native_runs": repeat,
        "native_runs_bit_identical": True,
        "state_hash": native_result["state_hash"],
        "journal_hash": native_result["journal_hash"],
        "first_divergence": None,
        "determinism_tolerance": "zero",
        "vi_retraces": native_result["vi_retraces"],
        "vi_queue": native_result["vi_queue"],
        "threads_created": native_result["threads_created"],
        "rdram_bytes": native_result["rdram_bytes"],
        "mmio_accesses": native_result["mmio_accesses"],
        "mmio_trace_sha256": mmio_trace_sha256,
        "unsupported_accesses": native_result["unsupported_accesses"],
        "invalid_rom_safe": True,
        "oracle": oracle["oracle"],
        "emulator_queue_transitions_observed": True,
        "emulator_native_checkpoint_parity": True,
        "build_identity": native_result["build_identity"],
        "executable_sha256": provenance["executable_sha256"],
        "generated_inventory_sha256": provenance["generated_root"]["inventory_sha256"],
        "libultra_identification_sha256": provenance["libultra_identification_sha256"],
        "oracle_checkpoint_sha256": provenance["oracle_checkpoint_sha256"],
        "oracle_probe_sha256": provenance["oracle_probe_sha256"],
        "bizhawk_executable_sha256": provenance["bizhawk_executable_sha256"],
        "source_closure_sha256": hashlib.sha256(
            json.dumps(
                provenance["source_closure"], sort_keys=True, separators=(",", ":")
            ).encode("ascii")
        ).hexdigest(),
        "producer_revision": repository["revision"],
        "producer_worktree_clean": repository["worktree_clean"],
        "private_evidence_sha256": hashlib.sha256(private_bytes).hexdigest(),
        "original_entry_asan_passed": sanitizer_provenance is not None,
        "sanitized_executable_sha256": (
            sanitizer_provenance["executable_sha256"]
            if sanitizer_provenance is not None else None
        ),
        "sanitized_build_identity": (
            sanitizer_provenance["embedded_build_identity"]
            if sanitizer_provenance is not None else None
        ),
        "sanitizer_runtime_sha256": (
            sanitizer_provenance["runtime_sha256"]
            if sanitizer_provenance is not None else None
        ),
    }
    public_out.parent.mkdir(parents=True, exist_ok=True)
    public_out.write_bytes(canonical(public))
    if stub_ledger_out is not None:
        write_stub_ledger(stub_ledger_out, mmio_entries, mmio_trace_sha256)
    return public


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", required=True, type=Path)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--oracle", required=True, type=Path)
    parser.add_argument("--generated-root", required=True, type=Path)
    parser.add_argument("--identification", required=True, type=Path)
    parser.add_argument("--bizhawk-executable", required=True, type=Path)
    parser.add_argument("--oracle-probe", required=True, type=Path)
    parser.add_argument("--expected-build-identity")
    parser.add_argument("--private-out", required=True, type=Path)
    parser.add_argument("--public-out", required=True, type=Path)
    parser.add_argument("--stub-ledger-out", type=Path)
    parser.add_argument("--sanitized-executable", type=Path)
    parser.add_argument("--sanitizer-runtime", type=Path)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--require-clean", action="store_true")
    arguments = parser.parse_args()
    try:
        result = verify(
            arguments.executable, arguments.rom, arguments.oracle,
            arguments.private_out, arguments.public_out, arguments.repeat,
            arguments.generated_root, arguments.identification,
            arguments.bizhawk_executable, arguments.oracle_probe,
            arguments.expected_build_identity, arguments.stub_ledger_out,
            arguments.require_clean, arguments.sanitized_executable,
            arguments.sanitizer_runtime,
        )
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"phase6 native verification: {error}")
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
