from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jsonschema import Draft202012Validator

from scripts.audit_generated_objects import (
    AuditFailure,
    _dumpbin_symbols,
    _is_msvc_compiler_owned_data,
    _nm_symbols,
    _parse_dumpbin_section_auxiliary,
)
from scripts.validate_project import (
    validate_audio_bridge,
    validate_cmake_presets,
    validate_dependency_lock,
    validate_graphics_bridge,
    validate_hashed_requirements,
    load_json,
    validate_phase3_manifests,
    validate_phase4_manifest,
    validate_instance,
    validate_workflow,
)
from scripts.validate_phase4_manifest import validate_public_completion


ROOT = Path(__file__).resolve().parents[1]


class GeneratedObjectAuditPolicyTests(unittest.TestCase):
    def nm_symbols_for(self, role: str, symbol: str, symbol_type: str) -> tuple[
        set[str], set[str], set[str], set[str], set[str]
    ]:
        object_path = ROOT / "tests" / "synthetic-compiler-metadata.o"
        output = f"{object_path}: {symbol} {symbol_type} 00000000 00000008\n"
        with mock.patch(
            "scripts.audit_generated_objects._run_tool", return_value=output
        ):
            return tuple(values[0] for values in _nm_symbols(
                "nm", [object_path], role
            ))

    def test_gnu_exception_metadata_is_narrow_runtime_metadata(self) -> None:
        for symbol, symbol_type in (
            ("DW.ref.__gxx_personality_v0", "V"),
            ("__clang_call_terminate", "W"),
        ):
            with self.subTest(symbol=symbol, symbol_type=symbol_type):
                functions, data, undefined, weak_functions, weak_data = (
                    self.nm_symbols_for("runtime-bridge", symbol, symbol_type)
                )
                self.assertEqual(
                    (functions, data, undefined, weak_functions, weak_data),
                    (set(), set(), set(), set(), set()),
                )

    def test_gnu_exception_personality_near_matches_remain_weak_audit_symbols(self) -> None:
        for role, symbol, symbol_type, expected_weak_kind in (
            ("runtime-bridge", "DW.ref.__gxx_personality_v0_extra", "V", "data"),
            ("runtime-bridge", "jfg_runtime_bridge", "V", "data"),
            ("runtime-bridge", "DW.ref.__gxx_personality_v0", "W", "function"),
            ("runtime-bridge", "__clang_call_terminate_extra", "W", "function"),
            ("runtime-bridge", "__clang_call_terminate", "V", "data"),
            ("baseline-body", "DW.ref.__gxx_personality_v0", "V", "data"),
            ("baseline-body", "__clang_call_terminate", "W", "function"),
        ):
            with self.subTest(role=role, symbol=symbol, symbol_type=symbol_type):
                _functions, _data, _undefined, weak_functions, weak_data = (
                    self.nm_symbols_for(role, symbol, symbol_type)
                )
                self.assertEqual(
                    weak_functions if expected_weak_kind == "function" else weak_data,
                    {symbol},
                )

    def dumpbin_data_for(self, flags: int, duplicate: bool = False) -> set[str]:
        object_path = ROOT / "tests" / "synthetic-compiler-data.obj"
        symbol_line = "003 00000000 SECT1 notype External | _Fenv1\n"
        output = (
            f"Dump of file {object_path}\n"
            "SECTION HEADER #1\n"
            "  .rdata name\n"
            "       8 size of raw data\n"
            "       0 number of relocations\n"
            f"{flags:X} flags\n"
            "COFF SYMBOL TABLE\n"
            "001 00000000 SECT1 notype Static | .rdata\n"
            "    Section length 8, #relocs 0, #linenums 0, checksum 0, "
            "selection 2 (pick any)\n"
            + symbol_line
            + (symbol_line if duplicate else "")
        )
        with mock.patch(
            "scripts.audit_generated_objects._run_tool", return_value=output
        ):
            return _dumpbin_symbols(
                "dumpbin",
                [object_path],
                "baseline-body",
                "MSVC",
            )[1][0]

    def assert_compiler_data(self, symbol: str, size: int) -> None:
        self.assertTrue(
            _is_msvc_compiler_owned_data(
                symbol,
                "baseline-body",
                "MSVC",
                "External",
                ".rdata",
                size,
                0,
                2,
                0x40001040,
            )
        )

    def test_msvc_compiler_data_requires_exact_coff_shape(self) -> None:
        self.assert_compiler_data("_Fenv1", 8)
        self.assert_compiler_data("__real@3f800000", 4)
        self.assert_compiler_data("__real@3ff0000000000000", 8)
        self.assert_compiler_data("__xmm@00000000000000000000000000000000", 16)
        self.assert_compiler_data(
            "??_C@_1DC@GLOLEHIO@?$AAc?$AAt?$AAx?$AA?$AA@",
            0x32,
        )
        self.assert_compiler_data(
            "??_C@_1DG@OEIIEOC@?$AAc?$AAt?$AAx?$AA?$AA@",
            0x36,
        )

    def test_dumpbin_section_lengths_are_hexadecimal(self) -> None:
        self.assertEqual(
            _parse_dumpbin_section_auxiliary(
                "Section length 13, #relocs 0, #linenums 0, checksum 0, "
                "selection 2 (pick any)"
            ),
            (19, 0, 2),
        )

    def test_dumpbin_requires_read_only_nonexecuting_characteristics(self) -> None:
        self.assertEqual(self.dumpbin_data_for(0x40001040), set())
        self.assertEqual(self.dumpbin_data_for(0xC0001040), {"_Fenv1"})
        self.assertEqual(self.dumpbin_data_for(0x60001040), {"_Fenv1"})

    def test_duplicate_compiler_header_data_is_rejected(self) -> None:
        with self.assertRaisesRegex(AuditFailure, "duplicate-compiler-header-data"):
            self.dumpbin_data_for(0x40001040, duplicate=True)

    def test_compiler_data_near_matches_remain_audited(self) -> None:
        for values in (
            ("jfg_Fenv1", "baseline-body", "MSVC", "External", ".rdata", 8, 0, 2, 0x40001040),
            ("_Fenv1", "unknown", "MSVC", "External", ".rdata", 8, 0, 2, 0x40001040),
            ("_Fenv1", "baseline-body", "GNU", "External", ".rdata", 8, 0, 2, 0x40001040),
            ("_Fenv1", "baseline-body", "MSVC", "WeakExternal", ".rdata", 8, 0, 2, 0x40001040),
            ("_Fenv1", "baseline-body", "MSVC", "External", ".data", 8, 0, 2, 0x40001040),
            ("_Fenv1", "baseline-body", "MSVC", "External", ".rdata", 4, 0, 2, 0x40001040),
            ("_Fenv1", "baseline-body", "MSVC", "External", ".rdata", 8, 1, 2, 0x40001040),
            ("_Fenv1", "baseline-body", "MSVC", "External", ".rdata", 8, 0, 5, 0x40001040),
            ("_Fenv1", "baseline-body", "MSVC", "External", ".rdata", 8, 0, 2, 0xC0001040),
            ("_Fenv1", "baseline-body", "MSVC", "External", ".rdata", 8, 0, 2, 0x60001040),
            ("__real@0000000", "baseline-body", "MSVC", "External", ".rdata", 4, 0, 2, 0x40001040),
            ("__real@00000000", "baseline-body", "MSVC", "External", ".rdata", 8, 0, 2, 0x40001040),
            ("__xmm@" + ("0" * 31), "baseline-body", "MSVC", "External", ".rdata", 16, 0, 2, 0x40001040),
            ("??_C@_0BD@AAAAAAAA@fixed_message_txt@$AA@", "baseline-body", "MSVC", "External", ".rdata", 20, 0, 2, 0x40001040),
            ("??_C@_0BD@ZZZZZZZZ@fixed_message_txt@$AA@", "baseline-body", "MSVC", "External", ".rdata", 19, 0, 2, 0x40001040),
            ("??_C@_2BD@AAAAAAAA@fixed_message_txt@$AA@", "baseline-body", "MSVC", "External", ".rdata", 19, 0, 2, 0x40001040),
            ("??_C@_0ABD@AAAAAAAA@fixed_message_txt@$AA@", "baseline-body", "MSVC", "External", ".rdata", 19, 0, 2, 0x40001040),
        ):
            with self.subTest(values=values):
                self.assertFalse(_is_msvc_compiler_owned_data(*values))


class GeneratedWarningPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.warnings = (ROOT / "cmake" / "Warnings.cmake").read_text(
            encoding="utf-8"
        )
        cls.project_policy, generated_and_after = cls.warnings.split(
            "function(jfg_set_generated_warnings target)", 1
        )
        cls.generated_policy = generated_and_after.split("endfunction()", 1)[0]

    def test_generated_msvc_unreachable_suppression_is_narrow(self) -> None:
        self.assertIn("/wd4702", self.generated_policy)
        self.assertNotIn("/wd4702", self.project_policy)

    def test_clang_cl_receives_generated_only_warning_equivalents(self) -> None:
        for warning in (
            "sign-compare",
            "tautological-compare",
            "type-limits",
            "unused-label",
            "unused-parameter",
            "unused-variable",
            "unused-but-set-variable",
        ):
            option = f"/clang:-Wno-{warning}"
            self.assertIn(option, self.generated_policy)
            self.assertNotIn(option, self.project_policy)


class WorkflowPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        lock = json.loads((ROOT / "dependencies.lock.json").read_text(encoding="utf-8"))
        cls.actions = lock["github_actions"]

    def test_repository_workflow_satisfies_policy(self) -> None:
        self.assertEqual(validate_workflow(self.workflow, self.actions), [])

    def test_moving_action_ref_is_rejected(self) -> None:
        modified = self.workflow.replace(
            f"actions/checkout@{self.actions['actions/checkout']}",
            "actions/checkout@v4",
            1,
        )
        errors = validate_workflow(modified, self.actions)
        self.assertTrue(any("not pinned to a full commit" in error for error in errors))

    def test_unknown_action_is_rejected(self) -> None:
        modified = self.workflow.replace(
            "    steps:\n",
            "    steps:\n      - uses: example/unknown@" + ("a" * 40) + "\n",
            1,
        )
        errors = validate_workflow(modified, self.actions)
        self.assertTrue(any("absent from the lock" in error for error in errors))

    def test_unknown_reusable_workflow_job_is_rejected(self) -> None:
        modified = self.workflow + (
            "\n  injected-reusable-job:\n"
            "    uses: example/unknown@" + ("a" * 40) + "\n"
        )
        errors = validate_workflow(modified, self.actions)
        self.assertTrue(any("absent from the lock" in error for error in errors))

    def test_missing_history_gate_is_rejected(self) -> None:
        modified = self.workflow.replace(
            "python scripts/check_repository_hygiene.py --history",
            "python scripts/check_repository_hygiene.py",
        )
        errors = validate_workflow(modified, self.actions)
        self.assertTrue(any("--history" in error for error in errors))

    def test_policy_scans_event_head_instead_of_synthetic_merge(self) -> None:
        modified = self.workflow.replace(
            "          ref: ${{ github.event.pull_request.head.sha || github.sha }}\n",
            "",
            1,
        )
        errors = validate_workflow(modified, self.actions)
        self.assertTrue(any("synthetic merge" in error for error in errors))

    def test_unhashed_install_gate_is_rejected(self) -> None:
        modified = self.workflow.replace(" --require-hashes", "")
        errors = validate_workflow(modified, self.actions)
        self.assertTrue(any("--require-hashes" in error for error in errors))

    def test_release_build_gate_is_rejected_when_removed(self) -> None:
        modified = self.workflow.replace(
            "          cmake --build --preset linux-release\n", "", 1
        )
        errors = validate_workflow(modified, self.actions)
        self.assertTrue(any("linux-release" in error for error in errors))

    def test_windows_debug_and_release_test_gates_cannot_be_removed(self) -> None:
        for configuration in ("Debug", "Release"):
            command = f"python scripts/build_windows.py --config {configuration} --test"
            with self.subTest(configuration=configuration):
                modified = self.workflow.replace(command, command.replace(" --test", ""))
                errors = validate_workflow(modified, self.actions)
                self.assertTrue(any(command in error for error in errors))

    def test_clang_build_gate_is_rejected_when_removed(self) -> None:
        modified = self.workflow.replace(
            "          cmake --build --preset linux-clang\n", "", 1
        )
        errors = validate_workflow(modified, self.actions)
        self.assertTrue(any("linux-clang" in error for error in errors))

    def test_workflow_requires_timeouts_and_concurrency(self) -> None:
        without_timeout = self.workflow.replace("    timeout-minutes: 10\n", "", 1)
        without_concurrency = self.workflow.replace("concurrency:\n", "parallel:\n", 1)
        self.assertTrue(any("timeout" in error for error in validate_workflow(without_timeout, self.actions)))
        self.assertTrue(any("concurrency" in error for error in validate_workflow(without_concurrency, self.actions)))


