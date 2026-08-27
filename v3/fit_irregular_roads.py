# -*- coding: utf-8 -*-
"""Second opinion on the 4 anchors the coastline could not decide, using roads.

Same idea as fit_irregular.py (place the sheet under both candidate anchors,
fit freely, keep the one needing less correction) but against the OSM road
network instead of the coastline - a genuinely independent source, since it
uses different pixels on the sheet (roads, not shoreline) and a different
modern reference (OSM highways, not OSM coastline).
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import coastfit  # noqa: E402
import grid  # noqa: E402
import roadmask  # noqa: E402
from fit_roads import MAJOR  # noqa: E402

M = coastfit.M_PER_DEG
OPPOSITE = {'top': 'bottom', 'bottom': 'top', 'left': 'right', 'right': 'left'}
TARGETS = ['34-XXIII-ie', '36-XXVI-ie', '36-XXVII-fg', '36-XXVIII-dh']


def main():
    segs = coastfit.load_osm(os.path.join(HERE, 'osm_roads.json'), highway_classes=MAJOR)
    for sid in TARGETS:
        rm = roadmask.road_mask(os.path.join(grid.CROP_DIR, sid + '.jpg'))
        g0 = grid.sheet_geometry(sid)
        print('%-14s road px=%d  (need >=150)' % (sid, rm.sum()))
        if rm.sum() < 150:
            print('    -> not enough road ink on this sheet to test\n')
            continue
        div = coastfit.orientation_diversity(rm)
        print('    orientation diversity=%.2f (need >=0.30)' % div)
        if div < 0.30:
            print('    -> roads too straight here to pin both axes\n')
            continue
        results = {}
        for a in (g0['anchor'], OPPOSITE[g0['anchor']]):
            g = grid.sheet_geometry(sid, anchor_override=a)
            pts = coastfit.sheet_coast_lonlat(rm, g)
            r = coastfit.fit(pts, segs, (g['west'], g['north'], g['east'], g['south']),
                             search_deg=0.02, step_deg=0.001)
            results[a] = r
            if r:
                print('    anchor=%-7s dlon=%+6.0fm dlat=%+6.0fm resid=%5.0fm'
                      % (a, r[0] * M, r[1] * M, r[2]))
            else:
                print('    anchor=%-7s (no fit)' % a)
        good = {k: v for k, v in results.items() if v is not None}
        if len(good) == 2:
            (a1, r1), (a2, r2) = good.items()
            c1 = np.hypot(r1[0], r1[1]) * M + r1[2]
            c2 = np.hypot(r2[0], r2[1]) * M + r2[2]
            pick = a1 if c1 < c2 else a2
            margin = abs(c1 - c2)
            print('    -> road evidence says %s (margin %.0f m), rule says %s : %s'
                  % (pick.upper(), margin, g0['anchor'],
                     'AGREES' if pick == g0['anchor'] else 'DISAGREES'))
        print()


if __name__ == '__main__':
    main()
