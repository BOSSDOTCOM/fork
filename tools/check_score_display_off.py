# SPDX-License-Identifier: GPL-3.0-or-later

"""Every harness that plays or searches with Fork sets CalibratedScore off (owner, 2026-11-12).

Fork's CalibratedScore option (src/uci/score_display.hpp, default on for GUIs and TCEC) changes only the
centipawn number in its info lines. Anything that reads those numbers must see Fork's raw scores: fastchess's
resign and draw adjudication in SPRT, head-to-head, fixed-node, gauntlet, anchor-check and decision-audit games
(an engine with the option on and one without would be adjudicated asymmetrically), and every tool that labels,
measures or analyses positions from Fork's search scores.

This check walks the tracked files under tools/, scripts/, bench/ and .github/ and finds every file that
launches an engine: a fastchess command (`-engine` with `cmd=`), or a UCI handshake (waiting for `uciok`,
python-chess's `popen_uci`, or writing `uci` and waiting for `readyok`). Each one must set the option off
(`option.CalibratedScore=false` for fastchess, `setoption name CalibratedScore value false` or python-chess's
`{'CalibratedScore': False}` over UCI, or the pair `('CalibratedScore', 'false')` a setoption loop sends), or be
listed in EXEMPT with the reason it cannot read a Fork score.
Builds without the option are unaffected: fastchess 1.8.2 warns "doesn't have option" and plays on (checked
2026-11-12 with the pinned release), and Fork answers an unknown setoption with one info string.

Workflows (owner, 2026-11-13: "make every harness force the option off by default, including branch workflows"):
every workflow under .github/workflows that plays games with Fork (it names fastchess, cutechess, run_shard.sh,
elo_gauntlet.sh or tools/sprt.sh) must also run .github/ci/score-display-check.sh on the engines it built, before
its games: if an engine advertises CalibratedScore, that step runs this check on the run's own harness and stops
the run if it fails. A later branch's workflow thereby checks itself; a branch older than this rule cannot, which is
why every dispatcher also calls tools/jobs/score_display_guard.py before it dispatches.

    check_score_display_off.py [REPO]     exit 0 if every launcher and workflow is covered, 1 with the list otherwise
"""
import re
import subprocess
import sys
from pathlib import Path

ROOTS = ('tools/', 'scripts/', 'bench/', '.github/')
LAUNCH = [re.compile(r'-engine\b[^\n]*cmd='), re.compile(r"'-engine',\s*f?'cmd="), re.compile(r'\buciok\b'),
          re.compile(r'popen_uci'), re.compile(r"['\"]uci\\n")]
OFF = [re.compile(r'option\.CalibratedScore=false'), re.compile(r'setoption name CalibratedScore value false'),
       re.compile(r"\{'CalibratedScore': False\}"),
       # a (name, value) pair fed to a setoption loop (tools/nnue/uho_diag.py, 2026-11-13)
       re.compile(r"\(\s*['\"]CalibratedScore['\"]\s*,\s*['\"]false['\"]\s*\)")]
EXEMPT = {
    '.github/ci/score-display-check.sh': "reads each built engine's option list (uci, quit): no search, no score; it "
                                         'runs this check when an engine has the option',
    '.github/workflows/ci.yml': "counts the tuning build's option lines (uci, quit): no search, no score",
    'scripts/uci-smoke.sh': 'sends only uci, isready and quit: no search, no score',
    'tools/gauntlet/build_anchor.sh': 'checks an anchor engine answers uciok; never runs Fork',
    'tools/get_anchor_engines.sh': 'checks the anchor engines answer uciok; never runs Fork',
    'tools/test_sprt.sh': "tools/sprt.sh's test against a fake fastchess; the real command is checked in tools/sprt.sh",
    'tools/measure/test_game_replay.py': "game_replay.py's test against a fake engine; the real handshake is checked in "
                                         'tools/measure/game_replay.py',
    'tools/check_score_display_off.py': 'this check',
}

WORKFLOWS = '.github/workflows/'
PLAYS = [re.compile(r'\bfastchess\b'), re.compile(r'\bcutechess'), re.compile(r'\brun_shard\.sh\b'),
         re.compile(r'\belo_gauntlet\.sh\b'), re.compile(r'\btools/sprt\.sh\b')]
BELT = re.compile(r'^\s*(?:run:\s*)?bash \.github/ci/score-display-check\.sh\s+\S', re.M)


def tracked(repo):
    out = subprocess.run(['git', '-C', str(repo), 'ls-files'], capture_output=True, text=True, check=True).stdout
    return [f for f in out.splitlines() if f.startswith(ROOTS)]


def launchers(repo):
    found = []
    for f in tracked(repo):
        p = repo / f
        if p.suffix not in ('.sh', '.py', '.yml', '.yaml', '.ps1', ''):
            continue
        try:
            text = p.read_text(encoding='utf-8')
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
        if any(r.search(text) for r in LAUNCH):
            found.append((f, any(r.search(text) for r in OFF)))
    return found


def workflows_without_belt(repo):
    """The workflows that play games with Fork but never run .github/ci/score-display-check.sh."""
    found = []
    for f in tracked(repo):
        if not f.startswith(WORKFLOWS) or Path(f).suffix not in ('.yml', '.yaml'):
            continue
        try:
            text = (repo / f).read_text(encoding='utf-8')
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
        if any(r.search(text) for r in PLAYS) and not BELT.search(text):
            found.append(f)
    return found


def main():
    repo = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1])
    missing = [f for f, off in launchers(repo) if not off and f not in EXEMPT]
    stale = [f for f in EXEMPT if not (repo / f).exists()]
    unbelted = workflows_without_belt(repo)
    for f in missing:
        print(f'check_score_display_off: {f} launches an engine without setting CalibratedScore off', file=sys.stderr)
    for f in stale:
        print(f'check_score_display_off: EXEMPT lists {f}, which does not exist', file=sys.stderr)
    for f in unbelted:
        print(f'check_score_display_off: {f} plays games with Fork but never runs .github/ci/score-display-check.sh '
              'on the engines it built', file=sys.stderr)
    if missing or stale or unbelted:
        return 1
    print(f'check_score_display_off: ok ({len(launchers(repo))} launchers, {len(EXEMPT)} exempt; workflows checked)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
