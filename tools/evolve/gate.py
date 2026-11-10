# SPDX-License-Identifier: GPL-3.0-or-later

"""The evaluator funnel's first stage: the gate (ideas.md idea 23).

A candidate passes only if, in order:
1. its region body follows the hot-path rules (static check, below: a real
   lexer, so string and character literals, comments, digraphs, splices and
   every form of floating literal are seen as the compiler sees them), and
   it never closes the function it is written in;
2. the candidate tree, as written on disk, equals the baseline tree in every
   file but the region's, and that file equals the baseline outside the
   region's body (regions.guard on the file's real text);
3. every translation unit that includes the region's file preprocesses
   (`-E`, the build's own compile commands) to the same text as the
   baseline's everywhere outside the region's body: whatever the lexer
   missed, a body cannot change any code outside itself;
4. those units compile (`-fsyntax-only`), then it builds: the baseline tree
   with the candidate's region body, Release, tests on, the same flags as
   Fork's presets;
5. perft from the standard positions equals the baseline engine's;
6. the correctness suites pass, among them the minimax oracle (the search
   equals plain minimax with pruning off: tests/test_search.cpp), the
   pruning and parameter suites, and the counting allocator (no heap
   allocation in the search); not bench parity, since a real candidate
   changes bench by design;
7. it is deterministic: two bench runs give one signature.
Steps 3-7 run with every configured compiler (two-compiler gating, owner,
2026-11-09: TCEC's g++ 11.4 and clang++-19, which disagree on some constexpr
bodies, audit-1 U-17): a candidate failing with either is refused, and the
benches of all compilers must agree (the same nodes and signature, as
bench_parity requires of every preset). Steps 1-3 run before anything is
built. Each step is a function of a `Runner`, so the unit tests replace
builds and processes with fakes. The first failing step ends the gate.
"""
import copy
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import regions

