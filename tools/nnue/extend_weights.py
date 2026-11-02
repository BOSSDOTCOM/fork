# SPDX-License-Identifier: GPL-3.0-or-later

"""S512+X's warm start (owner, 2026-11-02: XGR's exposure plane as an add-on
to S512r2): S-512's float weights (bullet's optimiser_state/weights.bin,
records sorted by name) with the 650 exposure inputs (640 rows and their
10-input factoriser, tools/train --arch s512x) appended to the first layer
as zero columns. bullet stores the first layer input by input (hidden values
per input), so the new inputs are hidden x 650 zeros at the end of l0w;
every other tensor is copied. With zero exposure weights the network
computes exactly S-512's output, so the warm start begins at S512r2's
validation loss.

    extend_weights.py S512_WEIGHTS.bin OUT.bin
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import models  # noqa: E402
import netformat  # noqa: E402

EXPOSURE_INPUTS = models.EXPOSURE_ROWS + 10  # the rows and their factoriser


def add_exposure_inputs(weights, hidden=512):
    """S-512's weights {name: floats} as S512+X's initial weights."""
    if len(weights['l0w']) != models.PIECE_SQUARES * hidden or len(weights['l0b']) != hidden:
        raise ValueError("not S-512's first layer")
    out = dict(weights)
    out['l0w'] = list(weights['l0w']) + [0.0] * (EXPOSURE_INPUTS * hidden)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('weights')
    ap.add_argument('out')
    a = ap.parse_args(argv)
    w = netformat.read_weights_bin(Path(a.weights).read_bytes())
    data = netformat.write_weights_bin(add_exposure_inputs(w))
    Path(a.out).write_bytes(data)
    print(f'{a.out}: {len(data)} bytes, l0w {len(w["l0w"])} -> {len(w["l0w"]) + EXPOSURE_INPUTS * 512} values')
    return 0


if __name__ == '__main__':
    sys.exit(main())
