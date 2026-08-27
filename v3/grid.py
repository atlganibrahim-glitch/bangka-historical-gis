# -*- coding: utf-8 -*-
"""Bangka sheet-grid geometry (v3).

One model covers every sheet.  Each sheet is placed by its *printed neatline*,
not by the edge of the scan: whichever axis of the frame spans a whole number
of 5' cells fixes the paper scale, and the other axis follows from its measured
pixel length.  That handles regular sheets, the two-cell coastal composites,
and the sheets that were printed short or long of their cell, without
stretching any of them.

A 5' cell is not square on paper: at Bangka's latitude 5' of latitude is
slightly shorter on the ground than 5' of longitude.  The measured frames agree
(median height/width 0.9959 over 115 sheets, MAD 0.0009, against 0.9943
predicted for the ellipsoid), which is what CELL_ASPECT encodes.
"""
import csv
import os

from PIL import Image

Image.MAX_IMAGE_PIXELS = None

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CROP_DIR = os.path.join(ROOT, 'new_crops', 'map')

SUBGRID = {
    'a': (0, 0), 'b': (1, 0), 'c': (2, 0), 'd': (3, 0),
    'e': (0, 1), 'f': (1, 1), 'g': (2, 1), 'h': (3, 1),
    'i': (0, 2), 'k': (1, 2), 'l': (2, 2), 'm': (3, 2),
    'n': (0, 3), 'o': (1, 3), 'p': (2, 3), 'q': (3, 3),
}
INV_SUBGRID = {v: k for k, v in SUBGRID.items()}
ROMAN = {'XXIII': 23, 'XXIV': 24, 'XXV': 25, 'XXVI': 26, 'XXVII': 27, 'XXVIII': 28}
INV_ROMAN = {v: k for k, v in ROMAN.items()}

CELL = 5 / 60.0
CELL_ASPECT = 0.9959          # printed frame height / width for one cell

BASE_LON, BASE_LAT = 105.0, -2.0
LON_OFFSET = 0.140831
LAT_OFFSET = 0.000121

# v3.1 refinement: a small residual shift found by fitting the map's own road
# network (v3/fit_roads.py) against OSM's major-road layer.  Roads move far
# less than the coastline over 90 years, so this is a genuine inland
# calibration check, not coastal change.  60 of 131 usable sheets converged
# independently on the same shift with a tight median residual (30 m) - not
# plausible by chance - so it is applied here rather than left as a footnote.
# Provenance: median of those 60 sheets' fitted (dlon, dlat), 2026-08-27.
ROAD_LON_CORRECTION = 200.4 / 111320.0
ROAD_LAT_CORRECTION = -66.8 / 111320.0

# Sheets whose printed frame is not a whole cell, with the edge that sits on a
# graticule line.  Anchors are decided in fit_irregular.py, never guessed.
IRREGULAR_ANCHOR = {
    '33-XXVI-d': 'top',
    '34-XXV-q': 'top',
}

_frames = None


def frames():
    global _frames
    if _frames is None:
        _frames = {}
        with open(os.path.join(HERE, 'frames.csv'), encoding='utf-8') as fh:
            for r in csv.DictReader(fh):
                num = lambda k: float(r[k]) if r[k] else None
                cw, ch = int(r['crop_w']), int(r['crop_h'])
                _frames[r['sheet_id']] = dict(
                    left=num('frame_left'), right=num('frame_right'),
                    top=num('frame_top'), bottom=num('frame_bottom'),
                    w=num('frame_w'), h=num('frame_h'), crop_w=cw, crop_h=ch)
    return _frames


def cell_index(sheet_id):
    col_s, roman, sub = sheet_id.split('-')
    bc, br = (int(col_s) - 32) * 4, (ROMAN[roman] - 25) * 4
    return [(bc + SUBGRID[ch][0], br + SUBGRID[ch][1]) for ch in sub]


def sheet_id_for(col, row):
    bc, sc = divmod(col, 4)
    br, sr = divmod(row, 4)
    return '%d-%s-%s' % (32 + bc, INV_ROMAN[25 + br], INV_SUBGRID[(sc, sr)])


def cell_bounds(col, row, apply_road_correction=True):
    """Bounds of one 5' graticule cell.

    apply_road_correction=False reproduces the v3.0 grid, which is what
    fit_roads.py needs so its measurement stays independent of its own result.
    """
    w = BASE_LON + LON_OFFSET + col * CELL
    n = BASE_LAT + LAT_OFFSET - row * CELL
    if apply_road_correction:
        w += ROAD_LON_CORRECTION
        n += ROAD_LAT_CORRECTION
    return w, n, w + CELL, n - CELL


def crop_size(sheet_id):
    with Image.open(os.path.join(CROP_DIR, sheet_id + '.jpg')) as im:
        return im.size


