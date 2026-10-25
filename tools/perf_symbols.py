"""Sums a perf report's raw addresses by containing function, from the
binary's own symbol table (`nm -n -C`): WSL's perf is built without libelf
and cannot name them. Inlined code counts for the function it was inlined
into. Usage (tools/perf_gate.sh):
    perf report ... --stdio --sort symbol | python3 -I tools/perf_symbols.py BINARY [N]
"""
import bisect
import re
import subprocess
import sys

binary = sys.argv[1]
top = int(sys.argv[2]) if len(sys.argv) > 2 else 15
syms = []
for line in subprocess.run(['nm', '-n', '-C', binary], capture_output=True, text=True).stdout.splitlines():
    m = re.match(r'([0-9a-f]+) ([tTwW]) (.*)', line)
    if m:
        syms.append((int(m.group(1), 16), m.group(3)))
addrs = [a for a, _ in syms]
totals = {}
for line in sys.stdin:
    m = re.match(r'\s+([\d.]+)%\s+\[\.\]\s+0x([0-9a-f]+)', line)
    if not m:
        continue
    pct, addr = float(m.group(1)), int(m.group(2), 16)
    i = bisect.bisect_right(addrs, addr) - 1
    name = syms[i][1] if i >= 0 else '?'
    totals[name] = totals.get(name, 0.0) + pct
for name, pct in sorted(totals.items(), key=lambda kv: -kv[1])[:top]:
    print(f'{pct:6.2f}%  {name[:110]}')
