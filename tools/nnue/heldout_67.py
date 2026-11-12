# SPDX-License-Identifier: GPL-3.0-or-later
"""The held-out 6-7-piece endgame check (owner, 2026-11-11, after the bug review's T1): random quiet positions of
the endgame slice v2 materials (docs/research/endgame-slice-v2/design.md, budget R), labelled by ChessTB WDL, so
the held-out drift of tools/nnue/endgame_heldout.py (4-5 pieces: S512ppr2 454, S512ppr3 514, r8btd90 526, r8brft1
612 of 3,800) can be measured where Fork's local tables (Syzygy 3-4-5) stop.

**The prober** (owner's order, 2026-11-11; design §0, item 2): `chess.chesstb` of the python-chess fork
noobpwnftw/python-chess at commit 38c108efd992538dc078750cba9fee30b9f030ce (GPL-3.0, pure Python) with python-lz4,
in its own virtual environment in WSL (`~/fork-tools/chesstb-venv`), never in Fork's .venv and never in the engine.
`generate` and `verify345` run there; every other command runs in Fork's .venv (upstream python-chess) and never
imports chess.chesstb.

**Rules, declared before any label was computed** (2026-11-11):
- **Materials**: the 28 `full/` WDL files on disk in WSL (`~/fork-data/chesstb/full/wdl`, the design's budget R:
  23 six-piece and 5 seven-piece materials), grouped in the design's four classes (§3: C1 rook endings, C2 rook
  against minor, C3 queen endings and imbalances, C4 piece against pawns) for the report.
- **Size**: PER_MATERIAL = 200 positions per material (the 4-5-piece set's per-class count), 5,600 in all. The
  prober was measured first (2026-11-11, `full/` files, cold): 234-795 probes a second, so labelling takes minutes,
  far inside the order's two-hour bound; the count is the 4-5-piece set's, not a budget limit.
- **Placement**: endgame_heldout.py's (that is endgame_check.py's) rules: the material's first side gets White or
  Black at random, the side to move is drawn at random, pawns on ranks 2-7, no castling right, no en-passant
  square, halfmove clock 0; kept only when legal (python-chess is_valid), not in check, no capture available and
  not over, **plus the slice v2 quiet rule (design §4): no promotion available**, so the static evaluation is not
  asked about a promotion one move away. One RNG per material, seeded with the string 'SEED:MATERIAL'
  (SEED = 2026111167, distinct from the 4-5-piece set's 20261111 and from every slice seed); no (board, side to
  move) twice.
- **Labels**: ChessTB WDL from the side to move, each material's `full/` file probed alone in an otherwise empty
  directory (a symbolic link to the file under `wdl/`), so a hidden dependency raises MissingTableError and stops
  the run (KB chesstb.md §2: a `full/` file decodes on its own except for en-passant captures, which the placement
  never creates). Before a file is opened its size must equal the download plan's and its SHA-256 the download
  manifest's (computed again here). +2 is won, -2 lost, **everything else drawn** (a cursed win or a blessed loss is
  a draw under the fifty-move rule: KB chesstb.md, design §5). The 4-5-piece set counted those as won and lost;
  the raw WDL is kept in the file, so either reading can be taken.
- **Misjudged** (endgame_check.py's thresholds): a won position below +100 cp, a lost one above -100 cp, a drawn one
  beyond +-200 cp, from the side to move, by each net's integer evaluation (R-int, tools/nnue/models.py) at the
  net's own scale.
- **Held out**: endgame slice v2 (not yet generated) must leave out every position of this file (design §4: "not
  in the held-out check set"; exact board and side to move, endgame_heldout.key) and use a seed other than SEED.
  `overlap` matches the file against the slice v1 files and Fork's self-play shards (every position of each game,
  heldout_deep.scan restricted to 6-7 pieces).

**Verification before use** (design §5.1, check 1): `sample345` draws random legal 3-5-piece positions (any side to
move, check allowed; every material of the Syzygy 3-4-5 directory, uniformly; either colour first) and labels them
with upstream python-chess's Syzygy prober; `verify345` probes the same positions with ChessTB's shipping 3-5-piece
WDL files (alone in a directory of links) and stops at the first class that differs once cursed and blessed are
mapped to draws (exact five-class agreement is counted too). `spot` asks the Lichess tablebase API (Syzygy, an
independent generator) about a stratified sample of this file, one request at a time, a minute's pause after any
HTTP 429 (KB tools.md §6.9), answers cached for a restart.

    heldout_67.py generate --source DIR --plan PLAN.tsv --manifest MANIFEST.jsonl --work DIR --out FILE.tsv
    heldout_67.py sample345 --syzygy DIR --out FILE.tsv [--n 100000] [--seed 2026111135]
    heldout_67.py verify345 FILE.tsv --source DIR --plan PLAN.tsv --manifest MANIFEST.jsonl --work DIR
    heldout_67.py spot FILE.tsv --cache FILE.jsonl [--n 300]
    heldout_67.py overlap FILE.tsv [--slices VF...] [--shards VF...] [--json OUT]
    heldout_67.py check FILE.tsv NET[=LAYOUT]... [--json OUT] [--paired REFERENCE_STEM]
    heldout_67.py report FILE.tsv CANDIDATE[=LAYOUT] --reference DEFAULT[=LAYOUT] [--json OUT]

`report` is the gate script's reported line (tools/nnue/gates.sh; never a gate, exit status 0 either way): both
nets' counts, their ratio, and a flag for the owner's review above endgame_heldout.FLAG_RATIO (1.15), the same
limit as the 4-5-piece check.
"""
import argparse
import hashlib
import json
import math
import os
import random
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import chess  # noqa: E402

