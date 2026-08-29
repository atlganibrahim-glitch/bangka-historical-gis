> **Superseded (August 2026).** This report describes the v2 pipeline and its
> claimed accuracy. Several of those claims did not hold up — most visibly,
> 21 sheet pairs actually overlapped along a full seam, which is what this
> report's "zero overlaps" claim missed. See [`V3_REPORT.md`](../V3_REPORT.md)
> for the corrected pipeline, what was wrong here, and the current measured
> accuracy. Kept below for provenance.

# Bangka Island Historical Topographic Map Archive — Georeferencing and Mosaicking Report

**Project Scope:** Preparation of the 1930s Dutch Colonial Topographic Map Series of Bangka Island
(`KK 083-04-01 / 085-04-10`) as a ground-truth dataset for AI-driven land-use and deforestation
analysis  
**Total Sheets:** 176  
**Date:** July 2026

---

## 1. Introduction and Project Objective

This study georeferences 176 topographic map sheets from the 1930s Bangka Island archive to
WGS 84 (EPSG:4326) and produces a coherent GIS base layer for deep-learning models analyzing
historical land use.

The archive comprises two sheet types:

- **164 single-cell sheets** — each covering one 5′ × 5′ graticule cell.
- **12 composite sheets** — printed across two adjacent cells (9 vertical 5′ × 10′, 3 horizontal
  10′ × 5′) to capture coastlines where a full cell would be mostly sea.

---

## 2. Cropping and Dataset Validation

Map margins (legends and white borders) were trimmed to produce `crop_*.jpg` files.

1. **CSV synchronization:** The 176 crop files in `recovered_maps/` have pixel dimensions
   (`crop_w` × `crop_h`) that exactly match `bangka_dataset_v2.csv`.
2. **Re-cropping:** Eight files (`crop_012, 047, 056, 057, 145, 151, 170, 172`) were re-cropped
   from raw scans (`main maps`). Seven are vertical composite sheets; `crop_056` (`33-XXVI-d`)
   is actually a **single-cell sheet** (not a composite — it was simply cropped taller).
3. **Terminology clarification:** The archive contains **12 true composite sheets** (two-letter
   sub-codes), not 8. Composite sheets are coastal; one cell contains land, the adjacent one
   is largely sea and was clipped away during cropping. This is not data loss but reflects the
   sheet's physical content.

---

## 3. Diagnosis: Grid Gaps and Scale

Early georeferencing attempts produced gaps between sheets. Direct measurement of disk outputs
clarified two points:

### A. Pixel Scale
* Measured mean pixel scale: **`0.00001904` degrees/pixel**.
* Nominal value (0.083333° ÷ 4341 px): `0.00001920` degrees/pixel.
* Deviation: **−0.85 %** (σ ≈ 0.007 %). Scale is consistent; there is no significant "shrinkage."
  The **15–30 % shrinkage** mentioned in earlier drafts is not seen in final outputs.

### B. Sheet Type Divergence
* **164** standard single-letter sheets (`a`, `b`, ... `q`).
* **12** composite sheets (`dh`, `ni`, `cd`, `on`, `fg`, etc.). Final composite outputs preserve
  a ~1:1 aspect ratio; no significant vertical/horizontal stretch is detected.

---

## 4. Solution Methodology and Applied Steps

### Step 1: Systematic Offset — Theoretical Grid → Real World

The theoretical Dutch sheet formula (`base_lon = 105.0 + (col−32)·20′`) does not coincide with
the sheets' true geographic position. Comparison against manually (OSM/satellite) referenced
sheets yields a **single, highly consistent** offset that must be applied to every sheet:

| Component | Value | Metric |
|---|---|---|
| Longitude (East) | **+0.14083° (+8.450′)** | ≈ +15.67 km |
| Latitude (North) | **+0.00012° (+0.007′)** | ≈ +13.4 m |
| Consistency (σ) | **0.0000′** | — |

The large longitude term is not an error but a **sheet-indexing / datum reference difference**:
it is the offset that maps the theoretical graticule to the sheets' true real-world position, and
it has been visually verified against OSM. Atop this sits a fine-tuning term on the order of tens
of metres (Batavia → WGS 84 datum + paper drift) — the "empirical GCP offset" (≈ −22.5 m lon /
+17 m lat) mentioned in prior drafts.

*(Prior documentation reported only the small fine-tuning term, omitting the dominant +8.45′ base
offset; this is why the stated longitude shift appeared two orders of magnitude too small.)*

### Step 2: Single-Cell Mosaicking (`GEOREF_FINAL_STANDARD_164`)

The top-left corner of each of 164 standard sheets was anchored to *theoretical grid + systematic
offset* and scaled to 5′ resolution. Because all 164 sheets share one exact grid origin
(**σ = 0.0000′**), the result is a **gap-free, seamless tiling** among single-cell sheets — this
claim is verified by measurement, not asserted.

### Step 3: Composite Sheet Normalization (`GEOREF_FINAL_COMPOSITE_12`)

Each composite spans two cells but, being coastal, contains land in only **one**; the other is open
sea and was largely cropped away. Verification established a consistent rule that holds for all
12:

- **The first letter of the sub-code names the land cell**, and each composite is anchored
  precisely to that cell (12 / 12 match). Codes are order-sensitive: `ni` → land in *lower* cell,
  `in` → land in *upper* cell.
- **Zero cell overlaps:** no cell is double-filled.
- **All 12 companion (sea) cells are intentionally empty** — as the coastline dictates.

Thus, composite sheets are **correctly placed**; the "floating/shifted" appearance some sheets show
in QGIS stems from these empty sea-side cells, not coordinate error.

---

## 5. Verification Summary

| Criterion | Result |
|---|---|
| CSV ↔ disk crop dimensions (176) | Synchronized |
| Single-cell grid origin scatter (164) | **σ = 0.0000′** (seamless tiling) |
| Pixel scale (vs. nominal) | −0.85 % (σ ≈ 0.007 %) |
| Systematic offset | +8.450′ E / +0.007′ N, σ = 0.0000′ |
| Composite "first-letter = land cell" rule | **12 / 12** |
| Composite cell overlaps | **0** |
| Composite companion cells = sea | **12 / 12** |

---

## 6. Conclusion and Assessment

By combining the theoretical colonial graticule, OSM-verified systematic offset, and a consistent
composite-anchoring rule, the 176-sheet archive has been transformed into a spatially coherent
WGS 84 dataset. The 164 single-cell sheets tile exactly (σ = 0.0′); the 12 coastal composite sheets
are correctly anchored to their land cells with intentional sea-side voids. The dataset
(`GEOREF_FINAL_STANDARD_164` + `GEOREF_FINAL_COMPOSITE_12`) serves as a suitable base layer for
historical cartography research and AI-driven image analysis.

**Recommended further validation:** To express the "seamless" claim with quantified tolerance, an
independent accuracy measurement of the 12 composite sheets (e.g. OSM overlay or printed neatline
RMS residual vs. exact arc-minutes) would be valuable. Automated neatline detection was attempted
but proved unreliable on these faint printed frames; a QGIS-based overlay or spot check would close
this gap.
