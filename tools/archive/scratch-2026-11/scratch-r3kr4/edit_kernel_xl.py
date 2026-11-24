"""One-off edit of tools/train/kaggle/bakeoff_r3.py: the xl1 arm (x_lower, S512+PPXL) and the session sets A / X."""
import sys
from pathlib import Path

p = Path(sys.argv[1])
s = p.read_text(encoding='utf-8')


def rep(a, b):
    global s
    assert s.count(a) == 1, a[:80]
    s = s.replace(a, b)


rep('''ARMS = {'kr1': {**BASE_SETTINGS, 'arch': 'h512pp', 'init': 'regioned', 'seed': 1},
        'pp1': {**BASE_SETTINGS, 'arch': 's512pp', 'init': 'source', 'seed': 1}}
QUEUES = [['kr1'], ['pp1']]
ARM_SET = 'all'             # a kernel copy only (module note): 'all', 'kr' or 'pp'
ARM_SETS = {'all': None, 'kr': ('kr1',), 'pp': ('pp1',)}
if ARM_SETS[ARM_SET]:
    QUEUES = [[a for a in q if a in ARM_SETS[ARM_SET]] for q in QUEUES]
    QUEUES = [q for q in QUEUES if q]
    ARMS = {a: v for a, v in ARMS.items() if a in ARM_SETS[ARM_SET]}''',
    '''ARMS = {'kr1': {**BASE_SETTINGS, 'arch': 'h512pp', 'init': 'regioned', 'seed': 1},
        'pp1': {**BASE_SETTINGS, 'arch': 's512pp', 'init': 'source', 'seed': 1},
        'xl1': {**BASE_SETTINGS, 'arch': 's512ppxl', 'init': 'exposure', 'seed': 1}}
# The warm starts laid out from SOURCE in the session: (architecture, extend_weights.py's net-file function that
# lays SOURCE's quantised net out the same way, for the quantised identity).
WARM_STARTS = {'regioned': ('h512pp', 'regioned_net'), 'exposure': ('s512ppxl', 'exposure_net')}
# The sessions (module note): A = kr1 and its same-recipe control pp1, one GPU each; X = xl1 alone (x_lower, owner
# 2026-11-14: compared against session A's control); kr and pp one arm of A each.
ARM_SET = 'A'               # a kernel copy only (module note): 'A', 'X', 'kr' or 'pp'
ARM_SETS = {'A': [['kr1'], ['pp1']], 'X': [['xl1']], 'kr': [['kr1']], 'pp': [['pp1']]}
QUEUES = ARM_SETS[ARM_SET]
ARMS = {a: v for a, v in ARMS.items() if any(a in q for q in QUEUES)}''')

rep('''def identity_probe(nnue, source_quantised, warm_quantised):
    """A script printing True when the warm start's quantised file, converted, is SOURCE's converted and laid out
    per region (tools/nnue's converter and extend_weights.regioned_net)."""
    return '\\n'.join([
        'import sys',
        f'sys.path.insert(0, {nnue!r})',
        'import convert, extend_weights, netformat',
        f'a = convert.convert(open({source_quantised!r}, "rb").read(), netformat.layout({nnue + "/s512pp.json"!r}), '
        f'{SCALE})',
        f'b = convert.convert(open({warm_quantised!r}, "rb").read(), netformat.layout({nnue + "/h512pp.json"!r}), '
        f'{SCALE})',
        'print(extend_weights.regioned_net(a) == b)', ''])''',
    '''def identity_probe(nnue, source_quantised, warm_quantised, arch='h512pp', lay_out='regioned_net'):
    """A script printing True when the warm start's quantised file, converted with `arch`'s layout, is SOURCE's
    converted and laid out by extend_weights.`lay_out` (regioned_net: every region SOURCE's rows; exposure_net: the
    exposure rows zero), both before any clamp."""
    return '\\n'.join([
        'import sys',
        f'sys.path.insert(0, {nnue!r})',
        'import convert, extend_weights, netformat',
        f'a = convert.convert(open({source_quantised!r}, "rb").read(), netformat.layout({nnue + "/s512pp.json"!r}), '
        f'{SCALE})',
        f'b = convert.convert(open({warm_quantised!r}, "rb").read(), netformat.layout({nnue + "/" + arch + ".json"!r}), '
        f'{SCALE})',
        f'print(extend_weights.{lay_out}(a) == b)', ''])''')

