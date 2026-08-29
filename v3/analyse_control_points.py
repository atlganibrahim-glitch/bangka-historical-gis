# -*- coding: utf-8 -*-
"""Measure per-sheet positional error from manually digitised control points.

This is the check the automated tests cannot do. fit_roads.py and
fit_singles.py compare a sheet's *drawn* content against a modern layer, and
both are limited by what has genuinely changed since the 1930s - and neither
samples the middle of a sheet. Hand-picked control points test the sheet
interior directly, and they work on the ~60% of sheets no automated test
could verify at all.

Input: a line layer, GeoJSON or GeoPackage (see
qgis/control_points_TEMPLATE.geojson). GeoPackage is recommended for actually
digitising in QGIS - live-editing a GeoJSON in place is failure-prone there
("Could not commit changes"); draw into a .gpkg and this script reads it
directly, no export step needed. One feature per control point, drawn as a
two-vertex line:

    start vertex -> where the feature sits on the georeferenced sheet
    end   vertex -> where that same feature actually is (modern reference)

so the line itself is the error vector, and the layer doubles as a visual
displacement field in QGIS.

Reports, per sheet: the mean shift (a correctable systematic offset) and the
scatter that remains after removing it (which is what actually limits the
sheet, and includes any within-sheet distortion).
"""
import json
import os
import struct
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import grid  # noqa: E402

M = 111320.0
DEFAULT = os.path.join(ROOT, 'qgis', 'control_points.gpkg')
MIN_PER_SHEET = 3


def _features_from_geojson(path):
    with open(path, encoding='utf-8') as fh:
        gj = json.load(fh)
    for f in gj.get('features', []):
        yield f.get('properties') or {}, f.get('geometry') or {}


def _wkb_linestring_coords(wkb):
    """(x0, y0), (x1, y1) from a WKB LineString/LineStringZ, or None.

    Hand-rolled so this script needs only pyogrio, not shapely - pyogrio
    hands back raw WKB bytes (it depends on GDAL, not on a full GEOS stack).
    """
    if wkb is None:
        return None
    order = '<' if wkb[0] == 1 else '>'
    gtype = int.from_bytes(wkb[1:5], 'little' if order == '<' else 'big')
    has_z = (gtype % 1000) // 100 == 1 or gtype > 1000  # 1002/2002-ish Z flags
    base = gtype % 1000
    if base != 2:          # 2 = LineString; anything else (Point, Multi*) is unusable here
        return None
    n = int.from_bytes(wkb[5:9], 'little' if order == '<' else 'big')
    if n < 2:
        return None
    dims = 3 if has_z else 2
    fmt = order + 'd' * dims
    size = 8 * dims
    off = 9
    first = struct.unpack(fmt, wkb[off:off + size])[:2]
    off += (n - 1) * size
    last = struct.unpack(fmt, wkb[off:off + size])[:2]
    return first, last


def _read_ogr_raw(path):
    """Read geometry (as WKB) + attributes from any OGR source, no geopandas."""
    import pyogrio.raw
    meta, fids, geometry, field_data = pyogrio.raw.read(path)
    fields = list(meta['fields'])
    n = len(geometry) if geometry is not None else 0
    for i in range(n):
        props = {name: field_data[j][i] for j, name in enumerate(fields)}
        yield props, geometry[i]


def load(path):
    pts = defaultdict(list)
    skipped = 0
    ext = os.path.splitext(path)[1].lower()

    if ext in ('.geojson', '.json'):
        for p, g in _features_from_geojson(path):
            sid = str(p.get('sheet_id') or '').strip()
            coords = g.get('coordinates', []) if g.get('type') == 'LineString' else []
            if len(coords) < 2 or not sid or sid.startswith('EXAMPLE'):
                skipped += 1
                continue
            (x0, y0), (x1, y1) = coords[0][:2], coords[-1][:2]
            _add(pts, sid, x0, y0, x1, y1)
    else:
        # GeoPackage / Shapefile / anything else OGR understands.
        for p, wkb in _read_ogr_raw(path):
            sid = str(p.get('sheet_id') or '').strip()
            ends = _wkb_linestring_coords(wkb)
            if ends is None or not sid or sid.startswith('EXAMPLE'):
                skipped += 1
                continue
            (x0, y0), (x1, y1) = ends
            _add(pts, sid, x0, y0, x1, y1)
    return pts, skipped


def _add(pts, sid, x0, y0, x1, y1):
    lat = np.radians((y0 + y1) / 2.0)
    pts[sid].append((
        (x1 - x0) * M * np.cos(lat),      # east error, metres
        (y1 - y0) * M,                    # north error, metres
        x0, y0))


