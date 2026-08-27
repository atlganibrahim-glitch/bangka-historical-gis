# -*- coding: utf-8 -*-
"""Turn pixel coordinates measured on a sheet into WGS 84 lon/lat.

This is the piece a detection pipeline needs after inference: the model reports
boxes in pixels, and this maps them onto the ground using the v3.1 geometry.

Two things commonly go wrong and are handled explicitly here:

* **Which crop the pixels were measured on.**  The v2 crops and the 2026
  neatline crops are trimmed differently - by a median of 14 px and up to 70 px
  (roughly 60 m, worst case 320 m).  Coordinates measured on a v2 crop must be
  shifted before they can be read against the new geometry; pass
  ``crop='old'`` and that is done for you, from the per-sheet table measured in
  crop_shift.py.
* **Sheets are not all one cell.**  Composites and the two irregular sheets
  span more than 5', so a fixed degrees-per-pixel constant is wrong for them.
  Everything here goes through the per-sheet geometry instead.

Typical use::

    import sheet_to_wgs84 as geo
    lon, lat = geo.pixel_to_lonlat('34-XXV-e', x=1200, y=850)
    geo.detections_to_geojson('patch_detections.csv', 'detections.geojson',
                              crop='old')
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import grid  # noqa: E402

_shift = None
_idx2sheet = None
_geom_cache = {}


def crop_shifts():
    """sheet_id -> (dx, dy): add these to a v2-crop pixel coordinate."""
    global _shift
    if _shift is None:
        _shift = {}
        path = os.path.join(HERE, 'old_to_new_crop_shift.csv')
        with open(path, encoding='utf-8') as fh:
            for r in csv.DictReader(fh):
                _shift[r['sheet_id']] = (float(r['dx_px']), float(r['dy_px']))
    return _shift


def index_to_sheet():
    """image_idx (0-175, as used in the v2 metadata) -> sheet_id."""
    global _idx2sheet
    if _idx2sheet is None:
        _idx2sheet = {}
        with open(os.path.join(ROOT, 'bangka_dataset_v2.csv'), encoding='utf-8') as fh:
            for r in csv.DictReader(fh):
                _idx2sheet[int(r['image_idx'])] = r['sheet_id']
    return _idx2sheet


def geometry(sheet_id):
    if sheet_id not in _geom_cache:
        _geom_cache[sheet_id] = grid.sheet_geometry(sheet_id)
    return _geom_cache[sheet_id]


def pixel_to_lonlat(sheet_id, x, y, crop='new'):
    """Pixel (x, y) on a sheet crop -> (lon, lat) in EPSG:4326.

    crop='new' for the 2026 neatline crops, crop='old' for the v2 crops.
    """
    if crop == 'old':
        dx, dy = crop_shifts()[sheet_id]
        x, y = x + dx, y + dy
    elif crop != 'new':
        raise ValueError("crop must be 'new' or 'old'")
    g = geometry(sheet_id)
    return g['west'] + x * g['xscale'], g['north'] - y * g['yscale']


def box_to_lonlat(sheet_id, x, y, w, h, crop='new'):
    """Detection box -> (centre_lon, centre_lat, west, north, east, south)."""
    cx, cy = pixel_to_lonlat(sheet_id, x + w / 2.0, y + h / 2.0, crop)
    west, north = pixel_to_lonlat(sheet_id, x, y, crop)
    east, south = pixel_to_lonlat(sheet_id, x + w, y + h, crop)
    return cx, cy, west, north, east, south


def detections_to_geojson(detections_csv, out_geojson, crop='new',
                          patch_offsets=None, as_boxes=False):
    """Convert a YOLO detection table to GeoJSON ready for QGIS.

    Expects the columns written by the inference notebook: image_idx, x, y,
    w, h, conf, class_name (and patch_filename).

    Boxes are in *patch* pixels, so patch_offsets must map patch_filename ->
    (x0, y0), the patch's origin within its sheet.  Without it the boxes are
    assumed to already be in sheet pixels.
    """
    idx2sheet = index_to_sheet()
    feats, skipped = [], 0
    with open(detections_csv, encoding='utf-8') as fh:
        for r in csv.DictReader(fh):
            sheet_id = idx2sheet.get(int(r['image_idx']))
            if sheet_id is None:
                skipped += 1
                continue
            x, y = float(r['x']), float(r['y'])
            w, h = float(r['w']), float(r['h'])
            if patch_offsets:
                off = patch_offsets.get(r.get('patch_filename'))
                if off is None:
                    skipped += 1
                    continue
                x, y = x + off[0], y + off[1]
            cx, cy, west, north, east, south = box_to_lonlat(sheet_id, x, y, w, h, crop)
            geom = (dict(type='Polygon', coordinates=[[[west, north], [east, north],
                                                       [east, south], [west, south],
                                                       [west, north]]])
                    if as_boxes else dict(type='Point', coordinates=[cx, cy]))
            props = dict(sheet_id=sheet_id, image_idx=int(r['image_idx']),
                         class_name=r.get('class_name'), conf=float(r.get('conf', 0)))
            feats.append(dict(type='Feature', geometry=geom, properties=props))
    with open(out_geojson, 'w', encoding='utf-8') as fh:
        json.dump(dict(type='FeatureCollection', features=feats), fh)
    return len(feats), skipped


if __name__ == '__main__':
    # self-check: a sheet corner must land on its own recorded bounds
    sid = '34-XXV-e'
    g = geometry(sid)
    lon, lat = pixel_to_lonlat(sid, 0, 0)
    print('%s top-left  -> %.6f, %.6f  (bounds %.6f, %.6f)'
          % (sid, lon, lat, g['west'], g['north']))
    lon, lat = pixel_to_lonlat(sid, g['w_px'], g['h_px'])
    print('%s bot-right -> %.6f, %.6f  (bounds %.6f, %.6f)'
          % (sid, lon, lat, g['east'], g['south']))
    dx, dy = crop_shifts()[sid]
    print('old-crop shift for %s: dx=%+.1f dy=%+.1f px' % (sid, dx, dy))
    print('image_idx 0 -> %s' % index_to_sheet()[0])
