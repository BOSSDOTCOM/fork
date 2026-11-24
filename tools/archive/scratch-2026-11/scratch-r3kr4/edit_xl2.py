"""One-off edit: x_lower's second seed xl2 and the session set X2 (owner's rule, 2026-11-14)."""
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
    ("Sessions (ARM_SET): A = kr1 (GPU 0) beside pp1 (GPU 1); X = xl1 alone (GPU 0).",
     "- xl2, x_lower's second seed: xl1's settings with seed 2 (owner's rule, 2026-11-14: a second seed only if xl1's\n"
     "  fixed-node result against pp1 lands between about +5 and +20; it landed at +17.60 +/- 8.69), its own session X2.\n"
     "Sessions (ARM_SET): A = kr1 (GPU 0) beside pp1 (GPU 1); X = xl1 alone (GPU 0); X2 = xl2 alone (GPU 0)."),
    ("Arm sets: ARM_SET = 'A' (kr1 and pp1), 'X' (xl1), 'kr' or 'pp' (one arm of A), set in a kernel copy by one exact",
     "Arm sets: ARM_SET = 'A' (kr1 and pp1), 'X' (xl1), 'X2' (xl2), 'kr' or 'pp' (one arm of A), set in a kernel copy by\none exact"),
    ("        'xl1': {**BASE_SETTINGS, 'arch': 's512ppxl', 'init': 'exposure', 'seed': 1}}",
     "        'xl1': {**BASE_SETTINGS, 'arch': 's512ppxl', 'init': 'exposure', 'seed': 1},\n"
     "        'xl2': {**BASE_SETTINGS, 'arch': 's512ppxl', 'init': 'exposure', 'seed': 2}}"),
    ("ARM_SET = 'A'               # a kernel copy only (module note): 'A', 'X', 'kr' or 'pp'",
     "ARM_SET = 'A'               # a kernel copy only (module note): 'A', 'X', 'X2', 'kr' or 'pp'"),
    ("ARM_SETS = {'A': [['kr1'], ['pp1']], 'X': [['xl1']], 'kr': [['kr1']], 'pp': [['pp1']]}",
     "ARM_SETS = {'A': [['kr1'], ['pp1']], 'X': [['xl1']], 'X2': [['xl2']], 'kr': [['kr1']], 'pp': [['pp1']]}"),
])
edit('tools/train/kaggle/test_bakeoff_r3.py', [
    ("""    def test_the_source_is_r8ceplo2s_float_weights(self):""",
     """    def test_session_x2_runs_xl2_alone_as_xl1_but_its_seed(self):
        # x_lower's second seed (owner's rule, 2026-11-14): xl1's recipe, data and warm start, seed 2.
        src = (HERE / 'bakeoff_r3.py').read_text(encoding='utf-8')
        old = "\\nARM_SET = 'A' "
        x = {'__name__': 'bakeoff_r3_x2'}
        exec(compile(src.replace(old, "\\nARM_SET = 'X2' ", 1), 'bakeoff_r3_x2.py', 'exec'), x)
        self.assertEqual(x['QUEUES'], [['xl2']])
        self.assertEqual(sorted(x['ARMS']), ['xl2'])
        x1 = {'__name__': 'bakeoff_r3_x'}
        exec(compile(src.replace(old, "\\nARM_SET = 'X' ", 1), 'bakeoff_r3_x.py', 'exec'), x1)
        xl2, xl1 = x['ARMS']['xl2'], x1['ARMS']['xl1']
        self.assertEqual((xl2['seed'], xl1['seed']), (2, 1))
        self.assertEqual({f: v for f, v in xl2.items() if f != 'seed'}, {f: v for f, v in xl1.items() if f != 'seed'})
        self.assertEqual(x['SOURCE'], k.SOURCE)

    def test_the_source_is_r8ceplo2s_float_weights(self):"""),
])
print('edited')
