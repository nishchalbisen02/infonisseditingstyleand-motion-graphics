#!/usr/bin/env python3
"""Launch intro: a crunchy collage motion-graphics reel from the owner's cut-out photos + logo.

  python3 motion-graphics/projects/launch-intro/music.py motion-graphics/projects/launch-intro/build/music.wav
  python3 motion-graphics/projects/launch-intro/intro.py --out launch-intro.mp4
  python3 motion-graphics/projects/launch-intro/intro.py --preview 0.6,2.2,5.6,9,12.3 --out sheet.png

Needs assets/ready/ from prep.py (owner photos: git-ignored, re-upload per session) and the music wav.
1080x1920, 30 fps, 16 s, locked to a 120 BPM grid (one beat = 15 frames). Graphics "boil" at 10 fps
(outlines, doodles and letters re-jitter every 3 frames) for the stop-motion / crunchy look.
"""
import argparse
import math
import os
import subprocess
import sys
import zlib

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
READY = os.path.join(HERE, "assets", "ready")
FONTS = os.path.join(HERE, "..", "..", "assets", "fonts")
ANTON = os.path.join(FONTS, "Anton-Regular.ttf")
MARKER = os.path.join(FONTS, "PermanentMarker-Regular.ttf")
MUSIC = os.path.join(HERE, "build", "music.wav")

W, H, FPS = 1080, 1920, 30
BEAT = 0.5
LENGTH = 16.0
BOIL_FPS = 10
HANDLE = "@letssmakesomenoise"

# brand palette (BGR), sampled from the owner's artworks
ORANGE = (24, 80, 214)
DARK_ORANGE = (16, 52, 150)
BLACK = (18, 16, 16)
CREAM = (226, 236, 243)
GREEN = (51, 71, 28)
RED = (92, 50, 232)
BLUE = (200, 128, 70)
YELLOW = (32, 184, 245)
WHITE = (246, 246, 246)


# ----------------------------------------------------------------------------------------------
# easing / timing
def clamp01(x):
    return min(max(x, 0.0), 1.0)


def ease_out(x):
    return 1 - (1 - clamp01(x)) ** 3


def ease_in(x):
    return clamp01(x) ** 3


