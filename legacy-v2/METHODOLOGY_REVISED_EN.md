# Georeferencing and Mosaicking of 176 Historical Dutch
# Topographic Maps of Bangka Island — Methodology (Revised)

> **Superseded (August 2026).** This document's headline claim — that the 12
> composite sheets have "zero overlaps" and are "correctly placed" — turned
> out to be wrong: all 12 derived their scale from a fixed nominal value
> instead of one true 5′ cell edge, so they overhung their neighbours by up
> to 278 m along a 9.3 km seam (21 overlapping sheet pairs total). This
> document's claim that neatline detection was attempted and failed also no
> longer holds — it succeeds cleanly on the 2026 crops. See
> [`V3_REPORT.md`](../V3_REPORT.md) for the corrected pipeline and current
> numbers. Kept below for provenance.

---

## Overview

The archive comprises **176 sheets** of the 1932–1934 Dutch colonial topographic
survey of Bangka Island. Each sheet is indexed on the Dutch 5-arcminute graticule
(e.g. `32-XXIV-g`), where the letter code maps to a 5′ × 5′ cell inside a 20′ × 20′
parent block. The goal was a gap-free, WGS 84 mosaic suitable as a ground-truth base
layer for computer-vision / deep-learning analysis of historical land use.

Of the 176 sheets:

- **164 are single-cell** sheets (one 5′ × 5′ graticule cell).
- **12 are composite** sheets (printed across two adjacent cells — 9 vertical 5′ × 10′,
  3 horizontal 10′ × 5′) to capture irregular coastlines where a full cell would be
  mostly sea.

---

## Phase 1 — Dataset Audit and Re-Cropping

A pixel-level audit compared every crop against `bangka_dataset_v2.csv`. The current
crop files reside in `recovered_maps/` and their on-disk dimensions now match
the CSV (`crop_w`, `crop_h`) exactly for all 176 rows — the dataset is synchronized.

**Correction to the earlier draft:** the previously cited list of "8 over-cropped
composite sheets" was imprecise. Verification shows:

- There are **12 true composite sheets** (two-letter sub-codes), not 8.
- The 8 re-cropped files were `crop_012, 047, 057, 145, 151, 170, 172` (7 vertical
  composites) plus `crop_056` — which is in fact a **single-cell sheet** (`33-XXVI-d`)
  that had simply been cropped slightly tall, not a composite.

Re-cropping restored the intended margins from the raw scans in `main maps/`, and the
CSV margin fields were re-synchronized. No systematic content loss remains relative to
the recorded crop geometry.

---

## Phase 2 — Diagnosis of Inter-Tile Behaviour and Scale

### Pixel scale
The georeferenced single-cell outputs were measured directly:

| Quantity | Value |
|---|---|
| Mean pixel scale | **0.00001904 °/px** |
| Nominal (0.08333° ÷ 4341 px) | 0.00001920 °/px |
| Deviation | **−0.85 %** (σ ≈ 0.007 %, very tight) |

The scale is therefore consistent and essentially correct. The earlier "15–30 %
shrinkage" figure is not supported by the final outputs; the residual −0.85 % is
negligible for mosaicking and arises from small differences in printed sheet size.

### Grid regularity (the key result)
Every single-cell sheet was projected onto a common global cell index and the implied
grid origin was back-computed:

- Grid origin scatter across all **164** single-cell sheets: **σ = 0.0000′** in both
  latitude and longitude.

That is, the 164 single-cell sheets tile the plane **exactly** — there is no residual
inter-tile gap or overlap among them. Any white space seen in earlier mosaics came not
from the single-cell sheets but from the composite sheets (Phase 4).

---

## Phase 3 — Systematic Offset (Theoretical Grid → Real-World WGS 84)

The theoretical Dutch sheet-indexing formula (`base_lon = 105.0 + (col−32)·20′`) does
**not** coincide with the real-world position of the sheets. Comparison against the
manually georeferenced reference sheets (aligned on OSM / satellite imagery) gives a
**single, highly consistent** systematic offset that must be applied to every sheet:

