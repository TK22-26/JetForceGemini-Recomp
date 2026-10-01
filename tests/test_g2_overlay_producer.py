from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRODUCER_SOURCE = ROOT / "src" / "evidence" / "g2_overlay_producer.cpp"
RUNTIME_SOURCE = ROOT / "src" / "runtime" / "generated_overlay_runtime.cpp"
CUSTOM_RELOCATOR_SOURCE = ROOT / "src" / "runtime" / "custom_overlay_relocator.cpp"
MINIMAL_RUNTIME_SOURCE = ROOT / "src" / "runtime" / "recomp_support" / "minimal_runtime.cpp"
TRAP_PROBE_SOURCE = ROOT / "src" / "evidence" / "g2_trap_probe_runtime.cpp"
FIXTURE_SOURCE = (
    ROOT / "tests" / "fixtures" / "g2-overlay-producer" / "generated_abi.cpp"
)
PREPARER = ROOT / "scripts" / "prepare_g2_overlay_case.py"
HARNESS_PATH = ROOT / "scripts" / "g2_production_evidence_harness.py"


def load_harness():
    spec = importlib.util.spec_from_file_location("g2_overlay_harness", HARNESS_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HARNESS = load_harness()
V3_SUITE_HEADER = struct.Struct("<IHHIII16s32s32s")
V3_STATIC_IMAGE = bytes.fromhex("0000000055667788")
V3_COMMITMENT_SALT = bytes(range(32))
V3_FUNCTION_PLAN_DIGEST = hashlib.sha256(b"fixture-reviewed-plan").digest()


class G2OverlayProducerTests(unittest.TestCase):
    def test_tracked_source_pin_matches_and_binary_pin_is_bound(self) -> None:
        mapping = ("overlay-lifecycle", "private-native-execution")
        self.assertEqual(
            HARNESS.PRODUCER_SOURCE_PROVENANCE[mapping]["source_sha256"],
            hashlib.sha256(PRODUCER_SOURCE.read_bytes()).hexdigest(),
        )
        # A binary pin may exist only alongside its reviewed source provenance
        # and build attestation, and the attestation must repeat the exact
        # pinned binary identity.
        binary = HARNESS.PRODUCER_BINARY_SHA256.get(mapping)
        if binary is not None:
            self.assertRegex(binary, r"^[0-9a-f]{64}$")
            self.assertGreater(len(set(binary)), 1)
            attestation = HARNESS.PRODUCER_BUILD_ATTESTATION[mapping]
            self.assertEqual(
                attestation["kind"], "jfg-g2-producer-build-attestation"
            )
            self.assertEqual(
                attestation["tracked_dependency_closure_sha256"],
                HARNESS.PRODUCER_SOURCE_PROVENANCE[mapping]["tracked_closure_sha256"],
            )
            self.assertEqual(
                attestation["reviewed_commit"],
                HARNESS.PRODUCER_SOURCE_PROVENANCE[mapping]["reviewed_commit"],
            )

    def compiler(self) -> Path:
        override = os.environ.get("JFG_TEST_CXX")
        if override:
            return Path(override)
        pinned = ROOT / "tools" / "build" / "llvm-22.1.8" / "bin" / "clang++.exe"
        if sys.platform == "win32" and pinned.is_file():
            return pinned
        located = shutil.which("clang++") or shutil.which("g++")
        if located is None:
            self.skipTest("a C++20 compiler is unavailable")
        return Path(located)

    @staticmethod
    def recipe(target: str, dependent: str) -> dict[str, object]:
        return {
            "schema_version": 1,
            "case_id": "rom-free-overlay-case",
            "guest_memory_size": 256,
            "target": {
                "module_id": 101,
                "section_index": 1,
                "guest_base": 0x80000040,
                "function_offset": 16,
                "initialized_image": target,
            },
            "dependent": {
                "module_id": 202,
                "section_index": 2,
                "guest_base": 0x80000080,
                "function_offset": 16,
                "initialized_image": dependent,
            },
            "reference_id": 303,
            "copy_check": {"offset": 16, "byte_count": 16},
            "relocation_probes": [
                {"offset": 0, "class": "full-word"},
                {"offset": 4, "class": "jump-target"},
                {"offset": 8, "class": "hi16"},
                {"offset": 12, "class": "lo16"},
            ],
        }

    def prepare(self, root: Path) -> tuple[Path, bytes]:
        target = root / "target.bin"
        dependent = root / "dependent.bin"
        target.write_bytes(bytes(range(32)))
        dependent.write_bytes(bytes(range(32)))
        recipe = root / "recipe.json"
        recipe.write_text(
            json.dumps(self.recipe(target.name, dependent.name)), encoding="utf-8"
        )
        output = root / "case-input.bin"
        result = subprocess.run(
            [
                sys.executable,
                str(PREPARER),
                "--recipe",
                str(recipe),
                "--output",
                str(output),
            ],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertEqual(result.stderr, b"")
        return output, output.read_bytes()

    @staticmethod
    def custom_v2_case() -> bytes:
        """ROM-free v2 case: static, self, and provider bindings only."""
        identifier = b"rom-free-custom-v2"
        provider = bytes(range(32))
        dependent = bytearray(40)
        struct.pack_into(">I", dependent, 4, 0x08000002)
        struct.pack_into(">I", dependent, 8, 0x3C010000)
        struct.pack_into(">I", dependent, 12, 0x34210000)
        module = lambda module_id, section, base, image: struct.pack(
            "<QIIII", module_id, section, base, 0, len(image)
        ) + bytes(image)
        records = (
            (0, 0, 2, 3, 0),      # external/self full word
            (4, 2, 4, 0, 0),      # local jump target from BE instruction
            (8, 0, 5, 2, 0),      # provider HI16
            (12, 0, 6, 2, 0),     # provider LO16
            (16, 0, 2, 3, 0),     # self full word
            (24, 3, 2, 1, 0),     # static initialized-data full word
        )
        bindings = (
            (1, 0, 0),  # static section zero
            (2, 4, 2),  # provider module
            (3, 4, 1),  # subject/self module
        )
        return b"".join(
            (
                b"JFG2OVL2",
                struct.pack("<IH", 2, len(identifier)),
                identifier,
                struct.pack("<I", 256),
                module(101, 1, 0x80000040, provider),
                module(202, 3, 0x80000080, dependent),
                struct.pack("<I", 2),
                struct.pack("<IB3x", 20, 0),
                struct.pack("<IB3x", 28, 0),
                struct.pack("<I", len(records)),
                b"".join(
                    struct.pack("<IBB2xIi", *record) for record in records
                ),
                struct.pack("<I", len(bindings)),
                b"".join(
                    struct.pack("<IIB3x", *binding) for binding in bindings
                ),
            )
        )

    @staticmethod
    def custom_v3_case(
        *,
        static_image: bytes = V3_STATIC_IMAGE,
        static_bss_size: int = 4,
    ) -> bytes:
        """ROM-free packed multi-overlay suite with all v3 coverage classes."""
        provider = bytes(range(32))
        second_provider = bytes(range(32, 64))
        dependent = bytearray(40)
        struct.pack_into(">I", dependent, 4, 0x08000002)
        struct.pack_into(">I", dependent, 8, 0x3C010000)
        struct.pack_into(">I", dependent, 16, 0x34210000)
        module = lambda token, slot, base, text, image, function, seed: struct.pack(
            "<QIIIIIIB3x", token, slot, base, text, 0, len(image), function, seed
        ) + bytes(image)
        records = (
            # All authoritative full-word records are represented by the R32
            # inventories above; the custom half contains only jump/HI/LO.
            (0, 0, 6, 3, 0),
            (4, 2, 4, 0, 0),
            # Non-adjacent sites with a rounded-high-half carry boundary.
            (8, 0, 5, 2, 0x7FFF7FBC),
            (16, 0, 6, 2, 0x7FFF7FBC),
            (12, 0, 6, 4, 0),
            (24, 3, 6, 1, 0),
        )
        bindings = (
            (1, 0, 0, 0),
            (2, 4, 2, 1),
            (3, 4, 1, 0),
            (4, 4, 2, 2),
        )
        subject = lambda slot, r32, custom, bound: b"".join(
            (
                struct.pack("<II", slot, len(r32)),
                b"".join(struct.pack("<IB3x", site, 0) for site in r32),
                struct.pack("<I", len(custom)),
                b"".join(struct.pack("<IBB2xIi", *record) for record in custom),
                struct.pack("<I", len(bound)),
                b"".join(struct.pack("<IIB3xI", *binding) for binding in bound),
            )
        )
        return b"".join(
            (
                b"JFG2OVL3",
                V3_SUITE_HEADER.pack(
                    3,
                    3,
                    3,
                    8 * 1024 * 1024,
                    len(static_image),
                    static_bss_size,
                    b"rom-free-v3-test",
                    V3_COMMITMENT_SALT,
                    V3_FUNCTION_PLAN_DIGEST,
                ),
                static_image,
                module(101, 1, 0x80000040, 32, provider, 0, 0),
                module(303, 2, 0x80000070, 32, second_provider, 16, 1),
                module(202, 3, 0x800000A0, 24, dependent, 16, 1),
                # Every populated module is a subject. This first subject is
                # deliberately R32-only, proving zero custom/binding counts
                # are accepted only with the generated-table closure.
                subject(1, (0,), (), ()),
                subject(2, (0, 4, 8, 12), (), ()),
                subject(3, (20, 28), records, bindings),
            )
        )

    @staticmethod
    def single_v3_case() -> bytes:
        """One populated overlay whose fixture BSS can exhaust 8 MiB."""
        image = bytes(range(32))
        module = struct.pack(
            "<QIIIIIIB3x",
            101,
            1,
            0x80000040,
            32,
            0,
            len(image),
            0,
            0,
        )
        subject = b"".join(
            (
                struct.pack("<II", 1, 1),
                struct.pack("<IB3x", 0, 0),
                struct.pack("<I", 0),
                struct.pack("<I", 0),
            )
        )
        return b"".join(
            (
                b"JFG2OVL3",
                V3_SUITE_HEADER.pack(
                    3,
                    1,
                    1,
                    8 * 1024 * 1024,
                    len(V3_STATIC_IMAGE),
                    4,
                    b"no-scratch-test!",
                    V3_COMMITMENT_SALT,
                    V3_FUNCTION_PLAN_DIGEST,
                ),
                V3_STATIC_IMAGE,
                module,
                image,
                subject,
            )
        )

    def build(
        self,
        root: Path,
        fixture_source: Path | None = None,
        *,
        fatal_body: bool = False,
        abort_body: bool = False,
        hang_body: bool = False,
        unsafe_first_body: bool = False,
        stack_first_body: bool = False,
        beyond_backing_body: bool = False,
        far_half_body: bool = False,
        far_end_body: bool = False,
        no_scratch: bool = False,
        arguments_body: bool = False,
        static_state_body: bool = False,
        high_static: bool = False,
        probe_budget: int | None = None,
        recomp_include: Path | None = None,
        memory_testing: bool = False,
    ) -> Path:
        executable = root / (
            "subject-probe.exe" if sys.platform == "win32" else "subject-probe"
        )
        command = [
                str(self.compiler()),
                "-std=c++20",
                "-O2",
                "-Wall",
                "-Wextra",
                "-Wpedantic",
                "-Werror",
                "-DJFG_G2_TRAP_PROBE_BRIDGES=1",
                "-I",
                str(ROOT / "include"),
                "-I",
                str(ROOT / "tests" / "fixtures" / "generated-code-synthetic" / "include"),
                str(PRODUCER_SOURCE),
                str(RUNTIME_SOURCE),
                str(CUSTOM_RELOCATOR_SOURCE),
                str(MINIMAL_RUNTIME_SOURCE),
                str(TRAP_PROBE_SOURCE),
                str(fixture_source or FIXTURE_SOURCE),
                "-o",
                str(executable),
            ]
        if recomp_include is not None:
            first_include = command.index("-I")
            command[first_include:first_include] = ["-I", str(recomp_include)]
        body_modes = sum(
            (
                fatal_body,
                abort_body,
                hang_body,
                unsafe_first_body,
                stack_first_body,
                beyond_backing_body,
                far_half_body,
                far_end_body,
                no_scratch,
                arguments_body,
                static_state_body,
            )
        )
        self.assertLessEqual(body_modes, 1)
        if fatal_body:
            command.insert(1, "-DJFG_G2_OVERLAY_FIXTURE_FATAL_BODY=1")
        elif abort_body:
            command.insert(1, "-DJFG_G2_OVERLAY_FIXTURE_ABORT_BODY=1")
        elif hang_body:
            command.insert(1, "-DJFG_G2_OVERLAY_FIXTURE_HANG_BODY=1")
        elif unsafe_first_body:
            command.insert(1, "-DJFG_G2_OVERLAY_FIXTURE_UNSAFE_FIRST_BODY=1")
        elif stack_first_body:
            command.insert(1, "-DJFG_G2_OVERLAY_FIXTURE_STACK_FIRST_BODY=1")
        elif beyond_backing_body:
            command.insert(1, "-DJFG_G2_OVERLAY_FIXTURE_BEYOND_BACKING_BODY=1")
        elif far_half_body:
            command.insert(1, "-DJFG_G2_OVERLAY_FIXTURE_FAR_HALF_BODY=1")
        elif far_end_body:
            command.insert(1, "-DJFG_G2_OVERLAY_FIXTURE_FAR_END_BODY=1")
        elif no_scratch:
            command.insert(1, "-DJFG_G2_OVERLAY_FIXTURE_NO_SCRATCH=1")
        elif arguments_body:
            command.insert(1, "-DJFG_G2_OVERLAY_FIXTURE_ARGUMENTS_BODY=1")
        elif static_state_body:
            command.insert(1, "-DJFG_G2_OVERLAY_FIXTURE_STATIC_STATE_BODY=1")
        if high_static:
            command.insert(1, "-DJFG_G2_OVERLAY_FIXTURE_HIGH_STATIC=1")
        if probe_budget is not None:
            self.assertGreater(probe_budget, 0)
            command.insert(1, "-DJFG_G2_OVERLAY_PRODUCER_TESTING=1")
            command.insert(
                1,
                f"-DJFG_G2_OVERLAY_TEST_MAX_PROBE_ATTEMPTS={probe_budget}",
            )
        if memory_testing:
            command.insert(1, "-DJFG_G2_OVERLAY_PRODUCER_TESTING=1")
        result = subprocess.run(
            command,
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        return executable

    @staticmethod
    def packed_offsets(payload: bytes) -> dict[str, int]:
        identifier_size = struct.unpack_from("<H", payload, 12)[0]
        cursor = 14 + identifier_size
        offsets = {"guest_size": cursor}
        cursor += 4
        for name in ("target", "dependent"):
            offsets[f"{name}_module_id"] = cursor
            offsets[f"{name}_section"] = cursor + 8
            offsets[f"{name}_base"] = cursor + 12
            offsets[f"{name}_function"] = cursor + 16
            offsets[f"{name}_size"] = cursor + 20
            image_size = struct.unpack_from("<I", payload, cursor + 20)[0]
            offsets[f"{name}_image"] = cursor + 24
            cursor += 24 + image_size
        offsets["reference_id"] = cursor
        offsets["copy_offset"] = cursor + 8
        offsets["copy_size"] = cursor + 12
        offsets["probe_count"] = cursor + 16
        offsets["probes"] = cursor + 20
        return offsets

    @staticmethod
    def probe_command(executable: Path, case_id: str, payload: bytes) -> list[str]:
        return [
            str(executable),
            "--g2-evidence-probe",
            "56" * 32,
            "overlay-lifecycle",
            "private-native-execution",
            "--case-id",
            case_id,
            "--subject-sha256",
            hashlib.sha256(payload).hexdigest(),
        ]

    @staticmethod
    def v3_packed_offsets(payload: bytes) -> dict[str, list[int] | int]:
        (
            _version,
            subject_count,
            module_count,
            _guest_size,
            static_size,
            _static_bss,
            _token,
            _salt,
            _function_plan_digest,
        ) = V3_SUITE_HEADER.unpack_from(payload, 8)
        cursor = 8 + V3_SUITE_HEADER.size + static_size
        module_headers: list[int] = []
        for _ in range(module_count):
            module_headers.append(cursor)
            image_size = struct.unpack_from("<I", payload, cursor + 24)[0]
            cursor += 36 + image_size
        subject_headers: list[int] = []
        r32_entries: list[int] = []
        custom_entries: list[int] = []
        binding_entries: list[int] = []
        for _ in range(subject_count):
            subject_headers.append(cursor)
            r32_count = struct.unpack_from("<I", payload, cursor + 4)[0]
            r32_entries.append(cursor + 8)
            cursor += 8 + r32_count * 8
            custom_count = struct.unpack_from("<I", payload, cursor)[0]
            custom_entries.append(cursor + 4)
            cursor += 4 + custom_count * 16
            binding_count = struct.unpack_from("<I", payload, cursor)[0]
            binding_entries.append(cursor + 4)
            cursor += 4 + binding_count * 16
        return {
            "static_image": 8 + V3_SUITE_HEADER.size,
            "module_headers": module_headers,
            "subject_headers": subject_headers,
            "r32_entries": r32_entries,
            "custom_entries": custom_entries,
            "binding_entries": binding_entries,
        }

    def test_rom_free_case_executes_runtime_and_emits_canonical_nonce_envelope(self) -> None:
        tools = ROOT / "tools"
        tools.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="g2-overlay-producer-", dir=tools) as temp:
            root = Path(temp)
            case_path, case_payload = self.prepare(root)
            executable = self.build(root)
            nonce = "12" * 32
            result = subprocess.run(
                [
                    str(executable),
                    "--g2-evidence-probe",
                    nonce,
                    "overlay-lifecycle",
                    "private-native-execution",
                    "--case-id",
                    "rom-free-overlay-case",
                    "--subject-sha256",
                    hashlib.sha256(case_payload).hexdigest(),
                ],
                cwd=case_path.parent,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            self.assertEqual(result.stderr, b"")
            envelope = json.loads(result.stdout)
            self.assertEqual(
                result.stdout,
                json.dumps(
                    envelope,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8"),
            )
            self.assertEqual(envelope["execution_nonce"], nonce)
            observation = envelope["observation"]
            execution = {
                "case_id": "rom-free-overlay-case",
                "subject_sha256": hashlib.sha256(case_payload).hexdigest(),
            }
            HARNESS.validate_overlay(observation, execution)

    def test_rom_free_v2_case_uses_table_r32_sites_and_custom_formulas(self) -> None:
        tools = ROOT / "tools"
        tools.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="g2-overlay-v2-", dir=tools) as temp:
            root = Path(temp)
            payload = self.custom_v2_case()
            (root / "case-input.bin").write_bytes(payload)
            executable = self.build(root)
            result = subprocess.run(
                self.probe_command(executable, "rom-free-custom-v2", payload),
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            envelope = json.loads(result.stdout)
            HARNESS.validate_overlay(
                envelope["observation"],
                {
                    "case_id": "rom-free-custom-v2",
                    "subject_sha256": hashlib.sha256(payload).hexdigest(),
                },
            )

    def test_rom_free_v3_suite_executes_multi_overlay_runtime_path(self) -> None:
        if not sys.platform.startswith("linux"):
            self.skipTest("generated-body invocation is deliberately Linux-only")
        tools = ROOT / "tools"
        tools.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="g2-overlay-v3-", dir=tools) as temp:
            root = Path(temp)
            payload = self.custom_v3_case()
            (root / "case-input.bin").write_bytes(payload)
            executable = self.build(root)
            case_id = "g2-custom-" + hashlib.sha256(payload).hexdigest()[:16]
            result = subprocess.run(
                self.probe_command(executable, case_id, payload),
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            envelope = json.loads(result.stdout)
            HARNESS.validate_overlay(
                envelope["observation"],
                {
                    "case_id": case_id,
                    "subject_sha256": hashlib.sha256(payload).hexdigest(),
                },
            )
            checks = {
                item["phase"]: item
                for item in envelope["observation"]["memory_checks"]
            }
            bss = checks["bss-clear"]
            self.assertEqual(
                bss["observed_sha256"],
                hashlib.sha256(bytes(bss["byte_count"])).hexdigest(),
            )
            # A state digest must describe the declared complete mapping, not
            # an arbitrary one-byte denominator.
            self.assertGreater(checks["reload"]["byte_count"], 1)
            relocations = envelope["observation"]["relocations"]
            # Six custom records plus every exact generated R32 descriptor
            # across the three populated subject overlays. The opaque IDs do
            # not expose any private site/module/address material.
            self.assertEqual(len(relocations), 13)
            self.assertEqual(
                [item["site_id"] for item in relocations],
                [f"relocation-{index}" for index in range(1, 14)],
            )
            self.assertNotIn("module_id", envelope["observation"])

    def test_linux_v3_accepts_only_the_authenticated_fatal_bridge(self) -> None:
        if not sys.platform.startswith("linux"):
            self.skipTest("generated-body invocation is deliberately Linux-only")
        tools = ROOT / "tools"
        tools.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="g2-overlay-v3-trap-", dir=tools) as temp:
            root = Path(temp)
            payload = self.custom_v3_case()
            (root / "case-input.bin").write_bytes(payload)
            executable = self.build(root, fatal_body=True)
            case_id = "g2-custom-" + hashlib.sha256(payload).hexdigest()[:16]
            result = subprocess.run(
                self.probe_command(executable, case_id, payload),
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            HARNESS.validate_overlay(
                json.loads(result.stdout)["observation"],
                {"case_id": case_id, "subject_sha256": hashlib.sha256(payload).hexdigest()},
            )
    def test_linux_v3_uses_reviewed_later_safe_function(self) -> None:
        if not sys.platform.startswith("linux"):
            self.skipTest("generated-body invocation is deliberately Linux-only")
        tools = ROOT / "tools"
        tools.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="g2-overlay-v3-safe-scan-", dir=tools
        ) as temp:
            root = Path(temp)
            payload = self.custom_v3_case()
            (root / "case-input.bin").write_bytes(payload)
            executable = self.build(root, unsafe_first_body=True)
            case_id = "g2-custom-" + hashlib.sha256(payload).hexdigest()[:16]
            result = subprocess.run(
                self.probe_command(executable, case_id, payload),
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            HARNESS.validate_overlay(
                json.loads(result.stdout)["observation"],
                {"case_id": case_id, "subject_sha256": hashlib.sha256(payload).hexdigest()},
            )

    def test_linux_v3_uses_bounded_stack_seed_for_stack_candidate(self) -> None:
        if not sys.platform.startswith("linux"):
            self.skipTest("generated-body invocation is deliberately Linux-only")
        tools = ROOT / "tools"
        tools.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="g2-overlay-v3-stack-seed-", dir=tools
        ) as temp:
            root = Path(temp)
            payload = self.custom_v3_case()
            (root / "case-input.bin").write_bytes(payload)
            executable = self.build(root, stack_first_body=True)
            case_id = "g2-custom-" + hashlib.sha256(payload).hexdigest()[:16]
            result = subprocess.run(
                self.probe_command(executable, case_id, payload),
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            HARNESS.validate_overlay(
                json.loads(result.stdout)["observation"],
                {"case_id": case_id, "subject_sha256": hashlib.sha256(payload).hexdigest()},
            )
            for _ in range(4):
                repeated = subprocess.run(
                    self.probe_command(executable, case_id, payload),
                    cwd=root,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                    timeout=30,
                )
                self.assertEqual(repeated.returncode, 0)
                self.assertEqual(repeated.stdout, result.stdout)
                self.assertEqual(repeated.stderr, b"")

    def test_linux_v3_uses_bounded_argument_seed_for_reviewed_leaf(self) -> None:
        if not sys.platform.startswith("linux"):
            self.skipTest("generated-body invocation is deliberately Linux-only")
        tools = ROOT / "tools"
        tools.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="g2-overlay-v3-argument-seed-", dir=tools
        ) as temp:
            root = Path(temp)
            payload = bytearray(self.custom_v3_case())
            module_headers = self.v3_packed_offsets(payload)["module_headers"]
            assert isinstance(module_headers, list)
            second_module = module_headers[1]
            third_module = module_headers[2]
            payload[second_module + 32] = 3
            payload[third_module + 32] = 3
            packed = bytes(payload)
            (root / "case-input.bin").write_bytes(packed)
            executable = self.build(root, arguments_body=True)
            case_id = "g2-custom-" + hashlib.sha256(packed).hexdigest()[:16]
            result = subprocess.run(
                self.probe_command(executable, case_id, packed),
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            HARNESS.validate_overlay(
                json.loads(result.stdout)["observation"],
                {"case_id": case_id, "subject_sha256": hashlib.sha256(packed).hexdigest()},
            )

    def test_linux_v3_supplies_exact_static_initialized_data_and_zero_bss(self) -> None:
        if not sys.platform.startswith("linux"):
            self.skipTest("generated-body invocation is deliberately Linux-only")
        tools = ROOT / "tools"
        tools.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="g2-overlay-v3-static-state-", dir=tools
        ) as temp:
            root = Path(temp)
            payload = self.custom_v3_case()
            (root / "case-input.bin").write_bytes(payload)
            executable = self.build(root, static_state_body=True)
            case_id = "g2-custom-" + hashlib.sha256(payload).hexdigest()[:16]
            result = subprocess.run(
                self.probe_command(executable, case_id, payload),
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            public = result.stdout.decode("utf-8")
            self.assertNotIn(V3_COMMITMENT_SALT.hex(), public)
            self.assertNotIn('"function_offset"', public)
            self.assertNotIn('"context_seed"', public)

            changed = bytearray(payload)
            static_image = self.v3_packed_offsets(payload)["static_image"]
            assert isinstance(static_image, int)
            changed[static_image + 4] ^= 0x01
            tampered = bytes(changed)
            (root / "case-input.bin").write_bytes(tampered)
            rejected = subprocess.run(
                self.probe_command(
                    executable,
                    "g2-custom-" + hashlib.sha256(tampered).hexdigest()[:16],
                    tampered,
                ),
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertEqual(rejected.stdout, b"")
            self.assertEqual(rejected.stderr, b"")

    def test_linux_v3_scratch_excludes_high_static_extent(self) -> None:
        if not sys.platform.startswith("linux"):
            self.skipTest("generated-body invocation is deliberately Linux-only")
        tools = ROOT / "tools"
        tools.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="g2-overlay-v3-high-static-", dir=tools
        ) as temp:
            root = Path(temp)
            payload = self.custom_v3_case(static_bss_size=0xFFF8)
            (root / "case-input.bin").write_bytes(payload)
            executable = self.build(root, stack_first_body=True, high_static=True)
            case_id = "g2-custom-" + hashlib.sha256(payload).hexdigest()[:16]
            result = subprocess.run(
                self.probe_command(executable, case_id, payload),
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))

    def test_linux_v3_probe_budget_is_shared_across_subjects(self) -> None:
        if not sys.platform.startswith("linux"):
            self.skipTest("generated-body invocation is deliberately Linux-only")
        tools = ROOT / "tools"
        tools.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="g2-overlay-v3-shared-budget-", dir=tools
        ) as temp:
            root = Path(temp)
            payload = self.custom_v3_case()
            (root / "case-input.bin").write_bytes(payload)
            executable = self.build(root, probe_budget=2)
            case_id = "g2-custom-" + hashlib.sha256(payload).hexdigest()[:16]
            result = subprocess.run(
                self.probe_command(executable, case_id, payload),
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, b"")
            self.assertEqual(result.stderr, b"")

    def test_linux_v3_rejects_unbound_reviewed_body_identity_and_seed(self) -> None:
        if not sys.platform.startswith("linux"):
            self.skipTest("generated-body invocation is deliberately Linux-only")
        tools = ROOT / "tools"
        tools.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="g2-overlay-v3-reviewed-body-", dir=tools
        ) as temp:
            root = Path(temp)
            payload = self.custom_v3_case()
            executable = self.build(root)
            module_headers = self.v3_packed_offsets(payload)["module_headers"]
            assert isinstance(module_headers, list)
            first_module = module_headers[0]
            candidates: dict[str, bytes] = {}
            changed = bytearray(payload)
            struct.pack_into("<I", changed, first_module + 28, 4)
            candidates["function-not-in-generated-table"] = bytes(changed)
            changed = bytearray(payload)
            changed[first_module + 32] = 5
            candidates["invalid-context-seed"] = bytes(changed)
            for label, candidate in candidates.items():
                with self.subTest(label=label):
                    (root / "case-input.bin").write_bytes(candidate)
                    case_id = "g2-custom-" + hashlib.sha256(candidate).hexdigest()[:16]
                    result = subprocess.run(
                        self.probe_command(executable, case_id, candidate),
                        cwd=root,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=False,
                        timeout=30,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, b"")
                    self.assertEqual(result.stderr, b"")

    def test_linux_v3_rejects_unauthenticated_abort_and_timeout(self) -> None:
        if not sys.platform.startswith("linux"):
            self.skipTest("generated-body invocation is deliberately Linux-only")
        tools = ROOT / "tools"
        tools.mkdir(exist_ok=True)
        for label, mode in (("abort", "abort_body"), ("timeout", "hang_body")):
            with self.subTest(label=label), tempfile.TemporaryDirectory(
                prefix=f"g2-overlay-v3-{label}-", dir=tools
            ) as temp:
                root = Path(temp)
                payload = self.custom_v3_case()
                (root / "case-input.bin").write_bytes(payload)
                executable = self.build(root, **{mode: True})
                case_id = "g2-custom-" + hashlib.sha256(payload).hexdigest()[:16]
                result = subprocess.run(
                    self.probe_command(executable, case_id, payload),
                    cwd=root,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                    timeout=30,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")
                self.assertEqual(result.stderr, b"")

    def test_linux_v3_rejects_exhausted_scratch_and_access_beyond_rdram(self) -> None:
        if not sys.platform.startswith("linux"):
            self.skipTest("generated-body invocation is deliberately Linux-only")
        tools = ROOT / "tools"
        tools.mkdir(exist_ok=True)
        cases = (
            ("no-scratch", self.single_v3_case(), {"no_scratch": True}),
            (
                "beyond-rdram",
                self.custom_v3_case(),
                {"beyond_backing_body": True},
            ),
            (
                "far-half-address-space",
                self.custom_v3_case(),
                {"far_half_body": True},
            ),
            (
                "far-end-address-space",
                self.custom_v3_case(),
                {"far_end_body": True},
            ),
        )
        for label, payload, mode in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory(
                prefix=f"g2-overlay-v3-{label}-", dir=tools
            ) as temp:
                root = Path(temp)
                (root / "case-input.bin").write_bytes(payload)
                executable = self.build(root, **mode)
                case_id = "g2-custom-" + hashlib.sha256(payload).hexdigest()[:16]
                result = subprocess.run(
                    self.probe_command(executable, case_id, payload),
                    cwd=root,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                    timeout=30,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, b"")
                self.assertEqual(result.stderr, b"")

    def test_v3_full_address_space_reservation_rejects_near_and_far_oob(self) -> None:
        tools = ROOT / "tools"
        tools.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="g2-overlay-v3-reservation-", dir=tools
        ) as temp:
            root = Path(temp)
            executable = self.build(root, memory_testing=True)
            inside = subprocess.run(
                [str(executable), "--g2-v3-reservation-test", "inside"],
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
            self.assertEqual(inside.returncode, 0, inside.stderr.decode(errors="replace"))
            self.assertEqual(inside.stdout, b"")
            self.assertEqual(inside.stderr, b"")
            for location in ("one-past", "far-half", "far-end"):
                with self.subTest(location=location):
                    result = subprocess.run(
                        [
                            str(executable),
                            "--g2-v3-reservation-test",
                            location,
                        ],
                        cwd=root,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=False,
                        timeout=30,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, b"")
                    self.assertEqual(result.stderr, b"")

    def test_v3_parser_rejects_reserved_geometry_and_binding_mutations(self) -> None:
        tools = ROOT / "tools"
        tools.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="g2-overlay-v3-reject-", dir=tools) as temp:
            root = Path(temp)
            payload = self.custom_v3_case()
            executable = self.build(root)
            case_id = "g2-custom-" + hashlib.sha256(payload).hexdigest()[:16]
            offsets = self.v3_packed_offsets(payload)
            module_headers = offsets["module_headers"]
            subject_headers = offsets["subject_headers"]
            r32_entries = offsets["r32_entries"]
            custom_entries = offsets["custom_entries"]
            binding_entries = offsets["binding_entries"]
            assert all(
                isinstance(value, list)
                for value in (
                    module_headers,
                    subject_headers,
                    r32_entries,
                    custom_entries,
                    binding_entries,
                )
            )
            first_module = module_headers[0]
            third_module = module_headers[2]
            r32 = r32_entries[2]
            records = custom_entries[2]
            bindings = binding_entries[2]
            malformed: dict[str, bytes] = {}
            changed = bytearray(payload)
            changed[first_module + 20] = 1
            malformed["module-reserved"] = bytes(changed)
            changed = bytearray(payload)
            struct.pack_into("<I", changed, third_module + 16, 20)
            malformed["text-metadata-mismatch"] = bytes(changed)
            changed = bytearray(payload)
            changed[r32 + 4] = 1
            malformed["r32-reserved"] = bytes(changed)
            changed = bytearray(payload)
            struct.pack_into("<I", changed, bindings + 12, 3)
            malformed["provider-slot-missing"] = bytes(changed)
            changed = bytearray(payload)
            changed[records + 6] = 1
            malformed["custom-reserved"] = bytes(changed)
            changed = bytearray(payload)
            struct.pack_into("<H", changed, 12, 2)
            malformed["all-populated-modules-must-be-subjects"] = bytes(changed)
            changed = bytearray(payload)
            struct.pack_into("<I", changed, records, 20)
            malformed["custom-r32-site-overlap"] = bytes(changed)
            changed = bytearray(payload)
            struct.pack_into("<I", changed, 16, 8 * 1024 * 1024 + 1)
            malformed["geometry-exceeds-rdram"] = bytes(changed)
            changed = bytearray(payload)
            struct.pack_into("<I", changed, first_module + 12, 0x80000004)
            malformed["overlay-overlaps-static"] = bytes(changed)
            changed = bytearray(payload)
            struct.pack_into("<I", changed, 20, 4)
            malformed["static-image-size-mismatch"] = bytes(changed)
            changed = bytearray(payload)
            struct.pack_into("<I", changed, 24, 8)
            malformed["static-bss-metadata-mismatch"] = bytes(changed)
            changed = bytearray(payload)
            struct.pack_into("<I", changed, 24, 0)
            malformed["static-bss-missing"] = bytes(changed)
            changed = bytearray(payload)
            changed[44:76] = bytes(32)
            malformed["missing-private-commitment-salt"] = bytes(changed)
            changed = bytearray(payload)
            changed[76:108] = bytes(32)
            malformed["missing-reviewed-plan-digest"] = bytes(changed)
            for label, candidate in malformed.items():
                with self.subTest(label=label):
                    (root / "case-input.bin").write_bytes(candidate)
                    result = subprocess.run(
                        self.probe_command(executable, case_id, candidate),
                        cwd=root,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=False,
                        timeout=30,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, b"")
                    self.assertEqual(result.stderr, b"")

    def test_v3_rejects_generated_r32_descriptor_mutation(self) -> None:
        tools = ROOT / "tools"
        tools.mkdir(exist_ok=True)
        original = FIXTURE_SOURCE.read_text(encoding="utf-8")
        mutated = original.replace("{20U, 1U, 16U}", "{20U, 1U, 20U}")
        self.assertNotEqual(mutated, original)
        with tempfile.TemporaryDirectory(prefix="g2-overlay-v3-r32-", dir=tools) as temp:
            root = Path(temp)
            payload = self.custom_v3_case()
            (root / "case-input.bin").write_bytes(payload)
            fixture = root / "generated_abi_mutated.cpp"
            fixture.write_text(mutated, encoding="utf-8", newline="\n")
            executable = self.build(root, fixture)
            case_id = "g2-custom-" + hashlib.sha256(payload).hexdigest()[:16]
            result = subprocess.run(
                self.probe_command(executable, case_id, payload),
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, b"")
            self.assertEqual(result.stderr, b"")

    def test_v2_parser_rejects_reserved_raw_address_and_r32_tampering(self) -> None:
        tools = ROOT / "tools"
        tools.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="g2-overlay-v2-reject-", dir=tools) as temp:
            root = Path(temp)
            payload = self.custom_v2_case()
            case_path = root / "case-input.bin"
            executable = self.build(root)
            identifier_length = struct.unpack_from("<H", payload, 12)[0]
            cursor = 14 + identifier_length + 4
            for _ in range(2):
                size = struct.unpack_from("<I", payload, cursor + 20)[0]
                cursor += 24 + size
            r32 = cursor
            r32_count = struct.unpack_from("<I", payload, r32)[0]
            custom_count = r32 + 4 + r32_count * 8
            records = custom_count + 4
            binding_count = records + 6 * 16
            bindings = binding_count + 4
            malformed: dict[str, bytes] = {}
            changed = bytearray(payload)
            changed[r32 + 4] = 1  # reserved R32 byte / no caller labels
            malformed["r32-reserved"] = bytes(changed)
            changed = bytearray(payload)
            struct.pack_into("<I", changed, r32, 16)  # table says 20
            malformed["r32-table-mismatch"] = bytes(changed)
            changed = bytearray(payload)
            changed[records + 6] = 1  # custom record reserved bytes
            malformed["record-reserved"] = bytes(changed)
            changed = bytearray(payload)
            struct.pack_into("<I", changed, records + 8, 0x80000000)
            malformed["raw-address-not-binding"] = bytes(changed)
            changed = bytearray(payload)
            changed[bindings + 8] = 9  # binding ABI enum, not an address kind
            malformed["binding-kind"] = bytes(changed)
            for name, malformed_payload in malformed.items():
                with self.subTest(name=name):
                    case_path.write_bytes(malformed_payload)
                    result = subprocess.run(
                        self.probe_command(
                            executable, "rom-free-custom-v2", malformed_payload
                        ),
                        cwd=root,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=False,
                        timeout=30,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, b"")
                    self.assertEqual(result.stderr, b"")

    def test_public_fixture_exports_a_closed_relocation_site_abi(self) -> None:
        fixture = FIXTURE_SOURCE.read_text(encoding="utf-8")
        producer = PRODUCER_SOURCE.read_text(encoding="utf-8")
        self.assertIn("int jfg_generated_relocation_sites(", fixture)
        self.assertIn("int jfg_generated_relocation_descriptors(", fixture)
        self.assertIn("JfgGeneratedR32Descriptor", fixture)
        self.assertIn("*output = nullptr;", fixture)
        self.assertIn("bool relocation_sites(", producer)
        self.assertIn("bool relocation_descriptors(", producer)
        self.assertIn("validate_generated_r32_formulas", producer)
        self.assertIn("count != jfg_generated_relocation_count(source_section)", producer)

    def test_v3_context_layout_drift_fails_at_compile_time(self) -> None:
        tools = ROOT / "tools"
        tools.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix="g2-overlay-v3-context-layout-", dir=tools
        ) as temp:
            root = Path(temp)
            include = root / "include"
            include.mkdir()
            original = (
                ROOT
                / "tests"
                / "fixtures"
                / "generated-code-synthetic"
                / "include"
                / "recomp.h"
            ).read_text(encoding="utf-8")
            mutated = original.replace("r2,  r3,  r4", "r2,  r3,  padding, r4")
            self.assertNotEqual(mutated, original)
            (include / "recomp.h").write_text(mutated, encoding="utf-8", newline="\n")
            output = root / "producer.o"
            result = subprocess.run(
                [
                    str(self.compiler()),
                    "-std=c++20",
                    "-DJFG_G2_TRAP_PROBE_BRIDGES=1",
                    "-I",
                    str(include),
                    "-I",
                    str(ROOT / "include"),
                    "-c",
                    str(PRODUCER_SOURCE),
                    "-o",
                    str(output),
                ],
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=120,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(output.exists())

    def test_v2_rejects_generated_descriptor_target_duplicate_order_and_count_mutations(self) -> None:
        tools = ROOT / "tools"
        tools.mkdir(exist_ok=True)
        original = FIXTURE_SOURCE.read_text(encoding="utf-8")
        mutations = {
            "target": original.replace("{20U, 1U, 16U}", "{20U, 1U, 20U}"),
            "duplicate": original.replace(
                "{20U, 1U, 16U},\n        {28U, 1U, 20U}",
                "{20U, 1U, 16U},\n        {20U, 1U, 20U}",
            ),
            "order": original.replace(
                "{20U, 1U, 16U},\n        {28U, 1U, 20U}",
                "{28U, 1U, 20U},\n        {20U, 1U, 16U}",
            ),
            "count": original.replace(
                "return section == 1U ? 1U : (section == 2U ? 4U : (section == 3U ? 2U : 0U));",
                "return section == 1U ? 1U : (section == 2U ? 4U : 0U);",
            ),
        }
        self.assertTrue(all(value != original for value in mutations.values()))
        with tempfile.TemporaryDirectory(prefix="g2-overlay-r32-descriptor-", dir=tools) as temp:
            root = Path(temp)
            payload = self.custom_v2_case()
            (root / "case-input.bin").write_bytes(payload)
            for label, content in mutations.items():
                with self.subTest(label=label):
                    fixture = root / f"generated_abi_{label}.cpp"
                    fixture.write_text(content, encoding="utf-8", newline="\n")
                    executable = self.build(root, fixture)
                    result = subprocess.run(
                        self.probe_command(executable, "rom-free-custom-v2", payload),
                        cwd=root,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=False,
                        timeout=30,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, b"")
                    self.assertEqual(result.stderr, b"")

    def test_producer_cross_checks_case_identity_and_subject(self) -> None:
        tools = ROOT / "tools"
        tools.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="g2-overlay-identity-", dir=tools) as temp:
            root = Path(temp)
            case_path, case_payload = self.prepare(root)
            executable = self.build(root)
            command = [
                str(executable),
                "--g2-evidence-probe",
                "34" * 32,
                "overlay-lifecycle",
                "private-native-execution",
                "--case-id",
                "rom-free-overlay-case",
                "--subject-sha256",
                hashlib.sha256(case_payload).hexdigest(),
            ]
            result = subprocess.run(
                command,
                cwd=case_path.parent,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            self.assertEqual(
                json.loads(result.stdout)["observation"]["case_id"],
                "rom-free-overlay-case",
            )
            command[6] = "different-harness-case"
            rejected_case = subprocess.run(
                command,
                cwd=case_path.parent,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
            self.assertNotEqual(rejected_case.returncode, 0)
            command[6] = "rom-free-overlay-case"
            command[-1] = "00" * 32
            rejected = subprocess.run(
                command,
                cwd=case_path.parent,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
            self.assertNotEqual(rejected.returncode, 0)

    def test_crafted_packed_cases_bypass_preparer_and_fail_at_parser(self) -> None:
        tools = ROOT / "tools"
        tools.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="g2-overlay-packed-reject-", dir=tools) as temp:
            root = Path(temp)
            case_path, valid_payload = self.prepare(root)
            executable = self.build(root)
            offsets = self.packed_offsets(valid_payload)

            def changed(field: str, value: int, encoding: str = "<I") -> bytes:
                payload = bytearray(valid_payload)
                struct.pack_into(encoding, payload, offsets[field], value)
                return bytes(payload)

            probes = offsets["probes"]
            malformed: dict[str, bytes] = {
                "uncached-base": changed("target_base", 0x7FFFFFFC),
                "unaligned-base": changed("target_base", 0x80000041),
                "section-out-of-range": changed("target_section", 65_500),
                "unaligned-function": changed("target_function", 2),
                "function-outside-image": changed("target_function", 32),
                "unaligned-image-size": changed("target_size", 31),
                "initialized-range-outside-guest": changed("target_base", 0x800000F0),
                "overlapping-initialized-ranges": changed("dependent_base", 0x80000050),
                "zero-copy": changed("copy_size", 0),
                "copy-outside-image": changed("copy_offset", 24),
            }

            for name, probe_index, relative, value, encoding in (
                ("unaligned-probe", 0, 0, 1, "<I"),
                ("probe-outside-image", 0, 0, 32, "<I"),
                ("probe-overlaps-copy", 0, 0, 16, "<I"),
                ("duplicate-probe", 1, 0, 0, "<I"),
                ("missing-relocation-class", 3, 4, 2, "<B"),
            ):
                payload = bytearray(valid_payload)
                struct.pack_into(encoding, payload, probes + probe_index * 8 + relative, value)
                malformed[name] = bytes(payload)

            for name, payload in malformed.items():
                with self.subTest(name=name):
                    case_path.write_bytes(payload)
                    result = subprocess.run(
                        self.probe_command(executable, "trusted-packed-case", payload),
                        cwd=case_path.parent,
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=False,
                        timeout=30,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, b"")
                    self.assertEqual(result.stderr, b"")

    def test_recipe_cannot_embed_an_observation_or_overwrite_a_case(self) -> None:
        tools = ROOT / "tools"
        tools.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="g2-overlay-reject-", dir=tools) as temp:
            root = Path(temp)
            target = root / "target.bin"
            dependent = root / "dependent.bin"
            target.write_bytes(bytes(range(32)))
            dependent.write_bytes(bytes(range(32)))
            document = self.recipe(target.name, dependent.name)
            document["observation"] = {"passed": True}
            recipe = root / "recipe.json"
            recipe.write_text(json.dumps(document), encoding="utf-8")
            output = root / "case-input.bin"
            command = [
                sys.executable,
                str(PREPARER),
                "--recipe",
                str(recipe),
                "--output",
                str(output),
            ]
            rejected = subprocess.run(
                command,
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertFalse(output.exists())

            document.pop("observation")
            recipe.write_text(json.dumps(document), encoding="utf-8")
            accepted = subprocess.run(
                command,
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
            self.assertEqual(accepted.returncode, 0)
            original = output.read_bytes()
            repeated = subprocess.run(
                command,
                cwd=ROOT,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=30,
            )
            self.assertNotEqual(repeated.returncode, 0)
            self.assertEqual(output.read_bytes(), original)

    def run_preparer(
        self,
        root: Path,
        document: dict[str, object],
        output_name: str,
    ) -> subprocess.CompletedProcess[bytes]:
        (root / "target.bin").write_bytes(bytes(range(32)))
        (root / "dependent.bin").write_bytes(bytes(range(32)))
        recipe = root / "recipe.json"
        recipe.write_text(json.dumps(document), encoding="utf-8")
        return subprocess.run(
            [
                sys.executable,
                str(PREPARER),
                "--recipe",
                str(recipe),
                "--output",
                str(root / output_name),
            ],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )

    def test_preparer_rejects_invalid_module_and_probe_geometry(self) -> None:
        tools = ROOT / "tools"
        tools.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="g2-overlay-geometry-", dir=tools) as temp:
            root = Path(temp)
            documents: list[tuple[str, dict[str, object]]] = []
            for field in ("module_id", "section_index", "guest_base"):
                document = self.recipe("target.bin", "dependent.bin")
                document["dependent"][field] = document["target"][field]
                documents.append((f"duplicate-{field}", document))

            document = self.recipe("target.bin", "dependent.bin")
            document["target"]["guest_base"] = 0x80000041
            documents.append(("unaligned-base", document))
            document = self.recipe("target.bin", "dependent.bin")
            document["dependent"]["function_offset"] = 17
            documents.append(("unaligned-function", document))
            document = self.recipe("target.bin", "dependent.bin")
            document["target"]["guest_base"] = 0x7FFFFFFC
            documents.append(("uncached-base", document))
            document = self.recipe("target.bin", "dependent.bin")
            document["guest_memory_size"] = 159
            documents.append(("guest-overrun", document))
            document = self.recipe("target.bin", "dependent.bin")
            document["target"]["guest_base"] = 0x80000070
            documents.append(("module-overlap", document))
            document = self.recipe("target.bin", "dependent.bin")
            document["copy_check"] = {"offset": 20, "byte_count": 16}
            documents.append(("copy-overrun", document))
            for label, offset in (
                ("unaligned-probe", 2),
                ("probe-overrun", 32),
                ("probe-copy-overlap", 16),
            ):
                document = self.recipe("target.bin", "dependent.bin")
                document["relocation_probes"][0]["offset"] = offset
                documents.append((label, document))

            for index, (label, document) in enumerate(documents):
                with self.subTest(label=label):
                    output = root / f"rejected-{index}.bin"
                    result = self.run_preparer(root, document, output.name)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(output.exists())

    def test_preparer_is_byte_deterministic(self) -> None:
        tools = ROOT / "tools"
        tools.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="g2-overlay-determinism-", dir=tools) as temp:
            root = Path(temp)
            document = self.recipe("target.bin", "dependent.bin")
            first = self.run_preparer(root, document, "case-a.bin")
            second = self.run_preparer(root, document, "case-b.bin")
            self.assertEqual(first.returncode, 0, first.stderr.decode(errors="replace"))
            self.assertEqual(second.returncode, 0, second.stderr.decode(errors="replace"))
            self.assertEqual((root / "case-a.bin").read_bytes(), (root / "case-b.bin").read_bytes())


if __name__ == "__main__":
    unittest.main()
