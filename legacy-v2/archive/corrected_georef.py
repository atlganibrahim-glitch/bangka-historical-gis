# -*- coding: utf-8 -*-
"""
Bangka Maps - Corrected Automatic Georeferencing
================================================
This script:
1. Computes Batavia Datum coordinates from the sheet ID
2. Performs Batavia (EPSG:4211) -> WGS 84 (EPSG:4326) datum transform
3. Projects the crop margins onto the coordinates
4. Saves as a GeoTIFF

Author: Auto-generated
Date: 2026
"""
import os
import sys
import pandas as pd
from osgeo import gdal, osr

gdal.UseExceptions()

# ==============================================================================
# SETTINGS
# ==============================================================================
INPUT_DIR    = os.path.dirname(os.path.abspath(__file__))   # crop_xxx.jpg is here
OUTPUT_DIR   = os.path.join(INPUT_DIR, "CORRECTED_MAPS")
CSV_PATH     = os.path.join(INPUT_DIR, "bangka_dataset.csv")

# Subgrid map (per the Dutch 1:25,000 system)
# Each large cell is 20' x 20' (20 minutes), split into a 4x4 = 16 subcells
# Each subcell is 5' x 5' (5 minutes)
SUBGRID_MAP = {
    'a': (0, 0), 'b': (1, 0), 'c': (2, 0), 'd': (3, 0),
    'e': (0, 1), 'f': (1, 1), 'g': (2, 1), 'h': (3, 1),
    'i': (0, 2), 'k': (1, 2), 'l': (2, 2), 'm': (3, 2),
    'n': (0, 3), 'o': (1, 3), 'p': (2, 3), 'q': (3, 3)
}

# Each subgrid cell is 5 minutes = 5/60 degrees
SUBGRID_SIZE = 5.0 / 60.0  # in degrees (~9.25 km)

# Dutch East Indies cartographic system - large cell 20' x 20'
BIG_CELL = 20.0 / 60.0  # = 4 * SUBGRID_SIZE

# Roman numeral equivalents
ROMAN_MAP = {
    'XXIII': 23, 'XXIV': 24, 'XXV': 25,
    'XXVI': 26, 'XXVII': 27, 'XXVIII': 28
}

# ==============================================================================
# DATUM TRANSFORM SETUP
# Batavia (EPSG:4211) -> WGS 84 (EPSG:4326)
# ==============================================================================
src_srs = osr.SpatialReference()
src_srs.ImportFromEPSG(4211)  # Batavia

dst_srs = osr.SpatialReference()
dst_srs.ImportFromEPSG(4326)  # WGS 84

transform = osr.CoordinateTransformation(src_srs, dst_srs)


def roman_to_int(roman):
    if roman not in ROMAN_MAP:
        raise ValueError(f"Unknown Roman numeral: '{roman}'")
    return ROMAN_MAP[roman]


def batavia_to_wgs84(lon, lat):
    """Transform a Batavia datum coordinate to WGS 84."""
    result = transform.TransformPoint(lon, lat)
    return result[0], result[1]  # (lon_wgs84, lat_wgs84)


