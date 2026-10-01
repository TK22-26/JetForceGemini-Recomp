from __future__ import annotations

import copy
import hashlib
import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import scripts.prepare_g2_cpu_case as PREPARE
import scripts.validate_phase4_private_evidence as PHASE4_PRIVATE


ROOT = Path(__file__).resolve().parents[1]


def digest(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


class PrepareG2CpuCaseTests(unittest.TestCase):
    def valid_core(self) -> dict[str, object]:
        document = PHASE4_PRIVATE._json_loads(
            (ROOT / "examples" / "phase4-generated-manifest.example.json").read_bytes()
        )
        assert isinstance(document, dict)
        return {
            field: copy.deepcopy(document[field])
            for field in PHASE4_PRIVATE.G3_PRODUCT_CORE_FIELDS
        }

    def fixture(self) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        compilers = [
            {
                "compiler_id": f"{family}-test",
                "family": family,
                "compiler_executable_sha256": digest(family),
            }
            for family in ("clang", "gcc", "msvc")
        ]
        core = {field: {} for field in PHASE4_PRIVATE.G3_PRODUCT_CORE_FIELDS}
        core.update({
            "symbols": {
                "expected_count": 3729,
                "generated_count": 2905,
                "excluded_count": 824,
                "replaceable_function_count": 2905,
                "exclusion_category_counts": {
                    "covered-alias": 824,
                    "validated-non-code": 0,
                    "runtime-abi": 0,
                },
                "covered_alias_ledger_sha256": digest("covered-alias-ledger"),
                "manual_size_recovery_count": 6,
                "manual_size_recovery_ledger_sha256": digest("size-recovery-ledger"),
                "manual_size_recovery_approval_set_sha256": digest(
                    "size-recovery-approvals"
                ),
                "inventory_sha256": digest("generated-inventory"),
                "approval_set_sha256": digest("covered-alias-approvals"),
            },
            "stubs": {"generated_game_function_stub_count": 0},
            "overlays": {
                "executable_section_count": 2,
                "expected_slot_count": 2,
                "listed_slot_count": 2,
                "populated_slot_count": 1,
                "empty_slot_count": 1,
            },
            "compilers": compilers,
            "analysis": {},
            "libraries": {
                "baseline": {"unmodified_body_member_count": 2905},
                "patch": {"member_count": 1},
                "minimal_runtime": {
                    "relocation_table_entry_count": 2,
                    "section_address_count": 2,
                    "handwritten_bridge_unit_count": 2,
                },
            },
            "reproducibility": {},
        })
        public = PHASE4_PRIVATE.g3_product_projection(
            core, digest("phase4-private-body")
        )
        fields = (
            "harness_id",
            "harness_sha256",
            "public_record_sha256",
            "public_result_set_sha256",
            "subject_sha256",
            "source_input_sha256",
            "declaration_sha256",
            "pins_sha256",
            "environment_sha256",
            "input_set_sha256",
            "output_set_sha256",
        )
        private = {
            "executions": [
                {
                    "id": f"execution-{index}",
                    "evidence_kind": kind,
                    "case_id": f"case-{index}",
                    **{field: digest(f"{kind}-{field}") for field in fields},
                    "observed_exit_code": 0,
                    "passed": True,
                }
                for index, kind in enumerate((
                    "generation",
                    "compiler-clang",
                    "compiler-gcc",
                    "compiler-msvc",
                    "forced-object-link-audit",
                    "clang-static-analysis",
                    "address-sanitizer",
                    "undefined-behavior-sanitizer",
                    "reproducibility-run-a",
                    "reproducibility-run-b",
                    "configuration-mutation",
                ))
            ]
        }
        inventory = {
            "schema_version": 2,
            "kind": "jfg-phase4-cpu-section-inventory",
            "sections": [
                {
                    "section_id": "main-core",
                    "kind": "main",
                    "expected": 2200,
                    "generated": 1720,
                    "excluded": 480,
                    "lookups": 1720,
                    "lifecycle": 0,
                    "relocations": 1,
                },
                {
                    "section_id": "overlay-core",
                    "kind": "overlay",
                    "expected": 1529,
                    "generated": 1185,
                    "excluded": 344,
                    "lookups": 1185,
                    "lifecycle": 1,
                    "relocations": 1,
                },
            ],
            "overlay_slots": [
                {
                    "slot_id": "slot-001",
                    "disposition": "populated",
                    "section_id": "overlay-core",
                },
                {
                    "slot_id": "slot-002",
                    "disposition": "empty-fail-closed",
                    "section_id": None,
                },
            ],
        }
        return public, private, inventory

    def test_case_is_derived_from_g3_denominators_and_binding(self) -> None:
        public, private, inventory = self.fixture()
        case = PREPARE.build_case(public, private, inventory)
        self.assertEqual(case[:8], b"JFGCPU02")
        self.assertEqual(struct.unpack_from("<HH", case, 8), (4, 3))

        forged = dict(public)
        forged["symbols"] = dict(public["symbols"])  # type: ignore[arg-type]
        forged["symbols"]["generated_count"] = 2906  # type: ignore[index]
        with self.assertRaises(PREPARE.PreparationError):
            PREPARE.build_case(forged, private, inventory)

        for field in (
            "covered_alias_ledger_sha256",
            "approval_set_sha256",
            "manual_size_recovery_ledger_sha256",
            "manual_size_recovery_approval_set_sha256",
        ):
            with self.subTest(missing_symbol_digest=field):
                forged = copy.deepcopy(public)
                forged["symbols"].pop(field)  # type: ignore[index]
                with self.assertRaises(PREPARE.PreparationError):
                    PREPARE.build_case(forged, private, inventory)

        forged = copy.deepcopy(public)
        forged["symbols"]["manual_size_recovery_count"] = 5  # type: ignore[index]
        with self.assertRaises(PREPARE.PreparationError):
            PREPARE.build_case(forged, private, inventory)

        forged_inventory = copy.deepcopy(inventory)
        forged_inventory["sections"][0]["excluded"] -= 1  # type: ignore[index]
        with self.assertRaises(PREPARE.PreparationError):
            PREPARE.build_case(public, private, forged_inventory)

    def test_binding_excludes_request_specific_result_digests_only(self) -> None:
        public, private, _ = self.fixture()
        expected = PREPARE.cpu_g3_product_binding_sha256(private, public)
        self.assertIsInstance(expected, str)

        request_specific = copy.deepcopy(private)
        for index, execution in enumerate(request_specific["executions"]):
            execution["artifact_set_sha256"] = digest(f"artifact-{index}")
            execution["result_sha256"] = digest(f"result-{index}")
        self.assertEqual(
            PREPARE.cpu_g3_product_binding_sha256(request_specific, public), expected
        )

        changed = copy.deepcopy(private)
        changed["executions"][0]["output_set_sha256"] = digest("changed-output")
        self.assertNotEqual(
            PREPARE.cpu_g3_product_binding_sha256(changed, public), expected
        )
        failed = copy.deepcopy(private)
        failed["executions"][0]["passed"] = False
        self.assertIsNone(PREPARE.cpu_g3_product_binding_sha256(failed, public))

    def test_binding_covers_exact_products_private_body_and_all_executions(self) -> None:
        public, private, _ = self.fixture()
        expected = PREPARE.cpu_g3_product_binding_sha256(private, public)
        self.assertIsInstance(expected, str)

        final_manifest = {
            "kind": "jfg-phase4-generated-manifest",
            **{
                field: copy.deepcopy(public[field])
                for field in PHASE4_PRIVATE.G3_PRODUCT_CORE_FIELDS
            },
            "attestation": {
                "private_evidence_sha256": public["private_evidence_sha256"]
            },
        }
        self.assertEqual(
            PREPARE.cpu_g3_product_binding_sha256(private, final_manifest), expected
        )

        for field in PHASE4_PRIVATE.G3_PRODUCT_CORE_FIELDS:
            changed = copy.deepcopy(public)
            changed[field] = {"mutation": field}
            with self.subTest(product_field=field):
                self.assertNotEqual(
                    PREPARE.cpu_g3_product_binding_sha256(private, changed), expected
                )

        patch_changed = copy.deepcopy(public)
        patch_changed["libraries"]["patch"] = {"member_count": 2}
        self.assertNotEqual(
            PREPARE.cpu_g3_product_binding_sha256(private, patch_changed), expected
        )

        digest_changed = copy.deepcopy(public)
        digest_changed["private_evidence_sha256"] = digest("different-private-body")
        self.assertNotEqual(
            PREPARE.cpu_g3_product_binding_sha256(private, digest_changed), expected
        )

        for index in range(len(private["executions"])):
            changed = copy.deepcopy(private)
            changed["executions"][index]["output_set_sha256"] = digest(
                f"changed-execution-{index}"
            )
            with self.subTest(execution=index):
                self.assertNotEqual(
                    PREPARE.cpu_g3_product_binding_sha256(changed, public), expected
                )

    def test_pre_g2_inputs_must_be_ignored_regular_files_and_fully_validate(self) -> None:
        core = self.valid_core()
        projection = PHASE4_PRIVATE.g3_product_projection(core, digest("private"))
        private = {"kind": "test-private"}
        (ROOT / "tools").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="cpu-audit-", dir=ROOT / "tools") as name:
            audit_root = Path(name)
            projection_path = audit_root / "projection.json"
            private_path = audit_root / "private.json"
            projection_path.write_bytes(PREPARE._canonical_bytes(projection))
            private_path.write_bytes(PREPARE._canonical_bytes(private))
            with mock.patch.object(
                PREPARE, "validate_phase4_private_file", return_value=[]
            ):
                self.assertEqual(
                    PREPARE.load_validated_g3_audit(projection_path, private_path),
                    (projection, private),
                )

            invalid_projection = copy.deepcopy(projection)
            invalid_projection["symbols"] = {}
            projection_path.write_bytes(PREPARE._canonical_bytes(invalid_projection))
            with mock.patch.object(
                PREPARE, "validate_phase4_private_file", return_value=[]
            ):
                with self.assertRaises(PREPARE.PreparationError):
                    PREPARE.load_validated_g3_audit(projection_path, private_path)
            projection_path.write_bytes(PREPARE._canonical_bytes(projection))

            with mock.patch.object(
                PREPARE,
                "validate_phase4_private_file",
                return_value=["fake passed flag rejected"],
            ):
                with self.assertRaises(PREPARE.PreparationError):
                    PREPARE.load_validated_g3_audit(projection_path, private_path)

            # The handle initially matches the checked path, then a path swap is
            # observed by the post-open identity check.
            with mock.patch.object(
                PREPARE.os.path, "samestat", side_effect=(True, False)
            ):
                with self.assertRaises(PREPARE.PreparationError):
                    PREPARE.load_validated_g3_audit(projection_path, private_path)

            link = audit_root / "private-link.json"
            try:
                os.symlink(private_path, link)
            except OSError:
                pass
            else:
                with self.assertRaises(PREPARE.PreparationError):
                    PREPARE.load_validated_g3_audit(projection_path, link)

        with tempfile.TemporaryDirectory(prefix="cpu-audit-unignored-", dir=ROOT) as name:
            unignored_root = Path(name)
            projection_path = unignored_root / "projection.json"
            private_path = unignored_root / "private.json"
            projection_path.write_bytes(PREPARE._canonical_bytes(projection))
            private_path.write_bytes(PREPARE._canonical_bytes(private))
            with mock.patch.object(
                PREPARE, "validate_phase4_private_file", return_value=[]
            ):
                with self.assertRaises(PREPARE.PreparationError):
                    PREPARE.load_validated_g3_audit(projection_path, private_path)


if __name__ == "__main__":
    unittest.main()