class DependencyAndBuildPolicyTests(unittest.TestCase):
    def load_phase3_documents(self) -> tuple[object, object, object, object, object]:
        return (
            json.loads((ROOT / "config" / "rsp-task-manifest.json").read_text(encoding="utf-8")),
            json.loads((ROOT / "schemas" / "rsp-task-manifest.schema.json").read_text(encoding="utf-8")),
            json.loads((ROOT / "config" / "runtime-capability-matrix.json").read_text(encoding="utf-8")),
            json.loads((ROOT / "schemas" / "runtime-capability-matrix.schema.json").read_text(encoding="utf-8")),
            json.loads((ROOT / "dependencies.lock.json").read_text(encoding="utf-8")),
        )

    def test_project_validation_runs_phase3_semantic_validators(self) -> None:
        rsp, rsp_schema, runtime, runtime_schema, lock = self.load_phase3_documents()
        self.assertEqual(
            validate_phase3_manifests(rsp, rsp_schema, runtime, runtime_schema, lock),
            [],
        )

        invalid_rsp = copy.deepcopy(rsp)
        invalid_rsp["$schema"] = " ".join(
            ["AA", "BB", "CC", "DD", "EE", "FF"] * 2
        )
        rsp_errors = validate_phase3_manifests(
            invalid_rsp, rsp_schema, runtime, runtime_schema, lock
        )
        self.assertTrue(any(error.startswith("RSP manifest:") for error in rsp_errors))

        invalid_runtime = copy.deepcopy(runtime)
        invalid_runtime["$schema"] = " ".join(
            ["AA", "BB", "CC", "DD", "EE", "FF"] * 2
        )
        runtime_errors = validate_phase3_manifests(
            rsp, rsp_schema, invalid_runtime, runtime_schema, lock
        )
        self.assertTrue(
            any(error.startswith("runtime matrix:") for error in runtime_errors)
        )

    def test_project_validation_runs_phase4_semantic_validator(self) -> None:
        manifest = json.loads(
            (ROOT / "examples" / "phase4-generated-manifest.example.json").read_text(
                encoding="utf-8"
            )
        )
        schema = json.loads(
            (ROOT / "schemas" / "phase4-generated-manifest.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(validate_phase4_manifest(manifest, schema), [])

        invalid = copy.deepcopy(manifest)
        invalid["symbols"]["generated_count"] += 1
        errors = validate_phase4_manifest(invalid, schema)
        self.assertTrue(any(error.startswith("Phase 4 manifest:") for error in errors))

    def test_project_validation_checks_the_tracked_signed_phase4_claim(self) -> None:
        manifest = load_json(ROOT / "evidence" / "phase4-completion.json")
        schema = load_json(ROOT / "schemas" / "phase4-generated-manifest.schema.json")
        self.assertEqual(validate_public_completion(manifest, schema), [])

        invalid = copy.deepcopy(manifest)
        invalid["symbols"]["generated_count"] += 1
        errors = validate_public_completion(invalid, schema)
        self.assertTrue(errors)
        self.assertIn("attestation: completion signature is invalid", errors)

    def test_project_validation_runs_graphics_bridge_semantic_validator(self) -> None:
        manifest = json.loads(
            (ROOT / "config" / "graphics-task-bridge.json").read_text(
                encoding="utf-8"
            )
        )
        schema = json.loads(
            (ROOT / "schemas" / "graphics-task-bridge.schema.json").read_text(
                encoding="utf-8"
            )
        )
        lock = json.loads(
            (ROOT / "dependencies.lock.json").read_text(encoding="utf-8")
        )
        self.assertEqual(validate_graphics_bridge(manifest, schema, lock), [])

        invalid = copy.deepcopy(manifest)
        invalid["decision"]["g2_gate"] = "blocked"
        errors = validate_graphics_bridge(invalid, schema, lock)
        self.assertTrue(any(error.startswith("graphics bridge:") for error in errors))

    def test_project_validation_runs_audio_bridge_semantic_validator(self) -> None:
        manifest = json.loads(
            (ROOT / "config" / "audio-task-bridge.json").read_text(
                encoding="utf-8"
            )
        )
        schema = json.loads(
            (ROOT / "schemas" / "audio-task-bridge.schema.json").read_text(
                encoding="utf-8"
            )
        )
        lock = json.loads(
            (ROOT / "dependencies.lock.json").read_text(encoding="utf-8")
        )
        self.assertEqual(validate_audio_bridge(manifest, schema, lock), [])

        invalid = copy.deepcopy(manifest)
        invalid["evidence"]["secondary_fallback_completion_count"] = 1
        errors = validate_audio_bridge(invalid, schema, lock)
        self.assertTrue(any(error.startswith("audio bridge:") for error in errors))

    def test_shared_json_validation_is_strict_and_does_not_echo_values(self) -> None:
        tools_root = ROOT / "tools"
        with tempfile.TemporaryDirectory(prefix="project-json-", dir=tools_root) as temp:
            directory = Path(temp)
            duplicate = directory / "duplicate.json"
            duplicate.write_text('{"safe": 1, "safe": 2}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate JSON object key"):
                load_json(duplicate)

            nonstandard = directory / "nonstandard.json"
            nonstandard.write_text('{"safe": NaN}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non-standard JSON number"):
                load_json(nonstandard)

            schema = directory / "schema.json"
            schema.write_text(
                json.dumps(
                    {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "type": "object",
                        "additionalProperties": False,
                    }
                ),
                encoding="utf-8",
            )
            hostile = directory / "hostile.json"
            marker = "private_marker_should_not_echo"
            hostile.write_text(json.dumps({marker: marker}), encoding="utf-8")
            errors = validate_instance(hostile, schema)
            self.assertEqual(len(errors), 1)
            self.assertIn("schema contract violation", errors[0])
            self.assertNotIn(marker, errors[0])

    def test_duplicate_dependency_repository_id_is_rejected(self) -> None:
        lock = json.loads(
            (ROOT / "dependencies.lock.json").read_text(encoding="utf-8")
        )
        lock["repositories"].append(copy.deepcopy(lock["repositories"][0]))
        errors = validate_dependency_lock(lock)
        self.assertTrue(any("duplicate dependency repository id" in error for error in errors))

    def test_repository_lock_is_fully_hashed(self) -> None:
        errors = validate_hashed_requirements(
            (ROOT / "requirements-dev.lock.txt").read_text(encoding="utf-8"),
            (ROOT / "requirements-dev.txt").read_text(encoding="utf-8"),
        )
        self.assertEqual(errors, [])

    def test_unhashed_requirement_is_rejected(self) -> None:
        errors = validate_hashed_requirements(
            "--only-binary=:all:\nexample==1.0\n", "example==1.0\n"
        )
        self.assertTrue(any("lacks only SHA-256 hashes" in error for error in errors))

    def test_direct_requirement_version_mismatch_is_rejected(self) -> None:
        errors = validate_hashed_requirements(
            "--only-binary=:all:\n"
            "example==1.0 --hash=sha256:" + ("a" * 64) + "\n",
            "example==2.0\n",
        )
        self.assertTrue(any("version differs from lock" in error for error in errors))

    def test_cmake_preset_schema_must_match_declared_minimum(self) -> None:
        presets = {
            "version": 3,
            "cmakeMinimumRequired": {"major": 3, "minor": 20, "patch": 0},
        }
        errors = validate_cmake_presets(
            "cmake_minimum_required(VERSION 3.20)\n", presets
        )
        self.assertTrue(any("requires a newer CMake" in error for error in errors))


class TaskPacketPathPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        schema = json.loads(
            (ROOT / "schemas" / "task-packet.schema.json").read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(schema)
        cls.validator = Draft202012Validator(schema)
        cls.example = json.loads(
            (ROOT / "examples" / "task-packet.example.json").read_text(
                encoding="utf-8"
            )
        )

    def errors_for(self, candidate: str) -> list[object]:
        instance = copy.deepcopy(self.example)
        instance["scope"]["allowed_files"] = [candidate]
        return list(self.validator.iter_errors(instance))

    def test_normalized_repository_path_is_accepted(self) -> None:
        self.assertEqual(self.errors_for("scripts/validate_project.py"), [])

    def test_non_normalized_or_forbidden_paths_are_rejected(self) -> None:
        candidates = (
            "tools/helper.exe",
            "docs/../tools/helper.exe",
            "./tools/helper.exe",
            "docs\\file.md",
            "/absolute/file.md",
            "C:/profile/file.md",
            "docs//file.md",
            ".git/config",
            "docs/.gitmodules",
            "assets/private/file.md",
            "captures/private/file.md",
            "ROMS/file.z64",
            "Generated/output.c",
            "EXTRACTED/asset.bin",
            "Docs/.GITMODULES",
        )
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                self.assertTrue(self.errors_for(candidate))


class PatchManifestPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        schema = json.loads(
            (ROOT / "schemas" / "patch-manifest.schema.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator.check_schema(schema)
        cls.validator = Draft202012Validator(schema)
        cls.example = json.loads(
            (ROOT / "examples" / "patch-manifest.example.json").read_text(
                encoding="utf-8"
            )
        )

    def test_repository_example_is_valid(self) -> None:
        self.assertEqual(list(self.validator.iter_errors(self.example)), [])

    def test_enhancement_requires_feature_flag(self) -> None:
        instance = copy.deepcopy(self.example)
        instance["category"] = "hfr"
        instance["feature_flag"] = None
        self.assertTrue(list(self.validator.iter_errors(instance)))

    def test_compatibility_patch_may_have_no_feature_flag(self) -> None:
        instance = copy.deepcopy(self.example)
        instance["category"] = "compatibility"
        instance["feature_flag"] = None
        self.assertEqual(list(self.validator.iter_errors(instance)), [])


if __name__ == "__main__":
    unittest.main()
