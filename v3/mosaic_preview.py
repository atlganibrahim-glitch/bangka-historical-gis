# -*- coding: utf-8 -*-
"""Low-resolution island mosaic, for eyeballing sheet alignment."""
import glob
import os
import sys

import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling

Image.MAX_IMAGE_PIXELS = None
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

WEST, EAST, SOUTH, NORTH = 105.05, 106.95, -3.30, -1.55
PPD = 900          # output pixels per degree


def build(patterns, out_png, outline_kind=None):
    W = int((EAST - WEST) * PPD)
    H = int((NORTH - SOUTH) * PPD)
    canvas = np.full((H, W, 3), 255, np.uint8)
    drawn = np.zeros((H, W), bool)
    double = np.zeros((H, W), np.int16)
    files = []
    for p in patterns:
        files += glob.glob(p)
    for f in sorted(files):
        msk = None
        with rasterio.open(f) as ds:
            b = ds.bounds
            tw = max(int(round((b.right - b.left) * PPD)), 1)
            th = max(int(round((b.top - b.bottom) * PPD)), 1)
            a = ds.read(out_shape=(ds.count, th, tw), resampling=Resampling.average)
            a = np.transpose(a[:3], (1, 2, 0)) if ds.count >= 3 else \
                np.repeat(np.transpose(a[:1], (1, 2, 0)), 3, axis=2)
        x0 = int(round((b.left - WEST) * PPD))
        y0 = int(round((NORTH - b.top) * PPD))
        x1, y1 = min(x0 + tw, W), min(y0 + th, H)
        sx0, sy0 = max(x0, 0), max(y0, 0)
        if sx0 >= x1 or sy0 >= y1:
            continue
        sub = a[sy0 - y0:y1 - y0, sx0 - x0:x1 - x0]
        if msk is None:
            msk = np.ones(a.shape[:2], bool)
        sm = msk[sy0 - y0:y1 - y0, sx0 - x0:x1 - x0]
        win = canvas[sy0:y1, sx0:x1]
        win[sm] = sub[sm]
        canvas[sy0:y1, sx0:x1] = win
        double[sy0:y1, sx0:x1] += sm.astype(np.int16)
        # red hairline around every sheet, so gaps and overlaps are visible
        canvas[sy0:y1, sx0:min(sx0 + 2, x1)] = (220, 0, 0)
        canvas[sy0:y1, max(x1 - 2, sx0):x1] = (220, 0, 0)
        canvas[sy0:min(sy0 + 2, y1), sx0:x1] = (220, 0, 0)
        canvas[max(y1 - 2, sy0):y1, sx0:x1] = (220, 0, 0)
        drawn[sy0:y1, sx0:x1] |= sm
    Image.fromarray(canvas).save(out_png)
    return drawn.sum(), int((double > 1).sum()), int(double.max())


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'mosaic_v3.png')
    which = sys.argv[2] if len(sys.argv) > 2 else 'v3'
    if which == 'v3':
        pats = [os.path.join(ROOT, 'GEOREF_V3', '*', '*.tif')]
    else:
        pats = [os.path.join(ROOT, 'GEOREF_FINAL_STANDARD_164', '*.tif'),
                os.path.join(ROOT, 'GEOREF_FINAL_COMPOSITE_12', '*.tif')]
    cov, dbl, mx = build(pats, out)
    print('painted px: %d   double-painted: %d (%.3f%%)   max sheets on one px: %d'
          % (cov, dbl, 100.0 * dbl / max(cov, 1), mx))
