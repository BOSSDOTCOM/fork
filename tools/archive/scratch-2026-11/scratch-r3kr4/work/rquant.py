import sys, json
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import models, netformat, convert
desc = json.loads(Path(sys.argv[2]).read_text())
arch = convert.arch_of(desc)
w = netformat.read_weights_bin(Path(sys.argv[3]).read_bytes())
w = {k: [models.to_f32(x) for x in v] for k, v in w.items()}
saved = models.saved_tensors(arch, w)
q = {t['name']: saved[t['name']][1] for t in desc['quantised']}
Path(sys.argv[4]).write_bytes(netformat.write_quantised(q, desc))
