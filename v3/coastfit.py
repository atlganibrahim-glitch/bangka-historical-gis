# -*- coding: utf-8 -*-
"""Fit a placed sheet against the modern OSM coastline.

The sheets are 1930s surveys, so the shoreline has genuinely moved in places
(tin dredging, mangrove, reclamation).  Everything here is therefore robust:
the score is the *median* distance from the sheet's drawn shoreline to the
nearest modern shoreline, never a mean.
"""
import json
import os

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
M_PER_DEG = 111320.0


def load_osm(path=os.path.join(HERE, 'osm_coastline.json'), highway_classes=None):
    """Load an Overpass way-geometry dump as a list of (lon, lat) polylines.

    highway_classes, if given, keeps only ways whose 'highway' tag is in the
    set (used for the road network; irrelevant for the coastline file).
    """
    with open(path) as fh:
        data = json.load(fh)
    segs = []
    for el in data['elements']:
        if highway_classes is not None:
            if el.get('tags', {}).get('highway') not in highway_classes:
                continue
        g = el.get('geometry') or []
        if len(g) > 1:
            segs.append(np.array([(p['lon'], p['lat']) for p in g], float))
    return segs


def distance_field(segs, west, north, east, south, pad_deg, res_deg):
    """Distance (in degrees) to the nearest OSM shoreline, on a raster."""
    w, e = west - pad_deg, east + pad_deg
    n, s = north + pad_deg, south - pad_deg
    W = max(int(round((e - w) / res_deg)), 2)
    H = max(int(round((n - s) / res_deg)), 2)
    canvas = np.full((H, W), 255, np.uint8)
    for seg in segs:
        xs = np.round((seg[:, 0] - w) / res_deg).astype(np.int32)
        ys = np.round((n - seg[:, 1]) / res_deg).astype(np.int32)
        pts = np.stack([xs, ys], 1)
        if pts[:, 0].max() < -5 or pts[:, 0].min() > W + 5:
            continue
        if pts[:, 1].max() < -5 or pts[:, 1].min() > H + 5:
            continue
        cv2.polylines(canvas, [pts.reshape(-1, 1, 2)], False, 0, 1)
    if (canvas == 0).sum() == 0:
        return None, None
    dist = cv2.distanceTransform(canvas, cv2.DIST_L2, 3) * res_deg
    return dist, (w, n, res_deg)


def fit(coast_lonlat, segs, bounds, search_deg=0.05, step_deg=0.0004,
        res_deg=0.0002, refine=True):
    """Best (dlon, dlat) shift aligning drawn shoreline to the modern one.

    Returns (dlon, dlat, median_residual_m, n_points) or None when there is
    not enough shoreline on either side to compare.
    """
    if len(coast_lonlat) < 40:
        return None
    west, north, east, south = bounds
    pad = search_deg + 0.02
    dist, meta = distance_field(segs, west, north, east, south, pad, res_deg)
    if dist is None:
        return None
    w0, n0, r = meta
    H, W = dist.shape

    def score(dlon, dlat):
        xs = np.round((coast_lonlat[:, 0] + dlon - w0) / r).astype(np.int32)
        ys = np.round((n0 - (coast_lonlat[:, 1] + dlat)) / r).astype(np.int32)
        ok = (xs >= 0) & (xs < W) & (ys >= 0) & (ys < H)
        if ok.sum() < 20:
            return np.inf
        return float(np.median(dist[ys[ok], xs[ok]]))

    best, grid = None, step_deg
    centre = (0.0, 0.0)
    span = search_deg
    for _ in range(3 if refine else 1):
        rng = np.arange(-span, span + 1e-12, grid)
        for dy in rng:
            for dx in rng:
                s = score(centre[0] + dx, centre[1] + dy)
                if best is None or s < best[2]:
                    best = (centre[0] + dx, centre[1] + dy, s)
        centre = (best[0], best[1])
        span, grid = grid * 1.5, grid / 4
    return best[0], best[1], best[2] * M_PER_DEG, len(coast_lonlat)


def orientation_diversity(sea_mask_bool):
    """How well a sheet's shoreline constrains *both* axes.

    A single straight stretch of coast leaves the along-shore direction free,
    so its "fit" is an artefact.  Measured from the shoreline normals (the
    gradient of the sea mask), which is independent of point ordering:
    0 = one direction only, 1 = normals spread over all directions.
    """
    m = sea_mask_bool.astype(np.float32)
    m = cv2.GaussianBlur(m, (0, 0), 2.0)
    gx = cv2.Sobel(m, cv2.CV_32F, 1, 0, ksize=5)
    gy = cv2.Sobel(m, cv2.CV_32F, 0, 1, ksize=5)
    mag = np.hypot(gx, gy)
    sel = mag > 0.15 * mag.max()
    if sel.sum() < 100:
        return 0.0
    th = np.arctan2(gy[sel], gx[sel])
    w = mag[sel]
    r = np.hypot((w * np.cos(2 * th)).sum(), (w * np.sin(2 * th)).sum()) / w.sum()
    return float(1.0 - r)


def sheet_coast_lonlat(mask_coast, geom):
    """Reduced-grid coastline pixels -> (lon, lat) using a sheet's geometry."""
    ys, xs = np.nonzero(mask_coast)
    h, w = mask_coast.shape
    lon = geom['west'] + (xs + 0.5) / w * (geom['east'] - geom['west'])
    lat = geom['north'] - (ys + 0.5) / h * (geom['north'] - geom['south'])
    return np.stack([lon, lat], 1)
