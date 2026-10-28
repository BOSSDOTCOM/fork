# SPDX-License-Identifier: GPL-3.0-or-later

"""The population database and the event log (ideas.md idea 23).

SQLite (standard library), one file per run, never committed. Tables:
- candidates: every proposal with its parent, island, agent, mode (residual
  or full replacement), region body, rationale, status and each funnel
  stage's result (critic, guard, gate, proxies, match), so a run can be
  audited and resumed;
- elites: the grid, MAP-Elites style (Mouret and Clune 2015, KB research.md
  §9): one elite per island and cell, a cell being the pair of behaviour
  descriptors (mean LMR reduction, re-search share) binned, plus the
  groups of context inputs the body reads (the owner, 2026-10-27: rules
  built on new information get niches of their own instead of competing
  with the table's refinements; groups, not exact input sets, which gave
  nearly every candidate a cell of its own in the validation run); a
  candidate enters an empty cell or replaces a fitter-proxied occupant only
  if it is fitter;
- events: an append-only log (critic rejections with reasons, gate
  failures, budget use, stops);
- meta: the run's fixed facts, such as the baseline commit's full hash.
Parent selection is seeded and depends only on the database's contents, so
a run is reproducible.
"""
import json
import random
import re
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS candidates (
  id INTEGER PRIMARY KEY, generation INTEGER, island TEXT, agent TEXT, parent INTEGER,
  mode TEXT, body TEXT, rationale TEXT, status TEXT,
  critic TEXT, gate TEXT, proxies TEXT, descriptors TEXT, fitness REAL, match TEXT, created REAL);
CREATE TABLE IF NOT EXISTS elites (
  island TEXT, cell TEXT, candidate INTEGER, fitness REAL, PRIMARY KEY (island, cell));
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY, generation INTEGER, kind TEXT, detail TEXT, created REAL);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""

# Grid bins: mean reduction in steps of 0.25 plies, re-search share in steps
# of 2 percentage points (Fork's bench: 0.5% re-searched at Milestone B).
ReductionBin = 0.25
ResearchBin = 0.02


# The LMR context's information inputs (lmr_table.hpp, LmrContext) in the
# owner's three groups (2026-10-27): move facts (its history, what the moved
# piece is and does), node facts, and iteration facts (how the search as a
# whole is going). depth, move_number, base and on_pv are left out: nearly
# every rule reads them, so they would not separate one kind of rule from
# another.
InputGroups = (('move', ('history', 'piece', 'threatened', 'attacks')),
               ('node', ('quiet_moves', 'phase', 'entry_bound', 'entry_depth')),
               ('iteration', ('score_trend', 'branch_share')))
_FIELD = re.compile(r'\bc\.([A-Za-z_]\w*)')


def inputs_used(body):
    """The input groups a region body reads, in InputGroups order, joined by '+' ('-' for none)."""
    fields = set(_FIELD.findall(body))
    return '+'.join(name for name, members in InputGroups if fields & set(members)) or '-'


def cell_of(descriptors, body=''):
    mean_reduction, research_share = descriptors[:2]
    return f'{int(mean_reduction / ReductionBin)}:{int(research_share / ResearchBin)}:{inputs_used(body)}'


class Population:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)

    def add(self, generation, island, agent, parent, mode, body, rationale):
        cur = self.db.execute(
            'INSERT INTO candidates (generation, island, agent, parent, mode, body, rationale, status, created) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (generation, island, agent, parent, mode, body, rationale, 'proposed', time.time()))
        self.db.commit()
        return cur.lastrowid

    def update(self, cid, **fields):
        cols = ', '.join(f'{k} = ?' for k in fields)
        values = [json.dumps(v) if isinstance(v, (dict, list, tuple)) else v for v in fields.values()]
        self.db.execute(f'UPDATE candidates SET {cols} WHERE id = ?', values + [cid])
        self.db.commit()

    def get(self, cid):
        row = self.db.execute('SELECT * FROM candidates WHERE id = ?', (cid,)).fetchone()
        if row is None:
            return None
        names = [d[0] for d in self.db.execute('SELECT * FROM candidates LIMIT 0').description]
        return dict(zip(names, row))

    def set_meta(self, key, value):
        self.db.execute('INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)', (key, value))
        self.db.commit()

    def get_meta(self, key):
        row = self.db.execute('SELECT value FROM meta WHERE key = ?', (key,)).fetchone()
        return row[0] if row else None

    def log(self, generation, kind, detail):
        self.db.execute('INSERT INTO events (generation, kind, detail, created) VALUES (?, ?, ?, ?)',
                        (generation, kind, json.dumps(detail) if not isinstance(detail, str) else detail,
                         time.time()))
        self.db.commit()

    def events(self, kind=None):
        q = 'SELECT generation, kind, detail FROM events' + (' WHERE kind = ?' if kind else '') + ' ORDER BY id'
        return self.db.execute(q, (kind,) if kind else ()).fetchall()

    def offer_elite(self, island, cid, descriptors, fitness):
        """Puts candidate `cid` in its cell if the cell is empty or it is fitter; True if it entered."""
        cell = cell_of(descriptors, self.get(cid)['body'] or '')
        row = self.db.execute('SELECT fitness FROM elites WHERE island = ? AND cell = ?', (island, cell)).fetchone()
        if row is not None and row[0] >= fitness:
            return False
        self.db.execute('INSERT OR REPLACE INTO elites (island, cell, candidate, fitness) VALUES (?, ?, ?, ?)',
                        (island, cell, cid, fitness))
        self.db.commit()
        return True

    def elites(self, island):
        return self.db.execute('SELECT cell, candidate, fitness FROM elites WHERE island = ? ORDER BY cell',
                               (island,)).fetchall()

    def best(self, island=None):
        q = 'SELECT candidate, fitness FROM elites' + (' WHERE island = ?' if island else '') + \
            ' ORDER BY fitness DESC, candidate LIMIT 1'
        return self.db.execute(q, (island,) if island else ()).fetchone()

    def choose_parents(self, island, count, seed):
        """Up to `count` elites of `island`, cells chosen uniformly (MAP-Elites), seeded."""
        cells = self.elites(island)
        if not cells:
            return []
        rng = random.Random(seed)
        picks = [rng.choice(cells) for _ in range(count)]
        return sorted({p[1] for p in picks})

    def reseed(self, island, from_island):
        """Replaces `island`'s elites with `from_island`'s best (FunSearch-style reset)."""
        best = self.best(from_island)
        self.db.execute('DELETE FROM elites WHERE island = ?', (island,))
        if best:
            row = self.db.execute('SELECT cell FROM elites WHERE island = ? AND candidate = ?',
                                  (from_island, best[0])).fetchone()
            self.db.execute('INSERT INTO elites (island, cell, candidate, fitness) VALUES (?, ?, ?, ?)',
                            (island, row[0], best[0], best[1]))
        self.db.commit()

    def close(self):
        self.db.close()
