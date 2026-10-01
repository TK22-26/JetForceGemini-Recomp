from __future__ import annotations

import copy
import hashlib
import inspect
import json
import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path
from unittest import mock

import scripts.build_phase4_completion_manifest as completion
import scripts.build_phase4_private_evidence as private_body
import scripts.prepare_phase4_products as preparation
from scripts.phase4_evidence_harness import PRODUCT_KINDS


class Phase4ProductPreparationTests(unittest.TestCase):
    @staticmethod
    def canonical(value: object) -> bytes:
        return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")

    @staticmethod
    def archive(name: str = "member.o", body: bytes = b"object") -> bytes:
        encoded_name = (name + "/").encode("ascii").ljust(16, b" ")
        header = (
            encoded_name
            + b"0".ljust(12, b" ")
            + b"0".ljust(6, b" ")
            + b"0".ljust(6, b" ")
            + b"100644".ljust(8, b" ")
            + str(len(body)).encode("ascii").ljust(10, b" ")
            + b"`\n"
        )
        return b"!<arch>\n" + header + body + (b"\n" if len(body) & 1 else b"")

    def make_recipe(self, root: Path) -> dict[str, object]:
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("analysis.cpp", b"int main() { return 0; }\n")
        payloads: dict[str, bytes] = {}
        sources: list[dict[str, object]] = []

        def add(identifier: str, payload: bytes) -> str:
            if identifier not in payloads:
                payloads[identifier] = payload
                path = root / f"{identifier}.bin"
                path.write_bytes(payload)
                sources.append({"id": identifier, "path": path.name})
            return identifier

        zip_source = add("source-zip", zip_buffer.getvalue())
        archive_source = add("static-archive", self.archive())
        sources.extend(
            [
                {
                    "id": "file-inventory",
                    "source": zip_source,
                    "preparation": "zip-file-inventory",
                },
                {
                    "id": "member-inventory",
                    "source": archive_source,
                    "preparation": "archive-member-inventory",
                },
            ]
        )

        public_results = {
            "compiler-result",
            "baseline-result",
            "patch-result",
            "minimal-runtime-result",
            "analyzer-result",
            "sanitizer-result",
            "config-diff-result",
        }
        mappings: dict[str, str] = {}
        for product_kind in sorted(set().union(*PRODUCT_KINDS.values())):
            identifier = "product-" + product_kind
            if product_kind in {
                "generated-source-archive",
                "generation-input-archive",
                "analysis-source-archive",
            }:
                mappings[product_kind] = zip_source
            elif product_kind in {
                "source-file-inventory",
                "generation-input-inventory",
                "analysis-source-inventory",
            }:
                mappings[product_kind] = "file-inventory"
            elif product_kind in {"baseline-archive", "patch-archive"}:
                mappings[product_kind] = archive_source
            elif product_kind in {"baseline-member-inventory", "patch-member-inventory"}:
                mappings[product_kind] = "member-inventory"
            elif product_kind in {
                "smoke-executable",
                "forced-link-executable",
                "instrumented-executable",
            }:
                mappings[product_kind] = add(identifier, b"MZ" + product_kind.encode("ascii"))
            elif product_kind in public_results:
                mappings[product_kind] = add(
                    identifier,
                    self.canonical(
                        {
                            "schema_version": 1,
                            "kind": "jfg-phase4-public-result",
                            "product_kind": product_kind,
                            "observed": {"source": product_kind},
                        }
                    ),
                )
            elif product_kind == "base-config":
                mappings[product_kind] = add(identifier, b"private base configuration\n")
            else:
                mappings[product_kind] = add(identifier, self.canonical({"product": product_kind}))

        return {
            "schema_version": 1,
            "kind": "jfg-phase4-product-preparation",
            "sources": sources,
            "executions": [
                {
                    "evidence_kind": evidence_kind,
                    "products": {
                        product_kind: mappings[product_kind]
                        for product_kind in sorted(PRODUCT_KINDS[evidence_kind])
                    },
                }
                for evidence_kind in sorted(PRODUCT_KINDS)
            ],
        }

    def test_stages_exact_matrix_and_command_free_plans(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            recipe = self.make_recipe(source)
            output = root / "prepared"
            index = preparation.prepare(
                recipe, source, output, require_ignored_output=False
            )
            self.assertEqual(len(index["executions"]), 11)
            self.assertTrue((output / "phase4-prepared-products.json").is_file())
            for execution in index["executions"]:
                plan = json.loads((output / execution["plan_path"]).read_text("utf-8"))
                self.assertEqual(set(plan), {"schema_version", "kind", "evidence_kind", "products"})
                self.assertNotIn("command", json.dumps(plan).casefold())
                self.assertEqual(
                    {row["product_kind"] for row in plan["products"]},
                    PRODUCT_KINDS[execution["evidence_kind"]],
                )

    def test_recipe_with_command_field_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source"
            source.mkdir()
            recipe = self.make_recipe(source)
            recipe["command"] = "all checks passed"
            with self.assertRaises(preparation.PreparationError):
                preparation.prepare(
                    recipe,
                    source,
                    Path(temporary) / "prepared",
                    require_ignored_output=False,
                )

    def test_missing_product_and_escaped_source_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source"
            source.mkdir()
            recipe = self.make_recipe(source)
            generation = next(
                row for row in recipe["executions"] if row["evidence_kind"] == "generation"
            )
            generation["products"].pop("report-set")
            with self.assertRaises(preparation.PreparationError):
                preparation.prepare(
                    recipe,
                    source,
                    Path(temporary) / "missing",
                    require_ignored_output=False,
                )
            escaped = self.make_recipe(source)
            escaped["sources"][0]["path"] = "../outside.bin"
            with self.assertRaises(preparation.PreparationError):
                preparation.prepare(
                    escaped,
                    source,
                    Path(temporary) / "escaped",
                    require_ignored_output=False,
                )

    def test_existing_output_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source"
            source.mkdir()
            recipe = self.make_recipe(source)
            output = Path(temporary) / "prepared"
            output.mkdir()
            sentinel = output / "keep.txt"
            sentinel.write_text("keep", encoding="utf-8")
            with self.assertRaises(preparation.PreparationError):
                preparation.prepare(recipe, source, output, require_ignored_output=False)
            self.assertEqual(sentinel.read_text("utf-8"), "keep")

    def test_no_caller_builder_rejects_unclosed_products_and_detects_tampering(self) -> None:
        self.assertEqual(
            list(inspect.signature(completion.derive_public_core).parameters),
            ["index_document", "bundle_root", "patch_provenance"],
        )
        with self.assertRaises(TypeError):
            completion.derive_public_core(  # type: ignore[call-arg]
                {"symbols": {"expected_count": 1}},
                {},
                Path("."),
                {},
            )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            output = root / "prepared"
            index = preparation.prepare(
                self.make_recipe(source), source, output, require_ignored_output=False
            )
            provenance = {
                "status": "applied",
                "patch_count": 0,
                "patchset_sha256": "0" * 64,
            }
            with self.assertRaises(completion.CompletionBuildError):
                completion.derive_public_core(index, output, provenance)
            target = output / index["executions"][0]["products"][0]["path"]
            target.write_bytes(target.read_bytes() + b"tamper")
            with self.assertRaises(completion.CompletionBuildError):
                completion.derive_public_core(index, output, provenance)

    def test_forced_semantic_inventory_helpers_reject_count_and_owner_mutations(self) -> None:
        roles = {
            "baseline-body": 2,
            "normal-wrapper": 2,
            "patch": 0,
            "alternate-entry-thunk": 1,
            "section-address-support": 3,
            "lookup-support": 2,
            "lifecycle-support": 1,
            "relocation-support": 5,
            "runtime-function": 17,
            "runtime-data": 1,
        }
        role_document = {
            "schema_version": 1,
            "kind": "jfg-phase4-generated-object-role-inventory",
            "role_counts": roles,
            "one_external_function_per_generated_object": True,
            "object_symbol_ownership_verified": True,
        }
        self.assertEqual(
            completion._object_role_counts(self.canonical(role_document)), roles
        )
        invalid_roles = copy.deepcopy(role_document)
        invalid_roles["role_counts"]["baseline-body"] = "2"
        with self.assertRaises(completion.CompletionBuildError):
            completion._object_role_counts(self.canonical(invalid_roles))

        owner_document = {
            "schema_version": 1,
            "kind": "jfg-phase4-host-function-inventory",
            "record_count": 2,
            "records": [
                {
                    "symbol_sha256": hashlib.sha256(label.encode()).hexdigest(),
                    "owner_role": "minimal-runtime",
                }
                for label in ("function-a", "function-b")
            ],
        }
        self.assertEqual(
            completion._host_inventory_count(
                self.canonical(owner_document), "function"
            ),
            2,
        )
        invalid_owner = copy.deepcopy(owner_document)
        invalid_owner["records"][1]["owner_role"] = "generated"
        with self.assertRaises(completion.CompletionBuildError):
            completion._host_inventory_count(
                self.canonical(invalid_owner), "function"
            )

    def test_source_roles_derive_patch_count_and_alias_ledger(self) -> None:
        recomp_declaration = b"RECOMP_" + b"FUNC void "
        semantic_payloads = {
            member: self.canonical(
                {
                    "schema_version": 1,
                    "kind": expected_kind,
                }
            )
            for member, expected_kind in completion.SEMANTIC_PRODUCTS_V6.items()
        }
        contents = {
            "baseline/fn_000_0000_recomp.c": recomp_declaration
            + b"fn_000_0000_recomp(",
            "baseline/fn_000_0000.c": recomp_declaration + b"fn_000_0000(",
            **{
                f"semantic/{member}.json": payload
                for member, payload in semantic_payloads.items()
            },
        }
        manifest = {
            "version": 6,
            "n64recomp_include": "include",
            "baseline_body_sources": ["baseline/fn_000_0000_recomp.c"],
            "normal_wrapper_sources": ["baseline/fn_000_0000.c"],
            "patch_sources": ["patch/fn_000_0000.c"],
            "game_patch_function_count": 1,
            "support_sources": [],
            "alternate_entry_thunk_sources": [],
            "table_support_sources": [],
            "link_smoke_sources": [],
            "symbol_inventory": "symbol_inventory.json",
            "symbol_inventory_sha256": hashlib.sha256(b"inventory").hexdigest(),
            "normalizer_revision_sha256": hashlib.sha256(
                completion.NORMALIZER_PATH.read_bytes()
            ).hexdigest(),
            "cpu_section_inventory": "cpu_section_inventory.json",
            "cpu_section_inventory_sha256": hashlib.sha256(b"cpu").hexdigest(),
            **{
                member: f"semantic/{member}.json"
                for member in completion.SEMANTIC_PRODUCTS_V6
            },
            **{
                f"{member}_sha256": hashlib.sha256(payload).hexdigest()
                for member, payload in semantic_payloads.items()
            },
        }
        self.assertEqual(set(manifest), completion.MANIFEST_KEYS_V6)
        contents["sources.json"] = self.canonical(manifest)
        patch_count, ledger = completion._source_role_facts(contents)
        self.assertEqual(patch_count, 1)
        self.assertRegex(ledger, r"^[0-9a-f]{64}$")

        downgrade = copy.deepcopy(manifest)
        downgrade["version"] = 5
        contents["sources.json"] = self.canonical(downgrade)
        with self.assertRaisesRegex(
            completion.CompletionBuildError, "generated source manifest"
        ):
            completion._source_role_facts(contents)

        unknown = copy.deepcopy(manifest)
        unknown["unexpected_semantic_product"] = "semantic/unknown.json"
        contents["sources.json"] = self.canonical(unknown)
        with self.assertRaisesRegex(
            completion.CompletionBuildError, "generated source manifest"
        ):
            completion._source_role_facts(contents)

        stale = copy.deepcopy(manifest)
        stale["normalizer_revision_sha256"] = "0" * 64
        contents["sources.json"] = self.canonical(stale)
        with self.assertRaisesRegex(
            completion.CompletionBuildError, "normalizer revision"
        ):
            completion._source_role_facts(contents)

        contents["sources.json"] = self.canonical(manifest)
        contents["baseline/fn_000_0000.c"] = recomp_declaration + b"fn_000_0001("
        with self.assertRaises(completion.CompletionBuildError):
            completion._source_role_facts(contents)

    def builder_fixture(
        self,
    ) -> tuple[
        dict[str, dict[str, tuple[str, str]]],
        dict[str, dict[str, bytes]],
        dict[tuple[str, str], dict[str, object]],
        dict[str, object],
    ]:
        payloads = {
            lane: {
                kind: f"{lane}:{kind}".encode()
                for kind in PRODUCT_KINDS[lane]
            }
            for lane in PRODUCT_KINDS
        }
        generation = {
            "schema_version": 1,
            "kind": "jfg-phase4-generation-semantic-result",
            "symbols": {
                "expected_count": completion.EXPECTED_EXECUTABLE_SYMBOL_COUNT,
                "generated_count": completion.EXPECTED_GENERATED_BODY_COUNT,
                "replaceable_function_count": completion.EXPECTED_GENERATED_BODY_COUNT,
                "alternate_entry_thunk_count": 1,
                "excluded_count": completion.EXPECTED_COVERED_ALIAS_COUNT,
                "unclassified_count": 0,
                "duplicate_native_symbol_count": 0,
                "exclusion_category_counts": {
                    "covered-alias": completion.EXPECTED_COVERED_ALIAS_COUNT,
                    "validated-non-code": 0,
                    "runtime-abi": 0,
                },
                "covered_alias_ledger_sha256": hashlib.sha256(
                    b"covered-alias-ledger"
                ).hexdigest(),
                "manual_size_recovery_count": 6,
                "manual_size_recovery_ledger_sha256": hashlib.sha256(
                    b"size-recovery-ledger"
                ).hexdigest(),
                "manual_size_recovery_approval_set_sha256": hashlib.sha256(
                    b"size-recovery-approvals"
                ).hexdigest(),
                "inventory_sha256": hashlib.sha256(b"inventory").hexdigest(),
                "approval_set_sha256": hashlib.sha256(b"approval").hexdigest(),
            },
            "calls": {
                "direct": {
                    "candidate_count": completion.EXPECTED_STATIC_DIRECT_CALL_CANDIDATE_COUNT,
                    "transfer_role_counts": {
                        "linked-call": completion.EXPECTED_STATIC_LINKED_CALL_COUNT,
                        "direct-tail": completion.EXPECTED_STATIC_DIRECT_TAIL_COUNT,
                    },
                    "instruction_class_counts": {
                        "jal": completion.EXPECTED_STATIC_JAL_CALL_CANDIDATE_COUNT,
                        "bgezal": completion.EXPECTED_STATIC_BGEZAL_CALL_CANDIDATE_COUNT,
                        "j": completion.EXPECTED_STATIC_J_CALL_CANDIDATE_COUNT,
                        "conditional-branch": completion.EXPECTED_STATIC_CONDITIONAL_BRANCH_CALL_CANDIDATE_COUNT,
                    },
                    "expected_count": completion.EXPECTED_STATIC_DIRECT_CALL_CANDIDATE_COUNT,
                    "resolved_count": completion.EXPECTED_STATIC_DIRECT_CALL_CANDIDATE_COUNT,
                    "approved_exception_count": 0,
                },
                "indirect_ranges": {
                    "expected_count": completion.EXPECTED_STATIC_INDIRECT_TRANSFER_COUNT,
                    "resolved_count": completion.EXPECTED_STATIC_INDIRECT_TRANSFER_COUNT,
                    "native_return_count": completion.EXPECTED_NATIVE_RETURN_TRANSFER_COUNT,
                    "decision_range_count": completion.EXPECTED_DECISION_RANGE_TRANSFER_COUNT,
                },
            },
            "relocations": {
                "instructions": {},
                "data_r32": {
                    "expected_count": completion.EXPECTED_R32_RELOCATION_COUNT,
                    "resolved_count": completion.EXPECTED_R32_RELOCATION_COUNT,
                    "approved_fail_closed_count": 0,
                },
            },
            "overlays": {
                "executable_section_count": completion.EXPECTED_EXECUTABLE_SECTION_COUNT,
                "expected_slot_count": completion.EXPECTED_OVERLAY_SLOT_COUNT,
                "populated_slot_count": completion.EXPECTED_POPULATED_OVERLAY_SLOT_COUNT,
                "empty_slot_count": completion.EXPECTED_EMPTY_OVERLAY_SLOT_COUNT,
                "listed_slot_count": completion.EXPECTED_OVERLAY_SLOT_COUNT,
                "lookup_table_slot_count": completion.EXPECTED_OVERLAY_SLOT_COUNT,
                "lifecycle_table_slot_count": completion.EXPECTED_OVERLAY_SLOT_COUNT,
                "generated_populated_module_count": completion.EXPECTED_POPULATED_OVERLAY_SLOT_COUNT,
                "relocation_table_entry_count": completion.EXPECTED_R32_RELOCATION_COUNT,
                "resolved_relocation_entry_count": completion.EXPECTED_R32_RELOCATION_COUNT,
                "unresolved_relocation_entry_count": 0,
                "missing_slot_count": 0,
                "duplicate_slot_count": 0,
                "manifest_sha256": hashlib.sha256(b"manifest").hexdigest(),
                "slot_inventory_sha256": hashlib.sha256(b"slots").hexdigest(),
                "lookup_table_sha256": hashlib.sha256(b"lookup").hexdigest(),
                "lifecycle_table_sha256": hashlib.sha256(b"lifecycle").hexdigest(),
                "relocation_table_sha256": hashlib.sha256(b"relocations").hexdigest(),
            },
            "stubs": {},
            "semantic_bindings": {},
        }
        payloads["generation"]["generation-result"] = self.canonical(generation)
        roles = {
            "baseline-body": completion.EXPECTED_GENERATED_BODY_COUNT,
            "normal-wrapper": completion.EXPECTED_GENERATED_BODY_COUNT,
            "patch": 0,
            "alternate-entry-thunk": 1,
            "section-address-support": 3,
            "lookup-support": 2,
            "lifecycle-support": 1,
            "relocation-support": 5,
            "runtime-function": 2,
            "runtime-data": 1,
        }
        payloads["forced-object-link-audit"]["object-role-inventory"] = self.canonical(
            {
                "schema_version": 1,
                "kind": "jfg-phase4-generated-object-role-inventory",
                "role_counts": roles,
                "one_external_function_per_generated_object": True,
                "object_symbol_ownership_verified": True,
            }
        )
        host_records = lambda count: [
            {
                "symbol_sha256": hashlib.sha256(f"host-{index}".encode()).hexdigest(),
                "owner_role": "minimal-runtime",
            }
            for index in range(count)
        ]
        for role, count in (("function", 2), ("data", 1)):
            payloads["forced-object-link-audit"][f"host-{role}-inventory"] = self.canonical(
                {
                    "schema_version": 1,
                    "kind": f"jfg-phase4-host-{role}-inventory",
                    "record_count": count,
                    "records": host_records(count),
                }
            )
        baseline_inventory = self.canonical(
            {
                "schema_version": 1,
                "kind": "jfg-phase4-archive-member-inventory",
                "members": [
                {
                    "name": f"member-{index}.o",
                    "sha256": hashlib.sha256(f"member-{index}".encode()).hexdigest(),
                    "size": 1,
                }
                for index in range(16)
                ],
            }
        )
        patch_inventory = self.canonical(
            {
                "schema_version": 1,
                "kind": "jfg-phase4-archive-member-inventory",
                "members": [
                    {
                        "name": "patch_archive_anchor.c.o",
                        "sha256": hashlib.sha256(b"anchor").hexdigest(),
                        "size": 1,
                    }
                ],
            }
        )
        payloads["forced-object-link-audit"]["baseline-member-inventory"] = baseline_inventory
        payloads["forced-object-link-audit"]["patch-member-inventory"] = patch_inventory

        for lane in ("compiler-clang", "compiler-gcc", "compiler-msvc"):
            payloads[lane]["generated-source-archive"] = payloads["generation"]["generated-source-archive"]
            payloads[lane]["source-file-inventory"] = payloads["generation"]["source-file-inventory"]
        for lane in ("address-sanitizer", "undefined-behavior-sanitizer"):
            payloads[lane]["analysis-source-archive"] = payloads[
                "clang-static-analysis"
            ]["analysis-source-archive"]
            payloads[lane]["analysis-source-inventory"] = payloads[
                "clang-static-analysis"
            ]["analysis-source-inventory"]
        forced = payloads["forced-object-link-audit"]
        forced["generated-source-archive"] = payloads["generation"]["generated-source-archive"]
        forced["source-file-inventory"] = payloads["generation"]["source-file-inventory"]
        for kind in ("overlay-lookup-table", "overlay-lifecycle-table", "relocation-table"):
            forced[kind] = payloads["generation"][kind]

        repro_a = payloads["reproducibility-run-a"]
        repro_b = payloads["reproducibility-run-b"]
        repro_a["normalized-run-payload"] = self.canonical(
            {"normalization_policy_id": "phase4-run-payload-v1", "records": []}
        )
        for kind in set(repro_a) & set(payloads["generation"]):
            repro_a[kind] = payloads["generation"][kind]
        repro_a["baseline-member-inventory"] = baseline_inventory
        repro_a["patch-member-inventory"] = patch_inventory
        for kind in repro_a:
            repro_b[kind] = repro_a[kind]

        categories = {
            "symbol-addition": 0,
            "symbol-removal": 0,
            "symbol-rename": 0,
            "section-movement": 0,
            "lookup-change": 1,
            "patch-change": 0,
            "compiler-option-change": 1,
        }
        config = payloads["configuration-mutation"]
        config["predeclared-expectation"] = self.canonical(categories)
        config["mutated-config-set"] = self.canonical(
            {"mutation_ids": ["lookup", "compiler-option"]}
        )

        products = {
            lane: {
                kind: (f"{lane}/{kind}", hashlib.sha256(value).hexdigest())
                for kind, value in lane_products.items()
            }
            for lane, lane_products in payloads.items()
        }
        source_digest = products["generation"]["source-file-inventory"][1]
        analysis_digest = products["clang-static-analysis"]["analysis-source-inventory"][1]
        results: dict[tuple[str, str], dict[str, object]] = {}
        for family in ("clang", "gcc", "msvc"):
            results[(f"compiler-{family}", "compiler-result")] = {
                "family": family,
                "source_inventory_sha256": source_digest,
            }
        baseline_expected = {
            "unmodified_body_member_count": completion.EXPECTED_GENERATED_BODY_COUNT,
            "callable_wrapper_member_count": completion.EXPECTED_GENERATED_BODY_COUNT,
            "alternate_entry_thunk_member_count": 1,
            "section_address_member_count": 3,
            "lookup_table_member_count": 2,
            "lifecycle_table_member_count": 1,
            "relocation_table_member_count": 5,
            "other_support_member_count": 0,
            "support_member_count": 12,
            "member_count": completion.EXPECTED_GENERATED_BODY_COUNT * 2 + 12,
            "one_function_per_body_member_verified": True,
            "wrapper_to_body_mapping_verified": True,
            "alternate_entry_mapping_verified": True,
            "forced_object_link_passed": True,
            "compile_passed": True,
            "link_passed": True,
            "archive_sha256": products["forced-object-link-audit"]["baseline-archive"][1],
            "member_inventory_sha256": products["forced-object-link-audit"]["baseline-member-inventory"][1],
        }
        patch_expected = {
            "approved_replacement_member_count": 0,
            "callable_wrapper_member_count": 0,
            "anchor_member_count": 1,
            "other_support_member_count": 0,
            "support_member_count": 1,
            "member_count": 1,
            "one_function_per_replacement_member_verified": True,
            "forced_object_link_passed": True,
            "compile_passed": True,
            "link_passed": True,
            "archive_sha256": products["forced-object-link-audit"]["patch-archive"][1],
            "member_inventory_sha256": products["forced-object-link-audit"]["patch-member-inventory"][1],
        }
        minimal_expected = {
            "target_runtime_abi_exclusion_count": 0,
            "required_host_function_export_count": 2,
            "resolved_host_function_export_count": 2,
            "required_host_data_export_count": 1,
            "resolved_host_data_export_count": 1,
            "unresolved_host_export_count": 0,
            "handwritten_bridge_unit_count": completion.ANALYSIS_BRIDGE_UNIT_COUNT,
            "section_address_count": completion.EXPECTED_EXECUTABLE_SECTION_COUNT,
            "section_address_capacity": completion.SECTION_ADDRESS_CAPACITY,
            "initialized_section_address_count": completion.EXPECTED_EXECUTABLE_SECTION_COUNT,
            "section_address_support_member_count": 3,
            "section_initialization_passed": True,
            "section_exact_capacity_test_passed": True,
            "section_over_capacity_rejection_passed": True,
            "object_symbol_ownership_verified": True,
            "host_function_inventory_sha256": products["forced-object-link-audit"]["host-function-inventory"][1],
            "host_data_inventory_sha256": products["forced-object-link-audit"]["host-data-inventory"][1],
            "relocation_table_entry_count": completion.EXPECTED_R32_RELOCATION_COUNT,
            "forced_object_link_passed": True,
        }
        for kind, expected in (
            ("baseline-result", baseline_expected),
            ("patch-result", patch_expected),
            ("minimal-runtime-result", minimal_expected),
        ):
            results[("forced-object-link-audit", kind)] = {
                **expected,
                "result_sha256": hashlib.sha256(kind.encode()).hexdigest(),
            }
        results[("clang-static-analysis", "analyzer-result")] = {
            "tool_id": "clang-analyzer",
            "passed": True,
        }
        for evidence_kind, sanitizer_id in (
            ("address-sanitizer", "address"),
            ("undefined-behavior-sanitizer", "undefined-behavior"),
        ):
            results[(evidence_kind, "sanitizer-result")] = {
                "sanitizer_id": sanitizer_id,
                "compiler_family": "clang",
                "target_id": "linux-x64",
                "run_count": 1,
                "issue_count": 0,
                "passed": True,
                "source_inventory_sha256": analysis_digest,
            }
        results[("configuration-mutation", "config-diff-result")] = {
            "mutation_case_count": 2,
            "base_config_sha256": products["configuration-mutation"]["base-config"][1],
            "mutated_config_set_sha256": products["configuration-mutation"]["mutated-config-set"][1],
            "predeclared_expectation_sha256": products["configuration-mutation"]["predeclared-expectation"][1],
            "expected_change_count": 2,
            "observed_change_count": 2,
            "expected_category_counts": categories,
            "observed_category_counts": copy.deepcopy(categories),
            "unexpected_change_count": 0,
            "unexpected_category_counts": {key: 0 for key in categories},
            "containment_passed": True,
            "result_sha256": hashlib.sha256(b"config-result").hexdigest(),
        }
        pins = {
            "jfg_decomp_commit": "1" * 40,
            "n64recomp_commit": "2" * 40,
            "minimal_runtime_source_sha256": analysis_digest,
            "n64recomp_patch_set_sha256": hashlib.sha256(b"patches").hexdigest(),
            "supported_input_id": "jfg-us-retail",
            "dependency_lock_sha256": hashlib.sha256(b"lock").hexdigest(),
            "config_sha256": products["configuration-mutation"]["base-config"][1],
            "input_elf_sha256": hashlib.sha256(b"elf").hexdigest(),
            "generator_executable_sha256": hashlib.sha256(b"generator").hexdigest(),
        }
        return products, payloads, results, pins

    def test_no_caller_builder_derives_every_core_class_and_rejects_mutations(self) -> None:
        products, payloads, results, pins = self.builder_fixture()

        def derive() -> dict[str, object]:
            with mock.patch.object(completion, "_prepared_products", return_value=products), mock.patch.object(
                completion,
                "_execution_product_bytes",
                side_effect=lambda _products, _root, lane: payloads[lane],
            ), mock.patch.object(
                completion,
                "_public_result",
                side_effect=lambda _products, _root, lane, kind: copy.deepcopy(results[(lane, kind)]),
            ), mock.patch.object(
                completion, "_generated_source_contents", return_value={"sources.json": b"{}"}
            ), mock.patch.object(
                completion, "_source_role_facts", return_value=(0, hashlib.sha256(b"aliases").hexdigest())
            ), mock.patch.object(
                completion, "_dependency_pins", return_value=copy.deepcopy(pins)
            ), mock.patch.object(
                completion, "validate_phase4_public_core", return_value=[]
            ), mock.patch.object(
                completion, "_verify_generation_semantics"
            ), mock.patch.object(
                completion, "_verify_cpu_section_inventory"
            ), mock.patch.object(
                completion, "_verify_archive_pair"
            ), mock.patch.object(
                completion,
                "_member_inventory",
                side_effect=lambda payload: [None]
                * (
                    completion.EXPECTED_GENERATED_BODY_COUNT * 2 + 12
                    if payload
                    == payloads["forced-object-link-audit"]["baseline-member-inventory"]
                    else 1
                ),
            ), mock.patch.object(
                completion, "_verify_forced_object_semantics"
            ), mock.patch.object(
                completion, "_verify_config_mutation"
            ):
                return completion.derive_public_core({}, Path("."), {})

        core = derive()
        self.assertEqual(
            set(core),
            {
                "pins",
                "symbols",
                "calls",
                "relocations",
                "overlays",
                "stubs",
                "compilers",
                "analysis",
                "libraries",
                "reproducibility",
                "config_diff",
            },
        )
        self.assertEqual(
            core["libraries"]["baseline"]["member_count"],
            completion.EXPECTED_GENERATED_BODY_COUNT * 2 + 12,
        )
        self.assertEqual(core["libraries"]["minimal_runtime"]["required_host_function_export_count"], 2)
        self.assertEqual(core["config_diff"]["mutation_case_count"], 2)

        semantic = json.loads(payloads["generation"]["generation-result"])
        denominator_mutations = (
            (semantic["symbols"], "expected_count", -1),
            (
                semantic["calls"]["direct"]["transfer_role_counts"],
                "direct-tail",
                -1,
            ),
            (semantic["calls"]["indirect_ranges"], "native_return_count", -1),
            (semantic["relocations"]["data_r32"], "expected_count", -1),
            (semantic["overlays"], "executable_section_count", -1),
        )
        for record, field, delta in denominator_mutations:
            with self.subTest(semantic_denominator=field):
                record[field] += delta
                payloads["generation"]["generation-result"] = self.canonical(semantic)
                with self.assertRaises(completion.CompletionBuildError):
                    derive()
                record[field] -= delta
        payloads["generation"]["generation-result"] = self.canonical(semantic)

        results[("forced-object-link-audit", "baseline-result")]["member_count"] -= 1
        with self.assertRaises(completion.CompletionBuildError):
            derive()
        results[("forced-object-link-audit", "baseline-result")]["member_count"] += 1
        payloads["reproducibility-run-b"]["report-set"] += b"mutation"
        with self.assertRaises(completion.CompletionBuildError):
            derive()
        payloads["reproducibility-run-b"]["report-set"] = payloads[
            "reproducibility-run-a"
        ]["report-set"]
        results[("configuration-mutation", "config-diff-result")][
            "mutation_case_count"
        ] = 1
        with self.assertRaises(completion.CompletionBuildError):
            derive()
        results[("configuration-mutation", "config-diff-result")][
            "mutation_case_count"
        ] = 2
        host_inventory = json.loads(
            payloads["forced-object-link-audit"]["host-function-inventory"]
        )
        host_inventory["records"][0]["owner_role"] = "generated"
        payloads["forced-object-link-audit"]["host-function-inventory"] = self.canonical(
            host_inventory
        )
        with self.assertRaises(completion.CompletionBuildError):
            derive()

    def test_unaccepted_adr_blocks_before_signing(self) -> None:
        with mock.patch.object(completion, "_adr_is_accepted", return_value=False):
            with self.assertRaises(completion.CompletionBuildError):
                completion.finalize({}, {}, Path("."), Path("missing"), {}, Path("missing"), Path("missing"))

    def test_builder_uses_strict_owner_attributed_adr_parser(self) -> None:
        accepted = "# Decision\n\n- Status: Accepted by `TK22-26`\n- Date: 2026-08-04\n"
        variants = {
            accepted: True,
            accepted.replace("Accepted by `TK22-26`", "Proposed for human approval"): False,
            accepted + "- Status: Accepted by `TK22-26`\n": False,
            "# Decision\n\n```\n- Status: Accepted by `TK22-26`\n```\n": False,
            accepted.replace("`TK22-26`", "`another-owner`"): False,
        }
        for text, expected in variants.items():
            with self.subTest(expected=expected), mock.patch.object(
                completion, "_read_regular", return_value=text.encode("utf-8")
            ):
                self.assertEqual(completion._adr_is_accepted(), expected)

    def private_body_recipe(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "kind": "jfg-phase4-private-body-preparation",
            "identity_sources": [{"path": "input.bin"}],
            "executions": [
                {
                    "evidence_kind": evidence_kind,
                    "id": "execution-" + evidence_kind,
                    "case_id": (
                        "reproducibility-case"
                        if evidence_kind.startswith("reproducibility-run-")
                        else "case-" + evidence_kind
                    ),
                    "environment": {
                        "environment_id": (
                            "reproducibility-environment"
                            if evidence_kind.startswith("reproducibility-run-")
                            else "environment-" + evidence_kind
                        ),
                        "platform_id": "test-platform",
                        "architecture_id": "test-architecture",
                        "toolchain_sha256": self.canonical(evidence_kind).hex()[:64].ljust(64, "0"),
                    },
                }
                for evidence_kind in private_body.EVIDENCE_KINDS
            ],
        }

    def test_private_body_recipe_cannot_assert_results_or_commands(self) -> None:
        recipe = self.private_body_recipe()
        paths, executions = private_body._recipe(recipe)
        self.assertEqual(paths, ["input.bin"])
        self.assertEqual(set(executions), set(private_body.EVIDENCE_KINDS))
        for forbidden in (
            {"passed": True},
            {"command": "all checks passed"},
            {"transcript": {"validated": True}},
        ):
            invalid = copy.deepcopy(recipe)
            invalid["executions"][0].update(forbidden)
            with self.assertRaises(private_body.PrivateBodyBuildError):
                private_body._recipe(invalid)

    def test_private_body_recipe_requires_exact_unique_matrix(self) -> None:
        recipe = self.private_body_recipe()
        recipe["executions"][1]["evidence_kind"] = recipe["executions"][0]["evidence_kind"]
        with self.assertRaises(private_body.PrivateBodyBuildError):
            private_body._recipe(recipe)


if __name__ == "__main__":
    unittest.main()
