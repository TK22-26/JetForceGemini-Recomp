from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from unittest import mock

import scripts.validate_runtime_capabilities as runtime_validator
from scripts.runtime_spike_models import (
    AddressMapping,
    AddressTranslator,
    BoundedDmaBroker,
    CacheCoherencyGate,
    DecompressionGateway,
    DmaBoundsError,
    FALLBACK_CONTRACT_REGISTRY,
    FallbackContractBinding,
    GapModelError,
    RegisterBroker,
    SaveDeviceError,
    SyntheticControllerPak,
    TESTED_FALLBACK_TESTS,
    TrapAbort,
    TrapInventory,
    TrapInventoryError,
    TrapRecord,
    UnknownRegister,
    UnmappedAddress,
)
from scripts.validate_runtime_capabilities import (
    ROOT,
    load_json,
    validate_matrix_document,
    validate_pins,
)


class RuntimeCapabilityMatrixTests(unittest.TestCase):
    def load_matrix_and_schema(self) -> tuple[dict[str, object], dict[str, object]]:
        matrix = load_json(ROOT / "config" / "runtime-capability-matrix.json")
        schema = load_json(
            ROOT / "schemas" / "runtime-capability-matrix.schema.json"
        )
        assert isinstance(matrix, dict)
        assert isinstance(schema, dict)
        return matrix, schema

    def test_runtime_capability_matrix_and_pins_validate(self) -> None:
        matrix, schema = self.load_matrix_and_schema()
        dependency_lock = load_json(ROOT / "dependencies.lock.json")

        self.assertEqual(validate_matrix_document(matrix, schema), [])
        self.assertEqual(validate_pins(matrix, dependency_lock), [])

    def test_every_declared_tested_fallback_has_a_synthetic_contract(self) -> None:
        matrix = json.loads(
            (ROOT / "config" / "runtime-capability-matrix.json").read_text(
                encoding="utf-8"
            )
        )
        referenced = {
            (record["fallback"]["id"], record["fallback"]["test_id"])
            for collection in (matrix["capabilities"], matrix["save_devices"])
            for record in collection
            if record["fallback"] is not None
        }
        referenced.update(
            (record["fallback_contract_id"], record["fallback_test_id"])
            for record in matrix["trap_inventory"]
            if record["fallback_test_id"] is not None
        )
        executable_test_methods = {
            method
            for candidate in globals().values()
            if isinstance(candidate, type)
            and issubclass(candidate, unittest.TestCase)
            for method in dir(candidate)
            if method.startswith("test_")
        }
        for contract_id, test_id in referenced:
            binding = FALLBACK_CONTRACT_REGISTRY[contract_id]
            self.assertEqual(binding.test_id, test_id)
            self.assertIsInstance(binding.implementation, type)
            self.assertIn(test_id, TESTED_FALLBACK_TESTS)
            self.assertIn(
                f"test_{test_id.replace('-', '_')}",
                executable_test_methods,
                f"fallback test ID has no executable unittest: {test_id}",
            )

    def test_fallback_implementation_class_drift_is_rejected(self) -> None:
        matrix, schema = self.load_matrix_and_schema()
        drifted = dict(FALLBACK_CONTRACT_REGISTRY)
        drifted["strict-trap-manifest"] = FallbackContractBinding(
            RegisterBroker, "trap-inventory-completeness"
        )
        with mock.patch.object(
            runtime_validator, "FALLBACK_CONTRACT_REGISTRY", drifted
        ):
            errors = validate_matrix_document(matrix, schema)
        self.assertIn(
            "strict-trap-manifest: fallback implementation class differs from baseline",
            errors,
        )

    def test_current_pin_all_clear_inversion_is_rejected_semantically(self) -> None:
        matrix, schema = self.load_matrix_and_schema()
        invalid = copy.deepcopy(matrix)
        gate = invalid["gate"]
        assert isinstance(gate, dict)
        gate["decision"] = "go"
        gate["broad_phase4_authorized"] = True
        gate["required_blocker_ids"] = []
        for capability in invalid["capabilities"]:
            assert isinstance(capability, dict)
            capability["runtime_status"] = "supported"
            capability["fundamental_blocker"] = False
            capability["fallback"] = None
        for device in invalid["save_devices"]:
            assert isinstance(device, dict)
            device["runtime_status"] = "supported"
            device["fallback"] = None
        for trap in invalid["trap_inventory"]:
            assert isinstance(trap, dict)
            trap["runtime_disposition"] = "supported"
            trap["fundamental_blocker"] = False
            trap["fallback_contract_id"] = None
            trap["fallback_test_id"] = None

        errors = validate_matrix_document(invalid, schema)
        self.assertIn("G2: current-pin decision must remain no-go", errors)
        self.assertIn(
            "direct-rcp-registers: current-pin runtime status differs from baseline",
            errors,
        )
        self.assertIn(
            "boot-self-check: current-pin disposition differs from baseline", errors
        )

    def test_matrix_and_dependency_pin_flips_cannot_redefine_baseline(self) -> None:
        matrix, _schema = self.load_matrix_and_schema()
        dependency_lock = load_json(ROOT / "dependencies.lock.json")
        assert isinstance(dependency_lock, dict)
        for matrix_name, repository_id in (
            ("jfg_decomp", "jfg-decomp"),
            ("n64recomp", "n64recomp"),
            ("n64modernruntime", "n64modernruntime"),
        ):
            with self.subTest(matrix_name=matrix_name):
                invalid_matrix = copy.deepcopy(matrix)
                invalid_lock = copy.deepcopy(dependency_lock)
                invalid_matrix["pins"][matrix_name] = "0" * 40
                repository = next(
                    item
                    for item in invalid_lock["repositories"]
                    if item.get("id") == repository_id
                )
                repository["commit"] = "0" * 40
                errors = validate_pins(invalid_matrix, invalid_lock)
                self.assertIn(
                    f"pinned runtime baseline mismatch for {matrix_name}", errors
                )
                self.assertIn(
                    f"dependency lock baseline mismatch for {matrix_name}", errors
                )

    def test_boot_self_check_uses_trap_contract_not_register_broker(self) -> None:
        matrix, schema = self.load_matrix_and_schema()
        trap = next(
            item
            for item in matrix["trap_inventory"]
            if item.get("id") == "boot-self-check"
        )
        self.assertEqual(trap["fallback_contract_id"], "strict-trap-manifest")
        self.assertEqual(trap["fallback_test_id"], "trap-inventory-completeness")

        invalid = copy.deepcopy(matrix)
        invalid_trap = next(
            item
            for item in invalid["trap_inventory"]
            if item.get("id") == "boot-self-check"
        )
        invalid_trap["fallback_contract_id"] = "strict-register-broker"
        invalid_trap["fallback_test_id"] = "unknown-register-fails-closed"
        errors = validate_matrix_document(invalid, schema)
        self.assertIn(
            "boot-self-check: trap fallback binding differs from baseline", errors
        )

    def test_fundamental_blocker_without_tested_fallback_is_rejected(self) -> None:
        matrix, schema = self.load_matrix_and_schema()
        invalid = copy.deepcopy(matrix)
        capabilities = invalid["capabilities"]
        assert isinstance(capabilities, list)
        capability = next(
            item
            for item in capabilities
            if isinstance(item, dict) and item.get("id") == "tlb-mappings"
        )
        capability["fallback"] = None
        errors = validate_matrix_document(invalid, schema)
        self.assertTrue(any("fundamental blocker lacks fallback" in item for item in errors))

    def test_private_path_detail_is_rejected(self) -> None:
        matrix, schema = self.load_matrix_and_schema()
        invalid = copy.deepcopy(matrix)
        capabilities = invalid["capabilities"]
        assert isinstance(capabilities, list)
        capability = capabilities[0]
        assert isinstance(capability, dict)
        capability["next_gate"] = (
            "Inspect " + "C:" + "\\Users" + "\\Example" + "\\private.bin"
        )
        errors = validate_matrix_document(invalid, schema)
        self.assertTrue(any("private-path or raw-symbol" in item for item in errors))

    def test_controller_pak_cannot_be_marked_supported_at_this_pin(self) -> None:
        matrix, schema = self.load_matrix_and_schema()
        invalid = copy.deepcopy(matrix)
        devices = invalid["save_devices"]
        assert isinstance(devices, list)
        device = next(
            item
            for item in devices
            if isinstance(item, dict) and item.get("id") == "controller-pak"
        )
        device["runtime_status"] = "supported"
        errors = validate_matrix_document(invalid, schema)
        self.assertIn(
            "controller-pak: pinned runtime status must remain unsupported",
            errors,
        )

    def test_controller_pak_requires_private_boot_roundtrip(self) -> None:
        matrix, schema = self.load_matrix_and_schema()
        capabilities = matrix["capabilities"]
        assert isinstance(capabilities, list)
        capability = next(
            item
            for item in capabilities
            if isinstance(item, dict) and item.get("id") == "controller-pak-save"
        )
        evidence = capability["target_evidence"]
        assert isinstance(evidence, list)
        capability["target_evidence"] = [
            item
            for item in evidence
            if not (
                isinstance(item, dict)
                and item.get("id") == "target-controller-pak-boot-roundtrip"
            )
        ]
        errors = validate_matrix_document(matrix, schema)
        self.assertIn(
            "controller-pak: oracle-only boot evidence must explicitly leave G2 blocked",
            errors,
        )

    def test_controller_pak_oracle_evidence_cannot_clear_g2(self) -> None:
        matrix, schema = self.load_matrix_and_schema()
        capabilities = matrix["capabilities"]
        assert isinstance(capabilities, list)
        capability = next(
            item
            for item in capabilities
            if isinstance(item, dict) and item.get("id") == "controller-pak-save"
        )
        evidence = capability["target_evidence"]
        assert isinstance(evidence, list)
        roundtrip = next(
            item
            for item in evidence
            if isinstance(item, dict)
            and item.get("id") == "target-controller-pak-boot-roundtrip"
        )
        roundtrip["gate_effect"] = "supports-synthetic-contract"
        errors = validate_matrix_document(matrix, schema)
        self.assertIn(
            "controller-pak: oracle-only boot evidence must explicitly leave G2 blocked",
            errors,
        )

    def test_cache_and_decompression_contract_claims_are_enforced(self) -> None:
        for capability_id, property_name in (
            ("cache-operations", "per-write-invalidation-accounting"),
            ("decompression", "input-bound"),
        ):
            with self.subTest(capability_id=capability_id):
                matrix, schema = self.load_matrix_and_schema()
                capabilities = matrix["capabilities"]
                assert isinstance(capabilities, list)
                capability = next(
                    item
                    for item in capabilities
                    if isinstance(item, dict) and item.get("id") == capability_id
                )
                fallback = capability["fallback"]
                assert isinstance(fallback, dict)
                properties = fallback["verified_properties"]
                assert isinstance(properties, list)
                properties.remove(property_name)
                errors = validate_matrix_document(matrix, schema)
                self.assertTrue(
                    any(
                        capability_id in error and "tested synthetic contract" in error
                        for error in errors
                    )
                )

    def test_controller_pak_unproven_claims_are_enforced(self) -> None:
        matrix, schema = self.load_matrix_and_schema()
        devices = matrix["save_devices"]
        assert isinstance(devices, list)
        device = next(
            item
            for item in devices
            if isinstance(item, dict) and item.get("id") == "controller-pak"
        )
        fallback = device["fallback"]
        assert isinstance(fallback, dict)
        exclusions = fallback["unproven_properties"]
        assert isinstance(exclusions, list)
        exclusions.remove("atomic-durable-host-persistence")
        errors = validate_matrix_document(matrix, schema)
        self.assertTrue(
            any(
                error
                == "controller-pak: unproven_properties differs from the tested synthetic contract"
                for error in errors
            )
        )

    def test_schema_field_is_exact_and_privacy_scanned(self) -> None:
        matrix, schema = self.load_matrix_and_schema()
        invalid = copy.deepcopy(matrix)
        invalid["$schema"] = " ".join(["AA", "BB", "CC", "DD", "EE", "FF"] * 2)
        errors = validate_matrix_document(invalid, schema)
        self.assertTrue(any("schema $schema" in item for item in errors))
        self.assertTrue(any("encoded-body" in item for item in errors))

    def test_case_variants_unc_and_encoded_bodies_are_rejected(self) -> None:
        probes = (
            "Inspect 0X89ABCDEF before continuing.",
            "Inspect FUNC_89ABCDEF before continuing.",
            "Inspect " + "\\\\HOST\\share\\capture" + " before continuing.",
            "Inspect /Home/Example/capture before continuing.",
            " ".join(["AA", "BB", "CC", "DD", "EE", "FF"] * 2),
        )
        for probe in probes:
            with self.subTest(probe=probe):
                matrix, schema = self.load_matrix_and_schema()
                capabilities = matrix["capabilities"]
                assert isinstance(capabilities, list)
                capability = capabilities[0]
                assert isinstance(capability, dict)
                capability["next_gate"] = probe
                errors = validate_matrix_document(matrix, schema)
                self.assertTrue(any("private-path or raw-symbol" in item for item in errors))

    def test_digest_sized_chunks_and_generic_posix_paths_are_rejected(self) -> None:
        for probe in (
            ("a" * 64) + " " + ("b" * 64),
            "/tmp/private/capture.json",
            "/root/private/capture.json",
            "/var/folders/private/capture.json",
            "/workspace/private/capture.json",
        ):
            with self.subTest(probe=probe):
                matrix, schema = self.load_matrix_and_schema()
                capability = matrix["capabilities"][0]
                assert isinstance(capability, dict)
                capability["next_gate"] = probe
                self.assertTrue(validate_matrix_document(matrix, schema))

    def test_unbound_evidence_and_count_mutations_are_locked(self) -> None:
        matrix, schema = self.load_matrix_and_schema()
        invalid = copy.deepcopy(matrix)
        capability = invalid["capabilities"][0]
        assert isinstance(capability, dict)
        evidence = capability["target_evidence"][0]
        assert isinstance(evidence, dict)
        evidence["candidate_count"] = 10**30
        evidence["summary"] = "Arbitrary reclassification that preserves schema shape."
        errors = validate_matrix_document(invalid, schema)
        self.assertIn(
            "current-pin runtime matrix differs from the maintainer-reviewed lock",
            errors,
        )

    def test_forbidden_private_field_names_are_case_insensitive(self) -> None:
        matrix, schema = self.load_matrix_and_schema()
        invalid = copy.deepcopy(matrix)
        capabilities = invalid["capabilities"]
        assert isinstance(capabilities, list)
        capability = capabilities[0]
        assert isinstance(capability, dict)
        evidence = capability["target_evidence"]
        assert isinstance(evidence, list)
        record = evidence[0]
        assert isinstance(record, dict)
        record["Raw-Bytes"] = "redacted"
        errors = validate_matrix_document(invalid, schema)
        self.assertTrue(any("forbidden private-body field" in item for item in errors))

    def test_integral_float_tokens_are_rejected(self) -> None:
        matrix, schema = self.load_matrix_and_schema()
        invalid = copy.deepcopy(matrix)
        capabilities = invalid["capabilities"]
        assert isinstance(capabilities, list)
        capability = capabilities[0]
        assert isinstance(capability, dict)
        evidence = capability["target_evidence"]
        assert isinstance(evidence, list)
        record = evidence[0]
        assert isinstance(record, dict)
        record["candidate_count"] = 106.0
        errors = validate_matrix_document(invalid, schema)
        self.assertTrue(any("canonical integer tokens" in item for item in errors))

    def test_duplicate_nested_evidence_ids_are_rejected(self) -> None:
        matrix, schema = self.load_matrix_and_schema()
        invalid = copy.deepcopy(matrix)
        capabilities = invalid["capabilities"]
        assert isinstance(capabilities, list)
        first = capabilities[0]
        second = capabilities[1]
        assert isinstance(first, dict)
        assert isinstance(second, dict)
        first_target = first["target_evidence"]
        second_target = second["target_evidence"]
        assert isinstance(first_target, list)
        assert isinstance(second_target, list)
        assert isinstance(first_target[0], dict)
        assert isinstance(second_target[0], dict)
        second_target[0]["id"] = first_target[0]["id"]
        errors = validate_matrix_document(invalid, schema)
        self.assertTrue(any("evidence IDs must be globally unique" in item for item in errors))


