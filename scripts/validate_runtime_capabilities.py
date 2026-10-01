#!/usr/bin/env python3
"""Validate the public-safe Phase 3 runtime capability matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

if __package__:
    from .public_safe import validate_canonical_json_numbers, validate_public_safe
    from .runtime_spike_models import (
        AddressTranslator,
        BoundedDmaBroker,
        CacheCoherencyGate,
        DecompressionGateway,
        FALLBACK_CONTRACT_REGISTRY,
        RegisterBroker,
        SyntheticControllerPak,
        TESTED_FALLBACK_TESTS,
        TrapInventory,
    )
else:
    from public_safe import validate_canonical_json_numbers, validate_public_safe
    from runtime_spike_models import (
        AddressTranslator,
        BoundedDmaBroker,
        CacheCoherencyGate,
        DecompressionGateway,
        FALLBACK_CONTRACT_REGISTRY,
        RegisterBroker,
        SyntheticControllerPak,
        TESTED_FALLBACK_TESTS,
        TrapInventory,
    )


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MATRIX = ROOT / "config" / "runtime-capability-matrix.json"
DEFAULT_SCHEMA = ROOT / "schemas" / "runtime-capability-matrix.schema.json"

REQUIRED_CAPABILITIES = frozenset(
    {
        "direct-rcp-registers",
        "kseg-aliases",
        "tlb-mappings",
        "cache-operations",
        "pi-dma",
        "decompression",
        "timers",
        "message-queues",
        "controller-pak-save",
        "anti-tamper-traps",
    }
)
REQUIRED_SAVE_DEVICES = frozenset(
    {"flashram", "controller-pak", "rumble-pak", "eeprom", "sram"}
)
REQUIRED_TRAP_CLASSES = frozenset(
    {"cpu-break", "cpu-syscall", "switch-bounds", "boot-self-check"}
)
PINNED_RUNTIME_BASELINE = {
    "jfg_decomp": "b49aa4791e8fb1e7acd3bba10346876358d0a9a7",
    "n64recomp": "ffb39cdad1da5de07eaaa48bd1db4a89a7986771",
    "n64modernruntime": "589bbf018a3e6d3646ddf7de1e7919f1b7e99bb1",
}
REQUIRED_G2_BLOCKERS = frozenset(
    {
        "anti-tamper-traps",
        "cache-operations",
        "controller-pak-save",
        "decompression",
        "direct-rcp-registers",
        "kseg-aliases",
        "pi-dma",
        "tlb-mappings",
    }
)
CAPABILITY_BASELINE = {
    "direct-rcp-registers": (
        "unsupported",
        True,
        "strict-register-broker",
        "unknown-register-fails-closed",
    ),
    "kseg-aliases": (
        "partial",
        True,
        "central-address-translator",
        "kseg-alias-translation",
    ),
    "tlb-mappings": (
        "unsupported",
        True,
        "explicit-static-mappings",
        "explicit-tlb-mapping",
    ),
    "cache-operations": (
        "partial",
        True,
        "host-code-coherency-gate",
        "cache-coherency-gate",
    ),
    "pi-dma": (
        "partial",
        True,
        "bounded-dma-broker",
        "bounded-dma-copy",
    ),
    "decompression": (
        "unverified",
        True,
        "bounded-decompression-callback",
        "decompressor-callback-boundary",
    ),
    "timers": ("partial", False, None, None),
    "message-queues": ("supported", False, None, None),
    "controller-pak-save": (
        "unsupported",
        True,
        "native-controller-pak-layer",
        "synthetic-controller-pak-lifecycle",
    ),
    "anti-tamper-traps": (
        "partial",
        True,
        "strict-trap-manifest",
        "trap-inventory-completeness",
    ),
}
SAVE_DEVICE_BASELINE = {
    "flashram": ("supported", None, None),
    "controller-pak": (
        "unsupported",
        "native-controller-pak-layer",
        "synthetic-controller-pak-lifecycle",
    ),
    "rumble-pak": ("supported", None, None),
    "eeprom": ("supported", None, None),
    "sram": ("partial", None, None),
}
TRAP_BASELINE = {
    "cpu-break": (
        "abort-only",
        True,
        "strict-trap-manifest",
        "trap-inventory-completeness",
    ),
    "cpu-syscall": (
        "missing-handler",
        True,
        "strict-trap-manifest",
        "trap-inventory-completeness",
    ),
    "switch-bounds": ("abort-only", False, None, None),
    "boot-self-check": (
        "unhandled",
        True,
        "strict-trap-manifest",
        "trap-inventory-completeness",
    ),
}
EXPECTED_IMPLEMENTATION_BINDINGS = {
    "strict-register-broker": (RegisterBroker, "unknown-register-fails-closed"),
    "central-address-translator": (AddressTranslator, "kseg-alias-translation"),
    "explicit-static-mappings": (AddressTranslator, "explicit-tlb-mapping"),
    "host-code-coherency-gate": (CacheCoherencyGate, "cache-coherency-gate"),
    "bounded-dma-broker": (BoundedDmaBroker, "bounded-dma-copy"),
    "bounded-decompression-callback": (
        DecompressionGateway,
        "decompressor-callback-boundary",
    ),
    "native-controller-pak-layer": (
        SyntheticControllerPak,
        "synthetic-controller-pak-lifecycle",
    ),
    "strict-trap-manifest": (TrapInventory, "trap-inventory-completeness"),
}
EXPECTED_CURRENT_PIN_MATRIX_SHA256 = (
    "0c1cdc11bbe80e0ba4b84a603f10687ad94183f2185bc484af693741c7a06ec7"
)


def canonical_hash(value: object) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()

EXPECTED_FALLBACK_CONTRACTS = {
    "cache-operations": {
        "verified_properties": {
            "per-write-invalidation-accounting",
            "reject-execution-while-dirty",
        },
        "unproven_properties": {
            "native-code-page-integration",
            "target-mutation-site-coverage",
        },
    },
    "decompression": {
        "verified_properties": {
            "input-bound",
            "missing-handler-rejection",
            "output-bound",
            "output-type-check",
        },
        "unproven_properties": {
            "target-algorithm",
            "target-byte-compatibility",
        },
    },
    "controller-pak-save": {
        "verified_properties": {
            "allocation",
            "bounds",
            "capacity",
            "delete",
            "enumeration",
            "logical-snapshot-reload",
            "read",
            "write",
        },
        "unproven_properties": {
            "atomic-durable-host-persistence",
            "controller-discovery",
            "native-format-compatibility",
            "repair-and-corruption",
            "target-parity",
        },
    },
}

def load_json(path: Path) -> object:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def unique_records(records: object, field: str, label: str) -> tuple[dict[str, dict], list[str]]:
    errors: list[str] = []
    indexed: dict[str, dict] = {}
    if not isinstance(records, list):
        return indexed, [f"{label}: expected an array"]
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"{label}[{index}]: expected an object")
            continue
        record_id = record.get(field)
        if not isinstance(record_id, str):
            errors.append(f"{label}[{index}].{field}: expected a string")
        elif record_id in indexed:
            errors.append(f"{label}: duplicate {field}: {record_id}")
        else:
            indexed[record_id] = record
    return indexed, errors


def validate_fallback_contract(
    owner_id: str, fallback: object, expected: dict[str, set[str]]
) -> list[str]:
    if not isinstance(fallback, dict):
        return [f"{owner_id}: structured synthetic contract is missing"]
    errors: list[str] = []
    for field, expected_values in expected.items():
        actual = fallback.get(field)
        actual_values = (
            set(actual)
            if isinstance(actual, list) and all(isinstance(item, str) for item in actual)
            else set()
        )
        if actual_values != expected_values:
            errors.append(
                f"{owner_id}: {field} differs from the tested synthetic contract"
            )
    return errors


def validate_fallback_binding(owner_id: str, fallback: object) -> list[str]:
    """Require a declared contract ID to identify one executable model/test pair."""
    if fallback is None:
        return []
    if not isinstance(fallback, dict):
        return [f"{owner_id}: fallback binding is malformed"]
    contract_id = fallback.get("id")
    binding = FALLBACK_CONTRACT_REGISTRY.get(contract_id)
    if binding is None:
        return [f"{owner_id}: fallback contract ID is not in the implementation registry"]
    if fallback.get("test_id") != binding.test_id:
        return [f"{owner_id}: fallback test ID does not match its implementation registry"]
    return []


def validate_implementation_registry() -> list[str]:
    """Reject registry drift in either implementation class or test binding."""
    errors: list[str] = []
    if set(FALLBACK_CONTRACT_REGISTRY) != set(EXPECTED_IMPLEMENTATION_BINDINGS):
        errors.append("fallback implementation registry IDs differ from baseline")
    for contract_id, (implementation, test_id) in EXPECTED_IMPLEMENTATION_BINDINGS.items():
        binding = FALLBACK_CONTRACT_REGISTRY.get(contract_id)
        if binding is None:
            continue
        if binding.implementation is not implementation:
            errors.append(
                f"{contract_id}: fallback implementation class differs from baseline"
            )
        if binding.test_id != test_id:
            errors.append(f"{contract_id}: fallback implementation test differs from baseline")
    if TESTED_FALLBACK_TESTS != frozenset(
        test_id for _implementation, test_id in EXPECTED_IMPLEMENTATION_BINDINGS.values()
    ):
        errors.append("tested fallback IDs differ from the independent baseline")
    return errors


def validate_pinned_record(
    owner_id: str,
    record: dict,
    expected: tuple[str, bool, str | None, str | None],
) -> list[str]:
    runtime_status, fundamental, fallback_id, fallback_test_id = expected
    errors: list[str] = []
    if record.get("runtime_status") != runtime_status:
        errors.append(f"{owner_id}: current-pin runtime status differs from baseline")
    if record.get("fundamental_blocker") is not fundamental:
        errors.append(f"{owner_id}: current-pin blocker verdict differs from baseline")
    fallback = record.get("fallback")
    actual_id = fallback.get("id") if isinstance(fallback, dict) else None
    actual_test_id = fallback.get("test_id") if isinstance(fallback, dict) else None
    if actual_id != fallback_id or actual_test_id != fallback_test_id:
        errors.append(f"{owner_id}: current-pin fallback binding differs from baseline")
    return errors


def validate_matrix_document(document: object, schema: object) -> list[str]:
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    errors = [
        f"schema {'.'.join(str(item) for item in error.path) or '$'}: {error.message}"
        for error in sorted(validator.iter_errors(document), key=lambda item: list(item.path))
    ]
    errors.extend(validate_implementation_registry())
    errors.extend(validate_public_safe(document))
    errors.extend(validate_canonical_json_numbers(document))
    if not isinstance(document, dict):
        return sorted(set(errors))

    gate = document.get("gate")
    if not isinstance(gate, dict):
        errors.append("G2: current-pin gate record is missing")
    else:
        if gate.get("id") != "G2":
            errors.append("G2: gate ID differs from the pinned baseline")
        if gate.get("decision") != "no-go-current-pin":
            errors.append("G2: current-pin decision must remain no-go")
        if gate.get("broad_phase4_authorized") is not False:
            errors.append("G2: broad Phase 4 cannot be authorized at the current pin")
        blocker_ids = gate.get("required_blocker_ids")
        actual_blockers = (
            set(blocker_ids)
            if isinstance(blocker_ids, list)
            and all(isinstance(item, str) for item in blocker_ids)
            else set()
        )
        if actual_blockers != REQUIRED_G2_BLOCKERS:
            errors.append("G2: required current-pin blocker IDs differ from baseline")

    capabilities, record_errors = unique_records(
        document.get("capabilities"), "id", "capabilities"
    )
    errors.extend(record_errors)
    if set(capabilities) != REQUIRED_CAPABILITIES:
        missing = sorted(REQUIRED_CAPABILITIES - set(capabilities))
        extra = sorted(set(capabilities) - REQUIRED_CAPABILITIES)
        errors.append(f"capability IDs differ; missing={missing}, extra={extra}")

    evidence_ids: set[str] = set()
    capability_fallback_ids: set[str] = set()
    for capability_id, capability in capabilities.items():
        capability_evidence_ids: set[str] = set()
        for field in ("target_evidence", "runtime_evidence"):
            evidence, record_errors = unique_records(
                capability.get(field), "id", f"{capability_id}.{field}"
            )
            errors.extend(record_errors)
            repeated = capability_evidence_ids & set(evidence)
            if repeated:
                errors.append(
                    f"{capability_id}: evidence IDs repeat across evidence collections: "
                    f"{sorted(repeated)}"
                )
            capability_evidence_ids.update(evidence)
        repeated = evidence_ids & capability_evidence_ids
        if repeated:
            errors.append(f"evidence IDs must be globally unique: {sorted(repeated)}")
        evidence_ids.update(capability_evidence_ids)

        expected_baseline = CAPABILITY_BASELINE.get(capability_id)
        if expected_baseline is not None:
            errors.extend(
                validate_pinned_record(capability_id, capability, expected_baseline)
            )
        unresolved = capability.get("runtime_status") != "supported"
        fundamental = capability.get("fundamental_blocker") is True
        fallback = capability.get("fallback")
        if isinstance(fallback, dict):
            fallback_id = fallback.get("id")
            if isinstance(fallback_id, str):
                if fallback_id in capability_fallback_ids:
                    errors.append(f"capabilities: duplicate fallback id: {fallback_id}")
                capability_fallback_ids.add(fallback_id)
        if fundamental and unresolved:
            if not isinstance(fallback, dict):
                errors.append(f"{capability_id}: fundamental blocker lacks fallback")
                continue
            test_id = fallback.get("test_id")
            if fallback.get("status") != "synthetic-tested":
                errors.append(f"{capability_id}: fallback is not synthetic-tested")
            if test_id not in TESTED_FALLBACK_TESTS:
                errors.append(f"{capability_id}: fallback test is not in the tested registry")
        errors.extend(validate_fallback_binding(capability_id, fallback))
        expected_contract = EXPECTED_FALLBACK_CONTRACTS.get(capability_id)
        if expected_contract is not None:
            errors.extend(
                validate_fallback_contract(
                    capability_id, capability.get("fallback"), expected_contract
                )
            )

    save_devices, record_errors = unique_records(
        document.get("save_devices"), "id", "save_devices"
    )
    errors.extend(record_errors)
    if set(save_devices) != REQUIRED_SAVE_DEVICES:
        errors.append("save-device IDs differ from the required Phase 3 matrix")
    for device_id, device in save_devices.items():
        expected = SAVE_DEVICE_BASELINE.get(device_id)
        if expected is None:
            continue
        runtime_status, fallback_id, fallback_test_id = expected
        if device.get("runtime_status") != runtime_status:
            errors.append(f"{device_id}: current-pin runtime status differs from baseline")
        fallback = device.get("fallback")
        actual_id = fallback.get("id") if isinstance(fallback, dict) else None
        actual_test_id = fallback.get("test_id") if isinstance(fallback, dict) else None
        if actual_id != fallback_id or actual_test_id != fallback_test_id:
            errors.append(f"{device_id}: current-pin fallback binding differs from baseline")
        errors.extend(validate_fallback_binding(device_id, fallback))
    controller_pak = save_devices.get("controller-pak", {})
    controller_fallback = controller_pak.get("fallback")
    if controller_pak.get("runtime_status") != "unsupported":
        errors.append("controller-pak: pinned runtime status must remain unsupported")
    if not isinstance(controller_fallback, dict) or controller_fallback.get(
        "test_id"
    ) != "synthetic-controller-pak-lifecycle":
        errors.append("controller-pak: tested native-accessory fallback is missing")
    errors.extend(
        validate_fallback_contract(
            "controller-pak",
            controller_fallback,
            EXPECTED_FALLBACK_CONTRACTS["controller-pak-save"],
        )
    )
    controller_capability = capabilities.get("controller-pak-save", {})
    controller_evidence = controller_capability.get("target_evidence", [])
    has_private_roundtrip = any(
        isinstance(item, dict)
        and item.get("id") == "target-controller-pak-boot-roundtrip"
        and item.get("kind") == "private-dynamic-aggregate"
        and item.get("confidence") == "observed"
        and item.get("gate_effect") == "oracle-only-does-not-clear-g2"
        for item in controller_evidence
    )
    if not has_private_roundtrip:
        errors.append(
            "controller-pak: oracle-only boot evidence must explicitly leave G2 blocked"
        )

    traps, record_errors = unique_records(
        document.get("trap_inventory"), "id", "trap_inventory"
    )
    errors.extend(record_errors)
    if set(traps) != REQUIRED_TRAP_CLASSES:
        errors.append("trap inventory differs from the required Phase 3 classes")
    for trap_id, trap in traps.items():
        expected = TRAP_BASELINE.get(trap_id)
        if expected is None:
            continue
        disposition, fundamental, contract_id, test_id = expected
        if trap.get("runtime_disposition") != disposition:
            errors.append(f"{trap_id}: current-pin disposition differs from baseline")
        if trap.get("fundamental_blocker") is not fundamental:
            errors.append(f"{trap_id}: current-pin blocker verdict differs from baseline")
        if trap.get("fallback_contract_id") != contract_id or trap.get(
            "fallback_test_id"
        ) != test_id:
            errors.append(f"{trap_id}: trap fallback binding differs from baseline")
        if contract_id is not None:
            binding = FALLBACK_CONTRACT_REGISTRY.get(contract_id)
            if binding is None or binding.test_id != test_id:
                errors.append(f"{trap_id}: trap fallback is not in the implementation registry")

    if canonical_hash(document) != EXPECTED_CURRENT_PIN_MATRIX_SHA256:
        errors.append("current-pin runtime matrix differs from the maintainer-reviewed lock")

    return sorted(set(errors))


def validate_pins(document: object, dependency_lock: object) -> list[str]:
    if not isinstance(document, dict) or not isinstance(dependency_lock, dict):
        return ["matrix or dependency lock is not an object"]
    repositories = dependency_lock.get("repositories")
    if not isinstance(repositories, list):
        return ["dependency lock has no repository list"]
    locked = {
        item.get("id"): item.get("commit")
        for item in repositories
        if isinstance(item, dict)
    }
    pins = document.get("pins")
    if not isinstance(pins, dict):
        return ["matrix pins are missing"]
    locked_by_matrix_name = {
        "jfg_decomp": locked.get("jfg-decomp"),
        "n64recomp": locked.get("n64recomp"),
        "n64modernruntime": locked.get("n64modernruntime"),
    }
    errors: list[str] = []
    for name, expected_commit in PINNED_RUNTIME_BASELINE.items():
        if pins.get(name) != expected_commit:
            errors.append(f"pinned runtime baseline mismatch for {name}")
        if locked_by_matrix_name.get(name) != expected_commit:
            errors.append(f"dependency lock baseline mismatch for {name}")
        if pins.get(name) != locked_by_matrix_name.get(name):
            errors.append(f"pin mismatch for {name}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    arguments = parser.parse_args()

    try:
        matrix = load_json(arguments.matrix)
        schema = load_json(arguments.schema)
        dependency_lock = load_json(ROOT / "dependencies.lock.json")
        errors = validate_matrix_document(matrix, schema)
        errors.extend(validate_pins(matrix, dependency_lock))
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"Runtime capability validation failed: {error}", file=sys.stderr)
        return 1

    if errors:
        print("Runtime capability validation failed:", file=sys.stderr)
        for error in sorted(set(errors)):
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Runtime capability validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