# The hot-path rules (.claude/rules/cpp-style.md) as they apply to a region
# body: no allocation, exceptions, virtual dispatch, std::function, floating
# point, randomness, clocks, the environment, mutable statics, threads,
# preprocessor lines, inline assembly or I/O. They run on the lexed code
# (comments and literals removed); the preprocessed comparison (step 3) and
# the gate's build and counting allocator back them up.
_STD = r'(?:\bstd\s*::\s*)'
FORBIDDEN = [
    (r'\bnew\b|\bdelete\b|\b(?:malloc|calloc|realloc|aligned_alloc|alloca|free|make_unique|make_shared|'
     r'make_unique_for_overwrite|make_shared_for_overwrite|allocate_shared)\b|\ballocator\b|\bpmr\b',
     'heap allocation'),
    (r'\bthrow\b|\btry\b|\bcatch\b|\bnoexcept\s*\(\s*false', 'exceptions'),
    (r'\bvirtual\b|\bfunction\s*<|' + _STD + r'function\b|\btypeid\b|\bdynamic_cast\b', 'dynamic dispatch'),
    (r'\b(?:float|double)(?:\d*_t)?\b|\bbfloat16_t\b|\b(?:sqrt|sqrtf|cbrt|pow|powf|exp|exp2|expm1|log|log2|log10|'
     r'log1p|logb|sin|cos|tan|asin|acos|atan|atan2|sinh|cosh|tanh|hypot|floor|ceil|round|lround|llround|trunc|'
     r'fmod|remainder|fabs|fma|fmin|fmax|nearbyint|rint|lrint|llrint|ldexp|frexp|modf|scalbn|lerp|atof|strtod|'
     r'strtof|strtold|erf|erfc|tgamma|lgamma)\s*\(', 'floating point'),
    (r'\b(?:rand|srand|rand_r|random|srandom|drand48|lrand48|arc4random)\s*\(|\brandom_device\b|\bmt19937\w*|'
     r'\bminstd_rand\w*|\bdefault_random_engine\b|\branlux\w*|\bknuth_b\b|\w+_distribution\b|' + _STD + r'random\b|'
     r'\b(?:time|clock|clock_gettime|gettimeofday|timespec_get|ftime|times)\s*\(|\bchrono\b|'
     r'\b(?:steady|system|high_resolution|utc|tai|gps|file)_clock\b|\brdtscp?\b|\b_?rdtsc\w*|'
     r'\bQueryPerformanceCounter\b|\bGetTickCount\w*', 'randomness or the clock'),
    (r'\b(?:getenv|secure_getenv|setenv|putenv|unsetenv|environ)\b', 'the environment'),
    (r'\b(?:static|thread_local|volatile|mutable|extern|inline|register|constinit)\b|\bconst_cast\b|'
     r'\breinterpret_cast\b', 'static or shared state'),
    (r'\bnamespace\b|\busing\b(?!\s+\w+\s*=)|\b(?:export|module|import)\b', 'declarations outside the function'),
    (r'\bthread\b|\bjthread\b|\batomic\w*|\bmutex\b|\bcondition_variable\b|\basync\b|\bfuture\b|\bpromise\b|'
     r'\bpthread_\w+', 'threads'),
    (r'\bco_(?:await|yield|return)\b', 'coroutines'),
    (r'\basm\b', 'inline assembly'),
    (r'\b(?:__\w*|_[A-Z]\w*)', 'reserved names or compiler builtins'),
    (r'\b(?:cout|cerr|clog|cin|wcout|wcerr|ifstream|ofstream|fstream|iostream|ostream|istream|stringstream|'
     r'istringstream|ostringstream|FILE|stdout|stderr|stdin)\b|\b(?:printf|fprintf|sprintf|snprintf|vprintf|'
     r'puts|fputs|putchar|fputc|putc|fopen|fclose|fwrite|fread|fflush|scanf|sscanf|fscanf|getchar|getc|fgetc|'
     r'fgets|perror|system|popen|exit|abort|quick_exit|_Exit|terminate|syscall|write|read|open)\s*\(', 'I/O'),
    (_STD + r'(?:vector|basic_string|string|wstring|u8string|u16string|u32string|map|multimap|unordered_map|'
     r'unordered_multimap|set|multiset|unordered_set|unordered_multiset|deque|list|forward_list|any|valarray|'
     r'regex|shared_ptr|unique_ptr|weak_ptr|stack|queue|priority_queue|flat_map|flat_set)\b|'
     r'\b(?:vector|basic_string|map|multimap|unordered_map|unordered_multimap|multiset|unordered_set|'
     r'unordered_multiset|deque|forward_list|valarray|shared_ptr|unique_ptr|weak_ptr|priority_queue)\s*<|'
     r'\b(?:string|wstring)\b', 'containers'),
    (r'\bgoto\b', 'goto'),
]

# Characters the lexer turns into tokens of their own (pp-numbers, names);
# everything else is punctuation, one character at a time.
_IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
_PPNUMBER = re.compile(r"\.?\d(?:[eEpP][+-]|'[0-9A-Za-z_]|[0-9A-Za-z_.])*")
_ENCODING = re.compile(r'(?:u8|u|U|L)?R?')
_RAW_DELIM = re.compile(r'[^ ()\\\t\v\f\n]{0,16}\(')
_SPLICE = re.compile(r'\\[ \t\f\v]*\r?\n')
_TRIGRAPH = re.compile(r"\?\?[=/'()!<>\-]")
_DIGRAPH = re.compile(r'<:|:>|<%|%>|%:')
_CLOSERS = {')': '(', ']': '[', '}': '{'}


def _string_end(text, i, quote):
    """The index after the literal opened by `quote` at text[i], or -1 if it never closes on its line."""
    j = i + 1
    while j < len(text):
        c = text[j]
        if c == '\\':
            j += 2
            continue
        if c == quote:
            return j + 1
        if c == '\n':
            return -1
        j += 1
    return -1


def _raw_end(text, i):
    """The index after the raw string literal whose quote is text[i], or -1."""
    m = _RAW_DELIM.match(text, i + 1)
    if not m:
        return -1
    delim = m.group()[:-1]
    close = text.find(')' + delim + '"', m.end())
    return -1 if close < 0 else close + len(delim) + 2


