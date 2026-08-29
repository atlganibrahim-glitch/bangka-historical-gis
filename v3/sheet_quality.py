# -*- coding: utf-8 -*-
"""Per-sheet quality table, so downstream results can be weighted or filtered.

Positional accuracy is not uniform across the 176 sheets, and a detection
pipeline has no way to know that from the rasters alone.  This collects, per
sheet, what is actually known about how well it is placed and how much of it is
usable land, so analyses can weight sheets, drop weak ones, or normalise counts
by area instead of treating every sheet as equivalent.
"""
import csv
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import coastfit  # noqa: E402
import grid  # noqa: E402

M = coastfit.M_PER_DEG
CACHE = os.path.join(HERE, 'masks')

COLS = ['sheet_id', 'image_idx', 'kind', 'anchor', 'anchor_evidence',
        'frame_measured', 'positional_grade', 'road_fit_resid_m',
        'road_fit_shift_m', 'old_crop_shift_px',
        'land_km2', 'sea_fraction', 'sheet_km2', 'notes']

# from fit_irregular.py; every other sheet is a plain cell needing no decision
ANCHOR_EVIDENCE = {
    '31-XXV-dh': 'shoreline', '32-XXIV-ni': 'shoreline', '33-XXV-ae': 'shoreline',
    '33-XXVI-d': 'shoreline', '34-XXIII-ie': 'roads', '34-XXIV-cd': 'shoreline',
    '34-XXVI-on': 'shoreline', '34-XXVII-g': 'shoreline', '35-XXVII-ko': 'shoreline',
    '36-XXVI-ie': 'roads', '36-XXVII-fg': 'roads', '36-XXVIII-bf': 'shoreline',
    '36-XXVIII-dh': 'roads', '37-XXVI-in': 'shoreline',
}

# margin (m) by which the winning anchor beat the losing one, from
# fit_irregular.py (shoreline) / fit_irregular_roads.py (roads) - this
# answers "which edge is right", a different and easier question than the
# absolute-position road_fit_* columns below.
ANCHOR_MARGIN = {
    '31-XXV-dh': 389, '32-XXIV-ni': 1284, '33-XXV-ae': 2037, '33-XXVI-d': 734,
    '34-XXIII-ie': 2778, '34-XXIV-cd': 4470, '34-XXVI-on': 886, '34-XXVII-g': 452,
    '35-XXVII-ko': 1864, '36-XXVI-ie': 3671, '36-XXVII-fg': 1840,
    '36-XXVIII-bf': 2054, '36-XXVIII-dh': 4493, '37-XXVI-in': 1316,
}


def load_sea(sid):
    p = os.path.join(CACHE, sid + '.npz')
    if not os.path.exists(p):
        return None
    z = np.load(p)
    shape = tuple(z['shape'])
    return np.unpackbits(z['sea'])[:shape[0] * shape[1]].reshape(shape).astype(bool)


def main():
    idx = {}
    with open(grid.v2_metadata_path(), encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            idx[r['sheet_id']] = int(r['image_idx'])

    shifts = {}
    with open(os.path.join(HERE, 'old_to_new_crop_shift.csv'), encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            shifts[r['sheet_id']] = float(np.hypot(float(r['dx_px']), float(r['dy_px'])))

    road = {}
    p = os.path.join(HERE, 'road_fits.npy')
    if os.path.exists(p):
        for r in np.load(p, allow_pickle=True):
            road[r[0]] = (float(r[1]) * M, float(r[2]) * M, float(r[3]))
    # consensus shift the v3.1 correction was built from
    if road:
        a = np.array([[v[0], v[1]] for v in road.values()])
        centre = np.median(a, axis=0)

    ids = sorted(os.path.splitext(f)[0] for f in os.listdir(grid.CROP_DIR)
                 if f.endswith('.jpg'))
    rows = []
    for sid in ids:
        g = grid.sheet_geometry(sid)
        raw = grid.frames()[sid]
        fm = {(True, True): 'both', (True, False): 'width',
              (False, True): 'height', (False, False): 'none'}[
            (raw['w'] is not None, raw['h'] is not None)]

        sea = load_sea(sid)
        lat_mid = (g['north'] + g['south']) / 2.0
        km2 = ((g['east'] - g['west']) * M * np.cos(np.radians(lat_mid))
               * (g['north'] - g['south']) * M) / 1e6
        sea_frac = float(sea.mean()) if sea is not None else None

        notes = []
        grade = 'A'
        if sid in road:
            dlon, dlat, resid = road[sid]
            d = float(np.hypot(dlon - centre[0], dlat - centre[1]))
            if d < 150:
                grade = 'A'
                notes.append('road fit agrees with the global calibration')
            else:
                grade = 'B'
                notes.append('road fit scattered; modern road density likely confused it')
            rr, rs = round(resid), round(d)
        else:
            grade = 'B'
            rr = rs = None
            notes.append('not enough road ink to check independently')

        if fm != 'both':
            grade = 'C' if grade == 'B' else 'B'
            notes.append('frame only partly measurable (%s)' % fm)
        if g['kind'] != 'single':
            notes.append('%s sheet, extends %.0f m beyond its cell'
                         % (g['kind'], (max(g['span_lon_arcmin'], g['span_lat_arcmin']) - 5) * 1852))
        ev = ANCHOR_EVIDENCE.get(sid)
        if ev == 'rule':
            grade = 'C' if grade in ('B', 'C') else 'B'
            notes.append('anchor rests on the sub-code rule, not measured')
        elif ev is not None:
            notes.append('anchor confirmed by %s (%.0f m margin over the other edge)'
                         % (ev, ANCHOR_MARGIN.get(sid, float('nan'))))

        rows.append(dict(
            sheet_id=sid, image_idx=idx.get(sid, ''), kind=g['kind'],
            anchor=g['anchor'], anchor_evidence=ANCHOR_EVIDENCE.get(sid, 'n/a (full cell)'),
            frame_measured=fm, positional_grade=grade,
            road_fit_resid_m=rr, road_fit_shift_m=rs,
            old_crop_shift_px=round(shifts.get(sid, float('nan')), 1),
            land_km2=round(km2 * (1 - sea_frac), 2) if sea_frac is not None else '',
            sea_fraction=round(sea_frac, 3) if sea_frac is not None else '',
            sheet_km2=round(km2, 2), notes='; '.join(notes)))

    out = os.path.join(ROOT, 'bangka_sheet_quality.csv')
    with open(out, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, COLS)
        w.writeheader()
        w.writerows(rows)

    from collections import Counter
    c = Counter(r['positional_grade'] for r in rows)
    print('wrote', out)
    print('grades:', dict(sorted(c.items())))
    land = [r['land_km2'] for r in rows if r['land_km2'] != '']
    print('total land area covered: %.0f km2 over %d sheets' % (sum(land), len(land)))
    print('\ngrade meaning:')
    print('  A  road-network check agrees with the global calibration')
    print('  B  no independent check possible, or frame partly measured')
    print('  C  more than one caveat - inspect before relying on it')


if __name__ == '__main__':
    main()
