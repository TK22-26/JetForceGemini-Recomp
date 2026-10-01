from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

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
                "child = subprocess.Popen([real_python_executable(), '-c', 'import time; time.sleep(30)'])\n"
                "guard.assign(child)\n"
                "pathlib.Path(sys.argv[1]).write_text(str(child.pid))\n"
                "os._exit(99)\n"
            )
            parent = subprocess.run([real_python_executable(), "-c", code, str(marker)],
                                    cwd=str(Path(__file__).resolve().parents[1]),
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


if __name__ == "__main__":
    unittest.main()
