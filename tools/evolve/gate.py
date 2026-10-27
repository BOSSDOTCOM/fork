"""The evaluator funnel's first stage: the gate (ideas.md idea 23).

A candidate passes only if, in order:
1. its region body follows the hot-path rules (static check, below);
2. it builds: the baseline tree with the candidate's region body, Release,
   tests on, the same flags as Fork's presets;
3. perft from the standard positions equals the baseline engine's;
4. the correctness suites pass, among them the minimax oracle (the search
   equals plain minimax with pruning off: tests/test_search.cpp), the
   pruning and parameter suites, and the counting allocator (no heap
   allocation in the search); not bench parity, since a real candidate
   changes bench by design;
5. it is deterministic: two bench runs give one signature.
Each step is a function of a `Runner`, so the unit tests replace builds and
processes with fakes. The first failing step ends the gate.
"""
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import regions

# The hot-path rules (.claude/rules/cpp-style.md) as they apply to a region
# body: no allocation, exceptions, virtual dispatch, std::function, floating
# point, randomness, mutable statics, threads, preprocessor lines, inline
# assembly or I/O. A token-level check: the gate's build and the counting
# allocator back it up.
FORBIDDEN = [
    (r'\bnew\b|\bdelete\b|\bmalloc\b|\bcalloc\b|\brealloc\b|\bfree\s*\(', 'heap allocation'),
    (r'\bthrow\b|\btry\b|\bcatch\b', 'exceptions'),
    (r'\bvirtual\b|std::function', 'dynamic dispatch'),
    (r'\bfloat\b|\bdouble\b|\blong\s+double\b|\d\.\d|\d[eE][+-]?\d', 'floating point'),
    (r'\brand\b|\bsrand\b|std::random|\bmt19937\b|\btime\s*\(', 'randomness or the clock'),
    (r'\bstatic\b|\bthread_local\b|\bvolatile\b|\bmutable\b', 'static or shared state'),
    (r'std::thread|std::atomic|\bmutex\b', 'threads'),
    (r'^\s*#', 'preprocessor lines'),
    (r'\basm\b|__asm', 'inline assembly'),
    (r'std::cout|printf|std::cerr|fopen|std::ifstream|std::ofstream', 'I/O'),
    (r'std::(vector|string|map|unordered_map|set|deque|list)\b', 'containers'),
    (r'\bgoto\b', 'goto'),
]


def static_violations(body):
    """The hot-path rules a region body breaks, as short reasons (empty: none)."""
    # Markers are comments, so they are looked for before comments go; the
    # other rules apply to code only.
    found = ['region markers inside the body'] if 'FORK-EVOLVE' in body else []
    code = re.sub(r'//[^\n]*', '', body)
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.S)
    for pattern, reason in FORBIDDEN:
        if re.search(pattern, code, flags=re.M) and reason not in found:
            found.append(reason)
    return found


@dataclass
class GateResult:
    passed: bool
    step: str  # the step that failed, or 'done'
    detail: str = ''
    bench: dict = field(default_factory=dict)  # nodes and signature, when built


class Runner:
    """The gate's actions on a real tree (Linux, WSL): build, perft, tests, bench."""

    def __init__(self, repo, work, jobs=4, timeout=1800, test_cache=None):
        self.repo = Path(repo)
        self.work = Path(work)
        self.jobs = jobs
        self.timeout = timeout
        # The tests' downloaded data (.cache/: perft suites, the 7-man tables,
        # pinned by SHA-256 in CMakeLists.txt), copied into each fresh tree so
        # no candidate downloads it again.
        self.test_cache = Path(test_cache).expanduser() if test_cache else None

    def run(self, cmd, cwd=None, timeout=None):
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout or self.timeout)
        return p.returncode, p.stdout + p.stderr

    def tree(self, commit, files, name):
        """A fresh copy of `commit` with `files` (path -> text) written over it."""
        dest = self.work / name
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)
        archive = subprocess.run(['git', '-C', str(self.repo), 'archive', commit], capture_output=True, check=True)
        subprocess.run(['tar', '-x', '-C', str(dest)], input=archive.stdout, check=True)
        for path, text in files.items():
            (dest / path).write_text(text, newline='\n')
        if self.test_cache and self.test_cache.is_dir():
            shutil.copytree(self.test_cache, dest / '.cache')
        return dest

    def build(self, tree, stats=False):
        out = tree / ('build-stats' if stats else 'build')
        flags = ['-DCMAKE_BUILD_TYPE=Release', '-DFORK_ARCH=x86-64-v3', '-G', 'Ninja',
                 f'-DFORK_BUILD_TESTS={"OFF" if stats else "ON"}', f'-DFORK_SEARCH_STATS={"ON" if stats else "OFF"}']
        code, log = self.run(['cmake', '-S', str(tree), '-B', str(out)] + flags)
        if code == 0:
            code, log = self.run(['cmake', '--build', str(out), '-j', str(self.jobs)])
        return code == 0, log[-3000:], out

    def read(self, commit, path):
        return subprocess.run(['git', '-C', str(self.repo), 'show', f'{commit}:{path}'], capture_output=True,
                              text=True, check=True).stdout

    def perft(self, engine):
        lines = []
        for fen in PERFT_FENS:
            code, out = self.run([str(engine), 'perft', '4', fen], timeout=300)
            if code != 0:
                return None
            lines.append(out.strip().split('\n')[-1])
        return lines

    def suites(self, build):
        code, log = self.run(['ctest', '--test-dir', str(build), '--output-on-failure', '-R',
                              '^(search|pruning|params|tt|ordering|no_alloc)$'])
        return code == 0, log[-3000:]

    def bench(self, engine):
        code, out = self.run([str(engine), 'bench'], timeout=600)
        if code != 0:
            return None
        fields = dict(line.split(None, 1) for line in out.strip().split('\n') if ' ' in line)
        return {'nodes': fields.get('nodes', '').strip(), 'signature': fields.get('signature', '').strip()}


# Standard perft positions: the start position and Kiwipete (as in
# tests/suite.hpp, which cites their sources). The gate compares with the
# baseline engine's own counts, so no count is written here.
PERFT_FENS = [
    'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
    'r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1',
]


def run_gate(runner, commit, region_name, region_body, baseline_perft, tag):
    """Gate one candidate: `region_body` replaces region `region_name` at `commit`."""
    violations = static_violations(region_body)
    if violations:
        return GateResult(False, 'static', 'breaks the hot-path rules: ' + ', '.join(violations))
    path = regions.REGIONS[region_name]
    base_text = runner.read(commit, path)
    cand_text = regions.replace_body(base_text, region_name, region_body)
    ok, why = regions.guard({path: base_text}, {path: cand_text}, region_name)
    if not ok:
        return GateResult(False, 'guard', why)
    tree = runner.tree(commit, {path: cand_text}, tag)
    built, log, build = runner.build(tree)
    if not built:
        return GateResult(False, 'build', log)
    engine = build / 'fork'
    counts = runner.perft(engine)
    if counts != baseline_perft:
        return GateResult(False, 'perft', f'{counts} != {baseline_perft}')
    passed, log = runner.suites(build)
    if not passed:
        return GateResult(False, 'suites', log)
    first, second = runner.bench(engine), runner.bench(engine)
    if not first or first != second:
        return GateResult(False, 'determinism', f'{first} then {second}')
    return GateResult(True, 'done', '', first)

