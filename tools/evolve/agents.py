"""The loop's agents and their budget (ideas.md idea 23).

Roles (the owner's spec): two proposers with distinct perspectives
(aggressive and cautious), optionally a third reasoning from Fork's search
statistics; an explorer (unconventional proposals, the full-replacement
share, its own protected island); a critic that reviews every proposal
before it is built; an analyst that every N generations summarizes what
wins and loses. Each role's prompt is a file in tools/evolve/prompts/,
combined with the shared context (context.md). All follow the clean-room
rules: no agent is shown, or may consult, another engine's source.

An agent is anything with `ask(role, prompt) -> Reply`. StubAgent answers
from a script (the dry run and the unit tests); CliAgent calls the Claude
Code CLI (`claude -p`) and reads its token use. The orchestrator never
starts a live loop without its explicit --live flag.
"""
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

PROMPTS = Path(__file__).resolve().parent / 'prompts'
ROLES = ('proposer_aggressive', 'proposer_cautious', 'proposer_stats', 'explorer', 'critic', 'analyst')


@dataclass
class Reply:
    text: str
    tokens: int = 0
    usage: dict | None = None  # the CLI's own breakdown, when it gives one


@dataclass
class Proposal:
    mode: str  # 'residual' or 'full'
    rationale: str
    body: str


@dataclass
class Verdict:
    accept: bool
    reasons: str


# The roles that judge or summarize get the shared context's rules and the
# region only: the measurements, the history, the analyst's notes and the
# proposers' reply format are for the proposers.
_CONTEXT_ONLY_RULES = ('critic', 'analyst')
_PROPOSER_PART = "## Fork's measurements"


def prompt_for(role, **fields):
    """The role's prompt: the shared context (for the critic and the analyst,
    only its rules and the region), then the role's file, with {fields} filled in."""
    context = (PROMPTS / 'context.md').read_text(encoding='utf-8')
    if role in _CONTEXT_ONLY_RULES:
        context = context.split(_PROPOSER_PART)[0].rstrip() + '\n'
    text = context + '\n\n' + (PROMPTS / f'{role}.md').read_text(encoding='utf-8')
    for k, v in fields.items():
        text = text.replace('{' + k + '}', str(v))
    return text


_MODE = re.compile(r'^MODE:\s*(residual|full)\s*$', re.M | re.I)
_RATIONALE = re.compile(r'^RATIONALE:\s*(.+?)(?=^```|\Z)', re.M | re.S)
_CODE = re.compile(r'```(?:cpp|c\+\+)?\n(.*?)```', re.S)
_VERDICT = re.compile(r'^VERDICT:\s*(accept|reject)\s*$', re.M | re.I)
_REASONS = re.compile(r'^REASONS:\s*(.+)', re.M | re.S)


def parse_proposal(text):
    """A Proposal from a proposer's or explorer's reply, or None if it is malformed."""
    mode, code = _MODE.search(text), _CODE.search(text)
    if not mode or not code:
        return None
    rationale = _RATIONALE.search(text)
    return Proposal(mode.group(1).lower(), rationale.group(1).strip() if rationale else '', code.group(1))


def parse_verdict(text):
    """The critic's Verdict; an unreadable reply is a rejection."""
    verdict = _VERDICT.search(text)
    reasons = _REASONS.search(text)
    if not verdict:
        return Verdict(False, 'unreadable critic reply')
    return Verdict(verdict.group(1).lower() == 'accept', reasons.group(1).strip() if reasons else '')


class Budget:
    """Tokens, candidates and wall time; `exhausted()` names the first limit reached."""

    def __init__(self, tokens, candidates, seconds, clock):
        self.limits = {'tokens': tokens, 'candidates': candidates, 'seconds': seconds}
        self.used = {'tokens': 0, 'candidates': 0}
        self.clock = clock
        self.start = clock()

    def spend(self, tokens=0, candidates=0):
        self.used['tokens'] += tokens
        self.used['candidates'] += candidates

    def exhausted(self):
        if self.used['tokens'] >= self.limits['tokens']:
            return 'token budget'
        if self.used['candidates'] >= self.limits['candidates']:
            return 'candidate budget'
        if self.clock() - self.start >= self.limits['seconds']:
            return 'time budget'
        return None