import endgame_check  # noqa: E402
import endgame_heldout as eh  # noqa: E402

SEED = 2026111167
SEED_345 = 2026111135
PER_MATERIAL = 200
N_345 = 100_000
SPOT = 300
PROBER = 'noobpwnftw/python-chess@38c108efd992538dc078750cba9fee30b9f030ce (chess.chesstb)'
# Endgame slice v2's materials, budget R (design §3 table and owner's decision (b), 2026-11-09), by class.
CLASSES = {
    'C1': ['KRPvKRP', 'KRPPvKR', 'KRPPvKRP'],
    'C2': ['KRPvKBP', 'KRPvKNP', 'KRvKBPP', 'KRvKNPP', 'KRPPvKB', 'KRPPvKN', 'KRPPvKNP'],
    'C3': ['KQPvKQP', 'KQPPvKQ', 'KQvKRBP', 'KQvKRNP', 'KQPvKRR', 'KQvKRRP', 'KQPvKRB', 'KQPvKRN', 'KQPPPvKQ'],
    'C4': ['KBvKPPP', 'KNvKPPP', 'KRvKPPP', 'KBPvKPP', 'KNPvKPP', 'KRPvKPP', 'KQvKPPP', 'KBPvKPPP', 'KRvKPPPP'],
}
MATERIALS = [m for ms in CLASSES.values() for m in ms]
CLASS_OF = {m: c for c, ms in CLASSES.items() for m in ms}
HEADER = '# class\tmaterial\twdl (ChessTB, side to move)\tfen  -- tools/nnue/heldout_67.py generate'
LICHESS = 'https://tablebase.lichess.org/standard?fen='


def pieces(material):
    return len(material) - 1


def verdict(wdl):
    """+2 won, -2 lost, anything else (a cursed win, a blessed loss, a draw) drawn."""
    return 'won' if wdl == 2 else 'lost' if wdl == -2 else 'drawn'


def quiet(b):
    return (not b.is_check() and not any(b.is_capture(m) or m.promotion for m in b.legal_moves)
            and not b.is_game_over())


