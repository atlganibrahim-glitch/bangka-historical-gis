# -*- coding: utf-8 -*-
"""Decide the anchoring edge of every sheet that is not a plain full cell.

A sheet printed longer or shorter than its cell touches a graticule line on
one edge only; which edge is a question about the world, so it is answered
against the modern shoreline rather than assumed.  The sheet is placed under
each candidate anchor and the shoreline is fitted freely; the anchor whose
fitted correction comes out near zero is the one that was already right.
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
MIN_DIVERSITY = 0.30


def main():
    segs = coastfit.load_osm()
    ids = sorted(os.path.splitext(f)[0] for f in os.listdir(grid.CROP_DIR)
                 if f.endswith('.jpg'))
    targets = [s for s in ids if grid.sheet_geometry(s)['anchor'] != 'cell']
    print('%d sheets need an anchor decision\n' % len(targets))
    print('%-14s %-10s %-8s %9s %9s %7s %6s' %
          ('sheet', 'kind', 'anchor', 'dlon(m)', 'dlat(m)', 'resid', 'div'))
    verdicts = {}
    for sid in targets:
        g0 = grid.sheet_geometry(sid)
        sea, coast = load(sid)
        div = coastfit.orientation_diversity(sea)
        span = abs(g0['span_lat_arcmin'] - 5.0) if g0['anchor'] in ('top', 'bottom') \
            else abs(g0['span_lon_arcmin'] - 5.0)
        if coast.sum() < 300 or div < MIN_DIVERSITY:
            print('%-14s %-10s %-8s  no usable shoreline (div %.2f) - keeping rule default'
                  % (sid, g0['kind'], g0['anchor'], div))
            verdicts[sid] = (g0['anchor'], 'rule', span * 1852)
            continue
        scores = {}
        for a in (g0['anchor'], OPPOSITE[g0['anchor']]):
            g = grid.sheet_geometry(sid, anchor_override=a)
            pts = coastfit.sheet_coast_lonlat(coast, g)
            r = coastfit.fit(pts, segs, (g['west'], g['north'], g['east'], g['south']),
                             search_deg=0.012, step_deg=0.0006)
            if r is None:
                continue
            scores[a] = r
            print('%-14s %-10s %-8s %+9.0f %+9.0f %7.0f %6.2f'
                  % (sid, g0['kind'], a, r[0] * M, r[1] * M, r[2], div))
        if len(scores) == 2:
            (a1, r1), (a2, r2) = scores.items()
            c1 = np.hypot(r1[0], r1[1]) * M + r1[2]
            c2 = np.hypot(r2[0], r2[1]) * M + r2[2]
            pick, margin = (a1, c2 - c1) if c1 < c2 else (a2, c1 - c2)
            agree = 'agrees with rule' if pick == g0['anchor'] else 'OVERRIDES rule'
            decisive = margin > 0.25 * span * 1852
            print('    -> %-6s margin %5.0f m over a %.0f m question : %s%s'
                  % (pick.upper(), margin, span * 1852, agree,
                     '' if decisive else ' (not decisive - keeping rule)'))
            verdicts[sid] = ((pick if decisive else g0['anchor']),
                             'shoreline' if decisive else 'rule', span * 1852)
        else:
            verdicts[sid] = (g0['anchor'], 'rule', span * 1852)
        print()
    print('\nfinal anchors:')
    for sid, (a, why, span) in sorted(verdicts.items()):
        print('  %-14s %-6s  (%s, %.0f m at stake)' % (sid, a, why, span))


if __name__ == '__main__':
    main()
