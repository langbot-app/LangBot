from __future__ import annotations

import ctypes
from ctypes import wintypes


class WindowsJob:
    """Own a process tree, including descendants whose parent has exited."""

    def __init__(self, pid: int):
        self._kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateJobObjectW": ([ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE),
            "OpenProcess": (
                [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD],
                wintypes.HANDLE,
            ),
            "AssignProcessToJobObject": (
                [wintypes.HANDLE, wintypes.HANDLE],
                wintypes.BOOL,
            ),
            "TerminateJobObject": ([wintypes.HANDLE, wintypes.UINT], wintypes.BOOL),
            "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self._kernel, name)
            function.argtypes = arguments
            function.restype = result
        self._handle = self._kernel.CreateJobObjectW(None, None)
        if not self._handle:
            raise ctypes.WinError(ctypes.get_last_error())
        process = self._kernel.OpenProcess(0x0100 | 0x0001, False, pid)
        try:
            if not process or not self._kernel.AssignProcessToJobObject(
                self._handle, process
            ):
                raise ctypes.WinError(ctypes.get_last_error())
        except BaseException:
            self._kernel.CloseHandle(self._handle)
            self._handle = None
            raise
        finally:
            if process:
                self._kernel.CloseHandle(process)

    def terminate(self) -> None:
        if self._handle and not self._kernel.TerminateJobObject(self._handle, 1):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self) -> None:
        if self._handle:
            try:
                self.terminate()
            finally:
                self._kernel.CloseHandle(self._handle)
                self._handle = None