def random_position(rng, material, max_tries=1_000_000):
    """A random quiet position of `material` (first side White or Black at random) by the rules above."""
    first, second = material.split('v')
    for _ in range(max_tries):
        strong = rng.choice([chess.WHITE, chess.BLACK])
        ps = [(eh.KIND[p], strong) for p in first] + [(eh.KIND[p], not strong) for p in second]
        squares = rng.sample(range(64), len(ps))
        if any(kind == chess.PAWN and sq // 8 in (0, 7) for (kind, _), sq in zip(ps, squares)):
            continue
        b = chess.Board(None)
        for (kind, colour), sq in zip(ps, squares):
            b.set_piece_at(sq, chess.Piece(kind, colour))
        b.turn = rng.choice([chess.WHITE, chess.BLACK])
        if b.is_valid() and quiet(b):
            return b
    raise RuntimeError(f'no quiet {material} position in {max_tries} tries')


def positions(material, n=PER_MATERIAL, seed=SEED):
    """n distinct (board, side to move) positions of one material, in drawing order."""
    rng = random.Random(f'{seed}:{material}')
    out, seen = [], set()
    while len(out) < n:
        b = random_position(rng, material)
        k = eh.key(b)
        if k not in seen:
            seen.add(k)
            out.append(b)
    return out


# ------------------------------------------------------------------------------------------- tables and hashes
def table_name(material, available):
    """The ChessTB file of a material ('KRvKBPP' is stored as KBPPKR): either side first, exactly one on disk."""
    a, b = material.split('v')
    hits = sorted({f'{a}{b}.lzw', f'{b}{a}.lzw'} & set(available))
    if len(hits) != 1:
        raise FileNotFoundError(f'{material}: {len(hits)} table files among {a}{b}.lzw, {b}{a}.lzw')
    return hits[0]


def sha256_file(path, chunk=1 << 24):
    """SHA-256 of a file, dropping its pages from the page cache as it goes (WSL's memory is capped)."""
    h = hashlib.sha256()
    fd = os.open(path, os.O_RDONLY)
    try:
        done = 0
        while True:
            block = os.read(fd, chunk)
            if not block:
                break
            h.update(block)
            done += len(block)
            if hasattr(os, 'posix_fadvise') and done % (1 << 30) < chunk:
                os.posix_fadvise(fd, 0, done, os.POSIX_FADV_DONTNEED)
        if hasattr(os, 'posix_fadvise'):
            os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
    finally:
        os.close(fd)
    return h.hexdigest()


def load_records(plan, manifest):
    """{bucket path: (plan bytes, manifest sha256)} from the download's plan.tsv and manifest.jsonl."""
    sizes = {}
    for line in Path(plan).read_text(encoding='utf-8').splitlines()[1:]:
        if line.strip():
            f = line.split('\t')
            sizes[f[3]] = int(f[4])
    shas = {}
    for line in Path(manifest).read_text(encoding='utf-8').splitlines():
        if line.strip():
            r = json.loads(line)
            shas[r['path']] = r['sha256']
    return {p: (sizes[p], shas.get(p)) for p in sizes}


def checked(source, rel, records, work):
    """The table file at source/rel after its size and SHA-256 are checked against the records (cached in
    work/verified.json by size and modification time, so a restart does not hash again)."""
    path = Path(source) / rel
    size, sha = records[rel]
    if sha is None:
        raise RuntimeError(f'{rel}: no SHA-256 in the manifest')
    st = path.stat()
    if st.st_size != size:
        raise RuntimeError(f'{rel}: {st.st_size} bytes, the plan says {size}')
    Path(work).mkdir(parents=True, exist_ok=True)
    cache_path = Path(work) / 'verified.json'
    cache = json.loads(cache_path.read_text(encoding='utf-8')) if cache_path.exists() else {}
    stamp = f'{st.st_size}:{st.st_mtime_ns}'
    if cache.get(rel, {}).get('stamp') != stamp or cache[rel]['sha256'] != sha:
        t0 = time.time()
        got = sha256_file(path)
        if got != sha:
            raise RuntimeError(f'{rel}: SHA-256 {got}, the manifest says {sha}')
        cache[rel] = {'stamp': stamp, 'sha256': got}
        tmp = cache_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(cache, indent=1, sort_keys=True) + '\n', encoding='utf-8')
        os.replace(tmp, cache_path)
        print(f'{rel}: {size} bytes, SHA-256 {got} matches the manifest ({time.time() - t0:.0f} s)', flush=True)
    return path


