from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import time
from unittest import mock
from scripts.autonomy import process_guard

from scripts.autonomy.process_guard import WorkerJob, real_python_executable


class ProcessGuardTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows Job Objects only")
    def test_closing_job_terminates_assigned_child(self) -> None:
        process = subprocess.Popen([real_python_executable(), "-c", "import time; time.sleep(30)"],
                                   stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
        try:
            with WorkerJob(memory_limit_bytes=512 * 1024 * 1024,
                           cpu_seconds=30) as guard:
                guard.assign(process)
                self.assertIsNone(process.poll())
            # Kill-on-close may report exit code zero on Windows; prompt exit
            # (rather than the script's 30-second sleep) is the contract.
            self.assertIsNotNone(process.wait(timeout=5))
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)

    @unittest.skipUnless(os.name == "nt", "Windows Job Objects only")
    def test_hard_parent_exit_terminates_assigned_child(self) -> None:
        import ctypes
        from ctypes import wintypes

        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "child-pid.txt"
            code = (
                "import os, pathlib, subprocess, sys\n"
                "from scripts.autonomy.process_guard import WorkerJob, real_python_executable\n"
                "guard = WorkerJob(memory_limit_bytes=512*1024*1024)\n"
                "child = guard.launch([real_python_executable(), '-c', 'import time; time.sleep(30)'])\n"
                "pathlib.Path(sys.argv[1]).write_text(str(child.pid))\n"
                "os._exit(99)\n"
            )
            parent = subprocess.run([real_python_executable(), "-c", code, str(marker)],
                                    cwd=str(Path(__file__).resolve().parents[2]),
                                    capture_output=True, timeout=10, check=False)
            self.assertEqual(parent.returncode, 99, parent.stderr.decode(errors="replace"))
            pid = int(marker.read_text())
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            kernel32.WaitForSingleObject.restype = wintypes.DWORD
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
            handle = kernel32.OpenProcess(0x00100001, False, pid)  # SYNCHRONIZE | TERMINATE
            if handle:
                try:
                    outcome = kernel32.WaitForSingleObject(handle, 5000)
                    if outcome != 0:
                        kernel32.TerminateProcess(handle, 1)
                    self.assertEqual(outcome, 0, "orphan child survived parent crash")
                finally:
                    kernel32.CloseHandle(handle)


@unittest.skipUnless(os.name == "nt", "Windows Job Objects only")
class SuspendedLaunchTests(unittest.TestCase):
    def test_worker_cannot_execute_before_assignment(self):
        with tempfile.TemporaryDirectory() as temporary, WorkerJob() as guard:
            marker = Path(temporary) / "ran"
            original_assign = guard.assign
            def assign(process):
                time.sleep(.15)
                self.assertFalse(marker.exists(), "worker ran before assignment")
                original_assign(process)
            with mock.patch.object(guard, "assign", side_effect=assign):
                worker = guard.launch([real_python_executable(), "-c",
                    "from pathlib import Path; import sys; Path(sys.argv[1]).touch()", str(marker)])
                self.assertEqual(worker.wait(timeout=5), 0)
            self.assertTrue(marker.exists())

    def test_assignment_failure_never_executes_worker(self):
        with tempfile.TemporaryDirectory() as temporary, WorkerJob() as guard:
            marker = Path(temporary) / "ran"
            captured = []
            def reject(process):
                captured.append(process)
                raise OSError("injected assignment failure")
            with mock.patch.object(guard, "assign", side_effect=reject):
                with self.assertRaisesRegex(OSError, "injected"):
                    guard.launch([real_python_executable(), "-c",
                        "from pathlib import Path; import sys; Path(sys.argv[1]).touch()", str(marker)])
            self.assertFalse(marker.exists())
            self.assertIsNotNone(captured[0].poll())

    def test_legacy_guard_receipt_cannot_prove_containment(self):
        import json
        from scripts.autonomy.supervisor import expired_attempt_contained
        with tempfile.TemporaryDirectory() as temporary:
            record = Path(temporary) / "worker.guard.json"
            with mock.patch("scripts.autonomy.supervisor.owner_process_dead", return_value=True):
                for schema, expected in ((1, False), (2, True)):
                    record.write_text(json.dumps({"schema": schema, "state": "finished", "owner_pid": 123}))
                    self.assertEqual(expired_attempt_contained(Path(temporary)), expected)

    def test_package_query_fails_closed(self):
        for status in (0, 122, 5):
            with self.subTest(status=status), mock.patch.object(
                    process_guard._kernel32, "GetPackageFullName", return_value=status):
                with self.assertRaises(OSError):
                    real_python_executable()

    def test_breakaway_is_rejected(self):
        with WorkerJob() as guard, self.assertRaisesRegex(ValueError, "breakaway"):
            guard.launch([real_python_executable(), "-c", "pass"], creationflags=0x01000000)

    def test_native_descendants_inherit_and_die_on_close(self):
        import ctypes
        from ctypes import wintypes
        k = process_guard._kernel32
        k.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
            ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
        k.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE,
                                    ctypes.POINTER(wintypes.BOOL)]
        native = str(Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe")
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "native-pid.txt"
            command = ("$p = Start-Process -FilePath '" + native.replace("'", "''") +
                "' -ArgumentList '-NoProfile','-NonInteractive','-Command','Start-Sleep -Seconds 30' "
                "-WindowStyle Hidden -PassThru; Set-Content -LiteralPath '" +
                str(marker).replace("'", "''") + "' -Value $p.Id; Start-Sleep -Seconds 30")
            handle = None
            with WorkerJob() as guard:
                worker = guard.launch([native, "-NoProfile", "-NonInteractive", "-Command", command],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW)
                deadline = time.monotonic() + 10
                while not marker.exists() and time.monotonic() < deadline:
                    time.sleep(.05)
                self.assertTrue(marker.exists(), "native grandchild did not start")
                pid = int(marker.read_text().strip())
                handle = k.OpenProcess(0x00101000, False, pid)
                self.assertTrue(handle)
                try:
                    for process_handle in (worker._handle, handle):
                        member = wintypes.BOOL()
                        self.assertTrue(k.IsProcessInJob(process_handle, guard.handle, ctypes.byref(member)))
                        self.assertTrue(member.value, "native process escaped the exact worker job")
                    guard.close()
                    self.assertIsNotNone(worker.wait(timeout=5))
                    self.assertEqual(k.WaitForSingleObject(handle, 5000), 0,
                                     "native grandchild survived guard close")
                finally:
                    k.CloseHandle(handle)

    def test_installed_store_python_is_rejected_before_code_runs(self):
        candidates = list((Path(os.environ["LOCALAPPDATA"]) / "Microsoft/WindowsApps").glob("PythonSoftwareFoundation.Python.*/python.exe"))
        if not candidates:
            self.skipTest("no Store Python installed")
        with tempfile.TemporaryDirectory() as temporary, WorkerJob() as guard:
            marker = Path(temporary) / "ran"
            with self.assertRaisesRegex(OSError, "packaged"):
                guard.launch([str(candidates[0]), "-c",
                    "from pathlib import Path; import sys; Path(sys.argv[1]).touch()", str(marker)])
            self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
