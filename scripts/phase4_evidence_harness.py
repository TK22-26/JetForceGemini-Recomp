#!/usr/bin/env python3
"""Repository-pinned verifier for local-only Phase 4 execution products.

This program receives a canonical request on standard input.  It never accepts
an executable name, argument vector, shell fragment, or environment assignment
from that request.  The request may only associate fixed semantic product roles
with already hash-bound artifacts beneath the private bundle root.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import plistlib
import re
import stat
import subprocess
import sys
import tempfile
import threading
import zipfile
from pathlib import Path, PurePosixPath


MAX_REQUEST_BYTES = 2 * 1024 * 1024
MAX_ARTIFACT_BYTES = 128 * 1024 * 1024
MAX_ARCHIVE_EXPANDED_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_ENTRY_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 16_384
MAX_PROCESS_STDOUT = 128 * 1024
MAX_PROCESS_STDERR = 64 * 1024
PROCESS_TIMEOUT_SECONDS = 20.0
BUILD_REPLAY_TIMEOUT_SECONDS = 1800.0
MAX_SYSTEM_EXECUTABLE_BYTES = 128 * 1024 * 1024

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
IDENTIFIER_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{1,70}[a-z0-9]$")
BODY_RE = re.compile(
    rb"RECOMP_FUNC\s+void\s+(fn_[0-9]{3}_[0-9]{4})_recomp\s*\("
)
WRAPPER_RE = re.compile(
    rb"RECOMP_FUNC\s+void\s+(fn_[0-9]{3}_[0-9]{4})\s*\("
)

PRODUCT_KINDS = {
    "generation": frozenset(
        {
            "generation-input-archive",
            "generation-input-inventory",
            "generated-source-archive",
            "generation-result",
            "generated-inventory",
            "cpu-section-inventory",
            "source-file-inventory",
            "alternate-entry-ledger",
            "covered-alias-ledger",
            "exception-ledger",
            "manual-size-recovery-ledger",
            "n64recomp-decision-sidecar",
            "overlay-slot-inventory",
            "overlay-lookup-table",
            "overlay-lifecycle-table",
            "relocation-table",
            "report-set",
        }
    ),
    "compiler-clang": frozenset(
        {
            "compiler-result",
            "generated-source-archive",
            "source-file-inventory",
            "smoke-executable",
        }
    ),
    "compiler-gcc": frozenset(
        {
            "compiler-result",
            "generated-source-archive",
            "source-file-inventory",
            "smoke-executable",
        }
    ),
    "compiler-msvc": frozenset(
        {
            "compiler-result",
            "generated-source-archive",
            "source-file-inventory",
            "smoke-executable",
        }
    ),
    "forced-object-link-audit": frozenset(
        {
            "generated-source-archive",
            "source-file-inventory",
            "baseline-archive",
            "baseline-member-inventory",
            "baseline-result",
            "patch-archive",
            "patch-member-inventory",
            "patch-result",
            "minimal-runtime-result",
            "host-function-inventory",
            "host-data-inventory",
            "object-role-inventory",
            "overlay-lookup-table",
            "overlay-lifecycle-table",
            "relocation-table",
            "forced-link-executable",
        }
    ),
    "clang-static-analysis": frozenset(
        {
            "analysis-source-archive",
            "analysis-source-inventory",
            "analyzer-result",
        }
    ),
    "address-sanitizer": frozenset(
        {
            "analysis-source-archive",
            "analysis-source-inventory",
            "sanitizer-result",
        }
    ),
    "undefined-behavior-sanitizer": frozenset(
        {
            "analysis-source-archive",
            "analysis-source-inventory",
            "sanitizer-result",
        }
    ),
    "reproducibility-run-a": frozenset(
        {
            "generation-input-archive",
            "generation-input-inventory",
            "generated-source-archive",
            "normalized-run-payload",
            "generation-result",
            "generated-inventory",
            "cpu-section-inventory",
            "alternate-entry-ledger",
            "covered-alias-ledger",
            "exception-ledger",
            "manual-size-recovery-ledger",
            "n64recomp-decision-sidecar",
            "overlay-slot-inventory",
            "overlay-lookup-table",
            "overlay-lifecycle-table",
            "relocation-table",
            "report-set",
            "source-file-inventory",
            "baseline-member-inventory",
            "patch-member-inventory",
        }
    ),
    "reproducibility-run-b": frozenset(
        {
            "generation-input-archive",
            "generation-input-inventory",
            "generated-source-archive",
            "normalized-run-payload",
            "generation-result",
            "generated-inventory",
            "cpu-section-inventory",
            "alternate-entry-ledger",
            "covered-alias-ledger",
            "exception-ledger",
            "manual-size-recovery-ledger",
            "n64recomp-decision-sidecar",
            "overlay-slot-inventory",
            "overlay-lookup-table",
            "overlay-lifecycle-table",
            "relocation-table",
            "report-set",
            "source-file-inventory",
            "baseline-member-inventory",
            "patch-member-inventory",
        }
    ),
    "configuration-mutation": frozenset(
        {
            "base-config",
            "mutated-config-set",
            "predeclared-expectation",
            "config-diff-result",
            "base-run-payload",
            "mutated-run-payload",
        }
    ),
}

CANONICAL_JSON_PRODUCTS = frozenset(
    {
        "generated-inventory",
        "generation-result",
        "cpu-section-inventory",
        "generation-input-inventory",
        "source-file-inventory",
        "overlay-lookup-table",
        "overlay-lifecycle-table",
        "overlay-slot-inventory",
        "alternate-entry-ledger",
        "covered-alias-ledger",
        "exception-ledger",
        "manual-size-recovery-ledger",
        "n64recomp-decision-sidecar",
        "relocation-table",
        "report-set",
        "compiler-result",
        "baseline-member-inventory",
        "patch-member-inventory",
        "baseline-result",
        "patch-result",
        "minimal-runtime-result",
        "host-function-inventory",
        "host-data-inventory",
        "object-role-inventory",
        "analysis-source-inventory",
        "analyzer-result",
        "sanitizer-result",
        "normalized-run-payload",
        "mutated-config-set",
        "predeclared-expectation",
        "config-diff-result",
        "base-run-payload",
        "mutated-run-payload",
    }
)

ANALYSIS_SOURCE_POLICY_ID = "phase4-handwritten-bridges-analysis-v2"
ANALYSIS_BRIDGE_UNIT_COUNT = 3
ANALYSIS_SOURCE_SHA256 = {
    "analysis_minimal.cpp": "5cc62976e261a72100fc9490611221e61cfed08f164ce23e0eee87a4f36861ab",
    "analysis_overlay.cpp": "3c16f81a986d799133b3ec4a62963db5e92e847c4a9d23f0d133aeebce5bb637",
    "analysis_relocator.cpp": "444db23e186d4e5f4fad9b0925f1443f471324db0a14e75fd2f43eedb076187e",
    "minimal_runtime.cpp": "f87870c1eb6486b82faa24dad69fe3383e6113e4033a91d0b47042458e0b484c",
    "generated_overlay_runtime.cpp": "a141677aff6a69c4d9b5ecc9cf497af839b9f173285c7ca54a2a4e98a44f17ae",
    "custom_overlay_relocator.cpp": "6b92554dd5126f2f7646d7403491b3ce49ab59c39a334e10b087bfd0a332c7d4",
    "jfg/runtime/generated_overlay_runtime.hpp": "feac4b376bf0bc1297d27fe9e9495c1b3389438f24249810cd761a4167067f9d",
    "jfg/runtime/custom_overlay_relocator.hpp": "95df33ac372255a0baec188e4213300d44573393f5653a3587c61457824b0af9",
    "recomp.h": "4a3659fb9edc9caed50faf52c87c9280e17c2f1a9c8a8f85a4a9ee39d7be9d79",
}

# The compiler replay executes only repository-owned orchestration and audit
# sources.  These digests are refreshed together after the Phase 4 source
# closure is frozen; a later tracked edit therefore invalidates old private
# compiler evidence instead of silently changing what the pinned harness runs.
BUILD_REPLAY_SOURCE_SHA256 = {
    "CMakeLists.txt": "24876c00a39454cd490b2c5542a922f778ccf592dd686bf896f3c64133bbfa9b",
    "cmake/GeneratedCode.cmake": "61b0b884cbc9a13a7588c5597425459100c5cf28efc1776c5dc764394aba9559",
    "cmake/Warnings.cmake": "2c055d2fc0be4ef76857fad47241df7ff28be5804c4f7631994a8a0c29df099b",
    "scripts/audit_generated_objects.py": "02811af543a8dfa8e1f18e20e907e8689370b2f7b8a1683812d885a9e80c5d95",
    "scripts/build_private_generated_root.py": "5878bb58f1733575443461f6f31ad19fccb1a64af1f6c5c5aa9f82798538b3dd",
    "scripts/prepare_generated_sources.py": "0a6119d24f778a6235146e01fd8162198c241f4065950667e50eb7c489052b51",
    "src/runtime/recomp_support/minimal_runtime.cpp": "f87870c1eb6486b82faa24dad69fe3383e6113e4033a91d0b47042458e0b484c",
    "src/runtime/recomp_support/patch_archive_anchor.c": "67234d52186bd44ec01f6e1f2b6954226e7814588e64391bb4402df340dade17",
    "tests/CMakeLists.txt": "a4d4e79a7022d6dce8fa816522dacd338539f8b01654a68d8a762b91ca09061e",
    "tests/generated_baseline_audit.cpp": "e57edfec23a1f216546359330b31b5c03616ad0529292230dd20e8da3b26c7c1",
    "tests/generated_link_smoke.cpp": "7d285a0130bfc530f232a5e489abcea4dc5c653159e8bd91125f96f29f412e9f",
    "tests/generated_patch_audit.cpp": "e57edfec23a1f216546359330b31b5c03616ad0529292230dd20e8da3b26c7c1",
}

# This is intentionally the *complete tracked* input closure of the three
# BUILD_REPLAY_TARGETS below, rather than the broader project closure.  The
# targets are constructed exclusively by jfg_add_generated_code_tests:
#
# * their generated C/C++ and recomp.h inputs come from the hash-bound private
#   archive staged by _write_generated_source_root;
# * the only handwritten compilation units are minimal_runtime.cpp,
#   patch_archive_anchor.c, and the three audit mains; and
# * configuration reads the top-level CMake file, these two CMake modules, and
#   the two repository scripts launched during configure/build.
#
# In particular, none of these targets links jfg_runtime.  Adding an unrelated
# runtime source or header here would make the policy look more comprehensive
# while concealing a target-closure error.
BUILD_REPLAY_TRACKED_CLOSURE = frozenset(BUILD_REPLAY_SOURCE_SHA256)

# Generation executes a different, deliberately narrow tracked closure.  These
# scripts operate only on the staged private evidence input and temporary
# output tree; they are kept separate from the CMake target closure above so a
# future runtime source cannot silently become trusted for either replay.
GENERATION_REPLAY_SOURCE_SHA256 = {
    "scripts/build_private_generated_root.py": "5878bb58f1733575443461f6f31ad19fccb1a64af1f6c5c5aa9f82798538b3dd",
    "scripts/probe_n64recomp_cpu.py": "26f7c5ad63fc35cc0230e5dc5c4bf39919203d451185ed13c274068d934f7b2d",
    "scripts/prepare_n64recomp_context_dump.py": "076bd0b00dad27c5c5109c0554a5bf28c588405dc012dce262bf7f84ecf9b546",
    "scripts/public_safe.py": "19df42298ddd6f7ad032eabe07e30d56dae93fe9a4a1d3757201506ec7aab498",
    "scripts/transform_private_n64recomp_inputs.py": "0f314f1751cafc180ec63a78ebe385116bcced6636bee06bdee13541fffca98b",
    "scripts/validate_elf.py": "2b5e394857b5d7200235710256f8b271d9789fb5c87eed7da5ee2cfe0720be47",
}

BUILD_REPLAY_TARGETS = (
    "jfg_generated_link_smoke",
    "jfg_generated_baseline_audit",
    "jfg_generated_patch_audit",
)

# GCC's C and C++ drivers are distinct executables.  The public compiler row
# binds g++-13; this separate repository policy pin prevents a same-version but
# different gcc-13 binary from compiling the generated C translation units.
GCC_C_DRIVER_SHA256 = "1b99826121ae6682a634e5efe09bd3e3df58ce58e0b28f849114ab5b89139c26"
GCC_CXX_DRIVER_SHA256 = "1353e9bdd29a7295c7226bf6c63abccce056d8cac31f112e5cdbecc3f28c2769"

# Tool identities are separate from the public compiler executable pin.  CMake
# launches these helpers while configuring, archiving, auditing objects, and
# linking the replay targets, so treating only the front-end as trusted would
# leave a material execution path unbound.  These are exact executable paths
# in the fixed Ubuntu-24.04 boundary; the compiler's cc1/cc1plus/collect2
# helpers are included because gcc-13 invokes them directly.
WSL_BUILD_TOOL_SHA256 = {
    "/usr/bin/cmake": "1c5227af4edd22d8d689def545e18ee458260c0fd579eba2187967f38817e638",
    "/usr/bin/ninja": "5965527e09fe2b3787772aa4f711d6a36b393e7f2fcaa744a7a96c5a4ddf59cb",
    "/usr/bin/gcc-13": GCC_C_DRIVER_SHA256,
    "/usr/bin/g++-13": GCC_CXX_DRIVER_SHA256,
    "/usr/bin/ar": "534681ac11c18868cfc4fdf98770aa0ba8973eedc90c231e94e6ba96e1a04f27",
    "/usr/bin/ranlib": "3fb728371b8fff3c7cf74c0cf2184293717b8729f591bb2290b540dfd92edef7",
    "/usr/bin/nm": "910ad8a63896f722374fdf22951d2a436c74e3ac9677511cc56378296bdf86cc",
    "/usr/bin/as": "7a2ef948033b05ad0c5dcb0d5be059bc68562b5d45713d91aee21df2b4bf4e92",
    "/usr/bin/ld": "e46a122cc3a29feba3b1d0fc2a274b6e46538be016ebe381370c0801bb98b0b8",
    "/usr/bin/python3": "1643dacd9feaedc58f3cc581e4d22577dfe25c09b10282936186ccf0f2e61118",
    "/usr/bin/readelf": "871be389739ecf9924b052c2fde4d2a2068a54e882201b9c34897337a5a0a130",
    "/usr/libexec/gcc/x86_64-linux-gnu/13/cc1": "5d1679131184e2de4435b426eb264bf13472fe026db8e5c6bc97445814e8e2f4",
    "/usr/libexec/gcc/x86_64-linux-gnu/13/cc1plus": "840b332fb62ec6f694ac77d91fe69ef7f80b0d69512ed89374af0ee7a506255d",
    "/usr/libexec/gcc/x86_64-linux-gnu/13/collect2": "4d1f341ae5b763b513258ee2812422a45e063c30a2f1924a0cf63d3699f3a158",
}

# Windows replay deliberately uses the VS 2022 build boundary.  CMake/Ninja
# are selected from that boundary, while link/lib/dumpbin are forced from its
# MSVC x64 tool directory even for clang-cl.  The Python interpreter belongs
# to the ignored local tools root and is passed explicitly to CMake.
WINDOWS_BUILD_TOOL_SHA256 = {
    "cmake.exe": "fc43b67ba03e1edb63b2937d6311808a094b31b815435b39547aef01cefe8fb1",
    "ninja.exe": "c074015e9f7b40c85fb3d7593a77e0eef8485760a6d33b02257b55ec1199810e",
    "vcvars64.bat": "6b516d8fcf543c14b2d861e1f45661e0029230fe0dc48e86ce78522801822209",
    "cmd.exe": "97ac98b1a92c286054cce55239cfccdfc23a5517bd07fe693072c9ca96c7dabb",
    "link.exe": "6b8facc40b829b4a9f11280ab98ea7862adcc33f0a64129a7c10b50c4167c662",
    "lib.exe": "e6bd02eab6ea941eff9b5a846fa722005eab29eb14be271ce3a2af16a075f574",
    "dumpbin.exe": "1106b753a44154134bffcc350aa5b8c57a7e2883878ba1401f47da9db4ba45c7",
    "python.exe": "21bb438c0d4a6f1f164b9a646f6ee000340185e5871180aec06db8d3f07c0082",
    "wsl.exe": "27cc8dd52be326e138a89f8889241b1d8c51dd1978b22eb70be77036ccdee3c2",
}

GENERATION_INPUT_NAMES = frozenset(
    {
        "patched.z64",
        "symbols.toml",
        "original_context.toml",
        "runtime_manifest.json",
        "recomp.h",
        "input.elf",
        "original.z64",
        "overlay-layout.json",
        "data_context.toml",
    }
)
GENERATION_INPUT_SIZE_LIMITS = {
    "patched.z64": 64 * 1024 * 1024,
    "symbols.toml": 16 * 1024 * 1024,
    "original_context.toml": 16 * 1024 * 1024,
    "runtime_manifest.json": 16 * 1024 * 1024,
    "recomp.h": 16 * 1024 * 1024,
    "input.elf": 64 * 1024 * 1024,
    "original.z64": 64 * 1024 * 1024,
    "overlay-layout.json": 16 * 1024 * 1024,
    "data_context.toml": 16 * 1024 * 1024,
}
GENERATION_RECOMPILER_RELATIVE = PurePosixPath(
    "tools/results/phase4/n64recomp-bounded/build/N64Recomp"
)

SANITIZER_PROBE_SOURCE = r'''#include "recomp.h"
#include "jfg/runtime/generated_overlay_runtime.hpp"
#include "jfg/runtime/custom_overlay_relocator.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>

extern "C" recomp_func_t* jfg_generated_lookup_function(int32_t);

namespace {
struct EmptyResolver final : jfg::CustomOverlayRelocationResolver {
    bool resolve_external(jfg::CustomOverlayRelocationSource, std::uint32_t, std::uint32_t, std::uint32_t&) override { return false; }
    bool resolve_local(jfg::CustomOverlayRelocationSource, std::uint32_t, std::uint32_t, std::uint32_t&) override { return false; }
};
void generated_target(uint8_t*, recomp_context*) {}

int checked_dispatch(
    void*, int32_t vram, uint8_t* rdram, recomp_context* context) {
    recomp_func_t* function = jfg_generated_lookup_function(vram);
    if (function == nullptr || rdram == nullptr || context == nullptr) {
        return 0;
    }
    function(rdram, context);
    return 1;
}

[[gnu::noinline]] void sanitizer_negative_control() {
#if defined(JFG_PHASE4_ASAN)
    volatile std::size_t index = 2;
    auto* bytes = static_cast<unsigned char*>(std::malloc(1));
    if (bytes == nullptr) {
        std::abort();
    }
    bytes[index] = 1;
    std::free(bytes);
#elif defined(JFG_PHASE4_UBSAN)
    volatile int value = std::numeric_limits<int>::max();
    volatile int overflow = value + 1;
    (void)overflow;
#else
#error "A Phase 4 sanitizer must be selected"
#endif
}
} // namespace

extern "C" std::size_t jfg_generated_section_count(void) { return 1; }

extern "C" int jfg_generated_initialize_sections(
    int32_t* addresses,
    std::size_t capacity
) {
    if (addresses == nullptr || capacity < 1) {
        return 0;
    }
    addresses[0] = static_cast<int32_t>(UINT32_C(0x80000000));
    return 1;
}

extern "C" recomp_func_t* jfg_generated_lookup_function(int32_t vram) {
    return vram == static_cast<int32_t>(UINT32_C(0x80000000))
        ? generated_target
        : nullptr;
}

int main(int argc, char** argv) {
    if (argc == 3 && std::strcmp(
            argv[1],
            "--phase4-evidence-sanitizer-negative-control"
        ) == 0) {
        sanitizer_negative_control();
        return 0;
    }
    if (argc != 4 || std::strcmp(argv[1], "--phase4-evidence-probe") != 0) {
        return 10;
    }
    recomp_context context{};
    uint8_t memory[1]{};
    cop0_status_write(&context, UINT64_C(7));
    if (jfg_minimal_runtime_section_capacity() != 4096 ||
        jfg_minimal_runtime_initialize() != 1 ||
        cop0_status_read(&context) != UINT64_C(7) ||
        jfg_minimal_runtime_bind_dispatch(checked_dispatch, nullptr) == 0) {
        return 11;
    }
    std::array<std::byte, 4096> overlay_memory{};
    jfg::GeneratedOverlayRuntime runtime(overlay_memory);
    std::array<std::byte, 4> image{};
    const jfg::CustomOverlayRelocationSection section{0U, UINT32_C(0x80000000), 4U, 4U, 4U};
    EmptyResolver resolver;
    if (!jfg::apply_custom_overlay_relocations(image, section, {}, resolver).applied()) {
        return 11;
    }
    get_function(static_cast<int32_t>(UINT32_C(0x80000000)))(memory, &context);
    if (jfg_minimal_runtime_unbind_dispatch(checked_dispatch, nullptr) == 0) {
        return 11;
    }
    std::printf(
        "{\"evidence_kind\":\"%s\",\"kind\":\"jfg-phase4-product-probe\","
        "\"nonce\":\"%s\",\"passed\":true,\"schema_version\":1}",
        argv[3],
        argv[2]
    );
    return 0;
}
'''


class AuditError(RuntimeError):
    pass


def _reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise AuditError("duplicate JSON key")
        result[key] = value
    return result


def _json_loads(payload: bytes) -> object:
    try:
        return json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_reject_duplicates,
            parse_constant=lambda value: (_ for _ in ()).throw(AuditError(value)),
        )
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise AuditError("JSON product is invalid") from error


def _canonical_bytes(value: object) -> bytes:
    def visit(item: object) -> None:
        if isinstance(item, float) and not math.isfinite(item):
            raise AuditError("non-finite value")
        if isinstance(item, dict):
            if not all(isinstance(key, str) for key in item):
                raise AuditError("non-string key")
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _is_reparse(metadata: os.stat_result) -> bool:
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse)


def _artifact_path(textual: object) -> Path:
    if not isinstance(textual, str):
        raise AuditError("artifact path is invalid")
    parsed = PurePosixPath(textual)
    if (
        parsed.is_absolute()
        or not parsed.parts
        or any(part in {"", ".", ".."} for part in parsed.parts)
        or parsed.as_posix() != textual
    ):
        raise AuditError("artifact path is invalid")
    root = Path.cwd().absolute()
    current = root
    try:
        if _is_reparse(current.lstat()):
            raise AuditError("artifact boundary is invalid")
        for part in parsed.parts:
            current = current / part
            if _is_reparse(current.lstat()):
                raise AuditError("artifact boundary is invalid")
        current.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (OSError, ValueError) as error:
        raise AuditError("artifact boundary is invalid") from error
    return current


def _read_regular(textual: object, maximum: int = MAX_ARTIFACT_BYTES) -> bytes:
    path = _artifact_path(textual)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        before = path.lstat()
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        after = path.lstat()
        if (
            _is_reparse(before)
            or _is_reparse(after)
            or not stat.S_ISREG(opened.st_mode)
            or not os.path.samestat(before, opened)
            or not os.path.samestat(after, opened)
        ):
            raise AuditError("artifact identity changed")
        if opened.st_size > maximum:
            raise AuditError("artifact is oversized")
        remaining = maximum + 1
        chunks: list[bytes] = []
        while remaining > 0:
            block = os.read(descriptor, min(1024 * 1024, remaining))
            if not block:
                break
            chunks.append(block)
            remaining -= len(block)
        payload = b"".join(chunks)
        if len(payload) > maximum:
            raise AuditError("artifact is oversized")
        return payload
    except OSError as error:
        raise AuditError("artifact could not be read") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _canonical_json_product(payload: bytes) -> object:
    document = _json_loads(payload)
    if _canonical_bytes(document) != payload:
        raise AuditError("JSON product is not canonical")
    return document


def _artifact_records(execution: dict[str, object]) -> dict[str, dict[str, object]]:
    artifacts = execution.get("artifacts")
    if not isinstance(artifacts, list):
        raise AuditError("artifact records are unavailable")
    records: dict[str, dict[str, object]] = {}
    for item in artifacts:
        if not isinstance(item, dict) or set(item) != {"path", "role", "sha256"}:
            raise AuditError("artifact record is invalid")
        path = item.get("path")
        digest = item.get("sha256")
        if (
            not isinstance(path, str)
            or path in records
            or not isinstance(digest, str)
            or SHA256_RE.fullmatch(digest) is None
        ):
            raise AuditError("artifact record is invalid")
        records[path] = item
    return records


def _audit_plan(
    records: dict[str, dict[str, object]], evidence_kind: str
) -> dict[str, str]:
    plans: list[dict[str, object]] = []
    for path, record in records.items():
        if record.get("role") != "configuration":
            continue
        try:
            payload = _read_regular(path)
            if _sha256(payload) != record.get("sha256"):
                raise AuditError("production audit plan digest differs")
            candidate = _canonical_json_product(payload)
        except AuditError:
            continue
        if isinstance(candidate, dict) and candidate.get("kind") == "jfg-phase4-production-audit":
            plans.append(candidate)
    if len(plans) != 1:
        raise AuditError("exactly one production audit plan is required")
    plan = plans[0]
    if set(plan) != {"schema_version", "kind", "evidence_kind", "products"} or any(
        plan.get(key) != value
        for key, value in (
            ("schema_version", 1),
            ("kind", "jfg-phase4-production-audit"),
            ("evidence_kind", evidence_kind),
        )
    ):
        raise AuditError("production audit plan is invalid")
    products = plan.get("products")
    if not isinstance(products, list):
        raise AuditError("production product plan is invalid")
    result: dict[str, str] = {}
    prefix = f"production/{evidence_kind}/"
    for item in products:
        if not isinstance(item, dict) or set(item) != {"product_kind", "artifact_path"}:
            raise AuditError("production product plan is invalid")
        product_kind = item.get("product_kind")
        artifact_path = item.get("artifact_path")
        if (
            not isinstance(product_kind, str)
            or not isinstance(artifact_path, str)
            or product_kind in result
            or artifact_path in result.values()
            or artifact_path not in records
            or not artifact_path.startswith(prefix)
            or records[artifact_path].get("role") == "result"
        ):
            raise AuditError("production product plan is invalid")
        result[product_kind] = artifact_path
    if frozenset(result) != PRODUCT_KINDS.get(evidence_kind):
        raise AuditError("production product set is incomplete")
    declared_paths = set(result.values())
    for path, record in records.items():
        if record.get("role") in {"output", "log"} and path not in declared_paths:
            raise AuditError("output artifact is absent from the production plan")
    return result


def _load_products(
    products: dict[str, str],
    records: dict[str, dict[str, object]],
    expected_products: dict[str, object],
) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    for product_kind, path in products.items():
        payload = _read_regular(path)
        digest = _sha256(payload)
        if digest != records[path].get("sha256"):
            raise AuditError("production product digest differs from the artifact record")
        expected = expected_products.get(product_kind)
        if expected is not None and digest != expected:
            raise AuditError("production product differs from the public result")
        if product_kind in CANONICAL_JSON_PRODUCTS:
            _canonical_json_product(payload)
        result[product_kind] = payload
    if set(expected_products) - set(result):
        raise AuditError("public result product is absent")
    return result


def _file_inventory(payload: bytes, expected_kind: str) -> list[dict[str, object]]:
    document = _canonical_json_product(payload)
    if not isinstance(document, dict) or set(document) != {"schema_version", "kind", "files"}:
        raise AuditError("file inventory is invalid")
    if document.get("schema_version") != 1 or document.get("kind") != expected_kind:
        raise AuditError("file inventory is invalid")
    files = document.get("files")
    if not isinstance(files, list) or not files:
        raise AuditError("file inventory is empty")
    previous = ""
    seen: set[str] = set()
    for item in files:
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "size"}:
            raise AuditError("file inventory row is invalid")
        path = item.get("path")
        digest = item.get("sha256")
        size = item.get("size")
        if (
            not isinstance(path, str)
            or path <= previous
            or path in seen
            or PurePosixPath(path).as_posix() != path
            or PurePosixPath(path).is_absolute()
            or any(part in {"", ".", ".."} for part in PurePosixPath(path).parts)
            or not isinstance(digest, str)
            or SHA256_RE.fullmatch(digest) is None
            or type(size) is not int
            or not 0 <= size <= MAX_ARCHIVE_ENTRY_BYTES
        ):
            raise AuditError("file inventory row is invalid")
        previous = path
        seen.add(path)
    return files


def _zip_files(payload: bytes) -> tuple[list[dict[str, object]], dict[str, bytes]]:
    inventory: list[dict[str, object]] = []
    contents: dict[str, bytes] = {}
    total = 0
    try:
        with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
            infos = archive.infolist()
            if not infos or len(infos) > MAX_ARCHIVE_ENTRIES:
                raise AuditError("ZIP product entry count is invalid")
            for info in infos:
                parsed = PurePosixPath(info.filename)
                unix_mode = (info.external_attr >> 16) & 0xFFFF
                if (
                    info.is_dir()
                    or info.flag_bits & 1
                    or parsed.is_absolute()
                    or parsed.as_posix() != info.filename
                    or any(part in {"", ".", ".."} for part in parsed.parts)
                    or stat.S_ISLNK(unix_mode)
                    or info.file_size > MAX_ARCHIVE_ENTRY_BYTES
                ):
                    raise AuditError("ZIP product entry is invalid")
                total += info.file_size
                if total > MAX_ARCHIVE_EXPANDED_BYTES:
                    raise AuditError("ZIP product expands beyond its limit")
                value = archive.read(info)
                if len(value) != info.file_size or info.filename in contents:
                    raise AuditError("ZIP product entry is invalid")
                contents[info.filename] = value
    except (OSError, RuntimeError, zipfile.BadZipFile) as error:
        if isinstance(error, AuditError):
            raise
        raise AuditError("ZIP product is invalid") from error
    for path in sorted(contents):
        value = contents[path]
        inventory.append({"path": path, "sha256": _sha256(value), "size": len(value)})
    return inventory, contents


def _generation_input_contents(products: dict[str, bytes]) -> dict[str, bytes]:
    inventory = _file_inventory(
        products["generation-input-inventory"], "jfg-phase4-file-inventory"
    )
    actual_inventory, contents = _zip_files(products["generation-input-archive"])
    if inventory != actual_inventory or set(contents) != GENERATION_INPUT_NAMES:
        raise AuditError("generation input archive differs from its fixed inventory")
    for path, payload in contents.items():
        maximum = GENERATION_INPUT_SIZE_LIMITS.get(path)
        if maximum is None or not payload or len(payload) > maximum:
            raise AuditError("generation input archive entry is outside its fixed bound")
    return contents


def _private_tree_contents(root: Path) -> dict[str, bytes]:
    try:
        metadata = root.lstat()
    except OSError as error:
        raise AuditError("generation replay output is unavailable") from error
    if _is_reparse(metadata) or not stat.S_ISDIR(metadata.st_mode):
        raise AuditError("generation replay output boundary is invalid")
    result: dict[str, bytes] = {}
    total = 0
    try:
        paths = sorted(root.rglob("*"))
    except OSError as error:
        raise AuditError("generation replay output is unavailable") from error
    for path in paths:
        try:
            metadata = path.lstat()
        except OSError as error:
            raise AuditError("generation replay output is unavailable") from error
        if _is_reparse(metadata):
            raise AuditError("generation replay output boundary is invalid")
        if stat.S_ISDIR(metadata.st_mode):
            continue
        if not stat.S_ISREG(metadata.st_mode):
            raise AuditError("generation replay output boundary is invalid")
        relative = path.relative_to(root).as_posix()
        if (
            relative in result
            or len(result) >= MAX_ARCHIVE_ENTRIES
            or len(result) and total >= MAX_ARCHIVE_EXPANDED_BYTES
        ):
            raise AuditError("generation replay output exceeds its bound")
        payload = _read_fixed_regular(path, MAX_ARCHIVE_ENTRY_BYTES)
        total += len(payload)
        if total > MAX_ARCHIVE_EXPANDED_BYTES:
            raise AuditError("generation replay output exceeds its bound")
        result[relative] = payload
    if not result:
        raise AuditError("generation replay output is empty")
    return result


def _ar_members(payload: bytes) -> list[dict[str, object]]:
    if not payload.startswith(b"!<arch>\n"):
        raise AuditError("static library format is invalid")
    offset = 8
    string_table = b""
    members: list[dict[str, object]] = []
    while offset < len(payload):
        if offset + 60 > len(payload):
            raise AuditError("static library member header is truncated")
        header = payload[offset : offset + 60]
        offset += 60
        if header[58:60] != b"`\n":
            raise AuditError("static library member header is invalid")
        try:
            size = int(header[48:58].decode("ascii").strip())
        except (UnicodeDecodeError, ValueError) as error:
            raise AuditError("static library member size is invalid") from error
        if size < 0 or size > MAX_ARTIFACT_BYTES or offset + size > len(payload):
            raise AuditError("static library member size is invalid")
        body = payload[offset : offset + size]
        offset += size + (size & 1)
        raw_name = header[:16].decode("ascii", errors="strict").rstrip()
        if raw_name == "//":
            string_table = body
            continue
        if raw_name in {"/", "/SYM64/"} or raw_name.startswith("__.SYMDEF"):
            continue
        if raw_name.startswith("#1/"):
            try:
                name_size = int(raw_name[3:])
            except ValueError as error:
                raise AuditError("static library BSD name is invalid") from error
            if name_size <= 0 or name_size > len(body):
                raise AuditError("static library BSD name is invalid")
            name = body[:name_size].decode("utf-8")
            body = body[name_size:]
        elif raw_name.startswith("/") and raw_name[1:].isdigit():
            index = int(raw_name[1:])
            if index >= len(string_table):
                raise AuditError("static library long name is invalid")
            end_candidates = [
                value for value in (string_table.find(b"/\n", index), string_table.find(b"\x00", index)) if value >= 0
            ]
            end = min(end_candidates) if end_candidates else len(string_table)
            name = string_table[index:end].decode("utf-8")
        else:
            name = raw_name[:-1] if raw_name.endswith("/") else raw_name
        if not name or any(character in name for character in ("\x00", "\r", "\n")):
            raise AuditError("static library member name is invalid")
        members.append({"name": name, "sha256": _sha256(body), "size": len(body)})
    if offset != len(payload) or not members:
        raise AuditError("static library contains no object members")
    return members


def _member_inventory(payload: bytes) -> list[dict[str, object]]:
    document = _canonical_json_product(payload)
    if not isinstance(document, dict) or set(document) != {"schema_version", "kind", "members"}:
        raise AuditError("archive member inventory is invalid")
    if document.get("schema_version") != 1 or document.get("kind") != "jfg-phase4-archive-member-inventory":
        raise AuditError("archive member inventory is invalid")
    members = document.get("members")
    if not isinstance(members, list) or not members:
        raise AuditError("archive member inventory is empty")
    names: set[str] = set()
    for item in members:
        if (
            not isinstance(item, dict)
            or set(item) != {"name", "sha256", "size"}
            or not isinstance(item.get("name"), str)
            or not item.get("name")
            or item.get("name") in names
            or any(character in str(item.get("name")) for character in ("\x00", "\r", "\n"))
            or not isinstance(item.get("sha256"), str)
            or SHA256_RE.fullmatch(str(item.get("sha256"))) is None
            or type(item.get("size")) is not int
            or not 0 <= int(item.get("size")) <= MAX_ARTIFACT_BYTES
        ):
            raise AuditError("archive member inventory row is invalid")
        names.add(str(item["name"]))
    return members


def _verify_archive_pair(
    products: dict[str, bytes], archive_kind: str, inventory_kind: str
) -> None:
    if _ar_members(products[archive_kind]) != _member_inventory(products[inventory_kind]):
        raise AuditError("static library members differ from the bound inventory")


def _pipe_reader(pipe: object, maximum: int, output: list[bytes]) -> None:
    try:
        output.append(pipe.read(maximum + 1))  # type: ignore[attr-defined]
    except (OSError, ValueError):
        output.append(b"")
    finally:
        try:
            pipe.close()  # type: ignore[attr-defined]
        except (OSError, ValueError):
            pass


def _run_bounded(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str] | None = None,
    timeout_seconds: float = PROCESS_TIMEOUT_SECONDS,
) -> tuple[int, bytes, bytes]:
    if not 0 < timeout_seconds <= BUILD_REPLAY_TIMEOUT_SECONDS:
        raise AuditError("fixed process timeout is invalid")
    base_environment = {
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
            "INCLUDE",
            "LIB",
            "LIBPATH",
            "VCINSTALLDIR",
            "VCToolsInstallDir",
            "WindowsSdkDir",
            "UniversalCRTSdkDir",
            "UCRTVersion",
            "WindowsSDKVersion",
        )
        if key in os.environ
    }
    if environment:
        base_environment.update(environment)
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=base_environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdout is not None
    assert process.stderr is not None
    stdout: list[bytes] = []
    stderr: list[bytes] = []
    threads = [
        threading.Thread(target=_pipe_reader, args=(process.stdout, MAX_PROCESS_STDOUT, stdout), daemon=True),
        threading.Thread(target=_pipe_reader, args=(process.stderr, MAX_PROCESS_STDERR, stderr), daemon=True),
    ]
    for thread in threads:
        thread.start()
    try:
        return_code = process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as error:
        process.kill()
        process.wait(timeout=5)
        raise AuditError("fixed production probe timed out") from error
    for thread in threads:
        thread.join(timeout=1)
    out = stdout[0] if stdout else b""
    err = stderr[0] if stderr else b""
    if len(out) > MAX_PROCESS_STDOUT or len(err) > MAX_PROCESS_STDERR:
        raise AuditError("fixed production probe output exceeded its limit")
    return return_code, out, err


def _read_system_executable(path: Path) -> bytes:
    try:
        before = path.stat(follow_symlinks=False)
        if not stat.S_ISREG(before.st_mode) or stat.S_ISLNK(before.st_mode) or before.st_size > MAX_SYSTEM_EXECUTABLE_BYTES:
            raise AuditError("fixed system executable boundary is invalid")
        with path.open("rb") as stream:
            payload = stream.read(MAX_SYSTEM_EXECUTABLE_BYTES + 1)
            after = os.fstat(stream.fileno())
    except OSError as error:
        raise AuditError("fixed system executable boundary is invalid") from error
    if (
        len(payload) > MAX_SYSTEM_EXECUTABLE_BYTES
        or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    ):
        raise AuditError("fixed system executable changed while it was read")
    return payload


def _verify_pinned_local_tool(path: Path, expected_sha256: str) -> None:
    if not isinstance(expected_sha256, str) or SHA256_RE.fullmatch(expected_sha256) is None:
        raise AuditError("fixed build tool policy is invalid")
    if _sha256(_read_system_executable(path)) != expected_sha256:
        raise AuditError("fixed build tool differs from its repository pin")


def _run_fixed_wsl(
    arguments: list[str],
    *,
    cwd: Path,
    environment: dict[str, str] | None = None,
    timeout_seconds: float = PROCESS_TIMEOUT_SECONDS,
) -> tuple[int, bytes, bytes]:
    payload = _read_system_executable(_fixed_wsl())
    digest = _sha256(payload)
    with tempfile.TemporaryDirectory(prefix="phase4-wsl-") as temporary:
        executable = Path(temporary) / "wsl.exe"
        executable.write_bytes(payload)
        if _sha256(executable.read_bytes()) != digest:
            raise AuditError("verified WSL copy differs")
        result = _run_bounded(
            [str(executable), *arguments],
            cwd=cwd,
            environment=environment,
            timeout_seconds=timeout_seconds,
        )
        if _sha256(executable.read_bytes()) != digest:
            raise AuditError("verified WSL copy changed during execution")
        return result


def _wsl_path(path: Path, *, must_exist: bool = True) -> str:
    resolved = str(path.resolve(strict=must_exist))
    if os.name != "nt":
        return resolved
    drive, tail = os.path.splitdrive(resolved)
    if not drive or len(drive) != 2 or drive[1] != ":":
        raise AuditError("ELF probe path cannot be translated")
    normalized = tail.replace("\\", "/")
    return f"/mnt/{drive[0].lower()}{normalized}"


def _product_command(path: Path, payload: bytes, arguments: list[str]) -> list[str]:
    if payload.startswith(b"MZ"):
        if os.name != "nt":
            raise AuditError("PE production probe is not runnable on this host")
        return [str(path), *arguments]
    if payload.startswith(b"\x7fELF"):
        if os.name != "nt":
            if not os.access(path, os.X_OK):
                raise AuditError("ELF production probe is not executable")
            return [str(path), *arguments]
        wsl = Path("C:/Windows/System32/wsl.exe")
        try:
            metadata = wsl.stat(follow_symlinks=False)
        except OSError:
            metadata = None
        if metadata is None or not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
            raise AuditError("WSL is unavailable for the fixed ELF probe")
        return [
            str(wsl),
            "-d",
            "Ubuntu-24.04",
            "--exec",
            _wsl_path(path),
            *arguments,
        ]
    raise AuditError("production probe is not PE or ELF")


def _run_product_probe(
    product_kind: str,
    product_path: str,
    product_payload: bytes,
    request: dict[str, object],
    required_markers: tuple[bytes, ...],
    environment: dict[str, str] | None = None,
) -> None:
    if not all(marker in product_payload for marker in required_markers):
        raise AuditError("production probe is missing required linked instrumentation")
    evidence_kind = str(request["execution"]["evidence_kind"])  # type: ignore[index]
    expected_names = {
        "smoke-executable": {"smoke-probe", "smoke-probe.exe"},
        "forced-link-executable": {"forced-link-probe", "forced-link-probe.exe"},
        "instrumented-executable": {"instrumented-probe", "instrumented-probe.exe"},
    }
    if PurePosixPath(product_path).name not in expected_names[product_kind]:
        raise AuditError("production probe name is not the fixed convention")
    nonce = _sha256(
        _canonical_bytes(
            {
                "public_claim_sha256": request.get("public_claim_sha256"),
                "evidence_kind": evidence_kind,
                "public_record_sha256": request["execution"].get("public_record_sha256"),  # type: ignore[index]
                "public_result_set_sha256": request["execution"].get("public_result_set_sha256"),  # type: ignore[index]
            }
        )
    )
    suffix = ".exe" if product_payload.startswith(b"MZ") else ""
    with tempfile.TemporaryDirectory(prefix="phase4-probe-") as temporary:
        path = Path(temporary) / (PurePosixPath(product_path).stem + suffix)
        path.write_bytes(product_payload)
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        if _sha256(path.read_bytes()) != _sha256(product_payload):
            raise AuditError("verified production probe copy differs")
        arguments = ["--phase4-evidence-probe", nonce, evidence_kind]
        if product_payload.startswith(b"\x7fELF") and os.name == "nt":
            return_code, stdout, stderr = _run_fixed_wsl(
                ["-d", "Ubuntu-24.04", "--exec", _wsl_path(path), *arguments],
                cwd=path.parent,
                environment=environment,
            )
        else:
            command = _product_command(path, product_payload, arguments)
            return_code, stdout, stderr = _run_bounded(
                command,
                cwd=path.parent,
                environment=environment,
            )
        if _sha256(path.read_bytes()) != _sha256(product_payload):
            raise AuditError("verified production probe changed during execution")
    if return_code != 0 or stderr:
        raise AuditError("production probe failed")
    proof = _json_loads(stdout)
    expected = {
        "schema_version": 1,
        "kind": "jfg-phase4-product-probe",
        "evidence_kind": evidence_kind,
        "nonce": nonce,
        "passed": True,
    }
    if proof != expected or _canonical_bytes(proof) != stdout:
        raise AuditError("production probe proof is invalid")


def _require_public_result(
    product: bytes, product_kind: str, public_record: object
) -> None:
    if not isinstance(public_record, dict) or "result_sha256" not in public_record:
        raise AuditError("trusted public result record is unavailable")
    observed = dict(public_record)
    observed.pop("result_sha256", None)
    expected = {
        "schema_version": 1,
        "kind": "jfg-phase4-public-result",
        "product_kind": product_kind,
        "observed": observed,
    }
    if _canonical_json_product(product) != expected:
        raise AuditError("structured product does not equal the trusted public result")


def _generated_source_contents(products: dict[str, bytes]) -> dict[str, bytes]:
    inventory = _file_inventory(
        products["source-file-inventory"], "jfg-phase4-file-inventory"
    )
    actual_inventory, contents = _zip_files(products["generated-source-archive"])
    if inventory != actual_inventory:
        raise AuditError("generated source archive differs from its inventory")
    manifest = contents.get("sources.json")
    if manifest is None:
        raise AuditError("generated source archive lacks its fixed manifest")
    document = _json_loads(manifest)
    source_groups = (
        "baseline_body_sources",
        "normal_wrapper_sources",
        "support_sources",
        "patch_sources",
        "link_smoke_sources",
    )
    semantic_products = {
        "generated_inventory": ("generated-inventory", "jfg-phase4-generated-inventory"),
        "generation_result": ("generation-result", "jfg-phase4-generation-semantic-result"),
        "alternate_entry_ledger": ("alternate-entry-ledger", "jfg-phase4-alternate-entry-ledger"),
        "covered_alias_ledger": ("covered-alias-ledger", "jfg-phase4-covered-alias-ledger"),
        "exception_ledger": ("exception-ledger", "jfg-phase4-approved-exception-ledger"),
        "manual_size_recovery_ledger": ("manual-size-recovery-ledger", "jfg-phase4-manual-size-recovery-ledger"),
        "n64recomp_decision_sidecar": ("n64recomp-decision-sidecar", "n64recomp-indirect-decision-sidecar"),
        "overlay_slot_inventory": ("overlay-slot-inventory", "jfg-phase4-overlay-slot-inventory"),
        "overlay_lookup_table": ("overlay-lookup-table", "jfg-phase4-generated-lookup-inventory"),
        "overlay_lifecycle_table": ("overlay-lifecycle-table", "jfg-phase4-overlay-lifecycle-inventory"),
        "relocation_table": ("relocation-table", "jfg-phase4-relocation-inventory"),
        "report_set": ("report-set", "jfg-phase4-generation-report-set"),
    }
    if (
        not isinstance(document, dict)
        or document.get("version") != 6
        or any(
        not isinstance(document.get(group), list) for group in source_groups
        )
    ):
        raise AuditError("generated source manifest is invalid")
    cpu_inventory_path = document.get("cpu_section_inventory")
    cpu_inventory_sha256 = document.get("cpu_section_inventory_sha256")
    if (
        cpu_inventory_path != "cpu_section_inventory.json"
        or not isinstance(cpu_inventory_sha256, str)
        or SHA256_RE.fullmatch(cpu_inventory_sha256) is None
        or cpu_inventory_path not in contents
        or _sha256(contents[cpu_inventory_path]) != cpu_inventory_sha256
    ):
        raise AuditError("generated source manifest lacks its CPU section inventory")
    _canonical_json_product(contents[cpu_inventory_path])
    alternate_sources = document.get("alternate_entry_thunk_sources")
    table_sources = document.get("table_support_sources")
    support_sources = document.get("support_sources")
    if (
        not isinstance(alternate_sources, list)
        or not isinstance(table_sources, list)
        or not isinstance(support_sources, list)
        or set(alternate_sources) & set(table_sources)
        or set(support_sources) != set(alternate_sources) | set(table_sources)
    ):
        raise AuditError("generated source support roles are invalid")
    for manifest_member, (product_kind, expected_kind) in semantic_products.items():
        path = document.get(manifest_member)
        expected_digest = document.get(f"{manifest_member}_sha256")
        if (
            not isinstance(path, str)
            or not isinstance(expected_digest, str)
            or SHA256_RE.fullmatch(expected_digest) is None
            or path not in contents
            or _sha256(contents[path]) != expected_digest
            or (
                product_kind in products
                and products[product_kind] != contents[path]
            )
        ):
            raise AuditError("generated source semantic product binding is invalid")
        semantic_document = _canonical_json_product(contents[path])
        if (
            not isinstance(semantic_document, dict)
            or semantic_document.get("schema_version") != 1
            or semantic_document.get("kind") != expected_kind
        ):
            raise AuditError("generated source semantic product is invalid")
    declared: list[str] = []
    for group in source_groups:
        values = document[group]
        assert isinstance(values, list)
        if any(not isinstance(value, str) for value in values):
            raise AuditError("generated source manifest is invalid")
        declared.extend(values)
    if len(declared) != len(set(declared)) or any(path not in contents for path in declared):
        raise AuditError("generated source manifest does not close its source set")
    source_suffixes = {".c", ".cc", ".cpp", ".cxx"}
    actual_sources = {
        path
        for path in contents
        if PurePosixPath(path).suffix in source_suffixes
    }
    if actual_sources != set(declared):
        raise AuditError("generated source manifest does not close its source set")
    return contents


def _verify_cpu_section_inventory(
    product: bytes,
    contents: dict[str, bytes],
    public_record: dict[str, object],
) -> None:
    if contents.get("cpu_section_inventory.json") != product:
        raise AuditError("CPU section inventory differs from the generated archive")
    document = _canonical_json_product(product)
    if (
        not isinstance(document, dict)
        or set(document) != {"schema_version", "kind", "sections", "overlay_slots"}
        or document.get("schema_version") != 2
        or document.get("kind") != "jfg-phase4-cpu-section-inventory"
    ):
        raise AuditError("CPU section inventory is invalid")
    rows = document.get("sections")
    slot_rows = document.get("overlay_slots")
    if not isinstance(rows, list) or not rows or not isinstance(slot_rows, list):
        raise AuditError("CPU section inventory is empty")

    fields = {
        "section_id",
        "kind",
        "expected",
        "generated",
        "excluded",
        "lookups",
        "lifecycle",
        "relocations",
    }
    totals = {
        "expected": 0,
        "generated": 0,
        "excluded": 0,
        "lookups": 0,
        "relocations": 0,
    }
    main_count = 0
    overlay_count = 0
    overlay_lifecycle_count = 0
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != fields:
            raise AuditError("CPU section inventory row is invalid")
        kind = row.get("kind")
        values = {field: row.get(field) for field in fields - {"section_id", "kind"}}
        expected_lifecycle = 0 if kind == "main" else 1
        if (
            row.get("section_id") != f"section-{index:03d}"
            or kind not in {"main", "overlay"}
            or any(type(value) is not int or value < 0 for value in values.values())
            or values["expected"] == 0
            or values["generated"] + values["excluded"] != values["expected"]
            or values["lookups"] != values["generated"]
            or values["lifecycle"] != expected_lifecycle
        ):
            raise AuditError("CPU section inventory row is invalid")
        main_count += int(kind == "main")
        overlay_count += int(kind == "overlay")
        overlay_lifecycle_count += values["lifecycle"]
        for field in totals:
            totals[field] += values[field]

    symbols = public_record.get("symbols")
    overlays = public_record.get("overlays")
    relocations = public_record.get("relocations")
    data_r32 = relocations.get("data_r32") if isinstance(relocations, dict) else None
    if not isinstance(symbols, dict) or not isinstance(overlays, dict) or not isinstance(data_r32, dict):
        raise AuditError("CPU section public denominators are unavailable")
    comparisons = (
        (totals["expected"], symbols.get("expected_count")),
        (totals["generated"], symbols.get("generated_count")),
        (totals["excluded"], symbols.get("excluded_count")),
        (totals["lookups"], symbols.get("replaceable_function_count")),
        (totals["relocations"], overlays.get("relocation_table_entry_count")),
        (totals["relocations"], data_r32.get("expected_count")),
        (overlay_count, overlays.get("populated_slot_count")),
        (overlay_count, overlays.get("generated_populated_module_count")),
        (overlay_lifecycle_count, overlays.get("populated_slot_count")),
    )
    if main_count != 1 or any(left != right for left, right in comparisons):
        raise AuditError("CPU section inventory differs from the public denominators")
    populated_sections: set[str] = set()
    populated_slots = 0
    empty_slots = 0
    for index, row in enumerate(slot_rows, start=1):
        if (
            not isinstance(row, dict)
            or set(row) != {"slot_id", "disposition", "section_id"}
            or row.get("slot_id") != f"slot-{index:03d}"
        ):
            raise AuditError("CPU overlay slot inventory row is invalid")
        if row.get("disposition") == "populated":
            section_id = row.get("section_id")
            if (
                not isinstance(section_id, str)
                or re.fullmatch(r"section-[0-9]{3}", section_id) is None
                or section_id == "section-000"
                or section_id in populated_sections
            ):
                raise AuditError("CPU populated overlay slot row is invalid")
            populated_sections.add(section_id)
            populated_slots += 1
        elif row.get("disposition") == "empty-fail-closed" and row.get("section_id") is None:
            empty_slots += 1
        else:
            raise AuditError("CPU empty overlay slot row is invalid")
    expected_overlay_sections = {
        str(row["section_id"])
        for row in rows
        if isinstance(row, dict) and row.get("kind") == "overlay"
    }
    slot_comparisons = (
        (len(slot_rows), overlays.get("expected_slot_count")),
        (len(slot_rows), overlays.get("listed_slot_count")),
        (populated_slots, overlays.get("populated_slot_count")),
        (empty_slots, overlays.get("empty_slot_count")),
    )
    if (
        populated_sections != expected_overlay_sections
        or populated_slots != overlay_count
        or any(left != right for left, right in slot_comparisons)
    ):
        raise AuditError("CPU overlay slot inventory differs from public denominators")


def _policy_approval_digest(
    policy_id: str,
    opaque_id: str,
    category: str,
    disposition: str,
) -> str:
    return _sha256(
        _canonical_bytes(
            {
                "policy_id": policy_id,
                "opaque_id": opaque_id,
                "category": category,
                "disposition": disposition,
            }
        )
    )


def _verify_generation_semantics(
    products: dict[str, bytes],
    contents: dict[str, bytes],
    public_record: dict[str, object] | None,
) -> None:
    manifest = _canonical_json_product(contents["sources.json"])
    if not isinstance(manifest, dict):
        raise AuditError("generated semantic manifest is invalid")

    generated = _canonical_json_product(products["generated-inventory"])
    alternate = _canonical_json_product(products["alternate-entry-ledger"])
    aliases = _canonical_json_product(products["covered-alias-ledger"])
    exceptions = _canonical_json_product(products["exception-ledger"])
    recoveries = _canonical_json_product(products["manual-size-recovery-ledger"])
    decisions = _canonical_json_product(products["n64recomp-decision-sidecar"])
    slots = _canonical_json_product(products["overlay-slot-inventory"])
    lookup = _canonical_json_product(products["overlay-lookup-table"])
    lifecycle = _canonical_json_product(products["overlay-lifecycle-table"])
    relocations = _canonical_json_product(products["relocation-table"])
    generation = _canonical_json_product(products["generation-result"])
    reports = _canonical_json_product(products["report-set"])
    if not all(
        isinstance(value, dict)
        for value in (
            generated,
            alternate,
            aliases,
            exceptions,
            recoveries,
            decisions,
            slots,
            lookup,
            lifecycle,
            relocations,
            generation,
            reports,
        )
    ):
        raise AuditError("generated semantic product is invalid")
    assert isinstance(generated, dict)
    assert isinstance(alternate, dict)
    assert isinstance(aliases, dict)
    assert isinstance(exceptions, dict)
    assert isinstance(recoveries, dict)
    assert isinstance(decisions, dict)
    assert isinstance(slots, dict)
    assert isinstance(lookup, dict)
    assert isinstance(lifecycle, dict)
    assert isinstance(relocations, dict)
    assert isinstance(generation, dict)
    assert isinstance(reports, dict)

    generated_keys = {
        "schema_version",
        "kind",
        "executable_section_count",
        "expected_symbol_count",
        "authoritative_body_count",
        "callable_wrapper_count",
        "alternate_entry_thunk_count",
        "table_support_member_count",
        "generated_game_function_stub_count",
        "covered_alias_count",
        "covered_alias_ledger_sha256",
        "covered_alias_approval_set_sha256",
        "manual_size_recovery_count",
        "manual_size_recovery_ledger_sha256",
        "manual_size_recovery_approval_set_sha256",
        "symbol_inventory_sha256",
        "alternate_entry_ledger_sha256",
        "alternate_entry_approval_set_sha256",
    }
    if (
        set(generated) != generated_keys
        or generated.get("schema_version") != 1
        or generated.get("kind") != "jfg-phase4-generated-inventory"
        or type(generated.get("executable_section_count")) is not int
        or generated["executable_section_count"] <= 0
        or type(generated.get("authoritative_body_count")) is not int
        or generated["authoritative_body_count"] <= 0
        or generated.get("callable_wrapper_count")
        != generated.get("authoritative_body_count")
        or type(generated.get("alternate_entry_thunk_count")) is not int
        or generated["alternate_entry_thunk_count"] < 0
        or generated.get("table_support_member_count") != 11
        or generated.get("generated_game_function_stub_count") != 0
        or generated.get("expected_symbol_count")
        != generated.get("authoritative_body_count") + generated.get("covered_alias_count")
        or type(generated.get("covered_alias_count")) is not int
        or generated["covered_alias_count"] < 0
        or generated.get("covered_alias_ledger_sha256")
        != _sha256(products["covered-alias-ledger"])
        or type(generated.get("manual_size_recovery_count")) is not int
        or generated["manual_size_recovery_count"] < 0
        or generated.get("manual_size_recovery_ledger_sha256")
        != _sha256(products["manual-size-recovery-ledger"])
        or generated.get("symbol_inventory_sha256")
        != _sha256(contents["symbol_inventory.json"])
        or generated.get("alternate_entry_ledger_sha256")
        != _sha256(products["alternate-entry-ledger"])
    ):
        raise AuditError("generated inventory semantics are invalid")

    alternate_entries = alternate.get("entries")
    if (
        set(alternate)
        != {
            "schema_version",
            "kind",
            "policy_id",
            "entry_count",
            "reason_counts",
            "approval_set_sha256",
            "entries",
        }
        or alternate.get("schema_version") != 1
        or alternate.get("kind") != "jfg-phase4-alternate-entry-ledger"
        or alternate.get("policy_id") != "phase4-alternate-entry-policy-v1"
        or not isinstance(alternate_entries, list)
        or alternate.get("entry_count") != len(alternate_entries)
        or len(alternate_entries) != generated.get("alternate_entry_thunk_count")
    ):
        raise AuditError("alternate-entry ledger is invalid")
    alternate_ids: set[str] = set()
    alternate_approvals: list[str] = []
    for row in alternate_entries:
        if not isinstance(row, dict) or set(row) != {
            "opaque_id",
            "section_id",
            "evidence_class",
            "owner_role",
            "reason_code",
            "disposition",
            "approval_sha256",
        }:
            raise AuditError("alternate-entry ledger row is invalid")
        opaque_id = row.get("opaque_id")
        section_id = row.get("section_id")
        if (
            not isinstance(opaque_id, str)
            or re.fullmatch(r"alternate-[0-9a-f]{24}", opaque_id) is None
            or opaque_id in alternate_ids
            or not isinstance(section_id, str)
            or re.fullmatch(r"section-[0-9]{3}", section_id) is None
            or row.get("evidence_class")
            not in {"control-transfer-entry", "covered-function-alias"}
            or row.get("owner_role") != "alternate-entry-thunk"
            or row.get("reason_code")
            not in {"validated-control-transfer-entry", "zero-size-covered-address"}
            or row.get("disposition") != "deterministic-generated-thunk"
            or row.get("approval_sha256")
            != _policy_approval_digest(
                "phase4-alternate-entry-policy-v1",
                opaque_id,
                str(row.get("reason_code")),
                "deterministic-generated-thunk",
            )
        ):
            raise AuditError("alternate-entry ledger row is invalid")
        alternate_ids.add(opaque_id)
        alternate_approvals.append(str(row["approval_sha256"]))
    alternate_approval_digest = _sha256(
        _canonical_bytes(sorted(alternate_approvals))
    )
    if (
        not isinstance(alternate.get("reason_counts"), dict)
        or set(alternate["reason_counts"])
        != {"validated-control-transfer-entry", "zero-size-covered-address"}
        or any(type(value) is not int or value < 0 for value in alternate["reason_counts"].values())
        or sum(alternate["reason_counts"].values()) != len(alternate_entries)
        or
        alternate.get("approval_set_sha256") != alternate_approval_digest
        or generated.get("alternate_entry_approval_set_sha256")
        != alternate_approval_digest
    ):
        raise AuditError("alternate-entry approval set is invalid")

    alias_entries = aliases.get("entries")
    if (
        set(aliases)
        != {
            "schema_version",
            "kind",
            "policy_id",
            "entry_count",
            "mapping_role_counts",
            "source_ledger_sha256",
            "approval_set_sha256",
            "entries",
        }
        or aliases.get("schema_version") != 1
        or aliases.get("kind") != "jfg-phase4-covered-alias-ledger"
        or aliases.get("policy_id") != "phase4-covered-alias-policy-v1"
        or not isinstance(alias_entries, list)
        or aliases.get("entry_count") != len(alias_entries)
        or len(alias_entries) != generated.get("covered_alias_count")
        or not isinstance(aliases.get("mapping_role_counts"), dict)
        or set(aliases["mapping_role_counts"])
        != {"authoritative-body", "alternate-entry-thunk"}
        or any(type(value) is not int or value < 0 for value in aliases["mapping_role_counts"].values())
        or sum(aliases["mapping_role_counts"].values()) != len(alias_entries)
    ):
        raise AuditError("covered-alias ledger is invalid")
    alias_approvals: list[str] = []
    for row in alias_entries:
        if not isinstance(row, dict) or set(row) != {
            "opaque_id",
            "section_id",
            "mapping_role",
            "evidence_class",
            "reason_code",
            "disposition",
            "approval_sha256",
        }:
            raise AuditError("covered-alias ledger row is invalid")
        opaque_id = row.get("opaque_id")
        mapping_role = row.get("mapping_role")
        expected_disposition = {
            "authoritative-body": "deterministic-body-alias",
            "alternate-entry-thunk": "deterministic-thunk-alias",
        }.get(mapping_role)
        if (
            not isinstance(opaque_id, str)
            or re.fullmatch(r"alias-[0-9a-f]{24}", opaque_id) is None
            or not isinstance(row.get("section_id"), str)
            or re.fullmatch(r"section-[0-9]{3}", row["section_id"]) is None
            or row.get("evidence_class") != "zero-size-covered-function"
            or row.get("reason_code") != "zero-size-covered-address"
            or row.get("disposition") != expected_disposition
            or row.get("approval_sha256")
            != _policy_approval_digest(
                "phase4-covered-alias-policy-v1",
                opaque_id,
                "zero-size-covered-alias",
                str(expected_disposition),
            )
        ):
            raise AuditError("covered-alias ledger row is invalid")
        alias_approvals.append(str(row["approval_sha256"]))
    alias_approval_digest = _sha256(_canonical_bytes(sorted(alias_approvals)))
    if (
        aliases.get("approval_set_sha256") != alias_approval_digest
        or generated.get("covered_alias_approval_set_sha256")
        != alias_approval_digest
    ):
        raise AuditError("covered-alias approval set is invalid")
    if (
        alternate["reason_counts"]["zero-size-covered-address"]
        != aliases["mapping_role_counts"]["alternate-entry-thunk"]
    ):
        raise AuditError("alternate-entry alias semantics do not reconcile")

    recovery_entries = recoveries.get("entries")
    if (
        set(recoveries)
        != {
            "schema_version",
            "kind",
            "policy_id",
            "entry_count",
            "source_ledger_sha256",
            "approval_set_sha256",
            "entries",
        }
        or recoveries.get("schema_version") != 1
        or recoveries.get("kind") != "jfg-phase4-manual-size-recovery-ledger"
        or recoveries.get("policy_id") != "phase4-manual-size-recovery-policy-v1"
        or not isinstance(recovery_entries, list)
        or recoveries.get("entry_count") != len(recovery_entries)
        or len(recovery_entries) != generated.get("manual_size_recovery_count")
    ):
        raise AuditError("manual-size recovery ledger is invalid")
    recovery_approvals: list[str] = []
    for row in recovery_entries:
        if not isinstance(row, dict) or set(row) != {
            "opaque_id",
            "section_id",
            "owner_role",
            "evidence_class",
            "reason_code",
            "disposition",
            "approval_sha256",
        }:
            raise AuditError("manual-size recovery ledger row is invalid")
        opaque_id = row.get("opaque_id")
        if (
            not isinstance(opaque_id, str)
            or re.fullmatch(r"manual-size-[0-9a-f]{24}", opaque_id) is None
            or not isinstance(row.get("section_id"), str)
            or re.fullmatch(r"section-[0-9]{3}", row["section_id"]) is None
            or row.get("owner_role") != "authoritative-body"
            or row.get("evidence_class") != "uncovered-zero-size-function"
            or row.get("reason_code") != "next-executable-symbol-boundary"
            or row.get("disposition") != "recovered-authoritative-body"
            or row.get("approval_sha256")
            != _policy_approval_digest(
                "phase4-manual-size-recovery-policy-v1",
                opaque_id,
                "uncovered-zero-size-function",
                "recovered-authoritative-body",
            )
        ):
            raise AuditError("manual-size recovery ledger row is invalid")
        recovery_approvals.append(str(row["approval_sha256"]))
    recovery_approval_digest = _sha256(_canonical_bytes(sorted(recovery_approvals)))
    if (
        recoveries.get("approval_set_sha256") != recovery_approval_digest
        or generated.get("manual_size_recovery_approval_set_sha256")
        != recovery_approval_digest
    ):
        raise AuditError("manual-size recovery approval set is invalid")

    exception_entries = exceptions.get("entries")
    exception_contracts = {
        "anomalous-r-mips-26": (
            "direct-call",
            "out-of-domain-overlay-reference",
            "fail-closed-trap",
        ),
        "reserved-atomic-hi-lo": (
            "instruction-relocation",
            "reserved-reference-class",
            "unresolved-data-atomic-pair",
        ),
    }
    if (
        set(exceptions)
        != {
            "schema_version",
            "kind",
            "policy_id",
            "entry_count",
            "category_counts",
            "source_ledger_sha256",
            "approval_set_sha256",
            "entries",
        }
        or exceptions.get("schema_version") != 1
        or exceptions.get("kind") != "jfg-phase4-approved-exception-ledger"
        or exceptions.get("policy_id") != "phase4-transform-exception-policy-v1"
        or not isinstance(exception_entries, list)
        or exceptions.get("entry_count") != len(exception_entries)
    ):
        raise AuditError("approved exception ledger is invalid")
    exception_counts = {key: 0 for key in exception_contracts}
    exception_ids: set[str] = set()
    exception_approvals: list[str] = []
    for row in exception_entries:
        if not isinstance(row, dict) or set(row) != {
            "opaque_id",
            "category",
            "evidence_class",
            "owner_role",
            "reason",
            "disposition",
            "approval_sha256",
        }:
            raise AuditError("approved exception ledger row is invalid")
        opaque_id = row.get("opaque_id")
        category = row.get("category")
        contract = exception_contracts.get(category) if isinstance(category, str) else None
        if (
            not isinstance(opaque_id, str)
            or re.fullmatch(r"exception-[0-9a-f]{24}", opaque_id) is None
            or opaque_id in exception_ids
            or contract is None
            or row.get("owner_role") != "transformer"
            or (row.get("evidence_class"), row.get("reason"), row.get("disposition"))
            != contract
            or row.get("approval_sha256")
            != _policy_approval_digest(
                "phase4-transform-exception-policy-v1",
                opaque_id,
                category,
                str(row.get("disposition")),
            )
        ):
            raise AuditError("approved exception ledger row is invalid")
        exception_ids.add(opaque_id)
        exception_counts[category] += 1
        exception_approvals.append(str(row["approval_sha256"]))
    if (
        exceptions.get("category_counts") != exception_counts
        or exceptions.get("approval_set_sha256")
        != _sha256(_canonical_bytes(sorted(exception_approvals)))
    ):
        raise AuditError("approved exception ledger does not reconcile")

    slot_rows = slots.get("slots")
    lifecycle_rows = lifecycle.get("slots")
    if (
        set(slots)
        != {
            "schema_version",
            "kind",
            "executable_section_count",
            "slot_count",
            "populated_slot_count",
            "empty_slot_count",
            "slots",
        }
        or set(lifecycle)
        != {
            "schema_version",
            "kind",
            "executable_section_count",
            "slot_count",
            "populated_slot_count",
            "empty_slot_count",
            "slots",
        }
        or not isinstance(slot_rows, list)
        or not isinstance(lifecycle_rows, list)
        or slots.get("slot_count") != len(slot_rows)
        or lifecycle.get("slot_count") != len(lifecycle_rows)
        or len(slot_rows) != len(lifecycle_rows)
        or slots.get("executable_section_count")
        != lifecycle.get("executable_section_count")
    ):
        raise AuditError("overlay slot semantics are invalid")
    populated_sections: set[str] = set()
    populated_count = 0
    empty_count = 0
    for index, (slot, life) in enumerate(zip(slot_rows, lifecycle_rows), start=1):
        if (
            not isinstance(slot, dict)
            or set(slot) != {
                "slot_id",
                "disposition",
                "section_id",
                "source_binding_sha256",
            }
            or not isinstance(life, dict)
            or set(life) != {"slot_id", "section_id", "disposition"}
            or slot.get("slot_id") != f"slot-{index:03d}"
            or life.get("slot_id") != slot.get("slot_id")
            or life.get("section_id") != slot.get("section_id")
            or not isinstance(slot.get("source_binding_sha256"), str)
            or SHA256_RE.fullmatch(str(slot.get("source_binding_sha256"))) is None
        ):
            raise AuditError("overlay slot semantic row is invalid")
        if slot.get("disposition") == "populated":
            section_id = slot.get("section_id")
            if (
                not isinstance(section_id, str)
                or re.fullmatch(r"section-[0-9]{3}", section_id) is None
                or section_id in populated_sections
                or life.get("disposition") != "load-unload-reload"
            ):
                raise AuditError("populated overlay slot semantic row is invalid")
            populated_sections.add(section_id)
            populated_count += 1
        elif (
            slot.get("disposition") == "empty-fail-closed"
            and slot.get("section_id") is None
            and life.get("disposition") == "empty-fail-closed"
        ):
            empty_count += 1
        else:
            raise AuditError("empty overlay slot semantic row is invalid")
    executable_section_count = slots.get("executable_section_count")
    if (
        type(executable_section_count) is not int
        or executable_section_count != populated_count + 1
        or slots.get("populated_slot_count") != populated_count
        or lifecycle.get("populated_slot_count") != populated_count
        or slots.get("empty_slot_count") != empty_count
        or lifecycle.get("empty_slot_count") != empty_count
    ):
        raise AuditError("overlay slots and executable sections do not reconcile")

    lookup_sections = lookup.get("sections")
    lookup_entries = lookup.get("entries")
    if (
        set(lookup)
        != {
            "schema_version",
            "kind",
            "executable_section_count",
            "overlay_slot_count",
            "entry_count",
            "authoritative_entry_count",
            "alternate_entry_count",
            "sections",
            "entries",
        }
        or not isinstance(lookup_sections, list)
        or not isinstance(lookup_entries, list)
        or len(lookup_sections) != executable_section_count
        or lookup.get("overlay_slot_count") != len(slot_rows)
        or lookup.get("entry_count") != len(lookup_entries)
        or lookup.get("authoritative_entry_count")
        != generated.get("authoritative_body_count")
        or lookup.get("alternate_entry_count")
        != generated.get("alternate_entry_thunk_count")
        or lookup.get("entry_count")
        != lookup.get("authoritative_entry_count")
        + lookup.get("alternate_entry_count")
    ):
        raise AuditError("lookup semantics are invalid")
    section_totals = {"authoritative_entry_count": 0, "alternate_entry_count": 0}
    for index, row in enumerate(lookup_sections):
        if (
            not isinstance(row, dict)
            or set(row)
            != {
                "section_id",
                "authoritative_entry_count",
                "alternate_entry_count",
            }
            or row.get("section_id") != f"section-{index:03d}"
            or any(
                type(row.get(field)) is not int or row[field] < 0
                for field in section_totals
            )
        ):
            raise AuditError("lookup section semantic row is invalid")
        for field in section_totals:
            section_totals[field] += row[field]
    if any(section_totals[field] != lookup.get(field) for field in section_totals):
        raise AuditError("lookup section semantics do not reconcile")
    entry_ids: set[str] = set()
    entry_class_counts = {"authoritative-body": 0, "alternate-entry": 0}
    for row in lookup_entries:
        if (
            not isinstance(row, dict)
            or set(row) != {"entry_id", "section_id", "entry_class"}
            or not isinstance(row.get("entry_id"), str)
            or re.fullmatch(r"lookup-[0-9a-f]{24}", str(row.get("entry_id"))) is None
            or row["entry_id"] in entry_ids
            or row.get("entry_class") not in entry_class_counts
            or not isinstance(row.get("section_id"), str)
            or re.fullmatch(r"section-[0-9]{3}", str(row.get("section_id"))) is None
        ):
            raise AuditError("lookup entry semantic row is invalid")
        entry_ids.add(str(row["entry_id"]))
        entry_class_counts[str(row["entry_class"])] += 1
    if (
        entry_class_counts["authoritative-body"]
        != lookup.get("authoritative_entry_count")
        or entry_class_counts["alternate-entry"]
        != lookup.get("alternate_entry_count")
    ):
        raise AuditError("lookup entry semantics do not reconcile")

    relocation_rows = relocations.get("sections")
    if (
        set(relocations)
        != {
            "schema_version",
            "kind",
            "executable_section_count",
            "entry_count",
            "resolved_entry_count",
            "unresolved_entry_count",
            "ledger_sha256",
            "approval_set_sha256",
            "sections",
        }
        or not isinstance(relocation_rows, list)
        or len(relocation_rows) != executable_section_count
        or relocations.get("resolved_entry_count") != relocations.get("entry_count")
        or relocations.get("unresolved_entry_count") != 0
    ):
        raise AuditError("relocation semantics are invalid")
    relocation_total = 0
    for index, row in enumerate(relocation_rows):
        if (
            not isinstance(row, dict)
            or set(row) != {"section_id", "entry_count"}
            or row.get("section_id") != f"section-{index:03d}"
            or type(row.get("entry_count")) is not int
            or row["entry_count"] < 0
        ):
            raise AuditError("relocation section semantic row is invalid")
        relocation_total += row["entry_count"]
    if relocation_total != relocations.get("entry_count"):
        raise AuditError("relocation section semantics do not reconcile")

    decision_rows = decisions.get("decisions")
    direct_rows = decisions.get("direct_calls")
    callable_set = decisions.get("generated_callable_set")
    callable_members = (
        callable_set.get("members") if isinstance(callable_set, dict) else None
    )
    if (
        set(decisions)
        != {"schema_version", "kind", "generated_callable_set", "decisions", "direct_calls"}
        or decisions.get("schema_version") != 1
        or decisions.get("kind") != "n64recomp-indirect-decision-sidecar"
        or not isinstance(callable_set, dict)
        or set(callable_set) != {"kind", "member_count", "members"}
        or callable_set.get("kind") != "exact-generated-callable-entry-set"
        or not isinstance(callable_members, list)
        or callable_set.get("member_count") != len(callable_members)
        or len(callable_members) != lookup.get("entry_count")
        or not isinstance(decision_rows, list)
        or not isinstance(direct_rows, list)
    ):
        raise AuditError("N64Recomp decision sidecar is invalid")
    callable_by_name: dict[str, dict[str, object]] = {}
    expected_member_order: list[tuple[int, int, int, str]] = []
    for member in callable_members:
        if (
            not isinstance(member, dict)
            or set(member)
            != {"generated_function", "source_section", "source_offset", "size"}
            or not isinstance(member.get("generated_function"), str)
            or member["generated_function"] in callable_by_name
            or type(member.get("source_section")) is not int
            or type(member.get("source_offset")) is not int
            or type(member.get("size")) is not int
            or member["source_section"] < 0
            or member["source_offset"] < 0
            or member["size"] <= 0
            or member["source_offset"] % 4 != 0
            or member["size"] % 4 != 0
        ):
            raise AuditError("N64Recomp callable-set row is invalid")
        callable_by_name[str(member["generated_function"])] = member
        expected_member_order.append(
            (
                member["source_section"],
                member["source_offset"],
                -member["size"],
                str(member["generated_function"]),
            )
        )
    if expected_member_order != sorted(expected_member_order):
        raise AuditError("N64Recomp callable set is noncanonical")
    decision_sites: set[tuple[int, int]] = set()
    decision_by_site: dict[tuple[int, int], bytes] = {}
    decision_class_by_site: dict[tuple[int, int], str] = {}
    emissions_by_site: dict[tuple[int, int], set[str]] = {}
    classification_counts = {
        "native-return": 0,
        "bounded-switch": 0,
        "dynamic-call": 0,
        "dynamic-tail": 0,
    }
    for row in decision_rows:
        if (
            not isinstance(row, dict)
            or set(row)
            != {
                "classification",
                "default_disposition",
                "generated_function",
                "range",
                "source_offset",
                "source_register",
                "source_section",
            }
            or row.get("classification")
            not in {"native-return", "bounded-switch", "dynamic-call", "dynamic-tail"}
            or type(row.get("source_section")) is not int
            or type(row.get("source_offset")) is not int
            or row["source_section"] < 0
            or row["source_offset"] < 0
            or row["source_offset"] % 4 != 0
            or type(row.get("source_register")) is not int
            or not 0 <= row["source_register"] < 32
            or row.get("generated_function") not in callable_by_name
        ):
            raise AuditError("N64Recomp decision sidecar row is invalid")
        classification = str(row["classification"])
        range_value = row.get("range")
        if classification == "native-return":
            if (
                row.get("source_register") != 31
                or row.get("default_disposition") != "fail-closed-return-context"
                or range_value != {"kind": "active-native-return-continuation"}
            ):
                raise AuditError("N64Recomp native-return range is invalid")
        elif classification == "bounded-switch":
            if (
                row.get("default_disposition") != "fail-closed-switch-error"
                or not isinstance(range_value, dict)
                or set(range_value) != {"kind", "members"}
                or range_value.get("kind") != "exact-target-member-set"
                or not isinstance(range_value.get("members"), list)
                or not range_value["members"]
            ):
                raise AuditError("N64Recomp bounded switch range is invalid")
            switch_members = range_value["members"]
            expected_switch_order: list[tuple[int, int]] = []
            for member in switch_members:
                if (
                    not isinstance(member, dict)
                    or set(member) != {"target_section", "target_offset"}
                    or type(member.get("target_section")) is not int
                    or type(member.get("target_offset")) is not int
                    or member["target_section"] < 0
                    or member["target_offset"] < 0
                    or member["target_offset"] % 4 != 0
                ):
                    raise AuditError("N64Recomp bounded switch member is invalid")
                expected_switch_order.append(
                    (member["target_section"], member["target_offset"])
                )
            if expected_switch_order != sorted(set(expected_switch_order)):
                raise AuditError("N64Recomp bounded switch range is noncanonical")
        elif (
            row.get("default_disposition") != "fail-closed-lookup-miss"
            or range_value != {"kind": "generated-callable-set"}
        ):
            raise AuditError("N64Recomp dynamic range is invalid")
        owner = callable_by_name[str(row["generated_function"])]
        if (
            owner["source_section"] != row["source_section"]
            or not owner["source_offset"]
            <= row["source_offset"]
            < owner["source_offset"] + owner["size"]
        ):
            raise AuditError("N64Recomp decision owner is invalid")
        site = (row["source_section"], row["source_offset"])
        projection = _canonical_bytes(
            {
                "classification": row.get("classification"),
                "default_disposition": row.get("default_disposition"),
                "range": row.get("range"),
                "source_register": row.get("source_register"),
            }
        )
        if site in decision_by_site and decision_by_site[site] != projection:
            raise AuditError("N64Recomp duplicate-site decisions differ")
        generated_function = row.get("generated_function")
        if not isinstance(generated_function, str):
            raise AuditError("N64Recomp decision owner is invalid")
        decision_by_site[site] = projection
        decision_class_by_site[site] = classification
        emissions_by_site.setdefault(site, set()).add(generated_function)
        decision_sites.add(site)
        classification_counts[classification] += 1
    if len(decision_rows) != sum(len(owners) for owners in emissions_by_site.values()):
        raise AuditError("N64Recomp decision emissions are duplicated")
    expected_owners_by_site = {
        site: {
            name
            for name, member in callable_by_name.items()
            if member["source_section"] == site[0]
            and member["source_offset"] <= site[1] < member["source_offset"] + member["size"]
        }
        for site in decision_sites
    }
    if emissions_by_site != expected_owners_by_site:
        raise AuditError("N64Recomp decision owner coverage is incomplete")
    direct_sites: set[tuple[int, int]] = set()
    direct_emissions: dict[tuple[int, int], set[str]] = {}
    direct_projection: dict[tuple[int, int], bytes] = {}
    direct_role_counts = {"linked-call": 0, "direct-tail": 0}
    direct_class_counts = {"jal": 0, "bgezal": 0, "j": 0, "conditional-branch": 0}
    for row in direct_rows:
        if not isinstance(row, dict) or set(row) != {
            "classification", "default_disposition", "generated_function",
            "instruction_class", "source_offset", "source_section", "target", "transfer_role",
        }:
            raise AuditError("N64Recomp direct-call sidecar row is invalid")
        role = row.get("transfer_role")
        instruction_class = row.get("instruction_class")
        target = row.get("target")
        owner_name = row.get("generated_function")
        if (
            role not in direct_role_counts
            or instruction_class not in direct_class_counts
            or (role == "linked-call" and instruction_class not in {"jal", "bgezal"})
            or (role == "direct-tail" and instruction_class not in {"j", "conditional-branch"})
            or row.get("classification") != "checked-lookup-call"
            or row.get("default_disposition") != "fail-closed-lookup-miss"
            or not isinstance(target, dict)
            or set(target) != {"address", "kind"}
            or type(target.get("address")) is not int
            or not 0 <= target["address"] <= 0xFFFFFFFF
            or target.get("kind") != "runtime-address"
            or not isinstance(owner_name, str)
            or owner_name not in callable_by_name
            or type(row.get("source_section")) is not int
            or type(row.get("source_offset")) is not int
            or row["source_offset"] < 0
            or row["source_offset"] % 4 != 0
        ):
            raise AuditError("N64Recomp direct-call sidecar row is invalid")
        owner = callable_by_name[owner_name]
        if (
            owner["source_section"] != row["source_section"]
            or not owner["source_offset"] <= row["source_offset"] < owner["source_offset"] + owner["size"]
        ):
            raise AuditError("N64Recomp direct-call owner is invalid")
        site = (row["source_section"], row["source_offset"])
        projection = _canonical_bytes({
            "classification": row["classification"],
            "default_disposition": row["default_disposition"],
            "instruction_class": instruction_class,
            "target": target,
            "transfer_role": role,
        })
        if site in direct_projection and direct_projection[site] != projection:
            raise AuditError("N64Recomp duplicate-site direct calls differ")
        direct_projection[site] = projection
        direct_emissions.setdefault(site, set()).add(owner_name)
        direct_sites.add(site)
    if len(direct_rows) != sum(len(owners) for owners in direct_emissions.values()):
        raise AuditError("N64Recomp direct-call emissions are duplicated")
    for site, owners in direct_emissions.items():
        containing = {
            name
            for name, member in callable_by_name.items()
            if member["source_section"] == site[0]
            and member["source_offset"] <= site[1] < member["source_offset"] + member["size"]
        }
        role = next(
            str(row["transfer_role"])
            for row in direct_rows
            if (row["source_section"], row["source_offset"]) == site
        )
        if not owners or not owners.issubset(containing) or (role == "linked-call" and owners != containing):
            raise AuditError("N64Recomp direct-call owner coverage is invalid")
        direct_role_counts[role] += 1
        instruction_class = next(
            str(row["instruction_class"])
            for row in direct_rows
            if (row["source_section"], row["source_offset"]) == site
        )
        direct_class_counts[instruction_class] += 1

    generation_keys = {
        "schema_version",
        "kind",
        "symbols",
        "calls",
        "relocations",
        "overlays",
        "stubs",
        "semantic_bindings",
    }
    generation_overlays = generation.get("overlays")
    bindings = generation.get("semantic_bindings")
    if (
        set(generation) != generation_keys
        or generation.get("schema_version") != 1
        or generation.get("kind") != "jfg-phase4-generation-semantic-result"
        or not isinstance(generation_overlays, dict)
        or not isinstance(bindings, dict)
        or generation.get("symbols", {}).get("inventory_sha256")
        != _sha256(products["generated-inventory"])
        or generation.get("calls", {}).get("indirect_ranges", {}).get("expected_count")
        != len(decision_sites)
        or generation.get("calls", {}).get("indirect_ranges", {}).get("resolved_count")
        != len(decision_sites)
        or generation.get("calls", {}).get("indirect_ranges", {}).get("native_return_count")
        != sum(value == "native-return" for value in decision_class_by_site.values())
        or generation.get("calls", {}).get("indirect_ranges", {}).get("decision_range_count")
        != sum(value != "native-return" for value in decision_class_by_site.values())
        or generation.get("calls", {}).get("direct", {}).get("candidate_count")
        != len(direct_sites)
        or generation.get("calls", {}).get("direct", {}).get("expected_count")
        != len(direct_sites)
        or generation.get("calls", {}).get("direct", {}).get("transfer_role_counts")
        != direct_role_counts
        or generation.get("calls", {}).get("direct", {}).get("instruction_class_counts")
        != direct_class_counts
        or generation.get("relocations", {}).get("data_r32", {}).get("expected_count")
        != relocations.get("entry_count")
        or generation_overlays.get("executable_section_count")
        != executable_section_count
        or generation_overlays.get("expected_slot_count") != len(slot_rows)
        or generation_overlays.get("populated_slot_count") != populated_count
        or generation_overlays.get("empty_slot_count") != empty_count
        or generation_overlays.get("slot_inventory_sha256")
        != _sha256(products["overlay-slot-inventory"])
        or generation_overlays.get("lookup_table_sha256")
        != _sha256(products["overlay-lookup-table"])
        or generation_overlays.get("lifecycle_table_sha256")
        != _sha256(products["overlay-lifecycle-table"])
        or generation_overlays.get("relocation_table_sha256")
        != _sha256(products["relocation-table"])
        or bindings
        != {
            "alternate_entry_ledger_sha256": _sha256(
                products["alternate-entry-ledger"]
            ),
            "covered_alias_ledger_sha256": _sha256(
                products["covered-alias-ledger"]
            ),
            "manual_size_recovery_ledger_sha256": _sha256(
                products["manual-size-recovery-ledger"]
            ),
            "exception_ledger_sha256": _sha256(products["exception-ledger"]),
            "n64recomp_decision_sidecar_sha256": _sha256(
                products["n64recomp-decision-sidecar"]
            ),
        }
    ):
        raise AuditError("generation semantic result does not reconcile")

    if public_record is not None:
        for field in ("symbols", "calls", "relocations", "stubs"):
            if generation.get(field) != public_record.get(field):
                raise AuditError("generation semantic result differs from public denominators")
        public_overlays = public_record.get("overlays")
        if not isinstance(public_overlays, dict) or any(
            key in public_overlays and public_overlays[key] != value
            for key, value in generation_overlays.items()
        ):
            raise AuditError("generation overlay semantics differ from public denominators")

    report_rows = reports.get("reports")
    expected_reports = {
        kind: _sha256(payload)
        for kind, payload in products.items()
        if kind
        in {
            "generation-result",
            "generated-inventory",
            "alternate-entry-ledger",
            "covered-alias-ledger",
            "exception-ledger",
            "manual-size-recovery-ledger",
            "overlay-slot-inventory",
            "overlay-lookup-table",
            "overlay-lifecycle-table",
            "relocation-table",
            "n64recomp-decision-sidecar",
        }
    }
    if (
        set(reports) != {"schema_version", "kind", "reports"}
        or not isinstance(report_rows, list)
        or report_rows
        != [
            {"product_kind": kind, "sha256": digest}
            for kind, digest in sorted(expected_reports.items())
        ]
    ):
        raise AuditError("generation report set does not reconcile")


def _repository_root() -> Path:
    textual = os.environ.get("JFG_PHASE4_REPOSITORY_ROOT")
    if not textual or not os.path.isabs(textual):
        raise AuditError("trusted repository root is unavailable")
    try:
        root = Path(textual).resolve(strict=True)
        metadata = root.lstat()
    except OSError as error:
        raise AuditError("trusted repository root is unavailable") from error
    if not stat.S_ISDIR(metadata.st_mode) or _is_reparse(metadata):
        raise AuditError("trusted repository root is unavailable")
    return root


def _read_fixed_regular(path: Path, maximum: int = 4 * 1024 * 1024) -> bytes:
    descriptor: int | None = None
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        before = path.lstat()
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        after = path.lstat()
        if (
            _is_reparse(before)
            or _is_reparse(after)
            or not stat.S_ISREG(opened.st_mode)
            or not os.path.samestat(before, opened)
            or not os.path.samestat(after, opened)
            or opened.st_size > maximum
        ):
            raise AuditError("tracked build replay source boundary is invalid")
        payload = bytearray()
        while len(payload) <= maximum:
            block = os.read(descriptor, min(64 * 1024, maximum + 1 - len(payload)))
            if not block:
                break
            payload.extend(block)
        if len(payload) > maximum:
            raise AuditError("tracked build replay source is oversized")
        return bytes(payload)
    except OSError as error:
        raise AuditError("tracked build replay source is unavailable") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _verify_build_replay_source_closure(repository_root: Path) -> None:
    if not BUILD_REPLAY_SOURCE_SHA256 or any(
        not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None
        for digest in BUILD_REPLAY_SOURCE_SHA256.values()
    ):
        raise AuditError("tracked build replay source policy is not pinned")
    for textual, expected in BUILD_REPLAY_SOURCE_SHA256.items():
        parsed = PurePosixPath(textual)
        try:
            path = repository_root.joinpath(*parsed.parts).resolve(strict=True)
            path.relative_to(repository_root)
        except (OSError, ValueError) as error:
            raise AuditError("tracked build replay source is unavailable") from error
        if _sha256(_read_fixed_regular(path)) != expected:
            raise AuditError("tracked build replay source differs from its pin")


def _verify_generation_replay_source_closure(repository_root: Path) -> None:
    if not GENERATION_REPLAY_SOURCE_SHA256 or any(
        not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None
        for digest in GENERATION_REPLAY_SOURCE_SHA256.values()
    ):
        raise AuditError("tracked generation replay source policy is not pinned")
    for textual, expected in GENERATION_REPLAY_SOURCE_SHA256.items():
        parsed = PurePosixPath(textual)
        try:
            path = repository_root.joinpath(*parsed.parts).resolve(strict=True)
            path.relative_to(repository_root)
        except (OSError, ValueError) as error:
            raise AuditError("tracked generation replay source is unavailable") from error
        if _sha256(_read_fixed_regular(path)) != expected:
            raise AuditError("tracked generation replay source differs from its pin")


def _fixed_generation_recompiler(
    repository_root: Path, expected_sha256: object
) -> tuple[Path, bytes]:
    if not isinstance(expected_sha256, str) or SHA256_RE.fullmatch(expected_sha256) is None:
        raise AuditError("generation recompiler identity is unavailable")
    try:
        path = repository_root.joinpath(*GENERATION_RECOMPILER_RELATIVE.parts).resolve(
            strict=True
        )
        path.relative_to(repository_root)
    except (OSError, ValueError) as error:
        raise AuditError("fixed generation recompiler is unavailable") from error
    payload = _read_fixed_regular(path, MAX_SYSTEM_EXECUTABLE_BYTES)
    if _sha256(payload) != expected_sha256 or not payload.startswith(b"\x7fELF"):
        raise AuditError("fixed generation recompiler differs from the public pin")
    return path, payload


def _generation_config() -> bytes:
    return (
        b"[input]\n"
        b"symbols_file_path = \"symbols.toml\"\n"
        b"rom_file_path = \"patched.z64\"\n"
        b"output_func_path = \"raw\"\n"
        b"indirect_decision_sidecar_path = \"raw/indirect_decisions.json\"\n"
        b"functions_per_output_file = 50\n"
        b"unpaired_lo16_warnings = false\n"
        b"use_lookup_for_all_function_calls = true\n"
    )


def _stage_generation_inputs(root: Path, inputs: dict[str, bytes]) -> None:
    """Stage bounded private inputs and re-read each with its declared bound."""
    for name, payload in inputs.items():
        maximum = GENERATION_INPUT_SIZE_LIMITS.get(name)
        if maximum is None:
            raise AuditError("generation replay input name is invalid")
        destination = root / name
        destination.write_bytes(payload)
        if _sha256(_read_fixed_regular(destination, maximum)) != _sha256(payload):
            raise AuditError("generation replay input staging differs")


def _replay_generation(
    products: dict[str, bytes], contents: dict[str, bytes], request: dict[str, object]
) -> None:
    inputs = _generation_input_contents(products)
    pins = request.get("pins")
    if (
        not isinstance(pins, dict)
        or pins.get("input_elf_sha256") != _sha256(inputs["input.elf"])
    ):
        raise AuditError("generation input ELF differs from the public pin")
    if products.get("cpu-section-inventory") != contents.get("cpu_section_inventory.json"):
        raise AuditError("CPU section inventory differs from the generated archive")
    _canonical_json_product(products["cpu-section-inventory"])
    repository_root = _repository_root()
    expected_toolchain = request["public_binding"].get("toolchain_sha256")  # type: ignore[index]
    generator, generator_payload = _fixed_generation_recompiler(
        repository_root, expected_toolchain
    )
    _verify_generation_replay_source_closure(repository_root)
    normalizer = repository_root / "scripts" / "build_private_generated_root.py"
    context_replay = repository_root / "scripts" / "prepare_n64recomp_context_dump.py"
    transformer = repository_root / "scripts" / "transform_private_n64recomp_inputs.py"
    expected_normalizer = GENERATION_REPLAY_SOURCE_SHA256.get(
        "scripts/build_private_generated_root.py"
    )
    if expected_normalizer is None or _sha256(_read_fixed_regular(normalizer)) != expected_normalizer:
        raise AuditError("tracked generation normalizer differs from its pin")
    _verify_fixed_wsl_file("/usr/bin/python3", WSL_BUILD_TOOL_SHA256["/usr/bin/python3"])
    _verify_fixed_wsl_file("/usr/bin/readelf", WSL_BUILD_TOOL_SHA256["/usr/bin/readelf"])
    with tempfile.TemporaryDirectory(prefix="phase4-generation-replay-") as temporary:
        temporary_root = Path(temporary)
        _stage_generation_inputs(temporary_root, inputs)
        replay_generator = temporary_root / "N64Recomp"
        replay_generator.write_bytes(generator_payload)
        os.chmod(replay_generator, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        config = temporary_root / "recompile.toml"
        config.write_bytes(_generation_config())
        context_output = temporary_root / "context"
        context_config = temporary_root / "context-replay.toml"
        transform_output = temporary_root / "transform"
        raw_output = temporary_root / "raw"
        normalized_output = temporary_root / "normalized"
        context_output.mkdir()
        return_code, _, _ = _run_fixed_wsl(
            [
                "-d",
                "Ubuntu-24.04",
                "--exec",
                "/usr/bin/python3",
                _wsl_path(context_replay),
                "--elf",
                _wsl_path(temporary_root / "input.elf"),
                "--generated-output",
                _wsl_path(temporary_root / "context-generated", must_exist=False),
                "--output-config",
                _wsl_path(context_config, must_exist=False),
            ],
            cwd=temporary_root,
            timeout_seconds=BUILD_REPLAY_TIMEOUT_SECONDS,
        )
        if return_code != 0:
            raise AuditError("fixed generation context replay failed")
        return_code, _, _ = _run_fixed_wsl(
            [
                "-d",
                "Ubuntu-24.04",
                "--exec",
                _wsl_path(replay_generator),
                _wsl_path(context_config),
                "--dump-context",
            ],
            cwd=context_output,
            timeout_seconds=BUILD_REPLAY_TIMEOUT_SECONDS,
        )
        if return_code != 0:
            raise AuditError("fixed generation context dump replay failed")
        context_dump = context_output / "dump.toml"
        data_context_dump = context_output / "data_dump.toml"
        if (
            _read_fixed_regular(context_dump, GENERATION_INPUT_SIZE_LIMITS["original_context.toml"])
            != inputs["original_context.toml"]
            or _read_fixed_regular(data_context_dump, GENERATION_INPUT_SIZE_LIMITS["data_context.toml"])
            != inputs["data_context.toml"]
        ):
            raise AuditError("generation context replay differs from the staged input")
        return_code, _, _ = _run_fixed_wsl(
            [
                "-d",
                "Ubuntu-24.04",
                "--exec",
                "/usr/bin/python3",
                _wsl_path(transformer),
                "--rom",
                _wsl_path(temporary_root / "original.z64"),
                "--elf",
                _wsl_path(temporary_root / "input.elf"),
                "--readelf",
                "/usr/bin/readelf",
                "--layout",
                _wsl_path(temporary_root / "overlay-layout.json"),
                "--context",
                _wsl_path(context_dump),
                "--data-context",
                _wsl_path(data_context_dump),
                "--output-dir",
                _wsl_path(transform_output, must_exist=False),
            ],
            cwd=temporary_root,
            timeout_seconds=BUILD_REPLAY_TIMEOUT_SECONDS,
        )
        if return_code != 0:
            raise AuditError("fixed generation transform replay failed")
        transformed = {
            "patched.z64": transform_output / "patched-private.z64",
            "symbols.toml": transform_output / "symbols-private.toml",
            "runtime_manifest.json": transform_output / "runtime-link-private.json",
        }
        if any(
            _read_fixed_regular(path, GENERATION_INPUT_SIZE_LIMITS[name]) != inputs[name]
            for name, path in transformed.items()
        ):
            raise AuditError("generation transform replay differs from the staged input")
        return_code, _, _ = _run_fixed_wsl(
            [
                "-d",
                "Ubuntu-24.04",
                "--exec",
                _wsl_path(replay_generator),
                _wsl_path(config),
            ],
            cwd=temporary_root,
            timeout_seconds=BUILD_REPLAY_TIMEOUT_SECONDS,
        )
        if return_code != 0:
            raise AuditError("fixed generation recompiler replay failed")
        return_code, _, _ = _run_fixed_wsl(
            [
                "-d",
                "Ubuntu-24.04",
                "--exec",
                "/usr/bin/python3",
                _wsl_path(normalizer),
                "--raw-generated",
                _wsl_path(raw_output, must_exist=False),
                "--symbols",
                _wsl_path(temporary_root / "symbols.toml"),
                "--original-context",
                _wsl_path(context_dump),
                "--runtime-manifest",
                _wsl_path(temporary_root / "runtime_manifest.json"),
                "--recomp-header",
                _wsl_path(temporary_root / "recomp.h"),
                "--output",
                _wsl_path(normalized_output, must_exist=False),
            ],
            cwd=temporary_root,
            timeout_seconds=BUILD_REPLAY_TIMEOUT_SECONDS,
        )
        if return_code != 0:
            raise AuditError("fixed generation normalizer replay failed")
        if _private_tree_contents(normalized_output) != contents:
            raise AuditError("generation replay output differs from the staged source archive")
    _, observed_generator = _fixed_generation_recompiler(repository_root, expected_toolchain)
    if observed_generator != generator_payload:
        raise AuditError("fixed generation recompiler changed during replay")
    if _sha256(_read_fixed_regular(normalizer)) != expected_normalizer:
        raise AuditError("tracked generation normalizer changed during replay")
    _verify_fixed_wsl_file("/usr/bin/python3", WSL_BUILD_TOOL_SHA256["/usr/bin/python3"])
    _verify_fixed_wsl_file("/usr/bin/readelf", WSL_BUILD_TOOL_SHA256["/usr/bin/readelf"])


def _compiler_option_set(public_record: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "kind": "jfg-phase4-fixed-cmake-option-set",
        "family": public_record.get("family"),
        "target_id": public_record.get("target_id"),
        "configuration_id": public_record.get("configuration_id"),
        "generated_language": "c11",
        "handwritten_language": "c++20",
        "warnings_as_errors": True,
        "object_shape_audit": True,
        "whole_object_targets": list(BUILD_REPLAY_TARGETS),
    }


def _verify_compiler_record(
    evidence_kind: str, public_record: object
) -> dict[str, object]:
    if not isinstance(public_record, dict):
        raise AuditError("compiler public record is unavailable")
    family = evidence_kind.removeprefix("compiler-")
    target = "linux-x64" if family == "gcc" else "windows-x64"
    configuration = public_record.get("configuration_id")
    if (
        public_record.get("family") != family
        or public_record.get("target_id") != target
        or configuration not in {"debug", "release"}
        or _sha256(_canonical_bytes(_compiler_option_set(public_record)))
        != public_record.get("option_set_sha256")
    ):
        raise AuditError("compiler public record differs from the fixed replay policy")
    return public_record


def _fixed_windows_build_tool(relative: str, tool_name: str) -> Path:
    expected_sha256 = WINDOWS_BUILD_TOOL_SHA256.get(tool_name)
    if expected_sha256 is None:
        raise AuditError("fixed Windows build tool policy is invalid")
    roots = tuple(
        Path(f"C:/Program Files/Microsoft Visual Studio/2022/{edition}")
        for edition in ("Community", "BuildTools", "Professional", "Enterprise")
    )
    for root in roots:
        candidate = root.joinpath(*PurePosixPath(relative).parts)
        try:
            path = candidate.resolve(strict=True)
            metadata = path.stat(follow_symlinks=False)
        except OSError:
            continue
        if stat.S_ISREG(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode):
            try:
                _verify_pinned_local_tool(path, expected_sha256)
            except AuditError:
                continue
            return path
    raise AuditError("fixed Windows build tool is unavailable")


def _fixed_windows_cmake() -> Path:
    return _fixed_windows_build_tool(
        "Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe", "cmake.exe"
    )


def _fixed_windows_ninja() -> Path:
    return _fixed_windows_build_tool(
        "Common7/IDE/CommonExtensions/Microsoft/CMake/Ninja/ninja.exe", "ninja.exe"
    )


def _fixed_windows_msvc_companion(tool_name: str) -> Path:
    expected_sha256 = WINDOWS_BUILD_TOOL_SHA256.get(tool_name)
    if expected_sha256 is None:
        raise AuditError("fixed Windows build tool policy is invalid")
    roots = tuple(
        Path(f"C:/Program Files/Microsoft Visual Studio/2022/{edition}/VC/Tools/MSVC")
        for edition in ("Community", "BuildTools", "Professional", "Enterprise")
    )
    for root in roots:
        try:
            versions = sorted((path for path in root.iterdir() if path.is_dir()), reverse=True)
        except OSError:
            continue
        for version in versions:
            candidate = version / "bin" / "Hostx64" / "x64" / tool_name
            try:
                path = candidate.resolve(strict=True)
                _verify_pinned_local_tool(path, expected_sha256)
            except (AuditError, OSError):
                continue
            return path
    raise AuditError("fixed Windows companion tool is unavailable")


def _fixed_windows_python(repository_root: Path) -> Path:
    candidate = repository_root / "tools" / "venv" / "Scripts" / "python.exe"
    try:
        path = candidate.resolve(strict=True)
        path.relative_to(repository_root)
    except (OSError, ValueError) as error:
        raise AuditError("fixed Windows Python build tool is unavailable") from error
    _verify_pinned_local_tool(path, WINDOWS_BUILD_TOOL_SHA256["python.exe"])
    return path


def _fixed_msvc(toolchain_sha256: object) -> Path:
    if not isinstance(toolchain_sha256, str) or SHA256_RE.fullmatch(toolchain_sha256) is None:
        raise AuditError("MSVC toolchain identity is unavailable")
    roots = tuple(
        Path(f"C:/Program Files/Microsoft Visual Studio/2022/{edition}/VC/Tools/MSVC")
        for edition in ("Community", "BuildTools", "Professional", "Enterprise")
    )
    for root in roots:
        try:
            versions = sorted(
                (path for path in root.iterdir() if path.is_dir()), reverse=True
            )
        except OSError:
            continue
        for version in versions:
            candidate = version / "bin" / "Hostx64" / "x64" / "cl.exe"
            try:
                path = candidate.resolve(strict=True)
                payload = _read_system_executable(path)
            except (AuditError, OSError):
                continue
            if _sha256(payload) == toolchain_sha256:
                return path
    raise AuditError("fixed MSVC executable does not match the public toolchain")


def _windows_build_environment(
    *, batch: Path | None = None, command: Path | None = None
) -> dict[str, str]:
    batch = batch or _fixed_windows_build_tool("VC/Auxiliary/Build/vcvars64.bat", "vcvars64.bat")
    _verify_pinned_local_tool(batch, WINDOWS_BUILD_TOOL_SHA256["vcvars64.bat"])
    command = command or Path("C:/Windows/System32/cmd.exe")
    try:
        metadata = command.stat(follow_symlinks=False)
    except OSError as error:
        raise AuditError("fixed Windows command boundary is unavailable") from error
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise AuditError("fixed Windows command boundary is unavailable")
    _verify_pinned_local_tool(command, WINDOWS_BUILD_TOOL_SHA256["cmd.exe"])
    with tempfile.TemporaryDirectory(prefix="phase4-vcenv-") as temporary:
        wrapper = Path(temporary) / "environment.bat"
        wrapper.write_text(
            "@echo off\r\n"
            f'call "{batch}" >nul\r\n'
            "if errorlevel 1 exit /b 1\r\n"
            "set\r\n",
            encoding="ascii",
            newline="",
        )
        bootstrap_path = ";".join(
            (
                "C:/Windows/System32",
                "C:/Windows",
                "C:/Windows/System32/Wbem",
                "C:/Windows/System32/WindowsPowerShell/v1.0",
            )
        )
        return_code, stdout, stderr = _run_bounded(
            [str(command), "/d", "/c", str(wrapper)],
            cwd=batch.parent,
            environment={
                "PATH": bootstrap_path,
                "__VSCMD_PREINIT_PATH": bootstrap_path,
            },
        )
    if return_code != 0 or stderr:
        raise AuditError("fixed Windows build environment is unavailable")
    _verify_pinned_local_tool(batch, WINDOWS_BUILD_TOOL_SHA256["vcvars64.bat"])
    _verify_pinned_local_tool(command, WINDOWS_BUILD_TOOL_SHA256["cmd.exe"])
    allowed = {
        "path",
        "include",
        "lib",
        "libpath",
        "vcinstalldir",
        "vctoolsinstalldir",
        "windowssdkdir",
        "universalcrtsdkdir",
        "ucrtversion",
        "windowssdkversion",
        "systemroot",
        "windir",
        "systemdrive",
        "programdata",
        "programfiles",
        "programfiles(x86)",
        "programw6432",
        "tmp",
        "temp",
    }
    result: dict[str, str] = {}
    for line in stdout.decode("utf-8", errors="ignore").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.casefold() in allowed:
            result[key] = value
    if not any(key.casefold() == "path" for key in result):
        raise AuditError("fixed Windows build environment is unavailable")
    return result


def _local_compiler_id(
    family: str, compiler: Path, environment: dict[str, str]
) -> str:
    arguments = ["/Bv"] if family == "msvc" else ["--version"]
    return_code, stdout, stderr = _run_bounded(
        [str(compiler), *arguments], cwd=compiler.parent, environment=environment
    )
    output = (stdout + b"\n" + stderr).decode("utf-8", errors="ignore")
    if family == "msvc":
        match = re.search(r"Compiler Version ([0-9]+\.[0-9]+)", output)
    else:
        match = re.search(r"clang version ([0-9]+(?:\.[0-9]+){0,3})", output)
    if match is None or (return_code not in {0, 2}):
        raise AuditError("fixed compiler version could not be observed")
    return f"{family}-{match.group(1)}"


def _write_generated_source_root(root: Path, contents: dict[str, bytes]) -> None:
    for textual, payload in contents.items():
        destination = root.joinpath(*PurePosixPath(textual).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        if _sha256(destination.read_bytes()) != _sha256(payload):
            raise AuditError("generated source replay staging differs")


def _cmake_replay_arguments(
    repository_root: str,
    source_root: str,
    build_root: str,
    c_compiler: str,
    cxx_compiler: str,
    configuration: str,
    ninja: str,
    archiver: str,
    ranlib: str,
    linker: str,
    symbol_tool: str,
    python: str,
) -> list[str]:
    return [
        "-S",
        repository_root,
        "-B",
        build_root,
        "-G",
        "Ninja",
        f"-DCMAKE_BUILD_TYPE={configuration}",
        f"-DCMAKE_MAKE_PROGRAM={ninja}",
        f"-DCMAKE_C_COMPILER={c_compiler}",
        f"-DCMAKE_CXX_COMPILER={cxx_compiler}",
        f"-DCMAKE_AR={archiver}",
        f"-DCMAKE_RANLIB={ranlib}",
        f"-DCMAKE_C_COMPILER_AR={archiver}",
        f"-DCMAKE_CXX_COMPILER_AR={archiver}",
        f"-DCMAKE_C_COMPILER_RANLIB={ranlib}",
        f"-DCMAKE_CXX_COMPILER_RANLIB={ranlib}",
        f"-DCMAKE_LINKER={linker}",
        f"-DCMAKE_NM={symbol_tool}",
        f"-DPython3_EXECUTABLE={python}",
        "-DBUILD_TESTING=ON",
        "-DJFG_BUILD_TESTS=ON",
        "-DJFG_BUILD_SYNTHETIC_GENERATED_TESTS=OFF",
        "-DJFG_BUILD_G2_PRODUCERS=OFF",
        "-DJFG_ENABLE_GENERATED_CODE=ON",
        f"-DJFG_GENERATED_ROOT={source_root}",
        "-DJFG_WARNINGS_AS_ERRORS=ON",
        "--log-level=ERROR",
    ]


def _windows_replay_compiler_build(
    contents: dict[str, bytes], public_record: dict[str, object], toolchain_sha256: object
) -> None:
    family = str(public_record["family"])
    compiler = (
        _fixed_msvc(toolchain_sha256)
        if family == "msvc"
        else _fixed_clang_cl(toolchain_sha256)
    )
    repository_root = _repository_root()
    cmake = _fixed_windows_cmake()
    ninja = _fixed_windows_ninja()
    batch = _fixed_windows_build_tool("VC/Auxiliary/Build/vcvars64.bat", "vcvars64.bat")
    command = Path("C:/Windows/System32/cmd.exe")
    linker = _fixed_windows_msvc_companion("link.exe")
    archiver = _fixed_windows_msvc_companion("lib.exe")
    symbol_tool = _fixed_windows_msvc_companion("dumpbin.exe")
    python = _fixed_windows_python(repository_root)
    fixed_tools = (cmake, ninja, batch, command, linker, archiver, symbol_tool, python)
    for tool in fixed_tools:
        _verify_pinned_local_tool(tool, WINDOWS_BUILD_TOOL_SHA256[tool.name.casefold()])
    environment = _windows_build_environment(batch=batch, command=command)
    # Ensure GeneratedCode.cmake's find_program(dumpbin) resolves the bound
    # companion instead of a host PATH entry when replaying clang-cl.
    environment["PATH"] = str(symbol_tool.parent) + ";" + environment.get("PATH", "")
    if _local_compiler_id(family, compiler, environment) != public_record.get("compiler_id"):
        raise AuditError("fixed compiler version differs from the public record")
    configuration = str(public_record["configuration_id"]).capitalize()
    compiler_digest = _sha256(_read_system_executable(compiler))
    with tempfile.TemporaryDirectory(prefix="phase4-compiler-replay-") as temporary:
        temporary_root = Path(temporary)
        source_root = temporary_root / "generated"
        build_root = temporary_root / "build"
        source_root.mkdir()
        _write_generated_source_root(source_root, contents)
        arguments = _cmake_replay_arguments(
            repository_root.as_posix(),
            source_root.as_posix(),
            build_root.as_posix(),
            compiler.as_posix(),
            compiler.as_posix(),
            configuration,
            ninja.as_posix(),
            archiver.as_posix(),
            archiver.as_posix(),
            linker.as_posix(),
            symbol_tool.as_posix(),
            python.as_posix(),
        )
        return_code, _, _ = _run_bounded(
            [str(cmake), *arguments],
            cwd=temporary_root,
            environment=environment,
            timeout_seconds=BUILD_REPLAY_TIMEOUT_SECONDS,
        )
        if return_code != 0:
            raise AuditError("fixed compiler configure replay failed")
        return_code, _, _ = _run_bounded(
            [
                str(cmake),
                "--build",
                str(build_root),
                "--config",
                configuration,
                "--parallel",
                "--target",
                *BUILD_REPLAY_TARGETS,
                "--",
                "--quiet",
            ],
            cwd=temporary_root,
            environment=environment,
            timeout_seconds=BUILD_REPLAY_TIMEOUT_SECONDS,
        )
        if return_code != 0:
            raise AuditError("fixed compiler build replay failed")
        for target in BUILD_REPLAY_TARGETS:
            executable = build_root / f"{target}.exe"
            return_code, stdout, stderr = _run_bounded(
                [str(executable)], cwd=build_root, environment=environment
            )
            if return_code != 0 or stdout or stderr:
                raise AuditError("fixed compiler whole-object probe failed")
        if _sha256(_read_system_executable(compiler)) != compiler_digest:
            raise AuditError("fixed compiler changed during build replay")
        for tool in fixed_tools:
            _verify_pinned_local_tool(tool, WINDOWS_BUILD_TOOL_SHA256[tool.name.casefold()])


def _wsl_compiler_id(compiler: str) -> str:
    return_code, stdout, stderr = _run_fixed_wsl(
        ["-d", "Ubuntu-24.04", "--exec", compiler, "-dumpfullversion"],
        cwd=Path.cwd(),
    )
    try:
        version = stdout.decode("ascii").strip()
    except UnicodeDecodeError as error:
        raise AuditError("fixed GCC version could not be observed") from error
    if return_code != 0 or stderr or re.fullmatch(r"[0-9]+(?:\.[0-9]+){0,3}", version) is None:
        raise AuditError("fixed GCC version could not be observed")
    return f"gcc-{version}"


def _verify_fixed_wsl_file(path: str, expected_sha256: str) -> None:
    if (
        WSL_BUILD_TOOL_SHA256.get(path) != expected_sha256
        or not isinstance(expected_sha256, str)
        or SHA256_RE.fullmatch(expected_sha256) is None
    ):
        raise AuditError("fixed WSL file policy is invalid")
    return_code, stdout, stderr = _run_fixed_wsl(
        ["-d", "Ubuntu-24.04", "--exec", "/usr/bin/sha256sum", path],
        cwd=Path.cwd(),
    )
    fields = stdout.decode("ascii", errors="ignore").split()
    if (
        return_code != 0
        or stderr
        or len(fields) != 2
        or fields[0] != expected_sha256
        or fields[1] != path
    ):
        raise AuditError("fixed WSL file differs from its repository pin")


def _verify_wsl_replay_toolchain() -> None:
    for path, expected_sha256 in WSL_BUILD_TOOL_SHA256.items():
        _verify_fixed_wsl_file(path, expected_sha256)


def _wsl_replay_compiler_build(
    contents: dict[str, bytes], public_record: dict[str, object], toolchain_sha256: object
) -> None:
    _verify_wsl_replay_toolchain()
    compiler = _wsl_compiler("gcc", toolchain_sha256)
    if compiler != "/usr/bin/g++-13" or toolchain_sha256 != GCC_CXX_DRIVER_SHA256:
        raise AuditError("fixed GCC C++ compiler differs from the repository pin")
    if _wsl_compiler_id(compiler) != public_record.get("compiler_id"):
        raise AuditError("fixed compiler version differs from the public record")
    c_compiler = "/usr/bin/gcc-13"
    _verify_fixed_wsl_file(c_compiler, GCC_C_DRIVER_SHA256)
    if _wsl_compiler_id(c_compiler).removeprefix("gcc-") != str(
        public_record.get("compiler_id")
    ).removeprefix("gcc-"):
        raise AuditError("fixed GCC language drivers do not match")
    configuration = str(public_record["configuration_id"]).capitalize()
    with tempfile.TemporaryDirectory(prefix="phase4-compiler-replay-") as temporary:
        temporary_root = Path(temporary)
        source_root = temporary_root / "generated"
        build_root = temporary_root / "build"
        source_root.mkdir()
        _write_generated_source_root(source_root, contents)
        arguments = _cmake_replay_arguments(
            _wsl_path(_repository_root()),
            _wsl_path(source_root),
            _wsl_path(build_root, must_exist=False),
            c_compiler,
            compiler,
            configuration,
            "/usr/bin/ninja",
            "/usr/bin/ar",
            "/usr/bin/ranlib",
            "/usr/bin/ld",
            "/usr/bin/nm",
            "/usr/bin/python3",
        )
        return_code, _, _ = _run_fixed_wsl(
            ["-d", "Ubuntu-24.04", "--exec", "/usr/bin/cmake", *arguments],
            cwd=temporary_root,
            timeout_seconds=BUILD_REPLAY_TIMEOUT_SECONDS,
        )
        if return_code != 0:
            raise AuditError("fixed compiler configure replay failed")
        return_code, _, _ = _run_fixed_wsl(
            [
                "-d",
                "Ubuntu-24.04",
                "--exec",
                "/usr/bin/cmake",
                "--build",
                _wsl_path(build_root),
                "--config",
                configuration,
                "--parallel",
                "--target",
                *BUILD_REPLAY_TARGETS,
                "--",
                "--quiet",
            ],
            cwd=temporary_root,
            timeout_seconds=BUILD_REPLAY_TIMEOUT_SECONDS,
        )
        if return_code != 0:
            raise AuditError("fixed compiler build replay failed")
        for target in BUILD_REPLAY_TARGETS:
            executable = build_root / target
            return_code, stdout, stderr = _run_fixed_wsl(
                ["-d", "Ubuntu-24.04", "--exec", _wsl_path(executable)],
                cwd=build_root,
            )
            if return_code != 0 or stdout or stderr:
                raise AuditError("fixed compiler whole-object probe failed")
    if _wsl_compiler("gcc", toolchain_sha256) != compiler:
        raise AuditError("fixed compiler changed during build replay")
    _verify_wsl_replay_toolchain()


def _replay_compiler_build(
    contents: dict[str, bytes], request: dict[str, object]
) -> None:
    evidence_kind = str(request["execution"]["evidence_kind"])  # type: ignore[index]
    public_record = request["public_binding"]["public_record"]  # type: ignore[index]
    toolchain_sha256 = request["public_binding"].get("toolchain_sha256")  # type: ignore[index]
    _replay_compiler_build_record(contents, evidence_kind, public_record, toolchain_sha256)


def _replay_compiler_build_record(
    contents: dict[str, bytes],
    evidence_kind: str,
    public_record: object,
    toolchain_sha256: object,
) -> None:
    verified_record = _verify_compiler_record(
        evidence_kind, public_record
    )
    repository_root = _repository_root()
    _verify_build_replay_source_closure(repository_root)
    if verified_record.get("family") == "gcc":
        if os.name != "nt":
            raise AuditError("GCC replay requires the pinned Ubuntu-24.04 boundary")
        _wsl_replay_compiler_build(contents, verified_record, toolchain_sha256)
    else:
        if os.name != "nt":
            raise AuditError("Windows compiler replay requires a Windows host")
        _windows_replay_compiler_build(contents, verified_record, toolchain_sha256)


def _verify_generation(
    products: dict[str, bytes], public_record: object, request: dict[str, object]
) -> None:
    if not isinstance(public_record, dict):
        raise AuditError("generation public record is unavailable")
    contents = _generated_source_contents(products)
    _replay_generation(products, contents, request)
    _verify_generation_semantics(products, contents, public_record)
    _verify_cpu_section_inventory(
        products["cpu-section-inventory"], contents, public_record
    )
    bodies: set[bytes] = set()
    wrappers: set[bytes] = set()
    joined = bytearray()
    for path, payload in contents.items():
        if path.endswith((".c", ".cc", ".cpp", ".h", ".hpp")):
            joined.extend(payload)
    manifest = _json_loads(contents["sources.json"])
    if not isinstance(manifest, dict):
        raise AuditError("generated source manifest is invalid")
    for path in manifest["baseline_body_sources"]:
        bodies.update(BODY_RE.findall(contents[path]))
    for path in manifest["normal_wrapper_sources"]:
        wrappers.update(WRAPPER_RE.findall(contents[path]))
    symbols = public_record.get("symbols")
    stubs = public_record.get("stubs")
    if (
        not isinstance(symbols, dict)
        or not isinstance(stubs, dict)
        or len(bodies) != symbols.get("generated_count")
        or len(wrappers) != symbols.get("replaceable_function_count")
        or bodies != wrappers
        or stubs.get("generated_game_function_stub_count") != 0
    ):
        raise AuditError("generated source denominator differs from the public record")
    for marker in (
        b"jfg_generated_lookup_function",
        b"jfg_generated_section_lifecycle",
        b"jfg_generated_apply_relocations_checked",
    ):
        if marker not in joined:
            raise AuditError("generated source support product is incomplete")


def _verify_compiler(
    products: dict[str, bytes], paths: dict[str, str], request: dict[str, object]
) -> None:
    public_record = request["public_binding"]["public_record"]  # type: ignore[index]
    _require_public_result(products["compiler-result"], "compiler-result", public_record)
    contents = _generated_source_contents(products)
    _replay_compiler_build(contents, request)
    _run_product_probe(
        "smoke-executable",
        paths["smoke-executable"],
        products["smoke-executable"],
        request,
        (
            b"jfg_generated_link_smoke",
            b"jfg_generated_lookup_function",
            b"jfg_generated_section_count",
        ),
    )


def _verify_owner_inventory(
    payload: bytes,
    *,
    kind: str,
    expected_count: object,
) -> None:
    document = _canonical_json_product(payload)
    if not isinstance(document, dict) or set(document) != {
        "schema_version",
        "kind",
        "record_count",
        "records",
    }:
        raise AuditError("host owner inventory is invalid")
    records = document.get("records")
    if (
        document.get("schema_version") != 1
        or document.get("kind") != kind
        or type(expected_count) is not int
        or expected_count <= 0
        or document.get("record_count") != expected_count
        or not isinstance(records, list)
        or len(records) != expected_count
    ):
        raise AuditError("host owner inventory is invalid")
    observed: list[str] = []
    for row in records:
        if (
            not isinstance(row, dict)
            or set(row) != {"symbol_sha256", "owner_role"}
            or row.get("owner_role") != "minimal-runtime"
            or not isinstance(row.get("symbol_sha256"), str)
            or SHA256_RE.fullmatch(str(row.get("symbol_sha256"))) is None
        ):
            raise AuditError("host owner inventory row is invalid")
        observed.append(str(row["symbol_sha256"]))
    if observed != sorted(observed) or len(observed) != len(set(observed)):
        raise AuditError("host owner inventory is noncanonical")


def _verify_forced_object_semantics(
    products: dict[str, bytes],
    contents: dict[str, bytes],
    libraries: dict[str, object],
) -> None:
    manifest = _canonical_json_product(contents["sources.json"])
    symbol_inventory = _canonical_json_product(contents["symbol_inventory.json"])
    roles = _canonical_json_product(products["object-role-inventory"])
    if (
        not isinstance(manifest, dict)
        or not isinstance(symbol_inventory, dict)
        or not isinstance(roles, dict)
        or symbol_inventory.get("version") != 2
        or set(roles)
        != {
            "schema_version",
            "kind",
            "role_counts",
            "one_external_function_per_generated_object",
            "object_symbol_ownership_verified",
        }
        or roles.get("schema_version") != 1
        or roles.get("kind") != "jfg-phase4-generated-object-role-inventory"
        or roles.get("one_external_function_per_generated_object") is not True
        or roles.get("object_symbol_ownership_verified") is not True
    ):
        raise AuditError("generated object role inventory is invalid")
    counts = roles.get("role_counts")
    expected_role_keys = {
        "baseline-body",
        "normal-wrapper",
        "patch",
        "alternate-entry-thunk",
        "section-address-support",
        "lookup-support",
        "lifecycle-support",
        "relocation-support",
        "runtime-function",
        "runtime-data",
    }
    if (
        not isinstance(counts, dict)
        or set(counts) != expected_role_keys
        or any(type(counts.get(key)) is not int or counts[key] < 0 for key in counts)
        or counts["baseline-body"] <= 0
        or counts["normal-wrapper"] != counts["baseline-body"]
        or counts["runtime-function"] <= 0
        or counts["runtime-data"] <= 0
    ):
        raise AuditError("generated object role counts are invalid")

    source_groups: dict[str, list[str]] = {}
    for key in (
        "baseline_body_sources",
        "normal_wrapper_sources",
        "alternate_entry_thunk_sources",
        "table_support_sources",
    ):
        rows = manifest.get(key)
        if not isinstance(rows, list) or not all(isinstance(row, str) for row in rows):
            raise AuditError("generated object source roles are invalid")
        source_groups[key] = rows
    if (
        counts["baseline-body"] != len(source_groups["baseline_body_sources"])
        or counts["normal-wrapper"] != len(source_groups["normal_wrapper_sources"])
        or counts["alternate-entry-thunk"]
        != len(source_groups["alternate_entry_thunk_sources"])
        or len(source_groups["table_support_sources"])
        != counts["section-address-support"]
        + counts["lookup-support"]
        + counts["lifecycle-support"]
        + counts["relocation-support"]
    ):
        raise AuditError("generated object source roles do not reconcile")

    symbol_role_fields = {
        "alternate-entry-thunk": "alternate_entry_thunk_symbols",
        "section-address-support": "section_address_support_symbols",
        "lookup-support": "lookup_support_symbols",
        "lifecycle-support": "lifecycle_support_symbols",
        "relocation-support": "relocation_support_symbols",
        "runtime-function": "runtime_bridge_symbols",
        "runtime-data": "runtime_data_symbols",
    }
    if any(
        not isinstance(symbol_inventory.get(field), list)
        or len(symbol_inventory[field]) != counts[role]
        for role, field in symbol_role_fields.items()
    ):
        raise AuditError("generated object symbol roles do not reconcile")

    baseline_members = _member_inventory(products["baseline-member-inventory"])
    patch_members = _member_inventory(products["patch-member-inventory"])
    expected_source_paths = sorted(
        source_groups["baseline_body_sources"]
        + source_groups["normal_wrapper_sources"]
        + source_groups["alternate_entry_thunk_sources"]
        + source_groups["table_support_sources"]
    )
    if len(baseline_members) != len(expected_source_paths):
        raise AuditError("baseline archive role denominator differs")
    normalized_member_names = [str(row["name"]).replace("\\", "/").casefold() for row in baseline_members]
    expected_basenames = [PurePosixPath(path).name.casefold() for path in expected_source_paths]
    if len(expected_basenames) != len(set(expected_basenames)):
        raise AuditError("generated source object basenames are ambiguous")
    for basename in expected_basenames:
        suffixes = (basename + ".o", basename + ".obj")
        if sum(name.endswith(suffixes) for name in normalized_member_names) != 1:
            raise AuditError("baseline archive member role is not traceable")
    patch_anchor_count = sum(
        str(member["name"]).replace("\\", "/").casefold().endswith(
            ("patch_archive_anchor.c.o", "patch_archive_anchor.c.obj")
        )
        for member in patch_members
    )
    if patch_anchor_count != 1:
        raise AuditError("patch archive anchor is invalid")
    if len(patch_members) != counts["patch"] + 1:
        raise AuditError("patch archive role denominator differs")

    baseline = libraries.get("baseline")
    patch = libraries.get("patch")
    runtime = libraries.get("minimal_runtime")
    if not all(isinstance(value, dict) for value in (baseline, patch, runtime)):
        raise AuditError("forced-link public library roles are unavailable")
    assert isinstance(baseline, dict) and isinstance(patch, dict) and isinstance(runtime, dict)
    public_counts = (
        (counts["baseline-body"], baseline.get("unmodified_body_member_count")),
        (counts["normal-wrapper"], baseline.get("callable_wrapper_member_count")),
        (counts["alternate-entry-thunk"], baseline.get("alternate_entry_thunk_member_count")),
        (counts["section-address-support"], baseline.get("section_address_member_count")),
        (counts["lookup-support"], baseline.get("lookup_table_member_count")),
        (counts["lifecycle-support"], baseline.get("lifecycle_table_member_count")),
        (counts["relocation-support"], baseline.get("relocation_table_member_count")),
        (len(baseline_members), baseline.get("member_count")),
        (counts["runtime-function"], runtime.get("required_host_function_export_count")),
        (counts["runtime-function"], runtime.get("resolved_host_function_export_count")),
        (counts["runtime-data"], runtime.get("required_host_data_export_count")),
        (counts["runtime-data"], runtime.get("resolved_host_data_export_count")),
    )
    if any(left != right for left, right in public_counts):
        raise AuditError("generated object roles differ from public library denominators")
    expected_support = (
        counts["alternate-entry-thunk"]
        + counts["section-address-support"]
        + counts["lookup-support"]
        + counts["lifecycle-support"]
        + counts["relocation-support"]
    )
    if (
        baseline.get("support_member_count") != expected_support
        or baseline.get("other_support_member_count") != 0
        or patch.get("approved_replacement_member_count") != counts["patch"]
        or patch.get("member_count") != len(patch_members)
        or runtime.get("unresolved_host_export_count") != 0
        or runtime.get("object_symbol_ownership_verified") is not True
        or runtime.get("host_function_inventory_sha256")
        != _sha256(products["host-function-inventory"])
        or runtime.get("host_data_inventory_sha256")
        != _sha256(products["host-data-inventory"])
    ):
        raise AuditError("generated object ownership does not reconcile")
    _verify_owner_inventory(
        products["host-function-inventory"],
        kind="jfg-phase4-host-function-inventory",
        expected_count=counts["runtime-function"],
    )
    _verify_owner_inventory(
        products["host-data-inventory"],
        kind="jfg-phase4-host-data-inventory",
        expected_count=counts["runtime-data"],
    )


def _verify_forced_link(
    products: dict[str, bytes], paths: dict[str, str], request: dict[str, object]
) -> None:
    contents = _generated_source_contents(products)
    _verify_archive_pair(products, "baseline-archive", "baseline-member-inventory")
    _verify_archive_pair(products, "patch-archive", "patch-member-inventory")
    public_record = request["public_binding"]["public_record"]  # type: ignore[index]
    if not isinstance(public_record, dict):
        raise AuditError("forced-link public record is unavailable")
    libraries = public_record.get("libraries")
    compilers = public_record.get("compilers")
    if not isinstance(libraries, dict) or not isinstance(compilers, list):
        raise AuditError("forced-link library record is unavailable")
    _verify_forced_object_semantics(products, contents, libraries)
    clang_records = [
        record
        for record in compilers
        if isinstance(record, dict) and record.get("family") == "clang"
    ]
    if len(clang_records) != 1:
        raise AuditError("forced-link replay requires one authenticated Clang record")
    clang_record = clang_records[0]
    source_inventory_sha256 = clang_record.get("source_inventory_sha256")
    toolchain_sha256 = clang_record.get("compiler_executable_sha256")
    if (
        source_inventory_sha256 != _sha256(products["source-file-inventory"])
        or not isinstance(toolchain_sha256, str)
        or SHA256_RE.fullmatch(toolchain_sha256) is None
    ):
        raise AuditError("forced-link replay compiler binding is unavailable")
    _replay_compiler_build_record(
        contents, "compiler-clang", clang_record, toolchain_sha256
    )
    for product_kind, field in (
        ("baseline-result", "baseline"),
        ("patch-result", "patch"),
        ("minimal-runtime-result", "minimal_runtime"),
    ):
        _require_public_result(products[product_kind], product_kind, libraries.get(field))
    _run_product_probe(
        "forced-link-executable",
        paths["forced-link-executable"],
        products["forced-link-executable"],
        request,
        (
            b"jfg_generated_link_smoke",
            b"jfg_generated_lookup_function",
            b"jfg_generated_apply_relocations",
            b"jfg_generated_section_lifecycle",
        ),
    )


def _fixed_clang(toolchain_sha256: object) -> Path:
    if not isinstance(toolchain_sha256, str) or SHA256_RE.fullmatch(toolchain_sha256) is None:
        raise AuditError("Clang toolchain identity is unavailable")
    seen: set[str] = set()
    for candidate in _fixed_clang_candidates():
        try:
            path = candidate.resolve(strict=True)
        except OSError:
            continue
        key = str(path).casefold()
        if key in seen:
            continue
        seen.add(key)
        try:
            metadata = path.stat(follow_symlinks=False)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 128 * 1024 * 1024:
                continue
            with path.open("rb") as stream:
                payload = stream.read(128 * 1024 * 1024 + 1)
        except OSError:
            continue
        if len(payload) <= 128 * 1024 * 1024 and _sha256(payload) == toolchain_sha256:
            return path
    raise AuditError("the fixed Clang executable does not match the public toolchain")


def _verify_tool_identity(path: Path, expected_sha256: object) -> None:
    if not isinstance(expected_sha256, str) or SHA256_RE.fullmatch(expected_sha256) is None:
        raise AuditError("toolchain identity is unavailable")
    if _sha256(_read_system_executable(path)) != expected_sha256:
        raise AuditError("toolchain changed during replay")


def _analysis_sources(
    products: dict[str, bytes], public_record: object
) -> dict[str, bytes]:
    if not isinstance(public_record, dict) or set(public_record) != {
        "result",
        "source_policy_id",
        "handwritten_bridge_unit_count",
    }:
        raise AuditError("analysis source policy binding is unavailable")
    if (
        public_record.get("source_policy_id") != ANALYSIS_SOURCE_POLICY_ID
        or public_record.get("handwritten_bridge_unit_count") != ANALYSIS_BRIDGE_UNIT_COUNT
    ):
        raise AuditError("analysis source policy binding differs")
    inventory = _file_inventory(
        products["analysis-source-inventory"], "jfg-phase4-file-inventory"
    )
    actual_inventory, contents = _zip_files(products["analysis-source-archive"])
    expected_inventory = [
        {"path": path, "sha256": digest, "size": len(contents.get(path, b""))}
        for path, digest in sorted(ANALYSIS_SOURCE_SHA256.items())
    ]
    if (
        inventory != actual_inventory
        or actual_inventory != expected_inventory
        or set(contents) != set(ANALYSIS_SOURCE_SHA256)
        or any(_sha256(contents[path]) != digest for path, digest in ANALYSIS_SOURCE_SHA256.items())
        or any(
            contents.get(name) != payload
            for name, payload in {
                "analysis_minimal.cpp": b'#include "minimal_runtime.cpp"\n',
                "analysis_overlay.cpp": b'#include "generated_overlay_runtime.cpp"\n',
                "analysis_relocator.cpp": b'#include "custom_overlay_relocator.cpp"\n',
            }.items()
        )
    ):
        raise AuditError("analysis source archive differs from the tracked source policy")
    return contents


def _fixed_clang_candidates() -> tuple[Path, ...]:
    if os.name != "nt":
        return tuple(Path(path) for path in ("/usr/bin/clang++", "/usr/bin/clang", "/usr/bin/clang-cl"))
    repository_text = os.environ.get("JFG_PHASE4_REPOSITORY_ROOT")
    repository_root = (
        Path(repository_text)
        if repository_text is not None and Path(repository_text).is_absolute()
        else Path(__file__).resolve().parents[1]
    )
    roots = (
        repository_root / "tools" / "build" / "llvm-22.1.8" / "bin",
        Path("C:/Program Files/LLVM/bin"),
        Path("C:/Program Files/Microsoft Visual Studio/2022/BuildTools/VC/Tools/Llvm/x64/bin"),
        Path("C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Tools/Llvm/x64/bin"),
        Path("C:/Program Files/Microsoft Visual Studio/2022/Professional/VC/Tools/Llvm/x64/bin"),
        Path("C:/Program Files/Microsoft Visual Studio/2022/Enterprise/VC/Tools/Llvm/x64/bin"),
    )
    return tuple(root / name for root in roots for name in ("clang++.exe", "clang.exe", "clang-cl.exe"))


def _fixed_clang_cl(toolchain_sha256: object) -> Path:
    if not isinstance(toolchain_sha256, str) or SHA256_RE.fullmatch(toolchain_sha256) is None:
        raise AuditError("Clang toolchain identity is unavailable")
    for candidate in _fixed_clang_candidates():
        if candidate.name.casefold() != "clang-cl.exe":
            continue
        try:
            path = candidate.resolve(strict=True)
            payload = _read_system_executable(path)
        except (AuditError, OSError):
            continue
        if _sha256(payload) == toolchain_sha256:
            return path
    raise AuditError("the fixed clang-cl executable does not match the public toolchain")


def _verify_analyzer(products: dict[str, bytes], request: dict[str, object]) -> None:
    public_record = request["public_binding"]["public_record"]  # type: ignore[index]
    contents = _analysis_sources(products, public_record)
    assert isinstance(public_record, dict)
    _require_public_result(products["analyzer-result"], "analyzer-result", public_record["result"])
    toolchain_sha256 = request["public_binding"].get("toolchain_sha256")  # type: ignore[index]
    clang = _fixed_clang(toolchain_sha256)
    with tempfile.TemporaryDirectory(prefix="phase4-analyzer-") as temporary:
        temporary_root = Path(temporary)
        for path, payload in contents.items():
            destination = temporary_root.joinpath(*PurePosixPath(path).parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
        for unit in ("analysis_minimal.cpp", "analysis_overlay.cpp", "analysis_relocator.cpp"):
            report = temporary_root / (unit + ".plist")
            command = [
                str(clang),
                "--analyze",
                "-std=c++20",
                "-Werror",
                "-Xanalyzer",
                "-analyzer-output=plist",
                "-o",
                str(report),
                str(temporary_root / unit),
            ]
            if clang.name.casefold().startswith("clang-cl"):
                command.insert(1, "--driver-mode=g++")
            _verify_tool_identity(clang, toolchain_sha256)
            return_code, stdout, stderr = _run_bounded(command, cwd=temporary_root)
            _verify_tool_identity(clang, toolchain_sha256)
            if return_code != 0 or stdout or stderr or not report.is_file():
                raise AuditError("fixed Clang analysis failed")
            try:
                analysis = plistlib.loads(report.read_bytes())
            except (OSError, plistlib.InvalidFileException) as error:
                raise AuditError("fixed Clang analysis report is invalid") from error
            if not isinstance(analysis, dict) or analysis.get("diagnostics") not in (None, []):
                raise AuditError("fixed Clang analysis found diagnostics")


def _fixed_wsl() -> Path:
    path = Path("C:/Windows/System32/wsl.exe")
    try:
        metadata = path.stat(follow_symlinks=False)
    except OSError as error:
        raise AuditError("fixed WSL boundary is unavailable") from error
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise AuditError("fixed WSL boundary is unavailable")
    _verify_pinned_local_tool(path, WINDOWS_BUILD_TOOL_SHA256["wsl.exe"])
    return path


def _wsl_compiler(family: object, toolchain_sha256: object) -> str:
    if family not in {"clang", "gcc"} or not isinstance(
        toolchain_sha256, str
    ) or SHA256_RE.fullmatch(toolchain_sha256) is None:
        raise AuditError("fixed sanitizer compiler binding is unavailable")
    candidates = (
        ("/usr/bin/g++-13", "/usr/bin/g++")
        if family == "gcc"
        else ("/usr/bin/clang++-18", "/usr/bin/clang++")
    )
    for candidate in candidates:
        return_code, stdout, stderr = _run_fixed_wsl(
            ["-d", "Ubuntu-24.04", "--exec", "/usr/bin/sha256sum", candidate],
            cwd=Path.cwd(),
        )
        if return_code != 0 or stderr:
            continue
        fields = stdout.decode("ascii", errors="ignore").split()
        if len(fields) == 2 and fields[0] == toolchain_sha256 and fields[1] == candidate:
            return candidate
    raise AuditError("fixed sanitizer compiler does not match the public toolchain")


def _sanitizer_compile(
    temporary_root: Path,
    evidence_kind: str,
    public_result: dict[str, object],
    toolchain_sha256: object,
) -> Path:
    if os.name != "nt":
        raise AuditError("sanitizer replay requires the pinned Ubuntu-24.04 boundary")
    if public_result.get("target_id") != "linux-x64":
        raise AuditError("sanitizer target is not the pinned Linux target")
    compiler = _wsl_compiler(public_result.get("compiler_family"), toolchain_sha256)
    executable = temporary_root / "instrumented-probe"
    sanitizer = "address" if evidence_kind == "address-sanitizer" else "undefined"
    macro = "JFG_PHASE4_ASAN" if evidence_kind == "address-sanitizer" else "JFG_PHASE4_UBSAN"
    paths = {
        name: _wsl_path(temporary_root / name)
        for name in (
            "minimal_runtime.cpp",
            "generated_overlay_runtime.cpp",
            "custom_overlay_relocator.cpp",
            "sanitizer_probe.cpp",
        )
    }
    command = [
        "-d",
        "Ubuntu-24.04",
        "--exec",
        compiler,
        "-std=c++20",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-fno-omit-frame-pointer",
        "-fno-sanitize-recover=all",
        f"-fsanitize={sanitizer}",
        f"-D{macro}=1",
        "-I",
        _wsl_path(temporary_root),
        paths["minimal_runtime.cpp"],
        paths["generated_overlay_runtime.cpp"],
        paths["custom_overlay_relocator.cpp"],
        paths["sanitizer_probe.cpp"],
        "-o",
        _wsl_path(executable, must_exist=False),
    ]
    return_code, stdout, stderr = _run_fixed_wsl(command, cwd=temporary_root)
    if return_code != 0 or stdout or stderr or not executable.is_file():
        raise AuditError("fixed sanitizer compilation failed")
    payload = executable.read_bytes()
    markers = (b"__asan_init", b"__asan_report_") if evidence_kind == "address-sanitizer" else (b"__ubsan_handle_",)
    if not payload.startswith(b"\x7fELF") or not all(marker in payload for marker in markers):
        raise AuditError("fixed sanitizer compilation lacks instrumentation")
    os.chmod(executable, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    return executable


def _verify_sanitizer(products: dict[str, bytes], request: dict[str, object]) -> None:
    public_record = request["public_binding"]["public_record"]  # type: ignore[index]
    contents = _analysis_sources(products, public_record)
    assert isinstance(public_record, dict)
    public_result = public_record.get("result")
    if not isinstance(public_result, dict):
        raise AuditError("sanitizer public result is unavailable")
    _require_public_result(products["sanitizer-result"], "sanitizer-result", public_result)
    evidence_kind = str(request["execution"]["evidence_kind"])  # type: ignore[index]
    if evidence_kind == "address-sanitizer":
        diagnostic_markers = (b"AddressSanitizer", b"ERROR:")
        environment = {"ASAN_OPTIONS": "abort_on_error=1:detect_leaks=0:halt_on_error=1"}
    else:
        diagnostic_markers = (b"runtime error:",)
        environment = {"UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=1"}
    with tempfile.TemporaryDirectory(
        prefix="phase4-sanitizer-", ignore_cleanup_errors=True
    ) as temporary:
        temporary_root = Path(temporary)
        for path, payload in contents.items():
            destination = temporary_root.joinpath(*PurePosixPath(path).parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
        (temporary_root / "sanitizer_probe.cpp").write_text(
            SANITIZER_PROBE_SOURCE, encoding="utf-8", newline="\n"
        )
        executable = _sanitizer_compile(
            temporary_root,
            evidence_kind,
            public_result,
            request["public_binding"].get("toolchain_sha256"),  # type: ignore[index]
        )
        executable_digest = _sha256(executable.read_bytes())
        negative = [
            "-d",
            "Ubuntu-24.04",
            "--exec",
            _wsl_path(executable),
            "--phase4-evidence-sanitizer-negative-control",
            evidence_kind,
        ]
        return_code, stdout, stderr = _run_fixed_wsl(
            negative, cwd=temporary_root, environment=environment
        )
        if (
            return_code == 0
            or stdout
            or not stderr
            or not all(marker in stderr for marker in diagnostic_markers)
        ):
            raise AuditError("sanitizer negative control did not trigger instrumentation")
        nonce = _sha256(
            _canonical_bytes(
                {
                    "public_claim_sha256": request.get("public_claim_sha256"),
                    "evidence_kind": evidence_kind,
                    "public_record_sha256": request["execution"].get("public_record_sha256"),  # type: ignore[index]
                    "public_result_set_sha256": request["execution"].get("public_result_set_sha256"),  # type: ignore[index]
                }
            )
        )
        positive = [
            "-d",
            "Ubuntu-24.04",
            "--exec",
            _wsl_path(executable),
            "--phase4-evidence-probe",
            nonce,
            evidence_kind,
        ]
        return_code, stdout, stderr = _run_fixed_wsl(
            positive, cwd=temporary_root, environment=environment
        )
        if _sha256(executable.read_bytes()) != executable_digest:
            raise AuditError("compiled sanitizer probe changed during execution")
        expected = {
            "schema_version": 1,
            "kind": "jfg-phase4-product-probe",
            "evidence_kind": evidence_kind,
            "nonce": nonce,
            "passed": True,
        }
        if return_code != 0 or stderr or _json_loads(stdout) != expected or _canonical_bytes(expected) != stdout:
            raise AuditError("compiled sanitizer probe failed")


def _verify_reproducibility(
    products: dict[str, bytes], public_record: object, request: dict[str, object]
) -> None:
    if not isinstance(public_record, dict):
        raise AuditError("reproducibility public record is unavailable")
    payload = _canonical_json_product(products["normalized-run-payload"])
    if not isinstance(payload, dict) or payload.get("normalization_policy_id") != "phase4-run-payload-v1":
        raise AuditError("normalized run payload has the wrong policy")
    _file_inventory(products["source-file-inventory"], "jfg-phase4-file-inventory")
    _member_inventory(products["baseline-member-inventory"])
    _member_inventory(products["patch-member-inventory"])
    contents = _generated_source_contents(products)
    _replay_generation(products, contents, request)
    # Reproducibility products are the same normalized semantic closure as the
    # generation lane; rerun all cross-product checks instead of accepting
    # equal-but-fabricated JSON blobs.
    _verify_generation_semantics(products, contents, None)
    for product_kind in (
        "generated-inventory",
        "cpu-section-inventory",
        "overlay-lookup-table",
        "overlay-lifecycle-table",
        "relocation-table",
        "report-set",
    ):
        _canonical_json_product(products[product_kind])


CONFIG_CATEGORIES = (
    "symbol-addition",
    "symbol-removal",
    "symbol-rename",
    "section-movement",
    "lookup-change",
    "patch-change",
    "compiler-option-change",
)


def _config_payload(payload: bytes) -> dict[str, object]:
    document = _canonical_json_product(payload)
    if not isinstance(document, dict) or set(document) != {
        "schema_version",
        "kind",
        "symbols",
        "lookup",
        "patches",
        "compiler_options",
    }:
        raise AuditError("configuration observation payload is invalid")
    if document.get("schema_version") != 1 or document.get("kind") != "jfg-phase4-config-observation":
        raise AuditError("configuration observation payload is invalid")
    for field in ("symbols", "lookup", "patches", "compiler_options"):
        value = document.get(field)
        if not isinstance(value, dict) or not all(
            isinstance(key, str) and IDENTIFIER_RE.fullmatch(key) is not None
            for key in value
        ):
            raise AuditError("configuration observation map is invalid")
    symbols = document["symbols"]
    assert isinstance(symbols, dict)
    for value in symbols.values():
        if (
            not isinstance(value, dict)
            or set(value) != {"name_sha256", "section_sha256"}
            or any(
                not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None
                for digest in value.values()
            )
        ):
            raise AuditError("configuration symbol observation is invalid")
    for field in ("lookup", "patches", "compiler_options"):
        values = document[field]
        assert isinstance(values, dict)
        if any(
            not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None
            for digest in values.values()
        ):
            raise AuditError("configuration observation digest is invalid")
    return document


def _changed_keys(before: dict[str, object], after: dict[str, object]) -> int:
    return sum(1 for key in set(before) | set(after) if before.get(key) != after.get(key))


def _verify_config_mutation(products: dict[str, bytes], public_record: object) -> None:
    if not isinstance(public_record, dict):
        raise AuditError("configuration public record is unavailable")
    _require_public_result(
        products["config-diff-result"], "config-diff-result", public_record
    )
    expectation = _canonical_json_product(products["predeclared-expectation"])
    if (
        not isinstance(expectation, dict)
        or tuple(sorted(expectation)) != tuple(sorted(CONFIG_CATEGORIES))
        or any(type(value) is not int or value < 0 for value in expectation.values())
        or expectation != public_record.get("expected_category_counts")
    ):
        raise AuditError("predeclared configuration expectation is invalid")
    before = _config_payload(products["base-run-payload"])
    after = _config_payload(products["mutated-run-payload"])
    before_symbols = before["symbols"]
    after_symbols = after["symbols"]
    assert isinstance(before_symbols, dict)
    assert isinstance(after_symbols, dict)
    shared = set(before_symbols) & set(after_symbols)
    observed = {
        "symbol-addition": len(set(after_symbols) - set(before_symbols)),
        "symbol-removal": len(set(before_symbols) - set(after_symbols)),
        "symbol-rename": sum(
            1
            for key in shared
            if before_symbols[key]["name_sha256"] != after_symbols[key]["name_sha256"]  # type: ignore[index]
        ),
        "section-movement": sum(
            1
            for key in shared
            if before_symbols[key]["section_sha256"] != after_symbols[key]["section_sha256"]  # type: ignore[index]
        ),
        "lookup-change": _changed_keys(before["lookup"], after["lookup"]),  # type: ignore[arg-type]
        "patch-change": _changed_keys(before["patches"], after["patches"]),  # type: ignore[arg-type]
        "compiler-option-change": _changed_keys(
            before["compiler_options"], after["compiler_options"]  # type: ignore[arg-type]
        ),
    }
    if observed != expectation or observed != public_record.get("observed_category_counts"):
        raise AuditError("observed configuration diff differs from its declaration")


def _validate_request(request: object) -> tuple[dict[str, object], dict[str, bytes], dict[str, str]]:
    if not isinstance(request, dict) or set(request) != {
        "schema_version",
        "kind",
        "public_claim_sha256",
        "pins",
        "execution",
        "public_binding",
    }:
        raise AuditError("harness request is invalid")
    if request.get("schema_version") != 1 or request.get("kind") != "jfg-phase4-harness-request":
        raise AuditError("harness request is invalid")
    execution = request.get("execution")
    public_binding = request.get("public_binding")
    if not isinstance(execution, dict) or not isinstance(public_binding, dict) or set(public_binding) != {
        "public_record",
        "expected_products",
        "toolchain_sha256",
    }:
        raise AuditError("harness binding is invalid")
    evidence_kind = execution.get("evidence_kind")
    if not isinstance(evidence_kind, str) or evidence_kind not in PRODUCT_KINDS:
        raise AuditError("harness evidence kind is invalid")
    public_record = public_binding.get("public_record")
    if _sha256(_canonical_bytes(public_record)) != execution.get("public_record_sha256"):
        raise AuditError("trusted public record binding differs")
    digest_fields: list[list[str]] = []

    def collect(value: object, path: str = "$") -> None:
        if isinstance(value, dict):
            for key in sorted(value):
                child = value[key]
                child_path = f"{path}.{key}"
                if isinstance(child, str) and key.endswith("_sha256") and SHA256_RE.fullmatch(child):
                    digest_fields.append([child_path, child])
                collect(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                collect(child, f"{path}[{index}]")

    collect(public_record)
    if _sha256(_canonical_bytes(digest_fields)) != execution.get("public_result_set_sha256"):
        raise AuditError("trusted public result-set binding differs")
    expected_products = public_binding.get("expected_products")
    if (
        not isinstance(expected_products, dict)
        or not expected_products
        or any(
            not isinstance(key, str)
            or not isinstance(value, str)
            or SHA256_RE.fullmatch(value) is None
            for key, value in expected_products.items()
        )
    ):
        raise AuditError("trusted public product bindings are invalid")
    records = _artifact_records(execution)
    paths = _audit_plan(records, evidence_kind)
    products = _load_products(paths, records, expected_products)
    if evidence_kind == "generation":
        _verify_generation(products, public_record, request)
    elif evidence_kind.startswith("compiler-"):
        _verify_compiler(products, paths, request)
    elif evidence_kind == "forced-object-link-audit":
        _verify_forced_link(products, paths, request)
    elif evidence_kind == "clang-static-analysis":
        _verify_analyzer(products, request)
    elif evidence_kind in {"address-sanitizer", "undefined-behavior-sanitizer"}:
        _verify_sanitizer(products, request)
    elif evidence_kind.startswith("reproducibility-run-"):
        _verify_reproducibility(products, public_record, request)
    elif evidence_kind == "configuration-mutation":
        _verify_config_mutation(products, public_record)
    else:
        raise AuditError("unsupported evidence kind")
    return execution, products, paths


def _transcript(execution: dict[str, object], public_claim_sha256: object) -> dict[str, object]:
    return {
        "schema_version": 1,
        "kind": "jfg-phase4-harness-transcript",
        "execution_id": execution.get("id"),
        "evidence_kind": execution.get("evidence_kind"),
        "harness_id": execution.get("harness_id"),
        "harness_sha256": execution.get("harness_sha256"),
        "case_id": execution.get("case_id"),
        "public_claim_sha256": public_claim_sha256,
        "public_record_sha256": execution.get("public_record_sha256"),
        "public_result_set_sha256": execution.get("public_result_set_sha256"),
        "subject_sha256": execution.get("subject_sha256"),
        "source_input_sha256": execution.get("source_input_sha256"),
        "declaration_sha256": execution.get("declaration_sha256"),
        "pins_sha256": execution.get("pins_sha256"),
        "environment_sha256": execution.get("environment_sha256"),
        "input_set_sha256": execution.get("input_set_sha256"),
        "output_set_sha256": execution.get("output_set_sha256"),
        "artifact_set_sha256": execution.get("artifact_set_sha256"),
        "result_sha256": execution.get("result_sha256"),
        "observed_exit_code": execution.get("observed_exit_code"),
        "passed": execution.get("passed"),
        "validated": True,
    }


def main() -> int:
    try:
        payload = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        if len(payload) > MAX_REQUEST_BYTES:
            raise AuditError("harness request is oversized")
        request = _json_loads(payload)
        execution, _, _ = _validate_request(request)
        transcript = _transcript(execution, request.get("public_claim_sha256"))
        sys.stdout.buffer.write(_canonical_bytes(transcript))
        return 0
    except (
        AuditError,
        KeyError,
        OSError,
        OverflowError,
        RecursionError,
        TypeError,
        ValueError,
        subprocess.SubprocessError,
    ):
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
