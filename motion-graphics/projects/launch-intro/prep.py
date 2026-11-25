#!/usr/bin/env python3
"""Prepare the launch-intro assets from the owner's photos.

  python3 motion-graphics/projects/launch-intro/prep.py

Reads  assets/src/   (the owner's photos + logo screenshot; git-ignored, re-upload per session)
Writes assets/ready/ (transparent PNG cutouts, logo, poster ink layer)

- Background removal with rembg: isnet-general-use for most photos, birefnet-portrait for the
  black & white photos on dark backgrounds (isnet leaves their hair half-transparent).
- Small stray blobs are dropped; only the subject is kept.
- Logo: white scribble text on black -> white text with alpha from brightness.
- Poster: black halftone ink on cream -> ink layer with alpha from darkness (risograph look).
"""
import gc
import os

import cv2
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "assets", "src")
OUT = os.path.join(HERE, "assets", "ready")

ISNET = ["greenhat", "niss-orange", "topdown", "hand"]
BIREFNET = ["boxface", "filmstrip"]


def keep_main_blobs(rgba, min_frac=0.03):
    a = rgba[:, :, 3]
    n, lab, stats, _ = cv2.connectedComponentsWithStats((a > 40).astype(np.uint8), 8)
    if n <= 2:
        return rgba
    areas = stats[1:, cv2.CC_STAT_AREA]
    keep = np.zeros(n, bool)
    keep[1:] = areas >= areas.max() * min_frac
    mask = keep[lab]
    mask = cv2.dilate(mask.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    out = rgba.copy()
    out[:, :, 3] = np.where(mask, a, 0)
    return out


def crop_to_alpha(rgba, pad=8):
    ys, xs = np.where(rgba[:, :, 3] > 10)
    y0, y1 = max(ys.min() - pad, 0), min(ys.max() + pad, rgba.shape[0])
    x0, x1 = max(xs.min() - pad, 0), min(xs.max() + pad, rgba.shape[1])
    return rgba[y0:y1, x0:x1]


def cutouts():
    from rembg import new_session, remove

    for model, names in (("isnet-general-use", ISNET), ("birefnet-portrait", BIREFNET)):
        session = new_session(model)
        for name in names:
            out = os.path.join(OUT, f"{name}.png")
            if os.path.exists(out):
                print("exists", out)
                continue
            src = next(os.path.join(SRC, f) for f in os.listdir(SRC) if os.path.splitext(f)[0] == name)
            im = Image.open(src).convert("RGB")
            rgba = np.array(remove(im, session=session))
            rgba = crop_to_alpha(keep_main_blobs(rgba))
            Image.fromarray(rgba).save(out)
            print("cut", name, rgba.shape)
            gc.collect()
        del session
        gc.collect()


def logo():
    g = np.array(Image.open(os.path.join(SRC, "logo.jpg")).convert("L")).astype(np.float32)
    a = np.clip((g - 45) / (200 - 45), 0, 1)  # brightness -> alpha, drops JPEG noise in the black
    a[a < 0.06] = 0
    rgba = np.zeros(g.shape + (4,), np.uint8)
    rgba[:, :, :3] = 255
    rgba[:, :, 3] = (a * 255).astype(np.uint8)
    rgba = crop_to_alpha(rgba, pad=16)
    Image.fromarray(rgba).save(os.path.join(OUT, "logo-white.png"))
    print("logo", rgba.shape)


def poster_ink():
    from rembg import new_session, remove

    im = Image.open(os.path.join(SRC, "poster.png")).convert("RGB")
    g = np.array(im.convert("L")).astype(np.float32)
    h = g.shape[0]
    ink = np.clip((215 - g) / (215 - 60), 0, 1)  # darkness -> alpha; the cream paper disappears
    ink[int(h * 0.855):] = 0  # drop the logo text + underline under the drawing (we have the logo)
    # The poster's paper has a faint dot screen: keep ink only inside the drawing's silhouette.
    sil = np.array(remove(im, session=new_session("isnet-general-use")))[:, :, 3] > 12
    sil = cv2.morphologyEx(sil.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((25, 25), np.uint8))
    sil = cv2.GaussianBlur(cv2.dilate(sil, np.ones((15, 15), np.uint8)).astype(np.float32), (0, 0), 4)
    ink *= np.clip(sil, 0, 1)
    rgba = np.zeros(g.shape + (4,), np.uint8)
    rgba[:, :, 3] = (ink * 255).astype(np.uint8)  # black ink
    rgba = crop_to_alpha(rgba, pad=10)
    Image.fromarray(rgba).save(os.path.join(OUT, "poster-ink.png"))
    print("poster ink", rgba.shape)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    logo()
    poster_ink()
    cutouts()