class AddressAndRegisterFallbackTests(unittest.TestCase):
    def test_unknown_register_fails_closed(self) -> None:
        broker = RegisterBroker(("video-status", "audio-status"))
        broker.write("video-status", 0x1_0000_0001)
        self.assertEqual(broker.read("video-status"), 1)
        with self.assertRaises(UnknownRegister):
            broker.read("unknown-status")
        with self.assertRaises(UnknownRegister):
            broker.write("unknown-status", 7)

    def test_kseg_alias_translation(self) -> None:
        translator = AddressTranslator()
        self.assertEqual(translator.to_physical(0x80000120), 0x120)
        self.assertEqual(translator.to_physical(0xA0000120), 0x120)
        with self.assertRaises(UnmappedAddress):
            translator.to_physical(0x00400020)

    def test_explicit_tlb_mapping(self) -> None:
        translator = AddressTranslator((AddressMapping(0x00400000, 0x1000, 0x100),))
        self.assertEqual(translator.to_physical(0x00400020), 0x1020)
        with self.assertRaises(UnmappedAddress):
            translator.to_physical(0x00400100)
        with self.assertRaises(ValueError):
            AddressTranslator(
                (
                    AddressMapping(0x1000, 0x2000, 0x100),
                    AddressMapping(0x1080, 0x3000, 0x100),
                )
            )
        with self.assertRaisesRegex(ValueError, "direct-mapped KSEG"):
            AddressTranslator((AddressMapping(0x7FFFFFF0, 0, 0x20),))
        with self.assertRaisesRegex(ValueError, "direct-mapped KSEG"):
            AddressTranslator((AddressMapping(0x80000000, 0, 0x100),))
        with self.assertRaisesRegex(ValueError, "direct-mapped KSEG"):
            AddressTranslator((AddressMapping(0xBFFFFFF0, 0, 0x20),))

        below_kseg = AddressTranslator((AddressMapping(0x7FFFFF00, 0x2000, 0x100),))
        self.assertEqual(below_kseg.to_physical(0x7FFFFF20), 0x2020)
        above_direct = AddressTranslator((AddressMapping(0xC0000000, 0x3000, 0x100),))
        self.assertEqual(above_direct.to_physical(0xC0000020), 0x3020)


