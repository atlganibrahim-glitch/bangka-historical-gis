# archive/ — Experimental & Superseded Scripts

> This whole tree (`legacy-v2/archive/`) is nested inside
> [`legacy-v2/`](../), the v2-era material superseded by v3 — see
> [`../../V3_REPORT.md`](../../V3_REPORT.md) for the current pipeline.

These scripts are **reference material only**. They are *not* part of the
v2 pipeline itself (see the scripts one level up in `legacy-v2/` and
the phase-by-phase description in [`../METHODOLOGY_REVISED_EN.md`](../METHODOLOGY_REVISED_EN.md)).
They are kept for transparency — mainly to document how the systematic offset was
explored and why the grid-line auto-detection approach was ultimately not used.

> Paths in these files assume they are run from the **true repository root**
> (e.g. `python legacy-v2/archive/georef_grid.py`, run from the top of the
> repo), where `GEOREF_FINAL_STANDARD_164/` lives. Some may need path
> adjustments to run.

**`bangka_dataset.csv`** also lives here: it is the **original** metadata table
(provided as source material; original compiler undocumented), superseded by
`../bangka_dataset_v2.csv`. It is kept as the input for the reproduction pipeline
and for provenance. See [`../../CHANGELOG.md`](../../CHANGELOG.md) for what was corrected.

| Script | What it was | Why it's archived |
|--------|-------------|-------------------|
| `georef_grid.py` | Automatic 1' grid-line detection → GCPs → affine georef | Auto-detection of the printed neatline/grid proved unreliable on these scans (see "Known Limitations" in the main README). Superseded by the grid-tiling + fixed-offset method. |
| `diagnose_georef.py` | Diagnostic CLI for `georef_grid.py`'s grid detection | Only meaningful alongside `georef_grid.py`; moved together to keep the import intact. |
| `grid_detection_diagnostic.py` | Early exploration of dark-line grid detection | Exploratory; contains an incomplete helper. Replaced by `georef_grid.py`. |
| `corrected_georef.py` | Alternative approach: Batavia (EPSG:4211) → WGS 84 datum transform, output to `CORRECTED_MAPS/` | Uses the older `bangka_dataset.csv`; its output is not referenced by the final dataset. Superseded by the offset-based method. |
| `offset_comparison.py` | Intended to compare OLD vs NEW GeoTIFF coordinates | Leftover: both compared directories point to the same folder, so it always reports zero difference. |
| `automated_crop.py` | Early GDAL-based legend crop → `CROPPED_IMAGES/` | Superseded by `map_crop.py`, whose output (`recovered_maps/`) is what the methodology uses. |
