# -*- coding: utf-8 -*-
"""Write the 176 georeferenced sheets (v3).

Inputs are the neatline-accurate crops; geometry comes from grid.py.  Output
is tiled, JPEG-compressed GeoTIFF with overviews - the source scans are JPEG
already, so this costs nothing in quality and keeps the archive near 0.7 GB
instead of 4.5 GB while making the sheets usable in QGIS at island scale.
"""
import os
import sys

import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling
from rasterio.transform import from_bounds

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import grid  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
OUT = os.path.join(ROOT, 'GEOREF_V3_1')


def write_sheet(sid):
    src = os.path.join(grid.CROP_DIR, sid + '.jpg')
    g = grid.sheet_geometry(sid)
    a = np.asarray(Image.open(src).convert('RGB'))
    h, w = a.shape[:2]
    transform = from_bounds(g['west'], g['south'], g['east'], g['north'], w, h)
    kind = 'composite' if g['kind'] == 'composite' else 'single'
    dst = os.path.join(OUT, kind, sid + '.tif')
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    profile = dict(driver='GTiff', height=h, width=w, count=3, dtype='uint8',
                   crs='EPSG:4326', transform=transform, tiled=True,
                   blockxsize=512, blockysize=512, compress='JPEG',
                   jpeg_quality=92, photometric='YCbCr', interleave='pixel',
                   BIGTIFF='IF_SAFER')
    with rasterio.open(dst, 'w', **profile) as ds:
        for b in range(3):
            ds.write(a[:, :, b], b + 1)
        # Mask off the paper outside the printed neatline.  The pixels stay
        # where they belong geographically, but GDAL and QGIS will not paint
        # them, so neighbouring sheets mosaic without double coverage.
        fl, fr, ft, fb = g['frame_px']
        mask = np.zeros((h, w), np.uint8)
        mask[int(round(ft)):int(round(fb)), int(round(fl)):int(round(fr))] = 255
        ds.write_mask(mask)
        ds.update_tags(SHEET_ID=sid, SHEET_KIND=g['kind'], ANCHOR=g['anchor'],
                       CELLS=';'.join('%d,%d' % c for c in g['cells']),
                       FRAME_PX='%.1f,%.1f,%.1f,%.1f' % g['frame_px'],
                       SPAN_ARCMIN='%.4f,%.4f' % (g['span_lon_arcmin'], g['span_lat_arcmin']),
                       VERSION='v3.1 (road-network offset applied)',
                       SOURCE='Topografische Dienst Nederlandsch-Indie, '
                              'Res. Bangka en Onderhoorigheden 1:25000, 1930-1936',
                       HOLDING='Leiden University Libraries, KK 083-04-01/085-04-10')
        ds.build_overviews([2, 4, 8, 16, 32], Resampling.average)
    return g, dst


def main():
    ids = sorted(os.path.splitext(f)[0] for f in os.listdir(grid.CROP_DIR)
                 if f.endswith('.jpg'))
    for i, sid in enumerate(ids, 1):
        g, dst = write_sheet(sid)
        print('[%3d/%d] %-14s %-9s anchor=%-6s %.5f..%.5f E  %.5f..%.5f N'
              % (i, len(ids), sid, g['kind'], g['anchor'],
                 g['west'], g['east'], g['south'], g['north']), flush=True)


if __name__ == '__main__':
    main()