class RuntimeBoundaryFallbackTests(unittest.TestCase):
    def test_cache_coherency_gate(self) -> None:
        gate = CacheCoherencyGate()
        self.assertEqual(gate.record_code_write("generated-region-a"), 1)
        self.assertEqual(gate.record_code_write("generated-region-a"), 2)
        with self.assertRaises(GapModelError):
            gate.require_coherent()
        self.assertEqual(gate.record_host_invalidation("generated-region-a"), 1)
        with self.assertRaises(GapModelError):
            gate.require_coherent()
        self.assertEqual(gate.record_host_invalidation("generated-region-a"), 2)
        gate.require_coherent()
        with self.assertRaises(GapModelError):
            gate.record_host_invalidation("generated-region-a")
        self.assertEqual(gate.record_code_write("generated-region-a"), 3)
        with self.assertRaises(GapModelError):
            gate.require_coherent()

    def test_bounded_dma_copy(self) -> None:
        source = bytes(range(16))
        target = bytearray(12)
        completions: list[str] = []
        BoundedDmaBroker.copy(
            source,
            target,
            source_offset=3,
            target_offset=2,
            length=5,
            completions=completions,
            completion_id="transfer-complete",
        )
        self.assertEqual(target[2:7], source[3:8])
        self.assertEqual(completions, ["transfer-complete"])

        unchanged = bytes(target)
        with self.assertRaises(DmaBoundsError):
            BoundedDmaBroker.copy(
                source,
                target,
                source_offset=14,
                target_offset=0,
                length=4,
                completions=completions,
                completion_id="must-not-complete",
            )
        self.assertEqual(bytes(target), unchanged)
        self.assertEqual(completions, ["transfer-complete"])

    def test_decompressor_callback_boundary(self) -> None:
        gateway = DecompressionGateway(max_input_bytes=8, max_output_bytes=8)
        with self.assertRaises(GapModelError):
            gateway.decompress(b"fixture")

        calls: list[bytes] = []

        def reverse(payload: bytes) -> bytes:
            calls.append(payload)
            return payload[::-1]

        gateway.register(reverse)
        self.assertEqual(gateway.decompress(b"fixture"), b"erutxif")
        with self.assertRaises(GapModelError):
            gateway.decompress(b"123456789")
        self.assertEqual(calls, [b"fixture"])

        gateway.register(lambda payload: payload * 2)
        with self.assertRaises(GapModelError):
            gateway.decompress(b"12345")
        gateway.register(lambda payload: bytearray(payload))  # type: ignore[arg-type,return-value]
        with self.assertRaises(GapModelError):
            gateway.decompress(b"fixture")


