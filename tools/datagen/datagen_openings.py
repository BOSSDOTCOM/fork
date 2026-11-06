# SPDX-License-Identifier: GPL-3.0-or-later

"""Writes the opening positions Fork's self-play data generation starts from
(DESIGN.md §5.3, deliverable 1), from one Lichess CC0 monthly game file.

Only headers and moves are read; every comment is skipped, so no
`[%eval]` (Stockfish's evaluations, KB data-policy.md) ever reaches the
output. A game is used when it is rated, standard chess, neither player has
the BOT title, and both are rated at least --min-rating. From each used
game: the position after a random ply in [--ply-min, --ply-max], then
--random-min to --random-max uniformly random legal plies (python-chess's
move generator), skipping positions where the game is over and positions
already written (compared without the move counters). Every random choice
comes from a generator seeded by (--seed, the game's index in the file), so
the same file and settings give the same output byte for byte.

The source's SHA-256 is checked against --sha256 (from Lichess's published
sha256sums.txt) before anything is read. With SOURCE "-" the compressed
file is read from standard input instead (a month too large to store,
streamed from its download): it is hashed while it streams, and the
output is published only if the hash matches at the end. The output EPD is
not committed (size); the manifest written beside it (OUT.manifest.json, or
--manifest) is, under data/manifests/, and regenerates it.

Memory stays small and a run can be resumed (owner, 2026-10-30). Positions
go straight to a file in a state folder (OUT.resume, or --state), and
duplicates are found through 64-bit BLAKE2b digests of the positions in one
open-addressing table (--dedup-mb caps it; two distinct positions with equal
digests would count as a duplicate, odds about n^2 / 2^65, some 6 in a
million at 15 M positions). At a game boundary every --checkpoint-seconds
the state folder records the games done, the counts, the output's length,
the tool file's SHA-256 and the SHA-256 of the source bytes read so far.
Run the same command again after a kill or a broken download: the source is
read again from its start (a stream cannot be hashed from the middle), the
games already done are skipped without being replayed, the re-read prefix
must hash as recorded, and the output continues where the checkpoint left
it. The finished output is moved out of the state folder, which is then
removed.

    .venv/Scripts/python.exe -I tools/datagen/datagen_openings.py \\
        lichess_db_standard_rated_2016-09.pgn.zst OUT.epd --sha256 HEX
    curl -sSfL URL | .venv/Scripts/python.exe -I tools/datagen/datagen_openings.py \\
        - OUT.epd --sha256 HEX --source-name NAME.pgn.zst
"""
import argparse
import hashlib
import io
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
from array import array
from pathlib import Path

import chess

COMMENT = re.compile(r'\{[^}]*\}')
MOVE_NUMBER = re.compile(r'^\d+\.+$')
RESULTS = {'1-0', '0-1', '1/2-1/2', '*'}
STAT_KEYS = ('games', 'not_rated', 'not_standard', 'bot', 'below_rating',
             'rating_pass', 'too_short', 'game_over', 'duplicate', 'written')
STATE_VERSION = 1


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


class HashingReader:
    """A binary stream that hashes everything read through it. With
    `check_at` it also compares the SHA-256 of its first `check_at` bytes
    with `expect` as they pass (a resumed run's re-read prefix)."""

    def __init__(self, raw, check_at=0, expect=None):
        self.raw = raw
        self.sha = hashlib.sha256()
        self.size = 0
        self.check_at = check_at
        self.expect = expect
        self.prefix_ok = check_at == 0

    def read(self, n=-1):
        data = self.raw.read(n)
        if not self.prefix_ok and self.size + len(data) >= self.check_at:
            cut = self.check_at - self.size
            self.sha.update(data[:cut])
            if self.sha.hexdigest() != self.expect:
                raise SourceChanged(f'the source\'s first {self.check_at} bytes differ from the checkpoint\'s')
            self.prefix_ok = True
            self.sha.update(data[cut:])
        else:
            self.sha.update(data)
        self.size += len(data)
        return data


class SourceChanged(Exception):
    pass


