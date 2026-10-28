# SPDX-License-Identifier: GPL-3.0-or-later

"""The evaluator funnel's last two stages (ideas.md idea 23): a short
fast-game match against the baseline, then the hand-off to a full SPRT.

The match is fastchess, candidate against baseline, each opening with both
colours, from Fork's own random openings (never a tuning book). It only
filters: a candidate that loses clearly in a few hundred fast games is not
worth an SPRT. The SPRT itself is not run here: hand_off() writes the
patch and the commands for tools/sprt.sh (gainer bounds [0, 3], STC then
LTC per the LTC rule), and the survivor's constants go to the
originality-checker first (the owner's rule for every search constant).
"""
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

_ELO = re.compile(r'Elo:\s*(-?[0-9.]+)\s*\+/-\s*([0-9.]+)')
_GAMES = re.compile(r'Games:\s*(\d+),\s*Wins:\s*(\d+),\s*Losses:\s*(\d+),\s*Draws:\s*(\d+)')


@dataclass
class MatchResult:
    games: int
    wins: int
    losses: int
    draws: int
    elo: float
    error: float

    def passes(self, floor):
        """Kept unless clearly worse: the upper end of the Elo interval is above `floor`."""
        return self.games > 0 and self.elo + self.error > floor


def parse(output):
    """The last report in a fastchess log."""
    elos, games = _ELO.findall(output), _GAMES.findall(output)
    if not elos or not games:
        return None
    elo, error = elos[-1]
    g, w, l, d = (int(x) for x in games[-1])
    return MatchResult(g, w, l, d, float(elo), float(error))


def run_match(fastchess, candidate, baseline, book, games, tc, concurrency, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    cmd = [str(fastchess), '-engine', f'cmd={candidate}', 'name=candidate',
           '-engine', f'cmd={baseline}', 'name=baseline',
           '-each', f'tc={tc}', 'option.Hash=16', 'option.Threads=1',
           '-openings', f'file={book}', 'format=epd', 'order=random', '-srand', '20261027',
           '-rounds', str(games // 2), '-repeat', '-concurrency', str(concurrency),
           '-pgnout', f'file={out / "match.pgn"}']
    p = subprocess.run(cmd, cwd=out, capture_output=True, text=True, encoding='utf-8', errors='replace')
    (out / 'match.log').write_text(p.stdout + p.stderr, encoding='utf-8')
    return parse(p.stdout)


def hand_off(out_dir, cid, region_file, patch, base_commit):
    """Writes the survivor's patch and the SPRT commands; returns the commands file."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / f'candidate-{cid}.patch').write_text(patch, encoding='utf-8', newline='')
    name = f'evolve-{cid}'
    text = f"""# Candidate {cid}: SPRT hand-off (ideas.md idea 23; not run by the loop)
# 1. The originality-checker screens the region's constants and structure.
# 2. Apply the patch on a branch from {base_commit}, run the full check, commit:
git switch -c {name} {base_commit}
git apply {out / f'candidate-{cid}.patch'}   # changes {region_file} only
# 3. SPRT on gainer bounds, short time control, then long (the LTC rule):
tools/sprt.sh {name} {base_commit} <commit of step 2> 0 3 8+0.08
tools/sprt.sh {name}-ltc {base_commit} <commit of step 2> 0 3 40+0.4 64
"""
    path = out / f'candidate-{cid}-sprt.txt'
    path.write_text(text, encoding='utf-8')
    return path
