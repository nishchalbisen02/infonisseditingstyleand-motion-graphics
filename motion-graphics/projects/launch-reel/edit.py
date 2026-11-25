#!/usr/bin/env python3
"""Launch reel: turn the 16:9 launch clip into a 9:16 reel.

  python3 motion-graphics/projects/launch-reel/edit.py SOURCE.mov [--out reel.mp4]
  python3 motion-graphics/projects/launch-reel/edit.py SOURCE.mov --preview 0.5,3,6,12,15.3,16.5 --out sheet.png

What it does (audio is kept exactly in sync, nothing is retimed):
  - vertical crop that follows the face in each shot
  - punch-in zoom cuts in the speech pauses, plus an impact zoom on the shot change
  - photo montage (7.0-11.3s): the owner's photos slam in as collage cards with chalk doodles,
    over the voice, on alternating orange/black plates (photos in ./assets, git-ignored)
  - pull-back on the smoke so the full "Let'smakesomenoise" end card fits the vertical frame
  - light grade (contrast, saturation, vignette), fine film grain, mild sharpening
  - Instagram handle (red bar + handwritten text) in the top-left of the vertical frame
  - loudness normalised for Instagram (-14 LUFS)

Needs: ffmpeg, numpy, pillow, opencv-python-headless<5
"""
import argparse
import math
import os
import subprocess
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SRC_W, SRC_H = 1920, 1080
OUT_W, OUT_H = 1080, 1920
FPS = 30
CUT = 157 / FPS  # shot change: lamp close-up -> lying-down selfie

# Face centre (fraction of source width), smoothed keyframes per shot.
FACE_X = [
    (0.00, 0.385), (1.60, 0.385), (2.20, 0.362), (3.00, 0.400), (3.80, 0.352), (4.40, 0.335), (CUT - 0.01, 0.360),
    (CUT, 0.520), (7.0, 0.530), (11.0, 0.575), (12.5, 0.570), (13.3, 0.545), (15.0, 0.530),
]
FACE_Y = [(0.0, 0.36), (CUT - 0.01, 0.36), (CUT, 0.45), (15.0, 0.45)]

# Zoom segments: (start, end, zoom at start, zoom at end). Cuts sit in the speech pauses.
ZOOM = [
    (0.00, 1.10, 1.00, 1.02),  # shot 1 is already a tight close-up: keep its punch-ins small
    (1.10, 2.76, 1.05, 1.06),
    (2.76, CUT, 1.00, 1.04),
    (CUT, 11.77, 1.06, 1.16),
    (11.77, 12.48, 1.30, 1.32),
    (12.48, 13.66, 1.10, 1.13),
    (13.66, 99.0, 1.28, 1.34),
]
MONTAGE_START, MONTAGE_END = 7.0, 11.30  # photo montage over the voice; ends in a speech pause
IMPACTS = [  # time, duration, starting zoom: a punch on the shot change and when the face comes back
    (CUT, 0.40, 1.30),
    (MONTAGE_END, 0.35, 1.30),
]

# End card: pull back from the face crop to fit the text block.
PULL_START, PULL_END = 15.05, 15.75
TEXT_BOX = (226, 1684, 596, 833)  # x0, x1, y0, y1 of text + underline in the source
TEXT_WIDTH_OUT = 960              # text width in the reel, px

# Instagram handle: text, look, where it sits in the reel, and when it fades out (before the smoke).
HANDLE = "@letssmakesomenoise"
HANDLE_FONT = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "fonts", "Mali-Regular.ttf")
HANDLE_SIZE = 40                  # px
HANDLE_BAR = (230, 25, 75)        # RGB of the red bar
WM_POS = (64, 210)
WM_FADE = (14.20, 14.45)


