# -*- coding: utf-8 -*-
"""Quantitative checks on the v3 placement."""
import glob
import os
import sys
from collections import Counter

import numpy as np
import rasterio

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import grid  # noqa: E402

M = 111320.0


def bounds_of(pattern):
    out = {}
    for f in glob.glob(pattern):
        sid = os.path.splitext(os.path.basename(f))[0]
        with rasterio.open(f) as d:
            out[sid] = (d.bounds.left, d.bounds.top, d.bounds.right, d.bounds.bottom)
    return out


def frame_bounds(sid, g):
    """The extent of the printed neatline (drop the scan margin outside it)."""
    fl, fr, ft, fb = g['frame_px']
    return (g['west'] + fl * g['xscale'],
            g['north'] - ft * g['yscale'],
            g['west'] + fr * g['xscale'],
            g['north'] - fb * g['yscale'])


def main():
    v3 = bounds_of(os.path.join(ROOT, 'GEOREF_V3', '*', '*.tif'))
    ids = sorted(v3)
    geoms = {s: grid.sheet_geometry(s) for s in ids}
    kinds = Counter(g['kind'] for g in geoms.values())
    print('=' * 74)
    print('v3 VERIFICATION   %d sheets   %s' % (len(ids), dict(kinds)))

    print('\n1. REGULAR SINGLE SHEETS ON THE EXACT GRATICULE')
    dev = []
    for sid, g in geoms.items():
        if g['anchor'] != 'cell':
            continue
        fb = frame_bounds(sid, g)
        cb = grid.cell_bounds(*g['cells'][0])
        dev.append(max(abs(fb[0] - cb[0]), abs(fb[1] - cb[1]),
                       abs(fb[2] - cb[2]), abs(fb[3] - cb[3])) * M)
    print('   neatline corner vs graticule: max %.3f m over %d sheets' % (max(dev), len(dev)))

    print('\n2. PAPER SCALE')
    sc = np.array([[g['xscale'], g['yscale']] for g in geoms.values()])
    nominal = grid.CELL / 4341.0
    print('   deg/px lon %.9f +/- %.9f   (%+.2f%% vs 5\'/4341px)'
          % (sc[:, 0].mean(), sc[:, 0].std(), (sc[:, 0].mean() / nominal - 1) * 100))
    fr = np.array([[g['frame_w'], g['frame_h']] for s, g in geoms.items()
                   if len(g['cells']) == 1 and g['anchor'] == 'cell'])
    asp = fr[:, 1] / fr[:, 0]
    print('   one-cell frame aspect h/w: %.4f +/- %.4f  (ellipsoid predicts 0.9943)'
          % (asp.mean(), asp.std()))

    print('\n3. SHEET EXTENTS THAT ARE NOT ONE CELL')
    for sid, g in sorted(geoms.items()):
        if g['anchor'] == 'cell':
            continue
        print('   %-14s %-10s anchor=%-6s  %.4f x %.4f arcmin  (%+.0f m beyond the cell)'
              % (sid, g['kind'], g['anchor'], g['span_lon_arcmin'], g['span_lat_arcmin'],
                 (max(g['span_lon_arcmin'], g['span_lat_arcmin']) - 5.0) * 1852))

    print('\n4. NEIGHBOUR SEAMS')
    ov = []
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = v3[ids[i]], v3[ids[j]]
            w = min(a[2], b[2]) - max(a[0], b[0])
            h = min(a[1], b[1]) - max(a[3], b[3])
            if w > 1e-9 and h > 1e-9:
                ov.append((ids[i], ids[j], w * M, h * M))
    widths = [min(x[2], x[3]) for x in ov]
    print('   overlapping pairs: %d   overlap width: median %.1f m, max %.1f m'
          % (len(ov), np.median(widths) if widths else 0, max(widths) if widths else 0))
    print('   (sheets overlap by exactly the scan margin kept outside the neatline;')
    print('    the neatlines themselves abut, see check 1)')
    big = [x for x in ov if min(x[2], x[3]) > 60]
    print('   overlaps wider than 60 m: %d' % len(big))
    for x in sorted(big, key=lambda t: -min(t[2], t[3]))[:6]:
        print('     %-14s x %-14s %6.0f m' % (x[0], x[1], min(x[2], x[3])))


if __name__ == '__main__':
    main()
