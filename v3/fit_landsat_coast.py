"""Does a 1982 coastline explain the residual better than a 2026 one?

INCONCLUSIVE - the reference layer could not be built well enough. Kept to
document the attempt, the data that exists, and what would be needed.

Motivation: fit_singles.py measures each coastal sheet against the modern OSM
coastline and bottoms out around 780 m. Most of that is believed to be real
change - Bangka's shore has moved a long way since the 1930s. A 1982 coastline
is roughly half the elapsed time away, so if the belief is right the residual
should drop clearly against it.

What is available (verified): Landsat MSS L1TP scenes over Bangka with good
geometry - LM03_L1TP_132061_19820706 (north, 10% cloud, GEOMETRIC_RMSE_MODEL
21.1 m, 27 GCPs) and LM03_L1TP_132062_19820320 (south, 43% cloud, 22.6 m).
Those RMSEs are well under the ~170 m signal, so the control would be sound
in principle. Free via the Planetary Computer STAC API, no auth beyond an
anonymous SAS token.

Why it failed here: extracting a usable shoreline from a single MSS scene did
not work. The southern scene is too cloudy to segment at all. In the northern
scene, thresholding the NIR band leaves a land mask whose western edge is a
long straight line cutting *through* the island rather than following the
coast - western/central northern Bangka reads as dark despite being land,
which a threshold change does not fix (it looks like a scene-wide radiometric
/ haze gradient). Fitting sheets against that mask gives a median residual of
1777 m versus 1175 m for OSM on the same 12 sheets - i.e. the extraction is
the problem, not the hypothesis. The hypothesis is neither confirmed nor
refuted.

What would be needed to do it properly: a cloud-free multi-scene composite
(median over many acquisitions across several years, with per-scene cloud
masking from the QA_PIXEL band and radiometric normalisation) rather than a
single scene. That is a real piece of work, not a quick check, but the input
data clearly exists.
"""
import os
import sys

import cv2
import numpy as np
import rasterio
from rasterio.warp import Resampling, calculate_default_transform, reproject

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import coastfit  # noqa: E402
import grid  # noqa: E402
from fit_singles import MIN_DIVERSITY, SEARCH, load  # noqa: E402

SCENE = os.path.join(HERE, 'landsat', 'LM03_L1TP_132061_19820706_02_T2_nir08.TIF')
M = coastfit.M_PER_DEG
RES = 0.0006          # ~66 m, matching the 60 m source pixel
BOX = (105.00, -2.42, 106.95, -1.40)   # Bangka within this scene's reach


