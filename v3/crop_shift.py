# -*- coding: utf-8 -*-
"""Pixel offset between the old (v2) crops and the new neatline crops.

Both are crops of the same underlying scan, so one is a translation of the
other plus a different amount of trimmed margin.  Phase correlation on a
downscaled grey version recovers that translation, which is what any pixel
coordinate measured on an old crop needs in order to be read against the new
geometry.
"""
import os
import sys

import cv2
import numpy as np
import pandas as pd
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import grid  # noqa: E402

REDUCE = 8


def grey(path, reduce=REDUCE):
    with Image.open(path) as im:
        return np.asarray(im.reduce(reduce).convert('L')).astype(np.float32)


def shift_old_to_new(old_path, new_path, reduce=REDUCE):
    """(dx, dy) in full-resolution pixels: new_xy = old_xy + (dx, dy)."""
    a, b = grey(old_path, reduce), grey(new_path, reduce)
    h = min(a.shape[0], b.shape[0])
    w = min(a.shape[1], b.shape[1])
    a, b = a[:h, :w], b[:h, :w]
    win = cv2.createHanningWindow((w, h), cv2.CV_32F)
    (dx, dy), resp = cv2.phaseCorrelate(a * win, b * win)
    return dx * reduce, dy * reduce, float(resp)


def main():
    df = pd.read_csv(grid.v2_metadata_path())
    rows = []
    for _, r in df.iterrows():
        old = os.path.join(ROOT, 'recovered_maps', str(r['crop_filename']))
        new = os.path.join(grid.CROP_DIR, r['sheet_id'] + '.jpg')
        if not (os.path.exists(old) and os.path.exists(new)):
            continue
        dx, dy, resp = shift_old_to_new(old, new)
        rows.append(dict(image_idx=int(r['image_idx']), sheet_id=r['sheet_id'],
                         old_crop=r['crop_filename'],
                         dx_px=round(dx, 1), dy_px=round(dy, 1),
                         confidence=round(resp, 3)))
        print('[%3d] %-14s dx=%+7.1f dy=%+7.1f  conf=%.3f'
              % (r['image_idx'], r['sheet_id'], dx, dy, resp), flush=True)
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(HERE, 'old_to_new_crop_shift.csv'), index=False)
    d = np.hypot(out.dx_px, out.dy_px)
    print('\n%d sheets' % len(out))
    print('shift magnitude px: median %.1f  P90 %.1f  max %.1f' %
          (np.median(d), np.percentile(d, 90), d.max()))
    print('  in metres (4.6 m/px): median %.0f  P90 %.0f  max %.0f' %
          (np.median(d) * 4.6, np.percentile(d, 90) * 4.6, d.max() * 4.6))
    print('low-confidence (<0.15) sheets: %d' % (out.confidence < 0.15).sum())


if __name__ == '__main__':
    main()
