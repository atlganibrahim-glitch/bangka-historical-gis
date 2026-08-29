# Bangka v3.1 — Accuracy & Robustness Assessment

*What the current dataset actually is, how it was tested, and what to watch
for before running the land-use symbol model on it. For the rebuild history
and what changed from v2, see `V3_REPORT.md`; this document is about the
current state only.*

---

## 1. Bottom line

| question | answer |
|---|---|
| Is the grid internally consistent? | Yes, tightly — max 8.4 m off the theoretical graticule, 0 overlaps between any two sheets. |
| Is the whole-island position correct? | Yes, to within a small, measured systematic shift — corrected in v3.1. |
| Is every individual sheet's position independently confirmed? | **No — only 30% of the land area (53/176 sheets) has been independently verified. The rest (62%) is unmeasured, not known-bad.** |
| Is accuracy uniform within a single sheet? | **Largely, on the sheets checked.** 33 hand-placed control points over 10 sheets give ~31 m scatter once each sheet's own offset is removed — but 9 of those 10 were already-verified sheets (§2.4). |
| Can model detections be placed on a map yet? | **No.** The pixel → coordinate step for patch-level detections has not been wired up (see §4). |

Read on for the tests behind each of these, then the two use-case sections.

---

## 2. What was tested, and how

Five independent tests were run. Each is described briefly enough to judge
whether the method itself is sound, not just the number it produced.

### 2.1 Internal geometry (does the grid tile correctly?)

Every sheet's printed frame (neatline) was detected directly from the scan —
a profile of "fraction of dark pixels" per row/column spikes on the ruled
border line and nowhere else — and compared against where the theoretical
5′ graticule says it should sit.

| check | result |
|---|---|
| Neatline corner vs. theoretical graticule (162 regular sheets) | max **8.4 m** |
| Structural overlaps between any two sheets | **0** |
| One-cell frame aspect ratio (height/width) vs. the ellipsoid's prediction for this latitude | measured 0.9960 ± 0.0032 vs. predicted 0.9943 — independent cross-check that the frame detection itself is correct |

This confirms the sheets tile together correctly. It does **not** confirm
the whole tiling sits in the right place on Earth — that's §2.2–2.3.

### 2.2 Absolute position — coastline vs. OpenStreetMap

The drawn shoreline on each coastal sheet was fitted against the modern OSM
coastline. Sheets whose visible coast runs in one straight direction were
excluded — a straight line can slide along itself and produce a fit that
looks confident but measures nothing (an aperture problem), so keeping them
in would have overstated precision.

| | value |
|---|---|
| Sheets with enough shoreline to test | 17 |
| Residual systematic shift after the v3.1 correction | ±300 m order |
| Median shoreline residual after fitting each sheet individually | 659 m |

**This number is not directly usable as a position-accuracy figure.** Bangka's
coastline has moved substantially since the 1930s — tin dredging, tailings
progradation, mangrove change — so a large fraction of this residual is real
geography, not error. It bounds the problem (accuracy is somewhere at or
below ~660–780 m near the coast) without pinning it down further.

### 2.3 Absolute position — inland road network vs. OpenStreetMap (the informative test)

Same method, applied to the roads drawn on each sheet instead of the
coastline. Roads move far less than a coastline over 90 years, so this
result is much closer to true positional accuracy.

| | value |
|---|---|
| Sheets with enough road ink to test | 131 / 176 |
| Median residual across all 131 | 170 m |
| Sheets converging independently on the *same* shift (a self-consistency signal, not assumed) | 60 / 131 |
| Median residual within that converged subset | **30 m** |
| Remaining systematic bias after applying the v3.1 correction | **+22 m E, +22 m N** |

The 60/131 convergence is the important result: 60 sheets, scattered across
the island, independently landed on the same correction. That is not
plausible by chance, and it is why the correction was trusted enough to
apply.

**The other 71 sheets did not converge, and we now know why.** Two
diagnostics settle it:

