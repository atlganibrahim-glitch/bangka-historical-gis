# -*- coding: utf-8 -*-
"""
Margin Recalculation - Edge + FFT Method
========================================
Reliable template matching for JPEG crop vs OLD TIFF:
  1. Apply Sobel edge detection to both images
  2. Run FFT cross-correlation on the edge images
  3. Validate starting from the expected region (CSV margin)
"""
import os, time
import numpy as np
import pandas as pd
from osgeo import gdal
gdal.UseExceptions()

# v2-era script; moved into legacy-v2/ during the v3 reorganisation.
# GEOREF_FINAL_STANDARD_164/ and recovered_maps/ stayed at the true repo
# root, not tracked in git either way; bangka_dataset_v2.csv and archive/
# moved into legacy-v2/ alongside this script.
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OLD_DIR  = os.path.join(ROOT, 'GEOREF_FINAL_STANDARD_164')
CROP_DIR = os.path.join(ROOT, 'recovered_maps')
CSV_IN   = os.path.join(HERE, 'archive', 'bangka_dataset.csv')
CSV_OUT  = os.path.join(HERE, 'bangka_dataset_v2.csv')

SCALE = 4   # downsampling factor (4x smaller)


def read_gray(path, scale):
    ds = gdal.Open(path)
    w, h = ds.RasterXSize, ds.RasterYSize
    nw, nh = max(1, w // scale), max(1, h // scale)
    nb = ds.RasterCount
    if nb >= 3:
        r = ds.GetRasterBand(1).ReadAsArray(0,0,w,h,nw,nh).astype(np.float32)
        g = ds.GetRasterBand(2).ReadAsArray(0,0,w,h,nw,nh).astype(np.float32)
        b = ds.GetRasterBand(3).ReadAsArray(0,0,w,h,nw,nh).astype(np.float32)
        arr = 0.299*r + 0.587*g + 0.114*b
    else:
        arr = ds.GetRasterBand(1).ReadAsArray(0,0,w,h,nw,nh).astype(np.float32)
    ds = None
    return arr, w, h


def sobel_edges(arr):
    """Simple Sobel edge detection (without scipy)."""
    kx = np.array([[-1,0,1],[-2,0,2],[-1,0,1]], dtype=np.float32)
    ky = kx.T
    # manual convolution (small kernel)
    from numpy.lib.stride_tricks import as_strided
    rows, cols = arr.shape
    # 2D convolution via sliding window
    def conv2(im, k):
        r, c = k.shape
        pr, pc = r//2, c//2
        padded = np.pad(im, ((pr,pr),(pc,pc)), mode='edge')
        # strided view
        shape  = (rows, cols, r, c)
        strides = (padded.strides[0], padded.strides[1], padded.strides[0], padded.strides[1])
        view = as_strided(padded, shape=shape, strides=strides)
        return (view * k).sum(axis=(2,3))
    gx = conv2(arr, kx)
    gy = conv2(arr, ky)
    return np.sqrt(gx**2 + gy**2)


def norm2d(a):
    a = a - a.mean()
    s = a.std()
    return a / s if s > 0 else a


def fft_xcorr(old_arr, crop_arr):
    """FFT cross-correlation; peak = offset of crop within old image."""
    eh, ew = old_arr.shape
    ch, cw = crop_arr.shape
    if ch > eh or cw > ew:
        return None, None, None
    e = norm2d(old_arr)
    c = norm2d(crop_arr)
    c_pad = np.zeros((eh, ew), dtype=np.float32)
    c_pad[:ch, :cw] = c
    E = np.fft.rfft2(e)
    C = np.fft.rfft2(c_pad)
    corr = np.fft.irfft2(E * np.conj(C), s=(eh, ew)).real
    # Mask invalid positions
    mask = np.ones((eh, ew), dtype=bool)
    mask[eh-ch+1:, :] = False
    mask[:, ew-cw+1:] = False
    corr[~mask] = -np.inf
    y, x = np.unravel_index(corr.argmax(), corr.shape)
    score = corr[y, x]
    return int(x), int(y), float(score)


def match_sheet(old_path, crop_path, csv_ml, csv_mr, csv_mt, csv_mb):
    """
    Find the pixel offset of the crop within the old image.
    Two steps:
      1. Full-image FFT match (at 1/SCALE size)
      2. Local validation at the region expected from the CSV margin
    Return the higher-scoring result.
    """
    e_arr, ew, eh = read_gray(old_path, SCALE)
    c_arr, cw, ch = read_gray(crop_path, SCALE)

    # -- Edge images --
    e_edge = sobel_edges(e_arr)
    c_edge = sobel_edges(c_arr)

    # -- Global FFT match --
    gx, gy, gscore = fft_xcorr(e_edge, c_edge)

    # -- Expected offset from CSV (validation/alternative) --
    # Expected pixel offset from CSV margins (at SCALE size)
    ex_csv = int(csv_ml * (ew // SCALE))
    ey_csv = int(csv_mt * (eh // SCALE))
    # Local correlation score at this point
    eeh, eew = e_edge.shape
    ceh, cew_ = c_edge.shape
    csv_score = -np.inf
    if (ey_csv + ceh <= eeh) and (ex_csv + cew_ <= eew):
        patch = e_edge[ey_csv:ey_csv+ceh, ex_csv:ex_csv+cew_]
        c_n = norm2d(c_edge)
        p_n = norm2d(patch)
        csv_score = float((p_n * c_n).sum())

    # Also compute the global match's local score around the CSV region
    global_score_local = -np.inf
    if gx is not None:
        gxf = min(max(gx, 0), eew - cew_)
        gyf = min(max(gy, 0), eeh - ceh)
        if (gyf + ceh <= eeh) and (gxf + cew_ <= eew):
            patch_g = e_edge[gyf:gyf+ceh, gxf:gxf+cew_]
            p_g_n = norm2d(patch_g)
            c_n   = norm2d(c_edge)
            global_score_local = float((p_g_n * c_n).sum())

    # Which one is better?
    if csv_score >= global_score_local:
        best_x_s = ex_csv
        best_y_s = ey_csv
        method = 'CSV-margin'
        best_score = csv_score
    else:
        best_x_s = gx
        best_y_s = gy
        method = 'FFT-global'
        best_score = global_score_local

    # Convert back to full resolution
    fx = best_x_s * SCALE
    fy = best_y_s * SCALE

    ml = fx / ew
    mt = fy / eh
    mr = max(0.0, (ew - fx - cw) / ew)
    mb = max(0.0, (eh - fy - ch) / eh)

    return ml, mt, mr, mb, fx, fy, method, best_score


# --- Main ---------------------------------------------------------------------
def main():
    df = pd.read_csv(CSV_IN)
    old_files = set(os.listdir(OLD_DIR))
    results = []
    success = 0
    skipped = []

    print('Computing margins for ' + str(len(df)) + ' maps...')
    print('=' * 80)

    for idx, row in df.iterrows():
        sid = row['sheet_id']
        cf  = str(row.get('crop_filename', ''))
        old_file = sid + '.tif'
        old_path = os.path.join(OLD_DIR, old_file)
        crop_path = os.path.join(CROP_DIR, cf)

        if old_file not in old_files:
            skipped.append((sid, 'OLD not found'))
            results.append(row.to_dict()); continue
        if not os.path.exists(crop_path):
            skipped.append((sid, 'crop not found: ' + cf))
            results.append(row.to_dict()); continue

        t0 = time.time()
        try:
            ml, mt, mr, mb, fx, fy, method, score = match_sheet(
                old_path, crop_path,
                row['margin_left'], row['margin_right'],
                row['margin_top'],  row['margin_bottom']
            )
            dt = time.time() - t0

            o_ml = row['margin_left'];  o_mr = row['margin_right']
            o_mt = row['margin_top'];   o_mb = row['margin_bottom']

            print(
                sid.ljust(25) +
                ' off=(' + str(fx) + ',' + str(fy) + ')' +
                '  ml=' + str(round(ml,4)) +
                '(d' + str(round(ml-o_ml,4)) + ')' +
                '  mr=' + str(round(mr,4)) +
                '(d' + str(round(mr-o_mr,4)) + ')' +
                '  mt=' + str(round(mt,4)) +
                '(d' + str(round(mt-o_mt,4)) + ')' +
                '  mb=' + str(round(mb,4)) +
                '(d' + str(round(mb-o_mb,4)) + ')' +
                '  [' + method + ',' + str(round(dt,1)) + 's]'
            )

            new_row = row.to_dict()
            new_row['margin_left']   = round(ml, 5)
            new_row['margin_right']  = round(mr, 5)
            new_row['margin_top']    = round(mt, 5)
            new_row['margin_bottom'] = round(mb, 5)
            results.append(new_row)
            success += 1

        except Exception as e:
            skipped.append((sid, str(e)))
            results.append(row.to_dict())
            print('  ERROR ' + sid + ': ' + str(e))

    df_out = pd.DataFrame(results, columns=df.columns)
    df_out.to_csv(CSV_OUT, index=False)

    print()
    print('=' * 80)
    print('Done: ' + str(success) + '/' + str(len(df)) + ' maps')
    print('Output: ' + CSV_OUT)
    if skipped:
        print('Skipped ' + str(len(skipped)) + ':')
        for s, r in skipped:
            print('  x ' + s + ': ' + r)

    df_old = pd.read_csv(CSV_IN)
    df_new = pd.read_csv(CSV_OUT)
    print()
    print('Margin change summary:')
    for col in ['margin_left', 'margin_right', 'margin_top', 'margin_bottom']:
        delta = df_new[col] - df_old[col]
        print('  ' + col.ljust(20) + ' mean_d=' + str(round(delta.mean(),5)) +
              '  std=' + str(round(delta.std(),5)) +
              '  max|d|=' + str(round(delta.abs().max(),5)))


if __name__ == '__main__':
    main()
