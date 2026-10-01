from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "src" / "evidence"
RUNTIME = ROOT / "src" / "runtime"
FIXTURES = ROOT / "tests" / "fixtures" / "g2-paired-producers"
HARNESS_PATH = ROOT / "scripts" / "g2_production_evidence_harness.py"
NONCE = "12" * 32
CASE_ID = "rom-free-paired-case"


def load_harness():
    spec = importlib.util.spec_from_file_location("g2_production_evidence_harness_paired", HARNESS_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PRODUCTION = load_harness()


class G2PairedProducerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pinned = ROOT / "tools" / "build" / "llvm-22.1.8" / "bin" / "clang++.exe"
        located = pinned if pinned.is_file() else shutil.which("clang++") or shutil.which("g++")
        if located is None:
            raise unittest.SkipTest("a C++20 compiler is unavailable")
        cls.compiler = Path(located)
        (ROOT / "tools").mkdir(exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(prefix="g2-paired-producers-", dir=ROOT / "tools")
        cls.build_root = Path(cls.temporary.name)
        cls.executables: dict[tuple[str, str], Path] = {}
        definitions = {
            ("graphics", "native"): [SOURCES / "g2_graphics_native_producer.cpp", SOURCES / "g2_graphics_bounded_adapter.cpp", RUNTIME / "graphics_task_bridge.cpp", RUNTIME / "bounded_custom_graphics.cpp"],
            ("graphics", "oracle"): [SOURCES / "g2_graphics_oracle_producer.cpp", RUNTIME / "graphics_task_bridge.cpp", RUNTIME / "bounded_custom_graphics.cpp", FIXTURES / "private_graphics_test_adapter.cpp"],
            ("audio", "native"): [SOURCES / "g2_audio_native_producer.cpp", RUNTIME / "audio_task_bridge.cpp", FIXTURES / "private_audio_test_adapter.cpp"],
            ("audio", "oracle"): [SOURCES / "g2_audio_oracle_producer.cpp", FIXTURES / "private_audio_test_adapter.cpp"],
            ("save", "native"): [SOURCES / "g2_save_native_producer.cpp", RUNTIME / "save_device_runtime.cpp", RUNTIME / "controller_pak.cpp"],
            ("save", "oracle"): [SOURCES / "g2_save_oracle_producer.cpp"],
        }
        for key, sources in definitions.items():
            output = cls.build_root / ("-".join(key) + (".exe" if sys.platform == "win32" else ""))
            result = subprocess.run(
                [str(cls.compiler), "-std=c++20", "-O2", "-Wall", "-Wextra", "-Wpedantic", "-Werror", "-I", str(ROOT / "include"), *map(str, sources), "-o", str(output)],
                cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=120,
            )
            if result.returncode != 0:
                raise AssertionError(result.stderr.decode(errors="replace"))
            cls.executables[key] = output

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    @staticmethod
    def case_bytes(family: int, payload: bytes) -> bytes:
        if family == 3:
            return b"JFG2PRD1" + struct.pack("<III", 1, family, len(payload)) + payload

        def blob(value: bytes) -> bytes:
            return struct.pack("<I", len(value)) + value

        if family == 1:
            if len(payload) != 4:
                raise ValueError("graphics test payload must be one command word")
            descriptor = bytearray(64)
            descriptor[16:20] = (0x80).to_bytes(4, "big")
            descriptor[48:52] = (0x100).to_bytes(4, "big")
            command = b"\xb8\x00\x00\x00" + payload
            memory = bytearray(0x108)
            memory[0x80:0x84] = b"\x01\x02\x03\x04"
            memory[0x100:0x108] = command
            body = b"".join(
                blob(value)
                for value in (
                    bytes(descriptor),
                    b"\x01\x02\x03\x04",
                    b"\x05\x06\x07\x08",
                    command,
                    bytes(memory),
                )
            )
        elif family == 2:
            if not payload or len(payload) % 4:
                raise ValueError("audio test output must be frame aligned")
            body = b"".join(
                (
                    struct.pack("<II", 0x200, len(payload)),
                    blob(bytes(64)),
                    blob(b"\x11\x12\x13\x14"),
                    blob(b"\x21\x22\x23\x24"),
                    blob(b"\x31\x32\x33\x34\x35\x36\x37\x38"),
                    blob(payload),
                )
            )
        else:
            raise ValueError("unknown paired family")
        return b"JFG2PRD1" + struct.pack("<III", 3, family, len(body)) + body

    def run_probe(self, key: tuple[str, str], case: bytes, *, case_id: str = CASE_ID, digest: str | None = None, extra: tuple[str, ...] = ()) -> subprocess.CompletedProcess[bytes]:
        family, flavor = key
        requirement = "save-round-trip" if family == "save" else f"{family}-tasks"
        evidence_class = f"private-{flavor}-execution"
        case_dir = self.build_root / ("case-" + "-".join(key))
        case_dir.mkdir(exist_ok=True)
        (case_dir / "case-input.bin").write_bytes(case)
        return subprocess.run(
            [str(self.executables[key]), "--g2-evidence-probe", NONCE, requirement, evidence_class, "--case-id", case_id, "--subject-sha256", digest or hashlib.sha256(case).hexdigest(), *extra],
            cwd=case_dir, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=10,
        )

    def assert_canonical(self, result: subprocess.CompletedProcess[bytes]) -> dict[str, object]:
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertEqual(result.stderr, b"")
        document = json.loads(result.stdout)
        self.assertEqual(result.stdout, json.dumps(document, sort_keys=True, separators=(",", ":")).encode())
        self.assertEqual(document["execution_nonce"], NONCE)
        return document["observation"]

    @staticmethod
    def execution(case: bytes) -> dict[str, object]:
        return {"case_id": CASE_ID, "subject_sha256": hashlib.sha256(case).hexdigest()}

    def assert_rejected(self, validator, *args, **kwargs) -> None:
        with self.assertRaises(PRODUCTION.HarnessReject):
            validator(*args, **kwargs)

    def test_graphics_native_and_independent_oracle_match_exact_output(self) -> None:
        payload = bytes.fromhex((FIXTURES / "graphics-payload.hex").read_text().strip())
        case = self.case_bytes(1, payload)
        native = self.assert_canonical(self.run_probe(("graphics", "native"), case))
        oracle = self.assert_canonical(self.run_probe(("graphics", "oracle"), case))
        expected = bytearray(32); expected[0] = 3; expected[1] = 0xB8; expected[3] = 1; expected[24] = 0xB8; expected[28:32] = payload
        digest = hashlib.sha256(expected).hexdigest()
        self.assertEqual(native["output_sha256"], digest)
        self.assertEqual(native["renderer_path"], "project-bounded-semantic")
        self.assertEqual(oracle["payload_sha256"], digest)
        self.assertEqual(native["output_byte_count"], oracle["payload_byte_count"])
        native_root = self.build_root / "case-graphics-native"
        oracle_root = self.build_root / "case-graphics-oracle"
        self.assertEqual((native_root / "graphics-output.bin").read_bytes(), expected)
        self.assertEqual((oracle_root / "graphics-output-a.bin").read_bytes(), expected)
        self.assertEqual((oracle_root / "graphics-output-b.bin").read_bytes(), expected)
        native_artifacts = {"graphics-output.bin": expected}
        oracle_artifacts = {"graphics-output-a.bin": expected, "graphics-output-b.bin": expected}
        self.assertEqual(native_artifacts, {"graphics-output.bin": (native_root / "graphics-output.bin").read_bytes()})
        self.assertEqual(oracle_artifacts, {name: (oracle_root / name).read_bytes() for name in oracle_artifacts})
        execution = self.execution(case)
        PRODUCTION.validate_graphics_native(native, execution, [({"path": name}, value) for name, value in native_artifacts.items()])
        PRODUCTION.validate_exact_oracle(oracle, execution, [({"path": name}, value) for name, value in oracle_artifacts.items()], kind="jfg-g2-graphics-oracle-observation", maximum=64 * 1024 * 1024, alignment=32, schema_version=2, require_program_evidence=True)
        altered = dict(native); altered["output_sha256"] = "00" * 32
        self.assert_rejected(PRODUCTION.validate_graphics_native, altered, execution, [({"path": name}, value) for name, value in native_artifacts.items()])
        mislabeled = dict(native); mislabeled["renderer_path"] = "rt64"
        self.assert_rejected(PRODUCTION.validate_graphics_native, mislabeled, execution, [({"path": name}, value) for name, value in native_artifacts.items()])
        self.assert_rejected(PRODUCTION.validate_exact_oracle, oracle, execution, [({"path": name}, value[:-1] + b"x") for name, value in oracle_artifacts.items()], kind="jfg-g2-graphics-oracle-observation", maximum=64 * 1024 * 1024, alignment=32, schema_version=2, require_program_evidence=True)

    def test_audio_native_and_independent_oracle_match_exact_output(self) -> None:
        payload = bytes.fromhex((FIXTURES / "audio-payload.hex").read_text().strip())
        case = self.case_bytes(2, payload)
        native = self.assert_canonical(self.run_probe(("audio", "native"), case))
        oracle = self.assert_canonical(self.run_probe(("audio", "oracle"), case))
        digest = hashlib.sha256(payload).hexdigest()
        self.assertEqual(native["output_sha256"], digest)
        self.assertEqual(oracle["payload_sha256"], digest)
        self.assertEqual(native["secondary_fallback"]["completion_count"], 0)
        native_root = self.build_root / "case-audio-native"
        oracle_root = self.build_root / "case-audio-oracle"
        self.assertEqual((native_root / "audio-output.bin").read_bytes(), payload)
        self.assertEqual((oracle_root / "audio-output-a.bin").read_bytes(), payload)
        self.assertEqual((oracle_root / "audio-output-b.bin").read_bytes(), payload)
        native_artifacts = {"audio-output.bin": payload}
        oracle_artifacts = {"audio-output-a.bin": payload, "audio-output-b.bin": payload}
        self.assertEqual(native_artifacts, {"audio-output.bin": (native_root / "audio-output.bin").read_bytes()})
        self.assertEqual(oracle_artifacts, {name: (oracle_root / name).read_bytes() for name in oracle_artifacts})
        execution = self.execution(case)
        PRODUCTION.validate_audio_native(native, execution, [({"path": name}, value) for name, value in native_artifacts.items()])
        PRODUCTION.validate_exact_oracle(oracle, execution, [({"path": name}, value) for name, value in oracle_artifacts.items()], kind="jfg-g2-audio-oracle-observation", maximum=1024 * 1024, alignment=4, schema_version=2, require_program_evidence=True)
        altered = dict(native); altered["frame_alignment_bytes"] = 3
        self.assert_rejected(PRODUCTION.validate_audio_native, altered, execution, [({"path": name}, value) for name, value in native_artifacts.items()])
        self.assert_rejected(PRODUCTION.validate_exact_oracle, oracle, execution, [({"path": name}, value[:-1] + b"x") for name, value in oracle_artifacts.items()], kind="jfg-g2-audio-oracle-observation", maximum=1024 * 1024, alignment=4, schema_version=2, require_program_evidence=True)

    def test_native_audio_cannot_link_without_the_private_adapter_abi(self) -> None:
        output = self.build_root / ("audio-native-unbound.exe" if sys.platform == "win32" else "audio-native-unbound")
        result = subprocess.run(
            [
                str(self.compiler),
                "-std=c++20",
                "-O2",
                "-I",
                str(ROOT / "include"),
                str(SOURCES / "g2_audio_native_producer.cpp"),
                str(RUNTIME / "audio_task_bridge.cpp"),
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

    def test_graphics_native_links_without_private_adapter_abi(self) -> None:
        output = self.build_root / "graphics-native-project-adapter"
        result = subprocess.run(
            [
                str(self.compiler), "-std=c++20", "-O2", "-I",
                str(ROOT / "include"),
                str(SOURCES / "g2_graphics_native_producer.cpp"),
                str(SOURCES / "g2_graphics_bounded_adapter.cpp"),
                str(RUNTIME / "graphics_task_bridge.cpp"),
                str(RUNTIME / "bounded_custom_graphics.cpp"),
                "-o", str(output),
            ],
            cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, check=False, timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))

    def test_graphics_oracle_cannot_link_without_private_adapter_abi(self) -> None:
        output = self.build_root / "graphics-oracle-unbound"
        result = subprocess.run(
            [
                str(self.compiler), "-std=c++20", "-O2", "-I",
                str(ROOT / "include"),
                str(SOURCES / "g2_graphics_oracle_producer.cpp"),
                "-o", str(output),
            ],
            cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, check=False, timeout=120,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_oracle_audio_cannot_link_without_private_adapter_abi(self) -> None:
        output = self.build_root / "audio-oracle-unbound"
        result = subprocess.run(
            [
                str(self.compiler),
                "-std=c++20",
                "-O2",
                "-I",
                str(ROOT / "include"),
                str(SOURCES / "g2_audio_oracle_producer.cpp"),
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

    def test_active_program_substitution_is_rejected_by_both_closures(self) -> None:
        for family, name, payload in (
            (1, "graphics", bytes.fromhex("10203040")),
            (2, "audio", bytes.fromhex("0011223344556677")),
        ):
            case = bytearray(self.case_bytes(family, payload))
            program_offset = 20 + (8 if family == 2 else 0) + 4 + 64 + 4
            case[program_offset] ^= 0x80
            for flavor in ("native", "oracle"):
                with self.subTest(family=name, flavor=flavor):
                    self.assertNotEqual(
                        self.run_probe((name, flavor), bytes(case)).returncode,
                        0,
                    )

    def test_identity_and_argument_injection_are_rejected(self) -> None:
        case = self.case_bytes(1, bytes.fromhex("10203040"))
        self.assertNotEqual(self.run_probe(("graphics", "native"), case, digest="01" * 32).returncode, 0)
        self.assertNotEqual(self.run_probe(("graphics", "native"), case, case_id='bad"id').returncode, 0)
        self.assertNotEqual(self.run_probe(("graphics", "native"), case, extra=("unexpected",)).returncode, 0)

    def test_save_native_runtime_and_independent_oracle_match_trace(self) -> None:
        payload = bytes.fromhex((FIXTURES / "save-payload.hex").read_text().strip())
        case = self.case_bytes(3, payload)
        native = self.assert_canonical(self.run_probe(("save", "native"), case))
        native_case = self.build_root / "case-save-native"
        self.assertGreater((native_case / "controller-pak-written.bin").stat().st_size, 0)
        self.assertEqual((native_case / "flashram-written.bin").stat().st_size, 128 * 1024)
        self.assertEqual(native["controller_pak_image_sha256"], hashlib.sha256((native_case / "controller-pak-written.bin").read_bytes()).hexdigest())
        self.assertEqual(native["flashram_image_sha256"], hashlib.sha256((native_case / "flashram-written.bin").read_bytes()).hexdigest())
        oracle = self.assert_canonical(self.run_probe(("save", "oracle"), case))
        oracle_case = self.build_root / "case-save-oracle"
        trace = (oracle_case / "semantic-trace-a.json").read_bytes()
        self.assertEqual(trace, (oracle_case / "semantic-trace-b.json").read_bytes())
        self.assertEqual(oracle["semantic_trace_sha256"], hashlib.sha256(trace).hexdigest())
        self.assertEqual(json.loads(trace), native["semantic_trace"])
        state_paths = [
            "controller-pak-initial.bin", "controller-pak-written.bin",
            "controller-pak-reloaded.bin", "controller-pak-restored.bin",
            "flashram-initial.bin", "flashram-written.bin",
            "flashram-reloaded.bin", "flashram-restored.bin",
        ]
        native_artifacts = {name: (native_case / name).read_bytes() for name in state_paths}
        oracle_artifacts = {
            "semantic-trace-a.json": trace,
            "semantic-trace-b.json": (oracle_case / "semantic-trace-b.json").read_bytes(),
            **{name: (oracle_case / name).read_bytes() for name in state_paths},
        }
        self.assertEqual(oracle_artifacts["semantic-trace-a.json"], oracle_artifacts["semantic-trace-b.json"])
        execution = self.execution(case)
        PRODUCTION.validate_save_native(native, execution, [({"path": name}, value) for name, value in native_artifacts.items()])
        PRODUCTION.validate_save_oracle(oracle, execution, [({"path": name}, value) for name, value in oracle_artifacts.items()])
        altered = dict(native); altered["flashram_image_sha256"] = "00" * 32
        self.assert_rejected(PRODUCTION.validate_save_native, altered, execution, [({"path": name}, value) for name, value in native_artifacts.items()])
        for name, value in native_artifacts.items():
            with self.subTest(native_artifact=name):
                altered_artifacts = dict(native_artifacts); altered_artifacts[name] = value[:-1] + b"x"
                self.assert_rejected(PRODUCTION.validate_save_native, native, execution, [({"path": path}, data) for path, data in altered_artifacts.items()])
        for name, value in oracle_artifacts.items():
            with self.subTest(oracle_artifact=name):
                altered_artifacts = dict(oracle_artifacts); altered_artifacts[name] = value[:-1] + b"x"
                self.assert_rejected(PRODUCTION.validate_save_oracle, oracle, execution, [({"path": path}, data) for path, data in altered_artifacts.items()])

    def test_malformed_truncated_oversized_and_noncanonical_cases_are_rejected(self) -> None:
        valid = self.case_bytes(2, bytes.fromhex("0011223344556677"))
        cases = [b"", valid[:-1], valid + b"x", b"BADMAGIC" + valid[8:], self.case_bytes(1, bytes.fromhex("10203040")), b"JFG2PRD1" + struct.pack("<III", 3, 2, 24 * 1024 * 1024 + 1)]
        for case in cases:
            with self.subTest(size=len(case)):
                self.assertNotEqual(self.run_probe(("audio", "oracle"), case).returncode, 0)

    def test_case_mutation_changes_observation_and_misaligned_oracle_is_rejected(self) -> None:
        first = self.case_bytes(2, bytes.fromhex("0011223344556677"))
        second = self.case_bytes(2, bytes.fromhex("0011223344556678"))
        left = self.assert_canonical(self.run_probe(("audio", "oracle"), first))
        right = self.assert_canonical(self.run_probe(("audio", "oracle"), second))
        self.assertNotEqual(left["payload_sha256"], right["payload_sha256"])
        with self.assertRaises(ValueError):
            self.case_bytes(2, b'{"output_sha256":"' + b"0" * 64 + b'"}x')


if __name__ == "__main__":
    unittest.main()
