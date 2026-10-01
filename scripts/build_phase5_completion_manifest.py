"""Build, sign, and verify the public Phase 5 completion manifest.

The manifest is fail-closed evidence per docs/planning/phase5-acceptance.md:
it binds the acceptance contract, the pinned schema/tolerance configs, and
the sanitized boundary-capture summary by digest, and carries an OpenSSH
Ed25519 signature in the ``jfg-phase5-completion-v1`` namespace verifying
against the pinned anonymous project key.  ROM-derived bytes never enter
the manifest; the private ledger participates by digest only.

Usage:
  build:  --capture-summary <path> --private-key <path> [--output <path>]
  verify: --verify [--manifest <path>]
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
NAMESPACE = "jfg-phase5-completion-v1"
SIGNING_POLICY_PATH = ROOT / "config" / "phase5-completion-signing.json"
DEFAULT_MANIFEST_PATH = ROOT / "evidence" / "phase5-completion.json"
SSH_TIMEOUT_SECONDS = 60.0
MINIMUM_CAPTURED_FUNCTIONS = 20

# Files the manifest binds by digest.  Reordering or editing any of them
# invalidates an existing signed manifest instead of silently drifting.
BOUND_FILES = (
    "docs/planning/phase5-acceptance.md",
    "config/state-hash-schema-v1.json",
    "config/divergence-tolerance-v1.json",
    "config/phase5-completion-signing.json",
    "include/jfg/testkernel/sha256.hpp",
    "include/jfg/testkernel/world.hpp",
    "include/jfg/testkernel/scheduler.hpp",
    "include/jfg/testkernel/journal.hpp",
    "include/jfg/testkernel/capture.hpp",
    "include/jfg/testkernel/fakes.hpp",
    "include/jfg/testkernel/corpus.hpp",
    "src/testkernel/world.cpp",
    "src/testkernel/scheduler.cpp",
    "src/testkernel/journal.cpp",
    "src/testkernel/capture.cpp",
    "src/testkernel/fakes.cpp",
    "src/testkernel/corpus.cpp",
    "src/app/jfg_test_main.cpp",
    "src/evidence/phase5_capture_producer.cpp",
    "scripts/prepare_phase5_capture_table.py",
    "scripts/run_phase5_boundary_captures.py",
    "tests/testkernel_tests.cpp",
    "tests/test_phase5_policy.py",
)

REQUIRED_CTEST_NAMES = (
    "jfg.testkernel",
    "jfg.testkernel_self_check",
    "jfg.testkernel_repeat",
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


def _load_policy() -> tuple[dict[str, object], Path]:
    policy = json.loads(SIGNING_POLICY_PATH.read_text(encoding="utf-8"))
    if (
        policy.get("kind") != "jfg-phase5-completion-signing-policy"
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


def _validate_summary(summary: object) -> dict[str, object]:
    if (
        not isinstance(summary, dict)
        or summary.get("kind") != "jfg-phase5-boundary-capture-summary"
        or summary.get("schema_version") != 1
    ):
        raise CompletionError("capture summary is invalid")
    captured = summary.get("captured_functions")
    if not isinstance(captured, int) or captured < MINIMUM_CAPTURED_FUNCTIONS:
        raise CompletionError(
            "boundary-capture gate not met: fewer than "
            f"{MINIMUM_CAPTURED_FUNCTIONS} captured functions"
        )
    for key in ("private_ledger_sha256", "generated_root_inventory_sha256"):
        value = summary.get(key)
        if not isinstance(value, str) or len(value) != 64:
            raise CompletionError(f"capture summary missing {key}")
    return summary


def build(summary_path: Path, private_key: Path, output: Path) -> None:
    summary = _validate_summary(
        json.loads(summary_path.read_text(encoding="utf-8"))
    )
    document: dict[str, object] = {
        "schema_version": 1,
        "kind": "jfg-phase5-completion",
        "acceptance_contract": "docs/planning/phase5-acceptance.md",
        "bound_files": {
            path: _sha256_file(ROOT / Path(path)) for path in BOUND_FILES
        },
        "required_ctest_names": list(REQUIRED_CTEST_NAMES),
        "boundary_capture_summary": summary,
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
        prefix="phase5-sign-", dir=tools_root
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
    errors = verify(output)
    if errors:
        raise CompletionError(f"self-verification failed: {errors}")
    print(f"PHASE5 COMPLETION MANIFEST FINALIZED: {output}")


def verify(manifest_path: Path) -> list[str]:
    errors: list[str] = []
    try:
        document = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ["manifest unreadable"]
    if (
        not isinstance(document, dict)
        or document.get("kind") != "jfg-phase5-completion"
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
    try:
        _validate_summary(document.get("boundary_capture_summary"))
    except CompletionError as error:
        errors.append(str(error))

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
    with tempfile.TemporaryDirectory(prefix="phase5-verify-") as temp:
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
    parser.add_argument("--capture-summary", type=Path)
    parser.add_argument("--private-key", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_MANIFEST_PATH)
    arguments = parser.parse_args()

    if arguments.verify:
        errors = verify(arguments.manifest)
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print("valid" if not errors else "invalid")
        return 0 if not errors else 1

    if arguments.capture_summary is None or arguments.private_key is None:
        parser.error("--capture-summary and --private-key are required")
    try:
        build(arguments.capture_summary, arguments.private_key, arguments.output)
    except CompletionError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
