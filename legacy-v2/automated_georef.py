import os
import pandas as pd
from osgeo import gdal

gdal.UseExceptions()

# ==============================================================================
# MAP CALIBRATION (SHIFT) SETTINGS
LON_OFFSET = 0.14043
LAT_OFFSET = -0.01045
# ==============================================================================

# v2-era script; run from the true repo root (recovered_maps/ and
# GEOREF_FINAL_STANDARD_164/ stayed there). archive/ moved into legacy-v2/
# alongside this script. Note: these constants do NOT match the ones baked
# into the published v2 rasters (+0.140831 / +0.000121) — see V3_REPORT.md §1d.
INPUT_DIR = "recovered_maps"  # cropped images live here
OUTPUT_DIR = "GEOREF_FINAL_STANDARD_164"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

df = pd.read_csv(os.path.join('legacy-v2', 'archive', 'bangka_dataset.csv'))

subgrid_map = {
    'a': (0, 0), 'b': (1, 0), 'c': (2, 0), 'd': (3, 0),
    'e': (0, 1), 'f': (1, 1), 'g': (2, 1), 'h': (3, 1),
    'i': (0, 2), 'k': (1, 2), 'l': (2, 2), 'm': (3, 2),
    'n': (0, 3), 'o': (1, 3), 'p': (2, 3), 'q': (3, 3)
}

CELL = 5 / 60.0
ROMAN_MAP = {'XXIII': 23, 'XXIV': 24, 'XXV': 25, 'XXVI': 26, 'XXVII': 27, 'XXVIII': 28}

def roman_to_int(roman):
    if roman not in ROMAN_MAP:
        raise ValueError(f"Unknown Roman numeral: '{roman}'")
    return ROMAN_MAP[roman]

def get_bounds_for_subcode(sub_code, base_lon, base_lat):
    coords = []
    for ch in sub_code:
        if ch not in subgrid_map:
            raise KeyError(f"Letter not in subgrid map: '{ch}' (sub_code='{sub_code}')")
        coords.append(subgrid_map[ch])

    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]

    left_lon = base_lon + min(xs) * CELL
    right_lon = base_lon + (max(xs) + 1) * CELL
    top_lat = base_lat - min(ys) * CELL
    bottom_lat = base_lat - (max(ys) + 1) * CELL

    return left_lon, top_lat, right_lon, bottom_lat

try:
    existing_files = os.listdir(INPUT_DIR)
except FileNotFoundError:
    print(f"ERROR: No folder named '{INPUT_DIR}' found.")
    exit()

existing_files_set = set(existing_files)

print(f"Processing maps with calibration ({LON_OFFSET}, {LAT_OFFSET})...\n" + "-" * 50)

success = 0
skipped = []

for index, row in df.iterrows():
    sheet_id = row['sheet_id']
    image_idx = row['image_idx']

    try:
        found_file = None
        crop_filename = row.get('crop_filename')

        if isinstance(crop_filename, str) and crop_filename in existing_files_set:
            found_file = crop_filename

        if found_file is None:
            search_prefix = f"{image_idx:03d}_"
            for file in existing_files:
                if file.startswith(search_prefix) and file.endswith(('.jpg', '.tif', '.png')):
                    found_file = file
                    break

        if found_file is None:
            skipped.append((sheet_id, "file not found"))
            continue

        input_path = os.path.join(INPUT_DIR, found_file)
        output_path = os.path.join(OUTPUT_DIR, f"{sheet_id}.tif")

        parts = sheet_id.split('-')
        if len(parts) != 3:
            continue

        col_str, row_roman, sub_code = parts
        col_num = int(col_str)

        base_lon = 105.0 + (col_num - 32) * (20 / 60.0) + LON_OFFSET
        base_lat = -2.0 - (roman_to_int(row_roman) - 25) * (20 / 60.0) + LAT_OFFSET

        left_lon, top_lat, right_lon, bottom_lat = get_bounds_for_subcode(sub_code, base_lon, base_lat)
        bounds = [left_lon, top_lat, right_lon, bottom_lat]

        print(f"Processing: {sheet_id} ({found_file})")

        options = gdal.TranslateOptions(
            format="GTiff",
            outputBounds=bounds,
            outputSRS="EPSG:4326"
        )

        out_ds = gdal.Translate(output_path, input_path, options=options)
        out_ds = None
        success += 1

    except Exception as e:
        skipped.append((sheet_id, str(e)))
        continue

print("-" * 50)
print(f"Done: {success} files calibrated.")
