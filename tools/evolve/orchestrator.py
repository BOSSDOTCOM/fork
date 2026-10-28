"""The heuristic-discovery loop's orchestrator (ideas.md idea 23, DESIGN.md
§5.2 deliverable 8c): a deterministic script, not an agent.

Each generation, for every island in turn: choose parents from the island's
grid (seeded), ask the island's agent for a proposal (residual mode, or a
full replacement for the explorer's share), have the critic review it, gate
it (static rules, guard, the preprocessed comparison, build, perft, the
correctness suites, determinism),
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

The gate builds with the config's `compiler` (passed to CMake as
CMAKE_CXX_COMPILER; its --version goes into the baseline event). For TCEC's
compilers, run the loop in the WSL distro Ubuntu-22.04
(scripts/tcec-toolchain-setup.sh): there "g++" is GCC 11.4, the strictest
of the four on the constexpr region (a body calling a non-constexpr function
compiles with Clang and fails with GCC: audit-1 U-17), and "clang++-19" is
the compiler update.sh picks first. The hand-off's full check
(scripts/check.sh full) builds all four before any SPRT.

    python3 tools/evolve/orchestrator.py --config tools/evolve/config.json --run-dir ~/fork-evolve/run1 \\
        (--dry-run | --live) [--generations G]
    python3 tools/evolve/orchestrator.py --run-dir ~/fork-evolve/run1 --resume (--dry-run | --live)

Failures: each agent call is retried with exponential backoff
(`agent_retries`, `agent_backoff_seconds`); a request that still fails (an
agent, a gate step that times out, a stats build, a crashed engine in the
proxies, the match) is logged as an `error` event, its candidate gets the
status `error:<step>`, it counts as a failed gate run toward the
gate-failure stop, and the generation goes on. A new run needs an empty
--run-dir; --resume continues a stopped or crashed run from its database:
the baseline (rebuilt from its commit, perft checked), the best so far, the
analyst's notes, the budget used (tokens and candidates from the logged
agent calls, wall time as the sum of the sessions' spans) and the next
request of the unfinished generation. A candidate whose request did not
finish is marked `interrupted`, not redone.
"""
import argparse
import json
import random
import re
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


class RunDirError(RuntimeError):
    pass


