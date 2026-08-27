# -*- coding: utf-8 -*-
"""Fetch an OpenStreetMap raster basemap for a bounding box.

Used only to build the figures in v3/make_figures.py.  Tiles are cached under
v3/tilecache/ so re-running the figure script does not re-download them; the
whole island needs a few dozen tiles at zoom 10, which is well within OSM's
tile usage policy for occasional use.  © OpenStreetMap contributors, ODbL.
"""
import io
import math
import os
import time
import urllib.request

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, 'tilecache')
UA = ('bangka-historical-gis/1.0 (figure generation; '
      'github.com/atlganibrahim-glitch/bangka-historical-gis)')
TILE = 256


def deg2tile(lon, lat, z):
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    r = math.radians(lat)
    y = (1.0 - math.log(math.tan(r) + 1.0 / math.cos(r)) / math.pi) / 2.0 * n
    return x, y


def tile2deg(x, y, z):
    n = 2 ** z
    lon = x / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * y / n))))
    return lon, lat


def _tile(z, x, y):
    path = os.path.join(CACHE, str(z), str(x), '%d.png' % y)
    if os.path.exists(path):
        return Image.open(path).convert('RGB')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    url = 'https://tile.openstreetmap.org/%d/%d/%d.png' % (z, x, y)
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    data = urllib.request.urlopen(req, timeout=30).read()
    with open(path, 'wb') as fh:
        fh.write(data)
    time.sleep(0.1)          # be polite to the tile servers
    return Image.open(io.BytesIO(data)).convert('RGB')


def basemap(west, east, south, north, z=10):
    """Stitched OSM image plus the exact geographic bounds it covers.

    The returned bounds are the tile-aligned ones, which are slightly larger
    than those asked for; use them, not the request, when placing overlays.
    """
    x0f, y0f = deg2tile(west, north, z)
    x1f, y1f = deg2tile(east, south, z)
    x0, y0, x1, y1 = int(x0f), int(y0f), int(x1f), int(y1f)
    img = Image.new('RGB', ((x1 - x0 + 1) * TILE, (y1 - y0 + 1) * TILE), 'white')
    for tx in range(x0, x1 + 1):
        for ty in range(y0, y1 + 1):
            img.paste(_tile(z, tx, ty), ((tx - x0) * TILE, (ty - y0) * TILE))
    w, n = tile2deg(x0, y0, z)
    e, s = tile2deg(x1 + 1, y1 + 1, z)
    return img, (w, e, s, n)
