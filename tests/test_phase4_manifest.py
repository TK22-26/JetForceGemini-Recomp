from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import scripts.validate_phase4_manifest as phase4
import scripts.validate_g2_private_evidence as g2_private


class Phase4ManifestTests(unittest.TestCase):
    def load_manifest_and_schema(self) -> tuple[dict[str, object], dict[str, object]]:
        manifest = phase4.load_json(
            phase4.ROOT / "examples" / "phase4-generated-manifest.example.json"
        )
        schema = phase4.load_json(
            phase4.ROOT / "schemas" / "phase4-generated-manifest.schema.json"
        )
        assert isinstance(manifest, dict)
        assert isinstance(schema, dict)
        return manifest, schema

    def load_g2_schema(self) -> dict[str, object]:
        schema = phase4.load_json(
            phase4.ROOT / "schemas" / "g2-completion-evidence.schema.json"
        )
        assert isinstance(schema, dict)
        return schema

    @staticmethod
    def digest(label: str) -> str:
        return hashlib.sha256(label.encode("utf-8")).hexdigest()

    @staticmethod
    def commit(label: str) -> str:
        return hashlib.sha1(label.encode("utf-8")).hexdigest()

    def make_nonplaceholder_manifest(self) -> dict[str, object]:
        manifest, _ = self.load_manifest_and_schema()

        def replace(value: object, location: str = "root") -> object:
            if isinstance(value, dict):
                return {
                    key: replace(child, f"{location}.{key}")
                    for key, child in value.items()
                }
            if isinstance(value, list):
                return [replace(child, f"{location}.{index}") for index, child in enumerate(value)]
            if isinstance(value, str) and len(value) == 64 and all(
                character in "0123456789abcdef" for character in value
            ):
                return self.digest(location)
            if isinstance(value, str) and len(value) == 40 and all(
                character in "0123456789abcdef" for character in value
            ):
                return self.commit(location)
            return value

        converted = replace(manifest)
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

        analysis_source = pins["minimal_runtime_source_sha256"]
        analysis["source_inventory_sha256"] = analysis_source
        sanitizers = analysis["sanitizers"]
        assert isinstance(sanitizers, list)
        for result in sanitizers:
            assert isinstance(result, dict)
            result["source_inventory_sha256"] = analysis_source

        generated_source = self.digest("generated-source-inventory")
        for result in compilers:
            assert isinstance(result, dict)
            result["source_inventory_sha256"] = generated_source
        reproducibility["source_file_inventory_sha256"] = generated_source
        reproducibility["generated_inventory_sha256"] = symbols["inventory_sha256"]
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
        config_diff["base_config_sha256"] = pins["config_sha256"]
        config_diff["predeclared_expectation_sha256"] = hashlib.sha256(
            phase4._canonical_bytes(config_diff["expected_category_counts"])
        ).hexdigest()
        return converted

    def make_g2_document(self, manifest: dict[str, object]) -> dict[str, object]:
        pins = manifest["pins"]
        assert isinstance(pins, dict)
        requirement_ids = (
            "cpu-sections",
            "overlay-lifecycle",
            "rsp-programs",
            "graphics-tasks",
            "audio-tasks",
            "save-round-trip",
            "runtime-traps",
            "dependency-legal-selection",
        )
        requirements = {
            identifier: {
                "passed": True,
                "evidence_record_count": 1,
                "executable_evidence_count": 1,
                "unresolved_count": 0,
                "result_sha256": self.digest(f"g2-{identifier}"),
            }
            for identifier in requirement_ids
        }
        return {
            "$schema": "../schemas/g2-completion-evidence.schema.json",
            "schema_version": 2,
            "kind": "jfg-g2-completion-evidence",
            "privacy": "public-safe-aggregate-only",
            "record_class": "maintainer-reviewed-public-aggregate",
            "pins": {
                "jfg_decomp_commit": pins["jfg_decomp_commit"],
                "n64recomp_commit": pins["n64recomp_commit"],
                "supported_input_id": pins["supported_input_id"],
                "dependency_lock_sha256": pins["dependency_lock_sha256"],
                "architecture_decision_sha256": hashlib.sha256(
                    phase4.ARCHITECTURE_DECISION.read_bytes()
                ).hexdigest(),
            },
            "requirements": requirements,
            "evidence_set_sha256": hashlib.sha256(
                phase4._canonical_bytes(requirements)
            ).hexdigest(),
            "gate": {
                "id": "G2",
                "decision": "go",
                "broad_phase4_authorized": True,
                "all_required_checks_passed": True,
            },
        }

    def make_g2_private_bundle(
        self,
        root: Path,
        manifest: dict[str, object],
        g2: dict[str, object],
    ) -> tuple[Path, Path]:
        decision = root / "accepted-decision.md"
        decision.write_text(
            "# Test decision\n\n- Status: Accepted\n",
            encoding="utf-8",
            newline="\n",
        )
        decision_digest = hashlib.sha256(decision.read_bytes()).hexdigest()
        lock = json.loads(phase4.ROOT.joinpath("dependencies.lock.json").read_text(encoding="utf-8"))
        repositories = {item["id"]: item for item in lock["repositories"]}
        manifest_pins = manifest["pins"]
        g2_pins = g2["pins"]
        assert isinstance(manifest_pins, dict)
        assert isinstance(g2_pins, dict)
        shared_pins = {
            "jfg_decomp_commit": repositories["jfg-decomp"]["commit"],
            "n64recomp_commit": repositories["n64recomp"]["commit"],
            "dependency_lock_sha256": hashlib.sha256(
                phase4.ROOT.joinpath("dependencies.lock.json").read_bytes()
            ).hexdigest(),
        }
        manifest_pins.update(shared_pins)
        g2_pins.update(shared_pins)
        g2_pins["architecture_decision_sha256"] = decision_digest
        private_g2_pins = copy.deepcopy(g2_pins)
        private_g2_pins["input_rom_sha256"] = self.digest("private-g2-input")

        harness = root / "test-only-unpinned-harness.py"
        harness.write_text("raise SystemExit(1)\n", encoding="utf-8", newline="\n")
        harness_digest = hashlib.sha256(harness.read_bytes()).hexdigest()
        pins_digest = hashlib.sha256(
            g2_private._canonical_bytes(private_g2_pins)
        ).hexdigest()
        private_requirements: dict[str, object] = {}
        public_requirements = g2["requirements"]
        assert isinstance(public_requirements, dict)
        for requirement_index, requirement_id in enumerate(g2_private.REQUIREMENT_IDS):
            classes = ["private-native-execution"]
            if requirement_id == "cpu-sections":
                classes = ["private-g3-compiler-product-binding"] * 3
            elif requirement_id in g2_private.NATIVE_AND_ORACLE:
                classes = ["private-native-execution", "private-oracle-execution"]
            elif requirement_id == "dependency-legal-selection":
                classes = ["human-approved-decision"]
            case_id = f"case-p{requirement_index:02d}"
            subject_payload = f"subject {requirement_id}\n".encode("utf-8")
            subject_digest = (
                decision_digest
                if requirement_id == "dependency-legal-selection"
                else hashlib.sha256(subject_payload).hexdigest()
            )
            source_digest = (
                private_g2_pins["dependency_lock_sha256"]
                if requirement_id == "dependency-legal-selection"
                else private_g2_pins["input_rom_sha256"]
            )
            executions: list[dict[str, object]] = []
            for execution_index, evidence_class in enumerate(classes):
                stem = f"p{requirement_index:02d}e{execution_index:02d}"
                configuration = root / f"{stem}-configuration.json"
                input_file = root / f"{stem}-input.bin"
                output = root / f"{stem}-output.bin"
                result = root / f"{stem}-result.json"
                configuration.write_text(
                    json.dumps({"case_id": case_id}, sort_keys=True),
                    encoding="utf-8",
                    newline="\n",
                )
                input_file.write_bytes(subject_payload)
                artifacts: list[dict[str, str]] = [
                    {
                        "path": configuration.name,
                        "role": "configuration",
                        "sha256": hashlib.sha256(configuration.read_bytes()).hexdigest(),
                    },
                ]
                if evidence_class == "human-approved-decision":
                    decision_copy = root / f"{stem}-decision.md"
                    decision_copy.write_bytes(decision.read_bytes())
                    artifacts.append(
                        {
                            "path": decision_copy.name,
                            "role": "decision",
                            "sha256": decision_digest,
                        }
                    )
                else:
                    artifacts.append(
                        {
                            "path": input_file.name,
                            "role": "input",
                            "sha256": hashlib.sha256(input_file.read_bytes()).hexdigest(),
                        }
                    )
                    output.write_bytes(f"output {stem}\n".encode("utf-8"))
                    artifacts.append(
                        {
                            "path": output.name,
                            "role": "output",
                            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                        }
                    )
                inputs = [
                    artifact
                    for artifact in artifacts
                    if artifact["role"] in {"configuration", "input", "decision"}
                ]
                outputs = [
                    artifact
                    for artifact in artifacts
                    if artifact["role"] in {"output", "log"}
                ]
                environment = {
                    "environment_id": f"env-p{requirement_index:02d}-e{execution_index:02d}",
                    "platform_id": "test-platform",
                    "architecture_id": "test-architecture",
                    "toolchain_sha256": self.digest(f"toolchain-{stem}"),
                }
                execution: dict[str, object] = {
                    "id": f"exec-p{requirement_index:02d}-e{execution_index:02d}",
                    "evidence_class": evidence_class,
                    "harness_id": "test-unpinned-harness",
                    "harness_sha256": harness_digest,
                    "case_id": case_id,
                    "subject_sha256": subject_digest,
                    "source_input_sha256": source_digest,
                    "pins_sha256": pins_digest,
                    "environment": environment,
                    "environment_sha256": hashlib.sha256(
                        g2_private._canonical_bytes(environment)
                    ).hexdigest(),
                    "input_set_sha256": hashlib.sha256(
                        g2_private._canonical_bytes(inputs)
                    ).hexdigest(),
                    "output_set_sha256": hashlib.sha256(
                        g2_private._canonical_bytes(outputs)
                    ).hexdigest(),
                    "artifact_set_sha256": "0" * 64,
                    "result_sha256": "0" * 64,
                    "observed_exit_code": 0,
                    "passed": True,
                    "artifacts": artifacts,
                }
                result.write_text(
                    json.dumps(
                        g2_private._result_expectation(execution, requirement_id),
                        sort_keys=True,
                    ),
                    encoding="utf-8",
                    newline="\n",
                )
                result_digest = hashlib.sha256(result.read_bytes()).hexdigest()
                artifacts.append(
                    {"path": result.name, "role": "result", "sha256": result_digest}
                )
                execution["result_sha256"] = result_digest
                execution["artifact_set_sha256"] = hashlib.sha256(
                    g2_private._canonical_bytes(artifacts)
                ).hexdigest()
                executions.append(execution)
            executable_count = sum(
                1
                for execution in executions
                if execution["evidence_class"] in g2_private.EXECUTABLE_CLASSES
            )
            private_requirement = {
                "evidence_record_count": len(executions),
                "executable_evidence_count": executable_count,
                "executions": executions,
                "unresolved": [],
            }
            private_requirements[requirement_id] = private_requirement
            public_requirement = public_requirements[requirement_id]
            assert isinstance(public_requirement, dict)
            public_requirement["evidence_record_count"] = len(executions)
            public_requirement["executable_evidence_count"] = executable_count
            public_requirement["unresolved_count"] = 0
            public_requirement["result_sha256"] = hashlib.sha256(
                g2_private._canonical_bytes(private_requirement)
            ).hexdigest()
        g2["evidence_set_sha256"] = hashlib.sha256(
            phase4._canonical_bytes(public_requirements)
        ).hexdigest()
        private_document = {
            "$schema": "../../../schemas/g2-private-evidence.schema.json",
            "schema_version": 2,
            "kind": "jfg-g2-private-executable-evidence",
            "pins": private_g2_pins,
            "requirements": private_requirements,
            "evidence_set_sha256": hashlib.sha256(
                g2_private._canonical_bytes(private_requirements)
            ).hexdigest(),
        }
        evidence = root / "g2-private.json"
        evidence.write_text(
            json.dumps(private_document, sort_keys=True),
            encoding="utf-8",
            newline="\n",
        )
        return evidence, decision

    def make_unsigned_completion(
        self, manifest: dict[str, object], g2_document: dict[str, object]
    ) -> dict[str, object]:
        completion = copy.deepcopy(manifest)
        completion["record_class"] = "maintainer-attested-public-aggregate"
        completion["attestation"] = {
            "evidence_class": "private-regenerable-aggregate",
            "body_policy": "local-only-not-exported",
            "private_evidence_sha256": self.digest("private-evidence-body"),
            "authentication": {
                "algorithm": "openssh-ed25519",
                "key_id": phase4.EXPECTED_KEY_ID,
                "principal": phase4.EXPECTED_SIGNER_PRINCIPAL,
                "namespace": phase4.EXPECTED_SIGNATURE_NAMESPACE,
                "payload_sha256": "0" * 64,
                "signature_hex_chunks": ["00"],
            },
        }
        completion["gate"] = {
            "id": "G3-M1",
            "scope": "whole-program",
            "claim": "phase4-complete",
            "predecessor_g2_complete": True,
            "predecessor_g2_evidence_sha256": hashlib.sha256(
                phase4._canonical_bytes(g2_document)
            ).hexdigest(),
            "g3_complete": True,
            "all_required_checks_passed": True,
        }
        return completion

    @contextmanager
    def signing_identity(self):
        executable = shutil.which("ssh-keygen")
        if executable is None:
            self.fail("OpenSSH ssh-keygen is a required Phase 4 validation dependency")
        assert executable is not None
        tools_root = phase4.ROOT / "tools"
        tools_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="phase4-test-key-", dir=tools_root) as temp:
            root = Path(temp)
            private_key = root / "completion-key"
            result = subprocess.run(
                [
                    executable,
                    "-q",
                    "-t",
                    "ed25519",
                    "-f",
                    str(private_key),
                    "-N",
                    "",
                    "-C",
                    phase4.EXPECTED_KEY_ID,
                ],
                capture_output=True,
                check=False,
                timeout=phase4.SSH_KEYGEN_TIMEOUT_SECONDS,
            )
            self.assertEqual(result.returncode, 0)
            public_key = private_key.with_suffix(".pub")
            policy = root / "phase4-completion-signing.json"
            policy.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "kind": "jfg-phase4-completion-signing-policy",
                        "algorithm": "openssh-ed25519",
                        "key_id": phase4.EXPECTED_KEY_ID,
                        "principal": phase4.EXPECTED_SIGNER_PRINCIPAL,
                        "namespace": phase4.EXPECTED_SIGNATURE_NAMESPACE,
                        "public_key_file": public_key.name,
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(phase4, "SIGNING_POLICY", policy):
                yield private_key

    def trusted_completion(self) -> tuple[dict[str, object], dict[str, object]]:
        manifest = self.make_nonplaceholder_manifest()
        g2 = self.make_g2_document(manifest)
        unsigned = self.make_unsigned_completion(manifest, g2)
        with self.signing_identity() as private_key:
            signed = phase4.sign_completion_manifest(unsigned, private_key)
            assert isinstance(signed, dict)
            # The patched signing policy ends with the context manager, so callers
            # use their own signing_identity context when verifying.
            return signed, g2

    def test_synthetic_example_is_unsigned_nonclaiming_and_valid(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        self.assertEqual(phase4.validate_manifest_document(manifest, schema), [])
        self.assertEqual(manifest["attestation"]["authentication"], {"algorithm": "none"})  # type: ignore[index]
        self.assertEqual(
            manifest["gate"],  # type: ignore[index]
            {
                "id": "G3-M1",
                "scope": "whole-program",
                "claim": "not-evidence",
                "predecessor_g2_complete": False,
                "g3_complete": False,
                "all_required_checks_passed": False,
            },
        )

    def test_shared_public_core_validator_rejects_nested_and_semantic_mutations(self) -> None:
        manifest = self.make_nonplaceholder_manifest()
        core = {
            field: copy.deepcopy(manifest[field])
            for field in phase4.G3_PRODUCT_CORE_FIELDS
        }
        self.assertEqual(phase4.validate_phase4_public_core(core), [])

        empty_nested = {
            field: {} for field in phase4.G3_PRODUCT_CORE_FIELDS
        }
        mutations = {
            "empty top level": {},
            "empty nested records": empty_nested,
            "missing nested field": copy.deepcopy(core),
            "wrong nested type": copy.deepcopy(core),
            "count reconciliation": copy.deepcopy(core),
            "compiler matrix": copy.deepcopy(core),
            "overlay coverage": copy.deepcopy(core),
            "call closure": copy.deepcopy(core),
            "missing direct candidate denominator": copy.deepcopy(core),
            "missing direct instruction partition": copy.deepcopy(core),
            "missing direct transfer-role partition": copy.deepcopy(core),
            "collapsed direct JAL-only partition": copy.deepcopy(core),
            "unexpected direct field": copy.deepcopy(core),
            "missing indirect partition": copy.deepcopy(core),
            "collapsed indirect decision subset": copy.deepcopy(core),
            "incomplete executable symbol denominator": copy.deepcopy(core),
            "missing covered alias ledger": copy.deepcopy(core),
            "wrong manual recovery denominator": copy.deepcopy(core),
            "missing overlay section denominator": copy.deepcopy(core),
            "missing overlay slot digest": copy.deepcopy(core),
        }
        mutations["missing nested field"]["symbols"].pop("expected_count")  # type: ignore[index,union-attr]
        mutations["wrong nested type"]["symbols"]["expected_count"] = "2905"  # type: ignore[index]
        mutations["count reconciliation"]["symbols"]["generated_count"] += 1  # type: ignore[index]
        mutations["compiler matrix"]["compilers"][1]["family"] = "clang"  # type: ignore[index]
        mutations["overlay coverage"]["overlays"]["listed_slot_count"] += 1  # type: ignore[index]
        mutations["call closure"]["calls"]["direct"]["resolved_count"] += 1  # type: ignore[index]
        mutations["missing direct candidate denominator"]["calls"]["direct"].pop(  # type: ignore[index]
            "candidate_count"
        )
        mutations["missing direct instruction partition"]["calls"]["direct"].pop(  # type: ignore[index]
            "instruction_class_counts"
        )
        mutations["missing direct transfer-role partition"]["calls"]["direct"].pop(  # type: ignore[index]
            "transfer_role_counts"
        )
        mutations["collapsed direct JAL-only partition"]["calls"]["direct"][  # type: ignore[index]
            "instruction_class_counts"
        ] = {"jal": phase4.EXPECTED_STATIC_JAL_CALL_CANDIDATE_COUNT, "bgezal": 0}
        mutations["unexpected direct field"]["calls"]["direct"][  # type: ignore[index]
            "self_reported_count"
        ] = phase4.EXPECTED_STATIC_DIRECT_CALL_CANDIDATE_COUNT
        mutations["missing indirect partition"]["calls"]["indirect_ranges"].pop(  # type: ignore[index]
            "native_return_count"
        )
        collapsed_indirect = mutations["collapsed indirect decision subset"]["calls"][  # type: ignore[index]
            "indirect_ranges"
        ]
        collapsed_indirect["expected_count"] = phase4.EXPECTED_DECISION_RANGE_TRANSFER_COUNT
        collapsed_indirect["resolved_count"] = phase4.EXPECTED_DECISION_RANGE_TRANSFER_COUNT
        collapsed_indirect["native_return_count"] = 0
        mutations["incomplete executable symbol denominator"]["symbols"].update(  # type: ignore[index]
            {
                "expected_count": phase4.EXPECTED_GENERATED_BODY_COUNT,
                "excluded_count": 0,
                "exclusion_category_counts": {
                    "covered-alias": 0,
                    "validated-non-code": 0,
                    "runtime-abi": 0,
                },
            }
        )
        mutations["missing covered alias ledger"]["symbols"].pop(  # type: ignore[index]
            "covered_alias_ledger_sha256"
        )
        mutations["wrong manual recovery denominator"]["symbols"][  # type: ignore[index]
            "manual_size_recovery_count"
        ] = 5
        mutations["missing overlay section denominator"]["overlays"].pop(  # type: ignore[index]
            "executable_section_count"
        )
        mutations["missing overlay slot digest"]["overlays"].pop(  # type: ignore[index]
            "slot_inventory_sha256"
        )

        for label, mutated in mutations.items():
            with self.subTest(mutation=label):
                self.assertTrue(phase4.validate_phase4_public_core(mutated))

    def test_public_validator_rejects_every_completion_claim(self) -> None:
        manifest = self.make_nonplaceholder_manifest()
        _, schema = self.load_manifest_and_schema()
        g2 = self.make_g2_document(manifest)
        completion = self.make_unsigned_completion(manifest, g2)
        errors = phase4.validate_manifest_document(completion, schema)
        self.assertIn(
            "completion requires trusted signature and G2 evidence validation", errors
        )

    def test_trusted_completion_requires_pinned_signature_and_actual_g2_body(self) -> None:
        manifest = self.make_nonplaceholder_manifest()
        _, schema = self.load_manifest_and_schema()
        g2_schema = self.load_g2_schema()
        g2 = self.make_g2_document(manifest)
        with tempfile.TemporaryDirectory(
            prefix="phase4-private-", dir=phase4.ROOT / "tools"
        ) as temp:
            g2_private_path, decision = self.make_g2_private_bundle(
                Path(temp), manifest, g2
            )
            completion = self.make_unsigned_completion(manifest, g2)
            with mock.patch.object(phase4, "ARCHITECTURE_DECISION", decision), mock.patch.object(
                g2_private, "ARCHITECTURE_DECISION", decision
            ), self.signing_identity() as private_key:
                signed = phase4.sign_completion_manifest(completion, private_key)
                body = Path(temp) / "evidence.json"
                body.write_bytes(b"private-evidence-body")
                errors = phase4.validate_trusted_completion(
                    signed,
                    schema,
                    g2,
                    g2_schema,
                    private_evidence_path=body,
                    g2_private_evidence_path=g2_private_path,
                )
                self.assertIn(
                    "completion: private evidence body could not be read", errors
                )
                # A synthetic G2 execution is rejected either because no
                # production pin exists for it or because it does not use
                # the pinned production harness identity.
                self.assertTrue(
                    "private evidence: pinned harness is unavailable" in errors
                    or "private evidence: execution does not use the pinned harness"
                    in errors,
                    errors,
                )
                missing_private_g2 = phase4.validate_trusted_completion(
                    signed,
                    schema,
                    g2,
                    g2_schema,
                    private_evidence_path=body,
                )
                self.assertIn(
                    "completion: local G2 executable evidence body is required",
                    missing_private_g2,
                )
                errors = phase4.validate_trusted_completion(
                    signed, schema, None, g2_schema
                )
                self.assertIn("completion: G2 evidence body is required", errors)
                self.assertIn(
                    "completion: local private evidence body is required", errors
                )

    def test_trusted_completion_rejects_caller_substituted_schemas(self) -> None:
        manifest = self.make_nonplaceholder_manifest()
        g2 = self.make_g2_document(manifest)
        g2["gate"] = {
            "id": "G2",
            "decision": "no-go",
            "broad_phase4_authorized": False,
            "all_required_checks_passed": False,
        }
        completion = self.make_unsigned_completion(manifest, g2)
        completion["gate"] = {
            "id": "G3-M1",
            "scope": "whole-program",
            "claim": "not-evidence",
            "predecessor_g2_complete": False,
            "predecessor_g2_evidence_sha256": hashlib.sha256(
                phase4._canonical_bytes(g2)
            ).hexdigest(),
            "g3_complete": False,
            "all_required_checks_passed": False,
        }

        with self.signing_identity() as private_key:
            signed = phase4.sign_completion_manifest(completion, private_key)
            with tempfile.TemporaryDirectory(
                prefix="phase4-private-", dir=phase4.ROOT / "tools"
            ) as temp:
                body = Path(temp) / "evidence.json"
                body.write_bytes(b"private-evidence-body")
                errors = phase4.validate_trusted_completion(
                    signed,
                    {},
                    g2,
                    {},
                    private_evidence_path=body,
                )

        self.assertIn("completion: Phase 4 schema is not the pinned contract", errors)
        self.assertIn("completion: G2 schema is not the pinned contract", errors)
        self.assertIn("schema: contract violation", errors)

    def test_caller_selected_signer_cannot_authenticate_completion(self) -> None:
        manifest = self.make_nonplaceholder_manifest()
        _, schema = self.load_manifest_and_schema()
        g2_schema = self.load_g2_schema()
        g2 = self.make_g2_document(manifest)
        completion = self.make_unsigned_completion(manifest, g2)
        with self.signing_identity() as untrusted_private_key:
            signed = phase4.sign_completion_manifest(completion, untrusted_private_key)
        with self.signing_identity():
            errors = phase4.validate_trusted_completion(
                signed, schema, g2, g2_schema
            )
        self.assertIn("attestation: completion signature is invalid", errors)

    def test_wrong_g2_digest_no_go_body_and_pin_mismatch_are_rejected(self) -> None:
        manifest = self.make_nonplaceholder_manifest()
        _, schema = self.load_manifest_and_schema()
        g2_schema = self.load_g2_schema()
        g2 = self.make_g2_document(manifest)
        completion = self.make_unsigned_completion(manifest, g2)
        with self.signing_identity() as private_key:
            signed = phase4.sign_completion_manifest(completion, private_key)
            wrong_digest = copy.deepcopy(g2)
            wrong_digest["evidence_set_sha256"] = self.digest("wrong-evidence-set")
            errors = phase4.validate_trusted_completion(
                signed, schema, wrong_digest, g2_schema
            )
            self.assertIn("G2 evidence: requirement-set digest is unbound", errors)
            self.assertIn(
                "completion: G2 evidence digest does not match the supplied body", errors
            )

            wrong_architecture = copy.deepcopy(g2)
            wrong_architecture["pins"]["architecture_decision_sha256"] = self.digest(  # type: ignore[index]
                "different-architecture-decision"
            )
            errors = phase4.validate_trusted_completion(
                signed, schema, wrong_architecture, g2_schema
            )
            self.assertIn(
                "G2 evidence: architecture decision digest is unbound", errors
            )

            no_go = copy.deepcopy(g2)
            no_go["gate"]["decision"] = "no-go"  # type: ignore[index]
            errors = phase4.validate_trusted_completion(
                signed, schema, no_go, g2_schema
            )
            self.assertIn("schema: contract violation", errors)

            mismatched = copy.deepcopy(g2)
            mismatched["pins"]["n64recomp_commit"] = "1" * 40  # type: ignore[index]
            mismatched["evidence_set_sha256"] = hashlib.sha256(
                phase4._canonical_bytes(mismatched["requirements"])
            ).hexdigest()
            errors = phase4.validate_trusted_completion(
                signed, schema, mismatched, g2_schema
            )
            self.assertIn("completion: G2 and Phase 4 pins differ", errors)

    def test_signed_completion_rejects_placeholder_evidence_identities(self) -> None:
        manifest = self.make_nonplaceholder_manifest()
        _, schema = self.load_manifest_and_schema()
        g2_schema = self.load_g2_schema()
        g2 = self.make_g2_document(manifest)
        g2["pins"]["architecture_decision_sha256"] = "1" * 64  # type: ignore[index]
        g2["requirements"]["graphics-tasks"]["result_sha256"] = "2" * 64  # type: ignore[index]
        g2["evidence_set_sha256"] = hashlib.sha256(
            phase4._canonical_bytes(g2["requirements"])
        ).hexdigest()
        completion = self.make_unsigned_completion(manifest, g2)

        with self.signing_identity() as private_key:
            signed = phase4.sign_completion_manifest(completion, private_key)
            errors = phase4.validate_trusted_completion(
                signed, schema, g2, g2_schema
            )

        self.assertIn(
            "completion: placeholder cryptographic identity is forbidden", errors
        )

    def test_private_evidence_body_is_required_and_recomputed(self) -> None:
        manifest = self.make_nonplaceholder_manifest()
        _, schema = self.load_manifest_and_schema()
        g2_schema = self.load_g2_schema()
        g2 = self.make_g2_document(manifest)
        tools_root = phase4.ROOT / "tools"
        with tempfile.TemporaryDirectory(prefix="phase4-private-", dir=tools_root) as temp:
            g2_private_path, decision = self.make_g2_private_bundle(
                Path(temp), manifest, g2
            )
            completion = self.make_unsigned_completion(manifest, g2)
            with mock.patch.object(phase4, "ARCHITECTURE_DECISION", decision), mock.patch.object(
                g2_private, "ARCHITECTURE_DECISION", decision
            ), self.signing_identity() as private_key:
                signed = phase4.sign_completion_manifest(completion, private_key)
                errors = phase4.validate_trusted_completion(
                    signed,
                    schema,
                    g2,
                    g2_schema,
                    g2_private_evidence_path=g2_private_path,
                )
                self.assertIn(
                    "completion: local private evidence body is required", errors
                )
                body = Path(temp) / "evidence.json"
                body.write_bytes(b"private-evidence-body")
                errors = phase4.validate_trusted_completion(
                    signed,
                    schema,
                    g2,
                    g2_schema,
                    private_evidence_path=body,
                    g2_private_evidence_path=g2_private_path,
                )
                self.assertIn(
                    "completion: private evidence body could not be read", errors
                )
                # A synthetic G2 execution is rejected either because no
                # production pin exists for it or because it does not use
                # the pinned production harness identity.
                self.assertTrue(
                    "private evidence: pinned harness is unavailable" in errors
                    or "private evidence: execution does not use the pinned harness"
                    in errors,
                    errors,
                )
                body.write_bytes(b"different body")
                errors = phase4.validate_trusted_completion(
                    signed,
                    schema,
                    g2,
                    g2_schema,
                    private_evidence_path=body,
                    g2_private_evidence_path=g2_private_path,
                )
                self.assertIn("completion: private evidence body could not be read", errors)

    def test_symbol_and_library_denominators_are_cross_reconciled(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        probes = (
            ("baseline", "unmodified_body_member_count", 1, "baseline"),
            ("aliases", "expected_count", 0, "aliases"),
            (
                "minimal_runtime",
                "target_runtime_abi_exclusion_count",
                1,
                "target runtime",
            ),
        )
        for section, field, value, marker in probes:
            with self.subTest(field=field):
                invalid = copy.deepcopy(manifest)
                invalid["libraries"][section][field] = value  # type: ignore[index]
                errors = phase4.validate_manifest_document(invalid, schema)
                self.assertTrue(any(marker in error for error in errors), errors)

    def test_every_generated_body_requires_a_callable_alias(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        invalid["symbols"]["replaceable_function_count"] = (  # type: ignore[index]
            invalid["symbols"]["generated_count"] - 1  # type: ignore[index]
        )
        invalid["libraries"]["baseline"][  # type: ignore[index]
            "callable_wrapper_member_count"
        ] -= 1
        invalid["libraries"]["baseline"]["member_count"] -= 1  # type: ignore[index]
        invalid["libraries"]["aliases"]["expected_count"] -= 1  # type: ignore[index]
        invalid["libraries"]["aliases"]["emitted_count"] -= 1  # type: ignore[index]
        errors = phase4.validate_manifest_document(invalid, schema)
        self.assertIn("schema: contract violation", errors)

    def test_body_wrappers_thunks_and_anchor_have_distinct_denominators(self) -> None:
        manifest, schema = self.load_manifest_and_schema()

        invalid = copy.deepcopy(manifest)
        baseline = invalid["libraries"]["baseline"]  # type: ignore[index]
        baseline["callable_wrapper_member_count"] = 9
        baseline["support_member_count"] = 5
        errors = phase4.validate_manifest_document(invalid, schema)
        self.assertIn("libraries: callable wrappers do not cover replaceable bodies", errors)
        self.assertIn("libraries: baseline support members do not reconcile", errors)

        invalid = copy.deepcopy(manifest)
        baseline = invalid["libraries"]["baseline"]  # type: ignore[index]
        baseline["alternate_entry_thunk_member_count"] = 0
        baseline["other_support_member_count"] = 1
        errors = phase4.validate_manifest_document(invalid, schema)
        self.assertIn("schema: contract violation", errors)

        invalid = copy.deepcopy(manifest)
        patch = invalid["libraries"]["patch"]  # type: ignore[index]
        patch["approved_replacement_member_count"] = 1
        patch["anchor_member_count"] = 0
        errors = phase4.validate_manifest_document(invalid, schema)
        self.assertIn("schema: contract violation", errors)

        invalid = copy.deepcopy(manifest)
        invalid["symbols"]["generated_count"] = 11  # type: ignore[index]
        invalid["symbols"]["expected_count"] = 15  # type: ignore[index]
        baseline = invalid["libraries"]["baseline"]  # type: ignore[index]
        baseline["unmodified_body_member_count"] = 11
        baseline["support_member_count"] = 3
        errors = phase4.validate_manifest_document(invalid, schema)
        self.assertIn("schema: contract violation", errors)

    def test_host_runtime_exports_and_section_state_are_closed(self) -> None:
        manifest, schema = self.load_manifest_and_schema()

        invalid = copy.deepcopy(manifest)
        runtime = invalid["libraries"]["minimal_runtime"]  # type: ignore[index]
        runtime["resolved_host_function_export_count"] = 14
        runtime["resolved_host_data_export_count"] = 2
        errors = phase4.validate_manifest_document(invalid, schema)
        self.assertIn(
            "libraries: host runtime function exports do not reconcile", errors
        )
        self.assertIn("libraries: host runtime data exports do not reconcile", errors)

        invalid = copy.deepcopy(manifest)
        runtime = invalid["libraries"]["minimal_runtime"]  # type: ignore[index]
        runtime["initialized_section_address_count"] = 1
        errors = phase4.validate_manifest_document(invalid, schema)
        self.assertIn("libraries: section-address initialization is incomplete", errors)

        invalid = copy.deepcopy(manifest)
        runtime = invalid["libraries"]["minimal_runtime"]  # type: ignore[index]
        runtime["section_address_count"] = 4097
        runtime["initialized_section_address_count"] = 4097
        errors = phase4.validate_manifest_document(invalid, schema)
        self.assertIn("libraries: section-address capacity is insufficient", errors)

        invalid = copy.deepcopy(manifest)
        invalid["libraries"]["baseline"]["section_address_member_count"] = 2  # type: ignore[index]
        errors = phase4.validate_manifest_document(invalid, schema)
        self.assertIn("libraries: section-address support members are unbound", errors)

    def test_relocation_and_overlay_lifecycle_closure_is_enforced(self) -> None:
        manifest, schema = self.load_manifest_and_schema()

        invalid = copy.deepcopy(manifest)
        invalid["relocations"]["instructions"]["atomic_hi_lo_pair_count"] = 0  # type: ignore[index]
        errors = phase4.validate_manifest_document(invalid, schema)
        self.assertIn("instruction relocations: HI/LO pairs are not atomic", errors)

        invalid = copy.deepcopy(manifest)
        invalid["relocations"]["data_r32"]["approved_fail_closed_count"] = 1  # type: ignore[index]
        invalid["relocations"]["data_r32"]["resolved_count"] -= 1  # type: ignore[index]
        errors = phase4.validate_manifest_document(invalid, schema)
        self.assertIn(
            "data relocations: every R32 record must resolve through the table", errors
        )

        invalid = copy.deepcopy(manifest)
        invalid["overlays"]["lifecycle_table_slot_count"] -= 1  # type: ignore[index]
        self.assertIn(
            "schema: contract violation",
            phase4.validate_manifest_document(invalid, schema),
        )

        invalid = copy.deepcopy(manifest)
        invalid["relocations"]["instructions"]["hi_lo_pair_count"] = 13  # type: ignore[index]
        invalid["relocations"]["instructions"]["atomic_hi_lo_pair_count"] = 13  # type: ignore[index]
        self.assertIn(
            "instruction relocations: HI/LO pair denominator exceeds relocation sites",
            phase4.validate_manifest_document(invalid, schema),
        )

    def test_config_diff_declares_and_matches_categories(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        invalid["config_diff"]["predeclared_expectation_sha256"] = "9" * 64  # type: ignore[index]
        self.assertIn(
            "config diff: predeclared expectation digest is unbound",
            phase4.validate_manifest_document(invalid, schema),
        )

        invalid = copy.deepcopy(manifest)
        invalid["config_diff"]["expected_change_count"] = 1  # type: ignore[index]
        invalid["config_diff"]["observed_category_counts"]["lookup-change"] = 0  # type: ignore[index]
        errors = phase4.validate_manifest_document(invalid, schema)
        self.assertIn(
            "config diff: observed categories differ from the declaration", errors
        )
        self.assertIn("config diff: expected categories do not reconcile", errors)
        self.assertIn("config diff: observed categories do not reconcile", errors)

        invalid = copy.deepcopy(manifest)
        invalid["config_diff"]["expected_change_count"] = 0  # type: ignore[index]
        invalid["config_diff"]["observed_change_count"] = 0  # type: ignore[index]
        self.assertIn(
            "schema: contract violation",
            phase4.validate_manifest_document(invalid, schema),
        )

    def test_baseline_and_patch_reproducibility_are_both_bound(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        for field in ("baseline", "patch"):
            with self.subTest(field=field):
                invalid = copy.deepcopy(manifest)
                invalid["libraries"][field]["member_inventory_sha256"] = "9" * 64  # type: ignore[index]
                errors = phase4.validate_manifest_document(invalid, schema)
                self.assertTrue(
                    any(f"{field} member inventory" in error for error in errors),
                    errors,
                )

    def test_clang_analysis_and_explicit_sanitizers_are_required(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        invalid["analysis"]["clang_static_analysis"]["tool_id"] = "msvc-analyze"  # type: ignore[index]
        self.assertIn(
            "schema: contract violation",
            phase4.validate_manifest_document(invalid, schema),
        )

        invalid = copy.deepcopy(manifest)
        invalid["analysis"]["sanitizers"][1]["sanitizer_id"] = "address"  # type: ignore[index]
        errors = phase4.validate_manifest_document(invalid, schema)
        self.assertIn(
            "analysis: address and undefined-behavior sanitizers are required", errors
        )
        self.assertIn("analysis: sanitizer results must be unique", errors)

    def test_malformed_values_fail_without_exception_or_private_echo(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        invalid["compilers"][0]["compiler_id"] = ["clang-18"]  # type: ignore[index]
        self.assertEqual(
            phase4.validate_manifest_document(invalid, schema),
            ["schema: contract violation"],
        )

        private_shaped_key = "Q:" + "\\" + "Example" + "\\" + "private"
        private_shaped_value = "/" + "home" + "/example/private"
        invalid = copy.deepcopy(manifest)
        invalid[private_shaped_key] = private_shaped_value
        errors = phase4.validate_manifest_document(invalid, schema)
        rendered = "\n".join(errors)
        self.assertNotIn(private_shaped_key, rendered)
        self.assertNotIn(private_shaped_value, rendered)
        self.assertIn("privacy: public-safe contract violation", errors)

        completion_manifest = self.make_nonplaceholder_manifest()
        g2 = self.make_g2_document(completion_manifest)
        completion = self.make_unsigned_completion(completion_manifest, g2)
        errors = phase4.validate_trusted_completion(
            completion,
            schema,
            {"malformed": {1, 2}},
            self.load_g2_schema(),
        )
        self.assertIn("completion: G2 evidence body is not canonical JSON", errors)

    def test_compiler_matrix_and_source_inventory_are_closed(self) -> None:
        manifest, schema = self.load_manifest_and_schema()
        invalid = copy.deepcopy(manifest)
        invalid["compilers"][0]["family"] = "gcc"  # type: ignore[index]
        invalid["compilers"][0]["compiler_id"] = "gcc-14"  # type: ignore[index]
        errors = phase4.validate_manifest_document(invalid, schema)
        self.assertIn(
            "compilers: exact Clang, GCC, and MSVC results are required", errors
        )

        invalid = copy.deepcopy(manifest)
        invalid["compilers"][0]["source_inventory_sha256"] = "9" * 64  # type: ignore[index]
        errors = phase4.validate_manifest_document(invalid, schema)
        self.assertIn(
            "compilers: results do not use one generated source inventory", errors
        )
        self.assertIn("reproducibility: compiler source inventory is unbound", errors)

    def test_tracked_signing_policy_is_anonymous_and_has_no_private_key(self) -> None:
        policy = phase4.load_json(phase4.SIGNING_POLICY)
        assert isinstance(policy, dict)
        self.assertEqual(policy["key_id"], phase4.EXPECTED_KEY_ID)
        executable = phase4._ssh_keygen()
        self.assertIsNotNone(executable)
        assert executable is not None
        self.assertNotIn("ssh_keygen_sha256", policy)
        public_key = phase4.SIGNING_POLICY.parent / str(policy["public_key_file"])
        line = public_key.read_text(encoding="utf-8").strip()
        self.assertTrue(line.startswith("ssh-ed25519 "))
        self.assertTrue(line.endswith(f" {phase4.EXPECTED_KEY_ID}"))
        self.assertFalse((phase4.SIGNING_POLICY.parent / "phase4-completion-signing-key").exists())

    def test_ssh_keygen_is_required_and_signature_operations_are_bounded(self) -> None:
        executable = shutil.which("ssh-keygen")
        self.assertIsNotNone(
            executable, "OpenSSH ssh-keygen is a required Phase 4 dependency"
        )
        manifest = self.make_nonplaceholder_manifest()
        g2 = self.make_g2_document(manifest)
        completion = self.make_unsigned_completion(manifest, g2)
        with self.signing_identity() as private_key:
            signed = phase4.sign_completion_manifest(completion, private_key)
            with mock.patch.object(
                phase4.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired("ssh-keygen", 1),
            ):
                self.assertEqual(
                    phase4._verify_completion_signature(signed),
                    ["attestation: completion signature could not be verified"],
                )
                with self.assertRaisesRegex(ValueError, "completion signing failed"):
                    phase4.sign_completion_manifest(completion, private_key)

    def test_path_shadow_cannot_select_signature_tool(self) -> None:
        with tempfile.TemporaryDirectory(prefix="phase4-shadow-ssh-") as temp:
            fake = Path(temp) / ("ssh-keygen.exe" if os.name == "nt" else "ssh-keygen")
            fake.write_bytes(b"fake signer")
            with mock.patch.dict(os.environ, {"PATH": temp}):
                selected = phase4._ssh_keygen()
            self.assertIsNotNone(selected)
            assert selected is not None
            self.assertNotEqual(selected.resolve(), fake.resolve())
            staged, digest = phase4._stage_ssh_keygen(selected, Path(temp))
            self.assertEqual(
                digest, hashlib.sha256(selected.read_bytes()).hexdigest()
            )
            self.assertEqual(
                hashlib.sha256(staged.read_bytes()).hexdigest(), digest
            )

    def test_private_evidence_rejects_tracked_repository_files(self) -> None:
        manifest = self.make_nonplaceholder_manifest()
        _, schema = self.load_manifest_and_schema()
        g2_schema = self.load_g2_schema()
        g2 = self.make_g2_document(manifest)
        completion = self.make_unsigned_completion(manifest, g2)
        with self.signing_identity() as private_key:
            signed = phase4.sign_completion_manifest(completion, private_key)
            errors = phase4.validate_trusted_completion(
                signed,
                schema,
                g2,
                g2_schema,
                private_evidence_path=phase4.DEFAULT_MANIFEST,
            )
        self.assertIn(
            "completion: private evidence body must be external or ignored", errors
        )

    def test_completion_cli_requires_local_private_evidence_body(self) -> None:
        manifest = self.make_nonplaceholder_manifest()
        g2 = self.make_g2_document(manifest)
        completion = self.make_unsigned_completion(manifest, g2)
        tools_root = phase4.ROOT / "tools"
        with tempfile.TemporaryDirectory(prefix="phase4-cli-", dir=tools_root) as temp:
            temp_root = Path(temp)
            manifest_path = temp_root / "completion.json"
            g2_path = temp_root / "g2.json"
            manifest_path.write_text(json.dumps(completion), encoding="utf-8")
            g2_path.write_text(json.dumps(g2), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(phase4.ROOT / "scripts" / "validate_phase4_manifest.py"),
                    "--manifest",
                    str(manifest_path),
                    "--g2-evidence",
                    str(g2_path),
                ],
                cwd=phase4.ROOT,
                capture_output=True,
                text=True,
                check=False,
                timeout=phase4.SSH_KEYGEN_TIMEOUT_SECONDS,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("completion: local private evidence body is required", result.stderr)

    def test_cli_validates_only_the_unsigned_nonclaiming_example_by_default(self) -> None:
        script = phase4.ROOT / "scripts" / "validate_phase4_manifest.py"
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=phase4.ROOT,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.strip(),
            "Phase 4 non-claiming manifest validation passed",
        )

    def test_duplicate_json_keys_and_nonstandard_numbers_fail_closed(self) -> None:
        tools_root = phase4.ROOT / "tools"
        with tempfile.TemporaryDirectory(prefix="phase4-json-", dir=tools_root) as temp:
            duplicate = Path(temp) / "duplicate.json"
            duplicate.write_text('{"kind": 1, "kind": 2}', encoding="utf-8")
            with self.assertRaises(ValueError):
                phase4.load_json(duplicate)
            nonstandard = Path(temp) / "nonstandard.json"
            nonstandard.write_text('{"count": NaN}', encoding="utf-8")
            with self.assertRaises(ValueError):
                phase4.load_json(nonstandard)


if __name__ == "__main__":
    unittest.main()