- Sheets that scatter have a median best-fit residual of **408 m**, versus
  **30 m** for sheets that converge. Their drawn roads do not match the
  modern network well *at any shift* — so the problem is not that the fit
  picked the wrong offset, it's that no offset aligns them.
- The scattered sheets are spatially interleaved with the converged ones
  (same longitude and latitude ranges, similar medians), so this is not a
  regional effect that a per-region correction could absorb.

A targeted attempt to recover them — refitting with a tighter road-class
filter (`trunk`+`primary` only, on the theory that modern minor roads were
confusing the fit) — recovered only 2 of the 71, both with poor residuals.
That avenue is closed; the script is kept as `v3/fit_roads_tight.py` with
the negative result documented.

The conclusion is that these 71 sheets are limited by **real road-network
change** since the 1930s, not by anything tunable in the method. **Their true
positional accuracy remains unknown — not measured as poor, but not
verifiable by this technique at all.** Confirming them needs a different kind
of control (see §6).

### 2.4 Hand-digitised control points (the only test that samples sheet interiors)

Every test above compares a sheet's *drawn* content against a modern layer,
and none of them samples the middle of a sheet. To check that, 33 control
points were digitised by hand across 10 sheets: for each one, a feature
identifiable on both the historical sheet and OpenStreetMap (mostly road
junctions), recorded as a line from where it sits on the georeferenced sheet
to where it actually is. Tooling: `v3/analyse_control_points.py`,
`v3/clean_control_points.py`, layer in `qgis/control_points.gpkg`.

Each sheet's points are split into a **shift** (the mean offset, which a
per-sheet translation could remove) and the **scatter** that remains after
removing it — the scatter is where within-sheet distortion would appear.

| | value |
|---|---|
| Sheets with ≥3 points | 10 |
| Per-sheet shift | median **22 m**, max 73 m |
| Residual scatter after removing the shift | median **31 m**, max 60 m |

Two things follow:

- **The method cross-validates the road test.** On the A-grade sheets, manual
  measurement gives ~20 m where the automated road fit gave ~21 m. Two fully
  independent techniques agreeing is meaningful evidence that both are right.
- **Within-sheet distortion appears to be small.** A scatter of ~31 m means a
  simple per-sheet translation would capture most of the remaining error;
  the sheets are not noticeably warped internally.

**Limitation, and it is the important one:** 9 of the 10 sheets are A-grade —
sheets whose accuracy was *already* known. Only one B-grade sheet
(`33-XXV-ae`: 49 m shift, 28 m scatter) is in the sample. So this confirms the
existing numbers and tests the interior question, but says almost nothing
about the ~60% of the island that no test has verified. Extending the same
exercise to 5–6 B-grade sheets — especially `34-XXVI-p` and `34-XXVI-q`,
where the road fit scattered badly — would settle that; the procedure is
documented in `MANUEL_KONTROL.md`.

### 2.5 Anchor-edge correctness (composite and irregular sheets only)

14 of the 176 sheets are printed larger than one graticule cell (12
composites + 2 irregular single-letter sheets). Each was placed under both
possible anchor hypotheses and fitted freely against OSM — shoreline where
available, the road network for the 4 sheets where it wasn't. All 14 landed
on the same answer as the simple sub-code rule, each by a wide margin
(hundreds to thousands of metres separating the two hypotheses). This is a
correctness check (right edge vs. wrong edge), not a fine-grained accuracy
number.

---

## 3. Coverage: how much of the island is actually verified

`bangka_sheet_quality.csv` grades every sheet by what's actually known
about it, not by assumption:

| grade | sheets | land area | meaning |
|---|---:|---:|---|
| A | 53 (30%) | 3,628 km² (32%) | Road-network test converged; treat as ~30 m accuracy |
| B | 109 (62%) | 6,891 km² (60%) | No independent check succeeded — unknown, not bad |
| C | 14 (8%) | 895 km² (8%) | Multiple caveats stacked; inspect before relying on it |

**The headline "170 m median" and "30 m best case" numbers describe a
minority of the island.** For most of the land area, no test has actually
confirmed the position — the true error there could be anywhere from very
good to considerably worse than 170 m, and there is currently no way to
tell which sheets are which without more testing.

