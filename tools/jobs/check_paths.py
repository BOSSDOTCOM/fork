# SPDX-License-Identifier: GPL-3.0-or-later
"""The path check (DESIGN.md section 1, "Paths across Git Bash, PowerShell, Windows Python and WSL"): a static
scan of shell scripts for a Git Bash or WSL path handed to a Windows program without conversion.

Why: Git Bash rewrites a POSIX-looking argument of a Windows program by heuristics (checked on this machine,
2026-11-10): a bare /c/x arrives as C:/x, but /c/x inside -c code or a quoted string arrives untouched,
/c/x=C:/y arrives as 'C:\\x=C;Y:\\', /mnt/c/x arrives as 'C:/Program Files/Git/mnt/c/x' and /home/u as
'C:/Program Files/Git/home/u'. Retrain 8b's chain lost its ready file to the first; job starts lost their WSL
commands (exit 127) to the third. The rule is therefore strict: a Windows program gets Windows-form paths.

Windows programs: a command word ending in .exe (outside /usr and /bin), a .venv/Scripts/ program, the bare
names powershell, pwsh, cmd and wsl, fork_wsl (tools/jobs/paths.sh), a variable assigned one of these (a for
loop's variable too), and a variable named py, python or python3 (any case; ${PYTHON:-python3} included),
since every Python on Windows is a Windows program. A bare python3 is not taken for one.

A function that hands "$@" to a Windows program (ledger() { "$py" ... "$@"; }, wslrun() { wsl.exe ... "$@"; })
is checked at each call like the program itself. A Windows program's NAME=VALUE prefixes are checked like its
arguments: Git Bash rewrites the environment the same way (Z=/mnt/c/q arrives as C:/Program Files/Git/mnt/c/q).

Rules (each finding: FILE:LINE: RULE: message):
  msys-path     a Git Bash drive path (/c/...), literal or in a variable, in a Windows program's argument,
                its environment or the heredoc it reads
  mount-path    a WSL mount path (/mnt/c/...) on the Windows side
  posix-path    another POSIX path on the Windows side: $HOME, an unquoted ~, $PWD, $(pwd), $(mktemp),
                $(dirname ...), a literal /home/ or /root/, or a variable built from one
  wsl-pathconv  an argument for the WSL side of wsl.exe (or of a command that runs wsl.exe, such as
                jobctl start ... -- wsl.exe ...) that starts with a POSIX path, without MSYS_NO_PATHCONV=1
                (on the command or exported earlier) or fork_wsl: Git Bash rewrites it
  wsl-form      a Git Bash drive path (/c/...) on the WSL side, which Linux cannot open
  bad-marker    an exception marker without a reason
  parse         a script the scan cannot read (an unterminated quote or substitution)
Converted forms are clean: $(fork_path win|winbs ...), $(fork_path_for PROGRAM ...), $(cygpath -m|-w ...),
$(wslpath -m|-w ...), $(pwd -W), Windows literals (C:/x), and variables assigned any of these. For the WSL
side, $(fork_path wsl ...) and /mnt/c/... are the right forms, given MSYS_NO_PATHCONV=1 or fork_wsl.
Redirections and here-strings are bash's own and are not checked; an unknown variable ($1, read) is not
flagged.

Intended exceptions: end the line with "# fork-paths: ok REASON", or put that comment alone on the line
above the command (it covers the whole command, continuation lines included). "# fork-paths: ok-file REASON"
anywhere on a line of its own exempts the whole file (for a script that runs only inside WSL or Linux). A
marker without a reason is itself a finding.

    python -I tools/jobs/check_paths.py [FILE|DIR...]   default: the repository's job and chain scripts
                                                       (tools/jobs, tools/github, tools/control_center,
                                                       scripts); exit 1 on any finding
"""
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCOPE = ('tools/jobs', 'tools/github', 'tools/control_center', 'scripts')