rep('''    warm = f'{WORK}/h512pp-warm.bin'
    if ok:
        rc, out, _ = sh(f'python3 {nnue}/extend_weights.py {src[0]} {warm} --arch h512pp')
        summary['warm_start'] = {'rc': rc, 'out': out[-300:]}
        ok = rc == 0 and os.path.exists(warm)
    init_of = {'source': src[0] if src else None, 'regioned': warm}''',
    '''    init_of = {'source': src[0] if src else None}
    warms = sorted({a['init'] for a in ARMS.values()} - {'source'})
    summary['warm_start'] = {}
    for init in warms:
        arch = WARM_STARTS[init][0]
        init_of[init] = f'{WORK}/{arch}-warm.bin'
        if ok:
            rc, out, _ = sh(f'python3 {nnue}/extend_weights.py {src[0]} {init_of[init]} --arch {arch}')
            summary['warm_start'][init] = {'rc': rc, 'out': out[-300:]}
            ok = rc == 0 and os.path.exists(init_of[init])''')

rep('''    if ok:
        c = {}
        for arch in ('h512pp', 's512pp'):
            rc, out, _ = sh(f'{train} check {spec(arch)} --out {WORK}/check-{arch}', env=env)
            c[f'check-{arch}'] = {'rc': rc, 'out': out[-300:]}
        # The reference: SOURCE on the arms' validation file at their result weight (0); the warm start must score
        # the same (its float identity).
        c['reference'] = score('s512pp', src[0], by_name[VAL_BLEND], VAL_POSITIONS, f'{WORK}/ref', result_weight=0.0)
        c['warm_float'] = score('h512pp', warm, by_name[VAL_BLEND], VAL_POSITIONS, f'{WORK}/ref-warm',
                                result_weight=0.0)
        ref, got = c['reference']['loss'], c['warm_float']['loss']
        c['warm_float_ok'] = ref is not None and got is not None and abs(ref - got) <= WARM_TOLERANCE
        # The quantised identity: the trainer's own files of both, converted, compared after laying SOURCE out.
        os.makedirs(f'{RESULT}/warm', exist_ok=True)
        qs, qw = quantise('s512pp', src[0], f'{WORK}/q-source'), quantise('h512pp', warm, f'{WORK}/q-warm')
        c['quantise_source'], c['quantise_warm'] = qs, qw
        same = False
        if qs['quantised'] and qw['quantised']:
            shutil.copy(qs['quantised'], f'{RESULT}/warm/source-quantised.bin')
            shutil.copy(qw['quantised'], f'{RESULT}/warm/warm-quantised.bin')
            with open(f'{WORK}/identity.py', 'w') as f:
                f.write(identity_probe(nnue, qs['quantised'], qw['quantised']))
            rc, out, _ = sh(f'python3 {WORK}/identity.py')
            same = rc == 0 and out.strip().endswith('True')
            c['quantised_identity_tail'] = out[-300:]
        c['quantised_identity'] = same
        # The trainer leg of the warm start (and of SOURCE beside it): its float outputs on the parity positions.
        for arch, w, tag in (('h512pp', warm, 'warm'), ('s512pp', src[0], 'source')):
            sh(f'{train} eval {spec(arch)} --weights {w} --epd {repo}/tests/nnue/parity.epd '
               f'--out {RESULT}/warm/parity-trainer-{tag}.txt', env=env)
        c['ok'] = all(c[f'check-{a}']['rc'] == 0 for a in ('h512pp', 's512pp')) and c['warm_float_ok'] and same
        summary['checks'] = c
        ok = c['ok']
        save()''',
    '''    if ok:
        c = {}
        archs = sorted({a['arch'] for a in ARMS.values()} | {'s512pp'})
        for arch in archs:
            rc, out, _ = sh(f'{train} check {spec(arch)} --out {WORK}/check-{arch}', env=env)
            c[f'check-{arch}'] = {'rc': rc, 'out': out[-300:]}
        # The feature leg of each new architecture: the trainer's active inputs on the parity positions against the
        # reference's (tools/nnue/reference.py features).
        for arch in archs:
            if arch == 's512pp':
                continue
            rc, out, _ = sh(f'{train} features {spec(arch)} --epd {repo}/tests/nnue/parity.epd '
                            f'> {WORK}/features-{arch}.txt', env=env)
            rc2, out2, _ = sh(f'python3 {nnue}/reference.py features --rust {WORK}/features-{arch}.txt '
                              f'--layout {nnue}/{arch}.json')
            c[f'features-{arch}'] = {'rc': rc, 'leg_rc': rc2, 'out': out2[-300:]}
        # The reference: SOURCE on the arms' validation file at their result weight (0); each warm start must score
        # the same (its float identity).
        c['reference'] = score('s512pp', src[0], by_name[VAL_BLEND], VAL_POSITIONS, f'{WORK}/ref', result_weight=0.0)
        os.makedirs(f'{RESULT}/warm', exist_ok=True)
        qs = quantise('s512pp', src[0], f'{WORK}/q-source')
        c['quantise_source'] = qs
        if qs['quantised']:
            shutil.copy(qs['quantised'], f'{RESULT}/warm/source-quantised.bin')
        sh(f'{train} eval {spec("s512pp")} --weights {src[0]} --epd {repo}/tests/nnue/parity.epd '
           f'--out {RESULT}/warm/parity-trainer-source.txt', env=env)
        ref = c['reference']['loss']
        good = all(c[f'check-{a}']['rc'] == 0 for a in archs) and \\
            all(v['rc'] == 0 and v['leg_rc'] == 0 for k, v in c.items() if k.startswith('features-'))
        for init in warms:
            arch, lay_out = WARM_STARTS[init]
            w = init_of[init]
            got = score(arch, w, by_name[VAL_BLEND], VAL_POSITIONS, f'{WORK}/ref-{init}', result_weight=0.0)
            c[f'warm_float-{init}'] = got
            c[f'warm_float_ok-{init}'] = ref is not None and got['loss'] is not None and \\
                abs(ref - got['loss']) <= WARM_TOLERANCE
            # The quantised identity: the trainer's own files of both, converted, compared after laying SOURCE out.
            qw = quantise(arch, w, f'{WORK}/q-{init}')
            c[f'quantise-{init}'] = qw
            same = False
            if qs['quantised'] and qw['quantised']:
                shutil.copy(qw['quantised'], f'{RESULT}/warm/{init}-quantised.bin')
                with open(f'{WORK}/identity-{init}.py', 'w') as f:
                    f.write(identity_probe(nnue, qs['quantised'], qw['quantised'], arch, lay_out))
                rc, out, _ = sh(f'python3 {WORK}/identity-{init}.py')
                same = rc == 0 and out.strip().endswith('True')
                c[f'quantised_identity_tail-{init}'] = out[-300:]
            c[f'quantised_identity-{init}'] = same
            # The trainer leg of the warm start: its float outputs on the parity positions.
            sh(f'{train} eval {spec(arch)} --weights {w} --epd {repo}/tests/nnue/parity.epd '
               f'--out {RESULT}/warm/parity-trainer-{init}.txt', env=env)
            good = good and c[f'warm_float_ok-{init}'] and same
        c['ok'] = good and ref is not None
        summary['checks'] = c
        ok = c['ok']
        save()''')

rep('''             'inputs_ok': summary['inputs']['ok'], 'warm_float_ok': summary['checks'].get('warm_float_ok'),
             'quantised_identity': summary['checks'].get('quantised_identity'),''',
    '''             'inputs_ok': summary['inputs']['ok'],
             'warm_float_ok': {k: v for k, v in summary['checks'].items() if k.startswith('warm_float_ok-')},
             'quantised_identity': {k: v for k, v in summary['checks'].items() if k.startswith('quantised_identity-')},''')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited')
