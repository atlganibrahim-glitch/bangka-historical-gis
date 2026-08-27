# -*- coding: utf-8 -*-
"""Extract a sea mask from a scanned sheet.

Sea and land are almost the same paper colour on these sheets, so colour is
useless; what separates them is ink density.  Open water carries no contours,
roads or settlement stipple, so a heavily blurred ink map is near zero there
and high everywhere on land.
"""
import cv2
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

REDUCE = 8          # work on a 1/8 overview; ~4.6 m/px becomes ~37 m/px
SIGMA = 8           # blur radius in reduced pixels (~64 px, ~135 m, full scale)
THRESH = 0.030      # ink fraction below this is open water


def ink_density(path_or_img, reduce=None, sigma=None):
    reduce = REDUCE if reduce is None else reduce
    sigma = SIGMA if sigma is None else sigma
    im = Image.open(path_or_img) if isinstance(path_or_img, str) else path_or_img
    a = np.asarray(im.reduce(reduce))
    ink = (a.min(axis=2) < 175).astype(np.float32)
    return cv2.GaussianBlur(ink, (0, 0), sigma)


def sea_mask(path_or_img, thresh=None, **kw):
    """Boolean sea mask on the reduced grid, keeping only water bodies that
    reach the sheet edge (interior blank patches are not sea)."""
    d = ink_density(path_or_img, **kw)
    water = (d < (THRESH if thresh is None else thresh)).astype(np.uint8)
    water = cv2.morphologyEx(water, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
    n, lab = cv2.connectedComponents(water)
    keep = np.zeros_like(water, dtype=bool)
    border = set(lab[0, :]) | set(lab[-1, :]) | set(lab[:, 0]) | set(lab[:, -1])
    h, w = water.shape
    for i in range(1, n):
        if i in border and (lab == i).sum() > 0.004 * h * w:
            keep |= (lab == i)
    return keep


def coastline(mask):
    """Pixels on the sea side of the land/sea boundary, excluding the sheet
    edge itself (an edge is a crop artefact, not a shoreline)."""
    m = mask.astype(np.uint8)
    edge = cv2.morphologyEx(m, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)).astype(bool)
    edge[:2, :] = edge[-2:, :] = edge[:, :2] = edge[:, -2:] = False
    return edge & mask