DRIVE = re.compile(r'(?<![\w./~-])/[A-Za-z](?=/)')
MOUNT = re.compile(r'(?<![\w./~-])/mnt/[A-Za-z](?=/|$|[\s\'"])')
POSIX_LIT = re.compile(r'(?<![\w./~-])/(?:home|root)/')
MARKER = re.compile(r'#\s*fork-paths:\s*(ok-file|ok)\b([^#]*)')
NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
ASSIGN = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)(\[[^\]]*\])?(\+?)=')
PY_NAME = re.compile(r'^(py|python3?)$', re.IGNORECASE)
KEYWORDS = {'if', 'then', 'else', 'elif', 'do', 'while', 'until', '!', '{', '}', 'time', 'fi', 'done', 'esac',
            'in', ';;'}
WRAPPERS = {'exec', 'nohup', 'command', 'builtin', 'stdbuf', 'nice'}
DECLARE = {'local', 'export', 'declare', 'readonly', 'typeset'}
TAINT_SUBS = re.compile(r'^\s*(?:cd\b.*&&\s*)?(pwd|mktemp|dirname)\b(?!\s+-W)')
CONVERT_WIN = re.compile(r'^\s*(?:fork_path\s+(?:win|winbs)\b|fork_path_for\b|cygpath\s+(?:-\w*[mw]\w*)'
                         r'|wslpath\s+(?:-\w*[mw]\w*)|pwd\s+-W\b)')
CONVERT_WSL = re.compile(r'^\s*(?:fork_path\s+wsl\b|wslpath\s+-u\b|wslpath\s+(?!-)|cygpath\s+-u\b)')


class ParseError(Exception):
    def __init__(self, line, what):
        super().__init__(what)
        self.line = line


# ---- lexing -------------------------------------------------------------------------------------------------

@dataclass
class Word:
    """A shell word: its parts in order. ('lit', text, quote) with quote in '', "'", '"';
    ('var', name, default Word or None); ('sub', [Command], inner text); ('tilde',); ('array', [Word])."""
    line: int
    parts: list = field(default_factory=list)
    redirect: bool = False

    def plain(self):
        return ''.join(p[1] for p in self.parts if p[0] == 'lit')

    def only_literal(self):
        return all(p[0] == 'lit' for p in self.parts)


@dataclass
class Command:
    line: int
    words: list = field(default_factory=list)
    heredocs: list = field(default_factory=list)  # (first body line, body text, quoted)
    end_line: int = 0


