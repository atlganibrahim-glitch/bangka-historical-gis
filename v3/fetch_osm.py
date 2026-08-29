# -*- coding: utf-8 -*-
"""Fetch the two OSM extracts the pipeline's accuracy checks depend on.

Neither is derived from anything else in this repo, so without this script
fit_singles.py, fit_irregular.py, fit_roads.py and fit_irregular_roads.py
cannot be reproduced from a clean checkout. v3/osm_coastline.json is small
enough to track in git directly; v3/osm_roads.json (~40 MB) is not, and is
regenerated here instead.

Uses the public Overpass API; no auth needed. The coastline query is quick.
The road query returns ~50k ways over Bangka and can take a few minutes -
Overpass mirrors vary in load, so a couple of alternates are tried in turn.
"""
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
UA = {'User-Agent': 'bangka-historical-gis/1.0 (research; '
                    'github.com/atlganibrahim-glitch/bangka-historical-gis)'}
MIRRORS = ['https://overpass-api.de/api/interpreter',
          'https://overpass.kumi.systems/api/interpreter']
BBOX = (-3.2, 105.0, -1.4, 106.9)   # (south, west, north, east) - Bangka


def query(ql, timeout=240):
    body = ql.encode()
    last = None
    for host in MIRRORS:
        try:
            req = urllib.request.Request(host, data=body, headers=UA)
            data = urllib.request.urlopen(req, timeout=timeout).read()
            return json.loads(data)
        except Exception as e:  # noqa: BLE001 - try the next mirror regardless of cause
            print('  %s failed (%s), trying next mirror' % (host, e))
            last = e
            time.sleep(2)
    raise RuntimeError('all Overpass mirrors failed') from last


def main():
    s, w, n, e = BBOX

    coast_path = os.path.join(HERE, 'osm_coastline.json')
    if os.path.exists(coast_path):
        print('osm_coastline.json already present, skipping')
    else:
        print('fetching coastline...')
        d = query('[out:json][timeout:180];way[natural=coastline](%f,%f,%f,%f);out geom;'
                  % (s, w, n, e))
        with open(coast_path, 'w', encoding='utf-8') as fh:
            json.dump(d, fh)
        print('  %d ways -> %s' % (len(d['elements']), coast_path))

    roads_path = os.path.join(HERE, 'osm_roads.json')
    if os.path.exists(roads_path):
        print('osm_roads.json already present, skipping')
    else:
        print('fetching roads (this is the slow one, ~50k ways expected)...')
        d = query('[out:json][timeout:180];way[highway](%f,%f,%f,%f);out geom;'
                  % (s, w, n, e))
        with open(roads_path, 'w', encoding='utf-8') as fh:
            json.dump(d, fh)
        print('  %d ways -> %s' % (len(d['elements']), roads_path))


if __name__ == '__main__':
    main()
