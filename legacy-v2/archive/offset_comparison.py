# -*- coding: utf-8 -*-
"""
Compare OLD (with legend) and NEW (cropped) GeoTIFF coordinates.
Compute the offset difference between them.
"""
import os
from osgeo import gdal
gdal.UseExceptions()

BASE = os.path.dirname(os.path.abspath(__file__))
OLD = os.path.join(BASE, "GEOREF_FINAL_STANDARD_164")
NEW = os.path.join(BASE, "GEOREF_FINAL_STANDARD_164")

old_files = set(f for f in os.listdir(OLD) if f.endswith('.tif') and not f.endswith('.aux.xml'))

print(f"{'Sheet':25} {'OLD Left':>12} {'OLD Top':>12} {'NEW Left':>12} {'NEW Top':>12} {'dLon':>10} {'dLat':>10}")
print("-"*100)

offsets_lon = []
offsets_lat = []

for file in sorted(old_files):
    old_path = os.path.join(OLD, file)
    new_path = os.path.join(NEW, file)

    if not os.path.exists(new_path):
        continue

    ds_o = gdal.Open(old_path)
    ds_n = gdal.Open(new_path)

    if not ds_o or not ds_n:
        continue

    gt_o = ds_o.GetGeoTransform()
    gt_n = ds_n.GetGeoTransform()

    old_left = gt_o[0]
    old_top = gt_o[3]
    new_left = gt_n[0]
    new_top = gt_n[3]

    d_lon = old_left - new_left
    d_lat = old_top - new_top

    offsets_lon.append(d_lon)
    offsets_lat.append(d_lat)

    print(f"{file:25} {old_left:12.6f} {old_top:12.6f} {new_left:12.6f} {new_top:12.6f} {d_lon:10.6f} {d_lat:10.6f}")

    ds_o = None
    ds_n = None

if offsets_lon:
    print("\n" + "="*100)
    print(f"Mean LON difference: {sum(offsets_lon)/len(offsets_lon):+.6f} degrees")
    print(f"Mean LAT difference: {sum(offsets_lat)/len(offsets_lat):+.6f} degrees")
    print(f"Min/Max LON difference:  {min(offsets_lon):.6f} / {max(offsets_lon):.6f}")
    print(f"Min/Max LAT difference:  {min(offsets_lat):.6f} / {max(offsets_lat):.6f}")
