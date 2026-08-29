# -*- coding: utf-8 -*-
"""Build a 1970s/80s coastline from Landsat MSS, as a second control layer.

Why: the OSM-coastline check (fit_singles.py) bottoms out around 780 m
because Bangka's shore has genuinely moved since the 1930s - tin dredging,
tailings, mangrove.  A Landsat scene from 1977-1982 is roughly half as far
from the survey date as OSM is, so the real-change component of the residual
should be substantially smaller.

The control has to be more accurate than the signal being measured, so only
L1TP scenes (terrain-precision, tied to ground control) are used, and each
scene's own GEOMETRIC_RMSE_MODEL is recorded alongside the result: 21-48 m
here, against a ~170 m signal.

Water is separated from land with a threshold on the near-infrared band,
where the contrast is strongest - water absorbs NIR almost completely while
vegetation reflects it.
"""
import json
import os
import sys
import urllib.request

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

STAC = 'https://planetarycomputer.microsoft.com/api/stac/v1'
SAS = 'https://planetarycomputer.microsoft.com/api/sas/v1/token/landsateuwest/landsat-c2'
UA = {'User-Agent': 'bangka-historical-gis/1.0 (research; coastline control layer)'}

# North and south of the island; both L1TP, chosen for RMSE and cloud cover.
SCENES = [
    ('LM03_L1TP_132061_19820706_02_T2', 'north'),
    ('LM03_L1TP_132062_19820320_02_T2', 'south'),
]
CACHE = os.path.join(HERE, 'landsat')


def _get(url, timeout=120):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def token():
    return json.loads(_get(SAS))['token']


def scene_info(sid, tok):
    d = json.loads(_get('%s/collections/landsat-c2-l1/items/%s' % (STAC, sid)))
    mtl = json.loads(_get(d['assets']['mtl.json']['href'] + '?' + tok))
    lp = mtl['LANDSAT_METADATA_FILE'].get('LEVEL1_PROCESSING_RECORD', {})
    return d, dict(rmse=float(lp.get('GEOMETRIC_RMSE_MODEL', 'nan')),
                   gcp=lp.get('GROUND_CONTROL_POINTS_MODEL'),
                   date=d['properties']['datetime'][:10],
                   cloud=d['properties'].get('eo:cloud_cover'))


def fetch_band(sid, band, tok):
    """Download one band GeoTIFF to the cache and return its local path."""
    os.makedirs(CACHE, exist_ok=True)
    out = os.path.join(CACHE, '%s_%s.TIF' % (sid, band))
    if os.path.exists(out):
        return out
    d = json.loads(_get('%s/collections/landsat-c2-l1/items/%s' % (STAC, sid)))
    href = d['assets'][band]['href'] + '?' + tok
    data = _get(href, timeout=600)
    with open(out, 'wb') as fh:
        fh.write(data)
    return out


def main():
    tok = token()
    print('scene                            date        cloud  RMSE(m)  GCP')
    paths = []
    for sid, where in SCENES:
        _, info = scene_info(sid, tok)
        print('%-32s %-11s %4.0f%%  %7.1f  %s  [%s]'
              % (sid, info['date'], info['cloud'], info['rmse'], info['gcp'], where))
        p = fetch_band(sid, 'nir08', tok)
        paths.append((sid, where, p, info))
        print('   nir08 -> %s (%.1f MB)' % (os.path.basename(p), os.path.getsize(p) / 1e6))
    return paths


if __name__ == '__main__':
    main()
