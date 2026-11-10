# SPDX-License-Identifier: GPL-3.0-or-later

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
    python3 tools/evolve/orchestrator.py --run-dir ~/fork-evolve/replay1 --replay-from ~/fork-evolve/run1 \\
        [--replay-candidates ID,ID]

Two fitness modes (config `fitness`): `proxies` (the LMR pilot's: best-move
agreement and score error against deep labels at a node budget) and `nodes`
(the ordering pilot's, owner 2026-11-09: nodes to a fixed depth, lower is
better, with the equivalence guard; depth_nodes.py and
docs/research/idea23-pilot/declaration.md). In `nodes` mode the baseline is
measured twice at the start and the run stops unless every position's count
repeats exactly (the self-check), the guard's threshold is computed from the
declared calibration bodies before generation 1, and a candidate whose
answers are not equivalent to the baseline's is refused (status `guard`).

Determinism and replay: every agent call's role, prompt digest and reply go
to replies.jsonl, and every candidate's record (its source body, the agent
and island, the gate's verdict, fitness and guard result) to
candidates.jsonl. --replay-from runs the logged run again in a new run dir
with the logged replies in place of the agents (agents.ReplayAgent), and
compares every candidate's body, status and measured answers with the log;
with --replay-candidates it rebuilds and measures only those candidates (and
the baseline) and compares their node counts exactly.

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
import depth_nodes  # noqa: E402
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
    """', fitness F, gain +G [L, H], trigger T%' (the parts known), for an agent; in the
    nodes mode ', node reduction R% [L%, H%], equivalent E%'."""
    p = json.loads(proxies_json) if proxies_json else {}
    if p.get('mode') == 'nodes':
        if 'gain_low' not in p:
            return ''
        out = (f', node reduction {100 * p["gain"]:+.2f}% [{100 * p["gain_low"]:+.2f}%, '
               f'{100 * p["gain_high"]:+.2f}%]')
        if 'equivalence' in p:
            out += f', equivalent on {100 * p["equivalence"]:.1f}% of positions'
        d = json.loads(descriptors_json) if descriptors_json else []
        if len(d) > 1:
            out += f', first-move cutoffs {100 * d[0]:.1f}%, mean cutoff index {d[1]:.4f}'
        return out
    if fitness is None:
        return ''
    d = json.loads(descriptors_json) if descriptors_json else []
    out = f', fitness {fitness:.4f}'
    if 'gain_low' in p:
        out += f', gain {p["gain"]:+.4f} [{p["gain_low"]:+.4f}, {p["gain_high"]:+.4f}]'
    if len(d) > 2:
        out += f', trigger {100 * d[2]:.1f}%'
    return out


def summary_line(row, region='lmr'):
    """One analyst line from (id, generation, island, mode, rationale, status, critic, proxies, descriptors,
    fitness, body): no per-position scores, no gate log."""
    cid, gen, island, mode, rationale, status, critic, proxies_json, descriptors_json, fitness, body = row
    d = json.loads(descriptors_json) if descriptors_json else []
    shape = f', mean reduction {d[0]:.3f}, re-searched {100 * d[1]:.2f}%' if len(d) > 1 and region == 'lmr' else ''
    verdict = json.loads(critic) if critic else {}
    reasons = f', critic: {verdict.get("reasons", "")[:200]}' if verdict and not verdict.get('accept') else ''
    return (f'- #{cid} g{gen} {island} {mode} {status}{score_text(fitness, proxies_json, descriptors_json)}{shape}'
            f', inputs {population.inputs_used(body or "", region)}{reasons}: {(rationale or "")[:240]}')