class SeenKeys:
    """Positions already written, kept as 64-bit BLAKE2b digests in one
    open-addressing table (linear probing, at most half full, doubled while
    under the cap; at the cap it fills to 90% and then refuses)."""

    def __init__(self, max_mb, slots=1 << 16):
        self.max_slots = max(slots, (max_mb << 20) // 8)
        self.table = array('Q', [0]) * slots
        self.count = 0

    @staticmethod
    def digest(key):
        return int.from_bytes(hashlib.blake2b(key.encode(), digest_size=8).digest(), 'little') or 1

    def add(self, key):
        """True when `key` is new (and now recorded), False when seen."""
        d = self.digest(key)
        t = self.table
        mask = len(t) - 1
        i = d & mask
        while t[i]:
            if t[i] == d:
                return False
            i = (i + 1) & mask
        if 2 * (self.count + 1) > len(t):
            if 2 * len(t) <= self.max_slots:
                self._grow()
                return self.add(key)
            if 10 * (self.count + 1) > 9 * len(t):
                raise MemoryError(f'duplicate table full at {self.count} positions; raise --dedup-mb')
        t[i] = d
        self.count += 1
        return True

    def _grow(self):
        old = self.table
        t = array('Q', [0]) * (2 * len(old))
        mask = len(t) - 1
        for d in old:
            if d:
                i = d & mask
                while t[i]:
                    i = (i + 1) & mask
                t[i] = d
        self.table = t


def position_key(fen):
    """A FEN without its move counters, which is python-chess's EPD of the
    position (tested): the duplicate check's key."""
    return fen.rsplit(' ', 2)[0]


def open_text(stream):
    """The PGN text of a byte stream, decompressing .zst while it streams."""
    import zstandard
    return io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(stream, read_across_frames=True),
                            encoding='utf-8', errors='replace')


def read_games(lines):
    """Yields (headers, movetext) per game of a PGN stream."""
    headers, moves, in_moves = {}, [], False
    for line in lines:
        line = line.strip()
        if line.startswith('['):
            if in_moves:
                yield headers, ' '.join(moves)
                headers, moves, in_moves = {}, [], False
            m = re.match(r'\[(\w+)\s+"(.*)"\]$', line)
            if m:
                headers[m.group(1)] = m.group(2)
        elif line:
            in_moves = True
            moves.append(line)
    if headers or moves:
        yield headers, ' '.join(moves)


def san_moves(movetext, limit):
    """The first `limit` SAN moves of a movetext, comments, move numbers,
    NAGs, annotations and the result removed."""
    out = []
    for tok in COMMENT.sub(' ', movetext).split():
        if MOVE_NUMBER.match(tok) or tok in RESULTS or tok.startswith('$'):
            continue
        tok = re.sub(r'^\d+\.+', '', tok).rstrip('?!')
        if tok:
            out.append(tok)
            if len(out) == limit:
                break
    return out


def rating(headers, key):
    try:
        return int(headers.get(key, ''))
    except ValueError:
        return None


def game_filter(headers, min_rating):
    """The stat key a game is dropped under, or None when it is used."""
    if not headers.get('Event', '').startswith('Rated'):
        return 'not_rated'
    if headers.get('Variant', 'Standard') != 'Standard':
        return 'not_standard'
    if 'BOT' in (headers.get('WhiteTitle'), headers.get('BlackTitle')):
        return 'bot'
    w, b = rating(headers, 'WhiteElo'), rating(headers, 'BlackElo')
    if w is None or b is None or min(w, b) < min_rating:
        return 'below_rating'
    return None


def opening_from(movetext, rng, a):
    """The opening position for one used game, or the stat key it fails on."""
    ply = rng.randint(a.ply_min, a.ply_max)
    sans = san_moves(movetext, ply)
    if len(sans) < ply:
        return 'too_short'
    board = chess.Board()
    for san in sans:
        board.push_san(san)
        if board.is_game_over(claim_draw=True):
            return 'game_over'
    for _ in range(rng.randint(a.random_min, a.random_max)):
        moves = sorted(board.legal_moves, key=lambda m: m.uci())
        if not moves:
            return 'game_over'
        board.push(rng.choice(moves))
        if board.is_game_over(claim_draw=True):
            return 'game_over'
    return board


def git_commit():
    root = Path(__file__).resolve().parents[2]
    try:
        head = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'], capture_output=True,
                              text=True, check=True).stdout.strip()
        dirty = subprocess.run(['git', '-C', str(root), 'status', '--porcelain', '--', 'tools/datagen'],
                               capture_output=True, text=True, check=True).stdout.strip()
        return head + ('-dirty' if dirty else '')
    except (OSError, subprocess.CalledProcessError):
        return 'unknown'


