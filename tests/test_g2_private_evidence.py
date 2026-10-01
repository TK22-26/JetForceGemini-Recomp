from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_g2_private_evidence.py"
SPEC = importlib.util.spec_from_file_location("validate_g2_private_evidence", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
G2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(G2)


HARNESS_SOURCE = r'''import json
import pathlib
import sys

request = json.load(sys.stdin)
execution = request["execution"]
result = {
    "schema_version": 1,
    "kind": "jfg-g2-harness-transcript",
    "execution_id": execution["id"],
    "requirement_id": request["requirement_id"],
    "evidence_class": execution["evidence_class"],
    "harness_id": execution["harness_id"],
    "harness_sha256": execution["harness_sha256"],
    "case_id": execution["case_id"],
    "subject_sha256": execution["subject_sha256"],
    "source_input_sha256": execution["source_input_sha256"],
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
pathlib.Path("harness-ran.marker").write_text("validated\n", encoding="utf-8")
sys.stdout.write(json.dumps(result, sort_keys=True))
'''


class G2PrivateEvidenceTests(unittest.TestCase):
    @staticmethod
    def digest(label: str) -> str:
        return hashlib.sha256(label.encode("utf-8")).hexdigest()

    def write_harness(
        self, bundle: Path, source: str = HARNESS_SOURCE, *, timeout: float = 5.0
    ) -> G2.PinnedHarness:
        harness = bundle / "test-harness.py"
        harness.write_text(source, encoding="utf-8", newline="\n")
        digest = hashlib.sha256(harness.read_bytes()).hexdigest()
        return G2.PinnedHarness("test-g2-harness", harness, digest, timeout)

    @staticmethod
    def result_document(
        execution: dict[str, object], requirement_id: str
    ) -> dict[str, object]:
        return G2._result_expectation(execution, requirement_id)

    def write_result(
        self,
        bundle: Path,
        execution: dict[str, object],
        requirement_id: str,
    ) -> None:
        artifacts = execution["artifacts"]
        assert isinstance(artifacts, list)
        result_artifact = next(item for item in artifacts if item["role"] == "result")
        path = bundle / str(result_artifact["path"])
        path.write_text(
            json.dumps(self.result_document(execution, requirement_id), sort_keys=True),
            encoding="utf-8",
            newline="\n",
        )
        result_artifact["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        execution["result_sha256"] = result_artifact["sha256"]
        execution["artifact_set_sha256"] = hashlib.sha256(
            G2._canonical_bytes(artifacts)
        ).hexdigest()

    def refresh_document_digests(
        self, private: dict[str, object], public: dict[str, object]
    ) -> None:
        private_requirements = private["requirements"]
        public_requirements = public["requirements"]
        assert isinstance(private_requirements, dict)
        assert isinstance(public_requirements, dict)
        for requirement_id in G2.REQUIREMENT_IDS:
            requirement = private_requirements[requirement_id]
            public_requirement = public_requirements[requirement_id]
            assert isinstance(requirement, dict)
            assert isinstance(public_requirement, dict)
            executions = requirement["executions"]
            assert isinstance(executions, list)
            requirement["evidence_record_count"] = len(executions)
            requirement["executable_evidence_count"] = sum(
                1
                for execution in executions
                if execution["evidence_class"] in G2.EXECUTABLE_CLASSES
            )
            public_requirement["evidence_record_count"] = requirement[
                "evidence_record_count"
            ]
            public_requirement["executable_evidence_count"] = requirement[
                "executable_evidence_count"
            ]
            public_requirement["result_sha256"] = hashlib.sha256(
                G2._canonical_bytes(requirement)
            ).hexdigest()
        private["evidence_set_sha256"] = hashlib.sha256(
            G2._canonical_bytes(private_requirements)
        ).hexdigest()
        public["evidence_set_sha256"] = hashlib.sha256(
            G2._canonical_bytes(public_requirements)
        ).hexdigest()

    def build_documents(
        self, bundle: Path, pin: G2.PinnedHarness
    ) -> tuple[
        dict[str, object],
        dict[str, object],
        Path,
        dict[tuple[str, str], G2.PinnedHarness],
    ]:
        decision = bundle / "accepted-decision.md"
        decision.write_text(
            "# Test decision\n\n- Status: Accepted by `TK22-26`\n",
            encoding="utf-8",
            newline="\n",
        )
        decision_digest = hashlib.sha256(decision.read_bytes()).hexdigest()
        lock = json.loads(G2.DEPENDENCY_LOCK.read_text(encoding="utf-8"))
        repositories = {item["id"]: item for item in lock["repositories"]}
        pins = {
            "jfg_decomp_commit": repositories["jfg-decomp"]["commit"],
            "n64recomp_commit": repositories["n64recomp"]["commit"],
            "supported_input_id": "jfg-us-retail",
            "input_rom_sha256": self.digest("private-input"),
            "dependency_lock_sha256": hashlib.sha256(
                G2.DEPENDENCY_LOCK.read_bytes()
            ).hexdigest(),
            "architecture_decision_sha256": decision_digest,
        }
        pins_digest = hashlib.sha256(G2._canonical_bytes(pins)).hexdigest()

        private_requirements: dict[str, object] = {}
        policy: dict[tuple[str, str], G2.PinnedHarness] = {}
        for requirement_index, requirement_id in enumerate(G2.REQUIREMENT_IDS):
            classes = ["private-native-execution"]
            if requirement_id == "cpu-sections":
                classes = ["private-g3-compiler-product-binding"] * 3
            elif requirement_id in G2.NATIVE_AND_ORACLE:
                classes = ["private-native-execution", "private-oracle-execution"]
            elif requirement_id == "dependency-legal-selection":
                classes = ["human-approved-decision"]
            case_id = f"case-r{requirement_index:02d}"
            subject_payload = f"subject {requirement_id}\n".encode("utf-8")
            subject_digest = (
                decision_digest
                if requirement_id == "dependency-legal-selection"
                else hashlib.sha256(subject_payload).hexdigest()
            )
            source_digest = (
                pins["dependency_lock_sha256"]
                if requirement_id == "dependency-legal-selection"
                else pins["input_rom_sha256"]
            )
            executions: list[dict[str, object]] = []
            for execution_index, evidence_class in enumerate(classes):
                stem = f"r{requirement_index:02d}e{execution_index:02d}"
                configuration = bundle / f"{stem}-configuration.json"
                input_file = bundle / f"{stem}-input.bin"
                output = bundle / f"{stem}-output.bin"
                result = bundle / f"{stem}-result.json"
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
                    }
                ]
                if evidence_class == "human-approved-decision":
                    decision_copy = bundle / f"{stem}-decision.md"
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
                input_records = [
                    item
                    for item in artifacts
                    if item["role"] in {"configuration", "input", "decision"}
                ]
                output_records = [
                    item for item in artifacts if item["role"] in {"output", "log"}
                ]
                environment = {
                    "environment_id": f"env-r{requirement_index:02d}-e{execution_index:02d}",
                    "platform_id": "test-platform",
                    "architecture_id": "test-architecture",
                    "toolchain_sha256": self.digest(f"toolchain-{stem}"),
                }
                execution: dict[str, object] = {
                    "id": f"exec-r{requirement_index:02d}-e{execution_index:02d}",
                    "evidence_class": evidence_class,
                    "harness_id": pin.harness_id,
                    "harness_sha256": pin.script_sha256,
                    "case_id": case_id,
                    "subject_sha256": subject_digest,
                    "source_input_sha256": source_digest,
                    "pins_sha256": pins_digest,
                    "environment": environment,
                    "environment_sha256": hashlib.sha256(
                        G2._canonical_bytes(environment)
                    ).hexdigest(),
                    "input_set_sha256": hashlib.sha256(
                        G2._canonical_bytes(input_records)
                    ).hexdigest(),
                    "output_set_sha256": hashlib.sha256(
                        G2._canonical_bytes(output_records)
                    ).hexdigest(),
                    "artifact_set_sha256": "0" * 64,
                    "result_sha256": "0" * 64,
                    "observed_exit_code": 0,
                    "passed": True,
                    "artifacts": artifacts,
                }
                result.write_text(
                    json.dumps(
                        self.result_document(execution, requirement_id), sort_keys=True
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
                    G2._canonical_bytes(artifacts)
                ).hexdigest()
                # result_sha256/artifact_set_sha256 intentionally do not appear in
                # the result body, avoiding a self-referential digest.
                executions.append(execution)
                policy[(requirement_id, evidence_class)] = pin
            executable_count = sum(
                1
                for execution in executions
                if execution["evidence_class"] in G2.EXECUTABLE_CLASSES
            )
            private_requirements[requirement_id] = {
                "evidence_record_count": len(executions),
                "executable_evidence_count": executable_count,
                "executions": executions,
                "unresolved": [],
            }

        private = {
            "$schema": "../../../schemas/g2-private-evidence.schema.json",
            "schema_version": 2,
            "kind": "jfg-g2-private-executable-evidence",
            "pins": pins,
            "requirements": private_requirements,
            "evidence_set_sha256": hashlib.sha256(
                G2._canonical_bytes(private_requirements)
            ).hexdigest(),
        }
        public_requirements = {
            requirement_id: {
                "passed": True,
                "evidence_record_count": private_requirements[requirement_id][
                    "evidence_record_count"
                ],
                "executable_evidence_count": private_requirements[requirement_id][
                    "executable_evidence_count"
                ],
                "unresolved_count": 0,
                "result_sha256": hashlib.sha256(
                    G2._canonical_bytes(private_requirements[requirement_id])
                ).hexdigest(),
            }
            for requirement_id in G2.REQUIREMENT_IDS
        }
        public = {
            "$schema": "../schemas/g2-completion-evidence.schema.json",
            "schema_version": 2,
            "kind": "jfg-g2-completion-evidence",
            "privacy": "public-safe-aggregate-only",
            "record_class": "maintainer-reviewed-public-aggregate",
            "pins": {
                key: value
                for key, value in pins.items()
                if key != "input_rom_sha256"
            },
            "requirements": public_requirements,
            "evidence_set_sha256": hashlib.sha256(
                G2._canonical_bytes(public_requirements)
            ).hexdigest(),
            "gate": {
                "id": "G2",
                "decision": "go",
                "broad_phase4_authorized": True,
                "all_required_checks_passed": True,
            },
        }
        return private, public, decision, policy

    def validate(
        self,
        private: object,
        public: object,
        decision: Path,
        bundle: Path,
        policy: dict[tuple[str, str], G2.PinnedHarness],
    ) -> list[str]:
        with mock.patch.object(G2, "ARCHITECTURE_DECISION", decision):
            return G2._validate_documents_for_tests(
                private,
                public,
                G2.load_json(G2.PRIVATE_SCHEMA),
                G2.load_json(G2.PUBLIC_SCHEMA),
                bundle,
                policy,
            )

    def make_bundle(self) -> tuple[
        tempfile.TemporaryDirectory[str],
        Path,
        G2.PinnedHarness,
        dict[str, object],
        dict[str, object],
        Path,
        dict[tuple[str, str], G2.PinnedHarness],
    ]:
        temporary = tempfile.TemporaryDirectory(prefix="g2-private-test-")
        bundle = Path(temporary.name)
        pin = self.write_harness(bundle)
        private, public, decision, policy = self.build_documents(bundle, pin)
        return temporary, bundle, pin, private, public, decision, policy

    def test_valid_bundle_executes_injected_test_harness(self) -> None:
        temporary, bundle, _, private, public, decision, policy = self.make_bundle()
        with temporary:
            self.assertEqual(
                self.validate(private, public, decision, bundle, policy), []
            )
            self.assertEqual(
                (bundle / "harness-ran.marker").read_text(encoding="utf-8"),
                "validated\n",
            )

    def test_trusted_producer_source_and_derivation_are_fail_closed(self) -> None:
        mapping = ("overlay-lifecycle", "private-native-execution")
        expected = dict(G2.PRODUCER_SOURCE_PROVENANCE[mapping])
        source = ROOT / expected["source_path"]
        source_bytes = source.read_bytes()
        expected["source_sha256"] = hashlib.sha256(source_bytes).hexdigest()
        with tempfile.TemporaryDirectory(prefix="g2-source-provenance-") as temp:
            bundle = Path(temp)
            config_path = bundle / "case.json"
            execution = {
                "evidence_class": mapping[1],
                "source_input_sha256": self.digest("supported-input"),
                "subject_sha256": self.digest("bounded-case"),
                "environment": {"toolchain_sha256": self.digest("toolchain")},
                "artifacts": [{
                    "path": "case.json", "role": "configuration", "sha256": self.digest("pending")
                }],
            }
            build = {
                "schema_version": 1,
                "kind": "jfg-g2-producer-build-attestation",
                "compiler_id": "clang-cl-22.1.8",
                "compiler_sha256": execution["environment"]["toolchain_sha256"],
                "cmake_generator": "Ninja",
                "cmake_configuration": "Release",
                "cmake_defines": ["JFG_ENABLE_GENERATED_CODE=ON"],
                "producer_compile_flags": ["/std:c++20", "/O2"],
                "generated_compile_flags": ["/O2"],
                "private_generated_closure_sha256": self.digest("private-closure"),
                "tracked_dependency_closure_sha256": expected["tracked_closure_sha256"],
                "reviewed_commit": expected["reviewed_commit"],
                "reviewed_tree": expected["reviewed_tree"],
            }
            derivation = {
                "schema_version": 1,
                "kind": "jfg-g2-source-derivation",
                "supported_input_sha256": execution["source_input_sha256"],
                "bounded_case_sha256": execution["subject_sha256"],
                "adapter_id": expected["adapter_id"],
                "adapter_version": expected["adapter_version"],
                "producer_source_path": expected["source_path"],
                "producer_source_sha256": expected["source_sha256"],
                "producer_source_revision": expected["reviewed_commit"],
                "producer_tree_revision": expected["reviewed_tree"],
                "tracked_dependency_closure_sha256": expected["tracked_closure_sha256"],
                "build_system": expected["build_system"],
                "build_recipe_id": expected["build_recipe_id"],
                "build_target": expected["build_target"],
                "build_attestation": build,
            }
            config_path.write_bytes(G2._canonical_bytes({"source_derivation": derivation}))
            execution["artifacts"][0]["sha256"] = hashlib.sha256(config_path.read_bytes()).hexdigest()  # type: ignore[index]
            with mock.patch.object(G2, "PRODUCER_SOURCE_PROVENANCE", {mapping: expected}), \
                    mock.patch.object(G2, "PRODUCER_BUILD_ATTESTATION", {mapping: build}), \
                    mock.patch.object(G2, "_tracked_repository_file", return_value=True), \
                    mock.patch.object(G2, "_tracked_blob", return_value=source_bytes), \
                    mock.patch.object(G2, "_tracked_dependency_closure_errors", return_value=[]):
                self.assertEqual(
                    G2._producer_source_errors(mapping[0], execution, bundle), []
                )
                derivation["bounded_case_sha256"] = self.digest("unbound-case")
                config_path.write_bytes(G2._canonical_bytes({"source_derivation": derivation}))
                self.assertEqual(
                    G2._producer_source_errors(mapping[0], execution, bundle),
                    ["private evidence: source derivation is unbound"],
                )
                with mock.patch.object(G2, "PRODUCER_SOURCE_PROVENANCE", {}):
                    self.assertEqual(
                        G2._producer_source_errors(mapping[0], execution, bundle),
                        ["private evidence: producer source provenance is unavailable"],
                    )
                with mock.patch.object(G2, "_tracked_blob", return_value=b"swapped"):
                    self.assertEqual(
                        G2._producer_source_errors(mapping[0], execution, bundle),
                        ["private evidence: producer source differs from its committed blob"],
                    )

    def test_trusted_validation_cannot_use_test_harness_policy(self) -> None:
        temporary, bundle, _, private, public, decision, _ = self.make_bundle()
        with temporary:
            private_path = bundle / "g2-private.json"
            private_path.write_text(json.dumps(private), encoding="utf-8")
            with mock.patch.object(G2, "ARCHITECTURE_DECISION", decision):
                errors = G2.validate_private_file(private_path, public)
            # Trusted validation must select the tracked production pins, never
            # a test-injected policy: a synthetic execution is rejected either
            # because no production pin exists for it or because it does not
            # use the pinned production harness identity.
            self.assertTrue(
                "private evidence: pinned harness is unavailable" in errors
                or "private evidence: execution does not use the pinned harness"
                in errors,
                errors,
            )

    def test_reviewed_revision_closure_and_clean_state_are_enforced(self) -> None:
        mapping = ("overlay-lifecycle", "private-native-execution")
        expected = dict(G2.PRODUCER_SOURCE_PROVENANCE[mapping])
        bounded_adapter = "src/evidence/g2_graphics_bounded_adapter.cpp"
        self.assertIn(bounded_adapter, G2.PRODUCER_TRACKED_DEPENDENCY_PATHS)
        rows = []
        payload_by_path = {}
        for textual in G2.PRODUCER_TRACKED_DEPENDENCY_PATHS:
            payload = ("tracked:" + textual).encode("utf-8")
            payload_by_path[textual] = payload
            rows.append({"path": textual, "sha256": hashlib.sha256(payload).hexdigest()})
        expected["tracked_closure_sha256"] = hashlib.sha256(
            G2._canonical_bytes(rows)
        ).hexdigest()

        def read(path: Path, **_kwargs: object) -> bytes:
            relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
            return payload_by_path[relative]

        def blob(path: Path, _revision: str) -> bytes:
            relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
            return payload_by_path[relative]

        with mock.patch.object(
            G2, "_git_object_id", side_effect=[
                expected["reviewed_commit"], expected["reviewed_tree"],
                expected["reviewed_commit"], expected["reviewed_tree"],
            ]
        ), mock.patch.object(G2, "_git_result", side_effect=[0, 0, 0, 0]), mock.patch.object(
            G2, "_read_regular_bounded", side_effect=read
        ), mock.patch.object(G2, "_tracked_blob", side_effect=blob), mock.patch.object(
            G2, "_tracked_repository_file", return_value=True
        ):
            self.assertEqual(G2._tracked_dependency_closure_errors(expected), [])
            stale = dict(expected)
            stale["tracked_closure_sha256"] = hashlib.sha256(
                G2._canonical_bytes(
                    [row for row in rows if row["path"] != bounded_adapter]
                )
            ).hexdigest()
            self.assertEqual(
                G2._tracked_dependency_closure_errors(stale),
                ["private evidence: tracked producer closure digest differs"],
            )

        with mock.patch.object(
            G2, "_git_object_id", side_effect=[expected["reviewed_commit"], expected["reviewed_tree"]]
        ), mock.patch.object(G2, "_git_result", side_effect=[0, 1]):
            self.assertEqual(
                G2._tracked_dependency_closure_errors(expected),
                ["private evidence: producer repository state is not clean"],
            )

        with mock.patch.object(G2, "_git_object_id", return_value=None):
            self.assertEqual(
                G2._tracked_dependency_closure_errors(expected),
                ["private evidence: reviewed producer revision is unavailable"],
            )

    def test_arbitrary_runner_role_is_rejected_by_v2_schema(self) -> None:
        temporary, bundle, _, private, public, decision, policy = self.make_bundle()
        with temporary:
            execution = private["requirements"]["overlay-lifecycle"]["executions"][0]  # type: ignore[index]
            fake = bundle / "fake-runner.txt"
            fake.write_text("not executable\n", encoding="utf-8")
            execution["artifacts"].append(  # type: ignore[index]
                {
                    "path": fake.name,
                    "role": "runner",
                    "sha256": hashlib.sha256(fake.read_bytes()).hexdigest(),
                }
            )
            self.assertIn(
                "schema: contract violation",
                self.validate(private, public, decision, bundle, policy),
            )

    def test_self_asserted_or_mismatched_result_is_rejected(self) -> None:
        temporary, bundle, _, private, public, decision, policy = self.make_bundle()
        with temporary:
            execution = private["requirements"]["overlay-lifecycle"]["executions"][0]  # type: ignore[index]
            result_artifact = next(  # type: ignore[assignment]
                item for item in execution["artifacts"] if item["role"] == "result"  # type: ignore[index]
            )
            result_path = bundle / result_artifact["path"]
            result_path.write_text('{"passed": false}', encoding="utf-8")
            result_artifact["sha256"] = hashlib.sha256(result_path.read_bytes()).hexdigest()
            execution["result_sha256"] = result_artifact["sha256"]  # type: ignore[index]
            execution["artifact_set_sha256"] = hashlib.sha256(  # type: ignore[index]
                G2._canonical_bytes(execution["artifacts"])  # type: ignore[index]
            ).hexdigest()
            self.refresh_document_digests(private, public)
            errors = self.validate(private, public, decision, bundle, policy)
            self.assertIn("private evidence: structured result contract differs", errors)

    def test_result_boolean_cannot_be_substituted_with_integer(self) -> None:
        temporary, bundle, _, private, public, decision, policy = self.make_bundle()
        with temporary:
            execution = private["requirements"]["overlay-lifecycle"]["executions"][0]  # type: ignore[index]
            result_artifact = next(  # type: ignore[assignment]
                item for item in execution["artifacts"] if item["role"] == "result"  # type: ignore[index]
            )
            result_path = bundle / result_artifact["path"]
            result_document = self.result_document(execution, "overlay-lifecycle")
            result_document["passed"] = 1
            result_path.write_text(json.dumps(result_document), encoding="utf-8")
            result_artifact["sha256"] = hashlib.sha256(result_path.read_bytes()).hexdigest()
            execution["result_sha256"] = result_artifact["sha256"]  # type: ignore[index]
            execution["artifact_set_sha256"] = hashlib.sha256(  # type: ignore[index]
                G2._canonical_bytes(execution["artifacts"])  # type: ignore[index]
            ).hexdigest()
            self.refresh_document_digests(private, public)
            self.assertIn(
                "private evidence: structured result is unbound",
                self.validate(private, public, decision, bundle, policy),
            )

    def test_native_oracle_cases_require_same_subject_and_distinct_environment(self) -> None:
        temporary, bundle, _, private, public, decision, policy = self.make_bundle()
        with temporary:
            requirement = private["requirements"]["graphics-tasks"]  # type: ignore[index]
            oracle = requirement["executions"][1]  # type: ignore[index]
            oracle["subject_sha256"] = self.digest("different-subject")  # type: ignore[index]
            self.write_result(bundle, oracle, "graphics-tasks")
            self.refresh_document_digests(private, public)
            errors = self.validate(private, public, decision, bundle, policy)
            self.assertIn("private evidence: case subject binding is inconsistent", errors)
            self.assertIn("private evidence: native/oracle case pair is incomplete", errors)

            native = requirement["executions"][0]  # type: ignore[index]
            oracle["subject_sha256"] = native["subject_sha256"]  # type: ignore[index]
            oracle["environment"] = copy.deepcopy(native["environment"])  # type: ignore[index]
            oracle["environment_sha256"] = native["environment_sha256"]  # type: ignore[index]
            self.write_result(bundle, oracle, "graphics-tasks")
            self.refresh_document_digests(private, public)
            errors = self.validate(private, public, decision, bundle, policy)
            self.assertIn("private evidence: native/oracle case pair is incomplete", errors)

    def test_runtime_traps_require_an_independent_native_oracle_pair(self) -> None:
        temporary, bundle, _, private, public, decision, policy = self.make_bundle()
        with temporary:
            requirement = private["requirements"]["runtime-traps"]  # type: ignore[index]
            executions = requirement["executions"]  # type: ignore[index]
            self.assertEqual(
                [execution["evidence_class"] for execution in executions],
                ["private-native-execution", "private-oracle-execution"],
            )

            # A second native record cannot relabel or replace the required
            # independent oracle route, even when its document digests are
            # recomputed consistently.
            executions[1]["evidence_class"] = "private-native-execution"
            self.write_result(bundle, executions[1], "runtime-traps")
            self.refresh_document_digests(private, public)
            errors = self.validate(private, public, decision, bundle, policy)
            self.assertIn("private evidence: native/oracle case pair is incomplete", errors)

    def test_runtime_trap_oracle_cannot_reuse_native_environment(self) -> None:
        temporary, bundle, _, private, public, decision, policy = self.make_bundle()
        with temporary:
            requirement = private["requirements"]["runtime-traps"]  # type: ignore[index]
            native, oracle = requirement["executions"]  # type: ignore[index]
            oracle["environment"] = copy.deepcopy(native["environment"])
            oracle["environment_sha256"] = native["environment_sha256"]
            self.write_result(bundle, oracle, "runtime-traps")
            self.refresh_document_digests(private, public)
            errors = self.validate(private, public, decision, bundle, policy)
            self.assertIn("private evidence: native/oracle case pair is incomplete", errors)

    def test_runtime_trap_provenance_cannot_be_shared_between_native_and_oracle(self) -> None:
        temporary, _, _, private, _, _, _ = self.make_bundle()
        with temporary:
            requirement = private["requirements"]["runtime-traps"]  # type: ignore[index]
            native_key = ("runtime-traps", "private-native-execution")
            oracle_key = ("runtime-traps", "private-oracle-execution")
            native_source = {
                "source_path": "src/evidence/trap_native.cpp",
                "source_sha256": self.digest("native-source"),
                "build_target": "jfg_g2_trap_native",
                "adapter_id": "g2-trap-native-adapter",
                "adapter_version": "v1",
            }
            native_build = {"kind": "native", "compiler_sha256": self.digest("native")}
            with mock.patch.object(
                G2,
                "PRODUCER_SOURCE_PROVENANCE",
                {native_key: native_source, oracle_key: copy.deepcopy(native_source)},
            ), mock.patch.object(
                G2,
                "PRODUCER_BUILD_ATTESTATION",
                {native_key: native_build, oracle_key: copy.deepcopy(native_build)},
            ):
                errors = G2._runtime_trap_provenance_errors(requirement)
            self.assertIn(
                "private evidence: native/oracle producer provenance is shared",
                errors,
            )
            self.assertIn(
                "private evidence: native/oracle build provenance is shared",
                errors,
            )

            oracle_source = copy.deepcopy(native_source)
            oracle_source.update(
                {
                    "source_path": "src/evidence/trap_oracle.cpp",
                    "source_sha256": self.digest("oracle-source"),
                    "build_target": "jfg_g2_trap_oracle",
                    "adapter_id": "g2-trap-oracle-adapter",
                }
            )
            oracle_build = {"kind": "oracle", "compiler_sha256": self.digest("oracle")}
            with mock.patch.object(
                G2,
                "PRODUCER_SOURCE_PROVENANCE",
                {native_key: native_source, oracle_key: oracle_source},
            ), mock.patch.object(
                G2,
                "PRODUCER_BUILD_ATTESTATION",
                {native_key: native_build, oracle_key: oracle_build},
            ):
                self.assertEqual(G2._runtime_trap_provenance_errors(requirement), [])

    def test_every_paired_requirement_requires_distinct_private_closures(self) -> None:
        temporary, _, _, private, _, _, _ = self.make_bundle()
        with temporary:
            requirement = private["requirements"]["runtime-traps"]  # type: ignore[index]
            shared_closure = self.digest("shared-private-closure")
            for requirement_id in G2.NATIVE_AND_ORACLE:
                native_key = (requirement_id, "private-native-execution")
                oracle_key = (requirement_id, "private-oracle-execution")
                sources = {
                    native_key: {
                        "source_path": "src/evidence/native.cpp",
                        "source_sha256": self.digest("native-source"),
                        "build_target": "native-target",
                        "adapter_id": "native-adapter",
                        "adapter_version": "v1",
                    },
                    oracle_key: {
                        "source_path": "src/evidence/oracle.cpp",
                        "source_sha256": self.digest("oracle-source"),
                        "build_target": "oracle-target",
                        "adapter_id": "oracle-adapter",
                        "adapter_version": "v1",
                    },
                }
                builds = {
                    native_key: {
                        "kind": "native",
                        "private_generated_closure_sha256": shared_closure,
                    },
                    oracle_key: {
                        "kind": "oracle",
                        "private_generated_closure_sha256": shared_closure,
                    },
                }
                with self.subTest(requirement_id=requirement_id), mock.patch.object(
                    G2, "PRODUCER_SOURCE_PROVENANCE", sources
                ), mock.patch.object(G2, "PRODUCER_BUILD_ATTESTATION", builds):
                    self.assertIn(
                        "private evidence: native/oracle build provenance is shared",
                        G2._paired_provenance_errors(requirement_id, requirement),
                    )

    def test_cpu_compiler_product_matrix_requires_three_records(self) -> None:
        temporary, bundle, _, private, public, decision, policy = self.make_bundle()
        with temporary:
            executions = private["requirements"]["cpu-sections"]["executions"]  # type: ignore[index]
            executions.pop()
            self.refresh_document_digests(private, public)
            errors = self.validate(private, public, decision, bundle, policy)
            self.assertIn(
                "private evidence: CPU compiler-product matrix is incomplete", errors
            )

    def test_cpu_product_bindings_do_not_claim_distinct_producer_environments(self) -> None:
        executions = [
            {
                "evidence_class": "private-g3-compiler-product-binding",
                "case_id": "cpu-case",
                "subject_sha256": self.digest("case"),
                "source_input_sha256": self.digest("input"),
                "environment_sha256": self.digest("one-real-producer-environment"),
            }
            for _ in range(3)
        ]
        requirement = {
            "evidence_record_count": 3,
            "executable_evidence_count": 3,
            "executions": executions,
        }
        self.assertEqual(G2._requirement_shape_errors("cpu-sections", requirement), [])

    def test_cpu_records_cross_bind_to_independent_g3_products(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="g2-cpu-g3-binding-", dir=ROOT / "tools"
        ) as temporary:
            bundle = Path(temporary)
            toolchains = [self.digest(f"compiler-{index}") for index in range(3)]
            compilers = [
                {
                    "family": family,
                    "compiler_id": f"{family}-test",
                    "compiler_executable_sha256": toolchain,
                    "generated_compile_passed": True,
                    "minimal_runtime_link_passed": True,
                    "forced_object_audit_passed": True,
                }
                for family, toolchain in zip(("clang", "gcc", "msvc"), toolchains)
            ]
            phase4_public = {
                "kind": "jfg-phase4-generated-manifest",
                "attestation": {
                    "private_evidence_sha256": self.digest("phase4-private-body")
                },
                "pins": {},
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
                    "covered_alias_ledger_sha256": self.digest(
                        "covered-alias-ledger"
                    ),
                    "manual_size_recovery_count": 6,
                    "manual_size_recovery_ledger_sha256": self.digest(
                        "size-recovery-ledger"
                    ),
                    "manual_size_recovery_approval_set_sha256": self.digest(
                        "size-recovery-approvals"
                    ),
                    "inventory_sha256": self.digest("generated-inventory"),
                    "approval_set_sha256": self.digest("covered-alias-approvals"),
                },
                "calls": {},
                "relocations": {},
                "stubs": {"generated_game_function_stub_count": 0},
                "overlays": {
                    "forced_object_link_passed": True,
                    "executable_section_count": 2,
                    "expected_slot_count": 2,
                    "listed_slot_count": 2,
                    "populated_slot_count": 1,
                    "empty_slot_count": 1,
                },
                "compilers": compilers,
                "analysis": {"all_available_sanitizers_passed": True},
                "libraries": {
                    "baseline": {"unmodified_body_member_count": 2905},
                    "patch": {"member_count": 1},
                    "minimal_runtime": {
                        "relocation_table_entry_count": 2,
                        "section_address_count": 2,
                        "handwritten_bridge_unit_count": 2,
                    },
                },
                "reproducibility": {"passed": True},
                "config_diff": {},
            }
            phase4_executions = []
            identity_fields = (
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
            for index, evidence_kind in enumerate(G2.CPU_G3_EVIDENCE_KINDS):
                record = {
                    "id": f"execution-{index}",
                    "evidence_kind": evidence_kind,
                    "case_id": f"case-{index}",
                }
                record.update(
                    {
                        field: self.digest(f"g3-{index}-{field}")
                        for field in identity_fields
                    }
                )
                record["observed_exit_code"] = 0
                record["passed"] = True
                phase4_executions.append(record)
            phase4_private = {"executions": phase4_executions}
            binding = G2.cpu_g3_product_binding_sha256(
                phase4_private, phase4_public
            )
            assert isinstance(binding, str)

            sections = [
                {
                    "section_id": "main-core",
                    "kind": "main",
                    "expected_body_count": 2200,
                    "attempted_body_count": 2200,
                    "generated_body_count": 1720,
                    "approved_exclusion_count": 480,
                    "unclassified_failure_count": 0,
                    "lookup_entry_count": 1720,
                    "lifecycle_entry_count": 0,
                    "relocation_entry_count": 1,
                },
                {
                    "section_id": "overlay-core",
                    "kind": "overlay",
                    "expected_body_count": 1529,
                    "attempted_body_count": 1529,
                    "generated_body_count": 1185,
                    "approved_exclusion_count": 344,
                    "unclassified_failure_count": 0,
                    "lookup_entry_count": 1185,
                    "lifecycle_entry_count": 1,
                    "relocation_entry_count": 1,
                },
            ]
            inventory_rows = [
                {
                    "section_id": item["section_id"],
                    "kind": item["kind"],
                    "expected": item["expected_body_count"],
                    "generated": item["generated_body_count"],
                    "excluded": item["approved_exclusion_count"],
                    "lookups": item["lookup_entry_count"],
                    "lifecycle": item["lifecycle_entry_count"],
                    "relocations": item["relocation_entry_count"],
                }
                for item in sections
            ]
            overlay_slots = [
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
            ]
            generation_root = bundle / "production" / "generation"
            generation_root.mkdir(parents=True)
            inventory_path = generation_root / "cpu-section-inventory.json"
            inventory_path.write_bytes(
                G2._canonical_bytes(
                    {
                        "schema_version": 2,
                        "kind": "jfg-phase4-cpu-section-inventory",
                        "sections": inventory_rows,
                        "overlay_slots": overlay_slots,
                    }
                )
            )
            plan_path = generation_root / "audit-plan.json"
            plan_path.write_bytes(
                G2._canonical_bytes(
                    {
                        "schema_version": 1,
                        "kind": "jfg-phase4-production-audit",
                        "evidence_kind": "generation",
                        "products": [
                            {
                                "product_kind": "cpu-section-inventory",
                                "artifact_path": "production/generation/cpu-section-inventory.json",
                            }
                        ],
                    }
                )
            )
            generation_execution = next(
                item
                for item in phase4_executions
                if item["evidence_kind"] == "generation"
            )
            generation_execution["artifacts"] = [
                {
                    "path": "production/generation/audit-plan.json",
                    "role": "configuration",
                    "sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
                },
                {
                    "path": "production/generation/cpu-section-inventory.json",
                    "role": "output",
                    "sha256": hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
                },
            ]
            link_audit = {
                "section_count": 2,
                "expected_object_count": 2905,
                "generated_object_count": 2905,
                "forced_object_count": 2905,
                "unresolved_symbol_count": 0,
                "duplicate_definition_count": 0,
                "generated_stub_count": 0,
                "expected_runtime_bridge_count": 2,
                "resolved_runtime_bridge_count": 2,
            }
            analysis = [
                {
                    "tool": tool,
                    "exit_code": 0,
                    "finding_count": 0,
                    "source_set_sha256": self.digest("cpu-case"),
                }
                for tool in (
                    "compiler-link",
                    "forced-object-audit",
                    "asan",
                    "ubsan",
                    "clang-static-analyzer",
                )
            ]
            cpu_executions: list[dict[str, object]] = []
            for index, (family, toolchain) in enumerate(
                zip(("clang", "gcc", "msvc"), toolchains)
            ):
                observation = {
                    "schema_version": 4,
                    "kind": "jfg-g2-cpu-observation",
                    "g3_product_binding_sha256": binding,
                    "compiler_id": f"{family}-test",
                    "compiler_executable_sha256": toolchain,
                    "sections": copy.deepcopy(sections),
                    "overlay_slots": copy.deepcopy(overlay_slots),
                    "link_audit": copy.deepcopy(link_audit),
                    "analysis_records": copy.deepcopy(analysis),
                }
                observation_path = bundle / f"cpu-{index}-observation.json"
                observation_path.write_bytes(G2._canonical_bytes(observation))
                observation_digest = hashlib.sha256(
                    observation_path.read_bytes()
                ).hexdigest()
                configuration_path = bundle / f"cpu-{index}-configuration.json"
                configuration_path.write_bytes(
                    G2._canonical_bytes({"observation_sha256": observation_digest})
                )
                cpu_executions.append(
                    {
                        "artifacts": [
                            {
                                "path": configuration_path.name,
                                "role": "configuration",
                                "sha256": hashlib.sha256(
                                    configuration_path.read_bytes()
                                ).hexdigest(),
                            },
                            {
                                "path": observation_path.name,
                                "role": "output",
                                "sha256": observation_digest,
                            },
                        ]
                    }
                )
            g2_private = {
                "requirements": {"cpu-sections": {"executions": cpu_executions}}
            }
            self.assertEqual(
                G2.validate_cpu_g3_binding(
                    g2_private, bundle, phase4_private, phase4_public, bundle
                ),
                [],
            )

            request_specific = copy.deepcopy(phase4_private)
            for index, execution in enumerate(request_specific["executions"]):
                execution["artifact_set_sha256"] = self.digest(
                    f"request-artifact-{index}"
                )
                execution["result_sha256"] = self.digest(f"request-result-{index}")
            self.assertEqual(
                G2.validate_cpu_g3_binding(
                    g2_private, bundle, request_specific, phase4_public, bundle
                ),
                [],
            )

            binding_error = (
                "private evidence: CPU records are not bound to independently "
                "executed G3 products"
            )
            for field in G2.G3_PRODUCT_CORE_FIELDS:
                changed_products = copy.deepcopy(phase4_public)
                changed_products[field] = {"mutation": field}
                with self.subTest(g3_product_field=field):
                    self.assertIn(
                        binding_error,
                        G2.validate_cpu_g3_binding(
                            g2_private,
                            bundle,
                            phase4_private,
                            changed_products,
                            bundle,
                        ),
                    )

            changed_patch = copy.deepcopy(phase4_public)
            changed_patch["libraries"]["patch"] = {"member_count": 2}
            self.assertIn(
                binding_error,
                G2.validate_cpu_g3_binding(
                    g2_private, bundle, phase4_private, changed_patch, bundle
                ),
            )

            changed_body_digest = copy.deepcopy(phase4_public)
            changed_body_digest["attestation"]["private_evidence_sha256"] = (
                self.digest("different-phase4-private-body")
            )
            self.assertIn(
                binding_error,
                G2.validate_cpu_g3_binding(
                    g2_private,
                    bundle,
                    phase4_private,
                    changed_body_digest,
                    bundle,
                ),
            )

            for index in range(len(phase4_executions)):
                changed_execution = copy.deepcopy(phase4_private)
                changed_execution["executions"][index]["output_set_sha256"] = (
                    self.digest(f"changed-g3-execution-{index}")
                )
                with self.subTest(g3_execution=index):
                    self.assertIn(
                        binding_error,
                        G2.validate_cpu_g3_binding(
                            g2_private,
                            bundle,
                            changed_execution,
                            phase4_public,
                            bundle,
                        ),
                    )

            different_projection = copy.deepcopy(phase4_public)
            different_projection["symbols"]["generated_count"] += 1
            self.assertEqual(
                G2.validate_cpu_g3_binding(
                    g2_private,
                    bundle,
                    phase4_private,
                    different_projection,
                    bundle,
                ),
                [
                    "private evidence: CPU records are not bound to independently executed G3 products"
                ],
            )

            first_observation_path = bundle / "cpu-0-observation.json"
            first_configuration_path = bundle / "cpu-0-configuration.json"
            original_observation = first_observation_path.read_bytes()
            substituted = json.loads(original_observation)
            substituted["compiler_id"] = "clang-substitute"
            first_observation_path.write_bytes(G2._canonical_bytes(substituted))
            substituted_digest = hashlib.sha256(
                first_observation_path.read_bytes()
            ).hexdigest()
            first_configuration_path.write_bytes(
                G2._canonical_bytes({"observation_sha256": substituted_digest})
            )
            cpu_executions[0]["artifacts"][0]["sha256"] = hashlib.sha256(  # type: ignore[index]
                first_configuration_path.read_bytes()
            ).hexdigest()
            cpu_executions[0]["artifacts"][1]["sha256"] = substituted_digest  # type: ignore[index]
            self.assertEqual(
                G2.validate_cpu_g3_binding(
                    g2_private, bundle, phase4_private, phase4_public, bundle
                ),
                [
                    "private evidence: CPU records are not bound to independently executed G3 products"
                ],
            )
            first_observation_path.write_bytes(original_observation)
            original_digest = hashlib.sha256(original_observation).hexdigest()
            first_configuration_path.write_bytes(
                G2._canonical_bytes({"observation_sha256": original_digest})
            )
            cpu_executions[0]["artifacts"][0]["sha256"] = hashlib.sha256(  # type: ignore[index]
                first_configuration_path.read_bytes()
            ).hexdigest()
            cpu_executions[0]["artifacts"][1]["sha256"] = original_digest  # type: ignore[index]

            # Move one body between sections while preserving every aggregate.
            # The case remains structurally valid and aggregate-identical, but
            # must differ from the authenticated G3 per-section inventory.
            for index, execution in enumerate(cpu_executions):
                observation_path = bundle / f"cpu-{index}-observation.json"
                forged = json.loads(observation_path.read_text(encoding="utf-8"))
                for field in (
                    "expected_body_count",
                    "attempted_body_count",
                    "generated_body_count",
                    "lookup_entry_count",
                ):
                    forged["sections"][0][field] -= 1
                    forged["sections"][1][field] += 1
                observation_path.write_bytes(G2._canonical_bytes(forged))
                digest = hashlib.sha256(observation_path.read_bytes()).hexdigest()
                configuration_path = bundle / f"cpu-{index}-configuration.json"
                configuration_path.write_bytes(
                    G2._canonical_bytes({"observation_sha256": digest})
                )
                execution["artifacts"][0]["sha256"] = hashlib.sha256(  # type: ignore[index]
                    configuration_path.read_bytes()
                ).hexdigest()
                execution["artifacts"][1]["sha256"] = digest  # type: ignore[index]
            self.assertEqual(
                G2.validate_cpu_g3_binding(
                    g2_private, bundle, phase4_private, phase4_public, bundle
                ),
                [
                    "private evidence: CPU records are not bound to independently executed G3 products"
                ],
            )

    def test_source_input_is_bound_to_public_private_pin(self) -> None:
        temporary, bundle, _, private, public, decision, policy = self.make_bundle()
        with temporary:
            execution = private["requirements"]["audio-tasks"]["executions"][0]  # type: ignore[index]
            execution["source_input_sha256"] = self.digest("wrong-input")  # type: ignore[index]
            self.write_result(bundle, execution, "audio-tasks")
            self.refresh_document_digests(private, public)
            errors = self.validate(private, public, decision, bundle, policy)
            self.assertIn(
                "private evidence: source input does not match the pinned input", errors
            )

    def test_private_record_cannot_select_a_bundle_harness(self) -> None:
        temporary, bundle, _, private, public, decision, policy = self.make_bundle()
        with temporary:
            execution = private["requirements"]["overlay-lifecycle"]["executions"][0]  # type: ignore[index]
            execution["harness_id"] = "bundle-selected-harness"  # type: ignore[index]
            self.write_result(bundle, execution, "overlay-lifecycle")
            self.refresh_document_digests(private, public)
            self.assertIn(
                "private evidence: execution does not use the pinned harness",
                self.validate(private, public, decision, bundle, policy),
            )

    def test_decision_artifact_must_be_the_authoritative_adr(self) -> None:
        temporary, bundle, _, private, public, decision, policy = self.make_bundle()
        with temporary:
            execution = private["requirements"]["dependency-legal-selection"][  # type: ignore[index]
                "executions"
            ][0]
            artifacts = execution["artifacts"]  # type: ignore[index]
            decision_artifact = next(item for item in artifacts if item["role"] == "decision")
            decision_copy = bundle / decision_artifact["path"]
            decision_copy.write_text("# Different decision\n", encoding="utf-8")
            decision_artifact["sha256"] = hashlib.sha256(
                decision_copy.read_bytes()
            ).hexdigest()
            input_records = [
                item
                for item in artifacts
                if item["role"] in {"configuration", "input", "decision"}
            ]
            execution["input_set_sha256"] = hashlib.sha256(  # type: ignore[index]
                G2._canonical_bytes(input_records)
            ).hexdigest()
            self.write_result(bundle, execution, "dependency-legal-selection")
            self.refresh_document_digests(private, public)
            self.assertIn(
                "private evidence: approved decision artifact is unbound",
                self.validate(private, public, decision, bundle, policy),
            )

    def test_authoritative_adr_status_rejects_examples_and_conflicts(self) -> None:
        self.assertTrue(
            G2._accepted_adr(
                "# Decision\n\n- Status: Accepted by `TK22-26`\n"
            )
        )
        self.assertFalse(
            G2._accepted_adr(
                "# Decision\n\n- Status: Proposed\n\n```md\n- Status: Accepted by `TK22-26`\n```\n"
            )
        )
        self.assertFalse(
            G2._accepted_adr(
                "# Decision\n\n- Status: Accepted by `TK22-26`\n\n- Status: Proposed\n"
            )
        )

    def test_total_and_executable_counts_are_distinct_and_bound(self) -> None:
        temporary, bundle, _, private, public, decision, policy = self.make_bundle()
        with temporary:
            legal = private["requirements"]["dependency-legal-selection"]  # type: ignore[index]
            self.assertEqual(legal["evidence_record_count"], 1)  # type: ignore[index]
            self.assertEqual(legal["executable_evidence_count"], 0)  # type: ignore[index]
            legal["executable_evidence_count"] = 1  # type: ignore[index]
            public["requirements"]["dependency-legal-selection"][  # type: ignore[index]
                "executable_evidence_count"
            ] = 1
            self.refresh_document_digests(private, public)
            # Restore the deliberate lie after the helper's normal reconciliation.
            legal["executable_evidence_count"] = 1  # type: ignore[index]
            public["requirements"]["dependency-legal-selection"][  # type: ignore[index]
                "executable_evidence_count"
            ] = 1
            private["evidence_set_sha256"] = hashlib.sha256(
                G2._canonical_bytes(private["requirements"])
            ).hexdigest()
            public["requirements"]["dependency-legal-selection"][  # type: ignore[index]
                "result_sha256"
            ] = hashlib.sha256(G2._canonical_bytes(legal)).hexdigest()
            public["evidence_set_sha256"] = hashlib.sha256(
                G2._canonical_bytes(public["requirements"])
            ).hexdigest()
            self.assertIn(
                "private evidence: executable evidence count is unbound",
                self.validate(private, public, decision, bundle, policy),
            )

    def test_every_artifact_must_be_external_or_ignored(self) -> None:
        temporary, bundle, _, private, public, decision, policy = self.make_bundle()
        with temporary, mock.patch.object(
            G2, "_private_path_is_allowed", return_value=False
        ):
            errors = self.validate(private, public, decision, bundle, policy)
            self.assertIn("private evidence: artifact must be external or ignored", errors)

    def test_harness_timeout_and_output_limits_fail_generically(self) -> None:
        with tempfile.TemporaryDirectory(prefix="g2-harness-limits-") as temp:
            bundle = Path(temp)
            timeout_pin = self.write_harness(
                bundle,
                "import time\ntime.sleep(2)\n",
                timeout=0.05,
            )
            transcript, errors = G2.execute_pinned_harness(
                timeout_pin, {}, bundle, require_tracked=False
            )
            self.assertIsNone(transcript)
            self.assertEqual(errors, ["private evidence: pinned harness timed out"])
            self.assertNotIn(str(bundle), "\n".join(errors))

            noisy_pin = self.write_harness(
                bundle,
                f"import sys\nsys.stdout.write('x' * {G2.MAX_HARNESS_STDOUT_BYTES + 1})\n",
            )
            transcript, errors = G2.execute_pinned_harness(
                noisy_pin, {}, bundle, require_tracked=False
            )
            self.assertIsNone(transcript)
            self.assertEqual(
                errors, ["private evidence: pinned harness rejected the execution"]
            )

    def test_open_once_identity_and_size_checks_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="g2-open-once-") as temp:
            body = Path(temp) / "body.bin"
            body.write_bytes(b"12345")
            with self.assertRaises(G2.EvidenceError):
                G2._read_regular_bounded(body, max_bytes=4)
            with mock.patch.object(G2.os.path, "samestat", return_value=False):
                with self.assertRaises(G2.EvidenceError):
                    G2._read_regular_bounded(body, max_bytes=8)

    def test_git_timeout_is_generic_and_does_not_raise(self) -> None:
        with mock.patch.object(
            G2.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired("git", 1),
        ):
            self.assertIsNone(G2._private_path_is_allowed(ROOT / "tools" / "evidence"))

    def test_tracked_harness_must_equal_index_and_committed_head(self) -> None:
        tools_root = ROOT / "tools"
        tools_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="tracked-harness-", dir=tools_root) as temp:
            bundle = Path(temp)
            pin = self.write_harness(bundle, "print('{}', end='')\n")

            def blob(_path: Path, revision: str) -> bytes:
                payload = pin.script_path.read_bytes()
                return payload if revision == "index" else payload + b"# dirty\n"

            with mock.patch.object(G2, "_tracked_repository_file", return_value=True), mock.patch.object(
                G2, "_tracked_blob", side_effect=blob
            ):
                transcript, errors = G2.execute_pinned_harness(
                    pin, {}, bundle, require_tracked=True
                )
            self.assertIsNone(transcript)
            self.assertEqual(
                errors,
                ["private evidence: pinned harness differs from its committed blob"],
            )

    def test_staged_harness_swap_after_precheck_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="g2-staged-swap-") as temp:
            bundle = Path(temp)
            pin = self.write_harness(bundle, "print('{}', end='')\n")
            original = G2._read_regular_bounded
            staged_reads = 0

            def swapped(path: Path, **kwargs: object) -> bytes:
                nonlocal staged_reads
                payload = original(path, **kwargs)
                if Path(path).parent.name.startswith("g2-harness-"):
                    staged_reads += 1
                    if staged_reads == 2:
                        return payload + b"# swapped"
                return payload

            with mock.patch.object(G2, "_read_regular_bounded", side_effect=swapped):
                transcript, errors = G2.execute_pinned_harness(
                    pin, {}, bundle, require_tracked=False
                )
            self.assertIsNone(transcript)
            self.assertEqual(
                errors,
                ["private evidence: staged harness changed during execution"],
            )

    def test_path_shadow_cannot_select_git_trust_anchor(self) -> None:
        with tempfile.TemporaryDirectory(prefix="g2-shadow-git-") as temp:
            fake = Path(temp) / ("git.exe" if G2.os.name == "nt" else "git")
            fake.write_bytes(b"fake git")
            with mock.patch.dict(G2.os.environ, {"PATH": temp}):
                selected = G2._fixed_git()
            self.assertIsNotNone(selected)
            assert selected is not None
            self.assertNotEqual(selected.resolve(), fake.resolve())


if __name__ == "__main__":
    unittest.main()
