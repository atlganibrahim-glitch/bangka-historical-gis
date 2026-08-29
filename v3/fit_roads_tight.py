# -*- coding: utf-8 -*-
"""Retry the sheets fit_roads.py could not resolve, with a tighter road class
filter (trunk + primary only, dropping secondary/tertiary/unclassified).

NEGATIVE RESULT - kept to document that this avenue was tried and closed.

Hypothesis: modern OSM has far more secondary/tertiary/unclassified roads
than existed in the 1930s (village and estate access roads), so the wider
filter gives the fit more wrong candidates to lock onto, and restricting to
the oldest, most stable routes should recover some of the 71 sheets that
fitted but scattered away from the consensus shift.

Outcome: it does not. Only 2 of 71 came into agreement, and their residuals
were poor (234 m and 1956 m). The reason is visible in the diagnostics:
sheets that scatter have a median best-fit residual of 408 m versus 30 m for
sheets that converge - i.e. their drawn roads do not match the modern network
well at *any* shift, so no amount of filter tuning aligns them. Outliers are
also spatially interleaved with inliers (same lon/lat ranges), so this is not
a regional effect that a per-region offset could absorb.

Conclusion: those 71 sheets are limited by real road-network change since the
1930s, not by this method's parameters. Verifying them needs a different kind
of control (manually picked control points, or a feature class more stable
than roads), not a better road filter.
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import coastfit  # noqa: E402
import grid  # noqa: E402
import roadmask  # noqa: E402
from fit_roads import MIN_DIVERSITY, MIN_ROAD_PX, MAX_RESID, SEARCH  # noqa: E402

TIGHT = {'trunk', 'primary', 'trunk_link', 'primary_link'}


def main():
    segs = coastfit.load_osm(os.path.join(HERE, 'osm_roads.json'), highway_classes=TIGHT)
    print('tight OSM road network: %d ways' % len(segs))

    M0 = coastfit.M_PER_DEG
    prev = {r[0]: r for r in np.load(os.path.join(HERE, 'road_fits.npy'), allow_pickle=True)}
    # Target the sheets that DID fit but landed far from the consensus shift -
    # those are the ones the "modern road density confused it" hypothesis is
    # about.  Sheets with no fit at all have too little road ink for any
    # filter, and a tighter filter only gives them less to match.
    centre = np.array([200.4 / M0, -66.8 / M0])
    retry = [sid for sid, r in prev.items()
             if np.hypot(r[1] - centre[0], r[2] - centre[1]) * M0 >= 150]
    print('%d sheets fitted but scattered (>150 m from consensus) - retrying those'
          % len(retry))

    rows, rejected = [], {}
    for sid in retry:
        rm = roadmask.road_mask(os.path.join(grid.CROP_DIR, sid + '.jpg'))
        if rm.sum() < MIN_ROAD_PX:
            rejected['too little road'] = rejected.get('too little road', 0) + 1
            continue
        div = coastfit.orientation_diversity(rm)
        if div < MIN_DIVERSITY:
            rejected['too straight'] = rejected.get('too straight', 0) + 1
            continue
        g = grid.sheet_geometry(sid)
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
        rows.append((sid, dlon, dlat, resid, n, div))
        print('%-14s dlon=%+7.0f m  dlat=%+7.0f m  resid=%5.0f m  div=%.2f  road_px=%d'
              % (sid, dlon * coastfit.M_PER_DEG, dlat * coastfit.M_PER_DEG, resid, div, rm.sum()),
              flush=True)

    print('\nrejected: %s' % ', '.join('%s x%d' % kv for kv in sorted(rejected.items())))
    if not rows:
        print('no new fits')
        return

    M = coastfit.M_PER_DEG
    a = np.array([[r[1], r[2], r[3]] for r in rows])
    d = np.hypot(a[:, 0] - centre[0], a[:, 1] - centre[1]) * M
    inl = d < 150
    print('\n%d new fits; %d (%.0f%%) agree with the existing +200.4/-66.8 m consensus (<150 m away)'
          % (len(rows), inl.sum(), 100 * inl.mean() if len(rows) else 0))
    if inl.sum():
        print('median residual of the newly-agreeing sheets: %.0f m' % np.median(a[inl, 2]))
    np.save(os.path.join(HERE, 'road_fits_tight.npy'), np.array(rows, dtype=object), allow_pickle=True)


if __name__ == '__main__':
    main()