class Lexer:
    def __init__(self, text, line=1):
        self.t = text
        self.i = 0
        self.line = line
        self.pending = []  # heredocs waiting for the next newline: (command, delimiter, quoted, strip tabs)
        self.backticks = 0  # inside `...`, a backtick ends the word

    def peek(self, k=0):
        j = self.i + k
        return self.t[j] if j < len(self.t) else ''

    def advance(self, n=1):
        for _ in range(n):
            if self.i < len(self.t):
                if self.t[self.i] == '\n':
                    self.line += 1
                self.i += 1

    def commands(self, closer=None):
        """Commands up to the end, or up to the unmatched closer (')' or '`') when nested."""
        out = []
        cur = None
        depth = 0

        def finish():
            nonlocal cur
            if cur is not None and (cur.words or cur.heredocs):
                cur.end_line = self.line
                out.append(cur)
            cur = None

        while self.i < len(self.t):
            c = self.peek()
            if c in ' \t\r':
                self.advance()
            elif c == '\\' and self.peek(1) == '\n':
                self.advance(2)
            elif c == '#' :
                while self.i < len(self.t) and self.peek() != '\n':
                    self.advance()
            elif c == '\n':
                finish()
                self.advance()
                self.read_heredocs()
            elif closer == '`' and c == '`':
                self.advance()
                finish()
                return out
            elif c in ';&|':
                if c == '&' and self.peek(1) == '>':
                    self.advance()
                    cur = cur or Command(self.line)
                    self.redirect(cur)
                    continue
                finish()
                self.advance()
            elif c == '(':
                if self.peek(1) == '(':  # (( arithmetic ))
                    self.skip_balanced('(', ')')
                    continue
                finish()
                depth += 1
                self.advance()
            elif c == ')':
                if depth == 0 and closer == ')':
                    self.advance()
                    finish()
                    return out
                finish()
                depth = max(0, depth - 1)
                self.advance()
            elif c in '<>':
                cur = cur or Command(self.line)
                if self.peek(1) == '(':  # process substitution
                    w = Word(self.line)
                    self.advance(2)
                    inner_start = self.i
                    w.parts.append(('sub', self.commands(')'), self.t[inner_start:self.i - 1]))
                    cur.words.append(w)
                else:
                    self.redirect(cur)
            else:
                cur = cur or Command(self.line)
                w = self.word()
                if w.parts and w.plain().isdigit() and w.only_literal() and self.peek() in '<>':
                    self.redirect(cur)  # 2>&1, 2>file
                else:
                    cur.words.append(w)
        if closer:
            raise ParseError(self.line, f"unterminated {'$(' if closer == ')' else '`'}")
        finish()
        return out

    def redirect(self, cur):
        op = ''
        while self.peek() in '<>&|-' and len(op) < 3 and self.peek():
            if self.peek() == '-' and not op.startswith('<<'):
                break
            op += self.peek()
            self.advance()
        while self.peek() in ' \t':
            self.advance()
        if op.startswith('<<') and op != '<<<':
            start = self.i
            delim = self.word()
            quoted = any(ch in self.t[start:self.i] for ch in '\'"\\')
            self.pending.append((cur, delim.plain(), quoted, op == '<<-'))
            return
        target = self.word()
        target.redirect = True
        cur.words.append(target)

    def read_heredocs(self):
        for cmd, delim, quoted, strip in self.pending:
            first = self.line
            body = []
            while True:
                if self.i >= len(self.t):
                    raise ParseError(first, f'unterminated heredoc {delim}')
                j = self.t.find('\n', self.i)
                j = len(self.t) if j < 0 else j
                text = self.t[self.i:j]
                self.i = min(j + 1, len(self.t))
                self.line += 1
                if (text.lstrip('\t') if strip else text).rstrip('\r') == delim:
                    break
                body.append(text)
            cmd.heredocs.append((first, '\n'.join(body), quoted))
        self.pending = []

    def skip_balanced(self, open_, close):
        depth = 0
        while self.i < len(self.t):
            c = self.peek()
            if c == open_:
                depth += 1
            elif c == close:
                depth -= 1
                if depth == 0:
                    self.advance()
                    return
            self.advance()
        raise ParseError(self.line, f'unterminated {open_}')

    def word(self):
        w = Word(self.line)
        lit = []
        start = self.i

        def flush(quote=''):
            if lit:
                w.parts.append(('lit', ''.join(lit), quote))
                lit.clear()

        while self.i < len(self.t):
            c = self.peek()
            if c in ' \t\r\n;&|()<>' :
                if c == '(' and lit and ASSIGN.match(''.join(lit) if not w.parts else ''):
                    flush()
                    self.advance()
                    w.parts.append(('array', self.array_words()))
                    continue
                break
            if c == '\\':
                if self.peek(1) == '\n':
                    self.advance(2)
                    continue
                lit.append(self.peek(1))
                self.advance(2)
            elif c == "'":
                flush()
                self.advance()
                j = self.t.find("'", self.i)
                if j < 0:
                    raise ParseError(self.line, 'unterminated single quote')
                w.parts.append(('lit', self.t[self.i:j], "'"))
                self.advance(j - self.i + 1)
            elif c == '"':
                flush()
                self.advance()
                self.double_quoted(w)
            elif c == '$':
                flush()
                self.dollar(w, '')
            elif c == '`':
                if self.backticks:
                    break
                flush()
                self.advance()
                w.parts.append(self.backtick())
            elif c == '~' and self.i == start:
                w.parts.append(('tilde',))
                self.advance()
            else:
                lit.append(c)
                self.advance()
        flush()
        return w

    def array_words(self):
        words = []
        while self.i < len(self.t):
            c = self.peek()
            if c in ' \t\r\n':
                self.advance()
            elif c == ')':
                self.advance()
                return words
            elif c == '#':
                while self.peek() not in ('\n', ''):
                    self.advance()
            else:
                words.append(self.word())
                if not words[-1].parts and self.peek() not in ')':
                    self.advance()  # a stray operator character inside an array: skip it
        raise ParseError(self.line, 'unterminated array')

    def double_quoted(self, w):
        lit = []

        def flush():
            if lit:
                w.parts.append(('lit', ''.join(lit), '"'))
                lit.clear()

        while self.i < len(self.t):
            c = self.peek()
            if c == '"':
                flush()
                self.advance()
                return
            if c == '\\' and self.peek(1) in '"\\$`\n':
                if self.peek(1) != '\n':
                    lit.append(self.peek(1))
                self.advance(2)
            elif c == '$':
                flush()
                self.dollar(w, '"')
            elif c == '`' and not self.backticks:
                flush()
                self.advance()
                w.parts.append(self.backtick())
            else:
                lit.append(c)
                self.advance()
        raise ParseError(self.line, 'unterminated double quote')

    def backtick(self):
        inner_start = self.i
        self.backticks += 1
        try:
            cmds = self.commands('`')
        finally:
            self.backticks -= 1
        return ('sub', cmds, self.t[inner_start:self.i - 1])

    def dollar(self, w, quote):
        nxt = self.peek(1)
        if nxt == '(' and self.peek(2) == '(':
            self.advance()
            self.skip_balanced('(', ')')
            return
        if nxt == '(':
            self.advance(2)
            inner_start = self.i
            w.parts.append(('sub', self.commands(')'), self.t[inner_start:self.i - 1]))
            return
        if nxt == '{':
            self.advance(2)
            j, depth = self.i, 1
            while j < len(self.t) and depth:
                ch = self.t[j]
                if ch == '\\':
                    j += 2
                    continue
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                elif ch in '"\'' :
                    k = self.t.find(ch, j + 1)
                    j = k if k >= 0 else len(self.t)
                j += 1
            if depth:
                raise ParseError(self.line, 'unterminated ${')
            inner = self.t[self.i:j - 1]
            self.advance(j - self.i)
            m = re.match(r'[#!]?([A-Za-z_][A-Za-z0-9_]*|[0-9@*#?$!-])(\[[^\]]*\])?', inner)
            name = m.group(1) if m else ''
            default = None
            rest = inner[m.end():] if m else ''
            dm = re.match(r':?[-=]', rest)
            if dm:
                default = Lexer(rest[dm.end():], self.line).word_from_text()
            w.parts.append(('var', name, default))
            return
        if nxt == "'":  # $'...'
            self.advance(2)
            j = self.i
            while j < len(self.t) and self.t[j] != "'":
                j += 2 if self.t[j] == '\\' else 1
            w.parts.append(('lit', self.t[self.i:j], "'"))
            self.advance(j - self.i + 1)
            return
        m = NAME.match(self.t, self.i + 1)
        if m:
            w.parts.append(('var', m.group(0), None))
            self.advance(1 + len(m.group(0)))
            return
        if nxt and nxt in '0123456789@*#?$!-':
            w.parts.append(('var', nxt, None))
            self.advance(2)
            return
        w.parts.append(('lit', '$', quote))
        self.advance()

    def word_from_text(self):
        """The whole text as one word, spaces included (a ${X:-default}'s default)."""
        w = Word(self.line)
        while self.i < len(self.t):
            sub = self.word()
            w.parts.extend(sub.parts)
            if self.i < len(self.t):
                w.parts.append(('lit', self.peek(), '"'))
                self.advance()
        return w


