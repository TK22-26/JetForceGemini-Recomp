"""Contain a Windows worker tree in a kill-on-close Job Object.

The handle is non-inheritable. If the supervisor process dies, Windows closes
its last handle and terminates the assigned worker and descendants. This is a
process-containment primitive, not a substitute for lease/artifact recovery.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def real_python_executable() -> str:
    """Avoid Windows Store app-execution aliases that exit before job assignment."""
    if os.name == "nt":
        candidate = Path(sys.base_prefix) / "python.exe"
        if candidate.is_file():
            return str(candidate)
        if "WindowsApps" in sys.executable:
            raise OSError("cannot resolve a non-alias Python executable")
    return sys.executable


if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    class _BasicLimit(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class _ExtendedLimit(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _BasicLimit),
            ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    _kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    _kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, wintypes.INT,
                                                  ctypes.c_void_p, wintypes.DWORD]
    _kernel32.SetInformationJobObject.restype = wintypes.BOOL
    _kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.restype = wintypes.BOOL
    _kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    _kernel32.WaitForSingleObject.restype = wintypes.DWORD

    _EXTENDED_LIMIT_CLASS = 9
    _KILL_ON_CLOSE = 0x00002000
    _JOB_MEMORY = 0x00000200
    _JOB_TIME = 0x00000004


def owner_process_dead(pid: int) -> bool:
    """Conservatively confirm a Windows guard owner has exited."""
    if os.name != "nt" or type(pid) is not int or pid <= 0:
        return False
    handle = _kernel32.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
    if not handle:
        return ctypes.get_last_error() == 87  # ERROR_INVALID_PARAMETER: no PID
    try:
        return _kernel32.WaitForSingleObject(handle, 0) == 0
    finally:
        _kernel32.CloseHandle(handle)


class WorkerJob:
    """One process-tree guard, scoped to the owner process lifetime."""

    def __init__(self, *, memory_limit_bytes: int | None = None,
                 cpu_seconds: int | None = None):
        if memory_limit_bytes is not None and memory_limit_bytes < 64 * 1024 * 1024:
            raise ValueError("worker memory cap is too small")
        if cpu_seconds is not None and cpu_seconds <= 0:
            raise ValueError("worker CPU cap must be positive")
        self.handle = None
        if os.name != "nt":
            return
        handle = _kernel32.CreateJobObjectW(None, None)
        if not handle:
            raise OSError(ctypes.get_last_error(), "CreateJobObjectW failed")
        self.handle = handle
        limits = _ExtendedLimit()
        limits.BasicLimitInformation.LimitFlags = _KILL_ON_CLOSE
        if memory_limit_bytes is not None:
            limits.BasicLimitInformation.LimitFlags |= _JOB_MEMORY
            limits.JobMemoryLimit = memory_limit_bytes
        if cpu_seconds is not None:
            limits.BasicLimitInformation.LimitFlags |= _JOB_TIME
            limits.BasicLimitInformation.PerJobUserTimeLimit = cpu_seconds * 10_000_000
        if not _kernel32.SetInformationJobObject(
                handle, _EXTENDED_LIMIT_CLASS, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.get_last_error()
            self.close()
            raise OSError(error, "SetInformationJobObject failed")

    def assign(self, process: subprocess.Popen[bytes]) -> None:
        if os.name == "nt":
            if not _kernel32.AssignProcessToJobObject(self.handle, process._handle):
                raise OSError(ctypes.get_last_error(), "AssignProcessToJobObject failed")

    def close(self) -> None:
        if self.handle is not None:
            _kernel32.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self) -> WorkerJob:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
