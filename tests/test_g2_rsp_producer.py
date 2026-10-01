from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "evidence" / "g2_rsp_producer.cpp"
FIXTURE = ROOT / "tests" / "fixtures" / "g2-rsp-producer" / "public-case.hex"
HARNESS_PATH = ROOT / "scripts" / "g2_production_evidence_harness.py"


def harness():
    spec = importlib.util.spec_from_file_location("g2_rsp_harness", HARNESS_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HARNESS = harness()


class G2RspProducerTests(unittest.TestCase):
    def compiler(self) -> Path:
        pinned = ROOT / "tools" / "build" / "llvm-22.1.8" / "bin" / "clang++.exe"
        if pinned.is_file():
            return pinned
        found = shutil.which("clang++") or shutil.which("g++")
        if not found:
            self.skipTest("C++20 compiler unavailable")
        return Path(found)

    def build(self, directory: Path) -> Path:
        executable = directory / ("rsp-probe.exe" if sys.platform == "win32" else "rsp-probe")
        result = subprocess.run([str(self.compiler()), "-std=c++20", "-O2", "-Wall", "-Wextra", "-Wpedantic", "-Werror", "-I", str(ROOT / "include"), str(SOURCE), "-o", str(executable)], cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120, check=False)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        return executable

    def case(self) -> bytes:
        return bytes.fromhex(FIXTURE.read_text(encoding="ascii").strip())

    @staticmethod
    def command(executable: Path, payload: bytes, *, nonce: str = "12" * 32) -> list[str]:
        return [str(executable), "--g2-evidence-probe", nonce, "rsp-programs", "private-native-execution", "--case-id", "rom-free-rsp-case", "--subject-sha256", hashlib.sha256(payload).hexdigest()]

    def execute(self, executable: Path, directory: Path, payload: bytes, command: list[str] | None = None) -> subprocess.CompletedProcess[bytes]:
        (directory / "case-input.bin").write_bytes(payload)
        return subprocess.run(command or self.command(executable, payload), cwd=directory, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False)

    def test_public_inventory_compiles_executes_and_validates_observation_schema(self) -> None:
        with tempfile.TemporaryDirectory(prefix="g2-rsp-producer-", dir=ROOT / "tools") as temporary:
            directory = Path(temporary); executable = self.build(directory); payload = self.case(); result = self.execute(executable, directory, payload)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace")); self.assertEqual(result.stderr, b"")
            envelope = json.loads(result.stdout)
            self.assertEqual(result.stdout, json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode())
            self.assertEqual(envelope["execution_nonce"], "12" * 32)
            execution = {"case_id": "rom-free-rsp-case", "subject_sha256": hashlib.sha256(payload).hexdigest()}
            HARNESS.validate_rsp(envelope["observation"], execution)
            programs = {item["family"]: item for item in envelope["observation"]["programs"]}
            probes = {item["program_id"]: item for item in envelope["observation"]["native_probes"]}
            slots = {item["program_id"]: item for item in envelope["observation"]["overlay_slots"]}
            self.assertEqual(programs["other"]["generated_entry_count"], 0)
            other = programs["other"]["program_id"]
            self.assertEqual(probes[other]["entry_count"], 0)
            self.assertEqual(probes[other]["broker_access_count"], 0)
            self.assertEqual(slots[other]["classification"], "empty")
            # A ROM-free test build can never impersonate the pinned producer.
            pinned = HARNESS.PRODUCER_BINARY_SHA256.get(("rsp-programs", "private-native-execution"))
            self.assertNotEqual(pinned, hashlib.sha256(executable.read_bytes()).hexdigest())

    def test_rsp_cross_record_family_bindings_reject_mutations(self) -> None:
        with tempfile.TemporaryDirectory(prefix="g2-rsp-bindings-", dir=ROOT / "tools") as temporary:
            directory = Path(temporary); executable = self.build(directory); payload = self.case()
            envelope = json.loads(self.execute(executable, directory, payload).stdout)
            observation = envelope["observation"]
            execution = {"case_id": "rom-free-rsp-case", "subject_sha256": hashlib.sha256(payload).hexdigest()}
            families = {item["family"]: item["program_id"] for item in observation["programs"]}
            for family, program_id in families.items():
                with self.subTest(family=family, field="slot-owner"):
                    altered = json.loads(json.dumps(observation))
                    next(item for item in altered["overlay_slots"] if item["program_id"] == program_id)["owner_id"] = "rsp-audio-primary" if family != "audio-primary" else "rsp-graphics"
                    with self.assertRaises(HARNESS.HarnessReject): HARNESS.validate_rsp(altered, execution)
                with self.subTest(family=family, field="probe"):
                    altered = json.loads(json.dumps(observation))
                    next(item for item in altered["native_probes"] if item["program_id"] == program_id)["probe_kind"] = "graphics-native"
                    with self.assertRaises(HARNESS.HarnessReject): HARNESS.validate_rsp(altered, execution)
                with self.subTest(family=family, field="evidence"):
                    altered = json.loads(json.dumps(observation))
                    next(item for item in altered["overlay_slots"] if item["program_id"] == program_id)["evidence_sha256"] = "01" * 32
                    with self.assertRaises(HARNESS.HarnessReject): HARNESS.validate_rsp(altered, execution)

    def test_identity_and_case_digest_are_required(self) -> None:
        with tempfile.TemporaryDirectory(prefix="g2-rsp-identity-", dir=ROOT / "tools") as temporary:
            directory=Path(temporary); executable=self.build(directory); payload=self.case(); command=self.command(executable,payload); command[-1]="00"*32
            rejected=self.execute(executable,directory,payload,command); self.assertNotEqual(rejected.returncode,0); self.assertEqual(rejected.stdout,b"")
            command=self.command(executable,payload); command[3]="overlay-lifecycle"
            rejected=self.execute(executable,directory,payload,command); self.assertNotEqual(rejected.returncode,0)

    def test_malformed_duplicate_and_coverage_gaps_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="g2-rsp-reject-", dir=ROOT / "tools") as temporary:
            directory=Path(temporary); executable=self.build(directory); valid=self.case()
            coverage_gap = bytearray(valid)
            audio_id = coverage_gap.index(b"audio-primary")
            coverage_gap[audio_id + len(b"audio-primary")] = 0
            cases = {"truncated":valid[:-1], "coverage-gap":bytes(coverage_gap), "duplicate": valid[:12] + valid[12:21] + valid[12:21] + valid[21:]}
            for label,payload in cases.items():
                with self.subTest(label=label):
                    result=self.execute(executable,directory,payload); self.assertNotEqual(result.returncode,0); self.assertEqual(result.stdout,b"")

    def test_case_has_no_expected_status_or_observation_fields(self) -> None:
        payload=self.case(); self.assertNotIn(b"passed",payload); self.assertNotIn(b"observation",payload); self.assertNotIn(b"expected",payload)

    def test_manifest_commitment_substitution_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="g2-rsp-manifest-", dir=ROOT / "tools") as temporary:
            directory = Path(temporary)
            executable = self.build(directory)
            payload = bytearray(self.case())
            payload[-1] ^= 1
            result = self.execute(executable, directory, bytes(payload))
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, b"")


if __name__ == "__main__":
    unittest.main()