def peak_memory_mb():
    """This process's peak resident memory in MB (peak working set on
    Windows)."""
    if sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in (
                    'PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage',
                    'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]

        c = Counters()
        c.cb = ctypes.sizeof(c)
        kernel32, psapi = ctypes.WinDLL('kernel32'), ctypes.WinDLL('psapi')
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        if not psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(c), c.cb):
            return -1.0
        return c.PeakWorkingSetSize / 2**20
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def lower_priority():
    if sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.WinDLL('kernel32')
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        kernel32.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), 0x4000)  # BELOW_NORMAL_PRIORITY_CLASS
    else:
        os.nice(10)


class Output:
    """The positions written so far and the checkpoint beside them, in the
    state folder."""

    def __init__(self, state, identity, dedup_mb):
        self.state = Path(state)
        self.positions = self.state / 'positions.epd'
        self.checkpoint = self.state / 'checkpoint.json'
        self.seen = SeenKeys(dedup_mb)
        self.resumed = None
        if self.checkpoint.exists():
            saved = json.loads(self.checkpoint.read_text())
            if saved['identity'] != identity:
                raise SystemExit(f'{self.checkpoint} belongs to another run (settings, source or tool '
                                 f'changed); delete {self.state} to start again')
            self.resumed = saved
            self.file = open(self.positions, 'r+b')
            self.file.truncate(saved['output_bytes'])
            for line in self.file:
                self.seen.add(position_key(line.decode().rstrip('\n')))
            self.file.seek(0, os.SEEK_END)
            if self.seen.count != saved['stats']['written']:
                raise SystemExit(f'{self.positions} holds {self.seen.count} positions, '
                                 f'the checkpoint says {saved["stats"]["written"]}')
        else:
            self.state.mkdir(parents=True, exist_ok=True)
            self.file = open(self.positions, 'wb')

    def save(self, identity, games_done, stats, reader, extra):
        self.file.flush()
        os.fsync(self.file.fileno())
        record = {'version': STATE_VERSION, 'identity': identity, 'games_done': games_done,
                  'stats': stats, 'output_bytes': self.file.tell(), 'source_bytes': reader.size,
                  'source_prefix_sha256': reader.sha.copy().hexdigest(), **extra}
        tmp = self.checkpoint.with_suffix('.tmp')
        tmp.write_text(json.dumps(record, indent=2) + '\n', newline='\n')
        os.replace(tmp, self.checkpoint)


