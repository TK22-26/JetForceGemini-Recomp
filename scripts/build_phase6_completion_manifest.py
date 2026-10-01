"""Build, sign, and verify the Phase 6 native-M2 completion manifest.

The manifest binds the deterministic infrastructure and the local native
original-entry proof. Private ROM, generated code, and raw oracle evidence
participate only through a sanitized summary and private-evidence digest.

Signature: OpenSSH Ed25519, namespace jfg-phase6-completion-v1, verified
against the pinned project key.

Usage:
  build:  --private-key <path> --private-evidence <path> [--output <path>]
  verify: --verify [--manifest <path>] [--private-evidence <path>]
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAMESPACE = "jfg-phase6-completion-v1"
SIGNING_POLICY_PATH = ROOT / "config" / "phase6-completion-signing.json"
DEFAULT_MANIFEST_PATH = ROOT / "evidence" / "phase6-completion.json"
SSH_TIMEOUT_SECONDS = 60.0

# The pinned representative-boot checkpoint (mirrors tests/boot_tests.cpp).
REPRESENTATIVE_CHECKPOINT = (
    "status=1;vi=5;events=14;threads=2;rsp=1;stubs=0;"
    "journal=2f8f8e185e7f380e643e64910d64bb88f77fb46def622cb6277e1f5c6f836800;"
    "state=4edff7780cc9a41302f9fa52fef8d054f5aff4cf57d7a7fe76983753eb77025f"
)

BOUND_FILES = (
    ".github/workflows/ci.yml",
    "CMakeLists.txt",
    "cmake/GeneratedCode.cmake",
    "docs/planning/phase6-acceptance.md",
    "docs/planning/phase6-native-boot-addendum.md",
    "docs/planning/phase6-native-boot-remaining.md",
    "config/phase6-completion-signing.json",
    "evidence/phase6-native-boot-summary.json",
    "evidence/phase6-native-stub-ledger.json",
    "include/jfg/boot/runtime.hpp",
    "include/jfg/boot/executor.hpp",
    "include/jfg/boot/representative.hpp",
    "include/jfg/boot/driver.hpp",
    "include/jfg/boot/hle.hpp",
    "include/jfg/boot/reset_handoff.hpp",
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
    "src/boot/runtime.cpp",
    "src/boot/executor.cpp",
    "src/boot/PROVENANCE.md",
    "src/boot/PHASE6_NATIVE_PROVENANCE.md",
    "src/boot/hle.cpp",
    "src/boot/native_boot.cpp",
    "src/boot/reset_handoff.cpp",
    "src/boot/thread_scheduler.cpp",
    "src/runtime/recomp_support/minimal_runtime.cpp",
    "src/app/jfg_boot_main.cpp",
    "src/app/jfg_native_boot_main.cpp",
    "scripts/prepare_phase6_native_dispatch_table.py",
    "scripts/verify_phase6_native_boot.py",
    "scripts/build_phase6_completion_manifest.py",
    "tests/CMakeLists.txt",
    "tests/boot_tests.cpp",
    "tests/hle_tests.cpp",
    "tests/reset_handoff_tests.cpp",
    "tests/test_phase6_cmake_behavior.py",
    "tests/test_phase6_policy.py",
    "tests/test_prepare_phase6_native_dispatch_table.py",
    "tests/test_verify_phase6_native_boot.py",
)

REQUIRED_CTEST_NAMES = (
    "jfg.boot",
    "jfg.boot_self_check",
    "jfg.boot_repeat",
    "jfg.boot_invalid_rom",
    "jfg.phase6_native_m2",
)

NATIVE_SUMMARY_PATH = ROOT / "evidence" / "phase6-native-boot-summary.json"
NATIVE_EXPECTED = {
    "schema_version": 2,
    "kind": "jfg-phase6-native-boot-summary",
    "status": "stable-vi",
    "native_runs": 3,
    "native_runs_bit_identical": True,
    "first_divergence": None,
    "determinism_tolerance": "zero",
    "vi_retraces": 3,
    "rdram_bytes": 4 * 1024 * 1024,
    "unsupported_accesses": 0,
    "invalid_rom_safe": True,
    "oracle": "BizHawk-2.11.1",
    "emulator_native_checkpoint_parity": True,
    "emulator_queue_transitions_observed": True,
    "original_entry_asan_passed": True,
    "producer_worktree_clean": True,
}
SHA256_FIELDS = (
    "state_hash",
    "journal_hash",
    "mmio_trace_sha256",
    "executable_sha256",
    "generated_inventory_sha256",
    "libultra_identification_sha256",
    "oracle_checkpoint_sha256",
    "oracle_probe_sha256",
    "bizhawk_executable_sha256",
    "source_closure_sha256",
    "private_evidence_sha256",
    "sanitized_executable_sha256",
    "sanitizer_runtime_sha256",
)
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


class CompletionError(RuntimeError):
    pass


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise CompletionError(f"bound file unavailable: {path}")
    return _sha256_bytes(path.read_bytes())


def _valid_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _load_native_summary() -> dict[str, object]:
    try:
        summary = json.loads(NATIVE_SUMMARY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CompletionError("native M2 summary is unreadable") from error
    if (
        not isinstance(summary, dict)
        or any(summary.get(key) != value for key, value in NATIVE_EXPECTED.items())
        or any(not _valid_sha256(summary.get(key)) for key in SHA256_FIELDS)
        or not isinstance(summary.get("mmio_accesses"), int)
        or summary["mmio_accesses"] <= 0
        or not isinstance(summary.get("build_identity"), str)
        or not summary["build_identity"]
        or not isinstance(summary.get("sanitized_build_identity"), str)
        or not summary["sanitized_build_identity"]
        or not isinstance(summary.get("producer_revision"), str)
        or len(summary["producer_revision"]) != 40
    ):
        raise CompletionError("native M2 summary does not satisfy the acceptance gate")
    return summary


def _private_evidence_errors(
    private_path: Path, summary: dict[str, object]
) -> list[str]:
    errors: list[str] = []
    try:
        private_bytes = private_path.read_bytes()
        private = json.loads(private_bytes)
    except (OSError, json.JSONDecodeError):
        return ["private native evidence is unreadable"]
    if _sha256_bytes(private_bytes) != summary.get("private_evidence_sha256"):
        errors.append("private native evidence digest mismatch")
    if (
        not isinstance(private, dict)
        or private.get("schema_version") != 2
        or private.get("kind") != "jfg-phase6-native-boot-private-evidence"
        or private.get("rom_sha1") != "493ced9008dbe932d6e91179b68e8630cf23a023"
    ):
        return errors + ["private native evidence kind/version is invalid"]

    native = private.get("native_result")
    runs = private.get("native_runs")
    ledger = private.get("mmio_ledger")
    oracle = private.get("emulator_checkpoint")
    provenance = private.get("provenance")
    determinism = private.get("determinism")
    comparison = private.get("comparison")
    sanitizer = private.get("sanitizer")
    native_binding = {
        "status": "status",
        "vi_retraces": "vi_retraces",
        "vi_queue": "vi_queue",
        "threads_created": "threads_created",
        "rdram_bytes": "rdram_bytes",
        "mmio_accesses": "mmio_accesses",
        "unsupported_accesses": "unsupported_accesses",
        "state_hash": "state_hash",
        "journal_hash": "journal_hash",
        "build_identity": "build_identity",
    }
    if (
        not isinstance(native, dict)
        or any(native.get(source) != summary.get(target)
               for source, target in native_binding.items())
        or native.get("vi_interrupts") != 3
        or native.get("vi_messages_delivered") != 3
        or not isinstance(native.get("vi_frames"), int)
        or native["vi_frames"] < 3
    ):
        errors.append("private native result is not bound to the public summary")
    if (
        not isinstance(runs, list)
        or len(runs) != summary.get("native_runs")
        or any(
            not isinstance(run, dict)
            or run.get("run") != index
            or run.get("state_hash") != summary.get("state_hash")
            or run.get("journal_hash") != summary.get("journal_hash")
            or not _valid_sha256(run.get("output_sha256"))
            for index, run in enumerate(runs, 1)
        )
        or len({run.get("output_sha256") for run in runs if isinstance(run, dict)}) != 1
    ):
        errors.append("private native repeat evidence is invalid")
    if (
        determinism != {
            "state_hash_equal": True,
            "journal_hash_equal": True,
            "canonical_outputs_bit_identical": True,
            "first_divergence": None,
            "tolerance": "zero",
        }
    ):
        errors.append("private determinism evidence is invalid")
    expected_comparison = {
        "stable_vi": True,
        "retrace_count_equal": True,
        "rdram_size_equal": True,
        "queue_identity_equal": True,
        "emulator_queue_transitions_observed": True,
        "invalid_rom_safe": True,
    }
    if comparison != expected_comparison:
        errors.append("private emulator/native comparison is invalid")
    if (
        not isinstance(sanitizer, dict)
        or sanitizer.get("sanitizer") != "address"
        or sanitizer.get("instrumentation_detector")
        not in {"clang-rt-asan-runtime-reference", "asan-init-symbol"}
        or sanitizer.get("passed") is not True
        or sanitizer.get("invalid_rom_safe") is not True
        or sanitizer.get("executable_sha256")
        != summary.get("sanitized_executable_sha256")
        or sanitizer.get("runtime_sha256")
        != summary.get("sanitizer_runtime_sha256")
        or sanitizer.get("embedded_build_identity")
        != summary.get("sanitized_build_identity")
    ):
        errors.append("private original-entry sanitizer evidence is invalid")
    if (
        not isinstance(ledger, dict)
        or ledger.get("instrumentation") != "page-guard-register-whitelist-v1"
        or ledger.get("trace_sha256") != summary.get("mmio_trace_sha256")
        or not isinstance(ledger.get("entries"), list)
        or len(ledger["entries"]) != summary.get("mmio_accesses")
        or any(
            not isinstance(entry, dict)
            or set(entry) != {"address", "operation"}
            or not isinstance(entry.get("address"), str)
            or len(entry["address"]) != 10
            or entry.get("operation") not in {"read", "write"}
            for entry in ledger.get("entries", [])
        )
    ):
        errors.append("private MMIO trace is invalid")
    if (
        not isinstance(oracle, dict)
        or oracle.get("oracle") != summary.get("oracle")
        or oracle.get("queue_observation") != "first-index-and-message-slots-v1"
        or oracle.get("queue_address") != summary.get("vi_queue")
        or oracle.get("observed_retraces") != 3
        or oracle.get("first_indices") != [1, 2, 3]
        or not isinstance(oracle.get("transition_frames"), list)
        or len(oracle["transition_frames"]) != 3
        or oracle["transition_frames"] != sorted(set(oracle["transition_frames"]))
        or not isinstance(oracle.get("message_values"), list)
        or len(oracle["message_values"]) != 3
        or not all(isinstance(value, str) for value in oracle["message_values"])
        or len(set(oracle["message_values"])) != 1
    ):
        errors.append("private emulator queue observation is invalid")

    if not isinstance(provenance, dict):
        errors.append("private provenance is invalid")
        return errors
    generated = provenance.get("generated_root")
    repository = provenance.get("repository")
    closure = provenance.get("source_closure")
    provenance_binding = {
        "executable_sha256": "executable_sha256",
        "embedded_build_identity": "build_identity",
        "bizhawk_executable_sha256": "bizhawk_executable_sha256",
        "libultra_identification_sha256": "libultra_identification_sha256",
        "oracle_checkpoint_sha256": "oracle_checkpoint_sha256",
        "oracle_probe_sha256": "oracle_probe_sha256",
    }
    if any(provenance.get(source) != summary.get(target)
           for source, target in provenance_binding.items()):
        errors.append("private tool provenance is not bound to the public summary")
    if (
        not isinstance(generated, dict)
        or generated.get("inventory_sha256")
        != summary.get("generated_inventory_sha256")
    ):
        errors.append("private generated inventory is not bound to the public summary")
    if (
        not isinstance(closure, dict)
        or set(closure) != set(SOURCE_CLOSURE)
        or any(closure.get(path) != _sha256_file(ROOT / path)
               for path in SOURCE_CLOSURE)
    ):
        errors.append("private source closure drifted")
    else:
        closure_digest = _sha256_bytes(_canonical_bytes(closure))
        if closure_digest != summary.get("source_closure_sha256"):
            errors.append("private source closure digest is unbound")
    if (
        not isinstance(repository, dict)
        or repository.get("worktree_clean") is not True
        or not isinstance(repository.get("revision"), str)
        or len(repository["revision"]) != 40
        or repository.get("revision") != summary.get("producer_revision")
        or repository.get("worktree_status_sha256")
        != _sha256_bytes(b"")
    ):
        errors.append("private repository provenance is not clean")
    else:
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", repository["revision"], "HEAD"],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=30,
        )
        if result.returncode != 0:
            errors.append("private producer revision is not an ancestor of HEAD")
    return errors


def _load_policy() -> tuple[dict[str, object], Path]:
    policy = json.loads(SIGNING_POLICY_PATH.read_text(encoding="utf-8"))
    if (
        policy.get("kind") != "jfg-phase6-completion-signing-policy"
        or policy.get("namespace") != NAMESPACE
        or policy.get("algorithm") != "openssh-ed25519"
    ):
        raise CompletionError("signing policy is invalid")
    public_key = ROOT / "config" / str(policy["public_key_file"])
    if public_key.is_symlink() or not public_key.is_file():
        raise CompletionError("pinned public key is unavailable")
    return policy, public_key


def _ssh_keygen() -> str:
    executable = shutil.which("ssh-keygen")
    if executable is None:
        raise CompletionError("OpenSSH signer is unavailable")
    return executable


def _payload(document: dict[str, object]) -> bytes:
    stripped = copy.deepcopy(document)
    stripped.pop("authentication", None)
    return _canonical_bytes(stripped)


def build(private_key: Path, output: Path, private_evidence: Path) -> None:
    native_summary = _load_native_summary()
    private_errors = _private_evidence_errors(private_evidence, native_summary)
    if private_errors:
        raise CompletionError("; ".join(private_errors))
    document: dict[str, object] = {
        "schema_version": 1,
        "kind": "jfg-phase6-completion",
        "acceptance_contract": "docs/planning/phase6-acceptance.md",
        "native_boot_status": {
            "state": "complete-local-m2",
            "tracked_by": "docs/planning/phase6-native-boot-remaining.md",
            "summary": "evidence/phase6-native-boot-summary.json",
            "private_evidence_sha256": native_summary["private_evidence_sha256"],
            "distribution_authorized": False,
        },
        "runtime_authorship": {
            "independently_authored": True,
            "third_party_source_copied": False,
            "provenance": "src/boot/PROVENANCE.md",
        },
        "representative_boot": {
            "role": "rom-free-regression-only",
            "acceptance_proof": False,
            "reached_stable_vi": True,
            "checkpoint": REPRESENTATIVE_CHECKPOINT,
        },
        "bound_files": {
            path: _sha256_file(ROOT / Path(path)) for path in BOUND_FILES
        },
        "required_ctest_names": list(REQUIRED_CTEST_NAMES),
        "authentication": {
            "algorithm": "openssh-ed25519",
            "namespace": NAMESPACE,
        },
    }
    payload = _payload(document)

    resolved_key = private_key.resolve()
    tools_root = (ROOT / "tools").resolve()
    try:
        resolved_key.relative_to(tools_root)
    except ValueError as error:
        raise CompletionError(
            "completion private key must remain under ignored tools"
        ) from error
    executable = _ssh_keygen()
    with tempfile.TemporaryDirectory(
        prefix="phase6-sign-", dir=tools_root
    ) as temp:
        payload_path = Path(temp) / "completion.payload"
        payload_path.write_bytes(payload)
        result = subprocess.run(
            [
                executable, "-Y", "sign",
                "-f", str(resolved_key),
                "-n", NAMESPACE,
                str(payload_path),
            ],
            capture_output=True,
            check=False,
            timeout=SSH_TIMEOUT_SECONDS,
        )
        signature_path = Path(str(payload_path) + ".sig")
        if result.returncode != 0 or not signature_path.is_file():
            raise CompletionError("completion signing failed")
        signature = signature_path.read_bytes()

    authentication = document["authentication"]
    assert isinstance(authentication, dict)
    authentication["payload_sha256"] = _sha256_bytes(payload)
    encoded = signature.hex()
    authentication["signature_hex_chunks"] = [
        encoded[index : index + 64] for index in range(0, len(encoded), 64)
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    errors = verify(output, private_evidence)
    if errors:
        raise CompletionError(f"self-verification failed: {errors}")
    print(f"PHASE6 NATIVE M2 COMPLETION MANIFEST FINALIZED: {output}")


def verify(manifest_path: Path, private_evidence: Path | None = None) -> list[str]:
    errors: list[str] = []
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ["manifest unreadable"]
    if (
        not isinstance(document, dict)
        or document.get("kind") != "jfg-phase6-completion"
        or document.get("schema_version") != 1
    ):
        return ["manifest kind/version invalid"]

    bound = document.get("bound_files")
    if not isinstance(bound, dict) or set(bound) != set(BOUND_FILES):
        errors.append("bound file set drifted")
    else:
        for path, recorded in bound.items():
            try:
                actual = _sha256_file(ROOT / Path(path))
            except CompletionError:
                errors.append(f"bound file missing: {path}")
                continue
            if actual != recorded:
                errors.append(f"bound file drifted: {path}")

    if document.get("required_ctest_names") != list(REQUIRED_CTEST_NAMES):
        errors.append("required ctest names drifted")

    representative = document.get("representative_boot")
    if (
        not isinstance(representative, dict)
        or representative.get("role") != "rom-free-regression-only"
        or representative.get("acceptance_proof") is not False
        or representative.get("reached_stable_vi") is not True
        or representative.get("checkpoint") != REPRESENTATIVE_CHECKPOINT
    ):
        errors.append("representative boot claim drifted")

    native = document.get("native_boot_status")
    try:
        native_summary = _load_native_summary()
    except CompletionError:
        native_summary = {}
    if (
        not isinstance(native, dict)
        or native.get("state") != "complete-local-m2"
        or native.get("summary") != "evidence/phase6-native-boot-summary.json"
        or native.get("distribution_authorized") is not False
        or native.get("private_evidence_sha256")
        != native_summary.get("private_evidence_sha256")
        or any(native_summary.get(key) != value for key, value in NATIVE_EXPECTED.items())
    ):
        errors.append("native boot completion claim drifted")
    if private_evidence is not None and native_summary:
        errors.extend(_private_evidence_errors(private_evidence, native_summary))

    authentication = document.get("authentication")
    if (
        not isinstance(authentication, dict)
        or authentication.get("namespace") != NAMESPACE
        or authentication.get("algorithm") != "openssh-ed25519"
    ):
        errors.append("authentication record invalid")
        return errors
    payload = _payload(document)
    if authentication.get("payload_sha256") != _sha256_bytes(payload):
        errors.append("payload digest mismatch")
    chunks = authentication.get("signature_hex_chunks")
    if not isinstance(chunks, list) or not all(
        isinstance(chunk, str) for chunk in chunks
    ):
        errors.append("signature encoding invalid")
        return errors
    try:
        signature = bytes.fromhex("".join(chunks))
    except ValueError:
        return errors + ["signature hex invalid"]

    try:
        policy, public_key = _load_policy()
        executable = _ssh_keygen()
    except CompletionError as error:
        return errors + [str(error)]
    with tempfile.TemporaryDirectory(prefix="phase6-verify-") as temp:
        temp_root = Path(temp)
        payload_path = temp_root / "completion.payload"
        payload_path.write_bytes(payload)
        signature_path = temp_root / "completion.sig"
        signature_path.write_bytes(signature)
        allowed_signers = temp_root / "allowed_signers"
        allowed_signers.write_text(
            f"{policy['principal']} namespaces=\"{NAMESPACE}\" "
            + public_key.read_text(encoding="utf-8").strip()
            + "\n",
            encoding="utf-8",
        )
        with payload_path.open("rb") as payload_stream:
            result = subprocess.run(
                [
                    executable, "-Y", "verify",
                    "-f", str(allowed_signers),
                    "-I", str(policy["principal"]),
                    "-n", NAMESPACE,
                    "-s", str(signature_path),
                ],
                stdin=payload_stream,
                capture_output=True,
                check=False,
                timeout=SSH_TIMEOUT_SECONDS,
            )
    if result.returncode != 0:
        errors.append("completion signature is invalid")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--private-key", type=Path)
    parser.add_argument("--private-evidence", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_MANIFEST_PATH)
    arguments = parser.parse_args()

    if arguments.verify:
        errors = verify(arguments.manifest, arguments.private_evidence)
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print("valid" if not errors else "invalid")
        return 0 if not errors else 1

    if arguments.private_key is None:
        parser.error("--private-key is required")
    if arguments.private_evidence is None:
        parser.error("--private-evidence is required")
    try:
        build(arguments.private_key, arguments.output, arguments.private_evidence)
    except CompletionError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
