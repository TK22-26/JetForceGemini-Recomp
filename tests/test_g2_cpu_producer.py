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
SOURCE = ROOT / "src" / "evidence" / "g2_cpu_producer.cpp"
FIXTURE = ROOT / "tests" / "fixtures" / "g2-cpu-producer" / "public-case.json"
HARNESS_PATH = ROOT / "scripts" / "g2_production_evidence_harness.py"


def harness():
    spec = importlib.util.spec_from_file_location("g2_cpu_harness", HARNESS_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HARNESS = harness()


class G2CpuProducerTests(unittest.TestCase):
    def compiler(self) -> Path:
        pinned = ROOT / "tools" / "build" / "llvm-22.1.8" / "bin" / "clang++.exe"
        if pinned.is_file():
            return pinned
        found = shutil.which("clang++") or shutil.which("g++")
        if not found:
            self.skipTest("C++20 compiler unavailable")
        return Path(found)

    def build(self, directory: Path) -> Path:
        executable = directory / ("cpu-probe.exe" if sys.platform == "win32" else "cpu-probe")
        result = subprocess.run(
            [str(self.compiler()), "-std=c++20", "-O2", "-Wall", "-Wextra", "-Wpedantic", "-Werror", "-I", str(ROOT / "include"), str(SOURCE), "-o", str(executable)],
            cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        return executable

    def case(self) -> bytes:
        document = json.loads(FIXTURE.read_text(encoding="utf-8"))
        body = [
            b"JFGCPU02",
            struct.pack(
                "<HH",
                document["schema_version"],
                len(document["compiler_products"]),
            ),
        ]
        for compiler_product in document["compiler_products"]:
            identifier = compiler_product["compiler_id"].encode("ascii")
            body.extend((
                bytes([len(identifier)]),
                identifier,
                bytes.fromhex(compiler_product["compiler_executable_sha256"]),
            ))
        body.append(bytes.fromhex(document["g3_product_binding_sha256"]))
        body.append(struct.pack("<H", len(document["sections"])))
        for section in document["sections"]:
            identifier = section["section_id"].encode("ascii")
            body.extend((
                bytes([len(identifier)]),
                identifier,
                bytes([section["kind"]]),
                struct.pack(
                    "<8I",
                    section["expected"],
                    section["attempted"],
                    section["generated"],
                    section["excluded"],
                    section["failures"],
                    section["lookups"],
                    section["lifecycle"],
                    section["relocations"],
                ),
            ))
        body.append(struct.pack("<H", len(document["overlay_slots"])))
        for slot in document["overlay_slots"]:
            identifier = slot["slot_id"].encode("ascii")
            body.extend((bytes([len(identifier)]), identifier, bytes([slot["disposition"]])))
            if slot["disposition"] == 0:
                section_identifier = slot["section_id"].encode("ascii")
                body.extend((bytes([len(section_identifier)]), section_identifier))
        body.append(struct.pack("<9I", *document["link_audit"]))
        body.append(struct.pack("<H", len(document["tools"])))
        for tool in document["tools"]:
            body.append(struct.pack(
                "<BII",
                tool["tool_id"],
                tool["exit_code"],
                tool["finding_count"],
            ))
        return b"".join(body)

    @staticmethod
    def command(executable: Path, payload: bytes, *, nonce: str = "34" * 32, compiler_id: str = "clang-test", compiler_sha256: str = bytes(range(1, 33)).hex()) -> list[str]:
        return [str(executable), "--g2-evidence-probe", nonce, "cpu-sections", "private-g3-compiler-product-binding", "--case-id", "rom-free-cpu-case", "--subject-sha256", hashlib.sha256(payload).hexdigest(), "--compiler-id", compiler_id, "--compiler-executable-sha256", compiler_sha256]

    def execute(self, executable: Path, directory: Path, payload: bytes, command: list[str] | None = None) -> subprocess.CompletedProcess[bytes]:
        (directory / "case-input.bin").write_bytes(payload)
        return subprocess.run(command or self.command(executable, payload), cwd=directory, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False)

    def validate(self, envelope: dict[str, object], payload: bytes) -> None:
        observation = envelope["observation"]
        assert isinstance(observation, dict)
        execution = {
            "case_id": "rom-free-cpu-case",
            "subject_sha256": hashlib.sha256(payload).hexdigest(),
        }
        config = {
            "g3_compiler_id": "clang-test",
            "g3_compiler_executable_sha256": bytes(range(1, 33)).hex(),
        }
        HARNESS.validate_cpu(observation, execution, config)

    def test_public_records_compile_execute_and_validate(self) -> None:
        with tempfile.TemporaryDirectory(prefix="g2-cpu-producer-", dir=ROOT / "tools") as temporary:
            directory = Path(temporary); executable = self.build(directory); payload = self.case()
            result = self.execute(executable, directory, payload)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace")); self.assertEqual(result.stderr, b"")
            envelope = json.loads(result.stdout)
            self.assertEqual(result.stdout, json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode())
            self.assertEqual(envelope["execution_nonce"], "34" * 32)
            self.assertEqual(
                envelope["observation"]["g3_product_binding_sha256"],
                "7172737475767778797a7b7c7d7e7f808182838485868788898a8b8c8d8e8f90",
            )
            self.validate(envelope, payload)
            # A ROM-free test build can never impersonate the pinned producer.
            pinned = HARNESS.PRODUCER_BINARY_SHA256.get(("cpu-sections", "private-g3-compiler-product-binding"))
            self.assertNotEqual(pinned, hashlib.sha256(executable.read_bytes()).hexdigest())

    def test_one_case_selects_each_of_three_bound_compiler_products(self) -> None:
        with tempfile.TemporaryDirectory(prefix="g2-cpu-matrix-", dir=ROOT / "tools") as temporary:
            directory = Path(temporary); executable = self.build(directory); payload = self.case()
            document = json.loads(FIXTURE.read_text(encoding="utf-8"))
            observations = []
            for compiler_product in document["compiler_products"]:
                result = self.execute(executable, directory, payload, self.command(executable, payload, compiler_id=compiler_product["compiler_id"], compiler_sha256=compiler_product["compiler_executable_sha256"]))
                self.assertEqual(result.returncode, 0, result.stderr.decode())
                observations.append(json.loads(result.stdout)["observation"])
            self.assertEqual({item["compiler_id"] for item in observations}, {item["compiler_id"] for item in document["compiler_products"]})

    def test_identity_digest_and_noncanonical_records_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="g2-cpu-ident-", dir=ROOT / "tools") as temporary:
            directory = Path(temporary); executable = self.build(directory); payload = self.case()
            command = self.command(executable, payload); command[-1] = "00" * 32
            self.assertNotEqual(self.execute(executable, directory, payload, command).returncode, 0)
            command = self.command(executable, payload); command[3] = "overlay-lifecycle"
            self.assertNotEqual(self.execute(executable, directory, payload, command).returncode, 0)

    def test_duplicate_compiler_product_missing_classification_and_malformed_cases_fail(self) -> None:
        with tempfile.TemporaryDirectory(prefix="g2-cpu-reject-", dir=ROOT / "tools") as temporary:
            directory = Path(temporary); executable = self.build(directory); valid = self.case()
            duplicate_compiler_product = bytearray(valid); duplicate_compiler_product[10:12] = struct.pack("<H", 2)
            missing_tool = bytearray(valid); missing_tool[-18] = 1
            for label, payload in {"truncated": valid[:-1], "duplicate-compiler-product": bytes(duplicate_compiler_product), "duplicate-tool": bytes(missing_tool)}.items():
                with self.subTest(label=label):
                    result = self.execute(executable, directory, payload)
                    self.assertNotEqual(result.returncode, 0); self.assertEqual(result.stdout, b"")

    def test_observation_is_derived_not_fixture_hardcoded(self) -> None:
        with tempfile.TemporaryDirectory(prefix="g2-cpu-derived-", dir=ROOT / "tools") as temporary:
            directory = Path(temporary); executable = self.build(directory); first = self.case()
            changed = bytearray(first); changed[23] ^= 0x80  # first toolchain digest only
            first_envelope = json.loads(self.execute(executable, directory, first).stdout)
            changed_command = self.command(executable, bytes(changed), compiler_sha256=(bytes([0x81]) + bytes(range(2, 33))).hex())
            changed_envelope = json.loads(self.execute(executable, directory, bytes(changed), changed_command).stdout)
            self.assertNotEqual(first_envelope["observation"]["compiler_executable_sha256"], changed_envelope["observation"]["compiler_executable_sha256"])
            self.assertNotEqual(first_envelope["observation"]["subject_sha256"], changed_envelope["observation"]["subject_sha256"])

    def test_case_has_no_expected_status_or_completion_fields(self) -> None:
        payload = self.case()
        for forbidden in (b"expected", b"passed", b"status", b"observation", b"completion"):
            self.assertNotIn(forbidden, payload)


if __name__ == "__main__":
    unittest.main()
