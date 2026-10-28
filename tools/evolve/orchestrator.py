"""The heuristic-discovery loop's orchestrator (ideas.md idea 23, DESIGN.md
§5.2 deliverable 8c): a deterministic script, not an agent.

Each generation, for every island in turn: choose parents from the island's
grid (seeded), ask the island's agent for a proposal (residual mode, or a
full replacement for the explorer's share), have the critic review it, gate
it (static rules, guard, build, perft, the correctness suites, determinism),
score it on the proxies at the baseline's node budget, place it in the
grid by its behaviour descriptors, and promote clear proxy winners to the
short match and the SPRT hand-off. Every N generations the analyst
summarizes; the explorer's island is protected for its first generations;
the weakest proposer island is reseeded from the best now and then
(FunSearch-style). The run stops at the first of: the generation limit, a
budget (tokens, candidates, wall time), no improvement for `patience`
generations, or a gate-failure rate that says something is broken.

Runs in WSL (Linux builds, fastchess). A live loop needs --live; the pilot's
preparation only runs --dry-run with stub agents.

    python3 tools/evolve/orchestrator.py --config tools/evolve/config.json --run-dir ~/fork-evolve/run1 \\
        (--dry-run | --live) [--generations G]
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import agents  # noqa: E402
import dashboard  # noqa: E402
import gate  # noqa: E402
import match  # noqa: E402
import population  # noqa: E402
import proxies  # noqa: E402
import regions  # noqa: E402


# The agents' context, trimmed to what they use (owner, 2026-10-27): the last
# RecentScores candidates in compact form; parents and analyst rows with
# their scores, never the per-position lists or full records.
RecentScores = 8


def score_text(fitness, proxies_json, descriptors_json):
    """', fitness F, gain +G [L, H], trigger T%' (the parts known), for an agent."""
    if fitness is None:
        return ''
    p = json.loads(proxies_json) if proxies_json else {}
    d = json.loads(descriptors_json) if descriptors_json else []
    out = f', fitness {fitness:.4f}'
    if 'gain_low' in p:
        out += f', gain {p["gain"]:+.4f} [{p["gain_low"]:+.4f}, {p["gain_high"]:+.4f}]'
    if len(d) > 2:
        out += f', trigger {100 * d[2]:.1f}%'
    return out


def summary_line(row):
    """One analyst line from (id, generation, island, mode, rationale, status, critic, proxies, descriptors,
    fitness, body): no per-position scores, no gate log."""
    cid, gen, island, mode, rationale, status, critic, proxies_json, descriptors_json, fitness, body = row
    d = json.loads(descriptors_json) if descriptors_json else []
    shape = f', mean reduction {d[0]:.3f}, re-searched {100 * d[1]:.2f}%' if len(d) > 1 else ''
    verdict = json.loads(critic) if critic else {}
    reasons = f', critic: {verdict.get("reasons", "")[:200]}' if verdict and not verdict.get('accept') else ''
    return (f'- #{cid} g{gen} {island} {mode} {status}{score_text(fitness, proxies_json, descriptors_json)}{shape}'
            f', inputs {population.inputs_used(body or "")}{reasons}: {(rationale or "")[:240]}')


class Loop:
    def __init__(self, cfg, run_dir, agent, runner, clock=time.time):
        self.cfg = cfg
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.agent = agent
        self.runner = runner
        self.pop = population.Population(str(self.run_dir / 'population.sqlite'))
        self.budget = agents.Budget(cfg['budget']['tokens'], cfg['budget']['candidates'],
                                    cfg['budget']['hours'] * 3600, clock)
        self.log_file = open(self.run_dir / 'run.log', 'a', encoding='utf-8')
        self.insights = '(none yet)'
        self.best_fitness, self.best_generation = None, 0
        self.labels = proxies.load_positions(cfg['positions'], 'evolve')[:cfg.get('positions_limit') or None]
        self.statistics = '(baseline statistics not measured yet)'

    def say(self, generation, kind, detail):
        self.pop.log(generation, kind, detail)
        self.log_file.write(json.dumps({'t': round(time.time(), 1), 'gen': generation, 'kind': kind,
                                        'detail': detail}) + '\n')
        self.log_file.flush()
        self.generation_now = max(getattr(self, 'generation_now', 0), generation)
        self.refresh()

    def refresh(self, status=None):
        """The state file and the live dashboard (dashboard.py); never stops the run."""
        if status:
            self.status = status
        state = {'run': self.run_dir.name, 'region': self.cfg['region'], 'status': getattr(self, 'status', 'running'),
                 'generation': getattr(self, 'generation_now', 0), 'generations': self.cfg.get('generations'),
                 'budget_used': self.budget.used, 'budget_limits': self.budget.limits,
                 'elapsed_seconds': self.budget.clock() - self.budget.start, 'islands': self.cfg['islands'],
                 'explorer_protected': self.cfg['explorer_protected']}
        try:
            (self.run_dir / 'state.json').write_text(json.dumps(state, indent=1))
            mirror = self.cfg.get('dashboard_mirror')
            dashboard.render(self.run_dir, mirror and str(Path(mirror) / self.run_dir.name))
        except Exception as e:  # noqa: BLE001 (the dashboard must never stop a run)
            self.log_file.write(json.dumps({'kind': 'dashboard_error', 'detail': str(e)}) + '\n')

    # --- the funnel for one body -------------------------------------------------
    def evaluate(self, generation, cid, island, body, place=True):
        """Gate, proxies and (if `place`) the grid for candidate `cid`; returns its fitness or None."""
        cfg = self.cfg
        self.refresh(status=f'generation {generation}: gating candidate {cid}')
        result = gate.run_gate(self.runner, cfg['baseline_commit'], cfg['region'], body, self.baseline_perft,
                               f'cand-{cid}')
        self.pop.update(cid, gate=json.dumps(result.__dict__))
        if not result.passed:
            self.pop.update(cid, status=f'gate:{result.step}')
            self.say(generation, 'gate_failed', {'id': cid, 'step': result.step, 'detail': result.detail[-400:]})
            return None
        engine = self.runner.work / f'cand-{cid}' / 'build' / 'fork'
        self.refresh(status=f'generation {generation}: measuring candidate {cid}')
        proxy = proxies.run_proxies(engine, self.labels, cfg['proxy_nodes'], cfg.get('proxy_jobs', 1))
        desc = self.descriptors(f'cand-{cid}')
        fitness = proxy.fitness()
        record = dict(proxy.__dict__)
        base = getattr(self, 'baseline_scores', None)
        interval = proxies.paired_interval(proxy.per_position, base, self.cfg['seed'] + cid) if base else None
        if interval:
            record.update(gain=interval[0], gain_low=interval[1], gain_high=interval[2])
        self.pop.update(cid, status='scored', proxies=json.dumps(record), descriptors=json.dumps(desc),
                        fitness=fitness)
        entered = self.pop.offer_elite(island, cid, desc, fitness) if place else False
        best = getattr(self, 'best_scores', None)
        if place and best:
            # An improvement (the stopping rule's) is beyond the noise: the
            # paired interval against the best so far lies above zero.
            vs_best = proxies.paired_interval(proxy.per_position, best, self.cfg['seed'] + 7 * cid)
            if vs_best and vs_best[1] > 0:
                self.best_scores, self.best_fitness, self.best_generation = proxy.per_position, fitness, generation
                self.say(generation, 'improved', {'id': cid, 'gain_over_best': [round(x, 4) for x in vs_best]})
        self.say(generation, 'scored', {'id': cid, 'island': island, 'fitness': round(fitness, 4),
                                        'agreement': round(proxy.agreement, 4),
                                        'score_error': round(proxy.score_error, 1), 'depth': round(proxy.depth, 2),
                                        'descriptors': [round(d, 4) for d in desc], 'elite': entered,
                                        'gain_interval': [round(x, 4) for x in interval] if interval else None,
                                        'trigger_rate': round(desc[2], 4) if len(desc) > 2 else None,
                                        'bench': result.bench})
        return fitness

    def descriptors(self, tag):
        tree = self.runner.work / tag
        built, log, build = self.runner.build(tree, stats=True)
        if not built:
            raise RuntimeError(f'stats build of {tag} failed: {log[-500:]}')
        _, out = self.runner.run([str(build / 'fork'), 'bench'], timeout=900)
        return proxies.descriptors(out)

    # --- one generation ----------------------------------------------------------
    def requests(self, generation):
        """(island, role, mode) for this generation: proposers residual, the explorer full."""
        cfg = self.cfg
        out = []
        for island in cfg['islands']:
            if island == 'explorer':
                continue
            out += [(island, island, 'residual')] * cfg['per_island']
        if 'explorer' in cfg['islands']:
            share = cfg['full_share']
            count = max(1, round(len(out) * share / (1 - share)))
            out += [('explorer', 'explorer', 'full')] * count
        return out

    def parents_text(self, island, generation, index):
        seed = self.cfg['seed'] * 1000003 + generation * 1009 + index * 31 + sum(map(ord, island))
        ids = self.pop.choose_parents(island, 2, seed)
        parts = []
        for pid in ids:
            c = self.pop.get(pid)
            p = json.loads(c['proxies']) if c['proxies'] else {}
            parts.append(f"- candidate {pid} (agreement {p.get('agreement', 0):.4f}, score error "
                         f"{p.get('score_error', 0):.1f}{score_text(c['fitness'], c['proxies'], c['descriptors'])}):\n"
                         f"```cpp\n{c['body']}\n```")
        return ids[0] if ids else None, '\n'.join(parts) or '(none: start from the baseline, a zero correction)'

    def generation(self, g):
        cfg = self.cfg
        rng = random.Random(cfg['seed'] * 7919 + g)
        gate_runs = gate_failures = 0
        requests = self.requests(g)
        for index, (island, role, mode) in enumerate(requests):
            stop = self.budget.exhausted()
            if stop:
                return stop
            self.refresh(status=f'generation {g}: asking the {role} ({index + 1} of {len(requests)})')
            parent, parents = self.parents_text(island, g, index)
            prompt = agents.prompt_for(role, mode=mode, parents=parents, statistics=self.statistics,
                                       history=self.history_text(), insights=self.insights,
                                       protected=cfg['explorer_protected'])
            reply = self.agent.ask(role, prompt)
            self.budget.spend(tokens=reply.tokens, candidates=1)
            self.say(g, 'agent_call', {'role': role, 'tokens': reply.tokens, 'usage': reply.usage})
            proposal = agents.parse_proposal(reply.text)
            if proposal is None:
                self.say(g, 'malformed', {'island': island, 'reply': reply.text[:400]})
                continue
            cid = self.pop.add(g, island, role, parent, proposal.mode, proposal.body, proposal.rationale)
            self.refresh(status=f'generation {g}: the critic reviews candidate {cid}')
            review = self.agent.ask('critic', agents.prompt_for('critic', mode=proposal.mode,
                                                                rationale=proposal.rationale, body=proposal.body))
            self.budget.spend(tokens=review.tokens)
            self.say(g, 'agent_call', {'role': 'critic', 'tokens': review.tokens, 'usage': review.usage})
            verdict = agents.parse_verdict(review.text)
            self.pop.update(cid, critic=json.dumps(verdict.__dict__))
            audit = not verdict.accept and rng.random() < cfg['critic_audit_share']
            if not verdict.accept:
                self.say(g, 'critic_rejected', {'id': cid, 'reasons': verdict.reasons, 'audited': audit})
                self.pop.update(cid, status='critic_rejected')
                if not audit:
                    continue
            gate_runs += 1
            fitness = self.evaluate(g, cid, island, proposal.body, place=not audit)
            if audit:  # scored only to measure the critic: it stays rejected
                self.pop.update(cid, status='critic_rejected (audited: ' + self.pop.get(cid)['status'] + ')')
            if fitness is None:
                gate_failures += 1
                continue
            if verdict.accept:
                self.promote(g, cid, fitness)
        self.explorer_and_resets(g)
        if g % cfg['analyst_every'] == 0:
            self.analyse(g)
        if gate_runs and gate_failures / gate_runs > cfg['max_gate_failure_rate'] and gate_runs >= 4:
            return f'gate failure rate {gate_failures}/{gate_runs}'
        if g - self.best_generation >= cfg['patience']:
            return f'no improvement beyond the fitness interval for {cfg["patience"]} generations'
        return None

    def promote(self, g, cid, fitness):
        """Short match and SPRT hand-off for a candidate clearly above the baseline on the proxies:
        past the margin, with its paired bootstrap interval's low end above zero (beyond the
        position-sampling noise), and a rule that changes some reductions."""
        cfg = self.cfg
        if fitness < self.baseline_fitness + cfg['promote_margin']:
            return
        c = self.pop.get(cid)
        record, desc = json.loads(c['proxies'] or '{}'), json.loads(c['descriptors'] or '[]')
        low, trigger = record.get('gain_low'), desc[2] if len(desc) > 2 else None
        if low is None or low <= 0 or not trigger:
            self.pop.update(cid, status='within noise: not promoted' if trigger else 'no trigger: not promoted')
            self.say(g, 'not_promoted', {'id': cid, 'gain': record.get('gain'), 'gain_low': low,
                                         'gain_high': record.get('gain_high'), 'trigger_rate': trigger})
            return
        if cfg['match']['games'] <= 0:
            self.pop.update(cid, status='promoted (match skipped)')
            self.say(g, 'promoted', {'id': cid, 'match': 'skipped (games = 0)'})
            return
        m = cfg['match']
        engine = self.runner.work / f'cand-{cid}' / 'build' / 'fork'
        baseline = self.runner.work / 'baseline' / 'build' / 'fork'
        result = match.run_match(m['fastchess'], engine, baseline, m['book'], m['games'], m['tc'], m['concurrency'],
                                 self.run_dir / f'match-{cid}')
        self.pop.update(cid, match=json.dumps(result.__dict__ if result else None))
        if result and result.passes(m['elo_floor']):
            c = self.pop.get(cid)
            path = regions.REGIONS[cfg['region']]
            text = regions.replace_body(self.runner.read(cfg['baseline_commit'], path), cfg['region'], c['body'])
            patch = make_patch(self.runner.read(cfg['baseline_commit'], path), text, path)
            where = match.hand_off(self.run_dir / 'handoff', cid, path, patch, cfg['baseline_commit'])
            self.pop.update(cid, status='sprt hand-off (originality screen first)')
            self.say(g, 'handoff', {'id': cid, 'commands': str(where)})
        else:
            self.pop.update(cid, status='match: not kept')
            self.say(g, 'match_failed', {'id': cid, 'result': result.__dict__ if result else None})

    def explorer_and_resets(self, g):
        cfg = self.cfg
        if 'explorer' in cfg['islands'] and g == cfg['explorer_protected']:
            # Protection ends: the explorer's elites now compete in every proposer island.
            for cell, cid, fitness in self.pop.elites('explorer'):
                desc = json.loads(self.pop.get(cid)['descriptors'])
                for island in cfg['islands']:
                    if island != 'explorer':
                        self.pop.offer_elite(island, cid, desc, fitness)
            self.say(g, 'explorer_joined', {'elites': len(self.pop.elites('explorer'))})
        if cfg['reset_every'] and g % cfg['reset_every'] == 0:
            ranked = sorted((self.pop.best(i) or (None, float('-inf')))[1:] + (i,)
                            for i in cfg['islands'] if i != 'explorer' or g > cfg['explorer_protected'])
            if len(ranked) >= 2:
                worst, best = ranked[0][1], ranked[-1][1]
                self.pop.reseed(worst, best)
                self.say(g, 'reseeded', {'island': worst, 'from': best})

    def analyse(self, g):
        rows = self.pop.db.execute(
            'SELECT id, generation, island, mode, rationale, status, critic, proxies, descriptors, fitness, body '
            'FROM candidates WHERE generation > ? ORDER BY id', (g - self.cfg['analyst_every'],)).fetchall()
        text = '\n'.join(summary_line(r) for r in rows) or '(no candidates)'
        reply = self.agent.ask('analyst', agents.prompt_for('analyst', every=self.cfg['analyst_every'],
                                                            candidates=text))
        self.budget.spend(tokens=reply.tokens)
        self.say(g, 'agent_call', {'role': 'analyst', 'tokens': reply.tokens, 'usage': reply.usage})
        self.insights = reply.text.strip() or self.insights
        self.say(g, 'analyst', {'insights': self.insights[:2000]})

    def history_text(self):
        rows = self.pop.db.execute('SELECT id, island, mode, status, fitness, proxies, descriptors, rationale '
                                   'FROM candidates ORDER BY id DESC LIMIT ?', (RecentScores,)).fetchall()
        return '\n'.join(f'- {r[0]} ({r[1]}, {r[2]}): {r[3]}{score_text(r[4], r[5], r[6])}: {(r[7] or "")[:120]}'
                         for r in rows) or '(nothing yet)'

    # --- the run -----------------------------------------------------------------
    def start(self):
        """Generation 0: the baseline (the region as committed) gated, scored and seeded in every island."""
        cfg = self.cfg
        self.refresh(status='baseline: building, gating and measuring the committed region')
        path = regions.REGIONS[cfg['region']]
        body = regions.body(self.runner.read(cfg['baseline_commit'], path), cfg['region'])
        tree = self.runner.tree(cfg['baseline_commit'], {}, 'baseline')
        built, log, build = self.runner.build(tree)
        if not built:
            raise RuntimeError('the baseline does not build: ' + log[-500:])
        self.baseline_perft = self.runner.perft(build / 'fork')
        cid = self.pop.add(0, 'baseline', 'baseline', None, 'residual', body, 'the committed region')
        fitness = self.evaluate(0, cid, cfg['islands'][0], body)
        if fitness is None:
            raise RuntimeError('the baseline fails its own gate')
        for island in cfg['islands'][1:]:
            self.pop.offer_elite(island, cid, json.loads(self.pop.get(cid)['descriptors']), fitness)
        self.baseline_fitness = fitness
        self.baseline_scores = json.loads(self.pop.get(cid)['proxies']).get('per_position') or None
        self.best_scores = self.baseline_scores
        _, out = self.runner.run([str(self.runner.work / f'cand-{cid}' / 'build-stats' / 'fork'), 'bench'],
                                 timeout=900)
        self.statistics = '\n'.join(line for line in out.split('\n') if line.startswith('stats:') and any(
            k in line for k in ('reduc', 'cutoff', 'LMR'))) or self.statistics
        self.best_fitness, self.best_generation = fitness, 0
        self.status = 'running'
        self.say(0, 'baseline', {'id': cid, 'fitness': fitness, 'perft': self.baseline_perft})

    def close(self):
        self.log_file.close()
        self.pop.close()

    def run(self, generations):
        self.start()
        reason = 'generation limit'
        for g in range(1, generations + 1):
            stop = self.generation(g)
            if stop:
                reason = stop
                break
        self.say(g, 'stopped', {'reason': reason, 'budget': self.budget.used})
        self.refresh(status=f'stopped: {reason}')
        self.close()
        return reason


def make_patch(before, after, path):
    import difflib
    return ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), f'a/{path}', f'b/{path}'))


def dry_run_agent():
    """Scripted replies for one generation: each funnel outcome once."""
    def proposal(mode, why, body):
        return f'MODE: {mode}\nRATIONALE: {why}\n```cpp\n{body}\n```\n'
    return agents.StubAgent({
        'proposer_aggressive': [proposal('residual', 'Stub: one more ply for late moves with a poor history at '
                                         'depth 8 and beyond.', '  return c.depth >= 8 && c.move_number >= 12 && '
                                         'c.history < 0 ? 1 : 0;')],
        'proposer_cautious': [proposal('residual', 'Stub: one ply less on PV nodes and for moves with a strong '
                                       'history.', '  return c.on_pv || c.history > 5000 ? -1 : 0;')],
        'proposer_stats': [proposal('residual', 'Stub: a body that does not compile (the gate must stop it).',
                                    '  return c.depth +;')],
        'explorer': [proposal('full', 'Stub: a floating-point rule (the critic must reject it).',
                              '  const double r = 0.4 * c.depth;\n  return static_cast<int>(r) - c.base;')],
        'critic': ['VERDICT: accept\nREASONS: Stub critic: integer, deterministic, inside the body.',
                   'VERDICT: accept\nREASONS: Stub critic: integer, deterministic, inside the body.',
                   'VERDICT: accept\nREASONS: Stub critic: looks fine (the gate will find the syntax error).',
                   'VERDICT: reject\nREASONS: Stub critic: floating point breaks the hot-path rules.'],
        'analyst': ['- Stub analyst: one generation only; nothing to summarize yet.'],
    })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', required=True)
    ap.add_argument('--run-dir', required=True)
    ap.add_argument('--generations', type=int)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true', help='stub agents (no tokens)')
    mode.add_argument('--live', action='store_true', help='real agents through claude -p: the evolution loop')
    a = ap.parse_args()
    cfg = json.loads(Path(a.config).read_text())
    # Paths: the repository is the one holding this script unless given;
    # relative paths are from it, and ~ is the user's home (the config is
    # committed, so it names no user).
    repo = Path(cfg.get('repo') or HERE.parents[1]).expanduser()
    cfg['repo'] = str(repo)
    cfg['positions'] = str(repo / Path(cfg['positions']).expanduser())
    for key in ('fastchess', 'book'):
        cfg['match'][key] = str(Path(cfg['match'][key]).expanduser())
    run_dir = Path(a.run_dir).expanduser()
    if a.live:
        agent = agents.CliAgent(**cfg.get('agent', {}))
        print('LIVE loop: real agents and tokens (owner approval required: deliverable 8c).', flush=True)
    else:
        agent = dry_run_agent()
        # The stub's script: one proposal from each of four islands, each a
        # different funnel outcome; every rejected proposal is gated too.
        cfg.update(islands=['proposer_aggressive', 'proposer_cautious', 'proposer_stats', 'explorer'],
                   per_island=1, critic_audit_share=1.0)
    runner = gate.Runner(cfg['repo'], run_dir / 'work', jobs=cfg.get('jobs', 4), test_cache=cfg.get('test_cache'))
    loop = Loop(cfg, run_dir, agent, runner)
    reason = loop.run(a.generations or cfg['generations'])
    print(f'stopped: {reason}; budget used {loop.budget.used}; run log {run_dir / "run.log"}')


if __name__ == '__main__':
    main()