# ---- analysis -----------------------------------------------------------------------------------------------

@dataclass
class Finding:
    path: str
    line: int
    rule: str
    message: str

    def __str__(self):
        return f'{self.path}:{self.line}: {self.rule}: {self.message}'


@dataclass
class VarState:
    """What the scan knows of a variable: the taints it holds (kind, origin) and whether it names a Windows
    program ('exe' or 'wsl')."""
    taints: list = field(default_factory=list)
    program: str = ''
    converted: str = ''


def sub_kind(inner):
    if CONVERT_WIN.match(inner):
        return 'win'
    if CONVERT_WSL.match(inner):
        return 'wsl'
    return ''


def word_info(word, state):
    """(taints, leads, program, converted) of a word: taints as (kind, description) for every tainted path in
    it; leads: whether it starts with a path (or has NAME=path), what Git Bash rewrites; program: 'exe' or
    'wsl' if the word names a Windows program; converted: 'win' or 'wsl' if the word is one conversion."""
    taints, leads, program, converted = [], False, '', ''
    subs = [p for p in word.parts if p[0] == 'sub']
    nonblank = [p for p in word.parts if not (p[0] == 'lit' and p[1] == '')]
    if len(nonblank) == 1 and nonblank[0][0] == 'sub':
        converted = sub_kind(nonblank[0][2])
    first = True
    after_eq = False
    for p in word.parts:
        kind = p[0]
        if kind == 'lit':
            text = p[1]
            for rx, k in ((DRIVE, 'msys'), (MOUNT, 'mount'), (POSIX_LIT, 'posix')):
                for m in rx.finditer(text):
                    if k == 'msys' and MOUNT.match(text, m.start() - 4 if m.start() >= 4 else 0) and \
                            text[max(0, m.start() - 4):m.start()] == '/mnt':
                        continue
                    taints.append((k, f'the literal path {text[m.start():m.start() + 24]!r}'))
            if (first and text.startswith('/')) or re.match(r'^[^/]*=/', text):
                leads = True
            after_eq = text.endswith('=')
        elif kind == 'tilde':
            taints.append(('posix', 'an unquoted ~ (the shell\'s home)'))
            leads = leads or first
        elif kind == 'var':
            name, default = p[1], p[2]
            vs = state.get(name)
            got = [(k, d if d.startswith(f'${name} ') else f'${name} (holding {d})') for k, d in
                   (vs.taints if vs else [])]
            if name in ('HOME', 'PWD', 'OLDPWD', 'TMPDIR', '0', 'BASH_SOURCE'):
                got.append(('posix', f'${name}'))
            if default is not None:
                got += [(k, f'${name} (defaulting to {d})') for k, d in word_info(default, state)[0]]
            taints += got
            if got and (first or after_eq):
                leads = True
            after_eq = False
        elif kind == 'sub':
            ck = sub_kind(p[2])
            if not ck and TAINT_SUBS.match(p[2]):
                taints.append(('posix', f'$({p[2].strip()[:30]})'))
                leads = leads or first or after_eq
            after_eq = False
        elif kind == 'array':
            for aw in p[1]:
                taints += word_info(aw, state)[0]
        first = False
    program = word_program(word, state)
    return taints, leads, program, converted