# The baseline statistics lines an agent sees, by region (from the stats
# build's bench: the lines about its own subject only).
StatisticsKeys = {'lmr': ('reduc', 'cutoff', 'LMR'), 'quiet_order': ('cutoff', 'quiet cutoffs at depth', 'makes')}


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
        self.region = cfg['region']
        self.mode = cfg.get('fitness', 'proxies')
        self.refusal = None  # why the last evaluate() returned None: 'gate' or 'guard'
        self.pop = population.Population(str(database), self.region)
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
        if self.mode == 'nodes':
            # The generation set: the evolve split, or a seeded sample of it
            # when the run must be shorter (the declaration says which).
            self.labels = depth_nodes.sample_rows(proxies.load_positions(cfg['positions'], 'evolve'),
                                                  cfg.get('positions_sample'), cfg['seed'])
        # The held-out split: measured for every scored candidate, shown on the
        # dashboard and required for promotion, but never shown to an agent
        # and never used for selection, so it stays independent of the search.
        self.holdout = proxies.load_positions(cfg['positions'], 'holdout')
        if self.mode == 'nodes':  # a seeded sample only for a test run (the pilot keeps all 940)
            self.holdout = depth_nodes.sample_rows(self.holdout, cfg.get('holdout_sample'), cfg['seed'] + 1)
        self.statistics = '(baseline statistics not measured yet)'
        self.guard_threshold = None

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
    def gate(self, generation, cid, body):
        """The gate for candidate `cid`; True if it passed (its status says why not)."""
        self.step = 'gate'
        self.refresh(status=f'generation {generation}: gating candidate {cid}')
        result = gate.run_gate(self.runner, self.commit, self.cfg['region'], body, self.reference, f'cand-{cid}')
        self.pop.update(cid, gate=json.dumps(result.__dict__))
        if not result.passed:
            self.pop.update(cid, status=f'gate:{result.step}')
            self.say(generation, 'gate_failed', {'id': cid, 'step': result.step, 'compiler': result.compiler,
                                                 'detail': result.detail[-400:]})
            return False
        self.gate_bench = result.bench
        return True

    def evaluate(self, generation, cid, island, body, place=True):
        """Gate, fitness and (if `place`) the grid for candidate `cid`; returns its fitness or None
        (self.refusal then says whether the gate or the equivalence guard refused it)."""
        self.refusal = None
        if self.mode == 'nodes':
            return self.evaluate_nodes(generation, cid, island, body, place)
        return self.evaluate_proxies(generation, cid, island, body, place)

    def measure(self, tag, rows):
        """The fixed-depth answers of the engine built for `tag` on `rows`."""
        engine = self.runner.work / tag / 'build' / 'fork'
        return depth_nodes.run_fixed_depth(engine, rows, self.cfg['depth'], self.cfg.get('proxy_jobs', 1),
                                           self.cfg.get('hash_mb', 16))

    def nodes_record(self, cid, answers, held):
        """The nodes mode's record of a candidate's answers against the baseline's (and the best's)."""
        cfg = self.cfg
        nodes = [a.nodes for a in answers]
        base = [a.nodes for a in self.baseline_answers]
        record = {'mode': 'nodes', 'depth': cfg['depth'], 'positions': len(nodes), 'total': sum(nodes),
                  'digest': depth_nodes.digest(answers), 'per_position': [a.row() for a in answers],
                  'summary': depth_nodes.paired_summary(nodes, base),
                  'equivalence': depth_nodes.equivalence_share(answers, self.baseline_answers,
                                                               cfg['guard']['tolerance_cp'])}
        gain = depth_nodes.reduction_interval(nodes, base, cfg['seed'] + cid)
        record.update(gain=gain[0], gain_low=gain[1], gain_high=gain[2])
        if held is not None:
            held_nodes = [a.nodes for a in held]
            held_base = [a.nodes for a in self.baseline_holdout_answers]
            interval = depth_nodes.reduction_interval(held_nodes, held_base, cfg['seed'] + 3 * cid)
            record.update(holdout_total=sum(held_nodes), holdout_digest=depth_nodes.digest(held),
                          holdout_per_position=[a.row() for a in held],
                          holdout_summary=depth_nodes.paired_summary(held_nodes, held_base),
                          holdout_equivalence=depth_nodes.equivalence_share(held, self.baseline_holdout_answers,
                                                                            cfg['guard']['tolerance_cp']),
                          holdout_gain=interval[0], holdout_low=interval[1], holdout_high=interval[2])
        return record

    def evaluate_nodes(self, generation, cid, island, body, place=True):
        """The nodes mode's funnel: the gate, nodes to the fixed depth on the generation set, the
        equivalence guard against the baseline's answers, then (if it passed) the stats build's
        descriptors, the held-out set and the grid."""
        if not self.gate(generation, cid, body):
            self.refusal = 'gate'
            return None
        self.step = 'nodes'
        self.refresh(status=f'generation {generation}: measuring candidate {cid}')
        answers = self.measure(f'cand-{cid}', self.labels)
        record = self.nodes_record(cid, answers, None)
        fitness = record['gain']
        if self.guard_threshold is not None and record['equivalence'] < self.guard_threshold:
            self.refusal = 'guard'
            record['guard_passed'] = False
            self.pop.update(cid, status='guard: not equivalent', proxies=json.dumps(record), fitness=fitness)
            self.say(generation, 'guard_refused', {'id': cid, 'equivalence': round(record['equivalence'], 4),
                                                   'threshold': round(self.guard_threshold, 4),
                                                   'reduction': round(fitness, 5)})
            return None
        record['guard_passed'] = self.guard_threshold is not None
        self.step = 'descriptors'
        desc = self.descriptors(f'cand-{cid}')
        held = None
        if self.holdout:
            self.step = 'holdout'
            held = self.measure(f'cand-{cid}', self.holdout)
        record = dict(self.nodes_record(cid, answers, held), guard_passed=record['guard_passed'])
        self.pop.update(cid, status='scored', proxies=json.dumps(record), descriptors=json.dumps(desc),
                        fitness=fitness)
        entered = self.pop.offer_elite(island, cid, desc, fitness) if place else False
        best = getattr(self, 'best_nodes', None)
        if place and best:
            vs_best = depth_nodes.reduction_interval([a.nodes for a in answers], best,
                                                     self.cfg['seed'] + 7 * cid)
            if vs_best and vs_best[1] > 0:
                self.best_nodes, self.best_fitness, self.best_generation = [a.nodes for a in answers], fitness, \
                    generation
                self.say(generation, 'improved', {'id': cid, 'gain_over_best': [round(x, 5) for x in vs_best]})
        self.say(generation, 'scored', {'id': cid, 'island': island, 'reduction': round(fitness, 5),
                                        'interval': [round(record['gain_low'], 5), round(record['gain_high'], 5)],
                                        'total': record['total'], 'equivalence': round(record['equivalence'], 4),
                                        'holdout_reduction': round(record['holdout_gain'], 5) if held else None,
                                        'descriptors': [round(d, 4) for d in desc], 'elite': entered,
                                        'bench': self.gate_bench})
        return fitness

    def log_candidate(self, cid):
        """Appends candidate `cid`'s record to candidates.jsonl: the proposal (agent, island, mode,
        rationale, source body), the critic's and the gate's verdicts, the fitness, the guard's
        result and the measured answers' digests (the per-position lists stay in the database)."""
        c = self.pop.get(cid)
        if c is None:
            return
        record = json.loads(c['proxies']) if c['proxies'] else {}
        gate_result = json.loads(c['gate']) if c['gate'] else {}
        entry = {k: c[k] for k in ('id', 'generation', 'island', 'agent', 'parent', 'mode', 'rationale', 'body',
                                   'status', 'fitness')}
        entry['critic'] = json.loads(c['critic']) if c['critic'] else None
        entry['gate'] = {'passed': gate_result.get('passed'), 'step': gate_result.get('step'),
                         'compiler': gate_result.get('compiler'), 'bench': gate_result.get('bench'),
                         'detail': (gate_result.get('detail') or '')[-2000:]} if gate_result else None
        entry['measured'] = {k: v for k, v in record.items() if not k.endswith('per_position')}
        entry['descriptors'] = json.loads(c['descriptors']) if c['descriptors'] else None
        with open(self.run_dir / 'candidates.jsonl', 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, sort_keys=True) + '\n')

    def evaluate_proxies(self, generation, cid, island, body, place=True):
        """The proxies mode's funnel (the LMR pilot's): gate, proxies and (if `place`) the grid."""
        cfg = self.cfg
        if not self.gate(generation, cid, body):
            self.refusal = 'gate'
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
                                        'bench': self.gate_bench})
        return fitness

    def descriptors(self, tag):
        tree = self.runner.work / tag
        built, log, build = self.runner.build(tree, stats=True)
        if not built:
            raise RuntimeError(f'stats build of {tag} failed: {log[-500:]}')
        _, out = self.runner.run([str(build / 'fork'), 'bench'], timeout=900)
        if self.mode == 'nodes':
            return list(depth_nodes.ordering_descriptors(out))
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
            if self.mode == 'nodes':
                head = f"- candidate {pid} ({p.get('total', 0):,} nodes"
            else:
                head = (f"- candidate {pid} (agreement {p.get('agreement', 0):.4f}, score error "
                        f"{p.get('score_error', 0):.1f}")
            parts.append(f"{head}{score_text(c['fitness'], c['proxies'], c['descriptors'])}):\n"
                         f"```cpp\n{c['body']}\n```")
        start = ('(none: start from the committed combination)' if self.region == 'quiet_order'
                 else '(none: start from the baseline, a zero correction)')
        return ids[0] if ids else None, '\n'.join(parts) or start

    def ask(self, g, role, prompt):
        """The agent's reply, retried with exponential backoff (a rate limit, a refused or
        timed-out session); the last failure is raised."""
        retries = self.cfg.get('agent_retries', 3)
        delay = self.cfg.get('agent_backoff_seconds', 60)
        for attempt in range(retries + 1):
            try:
                reply = self.agent.ask(role, prompt)
            except Exception as e:  # noqa: BLE001 (any CLI failure is retried, then reported)
                if attempt == retries:
                    raise
                wait = delay * 2 ** attempt
                self.say(g, 'agent_retry', {'role': role, 'attempt': attempt + 1, 'wait': wait,
                                            'error': repr(e)[-300:]})
                self.sleep(wait)
                continue
            # The replay log: every answered call, in order (agents.ReplayAgent).
            with open(self.run_dir / 'replies.jsonl', 'a', encoding='utf-8') as f:
                f.write(json.dumps({'generation': g, 'role': role, 'prompt_sha256': agents.prompt_digest(prompt),
                                    'text': reply.text, 'tokens': reply.tokens, 'usage': reply.usage},
                                   sort_keys=True) + '\n')
            return reply

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
            if self.cid is not None:
                self.log_candidate(self.cid)
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
        prompt = agents.prompt_for(role, region=self.region, mode=mode, parents=parents, statistics=self.statistics,
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
        review = self.ask(g, 'critic', agents.prompt_for('critic', region=self.region, mode=proposal.mode,
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
            return True, self.refusal != 'guard'  # a guard refusal is not a gate failure
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
        if self.mode == 'nodes':
            trigger = True  # no trigger rate: a different order changes nodes or it does not
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
        text = '\n'.join(summary_line(r, self.region) for r in rows) or '(no candidates)'
        reply = self.ask(g, 'analyst', agents.prompt_for('analyst', region=self.region, every=self.cfg['analyst_every'],
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
        self.baseline_perft = None
        for variant in self.runner.variants():
            built, log, build = variant.build(tree)
            if not built:
                raise RuntimeError(f'the baseline does not build with {variant.compiler}: ' + log[-500:])
            counts = variant.perft(build / 'fork')
            if self.baseline_perft is not None and counts != self.baseline_perft:
                raise RuntimeError(f'the baseline perft differs between compilers: {counts} != {self.baseline_perft}')
            self.baseline_perft = counts
        # What the gate compares every candidate with: the baseline tree's
        # files and, per compiler, the preprocessed text of each unit that
        # includes the region.
        self.reference = gate.make_reference(self.runner, cfg['region'], tree, self.baseline_perft)
        return body

    def statistics_from(self, tag):
        """The baseline statistics an agent sees: the region's lines of the stats build's bench."""
        _, out = self.runner.run([str(self.runner.work / tag / 'build-stats' / 'fork'), 'bench'], timeout=900)
        keys = StatisticsKeys.get(self.region, StatisticsKeys['lmr'])
        return '\n'.join(line for line in out.split('\n') if line.startswith('stats:') and any(
            k in line for k in keys)) or self.statistics

    def start_nodes(self):
        """The nodes mode's generation 0: the baseline gated and measured twice (the self-check:
        every position's answer must repeat exactly, the second time split across one more
        engine process), the guard's threshold from the declared calibration bodies, then the
        baseline's descriptors and grid places."""
        cfg = self.cfg
        self.say(0, 'session', {'resumed': False})
        self.refresh(status='baseline: building, gating and measuring the committed region')
        body = self.prepare_baseline()
        cid = self.pop.add(0, 'baseline', 'baseline', None, 'residual', body, 'the committed region')
        if not self.gate(0, cid, body):
            self.log_candidate(cid)
            raise RuntimeError('the baseline fails its own gate')
        tag, jobs = f'cand-{cid}', cfg.get('proxy_jobs', 1)
        engine = self.runner.work / tag / 'build' / 'fork'
        checks = {}
        for name, rows in (('generation set', self.labels), ('held-out set', self.holdout)):
            if not rows:
                continue
            self.refresh(status=f'baseline: the self-check on the {name}')
            first = depth_nodes.run_fixed_depth(engine, rows, cfg['depth'], jobs, cfg.get('hash_mb', 16))
            second = depth_nodes.run_fixed_depth(engine, rows, cfg['depth'], jobs + 1, cfg.get('hash_mb', 16))
            same = [a.row() == b.row() for a, b in zip(first, second)]
            checks[name] = {'positions': len(rows), 'total': sum(a.nodes for a in first),
                            'digest': depth_nodes.digest(first), 'second_digest': depth_nodes.digest(second),
                            'differing_positions': same.count(False)}
            self.say(0, 'self_check', dict(checks[name], set=name))
            if not all(same):
                self.log_candidate(cid)
                raise RuntimeError(f'self-check failed on the {name}: {same.count(False)} positions differ between '
                                   f'two measurements of the baseline')
            if name == 'generation set':
                self.baseline_answers = first
            else:
                self.baseline_holdout_answers = first
        if not self.holdout:
            self.baseline_holdout_answers = []
        # The guard's threshold (the declaration): the lowest equivalent share
        # among the calibration bodies, less the declared margin.
        shares = []
        for k, item in enumerate(cfg['guard'].get('calibration', [])):
            kid = self.pop.add(0, 'calibration', 'calibration', None, 'residual', item['body'], item['name'])
            self.refresh(status=f'baseline: calibrating the guard ({item["name"]})')
            if not self.gate(0, kid, item['body']):
                self.log_candidate(kid)
                raise RuntimeError(f'the guard calibration body {item["name"]!r} fails the gate')
            answers = self.measure(f'cand-{kid}', self.labels)
            record = self.nodes_record(kid, answers, None)
            shares.append(record['equivalence'])
            self.pop.update(kid, status='calibration', proxies=json.dumps(record), fitness=record['gain'])
            self.say(0, 'calibration', {'id': kid, 'name': item['name'], 'equivalence': round(record['equivalence'], 5),
                                        'reduction': round(record['gain'], 5)})
            self.log_candidate(kid)
        if shares:
            self.guard_threshold = min(shares) - cfg['guard']['margin']
        self.say(0, 'guard_threshold', {'threshold': self.guard_threshold, 'shares': shares,
                                        'tolerance_cp': cfg['guard']['tolerance_cp'], 'margin': cfg['guard']['margin']})
        self.step = 'descriptors'
        desc = self.descriptors(tag)
        record = dict(self.nodes_record(cid, self.baseline_answers, self.baseline_holdout_answers or None),
                      guard_passed=True, self_check=checks)
        self.pop.update(cid, status='scored', proxies=json.dumps(record), descriptors=json.dumps(desc), fitness=0.0)
        for island in cfg['islands']:
            self.pop.offer_elite(island, cid, desc, 0.0)
        self.log_candidate(cid)
        self.baseline_fitness = 0.0
        self.best_nodes = [a.nodes for a in self.baseline_answers]
        self.statistics = self.statistics_from(tag)
        self.best_fitness, self.best_generation = 0.0, 0
        self.status = 'running'
        self.say(0, 'baseline', {'id': cid, 'fitness': 0.0, 'total': record['total'],
                                 'holdout_total': record.get('holdout_total'), 'perft': self.baseline_perft,
                                 'commit': self.commit, 'compiler': self.runner.compiler_version(),
                                 'depth': cfg['depth'], 'positions': len(self.labels),
                                 'holdout_positions': len(self.holdout), 'statistics': self.statistics})

    def start(self):
        """Generation 0: the baseline (the region as committed) gated, scored and seeded in every island."""
        cfg = self.cfg
        if self.mode == 'nodes':
            return self.start_nodes()
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
        self.log_candidate(cid)
        self.statistics = self.statistics_from(f'cand-{cid}')
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
        if self.mode == 'nodes':
            self.baseline_answers = [depth_nodes.answer_from_row(r) for r in record['per_position']]
            self.baseline_holdout_answers = [depth_nodes.answer_from_row(r)
                                             for r in record.get('holdout_per_position') or []]
            self.best_nodes = [a.nodes for a in self.baseline_answers]
            threshold = self.pop.events('guard_threshold')
            self.guard_threshold = json.loads(threshold[-1][2])['threshold'] if threshold else None
        improved = self.pop.events('improved')
        if improved:
            best_generation, _, best = improved[-1]
            b = self.pop.get(json.loads(best)['id'])
            if self.mode == 'nodes':
                self.best_nodes = [row[0] for row in json.loads(b['proxies'])['per_position']]
            else:
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


def candidate_outcomes(database):
    """{id: (body, status, fitness, generation-set digest, held-out digest)} of a run's database."""
    pop = population.Population(str(database))
    try:
        out = {}
        for cid, body, status, fitness, record in pop.db.execute(
                'SELECT id, body, status, fitness, proxies FROM candidates ORDER BY id'):
            r = json.loads(record) if record else {}
            out[cid] = (body, status, fitness, r.get('digest'), r.get('holdout_digest'))
        return out
    finally:
        pop.close()


def compare_outcomes(logged, replayed, ids=None):
    """Rows (id, same body, same status, same fitness, same answers, same held-out answers) for the
    candidates `ids` (all of the logged run's by default) and whether every one matches."""
    rows, ok = [], True
    for cid in ids or sorted(logged):
        a, b = logged.get(cid), replayed.get(cid)
        if a is None or b is None:
            rows.append((cid, False, False, False, False, False))
            ok = False
            continue
        row = (cid, a[0] == b[0], a[1] == b[1], a[2] == b[2], a[3] == b[3], a[4] == b[4])
        ok = ok and all(row[1:])
        rows.append(row)
    return rows, ok


def replay_candidates(loop, source, ids):
    """Rebuilds the baseline and the logged candidates `ids` of the run in `source` and measures
    them again (nodes mode): each one's gate verdict, fitness and answers on both sets must
    equal the log's exactly. Returns (report rows, all equal)."""
    src = population.Population(str(Path(source) / 'population.sqlite'))
    try:
        base_id = src.db.execute("SELECT id FROM candidates WHERE agent = 'baseline'").fetchone()[0]
        bodies = {cid: src.get(cid)['body'] for cid in [base_id] + list(ids)}
    finally:
        src.close()
    cfg = loop.cfg
    loop.say(0, 'session', {'resumed': False, 'replay_of': str(source), 'candidates': list(ids)})
    loop.prepare_baseline()
    replayed = {}
    for cid in [base_id] + list(ids):
        new = loop.pop.add(0, 'replay', 'replay', None, 'residual', bodies[cid], f'replay of candidate {cid}')
        if not loop.gate(0, new, bodies[cid]):
            replayed[cid] = (bodies[cid], loop.pop.get(new)['status'], None, None, None)
            continue
        answers = loop.measure(f'cand-{new}', loop.labels)
        held = loop.measure(f'cand-{new}', loop.holdout) if loop.holdout else []
        if cid == base_id:
            loop.baseline_answers, loop.baseline_holdout_answers = answers, held
        record = loop.nodes_record(new, answers, held or None)
        loop.pop.update(new, status='replayed', proxies=json.dumps(record), fitness=record['gain'])
        loop.log_candidate(new)
        replayed[cid] = (bodies[cid], None, record['gain'], record['digest'], record.get('holdout_digest'))
    logged = candidate_outcomes(Path(source) / 'population.sqlite')
    # Statuses differ by design here (replayed, not scored): compare the rest.
    logged = {cid: (v[0], None) + v[2:] for cid, v in logged.items()}
    rows, ok = compare_outcomes(logged, {cid: (v[0], None) + v[2:] for cid, v in replayed.items()},
                                [base_id] + list(ids))
    loop.say(0, 'replay_compared', {'rows': rows, 'equal': ok, 'depth': cfg['depth']})
    loop.close()
    return rows, ok


def make_patch(before, after, path):
    import difflib
    return ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), f'a/{path}', f'b/{path}'))


def dry_run_agent(region='lmr'):
    """Scripted replies for one generation: each funnel outcome once."""
    def proposal(mode, why, body):
        return f'MODE: {mode}\nRATIONALE: {why}\n```cpp\n{body}\n```\n'
    if region == 'quiet_order':
        return agents.StubAgent({
            'proposer_aggressive': [proposal('residual', 'Stub: the follow entry at the reply weight.',
                                             '  int score = s.butterfly;\n'
                                             '  if (s.has_reply) score += s.reply * s.reply_weight / 4;\n'
                                             '  if (s.has_follow) score += s.follow * s.reply_weight / 4;\n'
                                             '  return score;')],
            'proposer_cautious': [proposal('residual', 'Stub: a body that does not compile (the gate must stop it).',
                                           '  return s.butterfly +;')],
            'explorer': [proposal('full', 'Stub: a floating-point blend (the critic must reject it).',
                                  '  const double r = 0.5 * s.butterfly;\n  return static_cast<int>(r);')],
            'critic': ['VERDICT: accept\nREASONS: Stub critic: integer, deterministic, inside the body.',
                       'VERDICT: accept\nREASONS: Stub critic: looks fine (the gate will find the syntax error).',
                       'VERDICT: reject\nREASONS: Stub critic: floating point breaks the hot-path rules.'],
            'analyst': ['- Stub analyst: one generation only; nothing to summarize yet.'],
        })
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
    ap.add_argument('--replay-candidates', help='with --replay-from: rebuild and measure only these ids (a,b,...)')
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true', help='stub agents (no tokens)')
    mode.add_argument('--live', action='store_true', help='real agents through claude -p: the evolution loop')
    mode.add_argument('--replay-from', help='a logged run dir: run it again with its logged replies and compare')
    a = ap.parse_args()
    run_dir = Path(a.run_dir).expanduser()
    if a.replay_from:
        source = Path(a.replay_from).expanduser()
        cfg = json.loads((source / 'config.json').read_text(encoding='utf-8'))
        cfg['budget'] = dict(cfg['budget'], hours=10 ** 6)  # wall time must not cut a replay short
        runner = gate.Runner(cfg['repo'], run_dir / 'work', jobs=cfg.get('jobs', 4), test_cache=cfg.get('test_cache'),
                             compilers=cfg.get('compilers') or [cfg['compiler']])
        try:
            loop = Loop(cfg, run_dir, agents.ReplayAgent(source / 'replies.jsonl'), runner)
        except RunDirError as e:
            sys.exit(f'orchestrator: {e}')
        if a.replay_candidates:
            ids = [int(x) for x in a.replay_candidates.split(',')]
            rows, ok = replay_candidates(loop, source, ids)
        else:
            src = population.Population(str(source / 'population.sqlite'))
            last = max((g for g, _, _ in src.events('generation_done')), default=0)
            src.close()
            loop.run(a.generations or last)
            rows, ok = compare_outcomes(candidate_outcomes(source / 'population.sqlite'),
                                        candidate_outcomes(run_dir / 'population.sqlite'))
            if loop.agent.mismatches:
                ok = False
                print(f'replay: {len(loop.agent.mismatches)} agent calls differ from the log: '
                      f'{loop.agent.mismatches[:5]}')
        (run_dir / 'replay.json').write_text(json.dumps({'source': str(source), 'equal': ok, 'rows': rows},
                                                        indent=1), encoding='utf-8')
        print('id  body status fitness answers held-out')
        for r in rows:
            print(f'{r[0]:>3} ' + ' '.join(f'{"same" if x else "DIFF":>7}' for x in r[1:]))
        print(f'replay of {source}: {"every candidate reproduced exactly" if ok else "DIFFERENCES"}')
        sys.exit(0 if ok else 1)
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
            islands = ['proposer_aggressive', 'proposer_cautious', 'explorer'] if cfg['region'] == 'quiet_order' \
                else ['proposer_aggressive', 'proposer_cautious', 'proposer_stats', 'explorer']
            cfg.update(islands=islands, per_island=1, critic_audit_share=1.0)
    if a.live:
        agent = agents.CliAgent(**cfg.get('agent', {}))
        print('LIVE loop: real agents and tokens (owner approval required: deliverable 8c).', flush=True)
    else:
        agent = dry_run_agent(cfg['region'])
    # The gate's compilers are named, never CMake's default: a candidate's
    # verdict must not depend on what `c++` happens to be (audit-1 U-17);
    # with `compilers`, every one of them must pass (two-compiler gating).
    runner = gate.Runner(cfg['repo'], run_dir / 'work', jobs=cfg.get('jobs', 4), test_cache=cfg.get('test_cache'),
                         compilers=cfg.get('compilers') or [cfg['compiler']])
    try:
        loop = Loop(cfg, run_dir, agent, runner, resume=a.resume)
    except RunDirError as e:
        sys.exit(f'orchestrator: {e}')
    reason = loop.run(a.generations or cfg['generations'])
    print(f'stopped: {reason}; budget used {loop.budget.used}; run log {run_dir / "run.log"}')


if __name__ == '__main__':
    main()