# --- Photo montage -----------------------------------------------------------------------------
# The owner's photos slam in as collage cards (B-roll over the voice) during the long second shot.
# They live in ./assets, which is git-ignored because the repo is public: re-upload them per session.
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
ORANGE, BLACK = (24, 80, 214), (16, 14, 14)  # BGR plates; orange sampled from the NISS artwork
CARD_W, CARD_CY, CARD_BORDER = 900, 900, 14
CARDS = [
    # file, plate colour, resting tilt (deg), chalk doodles: (kind, x, y, angle deg, size)
    ("1-topdown.png", ORANGE, -3.0, [("burst", 935, 250, -45, 1.0), ("squiggle", 540, 1590, -3, 1.0)]),
    ("2-niss-orange.png", BLACK, 2.5, [("bolt", 905, 250, 12, 1.2), ("star", 150, 1480, 0, 1.0),
                                       ("star", 228, 1565, 0, 0.6)]),
    ("3-filmstrip.png", ORANGE, -2.0, [("burst", 930, 360, -40, 1.0), ("squiggle", 560, 1470, 2, 1.0)]),
    ("4-hand.jpg", BLACK, 3.0, [("star", 160, 225, 0, 1.1), ("bolt", 175, 1560, -12, 0.9),
                                ("star", 925, 1585, 0, 0.9)]),
    ("5-boxface.png", ORANGE, -2.5, [("burst", 935, 250, -40, 0.9), ("burst", 150, 1560, 135, 1.0)]),
]

DOODLE_SHAPES = {
    # polylines in local px (y down), drawn in this order
    "burst": [[(28 * math.cos(a), 28 * math.sin(a)), (r * math.cos(a), r * math.sin(a))]
              for a, r in ((-0.56, 96), (0.0, 112), (0.56, 96))],
    "bolt": [[(-12, -62), (14, -10), (-6, -6), (20, 60)]],
    "star": [[(-28, 0), (28, 0)], [(0, -28), (0, 28)], [(-11, -11), (11, 11)]],
    "squiggle": [[(-210, 6), (-178, -9), (-194, 11), (-158, -2), (210, -14)]],  # like the end-card underline
}


def wobble(pts, rng, step=6.0, amp=1.8):
    """Densify a polyline and add a little hand-drawn wobble."""
    out = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        n = max(int(math.hypot(x1 - x0, y1 - y0) / step), 1)
        nx, ny = -(y1 - y0), x1 - x0
        ln = math.hypot(nx, ny) or 1
        for i in range(n):
            f = i / n
            w = amp * math.sin(f * math.pi * 2 + rng.uniform(0, 6.28)) * rng.uniform(0.5, 1)
            out.append((x0 + (x1 - x0) * f + nx / ln * w, y0 + (y1 - y0) * f + ny / ln * w))
    out.append(pts[-1])
    return np.array(out, np.float32)


DOODLE_SCALE, DOODLE_THICKNESS = 1.5, 10


def place_doodle(kind, x, y, ang, size, rng):
    size *= DOODLE_SCALE
    a = math.radians(ang)
    ca, sa = math.cos(a), math.sin(a)
    lines = []
    for line in DOODLE_SHAPES[kind]:
        pts = [(x + size * (px * ca - py * sa), y + size * (px * sa + py * ca)) for px, py in line]
        lines.append(wobble(pts, rng))
    return lines


def draw_partial(mask, lines, progress, thickness=DOODLE_THICKNESS):
    total = sum(float(np.linalg.norm(np.diff(l, axis=0), axis=1).sum()) for l in lines)
    budget = total * progress
    for l in lines:
        seg = np.linalg.norm(np.diff(l, axis=0), axis=1)
        if budget <= 0:
            break
        keep = int(np.searchsorted(np.cumsum(seg), budget)) + 2
        budget -= float(seg.sum())
        pts = (l[:keep] * 4).astype(np.int32)  # 2 bits of sub-pixel precision
        cv2.polylines(mask, [pts], False, 255, thickness, cv2.LINE_AA, shift=2)


