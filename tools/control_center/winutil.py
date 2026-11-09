# SPDX-License-Identifier: GPL-3.0-or-later
"""Small Win32 helpers through ctypes (no dependencies). Constants and structures from Microsoft Learn:
SetThreadExecutionState (ES_CONTINUOUS 0x80000000, ES_SYSTEM_REQUIRED 0x00000001; "the state being set
should remain in effect until the next call that uses ES_CONTINUOUS and one of the other state flags is
cleared"), MEMORYSTATUSEX (dwLength must be set before GlobalMemoryStatusEx), GetSystemTimes. On other
systems every function degrades to a harmless answer, so the tests run anywhere.
"""
import ctypes
import os
import shutil

WINDOWS = os.name == 'nt'
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
STILL_ACTIVE = 259

if WINDOWS:
    from ctypes import wintypes
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    k32.SetThreadExecutionState.restype = wintypes.DWORD
    k32.SetThreadExecutionState.argtypes = [wintypes.DWORD]
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [('dwLength', wintypes.DWORD), ('dwMemoryLoad', wintypes.DWORD),
                    ('ullTotalPhys', ctypes.c_uint64), ('ullAvailPhys', ctypes.c_uint64),
                    ('ullTotalPageFile', ctypes.c_uint64), ('ullAvailPageFile', ctypes.c_uint64),
                    ('ullTotalVirtual', ctypes.c_uint64), ('ullAvailVirtual', ctypes.c_uint64),
                    ('ullAvailExtendedVirtual', ctypes.c_uint64)]

    class FILETIME(ctypes.Structure):
        _fields_ = [('lo', wintypes.DWORD), ('hi', wintypes.DWORD)]


def sleep_block(on):
    """Keeps the system (not the display) awake while on; on=False hands the decision back to Windows.
    Applies to the calling thread. Returns True on success."""
    if not WINDOWS:
        return True
    flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED if on else ES_CONTINUOUS
    return k32.SetThreadExecutionState(flags) != 0


def pid_alive(pid):
    if not pid:
        return False
    if not WINDOWS:
        try:
            os.kill(int(pid), 0)
            return True
        except OSError:
            return False
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not h:
        return False
    try:
        code = wintypes.DWORD()
        return bool(k32.GetExitCodeProcess(h, ctypes.byref(code))) and code.value == STILL_ACTIVE
    finally:
        k32.CloseHandle(h)


def memory():
    """{'load': percent, 'total': bytes, 'free': bytes} of physical memory."""
    if not WINDOWS:
        return None
    m = MEMORYSTATUSEX()
    m.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    if not k32.GlobalMemoryStatusEx(ctypes.byref(m)):
        return None
    return {'load': m.dwMemoryLoad, 'total': m.ullTotalPhys, 'free': m.ullAvailPhys}


def cpu_times():
    """(idle, busy) 100-ns ticks since boot over all processors; the load is the busy share of a delta."""
    if not WINDOWS:
        return None
    idle, kernel, user = FILETIME(), FILETIME(), FILETIME()
    if not k32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
        return None
    v = lambda t: (t.hi << 32) | t.lo  # noqa: E731
    i, k, u = v(idle), v(kernel), v(user)
    return i, (k - i) + u  # kernel time includes the idle time


def disk(path):
    try:
        u = shutil.disk_usage(path)
        return {'total': u.total, 'free': u.free}
    except OSError:
        return None
