# Bangka Island 1930s Historical Topographic Map Dataset (176 Sheets) & Georeferencing Pipeline

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Dataset Size](https://img.shields.io/badge/Dataset-176%20Sheets-brightgreen.svg)
![GIS](https://img.shields.io/badge/GIS-QGIS%20%7C%20GDAL-orange.svg)
[![Hugging Face Dataset](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Dataset-yellow.svg)](https://huggingface.co/datasets/ibrahimatlgn/bangka-1930s-topographic-maps)

Georeferences 176 sheets of the **1930s Dutch Colonial Topographic Map
Series of Bangka Island** (`KK 083-04-01/085-04-10`) into WGS 84 (EPSG:4326)
GeoTIFFs, as a ground-truth base layer for deep-learning analysis of
historical land use.

**Current version: v3.1.** It replaces v2, which had a real bug — composite
sheets overhung their neighbours by up to 278 m along a 9.3 km seam.
Everything about what changed and why is in **[`V3_REPORT.md`](V3_REPORT.md)**
— read that first. The old v2 material is kept in [`legacy-v2/`](legacy-v2/)
for provenance only; don't use it.

![The 176 sheets over OpenStreetMap](figures/osm_overlay.png)
*All 176 sheets in their v3.1 positions, over OpenStreetMap. Basemap ©
OpenStreetMap contributors (ODbL).*

![v2 vs v3 at a composite seam](figures/seam_v2_v3.png)
*The bug, visualised: the same seam in v2 (left) and v3 (right). Red marks
where two sheets paint the same ground.*

## Quick Start

```python
import sys
sys.path.insert(0, "v3")
import sheet_to_wgs84 as geo

lon, lat = geo.pixel_to_lonlat("34-XXV-e", x=1200, y=850)   # -> WGS 84 coordinate
```

Or in QGIS: build a VRT over `GEOREF_V3_1/*/*.tif` (`gdalbuildvrt`) and add it
as one layer. Get the rasters from Hugging Face (below); full reproduction
steps are in `V3_REPORT.md`.

## Dataset Composition

- **162 single-cell sheets** — one 5′ × 5′ graticule cell each.
- **12 composite sheets** — printed across two adjacent cells, to capture
  coastlines where a full cell would be mostly sea.
- **2 irregular sheets** (`33-XXVI-d`, `34-XXVII-g`) — plain-looking codes,
  but printed past their cell like the composites.

## Key Results (v3.1 — see `V3_REPORT.md` for method and full numbers)

- **Neatline placement.** Every sheet is placed by its printed frame, not the
  scan edge — max 8.4 m off the exact graticule.
- **No structural overlaps.** 0 overlapping sheet pairs (v2 had 21).
- **Evidence-based anchoring.** All 14 non-standard sheets have their anchor
  edge confirmed against OSM (shoreline or roads), not assumed.
- **Inland accuracy** (vs OSM roads, which move far less than the coastline):
  median residual 170 m, down to 30 m on a well-fit subset.
- **Coastal accuracy** bottoms out around 780 m — that's mostly 90 years of
  real coastline change, not georeferencing error (details in the report).

**Before relying on these numbers, read
[`ACCURACY_ASSESSMENT.md`](ACCURACY_ASSESSMENT.md).** It sets out what each
test does and does not establish — in particular that only about 30% of the
island's land area has been independently verified, and that the rest is
unmeasured rather than known-good.

## Getting the Data

**📦 https://huggingface.co/datasets/ibrahimatlgn/bangka-1930s-topographic-maps**

```python
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="ibrahimatlgn/bangka-1930s-topographic-maps",
    repo_type="dataset",
    local_dir="bangka_data",
    allow_patterns=["GEOREF_V3_1/*", "bangka_dataset_v3_1.csv",
                    "bangka_sheet_quality.csv"],
)
```

The rasters are plain GeoTIFF in WGS 84 — any GIS reads them directly. Each
carries an internal mask that hides the paper outside the printed neatline,
so sheets mosaic without double coverage. In QGIS: `Layer → Add Raster Layer`,
or build one VRT over the whole folder for a single merged layer (much
faster than 176 individual layers).

Converting detection pixel coordinates to WGS 84 (e.g. from a model run on
the crops): use `v3/sheet_to_wgs84.py`.

## Data Provenance & Source

**"Res. Bangka en Onderhoorigheden"**, scale 1:25,000, surveyed 1930–1936 by
the Topografische Dienst in Nederlandsch-Indië. Digitized and held by
**Leiden University Libraries** (`KK 083-04-01/085-04-10`, public domain,
[hdl.handle.net/1887.1/item:2078333](http://hdl.handle.net/1887.1/item:2078333)).
Citing Leiden University Libraries as the source is requested.

The original metadata table and the neatline-accurate crops the v3 rebuild
is built from were supplied by Thomas Smits (supervisor). The georeferencing
pipeline and the accuracy metrics are the repository owner's own work.

## Repository Structure

```text
bangka-historical-gis/
├── README.md                 # This file
├── V3_REPORT.md              # How the sheets were built — start here
├── ACCURACY_ASSESSMENT.md    # How far the result can be trusted, and where it can't
├── CONTROL_POINTS_HOWTO.md   # Procedure for extending the manual accuracy check
├── CHANGELOG.md
├── bangka_dataset_v3_1.csv   # Current metadata (176 sheets) — use this
├── bangka_sheet_quality.csv  # Per-sheet positional confidence + land area
├── environment.yml
│
├── v3/                        # Pipeline — see V3_REPORT.md to run it
│   ├── grid.py                #   sheet geometry: crop pixels -> WGS 84
│   ├── georeference.py        #   writes the 176 GeoTIFFs
│   ├── sheet_to_wgs84.py      #   pixel -> lon/lat helper
│   ├── bangka_dataset_v3.csv  #   metadata for the *uncorrected* v3.0 (not v3.1) — see V3_REPORT.md
│   └── ...                    #   accuracy tests, verification, figures
│
├── figures/                   # Regenerate with v3/make_figures.py
├── qgis/                      # Portable QGIS layers (.geojson, .gpkg)
│
└── legacy-v2/                 # Superseded — see legacy-v2/README.md

(not tracked in git — see .gitignore)
GEOREF_V3_1/, new_crops/, main maps/, recovered_maps/,
GEOREF_FINAL_STANDARD_164/, GEOREF_FINAL_COMPOSITE_12/
```

## Reproducing the Pipeline

Only needed if you want to rebuild the GeoTIFFs yourself — not to use them.

```bash
conda env create -f environment.yml
conda activate bangka-gis
```

```bash
# Run from the repository root. Expects the crops in new_crops/map/*.jpg.
python v3/fetch_osm.py            # OSM coastline + roads for the accuracy checks below
python v3/scan_frames.py          # measure every printed neatline
python v3/build_masks.py          # cache sea masks / shorelines
python v3/fit_irregular.py        # decide composite/irregular anchors vs OSM shoreline
python v3/fit_irregular_roads.py  # same, vs OSM roads, for the rest
python v3/georeference.py         # write the 176 GeoTIFFs -> GEOREF_V3_1/
python v3/build_metadata.py       # -> bangka_dataset_v3_1.csv
python v3/sheet_quality.py        # -> bangka_sheet_quality.csv
```

Full details, including the v2 pipeline (superseded, not recommended), are
in `V3_REPORT.md` and `legacy-v2/README.md`.

## Known Limitations

- 4 of the 14 non-standard sheets' anchors were confirmed via OSM roads
  rather than the shoreline (which wasn't usable there) — see `V3_REPORT.md`
  for which ones.
- Coastal accuracy can't be measured below ~780 m against modern imagery,
  because the coastline itself has moved that much since the 1930s. Inland
  features (roads, buildings) are the better accuracy proxy.