def lex(body):
    """(code, numbers, problems): the body as the compiler's tokenizer sees it,
    with each comment replaced by a space and each string or character literal
    by an empty one ("" or ''); its pp-number tokens; lexing problems
    (unterminated comments or literals)."""
    out, numbers, problems = [], [], []
    i, n = 0, len(body)
    while i < n:
        c = body[i]
        if body.startswith('//', i):
            j = body.find('\n', i)
            out.append(' ')
            i = n if j < 0 else j
            continue
        if body.startswith('/*', i):
            j = body.find('*/', i + 2)
            if j < 0:
                problems.append('unterminated comment')
                break
            out.append(' ')
            i = j + 2
            continue
        if c.isdigit() or (c == '.' and i + 1 < n and body[i + 1].isdigit()):
            m = _PPNUMBER.match(body, i)
            numbers.append(m.group())
            out.append(m.group())
            i = m.end()
            continue
        if c.isascii() and (c.isalpha() or c == '_'):
            m = _IDENT.match(body, i)
            word, j = m.group(), m.end()
            if j < n and body[j] in '"\'' and _ENCODING.fullmatch(word) and not (body[j] == "'" and 'R' in word):
                i, c = j, body[j]
                raw = 'R' in word
            else:
                out.append(word)
                i = j
                continue
        else:
            raw = False
        if c in '"\'':
            end = _raw_end(body, i) if raw else _string_end(body, i, c)
            if end < 0:
                problems.append('unterminated literal')
                break
            out.append(c + c)
            i = end
            continue
        out.append(c)
        i += 1
    return ''.join(out), numbers, problems


def is_float_literal(token):
    """True for a floating literal in any form: 1.5, .5, 2., 1.f, 1e3, 0x1p3, 0x1.8p1, with separators."""
    t = token.replace("'", '')
    if re.match(r'0[xX]', t):
        return '.' in t or 'p' in t.lower()
    if re.match(r'0[bB]', t):
        return '.' in t
    return '.' in t or bool(re.match(r'\d+[eE]', t))


def _brackets_ok(code):
    """True if (), [] and {} nest properly and the body never closes past its own start."""
    stack = []
    for c in code:
        if c in '([{':
            stack.append(c)
        elif c in _CLOSERS:
            if not stack or stack.pop() != _CLOSERS[c]:
                return False
    return not stack


def static_violations(body):
    """The hot-path rules a region body breaks, as short reasons (empty: none)."""
    found = []

    def add(reason):
        if reason not in found:
            found.append(reason)
    # Checked on the raw text: markers are comments, and splices and
    # trigraphs act before comments and literals exist (translation phases
    # 1-2), so no part of the text is exempt.
    if 'FORK-EVOLVE' in body:
        add('region markers inside the body')
    if _SPLICE.search(body):
        add('line splices (backslash-newline)')
    if _TRIGRAPH.search(body):
        add('digraphs or trigraphs')
    code, numbers, problems = lex(body)
    for p in problems:
        add(p)
    if _DIGRAPH.search(code):
        add('digraphs or trigraphs')
    if '#' in code or '%:' in code:
        add('preprocessor lines')
    if '\\' in code:
        add('backslashes outside literals')
    if not code.isascii():
        add('non-ASCII characters in code')
    if not _brackets_ok(code):
        add('leaves the function (unbalanced braces, brackets or parentheses)')
    if any(is_float_literal(t) for t in numbers):
        add('floating point')
    for pattern, reason in FORBIDDEN:
        if re.search(pattern, code, flags=re.M):
            add(reason)
    return found


# --- the preprocessed comparison (step 3) -----------------------------------------

_MARKER = re.compile(r'^#\s*(?:line\s+)?(\d+)\s+"((?:[^"\\]|\\.)*)"')


def _norm_path(path):
    return path.replace('\\\\', '\\').replace('\\', '/')


