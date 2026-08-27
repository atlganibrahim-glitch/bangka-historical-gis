# -*- coding: utf-8 -*-
"""Extract the orange road network drawn on a sheet.

Roads print as a strong orange (R > G > B, high R-B), distinct from the
brownish-grey contour lines (low saturation, R-G small).  Extracted at
REDUCE=4 (about 8 m/px), then thinned with morphological closing so a
double-line road becomes one connected mask, matching the single-line OSM
geometry it will be compared against.
"""
import cv2
import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
REDUCE = 4


def road_mask(path_or_img, reduce=REDUCE):
    im = Image.open(path_or_img) if isinstance(path_or_img, str) else path_or_img
    a = np.asarray(im.reduce(reduce)).astype(np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    m = (r > 195) & (r - b > 50) & (r - g > 20)
    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    return m.astype(bool)