def make_plate(color, seed):
    """Flat colour with a faint paper texture."""
    rng = np.random.default_rng(seed)
    n = cv2.GaussianBlur(rng.normal(0, 1, (OUT_H // 8, OUT_W // 8)).astype(np.float32), (0, 0), 2.5)
    n = cv2.resize(n, (OUT_W, OUT_H), interpolation=cv2.INTER_CUBIC)
    n /= np.abs(n).max() + 1e-6
    plate = np.empty((OUT_H, OUT_W, 3), np.float32)
    plate[:] = color
    return plate * (1 + 0.08 * n[:, :, None])


def build_montage():
    cards = []
    rng = np.random.default_rng(11)
    for k, (name, plate, tilt, doodles) in enumerate(CARDS):
        im = cv2.imread(os.path.join(ASSETS, name), cv2.IMREAD_COLOR)
        if im is None:
            print(f"warning: {name} not found in {ASSETS}; skipping the photo montage", file=sys.stderr)
            return None
        h = round(im.shape[0] * CARD_W / im.shape[1])
        im = cv2.resize(im, (CARD_W, h), interpolation=cv2.INTER_AREA if im.shape[1] > CARD_W else cv2.INTER_CUBIC)
        b, pad = CARD_BORDER, 90
        H, W = h + 2 * (b + pad), CARD_W + 2 * (b + pad)
        rgb = np.zeros((H, W, 3), np.float32)
        alpha = np.zeros((H, W), np.float32)
        rgb[pad:H - pad, pad:W - pad] = (236, 241, 243)  # off-white sticker border
        rgb[pad + b:pad + b + h, pad + b:pad + b + CARD_W] = im
        alpha[pad:H - pad, pad:W - pad] = 1
        shadow = cv2.GaussianBlur(np.roll(np.roll(alpha, 20, 0), 10, 1), (0, 0), 18) * 0.55
        cards.append({
            "rgb": rgb, "alpha": alpha, "shadow": shadow, "tilt": tilt,
            "plate": make_plate(plate, 100 + k),
            "doodles": [place_doodle(*d, rng) for d in doodles],
        })
    chalk = np.clip(np.random.default_rng(5).uniform(0.55, 1.0, (OUT_H, OUT_W)).astype(np.float32), 0, 1)
    return {"cards": cards, "chalk": cv2.GaussianBlur(chalk, (0, 0), 0.7)}


def render_montage(t, montage):
    cards = montage["cards"]
    dur = (MONTAGE_END - MONTAGE_START) / len(cards)
    k = min(int((t - MONTAGE_START) / dur), len(cards) - 1)
    u = t - MONTAGE_START - k * dur
    c = cards[k]

    # slam in (overshoot), settle, then a slow push
    if u < 0.12:
        s = 1.32 + (0.97 - 1.32) * ease_out(u / 0.12)
    elif u < 0.24:
        s = 0.97 + 0.03 * ease_in_out((u - 0.12) / 0.12)
    else:
        s = 1.0 + 0.035 * (u - 0.24) / max(dur - 0.24, 0.01)
    rot = c["tilt"] + (6 if k % 2 else -6) * (1 - ease_out(u / 0.18))
    shake = 14 * (1 - ease_out(u / 0.14))
    dx, dy = shake * math.sin(u * 95), shake * math.cos(u * 70)

    H, W = c["alpha"].shape
    M = cv2.getRotationMatrix2D((W / 2, H / 2), rot, s)
    M[0, 2] += OUT_W / 2 + dx - W / 2
    M[1, 2] += CARD_CY + dy - H / 2
    size = (OUT_W, OUT_H)
    out = c["plate"] * (1 - cv2.warpAffine(c["shadow"], M, size, flags=cv2.INTER_LINEAR))[:, :, None]
    a = cv2.warpAffine(c["alpha"], M, size, flags=cv2.INTER_LINEAR)[:, :, None]
    out = out * (1 - a) + cv2.warpAffine(c["rgb"], M, size, flags=cv2.INTER_LINEAR) * a

    # chalk doodles draw on, one after another
    mask = np.zeros((OUT_H, OUT_W), np.uint8)
    for j, lines in enumerate(c["doodles"]):
        p = (u - 0.10 - 0.07 * j) / 0.22
        if p > 0:
            draw_partial(mask, lines, min(p, 1.0))
    if mask.any():
        m = (mask.astype(np.float32) / 255 * montage["chalk"])[:, :, None]
        out = out * (1 - m) + 246 * m

    if u < 0.10:  # flash on impact
        out += (255 - out) * 0.35 * (1 - u / 0.10)
    return out


def ease_in_out(x):
    x = min(max(x, 0.0), 1.0)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def interp(keys, t):
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t0 <= t <= t1:
            return v0 + (v1 - v0) * ease_in_out((t - t0) / (t1 - t0) if t1 > t0 else 1)
    return keys[-1][1]


def zoom_at(t):
    z = 1.0
    for t0, t1, z0, z1 in ZOOM:
        if t0 <= t < t1:
            z = z0 + (z1 - z0) * (t - t0) / (min(t1, 15.0) - t0)
            break
    for it, idur, iz in IMPACTS:
        if it <= t < it + idur:
            z = iz + (z - iz) * ease_out((t - it) / idur)
    return z


def layout(t):
    """Return (scale, src_cx, src_cy, endcard_mix) for time t."""
    z = zoom_at(min(t, PULL_START))
    crop_w, crop_h = OUT_W / OUT_H * SRC_H / z, SRC_H / z
    s_crop = OUT_H / crop_h
    cx = interp(FACE_X, min(t, PULL_START)) * SRC_W
    cy = interp(FACE_Y, min(t, PULL_START)) * SRC_H + 0.12 * crop_h
    cx = min(max(cx, crop_w / 2), SRC_W - crop_w / 2)
    cy = min(max(cy, crop_h / 2), SRC_H - crop_h / 2)

    x0, x1, y0, y1 = TEXT_BOX
    s_fit = TEXT_WIDTH_OUT / (x1 - x0)
    fx, fy = (x0 + x1) / 2, (y0 + y1) / 2
    m = ease_in_out((t - PULL_START) / (PULL_END - PULL_START))
    s = math.exp(math.log(s_crop) * (1 - m) + math.log(s_fit) * m)
    return s, cx + (fx - cx) * m, cy + (fy - cy) * m, m


def make_grade():
    x = np.arange(256) / 255.0
    curve = np.clip(0.5 + (x - 0.5) * 1.10, 0, 1) ** 0.98  # a little more contrast
    lut = (curve * 255).astype(np.uint8)
    sat = np.clip(np.arange(256) * 1.10, 0, 255).astype(np.uint8)
    yy, xx = np.mgrid[0:OUT_H, 0:OUT_W].astype(np.float32)
    r = np.sqrt(((xx - OUT_W / 2) / (OUT_W / 2)) ** 2 + ((yy - OUT_H / 2) / (OUT_H / 2)) ** 2) / math.sqrt(2)
    vig = (1.0 - 0.22 * np.clip((r - 0.35) / 0.65, 0, 1) ** 1.6).astype(np.float32)
    rng = np.random.default_rng(7)
    grain = [cv2.GaussianBlur(rng.normal(0, 4.0, (OUT_H, OUT_W)).astype(np.float32), (0, 0), 0.6) for _ in range(8)]
    return lut, sat, cv2.merge([vig, vig, vig]), grain


def edge_feather(width):
    """Source-space mask that fades the top/bottom `width` px of the frame into black."""
    y = np.arange(SRC_H, dtype=np.float32)
    d = np.minimum(y, SRC_H - 1 - y)
    col = np.clip(d / max(width, 1.0), 0, 1) ** 1.5
    return np.repeat(col[:, None], SRC_W, axis=1)


def render_handle():
    """Red bar + handle text on black (BGR float), drawn at 4x and scaled down for smooth edges."""
    k = 4
    font = ImageFont.truetype(HANDLE_FONT, HANDLE_SIZE * k)
    x0, y0, x1, y1 = font.getbbox(HANDLE)
    ascent, descent = font.getmetrics()
    bar_w, gap, pad = 3 * k, 22 * k, 6 * k
    w = bar_w + gap + x1 + pad
    h = ascent + descent + 2 * pad
    im = Image.new("RGB", (w, h), (0, 0, 0))
    d = ImageDraw.Draw(im)
    bar_top = pad + int(ascent * 0.28)
    d.rectangle((0, bar_top, bar_w, pad + ascent + int(descent * 0.2)), fill=HANDLE_BAR)
    d.text((bar_w + gap, pad), HANDLE, font=font, fill=(242, 242, 242))
    im = im.resize((w // k, h // k), Image.LANCZOS)
    patch = np.asarray(im, dtype=np.float32)[:, :, ::-1].copy()
    # soft shadow under the text so it stays readable over bright hair/skin
    shadow = cv2.GaussianBlur(patch.max(axis=2) / 255.0, (0, 0), 3.0)
    shadow = np.clip(shadow * 1.6, 0, 1)[:, :, None] * 0.45
    return patch, shadow


def render_frame(src, t, look, wm, montage=None):
    lut, sat, vig, grain = look
    if montage and MONTAGE_START <= t < MONTAGE_END:
        out = render_montage(t, montage) * vig + grain[int(t * FPS) % len(grain)][:, :, None]
        return overlay_handle(out, t, wm)
    s, cx, cy, _ = layout(t)
    M = np.float32([[s, 0, OUT_W / 2 - s * cx], [0, s, OUT_H / 2 - s * cy]])
    out = cv2.warpAffine(src, M, (OUT_W, OUT_H), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_CONSTANT)
    if t >= PULL_START:
        # The frame's top/bottom edges come into view as soon as the pull-back starts:
        # grow the feather with them so the smoke never shows a hard edge.
        width = 160 * min(1.0, 3 * (t - PULL_START) / (PULL_END - PULL_START))
        f = cv2.warpAffine(edge_feather(width), M, (OUT_W, OUT_H), flags=cv2.INTER_LINEAR, borderValue=0)
        out = (out * cv2.merge([f, f, f])).astype(np.uint8)

    # sharpen (stronger while zoomed in), grade, vignette, grain
    amt = 0.25 + 0.25 * min(max((s - 1.78) / 0.6, 0), 1)
    blur = cv2.GaussianBlur(out, (0, 0), 1.3)
    out = cv2.addWeighted(out, 1 + amt, blur, -amt, 0)
    out = cv2.LUT(out, lut)
    hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV)
    hsv[:, :, 1] = cv2.LUT(hsv[:, :, 1], sat)
    out = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR).astype(np.float32) * vig
    out += grain[int(t * FPS) % len(grain)][:, :, None]
    return overlay_handle(out, t, wm)


def overlay_handle(out, t, wm):
    """Instagram handle, screen-blended over a soft shadow."""
    a = 1 - min(max((t - WM_FADE[0]) / (WM_FADE[1] - WM_FADE[0]), 0), 1)
    if a > 0:
        patch, shadow = wm
        x, y = WM_POS
        h, w = patch.shape[:2]
        roi = out[y:y + h, x:x + w] * (1 - shadow * a)
        out[y:y + h, x:x + w] = roi + (255 - roi) * (patch * a / 255.0)
    return np.clip(out, 0, 255).astype(np.uint8)


def frames(source):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", source, "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         stdout=subprocess.PIPE)
    n = SRC_W * SRC_H * 3
    try:
        while True:
            buf = p.stdout.read(n)
            if len(buf) < n:
                break
            yield np.frombuffer(buf, np.uint8).reshape(SRC_H, SRC_W, 3)
    finally:
        p.stdout.close()
        p.terminate()
        p.wait()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--out", default="launch-reel.mp4")
    ap.add_argument("--preview", help="comma-separated seconds: save a contact sheet PNG instead of a video")
    args = ap.parse_args()

    look = make_grade()
    wm = render_handle()
    montage = build_montage()
    preview = sorted(float(x) for x in args.preview.split(",")) if args.preview else None
    picked = {}

    enc = None
    if not preview:
        enc = subprocess.Popen([
            "ffmpeg", "-v", "error", "-y",
            "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{OUT_W}x{OUT_H}", "-r", str(FPS), "-i", "-",
            "-i", args.source, "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-maxrate", "14M", "-bufsize", "28M",
            "-pix_fmt", "yuv420p", "-profile:v", "high",
            "-af", "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000,alimiter=limit=0.79:attack=2:release=60:level=false",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-movflags", "+faststart", "-shortest", args.out,
        ], stdin=subprocess.PIPE)

    total = 0
    for i, fr in enumerate(frames(args.source)):
        t = i / FPS
        total = i + 1
        if preview:
            for p in preview:
                if p not in picked and round(p * FPS) == i:
                    picked[p] = render_frame(fr, t, look, wm, montage)
            continue
        enc.stdin.write(render_frame(fr, t, look, wm, montage).tobytes())
        if i % 30 == 0:
            print(f"\rframe {i}", end="", flush=True)

    if preview:
        tiles = []
        for p in preview:
            img = cv2.resize(picked[p], (OUT_W // 3, OUT_H // 3))
            cv2.putText(img, f"{p:.2f}s", (12, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)
            tiles.append(img)
        while len(tiles) % 5:
            tiles.append(np.zeros_like(tiles[0]))
        rows = [np.hstack(tiles[r:r + 5]) for r in range(0, len(tiles), 5)]
        cv2.imwrite(args.out, np.vstack(rows))
        print(f"Saved preview {args.out}")
        return

    enc.stdin.close()
    if enc.wait() != 0:
        sys.exit("ffmpeg failed")
    print(f"\rSaved {args.out} ({total} frames, {total / FPS:.2f}s)")


if __name__ == "__main__":
    main()
