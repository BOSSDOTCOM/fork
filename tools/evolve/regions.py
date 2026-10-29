# SPDX-License-Identifier: GPL-3.0-or-later

"""Evolvable regions and the mutator guard (ideas.md idea 23).

An evolvable region is the code between two marker lines in one source file:

    // FORK-EVOLVE-BEGIN <name>
    ...the body a candidate may replace...
    // FORK-EVOLVE-END <name>

Only bodies are exchanged. The guard rejects any candidate whose file differs
from the baseline anywhere outside the region, removes or renames a marker,
or touches any other file, before anything is built.
"""
import re
from dataclasses import dataclass

BEGIN = '// FORK-EVOLVE-BEGIN '
END = '// FORK-EVOLVE-END '

# Registered regions: name -> the repository file holding it. The pilot
# evolves the late move reduction correction only (deliverable 8c).
REGIONS = {'lmr': 'src/search/lmr_table.hpp'}

_NAME = re.compile(r'^[a-z][a-z0-9_]*$')


@dataclass(frozen=True)
class Span:
    """Line indices: lines[begin] is the BEGIN marker, lines[end] the END marker."""
    name: str
    begin: int
    end: int


class RegionError(ValueError):
    pass


def find_regions(text):
    """Every region in `text`, by name; markers must pair up, unnested, once each."""
    lines = text.split('\n')
    spans, open_name, open_at = {}, None, None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(BEGIN):
            name = stripped[len(BEGIN):].strip()
            if open_name is not None:
                raise RegionError(f'region {name!r} opens inside {open_name!r} (line {i + 1})')
            if not _NAME.match(name) or name in spans:
                raise RegionError(f'bad or repeated region name {name!r} (line {i + 1})')
            open_name, open_at = name, i
        elif stripped.startswith(END):
            name = stripped[len(END):].strip()
            if name != open_name:
                raise RegionError(f'END {name!r} without its BEGIN (line {i + 1})')
            spans[name] = Span(name, open_at, i)
            open_name = None
    if open_name is not None:
        raise RegionError(f'region {open_name!r} is never closed')
    return spans


def body(text, name):
    """The body of region `name` (the lines between its markers)."""
    span = find_regions(text).get(name)
    if span is None:
        raise RegionError(f'no region {name!r}')
    lines = text.split('\n')
    return '\n'.join(lines[span.begin + 1:span.end])


def replace_body(text, name, new_body):
    """`text` with region `name`'s body replaced; markers and the rest unchanged."""
    span = find_regions(text).get(name)
    if span is None:
        raise RegionError(f'no region {name!r}')
    lines = text.split('\n')
    new_lines = new_body.rstrip('\n').split('\n') if new_body.strip() else []
    return '\n'.join(lines[:span.begin + 1] + new_lines + lines[span.end:])


def guard(baseline_files, candidate_files, name):
    """(True, '') if the candidate changes only region `name`'s body, else (False, reason).

    Both arguments map repository paths to file text. The candidate may name
    only the region's file; that file must equal the baseline once both
    bodies are blanked, with the markers exactly as before.
    """
    path = REGIONS.get(name)
    if path is None:
        return False, f'unknown region {name!r}'
    others = sorted(p for p in candidate_files if p != path)
    if others:
        return False, f'touches files outside the region: {", ".join(others)}'
    if path not in candidate_files:
        return False, f'does not contain {path}'
    try:
        base_spans = find_regions(baseline_files[path])
        cand_spans = find_regions(candidate_files[path])
    except RegionError as e:
        return False, f'markers: {e}'
    if set(base_spans) != set(cand_spans):
        return False, 'adds, removes or renames a region marker'
    blank_base = replace_body(baseline_files[path], name, '')
    blank_cand = replace_body(candidate_files[path], name, '')
    if blank_base != blank_cand:
        return False, f'changes {path} outside region {name!r}'
    return True, ''
