#!/usr/bin/env python3
"""Repository-owned dispatcher for private G2 executable evidence.

The validator executes a byte-pinned copy of this file with the ignored bundle
as its working directory.  The request cannot select a command.  Each fixed
requirement/evidence-class mapping has an exact artifact shape, fixed probe
protocol, and dedicated parser.  For executable classes the dispatcher reruns
the hash-bound subject and requires its canonical stdout to equal the bound
observation before deriving acceptance from granular records or raw bytes.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import secrets
import stat
import subprocess
import sys
import tempfile
import threading
from pathlib import Path, PurePosixPath


MAX_REQUEST_BYTES = 2 * 1024 * 1024
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
MAX_TOTAL_ARTIFACT_BYTES = 160 * 1024 * 1024
MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_PROBE_STDERR_BYTES = 64 * 1024
# The runtime-trap producer executes every reviewed trap class through the
# isolated single-child boundary with real per-probe deadlines; its honest
# wall-clock cost is tens of seconds, well above ordinary probes.
PROBE_TIMEOUT_SECONDS = 90.0
SHA256 = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]{1,70}[a-z0-9]$")
RSP_MANIFEST_EVIDENCE_SHA256 = (
    "99526b4401ef61307b21bc788a7b497711ffb33d3efb96391d2cae0687802a26"
)

MAPPING_IDS = {
    ("cpu-sections", "private-g3-compiler-product-binding"):
        "g2-cpu-sections-g3-product-v1",
    ("overlay-lifecycle", "private-native-execution"):
        "g2-overlay-lifecycle-native-v1",
    ("rsp-programs", "private-native-execution"):
        "g2-rsp-programs-native-v1",
    ("graphics-tasks", "private-native-execution"):
        "g2-graphics-native-v1",
    ("graphics-tasks", "private-oracle-execution"):
        "g2-graphics-oracle-v1",
    ("audio-tasks", "private-native-execution"):
        "g2-audio-native-v1",
    ("audio-tasks", "private-oracle-execution"):
        "g2-audio-oracle-v1",
    ("save-round-trip", "private-native-execution"):
        "g2-save-native-v1",
    ("save-round-trip", "private-oracle-execution"):
        "g2-save-oracle-v1",
    ("runtime-traps", "private-native-execution"):
        "g2-runtime-traps-native-v1",
    ("runtime-traps", "private-oracle-execution"):
        "g2-runtime-traps-oracle-v1",
    ("dependency-legal-selection", "human-approved-decision"):
        "g2-dependency-decision-v1",
}

PROBE_MARKERS = {
    ("cpu-sections", "private-g3-compiler-product-binding"): (
        b"jfg_g2_cpu_sections_probe",
        b"jfg_generated_link_smoke",
        b"jfg_generated_lookup_function",
    ),
    ("overlay-lifecycle", "private-native-execution"): (
        b"jfg_g2_overlay_lifecycle_probe",
        b"jfg_generated_section_lifecycle",
        b"jfg_generated_apply_relocations_checked",
        b"jfg_generated_lookup_function",
    ),
    ("rsp-programs", "private-native-execution"): (
        b"jfg_g2_rsp_programs_probe",
        b"jfg_g2_rsp_program_inventory",
    ),
    ("graphics-tasks", "private-native-execution"): (
        b"jfg_g2_graphics_native_probe",
        b"jfg_g2_graphics_real_task_backend_v2",
    ),
    ("graphics-tasks", "private-oracle-execution"): (
        b"jfg_g2_graphics_oracle_probe",
        b"jfg_g2_graphics_private_oracle_v2",
    ),
    ("audio-tasks", "private-native-execution"): (
        b"jfg_g2_audio_native_probe",
        b"jfg_g2_audio_generated_adapter_v2",
    ),
    ("audio-tasks", "private-oracle-execution"): (
        b"jfg_g2_audio_oracle_probe",
        b"jfg_g2_audio_private_oracle_v2",
    ),
    ("save-round-trip", "private-native-execution"): (
        b"jfg_g2_save_native_probe",
        b"jfg_g2_save_runtime",
    ),
    ("save-round-trip", "private-oracle-execution"): (
        b"jfg_g2_save_oracle_probe",
        b"jfg_g2_save_oracle",
    ),
    ("runtime-traps", "private-native-execution"): (
        b"jfg_g2_runtime_traps_probe",
        b"reserved_instruction",
        b"recomp_syscall_handler",
    ),
    ("runtime-traps", "private-oracle-execution"): (
        b"jfg_g2_runtime_traps_oracle_probe",
        b"jfg_g2_runtime_traps_oracle",
    ),
}

# A source record is a prerequisite, not a substitute, for a binary pin.  It
# deliberately names only tracked project source and public build structure;
# the private adapter and input stay outside the repository.
PRODUCER_SOURCE_PROVENANCE: dict[tuple[str, str], dict[str, str]] = {
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
# An exact binary pin cannot authorize itself.  This second independent map is
# populated only after the fixed compiler/configuration and the complete
# private generated-input closure have been reproduced and reviewed together.
PRODUCER_BUILD_ATTESTATION: dict[tuple[str, str], dict[str, object]] = {
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
}
PRODUCER_BINARY_SHA256: dict[tuple[str, str], str] = {
    ("cpu-sections", "private-g3-compiler-product-binding"): "017a0f17479182527ddee5f6ac87b29152e32b9f866d6958e19904f53b098823",
    ("overlay-lifecycle", "private-native-execution"): "198e696fc5064224a3da2decb9a1158e444bc7341ccc5aec5a987df55f4d5217",
    ("rsp-programs", "private-native-execution"): "2eb49dfe7d0c57dd52588b29d0279ed45581ae346dd18fd6655d43ce3bf7d8c5",
    ("graphics-tasks", "private-native-execution"): "774613585d906258ea40e5b91b09712a4065eb35139ae66ab0d9f13ce72a84c9",
    ("graphics-tasks", "private-oracle-execution"): "53554c431407b8f2ec16ca5da10c484e3ebe107d65fd251bf3bdf7a866078547",
    ("audio-tasks", "private-native-execution"): "7ba53201894fb940c106cdfe27f5eaa6a7fb638a4748c10925c4e439ca408c49",
    ("audio-tasks", "private-oracle-execution"): "b26ba9b9963c799626797d222a36a2232e279ea565a7b66260be0fc1049c7468",
    ("save-round-trip", "private-native-execution"): "766f2384bf326b64ab3cc1b0d44195a419e84043fe5ed3537c94e7096acbcabf",
    ("save-round-trip", "private-oracle-execution"): "26811bf53da05af7394920008fcfb774c4b4eced9814a92d603f48fe7161e0c0",
    ("runtime-traps", "private-native-execution"): "4d35c401ea2f17fd6654e5371c158c3bf85f18f61f7d2797978220c2b90e86c4",
    ("runtime-traps", "private-oracle-execution"): "00e133395d122dc6afd27b42c1ded33eadc224a081c54660785147a81771e629",
}

REQUEST_KEYS = {
    "schema_version",
    "kind",
    "pins",
    "execution",
    "requirement_id",
}
EXECUTION_KEYS = {
    "id",
    "evidence_class",
    "harness_id",
    "harness_sha256",
    "case_id",
    "subject_sha256",
    "source_input_sha256",
    "pins_sha256",
    "environment",
    "environment_sha256",
    "input_set_sha256",
    "output_set_sha256",
    "artifact_set_sha256",
    "result_sha256",
    "observed_exit_code",
    "passed",
    "artifacts",
}
ARTIFACT_KEYS = {"path", "role", "sha256"}
CONFIG_KEYS = {
    "schema_version",
    "kind",
    "requirement_id",
    "evidence_class",
    "case_id",
    "subject_sha256",
    "source_input_sha256",
    "observation_sha256",
    "policy_id",
    "source_derivation",
}
CPU_CONFIG_KEYS = CONFIG_KEYS | {
    "g3_compiler_id",
    "g3_compiler_executable_sha256",
}


def configuration_keys(mapping: tuple[str, str]) -> set[str]:
    if mapping == ("cpu-sections", "private-g3-compiler-product-binding"):
        return set(CPU_CONFIG_KEYS)
    keys = set(CONFIG_KEYS)
    if mapping == ("dependency-legal-selection", "human-approved-decision"):
        keys.remove("source_derivation")
    return keys


RESULT_KEYS = {
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
TRANSCRIPT_KEYS = set(RESULT_KEYS) | {
    "kind",
    "artifact_set_sha256",
    "result_sha256",
    "validated",
}
FORBIDDEN_OBSERVATION_KEYS = {
    "argv",
    "command",
    "command_line",
    "executable",
    "passed",
    "runner",
    "success",
    "validated",
}


class HarnessReject(Exception):
    pass


def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise HarnessReject()
        result[key] = value
    return result


def load_json_bytes(payload: bytes) -> object:
    if len(payload) > MAX_JSON_BYTES:
        raise HarnessReject()
    try:
        return json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda _value: (_ for _ in ()).throw(HarnessReject()),
        )
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
        raise HarnessReject() from None


def canonical_bytes(value: object) -> bytes:
    def visit(item: object) -> None:
        if isinstance(item, float) and not math.isfinite(item):
            raise HarnessReject()
        if isinstance(item, dict):
            for key, nested in item.items():
                if not isinstance(key, str):
                    raise HarnessReject()
                visit(nested)
        elif isinstance(item, list):
            for nested in item:
                visit(nested)

    visit(value)
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError):
        raise HarnessReject() from None


def digest_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def metadata_is_reparse(metadata: os.stat_result) -> bool:
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse)


def verify_staging_root(path: Path) -> None:
    metadata = path.lstat()
    if metadata_is_reparse(metadata):
        raise HarnessReject()
    if os.name == "nt":
        # Reviewed WSL launcher route: the staging directory is created
        # exclusively by this process, the staged producer and case are
        # written with O_EXCL/O_NOFOLLOW and rehashed both before launch and
        # after exit, and execution goes through the fixed absolute WSL
        # boundary rather than any native Windows producer.  Python's
        # mode/uid fields cannot prove an owner-only DACL, so identity is
        # enforced by those exclusive-creation and rehash checks instead.
        if not stat.S_ISDIR(metadata.st_mode):
            raise HarnessReject()
        return
    if metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise HarnessReject()


def write_all(descriptor: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(descriptor, payload[offset:])
        if written <= 0:
            raise HarnessReject()
        offset += written


def require_dict(value: object, keys: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise HarnessReject()
    return value


def require_list(value: object, *, nonempty: bool = True) -> list[object]:
    if not isinstance(value, list) or (nonempty and not value):
        raise HarnessReject()
    return value


def require_int(value: object, *, minimum: int = 0, maximum: int = 2**31) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise HarnessReject()
    return value


def require_identifier(value: object) -> str:
    if not isinstance(value, str) or IDENTIFIER.fullmatch(value) is None:
        raise HarnessReject()
    return value


def require_digest(value: object) -> str:
    if (
        not isinstance(value, str)
        or SHA256.fullmatch(value) is None
        or len(set(value)) == 1
    ):
        raise HarnessReject()
    return value


def require_exact(value: object, expected: object) -> None:
    if type(value) is not type(expected) or value != expected:
        raise HarnessReject()


def reject_assertion_fields(value: object) -> None:
    if isinstance(value, dict):
        if any(key in FORBIDDEN_OBSERVATION_KEYS for key in value):
            raise HarnessReject()
        for nested in value.values():
            reject_assertion_fields(nested)
    elif isinstance(value, list):
        for nested in value:
            reject_assertion_fields(nested)


def safe_artifact_path(textual: object) -> Path:
    if not isinstance(textual, str):
        raise HarnessReject()
    parsed = PurePosixPath(textual)
    if (
        parsed.is_absolute()
        or not parsed.parts
        or any(part in {"", ".", ".."} for part in parsed.parts)
        or parsed.as_posix() != textual
    ):
        raise HarnessReject()
    root = Path.cwd().resolve(strict=True)
    candidate = root.joinpath(*parsed.parts)
    current = root
    try:
        for component in parsed.parts:
            current = current / component
            metadata = current.lstat()
            if metadata_is_reparse(metadata):
                raise HarnessReject()
        candidate.resolve(strict=True).relative_to(root)
    except (OSError, ValueError):
        raise HarnessReject() from None
    return candidate


def read_regular(path: Path) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        before = path.lstat()
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        after = path.lstat()
        if (
            not stat.S_ISREG(opened.st_mode)
            or metadata_is_reparse(before)
            or metadata_is_reparse(after)
            or not os.path.samestat(before, opened)
            or not os.path.samestat(after, opened)
        ):
            raise HarnessReject()
        chunks: list[bytes] = []
        total = 0
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            total += len(block)
            if total > MAX_ARTIFACT_BYTES:
                raise HarnessReject()
            chunks.append(block)
        return b"".join(chunks)
    except OSError:
        raise HarnessReject() from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def artifact_records(
    execution: dict[str, object],
) -> tuple[dict[str, list[dict[str, object]]], dict[str, bytes]]:
    records = {
        role: []
        for role in ("configuration", "input", "output", "result", "log", "decision")
    }
    payloads: dict[str, bytes] = {}
    seen_paths: set[str] = set()
    total = 0
    artifacts = require_list(execution.get("artifacts"))
    for item in artifacts:
        record = require_dict(item, ARTIFACT_KEYS)
        path_text = record.get("path")
        if not isinstance(path_text, str) or path_text in seen_paths:
            raise HarnessReject()
        seen_paths.add(path_text)
        role = record.get("role")
        if not isinstance(role, str) or role not in records:
            raise HarnessReject()
        expected = require_digest(record.get("sha256"))
        payload = read_regular(safe_artifact_path(path_text))
        total += len(payload)
        if total > MAX_TOTAL_ARTIFACT_BYTES or digest_bytes(payload) != expected:
            raise HarnessReject()
        records[role].append(record)
        payloads[path_text] = payload
    if len(records["configuration"]) != 1 or len(records["result"]) != 1:
        raise HarnessReject()
    if records["log"]:
        raise HarnessReject()
    return records, payloads


def record_payload(
    record: dict[str, object], payloads: dict[str, bytes]
) -> bytes:
    path = record.get("path")
    if not isinstance(path, str) or path not in payloads:
        raise HarnessReject()
    return payloads[path]


def pipe_reader(pipe: object, maximum: int, sink: list[bytes]) -> None:
    try:
        sink.append(pipe.read(maximum + 1))  # type: ignore[attr-defined]
    except (OSError, ValueError):
        sink.append(b"")
    finally:
        try:
            pipe.close()  # type: ignore[attr-defined]
        except (OSError, ValueError):
            pass


def wsl_path(path: Path) -> str:
    drive, tail = os.path.splitdrive(str(path.resolve(strict=True)))
    if not drive or len(drive) != 2 or drive[1] != ":":
        raise HarnessReject()
    return f"/mnt/{drive[0].lower()}{tail.replace(chr(92), '/')}"


def _wsl_translate(path: Path) -> str:
    resolved = str(path.resolve(strict=True))
    drive, tail = os.path.splitdrive(resolved)
    if not drive or len(drive) != 2 or drive[1] != ":":
        raise HarnessReject()
    return f"/mnt/{drive[0].lower()}{tail.replace(chr(92), '/')}"


def product_command(path: Path, payload: bytes, arguments: list[str]) -> list[str]:
    if payload.startswith(b"MZ"):
        # Native Windows production execution stays disabled: the validator
        # cannot prove owner-only ACLs, non-reparse parents, and
        # executable-open identity for a PE producer.  Unit tests may replace
        # this selector, but evidence cannot.
        raise HarnessReject()
    if payload.startswith(b"\x7fELF"):
        if os.name != "nt":
            if not os.access(path, os.X_OK):
                raise HarnessReject()
            return [str(path), *arguments]
        # Reviewed WSL launcher route: execute the ELF producer through the
        # fixed absolute system WSL boundary and fixed distribution, exactly
        # as the pinned Phase 4 production harness executes its fixed ELF
        # probes.  The caller stages the producer and case exclusively and
        # rehashes both after exit, so a swap during execution is rejected.
        wsl = Path("C:/Windows/System32/wsl.exe")
        try:
            metadata = wsl.lstat()
        except OSError:
            raise HarnessReject() from None
        if metadata_is_reparse(metadata) or not stat.S_ISREG(metadata.st_mode):
            raise HarnessReject()
        return [
            str(wsl),
            "-d",
            "Ubuntu-24.04",
            "--exec",
            _wsl_translate(path),
            *arguments,
        ]
    raise HarnessReject()


def validate_source_derivation(
    mapping: tuple[str, str],
    config: dict[str, object],
    execution: dict[str, object],
) -> None:
    expected = PRODUCER_SOURCE_PROVENANCE.get(mapping)
    build = PRODUCER_BUILD_ATTESTATION.get(mapping)
    derivation = config.get("source_derivation")
    if expected is None or build is None or not isinstance(derivation, dict):
        raise HarnessReject()
    require_dict(
        build,
        {
            "schema_version",
            "kind",
            "compiler_id",
            "compiler_sha256",
            "cmake_generator",
            "cmake_configuration",
            "cmake_defines",
            "producer_compile_flags",
            "generated_compile_flags",
            "private_generated_closure_sha256",
            "tracked_dependency_closure_sha256",
            "reviewed_commit",
            "reviewed_tree",
        },
    )
    require_exact(build.get("schema_version"), 1)
    require_exact(build.get("kind"), "jfg-g2-producer-build-attestation")
    require_identifier(build.get("compiler_id"))
    require_digest(build.get("compiler_sha256"))
    environment = execution.get("environment")
    if not isinstance(environment, dict):
        raise HarnessReject()
    require_exact(build.get("compiler_sha256"), environment.get("toolchain_sha256"))
    require_exact(build.get("cmake_generator"), "Ninja")
    require_exact(build.get("cmake_configuration"), "Release")
    for field in ("cmake_defines", "producer_compile_flags", "generated_compile_flags"):
        values = require_list(build.get(field))
        if len(values) > 64 or any(
            not isinstance(item, str) or not item or len(item) > 160 for item in values
        ):
            raise HarnessReject()
    require_digest(build.get("private_generated_closure_sha256"))
    require_exact(
        build.get("tracked_dependency_closure_sha256"),
        expected["tracked_closure_sha256"],
    )
    require_exact(build.get("reviewed_commit"), expected["reviewed_commit"])
    require_exact(build.get("reviewed_tree"), expected["reviewed_tree"])
    required = {
        "schema_version",
        "kind",
        "supported_input_sha256",
        "bounded_case_sha256",
        "adapter_id",
        "adapter_version",
        "producer_source_path",
        "producer_source_sha256",
        "producer_source_revision",
        "producer_tree_revision",
        "tracked_dependency_closure_sha256",
        "build_system",
        "build_recipe_id",
        "build_target",
        "build_attestation",
    }
    require_dict(derivation, required)
    expected_derivation = {
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
    if canonical_bytes(derivation) != canonical_bytes(expected_derivation):
        raise HarnessReject()


def run_subject_probe(
    execution: dict[str, object],
    requirement: str,
    evidence_class: str,
    subject_record: dict[str, object],
    subject_payload: bytes,
    case_payload: bytes,
    observation_payload: bytes,
    config: dict[str, object],
) -> None:
    mapping = (requirement, evidence_class)
    policy_id = MAPPING_IDS.get(mapping)
    markers = PROBE_MARKERS.get(mapping)
    expected_producer = PRODUCER_BINARY_SHA256.get(mapping)
    validate_source_derivation(mapping, config, execution)
    case_id = require_identifier(execution.get("case_id"))
    subject_digest = require_digest(execution.get("subject_sha256"))
    if (
        policy_id is None
        or markers is None
        or expected_producer is None
        or digest_bytes(subject_payload) != expected_producer
        or not all(
            marker in subject_payload for marker in markers
        )
    ):
        raise HarnessReject()
    textual_path = subject_record.get("path")
    if not isinstance(textual_path, str):
        raise HarnessReject()
    parsed = PurePosixPath(textual_path)
    if (
        parsed.parent.as_posix()
        != f"production/{policy_id}/{execution.get('id')}"
        or parsed.name not in {"subject-probe", "subject-probe.exe"}
    ):
        raise HarnessReject()
    nonce = secrets.token_hex(32)
    original_path = safe_artifact_path(textual_path)
    try:
        with tempfile.TemporaryDirectory(prefix="g2-probe-") as temp:
            staged_root = Path(temp)
            verify_staging_root(staged_root)
            staged_subject = staged_root / parsed.name
            staged_case = staged_root / "case-input.bin"
            for staged, payload, mode in (
                (staged_subject, subject_payload, 0o500),
                (staged_case, case_payload, 0o400),
            ):
                descriptor = os.open(
                    staged,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0),
                    mode,
                )
                try:
                    write_all(descriptor, payload)
                finally:
                    os.close(descriptor)
                os.chmod(staged, mode)
            if os.name != "nt":
                staged_subject.chmod(0o500)
            if read_regular(staged_subject) != subject_payload or read_regular(staged_case) != case_payload:
                raise HarnessReject()
            arguments = [
                "--g2-evidence-probe", nonce, requirement, evidence_class,
                "--case-id", case_id, "--subject-sha256", subject_digest,
            ]
            if (requirement, evidence_class) == (
                "cpu-sections",
                "private-g3-compiler-product-binding",
            ):
                arguments += [
                    "--compiler-id",
                    require_identifier(config.get("g3_compiler_id")),
                    "--compiler-executable-sha256",
                    require_digest(config.get("g3_compiler_executable_sha256")),
                ]
            command = product_command(
                staged_subject,
                subject_payload,
                arguments,
            )
            environment = {
                key: os.environ[key]
                for key in ("SYSTEMROOT", "WINDIR", "TMP", "TEMP")
                if key in os.environ
            }
            process = subprocess.Popen(
                command,
                cwd=staged_root,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            assert process.stdout is not None
            assert process.stderr is not None
            stdout: list[bytes] = []
            stderr: list[bytes] = []
            readers = [
                threading.Thread(
                    target=pipe_reader,
                    args=(process.stdout, MAX_JSON_BYTES, stdout),
                    daemon=True,
                ),
                threading.Thread(
                    target=pipe_reader,
                    args=(process.stderr, MAX_PROBE_STDERR_BYTES, stderr),
                    daemon=True,
                ),
            ]
            for reader in readers:
                reader.start()
            try:
                return_code = process.wait(timeout=PROBE_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
                raise HarnessReject() from None
            for reader in readers:
                reader.join(timeout=1)
            # Re-open by no-follow identity after child exit: a replacement or
            # reparse-point swap cannot be accepted as the staged evidence.
            if read_regular(staged_subject) != subject_payload or read_regular(staged_case) != case_payload:
                raise HarnessReject()
    except (OSError, subprocess.SubprocessError):
        raise HarnessReject() from None
    stdout_payload = stdout[0] if stdout else b""
    stderr_payload = stderr[0] if stderr else b""
    if (
        return_code != 0
        or stderr_payload
        or len(stdout_payload) > MAX_JSON_BYTES
        or len(stderr_payload) > MAX_PROBE_STDERR_BYTES
    ):
        raise HarnessReject()
    response = load_json_bytes(stdout_payload)
    envelope = require_dict(response, {"execution_nonce", "observation"})
    require_exact(envelope.get("execution_nonce"), nonce)
    if canonical_bytes(envelope) != stdout_payload:
        raise HarnessReject()
    produced_observation = envelope.get("observation")
    if (
        not isinstance(produced_observation, dict)
        or canonical_bytes(produced_observation) != observation_payload
    ):
        raise HarnessReject()


def validate_common(
    request: object,
) -> tuple[
    dict[str, object],
    str,
    str,
    dict[str, list[dict[str, object]]],
    dict[str, bytes],
    dict[str, object],
]:
    document = require_dict(request, REQUEST_KEYS)
    require_exact(document.get("schema_version"), 1)
    require_exact(document.get("kind"), "jfg-g2-harness-request")
    requirement = document.get("requirement_id")
    if not isinstance(requirement, str):
        raise HarnessReject()
    execution = require_dict(document.get("execution"), EXECUTION_KEYS)
    evidence_class = execution.get("evidence_class")
    if not isinstance(evidence_class, str):
        raise HarnessReject()
    mapping = (requirement, evidence_class)
    policy_id = MAPPING_IDS.get(mapping)
    if policy_id is None:
        raise HarnessReject()

    self_digest = digest_bytes(Path(__file__).read_bytes())
    require_exact(execution.get("harness_id"), policy_id)
    require_exact(execution.get("harness_sha256"), self_digest)
    require_identifier(execution.get("id"))
    require_identifier(execution.get("case_id"))
    require_digest(execution.get("subject_sha256"))
    require_digest(execution.get("source_input_sha256"))
    require_digest(execution.get("pins_sha256"))
    require_digest(execution.get("environment_sha256"))
    require_digest(execution.get("input_set_sha256"))
    require_digest(execution.get("output_set_sha256"))
    require_digest(execution.get("artifact_set_sha256"))
    require_digest(execution.get("result_sha256"))
    require_exact(execution.get("observed_exit_code"), 0)
    require_exact(execution.get("passed"), True)
    if digest_bytes(canonical_bytes(document.get("pins"))) != execution.get("pins_sha256"):
        raise HarnessReject()
    if digest_bytes(canonical_bytes(execution.get("environment"))) != execution.get(
        "environment_sha256"
    ):
        raise HarnessReject()

    records, payloads = artifact_records(execution)
    input_records = records["configuration"] + records["input"] + records["decision"]
    output_records = records["output"] + records["log"]
    if digest_bytes(canonical_bytes(input_records)) != execution.get("input_set_sha256"):
        raise HarnessReject()
    if digest_bytes(canonical_bytes(output_records)) != execution.get("output_set_sha256"):
        raise HarnessReject()
    if digest_bytes(canonical_bytes(execution.get("artifacts"))) != execution.get(
        "artifact_set_sha256"
    ):
        raise HarnessReject()

    result_payload = record_payload(records["result"][0], payloads)
    if digest_bytes(result_payload) != execution.get("result_sha256"):
        raise HarnessReject()
    result = require_dict(load_json_bytes(result_payload), RESULT_KEYS)
    expected_result = {
        "schema_version": 1,
        "kind": "jfg-g2-execution-result",
        "execution_id": execution.get("id"),
        "requirement_id": requirement,
        "evidence_class": evidence_class,
        "harness_id": execution.get("harness_id"),
        "harness_sha256": execution.get("harness_sha256"),
        "case_id": execution.get("case_id"),
        "subject_sha256": execution.get("subject_sha256"),
        "source_input_sha256": execution.get("source_input_sha256"),
        "pins_sha256": execution.get("pins_sha256"),
        "environment_sha256": execution.get("environment_sha256"),
        "input_set_sha256": execution.get("input_set_sha256"),
        "output_set_sha256": execution.get("output_set_sha256"),
        "observed_exit_code": 0,
        "passed": True,
    }
    if canonical_bytes(result) != canonical_bytes(expected_result):
        raise HarnessReject()

    config_payload = record_payload(records["configuration"][0], payloads)
    config = require_dict(load_json_bytes(config_payload), configuration_keys(mapping))
    expected_config = {
        "schema_version": 1,
        "kind": "jfg-g2-production-case",
        "requirement_id": requirement,
        "evidence_class": evidence_class,
        "case_id": execution.get("case_id"),
        "subject_sha256": execution.get("subject_sha256"),
        "source_input_sha256": execution.get("source_input_sha256"),
        "observation_sha256": config.get("observation_sha256"),
        "policy_id": policy_id,
    }
    if mapping != ("dependency-legal-selection", "human-approved-decision"):
        expected_config["source_derivation"] = config.get("source_derivation")
    if mapping == ("cpu-sections", "private-g3-compiler-product-binding"):
        expected_config["g3_compiler_id"] = config.get("g3_compiler_id")
        expected_config["g3_compiler_executable_sha256"] = config.get(
            "g3_compiler_executable_sha256"
        )
    if canonical_bytes(config) != canonical_bytes(expected_config):
        raise HarnessReject()
    require_digest(config.get("observation_sha256"))
    if mapping != ("dependency-legal-selection", "human-approved-decision"):
        validate_source_derivation(mapping, config, execution)

    return execution, requirement, evidence_class, records, payloads, config


def observation_document(
    records: dict[str, list[dict[str, object]]],
    payloads: dict[str, bytes],
    config: dict[str, object],
) -> tuple[dict[str, object], bytes, list[tuple[dict[str, object], bytes]]]:
    output_records = records["output"]
    observation_digest = config.get("observation_sha256")
    matches = [item for item in output_records if item.get("sha256") == observation_digest]
    if len(matches) != 1:
        raise HarnessReject()
    observation_record = matches[0]
    observation_payload = record_payload(observation_record, payloads)
    observation = load_json_bytes(observation_payload)
    if (
        not isinstance(observation, dict)
        or canonical_bytes(observation) != observation_payload
    ):
        raise HarnessReject()
    reject_assertion_fields(observation)
    remaining = [
        (item, record_payload(item, payloads))
        for item in output_records
        if item is not observation_record
    ]
    return observation, observation_payload, remaining


def validate_observation_identity(
    observation: dict[str, object],
    execution: dict[str, object],
    expected_kind: str,
    *,
    schema_version: int = 1,
) -> None:
    require_exact(observation.get("schema_version"), schema_version)
    require_exact(observation.get("kind"), expected_kind)
    require_exact(observation.get("case_id"), execution.get("case_id"))
    require_exact(observation.get("subject_sha256"), execution.get("subject_sha256"))


def validate_overlay(observation: dict[str, object], execution: dict[str, object]) -> None:
    keys = {
        "schema_version",
        "kind",
        "case_id",
        "subject_sha256",
        "events",
        "relocations",
        "lifetimes",
        "memory_checks",
    }
    require_dict(observation, keys)
    validate_observation_identity(
        observation, execution, "jfg-g2-overlay-lifecycle-observation"
    )
    required_events = [
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
    event_kinds: list[str] = []
    previous_sequence = 0
    for raw in require_list(observation.get("events")):
        event = require_dict(raw, {"sequence", "kind", "generation"})
        sequence = require_int(event.get("sequence"), minimum=1)
        if sequence != previous_sequence + 1:
            raise HarnessReject()
        previous_sequence = sequence
        kind = event.get("kind")
        if not isinstance(kind, str):
            raise HarnessReject()
        require_int(event.get("generation"), minimum=1)
        event_kinds.append(kind)
    cursor = -1
    for kind in required_events:
        try:
            cursor = event_kinds.index(kind, cursor + 1)
        except ValueError:
            raise HarnessReject() from None

    relocation_classes = {"full-word", "jump-target", "hi16", "lo16"}
    seen_sites: set[str] = set()
    seen_classes: set[str] = set()
    for raw in require_list(observation.get("relocations")):
        item = require_dict(raw, {"site_id", "class", "generation", "write_count"})
        site = require_identifier(item.get("site_id"))
        if site in seen_sites:
            raise HarnessReject()
        seen_sites.add(site)
        relocation_class = item.get("class")
        if relocation_class not in relocation_classes:
            raise HarnessReject()
        seen_classes.add(str(relocation_class))
        require_int(item.get("generation"), minimum=1)
        require_exact(item.get("write_count"), 1)
    if seen_classes != relocation_classes:
        raise HarnessReject()

    lifetime_records = require_list(observation.get("lifetimes"))
    if len(lifetime_records) < 2:
        raise HarnessReject()
    generations: list[int] = []
    mappings: set[str] = set()
    states: set[str] = set()
    for raw in lifetime_records:
        item = require_dict(raw, {"generation", "mapping_sha256", "state_sha256"})
        generations.append(require_int(item.get("generation"), minimum=1))
        mappings.add(require_digest(item.get("mapping_sha256")))
        states.add(require_digest(item.get("state_sha256")))
    if generations != sorted(set(generations)) or len(mappings) != 1 or len(states) != 1:
        raise HarnessReject()

    required_phases = {"copy", "bss-clear", "reload"}
    observed_phases: set[str] = set()
    for raw in require_list(observation.get("memory_checks")):
        item = require_dict(
            raw,
            {
                "phase",
                "byte_count",
                "observed_sha256",
                "expected_sha256",
                "zero_byte_count",
            },
        )
        phase = item.get("phase")
        if phase not in required_phases or phase in observed_phases:
            raise HarnessReject()
        observed_phases.add(str(phase))
        byte_count = require_int(item.get("byte_count"), minimum=1)
        observed = require_digest(item.get("observed_sha256"))
        expected = require_digest(item.get("expected_sha256"))
        zero_count = require_int(item.get("zero_byte_count"), maximum=byte_count)
        if phase == "bss-clear":
            if zero_count != byte_count:
                raise HarnessReject()
        elif observed != expected or zero_count != 0:
            raise HarnessReject()
    if observed_phases != required_phases:
        raise HarnessReject()


def validate_rsp(observation: dict[str, object], execution: dict[str, object]) -> None:
    require_dict(
        observation,
        {
            "schema_version",
            "kind",
            "case_id",
            "subject_sha256",
            "programs",
            "overlay_slots",
            "native_probes",
        },
    )
    validate_observation_identity(
        observation, execution, "jfg-g2-rsp-program-observation"
    )
    expected_programs = {
        "graphics-representative": "graphics",
        "audio-primary": "audio-primary",
        "audio-secondary": "audio-secondary",
        "boot-loader": "other",
    }
    families = set(expected_programs.values())
    expected_by_family = {
        "graphics": ("executable", "rsp-graphics"),
        "audio-primary": ("executable", "rsp-audio-primary"),
        "audio-secondary": (
            "unsupported-with-fallback",
            "rsp-audio-secondary",
        ),
        "other": ("empty", "rsp-other"),
    }
    programs: dict[str, tuple[str, int, str]] = {}
    observed_families: set[str] = set()
    for raw in require_list(observation.get("programs")):
        item = require_dict(
            raw,
            {
                "program_id",
                "family",
                "generated_entry_count",
                "classification_evidence_sha256",
            },
        )
        program_id = require_identifier(item.get("program_id"))
        if (
            program_id in programs
            or program_id not in expected_programs
            or item.get("family") != expected_programs[program_id]
        ):
            raise HarnessReject()
        generated_entries = require_int(item.get("generated_entry_count"))
        family = str(item.get("family"))
        programs[program_id] = (
            family,
            generated_entries,
            require_digest(item.get("classification_evidence_sha256")),
        )
        observed_families.add(family)
    if (
        observed_families != families
        or set(programs) != set(expected_programs)
        or programs["boot-loader"][2] != RSP_MANIFEST_EVIDENCE_SHA256
    ):
        raise HarnessReject()

    slots_by_program: dict[str, tuple[str, str, str]] = {}
    slot_ids: set[str] = set()
    for raw in require_list(observation.get("overlay_slots")):
        item = require_dict(
            raw,
            {
                "slot_id",
                "program_id",
                "classification",
                "owner_id",
                "estimate_class",
                "evidence_sha256",
            },
        )
        slot = require_identifier(item.get("slot_id"))
        program_id = require_identifier(item.get("program_id"))
        if slot in slot_ids or program_id not in programs or program_id in slots_by_program:
            raise HarnessReject()
        slot_ids.add(slot)
        classification = item.get("classification")
        if classification not in {
            "executable",
            "empty",
            "unsupported-with-fallback",
        }:
            raise HarnessReject()
        owner = require_identifier(item.get("owner_id"))
        if item.get("estimate_class") not in {"small", "medium", "large"}:
            raise HarnessReject()
        evidence = require_digest(item.get("evidence_sha256"))
        family, _, classification_evidence = programs[program_id]
        expected_classification, expected_owner = expected_by_family[family]
        if (
            classification != expected_classification
            or owner != expected_owner
            or evidence != classification_evidence
        ):
            raise HarnessReject()
        slots_by_program[program_id] = (str(classification), owner, evidence)
    if set(slots_by_program) != set(programs):
        raise HarnessReject()

    probes_by_program: dict[str, tuple[str, int, int, int, int]] = {}
    for raw in require_list(observation.get("native_probes")):
        item = require_dict(
            raw,
            {
                "program_id",
                "probe_kind",
                "entry_count",
                "broker_access_count",
                "completion_count",
                "program_exit_code",
            },
        )
        program_id = require_identifier(item.get("program_id"))
        if program_id not in programs or program_id in probes_by_program:
            raise HarnessReject()
        kind = item.get("probe_kind")
        if kind != "classification-only":
            raise HarnessReject()
        entries = require_int(item.get("entry_count"))
        accesses = require_int(item.get("broker_access_count"))
        completions = require_int(item.get("completion_count"), maximum=1)
        program_exit = require_int(item.get("program_exit_code"), maximum=255)
        probes_by_program[program_id] = (
            str(kind), entries, accesses, completions, program_exit
        )
    if set(probes_by_program) != set(programs):
        raise HarnessReject()

    for program_id, (family, generated_entries, evidence) in programs.items():
        classification, owner, slot_evidence = slots_by_program[program_id]
        kind, entries, accesses, completions, program_exit = probes_by_program[program_id]
        expected_classification, expected_owner = expected_by_family[family]
        if (
            classification != expected_classification
            or owner != expected_owner
            or slot_evidence != evidence
            or kind != "classification-only"
            or generated_entries != 0
            or entries != 0
            or accesses != 0
            or completions != 0
            or program_exit != 0
        ):
            raise HarnessReject()


def validate_traps(
    observation: dict[str, object], execution: dict[str, object], *, oracle: bool = False
) -> None:
    require_dict(
        observation,
        {
            "schema_version",
            "kind",
            "case_id",
            "subject_sha256",
            "semantic_result_sha256",
            "candidate_counts",
            "records",
        },
    )
    validate_observation_identity(
        observation, execution,
        "jfg-g2-runtime-trap-oracle-observation" if oracle else
        "jfg-g2-runtime-trap-observation",
    )
    require_digest(observation.get("semantic_result_sha256"))
    kinds = {
        "cpu-break",
        "cpu-syscall",
        "switch-bounds",
        "boot-self-check",
        "dangling-jump-workaround",
        "checksum",
        "anti-tamper",
    }
    counts = require_dict(observation.get("candidate_counts"), kinds)
    expected_counts = {
        kind: require_int(counts.get(kind), maximum=1_000_000) for kind in kinds
    }
    if sum(expected_counts.values()) < 1:
        raise HarnessReject()
    observed_counts = {kind: 0 for kind in kinds}
    site_ids: set[str] = set()
    for raw in require_list(observation.get("records")):
        item = require_dict(
            raw,
            {
                "site_id",
                "kind",
                "reachability",
                "disposition",
                "owner_id",
                "estimate_class",
                "observed_hit_count",
                "mitigation_invocation_count",
                "native_trace_sha256",
                "oracle_trace_sha256",
                "static_review_sha256",
            },
        )
        site = require_identifier(item.get("site_id"))
        kind = item.get("kind")
        if site in site_ids or kind not in kinds:
            raise HarnessReject()
        site_ids.add(site)
        observed_counts[str(kind)] += 1
        reachability = item.get("reachability")
        disposition = item.get("disposition")
        require_identifier(item.get("owner_id"))
        if item.get("estimate_class") not in {
            "small",
            "medium",
            "large",
            "architecture-change",
        }:
            raise HarnessReject()
        hits = require_int(item.get("observed_hit_count"), maximum=10_000_000)
        mitigations = require_int(
            item.get("mitigation_invocation_count"), maximum=10_000_000
        )
        if reachability == "reachable":
            if disposition not in {"abort", "emulate", "defer-to-reviewed-handler"}:
                raise HarnessReject()
            if hits < 1 or mitigations < 1:
                raise HarnessReject()
            require_digest(item.get("native_trace_sha256"))
            require_digest(item.get("oracle_trace_sha256"))
            if item.get("static_review_sha256") is not None:
                raise HarnessReject()
        elif reachability == "unreachable":
            if disposition != "not-applicable" or hits != 0 or mitigations != 0:
                raise HarnessReject()
            require_digest(item.get("static_review_sha256"))
            if item.get("native_trace_sha256") is not None or item.get(
                "oracle_trace_sha256"
            ) is not None:
                raise HarnessReject()
        else:
            raise HarnessReject()
    if observed_counts != expected_counts:
        raise HarnessReject()


def validate_cpu(
    observation: dict[str, object],
    execution: dict[str, object],
    config: dict[str, object],
) -> None:
    require_dict(
        observation,
        {
            "schema_version",
            "kind",
            "case_id",
            "subject_sha256",
            "source_set_sha256",
            "compiler_id",
            "compiler_executable_sha256",
            "g3_product_binding_sha256",
            "sections",
            "overlay_slots",
            "link_audit",
            "analysis_records",
        },
    )
    validate_observation_identity(
        observation,
        execution,
        "jfg-g2-cpu-observation",
        schema_version=4,
    )
    require_digest(observation.get("g3_product_binding_sha256"))
    require_exact(observation.get("source_set_sha256"), execution.get("subject_sha256"))
    require_exact(observation.get("compiler_id"), config.get("g3_compiler_id"))
    require_exact(
        observation.get("compiler_executable_sha256"),
        config.get("g3_compiler_executable_sha256"),
    )
    require_identifier(observation.get("compiler_id"))
    require_digest(observation.get("compiler_executable_sha256"))

    section_ids: set[str] = set()
    section_kinds: set[str] = set()
    total_generated = 0
    sections = require_list(observation.get("sections"))
    for raw in sections:
        item = require_dict(
            raw,
            {
                "section_id",
                "kind",
                "expected_body_count",
                "attempted_body_count",
                "generated_body_count",
                "approved_exclusion_count",
                "unclassified_failure_count",
                "lookup_entry_count",
                "lifecycle_entry_count",
                "relocation_entry_count",
            },
        )
        section_id = require_identifier(item.get("section_id"))
        if section_id in section_ids or item.get("kind") not in {"main", "overlay"}:
            raise HarnessReject()
        section_ids.add(section_id)
        section_kinds.add(str(item.get("kind")))
        expected = require_int(item.get("expected_body_count"), minimum=1)
        attempted = require_int(item.get("attempted_body_count"), minimum=1)
        generated = require_int(item.get("generated_body_count"))
        exclusions = require_int(item.get("approved_exclusion_count"))
        failures = require_int(item.get("unclassified_failure_count"))
        lookups = require_int(item.get("lookup_entry_count"), minimum=1)
        lifecycle = require_int(item.get("lifecycle_entry_count"))
        require_int(item.get("relocation_entry_count"))
        if (
            attempted != expected
            or generated + exclusions != expected
            or failures != 0
            or lookups < generated
            or (item.get("kind") == "overlay" and lifecycle < 1)
        ):
            raise HarnessReject()
        total_generated += generated
    if section_kinds != {"main", "overlay"} or total_generated < 1:
        raise HarnessReject()

    overlay_section_ids = {
        str(item["section_id"])
        for item in sections
        if isinstance(item, dict) and item.get("kind") == "overlay"
    }
    populated_sections: set[str] = set()
    slot_ids: set[str] = set()
    empty_slot_count = 0
    for index, raw in enumerate(require_list(observation.get("overlay_slots")), start=1):
        item = require_dict(raw, {"slot_id", "disposition", "section_id"})
        slot_id = require_identifier(item.get("slot_id"))
        if slot_id != f"slot-{index:03d}" or slot_id in slot_ids:
            raise HarnessReject()
        slot_ids.add(slot_id)
        disposition = item.get("disposition")
        section_id = item.get("section_id")
        if disposition == "populated":
            if (
                not isinstance(section_id, str)
                or section_id not in overlay_section_ids
                or section_id in populated_sections
            ):
                raise HarnessReject()
            populated_sections.add(section_id)
        elif disposition == "empty-fail-closed" and section_id is None:
            empty_slot_count += 1
        else:
            raise HarnessReject()
    if populated_sections != overlay_section_ids or empty_slot_count < 1:
        raise HarnessReject()

    audit = require_dict(
        observation.get("link_audit"),
        {
            "section_count",
            "expected_object_count",
            "generated_object_count",
            "forced_object_count",
            "unresolved_symbol_count",
            "duplicate_definition_count",
            "generated_stub_count",
            "expected_runtime_bridge_count",
            "resolved_runtime_bridge_count",
        },
    )
    require_exact(audit.get("section_count"), len(sections))
    expected_objects = require_int(audit.get("expected_object_count"), minimum=1)
    if (
        require_int(audit.get("generated_object_count")) != expected_objects
        or require_int(audit.get("forced_object_count")) != expected_objects
        or require_int(audit.get("unresolved_symbol_count")) != 0
        or require_int(audit.get("duplicate_definition_count")) != 0
        or require_int(audit.get("generated_stub_count")) != 0
    ):
        raise HarnessReject()
    expected_bridges = require_int(audit.get("expected_runtime_bridge_count"))
    if require_int(audit.get("resolved_runtime_bridge_count")) != expected_bridges:
        raise HarnessReject()

    required_tools = {
        "compiler-link",
        "forced-object-audit",
        "asan",
        "ubsan",
        "clang-static-analyzer",
    }
    seen_tools: set[str] = set()
    for raw in require_list(observation.get("analysis_records")):
        item = require_dict(
            raw,
            {"tool", "exit_code", "finding_count", "source_set_sha256"},
        )
        tool = item.get("tool")
        if tool not in required_tools or tool in seen_tools:
            raise HarnessReject()
        seen_tools.add(str(tool))
        require_exact(item.get("exit_code"), 0)
        require_exact(item.get("finding_count"), 0)
        require_exact(item.get("source_set_sha256"), execution.get("subject_sha256"))
    if seen_tools != required_tools:
        raise HarnessReject()


def validate_graphics_native(
    observation: dict[str, object],
    execution: dict[str, object],
    remaining: list[tuple[dict[str, object], bytes]],
) -> None:
    require_dict(
        observation,
        {
            "schema_version",
            "kind",
            "case_id",
            "subject_sha256",
            "family",
            "renderer_path",
            "command_count",
            "parsed_command_count",
            "unsupported_command_count",
            "declared_region_count",
            "observed_region_count",
            "memory_access_count",
            "width",
            "height",
            "bytes_per_pixel",
            "row_pitch_bytes",
            "output_byte_count",
            "output_sha256",
            "program_evidence_sha256",
            "completion_events",
        },
    )
    validate_observation_identity(
        observation, execution, "jfg-g2-graphics-native-observation",
        schema_version=2,
    )
    require_exact(observation.get("family"), "f3ddkr-gbi")
    require_exact(observation.get("renderer_path"), "project-bounded-semantic")
    commands = require_int(observation.get("command_count"), minimum=1)
    require_exact(observation.get("parsed_command_count"), commands)
    require_exact(observation.get("unsupported_command_count"), 0)
    regions = require_int(observation.get("declared_region_count"), minimum=1)
    require_exact(observation.get("observed_region_count"), regions)
    require_int(observation.get("memory_access_count"), minimum=regions)
    width = require_int(observation.get("width"), minimum=1, maximum=8192)
    height = require_int(observation.get("height"), minimum=1, maximum=8192)
    bpp = require_int(observation.get("bytes_per_pixel"), minimum=1, maximum=16)
    pitch = require_int(observation.get("row_pitch_bytes"), minimum=width * bpp)
    byte_count = require_int(
        observation.get("output_byte_count"), minimum=1, maximum=64 * 1024 * 1024
    )
    if byte_count != pitch * height or len(remaining) != 1:
        raise HarnessReject()
    payload = remaining[0][1]
    if len(payload) != byte_count or digest_bytes(payload) != require_digest(
        observation.get("output_sha256")
    ):
        raise HarnessReject()
    require_digest(observation.get("program_evidence_sha256"))
    require_exact(
        observation.get("completion_events"),
        ["output-committed", "completion-prepared", "completion-committed"],
    )


def validate_exact_oracle(
    observation: dict[str, object],
    execution: dict[str, object],
    remaining: list[tuple[dict[str, object], bytes]],
    *,
    kind: str,
    maximum: int,
    alignment: int,
    schema_version: int = 1,
    require_program_evidence: bool = False,
) -> None:
    keys = {
        "schema_version",
        "kind",
        "case_id",
        "subject_sha256",
        "payload_byte_count",
        "payload_sha256",
        "element_alignment_bytes",
    }
    if require_program_evidence:
        keys.add("program_evidence_sha256")
    require_dict(
        observation,
        keys,
    )
    validate_observation_identity(
        observation, execution, kind, schema_version=schema_version
    )
    if require_program_evidence:
        require_digest(observation.get("program_evidence_sha256"))
    byte_count = require_int(
        observation.get("payload_byte_count"), minimum=1, maximum=maximum
    )
    require_exact(observation.get("element_alignment_bytes"), alignment)
    payload_digest = require_digest(observation.get("payload_sha256"))
    if byte_count % alignment != 0 or len(remaining) != 2:
        raise HarnessReject()
    first = remaining[0][1]
    second = remaining[1][1]
    if (
        len(first) != byte_count
        or len(second) != byte_count
        or first != second
        or digest_bytes(first) != payload_digest
        or digest_bytes(second) != payload_digest
    ):
        raise HarnessReject()


def validate_audio_native(
    observation: dict[str, object],
    execution: dict[str, object],
    remaining: list[tuple[dict[str, object], bytes]],
) -> None:
    require_dict(
        observation,
        {
            "schema_version",
            "kind",
            "case_id",
            "subject_sha256",
            "primary",
            "secondary_fallback",
            "output_byte_count",
            "output_sha256",
            "frame_alignment_bytes",
            "program_evidence_sha256",
        },
    )
    validate_observation_identity(
        observation, execution, "jfg-g2-audio-native-observation",
        schema_version=2,
    )
    primary = require_dict(
        observation.get("primary"),
        {
            "generated_entry_count",
            "parsed_command_count",
            "unsupported_command_count",
            "declared_region_count",
            "observed_region_count",
            "broker_read_count",
            "broker_write_count",
            "completion_count",
            "completion_events",
        },
    )
    require_exact(primary.get("generated_entry_count"), 1)
    require_int(primary.get("parsed_command_count"), minimum=1)
    require_exact(primary.get("unsupported_command_count"), 0)
    regions = require_int(primary.get("declared_region_count"), minimum=1)
    require_exact(primary.get("observed_region_count"), regions)
    require_int(primary.get("broker_read_count"), minimum=1)
    require_int(primary.get("broker_write_count"), minimum=1)
    require_exact(primary.get("completion_count"), 1)
    require_exact(
        primary.get("completion_events"),
        ["output-committed", "completion-prepared", "completion-committed"],
    )
    secondary = require_dict(
        observation.get("secondary_fallback"),
        {
            "generated_entry_count",
            "broker_write_count",
            "unsupported_return_count",
            "completion_count",
            "rolled_back_byte_count",
        },
    )
    require_exact(secondary.get("generated_entry_count"), 1)
    require_int(secondary.get("broker_write_count"), minimum=1)
    require_exact(secondary.get("unsupported_return_count"), 1)
    require_exact(secondary.get("completion_count"), 0)
    require_int(secondary.get("rolled_back_byte_count"), minimum=1)
    alignment = require_int(
        observation.get("frame_alignment_bytes"), minimum=1, maximum=64
    )
    byte_count = require_int(
        observation.get("output_byte_count"), minimum=alignment, maximum=1024 * 1024
    )
    if byte_count % alignment != 0 or len(remaining) != 1:
        raise HarnessReject()
    if len(remaining[0][1]) != byte_count or digest_bytes(remaining[0][1]) != require_digest(
        observation.get("output_sha256")
    ):
        raise HarnessReject()
    require_digest(observation.get("program_evidence_sha256"))


SAVE_OPERATIONS = {
    "allocate",
    "enumerate",
    "delete",
    "read",
    "write",
    "capacity",
    "persist",
    "fresh-process-reload",
    "restore",
    "missing",
    "bounds",
    "malformed",
}


def save_artifact_payloads(
    remaining: list[tuple[dict[str, object], bytes]],
) -> dict[str, bytes]:
    # The semantic trace names state artifacts by their fixed file names while
    # production artifacts are declared under the bounded per-execution
    # directory; key by final name and reject any collision.
    payloads: dict[str, bytes] = {}
    for metadata, payload in remaining:
        path = metadata.get("path")
        if not isinstance(path, str):
            raise HarnessReject()
        name = PurePosixPath(path).name
        if not name or name in payloads:
            raise HarnessReject()
        payloads[name] = payload
    return payloads


def validate_save_trace(
    document: object,
    case_id: object,
    subject: object,
    artifacts: dict[str, bytes] | None = None,
) -> dict[str, object]:
    trace = require_dict(
        document,
        {"schema_version", "kind", "case_id", "subject_sha256", "domains"},
    )
    reject_assertion_fields(trace)
    require_exact(trace.get("schema_version"), 1)
    require_exact(trace.get("kind"), "jfg-g2-save-semantic-trace")
    require_exact(trace.get("case_id"), case_id)
    require_exact(trace.get("subject_sha256"), subject)
    domains: set[str] = set()
    for raw in require_list(trace.get("domains")):
        item = require_dict(
            raw,
            {
                "domain",
                "operations",
                "initial_state_sha256",
                "written_state_sha256",
                "reloaded_state_sha256",
                "restored_state_sha256",
                "error_code_records",
                "state_artifacts",
            },
        )
        domain = item.get("domain")
        if domain not in {"controller-pak", "flashram"} or domain in domains:
            raise HarnessReject()
        domains.add(str(domain))
        operations = require_list(item.get("operations"))
        if set(operations) != SAVE_OPERATIONS or len(operations) != len(SAVE_OPERATIONS):
            raise HarnessReject()
        initial = require_digest(item.get("initial_state_sha256"))
        written = require_digest(item.get("written_state_sha256"))
        reloaded = require_digest(item.get("reloaded_state_sha256"))
        restored = require_digest(item.get("restored_state_sha256"))
        if written != reloaded or initial != restored or initial == written:
            raise HarnessReject()
        states = require_dict(
            item.get("state_artifacts"), {"initial", "written", "reloaded", "restored"}
        )
        expected_digests = {
            "initial": initial,
            "written": written,
            "reloaded": reloaded,
            "restored": restored,
        }
        expected_prefix = "controller-pak" if domain == "controller-pak" else "flashram"
        for stage, expected_digest in expected_digests.items():
            state = require_dict(states.get(stage), {"path", "sha256"})
            path = state.get("path")
            digest = require_digest(state.get("sha256"))
            if path != f"{expected_prefix}-{stage}.bin" or digest != expected_digest:
                raise HarnessReject()
            if artifacts is not None:
                payload = artifacts.get(path)
                if payload is None or digest_bytes(payload) != digest:
                    raise HarnessReject()
        errors = require_dict(item.get("error_code_records"), {"missing", "bounds", "malformed"})
        if any(require_int(errors.get(key), minimum=1, maximum=255) == 0 for key in errors):
            raise HarnessReject()
    if domains != {"controller-pak", "flashram"}:
        raise HarnessReject()
    return trace


def validate_save_native(
    observation: dict[str, object],
    execution: dict[str, object],
    remaining: list[tuple[dict[str, object], bytes]],
) -> None:
    require_dict(
        observation,
        {
            "schema_version",
            "kind",
            "case_id",
            "subject_sha256",
            "semantic_trace",
            "controller_pak_image_sha256",
            "flashram_image_sha256",
        },
    )
    validate_observation_identity(
        observation, execution, "jfg-g2-save-native-observation"
    )
    artifact_payloads = save_artifact_payloads(remaining)
    trace = validate_save_trace(
        observation.get("semantic_trace"),
        execution.get("case_id"),
        execution.get("subject_sha256"),
        artifact_payloads,
    )
    if set(artifact_payloads) != {
        "controller-pak-initial.bin", "controller-pak-written.bin",
        "controller-pak-reloaded.bin", "controller-pak-restored.bin",
        "flashram-initial.bin", "flashram-written.bin", "flashram-reloaded.bin",
        "flashram-restored.bin",
    }:
        raise HarnessReject()
    controller_digest = require_digest(observation.get("controller_pak_image_sha256"))
    flash_digest = require_digest(observation.get("flashram_image_sha256"))
    payloads = {digest_bytes(payload): payload for payload in artifact_payloads.values()}
    if controller_digest not in payloads or flash_digest not in payloads:
        raise HarnessReject()
    if not 1 <= len(payloads[controller_digest]) <= 1024 * 1024:
        raise HarnessReject()
    if len(payloads[flash_digest]) != 128 * 1024:
        raise HarnessReject()
    domains = {item["domain"]: item for item in require_list(trace["domains"])}
    if (
        domains["controller-pak"]["written_state_sha256"] != controller_digest
        or domains["flashram"]["written_state_sha256"] != flash_digest
    ):
        raise HarnessReject()


def validate_save_oracle(
    observation: dict[str, object],
    execution: dict[str, object],
    remaining: list[tuple[dict[str, object], bytes]],
) -> None:
    require_dict(
        observation,
        {
            "schema_version",
            "kind",
            "case_id",
            "subject_sha256",
            "semantic_trace_sha256",
        },
    )
    validate_observation_identity(
        observation, execution, "jfg-g2-save-oracle-observation"
    )
    trace_digest = require_digest(observation.get("semantic_trace_sha256"))
    artifact_payloads = save_artifact_payloads(remaining)
    expected_paths = {
        "semantic-trace-a.json", "semantic-trace-b.json",
        "controller-pak-initial.bin", "controller-pak-written.bin",
        "controller-pak-reloaded.bin", "controller-pak-restored.bin",
        "flashram-initial.bin", "flashram-written.bin", "flashram-reloaded.bin",
        "flashram-restored.bin",
    }
    if set(artifact_payloads) != expected_paths:
        raise HarnessReject()
    first = artifact_payloads["semantic-trace-a.json"]
    second = artifact_payloads["semantic-trace-b.json"]
    first_document = validate_save_trace(
        load_json_bytes(first), execution.get("case_id"), execution.get("subject_sha256"), artifact_payloads
    )
    second_document = validate_save_trace(
        load_json_bytes(second), execution.get("case_id"), execution.get("subject_sha256"), artifact_payloads
    )
    if (
        canonical_bytes(first_document) != canonical_bytes(second_document)
        or digest_bytes(canonical_bytes(first_document)) != trace_digest
        or digest_bytes(canonical_bytes(second_document)) != trace_digest
    ):
        raise HarnessReject()


def accepted_decision(payload: bytes) -> bool:
    try:
        lines = payload.decode("utf-8").replace("\r\n", "\n").splitlines()
    except UnicodeDecodeError:
        return False
    if not lines or re.fullmatch(r"# [^#].*", lines[0]) is None:
        return False
    index = 1
    while index < len(lines) and not lines[index].strip():
        index += 1
    accepted = "- Status: Accepted by `TK22-26`"
    markers = [line for line in lines if line.lstrip().startswith("- Status:")]
    return (
        index < len(lines)
        and lines[index] == accepted
        and markers == [accepted]
    )


def validate_dependency(
    execution: dict[str, object],
    records: dict[str, list[dict[str, object]]],
    payloads: dict[str, bytes],
    config: dict[str, object],
    pins: object,
) -> None:
    if (
        records["output"]
        or len(records["input"]) != 1
        or len(records["decision"]) != 1
    ):
        raise HarnessReject()
    input_payload = record_payload(records["input"][0], payloads)
    decision_payload = record_payload(records["decision"][0], payloads)
    require_exact(digest_bytes(input_payload), execution.get("source_input_sha256"))
    require_exact(digest_bytes(decision_payload), execution.get("subject_sha256"))
    require_exact(config.get("observation_sha256"), execution.get("subject_sha256"))
    pins_document = require_dict(
        pins,
        {
            "jfg_decomp_commit",
            "n64recomp_commit",
            "supported_input_id",
            "input_rom_sha256",
            "dependency_lock_sha256",
            "architecture_decision_sha256",
        },
    )
    require_exact(pins_document.get("supported_input_id"), "jfg-us-retail")
    require_exact(
        execution.get("source_input_sha256"), pins_document.get("dependency_lock_sha256")
    )
    require_exact(
        execution.get("subject_sha256"),
        pins_document.get("architecture_decision_sha256"),
    )
    if not accepted_decision(decision_payload):
        raise HarnessReject()
    lock = load_json_bytes(input_payload)
    if not isinstance(lock, dict) or not isinstance(lock.get("repositories"), list):
        raise HarnessReject()
    by_id: dict[str, dict[str, object]] = {}
    for item in lock["repositories"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise HarnessReject()
        identifier = item["id"]
        if identifier in by_id:
            raise HarnessReject()
        by_id[identifier] = item
    if not {
        "jfg-decomp",
        "n64recomp",
        "rt64",
        "n64modernruntime",
        "recompfrontend",
    }.issubset(by_id):
        raise HarnessReject()
    require_exact(by_id["jfg-decomp"].get("commit"), pins_document.get("jfg_decomp_commit"))
    require_exact(by_id["n64recomp"].get("commit"), pins_document.get("n64recomp_commit"))


def dispatch(
    execution: dict[str, object],
    requirement: str,
    evidence_class: str,
    records: dict[str, list[dict[str, object]]],
    payloads: dict[str, bytes],
    config: dict[str, object],
    pins: object,
) -> None:
    mapping = (requirement, evidence_class)
    if mapping == ("dependency-legal-selection", "human-approved-decision"):
        validate_dependency(execution, records, payloads, config, pins)
        return
    if len(records["input"]) != 2 or records["decision"]:
        raise HarnessReject()
    subject_records = [
        item
        for item in records["input"]
        if item.get("sha256") == execution.get("subject_sha256")
    ]
    probe_records = [item for item in records["input"] if item not in subject_records]
    if len(subject_records) != 1 or len(probe_records) != 1:
        raise HarnessReject()
    policy_id = MAPPING_IDS.get(mapping)
    subject_path = subject_records[0].get("path")
    if (
        policy_id is None
        or not isinstance(subject_path, str)
        or subject_path
        != f"production/{policy_id}/{execution.get('id')}/case-input.bin"
    ):
        raise HarnessReject()
    observation, observation_payload, remaining = observation_document(
        records, payloads, config
    )
    run_subject_probe(
        execution,
        requirement,
        evidence_class,
        probe_records[0],
        record_payload(probe_records[0], payloads),
        record_payload(subject_records[0], payloads),
        observation_payload,
        config,
    )

    if mapping == ("cpu-sections", "private-g3-compiler-product-binding"):
        if remaining:
            raise HarnessReject()
        validate_cpu(observation, execution, config)
    elif mapping == ("overlay-lifecycle", "private-native-execution"):
        if remaining:
            raise HarnessReject()
        validate_overlay(observation, execution)
    elif mapping == ("rsp-programs", "private-native-execution"):
        if remaining:
            raise HarnessReject()
        validate_rsp(observation, execution)
    elif mapping == ("runtime-traps", "private-native-execution"):
        if remaining:
            raise HarnessReject()
        validate_traps(observation, execution)
    elif mapping == ("runtime-traps", "private-oracle-execution"):
        if remaining:
            raise HarnessReject()
        validate_traps(observation, execution, oracle=True)
    elif mapping == ("graphics-tasks", "private-native-execution"):
        validate_graphics_native(observation, execution, remaining)
    elif mapping == ("graphics-tasks", "private-oracle-execution"):
        validate_exact_oracle(
            observation,
            execution,
            remaining,
            kind="jfg-g2-graphics-oracle-observation",
            maximum=64 * 1024 * 1024,
            alignment=32,
            schema_version=2,
            require_program_evidence=True,
        )
    elif mapping == ("audio-tasks", "private-native-execution"):
        validate_audio_native(observation, execution, remaining)
    elif mapping == ("audio-tasks", "private-oracle-execution"):
        validate_exact_oracle(
            observation,
            execution,
            remaining,
            kind="jfg-g2-audio-oracle-observation",
            maximum=1024 * 1024,
            alignment=4,
            schema_version=2,
            require_program_evidence=True,
        )
    elif mapping == ("save-round-trip", "private-native-execution"):
        validate_save_native(observation, execution, remaining)
    elif mapping == ("save-round-trip", "private-oracle-execution"):
        validate_save_oracle(observation, execution, remaining)
    else:
        raise HarnessReject()


def make_transcript(
    execution: dict[str, object], requirement: str
) -> dict[str, object]:
    transcript = {
        "schema_version": 1,
        "kind": "jfg-g2-harness-transcript",
        "execution_id": execution.get("id"),
        "requirement_id": requirement,
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
        "artifact_set_sha256": execution.get("artifact_set_sha256"),
        "result_sha256": execution.get("result_sha256"),
        "observed_exit_code": 0,
        "passed": True,
        "validated": True,
    }
    if set(transcript) != TRANSCRIPT_KEYS:
        raise HarnessReject()
    return transcript


def main() -> int:
    try:
        request_payload = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        if not request_payload or len(request_payload) > MAX_REQUEST_BYTES:
            raise HarnessReject()
        request = load_json_bytes(request_payload)
        execution, requirement, evidence_class, records, payloads, config = (
            validate_common(request)
        )
        assert isinstance(request, dict)
        dispatch(
            execution,
            requirement,
            evidence_class,
            records,
            payloads,
            config,
            request.get("pins"),
        )
        sys.stdout.buffer.write(canonical_bytes(make_transcript(execution, requirement)))
        return 0
    except (HarnessReject, OSError, RecursionError):
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