def landsat_coastline():
    """(lon, lat) points along the 1982 shoreline, plus the covered bounds."""
    with rasterio.open(SCENE) as src:
        dst_crs = 'EPSG:4326'
        transform, w, h = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds, resolution=RES)
        arr = np.zeros((h, w), np.uint8)
        reproject(rasterio.band(src, 1), arr, dst_transform=transform,
                  dst_crs=dst_crs, resampling=Resampling.average)
    # Crop to Bangka before anything else.  Without this the largest bright
    # region is the cloud field over the sea to the north-east, not the island.
    x0 = int((BOX[0] - transform.c) / transform.a)
    x1 = int((BOX[2] - transform.c) / transform.a)
    y0 = int((BOX[3] - transform.f) / transform.e)
    y1 = int((BOX[1] - transform.f) / transform.e)
    x0, x1 = max(x0, 0), min(x1, w)
    y0, y1 = max(y0, 0), min(y1, h)
    arr = arr[y0:y1, x0:x1]
    transform = transform * rasterio.Affine.translation(x0, y0)
    h, w = arr.shape

    valid = arr > 0
    # Land is bright in NIR, water almost black.  Clouds are bright too, so
    # take the largest connected bright region: within this crop the island is
    # one mass and cloud is scattered specks.
    thr = max(int(np.percentile(arr[valid], 60)), 2)
    bright = ((arr >= thr) & valid).astype(np.uint8)
    bright = cv2.morphologyEx(bright, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(bright, connectivity=8)
    if n < 2:
        raise SystemExit('no land found')
    biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    land = (lab == biggest).astype(np.uint8)
    land = cv2.morphologyEx(land, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    edge = cv2.morphologyEx(land, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)).astype(bool)
    # Drop the scene's own footprint edge.  The swath is a rotated parallelogram,
    # so its boundary runs diagonally across the island and the land mask abuts
    # it; without a generous margin that straight edge is extracted as if it
    # were shoreline and dominates the fit.
    inside = cv2.erode(valid.astype(np.uint8), np.ones((41, 41), np.uint8)).astype(bool)
    edge &= inside
    ys, xs = np.nonzero(edge)
    lon = transform.c + (xs + 0.5) * transform.a
    lat = transform.f + (ys + 0.5) * transform.e
    return np.stack([lon, lat], 1), (transform.c, transform.f + h * transform.e,
                                     transform.c + w * transform.a, transform.f)


def distance_field(pts, west, north, east, south, pad, res):
    w, e, n, s = west - pad, east + pad, north + pad, south - pad
    W, H = max(int((e - w) / res), 2), max(int((n - s) / res), 2)
    canvas = np.full((H, W), 255, np.uint8)
    xs = np.round((pts[:, 0] - w) / res).astype(np.int32)
    ys = np.round((n - pts[:, 1]) / res).astype(np.int32)
    ok = (xs >= 0) & (xs < W) & (ys >= 0) & (ys < H)
    if ok.sum() < 50:
        return None, None
    canvas[ys[ok], xs[ok]] = 0
    return cv2.distanceTransform(canvas, cv2.DIST_L2, 3) * res, (w, n, res)


def fit_against(pts_map, ref_pts, bounds, search=SEARCH, step=0.0006):
    dist, meta = distance_field(ref_pts, *bounds, pad=search + 0.02, res=0.0002)
    if dist is None:
        return None
    w0, n0, r = meta
    H, W = dist.shape

    def score(dlon, dlat):
        xs = np.round((pts_map[:, 0] + dlon - w0) / r).astype(np.int32)
        ys = np.round((n0 - (pts_map[:, 1] + dlat)) / r).astype(np.int32)
        ok = (xs >= 0) & (xs < W) & (ys >= 0) & (ys < H)
        if ok.sum() < 20:
            return np.inf
        return float(np.median(dist[ys[ok], xs[ok]]))

    best, centre, span, grid_ = None, (0.0, 0.0), search, step
    for _ in range(3):
        rng = np.arange(-span, span + 1e-12, grid_)
        for dy in rng:
            for dx in rng:
                s = score(centre[0] + dx, centre[1] + dy)
                if best is None or s < best[2]:
                    best = (centre[0] + dx, centre[1] + dy, s)
        centre, span, grid_ = (best[0], best[1]), grid_ * 1.5, grid_ / 4
    return best[0], best[1], best[2] * M


def main():
    ref, (rw, rs, re_, rn) = landsat_coastline()
    print('1982 Landsat coastline: %d points, lon %.3f..%.3f lat %.3f..%.3f'
          % (len(ref), rw, re_, rs, rn))

    osm = coastfit.load_osm()
    ids = sorted(os.path.splitext(f)[0] for f in os.listdir(os.path.join(HERE, 'masks')))
    rows = []
    print('%-14s %9s %9s %9s' % ('sheet', 'OSM(m)', '1982(m)', 'change'))
    for sid in ids:
        g = grid.sheet_geometry(sid)
        # only sheets inside the Landsat scene footprint
        if not (rw < g['west'] and g['east'] < re_ and rs < g['south'] and g['north'] < rn):
            continue
        sea, coast = load(sid)
        if coast.sum() < 300 or coastfit.orientation_diversity(sea) < MIN_DIVERSITY:
            continue
        pts = coastfit.sheet_coast_lonlat(coast, g)
        b = (g['west'], g['north'], g['east'], g['south'])
        r_osm = coastfit.fit(pts, osm, b, search_deg=SEARCH)
        r_ls = fit_against(pts, ref, b)
        if r_osm is None or r_ls is None:
            continue
        rows.append((sid, r_osm[2], r_ls[2]))
        print('%-14s %9.0f %9.0f %+9.0f' % (sid, r_osm[2], r_ls[2], r_ls[2] - r_osm[2]))

    if not rows:
        print('\nno sheets fell inside the usable scene area')
        return
    a = np.array([[r[1], r[2]] for r in rows])
    print('\n%d sheets compared' % len(rows))
    print('median residual vs OSM (2026): %.0f m' % np.median(a[:, 0]))
    print('median residual vs Landsat (1982): %.0f m' % np.median(a[:, 1]))
    better = (a[:, 1] < a[:, 0]).sum()
    print('1982 control gives a smaller residual on %d of %d sheets' % (better, len(rows)))


if __name__ == '__main__':
    main()
