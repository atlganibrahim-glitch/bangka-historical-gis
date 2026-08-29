# -*- coding: utf-8 -*-
"""Clean a digitised control-point layer in place.

Hand digitising produces three predictable defects, all silent:

  * empty features - a row created but never given a geometry
  * exact duplicates - the same line committed more than once, usually from
    re-pasting or a double commit. These are worse than useless: they look
    like independent measurements and pull a sheet's mean towards whichever
    point got repeated.
  * mistyped sheet_id - '35-XXVI-I' (capital i) for '35-XXVI-l' (lowercase L)
    is invisible by eye and creates a phantom sheet.

Rewrites the file with those removed/corrected and prints what it changed.
A .bak copy is kept next to it.
"""
import os
import shutil
import struct
import sys

import numpy as np
import pyogrio.raw as raw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import grid  # noqa: E402

DEFAULT = os.path.join(ROOT, 'qgis', 'control_points.gpkg')
LAYER = 'control_points'


def line_ends(wkb):
    if wkb is None:
        return None
    if int.from_bytes(wkb[1:5], 'little') % 1000 != 2:
        return None
    n = int.from_bytes(wkb[5:9], 'little')
    if n < 2:
        return None
    x0, y0 = struct.unpack('<dd', wkb[9:25])
    off = 9 + (n - 1) * 16
    x1, y1 = struct.unpack('<dd', wkb[off:off + 16])
    return x0, y0, x1, y1


def sheet_containing(lon, lat, cache=[]):
    if not cache:
        for sid in sorted(os.path.splitext(f)[0] for f in os.listdir(grid.CROP_DIR)
                          if f.endswith('.jpg')):
            g = grid.sheet_geometry(sid)
            cache.append((sid, g['west'], g['east'], g['south'], g['north']))
    for sid, w, e, s, n in cache:
        if w <= lon <= e and s <= lat <= n:
            return sid
    return None


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    meta, fids, geom, field_data = raw.read(path)
    fields = list(meta['fields'])
    n_in = len(geom)

    valid_ids = {os.path.splitext(f)[0] for f in os.listdir(grid.CROP_DIR) if f.endswith('.jpg')}
    keep, seen = [], {}
    dropped_empty = dropped_dup = relabelled = 0

    for i in range(n_in):
        ends = line_ends(geom[i])
        if ends is None:
            dropped_empty += 1
            continue
        key = tuple(round(v, 7) for v in ends)
        if key in seen:
            dropped_dup += 1
            continue
        seen[key] = i

        sid = str(field_data[fields.index('sheet_id')][i] or '').strip()
        if sid not in valid_ids:
            real = sheet_containing(ends[0], ends[1])
            if real:
                field_data[fields.index('sheet_id')][i] = real
                relabelled += 1
                sid = real
        keep.append(i)

    idx = np.array(keep, dtype=int)
    shutil.copy2(path, path + '.bak')
    raw.write(path, geom[idx], [fd[idx] for fd in field_data], fields,
              layer=LAYER, driver='GPKG', geometry_type='LineString',
              crs=meta['crs'])

    print('%s' % path)
    print('  in  : %d features' % n_in)
    print('  drop: %d empty, %d exact duplicates' % (dropped_empty, dropped_dup))
    print('  fix : %d mistyped sheet_id' % relabelled)
    print('  out : %d features  (backup at %s.bak)' % (len(keep), os.path.basename(path)))


if __name__ == '__main__':
    main()
