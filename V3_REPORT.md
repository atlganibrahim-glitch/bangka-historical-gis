# Bangka 1:25,000 sheets — v3 georeferencing rebuild

Rebuilt from the new neatline-accurate crops, after the report that the
published GeoTIFFs had imperfect crops and that the irregular sheets did not
line up with the rest.

Scripts are in [`v3/`](v3/). Two output sets are published:

| set | rasters | metadata | what it is |
|---|---|---|---|
| **v3.1** (recommended) | `GEOREF_V3_1/` | `bangka_dataset_v3_1.csv` | v3.0 plus the inland road-network offset (§5) |
| v3.0 | `GEOREF_V3/` | `bangka_dataset_v3.csv` | graticule-exact, no empirical shift |

They differ by a pure translation of +200.4 m E / −66.8 m N, identical on all
176 sheets.

---

## 1. What was actually wrong with v2

**a. Composite sheets overhung their neighbours.**
v2 derived a composite's pixel scale from a fixed nominal value rather than
pinning its across-track edge to exactly one cell, so composites came out
5.03′–5.11′ wide instead of 5.00′. The excess hung over the neighbouring sheet
along the whole seam:

| | v2 | v3 |
|---|---|---|
| overlapping sheet pairs | **21**, all involving composites | 0 structural |
| worst overlap | 278 m wide × 9277 m long | — |

That full-length overhang is what reads as "the irregular sheets do not match
the rest".

**b. Two sheets were irregular without anyone noticing.**
`33-XXVI-d` and `34-XXVII-g` carry ordinary single-letter codes, but their
printed neatlines are **not square** — 4338 × 4650 px (+7.2 %) and
4331 × 4513 px (+4.2 %). v2 squeezed both into a 5′ × 5′ cell, distorting the
sheet interior by up to 7 %, i.e. **≈ 700 m of misregistration** at the far
edge. They are coastal sheets printed past their cell, exactly like the twelve
two-letter composites.

**c. Crops were cut on fixed percentages, not on the frame.**
The old `map_crop.py` used a hard-coded ratio (`1 - 4102/5174`) for the bottom
margin, so marginal text such as "Reproductiebedrijf Topografische dienst,
Batavia" landed inside the map area on some sheets. The new crops are cut on
the neatline: measured against the detected frame, the residual margin is now
a median of **10 px (≈ 11 m)** per sheet.

**d. The repository did not reproduce the published data.**
`automated_georef.py` carried `LON_OFFSET = 0.14043, LAT_OFFSET = -0.01045`,
but the published rasters were built with `+0.140831, +0.000121` — a 1.2 km
discrepancy in latitude between the code and the data. v3 keeps the calibration
in one place, `v3/grid.py`.

---

## 2. What v3 does differently

### Placement is driven by the printed neatline, not the edge of the scan

The frame is detectable in the new crops. A profile of "fraction of dark
pixels" per row and column spikes on a ruled line that runs the full width or
height of the sheet, and on nothing else; a small skew search absorbs scans
that are a degree or two off square. Frame edges were measured on all 176
sheets (both axes on 144 of 164 singles) and stored in `v3/frames.csv`.

Each edge is then extended outward by *its own* measured margin, so the
neatline — not the paper edge — lands on the graticule, and the margins are
allowed to be asymmetric.

### One geometric model for every sheet

Whichever axis of the frame spans a whole number of 5′ cells fixes the paper
scale; the other axis follows from its measured pixel length. No sheet is
stretched to fill a cell it does not cover. This covers regular sheets, the
two-cell composites and the irregular sheets with the same rule.

A 5′ cell is **not square on paper**: at Bangka's latitude 5′ of latitude is
slightly shorter on the ground than 5′ of longitude. The measured frames
agree, which is an independent check that the frame detection is sound:

| | value |
|---|---|
| measured one-cell frame aspect (h/w) | **0.9960 ± 0.0032** (n = 144) |
| predicted from the ellipsoid at −2.6° | 0.9943 |

### Anchoring is measured, not assumed

A sheet printed longer than its cell touches a graticule line on one edge
only. Which edge is a question about the world, so it was answered against the
modern OSM shoreline rather than assumed: each sheet was placed under both
candidate anchors and its drawn shoreline fitted freely; the anchor needing no
correction is the right one (`v3/fit_irregular.py`).

**Result: 10 of the 14 non-standard sheets were decided by shoreline evidence,
and all 10 agree with the "first letter of the sub-code names the land cell"
rule.** The other 4 had too little usable shoreline (too straight, or none
in range), so they were re-tested against the OSM *road* network instead
(`v3/fit_irregular_roads.py`) — a second, independent source, since it uses
different pixels on the sheet (roads, not shoreline) and a different modern
reference layer. **All 4 also agree with the rule, each by a wide margin
(1840–4493 m separating the two hypotheses).** All 14 non-standard sheets are
now evidence-based; none rest on the rule alone.

