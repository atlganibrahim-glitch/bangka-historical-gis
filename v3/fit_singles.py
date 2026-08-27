# -*- coding: utf-8 -*-
"""Validate the placement of the single-cell sheets against the OSM shoreline.

Only sheets whose shoreline actually constrains both axes are used: a sheet
showing one straight stretch of coast can slide along it, so its "fit" is
meaningless and is discarded rather than averaged in.
"""
import glob
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import coastfit  # noqa: E402
import grid  # noqa: E402

CACHE = os.path.join(HERE, 'masks')
SEARCH = 0.015          # +/- 1.7 km; we are checking a calibration, not searching blind
MIN_DIVERSITY = 0.30
MAX_RESID = 1000.0       # m; above this the shoreline has simply moved too much


def load(sid):
    z = np.load(os.path.join(CACHE, sid + '.npz'))
    shape = tuple(z['shape'])
    coast = np.zeros(shape, bool)
    yx = z['coast_yx']
    if len(yx):
        coast[yx[:, 0], yx[:, 1]] = True
    sea = np.unpackbits(z['sea'])[:shape[0] * shape[1]].reshape(shape).astype(bool)
    return sea, coast


def fit_sheet(sid, segs, geom=None, search=SEARCH):
    sea, coast = load(sid)
    if coast.sum() < 300:
        return None, 'no shoreline'
    g = geom or grid.sheet_geometry(sid)
    pts = coastfit.sheet_coast_lonlat(coast, g)
    div = coastfit.orientation_diversity(sea)
    if div < MIN_DIVERSITY:
        return None, 'shoreline too straight (%.2f)' % div
    r = coastfit.fit(pts, segs, (g['west'], g['north'], g['east'], g['south']),
                     search_deg=search)
    if r is None:
        return None, 'no overlap with OSM'
    dlon, dlat, resid, n = r
    if max(abs(dlon), abs(dlat)) > search * 0.97:
        return None, 'fit ran to the search bound'
    return (dlon, dlat, resid, n, div), None


def main():
    segs = coastfit.load_osm()
    ids = sorted(os.path.splitext(os.path.basename(f))[0]
                 for f in glob.glob(os.path.join(CACHE, '*.npz')))
    rows, rejected = [], {}
    for sid in [s for s in ids if len(s.split('-')[2]) == 1]:
        r, why = fit_sheet(sid, segs)
        if r is None:
            rejected[why] = rejected.get(why.split('(')[0], 0) + 1
            continue
        dlon, dlat, resid, n, div = r
        if resid > MAX_RESID:
            rejected['residual too large'] = rejected.get('residual too large', 0) + 1
            continue
        rows.append((sid, dlon, dlat, resid, n, div))
        print('%-14s dlon=%+7.0f m  dlat=%+7.0f m  resid=%4.0f m  div=%.2f'
              % (sid, dlon * coastfit.M_PER_DEG, dlat * coastfit.M_PER_DEG, resid, div),
              flush=True)

    a = np.array([[r[1], r[2], r[3]] for r in rows])
    M = coastfit.M_PER_DEG
    print('\n--- %d usable coastal sheets (rejected: %s) ---'
          % (len(rows), ', '.join('%s x%d' % (k, v) for k, v in sorted(rejected.items()))))
    print('median dlon %+.5f deg (%+.0f m)   median dlat %+.5f deg (%+.0f m)'
          % (np.median(a[:, 0]), np.median(a[:, 0]) * M, np.median(a[:, 1]), np.median(a[:, 1]) * M))
    print('MAD: lon %.0f m   lat %.0f m' %
          (np.median(np.abs(a[:, 0] - np.median(a[:, 0]))) * M,
           np.median(np.abs(a[:, 1] - np.median(a[:, 1]))) * M))
    print('median shoreline residual: %.0f m' % np.median(a[:, 2]))
    np.save(os.path.join(HERE, 'single_fits.npy'),
            np.array(rows, dtype=object), allow_pickle=True)


if __name__ == '__main__':
    main()
