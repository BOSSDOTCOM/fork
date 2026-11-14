# SPDX-License-Identifier: GPL-3.0-or-later
"""In-process machine probes for the display (Windows, ctypes; no process is started, nothing is written).
Structures and calls from Microsoft Learn: GetSystemTimes, MEMORYSTATUSEX / GlobalMemoryStatusEx,
PERFORMANCE_INFORMATION / GetPerformanceInfo (commit charge in pages), OpenProcess with
PROCESS_QUERY_LIMITED_INFORMATION (0x1000: query only, the least access that reads exit code and times),
GetProcessTimes, GetTickCount64. On other systems every probe returns None, so the tests run anywhere."""
import ctypes
import os
import time

WINDOWS = os.name == 'nt'
QUERY_LIMITED = 0x1000
STILL_ACTIVE = 259
START_SLACK = 2.0     # seconds between a recorded process start and the live one's (jobctl's own slack)
START_WINDOW = 120    # an older record without process starts: its processes start this soon after it

if WINDOWS:
    from ctypes import wintypes
    _k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    _psapi = ctypes.WinDLL('psapi', use_last_error=True)
    _k32.OpenProcess.restype = wintypes.HANDLE
    _k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    _k32.CloseHandle.argtypes = [wintypes.HANDLE]
    _k32.GetTickCount64.restype = ctypes.c_ulonglong

    class _MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [('dwLength', wintypes.DWORD), ('dwMemoryLoad', wintypes.DWORD),
                    ('ullTotalPhys', ctypes.c_uint64), ('ullAvailPhys', ctypes.c_uint64),
                    ('ullTotalPageFile', ctypes.c_uint64), ('ullAvailPageFile', ctypes.c_uint64),
                    ('ullTotalVirtual', ctypes.c_uint64), ('ullAvailVirtual', ctypes.c_uint64),
                    ('ullAvailExtendedVirtual', ctypes.c_uint64)]

    class _PERFORMANCE_INFORMATION(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('CommitTotal', ctypes.c_size_t), ('CommitLimit', ctypes.c_size_t),
                    ('CommitPeak', ctypes.c_size_t), ('PhysicalTotal', ctypes.c_size_t),
                    ('PhysicalAvailable', ctypes.c_size_t), ('SystemCache', ctypes.c_size_t),
                    ('KernelTotal', ctypes.c_size_t), ('KernelPaged', ctypes.c_size_t),
                    ('KernelNonpaged', ctypes.c_size_t), ('PageSize', ctypes.c_size_t),
                    ('HandleCount', wintypes.DWORD), ('ProcessCount', wintypes.DWORD), ('ThreadCount', wintypes.DWORD)]

    class _FILETIME(ctypes.Structure):
        _fields_ = [('lo', wintypes.DWORD), ('hi', wintypes.DWORD)]


def cpu_times():
    """(idle, busy) 100-ns ticks since boot over all processors; the load is the busy share of a delta."""
    if not WINDOWS:
        return None
    idle, kernel, user = _FILETIME(), _FILETIME(), _FILETIME()
    if not _k32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
        return None
    v = lambda t: (t.hi << 32) | t.lo  # noqa: E731
    i, k, u = v(idle), v(kernel), v(user)
    return i, (k - i) + u   # kernel time includes the idle time


def memory():
    """{total, avail (bytes of physical memory), commit (percent of the commit limit in use)}, or None."""
    if not WINDOWS:
        return None
    m = _MEMORYSTATUSEX()
    m.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
    if not _k32.GlobalMemoryStatusEx(ctypes.byref(m)):
        return None
    out = {'total': m.ullTotalPhys, 'avail': m.ullAvailPhys, 'commit': None}
    p = _PERFORMANCE_INFORMATION()
    p.cb = ctypes.sizeof(_PERFORMANCE_INFORMATION)
    if _psapi.GetPerformanceInfo(ctypes.byref(p), p.cb) and p.CommitLimit:
        out['commit'] = round(100.0 * p.CommitTotal / p.CommitLimit, 1)
    return out


def processors():
    return os.cpu_count()


def boot_time():
    if not WINDOWS:
        return None
    return time.time() - _k32.GetTickCount64() / 1000


def pid_started(pid):
    """(alive, creation time as epoch seconds or None). Query access only."""
    if not WINDOWS or not pid:
        return False, None
    h = _k32.OpenProcess(QUERY_LIMITED, False, int(pid))
    if not h:
        return False, None
    try:
        code = wintypes.DWORD()
        alive = bool(_k32.GetExitCodeProcess(h, ctypes.byref(code))) and code.value == STILL_ACTIVE
        times = [_FILETIME() for _ in range(4)]
        if not _k32.GetProcessTimes(h, *(ctypes.byref(t) for t in times)):
            return alive, None
        ticks = (times[0].hi << 32) | times[0].lo          # 100 ns since 1601-01-01 UTC
        return alive, ticks / 1e7 - 11644473600
    finally:
        _k32.CloseHandle(h)


def job_live(rec, probe=pid_started, boot=None):
    """Whether a supervisor job whose record says running still has its recorded keeper or command process.
    The same rule as jobctl's recorded_alive (a process counts only if it started when the record says, so a
    reused process id does not), without opening the job's Job Object. `rec` is readers.job_record's result.
    Returns True, False, or None when it cannot be told (no recorded process ids)."""
    if rec.get('state') in ('ended', 'stopped', 'failed'):
        return False
    started = rec.get('started')
    boot = boot_time() if boot is None else boot
    if started is not None and boot is not None and started < boot - 60:
        return False                    # started before the last boot: nothing of it is left
    seen = False
    for key in ('keeper', 'pid'):
        pid = rec.get(key)
        if not pid:
            continue
        seen = True
        alive, actual = probe(pid)
        if not alive:
            continue
        want = rec.get(f'{key}_started')
        if actual is None:
            return True
        if want is not None:
            if abs(actual - float(want)) <= START_SLACK:
                return True
        elif started is None or started - START_SLACK <= actual <= started + START_WINDOW:
            return True
    return False if seen else None
