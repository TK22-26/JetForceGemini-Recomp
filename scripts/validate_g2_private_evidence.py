#!/usr/bin/env python3
"""Validate ignored, harness-produced executable evidence behind a G2 record."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
import subprocess
import sys
import tempfile
import threading
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Mapping, NamedTuple

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

try:
    from scripts.g2_decision_policy import accepted_architecture_decision
except ModuleNotFoundError:  # Direct `python scripts/...` execution.
    from g2_decision_policy import accepted_architecture_decision


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_SCHEMA = ROOT / "schemas" / "g2-private-evidence.schema.json"
PUBLIC_SCHEMA = ROOT / "schemas" / "g2-completion-evidence.schema.json"
ARCHITECTURE_DECISION = ROOT / "docs" / "adr" / "0003-phase4-dependency-architecture.md"
DEPENDENCY_LOCK = ROOT / "dependencies.lock.json"
REQUIREMENT_IDS = (
    "cpu-sections",
    "overlay-lifecycle",
    "rsp-programs",
    "graphics-tasks",
    "audio-tasks",
    "save-round-trip",
    "runtime-traps",
    "dependency-legal-selection",
)
EXECUTABLE_CLASSES = frozenset(
    {
        "private-native-execution",
        "private-oracle-execution",
        "private-g3-compiler-product-binding",
    }
)
# A trap record is only credible when a project-runtime execution and an
# independently-built oracle agree.  In particular, the native trap producer
# is not permitted to authenticate its own observation by being recorded a
# second time as an oracle.
NATIVE_AND_ORACLE = frozenset(
    {"graphics-tasks", "audio-tasks", "save-round-trip", "runtime-traps"}
)
SINGLE_NATIVE = frozenset({"overlay-lifecycle", "rsp-programs"})
CPU_COMPILER_PRODUCT_COUNT = 3
EXPECTED_PHASE4_EXECUTABLE_SYMBOL_COUNT = 3729
EXPECTED_PHASE4_GENERATED_BODY_COUNT = 2905
EXPECTED_PHASE4_COVERED_ALIAS_COUNT = 824
CPU_G3_EVIDENCE_KINDS = (
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
)
G3_PRODUCT_CORE_FIELDS = (
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
)

MAX_DOCUMENT_BYTES = 8 * 1024 * 1024
MAX_SCHEMA_BYTES = 2 * 1024 * 1024
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
MAX_RESULT_BYTES = 512 * 1024
MAX_HARNESS_BYTES = 2 * 1024 * 1024
MAX_HARNESS_REQUEST_BYTES = 2 * 1024 * 1024
MAX_HARNESS_STDOUT_BYTES = 128 * 1024
MAX_HARNESS_STDERR_BYTES = 16 * 1024
MAX_HARNESS_TIMEOUT_SECONDS = 1800.0
GIT_TIMEOUT_SECONDS = 10

_RESULT_KEYS = frozenset(
    {
        "schema_version",
        "kind",
        "execution_id",
        "requirement_id",
        "evidence_class",
        "harness_id",
        "harness_sha256",
        "case_id",
        "subject_sha256",
        "source_input_sha256",
        "pins_sha256",
        "environment_sha256",
        "input_set_sha256",
        "output_set_sha256",
        "observed_exit_code",
        "passed",
    }
)
_TRANSCRIPT_KEYS = frozenset(
    set(_RESULT_KEYS)
    | {
        "artifact_set_sha256",
        "result_sha256",
        "validated",
    }
)


class EvidenceError(RuntimeError):
    pass


class PinnedHarness(NamedTuple):
    """Repository-owned validator identity selected outside private evidence."""

    harness_id: str
    script_path: Path
    script_sha256: str
    timeout_seconds: float = 15.0


# Intentionally fail-closed until every mapping has a reviewed, independently
# pinned producer.  A caller-supplied executable with marker strings is not a
# trusted producer even when the dispatcher reruns it successfully.
PRODUCTION_HARNESS_PINS: Mapping[tuple[str, str], PinnedHarness] = MappingProxyType({
        ("cpu-sections", "private-g3-compiler-product-binding"): PinnedHarness(
            harness_id="g2-cpu-sections-g3-product-v1",
            script_path=ROOT / "scripts" / "g2_production_evidence_harness.py",
            script_sha256="ec5d91b14e92c9b7e27ef8f4e9507d04c78a0de1de096980446a29ecec6ab2a4",
            timeout_seconds=120.0,
        ),
        ("overlay-lifecycle", "private-native-execution"): PinnedHarness(
            harness_id="g2-overlay-lifecycle-native-v1",
            script_path=ROOT / "scripts" / "g2_production_evidence_harness.py",
            script_sha256="ec5d91b14e92c9b7e27ef8f4e9507d04c78a0de1de096980446a29ecec6ab2a4",
            timeout_seconds=120.0,
        ),
        ("rsp-programs", "private-native-execution"): PinnedHarness(
            harness_id="g2-rsp-programs-native-v1",
            script_path=ROOT / "scripts" / "g2_production_evidence_harness.py",
            script_sha256="ec5d91b14e92c9b7e27ef8f4e9507d04c78a0de1de096980446a29ecec6ab2a4",
            timeout_seconds=120.0,
        ),
        ("graphics-tasks", "private-native-execution"): PinnedHarness(
            harness_id="g2-graphics-native-v1",
            script_path=ROOT / "scripts" / "g2_production_evidence_harness.py",
            script_sha256="ec5d91b14e92c9b7e27ef8f4e9507d04c78a0de1de096980446a29ecec6ab2a4",
            timeout_seconds=120.0,
        ),
        ("graphics-tasks", "private-oracle-execution"): PinnedHarness(
            harness_id="g2-graphics-oracle-v1",
            script_path=ROOT / "scripts" / "g2_production_evidence_harness.py",
            script_sha256="ec5d91b14e92c9b7e27ef8f4e9507d04c78a0de1de096980446a29ecec6ab2a4",
            timeout_seconds=120.0,
        ),
        ("audio-tasks", "private-native-execution"): PinnedHarness(
            harness_id="g2-audio-native-v1",
            script_path=ROOT / "scripts" / "g2_production_evidence_harness.py",
            script_sha256="ec5d91b14e92c9b7e27ef8f4e9507d04c78a0de1de096980446a29ecec6ab2a4",
            timeout_seconds=120.0,
        ),
        ("audio-tasks", "private-oracle-execution"): PinnedHarness(
            harness_id="g2-audio-oracle-v1",
            script_path=ROOT / "scripts" / "g2_production_evidence_harness.py",
            script_sha256="ec5d91b14e92c9b7e27ef8f4e9507d04c78a0de1de096980446a29ecec6ab2a4",
            timeout_seconds=120.0,
        ),
        ("save-round-trip", "private-native-execution"): PinnedHarness(
            harness_id="g2-save-native-v1",
            script_path=ROOT / "scripts" / "g2_production_evidence_harness.py",
            script_sha256="ec5d91b14e92c9b7e27ef8f4e9507d04c78a0de1de096980446a29ecec6ab2a4",
            timeout_seconds=120.0,
        ),
        ("save-round-trip", "private-oracle-execution"): PinnedHarness(
            harness_id="g2-save-oracle-v1",
            script_path=ROOT / "scripts" / "g2_production_evidence_harness.py",
            script_sha256="ec5d91b14e92c9b7e27ef8f4e9507d04c78a0de1de096980446a29ecec6ab2a4",
            timeout_seconds=120.0,
        ),
        ("runtime-traps", "private-native-execution"): PinnedHarness(
            harness_id="g2-runtime-traps-native-v1",
            script_path=ROOT / "scripts" / "g2_production_evidence_harness.py",
            script_sha256="ec5d91b14e92c9b7e27ef8f4e9507d04c78a0de1de096980446a29ecec6ab2a4",
            timeout_seconds=120.0,
        ),
        ("runtime-traps", "private-oracle-execution"): PinnedHarness(
            harness_id="g2-runtime-traps-oracle-v1",
            script_path=ROOT / "scripts" / "g2_production_evidence_harness.py",
            script_sha256="ec5d91b14e92c9b7e27ef8f4e9507d04c78a0de1de096980446a29ecec6ab2a4",
            timeout_seconds=120.0,
        ),
        ("dependency-legal-selection", "human-approved-decision"): PinnedHarness(
            harness_id="g2-dependency-decision-v1",
            script_path=ROOT / "scripts" / "g2_production_evidence_harness.py",
            script_sha256="ec5d91b14e92c9b7e27ef8f4e9507d04c78a0de1de096980446a29ecec6ab2a4",
            timeout_seconds=120.0,
        ),
})

# An executable mapping is ineligible for a future binary pin unless this
# repository-owned source anchor is present, byte-for-byte reviewed in both the
# index and committed HEAD, and the private case carries the matching canonical
# derivation record. Producer binaries and private oracle/generated-audio
# adapters stay ignored; the project bounded graphics adapter is tracked and
# belongs to this reviewed closure.
PRODUCER_SOURCE_PROVENANCE: Mapping[tuple[str, str], Mapping[str, str]] = MappingProxyType(
    {
        ("cpu-sections", "private-g3-compiler-product-binding"): {
            "source_path": "src/evidence/g2_cpu_producer.cpp",
            "source_sha256": "df55e4b030d7972412736c3ed639da5d43a7f10ba4100cb31e3b97ff431c576a",
            "reviewed_commit": "4d245ccdd6cfcddad66f218431495ec038dfa945",
            "reviewed_tree": "2571bf03d837bc2cb7548f2810902fd66c287cdc",
            "tracked_closure_sha256": "080dfef5e6f4725c7199afa52b05afb640de1e8e7e4606226ceab2ff217cfe5d",
            "build_system": "cmake",
            "build_recipe_id": "g2-cpu-producer-cmake-v1",
            "build_target": "jfg_g2_cpu_producer",
            "adapter_id": "g2-cpu-g3-product-adapter",
            "adapter_version": "v1",
        },
        ("overlay-lifecycle", "private-native-execution"): {
            "source_path": "src/evidence/g2_overlay_producer.cpp",
            "source_sha256": "284b768e2f1d908652c3909aa91a5bc51fbb8df7c021f70ee939c6a04ce1b96f",
            "reviewed_commit": "4d245ccdd6cfcddad66f218431495ec038dfa945",
            "reviewed_tree": "2571bf03d837bc2cb7548f2810902fd66c287cdc",
            "tracked_closure_sha256": "080dfef5e6f4725c7199afa52b05afb640de1e8e7e4606226ceab2ff217cfe5d",
            "build_system": "cmake",
            "build_recipe_id": "g2-overlay-producer-cmake-v1",
            "build_target": "jfg_g2_overlay_producer",
            "adapter_id": "g2-overlay-private-adapter",
            "adapter_version": "v1",
        },
        ("rsp-programs", "private-native-execution"): {
            "source_path": "src/evidence/g2_rsp_producer.cpp",
            "source_sha256": "cdde1ecef32e419e01f60f2ebc329608987569b22b7086b1b90cbef31821bdb6",
            "reviewed_commit": "4d245ccdd6cfcddad66f218431495ec038dfa945",
            "reviewed_tree": "2571bf03d837bc2cb7548f2810902fd66c287cdc",
            "tracked_closure_sha256": "080dfef5e6f4725c7199afa52b05afb640de1e8e7e4606226ceab2ff217cfe5d",
            "build_system": "cmake",
            "build_recipe_id": "g2-rsp-producer-cmake-v1",
            "build_target": "jfg_g2_rsp_producer",
            "adapter_id": "g2-rsp-inventory-adapter",
            "adapter_version": "v1",
        },
        ("graphics-tasks", "private-native-execution"): {
            "source_path": "src/evidence/g2_graphics_native_producer.cpp",
            "source_sha256": "df0dc96065b2727d681585b64a85c4db50aa8c1aac0ff1ec987eddb544c5fb9d",
            "reviewed_commit": "4d245ccdd6cfcddad66f218431495ec038dfa945",
            "reviewed_tree": "2571bf03d837bc2cb7548f2810902fd66c287cdc",
            "tracked_closure_sha256": "080dfef5e6f4725c7199afa52b05afb640de1e8e7e4606226ceab2ff217cfe5d",
            "build_system": "cmake",
            "build_recipe_id": "g2-graphics-native-producer-cmake-v1",
            "build_target": "jfg_g2_graphics_native_producer",
            "adapter_id": "g2-graphics-real-task-backend",
            "adapter_version": "v2",
        },
        ("graphics-tasks", "private-oracle-execution"): {
            "source_path": "src/evidence/g2_graphics_oracle_producer.cpp",
            "source_sha256": "3a1f7edf197a1c037d24c2f153e6695e56644157f5a58224934b73f806819f9f",
            "reviewed_commit": "4d245ccdd6cfcddad66f218431495ec038dfa945",
            "reviewed_tree": "2571bf03d837bc2cb7548f2810902fd66c287cdc",
            "tracked_closure_sha256": "080dfef5e6f4725c7199afa52b05afb640de1e8e7e4606226ceab2ff217cfe5d",
            "build_system": "cmake",
            "build_recipe_id": "g2-graphics-oracle-producer-cmake-v1",
            "build_target": "jfg_g2_graphics_oracle_producer",
            "adapter_id": "g2-graphics-private-oracle",
            "adapter_version": "v2",
        },
        ("audio-tasks", "private-native-execution"): {
            "source_path": "src/evidence/g2_audio_native_producer.cpp",
            "source_sha256": "2809e6a9e51498b7cc7eb258c8dd6347cb66e330e21bb7dbeb6d7b466f85698d",
            "reviewed_commit": "4d245ccdd6cfcddad66f218431495ec038dfa945",
            "reviewed_tree": "2571bf03d837bc2cb7548f2810902fd66c287cdc",
            "tracked_closure_sha256": "080dfef5e6f4725c7199afa52b05afb640de1e8e7e4606226ceab2ff217cfe5d",
            "build_system": "cmake",
            "build_recipe_id": "g2-audio-native-producer-cmake-v1",
            "build_target": "jfg_g2_audio_native_producer",
            "adapter_id": "g2-audio-generated-adapter",
            "adapter_version": "v2",
        },
        ("audio-tasks", "private-oracle-execution"): {
            "source_path": "src/evidence/g2_audio_oracle_producer.cpp",
            "source_sha256": "796f862cc667d420ce2c1ab60356bef3b339d8168b2d17a44cd5ac955d1bbd98",
            "reviewed_commit": "4d245ccdd6cfcddad66f218431495ec038dfa945",
            "reviewed_tree": "2571bf03d837bc2cb7548f2810902fd66c287cdc",
            "tracked_closure_sha256": "080dfef5e6f4725c7199afa52b05afb640de1e8e7e4606226ceab2ff217cfe5d",
            "build_system": "cmake",
            "build_recipe_id": "g2-audio-oracle-producer-cmake-v1",
            "build_target": "jfg_g2_audio_oracle_producer",
            "adapter_id": "g2-audio-private-oracle",
            "adapter_version": "v2",
        },
        ("save-round-trip", "private-native-execution"): {
            "source_path": "src/evidence/g2_save_native_producer.cpp",
            "source_sha256": "1ced6d7417050e9c8e16967d63b1664cf7ccf3bb3eefe732fa22d20d38d341ea",
            "reviewed_commit": "4d245ccdd6cfcddad66f218431495ec038dfa945",
            "reviewed_tree": "2571bf03d837bc2cb7548f2810902fd66c287cdc",
            "tracked_closure_sha256": "080dfef5e6f4725c7199afa52b05afb640de1e8e7e4606226ceab2ff217cfe5d",
            "build_system": "cmake",
            "build_recipe_id": "g2-save-native-producer-cmake-v1",
            "build_target": "jfg_g2_save_native_producer",
            "adapter_id": "g2-save-native-runtime",
            "adapter_version": "v1",
        },
        ("save-round-trip", "private-oracle-execution"): {
            "source_path": "src/evidence/g2_save_oracle_producer.cpp",
            "source_sha256": "1056fa4ecb69d23e752cc58f7c6154f2ff46506389d7f65488b1420bdd03f70d",
            "reviewed_commit": "4d245ccdd6cfcddad66f218431495ec038dfa945",
            "reviewed_tree": "2571bf03d837bc2cb7548f2810902fd66c287cdc",
            "tracked_closure_sha256": "080dfef5e6f4725c7199afa52b05afb640de1e8e7e4606226ceab2ff217cfe5d",
            "build_system": "cmake",
            "build_recipe_id": "g2-save-oracle-producer-cmake-v1",
            "build_target": "jfg_g2_save_oracle_producer",
            "adapter_id": "g2-save-oracle-runtime",
            "adapter_version": "v1",
        },
        ("runtime-traps", "private-native-execution"): {
            "source_path": "src/evidence/g2_trap_producer.cpp",
            "source_sha256": "33d08d03b18b8767d8c35bfa568951e073bfdb09389f21467f0b3c6982457acf",
            "reviewed_commit": "4d245ccdd6cfcddad66f218431495ec038dfa945",
            "reviewed_tree": "2571bf03d837bc2cb7548f2810902fd66c287cdc",
            "tracked_closure_sha256": "080dfef5e6f4725c7199afa52b05afb640de1e8e7e4606226ceab2ff217cfe5d",
            "build_system": "cmake",
            "build_recipe_id": "g2-trap-producer-cmake-v1",
            "build_target": "jfg_g2_trap_producer",
            "adapter_id": "g2-runtime-traps-native",
            "adapter_version": "v1",
        },
        ("runtime-traps", "private-oracle-execution"): {
            "source_path": "src/evidence/g2_trap_oracle_producer.cpp",
            "source_sha256": "b525df75634ef57da8d6d3a0badc7f7239c3a31b7dac482ddf3b1e9c08c91721",
            "reviewed_commit": "4d245ccdd6cfcddad66f218431495ec038dfa945",
            "reviewed_tree": "2571bf03d837bc2cb7548f2810902fd66c287cdc",
            "tracked_closure_sha256": "080dfef5e6f4725c7199afa52b05afb640de1e8e7e4606226ceab2ff217cfe5d",
            "build_system": "cmake",
            "build_recipe_id": "g2-trap-oracle-producer-cmake-v1",
            "build_target": "jfg_g2_trap_oracle_producer",
            "adapter_id": "g2-runtime-traps-oracle",
            "adapter_version": "v1",
        },
    }
)
PRODUCER_BUILD_ATTESTATION: Mapping[tuple[str, str], Mapping[str, object]] = (
    MappingProxyType({
        ("cpu-sections", "private-g3-compiler-product-binding"): {
            "schema_version": 1,
            "kind": "jfg-g2-producer-build-attestation",
            "compiler_id": "gcc-13.3.0",
            "compiler_sha256": "1353e9bdd29a7295c7226bf6c63abccce056d8cac31f112e5cdbecc3f28c2769",
            "cmake_generator": "Ninja",
            "cmake_configuration": "Release",
            "cmake_defines": ["CMAKE_BUILD_TYPE=Release", "CMAKE_C_COMPILER=/usr/bin/gcc", "CMAKE_CXX_COMPILER=/usr/bin/g++", "JFG_ENABLE_GENERATED_CODE=ON", "JFG_BUILD_G2_PRODUCERS=ON", "JFG_BUILD_TESTS=OFF", "JFG_BUILD_SYNTHETIC_GENERATED_TESTS=OFF", "JFG_GENERATED_ROOT=tools/results/phase4/semantic-audit-current-v3/normalized-phase8-hash-v4", "JFG_G2_PRIVATE_AUDIO_ADAPTER_ROOT=tools/results/phase4/private-audio-g2", "JFG_G2_PRIVATE_AUDIO_ORACLE_ROOT=tools/results/phase4/g2-production-audio-oracle-v2", "JFG_G2_PRIVATE_AUDIO_RUNTIME_INCLUDE=tools/upstream/N64ModernRuntime/librecomp/include", "JFG_G2_PRIVATE_GRAPHICS_ORACLE_ROOT=tools/results/phase4/g2-production-graphics-oracle-v2"],
            "producer_compile_flags": ["-O3", "-DNDEBUG", "-std=gnu++20", "-Wall", "-Wextra", "-Wconversion", "-Wpedantic", "-Wshadow", "-Werror"],
            "generated_compile_flags": ["-O3", "-DNDEBUG", "-Wall", "-Wextra", "-Wno-sign-compare", "-Wno-tautological-compare", "-Wno-type-limits", "-Wno-unused-label", "-Wno-unused-parameter", "-Wno-unused-variable", "-Wno-unused-but-set-variable", "-Werror"],
            "private_generated_closure_sha256": "50dba0424bc71656f6cfebe59e850c7aa9fdb51620eec34d70cece47ccec9077",
            "tracked_dependency_closure_sha256": "080dfef5e6f4725c7199afa52b05afb640de1e8e7e4606226ceab2ff217cfe5d",
            "reviewed_commit": "4d245ccdd6cfcddad66f218431495ec038dfa945",
            "reviewed_tree": "2571bf03d837bc2cb7548f2810902fd66c287cdc",
        },
        ("overlay-lifecycle", "private-native-execution"): {
            "schema_version": 1,
            "kind": "jfg-g2-producer-build-attestation",
            "compiler_id": "gcc-13.3.0",
            "compiler_sha256": "1353e9bdd29a7295c7226bf6c63abccce056d8cac31f112e5cdbecc3f28c2769",
            "cmake_generator": "Ninja",
            "cmake_configuration": "Release",
            "cmake_defines": ["CMAKE_BUILD_TYPE=Release", "CMAKE_C_COMPILER=/usr/bin/gcc", "CMAKE_CXX_COMPILER=/usr/bin/g++", "JFG_ENABLE_GENERATED_CODE=ON", "JFG_BUILD_G2_PRODUCERS=ON", "JFG_BUILD_TESTS=OFF", "JFG_BUILD_SYNTHETIC_GENERATED_TESTS=OFF", "JFG_GENERATED_ROOT=tools/results/phase4/semantic-audit-current-v3/normalized-phase8-hash-v4", "JFG_G2_PRIVATE_AUDIO_ADAPTER_ROOT=tools/results/phase4/private-audio-g2", "JFG_G2_PRIVATE_AUDIO_ORACLE_ROOT=tools/results/phase4/g2-production-audio-oracle-v2", "JFG_G2_PRIVATE_AUDIO_RUNTIME_INCLUDE=tools/upstream/N64ModernRuntime/librecomp/include", "JFG_G2_PRIVATE_GRAPHICS_ORACLE_ROOT=tools/results/phase4/g2-production-graphics-oracle-v2"],
            "producer_compile_flags": ["-O3", "-DNDEBUG", "-std=gnu++20", "-Wall", "-Wextra", "-Wconversion", "-Wpedantic", "-Wshadow", "-Werror"],
            "generated_compile_flags": ["-O3", "-DNDEBUG", "-Wall", "-Wextra", "-Wno-sign-compare", "-Wno-tautological-compare", "-Wno-type-limits", "-Wno-unused-label", "-Wno-unused-parameter", "-Wno-unused-variable", "-Wno-unused-but-set-variable", "-Werror"],
            "private_generated_closure_sha256": "7b2e34ddf1d276546061a3362491ff183750613523868952027259fda326d7ee",
            "tracked_dependency_closure_sha256": "080dfef5e6f4725c7199afa52b05afb640de1e8e7e4606226ceab2ff217cfe5d",
            "reviewed_commit": "4d245ccdd6cfcddad66f218431495ec038dfa945",
            "reviewed_tree": "2571bf03d837bc2cb7548f2810902fd66c287cdc",
        },
        ("rsp-programs", "private-native-execution"): {
            "schema_version": 1,
            "kind": "jfg-g2-producer-build-attestation",
            "compiler_id": "gcc-13.3.0",
            "compiler_sha256": "1353e9bdd29a7295c7226bf6c63abccce056d8cac31f112e5cdbecc3f28c2769",
            "cmake_generator": "Ninja",
            "cmake_configuration": "Release",
            "cmake_defines": ["CMAKE_BUILD_TYPE=Release", "CMAKE_C_COMPILER=/usr/bin/gcc", "CMAKE_CXX_COMPILER=/usr/bin/g++", "JFG_ENABLE_GENERATED_CODE=ON", "JFG_BUILD_G2_PRODUCERS=ON", "JFG_BUILD_TESTS=OFF", "JFG_BUILD_SYNTHETIC_GENERATED_TESTS=OFF", "JFG_GENERATED_ROOT=tools/results/phase4/semantic-audit-current-v3/normalized-phase8-hash-v4", "JFG_G2_PRIVATE_AUDIO_ADAPTER_ROOT=tools/results/phase4/private-audio-g2", "JFG_G2_PRIVATE_AUDIO_ORACLE_ROOT=tools/results/phase4/g2-production-audio-oracle-v2", "JFG_G2_PRIVATE_AUDIO_RUNTIME_INCLUDE=tools/upstream/N64ModernRuntime/librecomp/include", "JFG_G2_PRIVATE_GRAPHICS_ORACLE_ROOT=tools/results/phase4/g2-production-graphics-oracle-v2"],
            "producer_compile_flags": ["-O3", "-DNDEBUG", "-std=gnu++20", "-Wall", "-Wextra", "-Wconversion", "-Wpedantic", "-Wshadow", "-Werror"],
            "generated_compile_flags": ["-O3", "-DNDEBUG", "-Wall", "-Wextra", "-Wno-sign-compare", "-Wno-tautological-compare", "-Wno-type-limits", "-Wno-unused-label", "-Wno-unused-parameter", "-Wno-unused-variable", "-Wno-unused-but-set-variable", "-Werror"],
            "private_generated_closure_sha256": "4e97d9d74777b7ba2cacbecf80af13d1e6bb06cb59259afce12df850de9be5fa",
            "tracked_dependency_closure_sha256": "080dfef5e6f4725c7199afa52b05afb640de1e8e7e4606226ceab2ff217cfe5d",
            "reviewed_commit": "4d245ccdd6cfcddad66f218431495ec038dfa945",
            "reviewed_tree": "2571bf03d837bc2cb7548f2810902fd66c287cdc",
        },
        ("graphics-tasks", "private-native-execution"): {
            "schema_version": 1,
            "kind": "jfg-g2-producer-build-attestation",
            "compiler_id": "gcc-13.3.0",
            "compiler_sha256": "1353e9bdd29a7295c7226bf6c63abccce056d8cac31f112e5cdbecc3f28c2769",
            "cmake_generator": "Ninja",
            "cmake_configuration": "Release",
            "cmake_defines": ["CMAKE_BUILD_TYPE=Release", "CMAKE_C_COMPILER=/usr/bin/gcc", "CMAKE_CXX_COMPILER=/usr/bin/g++", "JFG_ENABLE_GENERATED_CODE=ON", "JFG_BUILD_G2_PRODUCERS=ON", "JFG_BUILD_TESTS=OFF", "JFG_BUILD_SYNTHETIC_GENERATED_TESTS=OFF", "JFG_GENERATED_ROOT=tools/results/phase4/semantic-audit-current-v3/normalized-phase8-hash-v4", "JFG_G2_PRIVATE_AUDIO_ADAPTER_ROOT=tools/results/phase4/private-audio-g2", "JFG_G2_PRIVATE_AUDIO_ORACLE_ROOT=tools/results/phase4/g2-production-audio-oracle-v2", "JFG_G2_PRIVATE_AUDIO_RUNTIME_INCLUDE=tools/upstream/N64ModernRuntime/librecomp/include", "JFG_G2_PRIVATE_GRAPHICS_ORACLE_ROOT=tools/results/phase4/g2-production-graphics-oracle-v2"],
            "producer_compile_flags": ["-O3", "-DNDEBUG", "-std=gnu++20", "-Wall", "-Wextra", "-Wconversion", "-Wpedantic", "-Wshadow", "-Werror"],
            "generated_compile_flags": ["-O3", "-DNDEBUG", "-Wall", "-Wextra", "-Wno-sign-compare", "-Wno-tautological-compare", "-Wno-type-limits", "-Wno-unused-label", "-Wno-unused-parameter", "-Wno-unused-variable", "-Wno-unused-but-set-variable", "-Werror"],
            "private_generated_closure_sha256": "41d201991b5ef1a59db6aa43a5459b35e2eefdcdad20b3522cc000bac8c9d36c",
            "tracked_dependency_closure_sha256": "080dfef5e6f4725c7199afa52b05afb640de1e8e7e4606226ceab2ff217cfe5d",
            "reviewed_commit": "4d245ccdd6cfcddad66f218431495ec038dfa945",
            "reviewed_tree": "2571bf03d837bc2cb7548f2810902fd66c287cdc",
        },
        ("graphics-tasks", "private-oracle-execution"): {
            "schema_version": 1,
            "kind": "jfg-g2-producer-build-attestation",
            "compiler_id": "gcc-13.3.0",
            "compiler_sha256": "1353e9bdd29a7295c7226bf6c63abccce056d8cac31f112e5cdbecc3f28c2769",
            "cmake_generator": "Ninja",
            "cmake_configuration": "Release",
            "cmake_defines": ["CMAKE_BUILD_TYPE=Release", "CMAKE_C_COMPILER=/usr/bin/gcc", "CMAKE_CXX_COMPILER=/usr/bin/g++", "JFG_ENABLE_GENERATED_CODE=ON", "JFG_BUILD_G2_PRODUCERS=ON", "JFG_BUILD_TESTS=OFF", "JFG_BUILD_SYNTHETIC_GENERATED_TESTS=OFF", "JFG_GENERATED_ROOT=tools/results/phase4/semantic-audit-current-v3/normalized-phase8-hash-v4", "JFG_G2_PRIVATE_AUDIO_ADAPTER_ROOT=tools/results/phase4/private-audio-g2", "JFG_G2_PRIVATE_AUDIO_ORACLE_ROOT=tools/results/phase4/g2-production-audio-oracle-v2", "JFG_G2_PRIVATE_AUDIO_RUNTIME_INCLUDE=tools/upstream/N64ModernRuntime/librecomp/include", "JFG_G2_PRIVATE_GRAPHICS_ORACLE_ROOT=tools/results/phase4/g2-production-graphics-oracle-v2"],
            "producer_compile_flags": ["-O3", "-DNDEBUG", "-std=gnu++20", "-Wall", "-Wextra", "-Wconversion", "-Wpedantic", "-Wshadow", "-Werror"],
            "generated_compile_flags": ["-O3", "-DNDEBUG", "-Wall", "-Wextra", "-Wno-sign-compare", "-Wno-tautological-compare", "-Wno-type-limits", "-Wno-unused-label", "-Wno-unused-parameter", "-Wno-unused-variable", "-Wno-unused-but-set-variable", "-Werror"],
            "private_generated_closure_sha256": "e38eeacf967832031acb098eb0fa290f92d6b008ae9d53afce4c883ddc67ddff",
            "tracked_dependency_closure_sha256": "080dfef5e6f4725c7199afa52b05afb640de1e8e7e4606226ceab2ff217cfe5d",
            "reviewed_commit": "4d245ccdd6cfcddad66f218431495ec038dfa945",
            "reviewed_tree": "2571bf03d837bc2cb7548f2810902fd66c287cdc",
        },
        ("audio-tasks", "private-native-execution"): {
            "schema_version": 1,
            "kind": "jfg-g2-producer-build-attestation",
            "compiler_id": "gcc-13.3.0",
            "compiler_sha256": "1353e9bdd29a7295c7226bf6c63abccce056d8cac31f112e5cdbecc3f28c2769",
            "cmake_generator": "Ninja",
            "cmake_configuration": "Release",
            "cmake_defines": ["CMAKE_BUILD_TYPE=Release", "CMAKE_C_COMPILER=/usr/bin/gcc", "CMAKE_CXX_COMPILER=/usr/bin/g++", "JFG_ENABLE_GENERATED_CODE=ON", "JFG_BUILD_G2_PRODUCERS=ON", "JFG_BUILD_TESTS=OFF", "JFG_BUILD_SYNTHETIC_GENERATED_TESTS=OFF", "JFG_GENERATED_ROOT=tools/results/phase4/semantic-audit-current-v3/normalized-phase8-hash-v4", "JFG_G2_PRIVATE_AUDIO_ADAPTER_ROOT=tools/results/phase4/private-audio-g2", "JFG_G2_PRIVATE_AUDIO_ORACLE_ROOT=tools/results/phase4/g2-production-audio-oracle-v2", "JFG_G2_PRIVATE_AUDIO_RUNTIME_INCLUDE=tools/upstream/N64ModernRuntime/librecomp/include", "JFG_G2_PRIVATE_GRAPHICS_ORACLE_ROOT=tools/results/phase4/g2-production-graphics-oracle-v2"],
            "producer_compile_flags": ["-O3", "-DNDEBUG", "-std=gnu++20", "-Wall", "-Wextra", "-Wconversion", "-Wpedantic", "-Wshadow", "-Werror"],
            "generated_compile_flags": ["-O3", "-DNDEBUG", "-Wall", "-Wextra", "-Wno-sign-compare", "-Wno-tautological-compare", "-Wno-type-limits", "-Wno-unused-label", "-Wno-unused-parameter", "-Wno-unused-variable", "-Wno-unused-but-set-variable", "-Werror"],
            "private_generated_closure_sha256": "d34964934af9582e234bdd0ed3aa749a4c677502dd3458dfec8ea422d6cce202",
            "tracked_dependency_closure_sha256": "080dfef5e6f4725c7199afa52b05afb640de1e8e7e4606226ceab2ff217cfe5d",
            "reviewed_commit": "4d245ccdd6cfcddad66f218431495ec038dfa945",
            "reviewed_tree": "2571bf03d837bc2cb7548f2810902fd66c287cdc",
        },
        ("audio-tasks", "private-oracle-execution"): {
            "schema_version": 1,
            "kind": "jfg-g2-producer-build-attestation",
            "compiler_id": "gcc-13.3.0",
            "compiler_sha256": "1353e9bdd29a7295c7226bf6c63abccce056d8cac31f112e5cdbecc3f28c2769",
            "cmake_generator": "Ninja",
            "cmake_configuration": "Release",
            "cmake_defines": ["CMAKE_BUILD_TYPE=Release", "CMAKE_C_COMPILER=/usr/bin/gcc", "CMAKE_CXX_COMPILER=/usr/bin/g++", "JFG_ENABLE_GENERATED_CODE=ON", "JFG_BUILD_G2_PRODUCERS=ON", "JFG_BUILD_TESTS=OFF", "JFG_BUILD_SYNTHETIC_GENERATED_TESTS=OFF", "JFG_GENERATED_ROOT=tools/results/phase4/semantic-audit-current-v3/normalized-phase8-hash-v4", "JFG_G2_PRIVATE_AUDIO_ADAPTER_ROOT=tools/results/phase4/private-audio-g2", "JFG_G2_PRIVATE_AUDIO_ORACLE_ROOT=tools/results/phase4/g2-production-audio-oracle-v2", "JFG_G2_PRIVATE_AUDIO_RUNTIME_INCLUDE=tools/upstream/N64ModernRuntime/librecomp/include", "JFG_G2_PRIVATE_GRAPHICS_ORACLE_ROOT=tools/results/phase4/g2-production-graphics-oracle-v2"],
            "producer_compile_flags": ["-O3", "-DNDEBUG", "-std=gnu++20", "-Wall", "-Wextra", "-Wconversion", "-Wpedantic", "-Wshadow", "-Werror"],
            "generated_compile_flags": ["-O3", "-DNDEBUG", "-Wall", "-Wextra", "-Wno-sign-compare", "-Wno-tautological-compare", "-Wno-type-limits", "-Wno-unused-label", "-Wno-unused-parameter", "-Wno-unused-variable", "-Wno-unused-but-set-variable", "-Werror"],
            "private_generated_closure_sha256": "76af71dbc81deb5a8ce4263378672c2e6f0152413595badbff04629fd164c5ef",
            "tracked_dependency_closure_sha256": "080dfef5e6f4725c7199afa52b05afb640de1e8e7e4606226ceab2ff217cfe5d",
            "reviewed_commit": "4d245ccdd6cfcddad66f218431495ec038dfa945",
            "reviewed_tree": "2571bf03d837bc2cb7548f2810902fd66c287cdc",
        },
        ("save-round-trip", "private-native-execution"): {
            "schema_version": 1,
            "kind": "jfg-g2-producer-build-attestation",
            "compiler_id": "gcc-13.3.0",
            "compiler_sha256": "1353e9bdd29a7295c7226bf6c63abccce056d8cac31f112e5cdbecc3f28c2769",
            "cmake_generator": "Ninja",
            "cmake_configuration": "Release",
            "cmake_defines": ["CMAKE_BUILD_TYPE=Release", "CMAKE_C_COMPILER=/usr/bin/gcc", "CMAKE_CXX_COMPILER=/usr/bin/g++", "JFG_ENABLE_GENERATED_CODE=ON", "JFG_BUILD_G2_PRODUCERS=ON", "JFG_BUILD_TESTS=OFF", "JFG_BUILD_SYNTHETIC_GENERATED_TESTS=OFF", "JFG_GENERATED_ROOT=tools/results/phase4/semantic-audit-current-v3/normalized-phase8-hash-v4", "JFG_G2_PRIVATE_AUDIO_ADAPTER_ROOT=tools/results/phase4/private-audio-g2", "JFG_G2_PRIVATE_AUDIO_ORACLE_ROOT=tools/results/phase4/g2-production-audio-oracle-v2", "JFG_G2_PRIVATE_AUDIO_RUNTIME_INCLUDE=tools/upstream/N64ModernRuntime/librecomp/include", "JFG_G2_PRIVATE_GRAPHICS_ORACLE_ROOT=tools/results/phase4/g2-production-graphics-oracle-v2"],
            "producer_compile_flags": ["-O3", "-DNDEBUG", "-std=gnu++20", "-Wall", "-Wextra", "-Wconversion", "-Wpedantic", "-Wshadow", "-Werror"],
            "generated_compile_flags": ["-O3", "-DNDEBUG", "-Wall", "-Wextra", "-Wno-sign-compare", "-Wno-tautological-compare", "-Wno-type-limits", "-Wno-unused-label", "-Wno-unused-parameter", "-Wno-unused-variable", "-Wno-unused-but-set-variable", "-Werror"],
            "private_generated_closure_sha256": "dbaa8d179943b82a7e99148a0dfd0e8a694536d32b5a9700cd95fb9330129846",
            "tracked_dependency_closure_sha256": "080dfef5e6f4725c7199afa52b05afb640de1e8e7e4606226ceab2ff217cfe5d",
            "reviewed_commit": "4d245ccdd6cfcddad66f218431495ec038dfa945",
            "reviewed_tree": "2571bf03d837bc2cb7548f2810902fd66c287cdc",
        },
        ("save-round-trip", "private-oracle-execution"): {
            "schema_version": 1,
            "kind": "jfg-g2-producer-build-attestation",
            "compiler_id": "gcc-13.3.0",
            "compiler_sha256": "1353e9bdd29a7295c7226bf6c63abccce056d8cac31f112e5cdbecc3f28c2769",
            "cmake_generator": "Ninja",
            "cmake_configuration": "Release",
            "cmake_defines": ["CMAKE_BUILD_TYPE=Release", "CMAKE_C_COMPILER=/usr/bin/gcc", "CMAKE_CXX_COMPILER=/usr/bin/g++", "JFG_ENABLE_GENERATED_CODE=ON", "JFG_BUILD_G2_PRODUCERS=ON", "JFG_BUILD_TESTS=OFF", "JFG_BUILD_SYNTHETIC_GENERATED_TESTS=OFF", "JFG_GENERATED_ROOT=tools/results/phase4/semantic-audit-current-v3/normalized-phase8-hash-v4", "JFG_G2_PRIVATE_AUDIO_ADAPTER_ROOT=tools/results/phase4/private-audio-g2", "JFG_G2_PRIVATE_AUDIO_ORACLE_ROOT=tools/results/phase4/g2-production-audio-oracle-v2", "JFG_G2_PRIVATE_AUDIO_RUNTIME_INCLUDE=tools/upstream/N64ModernRuntime/librecomp/include", "JFG_G2_PRIVATE_GRAPHICS_ORACLE_ROOT=tools/results/phase4/g2-production-graphics-oracle-v2"],
            "producer_compile_flags": ["-O3", "-DNDEBUG", "-std=gnu++20", "-Wall", "-Wextra", "-Wconversion", "-Wpedantic", "-Wshadow", "-Werror"],
            "generated_compile_flags": ["-O3", "-DNDEBUG", "-Wall", "-Wextra", "-Wno-sign-compare", "-Wno-tautological-compare", "-Wno-type-limits", "-Wno-unused-label", "-Wno-unused-parameter", "-Wno-unused-variable", "-Wno-unused-but-set-variable", "-Werror"],
            "private_generated_closure_sha256": "be1103b765596253f94e5ac7ffec2d0e9b1fe5add9b9de0687f06688ee496884",
            "tracked_dependency_closure_sha256": "080dfef5e6f4725c7199afa52b05afb640de1e8e7e4606226ceab2ff217cfe5d",
            "reviewed_commit": "4d245ccdd6cfcddad66f218431495ec038dfa945",
            "reviewed_tree": "2571bf03d837bc2cb7548f2810902fd66c287cdc",
        },
        ("runtime-traps", "private-native-execution"): {
            "schema_version": 1,
            "kind": "jfg-g2-producer-build-attestation",
            "compiler_id": "gcc-13.3.0",
            "compiler_sha256": "1353e9bdd29a7295c7226bf6c63abccce056d8cac31f112e5cdbecc3f28c2769",
            "cmake_generator": "Ninja",
            "cmake_configuration": "Release",
            "cmake_defines": ["CMAKE_BUILD_TYPE=Release", "CMAKE_C_COMPILER=/usr/bin/gcc", "CMAKE_CXX_COMPILER=/usr/bin/g++", "JFG_ENABLE_GENERATED_CODE=ON", "JFG_BUILD_G2_PRODUCERS=ON", "JFG_BUILD_TESTS=OFF", "JFG_BUILD_SYNTHETIC_GENERATED_TESTS=OFF", "JFG_GENERATED_ROOT=tools/results/phase4/semantic-audit-current-v3/normalized-phase8-hash-v4", "JFG_G2_PRIVATE_AUDIO_ADAPTER_ROOT=tools/results/phase4/private-audio-g2", "JFG_G2_PRIVATE_AUDIO_ORACLE_ROOT=tools/results/phase4/g2-production-audio-oracle-v2", "JFG_G2_PRIVATE_AUDIO_RUNTIME_INCLUDE=tools/upstream/N64ModernRuntime/librecomp/include", "JFG_G2_PRIVATE_GRAPHICS_ORACLE_ROOT=tools/results/phase4/g2-production-graphics-oracle-v2"],
            "producer_compile_flags": ["-O3", "-DNDEBUG", "-std=gnu++20", "-Wall", "-Wextra", "-Wconversion", "-Wpedantic", "-Wshadow", "-Werror"],
            "generated_compile_flags": ["-O3", "-DNDEBUG", "-Wall", "-Wextra", "-Wno-sign-compare", "-Wno-tautological-compare", "-Wno-type-limits", "-Wno-unused-label", "-Wno-unused-parameter", "-Wno-unused-variable", "-Wno-unused-but-set-variable", "-Werror"],
            "private_generated_closure_sha256": "8da54dabd96d92b5512317f97076b23c330594153b558035f9cf1e8a4fd405e0",
            "tracked_dependency_closure_sha256": "080dfef5e6f4725c7199afa52b05afb640de1e8e7e4606226ceab2ff217cfe5d",
            "reviewed_commit": "4d245ccdd6cfcddad66f218431495ec038dfa945",
            "reviewed_tree": "2571bf03d837bc2cb7548f2810902fd66c287cdc",
        },
        ("runtime-traps", "private-oracle-execution"): {
            "schema_version": 1,
            "kind": "jfg-g2-producer-build-attestation",
            "compiler_id": "gcc-13.3.0",
            "compiler_sha256": "1353e9bdd29a7295c7226bf6c63abccce056d8cac31f112e5cdbecc3f28c2769",
            "cmake_generator": "Ninja",
            "cmake_configuration": "Release",
            "cmake_defines": ["CMAKE_BUILD_TYPE=Release", "CMAKE_C_COMPILER=/usr/bin/gcc", "CMAKE_CXX_COMPILER=/usr/bin/g++", "JFG_ENABLE_GENERATED_CODE=ON", "JFG_BUILD_G2_PRODUCERS=ON", "JFG_BUILD_TESTS=OFF", "JFG_BUILD_SYNTHETIC_GENERATED_TESTS=OFF", "JFG_GENERATED_ROOT=tools/results/phase4/semantic-audit-current-v3/normalized-phase8-hash-v4", "JFG_G2_PRIVATE_AUDIO_ADAPTER_ROOT=tools/results/phase4/private-audio-g2", "JFG_G2_PRIVATE_AUDIO_ORACLE_ROOT=tools/results/phase4/g2-production-audio-oracle-v2", "JFG_G2_PRIVATE_AUDIO_RUNTIME_INCLUDE=tools/upstream/N64ModernRuntime/librecomp/include", "JFG_G2_PRIVATE_GRAPHICS_ORACLE_ROOT=tools/results/phase4/g2-production-graphics-oracle-v2"],
            "producer_compile_flags": ["-O3", "-DNDEBUG", "-std=gnu++20", "-Wall", "-Wextra", "-Wconversion", "-Wpedantic", "-Wshadow", "-Werror"],
            "generated_compile_flags": ["-O3", "-DNDEBUG", "-Wall", "-Wextra", "-Wno-sign-compare", "-Wno-tautological-compare", "-Wno-type-limits", "-Wno-unused-label", "-Wno-unused-parameter", "-Wno-unused-variable", "-Wno-unused-but-set-variable", "-Werror"],
            "private_generated_closure_sha256": "619c9acc387bc9a9637178976be1cc113cf091330261a79ba7318c7040466b65",
            "tracked_dependency_closure_sha256": "080dfef5e6f4725c7199afa52b05afb640de1e8e7e4606226ceab2ff217cfe5d",
            "reviewed_commit": "4d245ccdd6cfcddad66f218431495ec038dfa945",
            "reviewed_tree": "2571bf03d837bc2cb7548f2810902fd66c287cdc",
        },
    })
)

PRODUCER_TRACKED_DEPENDENCY_PATHS = (
    "CMakeLists.txt",
    "cmake/GeneratedCode.cmake",
    "cmake/Warnings.cmake",
    "config/rsp-task-manifest.json",
    "include/jfg/evidence/g2_cpu_producer.hpp",
    "include/jfg/evidence/g2_paired_producer.hpp",
    "include/jfg/evidence/g2_private_task_adapter.hpp",
    "include/jfg/evidence/g2_private_task_case.hpp",
    "include/jfg/evidence/g2_rsp_producer.hpp",
    "include/jfg/evidence/g2_trap_probe_runtime.hpp",
    "include/jfg/evidence/g2_trap_producer.hpp",
    "include/jfg/platform/host.hpp",
    "include/jfg/runtime/audio_task_bridge.hpp",
    "include/jfg/runtime/bounded_custom_graphics.hpp",
    "include/jfg/runtime/controller_pak.hpp",
    "include/jfg/runtime/cpu_operation_bridge.h",
    "include/jfg/runtime/custom_overlay_relocator.hpp",
    "include/jfg/runtime/generated_overlay_runtime.hpp",
    "include/jfg/runtime/graphics_task_bridge.hpp",
    "include/jfg/runtime/log.hpp",
    "include/jfg/runtime/options.hpp",
    "include/jfg/runtime/rom_validator.hpp",
    "include/jfg/runtime/save_device_runtime.hpp",
    "src/evidence/g2_audio_native_producer.cpp",
    "src/evidence/g2_audio_oracle_producer.cpp",
    "src/evidence/g2_cpu_producer.cpp",
    "src/evidence/g2_graphics_bounded_adapter.cpp",
    "src/evidence/g2_graphics_native_producer.cpp",
    "src/evidence/g2_graphics_oracle_producer.cpp",
    "src/evidence/g2_overlay_producer.cpp",
    "src/evidence/g2_rsp_producer.cpp",
    "src/evidence/g2_save_native_producer.cpp",
    "src/evidence/g2_save_oracle_producer.cpp",
    "src/evidence/g2_trap_oracle_producer.cpp",
    "src/evidence/g2_trap_probe_runtime.cpp",
    "src/evidence/g2_trap_producer.cpp",
    "src/platform/host.cpp",
    "src/runtime/audio_task_bridge.cpp",
    "src/runtime/bounded_custom_graphics.cpp",
    "src/runtime/controller_pak.cpp",
    "src/runtime/custom_overlay_relocator.cpp",
    "src/runtime/generated_overlay_runtime.cpp",
    "src/runtime/graphics_task_bridge.cpp",
    "src/runtime/log.cpp",
    "src/runtime/options.cpp",
    "src/runtime/recomp_support/minimal_runtime.cpp",
    "src/runtime/rom_validator.cpp",
    "src/runtime/save_device_runtime.cpp",
)


def _reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _json_loads(payload: bytes) -> object:
    return json.loads(
        payload.decode("utf-8"),
        object_pairs_hook=_reject_duplicates,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
    )


def _canonical_bytes(value: object) -> bytes:
    def reject_nonfinite(item: object) -> None:
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError("non-finite number")
        if isinstance(item, dict):
            for key, nested in item.items():
                if not isinstance(key, str):
                    raise ValueError("non-string key")
                reject_nonfinite(nested)
        elif isinstance(item, list):
            for nested in item:
                reject_nonfinite(nested)

    reject_nonfinite(value)
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _is_placeholder(value: object) -> bool:
    return isinstance(value, str) and len(value) in {40, 64} and len(set(value)) == 1


def _metadata_is_reparse(metadata: os.stat_result) -> bool:
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse)


def _checked_absolute(path: Path, *, within: Path | None = None) -> Path:
    absolute = Path(os.path.abspath(path))
    if within is None:
        try:
            if _metadata_is_reparse(absolute.lstat()):
                raise EvidenceError("file boundary is invalid")
        except OSError as error:
            raise EvidenceError("file boundary is invalid") from error
        return absolute

    root = Path(os.path.abspath(within))
    try:
        relative = absolute.relative_to(root)
    except ValueError as error:
        raise EvidenceError("file boundary is invalid") from error
    current = root
    try:
        if _metadata_is_reparse(current.lstat()):
            raise EvidenceError("file boundary is invalid")
        for component in relative.parts:
            current = current / component
            if _metadata_is_reparse(current.lstat()):
                raise EvidenceError("file boundary is invalid")
        absolute.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (OSError, ValueError) as error:
        raise EvidenceError("file boundary is invalid") from error
    return absolute


def _open_checked(path: Path, *, within: Path | None = None) -> tuple[int, Path]:
    absolute = _checked_absolute(path, within=within)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        before = absolute.lstat()
        descriptor = os.open(absolute, flags)
        opened = os.fstat(descriptor)
        after = absolute.lstat()
        if (
            _metadata_is_reparse(before)
            or _metadata_is_reparse(after)
            or not stat.S_ISREG(opened.st_mode)
            or not os.path.samestat(before, opened)
            or not os.path.samestat(after, opened)
        ):
            raise EvidenceError("file boundary is invalid")
        _checked_absolute(absolute, within=within)
    except (OSError, ValueError, EvidenceError) as error:
        try:
            os.close(descriptor)  # type: ignore[possibly-undefined]
        except (OSError, UnboundLocalError):
            pass
        if isinstance(error, EvidenceError):
            raise
        raise EvidenceError("file boundary is invalid") from error
    return descriptor, absolute


def _read_regular_bounded(
    path: Path,
    *,
    max_bytes: int,
    within: Path | None = None,
) -> bytes:
    descriptor, _ = _open_checked(path, within=within)
    chunks: list[bytes] = []
    remaining = max_bytes + 1
    try:
        while remaining > 0:
            block = os.read(descriptor, min(1024 * 1024, remaining))
            if not block:
                break
            chunks.append(block)
            remaining -= len(block)
    except OSError as error:
        raise EvidenceError("file read failed") from error
    finally:
        os.close(descriptor)
    payload = b"".join(chunks)
    if len(payload) > max_bytes:
        raise EvidenceError("file read exceeded limit")
    return payload


def _hash_regular_bounded(
    path: Path,
    *,
    max_bytes: int,
    within: Path | None = None,
) -> str:
    descriptor, _ = _open_checked(path, within=within)
    digest = hashlib.sha256()
    total = 0
    try:
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            total += len(block)
            if total > max_bytes:
                raise EvidenceError("file read exceeded limit")
            digest.update(block)
    except OSError as error:
        raise EvidenceError("file read failed") from error
    finally:
        os.close(descriptor)
    return digest.hexdigest()


def load_json(path: Path, *, max_bytes: int = MAX_DOCUMENT_BYTES) -> object:
    return _json_loads(_read_regular_bounded(path, max_bytes=max_bytes))


def _fixed_git() -> Path | None:
    candidates = (
        Path("C:/Program Files/Git/cmd/git.exe"),
        Path("C:/Program Files/Git/bin/git.exe"),
        Path("/usr/bin/git"),
    )
    for candidate in candidates:
        try:
            if candidate.is_file() and not _metadata_is_reparse(candidate.lstat()):
                return candidate
        except OSError:
            continue
    return None


def _git_run(
    arguments: list[str], *, capture_stdout: bool = False
) -> tuple[int, bytes] | None:
    executable = _fixed_git()
    if executable is None:
        return None
    environment = {
        key: os.environ[key]
        for key in ("SYSTEMROOT", "WINDIR", "TMP", "TEMP")
        if key in os.environ
    }
    try:
        result = subprocess.run(
            [str(executable), "-C", str(ROOT), *arguments],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if capture_stdout else subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=environment,
            check=False,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    stdout = result.stdout if capture_stdout and result.stdout is not None else b""
    if len(stdout) > MAX_HARNESS_BYTES:
        return None
    return result.returncode, stdout


def _git_result(arguments: list[str]) -> int | None:
    result = _git_run(arguments)
    return None if result is None else result[0]


def _repository_relative(path: Path) -> PurePosixPath | None:
    absolute = Path(os.path.abspath(path))
    try:
        relative = absolute.relative_to(Path(os.path.abspath(ROOT)))
    except ValueError:
        return None
    return PurePosixPath(relative.as_posix())


def _private_path_is_allowed(path: Path) -> bool | None:
    relative = _repository_relative(path)
    if relative is None:
        return True
    tracked = _git_result(["ls-files", "--error-unmatch", "--", relative.as_posix()])
    if tracked is None:
        return None
    if tracked == 0:
        return False
    ignored = _git_result(["check-ignore", "-q", "--", relative.as_posix()])
    if ignored is None:
        return None
    return ignored == 0


def phase4_symbol_denominators(symbols: object) -> bool:
    """Recognize the fixed Phase 3 symbol partition carried into G2."""
    if not isinstance(symbols, dict):
        return False
    inventory_digest = symbols.get("inventory_sha256")
    approval_digest = symbols.get("approval_set_sha256")
    alias_ledger_digest = symbols.get("covered_alias_ledger_sha256")
    recovery_ledger_digest = symbols.get("manual_size_recovery_ledger_sha256")
    recovery_approval_digest = symbols.get(
        "manual_size_recovery_approval_set_sha256"
    )
    digests = (
        inventory_digest,
        approval_digest,
        alias_ledger_digest,
        recovery_ledger_digest,
        recovery_approval_digest,
    )
    return (
        symbols.get("expected_count") == EXPECTED_PHASE4_EXECUTABLE_SYMBOL_COUNT
        and symbols.get("generated_count") == EXPECTED_PHASE4_GENERATED_BODY_COUNT
        and symbols.get("replaceable_function_count")
        == EXPECTED_PHASE4_GENERATED_BODY_COUNT
        and symbols.get("excluded_count") == EXPECTED_PHASE4_COVERED_ALIAS_COUNT
        and symbols.get("exclusion_category_counts")
        == {
            "covered-alias": EXPECTED_PHASE4_COVERED_ALIAS_COUNT,
            "validated-non-code": 0,
            "runtime-abi": 0,
        }
        and symbols.get("manual_size_recovery_count") == 6
        and all(
            isinstance(digest, str)
            and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
            and not _is_placeholder(digest)
            for digest in digests
        )
    )


def _tracked_repository_file(path: Path) -> bool | None:
    relative = _repository_relative(path)
    if relative is None:
        return False
    result = _git_result(["ls-files", "--error-unmatch", "--", relative.as_posix()])
    return None if result is None else result == 0


def _tracked_blob(path: Path, revision: str) -> bytes | None:
    relative = _repository_relative(path)
    if relative is None:
        return None
    selector = (
        f":{relative.as_posix()}"
        if revision == "index"
        else f"{('HEAD' if revision == 'head' else revision)}:{relative.as_posix()}"
    )
    result = _git_run(["show", selector], capture_stdout=True)
    if result is None or result[0] != 0:
        return None
    return result[1]


def _git_object_id(selector: str) -> str | None:
    result = _git_run(["rev-parse", "--verify", selector], capture_stdout=True)
    if result is None or result[0] != 0:
        return None
    try:
        value = result[1].decode("ascii").strip()
    except UnicodeDecodeError:
        return None
    return value if re.fullmatch(r"[0-9a-f]{40}", value) else None


def _tracked_dependency_closure_errors(expected: Mapping[str, str]) -> list[str]:
    reviewed_commit = expected["reviewed_commit"]
    reviewed_tree = expected["reviewed_tree"]
    if (
        _git_object_id(reviewed_commit) != reviewed_commit
        or _git_object_id(f"{reviewed_commit}^{{tree}}") != reviewed_tree
        or _git_result(["merge-base", "--is-ancestor", reviewed_commit, "HEAD"]) != 0
    ):
        return ["private evidence: reviewed producer revision is unavailable"]
    # No tracked change anywhere may coexist with a production attestation.
    # Ignored private inputs remain outside this Git cleanliness check.
    if _git_result(["diff", "--quiet", "HEAD", "--"]) != 0:
        return ["private evidence: producer repository state is not clean"]
    rows: list[dict[str, str]] = []
    for textual in PRODUCER_TRACKED_DEPENDENCY_PATHS:
        path = ROOT.joinpath(*PurePosixPath(textual).parts)
        try:
            payload = _read_regular_bounded(path, max_bytes=MAX_HARNESS_BYTES, within=ROOT)
        except EvidenceError:
            return ["private evidence: tracked producer dependency is unavailable"]
        index_blob = _tracked_blob(path, "index")
        head_blob = _tracked_blob(path, "head")
        reviewed_blob = _tracked_blob(path, reviewed_commit)
        if (
            _tracked_repository_file(path) is not True
            or index_blob != payload
            or head_blob != payload
            or reviewed_blob != payload
        ):
            return ["private evidence: tracked producer dependency differs"]
        rows.append({"path": textual, "sha256": _sha256_bytes(payload)})
    if _sha256_bytes(_canonical_bytes(rows)) != expected["tracked_closure_sha256"]:
        return ["private evidence: tracked producer closure digest differs"]
    return []


def _producer_source_errors(
    requirement_id: str,
    execution: dict[str, object],
    bundle_root: Path,
) -> list[str]:
    """Validate reviewed source plus the case derivation before harness launch."""
    evidence_class = execution.get("evidence_class")
    if evidence_class not in EXECUTABLE_CLASSES:
        return []
    mapping = (requirement_id, str(evidence_class))
    expected = PRODUCER_SOURCE_PROVENANCE.get(mapping)
    if expected is None:
        return ["private evidence: producer source provenance is unavailable"]
    build = PRODUCER_BUILD_ATTESTATION.get(mapping)
    if build is None:
        return ["private evidence: producer build attestation is unavailable"]
    source = ROOT.joinpath(*PurePosixPath(expected["source_path"]).parts)
    try:
        source_bytes = _read_regular_bounded(source, max_bytes=MAX_HARNESS_BYTES, within=ROOT)
    except EvidenceError:
        return ["private evidence: producer source provenance is unavailable"]
    if _sha256_bytes(source_bytes) != expected["source_sha256"]:
        return ["private evidence: producer source differs from its reviewed digest"]
    tracked = _tracked_repository_file(source)
    index_blob = _tracked_blob(source, "index")
    head_blob = _tracked_blob(source, "head")
    if tracked is not True or index_blob != source_bytes or head_blob != source_bytes:
        return ["private evidence: producer source differs from its committed blob"]
    closure_errors = _tracked_dependency_closure_errors(expected)
    if closure_errors:
        return closure_errors
    artifacts = execution.get("artifacts")
    if not isinstance(artifacts, list):
        return ["private evidence: source derivation is unavailable"]
    configurations = [
        item for item in artifacts if isinstance(item, dict) and item.get("role") == "configuration"
    ]
    if len(configurations) != 1:
        return ["private evidence: source derivation is unavailable"]
    try:
        config = _json_loads(_read_regular_bounded(
            _artifact_path(bundle_root, configurations[0].get("path")),
            max_bytes=MAX_RESULT_BYTES,
            within=bundle_root,
        ))
    except (EvidenceError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return ["private evidence: source derivation is unavailable"]
    if not isinstance(config, dict) or not isinstance(config.get("source_derivation"), dict):
        return ["private evidence: source derivation is unavailable"]
    derivation = config["source_derivation"]
    expected_derivation: dict[str, object] = {
        "schema_version": 1,
        "kind": "jfg-g2-source-derivation",
        "supported_input_sha256": execution.get("source_input_sha256"),
        "bounded_case_sha256": execution.get("subject_sha256"),
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
    environment = execution.get("environment")
    if (
        not isinstance(build, Mapping)
        or not isinstance(environment, dict)
        or build.get("compiler_sha256") != environment.get("toolchain_sha256")
        or build.get("tracked_dependency_closure_sha256")
        != expected["tracked_closure_sha256"]
        or build.get("reviewed_commit") != expected["reviewed_commit"]
        or build.get("reviewed_tree") != expected["reviewed_tree"]
    ):
        return ["private evidence: producer build attestation is unbound"]
    try:
        if _canonical_bytes(derivation) != _canonical_bytes(expected_derivation):
            return ["private evidence: source derivation is unbound"]
    except (TypeError, ValueError, RecursionError):
        return ["private evidence: source derivation is unbound"]
    return []


def _schema_errors(document: object, schema: object) -> list[str]:
    try:
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        return ["schema: contract violation"] if any(validator.iter_errors(document)) else []
    except (SchemaError, TypeError, ValueError, RecursionError):
        return ["schema: contract unavailable"]


def _artifact_path(bundle_root: Path, textual: object) -> Path:
    if not isinstance(textual, str):
        raise EvidenceError("artifact boundary is invalid")
    parsed = PurePosixPath(textual)
    if (
        parsed.is_absolute()
        or not parsed.parts
        or any(part in {"", ".", ".."} for part in parsed.parts)
        or parsed.as_posix() != textual
    ):
        raise EvidenceError("artifact boundary is invalid")
    return _checked_absolute(bundle_root.joinpath(*parsed.parts), within=bundle_root)


def _bounded_pipe_reader(pipe: object, limit: int, destination: list[bytes]) -> None:
    try:
        destination.append(pipe.read(limit + 1))  # type: ignore[attr-defined]
    except (OSError, ValueError):
        destination.append(b"")
    finally:
        try:
            pipe.close()  # type: ignore[attr-defined]
        except (OSError, ValueError):
            pass


def _pipe_writer(pipe: object, payload: bytes, failed: list[bool]) -> None:
    try:
        pipe.write(payload)  # type: ignore[attr-defined]
        pipe.flush()  # type: ignore[attr-defined]
    except (BrokenPipeError, OSError, ValueError):
        failed.append(True)
    finally:
        try:
            pipe.close()  # type: ignore[attr-defined]
        except (OSError, ValueError):
            pass


def execute_pinned_harness(
    pin: PinnedHarness,
    request: object,
    bundle_root: Path,
    *,
    require_tracked: bool = True,
) -> tuple[object | None, list[str]]:
    """Run an externally selected, byte-pinned Python harness with bounded I/O."""
    errors: list[str] = []
    if not (0 < pin.timeout_seconds <= MAX_HARNESS_TIMEOUT_SECONDS):
        return None, ["private evidence: pinned harness policy is invalid"]
    try:
        harness_bytes = _read_regular_bounded(
            pin.script_path,
            max_bytes=MAX_HARNESS_BYTES,
            within=ROOT if require_tracked else None,
        )
    except EvidenceError:
        return None, ["private evidence: pinned harness is unavailable"]
    if _sha256_bytes(harness_bytes) != pin.script_sha256 or _is_placeholder(
        pin.script_sha256
    ):
        return None, ["private evidence: pinned harness identity differs"]
    if require_tracked:
        tracked = _tracked_repository_file(pin.script_path)
        if tracked is None:
            return None, ["private evidence: pinned harness tracking could not be verified"]
        if not tracked:
            return None, ["private evidence: pinned harness is not tracked"]
        index_blob = _tracked_blob(pin.script_path, "index")
        head_blob = _tracked_blob(pin.script_path, "head")
        if index_blob is None or head_blob is None:
            return None, ["private evidence: pinned harness committed blob is unavailable"]
        if index_blob != harness_bytes or head_blob != harness_bytes:
            return None, ["private evidence: pinned harness differs from its committed blob"]
    try:
        request_bytes = _canonical_bytes(request)
    except (TypeError, ValueError, RecursionError):
        return None, ["private evidence: harness request is invalid"]
    if len(request_bytes) > MAX_HARNESS_REQUEST_BYTES:
        return None, ["private evidence: harness request exceeds limit"]

    tools_root = ROOT / "tools"
    try:
        tools_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="g2-harness-", dir=tools_root) as temp:
            staged = Path(temp) / "harness.py"
            staged.write_bytes(harness_bytes)
            if _read_regular_bounded(staged, max_bytes=MAX_HARNESS_BYTES) != harness_bytes:
                return None, ["private evidence: staged harness identity differs"]
            environment = {
                key: os.environ[key]
                for key in (
                    "SYSTEMROOT",
                    "WINDIR",
                    "SystemDrive",
                    "ProgramData",
                    "ProgramFiles",
                    "ProgramFiles(x86)",
                    "ProgramW6432",
                    "ALLUSERSPROFILE",
                    "CommonProgramFiles",
                    "CommonProgramFiles(x86)",
                    "CommonProgramW6432",
                    "ComSpec",
                    "NUMBER_OF_PROCESSORS",
                    "OS",
                    "PATHEXT",
                    "PROCESSOR_ARCHITECTURE",
                    "PROCESSOR_IDENTIFIER",
                    "PROCESSOR_LEVEL",
                    "PROCESSOR_REVISION",
                    "TMP",
                    "TEMP",
                )
                if key in os.environ
            }
            environment.update(
                {
                    "JFG_PHASE4_REPOSITORY_ROOT": str(ROOT),
                    "PYTHONIOENCODING": "utf-8",
                    "PYTHONUTF8": "1",
                }
            )
            process = subprocess.Popen(
                [sys.executable, "-I", str(staged)],
                cwd=bundle_root,
                env=environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            assert process.stdin is not None
            assert process.stdout is not None
            assert process.stderr is not None
            stdout: list[bytes] = []
            stderr: list[bytes] = []
            write_failed: list[bool] = []
            threads = [
                threading.Thread(
                    target=_pipe_writer,
                    args=(process.stdin, request_bytes, write_failed),
                    daemon=True,
                ),
                threading.Thread(
                    target=_bounded_pipe_reader,
                    args=(process.stdout, MAX_HARNESS_STDOUT_BYTES, stdout),
                    daemon=True,
                ),
                threading.Thread(
                    target=_bounded_pipe_reader,
                    args=(process.stderr, MAX_HARNESS_STDERR_BYTES, stderr),
                    daemon=True,
                ),
            ]
            for thread in threads:
                thread.start()
            try:
                return_code = process.wait(timeout=pin.timeout_seconds)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
                return None, ["private evidence: pinned harness timed out"]
            for thread in threads:
                thread.join(timeout=1)
            stdout_bytes = stdout[0] if stdout else b""
            stderr_bytes = stderr[0] if stderr else b""
            if _read_regular_bounded(staged, max_bytes=MAX_HARNESS_BYTES) != harness_bytes:
                return None, ["private evidence: staged harness changed during execution"]
    except (OSError, subprocess.SubprocessError):
        return None, ["private evidence: pinned harness could not be executed"]

    if (
        return_code != 0
        or write_failed
        or len(stdout_bytes) > MAX_HARNESS_STDOUT_BYTES
        or len(stderr_bytes) > MAX_HARNESS_STDERR_BYTES
        or stderr_bytes
    ):
        return None, ["private evidence: pinned harness rejected the execution"]
    try:
        transcript = _json_loads(stdout_bytes)
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return None, ["private evidence: harness transcript is invalid"]
    return transcript, errors


def _result_expectation(
    execution: dict[str, object], requirement_id: str
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "kind": "jfg-g2-execution-result",
        "execution_id": execution.get("id"),
        "requirement_id": requirement_id,
        "evidence_class": execution.get("evidence_class"),
        "harness_id": execution.get("harness_id"),
        "harness_sha256": execution.get("harness_sha256"),
        "case_id": execution.get("case_id"),
        "subject_sha256": execution.get("subject_sha256"),
        "source_input_sha256": execution.get("source_input_sha256"),
        "pins_sha256": execution.get("pins_sha256"),
        "environment_sha256": execution.get("environment_sha256"),
        "input_set_sha256": execution.get("input_set_sha256"),
        "output_set_sha256": execution.get("output_set_sha256"),
        "observed_exit_code": execution.get("observed_exit_code"),
        "passed": execution.get("passed"),
    }


def _transcript_expectation(
    execution: dict[str, object], requirement_id: str
) -> dict[str, object]:
    expected = _result_expectation(execution, requirement_id)
    expected.update(
        {
            "kind": "jfg-g2-harness-transcript",
            "artifact_set_sha256": execution.get("artifact_set_sha256"),
            "result_sha256": execution.get("result_sha256"),
            "validated": True,
        }
    )
    return expected


def _execution_errors(
    document: dict[str, object],
    requirement_id: str,
    execution: dict[str, object],
    bundle_root: Path,
    harness_pins: Mapping[tuple[str, str], PinnedHarness],
    *,
    require_tracked_harnesses: bool,
    all_paths: set[str],
) -> list[str]:
    errors: list[str] = []
    artifacts = execution.get("artifacts")
    if not isinstance(artifacts, list):
        return ["private evidence: artifacts are unavailable"]
    role_records: dict[str, list[dict[str, object]]] = {
        role: []
        for role in ("configuration", "input", "output", "result", "log", "decision")
    }
    result_path: Path | None = None
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        textual_path = artifact.get("path")
        role = artifact.get("role")
        expected_digest = artifact.get("sha256")
        if isinstance(textual_path, str):
            if textual_path in all_paths:
                errors.append("private evidence: artifact paths are not globally unique")
            all_paths.add(textual_path)
        try:
            artifact_path = _artifact_path(bundle_root, textual_path)
            privacy = _private_path_is_allowed(artifact_path)
            if privacy is None:
                errors.append("private evidence: artifact privacy could not be verified")
            elif not privacy:
                errors.append("private evidence: artifact must be external or ignored")
            actual_digest = _hash_regular_bounded(
                artifact_path,
                max_bytes=MAX_ARTIFACT_BYTES,
                within=bundle_root,
            )
        except EvidenceError:
            errors.append("private evidence: artifact boundary or bounded read failed")
            artifact_path = None
            actual_digest = None
        if actual_digest != expected_digest:
            errors.append("private evidence: artifact digest mismatch")
        record = {"path": textual_path, "role": role, "sha256": expected_digest}
        if isinstance(role, str) and role in role_records:
            role_records[role].append(record)
            if role == "result" and artifact_path is not None:
                result_path = artifact_path

    if len(role_records["configuration"]) != 1:
        errors.append("private evidence: exactly one configuration artifact is required")
    if len(role_records["result"]) != 1:
        errors.append("private evidence: exactly one result artifact is required")
        result_path = None
    evidence_class = execution.get("evidence_class")
    if evidence_class in EXECUTABLE_CLASSES and not role_records["output"]:
        errors.append("private evidence: executable record has no output artifact")
    if evidence_class == "human-approved-decision":
        if len(role_records["decision"]) != 1:
            errors.append("private evidence: approved decision artifact is not bound exactly once")
        elif role_records["decision"][0].get("sha256") != execution.get(
            "subject_sha256"
        ):
            errors.append("private evidence: approved decision artifact is unbound")
    elif role_records["decision"]:
        errors.append("private evidence: unexpected decision artifact")
    elif execution.get("subject_sha256") not in {
        record.get("sha256") for record in role_records["input"]
    }:
        errors.append("private evidence: subject input artifact is unbound")

    input_records = (
        role_records["configuration"] + role_records["input"] + role_records["decision"]
    )
    output_records = role_records["output"] + role_records["log"]
    expected_values = {
        "pins_sha256": _sha256_bytes(_canonical_bytes(document.get("pins"))),
        "environment_sha256": _sha256_bytes(
            _canonical_bytes(execution.get("environment"))
        ),
        "input_set_sha256": _sha256_bytes(_canonical_bytes(input_records)),
        "output_set_sha256": _sha256_bytes(_canonical_bytes(output_records)),
        "artifact_set_sha256": _sha256_bytes(_canonical_bytes(artifacts)),
    }
    for field, expected in expected_values.items():
        if execution.get(field) != expected:
            errors.append("private evidence: execution binding digest is invalid")

    pins = document.get("pins")
    if isinstance(pins, dict):
        if requirement_id == "dependency-legal-selection":
            if execution.get("subject_sha256") != pins.get("architecture_decision_sha256"):
                errors.append("private evidence: decision subject is unbound")
            if execution.get("source_input_sha256") != pins.get("dependency_lock_sha256"):
                errors.append("private evidence: decision source is unbound")
        elif execution.get("source_input_sha256") != pins.get("input_rom_sha256"):
            errors.append("private evidence: source input does not match the pinned input")

    result_digest: str | None = None
    if result_path is not None:
        try:
            result_bytes = _read_regular_bounded(
                result_path,
                max_bytes=MAX_RESULT_BYTES,
                within=bundle_root,
            )
            result_digest = _sha256_bytes(result_bytes)
            result_document = _json_loads(result_bytes)
        except (EvidenceError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
            result_document = None
            errors.append("private evidence: structured result is invalid")
        if not isinstance(result_document, dict) or set(result_document) != _RESULT_KEYS:
            errors.append("private evidence: structured result contract differs")
        else:
            try:
                result_is_bound = _canonical_bytes(result_document) == _canonical_bytes(
                    _result_expectation(execution, requirement_id)
                )
            except (TypeError, ValueError, RecursionError):
                result_is_bound = False
            if not result_is_bound:
                errors.append("private evidence: structured result is unbound")
    if execution.get("result_sha256") != result_digest:
        errors.append("private evidence: result digest is unbound")

    for field in (
        "harness_sha256",
        "subject_sha256",
        "source_input_sha256",
        "pins_sha256",
        "environment_sha256",
        "input_set_sha256",
        "output_set_sha256",
        "artifact_set_sha256",
        "result_sha256",
    ):
        if _is_placeholder(execution.get(field)):
            errors.append("private evidence: placeholder identity is forbidden")

    # This precondition is intentionally outside the private dispatcher: a
    # staged harness cannot turn a mutable or opaque producer into provenance.
    if require_tracked_harnesses:
        errors.extend(_producer_source_errors(requirement_id, execution, bundle_root))

    harness_key = (requirement_id, str(evidence_class))
    pin = harness_pins.get(harness_key)
    if pin is None:
        errors.append("private evidence: pinned harness is unavailable")
    elif (
        execution.get("harness_id") != pin.harness_id
        or execution.get("harness_sha256") != pin.script_sha256
    ):
        errors.append("private evidence: execution does not use the pinned harness")
    elif not errors:
        request = {
            "schema_version": 1,
            "kind": "jfg-g2-harness-request",
            "pins": document.get("pins"),
            "execution": execution,
            "requirement_id": requirement_id,
        }
        transcript, harness_errors = execute_pinned_harness(
            pin,
            request,
            bundle_root,
            require_tracked=require_tracked_harnesses,
        )
        errors.extend(harness_errors)
        if not isinstance(transcript, dict) or set(transcript) != _TRANSCRIPT_KEYS:
            errors.append("private evidence: harness transcript contract differs")
        else:
            try:
                transcript_is_bound = _canonical_bytes(transcript) == _canonical_bytes(
                    _transcript_expectation(execution, requirement_id)
                )
            except (TypeError, ValueError, RecursionError):
                transcript_is_bound = False
            if not transcript_is_bound:
                errors.append("private evidence: harness transcript is unbound")
    return errors


def _paired_result_digest(
    requirement_id: str,
    execution: dict[str, object],
    bundle_root: Path,
) -> str | None:
    artifacts = execution.get("artifacts")
    if not isinstance(artifacts, list):
        return None
    configurations = [
        item
        for item in artifacts
        if isinstance(item, dict) and item.get("role") == "configuration"
    ]
    if len(configurations) != 1:
        return None
    try:
        config_path = _artifact_path(bundle_root, configurations[0].get("path"))
        config = _json_loads(
            _read_regular_bounded(
                config_path, max_bytes=MAX_RESULT_BYTES, within=bundle_root
            )
        )
        if not isinstance(config, dict):
            return None
        observation_sha256 = config.get("observation_sha256")
        observations = [
            item
            for item in artifacts
            if isinstance(item, dict)
            and item.get("role") == "output"
            and item.get("sha256") == observation_sha256
        ]
        if len(observations) != 1:
            return None
        observation_path = _artifact_path(bundle_root, observations[0].get("path"))
        observation = _json_loads(
            _read_regular_bounded(
                observation_path, max_bytes=MAX_ARTIFACT_BYTES, within=bundle_root
            )
        )
    except (EvidenceError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(observation, dict):
        return None
    evidence_class = execution.get("evidence_class")
    if requirement_id in {"graphics-tasks", "audio-tasks"}:
        field = (
            "output_sha256"
            if evidence_class == "private-native-execution"
            else "payload_sha256"
        )
        value = observation.get(field)
        return value if isinstance(value, str) else None
    if requirement_id == "save-round-trip":
        if evidence_class == "private-native-execution":
            trace = observation.get("semantic_trace")
            try:
                return _sha256_bytes(_canonical_bytes(trace))
            except (TypeError, ValueError, RecursionError):
                return None
        value = observation.get("semantic_trace_sha256")
        return value if isinstance(value, str) else None
    if requirement_id == "runtime-traps":
        value = observation.get("semantic_result_sha256")
        return value if isinstance(value, str) else None
    return None


def _execution_observation(
    execution: dict[str, object], bundle_root: Path
) -> dict[str, object] | None:
    artifacts = execution.get("artifacts")
    if not isinstance(artifacts, list):
        return None
    configurations = [
        item
        for item in artifacts
        if isinstance(item, dict) and item.get("role") == "configuration"
    ]
    if len(configurations) != 1:
        return None
    try:
        config_path = _artifact_path(bundle_root, configurations[0].get("path"))
        config = _json_loads(
            _read_regular_bounded(
                config_path, max_bytes=MAX_RESULT_BYTES, within=bundle_root
            )
        )
        if not isinstance(config, dict):
            return None
        observation_sha256 = config.get("observation_sha256")
        records = [
            item
            for item in artifacts
            if isinstance(item, dict)
            and item.get("role") == "output"
            and item.get("sha256") == observation_sha256
        ]
        if len(records) != 1:
            return None
        observation_path = _artifact_path(bundle_root, records[0].get("path"))
        observation = _json_loads(
            _read_regular_bounded(
                observation_path, max_bytes=MAX_ARTIFACT_BYTES, within=bundle_root
            )
        )
    except (EvidenceError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return None
    return observation if isinstance(observation, dict) else None


def _rsp_task_binding_errors(
    private_document: dict[str, object], bundle_root: Path
) -> list[str]:
    """Bind RSP classifications to independent real graphics/audio runs.

    The RSP inventory producer is deliberately classification-only.  It may
    not turn caller-supplied program bytes into a native execution claim.
    """
    requirements = private_document.get("requirements")
    if not isinstance(requirements, dict):
        return []

    def executions(requirement_id: str) -> list[dict[str, object]]:
        requirement = requirements.get(requirement_id)
        if not isinstance(requirement, dict) or not isinstance(
            requirement.get("executions"), list
        ):
            return []
        return [
            item
            for item in requirement["executions"]
            if isinstance(item, dict)
        ]

    rsp_runs = executions("rsp-programs")
    if len(rsp_runs) != 1:
        return ["private evidence: RSP task execution binding is absent"]
    rsp = _execution_observation(rsp_runs[0], bundle_root)
    if not isinstance(rsp, dict):
        return ["private evidence: RSP task execution binding is absent"]
    programs = rsp.get("programs")
    probes = rsp.get("native_probes")
    if not isinstance(programs, list) or not isinstance(probes, list):
        return ["private evidence: RSP task execution binding is absent"]
    by_family: dict[str, str] = {}
    for item in programs:
        if not isinstance(item, dict):
            return ["private evidence: RSP task execution binding is invalid"]
        family = item.get("family")
        evidence = item.get("classification_evidence_sha256")
        if not isinstance(family, str) or not isinstance(evidence, str) or family in by_family:
            return ["private evidence: RSP task execution binding is invalid"]
        by_family[family] = evidence
    if any(
        not isinstance(item, dict)
        or item.get("probe_kind") != "classification-only"
        or item.get("entry_count") != 0
        or item.get("broker_access_count") != 0
        or item.get("completion_count") != 0
        or item.get("program_exit_code") != 0
        for item in probes
    ):
        return ["private evidence: RSP inventory self-asserts native execution"]

    observed: dict[str, set[str]] = {}
    for requirement_id in ("graphics-tasks", "audio-tasks"):
        for execution in executions(requirement_id):
            if execution.get("evidence_class") not in {
                "private-native-execution",
                "private-oracle-execution",
            }:
                continue
            document = _execution_observation(execution, bundle_root)
            evidence = document.get("program_evidence_sha256") if isinstance(document, dict) else None
            if isinstance(evidence, str):
                observed.setdefault(requirement_id, set()).add(evidence)
    graphics = observed.get("graphics-tasks", set())
    audio = observed.get("audio-tasks", set())
    if (
        len(graphics) != 1
        or len(audio) != 1
        or by_family.get("graphics") not in graphics
        or by_family.get("audio-primary") not in audio
        or by_family.get("audio-secondary") not in audio
    ):
        return ["private evidence: RSP classifications are not bound to native task executions"]
    return []


def phase4_cpu_section_inventory(
    phase4_private_document: object,
    phase4_bundle_root: Path,
) -> dict[str, object] | None:
    """Load the exact CPU inventory authenticated by the G3 generation run."""
    if not isinstance(phase4_private_document, dict):
        return None
    executions = phase4_private_document.get("executions")
    if not isinstance(executions, list):
        return None
    generation = [
        item
        for item in executions
        if isinstance(item, dict) and item.get("evidence_kind") == "generation"
    ]
    if len(generation) != 1 or not isinstance(generation[0].get("artifacts"), list):
        return None
    artifacts: dict[str, dict[str, object]] = {}
    for raw in generation[0]["artifacts"]:
        if not isinstance(raw, dict):
            return None
        path = raw.get("path")
        if not isinstance(path, str) or path in artifacts:
            return None
        artifacts[path] = raw

    plans: list[dict[str, object]] = []
    try:
        for path, record in artifacts.items():
            if record.get("role") != "configuration":
                continue
            payload = _read_regular_bounded(
                _artifact_path(phase4_bundle_root, path),
                max_bytes=MAX_ARTIFACT_BYTES,
                within=phase4_bundle_root,
            )
            if _sha256_bytes(payload) != record.get("sha256"):
                return None
            candidate = _json_loads(payload)
            if (
                isinstance(candidate, dict)
                and candidate.get("kind") == "jfg-phase4-production-audit"
            ):
                plans.append(candidate)
        if len(plans) != 1:
            return None
        plan = plans[0]
        if (
            set(plan) != {"schema_version", "kind", "evidence_kind", "products"}
            or plan.get("schema_version") != 1
            or plan.get("evidence_kind") != "generation"
            or not isinstance(plan.get("products"), list)
        ):
            return None
        inventory_products = [
            item
            for item in plan["products"]
            if isinstance(item, dict)
            and set(item) == {"product_kind", "artifact_path"}
            and item.get("product_kind") == "cpu-section-inventory"
        ]
        if len(inventory_products) != 1:
            return None
        path = inventory_products[0].get("artifact_path")
        record = artifacts.get(path) if isinstance(path, str) else None
        if (
            record is None
            or record.get("role") != "output"
            or not path.startswith("production/generation/")
        ):
            return None
        payload = _read_regular_bounded(
            _artifact_path(phase4_bundle_root, path),
            max_bytes=MAX_ARTIFACT_BYTES,
            within=phase4_bundle_root,
        )
        if _sha256_bytes(payload) != record.get("sha256"):
            return None
        document = _json_loads(payload)
        if payload != _canonical_bytes(document) or not isinstance(document, dict):
            return None
    except (
        EvidenceError,
        OSError,
        UnicodeDecodeError,
        ValueError,
        json.JSONDecodeError,
        TypeError,
        RecursionError,
    ):
        return None
    if (
        set(document) != {"schema_version", "kind", "sections", "overlay_slots"}
        or document.get("schema_version") != 2
        or document.get("kind") != "jfg-phase4-cpu-section-inventory"
        or not isinstance(document.get("sections"), list)
        or not isinstance(document.get("overlay_slots"), list)
    ):
        return None
    return document


def cpu_g3_product_binding_sha256(
    phase4_private_document: object,
    phase4_public_document: object,
) -> str | None:
    """Commit a CPU record to the independently replayed G3 product set.

    This is deliberately a cross-bundle commitment.  A G2 CPU producer may
    report the value carried by its bounded case, but it cannot establish that
    value itself.  Trusted completion recomputes it only after the G3 private
    product harnesses have independently validated the corresponding records.
    """
    if not isinstance(phase4_private_document, dict) or not isinstance(
        phase4_public_document, dict
    ):
        return None
    executions = phase4_private_document.get("executions")
    if not isinstance(executions, list) or len(executions) != len(
        CPU_G3_EVIDENCE_KINDS
    ):
        return None
    by_kind: dict[str, dict[str, object]] = {}
    for item in executions:
        if not isinstance(item, dict):
            return None
        evidence_kind = item.get("evidence_kind")
        if evidence_kind not in CPU_G3_EVIDENCE_KINDS or not isinstance(
            evidence_kind, str
        ) or evidence_kind in by_kind:
            return None
        by_kind[evidence_kind] = item
    if set(by_kind) != set(CPU_G3_EVIDENCE_KINDS):
        return None

    if any(field not in phase4_public_document for field in G3_PRODUCT_CORE_FIELDS):
        return None
    public_projection = {
        field: phase4_public_document[field] for field in G3_PRODUCT_CORE_FIELDS
    }
    public_kind = phase4_public_document.get("kind")
    if public_kind == "jfg-phase4-g3-product-projection":
        private_evidence_sha256 = phase4_public_document.get(
            "private_evidence_sha256"
        )
    elif public_kind == "jfg-phase4-generated-manifest":
        attestation = phase4_public_document.get("attestation")
        private_evidence_sha256 = (
            attestation.get("private_evidence_sha256")
            if isinstance(attestation, dict)
            else None
        )
    else:
        return None
    if (
        not isinstance(private_evidence_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", private_evidence_sha256) is None
        or _is_placeholder(private_evidence_sha256)
    ):
        return None
    private_projection: list[dict[str, object]] = []
    identity_fields = (
        "id",
        "evidence_kind",
        "harness_id",
        "harness_sha256",
        "case_id",
        "public_record_sha256",
        "public_result_set_sha256",
        "subject_sha256",
        "source_input_sha256",
        "declaration_sha256",
        "pins_sha256",
        "environment_sha256",
        "input_set_sha256",
        "output_set_sha256",
        "observed_exit_code",
        "passed",
    )
    for evidence_kind in CPU_G3_EVIDENCE_KINDS:
        execution = by_kind[evidence_kind]
        digest_fields = (
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
        if (
            any(
                not isinstance(execution.get(field), str)
                or re.fullmatch(r"[0-9a-f]{64}", str(execution.get(field))) is None
                or _is_placeholder(execution.get(field))
                for field in digest_fields
            )
            or any(
                not isinstance(execution.get(field), str)
                or not execution.get(field)
                for field in ("id", "evidence_kind", "harness_id", "case_id")
            )
            or execution.get("observed_exit_code") != 0
            or execution.get("passed") is not True
        ):
            return None
        private_projection.append(
            {field: execution.get(field) for field in identity_fields}
        )
    projection = {
        "schema_version": 1,
        "kind": "jfg-g2-cpu-g3-product-binding",
        "g3_product_projection": public_projection,
        "private_evidence_sha256": private_evidence_sha256,
        "private_executions": private_projection,
    }
    try:
        return _sha256_bytes(_canonical_bytes(projection))
    except (TypeError, ValueError, RecursionError):
        return None


def validate_cpu_g3_binding(
    g2_private_document: object,
    g2_bundle_root: Path,
    phase4_private_document: object,
    phase4_public_document: object,
    phase4_bundle_root: Path | None = None,
) -> list[str]:
    """Cross-check G2 CPU aggregates against independently replayed G3 data."""
    error = "private evidence: CPU records are not bound to independently executed G3 products"
    if not isinstance(g2_private_document, dict) or not isinstance(
        phase4_public_document, dict
    ):
        return [error]
    requirements = g2_private_document.get("requirements")
    cpu = requirements.get("cpu-sections") if isinstance(requirements, dict) else None
    executions = cpu.get("executions") if isinstance(cpu, dict) else None
    if not isinstance(executions, list) or len(executions) != CPU_COMPILER_PRODUCT_COUNT:
        return [error]
    observations: list[dict[str, object]] = []
    for execution in executions:
        if not isinstance(execution, dict):
            return [error]
        observation = _execution_observation(execution, g2_bundle_root)
        if not isinstance(observation, dict):
            return [error]
        observations.append(observation)

    expected_binding = cpu_g3_product_binding_sha256(
        phase4_private_document, phase4_public_document
    )
    if expected_binding is None or {
        item.get("g3_product_binding_sha256") for item in observations
    } != {expected_binding}:
        return [error]

    # One case must describe one measured inventory; only the selected G3
    # compiler product may vary across its three producer executions.
    invariant_fields = ("sections", "overlay_slots", "link_audit", "analysis_records")
    try:
        invariant_records = {
            _canonical_bytes({field: item.get(field) for field in invariant_fields})
            for item in observations
        }
    except (TypeError, ValueError, RecursionError):
        return [error]
    if len(invariant_records) != 1:
        return [error]

    compilers = phase4_public_document.get("compilers")
    if not isinstance(compilers, list) or len(compilers) != 3:
        return [error]
    compiler_by_family: dict[str, dict[str, object]] = {}
    for item in compilers:
        if not isinstance(item, dict):
            return [error]
        family = item.get("family")
        if family not in {"clang", "gcc", "msvc"} or family in compiler_by_family:
            return [error]
        compiler_by_family[str(family)] = item
    expected_compiler_products = {
        (item.get("compiler_id"), item.get("compiler_executable_sha256"))
        for item in compiler_by_family.values()
    }
    observed_compiler_products = {
        (item.get("compiler_id"), item.get("compiler_executable_sha256"))
        for item in observations
    }
    if (
        len(expected_compiler_products) != CPU_COMPILER_PRODUCT_COUNT
        or any(None in item for item in expected_compiler_products)
        or observed_compiler_products != expected_compiler_products
    ):
        return [error]

    representative = observations[0]
    sections = representative.get("sections")
    audit = representative.get("link_audit")
    symbols = phase4_public_document.get("symbols")
    stubs = phase4_public_document.get("stubs")
    libraries = phase4_public_document.get("libraries")
    baseline = libraries.get("baseline") if isinstance(libraries, dict) else None
    runtime = libraries.get("minimal_runtime") if isinstance(libraries, dict) else None
    overlays = phase4_public_document.get("overlays")
    if not all(
        isinstance(value, dict)
        for value in (audit, symbols, stubs, baseline, runtime, overlays)
    ) or not isinstance(sections, list):
        return [error]
    if not phase4_symbol_denominators(symbols):
        return [error]

    if phase4_bundle_root is None:
        return [error]
    inventory = phase4_cpu_section_inventory(
        phase4_private_document, phase4_bundle_root
    )
    inventory_rows = inventory.get("sections") if isinstance(inventory, dict) else None
    inventory_slots = inventory.get("overlay_slots") if isinstance(inventory, dict) else None
    if not isinstance(inventory_rows, list) or not isinstance(inventory_slots, list):
        return [error]
    expected_sections: list[dict[str, object]] = []
    for row in inventory_rows:
        if not isinstance(row, dict):
            return [error]
        expected_sections.append(
            {
                "section_id": row.get("section_id"),
                "kind": row.get("kind"),
                "expected_body_count": row.get("expected"),
                "attempted_body_count": row.get("expected"),
                "generated_body_count": row.get("generated"),
                "approved_exclusion_count": row.get("excluded"),
                "unclassified_failure_count": 0,
                "lookup_entry_count": row.get("lookups"),
                "lifecycle_entry_count": row.get("lifecycle"),
                "relocation_entry_count": row.get("relocations"),
            }
        )
    try:
        if _canonical_bytes(sections) != _canonical_bytes(expected_sections):
            return [error]
    except (TypeError, ValueError, RecursionError):
        return [error]
    try:
        if _canonical_bytes(representative.get("overlay_slots")) != _canonical_bytes(
            inventory_slots
        ):
            return [error]
    except (TypeError, ValueError, RecursionError):
        return [error]

    def integer(value: object) -> int | None:
        return value if type(value) is int and value >= 0 else None

    totals: dict[str, int] = {
        "expected_body_count": 0,
        "generated_body_count": 0,
        "approved_exclusion_count": 0,
        "lookup_entry_count": 0,
        "relocation_entry_count": 0,
    }
    for section in sections:
        if not isinstance(section, dict):
            return [error]
        for field in totals:
            value = integer(section.get(field))
            if value is None:
                return [error]
            totals[field] += value
        if section.get("expected_body_count") != (
            int(section["generated_body_count"])
            + int(section["approved_exclusion_count"])
        ):
            return [error]

    assert isinstance(audit, dict)
    assert isinstance(symbols, dict)
    assert isinstance(stubs, dict)
    assert isinstance(baseline, dict)
    assert isinstance(runtime, dict)
    assert isinstance(overlays, dict)
    populated_slots = sum(
        isinstance(row, dict) and row.get("disposition") == "populated"
        for row in inventory_slots
    )
    empty_slots = sum(
        isinstance(row, dict) and row.get("disposition") == "empty-fail-closed"
        for row in inventory_slots
    )
    expected_pairs = (
        (totals["expected_body_count"], symbols.get("expected_count")),
        (totals["generated_body_count"], symbols.get("generated_count")),
        (totals["approved_exclusion_count"], symbols.get("excluded_count")),
        (totals["lookup_entry_count"], symbols.get("replaceable_function_count")),
        (totals["relocation_entry_count"], runtime.get("relocation_table_entry_count")),
        (audit.get("section_count"), overlays.get("executable_section_count")),
        (audit.get("section_count"), runtime.get("section_address_count")),
        (len(inventory_slots), overlays.get("expected_slot_count")),
        (len(inventory_slots), overlays.get("listed_slot_count")),
        (populated_slots, overlays.get("populated_slot_count")),
        (empty_slots, overlays.get("empty_slot_count")),
        (audit.get("expected_object_count"), baseline.get("unmodified_body_member_count")),
        (audit.get("generated_object_count"), baseline.get("unmodified_body_member_count")),
        (audit.get("forced_object_count"), baseline.get("unmodified_body_member_count")),
        (audit.get("generated_stub_count"), stubs.get("generated_game_function_stub_count")),
        (audit.get("expected_runtime_bridge_count"), runtime.get("handwritten_bridge_unit_count")),
        (audit.get("resolved_runtime_bridge_count"), runtime.get("handwritten_bridge_unit_count")),
    )
    if any(integer(left) is None or integer(right) is None or left != right for left, right in expected_pairs):
        return [error]
    return []


def _paired_result_errors(
    requirement_id: str,
    requirement: dict[str, object],
    bundle_root: Path,
) -> list[str]:
    if requirement_id not in NATIVE_AND_ORACLE:
        return []
    executions = requirement.get("executions")
    if not isinstance(executions, list):
        return []
    groups: dict[tuple[object, object, object], list[dict[str, object]]] = {}
    for item in executions:
        if not isinstance(item, dict) or item.get("evidence_class") not in {
            "private-native-execution",
            "private-oracle-execution",
        }:
            continue
        key = (
            item.get("case_id"),
            item.get("subject_sha256"),
            item.get("source_input_sha256"),
        )
        groups.setdefault(key, []).append(item)
    for group in groups.values():
        if len(group) != 2:
            continue
        digests = {
            _paired_result_digest(requirement_id, execution, bundle_root)
            for execution in group
        }
        if None in digests or len(digests) != 1:
            return ["private evidence: native/oracle result equality is unbound"]
    return []


def _paired_provenance_errors(
    requirement_id: str,
    requirement: dict[str, object],
) -> list[str]:
    """Reject an oracle that is merely a second view of the native route.

    Binary identity is enforced by the keyed production dispatcher mapping.
    This validator additionally makes the two reviewed source and build anchors
    non-interchangeable before either dispatcher is allowed to run.
    """
    executions = requirement.get("executions")
    if not isinstance(executions, list):
        return []
    groups: dict[tuple[object, object, object], list[dict[str, object]]] = {}
    for item in executions:
        if not isinstance(item, dict) or item.get("evidence_class") not in {
            "private-native-execution",
            "private-oracle-execution",
        }:
            continue
        key = (
            item.get("case_id"),
            item.get("subject_sha256"),
            item.get("source_input_sha256"),
        )
        groups.setdefault(key, []).append(item)

    errors: list[str] = []
    for group in groups.values():
        by_class = {str(item.get("evidence_class")): item for item in group}
        if len(group) != 2 or set(by_class) != {
            "private-native-execution",
            "private-oracle-execution",
        }:
            continue
        native_key = (requirement_id, "private-native-execution")
        oracle_key = (requirement_id, "private-oracle-execution")
        native_source = PRODUCER_SOURCE_PROVENANCE.get(native_key)
        oracle_source = PRODUCER_SOURCE_PROVENANCE.get(oracle_key)
        # Missing mappings already fail closed per execution.  Do not add a
        # second ambiguous error; this check is about a present-but-shared map.
        if native_source is not None and oracle_source is not None:
            source_identity = lambda value: (
                value.get("source_path"),
                value.get("source_sha256"),
                value.get("build_target"),
                value.get("adapter_id"),
                value.get("adapter_version"),
            )
            if source_identity(native_source) == source_identity(oracle_source):
                errors.append(
                    "private evidence: native/oracle producer provenance is shared"
                )
        native_build = PRODUCER_BUILD_ATTESTATION.get(native_key)
        oracle_build = PRODUCER_BUILD_ATTESTATION.get(oracle_key)
        if native_build is not None and oracle_build is not None:
            try:
                builds_are_shared = _canonical_bytes(native_build) == _canonical_bytes(
                    oracle_build
                )
            except (TypeError, ValueError, RecursionError):
                builds_are_shared = True
            native_closure = native_build.get("private_generated_closure_sha256")
            oracle_closure = oracle_build.get("private_generated_closure_sha256")
            if builds_are_shared or (
                isinstance(native_closure, str) and
                native_closure == oracle_closure
            ):
                errors.append(
                    "private evidence: native/oracle build provenance is shared"
                )
    return errors


def _runtime_trap_provenance_errors(requirement: dict[str, object]) -> list[str]:
    """Compatibility wrapper for focused callers of the original helper."""
    return _paired_provenance_errors("runtime-traps", requirement)


def _requirement_shape_errors(
    requirement_id: str, requirement: dict[str, object]
) -> list[str]:
    errors: list[str] = []
    executions = requirement.get("executions")
    if not isinstance(executions, list):
        return errors
    executable_count = sum(
        1
        for execution in executions
        if isinstance(execution, dict)
        and execution.get("evidence_class") in EXECUTABLE_CLASSES
    )
    if requirement.get("evidence_record_count") != len(executions):
        errors.append("private evidence: total evidence record count is unbound")
    if requirement.get("executable_evidence_count") != executable_count:
        errors.append("private evidence: executable evidence count is unbound")

    records = [item for item in executions if isinstance(item, dict)]
    classes = [str(item.get("evidence_class")) for item in records]
    executable_records = [
        item for item in records if item.get("evidence_class") in EXECUTABLE_CLASSES
    ]
    case_bindings: dict[str, tuple[object, object]] = {}
    for execution in records:
        case_id = execution.get("case_id")
        if not isinstance(case_id, str):
            continue
        binding = (execution.get("subject_sha256"), execution.get("source_input_sha256"))
        previous = case_bindings.setdefault(case_id, binding)
        if previous != binding:
            errors.append("private evidence: case subject binding is inconsistent")

    if requirement_id == "dependency-legal-selection":
        if classes != ["human-approved-decision"]:
            errors.append("private evidence: human-approved dependency decision is absent")
        return errors
    if "human-approved-decision" in classes:
        errors.append("private evidence: unexpected human decision record")

    if requirement_id == "cpu-sections":
        if any(
            item.get("evidence_class") != "private-g3-compiler-product-binding"
            for item in executable_records
        ):
            errors.append("private evidence: CPU evidence class is invalid")
        groups: dict[tuple[object, object, object], list[dict[str, object]]] = {}
        for item in executable_records:
            key = (
                item.get("case_id"),
                item.get("subject_sha256"),
                item.get("source_input_sha256"),
            )
            groups.setdefault(key, []).append(item)
        if not groups:
            errors.append("private evidence: CPU compiler-product binding is absent")
        for group in groups.values():
            if len(group) != CPU_COMPILER_PRODUCT_COUNT:
                errors.append("private evidence: CPU compiler-product matrix is incomplete")
    elif requirement_id in NATIVE_AND_ORACLE:
        allowed = {"private-native-execution", "private-oracle-execution"}
        if any(item.get("evidence_class") not in allowed for item in executable_records):
            errors.append("private evidence: paired execution class is invalid")
        groups: dict[tuple[object, object, object], list[dict[str, object]]] = {}
        for item in executable_records:
            key = (
                item.get("case_id"),
                item.get("subject_sha256"),
                item.get("source_input_sha256"),
            )
            groups.setdefault(key, []).append(item)
        if not groups:
            errors.append("private evidence: native/oracle pair is absent")
        for group in groups.values():
            group_classes = [item.get("evidence_class") for item in group]
            environments = {item.get("environment_sha256") for item in group}
            if (
                sorted(group_classes)
                != ["private-native-execution", "private-oracle-execution"]
                or len(environments) != 2
            ):
                errors.append("private evidence: native/oracle case pair is incomplete")
    elif requirement_id in SINGLE_NATIVE:
        if not executable_records or any(
            item.get("evidence_class") != "private-native-execution"
            for item in executable_records
        ):
            errors.append("private evidence: required native execution is absent")
    return errors


def _artifact_errors(
    document: dict[str, object],
    bundle_root: Path,
    harness_pins: Mapping[tuple[str, str], PinnedHarness],
    *,
    require_tracked_harnesses: bool,
) -> list[str]:
    errors: list[str] = []
    requirements = document.get("requirements")
    if not isinstance(requirements, dict):
        return ["private evidence: requirements are unavailable"]
    all_execution_ids: set[str] = set()
    all_paths: set[str] = set()
    for requirement_id in REQUIREMENT_IDS:
        requirement = requirements.get(requirement_id)
        if not isinstance(requirement, dict):
            continue
        errors.extend(_requirement_shape_errors(requirement_id, requirement))
        executions = requirement.get("executions")
        if not isinstance(executions, list):
            continue
        for execution in executions:
            if not isinstance(execution, dict):
                continue
            execution_id = execution.get("id")
            if not isinstance(execution_id, str) or execution_id in all_execution_ids:
                errors.append("private evidence: execution IDs are not globally unique")
            else:
                all_execution_ids.add(execution_id)
            errors.extend(
                _execution_errors(
                    document,
                    requirement_id,
                    execution,
                    bundle_root,
                    harness_pins,
                    require_tracked_harnesses=require_tracked_harnesses,
                    all_paths=all_paths,
                )
            )
        if require_tracked_harnesses:
            errors.extend(_paired_result_errors(requirement_id, requirement, bundle_root))
            if requirement_id in NATIVE_AND_ORACLE:
                errors.extend(
                    _paired_provenance_errors(requirement_id, requirement)
                )
    return errors


def _accepted_adr(text: str) -> bool:
    return accepted_architecture_decision(text)


def _validate_documents(
    private_document: object,
    public_document: object,
    private_schema: object,
    public_schema: object,
    bundle_root: Path,
    harness_pins: Mapping[tuple[str, str], PinnedHarness],
    *,
    require_tracked_harnesses: bool,
) -> list[str]:
    errors = _schema_errors(private_document, private_schema)
    errors.extend(_schema_errors(public_document, public_schema))
    if errors or not isinstance(private_document, dict) or not isinstance(public_document, dict):
        return sorted(set(errors))

    private_requirements = private_document.get("requirements")
    public_requirements = public_document.get("requirements")
    expected_private_set = (
        _sha256_bytes(_canonical_bytes(private_requirements))
        if isinstance(private_requirements, dict)
        else None
    )
    if private_document.get("evidence_set_sha256") != expected_private_set:
        errors.append("private evidence: requirement-set digest is unbound")
    private_pins = private_document.get("pins")
    public_pins = public_document.get("pins")
    expected_public_pins = (
        {
            key: value
            for key, value in private_pins.items()
            if key != "input_rom_sha256"
        }
        if isinstance(private_pins, dict)
        else None
    )
    if public_pins != expected_public_pins:
        errors.append("private evidence: public pins are not the safe private projection")

    try:
        lock_bytes = _read_regular_bounded(DEPENDENCY_LOCK, max_bytes=MAX_DOCUMENT_BYTES)
        decision_bytes = _read_regular_bounded(
            ARCHITECTURE_DECISION, max_bytes=MAX_DOCUMENT_BYTES
        )
        lock_digest = _sha256_bytes(lock_bytes)
        decision_digest = _sha256_bytes(decision_bytes)
        decision_text = decision_bytes.decode("utf-8")
    except (EvidenceError, UnicodeDecodeError):
        lock_bytes = None
        lock_digest = None
        decision_digest = None
        decision_text = ""
        errors.append("private evidence: repository pins are unavailable")

    pins = private_pins
    if isinstance(pins, dict):
        if pins.get("supported_input_id") != "jfg-us-retail":
            errors.append("private evidence: supported input policy is unbound")
        if pins.get("dependency_lock_sha256") != lock_digest:
            errors.append("private evidence: dependency lock digest is unbound")
        if pins.get("architecture_decision_sha256") != decision_digest:
            errors.append("private evidence: architecture decision digest is unbound")
    if not _accepted_adr(decision_text):
        errors.append("private evidence: architecture decision lacks authoritative acceptance")

    try:
        lock = _json_loads(lock_bytes) if lock_bytes is not None else None
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
        lock = None
        errors.append("private evidence: dependency lock could not be parsed")
    if isinstance(lock, dict) and isinstance(pins, dict):
        repositories = lock.get("repositories")
        if isinstance(repositories, list):
            by_id = {
                item.get("id"): item
                for item in repositories
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            }
            expected_commits = {
                "jfg_decomp_commit": by_id.get("jfg-decomp", {}).get("commit"),
                "n64recomp_commit": by_id.get("n64recomp", {}).get("commit"),
            }
            if any(pins.get(field) != value for field, value in expected_commits.items()):
                errors.append("private evidence: dependency commits differ from the lock")

    errors.extend(
        _artifact_errors(
            private_document,
            bundle_root,
            harness_pins,
            require_tracked_harnesses=require_tracked_harnesses,
        )
    )
    if require_tracked_harnesses:
        errors.extend(_rsp_task_binding_errors(private_document, bundle_root))

    if isinstance(private_requirements, dict) and isinstance(public_requirements, dict):
        expected_public_set = _sha256_bytes(_canonical_bytes(public_requirements))
        if public_document.get("evidence_set_sha256") != expected_public_set:
            errors.append("private evidence: public requirement-set digest is unbound")
        for requirement_id in REQUIREMENT_IDS:
            private_requirement = private_requirements.get(requirement_id)
            public_requirement = public_requirements.get(requirement_id)
            if not isinstance(private_requirement, dict) or not isinstance(public_requirement, dict):
                continue
            unresolved = private_requirement.get("unresolved")
            expected_result = _sha256_bytes(_canonical_bytes(private_requirement))
            if public_requirement.get("result_sha256") != expected_result:
                errors.append("private evidence: public requirement digest is unbound")
            if public_requirement.get("evidence_record_count") != private_requirement.get(
                "evidence_record_count"
            ):
                errors.append("private evidence: public evidence record count is unbound")
            if public_requirement.get("executable_evidence_count") != private_requirement.get(
                "executable_evidence_count"
            ):
                errors.append("private evidence: public executable count is unbound")
            if public_requirement.get("unresolved_count") != (
                len(unresolved) if isinstance(unresolved, list) else None
            ):
                errors.append("private evidence: public unresolved count is unbound")
    return sorted(set(errors))


def validate_documents(
    private_document: object,
    public_document: object,
    private_schema: object,
    public_schema: object,
    bundle_root: Path,
) -> list[str]:
    """Trusted in-memory validation; production harness selection is not injectable."""
    return _validate_documents(
        private_document,
        public_document,
        private_schema,
        public_schema,
        bundle_root,
        PRODUCTION_HARNESS_PINS,
        require_tracked_harnesses=True,
    )


def _validate_documents_for_tests(
    private_document: object,
    public_document: object,
    private_schema: object,
    public_schema: object,
    bundle_root: Path,
    harness_pins: Mapping[tuple[str, str], PinnedHarness],
) -> list[str]:
    """Internal unit-test seam; trusted file validators never call this function."""
    return _validate_documents(
        private_document,
        public_document,
        private_schema,
        public_schema,
        bundle_root,
        harness_pins,
        require_tracked_harnesses=False,
    )


def validate_files(private_path: Path, public_path: Path) -> list[str]:
    try:
        private_file = _checked_absolute(private_path)
        public_file = _checked_absolute(public_path)
        private_allowed = _private_path_is_allowed(private_file)
        if private_allowed is None:
            return ["private evidence: body privacy could not be verified"]
        if not private_allowed:
            return ["private evidence: body must be external or ignored"]
        private_document = load_json(private_file)
        public_document = load_json(public_file)
        private_schema = load_json(PRIVATE_SCHEMA, max_bytes=MAX_SCHEMA_BYTES)
        public_schema = load_json(PUBLIC_SCHEMA, max_bytes=MAX_SCHEMA_BYTES)
    except (EvidenceError, OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return ["private evidence: input could not be read"]
    return validate_documents(
        private_document,
        public_document,
        private_schema,
        public_schema,
        private_file.parent,
    )


def validate_private_file(private_path: Path, public_document: object) -> list[str]:
    """Validate an ignored bundle against an already parsed public G2 body."""
    try:
        private_file = _checked_absolute(private_path)
        private_allowed = _private_path_is_allowed(private_file)
        if private_allowed is None:
            return ["private evidence: body privacy could not be verified"]
        if not private_allowed:
            return ["private evidence: body must be external or ignored"]
        private_document = load_json(private_file)
        private_schema = load_json(PRIVATE_SCHEMA, max_bytes=MAX_SCHEMA_BYTES)
        public_schema = load_json(PUBLIC_SCHEMA, max_bytes=MAX_SCHEMA_BYTES)
    except (EvidenceError, OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return ["private evidence: input could not be read"]
    return validate_documents(
        private_document,
        public_document,
        private_schema,
        public_schema,
        private_file.parent,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-evidence", required=True, type=Path)
    parser.add_argument("--public-evidence", required=True, type=Path)
    arguments = parser.parse_args(argv)
    errors = validate_files(arguments.private_evidence, arguments.public_evidence)
    if errors:
        print("G2 private evidence validation failed: " + "; ".join(errors), file=sys.stderr)
        return 1
    print("G2 private evidence validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
