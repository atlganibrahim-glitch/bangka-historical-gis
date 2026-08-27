# -*- coding: utf-8 -*-
"""Did the v3.1 road-network correction actually help?

Re-measures inland accuracy against OSM roads under both grids.  The fit is
the same in both cases; only the starting placement differs, so the residual
shift should collapse towards zero for v3.1 if the correction is real.
"""
import glob
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import coastfit  # noqa: E402
import grid  # noqa: E402
import roadmask  # noqa: E402
from fit_roads import MAJOR, MIN_DIVERSITY, MIN_ROAD_PX, SEARCH  # noqa: E402

M = coastfit.M_PER_DEG


def measure(segs, corrected):
    ids = sorted(os.path.splitext(os.path.basename(f))[0]
                 for f in glob.glob(os.path.join(grid.CROP_DIR, '*.jpg')))
    out = []
    for sid in ids:
        rm = roadmask.road_mask(os.path.join(grid.CROP_DIR, sid + '.jpg'))
        if rm.sum() < MIN_ROAD_PX:
            continue
        if coastfit.orientation_diversity(rm) < MIN_DIVERSITY:
            continue
        g = grid.sheet_geometry(sid, apply_road_correction=corrected)
        pts = coastfit.sheet_coast_lonlat(rm, g)
        r = coastfit.fit(pts, segs, (g['west'], g['north'], g['east'], g['south']),
                         search_deg=SEARCH, step_deg=0.0008)
        if r is None or max(abs(r[0]), abs(r[1])) > SEARCH * 0.97:
            continue
        out.append((sid, r[0] * M, r[1] * M, r[2]))
    return out


def summarise(name, rows):
    a = np.array([[r[1], r[2], r[3]] for r in rows])
    dist = np.hypot(a[:, 0], a[:, 1])
    print('%-6s n=%3d   median |shift| %6.1f m   median dE %+7.1f  dN %+7.1f   '
          'sheets within 100 m: %d (%.0f%%)'
          % (name, len(rows), np.median(dist), np.median(a[:, 0]), np.median(a[:, 1]),
             (dist < 100).sum(), 100.0 * (dist < 100).mean()))
    return dist


def main():
    segs = coastfit.load_osm(os.path.join(HERE, 'osm_roads.json'), highway_classes=MAJOR)
    print('OSM major roads: %d ways\n' % len(segs))
    print('Residual shift still needed after placement (smaller = better):')
    d0 = summarise('v3.0', measure(segs, corrected=False))
    d1 = summarise('v3.1', measure(segs, corrected=True))
    print('\nmedian residual shift: %.1f m -> %.1f m  (%+.1f m)'
          % (np.median(d0), np.median(d1), np.median(d1) - np.median(d0)))


if __name__ == '__main__':
    main()