---

## 4. What has not been tested at all

- **Within-sheet distortion — now partly measured, see §2.5.** A first
  hand-digitised sample suggests it is small, but only on 10 sheets, almost
  all of them already-verified ones.
- **The path from a model detection to a map coordinate.** The inference
  notebook currently outputs pixel boxes within a patch, with no step
  converting that to a real-world coordinate. Nothing in this document
  about positional accuracy is usable in practice until that connection
  exists — see §5.2.

---

## 5. Two use cases, and what to watch for in each

### 5.1 Aggregate / regional comparison (patch-scale or coarser, ≳1 km)

At this scale the measured error (170 m median, up to ~675 m at the 90th
percentile) stays well inside a single analysis cell, so this is the safer
use case. Still:

- **Don't use hard grid boundaries at the sub-1 km scale.** A symbol within
  ~200–700 m of a cell edge can fall on either side of it purely from
  positional error, not real content.
- **Composite/irregular sheet edges are less tested than plain sheet
  interiors** (§2.4 confirms which edge is right, not how precisely).
  Treat detections near those 14 sheets' boundaries with extra caution.
- **The biggest risk is confounding registration error with the very
  change being measured.** A symbol that appears to have "moved" or
  "disappeared" near a boundary could be 170 m of position error, not land
  change — and both point in a direction that's easy to mistake for a
  real signal.
- **Results currently mix a 30%-verified and a 62%-unverified population.**
  Any conclusion should be checked on the A-grade subset alone before it's
  trusted for the full island.

### 5.2 Point-level / single-symbol matching (sub-100 m)

Not usable yet for two separate reasons that need to be fixed in this
order:

1. **No coordinate conversion exists yet.** Detections are pixel boxes
   inside a patch; nothing converts that to WGS 84. This has to be wired up
   before positional accuracy is even a meaningful question at this scale.
2. **Even once wired up, current accuracy is not adequate at this
   resolution** for most sheets — see §3 and §4. A single detected symbol
   could be off by anywhere from ~20 m to several hundred metres, depending
   entirely on which sheet it's on, and there is no per-detection way to
   know which today.

---

## 6. Recommendation, by what you actually need

**If the goal is regional/aggregate patterns** (e.g. land-use type density
by area, compared against a similarly coarse modern layer): the current
v3.1 data is usable now, with two changes to the analysis, not the data —
use grid cells of ≥1 km, and report results split by `positional_grade` (A
vs. everything) rather than pooled, at least until §6's second option below
narrows that gap.

**If the goal is point-level or sub-100 m comparison**: two things need to
happen, in order:

1. **Wire up the coordinate conversion** (`v3/sheet_to_wgs84.py` is ready
   for this) — needs the patch-tiling scheme from `patches.csv` and
   confirmation of which crop generation the patches were cut from. Nothing
   past this point matters until it's done.
2. **Extend the verification to cover more than 30% of the island.** Note
   that the cheap option here has already been tried and does not work:
   refitting the 71 unconverged sheets with a tighter road-class filter
   recovered only 2 of them (§2.3). Automated road matching has reached its
   limit on this data. What remains:
   - **Manually-picked control points, a handful per sheet** (road
     junctions, river confluences, settlement centres) with a small
     per-sheet correction fitted from them. This is the option that would
     actually close the gap — and it has a second benefit the automated
     tests don't: it samples the sheet's *interior*, which is the one thing
     never tested so far (§4). Cost is real but bounded: it's the only
     approach here that addresses both the coverage gap and the
     within-sheet unknown at once.
   - **A more stable feature class than roads.** Two of the model's 14
     classes are mine symbols (`mijn`, `verlaten mijn`); documented
     historical tin-mine locations, if they exist independently of OSM,
     would give a third fully independent check. Coastal promontories and
     river mouths are also more stable than the shoreline as a whole.

Either path is compatible with the data as it stands today — the choice is
about how much additional validation work matches how precise the
downstream comparison needs to be.
