# SPDX-License-Identifier: GPL-3.0-or-later
"""Generates tools/train/kaggle/retrain_8b_rft.py (idea 70, docs/research/retrain-8b/rft-plan.md) from retrain 8b's
own kernel (tools/train/kaggle/retrain_8b.py at 8b's launch commit 320c0be), as the cw kernel was made: every
replacement below is exact (asserted once), so everything not named here is 8b's. test_rft_kernel.py regenerates
the kernel and compares it byte for byte.

    python -I tools/train/kaggle/make_rft_kernel.py tools/train/kaggle/retrain_8b.py tools/train/kaggle/retrain_8b_rft.py
"""
import sys

src, dest = sys.argv[1], sys.argv[2]
s = open(src, encoding='utf-8').read()


def rep(a, b):
    global s
    assert s.count(a) == 1, a[:80]
    s = s.replace(a, b)


head_end = s.index('import glob\n')
s = '''# SPDX-License-Identifier: GPL-3.0-or-later

"""Idea 70, the result fine-tune of retrain 8b's winner (owner, 2026-11-10; docs/research/retrain-8b/rft-plan.md), on
Kaggle (GPU T4 x2). Made from retrain 8b's own kernel (tools/train/kaggle/retrain_8b.py at 8b's launch commit 320c0be)
by one script with exact replacements, so everything but the arms is 8b's: architecture s512pp, S = 92, AdamW, batch
16,384 x 305 per superbatch, read interleaved, validation g4s1-val.vf (its first 20,000 positions per superbatch, for
monitoring); the same 16 datasets and input checks (every file's SHA-256 against the manifests), the same window
average and quantisation, the same offline files.

The arms (declared in rft-plan.md before any result): rft1 and rft2, seeds 1 and 2 side by side (one T4 each), warm
from the winner's window average (8b's candidate itself, float weights from 8b's session output, dataset
fork-r8b-rft-init), at --result-weight 1.0 (the game result alone), LR 1e-5 constant for 60 superbatches, on arm c's
129 files (at result weight 1 every copy of a position carries the same target, so the originals serve any winner).
Each arm's candidate is <arm>-avg, the mean of superbatches 46-60's float weights. WINNER names the base net (td90 if
8b's first SPRT passes; c if the second does; the owner names one otherwise).

Validity (blocking; summary['validity']): 8b's inputs check; the winner's weights reproduce their own g4s1-val prefix
loss from 8b's session (result weight 0.5) within 1e-6; each arm's superbatch 0 equals the winner's prefix loss at
result weight 1.0 (computed in this session) within 1e-6.

Offline: the winner and every candidate on all of g4s1-val.vf and its prefix at result weight 0.5 (8b's diagnostic)
and on all of it at 1.0 ('full_result'), on idea 52's evaluation files; the trainer's parity outputs per candidate.

    python3 retrain_8b_rft.py                      # on Kaggle
    python retrain_8b_rft.py --plan                # anywhere: the settings and the arms' commands; touches nothing
    python retrain_8b_rft.py --check-inputs DIR... # anywhere: the input checks and the arms' file lists
"""
''' + s[head_end:]
rep("COMMIT = 'phase-4'          # replaced by the pushed commit's hash (holding g4.json and r8b-g4.json) before the push",
    "COMMIT = 'phase-4'          # replaced by the pushed commit's hash before the push")