def ease_in_out(x):
    x = clamp01(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def slam(u, big=0.45, dur=0.12):
    """Scale multiplier for an element that lands at u=0: big -> slight undershoot -> 1."""
    if u < 0:
        return None
    if u < dur:
        return 1 + big * (1 - ease_out(u / dur))
    if u < dur + 0.08:
        return 1 - 0.035 * math.sin(math.pi * (u - dur) / 0.08)
    return 1.0


def boil_step(t):
    return int(t * BOIL_FPS)


def hsh(x):
    """Stable hash (Python's hash() changes between runs)."""
    return zlib.crc32(repr(x).encode())


def jitter(t, key, amp):
    """Deterministic 10 fps jitter for element `key`."""
    r = np.random.default_rng((boil_step(t) * 7919 + hsh(key)) & 0xFFFFFFFF)
    return r.uniform(-amp, amp), r.uniform(-amp, amp)


# ----------------------------------------------------------------------------------------------
# sprites
class Sprite:
    def __init__(self, rgb, a):
        self.rgb = np.ascontiguousarray(rgb, np.float32)
        self.a = np.ascontiguousarray(a, np.float32)
        self._mips = {}
        self._tints = {}

    @property
    def w(self):
        return self.a.shape[1]

    @property
    def h(self):
        return self.a.shape[0]

    def mip(self, scale):
        """A pre-shrunk copy when drawing small (warpAffine aliases when shrinking a lot)."""
        level = 0
        while scale * (2 ** (level + 1)) <= 1.0 and level < 3:
            level += 1
        if level == 0:
            return self, 1.0
        if level not in self._mips:
            f = 0.5 ** level
            size = (max(int(self.w * f), 1), max(int(self.h * f), 1))
            self._mips[level] = Sprite(cv2.resize(self.rgb, size, interpolation=cv2.INTER_AREA),
                                       cv2.resize(self.a, size, interpolation=cv2.INTER_AREA))
        return self._mips[level], 2 ** level

    def tinted(self, color):
        key = tuple(color)
        if key not in self._tints:
            self._tints[key] = Sprite(np.broadcast_to(np.array(color, np.float32), self.rgb.shape), self.a)
        return self._tints[key]


def load(name, height=None):
    im = cv2.imread(os.path.join(READY, name), cv2.IMREAD_UNCHANGED)
    if im is None:
        sys.exit(f"missing {name} in {READY}: run prep.py first")
    if height:
        f = height / im.shape[0]
        im = cv2.resize(im, (int(im.shape[1] * f), height), interpolation=cv2.INTER_AREA if f < 1 else cv2.INTER_CUBIC)
    return Sprite(im[:, :, :3], im[:, :, 3] / 255.0)


def smooth_noise(shape, scale, seed):
    r = np.random.default_rng(seed)
    small = r.normal(0, 1, (max(shape[0] // scale, 2), max(shape[1] // scale, 2))).astype(np.float32)
    big = cv2.resize(small, (shape[1], shape[0]), interpolation=cv2.INTER_CUBIC)
    return big / (np.abs(big).max() + 1e-6)


def sticker(sp, r=16, color=WHITE, seed=0, rough=5.0):
    """White die-cut sticker border with a slightly ragged paper edge."""
    pad = int(r + rough + 6)
    a = np.pad(sp.a, pad)
    rgb = np.pad(sp.rgb, ((pad, pad), (pad, pad), (0, 0)))
    inside = (a > 0.5).astype(np.uint8)
    dist = cv2.distanceTransform(1 - inside, cv2.DIST_L2, 5)
    edge = r + rough * smooth_noise(a.shape, 24, seed)
    outline = np.clip(edge - dist + 0.5, 0, 1).astype(np.float32)
    out_a = np.maximum(outline, a)
    out_rgb = rgb * a[:, :, None] + np.array(color, np.float32) * (1 - a[:, :, None])
    return Sprite(out_rgb, out_a)


def boil_set(sp, n=3, **kw):
    return [sticker(sp, seed=s, **kw) for s in range(n)]


def text_sprite(text, font, size, fill, stroke=0, stroke_fill=(0, 0, 0)):
    f = ImageFont.truetype(font, size)
    x0, y0, x1, y1 = f.getbbox(text, stroke_width=stroke)
    pad = 6
    im = Image.new("RGBA", (x1 - x0 + 2 * pad, y1 - y0 + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad - x0, pad - y0), text, font=f, fill=tuple(fill[::-1]) + (255,),
                            stroke_width=stroke, stroke_fill=tuple(stroke_fill[::-1]) + (255,))
    arr = np.asarray(im).astype(np.float32)
    return Sprite(arr[:, :, 2::-1], arr[:, :, 3] / 255.0)


def letters(text, font, size, fill, stroke=0, stroke_fill=(0, 0, 0)):
    """Per-letter sprites + x offsets (letter centre relative to word centre), for letter boil."""
    f = ImageFont.truetype(font, size)
    total = f.getlength(text)
    out = []
    for i, ch in enumerate(text):
        x = f.getlength(text[:i]) + f.getlength(ch) / 2 - total / 2
        im = Image.new("RGBA", (int(f.getlength(ch)) + 2 * stroke + 20, int(size * 1.35)), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((10 + stroke, 0), ch, font=f, fill=tuple(fill[::-1]) + (255,),
                                stroke_width=stroke, stroke_fill=tuple(stroke_fill[::-1]) + (255,))
        arr = np.asarray(im).astype(np.float32)
        out.append((Sprite(arr[:, :, 2::-1], arr[:, :, 3] / 255.0), x))
    return out


# ----------------------------------------------------------------------------------------------
# drawing
def draw(canvas, sp, x, y, scale=1.0, rot=0.0, alpha=1.0, shadow=None):
    """Composite sprite centred at (x, y). shadow = (dx, dy, color, opacity) for a hard riso shadow."""
    if scale <= 0.01 or alpha <= 0.003:
        return
    if shadow:
        dx, dy, color, op = shadow
        draw(canvas, sp.tinted(color), x + dx, y + dy, scale, rot, alpha * op)
    src, f = sp.mip(scale)
    s = scale * f
    M = cv2.getRotationMatrix2D((src.w / 2, src.h / 2), rot, s)
    M[0, 2] += x - src.w / 2
    M[1, 2] += y - src.h / 2
    corners = np.array([[0, 0, 1], [src.w, 0, 1], [0, src.h, 1], [src.w, src.h, 1]], np.float32) @ M.T
    x0, y0 = np.floor(corners.min(axis=0)).astype(int) - 2
    x1, y1 = np.ceil(corners.max(axis=0)).astype(int) + 2
    x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
    if x1 <= x0 or y1 <= y0:
        return
    M[0, 2] -= x0
    M[1, 2] -= y0
    size = (x1 - x0, y1 - y0)
    a = cv2.warpAffine(src.a, M, size, flags=cv2.INTER_LINEAR)[:, :, None] * alpha
    rgb = cv2.warpAffine(src.rgb, M, size, flags=cv2.INTER_LINEAR)
    roi = canvas[y0:y1, x0:x1]
    roi *= 1 - a
    roi += rgb * a


def make_plate(color, seed, dots=True, dot_color=None, spacing=24, angle=28):
    """Flat colour + paper blotches + a halftone dot field."""
    base = np.empty((H, W, 3), np.float32)
    base[:] = color
    base *= 1 + 0.07 * smooth_noise((H, W), 90, seed)[:, :, None]
    if dots:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        u, v = xx * c + yy * s, -xx * s + yy * c
        du = (u % spacing) - spacing / 2
        dv = (v % spacing) - spacing / 2
        d = np.sqrt(du * du + dv * dv)
        field = (smooth_noise((H, W), 260, seed + 1) * 0.5 + 0.5) ** 1.5
        dot = np.clip(field * spacing * 0.42 - d + 0.5, 0, 1)[:, :, None] * 0.55
        dc = np.array(dot_color if dot_color else [c_ * 0.72 for c_ in color], np.float32)
        base = base * (1 - dot) + dc * dot
    return base


ANGLES = {}


def sunburst(canvas, color, rot, rays=22, opacity=0.6, cx=W / 2, cy=H / 2):
    if (cx, cy) not in ANGLES:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        ANGLES[(cx, cy)] = np.arctan2(yy - cy, xx - cx)
    step = 2 * math.pi / rays
    m = (((ANGLES[(cx, cy)] + rot) % step) < step / 2).astype(np.float32)[:, :, None] * opacity
    canvas *= 1 - m
    canvas += np.array(color, np.float32) * m


# ----------------------------------------------------------------------------------------------
# chalk doodles
SHAPES = {
    "burst": [[(28 * math.cos(a), 28 * math.sin(a)), (r * math.cos(a), r * math.sin(a))]
              for a, r in ((-0.56, 96), (0.0, 112), (0.56, 96))],
    "bolt": [[(-12, -62), (14, -10), (-6, -6), (20, 60)]],
    "star": [[(-28, 0), (28, 0)], [(0, -28), (0, 28)], [(-11, -11), (11, 11)]],
    "squiggle": [[(-210, 6), (-178, -9), (-194, 11), (-158, -2), (210, -14)]],
    "crown": [[(-70, 30), (-80, -40), (-38, 0), (0, -58), (38, 0), (80, -40), (70, 30), (-70, 30)],
              [(-60, 14), (60, 14)]],
    "circle": [[(90 * math.cos(a), 52 * math.sin(a)) for a in np.linspace(0.2, 2 * math.pi + 0.9, 28)]],
    "arrow": [[(-90, 40), (-30, -10), (40, -30), (90, -40)], [(60, -70), (92, -40), (58, -8)]],
}
CHALK = None


def wobble(pts, rng, step=6.0, amp=2.2):
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


def doodle(canvas, kind, x, y, t, ang=0.0, size=1.5, progress=1.0, color=WHITE, thick=10, key=""):
    """Chalk doodle that boils at 10 fps; progress 0..1 draws it on."""
    global CHALK
    if progress <= 0:
        return
    if CHALK is None:
        CHALK = cv2.GaussianBlur(np.random.default_rng(5).uniform(0.55, 1.0, (H, W)).astype(np.float32), (0, 0), 0.7)
    rng = np.random.default_rng((boil_step(t) * 31 + hsh((kind, key, round(x), round(y)))) & 0xFFFFFFFF)
    a = math.radians(ang)
    ca, sa = math.cos(a), math.sin(a)
    lines = []
    for line in SHAPES[kind]:
        pts = [(x + size * (px * ca - py * sa), y + size * (px * sa + py * ca)) for px, py in line]
        lines.append(wobble(pts, rng))
    total = sum(float(np.linalg.norm(np.diff(l, axis=0), axis=1).sum()) for l in lines)
    budget = total * clamp01(progress)
    allp = np.concatenate(lines)
    bx0, by0 = np.maximum(allp.min(axis=0).astype(int) - thick - 4, 0)
    bx1, by1 = np.minimum(allp.max(axis=0).astype(int) + thick + 4, [W, H])
    if bx1 <= bx0 or by1 <= by0:
        return
    mask = np.zeros((by1 - by0, bx1 - bx0), np.uint8)
    for l in lines:
        if budget <= 0:
            break
        seg = np.linalg.norm(np.diff(l, axis=0), axis=1)
        keep = int(np.searchsorted(np.cumsum(seg), budget)) + 2
        budget -= float(seg.sum())
        pts = ((l[:keep] - [bx0, by0]) * 4).astype(np.int32)
        cv2.polylines(mask, [pts], False, 255, thick, cv2.LINE_AA, shift=2)
    m = (mask.astype(np.float32) / 255 * CHALK[by0:by1, bx0:bx1])[:, :, None]
    roi = canvas[by0:by1, bx0:bx1]
    roi *= 1 - m
    roi += np.array(color, np.float32) * m


# ----------------------------------------------------------------------------------------------
# assets
class Assets:
    def __init__(self):
        cut = {
            "greenhat": load("greenhat.png", 1150),
            "niss": load("niss-orange.png", 1150),
            "boxface": load("boxface.png", 1150),
            "filmstrip": load("filmstrip.png", 1100),
            "topdown": load("topdown.png", 1000),
            "hand": load("hand.png", 1200),
        }
        self.stickers = {k: boil_set(v, r=18) for k, v in cut.items()}
        self.ink = load("poster-ink.png", 1150)
        self.ink_orange = self.ink.tinted(BLACK)
        logo = load("logo-white.png")
        self.logo = logo
        self.plates = {
            "black": make_plate(BLACK, 1, dot_color=(40, 36, 36)),
            "orange": make_plate(ORANGE, 2),
            "green": make_plate(GREEN, 3),
            "cream": make_plate(CREAM, 4, dot_color=(190, 205, 215)),
            "red": make_plate(RED, 5),
            "blue": make_plate(BLUE, 6),
        }
        # countdown digits and words
        self.digits = {d: boil_set(text_sprite(d, ANTON, 1000, c), r=16)
                       for d, c in (("3", ORANGE), ("2", CREAM), ("1", YELLOW))}
        self.words = {
            "LET'S": letters("LET'S", ANTON, 520, BLACK),
            "MAKE": letters("MAKE", ANTON, 560, CREAM),
            "SOME": letters("SOME", ANTON, 560, RED, stroke=10, stroke_fill=BLACK),
            "NOISE": letters("NOISE", ANTON, 470, WHITE, stroke=16, stroke_fill=BLACK),
        }
        # scrolling ribbon (marquee band)
        self.ribbons = {}
        for name, band, ink in (("black", BLACK, CREAM), ("cream", CREAM, BLACK)):
            txt = text_sprite("LET'S MAKE SOME NOISE  /  ", ANTON, 78, ink)
            reps = int(math.ceil(2600 / txt.w)) + 1
            hgt = 128
            rgb = np.empty((hgt, txt.w * reps, 3), np.float32)
            rgb[:] = band
            a = np.ones((hgt, txt.w * reps), np.float32)
            y0 = (hgt - txt.h) // 2
            for k in range(reps):
                sl = (slice(y0, y0 + txt.h), slice(k * txt.w, (k + 1) * txt.w))
                rgb[sl] = rgb[sl] * (1 - txt.a[:, :, None]) + txt.rgb * txt.a[:, :, None]
            self.ribbons[name] = (rgb, a, txt.w)
        self.handle = text_sprite(HANDLE, ANTON, 76, BLACK)
        self.follow = text_sprite("FOLLOW", MARKER, 70, YELLOW)
        self.niss_tag = boil_set(text_sprite("NISS", MARKER, 150, WHITE, stroke=8, stroke_fill=BLACK), r=10,
                                 color=BLACK)
        r = np.random.default_rng(9)
        self.grain = [cv2.GaussianBlur(r.normal(0, 7.0, (H, W)).astype(np.float32), (0, 0), 0.7) for _ in range(6)]
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        rr = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / math.sqrt(2)
        v = (1.0 - 0.28 * np.clip((rr - 0.4) / 0.6, 0, 1) ** 1.5).astype(np.float32)
        self.vignette = v[:, :, None]

    def st(self, name, t):
        """Boiling sticker variant for this 10 fps step."""
        s = self.stickers[name]
        return s[boil_step(t) % len(s)]


def ribbon(canvas, assets, kind, y, angle, t, speed=520):
    rgb, a, period = assets.ribbons[kind]
    off = int(t * speed) % period
    band = Sprite(np.roll(rgb, -off, axis=1)[:, :2300], np.roll(a, -off, axis=1)[:, :2300])
    draw(canvas, band, W / 2, y, 1.0, angle, shadow=(10, 14, BLACK, 0.45))


def word(canvas, letters_, x, y, t, scale=1.0, rot=0.0, amp=6, shadow=None, key="w"):
    for i, (sp, dx) in enumerate(letters_):
        jx, jy = jitter(t, (key, i), amp)
        jr = jitter(t, (key, i, "r"), 3)[0]
        c, s = math.cos(math.radians(-rot)), math.sin(math.radians(-rot))
        px = x + (dx * c) * scale + jx
        py = y + (dx * s) * scale + jy
        draw(canvas, sp, px, py, scale, rot + jr, shadow=shadow)


# ----------------------------------------------------------------------------------------------
# scenes (t in seconds; beats every 0.5 s)
def scene_countdown(c, A, t):
    c[:] = A.plates["black"]
    doodle(c, "squiggle", W / 2, 980, t, size=2.3, progress=t / 0.45, key="intro")
    items = [(0.5, "3", "black", "greenhat", (820, 1620, -12)),
             (1.0, "2", "orange", "niss", (250, 1620, 10)),
             (1.5, "1", "green", "topdown", (840, 1600, -6))]
    for t0, d, plate, who, (hx, hy, hr) in items:
        if t0 <= t < t0 + 0.5:
            u = t - t0
            c[:] = A.plates[plate]
            doodle(c, "squiggle", W / 2, 1500, t, size=2.0, key="u" + d)
            peek = ease_out(u / 0.16)
            draw(c, A.st(who, t), hx, hy + (1 - peek) * 700, 0.52, hr, shadow=(16, 20, BLACK, 0.5))
            s = slam(u, 0.5)
            dig = A.digits[d][boil_step(t) % 3]
            draw(c, dig, W / 2 + jitter(t, d, 5)[0], 820, 0.95 * s, -4 if d == "2" else 4,
                 shadow=(18, 24, BLACK, 0.6))
            doodle(c, "burst", 860, 300, t, -45, 1.6, (u - 0.05) / 0.15, key=d)
            doodle(c, "star", 170, 380, t, 0, 1.3, (u - 0.1) / 0.15, key=d)


DROP = [("greenhat", "orange", "black", -5), ("niss", "green", "cream", 5),
        ("boxface", "cream", "black", -4), ("filmstrip", "red", "black", 4)]


def scene_drop(c, A, t):
    k = min(int((t - 2.0) / BEAT), 3)
    who, plate, rib, rot = DROP[k]
    u = t - 2.0 - k * BEAT
    c[:] = A.plates[plate]
    ribbon(c, A, rib, 1260, -12 if k % 2 == 0 else 10, t)
    pop = 1.0 + (0.05 * (1 - ease_out((u - 0.25) / 0.1)) if u >= 0.25 else 0)
    s = slam(u, 0.55) * pop
    jx, jy = jitter(t, "drop", 4)
    draw(c, A.st(who, t), W / 2 + jx, 900 + jy, s, rot, shadow=(20, 26, BLACK, 0.55))
    doodle(c, "burst", 900, 330, t, -45, 1.7, (u - 0.04) / 0.14, key=who)
    doodle(c, "bolt", 160, 520, t, -15, 1.5, (u - 0.08) / 0.14, color=YELLOW, key=who)
    doodle(c, "star", 190, 1500, t, 0, 1.3, (u - 0.12) / 0.14, key=who)
    doodle(c, "star", 900, 1560, t, 0, 0.9, (u - 0.16) / 0.14, key=who)


def scene_words(c, A, t):
    k = min(int((t - 4.0) / BEAT), 3)
    u = t - 4.0 - k * BEAT
    s = slam(u, 0.4)
    if k == 0:
        c[:] = A.plates["orange"]
        word(c, A.words["LET'S"], W / 2, 700, t, 0.9 * s, -5, key="lets")
        doodle(c, "squiggle", W / 2, 1010, t, -4, 2.0, (u - 0.05) / 0.15, key="lets")
        draw(c, A.st("topdown", t), 560, 1480 + (1 - ease_out(u / 0.18)) * 500, 0.78, 3, shadow=(16, 22, BLACK, 0.5))
    elif k == 1:
        c[:] = A.plates["black"]
        word(c, A.words["MAKE"], W / 2, 640, t, 0.88 * s, 4, key="make")
        hu = ease_out(u / 0.22)
        draw(c, A.st("hand", t), 640 + (1 - hu) * 300, 1380 + (1 - hu) * 700, 0.95, -18 + 12 * hu,
             shadow=(18, 24, (0, 0, 0), 0.5))
        doodle(c, "bolt", 150, 1150, t, -20, 1.6, (u - 0.1) / 0.14, color=YELLOW, key="make")
    elif k == 2:
        c[:] = A.plates["cream"]
        word(c, A.words["SOME"], W / 2, 640, t, 0.88 * s, -3, shadow=(14, 18, BLACK, 0.9), key="some")
        iu = ease_out(u / 0.2)
        draw(c, A.ink_orange, W / 2, 1420 + (1 - iu) * 600, 0.78, 0)
        doodle(c, "burst", 930, 300, t, -45, 1.6, (u - 0.05) / 0.14, color=BLACK, key="some")
    else:
        c[:] = A.plates["orange"]
        sunburst(c, DARK_ORANGE, t * 0.8, opacity=0.55)
        heads = [("greenhat", 230, 400, -12), ("niss", 860, 420, 12), ("boxface", 230, 1480, 8),
                 ("filmstrip", 860, 1500, -8)]
        for i, (who, hx, hy, hr) in enumerate(heads):
            hs = slam(u - 0.04 * i, 0.6)
            if hs:
                jx, jy = jitter(t, who, 8)
                draw(c, A.st(who, t), hx + jx, hy + jy, 0.4 * hs, hr, shadow=(12, 16, BLACK, 0.5))
        word(c, A.words["NOISE"], W / 2, 930, t, 0.94 * s, -6, amp=14, shadow=(14, 18, RED, 1.0), key="noise")
        doodle(c, "burst", 120, 820, t, 180, 1.6, (u - 0.06) / 0.12, key="noise")
        doodle(c, "burst", 960, 1040, t, 0, 1.6, (u - 0.06) / 0.12, key="noise")


RAPID = [("greenhat", "red"), ("niss", "black"), ("boxface", "orange"), ("filmstrip", "green"),
         ("topdown", "cream"), ("hand", "blue"), ("greenhat", "orange"), ("niss", "black")]


def scene_hand(c, A, t):
    if t < 7.0:
        u = t - 6.0
        c[:] = A.plates["cream"]
        sunburst(c, (205, 218, 228), -t * 0.6, opacity=0.6)
        ribbon(c, A, "black", 520, 8, t, speed=-600)
        a_in = ease_out(u / 0.3)
        out = ease_in((u - 0.72) / 0.28)
        x = 700 - 140 * a_in
        y = 2500 - 1450 * a_in - 2600 * out
        rot = -32 + 24 * a_in + 6 * math.sin(u * 9) * (1 - out)
        sc = 1.9 - 0.45 * a_in
        sp = A.st("hand", t)
        if out > 0:  # motion-smear ghosts on the whip out
            for g in range(1, 4):
                draw(c, sp, x, y + 160 * g * out, sc, rot, alpha=0.18)
        draw(c, sp, x, y, sc, rot, shadow=(24, 30, BLACK, 0.45))
        doodle(c, "arrow", 230, 1500, t, -30, 1.8, (u - 0.2) / 0.2, color=BLACK, key="hand")
        doodle(c, "star", 880, 380, t, 0, 1.4, (u - 0.25) / 0.15, color=BLACK, key="hand")
    else:
        k = min(int((t - 7.0) / 0.125), 7)
        u = t - 7.0 - k * 0.125
        who, plate = RAPID[k]
        c[:] = A.plates[plate]
        s = (0.75 + 0.06 * k) * slam(u, 0.3, 0.06)
        draw(c, A.st(who, t), W / 2, 930, s, 8 if k % 2 else -8, shadow=(18, 22, BLACK, 0.55))


COLLAGE = [
    # beat time, what, x, y, scale, rot
    (8.0, "ink", 560, 1160, 0.95, 0),
    (8.5, "greenhat", 255, 500, 0.52, -10),
    (9.0, "niss", 835, 540, 0.52, 9),
    (9.5, "boxface", 215, 1130, 0.44, -6),
    (10.0, "filmstrip", 875, 1150, 0.44, 7),
    (10.5, "topdown", 560, 1540, 0.5, -3),
    (11.0, "hand", 930, 1700, 0.62, -26),
    (11.5, "niss_tag", 560, 270, 1.0, -8),
]


def scene_collage(c, A, t):
    c[:] = A.plates["orange"]
    for i, (t0, what, x, y, sc, rot) in enumerate(COLLAGE):
        if i == 1:
            ribbon(c, A, "black", 1420, 9, t)  # over the ink drawing, under the stickers
        s = slam(t - t0, 0.5)
        if s is None:
            continue
        jx, jy = jitter(t, what, 4)
        jr = jitter(t, (what, "r"), 1.2)[0]
        if what == "ink":
            draw(c, A.ink_orange, x + jx, y + jy, sc * s, rot + jr)
        elif what == "niss_tag":
            draw(c, A.niss_tag[boil_step(t) % 3], x + jx, y + jy, sc * s, rot + jr, shadow=(10, 12, BLACK, 0.5))
            doodle(c, "crown", x + 170, y - 90, t, 14, 1.0, (t - t0 - 0.05) / 0.15, color=YELLOW, key="tag")
        else:
            draw(c, A.st(what, t), x + jx, y + jy, sc * s, rot + jr, shadow=(16, 20, BLACK, 0.5))
        p = (t - t0 - 0.03) / 0.14
        kinds = ("burst", "star", "bolt")
        doodle(c, kinds[i % 3], x + (150 if x < W / 2 else -150), y - 190, t, -45 if x < W / 2 else -135,
               1.3, p, color=YELLOW if i % 3 == 2 else WHITE, key=what)


def scene_logo(c, A, t):
    c[:] = A.plates["black"]
    sunburst(c, (20, 36, 90), t * 0.35, opacity=0.65, cy=760)
    u = t - 12.0
    # heads peeking from the bottom edge, bobbing on the beat
    for i, (who, hx, hr) in enumerate((("greenhat", 150, 8), ("niss", 410, -6), ("boxface", 670, 6),
                                        ("filmstrip", 930, -8))):
        t0 = 12.5 + 0.25 * i
        if t >= t0:
            rise = ease_out((t - t0) / 0.2)
            bob = 26 * (1 - ease_out(((t - 12.0) % BEAT) / 0.25)) if t > 13.5 else 0
            draw(c, A.st(who, t), hx, 1600 + (1 - rise) * 700 - bob, 0.5, hr, shadow=(12, 16, BLACK, 0.5))
    s = slam(u, 0.6, 0.14)
    jx, jy = jitter(t, "logo", 3)
    draw(c, A.logo, W / 2 + jx, 760 + jy, 0.97 * s, -3, shadow=(10, 12, RED, 1.0))
    for kind, x, y, ang, d in (("burst", 110, 600, 200, 0.05), ("burst", 975, 900, 20, 0.08),
                               ("star", 880, 500, 0, 0.12), ("star", 170, 1130, 0, 0.16)):
        doodle(c, kind, x, y, t, ang, 1.5, (u - d) / 0.15, key="logo")
    if t >= 13.0:  # handle on a tape label, typed in
        tu = t - 13.0
        n = int(len(HANDLE) * clamp01(tu / 0.45))
        tape_w = A.handle.w + 60
        tape = Sprite(np.full((A.handle.h + 36, tape_w, 3), ORANGE, np.float32),
                      np.ones((A.handle.h + 36, tape_w), np.float32))
        sub = Sprite(A.handle.rgb[:, : int(A.handle.w * n / len(HANDLE))], A.handle.a[:, : int(A.handle.w * n / len(HANDLE))])
        ts = slam(tu, 0.25, 0.08)
        draw(c, tape, W / 2, 1000, ts, 2, shadow=(10, 12, BLACK, 0.6))
        if sub.w > 2:
            # left-align the typed part inside the tape
            off = (sub.w - A.handle.w) / 2
            c2, s2 = math.cos(math.radians(-2)), math.sin(math.radians(-2))
            draw(c, sub, W / 2 + off * c2 * ts, 1000 + off * s2 * ts, ts, 2)
    if t >= 13.5:
        draw(c, A.follow, 300, 905, slam(t - 13.5, 0.4), -10)


SCENES = [(0.0, scene_countdown), (2.0, scene_drop), (4.0, scene_words), (6.0, scene_hand),
          (8.0, scene_collage), (12.0, scene_logo)]

# impact effects: (time, strength)
IMPACTS = ([(0.5, 0.6), (1.0, 0.6), (1.5, 0.6), (2.0, 1.0), (2.5, 0.5), (3.0, 0.5), (3.5, 0.5),
            (4.0, 0.6), (4.5, 0.6), (5.0, 0.6), (5.5, 1.0), (6.0, 0.5)]
           + [(7.0 + 0.125 * k, 0.35) for k in range(8)]
           + [(8.0 + 0.5 * k, 0.45) for k in range(8)] + [(12.0, 1.2), (13.0, 0.35), (15.0, 1.0)])


def post(c, A, t, i):
    # camera: slow push in the collage, punch on the last logo hit
    zoom = 1.0
    if 8.0 <= t < 12.0:
        zoom = 1.0 + 0.12 * ease_in_out((t - 8.0) / 4.0) + 0.05 * ease_in((t - 11.5) / 0.5)
    elif t >= 15.0:
        zoom = 1.0 + 0.06 * ease_out((t - 15.0) / 0.3)
    sx = sy = 0.0
    split = 1.0
    flash = 0.0
    for ti, k in IMPACTS:
        d = t - ti
        if 0 <= d < 0.4:
            e = math.exp(-d / 0.09)
            r = np.random.default_rng(int(ti * 1000) + i)
            sx += r.uniform(-1, 1) * 28 * k * e
            sy += r.uniform(-1, 1) * 28 * k * e
            split += 16 * k * math.exp(-d / 0.07)
            flash = max(flash, 0.45 * k * math.exp(-d / 0.035))
    if 11.5 <= t < 12.0:  # build-up shake
        e = ease_in((t - 11.5) / 0.5)
        r = np.random.default_rng(i)
        sx += r.uniform(-1, 1) * 22 * e
        sy += r.uniform(-1, 1) * 22 * e
        split += 10 * e
    if zoom != 1.0 or sx or sy:
        M = np.float32([[zoom, 0, (1 - zoom) * W / 2 + sx], [0, zoom, (1 - zoom) * H / 2 + sy]])
        c = cv2.warpAffine(c, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    k = int(round(split))
    if k > 0:
        b, g, r_ = cv2.split(c)
        c = cv2.merge([np.roll(b, -k, axis=1), g, np.roll(r_, k, axis=1)])
    if flash > 0:
        c += (255 - c) * flash
    # TV static: intro flicker, the gap before the drop, the cut into the logo
    st = 0.0
    if t < 0.5:
        st = 0.28 + 0.2 * (boil_step(t) % 2)
    elif 1.875 <= t < 2.0 or 11.93 <= t < 12.0:
        st = 0.92
    elif t < 2.0:
        st = 0.08
    if st > 0:
        noise = np.random.default_rng(i + 999).uniform(0, 255, (H // 3, W // 3)).astype(np.float32)
        noise = cv2.resize(noise, (W, H), interpolation=cv2.INTER_NEAREST)[:, :, None]
        c = c * (1 - st) + noise * st
    c = c * A.vignette + A.grain[boil_step(t) % len(A.grain)][:, :, None]
    if t > LENGTH - 0.25:
        c *= clamp01((LENGTH - t) / 0.25)
    return np.clip(c, 0, 255).astype(np.uint8)


def render(A, t, i):
    c = np.empty((H, W, 3), np.float32)
    fn = [f for t0, f in SCENES if t >= t0][-1]
    fn(c, A, t)
    return post(c, A, t, i)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="launch-intro.mp4")
    ap.add_argument("--preview", help="comma-separated seconds: contact sheet PNG instead of a video")
    ap.add_argument("--music", default=MUSIC)
    args = ap.parse_args()
    A = Assets()

    if args.preview:
        tiles = []
        for p in (float(x) for x in args.preview.split(",")):
            i = round(p * FPS)
            img = cv2.resize(render(A, i / FPS, i), (W // 3, H // 3), interpolation=cv2.INTER_AREA)
            cv2.putText(img, f"{p:.2f}s", (10, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
            tiles.append(img)
        while len(tiles) % 5:
            tiles.append(np.zeros_like(tiles[0]))
        cv2.imwrite(args.out, np.vstack([np.hstack(tiles[r:r + 5]) for r in range(0, len(tiles), 5)]))
        print(f"Saved preview {args.out}")
        return

    if not os.path.exists(args.music):
        sys.exit(f"missing {args.music}: run music.py first")
    enc = subprocess.Popen([
        "ffmpeg", "-v", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-i", args.music, "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "slow", "-crf", "19", "-maxrate", "16M", "-bufsize", "32M",
        "-pix_fmt", "yuv420p", "-profile:v", "high",
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000,alimiter=limit=0.79:attack=2:release=60:level=false",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", "-shortest", args.out,
    ], stdin=subprocess.PIPE)
    n = int(LENGTH * FPS)
    for i in range(n):
        enc.stdin.write(render(A, i / FPS, i).tobytes())
        if i % 30 == 0:
            print(f"\rframe {i}/{n}", end="", flush=True)
    enc.stdin.close()
    if enc.wait() != 0:
        sys.exit("ffmpeg failed")
    print(f"\rSaved {args.out} ({n} frames, {LENGTH:.1f}s)")


if __name__ == "__main__":
    main()
