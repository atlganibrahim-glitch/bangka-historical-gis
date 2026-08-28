# -*- coding: utf-8 -*-
"""
Grid-Based Automatic Georeferencing - +/-100m Target
====================================================
Method:
  1. Detect the 1' coordinate grid lines on the map via gradients
  2. From the OLD estimated position, assign which 1' value each corresponds to
  3. Intersection points -> GCP list
  4. Apply Batavia->WGS84 datum correction (+0.00163 deg lon, -0.000255 deg lat)
  5. CreateCopy + SetGCPs + PolynomialOrder=1 -> precise georef

Expected accuracy: +/-50-100m (depends on the map's survey accuracy)
"""
import os, math
import numpy as np
import pandas as pd
from osgeo import gdal, osr
gdal.UseExceptions()

BASE     = os.path.dirname(os.path.abspath(__file__))
OLD_DIR  = os.path.join(BASE, 'GEOREF_FINAL_STANDARD_164')
CSV_PATH = os.path.join(BASE, 'bangka_dataset_v2.csv')
OUT_DIR  = os.path.join(BASE, 'GEOREF_GRID')
os.makedirs(OUT_DIR, exist_ok=True)

# Batavia -> WGS84 datum correction (computed for the Bangka region)
DATUM_DLON = +0.001630   # +181m East
DATUM_DLAT = -0.000255   # -28m South

# Target projection
SRS_WGS84 = osr.SpatialReference()
SRS_WGS84.ImportFromEPSG(4326)
WKT_WGS84 = SRS_WGS84.ExportToWkt()

# --- Gradient-based grid line detection --------------------------------------

def read_gray_full(path):
    """Grayscale image as the average of all channels (full resolution)."""
    ds = gdal.Open(path)
    if ds is None:
        raise FileNotFoundError(path)
    W, H = ds.RasterXSize, ds.RasterYSize
    nb = ds.RasterCount
    if nb >= 3:
        r = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
        g = ds.GetRasterBand(2).ReadAsArray().astype(np.float32)
        b = ds.GetRasterBand(3).ReadAsArray().astype(np.float32)
        gray = (r + g + b) / 3.0
    else:
        gray = ds.GetRasterBand(1).ReadAsArray().astype(np.float32)
    ds = None
    return gray, W, H


def sobel_row(gray):
    """Horizontal edge strength per row (sum of vertical Sobel filter)."""
    # Simple vertical Sobel: [-1, 0, 1] columns
    ky = np.array([-1.0, 0.0, 1.0])
    # Gradient sum per row
    rows = gray.shape[0]
    # Vertical difference: |I[i+1] - I[i-1]| / 2
    top = np.vstack([gray[0:1], gray[:-1]])
    bot = np.vstack([gray[1:], gray[-1:]])
    grad_y = np.abs(bot - top)
    # Total gradient strength per row (horizontal integration)
    return grad_y.mean(axis=1)


def sobel_col(gray):
    """Vertical edge strength per column."""
    left  = np.hstack([gray[:, 0:1], gray[:, :-1]])
    right = np.hstack([gray[:, 1:], gray[:, -1:]])
    grad_x = np.abs(right - left)
    return grad_x.mean(axis=0)


def cluster_peaks(arr, gap=5):
    """Group consecutive high values -> return centers."""
    if len(arr) == 0:
        return np.array([])
    centers = []
    group = [arr[0]]
    for v in arr[1:]:
        if v - group[-1] <= gap:
            group.append(v)
        else:
            centers.append(int(round(np.mean(group))))
            group = [v]
    centers.append(int(round(np.mean(group))))
    return np.array(centers)


