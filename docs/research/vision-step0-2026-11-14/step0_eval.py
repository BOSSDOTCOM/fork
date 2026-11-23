# SPDX-License-Identifier: GPL-3.0-or-later
"""Vision step 0 (ideas.md 185): a network's output on every position of a `fork-train dump`, in Fork's integer
arithmetic (tools/nnue/models.py's features, regions, links and phase bucket; the sums, clipped squares and output in
numpy, as idea 175's and idea 178's studies computed them), for the squared-output family: S512 (architecture 2,
S512r2), S512+PP (8: r8brft1, r3pp1) and H512+PP (9: r3kr1).

Saves y (the output before the scale: the trainer-space prediction is sigmoid(y / (QA * QB))), the evaluation in
centipawns and the net's output bucket. With --hidden FILE, also the 1,024 clipped hidden values v (uint8, the side
to move's 512 then the other side's) of every position as a raw n x 1024 file, for the head refits.

Checks: on every --check-every-th position the centipawns against models.r_int (the integer reference the
trainer-engine parity test holds to the engine); with --fork BIN (a build whose embedded net is NET) against
`BIN evalfens` on every --fork-every-th position.

    step0_eval.py DUMP --net NET.fnet --out OUT.npz [--hidden V.u8] [--fork BIN] [--workers 3]
"""
import argparse
import ctypes
import json
import os
import subprocess
import sys
import time
from multiprocessing import Pool
from pathlib import Path

for var in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[var] = '1'

import numpy as np  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import step0_common as sc  # noqa: E402

sys.path.insert(0, str(sc.REPO / 'tools' / 'nnue'))
import models  # noqa: E402
import netformat  # noqa: E402

EVAL_LIMIT = 20000
NAMES = {2: 's512', 8: 's512pp', 9: 'h512pp'}
G = {}


def below_normal():
    if sys.platform == 'win32':
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)


def load(path):
    data = Path(path).read_bytes()
    head = netformat.header_fields(data)
    name = NAMES[head['architecture']]
    payload = data[netformat.HEADER_BYTES:]
    arch = models.arch_from_net(name, payload)
    net = models.unpack(arch, payload)
    return arch, net, head['scale']


def init(path):
    below_normal()
    arch, net, scale = load(path)
    G.update(arch=arch, net=net, scale=scale,
             ftw=np.frombuffer(bytes(net['ftw']), dtype='<i2').reshape(-1, 512),
             ftb=np.array(net['ftb'], dtype=np.int32),
             outw=np.array(net['outw'], dtype=np.int64).reshape(8, 2, 512),
             outb=np.array(net['outb'], dtype=np.int64))


def trunc_div(a, b):
    return np.sign(a) * (np.abs(a) // b)


def work(job):
    start, packed_list, check_every, want_hidden = job
    arch, ftw, ftb, outw, outb, scale = G['arch'], G['ftw'], G['ftb'], G['outw'], G['outb'], G['scale']
    rows, starts = [], []
    m = len(packed_list)
    buckets = np.zeros(m, dtype=np.int64)
    checks = []
    for i, packed in enumerate(packed_list):
        b = sc.board_of(packed)
        stm, ntm, k = models.both_perspectives(arch, b)
        starts.append(len(rows))
        rows.extend(models.saved_features(arch, stm))
        starts.append(len(rows))
        rows.extend(models.saved_features(arch, ntm))
        buckets[i] = k
        if check_every and (start + i) % check_every == 0:
            checks.append((i, models.r_int(arch, G['net'], scale, b)))
    sums = np.add.reduceat(ftw[np.array(rows)].astype(np.int32), np.array(starts), axis=0) + ftb
    assert sums.min() >= -32768 and sums.max() <= 32767
    v = np.clip(sums, 0, sc.QA).astype(np.int64).reshape(m, 2, 512)
    total = np.einsum('mhj,mhj->m', v, v * outw[buckets])
    ys = trunc_div(total, sc.QA) + outb[buckets]
    cp = np.clip(trunc_div(ys * scale, sc.QA * sc.QB), -(EVAL_LIMIT - 1), EVAL_LIMIT - 1)
    bad = sum(int(cp[i] != want) for i, want in checks)
    hidden = v.reshape(m, 1024).astype(np.uint8) if want_hidden else None
    return start, ys, cp, buckets, hidden, len(checks), bad


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('dump')
    ap.add_argument('--net', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--hidden')
    ap.add_argument('--fork')
    ap.add_argument('--fork-every', type=int, default=20)
    ap.add_argument('--check-every', type=int, default=500)
    ap.add_argument('--workers', type=int, default=3)
    ap.add_argument('--chunk', type=int, default=2000)
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args(argv)
    below_normal()
    t0 = time.time()
    positions, _ = sc.read_dump(a.dump, a.limit)
    n = len(positions)
    ys = np.zeros(n, dtype=np.int64)
    cp = np.zeros(n, dtype=np.int64)
    buckets = np.zeros(n, dtype=np.int8)
    hidden = np.memmap(a.hidden, dtype=np.uint8, mode='w+', shape=(n, 1024)) if a.hidden else None
    checked = bad = 0
    jobs = [(c0, positions[c0:c0 + a.chunk], a.check_every, bool(a.hidden)) for c0 in range(0, n, a.chunk)]
    with Pool(a.workers, initializer=init, initargs=(a.net,)) as pool:
        for k, (start, y, c, bk, h, nc, nb) in enumerate(pool.imap(work, jobs)):
            e = start + len(y)
            ys[start:e], cp[start:e], buckets[start:e] = y, c, bk
            if hidden is not None:
                hidden[start:e] = h
            checked += nc
            bad += nb
            if k % 50 == 0:
                print(f'{e} / {n}, {time.time() - t0:.0f} s', flush=True)
    if hidden is not None:
        hidden.flush()
        del hidden
    report = {'dump': os.path.basename(a.dump), 'net': os.path.basename(a.net), 'positions': n,
              'r_int_check': {'checked': checked, 'mismatches': bad}}
    if a.fork:
        idx = list(range(0, n, a.fork_every))
        fens = ''.join(sc.board_of(positions[i]).fen() + '\n' for i in idx)
        got = subprocess.run([a.fork, 'evalfens'], input=fens, capture_output=True, text=True, check=True).stdout
        got = np.array([int(x) for x in got.split()])
        report['evalfens_check'] = {'checked': len(idx), 'mismatches': int((got != cp[idx]).sum())}
    np.savez(a.out, ys=ys, cp=cp, buckets=buckets)
    report['seconds'] = round(time.time() - t0)
    Path(a.out.rsplit('.', 1)[0] + '.json').write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))


if __name__ == '__main__':
    main()
