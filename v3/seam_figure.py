# -*- coding: utf-8 -*-
"""Side-by-side detail of one composite seam, v2 against v3."""
import glob
import os
import sys

import numpy as np
import rasterio
from PIL import Image, ImageDraw
from rasterio.enums import Resampling
from rasterio.warp import reproject

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
Image.MAX_IMAGE_PIXELS = None


def render(files, west, east, south, north, ppd, use_mask):
    W, H = int((east - west) * ppd), int((north - south) * ppd)
    canvas = np.full((H, W, 3), 255, np.uint8)
    hits = np.zeros((H, W), np.int16)
    for f in files:
        with rasterio.open(f) as ds:
            b = ds.bounds
            if b.right < west or b.left > east or b.top < south or b.bottom > north:
                continue
            tw = max(int(round((b.right - b.left) * ppd)), 1)
            th = max(int(round((b.top - b.bottom) * ppd)), 1)
            a = np.transpose(ds.read(out_shape=(3, th, tw),
                                     resampling=Resampling.average), (1, 2, 0))
            if use_mask:
                m = ds.read_masks(1, out_shape=(th, tw),
                                  resampling=Resampling.nearest) > 127
            else:
                m = np.ones((th, tw), bool)
        x0 = int(round((b.left - west) * ppd))
        y0 = int(round((north - b.top) * ppd))
        sx0, sy0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x0 + tw, W), min(y0 + th, H)
        if sx0 >= x1 or sy0 >= y1:
            continue
        sub = a[sy0 - y0:y1 - y0, sx0 - x0:x1 - x0]
        sm = m[sy0 - y0:y1 - y0, sx0 - x0:x1 - x0]
        win = canvas[sy0:y1, sx0:x1]
        win[sm] = sub[sm]
        canvas[sy0:y1, sx0:x1] = win
        hits[sy0:y1, sx0:x1] += sm.astype(np.int16)
    return canvas, hits


def main():
    # the worst v2 overhang: 35-XXVII-ko spilling east over 35-XXVII-l
    west, east, south, north = 106.28, 106.44, -2.95, -2.79
    ppd = 3600
    v2 = glob.glob(os.path.join(ROOT, 'GEOREF_FINAL_STANDARD_164', '*.tif')) + \
        glob.glob(os.path.join(ROOT, 'GEOREF_FINAL_COMPOSITE_12', '*.tif'))
    v2 = [f for f in v2 if not f.endswith('.aux.xml')]
    v3 = glob.glob(os.path.join(ROOT, 'GEOREF_V3', '*', '*.tif'))

    panels = []
    for name, files, use_mask in (('v2 (published)', v2, False), ('v3 (rebuilt)', v3, True)):
        img, hits = render(files, west, east, south, north, ppd, use_mask)
        over = hits > 1
        tint = img.copy()
        tint[over] = (0.45 * tint[over] + 0.55 * np.array([230, 40, 40])).astype(np.uint8)
        pil = Image.fromarray(tint)
        d = ImageDraw.Draw(pil)
        d.rectangle([0, 0, pil.width - 1, pil.height - 1], outline=(60, 60, 60), width=3)
        d.text((14, 12), '%s   double-covered: %.2f%%'
               % (name, 100.0 * over.sum() / max((hits > 0).sum(), 1)), fill=(20, 20, 20))
        panels.append(pil)

    gap = 18
    out = Image.new('RGB', (sum(p.width for p in panels) + gap, panels[0].height), 'white')
    x = 0
    for p in panels:
        out.paste(p, (x, 0))
        x += p.width + gap
    dst = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'seam_v2_v3.png')
    out.save(dst)
    print('wrote', dst, out.size)


if __name__ == '__main__':
    main()