def _sheet_containing(lon, lat, _cache=[]):
    """Which sheet actually covers this point (first match), or None."""
    if not _cache:
        for sid in sorted(os.path.splitext(f)[0] for f in os.listdir(grid.CROP_DIR)
                          if f.endswith('.jpg')):
            g = grid.sheet_geometry(sid)
            _cache.append((sid, g['west'], g['east'], g['south'], g['north']))
    for sid, w, e, s, n in _cache:
        if w <= lon <= e and s <= lat <= n:
            return sid
    return None


def validate(pts):
    """Catch mislabelled sheet_ids before they corrupt the per-sheet averages.

    A typo like 35-XXVI-I for 35-XXVI-l (capital i, lowercase L) is invisible
    by eye and would otherwise silently create a phantom sheet, so each point
    is checked against the sheet that geographically contains it.
    """
    valid = {os.path.splitext(f)[0] for f in os.listdir(grid.CROP_DIR) if f.endswith('.jpg')}
    fixes = {}
    for sid in list(pts):
        if sid in valid:
            # labelled with a real sheet: check the points are actually on it
            wrong = [p for p in pts[sid] if _sheet_containing(p[2], p[3]) != sid]
            if wrong:
                print('WARNING  %-14s %d of %d points do not fall inside this sheet'
                      % (sid, len(wrong), len(pts[sid])))
            continue
        # not a real sheet id - try to recover it from the geometry
        guesses = {_sheet_containing(p[2], p[3]) for p in pts[sid]}
        guesses.discard(None)
        if len(guesses) == 1:
            real = guesses.pop()
            print('FIXED    %-14s is not a sheet id; all its points fall inside %s '
                  '- relabelled' % (sid, real))
            fixes[sid] = real
        else:
            print('DROPPED  %-14s is not a sheet id and its points span %s'
                  % (sid, guesses or 'nothing'))
            fixes[sid] = None
    for bad, real in fixes.items():
        moved = pts.pop(bad)
        if real:
            pts[real].extend(moved)
    return pts


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    if not os.path.exists(path):
        raise SystemExit('no control-point file at %s\n'
                         'Copy qgis/control_points_TEMPLATE.geojson to that name '
                         'and digitise into it (see the guide).' % path)
    pts, skipped = load(path)
    if not pts:
        raise SystemExit('no usable control points found (%d features skipped)' % skipped)
    pts = validate(pts)
    print()

    print('%-14s %4s %10s %10s %10s %10s' %
          ('sheet', 'n', 'dE(m)', 'dN(m)', '|shift|', 'scatter'))
    rows = []
    for sid in sorted(pts):
        v = np.array([[a, b] for a, b, *_ in pts[sid]])
        if len(v) < MIN_PER_SHEET:
            print('%-14s %4d   (need >= %d points to separate shift from scatter)'
                  % (sid, len(v), MIN_PER_SHEET))
            continue
        shift = v.mean(axis=0)
        resid = v - shift
        scatter = float(np.sqrt((resid ** 2).sum(axis=1).mean()))   # RMS about the mean
        rows.append((sid, len(v), shift[0], shift[1], float(np.hypot(*shift)), scatter))
        print('%-14s %4d %10.0f %10.0f %10.0f %10.0f'
              % (sid, len(v), shift[0], shift[1], np.hypot(*shift), scatter))

    if not rows:
        return
    a = np.array([[r[2], r[3], r[4], r[5]] for r in rows])
    print('\n%d sheets with enough points (%d features skipped)' % (len(rows), skipped))
    print('systematic shift, median over sheets : dE %+.0f m, dN %+.0f m'
          % (np.median(a[:, 0]), np.median(a[:, 1])))
    print('per-sheet |shift|  : median %.0f m, max %.0f m' % (np.median(a[:, 2]), a[:, 2].max()))
    print('residual scatter   : median %.0f m, max %.0f m' % (np.median(a[:, 3]), a[:, 3].max()))
    print()
    print('How to read this:')
    print('  |shift|  is correctable - it is a constant offset for that sheet.')
    print('  scatter  is not. It is what remains after the best possible shift,')
    print('           so it bounds how well a translation-only correction can do')
    print('           and is where within-sheet distortion would show up.')
    print()
    if np.median(a[:, 3]) < 60:
        print('  Scatter is small: a per-sheet translation would capture most of the error.')
    else:
        print('  Scatter is large: a translation alone will not fix these sheets;')
        print('  the sheets are distorted internally and would need a higher-order fit.')
    np.save(os.path.join(HERE, 'control_point_fits.npy'),
            np.array(rows, dtype=object), allow_pickle=True)


if __name__ == '__main__':
    main()