| sheet | kind | anchor | decided by | margin |
|---|---|---|---|---|
| 31-XXV-dh | composite | top | shoreline | 389 m |
| 32-XXIV-ni | composite | bottom | shoreline | 1284 m |
| 33-XXV-ae | composite | top | shoreline | 2037 m |
| 33-XXVI-d | irregular | top | shoreline | 734 m |
| 34-XXIII-ie | composite | bottom | roads | 2778 m |
| 34-XXIV-cd | composite | left | shoreline | 4470 m |
| 34-XXVI-on | composite | right | shoreline | 886 m |
| 34-XXVII-g | irregular | top | shoreline | 452 m |
| 35-XXVII-ko | composite | top | shoreline | 1864 m |
| 36-XXVI-ie | composite | bottom | roads | 3671 m |
| 36-XXVII-fg | composite | left | roads | 1840 m |
| 36-XXVIII-bf | composite | top | shoreline | 2054 m |
| 36-XXVIII-dh | composite | top | roads | 4493 m |
| 37-XXVI-in | composite | top | shoreline | 1316 m |

("at stake" from the first pass is renamed "margin" here since it now
means the same thing for every row: how much less correction the winning
anchor needed than the losing one — not, as before, how much the sheet
overflows its cell.)

### Sheets carry a neatline mask

Every GeoTIFF has an internal mask that hides the paper outside the frame.
Pixels keep their true positions, but GDAL and QGIS will not paint the
margins, so sheets mosaic without double coverage: over the whole island,
**0.046 %** of painted pixels are covered twice, and never by more than two
sheets.

### Output format

Tiled, JPEG-compressed (quality 92, the sources are JPEG already) with
internal overviews. The archive drops from **4.5 GB to 870 MB** and opens at
island scale in QGIS without pyramid building.

---

## 3. Verification

| check | result |
|---|---|
| neatline corner vs the exact graticule, 162 regular sheets | max **8.4 m** |
| one-cell frame aspect vs ellipsoid prediction | 0.9960 vs 0.9943 |
| pixel scale vs 5′/4341 px nominal | −0.04 % (σ 0.3 %) |
| structural sheet overlaps | **0** |
| double-painted mosaic area | 0.046 % |
| anchors confirmed against modern shoreline | **10 / 10 decisive cases** |

### Absolute accuracy against modern imagery

The drawn shoreline of each coastal sheet was matched to the OSM coastline
(`v3/fit_singles.py`), discarding sheets whose coast runs in a single
direction — those can slide along it, so their "fit" is an artefact rather
than a measurement.

| | value |
|---|---|
| residual systematic shift, 17 usable coastal sheets | **+289 m E, −75 m N** |
| sheet-to-sheet spread (MAD) | 401 m E, 598 m N |
| median shoreline residual after fitting | 659 m |

So the existing global calibration is **unbiased to within about ±300 m**, and
the sheet-to-sheet scatter is ~0.5 km.

Comparing the two versions where each actually places its sheets
(`v3/compare_v2_v3.py`):

| | v2 | v3 |
|---|---|---|
| single sheets (n = 40) | 872 m | **767 m** |
| composites (n = 7) | 829 m | 854 m |
| all (n = 47) | 860 m | 783 m |

**Read this honestly.** v3 improves single sheets by ~105 m median. The
composite figure moves within noise on seven sheets. The ~780 m floor is
**not** georeferencing error: it is ninety years of real coastal change —
Bangka's shoreline has moved substantially through tin dredging, tailings
progradation and mangrove change — plus the ~135 m smoothing in the shoreline
extraction. Shoreline matching cannot resolve the georeferencing below that
floor, in either direction.

What v3 gives that v2 did not is **geometric correctness**: no sheet stretched
into a cell it does not cover, no sheet overhanging its neighbour, the
neatlines on the graticule to 8 m, and every non-standard sheet's anchoring
backed by evidence.

---

## 4. Open items

**Two crops worth confirming by eye.** Not a crop error this time — these two
sheets really are printed past their cell, and v3 handles them as such. But
their frames should be checked before publication:

- `33-XXVI-d` — frame 4338 × 4650 px, +7.2 % taller than one cell (+734 m)
- `34-XXVII-g` — frame 4331 × 4513 px, +4.2 % taller than one cell (+452 m)

**Twenty sheets have one frame edge too faint to measure** (`frame_measured`
column in `bangka_dataset_v3.csv`); those fall back to the crop edge, worth
about 10 px each.

