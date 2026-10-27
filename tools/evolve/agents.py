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


@dataclass
class Proposal:
    mode: str  # 'residual' or 'full'
    rationale: str
    body: str


@dataclass
class Verdict:
    accept: bool
    reasons: str


def prompt_for(role, **fields):
    """The role's prompt: the shared context, then the role's file, with {fields} filled in."""
    text = (PROMPTS / 'context.md').read_text(encoding='utf-8') + '\n\n' + \
        (PROMPTS / f'{role}.md').read_text(encoding='utf-8')
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
    """A live agent through the Claude Code CLI (not run in the pilot's preparation)."""

    def __init__(self, model=None, timeout=900):
        self.model = model
        self.timeout = timeout

    def ask(self, role, prompt):
        cmd = ['claude', '-p', '--output-format', 'json']
        if self.model:
            cmd += ['--model', self.model]
        p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=self.timeout)
        if p.returncode != 0:
            raise RuntimeError(f'claude -p failed for {role}: {p.stderr[-500:]}')
        out = json.loads(p.stdout)
        usage = out.get('usage', {})
        tokens = sum(int(usage.get(k, 0)) for k in ('input_tokens', 'output_tokens',
                                                     'cache_creation_input_tokens', 'cache_read_input_tokens'))
        return Reply(out.get('result', ''), tokens)
