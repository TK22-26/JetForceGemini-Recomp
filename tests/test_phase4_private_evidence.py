from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import scripts.validate_phase4_manifest as phase4
import scripts.validate_phase4_private_evidence as private
import scripts.phase4_evidence_harness as production
from scripts.validate_g2_private_evidence import PinnedHarness


class Phase4PrivateEvidenceTests(unittest.TestCase):
    def test_analysis_policy_matches_the_pinned_production_harness(self) -> None:
        self.assertEqual(
            private.ANALYSIS_SOURCE_POLICY_ID,
            production.ANALYSIS_SOURCE_POLICY_ID,
        )
        self.assertEqual(
            private.ANALYSIS_BRIDGE_UNIT_COUNT,
            production.ANALYSIS_BRIDGE_UNIT_COUNT,
        )

    @staticmethod
    def digest(payload: bytes | str) -> str:
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def canonical(value: object) -> bytes:
        return private._canonical_bytes(value)

    def make_public_manifest(self) -> tuple[dict[str, object], dict[str, bytes]]:
        document = phase4.load_json(phase4.DEFAULT_MANIFEST)
        assert isinstance(document, dict)

        def replace(value: object, location: str = "root") -> object:
            if isinstance(value, dict):
                return {
                    key: replace(child, f"{location}.{key}")
                    for key, child in value.items()
                }
            if isinstance(value, list):
                return [
                    replace(child, f"{location}.{index}")
                    for index, child in enumerate(value)
                ]
            if isinstance(value, str) and len(value) in {40, 64} and all(
                character in "0123456789abcdef" for character in value
            ):
                algorithm = hashlib.sha1 if len(value) == 40 else hashlib.sha256
                return algorithm(location.encode("utf-8")).hexdigest()
            return value

        converted = replace(document)
        assert isinstance(converted, dict)
        pins = converted["pins"]
        symbols = converted["symbols"]
        compilers = converted["compilers"]
        analysis = converted["analysis"]
        libraries = converted["libraries"]
        overlays = converted["overlays"]
        reproducibility = converted["reproducibility"]
        config_diff = converted["config_diff"]
        assert isinstance(pins, dict)
        assert isinstance(symbols, dict)
        assert isinstance(compilers, list)
        assert isinstance(analysis, dict)
        assert isinstance(libraries, dict)
        assert isinstance(overlays, dict)
        assert isinstance(reproducibility, dict)
        assert isinstance(config_diff, dict)

        payloads: dict[str, bytes] = {}

        def bind(payload: bytes) -> str:
            digest = self.digest(payload)
            payloads[digest] = payload
            return digest

        input_elf = bind(b"test input elf\n")
        config = bind(b"test base configuration\n")
        generator = bind(b"test generator executable identity\n")
        generated_inventory = bind(b"test generated source inventory\n")
        analysis_inventory = bind(b"test analysis source inventory\n")
        pins["input_elf_sha256"] = input_elf
        pins["config_sha256"] = config
        pins["generator_executable_sha256"] = generator
        pins["minimal_runtime_source_sha256"] = analysis_inventory

        for item in compilers:
            assert isinstance(item, dict)
            family = str(item["family"])
            item["source_inventory_sha256"] = generated_inventory
            item["option_set_sha256"] = bind(f"{family} option set\n".encode("utf-8"))
            item["compiler_executable_sha256"] = bind(
                f"{family} compiler executable\n".encode("utf-8")
            )
        symbols["inventory_sha256"] = generated_inventory
        reproducibility["generated_inventory_sha256"] = generated_inventory
        reproducibility["source_file_inventory_sha256"] = generated_inventory
        reproducibility["overlay_table_sha256"] = overlays["lookup_table_sha256"]
        reproducibility["lifecycle_table_sha256"] = overlays["lifecycle_table_sha256"]
        reproducibility["relocation_table_sha256"] = overlays["relocation_table_sha256"]
        baseline = libraries["baseline"]
        patch = libraries["patch"]
        assert isinstance(baseline, dict)
        assert isinstance(patch, dict)
        reproducibility["baseline_member_inventory_sha256"] = baseline[
            "member_inventory_sha256"
        ]
        reproducibility["patch_member_inventory_sha256"] = patch[
            "member_inventory_sha256"
        ]

        analysis["source_inventory_sha256"] = analysis_inventory
        sanitizers = analysis["sanitizers"]
        assert isinstance(sanitizers, list)
        for sanitizer in sanitizers:
            assert isinstance(sanitizer, dict)
            sanitizer["source_inventory_sha256"] = analysis_inventory

        config_diff["base_config_sha256"] = config
        mutated = bind(b"test mutated configuration set\n")
        config_diff["mutated_config_set_sha256"] = mutated
        expected_categories = config_diff["expected_category_counts"]
        expectation_payload = self.canonical(expected_categories)
        config_diff["predeclared_expectation_sha256"] = bind(expectation_payload)

        analyzer = analysis["clang_static_analysis"]
        assert isinstance(analyzer, dict)
        analyzer_declaration = self.canonical({"tool_id": analyzer["tool_id"]})
        bind(analyzer_declaration)
        for sanitizer in sanitizers:
            assert isinstance(sanitizer, dict)
            declaration = self.canonical(
                {
                    "sanitizer_id": sanitizer["sanitizer_id"],
                    "compiler_family": sanitizer["compiler_family"],
                    "target_id": sanitizer["target_id"],
                }
            )
            bind(declaration)
        normalization = self.canonical(
            {"normalization_policy_id": reproducibility["normalization_policy_id"]}
        )
        bind(normalization)
        return converted, payloads

    def test_g3_projection_is_exact_noncompletion_and_matches_final_core(self) -> None:
        public_document, _ = self.make_public_manifest()
        core = {
            field: copy.deepcopy(public_document[field])
            for field in private.G3_PRODUCT_CORE_FIELDS
        }
        projection = private.g3_product_projection(core, self.digest("private body"))
        self.assertEqual(private.g3_product_projection_errors(projection), [])
        self.assertIs(projection["completion"], False)
        self.assertNotIn("gate", projection)
        self.assertNotIn("attestation", projection)
        self.assertEqual(
            private.public_claim_sha256(projection),
            private.public_claim_sha256(public_document),
        )

        completion_only = copy.deepcopy(public_document)
        completion_only["gate"] = {"predecessor_g2_evidence_sha256": self.digest("changed")}
        completion_only["attestation"] = {"signature": "changed"}
        completion_only["$schema"] = "changed"
        completion_only["kind"] = "changed"
        self.assertEqual(
            private.public_claim_sha256(completion_only),
            private.public_claim_sha256(projection),
        )

        changed_core = copy.deepcopy(projection)
        changed_core["symbols"]["generated_count"] += 1  # type: ignore[index]
        self.assertNotEqual(
            private.public_claim_sha256(changed_core),
            private.public_claim_sha256(projection),
        )
        self.assertEqual(
            private.g3_product_projection_errors(changed_core),
            ["Phase 4 G3 product projection is invalid"],
        )

        empty_nested = copy.deepcopy(projection)
        empty_nested["symbols"] = {}
        self.assertEqual(
            private.g3_product_projection_errors(empty_nested),
            ["Phase 4 G3 product projection is invalid"],
        )

        for mutate in (
            lambda item: item.update({"gate": {"predecessor_g2_complete": True}}),
            lambda item: item.update({"completion": True}),
            lambda item: item.update({"private_evidence_sha256": "0" * 64}),
            lambda item: item.pop("compilers"),
        ):
            malformed = copy.deepcopy(projection)
            mutate(malformed)
            self.assertEqual(
                private.g3_product_projection_errors(malformed),
                ["Phase 4 G3 product projection is invalid"],
            )

    def make_harness(self, root: Path, *, oversized: bool = False) -> PinnedHarness:
        harness = root / ("oversized-harness.py" if oversized else "harness.py")
        if oversized:
            source = "import sys\nsys.stdout.write('x' * 140000)\n"
        else:
            source = r'''import hashlib
import json
import pathlib
import sys

request = json.load(sys.stdin)
execution = request["execution"]
root = pathlib.Path.cwd().resolve()
for artifact in execution["artifacts"]:
    candidate = (root / pathlib.PurePosixPath(artifact["path"])).resolve()
    candidate.relative_to(root)
    payload = candidate.read_bytes()
    if hashlib.sha256(payload).hexdigest() != artifact["sha256"]:
        raise SystemExit(3)
result = {
    "schema_version": 1,
    "kind": "jfg-phase4-harness-transcript",
    "execution_id": execution["id"],
    "evidence_kind": execution["evidence_kind"],
    "harness_id": execution["harness_id"],
    "harness_sha256": execution["harness_sha256"],
    "case_id": execution["case_id"],
    "public_claim_sha256": request["public_claim_sha256"],
    "public_record_sha256": execution["public_record_sha256"],
    "public_result_set_sha256": execution["public_result_set_sha256"],
    "subject_sha256": execution["subject_sha256"],
    "source_input_sha256": execution["source_input_sha256"],
    "declaration_sha256": execution["declaration_sha256"],
    "pins_sha256": execution["pins_sha256"],
    "environment_sha256": execution["environment_sha256"],
    "input_set_sha256": execution["input_set_sha256"],
    "output_set_sha256": execution["output_set_sha256"],
    "artifact_set_sha256": execution["artifact_set_sha256"],
    "result_sha256": execution["result_sha256"],
    "observed_exit_code": execution["observed_exit_code"],
    "passed": execution["passed"],
    "validated": True,
}
json.dump(result, sys.stdout, sort_keys=True, separators=(",", ":"))
'''
        harness.write_text(source, encoding="utf-8", newline="\n")
        return PinnedHarness(
            "phase4-test-harness",
            harness,
            self.digest(harness.read_bytes()),
            10.0,
        )

    def make_bundle(
        self,
        root: Path,
        public_document: dict[str, object],
        payloads: dict[str, bytes],
        pin: PinnedHarness,
    ) -> tuple[dict[str, object], dict[str, PinnedHarness]]:
        pins = public_document["pins"]
        assert isinstance(pins, dict)
        pins_digest = self.digest(self.canonical(pins))
        private_document: dict[str, object] = {
            "$schema": "../../../schemas/phase4-private-evidence.schema.json",
            "schema_version": 2,
            "kind": "jfg-phase4-private-executable-evidence",
            "public_claim_sha256": private.public_claim_sha256(public_document),
            "pins": copy.deepcopy(pins),
            "pins_sha256": pins_digest,
            "executions": [],
            "evidence_set_sha256": "0" * 64,
        }
        executions = private_document["executions"]
        assert isinstance(executions, list)
        harness_pins: dict[str, PinnedHarness] = {}
        shared_repro_environment: dict[str, object] | None = None

        for index, evidence_kind in enumerate(private.EVIDENCE_KINDS):
            binding = private._binding(public_document, evidence_kind)
            assert binding is not None
            source_digest = str(binding["source_input_sha256"])
            subject_digest = str(binding["subject_sha256"])
            declaration_digest = str(binding["declaration_sha256"])
            self.assertIn(source_digest, payloads)
            self.assertIn(subject_digest, payloads)
            self.assertIn(declaration_digest, payloads)

            stem = f"e{index:02d}"
            if evidence_kind.startswith("reproducibility-run-"):
                if shared_repro_environment is None:
                    shared_repro_environment = {
                        "environment_id": "repro-environment",
                        "platform_id": "test-platform",
                        "architecture_id": "test-architecture",
                        "toolchain_sha256": binding["toolchain_sha256"],
                    }
                environment = copy.deepcopy(shared_repro_environment)
                case_id = "reproducibility-pair"
            else:
                environment = {
                    "environment_id": f"environment-{stem}",
                    "platform_id": "test-platform",
                    "architecture_id": "test-architecture",
                    "toolchain_sha256": binding.get("toolchain_sha256")
                    or self.digest(f"toolchain-{stem}"),
                }
                case_id = f"case-{stem}"

            artifacts: list[dict[str, str]] = []

            def artifact(role: str, suffix: str, digest: str, payload: bytes) -> None:
                path = root / f"{stem}-{suffix}"
                path.write_bytes(payload)
                self.assertEqual(self.digest(payload), digest)
                artifacts.append({"path": path.name, "role": role, "sha256": digest})

            if evidence_kind == "configuration-mutation":
                artifact("configuration", "configuration.bin", source_digest, payloads[source_digest])
                artifact("input", "subject.bin", subject_digest, payloads[subject_digest])
                artifact(
                    "expectation",
                    "expectation.json",
                    declaration_digest,
                    payloads[declaration_digest],
                )
            else:
                artifact(
                    "configuration",
                    "configuration.bin",
                    declaration_digest,
                    payloads[declaration_digest],
                )
                artifact("input", "input.bin", source_digest, payloads[source_digest])
                if subject_digest != source_digest:
                    artifact("input", "subject.bin", subject_digest, payloads[subject_digest])
            output_payload = f"verified output {evidence_kind}\n".encode("utf-8")
            artifact("output", "output.bin", self.digest(output_payload), output_payload)

            input_records = [
                record for record in artifacts if record["role"] in private._INPUT_ROLES
            ]
            output_records = [
                record for record in artifacts if record["role"] in private._OUTPUT_ROLES
            ]
            execution: dict[str, object] = {
                "id": f"execution-{stem}",
                "evidence_kind": evidence_kind,
                "harness_id": pin.harness_id,
                "harness_sha256": pin.script_sha256,
                "case_id": case_id,
                "public_record_sha256": binding["public_record_sha256"],
                "public_result_set_sha256": binding["public_result_set_sha256"],
                "subject_sha256": subject_digest,
                "source_input_sha256": source_digest,
                "declaration_sha256": declaration_digest,
                "pins_sha256": pins_digest,
                "environment": environment,
                "environment_sha256": self.digest(self.canonical(environment)),
                "input_set_sha256": self.digest(self.canonical(input_records)),
                "output_set_sha256": self.digest(self.canonical(output_records)),
                "artifact_set_sha256": "0" * 64,
                "result_sha256": "0" * 64,
                "observed_exit_code": 0,
                "passed": True,
                "artifacts": artifacts,
            }
            result_payload = self.canonical(
                private._result_expectation(private_document, execution)
            )
            artifact(
                "result",
                "result.json",
                self.digest(result_payload),
                result_payload,
            )
            execution["result_sha256"] = self.digest(result_payload)
            execution["artifact_set_sha256"] = self.digest(self.canonical(artifacts))
            executions.append(execution)
            harness_pins[evidence_kind] = pin

        private_document["evidence_set_sha256"] = self.digest(
            self.canonical(executions)
        )
        return private_document, harness_pins

    def make_complete_fixture(
        self, root: Path
    ) -> tuple[
        dict[str, object],
        dict[str, object],
        dict[str, object],
        dict[str, PinnedHarness],
    ]:
        public_document, payloads = self.make_public_manifest()
        pin = self.make_harness(root)
        private_document, harness_pins = self.make_bundle(
            root, public_document, payloads, pin
        )
        schema = phase4.load_json(private.PRIVATE_SCHEMA)
        assert isinstance(schema, dict)
        return public_document, private_document, schema, harness_pins

    def test_structured_bundle_executes_every_pinned_harness(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="phase4-private-v2-", dir=phase4.ROOT / "tools"
        ) as temp:
            root = Path(temp)
            public_document, private_document, schema, pins = self.make_complete_fixture(root)
            self.assertEqual(
                private._validate_documents_for_tests(
                    private_document, public_document, schema, root, pins
                ),
                [],
            )
            core = {
                field: copy.deepcopy(public_document[field])
                for field in private.G3_PRODUCT_CORE_FIELDS
            }
            projection = private.g3_product_projection(
                core, self.digest(self.canonical(private_document))
            )
            self.assertEqual(
                private._validate_documents_for_tests(
                    private_document, projection, schema, root, pins
                ),
                [],
            )

    def test_production_registry_is_byte_pinned_and_not_publicly_injectable(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="phase4-private-v2-", dir=phase4.ROOT / "tools"
        ) as temp:
            root = Path(temp)
            public_document, private_document, _, pins = self.make_complete_fixture(root)
            body = root / "phase4-private.json"
            body_bytes = self.canonical(private_document)
            body.write_bytes(body_bytes)
            attestation = public_document["attestation"]
            assert isinstance(attestation, dict)
            attestation["private_evidence_sha256"] = self.digest(body_bytes)

            self.assertEqual(
                set(private.PRODUCTION_HARNESS_PINS), set(private.EVIDENCE_KINDS)
            )
            production_pins = set(private.PRODUCTION_HARNESS_PINS.values())
            self.assertEqual(len(production_pins), 1)
            production_pin = next(iter(production_pins))
            self.assertEqual(
                production_pin.script_sha256,
                self.digest(production_pin.script_path.read_bytes()),
            )
            with mock.patch.object(private, "PRODUCTION_HARNESS_PINS", pins):
                errors = private.validate_private_file(body, public_document)
            self.assertEqual(
                errors,
                ["Phase 4 private evidence: execution does not use the pinned harness"],
            )
            attestation["private_evidence_sha256"] = self.digest(b"different bundle")
            errors = private.validate_private_file(body, public_document)
            self.assertIn(
                "completion: private evidence digest does not match the local body",
                errors,
            )

    def test_arbitrary_text_and_handwritten_pass_flag_are_not_evidence(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="phase4-private-v2-", dir=phase4.ROOT / "tools"
        ) as temp:
            root = Path(temp)
            public_document, private_document, schema, pins = self.make_complete_fixture(root)
            body = root / "phase4-private.json"
            body.write_bytes(b"private-evidence-body")
            attestation = public_document["attestation"]
            assert isinstance(attestation, dict)
            attestation["private_evidence_sha256"] = self.digest(body.read_bytes())
            self.assertEqual(
                private.validate_private_file(body, public_document),
                ["completion: private evidence body could not be read"],
            )

            forged = copy.deepcopy(private_document)
            executions = forged["executions"]
            assert isinstance(executions, list)
            execution = executions[0]
            assert isinstance(execution, dict)
            artifacts = execution["artifacts"]
            assert isinstance(artifacts, list)
            result_record = next(
                item
                for item in artifacts
                if isinstance(item, dict) and item.get("role") == "result"
            )
            result_path = root / str(result_record["path"])
            forged_result = self.canonical({"passed": True})
            result_path.write_bytes(forged_result)
            result_digest = self.digest(forged_result)
            result_record["sha256"] = result_digest
            execution["result_sha256"] = result_digest
            execution["artifact_set_sha256"] = self.digest(self.canonical(artifacts))
            forged["evidence_set_sha256"] = self.digest(self.canonical(executions))
            errors = private._validate_documents_for_tests(
                forged, public_document, schema, root, pins
            )
            self.assertIn(
                "Phase 4 private evidence: structured result contract differs", errors
            )

    def test_pre_g2_audit_rejects_pass_result_and_artifact_mutation(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="phase4-private-v2-", dir=phase4.ROOT / "tools"
        ) as temp:
            root = Path(temp)
            public_document, private_document, schema, pins = self.make_complete_fixture(root)
            for field, value in (
                ("passed", False),
                ("result_sha256", self.digest("mutated-result")),
                ("artifact_set_sha256", self.digest("mutated-artifacts")),
            ):
                with self.subTest(field=field):
                    changed = copy.deepcopy(private_document)
                    changed["executions"][0][field] = value  # type: ignore[index]
                    changed["evidence_set_sha256"] = self.digest(
                        self.canonical(changed["executions"])
                    )
                    self.assertTrue(
                        private._validate_documents_for_tests(
                            changed, public_document, schema, root, pins
                        )
                    )

    def test_pre_g2_audit_rejects_missing_and_stale_harness_pins(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="phase4-private-v2-", dir=phase4.ROOT / "tools"
        ) as temp:
            root = Path(temp)
            public_document, private_document, schema, pins = self.make_complete_fixture(root)
            missing = dict(pins)
            missing.pop("generation")
            errors = private._validate_documents_for_tests(
                private_document, public_document, schema, root, missing
            )
            self.assertIn("Phase 4 private evidence: pinned harness is unavailable", errors)

            stale = dict(pins)
            original = stale["generation"]
            stale["generation"] = PinnedHarness(
                original.harness_id,
                original.script_path,
                self.digest("stale-harness"),
                original.timeout_seconds,
            )
            errors = private._validate_documents_for_tests(
                private_document, public_document, schema, root, stale
            )
            self.assertIn(
                "Phase 4 private evidence: execution does not use the pinned harness",
                errors,
            )

    def test_public_records_exact_matrix_and_repro_pair_are_bound(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="phase4-private-v2-", dir=phase4.ROOT / "tools"
        ) as temp:
            root = Path(temp)
            public_document, private_document, schema, pins = self.make_complete_fixture(root)

            changed_public = copy.deepcopy(public_document)
            changed_public["compilers"][0]["result_sha256"] = self.digest("changed")  # type: ignore[index]
            errors = private._validate_documents_for_tests(
                private_document, changed_public, schema, root, pins
            )
            self.assertIn("Phase 4 private evidence: public claim digest is unbound", errors)
            self.assertIn("Phase 4 private evidence: public execution binding differs", errors)

            malformed_public = copy.deepcopy(public_document)
            malformed_public["compilers"][0]["source_inventory_sha256"] = ["private"]  # type: ignore[index]
            errors = private._validate_documents_for_tests(
                private_document, malformed_public, schema, root, pins
            )
            self.assertIn(
                "Phase 4 private evidence: public binding is unavailable", errors
            )

            incomplete = copy.deepcopy(private_document)
            executions = incomplete["executions"]
            assert isinstance(executions, list)
            executions.pop()
            incomplete["evidence_set_sha256"] = self.digest(self.canonical(executions))
            errors = private._validate_documents_for_tests(
                incomplete, public_document, schema, root, pins
            )
            self.assertIn("schema: contract violation", errors)

            unpaired = copy.deepcopy(private_document)
            run_b = next(
                item
                for item in unpaired["executions"]  # type: ignore[index]
                if item["evidence_kind"] == "reproducibility-run-b"
            )
            run_b["case_id"] = "different-repro-case"
            unpaired["evidence_set_sha256"] = self.digest(
                self.canonical(unpaired["executions"])
            )
            errors = private._validate_documents_for_tests(
                unpaired, public_document, schema, root, pins
            )
            self.assertIn(
                "Phase 4 private evidence: reproducibility runs are not paired", errors
            )

    def test_predeclared_mutation_artifact_and_bounded_harness_output_are_required(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="phase4-private-v2-", dir=phase4.ROOT / "tools"
        ) as temp:
            root = Path(temp)
            public_document, private_document, schema, pins = self.make_complete_fixture(root)
            changed = copy.deepcopy(private_document)
            execution = next(
                item
                for item in changed["executions"]  # type: ignore[index]
                if item["evidence_kind"] == "configuration-mutation"
            )
            expectation = next(
                item for item in execution["artifacts"] if item["role"] == "expectation"
            )
            expectation["role"] = "input"
            execution["artifact_set_sha256"] = self.digest(
                self.canonical(execution["artifacts"])
            )
            changed["evidence_set_sha256"] = self.digest(self.canonical(changed["executions"]))
            errors = private._validate_documents_for_tests(
                changed, public_document, schema, root, pins
            )
            self.assertIn(
                "Phase 4 private evidence: predeclared mutation expectation is unbound",
                errors,
            )

            oversized_pin = self.make_harness(root, oversized=True)
            oversized_pins = {
                evidence_kind: oversized_pin for evidence_kind in private.EVIDENCE_KINDS
            }
            oversized_bundle, _ = self.make_bundle(
                root, public_document, self.make_public_manifest()[1], oversized_pin
            )
            errors = private._validate_documents_for_tests(
                oversized_bundle, public_document, schema, root, oversized_pins
            )
            self.assertIn("private evidence: pinned harness rejected the execution", errors)

    def test_bundle_symlink_and_tracked_public_file_are_rejected(self) -> None:
        public_document, _ = self.make_public_manifest()
        self.assertEqual(
            private.validate_private_file(phase4.DEFAULT_MANIFEST, public_document),
            ["completion: private evidence body must be external or ignored"],
        )
        with tempfile.TemporaryDirectory(
            prefix="phase4-private-v2-", dir=phase4.ROOT / "tools"
        ) as temp:
            root = Path(temp)
            target = root / "target.json"
            target.write_text("{}", encoding="utf-8")
            link = root / "link.json"
            try:
                os.symlink(target, link)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are unavailable")
            self.assertEqual(
                private.validate_private_file(link, public_document),
                ["completion: private evidence body could not be read"],
            )


if __name__ == "__main__":
    unittest.main()