def link_dir(work, name, files):
    """work/tb/name/wdl/ holding only links to `files`: the prober then sees those tables and nothing else."""
    d = Path(work) / 'tb' / name / 'wdl'
    d.mkdir(parents=True, exist_ok=True)
    want = {Path(f).name: Path(f) for f in files}
    for p in d.iterdir():
        if p.name not in want:
            raise RuntimeError(f'{p}: an unexpected file in the probe directory')
    for n, f in want.items():
        if not (d / n).is_symlink():
            os.symlink(f, d / n)
        elif Path(os.readlink(d / n)) != f:
            raise RuntimeError(f'{d / n} links elsewhere')
    return d.parent


# ------------------------------------------------------------------------------------------------------ generate
def generate(source, plan, manifest, work, out, per_material=PER_MATERIAL, seed=SEED):
    """Every material's positions and labels; a material's rows go to work/parts/MATERIAL.tsv when it finishes,
    and a restart skips the materials already done."""
    import chess.chesstb
    records = load_records(plan, manifest)
    available = [Path(p).name for p in records if p.startswith('full/wdl/')]
    parts = Path(work) / 'parts'
    parts.mkdir(parents=True, exist_ok=True)
    for material in MATERIALS:
        part = parts / f'{material}.tsv'
        if part.exists():
            continue
        rel = 'full/wdl/' + table_name(material, available)
        path = checked(source, rel, records, work)
        t0 = time.time()
        boards = positions(material, per_material, seed)
        t1 = time.time()
        with chess.chesstb.open_tablebase(str(link_dir(work, material, [path]))) as tb:
            wdl = [tb.probe_wdl(b) for b in boards]
        t2 = time.time()
        lines = [f'{CLASS_OF[material]}\t{material}\t{w}\t{b.fen()}' for w, b in zip(wdl, boards)]
        tmp = part.with_suffix('.tmp')
        tmp.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
        os.replace(tmp, part)
        c = Counter(verdict(w) for w in wdl)
        print(f'{material} ({rel}): {len(boards)} positions in {t1 - t0:.1f} s, probed in {t2 - t1:.2f} s '
              f'({len(boards) / max(t2 - t1, 1e-9):.0f}/s); won {c["won"]}, drawn {c["drawn"]}, lost {c["lost"]}, '
              f'cursed/blessed {sum(1 for w in wdl if w in (1, -1))}', flush=True)
    rows = []
    for material in MATERIALS:
        rows += (parts / f'{material}.tsv').read_text(encoding='utf-8').splitlines()
    Path(out).write_text('\n'.join([HEADER] + rows) + '\n', encoding='utf-8', newline='\n')
    print(f'{len(rows)} positions written to {out}', flush=True)


def read(path):
    """[(class, material, wdl, board)]."""
    rows = []
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if line and not line.startswith('#'):
            cls, material, wdl, fen = line.split('\t')
            rows.append((cls, material, int(wdl), chess.Board(fen)))
    return rows


# -------------------------------------------------------------------------------------------- 3-5-piece check
def syzygy_materials(syzygy):
    return sorted(p.stem for p in Path(syzygy).glob('*.rtbw'))


