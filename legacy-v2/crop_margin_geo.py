# -*- coding: utf-8 -*-
"""
Bangka Maps - Crop-Margin-Corrected Georeferencing
==================================================
This script uses the OLD calibrated maps as reference:
- OLD maps = original (with legend) maps, in the correct position
- NEW maps = cropped (edges removed) maps

Coordinates for the cropped maps are computed as follows:
  OLD map extent + margin correction = CROP map extent

This method:
- Preserves the existing calibration
- Only projects the cropped-edge information onto the coordinates
- Inherits the datum handling from the OLD map

Usage: run in the QGIS Python console or in a terminal.
"""
import os
import pandas as pd
from osgeo import gdal, osr

gdal.UseExceptions()

# v2-era script; moved into legacy-v2/ during the v3 reorganisation.
# GEOREF_FINAL_STANDARD_164/ and recovered_maps/ stayed at the true repo
# root; bangka_dataset_v2.csv moved into legacy-v2/ alongside this script.
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OLD_DIR    = os.path.join(ROOT, "GEOREF_FINAL_STANDARD_164")
CROP_DIR   = os.path.join(ROOT, "recovered_maps")
OUTPUT_DIR = os.path.join(ROOT, "GEOREF_FINAL_STANDARD_164")
CSV_PATH   = os.path.join(HERE, "bangka_dataset_v2.csv")

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

df = pd.read_csv(CSV_PATH)
existing_crop = set(os.listdir(CROP_DIR))
old_files = set(os.listdir(OLD_DIR))

print(f"OLD calibrated folder: {OLD_DIR}")
print(f"Output folder: {OUTPUT_DIR}")
print(f"Total records: {len(df)}")
print("-" * 70)

success = 0
skipped = []

for _, row in df.iterrows():
    sheet_id      = row['sheet_id']
    crop_filename = row.get('crop_filename', '')

    # Margin values (as a ratio of the original image)
    # e.g. margin_left=0.07 -> 7% of the original image cropped from the left edge
    ml = float(row['margin_left'])
    mr = float(row['margin_right'])
    mt = float(row['margin_top'])
    mb = float(row['margin_bottom'])

    # Check the files
    old_file = f"{sheet_id}.tif"
    if old_file not in old_files:
        skipped.append((sheet_id, f"OLD map not found: {old_file}"))
        continue

    if not isinstance(crop_filename, str) or crop_filename not in existing_crop:
        skipped.append((sheet_id, f"Crop file not found: {crop_filename}"))
        continue

    old_path    = os.path.join(OLD_DIR, old_file)
    crop_path   = os.path.join(CROP_DIR, crop_filename)
    output_path = os.path.join(OUTPUT_DIR, f"{sheet_id}.tif")

    try:
        # Get the OLD map's extent
        ds_old = gdal.Open(old_path)
        if not ds_old:
            skipped.append((sheet_id, "OLD file could not be opened"))
            continue

        gt = ds_old.GetGeoTransform()
        old_w = ds_old.RasterXSize
        old_h = ds_old.RasterYSize
        proj  = ds_old.GetProjection()

        old_left   = gt[0]
        old_top    = gt[3]
        old_right  = gt[0] + gt[1] * old_w
        old_bottom = gt[3] + gt[5] * old_h
        ds_old = None

        # OLD map full extent
        old_lon_span = old_right - old_left
        old_lat_span = old_top   - old_bottom  # positive value

        # The crop map's margins relative to the OLD map's pixel ratio
        # NOTE: OLD map = original with legend (full sheet)
        #       Crop map = legend-removed version
        # Margin values are relative to the original map's pixel size
        crop_left   = old_left   + ml * old_lon_span
        crop_right  = old_right  - mr * old_lon_span
        crop_top    = old_top    - mt * old_lat_span
        crop_bottom = old_bottom + mb * old_lat_span

        # Read the crop pixel dimensions
        ds_crop = gdal.Open(crop_path)
        if not ds_crop:
            skipped.append((sheet_id, "Crop file could not be opened"))
            continue
        cols = ds_crop.RasterXSize
        rows = ds_crop.RasterYSize

        # GeoTransform: (ulx, px_width, 0, uly, 0, px_height)
        # uly = north bound (crop_top), px_height negative (southward)
        px_x = (crop_right - crop_left) / cols
        px_y = (crop_bottom - crop_top) / rows  # negative
        gt_new = (crop_left, px_x, 0.0, crop_top, 0.0, px_y)

        srs = osr.SpatialReference()
        srs.ImportFromEPSG(4326)

        # Copy the pixel data, assign the coordinate directly (overrides the
        # existing wrong georef - no reprojection)
        driver = gdal.GetDriverByName("GTiff")
        co = ["COMPRESS=LZW", "TILED=YES", "BIGTIFF=IF_NEEDED"]
        out_ds = driver.CreateCopy(output_path, ds_crop, strict=0,
                                   options=co)
        out_ds.SetGeoTransform(gt_new)
        out_ds.SetProjection(srs.ExportToWkt())
        out_ds = None
        ds_crop = None
        success += 1

        print(f"OK  {sheet_id:25} | Left={crop_left:.5f} Top={crop_top:.5f} "
              f"Right={crop_right:.5f} Bottom={crop_bottom:.5f}")

    except Exception as e:
        skipped.append((sheet_id, str(e)))
        print(f"ERROR {sheet_id}: {e}")
        continue

print("\n" + "=" * 70)
print(f"Done: {success}/{len(df)} maps processed successfully")
if skipped:
    print(f"\nSkipped {len(skipped)} maps:")
    for s, r in skipped:
        print(f"  x {s}: {r}")
else:
    print("All maps processed successfully!")
