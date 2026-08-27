# -*- coding: utf-8 -*-
"""Decide, from the map's own shoreline, which edge each composite anchors on.

A composite covers one land cell plus a slice of its sea-side companion.  The
question is which end of the slice sits on the cell boundary.  The two answers
differ by the whole overflow (0.3-4.5 km here), so the modern shoreline settles
it: the sheet is placed under each hypothesis, the shoreline is fitted freely
over a wide window, and the hypothesis whose fitted correction is near zero is
the right one.
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import coastfit  # noqa: E402
import grid  # noqa: E402
from fit_singles import load  # noqa: E402

M = coastfit.M_PER_DEG
OPPOSITE = {'top': 'bottom', 'bottom': 'top', 'left': 'right', 'right': 'left'}


def main():
    segs = coastfit.load_osm()
    comps = sorted(s for s in
                   (os.path.splitext(f)[0] for f in os.listdir(os.path.join(HERE, 'masks')))
                   if len(s.split('-')[2]) == 2)
    print('%-14s %-8s %10s %10s %8s %6s  %s'
          % ('sheet', 'anchor', 'dlon(m)', 'dlat(m)', 'resid', 'div', 'verdict'))
    results = {}
    for sid in comps:
        sea, coast = load(sid)
        div = coastfit.orientation_diversity(sea)
        if coast.sum() < 300:
            print('%-14s %-8s %10s %10s %8s %6.2f  no shoreline - rule only'
                  % (sid, '-', '-', '-', '-', div))
            results[sid] = (None, 'no shoreline')
            continue
        rows = []
        for anchor in (grid.sheet_geometry(sid)['anchor'],):
            for a in (anchor, OPPOSITE[anchor]):
                g = grid.sheet_geometry(sid, anchor_override=a)
                pts = coastfit.sheet_coast_lonlat(coast, g)
                r = coastfit.fit(pts, segs, (g['west'], g['north'], g['east'], g['south']),
                                 search_deg=0.012, step_deg=0.0006)
                rows.append((a, r))
        for a, r in rows:
            if r is None:
                print('%-14s %-8s %10s %10s %8s %6.2f  (no fit)' % (sid, a, '-', '-', '-', div))
            else:
                print('%-14s %-8s %+10.0f %+10.0f %8.0f %6.2f'
                      % (sid, a, r[0] * M, r[1] * M, r[2], div))
        good = [(a, r) for a, r in rows if r is not None]
        if len(good) == 2 and div >= 0.30:
            (a1, r1), (a2, r2) = good
            d1 = np.hypot(r1[0], r1[1]) * M
            d2 = np.hypot(r2[0], r2[1]) * M
            pick = a1 if (d1 + r1[2]) < (d2 + r2[2]) else a2
            margin = abs((d1 + r1[2]) - (d2 + r2[2]))
            print('    -> %s  (margin %.0f m)' % (pick.upper(), margin))
            results[sid] = (pick, margin)
        else:
            results[sid] = (None, 'inconclusive')
        print()
    np.save(os.path.join(HERE, 'composite_anchor_votes.npy'),
            np.array(list(results.items()), dtype=object), allow_pickle=True)


if __name__ == '__main__':
    main()
