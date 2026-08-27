# -*- coding: utf-8 -*-
"""Regenerate every figure used in the README and V3_REPORT.

Figures are generated from the data rather than screenshotted, so they stay
consistent with whatever the pipeline currently produces.  Run after
georeference.py.
"""
import glob
import os
import sys

import numpy as np
import rasterio
from PIL import Image, ImageDraw, ImageFont
from rasterio.enums import Resampling

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import basemap  # noqa: E402
import grid  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
OUT = os.path.join(ROOT, 'figures')
RASTERS = os.path.join(ROOT, 'GEOREF_V3_1', '*', '*.tif')

_FONT_CANDIDATES = ['C:/Windows/Fonts/segoeui.ttf', 'C:/Windows/Fonts/arial.ttf',
                    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']


def font(size):
    for p in _FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                pass
    return ImageFont.load_default()


def caption(draw, xy, text, fill=(30, 30, 30), size=15, bg=(255, 255, 255)):
    """Text with a solid pad behind it, so it stays readable over a map."""
    f = font(size)
    x, y = xy
    box = draw.textbbox((x, y), text, font=f)
    draw.rectangle([box[0] - 5, box[1] - 3, box[2] + 5, box[3] + 3], fill=bg)
    draw.text((x, y), text, font=f, fill=fill)


def _render_sheets(pattern, west, east, south, north, ppd, use_mask=True):
    """Paint the georeferenced sheets into a lon/lat-aligned RGBA canvas."""
    W, H = int(round((east - west) * ppd)), int(round((north - south) * ppd))
    canvas = np.zeros((H, W, 4), np.uint8)
    for f in sorted(glob.glob(pattern)):
        with rasterio.open(f) as ds:
            b = ds.bounds
            if b.right < west or b.left > east or b.top < south or b.bottom > north:
                continue
            tw = max(int(round((b.right - b.left) * ppd)), 1)
            th = max(int(round((b.top - b.bottom) * ppd)), 1)
            a = np.transpose(ds.read(out_shape=(3, th, tw),
                                     resampling=Resampling.average), (1, 2, 0))
            m = (ds.read_masks(1, out_shape=(th, tw), resampling=Resampling.nearest) > 127
                 if use_mask else np.ones((th, tw), bool))
        x0 = int(round((b.left - west) * ppd))
        y0 = int(round((north - b.top) * ppd))
        sx0, sy0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x0 + tw, W), min(y0 + th, H)
        if sx0 >= x1 or sy0 >= y1:
            continue
        sub = a[sy0 - y0:y1 - y0, sx0 - x0:x1 - x0]
        sm = m[sy0 - y0:y1 - y0, sx0 - x0:x1 - x0]
        win = canvas[sy0:y1, sx0:x1]
        win[..., :3][sm] = sub[sm]
        win[..., 3][sm] = 255
        canvas[sy0:y1, sx0:x1] = win
    return Image.fromarray(canvas, 'RGBA')


def fig_osm_overlay(path, z=10, opacity=0.75):
    """The sheets over modern OSM - does the archive land on the real island?

    Not called by main(): figures/osm_overlay.png is a hand-framed QGIS export
    (it carries a .pgw, so it stays georeferenced) and is tracked in git rather
    than regenerated, so this must not overwrite it.  Kept because it is the
    reproducible way to rebuild that view if the QGIS export is ever lost -
    call it explicitly with a different output path.
    """
    bm, (w, e, s, n) = basemap.basemap(105.0, 107.0, -3.35, -1.45, z=z)
    ppd = bm.width / (e - w)
    sheets = _render_sheets(RASTERS, w, e, s, n, ppd)
    sheets.putalpha(sheets.getchannel('A').point(lambda v: int(v * opacity)))
    out = bm.convert('RGBA')
    out.alpha_composite(sheets)
    out = out.convert('RGB')
    d = ImageDraw.Draw(out)
    caption(d, (12, out.height - 32),
            'historical sheets (v3.1) over OpenStreetMap  ·  basemap © OpenStreetMap contributors (ODbL)',
            size=17)
    out.save(path)
    return out.size


