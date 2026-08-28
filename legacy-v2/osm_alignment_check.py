# -*- coding: utf-8 -*-
"""
OSM Alignment Check Script
==========================
Run this in the QGIS console.

What it does:
  Compares the coordinate of a known OSM point (road junction, coastline
  coordinate, etc.) as it appears on the map with its true WGS84 coordinate,
  to compute the systematic shift.

Usage:
  1. Open a map layer in QGIS (GEOREF_FINAL_STANDARD_164)
  2. Find a point you can identify on OSM
     (e.g. a road junction, village, coastal cape)
  3. Read that point's coordinate from the QGIS coordinate bar,
     both on the map and on OSM
  4. Fill in the values below and run
"""
import math

# === ENTER HERE ===
# Pick a point on the map; read it from the QGIS coordinate bar
# while the cursor is over that point:

# Visible location on the georeferenced map (GEOREF_FINAL_STANDARD_164)
MAP_LON = 106.123  # example - change this!
MAP_LAT = -2.456   # example - change this!

# True coordinate of the same physical point on OSM/Google
# (on OSM: right-click -> "Copy this location", or from the coordinate bar)
TRUE_LON = 106.125  # example - change this!
TRUE_LAT = -2.453   # example - change this!
# ====================

delta_lon = TRUE_LON - MAP_LON
delta_lat = TRUE_LAT - MAP_LAT

# Convert to meters (approximate, at Bangka's latitude)
M_PER_DEG_LON = 111320 * abs(math.cos(math.radians(-2.0)))  # cos(-2 deg)
M_PER_DEG_LAT = 111320

# Simple computation
cos_lat = math.cos(math.radians(MAP_LAT))
dx_m = delta_lon * 111320 * cos_lat
dy_m = delta_lat * 111320

print("=" * 55)
print("OSM ALIGNMENT CHECK")
print("=" * 55)
print(f"  Coordinate on map : {MAP_LON:.6f}, {MAP_LAT:.6f}")
print(f"  True coordinate   : {TRUE_LON:.6f}, {TRUE_LAT:.6f}")
print()
print(f"  dLon : {delta_lon:+.6f} deg ({dx_m:+.1f} m East)")
print(f"  dLat : {delta_lat:+.6f} deg ({dy_m:+.1f} m North)")
print()
print(f"  Total shift : {math.sqrt(dx_m**2 + dy_m**2):.1f} m")
bearing = math.degrees(math.atan2(dx_m, dy_m))
print(f"  Bearing     : {bearing:.1f} deg (0=N, 90=E, 180=S, 270=W)")
print()
if abs(dx_m) < 100 and abs(dy_m) < 100:
    print("[OK] Shift < 100m - Georeferencing is good enough!")
elif abs(dx_m) < 500 and abs(dy_m) < 500:
    print("[WARN] Shift between 100-500m - Datum difference or georef error")
else:
    print("[ERROR] Shift > 500m - Large error, datum transform may be needed")
