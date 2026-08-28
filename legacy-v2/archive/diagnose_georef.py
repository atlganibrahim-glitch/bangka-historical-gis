#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnostic helper for georeferencing pipeline.

Usage:
  python diagnose_georef.py --sheet <sheet_id>
  python diagnose_georef.py --crop <crop_path> --eski <eski_path> --ml ML --mr MR --mt MT --mb MB

Prints detected grid line pixel positions and the pixel->coordinate mapping
used by `assign_arc_minutes` so you can inspect systematic vertical bias.
"""
import os
import sys
import argparse
import pandas as pd
import math

import georef_grid as gg
from osgeo import gdal


def px_to_coord(px, total_px, coord_min, coord_max, is_lat=True):
    frac = px / float(total_px)
    return coord_min + frac * (coord_max - coord_min)


def diagnose_from_sheet(sheet_id, csv_path=None):
    df = pd.read_csv(csv_path or os.path.join(os.path.dirname(__file__), 'bangka_dataset_v2.csv'))
    row = df[df['sheet_id'] == sheet_id]
    if row.empty:
        print(f"Sheet '{sheet_id}' not found in CSV")
        return
    row = row.iloc[0]
    crop_fn = row.get('crop_filename')
    ml = float(row['margin_left'])
    mr = float(row['margin_right'])
    mt = float(row['margin_top'])
    mb = float(row['margin_bottom'])

    base = os.path.dirname(__file__)
    crop_path = os.path.join(base, crop_fn)
    eski_path = os.path.join(base, 'GEOREF_FINAL_STANDARD_164', sheet_id + '.tif')
    return diagnose_from_paths(crop_path, eski_path, ml, mr, mt, mb)


def diagnose_from_paths(crop_path, eski_path, ml, mr, mt, mb):
    print(f"Diagnosing: crop={crop_path}\n         eski={eski_path}")

    # read eski extent
    ds_e = gdal.Open(eski_path)
    if not ds_e:
        print('Unable to open eski file')
        return
    gt = ds_e.GetGeoTransform()
    ew, eh = ds_e.RasterXSize, ds_e.RasterYSize
    eski_W = gt[0]
    eski_N = gt[3]
    eski_E = gt[0] + gt[1] * ew
    eski_S = gt[3] + gt[5] * eh
    ds_e = None

    eski_lon_span = eski_E - eski_W
    eski_lat_span = eski_N - eski_S
    crop_W = eski_W + ml * eski_lon_span
    crop_E = eski_E - mr * eski_lon_span
    crop_N = eski_N - mt * eski_lat_span
    crop_S = eski_S + mb * eski_lat_span

    print(f"Computed crop extent:\n  W={crop_W:.7f}, E={crop_E:.7f}, N={crop_N:.7f}, S={crop_S:.7f}")

    # detect grid
    row_px, col_px, W, H = gg.detect_grid_lines(crop_path, scale=2)
    print(f"Detected rows (y px): {row_px.tolist()}")
    print(f"Detected cols (x px): {col_px.tolist()}")

    print('\nRow pixel -> approx_lat -> rounded_minute -> exact_min_deg')
    for y in row_px:
        approx = px_to_coord(y, H, crop_N, crop_S, is_lat=True)
        exact_min = round(approx / gg.ONE_MIN)
        exact_deg = exact_min * gg.ONE_MIN
        print(f"  y={int(y):4d} -> approx={approx:.7f} -> min={exact_min} -> exact={exact_deg:.7f}")

    print('\nCol pixel -> approx_lon -> rounded_minute -> exact_min_deg')
    for x in col_px:
        approx = px_to_coord(x, W, crop_W, crop_E, is_lat=False)
        exact_min = round(approx / gg.ONE_MIN)
        exact_deg = exact_min * gg.ONE_MIN
        print(f"  x={int(x):4d} -> approx={approx:.7f} -> min={exact_min} -> exact={exact_deg:.7f}")

    # show what assign_arc_minutes returns
    lat_assign = gg.assign_arc_minutes(row_px, H, crop_N, crop_S, is_lat=True)
    lon_assign = gg.assign_arc_minutes(col_px, W, crop_W, crop_E, is_lat=False)
    print('\nassign_arc_minutes lat results:')
    print(lat_assign)
    print('assign_arc_minutes lon results:')
    print(lon_assign)

    return dict(row_px=row_px, col_px=col_px, W=W, H=H,
                crop_W=crop_W, crop_E=crop_E, crop_N=crop_N, crop_S=crop_S,
                lat_assign=lat_assign, lon_assign=lon_assign)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--sheet', help='sheet_id to diagnose')
    p.add_argument('--crop', help='path to crop image')
    p.add_argument('--eski', help='path to eski geotiff')
    p.add_argument('--ml', type=float, default=0.07)
    p.add_argument('--mr', type=float, default=0.063)
    p.add_argument('--mt', type=float, default=0.078)
    p.add_argument('--mb', type=float, default=0.207)
    args = p.parse_args()

    if args.sheet:
        diagnose_from_sheet(args.sheet)
    elif args.crop and args.eski:
        diagnose_from_paths(args.crop, args.eski, args.ml, args.mr, args.mt, args.mb)
    else:
        p.print_help()


if __name__ == '__main__':
    main()