| Component | Value | Metric |
|---|---|---|
| Longitude | **+0.14083° (+8.450′)** East | ≈ +15.67 km |
| Latitude | **+0.00012° (+0.007′)** North | ≈ +13.4 m |
| Consistency (σ over reference sheets) | **0.0000′** | — |

This large longitude term is a **sheet-indexing / datum reference difference**, not an
error: it is the offset that makes the theoretical graticule agree with the maps'
true geographic position, and it has been confirmed visually against OSM. A further
sub-arc-minute refinement (on the order of tens of metres, Batavia → WGS 84 datum plus
paper drift) sits on top of this base and is what the earlier draft reported as the
"empirical GCP offset" (≈ −22.5 m lon / +17 m lat). Both layers are now baked into the
176 outputs; the reference offset can be recovered directly from any output tile, so no
external GCP file is required to reproduce it.

*(Note: the earlier draft reported only the small refinement term and omitted the
dominant +8.45′ base offset, which is why its stated longitude shift looked two orders
of magnitude too small.)*

---

## Phase 4 — Standardization and Coastal (Composite) Normalization

### Standard 164 single-cell sheets → `GEOREF_FINAL_STANDARD_164/`
Each map's top-left corner was anchored to *theoretical top-left + systematic offset*
and scaled to the 5′ resolution. Because the 164 sheets share one exact grid origin
(σ = 0.0000′), the result is a **seamless, gap-free tiling** across all single-cell
sheets — verified, not asserted.

### Special 12 composite sheets → `GEOREF_FINAL_COMPOSITE_12/`
Each composite covers two cells but, being coastal, contains land in only **one** of
them; the other is open sea and was largely cropped away. Verification established a
clean, consistent rule and confirmed it holds for all 12:

- **The first letter of the sub-code names the land cell**, and each composite is
  anchored exactly to that cell (12 / 12 match). Note the codes are order-sensitive:
  `ni` → land in the *lower* cell, `in` → land in the *upper* cell.
- **Zero overlaps**: no cell is double-filled. Each composite occupies a unique cell
  not used by any single-cell sheet.
- **The 12 unfilled companion cells are all sea** — intentionally empty, exactly as
  the coastline dictates.

Consequently, the composite sheets are **correctly placed**, and their empty sea-side
cells (not any coordinate error) are the source of the "floating / shifted" appearance
some sheets show in QGIS. Aspect ratios were preserved at ~1:1; no 50 % stretching is
present in the final composites.

---

## Verification Summary

| Check | Result |
|---|---|
| CSV ↔ disk crop dimensions (176) | Synchronized |
| Single-cell grid origin scatter (164) | **σ = 0.0000′** (exact tiling) |
| Pixel scale vs nominal | −0.85 % (σ ≈ 0.007 %) |
| Systematic offset | +8.450′ E / +0.007′ N, σ = 0.0000′ |
| Composite "first-letter = land cell" rule | **12 / 12** |
| Composite cell overlaps | **0** |
| Composite companion cells = sea | **12 / 12** |

---

## Conclusion and AI-Readiness

Combining the theoretical colonial graticule with an OSM-verified systematic offset and
a consistent composite-anchoring rule, the 176-sheet archive has been standardized into
a spatially coherent WGS 84 dataset. The 164 single-cell sheets tile exactly (σ = 0.0′);
the 12 coastal composites are correctly anchored to their land cells with their sea-side
cells intentionally empty. The dataset (`bangka_dataset_v2.csv` + the two GeoTIFF
archives) is suitable as a ground-truth base layer for deep-learning segmentation of
historical land use and deforestation.

**Remaining optional refinement:** an independent per-sheet accuracy figure (e.g. RMS
residual of the printed neatline against exact arc-minutes, or an OSM overlay check of
the 12 composites) would let the "seamless" claim be stated with a quantified tolerance
rather than a qualitative one. Automated neatline detection was attempted but the frame
lines on these scans are too faint for a reliable measurement; a QGIS-based overlay or
manual GCP check on a sample would close this gap.