def outside_lines(preprocessed, root, header, body_lines):
    """(lines, included) for one unit's `-E` output (with line markers): every
    non-blank line that does not come from lines body_lines[0]..body_lines[1]
    (1-based, inclusive) of `header` (a path relative to the tree `root`), with
    the tree's path replaced by <tree>; `included` says whether the header was
    entered at all."""
    root_norm = _norm_path(str(root)).rstrip('/')
    header_path = root_norm + '/' + header
    # The tree's path as string literals spell it (__FILE__ in an assertion):
    # with backslashes on Windows, escaped in the literal, and with slashes.
    spellings = sorted({root_norm, str(root).rstrip('/\\'), str(root).rstrip('/\\').replace('\\', '\\\\')},
                       key=len, reverse=True)

    def strip_root(text):
        for spelling in spellings:
            text = text.replace(spelling, '<tree>')
        return text
    lines, included = [], False
    current, number = '', 0
    for raw in preprocessed.split('\n'):
        m = _MARKER.match(raw)
        if m:
            number, current = int(m.group(1)), _norm_path(m.group(2))
            if current == header_path:
                included = True
            continue
        here = number
        number += 1
        if current == header_path and body_lines[0] <= here <= body_lines[1]:
            continue
        text = raw.strip()
        if text:
            lines.append((current.replace(root_norm, '<tree>'), strip_root(text)))
    return lines, included


def body_lines(text, name):
    """The 1-based line numbers (first, last) of region `name`'s body in `text`."""
    span = regions.find_regions(text)[name]
    return span.begin + 2, span.end


def first_difference(a, b):
    """A short description of where two outside-line lists first differ, or None if equal."""
    if a == b:
        return None
    for k, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return f'line {k}: {x[0]}: {x[1][:160]!r} became {y[0]}: {y[1][:160]!r}'
    return f'{len(a)} lines became {len(b)}'


@dataclass
class Reference:
    """What every candidate is compared with, measured once on the baseline tree."""
    perft: list
    files: dict  # relative path -> SHA-256, every file of the baseline tree
    units: dict  # per compiler (its index): each unit including the region's file -> its outside lines


def make_reference(runner, region_name, tree, perft):
    """The Reference from the baseline tree, built with every compiler (each
    in its own build folder): its files, and per compiler the preprocessed
    text of every unit that includes the region's file."""
    path = regions.REGIONS[region_name]
    lines = body_lines(runner.read_file(tree, path), region_name)
    units = {}
    for index, variant in enumerate(runner.variants()):
        mine = units[index] = {}
        for unit, text in variant.preprocess(Path(tree) / variant.build_name, None).items():
            outside, included = outside_lines(text, tree, path, lines)
            if included:
                mine[unit] = outside
        if not mine:
            raise RuntimeError(f'no translation unit includes {path}: the preprocessed check would be empty')
    return Reference(list(perft) if perft is not None else None, runner.snapshot(tree), units)


@dataclass
class GateResult:
    passed: bool
    step: str  # the step that failed, or 'done'
    detail: str = ''
    bench: dict = field(default_factory=dict)  # nodes and signature, when built
    compiler: str = ''  # the compiler a failing step ran with ('' before any build)


# The build targets the gate needs: the engine (perft, bench, the proxies),
# the test runner and the counting-allocator test (SUITES); a stats build
# needs the engine only. Building only these keeps a candidate's two builds
# at about three minutes each at -j 2 instead of every tool of the tree.
GateTargets = ('fork', 'fork_tests', 'fork_alloc_test')
StatsTargets = ('fork',)
# Targets that write generated headers a unit includes (build_id.hpp for
# main.cpp and bench/micro.cpp): built before a candidate's units are
# preprocessed, so `-E` sees the same headers as the baseline's built tree.
GeneratedTargets = ('fork_build_id',)