def run(a, reader, out, identity, log=print):
    """Processes every game of the source, resuming after the checkpoint's
    games; returns the counts."""
    saved = out.resumed or {}
    stats = dict(saved.get('stats') or dict.fromkeys(STAT_KEYS, 0))
    done = saved.get('games_done', 0)
    extra = {'tool_commit': saved.get('tool_commit', a.tool_commit),
             'started': saved.get('started', time.strftime('%Y-%m-%d %H:%M:%S')),
             'resumes': saved.get('resumes', -1) + 1}
    start = last = time.time()
    read = 0
    with open_text(reader) as lines:
        for index, (headers, movetext) in enumerate(read_games(lines)):
            if a.limit_games and index >= a.limit_games:
                break
            read = index + 1
            if index < done:
                continue
            stats['games'] += 1
            why = game_filter(headers, a.min_rating)
            if why:
                stats[why] += 1
            else:
                stats['rating_pass'] += 1
                rng = random.Random(f'{a.seed}:{index}')
                board = opening_from(movetext, rng, a)
                if isinstance(board, str):
                    stats[board] += 1
                else:
                    fen = board.fen()
                    if out.seen.add(position_key(fen)):
                        out.file.write(fen.encode() + b'\n')
                        stats['written'] += 1
                    else:
                        stats['duplicate'] += 1
            now = time.time()
            due = (now - last >= a.checkpoint_seconds if not a.checkpoint_games
                   else (index + 1) % a.checkpoint_games == 0)
            if due and reader.prefix_ok:
                out.save(identity, index + 1, stats, reader, extra)
                last = now
                log(f'{time.strftime("%H:%M:%S")} games {stats["games"]}, used {stats["rating_pass"]}, '
                    f'written {stats["written"]}, source {reader.size / 2**30:.2f} GiB, '
                    f'{(index + 1 - done) / max(now - start, 1e-9):.0f} games/s, '
                    f'peak memory {peak_memory_mb():.0f} MB', flush=True)
        if a.source == '-':
            while reader.read(1 << 20):  # hash any bytes the decompressor left unread
                pass
    if not reader.prefix_ok:
        raise SourceChanged(f'the source ended before the checkpoint\'s {reader.check_at} bytes')
    if read < done:
        raise SourceChanged(f'the source has {read} games, the checkpoint {done}')
    return stats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('source', help='Lichess monthly PGN (.pgn.zst), or "-" for the compressed file on stdin')
    ap.add_argument('out', help='output EPD (one FEN per line)')
    ap.add_argument('--sha256', required=True, help="the source's published SHA-256")
    ap.add_argument('--manifest', help='manifest path (default: OUT.manifest.json)')
    ap.add_argument('--state', help='state folder for resuming (default: OUT.resume)')
    ap.add_argument('--seed', type=int, default=20261028)
    ap.add_argument('--min-rating', type=int, default=2000)
    ap.add_argument('--ply-min', type=int, default=8)
    ap.add_argument('--ply-max', type=int, default=16)
    ap.add_argument('--random-min', type=int, default=2)
    ap.add_argument('--random-max', type=int, default=4)
    ap.add_argument('--limit-games', type=int, default=0, help='stop after N games (tests; 0 = all)')
    ap.add_argument('--source-name', help='with SOURCE "-": the streamed file\'s name, for the manifest')
    ap.add_argument('--dedup-mb', type=int, default=256, help='cap of the duplicate table (MB)')
    ap.add_argument('--checkpoint-seconds', type=float, default=120)
    ap.add_argument('--checkpoint-games', type=int, default=0, help='checkpoint every N games instead (tests)')
    ap.add_argument('--low-priority', action='store_true', help='run at below-normal priority')
    a = ap.parse_args(argv)
    if not (0 < a.ply_min <= a.ply_max and 0 <= a.random_min <= a.random_max):
        ap.error('need 0 < ply-min <= ply-max and 0 <= random-min <= random-max')
    if a.source == '-' and (not a.source_name or a.limit_games):
        ap.error('streaming needs --source-name, and reads the whole stream (no --limit-games)')
    if a.low_priority:
        lower_priority()

    source_name = a.source_name if a.source == '-' else Path(a.source).name
    expected = a.sha256.lower()
    if a.source != '-':
        digest = sha256_of(a.source)
        if digest != expected:
            print(f'SHA-256 mismatch for {a.source}: {digest}, expected {a.sha256}; nothing written', file=sys.stderr)
            return 1
    settings = {k: getattr(a, k) for k in
                ('seed', 'min_rating', 'ply_min', 'ply_max', 'random_min', 'random_max', 'limit_games')}
    identity = {'source': source_name, 'source_sha256': expected, 'settings': settings,
                'tool_sha256': sha256_of(__file__)}
    state = Path(a.state or a.out + '.resume')
    out = Output(state, identity, a.dedup_mb)
    a.tool_commit = git_commit()
    saved = out.resumed or {}
    if saved:
        print(f'resuming after game {saved["games_done"]} ({saved["stats"]["written"]} positions written); '
              f're-reading the first {saved["source_bytes"]} source bytes', flush=True)
    raw = sys.stdin.buffer if a.source == '-' else open(a.source, 'rb')
    reader = HashingReader(raw, saved.get('source_bytes', 0), saved.get('source_prefix_sha256'))
    try:
        stats = run(a, reader, out, identity)
    except SourceChanged as e:
        print(f'{e}; nothing published, {state} kept', file=sys.stderr)
        return 2
    finally:
        out.file.close()
        if raw is not sys.stdin.buffer:
            raw.close()
    digest = reader.sha.hexdigest()
    if digest != expected:
        print(f'SHA-256 mismatch for {a.source}: {digest}, expected {a.sha256}; nothing published, '
              f'{state} kept for a resume', file=sys.stderr)
        return 1
    os.replace(out.positions, a.out)
    manifest = {
        'tool': 'tools/datagen/datagen_openings.py',
        'tool_commit': saved.get('tool_commit', a.tool_commit),
        'source': source_name,
        'source_sha256': digest,
        'settings': settings,
        'filters': 'rated standard games, no BOT title, both ratings >= min_rating; comments never read',
        'stats': stats,
        'output': Path(a.out).name,
        'output_sha256': sha256_of(a.out),
        'positions': stats['written'],
    }
    Path(a.manifest or a.out + '.manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', newline='\n')
    shutil.rmtree(state)
    print(json.dumps(stats))
    print(f'peak memory {peak_memory_mb():.0f} MB')
    return 0


if __name__ == '__main__':
    sys.exit(main())
