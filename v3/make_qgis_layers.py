# -*- coding: utf-8 -*-
"""Vector helpers for checking the rebuild in QGIS.

  sheet_index_v3.geojson  - the printed neatline of every sheet, attributed
  graticule_5min.geojson  - the 5' cell grid the neatlines should land on

Both follow whatever grid.py is currently calibrated to (v3.1 by default), so
they stay consistent with the rasters they are meant to check.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, 'qgis')
sys.path.insert(0, HERE)
import grid  # noqa: E402


def ring(w, n, e, s):
    return [[[w, n], [e, n], [e, s], [w, s], [w, n]]]


def main():
    os.makedirs(OUT, exist_ok=True)
    ids = sorted(os.path.splitext(f)[0] for f in os.listdir(grid.CROP_DIR)
                 if f.endswith('.jpg'))

    feats = []
    cells_used = set()
    for sid in ids:
        g = grid.sheet_geometry(sid)
        fl, fr, ft, fb = g['frame_px']
        # the neatline itself, dropping the scan margin outside it
        w = g['west'] + fl * g['xscale']
        e = g['west'] + fr * g['xscale']
        n = g['north'] - ft * g['yscale']
        s = g['north'] - fb * g['yscale']
        raw = grid.frames()[sid]
        feats.append(dict(
            type='Feature', geometry=dict(type='Polygon', coordinates=ring(w, n, e, s)),
            properties=dict(
                sheet_id=sid, kind=g['kind'], anchor=g['anchor'],
                span_lon_arcmin=round(g['span_lon_arcmin'], 4),
                span_lat_arcmin=round(g['span_lat_arcmin'], 4),
                beyond_cell_m=round((max(g['span_lon_arcmin'], g['span_lat_arcmin']) - 5.0) * 1852),
                frame_measured={(True, True): 'both', (True, False): 'width',
                                (False, True): 'height', (False, False): 'none'}[
                    (raw['w'] is not None, raw['h'] is not None)],
                n_cells=len(g['cells']))))
        cells_used.update(g['cells'])

    with open(os.path.join(OUT, 'sheet_index_v3.geojson'), 'w', encoding='utf-8') as fh:
        json.dump(dict(type='FeatureCollection', features=feats), fh)

    cols = [c for c, r in cells_used]
    rows = [r for c, r in cells_used]
    gfeats = []
    for c in range(min(cols) - 1, max(cols) + 2):
        for r in range(min(rows) - 1, max(rows) + 2):
            w, n, e, s = grid.cell_bounds(c, r)
            gfeats.append(dict(
                type='Feature', geometry=dict(type='Polygon', coordinates=ring(w, n, e, s)),
                properties=dict(cell_col=c, cell_row=r,
                                sheet_id=grid.sheet_id_for(c, r),
                                has_sheet=(c, r) in cells_used)))
    with open(os.path.join(OUT, 'graticule_5min.geojson'), 'w', encoding='utf-8') as fh:
        json.dump(dict(type='FeatureCollection', features=gfeats), fh)

    print('sheet_index_v3.geojson : %d sheets' % len(feats))
    print('graticule_5min.geojson : %d cells (%d carry a sheet)'
          % (len(gfeats), len(cells_used)))


if __name__ == '__main__':
    main()