def compute_coordinates(sheet_id, margin_left, margin_right, margin_top, margin_bottom):
    """
    Compute the exact coordinates from the sheet ID.

    Dutch cartographic system:
    - Column number (31, 32, 33...): each column is a 20' latitude interval
    - Roman numeral (XXIII, XXIV...): each row is a 20' longitude interval
    - Sub code (a-q): a 5'x5' cell within a 4x4 grid

    Reference point: 105 deg E, -1 deg S (Batavia datum)
    """
    parts = sheet_id.split('-')
    if len(parts) != 3:
        raise ValueError(f"Invalid sheet_id format: '{sheet_id}' (expected: NN-ROMAN-xx)")

    col_str, row_roman, sub_code = parts
    col_num = int(col_str)
    row_num = roman_to_int(row_roman)

    # Top-left corner of the large cell (Batavia datum)
    # Dutch system: column 32 = starts at 105 deg east
    # Each column is 20' = 0.3333 deg
    base_lon = 105.0 + (col_num - 32) * BIG_CELL

    # Row 25 = -2 deg (southern latitude, negative)
    # Latitude decreases as you go down
    base_lat = -2.0 - (row_num - 25) * BIG_CELL

    # Parse the sub code (e.g. "ni" = combination of n and i -> 2 merged cells)
    coords = []
    for ch in sub_code:
        if ch not in SUBGRID_MAP:
            raise KeyError(f"Unknown subcell code: '{ch}' (sheet_id='{sheet_id}')")
        coords.append(SUBGRID_MAP[ch])

    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]

    # Subcell bounds (Batavia datum)
    left_lon_bat   = base_lon + min(xs) * SUBGRID_SIZE
    right_lon_bat  = base_lon + (max(xs) + 1) * SUBGRID_SIZE
    top_lat_bat    = base_lat - min(ys) * SUBGRID_SIZE
    bottom_lat_bat = base_lat - (max(ys) + 1) * SUBGRID_SIZE

    # Apply the crop margins
    # Margins are given as a percentage of the original image's pixels
    # Compute the actual coverage area
    full_lon_span = right_lon_bat - left_lon_bat
    full_lat_span = top_lat_bat   - bottom_lat_bat  # positive value

    # Before cropping the margins cover the full area; we are cropping it
    # margin_left = how much was cropped from the left side (ratio)
    # So the crop image's left bound = original left + margin_left * total_width
    crop_left_lon_bat   = left_lon_bat   + margin_left  * full_lon_span
    crop_right_lon_bat  = right_lon_bat  - margin_right * full_lon_span
    crop_top_lat_bat    = top_lat_bat    - margin_top    * full_lat_span
    crop_bottom_lat_bat = bottom_lat_bat + margin_bottom * full_lat_span

    # Batavia -> WGS 84 transform (4 corners)
    # Top-Left
    tl_lon, tl_lat = batavia_to_wgs84(crop_left_lon_bat,  crop_top_lat_bat)
    # Bottom-Right
    br_lon, br_lat = batavia_to_wgs84(crop_right_lon_bat, crop_bottom_lat_bat)
    # Top-Right
    tr_lon, tr_lat = batavia_to_wgs84(crop_right_lon_bat, crop_top_lat_bat)
    # Bottom-Left
    bl_lon, bl_lat = batavia_to_wgs84(crop_left_lon_bat,  crop_bottom_lat_bat)

    return tl_lon, tl_lat, tr_lon, tr_lat, bl_lon, bl_lat, br_lon, br_lat


# ==============================================================================
# MAIN PROCESS
# ==============================================================================
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

df = pd.read_csv(CSV_PATH)
existing_files = set(os.listdir(INPUT_DIR))

print(f"Total maps: {len(df)}")
print(f"Input: {INPUT_DIR}")
print(f"Output: {OUTPUT_DIR}")
print("-" * 60)

success = 0
skipped = []

for _, row in df.iterrows():
    sheet_id     = row['sheet_id']
    crop_filename = row.get('crop_filename', '')
    margin_left   = float(row['margin_left'])
    margin_right  = float(row['margin_right'])
    margin_top    = float(row['margin_top'])
    margin_bottom = float(row['margin_bottom'])

    # Find the file
    if isinstance(crop_filename, str) and crop_filename in existing_files:
        found_file = crop_filename
    else:
        skipped.append((sheet_id, "crop file not found"))
        continue

    input_path  = os.path.join(INPUT_DIR,  found_file)
    output_path = os.path.join(OUTPUT_DIR, f"{sheet_id}.tif")

    try:
        tl_lon, tl_lat, tr_lon, tr_lat, bl_lon, bl_lat, br_lon, br_lat = \
            compute_coordinates(sheet_id, margin_left, margin_right, margin_top, margin_bottom)

        # Georeferencing with GDAL
        # outputBounds = [left, bottom, right, top] (WGS 84)
        left_wgs84   = min(tl_lon, bl_lon)
        right_wgs84  = max(tr_lon, br_lon)
        top_wgs84    = max(tl_lat, tr_lat)
        bottom_wgs84 = min(bl_lat, br_lat)

        options = gdal.TranslateOptions(
            format        = "GTiff",
            outputBounds  = [left_wgs84, bottom_wgs84, right_wgs84, top_wgs84],
            outputSRS     = "EPSG:4326",
            creationOptions = ["COMPRESS=LZW", "TILED=YES"]
        )

        out_ds = gdal.Translate(output_path, input_path, options=options)
        out_ds = None
        success += 1
        print(f"  OK  {sheet_id:25} | Left={left_wgs84:.5f} Top={top_wgs84:.5f} Right={right_wgs84:.5f} Bottom={bottom_wgs84:.5f}")

    except Exception as e:
        skipped.append((sheet_id, str(e)))
        print(f" ERROR {sheet_id:25} | {e}")
        continue

print("\n" + "=" * 60)
print(f"Done: {success} maps processed successfully")
if skipped:
    print(f"Skipped ({len(skipped)}):")
    for s, r in skipped:
        print(f"  - {s}: {r}")