def fig_mosaic(path, ppd=900):
    """All 176 sheets, sheet outlines in red - coverage and seams."""
    west, east, south, north = 105.05, 106.95, -3.30, -1.55
    img = _render_sheets(RASTERS, west, east, south, north, ppd)
    out = Image.new('RGB', img.size, 'white')
    out.paste(img, (0, 0), img)
    d = ImageDraw.Draw(out)
    for f in sorted(glob.glob(RASTERS)):
        with rasterio.open(f) as ds:
            b = ds.bounds
        d.rectangle([(b.left - west) * ppd, (north - b.top) * ppd,
                     (b.right - west) * ppd, (north - b.bottom) * ppd],
                    outline=(220, 0, 0), width=2)
    caption(d, (12, 12),
            '176 sheets, v3.1 — red outlines are sheet extents; no structural overlaps',
            size=17)
    out.save(path)
    return out.size


def fig_irregular(path, sid='33-XXVI-d'):
    """A sheet whose printed frame is taller than its 5' cell.

    Blue is the detected neatline, red is the graticule cell it was forced
    into by v2 - the gap between them is the distortion v3 removes.
    """
    g = grid.sheet_geometry(sid)
    with Image.open(os.path.join(grid.CROP_DIR, sid + '.jpg')) as im:
        scale = 760.0 / im.width
        img = im.resize((int(im.width * scale), int(im.height * scale))).convert('RGB')
    fl, fr, ft, fb = [v * scale for v in g['frame_px']]
    cell_h = (fr - fl) * grid.CELL_ASPECT          # one cell, at this sheet's scale
    pad_b, pad_r = 40, 330
    out = Image.new('RGB', (img.width + pad_r, img.height + pad_b), 'white')
    out.paste(img, (0, 0))
    d = ImageDraw.Draw(out)
    d.rectangle([fl, ft, fr, fb], outline=(20, 90, 220), width=3)
    d.rectangle([fl, ft, fr, ft + cell_h], outline=(220, 0, 0), width=3)
    over_m = (g['span_lat_arcmin'] - 5.0) * 1852
    x = img.width + 16
    d.text((x, ft + 4), sid, font=font(21), fill=(0, 0, 0))
    d.text((x, ft + 40), 'blue: printed neatline', font=font(16), fill=(20, 90, 220))
    d.text((x, ft + 62), "red: one 5-arcmin cell", font=font(16), fill=(200, 0, 0))
    d.text((x, ft + 100), 'The printed frame is %.1f%%' % (g['frame_h'] / g['frame_w'] * 100 - 100),
           font=font(16), fill=(0, 0, 0))
    d.text((x, ft + 122), 'taller than one cell, i.e.', font=font(16), fill=(0, 0, 0))
    d.text((x, ft + 144), '%.0f m of extra coastline.' % over_m, font=font(16), fill=(0, 0, 0))
    d.text((x, ft + 182), 'v2 squeezed the whole sheet', font=font(16), fill=(95, 95, 95))
    d.text((x, ft + 204), 'into the red box, distorting', font=font(16), fill=(95, 95, 95))
    d.text((x, ft + 226), 'its interior by that much.', font=font(16), fill=(95, 95, 95))
    out.save(path)
    return out.size


def main():
    os.makedirs(OUT, exist_ok=True)
    jobs = [
        ('mosaic_v3.png', fig_mosaic, 'all 176 sheets, outlines in red'),
        ('irregular_sheet.png', fig_irregular, 'a sheet printed past its cell'),
    ]
    for name, fn, desc in jobs:
        p = os.path.join(OUT, name)
        size = fn(p)
        print('%-22s %-38s %s' % (name, desc, size), flush=True)

    # The before/after seam figure needs the v2 rasters, which are not always
    # present; skip rather than fail when they are not.
    if glob.glob(os.path.join(ROOT, 'GEOREF_FINAL_COMPOSITE_12', '*.tif')):
        import seam_figure
        sys.argv = ['seam_figure', os.path.join(OUT, 'seam_v2_v3.png')]
        seam_figure.main()
    else:
        print('%-22s %s' % ('seam_v2_v3.png', 'skipped - v2 rasters not present'))


if __name__ == '__main__':
    main()
