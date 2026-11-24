"""r8ceplo2's float weights laid out as round 3's two warm starts (H512+PP, S512+PPXL), quantised by the reference
(bullet's save list redone), converted at S = 87: equal to r8ceplo2's own converted file laid out by regioned_net /
exposure_net (before the clamp), as the kernel's in-session quantised identity checks them."""
import json
import sys
from pathlib import Path

nnue = Path(sys.argv[1])
sys.path.insert(0, str(nnue))
import convert  # noqa: E402
import extend_weights  # noqa: E402
import models  # noqa: E402
import netformat  # noqa: E402

src = Path(sys.argv[2]).read_bytes()


def quantised_net(name, data):
    desc = json.loads((nnue / f'{name}.json').read_text())
    arch = convert.arch_of(desc)
    w = netformat.read_weights_bin(data)
    w = {k: [models.to_f32(x) for x in v] for k, v in w.items()}
    saved = models.saved_tensors(arch, w)
    q = netformat.write_quantised({t['name']: saved[t['name']][1] for t in desc['quantised']}, desc)
    return convert.convert(q, desc, 87)


pp = quantised_net('s512pp', src)
for name, lay, fn in (('h512pp', extend_weights.regioned_weights, extend_weights.regioned_net),
                      ('s512ppxl', extend_weights.exposure_weights, extend_weights.exposure_net)):
    print(name, 'warm start quantised == laid-out r8ceplo2:', quantised_net(name, lay(src)) == fn(pp), flush=True)