def detect_grid_lines(crop_path, scale=2):
    """
    Gradient-based grid line detection.
    scale: downsampling factor for memory (1=full, 2=half, 4=quarter)
    """
    ds = gdal.Open(crop_path)
    W, H = ds.RasterXSize, ds.RasterYSize
    nw, nh = max(1, W//scale), max(1, H//scale)
    nb = ds.RasterCount
    if nb >= 3:
        r = ds.GetRasterBand(1).ReadAsArray(0,0,W,H,nw,nh).astype(np.float32)
        g = ds.GetRasterBand(2).ReadAsArray(0,0,W,H,nw,nh).astype(np.float32)
        b = ds.GetRasterBand(3).ReadAsArray(0,0,W,H,nw,nh).astype(np.float32)
        gray = (r + g + b) / 3.0
    else:
        gray = ds.GetRasterBand(1).ReadAsArray(0,0,W,H,nw,nh).astype(np.float32)
    ds = None

    # Gradient profiles
    row_grad = sobel_row(gray)
    col_grad = sobel_col(gray)

    # Find peaks with a k*std threshold
    def find_peaks(arr, k=2.5):
        thresh = arr.mean() + k * arr.std()
        cands = np.where(arr > thresh)[0]
        return cluster_peaks(cands, gap=3)

    row_peaks_s = find_peaks(row_grad, k=2.5)
    col_peaks_s = find_peaks(col_grad, k=2.5)

    # Convert to full resolution
    row_peaks = (row_peaks_s * scale + scale // 2).clip(0, H - 1)
    col_peaks = (col_peaks_s * scale + scale // 2).clip(0, W - 1)

    return row_peaks, col_peaks, W, H


# --- GCP assignment ----------------------------------------------------------

ONE_MIN = 1.0 / 60.0   # 1 minute = 0.01667 deg


def assign_arc_minutes(pixel_positions, total_pixels, coord_min, coord_max,
                       is_lat=True):
    """
    Assign the nearest whole-minute coordinate to each pixel position.

    is_lat=True: on the y axis, small pixel = north (large coordinate)
    is_lat=False: on the x axis, small pixel = west (small coordinate)

    Returns: list of (pixel, exact_coord_in_degrees)
    """
    def px_to_coord(px):
        frac = px / total_pixels
        if is_lat:
            # As y increases, lat decreases (goes south)
            return coord_min + frac * (coord_max - coord_min)
        else:
            return coord_min + frac * (coord_max - coord_min)

    results = []
    for px in pixel_positions:
        approx = px_to_coord(px)
        # Round to the nearest whole minute
        exact_min = round(approx / ONE_MIN)
        exact_coord = exact_min * ONE_MIN
        # Is the assignment reasonable? (must be within OLD range + 1' tolerance)
        lo = min(coord_min, coord_max) - ONE_MIN * 1.5
        hi = max(coord_min, coord_max) + ONE_MIN * 1.5
        if lo <= exact_coord <= hi:
            results.append((int(px), float(exact_coord)))

    return results


def make_gcps(row_assignments, col_assignments, W, H, crop_N, crop_S, crop_W, crop_E):
    """
    Generate GCPs from the intersection of horizontal (latitude) and
    vertical (longitude) lines. The Batavia->WGS84 datum correction is
    applied at this stage.
    """
    gcps = []
    for (y_px, lat) in row_assignments:
        for (x_px, lon) in col_assignments:
            # Datum correction (Batavia -> WGS84)
            lon_wgs = lon + DATUM_DLON
            lat_wgs = lat + DATUM_DLAT
            gcp = gdal.GCP(lon_wgs, lat_wgs, 0.0, float(x_px), float(y_px))
            gcps.append(gcp)
    return gcps


# --- Main function -----------------------------------------------------------

def process_sheet(sheet_id, crop_path, old_path, output_path,
                  ml=0.07, mr=0.063, mt=0.078, mb=0.207):
    """
    Process one map sheet with grid-based georeferencing.
    Returns: (gcp_count, rmse) or None (failed)
    """
    # OLD estimated extent
    ds_e = gdal.Open(old_path)
    if not ds_e:
        return None
    gt = ds_e.GetGeoTransform()
    ew, eh = ds_e.RasterXSize, ds_e.RasterYSize
    old_W = gt[0]
    old_N = gt[3]
    old_E = gt[0] + gt[1] * ew
    old_S = gt[3] + gt[5] * eh
    ds_e = None

    # The crop's true geographic extent (from the margin values)
    old_lon_span = old_E - old_W
    old_lat_span = old_N - old_S   # positive: N > S
    crop_W = old_W + ml * old_lon_span
    crop_E = old_E - mr * old_lon_span
    crop_N = old_N - mt * old_lat_span  # cropped toward the top
    crop_S = old_S + mb * old_lat_span  # cropped toward the bottom

    # Detect the crop's grid lines
    row_px, col_px, CW, CH = detect_grid_lines(crop_path, scale=2)

    if len(row_px) < 2 or len(col_px) < 2:
        return None

    # Pixel -> approximate coordinate -> assign whole minute
    # Match over the crop dimensions (crop extent, not OLD!)
    lat_gcps = assign_arc_minutes(row_px, CH, crop_N, crop_S, is_lat=True)
    lon_gcps = assign_arc_minutes(col_px, CW, crop_W, crop_E, is_lat=False)

    if len(lat_gcps) < 2 or len(lon_gcps) < 2:
        return None

    # Build GCPs
    gcps = make_gcps(lat_gcps, lon_gcps, CW, CH,
                     old_N, old_S, old_W, old_E)

    if len(gcps) < 4:
        return None

    # Create GeoTIFF
    ds_src = gdal.Open(crop_path)
    if not ds_src:
        return None

    driver = gdal.GetDriverByName('GTiff')
    co = ['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=IF_NEEDED']
    ds_out = driver.CreateCopy(output_path, ds_src, strict=0, options=co)
    ds_out.SetGCPs(gcps, WKT_WGS84)

    # Compute and apply the GeoTransform with polynomial order 1 (affine)
    gdal.GCPsToGeoTransform_internal = None  # clear
    gt_new = gdal.GCPsToGeoTransform(gcps)
    if gt_new:
        ds_out.SetGeoTransform(gt_new)
        ds_out.SetProjection(WKT_WGS84)

    ds_out = None
    ds_src = None

    # Compute RMSE
    if gt_new:
        errors = []
        for gcp in gcps:
            lon_est = gt_new[0] + gcp.GCPPixel * gt_new[1] + gcp.GCPLine * gt_new[2]
            lat_est = gt_new[3] + gcp.GCPPixel * gt_new[4] + gcp.GCPLine * gt_new[5]
            dx = (lon_est - gcp.GCPX) * 111320 * abs(math.cos(math.radians(gcp.GCPY)))
            dy = (lat_est - gcp.GCPY) * 111320
            errors.append(math.sqrt(dx**2 + dy**2))
        rmse = math.sqrt(sum(e**2 for e in errors) / len(errors))
    else:
        rmse = -1

    return len(gcps), round(rmse, 2)


# --- Batch processing --------------------------------------------------------

def main():
    df = pd.read_csv(CSV_PATH)
    old_files = set(os.listdir(OLD_DIR))

    success, skipped = 0, []

    print('GRID-BASED GEOREFERENCING')
    print('Target: +/-100m (Bangka 1932 maps)')
    print('=' * 70)

    for _, row in df.iterrows():
        sid = row['sheet_id']
        cf  = str(row.get('crop_filename', ''))

        old_path  = os.path.join(OLD_DIR, sid + '.tif')
        crop_path = os.path.join(BASE, cf)
        out_path  = os.path.join(OUT_DIR, sid + '.tif')

        if not os.path.exists(old_path):
            skipped.append((sid, 'OLD missing'))
            continue
        if not os.path.exists(crop_path):
            skipped.append((sid, 'Crop missing'))
            continue

        try:
            result = process_sheet(sid, crop_path, old_path, out_path)
            if result is None:
                skipped.append((sid, 'Grid not detected'))
                print(f'  WARNING {sid}: grid < 4 GCP')
            else:
                gcp_n, rmse = result
                status = 'v' if rmse < 100 else '!'
                print(f'  {status} {sid:25} | GCP={gcp_n:2d} | RMSE={rmse:6.1f}m')
                success += 1
        except Exception as e:
            skipped.append((sid, str(e)))
            print(f'  x ERROR {sid}: {e}')

    print()
    print('=' * 70)
    print(f'Done: {success}/{len(df)} maps')
    print(f'Output: {OUT_DIR}')
    if skipped:
        print(f'\nSkipped {len(skipped)} maps:')
        for s, r in skipped:
            print(f'  x {s}: {r}')


if __name__ == '__main__':
    main()
