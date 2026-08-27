# -*- coding: utf-8 -*-
"""How well does each version's shoreline sit on the modern shoreline?

Compares the published v2 rasters against the v3 rebuild with no fitting at
all: the residual is measured where each version actually places the sheet.
"""
import os
import sys

import numpy as np
import pandas as pd
import rasterio
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import coastfit  # noqa: E402
import grid  # noqa: E402
import seamask  # noqa: E402
from fit_singles import load  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
M = coastfit.M_PER_DEG


NEAR_M = 3000.0     # a drawn shoreline further than this from any modern one is
                    # an inland blank (swamp, wide river), not a coast


def residual(pts, dist, meta):
    """Median offset of the drawn shoreline from the modern one.

    Restricted to shoreline pixels that have a modern counterpart within
    NEAR_M, so interior blank areas misread as water cannot dominate; returns
    None when too little of the sheet's water is actually coastal.
    """
    w0, n0, r = meta
    H, W = dist.shape
    xs = np.round((pts[:, 0] - w0) / r).astype(np.int32)
    ys = np.round((n0 - pts[:, 1]) / r).astype(np.int32)
    ok = (xs >= 0) & (xs < W) & (ys >= 0) & (ys < H)
    if ok.sum() < 50:
        return None
    d = dist[ys[ok], xs[ok]] * M
    near = d < NEAR_M
    if near.mean() < 0.30 or near.sum() < 50:
        return None
    return float(np.median(d[near])), float(near.mean())


def main():
    segs = coastfit.load_osm()
    v2map = pd.read_csv(os.path.join(ROOT, 'bangka_dataset_v2.csv')).set_index('sheet_id')
    rows = []
    for sid in sorted(os.path.splitext(f)[0] for f in os.listdir(grid.CROP_DIR)):
        kind = 'composite' if len(sid.split('-')[2]) == 2 else 'single'
        g3 = grid.sheet_geometry(sid)
        _, coast3 = load(sid)
        if coast3.sum() < 300:
            continue
        dist, meta = coastfit.distance_field(
            segs, g3['west'], g3['north'], g3['east'], g3['south'], 0.06, 0.0002)
        if dist is None:
            continue
        res3 = residual(coastfit.sheet_coast_lonlat(coast3, g3), dist, meta)
        if res3 is None:
            continue
        r3, cov3 = res3

        v2dir = 'GEOREF_FINAL_COMPOSITE_12' if kind == 'composite' else 'GEOREF_FINAL_STANDARD_164'
        v2f = os.path.join(ROOT, v2dir, sid + '.tif')
        old_crop = os.path.join(ROOT, 'recovered_maps', str(v2map.loc[sid, 'crop_filename']))
        if not (os.path.exists(v2f) and os.path.exists(old_crop)):
            continue
        with rasterio.open(v2f) as d:
            b = d.bounds
        m2 = seamask.sea_mask(old_crop)
        c2 = seamask.coastline(m2)
        if c2.sum() < 300:
            continue
        g2 = dict(west=b.left, north=b.top, east=b.right, south=b.bottom)
        res2 = residual(coastfit.sheet_coast_lonlat(c2, g2), dist, meta)
        if res2 is None:
            continue
        r2, cov2 = res2
        rows.append((sid, kind, r2, r3))
        print('%-14s %-9s  v2=%6.0f m   v3=%6.0f m   %+6.0f m'
              % (sid, kind, r2, r3, r3 - r2), flush=True)

    a = pd.DataFrame(rows, columns=['sheet_id', 'kind', 'v2_resid_m', 'v3_resid_m'])
    a.to_csv(os.path.join(HERE, 'v2_v3_shoreline_residuals.csv'), index=False)
    print('\n' + '=' * 60)
    for k in ('single', 'composite'):
        s = a[a.kind == k]
        if len(s):
            print('%-10s n=%3d   median residual  v2 %5.0f m -> v3 %5.0f m   (%+.0f m)'
                  % (k, len(s), s.v2_resid_m.median(), s.v3_resid_m.median(),
                     s.v3_resid_m.median() - s.v2_resid_m.median()))
    print('%-10s n=%3d   median residual  v2 %5.0f m -> v3 %5.0f m'
          % ('all', len(a), a.v2_resid_m.median(), a.v3_resid_m.median()))
    better = (a.v3_resid_m < a.v2_resid_m).sum()
    print('improved on %d of %d sheets' % (better, len(a)))


if __name__ == '__main__':
    main()