def word_program(word, state):
    plain = word.plain()
    parts = word.parts
    if parts and all(p[0] == 'lit' for p in parts):
        base = plain.replace('\\', '/').rsplit('/', 1)[-1].lower()
        if base in ('wsl', 'wsl.exe'):
            return 'wsl'
        if base == 'fork_wsl':
            return 'fork_wsl'
        if plain.startswith(('/usr/', '/bin/')):
            return ''
        if base.endswith('.exe') or base in ('powershell', 'pwsh', 'cmd') or '/Scripts/' in plain.replace('\\', '/'):
            return 'exe'
        return ''
    vars_ = [p for p in parts if p[0] == 'var']
    if len(vars_) == 1 and all(p[0] == 'var' or (p[0] == 'lit' and p[1] == '') for p in parts):
        name, default = vars_[0][1], vars_[0][2]
        vs = state.get(name)
        if vs and vs.program:
            return vs.program
        if PY_NAME.match(name):
            return 'exe'
        if default is not None and word_program(default, state):
            return word_program(default, state)
    return ''


class Scanner:
    def __init__(self, path, text):
        self.path = path
        self.lines = text.split('\n')
        self.state = {}
        self.nopathconv = False
        self.findings = []
        self.function = None  # the function whose body is being read
        self.braces = 0
        self.wrappers = {}  # function -> (side, nopathconv): it passes "$@" to a Windows program
        self.ok_lines = {}  # line -> reason
        for n, line in enumerate(self.lines, 1):
            m = MARKER.search(line)
            if m:
                self.ok_lines[n] = (m.group(1), m.group(2).strip(), line.lstrip().startswith('#'))

    def exempt(self, cmd, line):
        for n in (line, cmd.line):
            mk = self.ok_lines.get(n)
            if mk and mk[0] == 'ok' and mk[1]:
                return True
        mk = self.ok_lines.get(cmd.line - 1)
        return bool(mk and mk[0] == 'ok' and mk[1] and mk[2])

    def add(self, cmd, line, rule, message):
        if not self.exempt(cmd, line):
            self.findings.append(Finding(self.path, line, rule, message))

    def run(self, commands):
        for n, (kind, reason, alone) in sorted(self.ok_lines.items()):
            if not reason:
                self.findings.append(Finding(self.path, n, 'bad-marker',
                                             f'"fork-paths: {kind}" needs a reason after it'))
        if any(k == 'ok-file' and r and alone for k, r, alone in self.ok_lines.values()):
            return [f for f in self.findings if f.rule == 'bad-marker']
        self.walk(commands)
        seen, out = set(), []
        for f in sorted(self.findings, key=lambda f: (f.line, f.rule)):
            if (f.line, f.rule) not in seen:
                seen.add((f.line, f.rule))
                out.append(f)
        return out

    def walk(self, commands):
        for k, cmd in enumerate(commands):
            for w in cmd.words:
                self.walk_word_subs(w)
            # A function definition, NAME() { ... }: the lexer gives NAME alone, then the body's commands.
            first = cmd.words[0].plain() if cmd.words and cmd.words[0].only_literal() else ''
            if self.function is None and len(cmd.words) == 1 and NAME.fullmatch(first) and k + 1 < len(commands) \
                    and commands[k + 1].words and commands[k + 1].words[0].plain() == '{':
                self.function, self.braces = first, 0
                continue
            if self.function is not None:
                self.braces += sum(1 for w in cmd.words if w.only_literal() and w.plain() == '{')
                self.braces -= sum(1 for w in cmd.words if w.only_literal() and w.plain() == '}')
            self.command(cmd)
            if self.function is not None and self.braces <= 0:
                self.function = None

    def walk_word_subs(self, w):
        for p in w.parts:
            if p[0] == 'sub':
                self.walk(p[1])
            elif p[0] == 'array':
                for aw in p[1]:
                    self.walk_word_subs(aw)
            elif p[0] == 'var' and p[2] is not None:
                self.walk_word_subs(p[2])

    def assign(self, word, prefix_only=False):
        text = word.plain() if word.parts and word.parts[0][0] == 'lit' else ''
        m = ASSIGN.match(text)
        if not m:
            return False
        if prefix_only:
            return True
        name, append = m.group(1), m.group(3)
        value = Word(word.line, [('lit', word.parts[0][1][m.end():], word.parts[0][2])] + word.parts[1:])
        taints, _, program, converted = word_info(value, self.state)
        old = self.state.get(name) if append else None
        vs = VarState(taints=(old.taints if old else []) + ([] if converted else taints),
                      program=program or (old.program if old else ''), converted=converted)
        self.state[name] = vs
        return True

    def command(self, cmd):
        words = [w for w in cmd.words if not w.redirect]
        i = 0
        prefix_nopathconv = False
        while i < len(words):
            p = words[i].plain() if words[i].only_literal() else None
            if p in KEYWORDS:
                i += 1
                continue
            break
        if i < len(words) and words[i].only_literal() and words[i].plain() == 'for' and i + 1 < len(words):
            var = words[i + 1].plain()
            vals = words[i + 3:] if i + 2 < len(words) and words[i + 2].plain() == 'in' else []
            vs = VarState()
            for v in vals:
                t, _, prog, conv = word_info(v, self.state)
                vs.taints += [] if conv else t
                vs.program = vs.program or prog
            self.state[var] = vs
            return
        if i < len(words) and words[i].only_literal() and words[i].plain() in ('case', 'select', 'function'):
            return
        # NAME=VALUE words: alone, they set variables; before a command, they are its environment.
        j = i
        while j < len(words) and self.assign(words[j], prefix_only=True):
            j += 1
        if j == len(words):
            for w in words[i:j]:
                self.assign(w)
            return
        env_words = words[i:j]
        for w in env_words:
            if w.plain().startswith(('MSYS_NO_PATHCONV=', 'MSYS2_ARG_CONV_EXCL=')):
                prefix_nopathconv = True
        i = j
        head = words[i].plain() if words[i].only_literal() else None
        if head in DECLARE:
            for w in words[i + 1:]:
                if w.only_literal() and w.plain() in ('MSYS_NO_PATHCONV=1', "MSYS2_ARG_CONV_EXCL=*"):
                    if head == 'export':
                        self.nopathconv = True
                if not self.assign(w) and w.only_literal() and w.plain() == 'MSYS_NO_PATHCONV' and head == 'export':
                    self.nopathconv = self.nopathconv or bool(self.state.get('MSYS_NO_PATHCONV'))
            return
        while i < len(words):
            h = words[i].plain() if words[i].only_literal() else None
            if h in WRAPPERS:
                i += 1
            elif h == 'env':
                i += 1
                while i < len(words) and (self.assign(words[i], True) or words[i].plain().startswith('-')):
                    if words[i].plain().startswith(('MSYS_NO_PATHCONV=', 'MSYS2_ARG_CONV_EXCL=')):
                        prefix_nopathconv = True
                    i += 1
            elif h == 'timeout':
                i += 1
                while i < len(words) and words[i].plain().startswith('-'):
                    i += 1
                i += 1  # the duration
            else:
                break
        if i >= len(words):
            return
        if words[i].only_literal() and words[i].plain() == 'read':
            for w in words[i + 1:]:
                if w.only_literal() and NAME.fullmatch(w.plain()):
                    self.state[w.plain()] = VarState()
            return
        head = words[i].plain() if words[i].only_literal() else None
        if head in self.wrappers:
            side, nopathconv = self.wrappers[head]
            nopathconv = nopathconv or prefix_nopathconv or self.nopathconv
            program = 'wrapper'
        else:
            program = word_program(words[i], self.state)
            if not program:
                return
            nopathconv = prefix_nopathconv or self.nopathconv or program == 'fork_wsl'
            side = 'wsl' if program in ('wsl', 'fork_wsl') else 'win'
        heredoc_side = side
        # NAME=VALUE before a Windows program: its environment, which Git Bash rewrites like a bare argument.
        for w in env_words if program in ('exe', 'wrapper') and side == 'win' else []:
            m = ASSIGN.match(w.plain() if w.parts and w.parts[0][0] == 'lit' else '')
            value = Word(w.line, [('lit', w.parts[0][1][m.end():], w.parts[0][2])] + w.parts[1:])
            taints, _, _, converted = word_info(value, self.state)
            for kind, desc in [] if converted else taints:
                self.add(cmd, w.line, {'msys': 'msys-path', 'mount': 'mount-path', 'posix': 'posix-path'}[kind],
                         f'{desc}, in the environment of a Windows program; convert it: '
                         f'"$(fork_path_for PROGRAM PATH)" (tools/jobs/paths.sh)')
        for w in words[i + 1:]:
            if self.function and any(p[0] == 'var' and p[1] in '@*' for p in w.parts):
                self.wrappers[self.function] = (side, nopathconv)
            taints, leads, prog, converted = word_info(w, self.state)
            if side == 'win' and prog in ('wsl', 'fork_wsl'):
                side = 'wsl'
                nopathconv = nopathconv or prog == 'fork_wsl'
                continue
            if converted:
                continue
            if side == 'win':
                for kind, desc in taints:
                    self.add(cmd, w.line, {'msys': 'msys-path', 'mount': 'mount-path', 'posix': 'posix-path'}[kind],
                             f'{desc} reaches a Windows program; convert it: "$(fork_path_for PROGRAM PATH)" '
                             f'or "$(fork_path win PATH)" (tools/jobs/paths.sh)')
            else:
                if any(k == 'msys' for k, _ in taints):
                    self.add(cmd, w.line, 'wsl-form', 'a Git Bash /c/ path on the WSL side; Linux needs '
                             '"$(fork_path wsl PATH)" (/mnt/c/...)')
                elif leads and not nopathconv:
                    self.add(cmd, w.line, 'wsl-pathconv', 'a POSIX path for WSL passed through Git Bash, which '
                             'rewrites it; use fork_wsl or MSYS_NO_PATHCONV=1 (tools/jobs/paths.sh)')
        for first, body, quoted in cmd.heredocs:
            if heredoc_side != 'win':
                continue
            for k, line in enumerate(body.split('\n')):
                n = first + k
                for rx, kind in ((DRIVE, 'msys'), (MOUNT, 'mount')):
                    for m in rx.finditer(line):
                        if kind == 'msys' and line[max(0, m.start() - 4):m.start()] == '/mnt':
                            continue
                        self.add(cmd, n, f'{kind}-path' if kind == 'msys' else 'mount-path',
                                 f'the literal path {line[m.start():m.start() + 24]!r} in the heredoc a Windows '
                                 'program reads')
                if quoted:
                    continue
                for m in re.finditer(r'\$\{?([A-Za-z_][A-Za-z0-9_]*)', line):
                    vs = self.state.get(m.group(1))
                    got = list(vs.taints) if vs else []
                    if m.group(1) in ('HOME', 'PWD'):
                        got.append(('posix', '$' + m.group(1)))
                    for kind, desc in got:
                        self.add(cmd, n, {'msys': 'msys-path', 'mount': 'mount-path', 'posix': 'posix-path'}[kind],
                                 f'${m.group(1)} ({desc}) in the heredoc a Windows program reads; convert it '
                                 'first (tools/jobs/paths.sh)')


def scan_text(text, path='<text>'):
    try:
        commands = Lexer(text).commands()
    except ParseError as e:
        return [Finding(str(path), e.line, 'parse', f'cannot read the script: {e}')]
    return Scanner(str(path), text).run(commands)


def scan_file(path):
    path = Path(path)
    try:  # named relative to the current folder where it can be: no home folder in the messages
        shown = path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        shown = path.as_posix()
    return scan_text(path.read_text(encoding='utf-8', errors='replace'), shown)


def repository_scripts():
    r = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '--', *(f'{d}/*.sh' for d in SCOPE)],
                       capture_output=True, text=True, check=True)
    return [ROOT / f for f in r.stdout.split() if '/fixtures/' not in f]


def main(argv):
    files = []
    for a in argv:
        p = Path(a)
        files += sorted(p.rglob('*.sh')) if p.is_dir() else [p]
    if not argv:
        files = repository_scripts()
    found = []
    for f in files:
        try:
            found += scan_file(f)
        except OSError as e:
            print(f'{f}: cannot read: {e}', file=sys.stderr)
            return 2
    for f in found:
        print(f)
    return 1 if found else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