class Runner:
    """The gate's actions on a real tree (Linux, WSL): build, perft, tests, bench.

    `compilers` lists the compilers every candidate must pass with (CMake's
    CMAKE_CXX_COMPILER); the first builds in `build/` and is the one whose
    engine is measured, the others in `build-1/`, `build-2/`... `variants()`
    gives one Runner per compiler."""

    def __init__(self, repo, work, jobs=4, timeout=1800, test_cache=None, compiler=None, compilers=None):
        self.repo = Path(repo)
        self.work = Path(work)
        self.jobs = jobs
        self.timeout = timeout
        # The tests' downloaded data (.cache/: perft suites, the 7-man tables,
        # pinned by SHA-256 in CMakeLists.txt), copied into each fresh tree so
        # no candidate downloads it again.
        self.test_cache = Path(test_cache).expanduser() if test_cache else None
        self.compilers = list(compilers) if compilers else [compiler]
        self.compiler = self.compilers[0]
        self.build_name = 'build'

    def variants(self):
        """One Runner per compiler, each with its own build folder (the first's is `build`)."""
        out = []
        for index, compiler in enumerate(self.compilers):
            v = copy.copy(self)
            v.compiler, v.build_name = compiler, 'build' if index == 0 else f'build-{index}'
            out.append(v)
        return out

    def run(self, cmd, cwd=None, timeout=None):
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace',
                           timeout=timeout or self.timeout)
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
            (dest / path).write_text(text, encoding='utf-8', newline='\n')
        if self.test_cache and self.test_cache.is_dir():
            shutil.copytree(self.test_cache, dest / '.cache')
        return dest

    def read_file(self, tree, path):
        """A file of a written tree, as it is on disk."""
        return (Path(tree) / path).read_text(encoding='utf-8')

    def snapshot(self, tree):
        """SHA-256 of every file in a tree, by relative path (the build folders, `build` and every
        `build-*` of the compilers and the stats build, and the test cache left out)."""
        tree = Path(tree)
        out = {}
        for dirpath, dirnames, filenames in os.walk(tree):
            if Path(dirpath) == tree:
                dirnames[:] = [d for d in dirnames if d not in ('build', '.cache') and not d.startswith('build-')]
            for f in filenames:
                p = Path(dirpath) / f
                out[p.relative_to(tree).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
        return out

    def configure(self, tree, stats=False):
        out = Path(tree) / ('build-stats' if stats else self.build_name)
        flags = ['-DCMAKE_BUILD_TYPE=Release', '-DFORK_ARCH=x86-64-v3', '-G', 'Ninja',
                 '-DCMAKE_EXPORT_COMPILE_COMMANDS=ON',
                 f'-DFORK_BUILD_TESTS={"OFF" if stats else "ON"}', f'-DFORK_SEARCH_STATS={"ON" if stats else "OFF"}']
        if self.compiler:
            flags.append(f'-DCMAKE_CXX_COMPILER={self.compiler}')
        code, log = self.run(['cmake', '-S', str(tree), '-B', str(out)] + flags)
        return code == 0, log[-3000:], out

    def generate(self, build):
        """Builds the generated headers (GeneratedTargets) of a configured build; (ok, log)."""
        code, log = self.run(['cmake', '--build', str(build), '--target', *GeneratedTargets])
        return code == 0, log[-3000:]

    def build(self, tree, stats=False):
        ok, log, out = self.configure(tree, stats)
        if ok:
            code, log = self.run(['cmake', '--build', str(out), '-j', str(self.jobs), '--target',
                                  *(StatsTargets if stats else GateTargets)])
            ok, log = code == 0, log[-3000:]
        return ok, log, out

    def resolve(self, ref):
        """The full hash of the commit `ref` names (a branch, HEAD, a short hash)."""
        return subprocess.run(['git', '-C', str(self.repo), 'rev-parse', '--verify', '--end-of-options',
                               f'{ref}^{{commit}}'], capture_output=True, text=True, encoding='utf-8',
                              check=True).stdout.strip()

    def read(self, commit, path):
        return subprocess.run(['git', '-C', str(self.repo), 'show', f'{commit}:{path}'], capture_output=True,
                              text=True, encoding='utf-8', check=True).stdout

    def preprocess(self, build, units):
        """{unit: `-E` output} for the C++ units of a configured build (relative
        to its tree) named in `units`, or all of them for None, each with its
        own compile command from compile_commands.json."""
        return self._each_unit(build, units, '-E')

    def syntax(self, build, units):
        """'' if every unit named compiles (`-fsyntax-only`, its own compile
        command: the same flags, so -Werror's warnings count), else the first
        failure's unit and compiler output."""
        try:
            self._each_unit(build, units, '-fsyntax-only')
        except RuntimeError as e:
            return str(e)
        return ''

    def _each_unit(self, build, units, mode):
        build = Path(build)
        tree = build.parent
        entries = json.loads((build / 'compile_commands.json').read_text(encoding='utf-8'))
        jobs = []
        for e in entries:
            rel = Path(os.path.relpath(Path(e['directory']) / e['file'], tree)).as_posix()
            if not rel.endswith(('.cpp', '.cc', '.cxx')) or (units is not None and rel not in units):
                continue
            jobs.append((rel, e))
        if units is not None and len(jobs) != len(set(units)):
            missing = sorted(set(units) - {rel for rel, _ in jobs})
            raise RuntimeError(f'compile commands missing for {missing}')

        def one(job):
            rel, e = job
            code, out = self.run(preprocess_command(e, mode), cwd=e['directory'])
            if code != 0:
                raise RuntimeError(f'{"preprocessing" if mode == "-E" else "compiling"} {rel} failed: {out[-1500:]}')
            return rel, out
        with ThreadPoolExecutor(max(1, self.jobs)) as pool:
            return dict(pool.map(one, jobs))

    def perft(self, engine):
        lines = []
        for fen in PERFT_FENS:
            code, out = self.run([str(engine), 'perft', '4', fen], timeout=300)
            if code != 0:
                return None
            lines.append(perft_count(out))
        return lines

    def suites(self, build):
        code, log = self.run(['ctest', '--test-dir', str(build), '--output-on-failure', '--no-tests=error',
                              '-j', str(self.jobs), '-R', '^(' + '|'.join(SUITES) + ')$'])
        return suites_passed(code, log), log[-3000:]

    def compiler_version(self):
        """The first line of each configured compiler's --version (CMake's default when none is set), joined by '; '."""
        out = []
        for compiler in self.compilers:
            code, text = self.run([compiler or 'c++', '--version'], timeout=60)
            out.append(text.split('\n')[0].strip() if code == 0 else f'unknown ({compiler or "c++"})')
        return '; '.join(out)

    def bench(self, engine):
        code, out = self.run([str(engine), 'bench'], timeout=600)
        if code != 0:
            return None
        fields = dict(line.split(None, 1) for line in out.strip().split('\n') if ' ' in line)
        return {'nodes': fields.get('nodes', '').strip(), 'signature': fields.get('signature', '').strip()}


def preprocess_command(entry, mode='-E'):
    """A compile_commands.json entry's command turned into `-E` to standard
    output (or `mode`, e.g. -fsyntax-only): its own compiler, defines, include
    paths and flags; no object file, no dependency file."""
    args = list(entry['arguments']) if 'arguments' in entry else shlex.split(entry['command'])
    out, skip = [], False
    for a in args:
        if skip:
            skip = False
            continue
        if a in ('-o', '-MF', '-MT', '-MQ'):
            skip = True
            continue
        if a in ('-c', '-MD', '-MMD') or (a.startswith('-o') and len(a) > 2):
            continue
        out.append(a)
    return out + [mode]


# The correctness suites the gate runs (ctest names). A rename or a dropped
# suite must fail the gate, not shrink it: ctest runs with --no-tests=error
# (exit 8 when nothing matches; checked on CMake 3.22.1, TCEC's) and the
# count it reports must equal this list's.
SUITES = ('search', 'pruning', 'params', 'tt', 'ordering', 'no_alloc')
_CTEST_TOTAL = re.compile(r'tests passed, \d+ tests? failed out of (\d+)')


def suites_passed(code, log):
    """True if ctest exited 0 and ran exactly the gate's suites, no fewer."""
    totals = _CTEST_TOTAL.findall(log)
    return code == 0 and bool(totals) and int(totals[-1]) == len(SUITES)


def perft_count(output):
    """The `nodes N` line of `fork perft` (its time and nps lines vary run to run)."""
    for line in output.split('\n'):
        if line.startswith('nodes '):
            return line.strip()
    return None


# Standard perft positions: the start position and Kiwipete (as in
# tests/suite.hpp, which cites their sources). The gate compares with the
# baseline engine's own counts, so no count is written here.
PERFT_FENS = [
    'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
    'r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1',
]


def run_gate(runner, commit, region_name, region_body, reference, tag):
    """Gate one candidate: `region_body` replaces region `region_name` at `commit`;
    `reference` is the baseline's (make_reference)."""
    violations = static_violations(region_body)
    if violations:
        return GateResult(False, 'static', 'breaks the hot-path rules: ' + ', '.join(violations))
    path = regions.REGIONS[region_name]
    base_text = runner.read(commit, path)
    tree = runner.tree(commit, {path: regions.replace_body(base_text, region_name, region_body)}, tag)
    # The guard reads back what was written, so it checks the file the
    # compiler will see, and every other file of the tree.
    real = runner.read_file(tree, path)
    ok, why = regions.guard({path: base_text}, {path: real}, region_name)
    if ok and regions.body(real, region_name) != regions.body(
            regions.replace_body(base_text, region_name, region_body), region_name):
        ok, why = False, 'the written body differs from the checked one'
    if ok:
        files = runner.snapshot(tree)
        changed = sorted(p for p in set(files) | set(reference.files)
                         if p != path and files.get(p) != reference.files.get(p))
        if changed:
            ok, why = False, 'the tree differs from the baseline outside the region: ' + ', '.join(changed[:10])
    if not ok:
        return GateResult(False, 'guard', why)
    lines = body_lines(real, region_name)
    variants = runner.variants()
    # Every compiler's preprocessed units and their compilation first (a
    # minute or two), then the builds and checks (several minutes each).
    for index, variant in enumerate(variants):
        name = variant.compiler or 'c++'
        configured, log, build = variant.configure(tree)
        if configured:
            configured, log = variant.generate(build)
        if not configured:
            return GateResult(False, 'build', log, compiler=name)
        units = sorted(reference.units[index])
        for unit, text in sorted(variant.preprocess(build, units).items()):
            outside, included = outside_lines(text, tree, path, lines)
            diff = first_difference(reference.units[index][unit], outside) if included else \
                f'{path} is no longer included'
            if diff:
                return GateResult(False, 'preprocessed', f'[{name}] {unit} changes outside the region: {diff}',
                                  compiler=name)
        failure = variant.syntax(build, units)
        if failure:
            return GateResult(False, 'build', f'[{name}] {failure}', compiler=name)
    benches = []
    for variant in variants:
        name = variant.compiler or 'c++'
        built, log, build = variant.build(tree)
        if not built:
            return GateResult(False, 'build', f'[{name}] {log}', compiler=name)
        engine = build / 'fork'
        counts = variant.perft(engine)
        if counts != reference.perft:
            return GateResult(False, 'perft', f'[{name}] {counts} != {reference.perft}', compiler=name)
        passed, log = variant.suites(build)
        if not passed:
            return GateResult(False, 'suites', f'[{name}] {log}', compiler=name)
        first, second = variant.bench(engine), variant.bench(engine)
        if not first or first != second:
            return GateResult(False, 'determinism', f'[{name}] {first} then {second}', compiler=name)
        benches.append((name, first))
    if any(bench != benches[0][1] for _, bench in benches):
        return GateResult(False, 'determinism', 'the compilers disagree: ' +
                          ', '.join(f'{name} {bench}' for name, bench in benches))
    return GateResult(True, 'done', '', benches[0][1])