rep("SUPERBATCHES = 360\n", "SUPERBATCHES = 60            # rft-plan.md section 3: about a third of a pass, no position twice\n")
old_init = s[s.index('# S512ppr3\'s float weights (item 8a\'s R1-avg)'):s.index('TOLERANCE = 1e-6')]
rep(old_init, '''# The window averages of 8b (float weights from fork-retrain-8b's output, dataset fork-r8b-rft-init), each checked by
# reproducing its own g4s1-val prefix loss of 8b's session (offline, result weight 0.5).
WINNER = 'td90'             # rft-plan.md section 1: td90 if r8b-stc-1 passes; the chain sets it before the push
INITS = {
    'c': {'weights': 'r8b-c-avg.bin', 'sha256': '162f3f4acf34ead2c921617e2bd64c6dcd4d5cba4bfb4b46937809fad3ceee25',
          'val': 'g4s1-val.vf', 'loss': 0.01940656},
    'i52': {'weights': 'r8b-i52-avg.bin', 'sha256': '87976b596a13d08e8252d7148dbdc6a0458cd8d8148a4f401a011e99561d3056',
            'val': 'g4s1-val.vf', 'loss': 0.01939691},
    'td80': {'weights': 'r8b-td80-avg.bin', 'sha256': '0116a9e6c676323bb56a75233e543ef7f9268c51c33fddf77b4bf6e29259e4cc',
             'val': 'g4s1-val.vf', 'loss': 0.01938677},
    'td90': {'weights': 'r8b-td90-avg.bin', 'sha256': 'b5ae40056f943d4407fef453f3034a52baddb9e441b7ba352772831904bfe7c1',
             'val': 'g4s1-val.vf', 'loss': 0.01938369},
}
INIT = INITS[WINNER]
NO_DROP = 10 ** 6           # an --lr-step no run reaches: a constant LR (8a's kernel)
''')
rep("WINDOW = (331, 360)\nKEEP = {180, 360}\n", "WINDOW = (46, 60)           # the last 15 superbatches, as 8a's 60-superbatch arm D1\nKEEP = {60}\n")
old_arms = s[s.index('ARMS = {\n'):s.index("DATA = '/kaggle/input'")]
rep(old_arms, '''ARMS = {
    'rft1': {'files': 'control', 'init': True, 'lr': 1e-5, 'lr_step': NO_DROP, 'result_weight': 1.0, 'val': VAL, 'seed': 1},
    'rft2': {'files': 'control', 'init': True, 'lr': 1e-5, 'lr_step': NO_DROP, 'result_weight': 1.0, 'val': VAL, 'seed': 2},
}
SEED = 1
QUEUES = [['rft1'], ['rft2']]
CANDIDATES = ['rft1', 'rft2']
''')
rep("--lr-step {a[\"lr_step\"]} --seed {SEED} '", "--lr-step {a[\"lr_step\"]} --seed {a.get(\"seed\", SEED)} '")
rep("""    print(json.dumps({'commit': COMMIT, 'arch': ARCH, 'scale': SCALE, 'manifests': MANIFESTS, 'init': INIT,""",
    """    print(json.dumps({'commit': COMMIT, 'arch': ARCH, 'scale': SCALE, 'manifests': MANIFESTS, 'winner': WINNER,
                      'init': INIT, 'superbatches': SUPERBATCHES,""")
rep("""                'manifests': MANIFESTS, 'init': INIT, 'window': WINDOW, 'keep': sorted(KEEP), 'seed': SEED}""",
    """                'manifests': MANIFESTS, 'winner': WINNER, 'init': INIT, 'window': WINDOW, 'keep': sorted(KEEP),
                'seed': SEED}""")
rep("""        c['reference'] = score(init[0], by_name[VAL], VAL_POSITIONS, f'{WORK}/init-ref')""",
    """        # The arms' superbatch 0 is the winner at their own result weight (1.0): the reference is that.
        c['reference'] = score(init[0], by_name[VAL], VAL_POSITIONS, f'{WORK}/init-ref', result_weight=1.0)""")
rep("""        nets = {'s512ppr3': init[0]}""", """        nets = {f'{WINNER}-avg (base)': init[0]}""")
rep("""                         'prefix': score(w, by_name[VAL], VAL_POSITIONS, f'{WORK}/s-{name}-p'),""",
    """                         'prefix': score(w, by_name[VAL], VAL_POSITIONS, f'{WORK}/s-{name}-p'),
                         'full_result': score(w, by_name[VAL], ALL_POSITIONS, f'{WORK}/s-{name}-r', result_weight=1.0),""")
rep("""            if name.endswith('-avg'):""", """            if name.endswith('-avg') and not name.startswith(WINNER):""")
# Offline output folders must not collide with the base's name; 'name' strings with spaces are used in paths:
rep("""            res[name] = {'full': score(w, by_name[VAL], ALL_POSITIONS, f'{WORK}/s-{name}'),""",
    """            tag = name.split()[0]
            res[name] = {'full': score(w, by_name[VAL], ALL_POSITIONS, f'{WORK}/s-{tag}'),""")
s = s.replace("f'{WORK}/s-{name}-p'", "f'{WORK}/s-{tag}-p'").replace("f'{WORK}/s-{name}-r'", "f'{WORK}/s-{tag}-r'")
s = s.replace("f'{WORK}/s-{name}-h'", "f'{WORK}/s-{tag}-h'").replace("f'{WORK}/s-{name}-k'", "f'{WORK}/s-{tag}-k'")
# 8b's score() and quantise() read one data file from arm c's list; this kernel's arms are rft1 and rft2 (the same
# 129 files).
assert s.count('lists["c"][0]') == 2
s = s.replace('lists["c"][0]', 'lists[CANDIDATES[0]][0]')
rep("""    print('offline: each arm\\'s window mean, quantised; S512ppr3 and the candidates scored (result weight 0.5) on '""",
    """    print('offline: each arm\\'s window mean, quantised; the winner and the candidates scored (result weight 0.5) on '""")
open(dest, 'w', encoding='utf-8', newline='\n').write(s)
print('written', dest)
