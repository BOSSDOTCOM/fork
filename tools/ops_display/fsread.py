# SPDX-License-Identifier: GPL-3.0-or-later
"""The Operations Display's only door to the file system: read-only, shared, change-gated.

Rules this module keeps (DESIGN.md section 9):
  * nothing is ever opened for writing; there is no write, rename, delete or mkdir here;
  * on Windows a file is opened with read, write AND delete sharing, so a production script that
    replaces or removes the file while it is open here does not fail (jobctl replaces job records
    by rename; a keeper died on a blocked rename on 2026-11-12);
  * files are read whole (small ones) or by their tail, and closed at once;
  * a source is re-read only when its size or modified time changed; a failed read keeps the last
    good value and marks the source, so one bad file never blanks the screen.
"""
import json
import os
import re
import time

WINDOWS = os.name == 'nt'
MAX_WHOLE = 4 * 1024 * 1024   # a "small file" read whole; larger ones must be read by tail

if WINDOWS:
    import ctypes
    import msvcrt
    from ctypes import wintypes
    _k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    _k32.CreateFileW.restype = wintypes.HANDLE
    _k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                 wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    _k32.CloseHandle.argtypes = [wintypes.HANDLE]
    GENERIC_READ = 0x80000000
    SHARE_ALL = 0x1 | 0x2 | 0x4          # FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE
    OPEN_EXISTING = 3
    INVALID_HANDLE = wintypes.HANDLE(-1).value


def open_shared(path):
    """A binary read handle that blocks no other process (see the module text). Raises OSError."""
    path = os.fspath(path)
    if not WINDOWS:
        return open(path, 'rb')
    h = _k32.CreateFileW(path, GENERIC_READ, SHARE_ALL, None, OPEN_EXISTING, 0, None)
    if h is None or h == INVALID_HANDLE:
        err = ctypes.get_last_error()
        raise OSError(err, ctypes.FormatError(err).strip(), path)
    try:
        fd = msvcrt.open_osfhandle(h, os.O_RDONLY | os.O_BINARY)
    except OSError:
        _k32.CloseHandle(h)
        raise
    return os.fdopen(fd, 'rb')


def read_bytes(path, limit=MAX_WHOLE):
    with open_shared(path) as f:
        data = f.read(limit + 1)
    if len(data) > limit:
        raise OSError(f'{os.path.basename(os.fspath(path))} is larger than {limit} bytes; read it by tail')
    return data


def read_text(path, limit=MAX_WHOLE):
    return read_bytes(path, limit).decode('utf-8', 'replace')


def tail_text(path, nbytes):
    """The last nbytes of a text file as whole lines: a first line cut by the seek is dropped, and so is a
    last line without its newline (a writer is in the middle of it)."""
    with open_shared(path) as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        start = max(0, size - nbytes)
        f.seek(start)
        data = f.read(nbytes)
    text = data.decode('utf-8', 'replace')
    if start > 0:
        cut = text.find('\n')
        text = text[cut + 1:] if cut >= 0 else ''
    if text and not text.endswith('\n'):
        cut = text.rfind('\n')
        text = text[:cut + 1] if cut >= 0 else ''
    return text


def read_json(path, limit=MAX_WHOLE):
    """The parsed file. Raises OSError (missing, unreadable) or ValueError (not JSON, e.g. half written)."""
    return json.loads(read_text(path, limit))


def stat(path):
    """(modified time, size), or None when the path is missing or unreadable."""
    try:
        s = os.stat(path)
        return s.st_mtime, s.st_size
    except OSError:
        return None


def mtime(path):
    s = stat(path)
    return s[0] if s else None


def listdir(path):
    """Entries of a folder as (name, is_dir, mtime, size), or [] when it is missing."""
    out = []
    try:
        with os.scandir(path) as it:
            for e in it:
                try:
                    s = e.stat()
                    out.append((e.name, e.is_dir(), s.st_mtime, s.st_size))
                except OSError:
                    continue
    except OSError:
        return []
    return sorted(out)


# ---------------------------------------------------------------- personal paths

_HOME = re.compile(r'''(?ix)
    (?: (?:[a-z]:[\\/]+ | /[a-z]/ | /mnt/[a-z]/ ) users [\\/]+ [^\\/\s"'<>|:*?]+     # Windows home, three spellings
      | (?:[\\/]{2}wsl(?:\.localhost|\$)[\\/]+[^\\/\s"']+)? [\\/]home[\\/]+ [^\\/\s"'<>|:*?]+ )   # a WSL home
''')
_IP = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')


def scrub(text):
    """Text safe to show: every home folder becomes ~ (no user name), every IPv4 address is removed."""
    text = _HOME.sub('~', text)
    return _IP.sub(lambda m: m.group(0) if m.group(0).startswith('127.') else '[address]', text)


# ---------------------------------------------------------------- change-gated cache

class Source:
    """One source's last good value and its health."""
    __slots__ = ('value', 'sig', 'read_at', 'error', 'error_at', 'missing')

    def __init__(self):
        self.value, self.sig, self.read_at, self.error, self.error_at, self.missing = None, None, None, None, None, False


class Cache:
    """load(key, path, loader): the loader's value for the file, re-run only when the file changed.

    The loader gets the path and returns a value; it may raise OSError or ValueError (and any parse error).
    On failure the last good value stays, and health() reports the source as failing, so the display can
    raise an alert that names the file instead of going blank."""

    def __init__(self, clock=time.time):
        self.sources = {}
        self.clock = clock

    def load(self, key, path, loader, default=None, optional=False):
        src = self.sources.setdefault(key, Source())
        sig = stat(path)
        if sig is None:
            src.missing = True
            src.sig = None
            if not optional:
                src.error, src.error_at = 'missing', self.clock()
            else:
                src.error = None
            return src.value if src.value is not None and not optional else default
        src.missing = False
        if sig == src.sig and src.error is None:
            return src.value
        try:
            value = loader(path)
        except Exception as e:  # noqa: BLE001  a reader must never take the display down
            src.error, src.error_at = f'{type(e).__name__}: {e}'[:160], self.clock()
            src.sig = None      # try again next time: the file may have been half written
            return src.value if src.value is not None else default
        src.value, src.sig, src.read_at, src.error = value, sig, self.clock(), None
        return value

    def health(self):
        """{key: {ok, error, age}} for every source seen."""
        now = self.clock()
        out = {}
        for k, s in self.sources.items():
            out[k] = {'ok': s.error is None, 'error': s.error, 'missing': s.missing,
                      'age': None if s.read_at is None else round(now - s.read_at)}
        return out