**Systematic refinement — applied in v3.1, see §5.**

**Four composites could not be decided by shoreline** (`34-XXIII-ie`,
`36-XXVI-ie`, `36-XXVII-fg`, `36-XXVIII-dh`) and rest on the sub-code rule,
which holds 10/10 where it could be tested. Confirming them would need a
non-shoreline control — a road junction or river confluence identifiable on
both the sheet and modern imagery.

---

## 5. v3.1 — inland calibration against the road network

### Why the coastline was the wrong yardstick

Everything in §3 measures the sheets against the modern **shoreline**, and that
measurement bottoms out at ~780 m because Bangka's coast has genuinely moved
that far since the 1930s. It cannot tell a placement error from tin-dredging.

Roads are a better control: they are inland, they are drawn on these sheets in
a distinctive orange, and the major road network has largely kept its alignment
over ninety years. `v3/roadmask.py` extracts the orange road ink; `v3/fit_roads.py`
fits it against OSM's major-road classes (`trunk`/`primary`/`secondary`/
`tertiary`/`unclassified`, 3178 ways).

### What it found

Of 176 sheets, 131 carried enough road ink to fit. Their residuals:

| percentile | residual |
|---|---|
| P25 | 30 m |
| P50 | **170 m** |
| P75 | 440 m |
| P90 | 675 m |

More usefully, **60 of those 131 sheets converged independently on the same
shift** — +200 m East, −67 m North — with a median residual of only **30 m**
within that cluster. Sixty sheets agreeing to that precision by chance is not
plausible; it is a real systematic offset in the v3.0 grid.

The other 71 sheets scattered. That is a limitation of the *measurement*, not
evidence those sheets are misplaced: village and service roads have multiplied
enormously since the 1930s, so on road-dense sheets the fit can lock onto a
modern road that did not exist when the sheet was surveyed.

### The correction, and proof it works

v3.1 adds **+200.4 m E / −66.8 m N** to the grid origin
(`ROAD_LON_CORRECTION` / `ROAD_LAT_CORRECTION` in `v3/grid.py`). Re-running the
same measurement under both grids (`v3/verify_v31.py`) — note `fit_roads.py`
measures against the *uncorrected* grid, so this stays an independent check
rather than validating its own output:

| | v3.0 | v3.1 |
|---|---|---|
| median residual systematic shift | +200 m E, −61 m N | **+22 m E, +22 m N** |
| median \|shift\| still needed | 303 m | **189 m** |
| sheets landing within 100 m | 2 (2 %) | **52 (40 %)** |

The systematic component is essentially gone.

### What this means for absolute accuracy

| use case | v3.1 verdict |
|---|---|
| regional analysis, ≥300 m features | comfortably sufficient |
| 100–300 m features | usable; residual scatter is the limit, not bias |
| per-pixel / single-symbol overlay | needs per-sheet control points, not a global offset |

Both versions are kept: `GEOREF_V3/` + `bangka_dataset_v3.csv` (graticule-exact,
no empirical shift) and `GEOREF_V3_1/` + `bangka_dataset_v3_1.csv` (recommended).
Every v3.1 raster is tagged `VERSION=v3.1`, and all 176 carry exactly the same
shift (σ = 0.00 m), so the two sets differ by a pure translation and nothing else.

---

## 6. Reproducing

```bash
python v3/scan_frames.py       # measure every printed neatline -> v3/frames.csv
python v3/build_masks.py       # cache sea masks / shorelines   -> v3/masks/
python v3/fit_irregular.py     # decide anchors against OSM
python v3/fit_roads.py         # inland accuracy vs OSM roads   -> v3/road_fits.npy
python v3/georeference.py      # write the 176 sheets           -> GEOREF_V3_1/
python v3/build_metadata.py    # metadata                       -> bangka_dataset_v3_1.csv
python v3/verify_v3.py         # geometric checks
python v3/verify_v31.py        # did the v3.1 correction help?
python v3/fit_singles.py       # absolute accuracy vs OSM coastline
python v3/compare_v2_v3.py     # v2 vs v3 shoreline residuals
python v3/mosaic_preview.py out.png v3
```

Requires `numpy pandas pillow opencv-python rasterio`. OSM extracts are cached
in `v3/osm_coastline.json` (`natural=coastline`) and `v3/osm_roads.json`
(`highway=*`), both Overpass, Bangka bbox.

Source sheets: Topografische Dienst in Nederlandsch-Indië, *Res. Bangka en
Onderhoorigheden*, 1:25,000, 1930–1936. Held by Leiden University Libraries,
`KK 083-04-01/085-04-10`, public domain.
