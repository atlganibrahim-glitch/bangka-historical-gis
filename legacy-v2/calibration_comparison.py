# -*- coding: utf-8 -*-
"""
Manual Georeferencing Calibration Comparator
============================================
Run this script after doing a manual georeferencing in QGIS.

What it does:
  1. Reads the extent of the manually georeferenced TIF file
  2. Compares it with the automatically computed extent
  3. Finds the delta (difference) values
  4. Derives an "offset" coefficient to apply to all maps

Usage:
  Write the manually georeferenced GeoTIFF into the MANUAL_FILE variable
  below, then run the script.
"""
import os
import pandas as pd
from osgeo import gdal
gdal.UseExceptions()

# v2-era script; moved into legacy-v2/ during the v3 reorganisation.
# GEOREF_FINAL_STANDARD_164/ stayed at the true repo root; archive/ moved
# into legacy-v2/ alongside this script.
_HERE = os.path.dirname(os.path.abspath(__file__))
OLD_DIR  = os.path.join(os.path.dirname(_HERE), "GEOREF_FINAL_STANDARD_164")
CSV_PATH = os.path.join(_HERE, "archive", "bangka_dataset.csv")

# ============================================================
# HERE: the sheet_id and file path you georeferenced manually
SHEET_ID    = "31-XXIV-q"   # sheet_id value in the CSV
MANUAL_FILE = r"D:\İşlenecekHaritalar\31-XXIV-q_manual.tif"  # the file QGIS saved
# ============================================================

def get_extent(path):
    """Return the extent of a TIF file: (left, top, right, bottom)"""
    ds = gdal.Open(path)
    if not ds:
        raise FileNotFoundError(f"Could not open file: {path}")
    gt = ds.GetGeoTransform()
    w, h = ds.RasterXSize, ds.RasterYSize
    left   = gt[0]
    top    = gt[3]
    right  = gt[0] + gt[1] * w
    bottom = gt[3] + gt[5] * h
    ds = None
    return left, top, right, bottom

def get_old_extent(sheet_id):
    path = os.path.join(OLD_DIR, sheet_id + ".tif")
    return get_extent(path)

def calc_crop_extent(sheet_id, df):
    """The crop extent computed with the current script logic"""
    row = df[df['sheet_id'] == sheet_id].iloc[0]
    ml, mr, mt, mb = row['margin_left'], row['margin_right'], row['margin_top'], row['margin_bottom']

    el, et, er, eb = get_old_extent(sheet_id)
    dlon = er - el
    dlat = et - eb  # positive

    cl = el + ml * dlon
    cr = er - mr * dlon
    ct = et - mt * dlat
    cb = eb + mb * dlat
    return cl, ct, cr, cb


def main():
    if not os.path.exists(MANUAL_FILE):
        print(f"ERROR: Manual georeference file not found!")
        print(f"  Expected: {MANUAL_FILE}")
        print(f"\n  Use 'Save as...' from the QGIS Georeferencer and save to this path.")
        print(f"  Or update the MANUAL_FILE variable.")
        return

    df = pd.read_csv(CSV_PATH)

    print("=" * 65)
    print("GEOREFERENCING CALIBRATION COMPARISON")
    print("=" * 65)
    print(f"Map: {SHEET_ID}")
    print()

    # Manual result
    m_left, m_top, m_right, m_bottom = get_extent(MANUAL_FILE)
    print(f"Manual (QGIS) extent:")
    print(f"  Left(W)  : {m_left:.6f} deg")
    print(f"  Right(E) : {m_right:.6f} deg")
    print(f"  North(N) : {m_top:.6f} deg")
    print(f"  South(S) : {m_bottom:.6f} deg")
    print()

    # Automatic computation
    a_left, a_top, a_right, a_bottom = calc_crop_extent(SHEET_ID, df)
    print(f"Automatically computed extent:")
    print(f"  Left(W)  : {a_left:.6f} deg")
    print(f"  Right(E) : {a_right:.6f} deg")
    print(f"  North(N) : {a_top:.6f} deg")
    print(f"  South(S) : {a_bottom:.6f} deg")
    print()

    # Delta (difference)
    d_left   = m_left   - a_left
    d_top    = m_top    - a_top
    d_right  = m_right  - a_right
    d_bottom = m_bottom - a_bottom

    print(f"Difference (Manual - Automatic):")
    print(f"  dLeft   : {d_left:+.6f} deg  ({d_left*111320:.1f} m)")
    print(f"  dRight  : {d_right:+.6f} deg  ({d_right*111320:.1f} m)")
    print(f"  dNorth  : {d_top:+.6f} deg  ({d_top*111320:.1f} m)")
    print(f"  dSouth  : {d_bottom:+.6f} deg  ({d_bottom*111320:.1f} m)")
    print()

    # Average offset (can be applied to all maps if consistent)
    avg_lon_offset = (d_left + d_right) / 2
    avg_lat_offset = (d_top + d_bottom) / 2
    consistency_lon = abs(d_left - d_right)
    consistency_lat = abs(d_top - d_bottom)

    print(f"Average offset (to apply to all maps):")
    print(f"  Longitude (lon): {avg_lon_offset:+.6f} deg  ({avg_lon_offset*111320:.1f} m)")
    print(f"  Latitude  (lat): {avg_lat_offset:+.6f} deg  ({avg_lat_offset*111320:.1f} m)")
    print()

    if consistency_lon < 0.001 and consistency_lat < 0.001:
        print("[OK] Offset is consistent - can be applied to all maps!")
        print()
        print("   Add to crop_margin_geo.py:")
        print(f"   LON_OFFSET = {avg_lon_offset:.6f}")
        print(f"   LAT_OFFSET = {avg_lat_offset:.6f}")
    else:
        print("[WARN] Left/Right or North/South differences are inconsistent.")
        print("    This map may need a different transform type.")
        print(f"    Lon diff: {consistency_lon:.6f} deg, Lat diff: {consistency_lat:.6f} deg")

    # Also show the OLD extent
    print()
    el, et, er, eb = get_old_extent(SHEET_ID)
    print(f"OLD reference extent:")
    print(f"  Left={el:.6f}  Right={er:.6f}  North={et:.6f}  South={eb:.6f}")


if __name__ == "__main__":
    main()