def random_legal(rng, material):
    """A random legal position of a 'KRPvKR'-style material, either colour first, any side to move."""
    first, second = material.split('v')
    if rng.random() < 0.5:
        first, second = second, first
    ps = [(eh.KIND[p], chess.WHITE) for p in first] + [(eh.KIND[p], chess.BLACK) for p in second]
    while True:
        squares = rng.sample(range(64), len(ps))
        if any(kind == chess.PAWN and sq // 8 in (0, 7) for (kind, _), sq in zip(ps, squares)):
            continue
        b = chess.Board(None)
        for (kind, colour), sq in zip(ps, squares):
            b.set_piece_at(sq, chess.Piece(kind, colour))
        b.turn = rng.choice([chess.WHITE, chess.BLACK])
        if b.is_valid():
            return b


def sample345(syzygy, out, n=N_345, seed=SEED_345):
    import chess.syzygy
    mats = syzygy_materials(syzygy)
    rng = random.Random(seed)
    lines = [f'# material\twdl (Syzygy, side to move)\tfen  -- tools/nnue/heldout_67.py sample345, seed {seed}']
    with chess.syzygy.open_tablebase(syzygy) as tb:
        for _ in range(n):
            m = rng.choice(mats)
            b = random_legal(rng, m)
            lines.append(f'{m}\t{tb.probe_wdl(b)}\t{b.fen()}')
    Path(out).write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
    print(f'{n} positions of {len(mats)} materials written to {out}')


def verify345(sample, source, plan, manifest, work):
    import chess.chesstb
    records = load_records(plan, manifest)
    rels = sorted(p for p in records if p.startswith('wdl/'))
    paths = [checked(source, rel, records, work) for rel in rels]
    pairs, first_bad = Counter(), None
    rows = [line.split('\t') for line in Path(sample).read_text(encoding='utf-8').splitlines()
            if line and not line.startswith('#')]
    t0 = time.time()
    with chess.chesstb.open_tablebase(str(link_dir(work, 'shipping-345', paths))) as tb:
        for m, s, fen in rows:
            got = tb.probe_wdl(chess.Board(fen))
            pairs[(int(s), got)] += 1
            if verdict(int(s)) != verdict(got):
                first_bad = (m, int(s), got, fen)
                break
    exact = sum(c for (a, b), c in pairs.items() if a == b)
    total = sum(pairs.values())
    report = {'positions': total, 'of': len(rows), 'tables': len(paths), 'exact_agree': exact,
              'mapped_agree': sum(c for (a, b), c in pairs.items() if verdict(a) == verdict(b)),
              'pairs (syzygy, chesstb)': {f'{a},{b}': c for (a, b), c in sorted(pairs.items())},
              'first_disagreement': first_bad, 'seconds': round(time.time() - t0), 'prober': PROBER}
    print(json.dumps(report, indent=1))
    return 1 if first_bad else 0


# ------------------------------------------------------------------------------------------------ Lichess check
LICHESS_WDL = {'win': 2, 'cursed-win': 1, 'draw': 0, 'blessed-loss': -1, 'loss': -2}


def spot_sample(rows, n=SPOT, seed=SEED):
    """n rows stratified by class (n / 4 each), seeded."""
    rng = random.Random(f'{seed}:spot')
    out = []
    for cls in CLASSES:
        idx = [i for i, r in enumerate(rows) if r[0] == cls]
        out += sorted(rng.sample(idx, n // len(CLASSES)))
    return out


def spot(rows, cache, n=SPOT, pause=1.0):
    import urllib.error
    import urllib.parse
    import urllib.request
    done = {}
    if Path(cache).exists():
        for line in Path(cache).read_text(encoding='utf-8').splitlines():
            r = json.loads(line)
            done[r['fen']] = r
    for i in spot_sample(rows, n):
        fen = rows[i][3].fen()
        if fen in done:
            continue
        while True:
            req = urllib.request.Request(LICHESS + urllib.parse.quote(fen),
                                         headers={'User-Agent': 'Fork chess engine held-out check (one at a time)'})
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    body = json.loads(resp.read().decode('utf-8'))
                break
            except urllib.error.HTTPError as e:
                if e.code != 429:
                    raise
                print('HTTP 429: pausing 60 s', flush=True)
                time.sleep(60)
        r = {'fen': fen, 'category': body.get('category'), 'dtz': body.get('dtz')}
        done[fen] = r
        with open(cache, 'a', encoding='utf-8', newline='\n') as f:
            f.write(json.dumps(r) + '\n')
        time.sleep(pause)
    pairs, bad = Counter(), []
    for i in spot_sample(rows, n):
        cls, material, wdl, b = rows[i]
        cat = done[b.fen()]['category']
        lw = LICHESS_WDL.get(cat)
        pairs[(wdl, cat)] += 1
        if lw is None or verdict(lw) != verdict(wdl):
            bad.append({'material': material, 'fen': b.fen(), 'chesstb': wdl, 'lichess': cat})
    exact = sum(c for (w, cat), c in pairs.items() if LICHESS_WDL.get(cat) == w)
    report = {'positions': sum(pairs.values()), 'exact_agree': exact,
              'mapped_agree': sum(pairs.values()) - len(bad), 'disagreements': bad,
              'pairs (chesstb, lichess)': {f'{w},{c}': k for (w, c), k in sorted(pairs.items())},
              'by_pieces': dict(Counter(pieces(rows[i][1]) for i in spot_sample(rows, n)))}
    print(json.dumps(report, indent=1))
    return 1 if bad else 0


# ------------------------------------------------------------------------------------------------------ overlap
def overlap(rows, slices, shards):
    import heldout_deep as hd
    report = {}
    if slices:
        rep = eh.overlap([(cls, wdl, b) for cls, _, wdl, b in rows], slices)
        report['slices'] = {'files': rep['files'], 'found': rep['matches']['held-out']['found_in_any_file'],
                            'held_out_classes_in_slice': rep['held_out_classes_in_slice'],
                            'piece_counts': rep['piece_counts']}
    if shards:
        saved = hd.PIECES
        hd.PIECES = range(6, 8)
        try:
            rep, found = hd.overlap([{'fen': b.fen()} for *_, b in rows], shards)
        finally:
            hd.PIECES = saved
        report['shards'] = rep
    found = (report.get('slices', {}).get('found', 0) + len(report.get('slices', {}).get(
        'held_out_classes_in_slice', {})) + report.get('shards', {}).get('found', 0))
    return report, found


# -------------------------------------------------------------------------------------------------------- check
def misjudged_vectors(rows, nets):
    """{net stem: [misjudged per position]}."""
    import models
    import netformat
    out = {}
    for arg in nets:
        path, _, lay = arg.partition('=')
        desc = netformat.layout(lay or str(HERE / 's512pp.json'))
        data = Path(path).read_bytes()
        arch = models.arch_from_net(desc['name'], data[netformat.HEADER_BYTES:])
        net = models.unpack(arch, data[netformat.HEADER_BYTES:])
        scale = netformat.header_fields(data)['scale']
        out[Path(path).stem] = [endgame_check.misjudged(verdict(wdl), models.r_int(arch, net, scale, b))
                                for _, _, wdl, b in rows]
    return out


def sign_test(b, c):
    """Two-sided exact sign test on b against c discordant positions."""
    n = b + c
    return min(1.0, 2 * sum(math.comb(n, k) for k in range(0, min(b, c) + 1)) / 2 ** n) if n else 1.0


def tables(rows, vecs):
    res = {}
    for name, v in vecs.items():
        t = {}
        for (cls, material, wdl, _), bad in zip(rows, v):
            for k in ((material, verdict(wdl)), (cls, 'all'), (f'{pieces(material)}-piece', 'all'), ('all', 'all')):
                cell = t.setdefault(k, [0, 0])
                cell[0] += 1
                cell[1] += bad
        res[name] = t
    return res


def print_check(rows, vecs, paired=None):
    res = tables(rows, vecs)
    names = list(vecs)
    first = res[names[0]]
    print(f'{"material":9} {"result":6} {"positions":>9}  ' + '  '.join(f'{n:>10}' for n in names))
    for material in MATERIALS:
        for kind in ('won', 'drawn', 'lost'):
            if (material, kind) in first:
                print(f'{material:9} {kind:6} {first[(material, kind)][0]:>9}  '
                      + '  '.join(f'{res[n][(material, kind)][1]:>10}' for n in names))
    for group in list(CLASSES) + ['6-piece', '7-piece', 'all']:
        k = (group, 'all')
        print(f'{group:9} {"all":6} {first[k][0]:>9}  ' + '  '.join(f'{res[n][k][1]:>10}' for n in names))
    out = {'nets': {n: {f'{a} {b}': v for (a, b), v in t.items()} for n, t in res.items()}}
    if paired:
        ref = vecs[paired]
        out['paired'] = {}
        for n in names:
            if n == paired:
                continue
            b = sum(x and not y for x, y in zip(ref, vecs[n]))
            c = sum(y and not x for x, y in zip(ref, vecs[n]))
            p = sign_test(b, c)
            out['paired'][n] = {f'{paired}_only': b, f'{n}_only': c, 'sign_test_p': round(p, 4)}
            print(f'{paired} vs {n}: {paired} alone misjudges {b}, {n} alone {c}, two-sided sign test p = {p:.4f}')
    return out


def flag_line(cand, ct, ref, rt, limit=None):
    limit = eh.FLAG_RATIO if limit is None else limit
    ratio = ct / rt if rt else float('inf') if ct else 1.0
    flagged = ratio > limit
    return (f'held-out 6-7-piece check: {cand} {ct} misjudged, the default {ref} {rt}, ratio {ratio:.3f}: '
            + (f"FLAG for the owner's review (a rise of more than {100 * (limit - 1):.0f}%)" if flagged
               else f'within the flag limit ({limit:.2f})')), flagged


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    g = sub.add_parser('generate')
    for p in (g, sub.add_parser('verify345')):
        if p is not g:
            p.add_argument('sample')
        p.add_argument('--source', required=True, help='the ChessTB download folder (holding wdl/ and full/wdl/)')
        p.add_argument('--plan', required=True)
        p.add_argument('--manifest', required=True)
        p.add_argument('--work', required=True, help='a folder of this tool (probe links, parts, hash cache)')
    g.add_argument('--out', required=True)
    g.add_argument('--per-material', type=int, default=PER_MATERIAL)
    g.add_argument('--seed', type=int, default=SEED)
    s = sub.add_parser('sample345')
    s.add_argument('--syzygy', required=True)
    s.add_argument('--out', required=True)
    s.add_argument('--n', type=int, default=N_345)
    s.add_argument('--seed', type=int, default=SEED_345)
    sp = sub.add_parser('spot')
    sp.add_argument('positions')
    sp.add_argument('--cache', required=True)
    sp.add_argument('--n', type=int, default=SPOT)
    o = sub.add_parser('overlap')
    o.add_argument('positions')
    o.add_argument('--slices', nargs='*', default=[])
    o.add_argument('--shards', nargs='*', default=[])
    o.add_argument('--json')
    c = sub.add_parser('check')
    c.add_argument('positions')
    c.add_argument('nets', nargs='+')
    c.add_argument('--paired', help='the net (file stem) the others are compared with, position by position')
    c.add_argument('--json')
    r = sub.add_parser('report')
    r.add_argument('positions')
    r.add_argument('candidate')
    r.add_argument('--reference', required=True)
    r.add_argument('--flag-ratio', type=float, default=eh.FLAG_RATIO)
    r.add_argument('--json')
    a = ap.parse_args(argv)
    if a.cmd == 'generate':
        generate(a.source, a.plan, a.manifest, a.work, a.out, a.per_material, a.seed)
        return 0
    if a.cmd == 'sample345':
        sample345(a.syzygy, a.out, a.n, a.seed)
        return 0
    if a.cmd == 'verify345':
        return verify345(a.sample, a.source, a.plan, a.manifest, a.work)
    rows = read(a.positions)
    if a.cmd == 'spot':
        return spot(rows, a.cache, a.n)
    if a.cmd == 'overlap':
        rep, found = overlap(rows, a.slices, a.shards)
        if a.json:
            Path(a.json).write_text(json.dumps(rep, indent=1) + '\n', encoding='utf-8')
        print(json.dumps({'found': found, 'slices': {k: v for k, v in rep.get('slices', {}).items() if k != 'files'},
                          'shards': {k: v for k, v in rep.get('shards', {}).items() if k != 'files'}}))
        return 1 if found else 0
    if a.cmd == 'check':
        vecs = misjudged_vectors(rows, a.nets)
        out = print_check(rows, vecs, a.paired)
        if a.json:
            Path(a.json).write_text(json.dumps(out, indent=1) + '\n', encoding='utf-8')
        return 0
    vecs = misjudged_vectors(rows, [a.candidate, a.reference])
    cand, ref = list(vecs) if len(vecs) == 2 else (list(vecs)[0], list(vecs)[0] + ' (reference)')
    ct = sum(vecs[cand])
    rt = sum(vecs[list(vecs)[-1]])
    line, flagged = flag_line(cand, ct, ref, rt, a.flag_ratio)
    print_check(rows, vecs)
    print(line)
    if a.json:
        Path(a.json).write_text(json.dumps({'candidate': cand, 'candidate_misjudged': ct, 'reference': ref,
                                            'reference_misjudged': rt, 'positions': len(rows),
                                            'ratio': ct / rt if rt else None, 'flag_ratio': a.flag_ratio,
                                            'flagged': flagged}, indent=1) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