class SaveAndTrapFallbackTests(unittest.TestCase):
    def test_synthetic_controller_pak_lifecycle(self) -> None:
        device = SyntheticControllerPak(capacity_bytes=32, max_notes=2)
        device.allocate("slot-a", 12)
        device.allocate("slot-b", 8)
        self.assertEqual(device.free_bytes, 12)
        device.write("slot-a", 2, b"test")
        self.assertEqual(device.read("slot-a", 2, 4), b"test")
        self.assertEqual(
            device.enumerate_notes(), (("slot-a", 12), ("slot-b", 8))
        )
        snapshot = device.export_logical_snapshot()
        restored = SyntheticControllerPak.from_logical_snapshot(
            snapshot, capacity_bytes=32, max_notes=2
        )
        self.assertEqual(restored.enumerate_notes(), device.enumerate_notes())
        self.assertEqual(restored.read("slot-a", 2, 4), b"test")
        device.write("slot-a", 2, b"next")
        self.assertEqual(restored.read("slot-a", 2, 4), b"test")
        with self.assertRaises(SaveDeviceError):
            device.write("slot-a", 10, b"overflow")
        with self.assertRaises(SaveDeviceError):
            device.allocate("slot-a", 4)
        device.delete("slot-a")
        self.assertEqual(device.enumerate_notes(), (("slot-b", 8),))
        with self.assertRaises(SaveDeviceError):
            device.read("slot-a", 0, 1)
        with self.assertRaises(SaveDeviceError):
            SyntheticControllerPak.from_logical_snapshot(
                (("slot-a", b"one"), ("slot-a", b"two")),
                capacity_bytes=32,
                max_notes=2,
            )

    def test_trap_inventory_completeness(self) -> None:
        records = (
            TrapRecord("break-class", "cpu-break", "abort"),
            TrapRecord(
                "syscall-class", "cpu-syscall", "defer-to-reviewed-handler"
            ),
            TrapRecord("switch-class", "switch-bounds", "abort"),
            TrapRecord("self-check-class", "boot-self-check", "emulate"),
        )
        inventory = TrapInventory(records)
        inventory.require_kinds(
            ("cpu-break", "cpu-syscall", "switch-bounds", "boot-self-check")
        )
        self.assertEqual(inventory.dispatch("self-check-class"), "emulate")
        with self.assertRaisesRegex(TrapInventoryError, "reviewed handler"):
            inventory.dispatch("syscall-class")
        deferred: list[str] = []
        self.assertEqual(
            inventory.dispatch("syscall-class", reviewed_handler=deferred.append),
            "defer-to-reviewed-handler",
        )
        self.assertEqual(deferred, ["syscall-class"])
        with self.assertRaises(TrapAbort):
            inventory.dispatch("break-class")
        with self.assertRaises(TrapInventoryError):
            inventory.dispatch("unknown-class")
        with self.assertRaises(TrapInventoryError):
            TrapInventory((records[0], records[0]))
        with self.assertRaises(TrapInventoryError):
            TrapInventory(records[:-1]).require_kinds(("boot-self-check",))
        with self.assertRaisesRegex(ValueError, "kind"):
            TrapRecord("legacy-self-check", "self-check", "emulate")


if __name__ == "__main__":
    unittest.main()
