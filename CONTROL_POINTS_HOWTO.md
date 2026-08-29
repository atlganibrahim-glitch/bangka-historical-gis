# Measuring sheet accuracy by hand — control point procedure

This is the check the automated tests cannot do. A first round has already
been run (33 points over 10 sheets, see `ACCURACY_ASSESSMENT.md` §2.4); this
document is the procedure for extending it.

---

## Why this is needed

Both automated tests compare a sheet's **drawn content** against a modern
layer, and both are limited by what has genuinely changed since the 1930s:

- **Coastline test** (`fit_singles.py`) bottoms out around 780 m, because
  Bangka's shore really has moved that far.
- **Road test** (`fit_roads.py`) gave a clear answer on only 60 of 176
  sheets; on 71 others the road network has changed so much that no shift
  aligns them.

Neither test samples the **middle** of a sheet — they only see content near
a coast or a road. Ninety-year-old paper does not shrink uniformly (fold
lines, humidity, scan skew), so a sheet's corners can be correct while its
interior is not.

Hand-placed control points address both gaps at once: they work on the ~60%
of sheets no automated test could verify, and they sample sheet interiors.

## What gets measured: shift and scatter

Each sheet yields two numbers, and they mean very different things:

- **Shift** — the sheet as a whole sitting at a constant offset.
  **Correctable**, with a single per-sheet translation.
- **Scatter** — what remains *after* the best possible shift is removed.
  **Not correctable** by translation. Within-sheet distortion shows up here.

This is why each sheet needs **at least 3 points, ideally 5–6**: with one or
two you cannot separate the shift from the scatter.

---

## Step 0 — Keep the scope realistic

**Do not attempt all 176 sheets.** Work in batches of ~10, and choose them
deliberately.

The first round covered 10 sheets but 9 of them were **A-grade** — sheets
whose accuracy was already known. That validated the method (manual ~20 m
vs. automated ~21 m) but told us almost nothing new.

**The valuable work now is B-grade sheets.** From `bangka_sheet_quality.csv`,
prioritise:

| sheets | why |
|---|---|
| `32-XXIII-p`, `32-XXIII-q`, `32-XXIV-g` | Road test could not measure them at all (too little road ink) |
| `34-XXVI-p`, `34-XXVI-q` | Road test measured them and they scattered badly (1059 m, 808 m) — manual points will show whether that is real error or a limit of the method |

Roughly 10 minutes per sheet.

---

## Step 1 — Set up QGIS

Layer order, top to bottom:

1. `qgis/control_points.gpkg` — the control points (ready, may be non-empty)
2. `qgis/sheet_index_v3.geojson` — to see which sheet you are on
3. `bangka_v3_1.vrt` — the historical sheets
4. **A reference layer** (below)

### Which reference to use

| source | how to add | good for |
|---|---|---|
| **OSM Standard** | Browser → XYZ Tiles → OpenStreetMap | Road junctions — **most reliable**, drawn from vector data |
| **Esri World Imagery** | XYZ Tiles → New Connection, URL below | Rivers, coast, terrain detail |

```
https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}
```

> **Note:** satellite imagery has its own positional error (5–50 m depending
> on location). That is acceptable against the 30–200 m we are measuring, but
> **prefer OSM for road junctions** — it is vector data derived from GPS
> traces and is more trustworthy for this purpose.

---

## Step 2 — The control point layer

`qgis/control_points.gpkg` is ready, with an explicitly defined schema
(LineString, EPSG:4326). Add it via **Layer → Add Layer → Add Vector Layer**.

> **Why a GeoPackage and not GeoJSON:** live-editing an empty GeoJSON in
> QGIS is not reliable — the geometry type is not recorded in the file, so
> the driver guesses wrong and raises *"Could not commit changes … geometry
> type is not compatible"*, **silently rejecting everything you drew**. In a
> GeoPackage the type is stored in the schema and the problem does not arise.

Fields:

| field | what to enter |
|---|---|
| `sheet_id` | e.g. `34-XXV-e` — which sheet you are working on |
| `feature_type` | `road junction`, `river confluence`, `bridge`, … |
| `note` | optional |

---

## Step 3 — Choosing points

This step determines the quality of the result. Take your time.

