# Changelog

## v3 / v3.1 (August 2026)
Full rebuild from new neatline-accurate crops, prompted by a report that the
published v2 GeoTIFFs had imperfect crops and that the composite sheets did
not align with their neighbours. Root cause, fix, and measured accuracy are
in [`V3_REPORT.md`](V3_REPORT.md); summary:

- Composite sheets no longer overhang their neighbours (21 overlapping pairs
  in v2 → 0 in v3).
- 2 single-letter sheets found to be irregular (not full 5′ cells) and fixed
  the same way as the composites.
- Every non-standard sheet's anchor edge (which side sits on the graticule)
  is now backed by measurement against OSM (shoreline or road network), not
  assumed from the sub-code rule alone.
- v3.1 adds a small measured inland correction (+200.4 m E / −66.8 m N).
- New pipeline: [`v3/`](v3/). New metadata: `bangka_dataset_v3.csv` /
  `bangka_dataset_v3_1.csv`, plus a per-sheet positional-quality table,
  `bangka_sheet_quality.csv`.
- `bangka_dataset_v2.csv` (below) is unaffected — the v3 rebuild used the new
  crops directly, not this CSV's margin values.

## bangka_dataset_v2.csv
Updated/corrected version of the original `bangka_dataset.csv` (which was
provided as source material by Thomas Smits; original compiler undocumented).
The original now lives in [`archive/bangka_dataset.csv`](archive/bangka_dataset.csv).

### Corrections applied
_All figures below are the actual diff between `archive/bangka_dataset.csv` and
`bangka_dataset_v2.csv`._

- **Rows:** 176 → 176 (no sheets added or removed).
- **Sheet IDs:** identical set, no duplicates in either file; no `sheet_id` renamed.
- **Columns:** identical (17 columns; none added, removed, or renamed).
- **Changed cells:** 1037 in total, confined to the crop-geometry columns.
  All other columns (`image_idx`, `label`, `filename`, `width_px`, `height_px`,
  `year`, `method`, `instrument`, `crop_filename`, `crop_w`) are unchanged.

| Column | Sheets changed | mean \|Δ\| | max \|Δ\| | Notes |
|--------|---------------:|-----------:|----------:|-------|
| `margin_bottom` | 176 / 176 | 0.00357 | 0.03200 | Largest correction; range tightened from `[0.175, 0.210]` to `[0.2065, 0.2078]` |
| `margin_left`   | 176 / 176 | 0.00025 | 0.00090 | Fine per-sheet adjustment |
| `margin_right`  | 175 / 176 | 0.00026 | 0.00084 | Fine per-sheet adjustment |
| `margin_top`    | 175 / 176 | 0.00020 | 0.00067 | Fine per-sheet adjustment |
| `crop_h`        | 168 / 176 | 16.9 px  | 19 px    | Recomputed crop height |
| `pct_retained`  | 167 / 176 | 0.29     | 0.30     | Recomputed from the corrected crop |

- **Nature of the change:** the original table used a handful of **nominal,
  constant** margin values (5–10 distinct values per margin column, e.g. a flat
  `margin_left = 0.07`). v2 replaces these with **per-sheet measured** values
  (68–91 distinct values per column), derived by matching each cropped image
  against its full reference sheet (see `recalc_margins.py`).

### How errors were identified
<!-- Owner to fill: e.g. inconsistencies surfaced during georeferencing /
     verify_georef.py flagged sheets that failed tiling checks -->
