import re
def blocks(s):
    out=[]; i=0
    while True:
        a=s.find('<<<<<<< HEAD\n',i)
        if a<0: break
        m=s.index('=======\n',a); b=s.index('>>>>>>> origin/phase-4\n',m)
        out.append((a,m,b)); i=b+1
    return out
# DESIGN.md: keep ours, then theirs.
p='docs/DESIGN.md'; s=open(p,encoding='utf-8',newline='').read()
(a,m,b),=blocks(s)
ours=s[a+13:m]; theirs=s[m+8:b]
s=s[:a]+ours+theirs+s[b+len('>>>>>>> origin/phase-4\n'):]
open(p,'w',encoding='utf-8',newline='').write(s)
# nets.md: first block theirs (r8brft1); second block ours with r8ceplo2's status rewritten.
p='docs/nets.md'; s=open(p,encoding='utf-8',newline='').read()
bl=blocks(s); assert len(bl)==2
(a2,m2,b2)=bl[1]; ours2=s[a2+13:m2]
lines=ours2.split('\n')
assert lines[0].startswith('| Status | The default network from 2026-11-14')
lines[0]=("| Status | The default network from 2026-11-14 (owner: promotion pre-approved on H1 with the gates passing and no "
 "held-out flag; H1 at about 5:12 PM EST) until r3kr1 replaced it the same day (default 2026-11-14 until r3kr1; owner's "
 "order, about 7:20 PM EST). The labeller of generation 4's part g4d (arm A, the score adjudication at 1,500 cp over 16 "
 "plies; started 2026-11-14 at 7:59 PM EST from a fresh x86-64-v3 PGO build of phase-4 1b5d686, bench-checked), by the "
 "one-switch-per-day rule; the cloud VM's switch at its next run is pending (DESIGN.md §5.3, labeller policy; §6, the "
 "decisions log). Still buildable with `-DFORK_NET=nets/r8ceplo2.fnet` (tests/bench-r8ceplo2.ref), checked in CI's `nets` "
 "job, which also runs its nnue suite: the cases of architecture 8, which the default build (architecture 9) no longer "
 "compiles |")
ours2='\n'.join(lines)
s=s[:a2]+ours2+s[b2+len('>>>>>>> origin/phase-4\n'):]
(a1,m1,b1)=blocks(s)[0]
s=s[:a1]+s[m1+8:b1]+s[b1+len('>>>>>>> origin/phase-4\n'):]
assert '<<<<<<<' not in s and '>>>>>>>' not in s
open(p,'w',encoding='utf-8',newline='').write(s)
