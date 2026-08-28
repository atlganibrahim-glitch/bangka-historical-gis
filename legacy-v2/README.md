# legacy-v2/ — superseded by v3.1

Everything in this folder is the **v2 pipeline**, kept for provenance only.
It has known bugs (composite sheets overlapping their neighbours by up to
278 m) and should not be used. See [`../V3_REPORT.md`](../V3_REPORT.md) for
the current pipeline and [`../CHANGELOG.md`](../CHANGELOG.md) for what
changed.

| file | what it is |
|---|---|
| `METHODOLOGY_REVISED_EN.md`, `bangka_technical_report.md` | v2 write-ups |
| `bangka_dataset_v2.csv` | v2 metadata |
| `map_crop.py` → `recalc_margins.py` → `automated_georef.py` → `crop_margin_geo.py` | v2 pipeline, in run order |
| `verify_georef.py`, `osm_alignment_check.py`, `calibration_comparison.py` | v2 QC scripts |
| `archive/` | pre-v2 experiments and the original source CSV |

These scripts expect to run from the **true repository root** (one level up
from here), e.g. `python legacy-v2/map_crop.py`, since the large data
folders they read and write (`main maps/`, `recovered_maps/`,
`GEOREF_FINAL_STANDARD_164/`) live there, not inside `legacy-v2/`.