class StubAgent:
    """Scripted replies: `script` maps a role to a list of replies, used in order."""

    def __init__(self, script, tokens_per_reply=0):
        self.script = {role: list(replies) for role, replies in script.items()}
        self.tokens = tokens_per_reply
        self.asked = []

    def ask(self, role, prompt):
        self.asked.append((role, prompt))
        replies = self.script.get(role) or ['']
        text = replies.pop(0) if len(replies) > 1 else replies[0]
        return Reply(text, self.tokens)


class CliAgent:
    """A live agent through the Claude Code CLI, with no tools at all.

    Each call is a fresh, non-interactive session (`claude -p`, no session
    kept) in a folder of its own, with every built-in tool and every MCP
    server off (`--tools ""`, `--disallowedTools "*"`, an empty strict MCP
    config) and safe mode (no CLAUDE.md, memory, hooks or plugins), so an
    agent can read nothing and fetch nothing: the clean-room rule enforced
    by the CLI, not only asked in the prompt. The streamed output's init
    event lists the session's tools; a reply from a session whose tool or
    MCP list is not empty is refused. Checked by hand on 2026-10-27 (CLI
    2.1.310): tools [] and mcp [] from WSL through cmd.exe.

    `launcher` is the command that runs the CLI: from WSL, the Windows CLI
    through `cmd.exe /c claude` (its sign-in is the Windows one; the CLI's
    docs do not cover this path, which was tested instead).
    """

    def __init__(self, launcher=('cmd.exe', '/c', 'claude'), workdir='/mnt/c/Users/Public/fork-agent',
                 model='sonnet', max_turns=2, timeout=900):
        self.launcher = list(launcher)
        self.workdir = workdir
        self.model = model
        self.max_turns = max_turns
        self.timeout = timeout

    def command(self):
        return self.launcher + [
            '-p', 'Follow the instructions on stdin.', '--output-format', 'stream-json', '--verbose',
            '--tools', '""', '--disallowedTools', '*', '--strict-mcp-config', '--mcp-config', 'empty-mcp.json',
            '--permission-mode', 'dontAsk', '--max-turns', str(self.max_turns), '--no-session-persistence',
            '--safe-mode', '--disable-slash-commands', '--model', self.model]

    def ask(self, role, prompt):
        import os
        os.makedirs(self.workdir, exist_ok=True)
        with open(os.path.join(self.workdir, 'empty-mcp.json'), 'w', encoding='utf-8') as f:
            f.write('{"mcpServers":{}}')
        p = subprocess.run(self.command(), input=prompt, capture_output=True, text=True, encoding='utf-8',
                           cwd=self.workdir, timeout=self.timeout)
        if p.returncode != 0:
            raise RuntimeError(f'claude -p failed for {role}: {p.stderr[-500:]}')
        return parse_stream(p.stdout, role)


def parse_stream(text, role='agent'):
    """The Reply from a stream-json session; refuses one that had any tool."""
    init, result = None, None
    for line in text.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get('type') == 'system' and event.get('subtype') == 'init':
            init = event
        elif event.get('type') == 'result':
            result = event
    if init is None or result is None:
        raise RuntimeError(f'{role}: no init or result event in the CLI output')
    if init.get('tools') or init.get('mcp_servers'):
        raise RuntimeError(f'{role}: the session had tools ({init.get("tools")}) or MCP servers; reply refused')
    if result.get('subtype') != 'success' or result.get('is_error'):
        raise RuntimeError(f'{role}: the CLI reported {result.get("subtype")}')
    usage = result.get('usage', {})
    tokens = sum(int(usage.get(k, 0) or 0) for k in ('input_tokens', 'output_tokens',
                                                     'cache_creation_input_tokens', 'cache_read_input_tokens'))
    return Reply(result.get('result', ''), tokens, {k: usage.get(k, 0) for k in (
        'input_tokens', 'output_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens')})
