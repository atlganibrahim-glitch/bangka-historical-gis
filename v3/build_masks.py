# -*- coding: utf-8 -*-
"""Cache the sea mask / shoreline of every sheet (slow part, run once)."""
import glob
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import seamask  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, 'masks')


def main():
    os.makedirs(CACHE, exist_ok=True)
    files = sorted(glob.glob(os.path.join(seamask.__dict__['__file__'], '..', '..',
                                          'new_crops', 'map', '*.jpg')))
    files = [os.path.normpath(f) for f in files]
    for i, f in enumerate(files, 1):
        sid = os.path.splitext(os.path.basename(f))[0]
        out = os.path.join(CACHE, sid + '.npz')
        if os.path.exists(out):
            continue
        m = seamask.sea_mask(f)
        c = seamask.coastline(m)
        np.savez_compressed(out, sea=np.packbits(m), coast_yx=np.argwhere(c).astype(np.int16),
                            shape=np.array(m.shape))
        print('[%3d/%d] %-14s sea=%.3f coast=%d' % (i, len(files), sid, m.mean(), c.sum()),
              flush=True)


if __name__ == '__main__':
    main()
