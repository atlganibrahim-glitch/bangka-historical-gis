# -*- coding: utf-8 -*-
import os, sys
from osgeo import gdal
gdal.UseExceptions()

# v2-era script; moved into legacy-v2/ during the v3 reorganisation.
# GEOREF_FINAL_STANDARD_164/ stayed at the true repo root.
FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "GEOREF_FINAL_STANDARD_164")

# Check the coordinates of the first few GeoTIFFs
files = sorted([f for f in os.listdir(FOLDER) if f.endswith('.tif')])[:5]

for file in files:
    path = os.path.join(FOLDER, file)
    ds = gdal.Open(path)
    if ds:
        gt = ds.GetGeoTransform()
        w = ds.RasterXSize
        h = ds.RasterYSize
        left  = gt[0]
        top   = gt[3]
        right = gt[0] + gt[1]*w
        bottom = gt[3] + gt[5]*h
        print(f"{file}: Left={left:.5f}, Top={top:.5f}, Right={right:.5f}, Bottom={bottom:.5f}")
        ds = None
    else:
        print(f"{file}: COULD NOT OPEN")