### Good control points

- **Road junctions** — especially where two main roads cross. Best choice.
- **River confluences** — the exact point where two branches meet.
- **Bridges** — where a road crosses a river.
- **Distinct headlands** — rocky, hard-substrate points only.

### Avoid

- **Straight coastline** — it has moved, and a fit can slide along it.
- **Beaches, mangrove coasts, estuary mouths** — the most-changed features.
- **Settlement centres** — villages grew; the "centre" has moved.
- **Points strung along a single road** — if they are collinear you cannot
  measure the shift along that direction.
- **Anywhere near mining areas** — tin mining has reshaped the terrain
  completely in places.

### Spread them out

**Distribute points across the sheet** — roughly one near each corner and one
in the middle. If they cluster in one corner you cannot see within-sheet
distortion, which is one of the main reasons for doing this at all.

---

## Step 4 — Digitising

Each control point is a **two-vertex line**: where it appears → where it
should be.

1. Identify the sheet from `sheet_index_v3` (Identify tool, note `sheet_id`).
2. Find a junction on the historical sheet, zoom to about `1:5000`.
3. Select the `control_points` layer → **Toggle Editing** (pencil icon).
4. Choose **Add Line Feature**.
5. **First click:** exactly on the junction in the historical sheet.
6. Turn off the historical layer's visibility so OSM/imagery shows through.
7. **Second click:** the same junction on the modern layer.
8. **Right-click** to finish the line; the attribute form opens.
9. Fill in `sheet_id` and `feature_type` → OK.
10. Turn the historical layer back on, move to the next point.

> **Tip:** instead of toggling visibility at step 6, set the historical
> layer's **Opacity** to 50% and see both at once. Faster, but easier to
> confuse two nearby junctions — toggle if unsure.

After 5–6 points on a sheet, turn off **Toggle Editing** and **save**.

### Direction matters

The line must **always** run from the historical position to the modern one.
Drawing one backwards flips that point's error vector and corrupts the
sheet's mean. Styling the layer with arrow markers makes this checkable at a
glance (Symbology → Line → Marker line → arrow).

---

## Step 5 — Clean, then analyse

Hand digitising reliably produces empty features, exact duplicates (from
re-pasting or a double commit) and `sheet_id` typos. Clean first:

```bash
python v3/clean_control_points.py
```

It removes empties and duplicates, recovers mistyped sheet ids from the
geometry, and keeps a `.bak` copy. Then:

```bash
python v3/analyse_control_points.py
```

Per sheet it reports `n` (points), `dE`/`dN` (east/north shift), `|shift|`
and `scatter`. Pass a path to use a different file:

```bash
python v3/analyse_control_points.py qgis/pilot_points.gpkg
```

> **If QGIS is still open**, the GeoPackage's data may sit in a `-wal`
> journal rather than the main file. The scripts read it correctly either
> way, but before committing to git, close QGIS or run a SQLite
> `PRAGMA wal_checkpoint(TRUNCATE)` — otherwise the committed file can be
> empty.

---

## Step 6 — Reading the result

**Check any A-grade sheets first** — they are the control group. Manual
measurement should land near the road test's figure (~20–30 m). If it comes
out wildly different, suspect the point selection or a reversed line rather
than the data.

**Then the B-grade sheets** — that is where the new information is:

| observation | meaning | action |
|---|---|---|
| large shift, small scatter | Sheet is offset as a whole, interior sound | Apply a per-sheet translation — easy gain |
| small shift, small scatter | Sheet is already correct | Nothing to do |
| large scatter | Sheet is internally distorted | Translation will not fix it; needs a higher-order fit, or flag the sheet as low-confidence |

The script prints which of these applies.

---

## Afterwards

- **If scatter stays small** — the per-sheet shifts can be wired into
  `v3/grid.py`, the GeoTIFFs regenerated, and `bangka_sheet_quality.csv`
  updated to reflect the newly verified sheets.
- **If scatter is large on B-grade sheets** — that is itself a finding, and
  the accuracy claims in `ACCURACY_ASSESSMENT.md` should be revised down for
  the unverified population.

Either outcome closes the "only 30% verified" gap recorded in
`ACCURACY_ASSESSMENT.md` §3.
