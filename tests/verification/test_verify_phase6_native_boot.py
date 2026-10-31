"""Tests for the strict private Phase 6 native M2 verifier."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import verify_phase6_native_boot as verifier


class NativeRunContract(unittest.TestCase):
    def result(self) -> dict[str, object]:
        return {
            "kind": "jfg-phase6-native-boot",
            "status": "stable-vi",
            "build_identity": "MSVC-19.40.33811.0-Release",
            "sanitizer": "none",
            "vi_retraces": 3,
            "vi_frames": 3,
            "vi_interrupts": 3,
            "vi_messages_delivered": 3,
            "vi_queue": "0x800fb480",
            "threads_created": 5,
            "rdram_bytes": 4 * 1024 * 1024,
            "mmio_accesses": 2,
            "unsupported_accesses": 0,
            "mmio_trace": "r:0xa4400010,w:0xa4400000",
            "journal_entries": 10,
            "state_hash": "a" * 64,
            "journal_hash": "b" * 64,
        }

    @mock.patch.object(verifier.subprocess, "run")
    def test_accepts_only_the_canonical_success_record(self, run: mock.Mock) -> None:
        payload = (json.dumps(self.result(), separators=(",", ":")) + "\r\n").encode()
        run.return_value = subprocess.CompletedProcess([], 0, payload, b"")

        normalized, result = verifier.run_native(Path("runner"), Path("game.z64"))

        self.assertEqual(normalized, payload.replace(b"\r\n", b"\n"))
        self.assertEqual(result, self.result())

    @mock.patch.object(verifier.subprocess, "run")
    def test_rejects_extra_output(self, run: mock.Mock) -> None:
        payload = (json.dumps(self.result(), separators=(",", ":")) + "\nextra\n").encode()
        run.return_value = subprocess.CompletedProcess([], 0, payload, b"")
        with self.assertRaisesRegex(ValueError, "not one JSON document"):
            verifier.run_native(Path("runner"), Path("game.z64"))

    def test_reports_the_first_semantic_divergence(self) -> None:
        baseline = self.result()
        changed = dict(baseline)
        changed["state_hash"] = "c" * 64

        divergence = verifier.first_divergence(
            b"baseline\n", baseline, b"changed\n", changed, 2
        )

        self.assertEqual(
            divergence,
            {
                "run": 2,
                "domain": "state_hash",
                "expected": "a" * 64,
                "actual": "c" * 64,
            },
        )

    def test_rejects_an_incomplete_mmio_trace(self) -> None:
        result = self.result()
        result["mmio_accesses"] = 3
        payload = (json.dumps(result, separators=(",", ":")) + "\n").encode()
        with mock.patch.object(
            verifier.subprocess,
            "run",
            return_value=subprocess.CompletedProcess([], 0, payload, b""),
        ):
            with self.assertRaisesRegex(ValueError, "MMIO count"):
                verifier.run_native(Path("runner"), Path("game.z64"))

    @mock.patch.object(verifier.subprocess, "run")
    def test_rejects_a_nonzero_unsupported_count(self, run: mock.Mock) -> None:
        result = self.result()
        result["unsupported_accesses"] = 1
        payload = (json.dumps(result, separators=(",", ":")) + "\n").encode()
        run.return_value = subprocess.CompletedProcess([], 0, payload, b"")
        with self.assertRaisesRegex(ValueError, "does not clear the M2 gate"):
            verifier.run_native(Path("runner"), Path("game.z64"))


class InvalidRomContract(unittest.TestCase):
    @mock.patch.object(verifier.subprocess, "run")
    def test_requires_silent_exit_two(self, run: mock.Mock) -> None:
        run.return_value = subprocess.CompletedProcess([], 2, b"", b"")
        verifier.verify_invalid_rom(Path("runner"))

        command = run.call_args.args[0]
        self.assertEqual(command[0], "runner")
        self.assertEqual(Path(command[2]).name, "invalid.z64")

    @mock.patch.object(verifier.subprocess, "run")
    def test_rejects_invalid_rom_diagnostics(self, run: mock.Mock) -> None:
        run.return_value = subprocess.CompletedProcess([], 2, b"unexpected", b"")
        with self.assertRaisesRegex(ValueError, "fail safely and silently"):
            verifier.verify_invalid_rom(Path("runner"))


class SanitizerProvenanceContract(unittest.TestCase):
    def test_requires_an_asan_runtime_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            executable = Path(temporary) / "runner.exe"
            executable.write_bytes(b"MZ...clang_rt.asan_dynamic-x86_64.dll...")
            self.assertEqual(
                verifier.verify_address_sanitizer_instrumentation(executable),
                "clang-rt-asan-runtime-reference",
            )
            executable.write_bytes(b"MZ ordinary executable")
            with self.assertRaisesRegex(ValueError, "no AddressSanitizer"):
                verifier.verify_address_sanitizer_instrumentation(executable)


if __name__ == "__main__":
    unittest.main()
