# -*- coding: utf-8 -*-
"""
Grid-Based Automatic Georeferencing - Diagnostic
================================================
Detects the printed 1' coordinate grid lines on the map.
The pixel positions of these lines + their known coordinates -> precise GCPs

Method:
  1. Detect horizontal dark lines (latitude grids)
  2. Detect vertical dark lines (longitude grids)
  3. From the OLD approximate position, find which 1' value each corresponds to
  4. Build a GCP list -> gdal.GCP -> affine transform
"""
import os
import numpy as np
from osgeo import gdal, osr
gdal.UseExceptions()

BASE     = r'D:\İşlenecekHaritalar'
OLD_DIR  = os.path.join(BASE, 'GEOREF_FINAL_STANDARD_164')

# Test map
CROP_FILE = os.path.join(BASE, 'crop_000.jpg')
SHEET_ID  = '31-XXIV-q'
OLD_FILE  = os.path.join(OLD_DIR, SHEET_ID + '.tif')


def get_old_extent(old_path):
    ds = gdal.Open(old_path)
    gt = ds.GetGeoTransform()
    w, h = ds.RasterXSize, ds.RasterYSize
    return gt[0], gt[3], gt[0]+gt[1]*w, gt[3]+gt[5]*h


def detect_grid_lines(img_path, dark_threshold=100, min_coverage=0.20, scale=4):
    """
    Detect the grid lines on the map.

    dark_threshold: pixels below this value = dark
    min_coverage: the fraction a line must cover along a row/column (0-1)

    Returns: (row_positions, col_positions) - full-resolution pixel indices
    """
    ds = gdal.Open(img_path)
    W, H = ds.RasterXSize, ds.RasterYSize
    nw, nh = W // scale, H // scale

    nb = ds.RasterCount
    if nb >= 3:
        r = ds.GetRasterBand(1).ReadAsArray(0,0,W,H,nw,nh).astype(np.float32)
        g = ds.GetRasterBand(2).ReadAsArray(0,0,W,H,nw,nh).astype(np.float32)
        b = ds.GetRasterBand(3).ReadAsArray(0,0,W,H,nw,nh).astype(np.float32)
        gray = 0.299*r + 0.587*g + 0.114*b
    else:
        gray = ds.GetRasterBand(1).ReadAsArray(0,0,W,H,nw,nh).astype(np.float32)
    ds = None

    dark = gray < dark_threshold

    # Per row: what fraction is dark?
    row_cov = dark.mean(axis=1)
    # Per column: what fraction is dark?
    col_cov = dark.mean(axis=0)

    # Grid line = row/column with more dark pixels than min_coverage
    row_lines_s = np.where(row_cov >= min_coverage)[0]
    col_lines_s = np.where(col_cov >= min_coverage)[0]

    # Cluster: take the center of each consecutive pixel group
    def cluster_centers(arr, gap=3):
        if len(arr) == 0:
            return np.array([])
        centers = []
        group = [arr[0]]
        for i in arr[1:]:
            if i - group[-1] <= gap:
                group.append(i)
            else:
                centers.append(int(np.mean(group)))
                group = [i]
        centers.append(int(np.mean(group)))
        return np.array(centers)

    row_centers = cluster_centers(row_lines_s)
    col_centers = cluster_centers(col_lines_s)

    # Convert to full resolution
    row_full = row_centers * scale + scale // 2
    col_full = col_centers * scale + scale // 2

    return row_full, col_full, W, H


def assign_minute_coords(pixel_positions, extent_min, extent_max, is_lat=True):
    """
    Assign the nearest whole-minute coordinate to each pixel position.

    pixel_positions: pixel indices (0 = left/top)
    extent_min, extent_max: approximate coordinate range from OLD
    is_lat: True=latitude (y, decreases downward), False=longitude (x, increases rightward)
    """
    N = len(pixel_positions)
    if N == 0:
        return []

    total_px = None  # to be provided externally

    results = []
    for px in pixel_positions:
        # Pixel -> coordinate (approximate)
        # image_height or width must be provided; simply use extent for now
        # Here we only compute the approximate coordinate
        results.append(px)
    return results


def find_grid_gcp(crop_path, old_path):
    """
    Generate GCPs from the grid lines on the crop map.
    """
    # OLD approximate extent
    el, et, er, eb = get_old_extent(old_path)

    # Detect grid lines
    # Try different threshold values
    for threshold in [80, 100, 120]:
        row_px, col_px, W, H = detect_grid_lines(crop_path, dark_threshold=threshold,
                                                  min_coverage=0.15)
        if len(row_px) >= 2 and len(col_px) >= 2:
            break

    print(f'  Pixel size        : {W} x {H}')
    print(f'  Threshold         : {threshold}')
    print(f'  Horizontal grid lines : {len(row_px)} @ pixel={row_px.tolist()}')
    print(f'  Vertical grid lines   : {len(col_px)} @ pixel={col_px.tolist()}')

    if len(row_px) < 2 or len(col_px) < 2:
        print('  WARNING: Not enough grid lines found!')
        return None

    # Pixel -> coordinate (OLD-based approximate)
    # Latitude: top=et, bottom=eb, reversed direction (y increases = lat decreases)
    def px_to_lat(y_px):
        return et + (y_px / H) * (eb - et)

    def px_to_lon(x_px):
        return el + (x_px / W) * (er - el)

    print()
    print('  Grid line coordinates (OLD-based approximate):')
    print('  Horizontal (latitude):')
    lat_approx = []
    for y in row_px:
        lat = px_to_lat(y)
        lat_min = round(lat * 60)  # nearest whole minute
        lat_exact = lat_min / 60.0
        lat_approx.append(lat_exact)
        print(f'    y={y:5d}px  ->  lat_approx={lat:.6f} deg  ->  lat_1min={lat_exact:.6f} deg  ({lat_min//60}d{abs(lat_min)%60}\')')

    print('  Vertical (longitude):')
    lon_approx = []
    for x in col_px:
        lon = px_to_lon(x)
        lon_min = round(lon * 60)  # nearest whole minute
        lon_exact = lon_min / 60.0
        lon_approx.append(lon_exact)
        print(f'    x={x:5d}px  ->  lon_approx={lon:.6f} deg  ->  lon_1min={lon_exact:.6f} deg  ({lon_min//60}d{abs(lon_min)%60}\')')

    # Build GCPs: all intersection points
    print()
    print('  GCP intersection points:')
    gcps = []
    for i, y_px in enumerate(row_px):
        for j, x_px in enumerate(col_px):
            lat = lat_approx[i]
            lon = lon_approx[j]
            gcp = gdal.GCP(lon, lat, 0, float(x_px), float(y_px))
            gcps.append(gcp)
            if i == 0 and j < 3:  # show only the first few
                print(f'    ({x_px}px, {y_px}px) -> ({lon:.6f} deg, {lat:.6f} deg)')

    print(f'  Total GCPs: {len(gcps)}')
    return gcps, W, H


# --- RUN --------------------------------------------------------------------
print('=' * 60)
print('GRID-BASED GEOREFERENCING DIAGNOSTIC')
print('=' * 60)
print(f'Map: {SHEET_ID}')
print()

result = find_grid_gcp(CROP_FILE, OLD_FILE)

if result:
    gcps, W, H = result
    print()
    print('[OK] Grid GCPs generated successfully.')
    print('   Next step: apply an affine transform using these GCPs.')
else:
    print('[ERROR] Grid not detected - try a different color channel or threshold.')