class Loop:
    def __init__(self, cfg, run_dir, agent, runner, clock=time.time, resume=False, sleep=time.sleep):
        self.cfg = cfg
        self.run_dir = Path(run_dir)
        # One run per folder: a second start would mix two runs' baselines,
        # generations and budgets in one database (audit-1 U-7).
        database = self.run_dir / 'population.sqlite'
        if resume and not database.exists():
            raise RunDirError(f'nothing to resume: {database} does not exist')
        if not resume and self.run_dir.exists() and any(self.run_dir.iterdir()):
            raise RunDirError(f'{self.run_dir} is not empty: pass --resume to continue its run, or choose a new '
                              f'--run-dir')
        self.resume = resume
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.agent = agent
        self.runner = runner
        self.sleep = sleep
        self.cid, self.step = None, None
        self.pop = population.Population(str(database))
        # The baseline commit is pinned to its full hash once, at the start: a
        # symbolic ref such as HEAD would move under a long run when the owner
        # commits beside it, and every later candidate would be built on other
        # code than the baseline it is scored against (audit-1 U-8). Every
        # read, tree, hand-off patch and printed command uses the hash.
        if resume:
            self.commit = self.pop.get_meta('baseline_commit')
            if not self.commit:
                raise RunDirError('cannot resume: the database has no pinned baseline commit')
        else:
            self.commit = runner.resolve(cfg['baseline_commit'])
            if not re.fullmatch(r'[0-9a-f]{40}', self.commit or ''):
                raise RunDirError(f'{cfg["baseline_commit"]!r} did not resolve to a full commit hash: {self.commit!r}')
            self.pop.set_meta('baseline_commit', self.commit)
            self.pop.set_meta('baseline_ref', cfg['baseline_commit'])
            # The run's configuration as it started; --resume reads it back.
            (self.run_dir / 'config.json').write_text(json.dumps(cfg, indent=1), encoding='utf-8')
        self.budget = agents.Budget(cfg['budget']['tokens'], cfg['budget']['candidates'],
                                    cfg['budget']['hours'] * 3600, clock)
        self.log_file = open(self.run_dir / 'run.log', 'a', encoding='utf-8')
        self.insights = '(none yet)'
        self.best_fitness, self.best_generation = None, 0
        self.labels = proxies.load_positions(cfg['positions'], 'evolve')[:cfg.get('positions_limit') or None]
        # The held-out split: measured for every scored candidate, shown on the
        # dashboard and required for promotion, but never shown to an agent
        # and never used for selection, so it stays independent of the search.
        self.holdout = proxies.load_positions(cfg['positions'], 'holdout')
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
                 'explorer_protected': self.cfg['explorer_protected'], 'baseline_commit': self.commit}
        try:
            (self.run_dir / 'state.json').write_text(json.dumps(state, indent=1), encoding='utf-8')
            mirror = self.cfg.get('dashboard_mirror')
            dashboard.render(self.run_dir, mirror and str(Path(mirror) / self.run_dir.name))
        except Exception as e:  # noqa: BLE001 (the dashboard must never stop a run)
            self.log_file.write(json.dumps({'kind': 'dashboard_error', 'detail': str(e)}) + '\n')

    # --- the funnel for one body -------------------------------------------------
    def evaluate(self, generation, cid, island, body, place=True):
        """Gate, proxies and (if `place`) the grid for candidate `cid`; returns its fitness or None."""
        cfg = self.cfg
        self.step = 'gate'
        self.refresh(status=f'generation {generation}: gating candidate {cid}')
        result = gate.run_gate(self.runner, self.commit, cfg['region'], body, self.reference,
                               f'cand-{cid}')
        self.pop.update(cid, gate=json.dumps(result.__dict__))
        if not result.passed:
            self.pop.update(cid, status=f'gate:{result.step}')
            self.say(generation, 'gate_failed', {'id': cid, 'step': result.step, 'detail': result.detail[-400:]})
            return None
        engine = self.runner.work / f'cand-{cid}' / 'build' / 'fork'
        self.step = 'proxies'
        self.refresh(status=f'generation {generation}: measuring candidate {cid}')
        proxy = proxies.run_proxies(engine, self.labels, cfg['proxy_nodes'], cfg.get('proxy_jobs', 1))
        self.step = 'descriptors'
        desc = self.descriptors(f'cand-{cid}')
        fitness = proxy.fitness()
        record = dict(proxy.__dict__)
        base = getattr(self, 'baseline_scores', None)
        interval = proxies.paired_interval(proxy.per_position, base, self.cfg['seed'] + cid) if base else None
        if interval:
            record.update(gain=interval[0], gain_low=interval[1], gain_high=interval[2])
        if self.holdout:
            self.step = 'holdout'
            held = proxies.run_proxies(engine, self.holdout, cfg['proxy_nodes'], cfg.get('proxy_jobs', 1))
            record.update(holdout_fitness=held.fitness(), holdout_per_position=held.per_position)
            held_base = getattr(self, 'baseline_holdout', None)
            held_interval = proxies.paired_interval(held.per_position, held_base,
                                                    self.cfg['seed'] + 3 * cid) if held_base else None
            if held_interval:
                record.update(holdout_gain=held_interval[0], holdout_low=held_interval[1],
                              holdout_high=held_interval[2])
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

    def ask(self, g, role, prompt):
        """The agent's reply, retried with exponential backoff (a rate limit, a refused or
        timed-out session); the last failure is raised."""
        retries = self.cfg.get('agent_retries', 3)
        delay = self.cfg.get('agent_backoff_seconds', 60)
        for attempt in range(retries + 1):
            try:
                return self.agent.ask(role, prompt)
            except Exception as e:  # noqa: BLE001 (any CLI failure is retried, then reported)
                if attempt == retries:
                    raise
                wait = delay * 2 ** attempt
                self.say(g, 'agent_retry', {'role': role, 'attempt': attempt + 1, 'wait': wait,
                                            'error': repr(e)[-300:]})
                self.sleep(wait)

    def generation(self, g, first=0):
        """Generation `g` from request `first` on (a resumed run starts mid-generation); the
        stop reason, or None. Each request ends with a request_done event, so a resume
        knows where it is; one request's failure is logged and counted, not fatal."""
        cfg = self.cfg
        requests = self.requests(g)
        counts = self.request_counts(g)
        for index, (island, role, mode) in enumerate(requests):
            if index < first:
                continue
            stop = self.budget.exhausted()
            if stop:
                return stop
            self.cid, self.step = None, 'proposer'
            gated = failed = False
            try:
                gated, failed = self.request(g, index, island, role, mode, len(requests))
            except Exception as e:  # noqa: BLE001 (one candidate's failure must not end the run)
                gated = failed = True
                if self.cid is not None:
                    self.pop.update(self.cid, status=f'error:{self.step}')
                self.say(g, 'error', {'id': self.cid, 'island': island, 'step': self.step, 'error': repr(e)[-400:]})
            counts[0] += gated
            counts[1] += failed
            self.say(g, 'request_done', {'index': index, 'id': self.cid, 'gated': gated, 'failed': failed})
        self.explorer_and_resets(g)
        if g % cfg['analyst_every'] == 0:
            try:
                self.analyse(g)
            except Exception as e:  # noqa: BLE001 (the analyst's notes are kept as they were)
                self.say(g, 'error', {'id': None, 'step': 'analyst', 'error': repr(e)[-400:]})
        self.say(g, 'generation_done', {'gate_runs': counts[0], 'gate_failures': counts[1]})
        gate_runs, gate_failures = counts
        if gate_runs and gate_failures / gate_runs > cfg['max_gate_failure_rate'] and gate_runs >= 4:
            return f'gate failure rate {gate_failures}/{gate_runs}'
        if g - self.best_generation >= cfg['patience']:
            return f'no improvement beyond the fitness interval for {cfg["patience"]} generations'
        return None

    def request_counts(self, g):
        """[gate runs, gate failures] of generation g's finished requests (errors count as both)."""
        counts = [0, 0]
        for row in self.pop.db.execute("SELECT detail FROM events WHERE kind = 'request_done' AND generation = ?",
                                       (g,)):
            d = json.loads(row[0])
            counts[0] += d['gated']
            counts[1] += d['failed']
        return counts

    def request(self, g, index, island, role, mode, total):
        """One proposal through the funnel; (gated, gate failed)."""
        cfg = self.cfg
        # Seeded per request, so a run resumed mid-generation draws as an uninterrupted one would.
        rng = random.Random(cfg['seed'] * 7919 + g * 1009 + index)
        self.refresh(status=f'generation {g}: asking the {role} ({index + 1} of {total})')
        parent, parents = self.parents_text(island, g, index)
        prompt = agents.prompt_for(role, mode=mode, parents=parents, statistics=self.statistics,
                                   history=self.history_text(), insights=self.insights,
                                   protected=cfg['explorer_protected'])
        reply = self.ask(g, role, prompt)
        self.budget.spend(tokens=reply.tokens, candidates=1)
        self.say(g, 'agent_call', {'role': role, 'tokens': reply.tokens, 'usage': reply.usage})
        proposal = agents.parse_proposal(reply.text)
        if proposal is None:
            self.say(g, 'malformed', {'island': island, 'reply': reply.text[:400]})
            return False, False
        cid = self.cid = self.pop.add(g, island, role, parent, proposal.mode, proposal.body, proposal.rationale)
        self.step = 'critic'
        self.refresh(status=f'generation {g}: the critic reviews candidate {cid}')
        review = self.ask(g, 'critic', agents.prompt_for('critic', mode=proposal.mode,
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
                return False, False
        fitness = self.evaluate(g, cid, island, proposal.body, place=not audit)
        if audit:  # scored only to measure the critic: it stays rejected
            self.pop.update(cid, status='critic_rejected (audited: ' + self.pop.get(cid)['status'] + ')')
        if fitness is None:
            return True, True
        if verdict.accept:
            self.step = 'promote'
            self.promote(g, cid, fitness)
        return True, False

    def promote(self, g, cid, fitness):
        """Short match and SPRT hand-off for a candidate clearly above the baseline on the proxies:
        past the margin, with its paired bootstrap interval's low end above zero (beyond the
        position-sampling noise) on the scoring set and on the held-out set, and a rule that
        changes some reductions."""
        cfg = self.cfg
        if fitness < self.baseline_fitness + cfg['promote_margin']:
            return
        c = self.pop.get(cid)
        record, desc = json.loads(c['proxies'] or '{}'), json.loads(c['descriptors'] or '[]')
        low, trigger = record.get('gain_low'), desc[2] if len(desc) > 2 else None
        held_low = record.get('holdout_low')
        if low is None or low <= 0 or not trigger or held_low is None or held_low <= 0:
            why = ('no trigger' if not trigger else 'within noise' if low is None or low <= 0
                   else 'not confirmed on the held-out set')
            self.pop.update(cid, status=f'{why}: not promoted')
            self.say(g, 'not_promoted', {'id': cid, 'reason': why, 'gain': record.get('gain'), 'gain_low': low,
                                         'gain_high': record.get('gain_high'), 'trigger_rate': trigger,
                                         'holdout_gain': record.get('holdout_gain'), 'holdout_low': held_low,
                                         'holdout_high': record.get('holdout_high')})
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
            text = regions.replace_body(self.runner.read(self.commit, path), cfg['region'], c['body'])
            patch = make_patch(self.runner.read(self.commit, path), text, path)
            where = match.hand_off(self.run_dir / 'handoff', cid, path, patch, self.commit)
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
        reply = self.ask(g, 'analyst', agents.prompt_for('analyst', every=self.cfg['analyst_every'],
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
    def prepare_baseline(self):
        """Builds the baseline tree and the gate's reference (its perft, files and preprocessed
        units); returns the committed region body."""
        cfg = self.cfg
        path = regions.REGIONS[cfg['region']]
        body = regions.body(self.runner.read(self.commit, path), cfg['region'])
        tree = self.runner.tree(self.commit, {}, 'baseline')
        built, log, build = self.runner.build(tree)
        if not built:
            raise RuntimeError('the baseline does not build: ' + log[-500:])
        self.baseline_perft = self.runner.perft(build / 'fork')
        # What the gate compares every candidate with: the baseline tree's
        # files and the preprocessed text of each unit that includes the region.
        self.reference = gate.make_reference(self.runner, cfg['region'], tree, build, self.baseline_perft)
        return body

    def start(self):
        """Generation 0: the baseline (the region as committed) gated, scored and seeded in every island."""
        cfg = self.cfg
        self.say(0, 'session', {'resumed': False})
        self.refresh(status='baseline: building, gating and measuring the committed region')
        body = self.prepare_baseline()
        cid = self.pop.add(0, 'baseline', 'baseline', None, 'residual', body, 'the committed region')
        fitness = self.evaluate(0, cid, cfg['islands'][0], body)
        if fitness is None:
            raise RuntimeError('the baseline fails its own gate')
        for island in cfg['islands'][1:]:
            self.pop.offer_elite(island, cid, json.loads(self.pop.get(cid)['descriptors']), fitness)
        self.baseline_fitness = fitness
        self.baseline_scores = json.loads(self.pop.get(cid)['proxies']).get('per_position') or None
        self.baseline_holdout = json.loads(self.pop.get(cid)['proxies']).get('holdout_per_position') or None
        self.best_scores = self.baseline_scores
        _, out = self.runner.run([str(self.runner.work / f'cand-{cid}' / 'build-stats' / 'fork'), 'bench'],
                                 timeout=900)
        self.statistics = '\n'.join(line for line in out.split('\n') if line.startswith('stats:') and any(
            k in line for k in ('reduc', 'cutoff', 'LMR'))) or self.statistics
        self.best_fitness, self.best_generation = fitness, 0
        self.status = 'running'
        self.say(0, 'baseline', {'id': cid, 'fitness': fitness, 'perft': self.baseline_perft, 'commit': self.commit,
                                 'compiler': self.runner.compiler_version(), 'statistics': self.statistics})

    def restore(self):
        """A resumed run's state from its database (population.py: "so a run can be audited and
        resumed"): the baseline (rebuilt from the same commit; its perft must not change), its
        scores, the best so far, the analyst's notes, the budget used, and where to go on.
        Returns (generation, first request)."""
        db = self.pop.db
        row = db.execute("SELECT id FROM candidates WHERE agent = 'baseline' ORDER BY id").fetchall()
        events = self.pop.events('baseline')
        if len(row) != 1 or not events:
            raise RunDirError(f'cannot resume: {len(row)} baselines and {len(events)} baseline events in the database')
        cid = row[0][0]
        detail = json.loads(events[-1][2])
        self.say(0, 'session', {'resumed': True})
        self.refresh(status='resuming: rebuilding the baseline and the gate reference')
        self.prepare_baseline()
        if self.baseline_perft != detail['perft']:
            raise RuntimeError(f'the baseline perft changed: {self.baseline_perft} != {detail["perft"]}')
        c = self.pop.get(cid)
        record = json.loads(c['proxies'])
        self.baseline_fitness = c['fitness']
        self.baseline_scores = record.get('per_position') or None
        self.baseline_holdout = record.get('holdout_per_position') or None
        self.statistics = detail.get('statistics') or self.statistics
        self.best_scores, self.best_fitness, self.best_generation = self.baseline_scores, c['fitness'], 0
        improved = self.pop.events('improved')
        if improved:
            best_generation, _, best = improved[-1]
            b = self.pop.get(json.loads(best)['id'])
            self.best_scores = json.loads(b['proxies'])['per_position']
            self.best_fitness, self.best_generation = b['fitness'], best_generation
        analyst = self.pop.events('analyst')
        if analyst:
            self.insights = json.loads(analyst[-1][2])['insights']
        # The budget: tokens and candidates from the logged agent calls; wall
        # time as the sum of the sessions' spans (first to last event of each).
        tokens = candidates = 0
        for _, _, d in self.pop.events('agent_call'):
            d = json.loads(d)
            tokens += d['tokens']
            candidates += d['role'] not in ('critic', 'analyst')
        elapsed, span_start, last = 0.0, None, None
        for kind, created in db.execute('SELECT kind, created FROM events ORDER BY id'):
            if kind == 'session' or span_start is None:
                if span_start is not None:
                    elapsed += last - span_start
                span_start = created
            last = created
        self.budget.restore(tokens, candidates, elapsed)
        done = [g for g, _, _ in self.pop.events('generation_done')]
        g = max(done) + 1 if done else 1
        finished = [json.loads(d) for gen, _, d in self.pop.events('request_done') if gen == g]
        first = max((d['index'] for d in finished), default=-1) + 1
        # A candidate whose request did not finish is marked, not redone.
        kept = {d['id'] for d in finished}
        for stale, status in db.execute('SELECT id, status FROM candidates WHERE generation >= ?', (g,)).fetchall():
            if stale not in kept and not (status or '').startswith('interrupted'):
                self.pop.update(stale, status='interrupted: ' + (status or ''))
        self.status = 'running'
        self.say(g, 'resumed', {'generation': g, 'first_request': first, 'budget': self.budget.used,
                                'elapsed_seconds': round(elapsed, 1), 'best_generation': self.best_generation,
                                'commit': self.commit})
        return g, first

    def close(self):
        self.log_file.close()
        self.pop.close()

    def run(self, generations):
        if self.resume:
            first_generation, first_request = self.restore()
        else:
            self.start()
            first_generation, first_request = 1, 0
        reason = 'generation limit'
        g = first_generation - 1
        for g in range(first_generation, generations + 1):
            stop = self.generation(g, first_request if g == first_generation else 0)
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
    ap.add_argument('--config', help='the run configuration (a resumed run uses the copy in its run dir)')
    ap.add_argument('--run-dir', required=True)
    ap.add_argument('--generations', type=int)
    ap.add_argument('--resume', action='store_true', help='continue the run in --run-dir where it stopped')
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true', help='stub agents (no tokens)')
    mode.add_argument('--live', action='store_true', help='real agents through claude -p: the evolution loop')
    a = ap.parse_args()
    run_dir = Path(a.run_dir).expanduser()
    if a.resume:
        # The run's own configuration, as it started (edit that copy to
        # change a limit); the dry-run island set is already in it.
        cfg = json.loads((run_dir / 'config.json').read_text(encoding='utf-8'))
    else:
        if not a.config:
            ap.error('--config is required for a new run')
        cfg = json.loads(Path(a.config).read_text(encoding='utf-8'))
        # Paths: the repository is the one holding this script unless given;
        # relative paths are from it, and ~ is the user's home (the config is
        # committed, so it names no user).
        repo = Path(cfg.get('repo') or HERE.parents[1]).expanduser()
        cfg['repo'] = str(repo)
        cfg['positions'] = str(repo / Path(cfg['positions']).expanduser())
        for key in ('fastchess', 'book'):
            cfg['match'][key] = str(Path(cfg['match'][key]).expanduser())
        if a.dry_run:
            # The stub's script: one proposal from each of four islands, each a
            # different funnel outcome; every rejected proposal is gated too.
            cfg.update(islands=['proposer_aggressive', 'proposer_cautious', 'proposer_stats', 'explorer'],
                       per_island=1, critic_audit_share=1.0)
    if a.live:
        agent = agents.CliAgent(**cfg.get('agent', {}))
        print('LIVE loop: real agents and tokens (owner approval required: deliverable 8c).', flush=True)
    else:
        agent = dry_run_agent()
    # The gate's compiler is named, never CMake's default: a candidate's
    # verdict must not depend on what `c++` happens to be (audit-1 U-17).
    runner = gate.Runner(cfg['repo'], run_dir / 'work', jobs=cfg.get('jobs', 4), test_cache=cfg.get('test_cache'),
                         compiler=cfg['compiler'])
    try:
        loop = Loop(cfg, run_dir, agent, runner, resume=a.resume)
    except RunDirError as e:
        sys.exit(f'orchestrator: {e}')
    reason = loop.run(a.generations or cfg['generations'])
    print(f'stopped: {reason}; budget used {loop.budget.used}; run log {run_dir / "run.log"}')


if __name__ == '__main__':
    main()
