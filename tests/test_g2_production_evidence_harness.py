from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import copy
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_PATH = ROOT / "scripts" / "g2_production_evidence_harness.py"
VALIDATOR_PATH = ROOT / "scripts" / "validate_g2_private_evidence.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PRODUCTION = load_module("g2_production_evidence_harness", PRODUCTION_PATH)
VALIDATOR = load_module("validate_g2_private_evidence_production", VALIDATOR_PATH)


def canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def named_digest(name: str) -> str:
    return digest(name.encode("utf-8"))


class G2ProductionHarnessTests(unittest.TestCase):
    harness_sha256 = digest(PRODUCTION_PATH.read_bytes())

    def observation_identity(self, kind: str, case_id: str, subject: str) -> dict[str, object]:
        return {
            "schema_version": 1,
            "kind": kind,
            "case_id": case_id,
            "subject_sha256": subject,
        }

    def build_attestation(self, mapping) -> dict[str, object]:
        provenance = PRODUCTION.PRODUCER_SOURCE_PROVENANCE[mapping]
        return {
            "schema_version": 1,
            "kind": "jfg-g2-producer-build-attestation",
            "compiler_id": "clang-cl-22.1.8",
            "compiler_sha256": named_digest("toolchain"),
            "cmake_generator": "Ninja",
            "cmake_configuration": "Release",
            "cmake_defines": [
                "JFG_ENABLE_GENERATED_CODE=ON",
                "JFG_BUILD_G2_PRODUCERS=ON",
            ],
            "producer_compile_flags": ["/std:c++20", "/O2", "/WX"],
            "generated_compile_flags": ["/O2", "/WX"],
            "private_generated_closure_sha256": named_digest("private-generated-closure"),
            "tracked_dependency_closure_sha256": provenance["tracked_closure_sha256"],
            "reviewed_commit": provenance["reviewed_commit"],
            "reviewed_tree": provenance["reviewed_tree"],
        }

    def source_derivation(self, mapping, source_input, case_digest) -> dict[str, object]:
        provenance = PRODUCTION.PRODUCER_SOURCE_PROVENANCE[mapping]
        return {
            "schema_version": 1,
            "kind": "jfg-g2-source-derivation",
            "supported_input_sha256": source_input,
            "bounded_case_sha256": case_digest,
            "adapter_id": provenance["adapter_id"],
            "adapter_version": provenance["adapter_version"],
            "producer_source_path": provenance["source_path"],
            "producer_source_sha256": provenance["source_sha256"],
            "producer_source_revision": provenance["reviewed_commit"],
            "producer_tree_revision": provenance["reviewed_tree"],
            "tracked_dependency_closure_sha256": provenance["tracked_closure_sha256"],
            "build_system": provenance["build_system"],
            "build_recipe_id": provenance["build_recipe_id"],
            "build_target": provenance["build_target"],
            "build_attestation": self.build_attestation(mapping),
        }

    def overlay_observation(self, case_id: str, subject: str) -> dict[str, object]:
        observation = self.observation_identity(
            "jfg-g2-overlay-lifecycle-observation", case_id, subject
        )
        events = [
            "load-begin",
            "copy-complete",
            "bss-cleared",
            "relocation-applied",
            "cache-invalidated",
            "module-published",
            "callback-enter",
            "callback-reentry-rejected",
            "callback-complete",
            "lookup",
            "unpublish",
            "dependency-invalidated",
            "unload-complete",
            "dependency-rebound",
            "stale-token-rejected",
            "reload-verified",
            "callback-failure-rolled-back",
        ]
        observation.update(
            {
                "events": [
                    {"sequence": index, "kind": kind, "generation": 1 if index < 14 else 2}
                    for index, kind in enumerate(events, 1)
                ],
                "relocations": [
                    {
                        "site_id": f"site-{index}",
                        "class": kind,
                        "generation": 1,
                        "write_count": 1,
                    }
                    for index, kind in enumerate(
                        ("full-word", "jump-target", "hi16", "lo16"), 1
                    )
                ],
                "lifetimes": [
                    {
                        "generation": generation,
                        "mapping_sha256": named_digest("mapping"),
                        "state_sha256": named_digest("state"),
                    }
                    for generation in (1, 2)
                ],
                "memory_checks": [
                    {
                        "phase": "copy",
                        "byte_count": 16,
                        "observed_sha256": named_digest("copy"),
                        "expected_sha256": named_digest("copy"),
                        "zero_byte_count": 0,
                    },
                    {
                        "phase": "bss-clear",
                        "byte_count": 16,
                        "observed_sha256": named_digest("zero"),
                        "expected_sha256": named_digest("expected-zero"),
                        "zero_byte_count": 16,
                    },
                    {
                        "phase": "reload",
                        "byte_count": 16,
                        "observed_sha256": named_digest("reload"),
                        "expected_sha256": named_digest("reload"),
                        "zero_byte_count": 0,
                    },
                ],
            }
        )
        return observation

    def rsp_observation(self, case_id: str, subject: str) -> dict[str, object]:
        observation = self.observation_identity(
            "jfg-g2-rsp-program-observation", case_id, subject
        )
        rows = (
            ("graphics-representative", "graphics", "executable", "rsp-graphics"),
            ("audio-primary", "audio-primary", "executable", "rsp-audio-primary"),
            ("audio-secondary", "audio-secondary", "unsupported-with-fallback", "rsp-audio-secondary"),
            ("boot-loader", "other", "empty", "rsp-other"),
        )
        observation.update(
            {
                "programs": [
                    {
                        "program_id": program_id,
                        "family": family,
                        "generated_entry_count": 0,
                        "classification_evidence_sha256": (
                            PRODUCTION.RSP_MANIFEST_EVIDENCE_SHA256
                            if program_id == "boot-loader"
                            else named_digest(family)
                        ),
                    }
                    for program_id, family, _, _ in rows
                ],
                "overlay_slots": [
                    {
                        "slot_id": f"slot-{index}",
                        "program_id": program_id,
                        "classification": (
                            classification
                        ),
                        "owner_id": owner,
                        "estimate_class": "small",
                        "evidence_sha256": (
                            PRODUCTION.RSP_MANIFEST_EVIDENCE_SHA256
                            if program_id == "boot-loader"
                            else named_digest(family)
                        ),
                    }
                    for index, (program_id, family, classification, owner) in enumerate(rows, 1)
                ],
                "native_probes": [
                    {
                        "program_id": program_id,
                        "probe_kind": "classification-only",
                        "entry_count": 0,
                        "broker_access_count": 0,
                        "completion_count": 0,
                        "program_exit_code": 0,
                    }
                    for program_id, _, _, _ in rows
                ],
            }
        )
        return observation

    def trap_observation(self, case_id: str, subject: str) -> dict[str, object]:
        observation = self.observation_identity(
            "jfg-g2-runtime-trap-observation", case_id, subject
        )
        kinds = (
            "cpu-break",
            "cpu-syscall",
            "switch-bounds",
            "boot-self-check",
            "dangling-jump-workaround",
            "checksum",
            "anti-tamper",
        )
        observation.update(
            {
                "candidate_counts": {kind: 1 for kind in kinds},
                "semantic_result_sha256": named_digest("runtime-traps-semantic"),
                "records": [
                    {
                        "site_id": f"site-{index}",
                        "kind": kind,
                        "reachability": "reachable",
                        "disposition": "abort",
                        "owner_id": "runtime-owner",
                        "estimate_class": "small",
                        "observed_hit_count": 1,
                        "mitigation_invocation_count": 1,
                        "native_trace_sha256": named_digest(f"native-{kind}"),
                        "oracle_trace_sha256": named_digest(f"oracle-{kind}"),
                        "static_review_sha256": None,
                    }
                    for index, kind in enumerate(kinds, 1)
                ],
            }
        )
        return observation

    def test_runtime_trap_semantic_result_is_required(self) -> None:
        subject = named_digest("runtime-trap-subject")
        observation = self.trap_observation("runtime-trap-case", subject)
        observation.pop("semantic_result_sha256")
        with self.assertRaises(PRODUCTION.HarnessReject):
            PRODUCTION.validate_traps(
                observation,
                {"case_id": "runtime-trap-case", "subject_sha256": subject},
            )

    def write_request(
        self,
        bundle: Path,
        requirement: str,
        evidence_class: str,
        observation_factory,
    ) -> dict[str, object]:
        mapping = (requirement, evidence_class)
        policy_id = PRODUCTION.MAPPING_IDS[mapping]
        root = bundle / "production" / policy_id
        root.mkdir(parents=True)
        case_id = f"{requirement}-case"
        case_payload = b"bounded-private-case-input"
        subject = digest(case_payload)
        observation = observation_factory(case_id, subject)
        observation_payload = canonical(observation)
        probe_payload = b"MZ" + b"\x00".join(PRODUCTION.PROBE_MARKERS[mapping])
        pins = {
            "jfg_decomp_commit": named_digest("jfg")[:40],
            "n64recomp_commit": named_digest("recomp")[:40],
            "supported_input_id": "jfg-us-retail",
            "input_rom_sha256": named_digest("rom"),
            "dependency_lock_sha256": named_digest("lock"),
            "architecture_decision_sha256": named_digest("decision"),
        }
        environment = {
            "environment_id": "windows-clang",
            "platform_id": "windows",
            "architecture_id": "x64",
            "toolchain_sha256": named_digest("toolchain"),
        }
        execution: dict[str, object] = {
            "id": f"execution-{requirement}",
            "evidence_class": evidence_class,
            "harness_id": policy_id,
            "harness_sha256": self.harness_sha256,
            "case_id": case_id,
            "subject_sha256": subject,
            "source_input_sha256": pins["input_rom_sha256"],
            "pins_sha256": digest(canonical(pins)),
            "environment": environment,
            "environment_sha256": digest(canonical(environment)),
            "input_set_sha256": "",
            "output_set_sha256": "",
            "artifact_set_sha256": "",
            "result_sha256": "",
            "observed_exit_code": 0,
            "passed": True,
            "artifacts": [],
        }
        config = {
            "schema_version": 1,
            "kind": "jfg-g2-production-case",
            "requirement_id": requirement,
            "evidence_class": evidence_class,
            "case_id": case_id,
            "subject_sha256": subject,
            "source_input_sha256": pins["input_rom_sha256"],
            "observation_sha256": digest(observation_payload),
            "policy_id": policy_id,
        }
        if mapping in PRODUCTION.PRODUCER_SOURCE_PROVENANCE:
            config["source_derivation"] = self.source_derivation(
                mapping, pins["input_rom_sha256"], subject
            )
        if mapping == ("cpu-sections", "private-g3-compiler-product-binding"):
            config["g3_compiler_id"] = observation.get("compiler_id")
            config["g3_compiler_executable_sha256"] = observation.get(
                "compiler_executable_sha256"
            )
        files = {
            "case.json": canonical(config),
            "case-input.bin": case_payload,
            "subject-probe.exe": probe_payload,
            "observation.json": observation_payload,
        }
        roles = {
            "case.json": "configuration",
            "case-input.bin": "input",
            "subject-probe.exe": "input",
            "observation.json": "output",
        }
        artifacts = []
        for name in ("case.json", "case-input.bin", "subject-probe.exe", "observation.json"):
            (root / name).write_bytes(files[name])
            artifacts.append(
                {
                    "path": f"production/{policy_id}/{name}",
                    "role": roles[name],
                    "sha256": digest(files[name]),
                }
            )
        input_records = artifacts[:3]
        output_records = artifacts[3:]
        execution["input_set_sha256"] = digest(canonical(input_records))
        execution["output_set_sha256"] = digest(canonical(output_records))
        result = {
            "schema_version": 1,
            "kind": "jfg-g2-execution-result",
            "execution_id": execution["id"],
            "requirement_id": requirement,
            "evidence_class": evidence_class,
            "harness_id": policy_id,
            "harness_sha256": self.harness_sha256,
            "case_id": case_id,
            "subject_sha256": subject,
            "source_input_sha256": pins["input_rom_sha256"],
            "pins_sha256": execution["pins_sha256"],
            "environment_sha256": execution["environment_sha256"],
            "input_set_sha256": execution["input_set_sha256"],
            "output_set_sha256": execution["output_set_sha256"],
            "observed_exit_code": 0,
            "passed": True,
        }
        result_payload = canonical(result)
        (root / "result.json").write_bytes(result_payload)
        artifacts.append(
            {
                "path": f"production/{policy_id}/result.json",
                "role": "result",
                "sha256": digest(result_payload),
            }
        )
        execution["result_sha256"] = digest(result_payload)
        execution["artifacts"] = artifacts
        execution["artifact_set_sha256"] = digest(canonical(artifacts))
        return {
            "schema_version": 1,
            "kind": "jfg-g2-harness-request",
            "pins": pins,
            "execution": execution,
            "requirement_id": requirement,
        }

    def run_production(self, bundle: Path, request: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [os.sys.executable, "-I", str(PRODUCTION_PATH)],
            cwd=bundle,
            input=canonical(request),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=20,
        )

    def rebind_probe(
        self,
        bundle: Path,
        request: dict[str, object],
        probe_payload: bytes,
    ) -> None:
        execution = request["execution"]
        assert isinstance(execution, dict)
        artifacts = execution["artifacts"]
        assert isinstance(artifacts, list)
        probe_record = next(
            item
            for item in artifacts
            if isinstance(item, dict)
            and str(item.get("path", "")).endswith("subject-probe.exe")
        )
        probe_path = bundle.joinpath(*Path(str(probe_record["path"])).parts)
        probe_path.write_bytes(probe_payload)
        probe_record["sha256"] = digest(probe_payload)
        input_records = [
            item
            for item in artifacts
            if isinstance(item, dict) and item.get("role") in {"configuration", "input", "decision"}
        ]
        execution["input_set_sha256"] = digest(canonical(input_records))
        result_record = next(
            item
            for item in artifacts
            if isinstance(item, dict) and item.get("role") == "result"
        )
        result = VALIDATOR._result_expectation(execution, str(request["requirement_id"]))
        result_payload = canonical(result)
        result_path = bundle.joinpath(*Path(str(result_record["path"])).parts)
        result_path.write_bytes(result_payload)
        result_record["sha256"] = digest(result_payload)
        execution["result_sha256"] = digest(result_payload)
        execution["artifact_set_sha256"] = digest(canonical(artifacts))

    def test_internally_consistent_parser_only_records_cannot_pass(self) -> None:
        cases = (
            (
                "overlay-lifecycle",
                "private-native-execution",
                self.overlay_observation,
            ),
            ("rsp-programs", "private-native-execution", self.rsp_observation),
            ("runtime-traps", "private-native-execution", self.trap_observation),
        )
        for requirement, evidence_class, factory in cases:
            with self.subTest(requirement=requirement), tempfile.TemporaryDirectory() as temp:
                bundle = Path(temp)
                request = self.write_request(
                    bundle, requirement, evidence_class, factory
                )
                result = self.run_production(bundle, request)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")
                self.assertEqual(result.stderr, b"")

    def test_rsp_records_are_cross_bound_by_program_and_classification(self) -> None:
        subject = named_digest("rsp-subject")
        observation = self.rsp_observation("rsp-case", subject)
        execution = {"case_id": "rsp-case", "subject_sha256": subject}
        PRODUCTION.validate_rsp(observation, execution)

        mutations = (
            ("probe program id", lambda value: value["native_probes"][0].update(program_id="audio-primary")),
            ("generated count", lambda value: value["programs"][0].update(generated_entry_count=2)),
            ("empty requires zero generated", lambda value: value["overlay_slots"][0].update(classification="empty")),
            ("classification cannot claim an exit", lambda value: value["native_probes"][2].update(program_exit_code=7)),
            ("classification only requires no accesses", lambda value: (
                value["programs"][0].update(generated_entry_count=0),
                value["overlay_slots"][0].update(classification="empty"),
                value["native_probes"][0].update(probe_kind="classification-only", entry_count=0, broker_access_count=1, completion_count=0, program_exit_code=0),
            )),
        )
        for name, mutate in mutations:
            with self.subTest(name=name):
                altered = copy.deepcopy(observation)
                mutate(altered)
                with self.assertRaises(PRODUCTION.HarnessReject):
                    PRODUCTION.validate_rsp(altered, execution)

        empty = copy.deepcopy(observation)
        empty["programs"][0]["generated_entry_count"] = 0
        empty["overlay_slots"][0]["classification"] = "empty"
        empty["native_probes"][0].update(
            probe_kind="classification-only",
            entry_count=0,
            broker_access_count=0,
            completion_count=0,
            program_exit_code=0,
        )
        with self.assertRaises(PRODUCTION.HarnessReject):
            PRODUCTION.validate_rsp(empty, execution)

    def test_pinned_hardcoded_and_echo_executables_fail_fresh_nonce_protocol(self) -> None:
        compiler = ROOT / "tools" / "build" / "llvm-22.1.8" / "bin" / "clang++.exe"
        if not compiler.is_file():
            located = shutil.which("clang++") or shutil.which("g++")
            if located is None:
                self.skipTest("a C++ compiler is unavailable for the adversarial producer")
            compiler = Path(located)
        with tempfile.TemporaryDirectory() as temp:
            bundle = Path(temp)
            request = self.write_request(
                bundle,
                "overlay-lifecycle",
                "private-native-execution",
                self.overlay_observation,
            )
            execution = request["execution"]
            assert isinstance(execution, dict)
            artifacts = execution["artifacts"]
            assert isinstance(artifacts, list)
            observation_record = next(
                item
                for item in artifacts
                if isinstance(item, dict) and str(item.get("path", "")).endswith("observation.json")
            )
            observation_path = bundle.joinpath(*Path(str(observation_record["path"])).parts)
            observation_text = observation_path.read_text(encoding="utf-8")
            marker_text = " ".join(
                marker.decode("ascii")
                for marker in PRODUCTION.PROBE_MARKERS[
                    ("overlay-lifecycle", "private-native-execution")
                ]
            )
            source = bundle / "hardcoded-producer.cpp"
            source.write_text(
                "#include <iostream>\n"
                "#include <string_view>\n"
                f'[[maybe_unused]] static const char markers[] = "{marker_text}";\n'
                "int main(int argc, char** argv) {\n"
                "  if (argc != 5 || std::string_view(argv[1]) != \"--g2-evidence-probe\") return 2;\n"
                f'  std::cout << R"G2({observation_text})G2";\n'
                "  return markers[0] == 0 ? 3 : 0;\n"
                "}\n",
                encoding="utf-8",
            )
            executable = bundle / "hardcoded-producer.exe"
            compile_result = subprocess.run(
                [str(compiler), "-std=c++20", "-O0", str(source), "-o", str(executable)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=60,
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr.decode(errors="replace"))
            execution = request["execution"]
            assert isinstance(execution, dict)
            artifacts = execution["artifacts"]
            assert isinstance(artifacts, list)
            probe_record = next(
                item
                for item in artifacts
                if isinstance(item, dict)
                and str(item.get("path", "")).endswith("subject-probe.exe")
            )
            case_record = next(
                item
                for item in artifacts
                if isinstance(item, dict)
                and str(item.get("path", "")).endswith("case-input.bin")
            )
            case_path = bundle.joinpath(*Path(str(case_record["path"])).parts)

            def rejected_probe(probe: Path) -> None:
                probe_payload = probe.read_bytes()
                self.rebind_probe(bundle, request, probe_payload)
                previous = Path.cwd()
                os.chdir(bundle)
                try:
                    with mock.patch.dict(
                        PRODUCTION.PRODUCER_BINARY_SHA256,
                        {
                            ("overlay-lifecycle", "private-native-execution"): digest(
                                probe_payload
                            )
                        },
                        clear=True,
                    ), mock.patch.dict(
                        PRODUCTION.PRODUCER_BUILD_ATTESTATION,
                        {
                            ("overlay-lifecycle", "private-native-execution"):
                                self.build_attestation(("overlay-lifecycle", "private-native-execution"))
                        },
                        clear=True,
                    ), mock.patch.object(
                        PRODUCTION, "verify_staging_root", return_value=None
                    ):
                        with self.assertRaises(PRODUCTION.HarnessReject):
                            PRODUCTION.run_subject_probe(
                                execution,
                                "overlay-lifecycle",
                                "private-native-execution",
                                probe_record,
                                probe_payload,
                                case_path.read_bytes(),
                                observation_text.encode("utf-8"),
                                {"source_derivation": self.source_derivation(
                                    ("overlay-lifecycle", "private-native-execution"),
                                    execution["source_input_sha256"],
                                    execution["subject_sha256"],
                                )},
                            )
                finally:
                    os.chdir(previous)

            rejected_probe(executable)

            source.write_text(
                "#include <fstream>\n"
                "#include <iostream>\n"
                "#include <iterator>\n"
                "#include <string>\n"
                f'[[maybe_unused]] static const char markers[] = "{marker_text}";\n'
                "int main(int argc, char**) {\n"
                "  if (argc != 5 || markers[0] == 0) return 2;\n"
                "  std::ifstream input(\"case-input.bin\", std::ios::binary);\n"
                "  std::cout << input.rdbuf();\n"
                "  return input && std::cout ? 0 : 3;\n"
                "}\n",
                encoding="utf-8",
            )
            echo_executable = bundle / "echo-producer.exe"
            echo_compile = subprocess.run(
                [
                    str(compiler),
                    "-std=c++20",
                    "-O0",
                    str(source),
                    "-o",
                    str(echo_executable),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=60,
            )
            self.assertEqual(
                echo_compile.returncode,
                0,
                echo_compile.stderr.decode(errors="replace"),
            )
            rejected_probe(echo_executable)

    def test_assertion_only_observation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            bundle = Path(temp)
            request = self.write_request(
                bundle,
                "overlay-lifecycle",
                "private-native-execution",
                lambda case_id, subject: {
                    **self.observation_identity("jfg-g2-overlay-lifecycle-observation", case_id, subject),
                    "passed": True,
                },
            )
            result = self.run_production(bundle, request)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, b"")

    def test_subject_executes_from_verified_staged_copy(self) -> None:
        mapping = ("overlay-lifecycle", "private-native-execution")
        policy_id = PRODUCTION.MAPPING_IDS[mapping]
        with tempfile.TemporaryDirectory() as temp:
            bundle = Path(temp)
            root = bundle / "production" / policy_id / "overlay-exec"
            root.mkdir(parents=True)
            original = root / "subject-probe.exe"
            payload = b"MZ" + b"\x00".join(PRODUCTION.PROBE_MARKERS[mapping])
            original.write_bytes(payload)
            case_payload = b"case"
            observation = canonical({"observation": "fixed"})
            nonce = "12" * 32
            response = canonical(
                {
                    "execution_nonce": nonce,
                    "observation": {"observation": "fixed"},
                }
            )
            record = {
                "path": f"production/{policy_id}/overlay-exec/subject-probe.exe",
                "role": "input",
                "sha256": digest(payload),
            }
            execution = {
                "id": "overlay-exec",
                "artifact_set_sha256": named_digest("artifacts"),
                "case_id": "overlay-case",
                "environment_sha256": named_digest("environment"),
                "input_set_sha256": named_digest("inputs"),
                "output_set_sha256": named_digest("outputs"),
                "subject_sha256": digest(case_payload),
                "source_input_sha256": named_digest("source"),
                "environment": {"toolchain_sha256": named_digest("toolchain")},
            }
            config = self.source_derivation(
                mapping, execution["source_input_sha256"], execution["subject_sha256"]
            )

            class Process:
                def __init__(self):
                    self.stdout = io.BytesIO(response)
                    self.stderr = io.BytesIO()

                def wait(self, timeout=None):
                    return 0

                def kill(self):
                    return None

            def fixed_command(path, staged_payload, arguments):
                self.assertNotEqual(path, original)
                self.assertEqual(path.read_bytes(), payload)
                self.assertEqual((path.parent / "case-input.bin").read_bytes(), case_payload)
                self.assertEqual(
                    arguments,
                    [
                        "--g2-evidence-probe", nonce, mapping[0], mapping[1],
                        "--case-id", execution["case_id"], "--subject-sha256",
                        execution["subject_sha256"],
                    ],
                )
                original.write_bytes(b"swapped-after-verified-read")
                return ["fixed-subject"]

            previous = Path.cwd()
            os.chdir(bundle)
            try:
                with mock.patch.dict(
                    PRODUCTION.PRODUCER_BINARY_SHA256,
                    {mapping: digest(payload)},
                    clear=True,
                ), mock.patch.dict(
                    PRODUCTION.PRODUCER_BUILD_ATTESTATION,
                    {mapping: self.build_attestation(mapping)},
                    clear=True,
                ), mock.patch.object(
                    PRODUCTION, "verify_staging_root", return_value=None
                ), mock.patch.object(
                    PRODUCTION.secrets, "token_hex", return_value=nonce
                ), mock.patch.object(
                    PRODUCTION, "product_command", side_effect=fixed_command
                ), mock.patch.object(
                    PRODUCTION.subprocess, "Popen", return_value=Process()
                ):
                    PRODUCTION.run_subject_probe(
                        execution,
                        mapping[0],
                        mapping[1],
                        record,
                        payload,
                        case_payload,
                        observation,
                        {"source_derivation": config},
                    )
            finally:
                os.chdir(previous)
            self.assertEqual(original.read_bytes(), b"swapped-after-verified-read")

    def test_source_derivation_rejects_unbound_case_or_source_revision(self) -> None:
        mapping = ("overlay-lifecycle", "private-native-execution")
        execution = {
            "source_input_sha256": named_digest("supported-input"),
            "subject_sha256": named_digest("bounded-case"),
            "environment": {"toolchain_sha256": named_digest("toolchain")},
        }
        derivation = self.source_derivation(
            mapping, execution["source_input_sha256"], execution["subject_sha256"]
        )
        with mock.patch.dict(
            PRODUCTION.PRODUCER_BUILD_ATTESTATION,
            {mapping: self.build_attestation(mapping)},
            clear=True,
        ):
            PRODUCTION.validate_source_derivation(
                mapping, {"source_derivation": derivation}, execution
            )
        for field, replacement in (
            ("bounded_case_sha256", named_digest("different-case")),
            ("supported_input_sha256", named_digest("different-input")),
            ("producer_source_revision", named_digest("different-revision")),
            ("build_target", "unreviewed-target"),
        ):
            with self.subTest(field=field):
                altered = dict(derivation)
                altered[field] = replacement
                with mock.patch.dict(
                    PRODUCTION.PRODUCER_BUILD_ATTESTATION,
                    {mapping: self.build_attestation(mapping)},
                    clear=True,
                ), self.assertRaises(PRODUCTION.HarnessReject):
                    PRODUCTION.validate_source_derivation(
                        mapping, {"source_derivation": altered}, execution
                    )
        with self.assertRaises(PRODUCTION.HarnessReject):
            PRODUCTION.validate_source_derivation(mapping, {}, execution)
        with self.assertRaises(PRODUCTION.HarnessReject):
            PRODUCTION.validate_source_derivation(
                mapping, {"source_derivation": derivation}, execution
            )
        altered_build = dict(self.build_attestation(mapping))
        altered_build["producer_compile_flags"] = ["/unreviewed"]
        altered_derivation = dict(derivation)
        altered_derivation["build_attestation"] = altered_build
        with mock.patch.dict(
            PRODUCTION.PRODUCER_BUILD_ATTESTATION,
            {mapping: self.build_attestation(mapping)},
            clear=True,
        ), self.assertRaises(PRODUCTION.HarnessReject):
            PRODUCTION.validate_source_derivation(
                mapping, {"source_derivation": altered_derivation}, execution
            )

    def test_staged_subject_or_case_swap_after_command_selection_is_rejected(self) -> None:
        mapping = ("overlay-lifecycle", "private-native-execution")
        policy_id = PRODUCTION.MAPPING_IDS[mapping]
        with tempfile.TemporaryDirectory() as temp:
            bundle = Path(temp)
            source_root = bundle / "production" / policy_id / "overlay-exec"
            source_root.mkdir(parents=True)
            payload = b"MZ" + b"\x00".join(PRODUCTION.PROBE_MARKERS[mapping])
            original = source_root / "subject-probe.exe"
            original.write_bytes(payload)
            case_payload = b"case"
            record = {
                "path": f"production/{policy_id}/overlay-exec/subject-probe.exe",
                "role": "input",
                "sha256": digest(payload),
            }
            execution = {
                "id": "overlay-exec",
                "case_id": "overlay-case",
                "subject_sha256": digest(case_payload),
                "source_input_sha256": named_digest("source"),
                "environment": {"toolchain_sha256": named_digest("toolchain")},
            }
            config = {"source_derivation": self.source_derivation(
                mapping, execution["source_input_sha256"], execution["subject_sha256"]
            )}
            response = canonical({"execution_nonce": "34" * 32, "observation": {"fixed": True}})

            for target in ("subject-probe.exe", "case-input.bin"):
                with self.subTest(target=target):
                    class Process:
                        def __init__(self):
                            self.stdout = io.BytesIO(response)
                            self.stderr = io.BytesIO()
                        def wait(self, timeout=None): return 0
                        def kill(self): return None

                    def select_then_swap(path, staged_payload, arguments):
                        (path.parent / target).write_bytes(b"swapped")
                        return ["fixed-subject"]

                    previous = Path.cwd()
                    os.chdir(bundle)
                    try:
                        with mock.patch.dict(PRODUCTION.PRODUCER_BINARY_SHA256, {mapping: digest(payload)}, clear=True), \
                            mock.patch.dict(PRODUCTION.PRODUCER_BUILD_ATTESTATION, {mapping: self.build_attestation(mapping)}, clear=True), \
                            mock.patch.object(PRODUCTION, "verify_staging_root", return_value=None), \
                            mock.patch.object(PRODUCTION.secrets, "token_hex", return_value="34" * 32), \
                            mock.patch.object(PRODUCTION, "product_command", side_effect=select_then_swap), \
                            mock.patch.object(PRODUCTION.subprocess, "Popen", return_value=Process()):
                            with self.assertRaises(PRODUCTION.HarnessReject):
                                PRODUCTION.run_subject_probe(
                                    execution, mapping[0], mapping[1], record, payload,
                                    case_payload, canonical({"fixed": True}), config,
                                )
                    finally:
                        os.chdir(previous)

    def test_modified_tracked_harness_must_equal_index_blob(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tools") as temp:
            harness = Path(temp) / "harness.py"
            payload = b"print('modified')\n"
            harness.write_bytes(payload)
            pin = VALIDATOR.PinnedHarness("test-harness", harness, digest(payload))
            with mock.patch.object(
                VALIDATOR, "_tracked_repository_file", return_value=True
            ), mock.patch.object(
                VALIDATOR,
                "_tracked_blob",
                return_value=b"committed-index-body",
            ):
                transcript, errors = VALIDATOR.execute_pinned_harness(
                    pin, {}, Path(temp), require_tracked=True
                )
            self.assertIsNone(transcript)
            self.assertIn(
                "private evidence: pinned harness differs from its committed blob",
                errors,
            )

    def test_native_oracle_result_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            bundle = Path(temp)
            subject = named_digest("paired-subject")
            source = named_digest("paired-source")

            def execution(evidence_class: str, result_digest: str) -> dict[str, object]:
                prefix = "native" if evidence_class == "private-native-execution" else "oracle"
                field = "output_sha256" if prefix == "native" else "payload_sha256"
                observation = {field: result_digest}
                observation_payload = canonical(observation)
                config = {"observation_sha256": digest(observation_payload)}
                config_path = f"{prefix}-config.json"
                observation_path = f"{prefix}-observation.json"
                (bundle / config_path).write_bytes(canonical(config))
                (bundle / observation_path).write_bytes(observation_payload)
                return {
                    "case_id": "paired-case",
                    "subject_sha256": subject,
                    "source_input_sha256": source,
                    "evidence_class": evidence_class,
                    "artifacts": [
                        {
                            "path": config_path,
                            "role": "configuration",
                            "sha256": digest(canonical(config)),
                        },
                        {
                            "path": observation_path,
                            "role": "output",
                            "sha256": digest(observation_payload),
                        },
                    ],
                }

            requirement = {
                "executions": [
                    execution("private-native-execution", named_digest("native-output")),
                    execution("private-oracle-execution", named_digest("oracle-output")),
                ]
            }
            self.assertEqual(
                VALIDATOR._paired_result_errors("graphics-tasks", requirement, bundle),
                ["private evidence: native/oracle result equality is unbound"],
            )
            shared = named_digest("shared-output")
            requirement["executions"] = [
                execution("private-native-execution", shared),
                execution("private-oracle-execution", shared),
            ]
            self.assertEqual(
                VALIDATOR._paired_result_errors("graphics-tasks", requirement, bundle),
                [],
            )

    def test_runtime_trap_semantic_digest_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            bundle = Path(temp)
            subject = named_digest("trap-paired-subject")
            source = named_digest("trap-paired-source")

            def execution(evidence_class: str, semantic: str) -> dict[str, object]:
                prefix = "native" if evidence_class == "private-native-execution" else "oracle"
                observation = {"semantic_result_sha256": semantic}
                payload = canonical(observation)
                config = {"observation_sha256": digest(payload)}
                config_path = f"{prefix}-config.json"
                output_path = f"{prefix}-observation.json"
                (bundle / config_path).write_bytes(canonical(config))
                (bundle / output_path).write_bytes(payload)
                return {"case_id": "trap-paired-case", "subject_sha256": subject,
                    "source_input_sha256": source, "evidence_class": evidence_class,
                    "artifacts": [
                        {"path": config_path, "role": "configuration", "sha256": digest(canonical(config))},
                        {"path": output_path, "role": "output", "sha256": digest(payload)},
                    ]}

            requirement = {"executions": [
                execution("private-native-execution", named_digest("native-semantic")),
                execution("private-oracle-execution", named_digest("oracle-semantic")),
            ]}
            self.assertEqual(
                VALIDATOR._paired_result_errors("runtime-traps", requirement, bundle),
                ["private evidence: native/oracle result equality is unbound"],
            )
            shared = named_digest("shared-semantic")
            requirement["executions"] = [
                execution("private-native-execution", shared),
                execution("private-oracle-execution", shared),
            ]
            self.assertEqual(
                VALIDATOR._paired_result_errors("runtime-traps", requirement, bundle), [],
            )

    @unittest.skipUnless(os.name == "nt", "Windows WSL launcher policy")
    def test_shadow_or_reparse_wsl_launcher_is_never_selected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            fake = Path(temp) / "wsl.exe"
            fake.write_bytes(b"MZfake")
            with mock.patch.dict(os.environ, {"PATH": temp}):
                probe = Path(temp) / "subject-probe"
                probe.write_bytes(b"\x7fELFpayload")
                command = PRODUCTION.product_command(
                    probe,
                    b"\x7fELFpayload",
                    ["fixed"],
                )
            # The reviewed launcher is the fixed absolute system WSL boundary;
            # a PATH-shadowed wsl.exe can never be selected.
            self.assertEqual(
                Path(command[0]).resolve(),
                Path("C:/Windows/System32/wsl.exe").resolve(),
            )
            self.assertEqual(command[1:3], ["-d", "Ubuntu-24.04"])
            with self.assertRaises(PRODUCTION.HarnessReject):
                PRODUCTION.product_command(fake, b"MZpayload", ["fixed"])

    def test_reparse_or_unverifiable_staging_root_is_rejected(self) -> None:
        metadata = mock.Mock(st_mode=stat.S_IFDIR | 0o700)
        metadata.st_file_attributes = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        with mock.patch.object(Path, "lstat", return_value=metadata), self.assertRaises(
            PRODUCTION.HarnessReject
        ):
            PRODUCTION.verify_staging_root(Path("unused"))
        if os.name == "nt":
            # A non-reparse exclusively created staging directory is accepted
            # on the reviewed WSL route; anything that is not a directory is
            # still rejected.
            metadata.st_file_attributes = 0
            with mock.patch.object(Path, "lstat", return_value=metadata):
                PRODUCTION.verify_staging_root(Path("unused"))
            regular = mock.Mock(st_mode=stat.S_IFREG | 0o700)
            regular.st_file_attributes = 0
            with mock.patch.object(Path, "lstat", return_value=regular), self.assertRaises(
                PRODUCTION.HarnessReject
            ):
                PRODUCTION.verify_staging_root(Path("unused"))

    def test_partial_stage_writes_are_completed_and_zero_write_rejects(self) -> None:
        calls: list[bytes] = []

        def partial(_descriptor: int, payload: bytes) -> int:
            calls.append(payload)
            return min(2, len(payload))

        with mock.patch.object(PRODUCTION.os, "write", side_effect=partial):
            PRODUCTION.write_all(7, b"abcdef")
        self.assertEqual(calls, [b"abcdef", b"cdef", b"ef"])
        with mock.patch.object(PRODUCTION.os, "write", return_value=0), self.assertRaises(
            PRODUCTION.HarnessReject
        ):
            PRODUCTION.write_all(7, b"x")

    def test_strict_owner_attributed_decision_parser(self) -> None:
        accepted = b"# Decision\n\n- Status: Accepted by `TK22-26`\n"
        self.assertTrue(PRODUCTION.accepted_decision(accepted))
        self.assertFalse(PRODUCTION.accepted_decision(b"# Decision\n\n- Status: Accepted\n"))
        self.assertFalse(
            PRODUCTION.accepted_decision(
                accepted + b"```md\n- Status: Accepted by `TK22-26`\n```\n"
            )
        )


if __name__ == "__main__":
    unittest.main()
