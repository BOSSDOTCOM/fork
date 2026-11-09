# SPDX-License-Identifier: GPL-3.0-or-later

"""An anchor's fastchess options, from its own `uci` output
(.github/workflows/gauntlet.yml, the games jobs of both modes): the options
the table lists (tools/gauntlet/anchors.tsv, last column) that the engine
has, any thread option at 1 and any book switch off. Prints them as
"option.NAME=VALUE ..." (nothing if none).

    python3 tools/gauntlet/uci_options.py LISTED UCI_OUTPUT
"""
import re
import sys

listed = [] if sys.argv[1] == '-' else sys.argv[1].split()
names = {}
for line in open(sys.argv[2], errors='replace'):
    m = re.match(r'option name (.+?) type (\w+)', line.strip())
    if m:
        names[m.group(1)] = m.group(2)
chosen = {}
for o in listed:
    key, value = o[len('option.'):].split('=', 1)
    if key in names:
        chosen[key] = value
for key, kind in names.items():
    if re.fullmatch(r'(num)?_?threads', key, re.I):
        chosen.setdefault(key, '1')
    if 'book' in key.lower() and kind == 'check':
        chosen.setdefault(key, 'false')
print(' '.join(f'option.{k}={v}' for k, v in chosen.items()))
