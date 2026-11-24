"""One-off edit: round 3's warm-start SOURCE becomes r8ceplo2 (owner, 2026-11-14 ~5:55 PM EST)."""
import sys
from pathlib import Path

wt = Path(sys.argv[1])


def edit(rel, pairs):
    p = wt / rel
    s = p.read_text(encoding='utf-8')
    for a, b in pairs:
        assert s.count(a) == 1, (rel, a[:70])
        s = s.replace(a, b)
    p.write_text(s, encoding='utf-8', newline='\n')


edit('tools/train/kaggle/bakeoff_r3.py', [
    ("alongside it; warm-start from 8c's winner once promoted, r8brft1 otherwise. Written from retrain 8c's kernel",
     "alongside it; warm-start from 8c's winner once promoted, r8brft1 otherwise (8c's winner r8ceplo2, the default\n"
     "since 2026-11-14, is SOURCE for all round 3 training from then on: owner, ~5:55 PM EST). Written from retrain 8c's\n"
     "kernel"),
    ("""SOURCE (the owner's decision 6): r8brft1's float weights (retrain 8b's result fine-tune, its rft1 window average:
Kaggle kernel fork-retrain-8b-rft version 1's avg-rft1/weights.bin), to be uploaded as the dataset named in SOURCE; if
retrain 8c's winner is promoted first, SOURCE becomes that arm's window average (its avg-<arm>/weights.bin) by one edit
of SOURCE (name, file, SHA-256). Either is an S512+PP net's float weights.""",
     """SOURCE (the owner's decision 6, and his order of 2026-11-14 ~5:55 PM EST: "set the warm-start source for all future
round 3 training to r8ceplo2, using its float weights from 8c's A1 outputs"): r8ceplo2's float window average (retrain
8c session A1's arm eplo2, its avg-eplo2/weights.bin), the file r8ceplo2-avg.bin of the dataset fork-r3-init-8c.
Checked before use (2026-11-14): those weights, quantised (bullet's save list, and the reference's redo of it: the
same bytes) and converted at r8ceplo2's S = 87 with its one link weight clamped (tools/nnue/pp_bound.py), are
nets/r8ceplo2.fnet byte for byte (SHA-256 f4634cec...7d49f5a), and a build with them gives r8ceplo2's bench (5,403,414
/ 34c916638218aa11) with netcheck exact on tests/nnue/r8ceplo2.parity. Before that, SOURCE was r8brft1's float weights
(fork-retrain-8b-rft v1's avg-rft1/weights.bin, dataset fork-r3-kr4-init: round 3's first sessions were launched from
r8ceplo2 by an explicit --source). Another source is one edit of SOURCE (name, file, SHA-256, dataset); it must be an
S512+PP net's float weights."""),
    ("""# The source net's float weights (module note): r8brft1's until 8c's winner is promoted.
SOURCE = {'name': 'r8brft1', 'weights': 'r8brft1-avg.bin',
          'sha256': '2d70ebccb6e6eb7d192faea0e16bee5c1aa2169c0346f3791e5d6bb27ae1dba1',
          'dataset': 'fork-r3-kr4-init'}""",
     """# The source net's float weights (module note): r8ceplo2's (8c's winner, the default since 2026-11-14).
SOURCE = {'name': 'r8ceplo2', 'weights': 'r8ceplo2-avg.bin',
          'sha256': '4118015e47ca596a966ee29821a43ae613155af9b0c9a95913d6fc81e06f3539',
          'dataset': 'fork-r3-init-8c'}"""),
])
edit('tools/train/kaggle/test_bakeoff_r3.py', [
    ("""    def test_the_source_is_r8brft1s_float_weights(self):
        # r8brft1's window average (fork-retrain-8b-rft v1, avg-rft1/weights.bin), SHA-256 checked on this machine
        # 2026-11-14 (its quantised layers are nets/r8brft1.fnet's but its one clamped link weight).
        self.assertEqual(k.SOURCE['name'], 'r8brft1')
        self.assertEqual(k.SOURCE['sha256'], '2d70ebccb6e6eb7d192faea0e16bee5c1aa2169c0346f3791e5d6bb27ae1dba1')""",
     """    def test_the_source_is_r8ceplo2s_float_weights(self):
        # Owner, 2026-11-14 ~5:55 PM EST: r8ceplo2 is round 3's warm-start source from then on. Its window average
        # (retrain 8c A1's avg-eplo2/weights.bin), SHA-256 checked on this machine 2026-11-14; quantised and
        # converted at S = 87 with its one link clamp it is nets/r8ceplo2.fnet byte for byte.
        self.assertEqual((k.SOURCE['name'], k.SOURCE['weights'], k.SOURCE['dataset']),
                         ('r8ceplo2', 'r8ceplo2-avg.bin', 'fork-r3-init-8c'))
        self.assertEqual(k.SOURCE['sha256'], '4118015e47ca596a966ee29821a43ae613155af9b0c9a95913d6fc81e06f3539')"""),
])
edit('tools/nnue/extend_weights.py', [
    ("""2026-11-14), from an S512+PP net (r8brft1 first; the next default's when
one is promoted): S512+PP's piece inputs""",
     """2026-11-14), from an S512+PP net (r8ceplo2's, the default, for all round 3
training from 2026-11-14 ~5:55 PM EST: owner; r8brft1 before): S512+PP's
piece inputs"""),
    ("""owner, 2026-11-14), from an S512+PP net the same way (r8brft1 first; 8c's
winner when promoted), with the exposure plane's""",
     """owner, 2026-11-14), from an S512+PP net the same way (r8ceplo2's from
2026-11-14 ~5:55 PM EST; r8brft1 before), with the exposure plane's"""),
])
print('edited')
