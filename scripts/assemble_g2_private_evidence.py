#!/usr/bin/env python3
"""Assemble local-only G2 evidence from a deliberately small, untrusted plan.

The plan names local artifacts but never supplies a digest, harness, source, or
binary identity.  This module is intentionally unusable in production until
the repository has a complete trusted pin policy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import tempfile
import re
from pathlib import Path, PurePosixPath
from typing import Mapping

try:
    from scripts import validate_g2_private_evidence as G2
    from scripts import g2_production_evidence_harness as H
except ModuleNotFoundError:
    import validate_g2_private_evidence as G2
    import g2_production_evidence_harness as H


ROOT = Path(__file__).resolve().parents[1]
PLAN_KIND = "jfg-g2-private-evidence-assembly-plan"
PLAN_SCHEMA = "../schemas/g2-private-evidence-assembly-plan.schema.json"
PLAN_KEYS = {"$schema", "schema_version", "kind", "executions"}
ENTRY_KEYS = {"requirement_id", "evidence_class", "id", "case_id", "environment", "artifacts"}
ARTIFACT_KEYS = {"path", "role"}
EXPECTED = (
    ("cpu-sections", "private-g3-compiler-product-binding"),
    ("cpu-sections", "private-g3-compiler-product-binding"),
    ("cpu-sections", "private-g3-compiler-product-binding"),
    ("overlay-lifecycle", "private-native-execution"),
    ("rsp-programs", "private-native-execution"),
    ("graphics-tasks", "private-native-execution"),
    ("graphics-tasks", "private-oracle-execution"),
    ("audio-tasks", "private-native-execution"),
    ("audio-tasks", "private-oracle-execution"),
    ("save-round-trip", "private-native-execution"),
    ("save-round-trip", "private-oracle-execution"),
    ("runtime-traps", "private-native-execution"),
    ("runtime-traps", "private-oracle-execution"),
    ("dependency-legal-selection", "human-approved-decision"),
)
IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]{1,70}[a-z0-9]$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
SUPPORTED_INPUT_ID = "jfg-us-retail"


class AssemblyError(RuntimeError):
    pass


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _inside_tools(path: Path, *, must_exist: bool) -> Path:
    absolute = Path(os.path.abspath(path))
    tools = Path(os.path.abspath(ROOT / "tools"))
    try:
        absolute.relative_to(tools)
    except ValueError as error:
        raise AssemblyError("local path rejected") from error
    current = tools
    try:
        if not current.is_dir() or G2._metadata_is_reparse(current.lstat()):
            raise AssemblyError("local path rejected")
        relative = absolute.relative_to(tools)
        for part in relative.parts:
            current /= part
            if current.exists() and G2._metadata_is_reparse(current.lstat()):
                raise AssemblyError("local path rejected")
        if must_exist and not absolute.exists():
            raise AssemblyError("local path rejected")
    except OSError as error:
        raise AssemblyError("local path rejected") from error
    allowed = G2._private_path_is_allowed(absolute)
    if allowed is not True:
        raise AssemblyError("local path rejected")
    return absolute


def _read(path: Path) -> bytes:
    try:
        return G2._read_regular_bounded(path, max_bytes=G2.MAX_ARTIFACT_BYTES, within=path.parent)
    except G2.EvidenceError as error:
        raise AssemblyError("artifact rejected") from error


def _planned_artifact_path(bundle: Path, textual: object) -> Path:
    if not isinstance(textual, str):
        raise AssemblyError("artifact rejected")
    parsed = PurePosixPath(textual)
    if (parsed.is_absolute() or not parsed.parts or any(part in {"", ".", ".."} for part in parsed.parts) or parsed.as_posix() != textual):
        raise AssemblyError("artifact rejected")
    return Path(os.path.abspath(bundle.joinpath(*parsed.parts)))


def _write_new_atomic(path: Path, payload: bytes) -> None:
    _inside_tools(path, must_exist=False)
    if path.exists():
        raise AssemblyError("output rejected")
    parent = path.parent
    if not parent.is_dir():
        raise AssemblyError("output rejected")
    descriptor = None
    temporary = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(prefix=".g2-", dir=parent)
        temporary = Path(temporary_name)
        os.write(descriptor, payload)
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        # link is atomic and fails if the final name appeared concurrently.
        os.link(temporary, path)
    except (OSError, ValueError) as error:
        raise AssemblyError("output rejected") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary is not None:
            try:
                temporary.unlink()
            except OSError:
                pass


def _trusted_pins(configs: list[dict[str, object]]) -> dict[str, str] | None:
    """Derive repository pins and the common supported input from canonical configs."""
    try:
        lock_bytes = G2._read_regular_bounded(G2.DEPENDENCY_LOCK, max_bytes=G2.MAX_DOCUMENT_BYTES)
        decision_bytes = G2._read_regular_bounded(G2.ARCHITECTURE_DECISION, max_bytes=G2.MAX_DOCUMENT_BYTES)
        lock = G2._json_loads(lock_bytes)
    except (G2.EvidenceError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return None
    try:
        decision_text = decision_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if not isinstance(lock, dict) or not G2._accepted_adr(decision_text):
        return None
    records = lock.get("repositories")
    if not isinstance(records, list):
        return None
    repositories: dict[str, dict[str, object]] = {}
    for item in records:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or item["id"] in repositories:
            return None
        repositories[item["id"]] = item
    commits = [repositories.get(name, {}).get("commit") for name in ("jfg-decomp", "n64recomp")]
    sources = {config.get("source_input_sha256") for config in configs}
    if len(sources) != 1 or not all(isinstance(item, str) and COMMIT.fullmatch(item) and len(set(item)) != 1 for item in commits) or not all(isinstance(item, str) and SHA256.fullmatch(item) and len(set(item)) != 1 for item in sources):
        return None
    return {"jfg_decomp_commit": commits[0], "n64recomp_commit": commits[1], "supported_input_id": SUPPORTED_INPUT_ID, "input_rom_sha256": sources.pop(), "dependency_lock_sha256": _sha(lock_bytes), "architecture_decision_sha256": _sha(decision_bytes)}  # type: ignore[return-value]


def _validate_plan(plan: object) -> list[dict[str, object]]:
    if not isinstance(plan, dict) or set(plan) != PLAN_KEYS:
        raise AssemblyError("plan rejected")
    if plan.get("$schema") != PLAN_SCHEMA or plan.get("schema_version") != 1 or plan.get("kind") != PLAN_KIND:
        raise AssemblyError("plan rejected")
    entries = plan.get("executions")
    if not isinstance(entries, list) or len(entries) != len(EXPECTED):
        raise AssemblyError("plan rejected")
    result: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    seen_paths: set[str] = set()
    for entry, expected in zip(entries, EXPECTED, strict=True):
        if not isinstance(entry, dict) or set(entry) != ENTRY_KEYS:
            raise AssemblyError("plan rejected")
        if (entry.get("requirement_id"), entry.get("evidence_class")) != expected:
            raise AssemblyError("plan rejected")
        if not isinstance(entry.get("id"), str) or IDENTIFIER.fullmatch(entry["id"]) is None or entry["id"] in seen_ids or not isinstance(entry.get("case_id"), str) or IDENTIFIER.fullmatch(entry["case_id"]) is None:
            raise AssemblyError("plan rejected")
        seen_ids.add(entry["id"])
        environment = entry.get("environment")
        if not isinstance(environment, dict) or set(environment) != {"environment_id", "platform_id", "architecture_id", "toolchain_sha256"} or any(not isinstance(environment.get(key), str) for key in ("environment_id", "platform_id", "architecture_id")) or any(IDENTIFIER.fullmatch(environment[key]) is None for key in ("environment_id", "platform_id", "architecture_id")) or not isinstance(environment.get("toolchain_sha256"), str) or SHA256.fullmatch(environment["toolchain_sha256"]) is None or len(set(environment["toolchain_sha256"])) == 1:
            raise AssemblyError("plan rejected")
        artifacts = entry.get("artifacts")
        if not isinstance(artifacts, list):
            raise AssemblyError("plan rejected")
        roles = [item.get("role") for item in artifacts if isinstance(item, dict)]
        executable = expected[1] in G2.EXECUTABLE_CLASSES
        valid_roles = (len(roles) >= 5 and roles[:3] == ["configuration", "input", "input"] and all(role == "output" for role in roles[3:-1]) and roles[-1] == "result") if executable else roles == ["configuration", "input", "decision", "result"]
        if not valid_roles:
            raise AssemblyError("plan rejected")
        for item in artifacts:
            if not isinstance(item, dict) or set(item) != ARTIFACT_KEYS or not isinstance(item.get("path"), str):
                raise AssemblyError("plan rejected")
            if item["path"] in seen_paths:
                raise AssemblyError("plan rejected")
            seen_paths.add(item["path"])
            policy_id = H.MAPPING_IDS.get(expected)
            prefix = f"production/{policy_id}/{entry['id']}/"
            if policy_id is None or not item["path"].startswith(prefix):
                raise AssemblyError("plan rejected")
        if executable and artifacts[1]["path"] != f"production/{policy_id}/{entry['id']}/case-input.bin":
            raise AssemblyError("plan rejected")
        if executable and PurePosixPath(artifacts[2]["path"]).name not in {"subject-probe", "subject-probe.exe"}:
            raise AssemblyError("plan rejected")
        result.append(entry)
    return result


def _assemble_for_tests(plan_path: Path, private_path: Path, public_path: Path, *, pins: Mapping[str, str] | None, harness_pins: Mapping[tuple[str, str], G2.PinnedHarness], validator: object = None) -> tuple[dict[str, object], dict[str, object]]:
    expected_pin_keys = {"jfg_decomp_commit", "n64recomp_commit", "supported_input_id", "input_rom_sha256", "dependency_lock_sha256", "architecture_decision_sha256"}
    digest_pin_keys = {"input_rom_sha256", "dependency_lock_sha256", "architecture_decision_sha256"}
    if pins is None or set(pins) != expected_pin_keys or pins.get("supported_input_id") != SUPPORTED_INPUT_ID or not all(isinstance(pins[key], str) and COMMIT.fullmatch(pins[key]) and len(set(pins[key])) != 1 for key in ("jfg_decomp_commit", "n64recomp_commit")) or not all(isinstance(pins[key], str) and SHA256.fullmatch(pins[key]) and len(set(pins[key])) != 1 for key in digest_pin_keys):
        raise AssemblyError("trusted pins unavailable")
    plan_file = _inside_tools(plan_path, must_exist=True)
    bundle = plan_file.parent
    try:
        plan_bytes = _read(plan_file)
        plan = G2._json_loads(plan_bytes)
        if G2._canonical_bytes(plan) != plan_bytes:
            raise ValueError("noncanonical")
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise AssemblyError("plan rejected") from error
    entries = _validate_plan(plan)
    for output in (private_path, public_path):
        _inside_tools(output, must_exist=False)
        if output.exists() or output.parent != bundle or output == plan_file:
            raise AssemblyError("output rejected")
    if private_path == public_path:
        raise AssemblyError("output rejected")
    pins_copy = dict(pins)
    pins_sha = _sha(G2._canonical_bytes(pins_copy))
    requirements: dict[str, dict[str, object]] = {identifier: {"evidence_record_count": 0, "executable_evidence_count": 0, "executions": [], "unresolved": []} for identifier in G2.REQUIREMENT_IDS}
    pending: list[tuple[Path, bytes]] = []
    source_copies: list[tuple[Path, str, bytes]] = []
    for entry in entries:
        requirement_id = str(entry["requirement_id"])
        evidence_class = str(entry["evidence_class"])
        pin = harness_pins.get((requirement_id, evidence_class))
        if pin is None:
            raise AssemblyError("trusted harness unavailable")
        artifacts: list[dict[str, object]] = []
        subject_sha = None
        result_path = None
        config_document = None
        for declared in entry["artifacts"]:  # type: ignore[index]
            assert isinstance(declared, dict)
            textual = declared["path"]
            role = declared["role"]
            artifact_path = _planned_artifact_path(bundle, textual)
            if role == "result":
                _inside_tools(artifact_path, must_exist=False)
                if artifact_path.exists():
                    raise AssemblyError("output rejected")
                result_path = artifact_path
                artifacts.append({"path": textual, "role": role, "sha256": ""})
                continue
            _inside_tools(artifact_path, must_exist=True)
            payload = _read(artifact_path)
            digest = _sha(payload)
            artifacts.append({"path": textual, "role": role, "sha256": digest})
            source_copies.append((artifact_path, str(textual), payload))
            if role == "configuration":
                try:
                    config_document = G2._json_loads(payload)
                    expected_config_keys = H.configuration_keys(
                        (requirement_id, evidence_class)
                    )
                    if G2._canonical_bytes(config_document) != payload or not isinstance(config_document, dict) or set(config_document) != expected_config_keys:
                        raise ValueError("config")
                except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
                    raise AssemblyError("artifact rejected") from None
            if role == "decision" or (role == "input" and subject_sha is None):
                subject_sha = digest
        if subject_sha is None or result_path is None or not isinstance(config_document, dict):
            raise AssemblyError("artifact rejected")
        source_sha = pins_copy["dependency_lock_sha256"] if requirement_id == "dependency-legal-selection" else pins_copy["input_rom_sha256"]
        environment = entry["environment"]
        execution: dict[str, object] = {
            "id": entry["id"], "evidence_class": evidence_class,
            "harness_id": pin.harness_id, "harness_sha256": pin.script_sha256,
            "case_id": entry["case_id"], "subject_sha256": subject_sha,
            "source_input_sha256": source_sha, "pins_sha256": pins_sha,
            "environment": environment, "environment_sha256": _sha(G2._canonical_bytes(environment)),
            "input_set_sha256": _sha(G2._canonical_bytes([item for item in artifacts if item["role"] in {"configuration", "input", "decision"}])),
            "output_set_sha256": _sha(G2._canonical_bytes([item for item in artifacts if item["role"] in {"output", "log"}])),
            "artifact_set_sha256": "", "result_sha256": "", "observed_exit_code": 0,
            "passed": True, "artifacts": artifacts,
        }
        if (config_document.get("requirement_id"), config_document.get("evidence_class"), config_document.get("case_id"), config_document.get("subject_sha256"), config_document.get("source_input_sha256")) != (requirement_id, evidence_class, entry["case_id"], subject_sha, source_sha):
            raise AssemblyError("artifact rejected")
        result = G2._canonical_bytes(G2._result_expectation(execution, requirement_id))
        result_digest = _sha(result)
        artifacts[-1]["sha256"] = result_digest
        execution["result_sha256"] = result_digest
        execution["artifact_set_sha256"] = _sha(G2._canonical_bytes(artifacts))
        pending.append((result_path, result))
        requirement = requirements[requirement_id]
        requirement["executions"].append(execution)  # type: ignore[index]
    for requirement in requirements.values():
        executions = requirement["executions"]
        requirement["evidence_record_count"] = len(executions)  # type: ignore[arg-type]
        requirement["executable_evidence_count"] = sum(item["evidence_class"] in G2.EXECUTABLE_CLASSES for item in executions)  # type: ignore[index]
    private: dict[str, object] = {"$schema": "../../../schemas/g2-private-evidence.schema.json", "schema_version": 2, "kind": "jfg-g2-private-executable-evidence", "pins": pins_copy, "requirements": requirements, "evidence_set_sha256": _sha(G2._canonical_bytes(requirements))}
    public_requirements = {key: {"passed": True, "evidence_record_count": value["evidence_record_count"], "executable_evidence_count": value["executable_evidence_count"], "unresolved_count": 0, "result_sha256": _sha(G2._canonical_bytes(value))} for key, value in requirements.items()}
    public_pins = {
        key: value for key, value in pins_copy.items() if key != "input_rom_sha256"
    }
    public: dict[str, object] = {"$schema": "../schemas/g2-completion-evidence.schema.json", "schema_version": 2, "kind": "jfg-g2-completion-evidence", "privacy": "public-safe-aggregate-only", "record_class": "maintainer-reviewed-public-aggregate", "pins": public_pins, "requirements": public_requirements, "evidence_set_sha256": _sha(G2._canonical_bytes(public_requirements)), "gate": {"id": "G2", "decision": "go", "broad_phase4_authorized": True, "all_required_checks_passed": True}}
    pending.extend(((private_path, G2._canonical_bytes(private)), (public_path, G2._canonical_bytes(public))))
    # Build an isolated mirror.  Every copied source is opened again and must
    # retain its original bytes, so a post-plan replacement cannot race into
    # validation or publication.
    published: list[Path] = []
    try:
        with tempfile.TemporaryDirectory(dir=ROOT / "tools", prefix="g2-stage-") as stage_name:
            stage = Path(stage_name)
            for source, textual, expected in source_copies:
                if _read(source) != expected:
                    raise AssemblyError("artifact rejected")
                target = _planned_artifact_path(stage, textual)
                target.parent.mkdir(parents=True, exist_ok=True)
                _write_new_atomic(target, expected)
            for path, payload in pending:
                # Result artifacts retain their planned relative location;
                # documents use their final filenames in the staged root.
                target = _planned_artifact_path(stage, path.relative_to(bundle).as_posix())
                target.parent.mkdir(parents=True, exist_ok=True)
                _write_new_atomic(target, payload)
            if validator is not None:
                errors = validator(private, public, stage, harness_pins)  # type: ignore[operator]
                if errors:
                    raise AssemblyError("assembled evidence rejected")
            for path, payload in pending:
                _write_new_atomic(path, payload)
                published.append(path)
            for source, _textual, expected in source_copies:
                if _read(source) != expected:
                    raise AssemblyError("artifact rejected")
    except AssemblyError:
        for path in reversed(published):
            try:
                path.unlink()
            except OSError:
                pass
        raise
    return private, public


def assemble(plan_path: Path, private_path: Path, public_path: Path) -> None:
    # The private helper does all parser/path work; this preflight extracts only
    # canonical executable configurations for the trusted supported-input pin.
    try:
        raw = _read(_inside_tools(plan_path, must_exist=True))
        plan = G2._json_loads(raw)
        entries = _validate_plan(plan)
        configs: list[dict[str, object]] = []
        for entry in entries:
            if entry["evidence_class"] not in G2.EXECUTABLE_CLASSES:
                continue
            config_path = _planned_artifact_path(plan_path.parent, entry["artifacts"][0]["path"])  # type: ignore[index]
            config = G2._json_loads(_read(config_path))
            if G2._canonical_bytes(config) != _read(config_path) or not isinstance(config, dict) or set(config) != H.configuration_keys((str(entry["requirement_id"]), str(entry["evidence_class"]))):
                raise ValueError("config")
            configs.append(config)
    except (AssemblyError, G2.EvidenceError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        raise AssemblyError("plan rejected") from None
    pins = _trusted_pins(configs)
    if pins is None or len(G2.PRODUCTION_HARNESS_PINS) != len(set(EXPECTED)):
        raise AssemblyError("trusted pins unavailable")
    _assemble_for_tests(plan_path, private_path, public_path, pins=pins, harness_pins=G2.PRODUCTION_HARNESS_PINS, validator=lambda private, public, stage, _policy: G2.validate_documents(private, public, G2.load_json(G2.PRIVATE_SCHEMA), G2.load_json(G2.PUBLIC_SCHEMA), stage))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--private-evidence", required=True, type=Path)
    parser.add_argument("--public-evidence", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        assemble(args.plan, args.private_evidence, args.public_evidence)
    except AssemblyError:
        print("G2 evidence assembly failed", file=os.sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
