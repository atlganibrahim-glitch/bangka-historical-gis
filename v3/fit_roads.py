# -*- coding: utf-8 -*-
"""Inland positional accuracy, measured against the OSM road network.

The coastline check answers "how far off is the map at the coast", which is
dominated by 90 years of real coastal change and is not the number a
vegetation-change model needs.  Roads move far less than coastlines, so this
is a genuine estimate of inland co-registration accuracy - closer to what
matters for comparing land cover between the historical sheets and a modern
base layer.
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

MAJOR = {'trunk', 'primary', 'secondary', 'tertiary', 'unclassified',
        'trunk_link', 'primary_link', 'secondary_link', 'tertiary_link'}
MIN_DIVERSITY = 0.30
MIN_ROAD_PX = 150
MAX_RESID = 1500.0
SEARCH = 0.015


def main():
    segs = coastfit.load_osm(os.path.join(HERE, 'osm_roads.json'), highway_classes=MAJOR)
    print('OSM major-road network: %d ways' % len(segs))
    ids = sorted(os.path.splitext(os.path.basename(f))[0]
                 for f in glob.glob(os.path.join(grid.CROP_DIR, '*.jpg')))
    rows, rejected = [], {}
    for sid in ids:
        rm = roadmask.road_mask(os.path.join(grid.CROP_DIR, sid + '.jpg'))
        if rm.sum() < MIN_ROAD_PX:
            rejected['too little road'] = rejected.get('too little road', 0) + 1
            continue
        div = coastfit.orientation_diversity(rm)
        if div < MIN_DIVERSITY:
            rejected['too straight'] = rejected.get('too straight', 0) + 1
            continue
        # measure against the uncorrected v3.0 grid, so this stays an
        # independent check rather than validating its own output
        g = grid.sheet_geometry(sid, apply_road_correction=False)
        pts = coastfit.sheet_coast_lonlat(rm, g)
        r = coastfit.fit(pts, segs, (g['west'], g['north'], g['east'], g['south']),
                         search_deg=SEARCH, step_deg=0.0008)
        if r is None:
            rejected['no OSM road nearby'] = rejected.get('no OSM road nearby', 0) + 1
            continue
        dlon, dlat, resid, n = r
        if max(abs(dlon), abs(dlat)) > SEARCH * 0.97:
            rejected['fit ran to search bound'] = rejected.get('fit ran to search bound', 0) + 1
            continue
        if resid > MAX_RESID:
            rejected['residual too large'] = rejected.get('residual too large', 0) + 1
            continue
        rows.append((sid, dlon, dlat, resid, n, div))
        print('%-14s dlon=%+7.0f m  dlat=%+7.0f m  resid=%5.0f m  div=%.2f  road_px=%d'
              % (sid, dlon * coastfit.M_PER_DEG, dlat * coastfit.M_PER_DEG, resid, div, rm.sum()),
              flush=True)

    print('\n' + '=' * 70)
    print('rejected: %s' % ', '.join('%s x%d' % kv for kv in sorted(rejected.items())))
    if not rows:
        print('no usable sheets')
        return
    a = np.array([[r[1], r[2], r[3]] for r in rows])
    M = coastfit.M_PER_DEG
    resid = a[:, 2]
    print('usable sheets: %d / %d' % (len(rows), len(ids)))
    print('median inland residual: %.0f m' % np.median(resid))
    print('P25 / P75: %.0f m / %.0f m' % (np.percentile(resid, 25), np.percentile(resid, 75)))
    print('P90: %.0f m   max: %.0f m' % (np.percentile(resid, 90), resid.max()))
    mad = np.median(np.abs(resid - np.median(resid)))
    print('median absolute deviation: %.0f m  (robust sigma ~ %.0f m)' % (mad, 1.4826 * mad))
    print('systematic component: median dlon %+.0f m, dlat %+.0f m'
          % (np.median(a[:, 0]) * M, np.median(a[:, 1]) * M))
    np.save(os.path.join(HERE, 'road_fits.npy'), np.array(rows, dtype=object), allow_pickle=True)


if __name__ == '__main__':
    main()
