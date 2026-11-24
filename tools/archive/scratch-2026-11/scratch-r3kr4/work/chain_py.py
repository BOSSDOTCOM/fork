import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import models, netformat, convert, extend_weights, json
def net_from_float(name, weights, desc_path, scale):
    desc = json.loads(Path(desc_path).read_text())
    arch = convert.arch_of(desc)
    w = netformat.read_weights_bin(Path(weights).read_bytes())
    w = {k: [models.to_f32(x) for x in v] for k, v in w.items()}
    saved = models.saved_tensors(arch, w)
    payload = models.map_block(arch) + models.pack(models.fork_tensors(arch, saved, scale))
    return netformat.write_net2(arch.id, arch.saved_inputs, arch.hidden, 8, scale, payload)
root = Path(sys.argv[1]).parent.parent
pp = net_from_float('s512pp', sys.argv[2], root / 'tools/nnue/s512pp.json', 88)
kr = net_from_float('h512pp', sys.argv[3], root / 'tools/nnue/h512pp.json', 88)
r8 = (root / 'nets/r8brft1.fnet').read_bytes()
def diff(a, b):
    return sum(1 for i in range(0, len(a), 2) if a[i:i+2] != b[i:i+2])
print('s512pp from float vs r8brft1.fnet: same size', len(pp) == len(r8), 'differing i16 words (payload)', diff(pp[64:], r8[64:]))
ex = extend_weights.regioned_net(pp)
print('h512pp from float == expand(s512pp from float):', kr == ex)
Path(sys.argv[4]).write_bytes(kr)