def frame_edges(sheet_id):
    """Neatline edge positions in crop pixels, falling back to the crop edge
    wherever a frame line was too faint to measure."""
    f = frames()[sheet_id]
    cw, ch = f['crop_w'], f['crop_h']
    return (0.0 if f['left'] is None else f['left'],
            float(cw) if f['right'] is None else f['right'],
            0.0 if f['top'] is None else f['top'],
            float(ch) if f['bottom'] is None else f['bottom'], cw, ch)


def _frame_px(sheet_id):
    l, r, t, b, cw, ch = frame_edges(sheet_id)
    return (r - l), (b - t), cw, ch


def sheet_geometry(sheet_id, anchor_override=None, apply_road_correction=True):
    cells = cell_index(sheet_id)
    fw, fh, cw, ch = _frame_px(sheet_id)
    vertical_pair = len(cells) == 2 and cells[0][0] == cells[1][0]
    horizontal_pair = len(cells) == 2 and not vertical_pair

    # Which axis spans a known whole number of cells?  That axis sets the scale.
    n_lon_cells = 2 if horizontal_pair else 1
    n_lat_cells = 2 if vertical_pair else 1
    if horizontal_pair:
        deg_per_px = CELL / (fh / CELL_ASPECT)          # height is one cell
    else:
        deg_per_px = CELL / fw                          # width is one cell

    span_lon = fw * deg_per_px
    span_lat = fh * deg_per_px / CELL_ASPECT

    land = cells[0]
    lw, ln, le, ls = cell_bounds(*land, apply_road_correction=apply_road_correction)

    if len(cells) == 1:
        # Only call a sheet irregular when both frame edges were actually
        # measured; a half-measured frame is not evidence of anything.
        raw = frames()[sheet_id]
        measured = raw['w'] is not None and raw['h'] is not None
        exact = not measured or (abs(span_lon / CELL - 1) < 0.02
                                 and abs(span_lat / CELL - 1) < 0.02)
        if exact:
            anchor = 'cell'
            west, north, east, south = lw, ln, le, ls
        else:
            anchor = anchor_override or IRREGULAR_ANCHOR.get(sheet_id, 'top')
            west, east = lw, lw + span_lon
            if anchor == 'top':
                north, south = ln, ln - span_lat
            else:
                south, north = ls, ls + span_lat
    elif vertical_pair:
        # The sheet's frame touches one of the two outer edges of the enclosing
        # 5' x 10' rectangle - not an edge of the land cell, which may be the
        # lower of the pair.  The rule is that it touches the land cell's own
        # outer edge, with the unprinted sea falling off the companion end.
        upper = min(cells, key=lambda c: c[1])
        lower = max(cells, key=lambda c: c[1])
        rect_north = cell_bounds(*upper, apply_road_correction=apply_road_correction)[1]
        rect_south = cell_bounds(*lower, apply_road_correction=apply_road_correction)[3]
        anchor = anchor_override or ('top' if cells[0] == upper else 'bottom')
        west, east = lw, lw + span_lon
        if anchor == 'top':
            north, south = rect_north, rect_north - span_lat
        else:
            south, north = rect_south, rect_south + span_lat
    else:
        left_c = min(cells, key=lambda c: c[0])
        right_c = max(cells, key=lambda c: c[0])
        rect_west = cell_bounds(*left_c, apply_road_correction=apply_road_correction)[0]
        rect_east = cell_bounds(*right_c, apply_road_correction=apply_road_correction)[2]
        anchor = anchor_override or ('left' if cells[0] == left_c else 'right')
        north, south = ln, ln - span_lat
        if anchor == 'left':
            west, east = rect_west, rect_west + span_lon
        else:
            east, west = rect_east, rect_east - span_lon

    # Everything above positions the *neatline*.  The crop keeps a little paper
    # on each side of it, and those margins are not symmetric, so extend each
    # edge by its own measured margin instead of splitting the difference.
    fl, fr, ft, fb, _, _ = frame_edges(sheet_id)
    west -= fl * deg_per_px
    east += (cw - fr) * deg_per_px
    north += ft * deg_per_px / CELL_ASPECT
    south -= (ch - fb) * deg_per_px / CELL_ASPECT

    return dict(sheet_id=sheet_id,
                kind='composite' if len(cells) == 2 else
                     ('irregular' if anchor not in ('cell',) else 'single'),
                anchor=anchor, west=west, north=north, east=east, south=south,
                w_px=cw, h_px=ch, frame_w=fw, frame_h=fh,
                frame_px=(fl, fr, ft, fb),
                xscale=(east - west) / cw, yscale=(north - south) / ch,
                span_lon_arcmin=(east - west) * 60, span_lat_arcmin=(north - south) * 60,
                n_lon_cells=n_lon_cells, n_lat_cells=n_lat_cells, cells=cells)
