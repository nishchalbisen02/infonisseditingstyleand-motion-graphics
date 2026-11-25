#!/usr/bin/env python3
"""Launch reel: turn the 16:9 launch clip into a 9:16 reel.

  python3 motion-graphics/projects/launch-reel/edit.py SOURCE.mov [--out reel.mp4]
  python3 motion-graphics/projects/launch-reel/edit.py SOURCE.mov --preview 0.5,3,6,12,15.3,16.5 --out sheet.png

What it does (audio is kept exactly in sync, nothing is retimed):
  - vertical crop that follows the face in each shot
  - punch-in zoom cuts in the speech pauses, plus an impact zoom on the shot change
  - pull-back on the smoke so the full "Let'smakesomenoise" end card fits the vertical frame
  - light grade (contrast, saturation, vignette), fine film grain, mild sharpening
  - the "makesamaynoise" handle moved from the 16:9 corner into the vertical frame
  - loudness normalised for Instagram (-14 LUFS)

Needs: ffmpeg, numpy, opencv-python-headless<5
"""
import argparse
import math
import subprocess
import sys

import cv2
import numpy as np

SRC_W, SRC_H = 1920, 1080
OUT_W, OUT_H = 1080, 1920
FPS = 30
CUT = 157 / FPS  # shot change: lamp close-up -> lying-down selfie

# Face centre (fraction of source width), smoothed keyframes per shot.
FACE_X = [
    (0.00, 0.385), (1.60, 0.385), (2.20, 0.362), (3.00, 0.400), (3.80, 0.352), (4.40, 0.335), (CUT - 0.01, 0.360),
    (CUT, 0.520), (7.0, 0.530), (9.0, 0.550), (11.0, 0.540), (13.0, 0.530), (15.0, 0.530),
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
IMPACT = (CUT, 0.40, 1.30)  # time, duration, starting zoom of the punch on the shot change

# End card: pull back from the face crop to fit the text block.
PULL_START, PULL_END = 15.05, 15.75
TEXT_BOX = (226, 1684, 596, 833)  # x0, x1, y0, y1 of text + underline in the source
TEXT_WIDTH_OUT = 960              # text width in the reel, px

# Handle watermark: source box, where it goes in the reel, and when it disappears.
WM_SRC = (70, 330, 62, 118)       # x0, x1, y0, y1 (taken from a dark frame)
WM_FRAME_T = 8.0
WM_POS, WM_SCALE = (64, 210), 1.35
WM_FADE = (14.20, 14.45)


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
    it, idur, iz = IMPACT
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


def extract_watermark(frame):
    x0, x1, y0, y1 = WM_SRC
    patch = frame[y0:y1, x0:x1].astype(np.float32)
    patch = np.clip((patch - 40) * 255 / 215, 0, 255)
    size = (int((x1 - x0) * WM_SCALE), int((y1 - y0) * WM_SCALE))
    return cv2.resize(patch, size, interpolation=cv2.INTER_CUBIC)


def render_frame(src, t, look, wm):
    lut, sat, vig, grain = look
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

    # handle watermark (screen blend)
    a = 1 - min(max((t - WM_FADE[0]) / (WM_FADE[1] - WM_FADE[0]), 0), 1)
    if a > 0:
        x, y = WM_POS
        h, w = wm.shape[:2]
        roi = out[y:y + h, x:x + w]
        out[y:y + h, x:x + w] = roi + (255 - roi) * (wm * a / 255.0)
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
    wm = None
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

    # The watermark is taken from a dark frame, so grab that frame first.
    for i, fr in enumerate(frames(args.source)):
        if i == int(WM_FRAME_T * FPS):
            wm = extract_watermark(fr)
            break

    total = 0
    for i, fr in enumerate(frames(args.source)):
        t = i / FPS
        total = i + 1
        if preview:
            for p in preview:
                if p not in picked and round(p * FPS) == i:
                    picked[p] = render_frame(fr, t, look, wm)
            continue
        enc.stdin.write(render_frame(fr, t, look, wm).tobytes())
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
