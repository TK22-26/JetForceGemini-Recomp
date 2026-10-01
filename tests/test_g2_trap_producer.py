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
SOURCE = ROOT / "src" / "evidence" / "g2_trap_producer.cpp"
ORACLE_SOURCE = ROOT / "src" / "evidence" / "g2_trap_oracle_producer.cpp"
PROBE_RUNTIME = ROOT / "src" / "evidence" / "g2_trap_probe_runtime.cpp"
HARNESS_PATH = ROOT / "scripts" / "g2_production_evidence_harness.py"
NONCE = "34" * 32
CASE_ID = "rom-free-trap-case"
spec = importlib.util.spec_from_file_location("g2_harness", HARNESS_PATH)
assert spec and spec.loader
HARNESS = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = HARNESS
spec.loader.exec_module(HARNESS)


class G2TrapProducerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pinned = ROOT / "tools" / "build" / "llvm-22.1.8" / "bin" / "clang++.exe"
        compiler = (
            pinned if sys.platform == "win32" and pinned.is_file()
            else shutil.which("clang++") or shutil.which("g++")
        )
        if compiler is None:
            raise unittest.SkipTest("a C++20 compiler is unavailable")
        cls.temporary = tempfile.TemporaryDirectory(prefix="g2-trap-producer-", dir=ROOT / "tools")
        cls.root = Path(cls.temporary.name)
        cls.executable = cls.root / ("producer.exe" if sys.platform == "win32" else "producer")
        cls.oracle = cls.root / ("oracle.exe" if sys.platform == "win32" else "oracle")
        command = [str(compiler), "-std=c++20", "-O2", "-Wall", "-Wextra", "-Wpedantic", "-Werror", "-I", str(ROOT / "include"), str(SOURCE)]
        if sys.platform.startswith("linux"):
            command.append(str(PROBE_RUNTIME))
        command += ["-o", str(cls.executable)]
        built = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=120)
        if built.returncode:
            raise AssertionError(built.stderr.decode(errors="replace"))
        oracle = subprocess.run(
            [str(compiler), "-std=c++20", "-O2", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
             "-I", str(ROOT / "include"), str(ORACLE_SOURCE), "-o", str(cls.oracle)],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=120,
        )
        if oracle.returncode:
            raise AssertionError(oracle.stderr.decode(errors="replace"))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    @staticmethod
    def case(events: list[tuple[int, int, int, int, int, int]], decisions: list[tuple[int, int, int, int]]) -> bytes:
        encoded = []
        for row in events:
            raw = struct.pack("<IIIIII", *row)
            encoded.append(raw + hashlib.sha256(b"behavior" + raw).digest() + hashlib.sha256(b"provenance" + raw).digest())
        return b"JFG2TRP1" + struct.pack("<III", 2, len(events), len(decisions)) + b"".join(encoded) + b"".join(struct.pack("<IIII", *row) for row in decisions)

    @staticmethod
    def valid_case() -> bytes:
        return G2TrapProducerTests.case([(kind, kind, 1, kind, 10 + kind, 20 + kind) for kind in range(1, 8)], [(kind, (kind - 1) % 3 + 1, 1, 1) for kind in range(1, 8)])

    def probe(self, payload: bytes, *, oracle: bool = False, digest: str | None = None, case_id: str = CASE_ID, extra: tuple[str, ...] = ()) -> subprocess.CompletedProcess[bytes]:
        work = self.root / "case"; work.mkdir(exist_ok=True); (work / "case-input.bin").write_bytes(payload)
        return subprocess.run([str(self.oracle if oracle else self.executable), "--g2-evidence-probe", NONCE, "runtime-traps", "private-oracle-execution" if oracle else "private-native-execution", "--case-id", case_id, "--subject-sha256", digest or hashlib.sha256(payload).hexdigest(), *extra], cwd=work, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=10)

    def observation(self, payload: bytes) -> dict[str, object]:
        if not sys.platform.startswith("linux"):
            self.skipTest("native trap evidence is fail-closed outside Linux")
        result = self.probe(payload); self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace")); self.assertEqual(result.stderr, b"")
        document = json.loads(result.stdout); self.assertEqual(result.stdout, json.dumps(document, sort_keys=True, separators=(",", ":")).encode()); self.assertEqual(document["execution_nonce"], NONCE)
        return document["observation"]

    def test_schema_valid_public_observation_is_derived_from_raw_inputs(self) -> None:
        payload = self.valid_case(); observation = self.observation(payload)
        HARNESS.validate_traps(observation, {"case_id": CASE_ID, "subject_sha256": hashlib.sha256(payload).hexdigest()})
        self.assertEqual(set(observation["candidate_counts"]), {"cpu-break", "cpu-syscall", "switch-bounds", "boot-self-check", "dangling-jump-workaround", "checksum", "anti-tamper"})

    def test_identity_injection_and_self_asserted_fields_are_rejected(self) -> None:
        payload = self.valid_case()
        self.assertNotEqual(self.probe(payload, digest="01" * 32).returncode, 0)
        self.assertNotEqual(self.probe(payload, case_id='bad"id').returncode, 0)
        self.assertNotEqual(self.probe(payload, extra=("unexpected",)).returncode, 0)
        self.assertNotEqual(self.probe(payload + b'{"passed":true}').returncode, 0)

    def test_missing_duplicate_contradictory_and_malformed_records_are_rejected(self) -> None:
        events = [(kind, kind, 1, 1, 1, 2) for kind in range(1, 8)]; decisions = [(kind, 1, 1, 1) for kind in range(1, 8)]
        cases = [b"", self.valid_case()[:-1], self.case(events + [events[0]], decisions), self.case(events, decisions[:-1]), self.case(events[:-1] + [(7, 7, 0, 1, 1, 2)], decisions), self.case(events, decisions + [decisions[0]])]
        for payload in cases:
            with self.subTest(length=len(payload)):
                self.assertNotEqual(self.probe(payload).returncode, 0)

    def test_sparse_candidate_ledger_preserves_zero_kind_counts(self) -> None:
        payload = self.case([(1, 1, 1, 1, 11, 21)], [(kind, 1, 1, 1) for kind in range(1, 8)])
        if not sys.platform.startswith("linux"):
            self.assertNotEqual(self.probe(payload).returncode, 0)
            return
        observation = self.observation(payload)
        self.assertEqual(observation["candidate_counts"]["cpu-break"], 1)
        self.assertEqual(observation["candidate_counts"]["cpu-syscall"], 0)

    def test_mutating_raw_event_changes_derived_trace_not_a_fixed_expected_result(self) -> None:
        left = self.observation(self.valid_case())
        changed = [(kind, kind, 1, kind + (1 if kind == 3 else 0), 10 + kind, 20 + kind) for kind in range(1, 8)]
        right = self.observation(self.case(changed, [(kind, (kind - 1) % 3 + 1, 1, 1) for kind in range(1, 8)]))
        self.assertNotEqual(left["records"][2]["native_trace_sha256"], right["records"][2]["native_trace_sha256"])

    @unittest.skipUnless(sys.platform.startswith("linux"), "native trap evidence is Linux-only")
    def test_oracle_has_a_distinct_route_and_matches_native_semantics(self) -> None:
        payload = self.valid_case()
        native = self.observation(payload)
        result = self.probe(payload, oracle=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        oracle = json.loads(result.stdout)["observation"]
        HARNESS.validate_traps(oracle, {"case_id": CASE_ID, "subject_sha256": hashlib.sha256(payload).hexdigest()}, oracle=True)
        self.assertEqual(native["semantic_result_sha256"], oracle["semantic_result_sha256"])

    @unittest.skipUnless(sys.platform.startswith("linux"), "native trap evidence is Linux-only")
    def test_mixed_reachability_within_one_kind_has_native_oracle_parity(self) -> None:
        events = [(1, 1, 1, 1, 11, 21), (1, 2, 0, 0, 12, 22)]
        decisions = [(kind, 1 if kind == 1 else 0, 1, 1) for kind in range(1, 8)]
        payload = self.case(events, decisions)
        native = self.observation(payload)
        oracle_result = self.probe(payload, oracle=True)
        self.assertEqual(oracle_result.returncode, 0, oracle_result.stderr.decode(errors="replace"))
        oracle = json.loads(oracle_result.stdout)["observation"]
        self.assertEqual(native["semantic_result_sha256"], oracle["semantic_result_sha256"])


if __name__ == "__main__":
    unittest.main()
