# -*- coding: utf-8 -*-
"""Locate the printed neatline (map frame) inside a crop.

The frame is a single ruled line running the full width or height of the
sheet.  Map detail never does that, so a profile of "fraction of dark pixels
in this row/column" spikes on the frame and nowhere else.  A small skew search
keeps a scan that is a degree or two off from smearing the spike away.
"""
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

REDUCE = 2
DARK = 150          # a ruled line is much darker than printed detail
EDGE_FRAC = 0.03    # the crops are cut on the frame, so it sits at the edge
SKEWS = np.arange(-4, 4.5, 0.5)   # reduced px of drift across the sheet


def _profiles(dark, axis, skews):
    """Dark-pixel fraction per row (axis=0) or column (axis=1), best over skew."""
    n = dark.shape[0] if axis == 0 else dark.shape[1]
    m = dark.shape[1] if axis == 0 else dark.shape[0]
    best = np.zeros(n)
    for s in skews:
        if s == 0:
            prof = dark.mean(axis=1 - axis + 0) if False else (
                dark.mean(axis=1) if axis == 0 else dark.mean(axis=0))
        else:
            shifts = np.round(np.linspace(-s / 2, s / 2, m)).astype(int)
            acc = np.zeros(n)
            for j, sh in enumerate(shifts):
                col = dark[:, j] if axis == 0 else dark[j, :]
                acc += np.roll(col, -sh)
            prof = acc / m
        best = np.maximum(best, prof)
    return best


def _pick(prof, lo, hi, n):
    """Strongest spike inside [lo, hi), as a sub-pixel position, or None."""
    seg = prof[lo:hi]
    if len(seg) < 5:
        return None
    base = np.median(prof)
    k = int(np.argmax(seg))
    peak = seg[k]
    if peak < base + 0.04 or peak < 0.05:
        return None
    i = lo + k
    w = prof[max(i - 2, 0):i + 3] - base
    w = np.clip(w, 0, None)
    if w.sum() <= 0:
        return None
    off = (w * (np.arange(len(w)) - (i - max(i - 2, 0)))).sum() / w.sum()
    return (i + off), float(peak - base)


def find_frame(path, reduce=REDUCE):
    with Image.open(path) as im:
        a = np.asarray(im.reduce(reduce).convert('L'))
    dark = (a < DARK).astype(np.float32)
    H, W = dark.shape
    rows = _profiles(dark, 0, SKEWS)
    cols = _profiles(dark, 1, SKEWS)
    eh, ew = int(H * EDGE_FRAC), int(W * EDGE_FRAC)
    out = {}
    for name, prof, lo, hi, n in (
            ('top', rows, 0, eh, H), ('bottom', rows, H - eh, H, H),
            ('left', cols, 0, ew, W), ('right', cols, W - ew, W, W)):
        r = _pick(prof, lo, hi, n)
        out[name] = None if r is None else (r[0] * reduce, r[1])
    return out, (W * reduce, H * reduce)
