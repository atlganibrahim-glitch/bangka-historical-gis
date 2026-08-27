# -*- coding: utf-8 -*-
"""bangka_dataset_v3.csv - one row per sheet, carrying the actual v3 geometry."""
import csv
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import grid  # noqa: E402

COLS = ['sheet_id', 'kind', 'label', 'source_filename', 'crop_filename',
        'year', 'method', 'instrument', 'crop_w', 'crop_h',
        'frame_w', 'frame_h', 'frame_measured',
        'cells', 'anchor', 'west', 'north', 'east', 'south',
        'deg_per_px_x', 'deg_per_px_y', 'span_lon_arcmin', 'span_lat_arcmin']


def main():
    old = pd.read_csv(os.path.join(ROOT, 'bangka_dataset_v2.csv')).set_index('sheet_id')
    ids = sorted(os.path.splitext(f)[0] for f in os.listdir(grid.CROP_DIR)
                 if f.endswith('.jpg'))
    out = os.path.join(ROOT, 'bangka_dataset_v3.csv')
    with open(out, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, COLS)
        w.writeheader()
        for sid in ids:
            g = grid.sheet_geometry(sid)
            o = old.loc[sid] if sid in old.index else None
            w.writerow(dict(
                sheet_id=sid, kind=g['kind'],
                label=('' if o is None else o['label']),
                source_filename=('' if o is None else o['filename']),
                crop_filename=sid + '.jpg',
                year=('' if o is None else o['year']),
                method=('' if o is None else o['method']),
                instrument=('' if o is None else o['instrument']),
                crop_w=g['w_px'], crop_h=g['h_px'],
                frame_w='%.1f' % g['frame_w'], frame_h='%.1f' % g['frame_h'],
                frame_measured={(True, True): 'both', (True, False): 'width',
                                (False, True): 'height', (False, False): 'none'}[
                    (grid.frames()[sid]['w'] is not None,
                     grid.frames()[sid]['h'] is not None)],
                cells=';'.join('%d,%d' % c for c in g['cells']),
                anchor=g['anchor'],
                west='%.7f' % g['west'], north='%.7f' % g['north'],
                east='%.7f' % g['east'], south='%.7f' % g['south'],
                deg_per_px_x='%.9f' % g['xscale'], deg_per_px_y='%.9f' % g['yscale'],
                span_lon_arcmin='%.4f' % g['span_lon_arcmin'],
                span_lat_arcmin='%.4f' % g['span_lat_arcmin']))
    print('wrote', out, len(ids), 'rows')


if __name__ == '__main__':
    main()
