# -*- coding: utf-8 -*-
"""Measure the printed frame of every sheet and flag the irregular ones."""
import csv
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import grid  # noqa: E402
import neatline  # noqa: E402


def main():
    ids = sorted(os.path.splitext(f)[0] for f in os.listdir(grid.CROP_DIR)
                 if f.endswith('.jpg'))
    rows = []
    for i, sid in enumerate(ids, 1):
        f, (w, h) = neatline.find_frame(os.path.join(grid.CROP_DIR, sid + '.jpg'))
        fw = None if (f['left'] is None or f['right'] is None) else f['right'][0] - f['left'][0]
        fh = None if (f['top'] is None or f['bottom'] is None) else f['bottom'][0] - f['top'][0]
        rows.append(dict(sheet_id=sid, kind='composite' if len(sid.split('-')[2]) == 2 else 'single',
                         crop_w=w, crop_h=h,
                         frame_left='' if f['left'] is None else round(f['left'][0], 1),
                         frame_right='' if f['right'] is None else round(f['right'][0], 1),
                         frame_top='' if f['top'] is None else round(f['top'][0], 1),
                         frame_bottom='' if f['bottom'] is None else round(f['bottom'][0], 1),
                         frame_w='' if fw is None else round(fw, 1),
                         frame_h='' if fh is None else round(fh, 1),
                         aspect='' if (fw is None or fh is None) else round(fh / fw, 4)))
        print('[%3d/%d] %-14s crop %dx%d  frame %s x %s' %
              (i, len(ids), sid, w, h,
               'n/a' if fw is None else '%.0f' % fw,
               'n/a' if fh is None else '%.0f' % fh), flush=True)
    out = os.path.join(HERE, 'frames.csv')
    with open(out, 'w', newline='', encoding='utf-8') as fh_:
        wr = csv.DictWriter(fh_, list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    asp = [r['aspect'] for r in rows if r['kind'] == 'single' and r['aspect'] != '']
    a = np.array(asp)
    print('\nsingle-cell frame aspect (h/w): median %.4f  MAD %.4f  n=%d' %
          (np.median(a), np.median(np.abs(a - np.median(a))), len(a)))
    bad = sorted([r for r in rows if r['kind'] == 'single' and r['aspect'] != ''
                  and abs(r['aspect'] - 1.0) > 0.02], key=lambda r: -abs(r['aspect'] - 1))
    print('\nsingles whose frame is not square (>2%%) - irregular sheets in disguise:')
    for r in bad:
        print('   %-14s frame %.0f x %.0f  aspect %.4f  (%+.1f%%)' %
              (r['sheet_id'], r['frame_w'], r['frame_h'], r['aspect'],
               (r['aspect'] - 1) * 100))
    print('wrote', out)


if __name__ == '__main__':
    main()
