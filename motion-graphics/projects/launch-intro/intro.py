#!/usr/bin/env python3
"""Launch intro v2: a scroll-stopping, crunchy collage motion-graphics reel from the owner's photos + logo.

  python3 motion-graphics/projects/launch-intro/music.py motion-graphics/projects/launch-intro/build/music.wav
  python3 motion-graphics/projects/launch-intro/intro.py --out launch-intro.mp4
  python3 motion-graphics/projects/launch-intro/intro.py --preview 0.6,2.2,5.6,9,12.3 --out sheet.png

Needs assets/ready/ from prep.py (owner photos: git-ignored, re-upload per session) and the music wav.
1080x1920, 30 fps, 16 s on the 120 BPM grid in timeline.py (one beat = 15 frames).

  0-2s   hook: SOUND ON + volume slider climbing while the music is muffled; silence; DROP
  2-4s   drop: shockwave + confetti, LET'S MAKE / SOME NOISE, heads swapped by whip pans
  4-6s   LET'S / MAKE / SOME / NOISE, joined by zoom-through transitions
  6-8s   EDITS. / DESIGN. / MOTION. (whip pans), 16th-note photo stutter
  8-12s  collage drops on 8ths with parallax + equalizer bars; camera dives into the poster's monitor
  12-16s CRT logo reveal, handle typed on tape, heads bouncing, final hit

Everything pulses with the music's bass, the equalizer reads its real spectrum, and graphics boil at
10 fps (outlines, doodles and letters re-jitter every 3 frames) for the stop-motion look.
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
sys.path.insert(0, HERE)
from timeline import (BEAT, DROP, FINAL_HIT, GAPS, LENGTH, LOGO, MINI_HIT, MONITOR, RAPID,  # noqa: E402
                      WHIPS, ZOOMS)

W, H, FPS = 1080, 1920, 30
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
# audio analysis (drives the pulses and the equalizer bars)
class Audio:
    def __init__(self, path, bands=14):
        from scipy.io import wavfile
        from scipy.signal import butter, sosfilt

        sr, x = wavfile.read(path)
        x = x.astype(np.float32).mean(axis=1) / 32768
        n = int(LENGTH * FPS)
        hop = sr // FPS
        lo = sosfilt(butter(4, 150, btype="lowpass", fs=sr, output="sos"), x)
        rms = np.array([np.sqrt(np.mean(lo[max(i * hop - hop, 0):i * hop + hop] ** 2) + 1e-12) for i in range(n)])
        rms /= np.percentile(rms, 97) + 1e-9
        env = np.zeros(n)
        for i in range(n):  # instant attack, fast release
            env[i] = max(min(rms[i], 1.2), env[i - 1] * 0.72 if i else 0)
        self.bass = np.clip(env, 0, 1.2)
        edges = np.geomspace(50, 9000, bands + 1)
        win = 2048
        freqs = np.fft.rfftfreq(win, 1 / sr)
        window = np.hanning(win)
        spec = np.zeros((n, bands))
        for i in range(n):
            seg = x[i * hop:i * hop + win]
            if seg.size < win:
                seg = np.pad(seg, (0, win - seg.size))
            mag = np.abs(np.fft.rfft(seg * window))
            for b in range(bands):
                m = (freqs >= edges[b]) & (freqs < edges[b + 1])
                spec[i, b] = 20 * np.log10(mag[m].mean() + 1e-9)
        spec = (spec - spec.max(axis=0) + 42) / 42  # each band: its loudest frame -> 1, -42 dB -> 0
        self.bands = np.clip(spec, 0, 1)

    def at(self, t):
        return float(self.bass[min(int(t * FPS), len(self.bass) - 1)])

    def bands_at(self, t):
        return self.bands[min(int(t * FPS), len(self.bands) - 1)]


# ----------------------------------------------------------------------------------------------
# assets
class Assets:
    def __init__(self, music):
        cut = {
            "greenhat": load("greenhat.png", 1150),
            "niss": load("niss-orange.png", 1150),
            "boxface": load("boxface.png", 1150),
            "filmstrip": load("filmstrip.png", 1100),
            "topdown": load("topdown.png", 1000),
            "hand": load("hand.png", 1200),
        }
        self.stickers = {k: boil_set(v, r=18) for k, v in cut.items()}
        self.ink = load("poster-ink.png", 1150).tinted(BLACK)
        self.logo = load("logo-white.png")
        self.audio = Audio(music)
        self.plates = {
            "black": make_plate(BLACK, 1, dot_color=(40, 36, 36)),
            "orange": make_plate(ORANGE, 2),
            "green": make_plate(GREEN, 3),
            "cream": make_plate(CREAM, 4, dot_color=(190, 205, 215)),
            "red": make_plate(RED, 5),
            "blue": make_plate(BLUE, 6),
        }
        L = lambda txt, size, fill, stroke=12: letters(txt, ANTON, size, fill, stroke=stroke, stroke_fill=BLACK)
        self.words = {
            "SOUND ON": L("SOUND ON", 205, CREAM, 12),
            "LET'S MAKE": L("LET'S MAKE", 215, CREAM),
            "SOME NOISE": L("SOME NOISE", 215, CREAM),
            "LET'S": letters("LET'S", ANTON, 520, BLACK),
            "MAKE": letters("MAKE", ANTON, 560, CREAM),
            "SOME": L("SOME", 560, RED, 10),
            "NOISE": L("NOISE", 470, WHITE, 16),
            "EDITS.": L("EDITS.", 330, YELLOW, 14),
            "DESIGN.": L("DESIGN.", 300, RED, 14),
            "MOTION.": L("MOTION.", 290, CREAM, 14),
        }
        self.max_tag = boil_set(text_sprite("MAX!", MARKER, 120, YELLOW, stroke=6, stroke_fill=BLACK), r=10, color=BLACK)
        self.vol_label = text_sprite("VOLUME", ANTON, 58, CREAM, stroke=5, stroke_fill=BLACK)
        self.pct = {}
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
        scan = np.ones((H, 1, 1), np.float32)
        scan[::3] = 0.72  # CRT scanlines
        self.scanlines = scan

    def st(self, name, t):
        s = self.stickers[name]
        return s[boil_step(t) % len(s)]

    def percent(self, v):
        if v not in self.pct:
            self.pct[v] = text_sprite(f"{v}%", ANTON, 64, YELLOW if v >= 100 else CREAM, stroke=5, stroke_fill=BLACK)
        return self.pct[v]


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
# hit effects
def rings(c, cx, cy, t0, t, color=WHITE, n=3, life=0.55, rmax=1300, thick=28):
    """Shockwave: concentric rings racing outward."""
    for k in range(n):
        u = t - t0 - k * 0.07
        if 0 <= u < life:
            r = 60 + rmax * ease_out(u / life)
            th = max(int(thick * (1 - u / life)), 2)
            cv2.circle(c, (int(cx), int(cy)), int(r), color, th)


def particles(c, cx, cy, t0, t, seed, n=34, life=0.85, speed=(800, 2300),
              colors=(WHITE, YELLOW, CREAM, RED, BLUE)):
    """Confetti / halftone dots / chalk sparks bursting out with drag and gravity."""
    u = t - t0
    if u < 0 or u > life:
        return
    r = np.random.default_rng(seed)
    for _ in range(n):
        ang = r.uniform(0, 2 * math.pi)
        sp = r.uniform(*speed)
        size = r.uniform(9, 24) * (1 - u / life) + 2
        kind = int(r.integers(0, 3))
        col = colors[int(r.integers(len(colors)))]
        spin = r.uniform(-14, 14)
        dist = sp * (1 - math.exp(-u * 4.5)) / 4.5
        x = cx + math.cos(ang) * dist
        y = cy + math.sin(ang) * dist + 700 * u * u
        if kind == 0:
            cv2.circle(c, (int(x), int(y)), int(size), col, -1)
        elif kind == 1:
            a = spin * u
            pts = np.array([[x + size * math.cos(a + q * math.pi / 2), y + size * 0.6 * math.sin(a + q * math.pi / 2)]
                            for q in range(4)], np.int32)
            cv2.fillPoly(c, [pts], col)
        else:
            s2 = int(size * 1.3)
            cv2.line(c, (int(x) - s2, int(y)), (int(x) + s2, int(y)), col, 4)
            cv2.line(c, (int(x), int(y) - s2), (int(x), int(y) + s2), col, 4)


def eq_bars(c, A, t, y_base=H, height=300, alpha=1.0):
    """Equalizer bars driven by the real music spectrum."""
    b = A.audio.bands_at(t)
    n = len(b)
    margin, gap = 40, 12
    bw = (W - 2 * margin - gap * (n - 1)) / n
    for i, v in enumerate(b):
        h = int(24 + height * v)
        x0 = int(margin + i * (bw + gap))
        col = YELLOW if i % 2 else CREAM
        cv2.rectangle(c, (x0, y_base - h), (int(x0 + bw), y_base + 10), BLACK, -1)
        cv2.rectangle(c, (x0 + 5, y_base - h + 5), (int(x0 + bw) - 5, y_base + 10), col, -1)


def speaker(c, x, y, t, pulse, size=1.0):
    s = size
    body = np.array([[x - 70 * s, y - 32 * s], [x - 30 * s, y - 32 * s], [x + 25 * s, y - 78 * s],
                     [x + 25 * s, y + 78 * s], [x - 30 * s, y + 32 * s], [x - 70 * s, y + 32 * s]], np.int32)
    cv2.fillPoly(c, [body], BLACK)
    cv2.polylines(c, [body], True, BLACK, 14)
    inner = np.array([[x - 62 * s, y - 24 * s], [x - 27 * s, y - 24 * s], [x + 17 * s, y - 62 * s],
                      [x + 17 * s, y + 62 * s], [x - 27 * s, y + 24 * s], [x - 62 * s, y + 24 * s]], np.int32)
    cv2.fillPoly(c, [inner], CREAM)
    waves = 1 + int(round(pulse * 2.2))
    for k in range(min(waves, 3)):
        r = int((62 + 38 * k) * s)
        cv2.ellipse(c, (int(x + 30 * s), int(y)), (r, r), 0, -48, 48, BLACK, 20)
        cv2.ellipse(c, (int(x + 30 * s), int(y)), (r, r), 0, -48, 48, CREAM, 10)


def slider(c, A, t, value, x0=170, x1=910, y=1560):
    """Volume slider sticker."""
    cv2.rectangle(c, (x0 - 34, y - 112), (x1 + 34, y + 54), BLACK, -1)
    cv2.rectangle(c, (x0 - 26, y - 104), (x1 + 26, y + 46), (40, 36, 36), -1)
    draw(c, A.vol_label, x0 + A.vol_label.w / 2, y - 62, 1.0)
    pct = int(round(value * 100))
    sp = A.percent(pct)
    draw(c, sp, x1 - sp.w / 2, y - 62, 1.0)
    cv2.rectangle(c, (x0, y - 16), (x1, y + 16), (70, 66, 66), -1)
    xf = int(x0 + (x1 - x0) * value)
    fill = RED if value >= 0.9 else ORANGE
    cv2.rectangle(c, (x0, y - 16), (xf, y + 16), fill, -1)
    cv2.circle(c, (xf, y), 38, BLACK, -1)
    cv2.circle(c, (xf, y), 30, CREAM, -1)


# ----------------------------------------------------------------------------------------------
# scenes (t in seconds; beats every 0.5 s)
def scene_hook(c, A, t):
    """SOUND ON: side-eye face, volume slider climbing, music muffled until the drop."""
    c[:] = A.plates["green"]
    p = A.audio.at(t)
    sunburst(c, (40, 58, 22), t * 0.25, opacity=0.5, cy=1180)
    s = 0.76 + 0.1 * ease_in_out(t / 1.875) + 0.025 * p
    jx, jy = jitter(t, "hook", 4)
    draw(c, A.st("greenhat", t), W / 2 + jx, 1010 + jy, s, -3, shadow=(20, 26, BLACK, 0.5))
    word(c, A.words["SOUND ON"], W / 2 + 75, 330, t, slam(t, 0.35) or 1.0, -3, amp=5,
         shadow=(10, 14, BLACK, 0.8), key="sound")
    speaker(c, 118, 338, t, p, 0.95)
    value = 0.06 + 0.94 * ease_in(t / 1.75) if t < 1.75 else 1.0
    slider(c, A, t, value, y=1600)
    if t >= 1.75:
        draw(c, A.max_tag[boil_step(t) % 3], 860, 1410, slam(t - 1.75, 0.6, 0.06), 10, shadow=(8, 10, BLACK, 0.6))


DROP_HEADS = [("niss", "orange", DARK_ORANGE), ("boxface", "red", (70, 30, 170)),
              ("filmstrip", "blue", (150, 90, 45)), ("topdown", "cream", (196, 210, 222))]


def scene_drop(c, A, t):
    k = min(int((t - DROP) / BEAT), 3)
    who, plate, burst = DROP_HEADS[k]
    c[:] = A.plates[plate]
    sunburst(c, burst, t * 1.4, opacity=0.6, cy=980)
    p = A.audio.at(t)
    s = (slam(t - DROP, 0.6, 0.12) if k == 0 else 1.0) * (1 + 0.07 * p)
    jx, jy = jitter(t, "drop", 4)
    draw(c, A.st(who, t), W / 2 + jx, 990 + jy, 0.95 * s, -4 if k % 2 else 4, shadow=(22, 28, BLACK, 0.55))
    rings(c, W / 2, 990, DROP, t, WHITE)
    particles(c, W / 2, 990, DROP, t, seed=1)
    ts = (slam(t - DROP, 0.5, 0.1) or 1.0) * (1 + 0.04 * p)
    word(c, A.words["LET'S MAKE"], W / 2, 250, t, ts, -3, amp=5, shadow=(10, 14, BLACK, 0.85), key="lm")
    word(c, A.words["SOME NOISE"], W / 2, 1690, t, ts, -3, amp=5, shadow=(10, 14, BLACK, 0.85), key="sn")


def scene_words(c, A, t):
    k = min(int((t - 4.0) / BEAT), 3)
    u = t - 4.0 - k * BEAT
    s = slam(u, 0.3) * (1 + 0.05 * A.audio.at(t))
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
        draw(c, A.ink, W / 2, 1420 + (1 - iu) * 600, 0.78, 0)
        doodle(c, "burst", 930, 300, t, -45, 1.6, (u - 0.05) / 0.14, color=BLACK, key="some")
    else:
        c[:] = A.plates["orange"]
        sunburst(c, DARK_ORANGE, t * 1.6, opacity=0.6, cy=930)
        rings(c, W / 2, 930, 5.5, t, CREAM, life=0.45)
        heads = [("greenhat", 230, 400, -12), ("niss", 860, 420, 12), ("boxface", 230, 1480, 8),
                 ("filmstrip", 860, 1500, -8)]
        for i, (who, hx, hy, hr) in enumerate(heads):
            hs = slam(u - 0.04 * i, 0.6)
            if hs:
                jx, jy = jitter(t, who, 8)
                draw(c, A.st(who, t), hx + jx, hy + jy, 0.4 * hs, hr, shadow=(12, 16, BLACK, 0.5))
        particles(c, W / 2, 930, 5.5, t, seed=2, n=40)
        word(c, A.words["NOISE"], W / 2, 930, t, 0.94 * s, -6, amp=14, shadow=(14, 18, RED, 1.0), key="noise")


WHO = [("EDITS.", "filmstrip", "black", YELLOW), ("DESIGN.", "boxface", "cream", RED),
       ("MOTION.", "hand", "orange", CREAM)]
STUTTER = [("greenhat", "red"), ("niss", "black"), ("boxface", "orange"), ("filmstrip", "green")]


def scene_who(c, A, t):
    if t >= RAPID[0]:
        k = min(int((t - RAPID[0]) / 0.125), 3)
        u = t - RAPID[0] - k * 0.125
        who, plate = STUTTER[k]
        c[:] = A.plates[plate]
        s = (0.8 + 0.08 * k) * slam(u, 0.3, 0.06)
        draw(c, A.st(who, t), W / 2, 960, s, 8 if k % 2 else -8, shadow=(18, 22, BLACK, 0.55))
        rings(c, W / 2, 960, RAPID[0] + k * 0.125, t, WHITE, n=1, life=0.12, rmax=700)
        return
    k = min(int((t - 6.0) / BEAT), 2)
    u = t - 6.0 - k * BEAT
    txt, who, plate, _ = WHO[k]
    c[:] = A.plates[plate]
    p = A.audio.at(t)
    rise = ease_out(u / 0.22)
    rot = 4 * math.sin(u * 8) if who == "hand" else (-3 if k % 2 else 3)
    draw(c, A.st(who, t), 560, 1220 + (1 - rise) * 600, 0.9 * (1 + 0.04 * p), rot, shadow=(20, 26, BLACK, 0.5))
    # letters slam in one after another
    lets = A.words[txt]
    for i, (sp, dx) in enumerate(lets):
        ls = slam(u - 0.03 * i, 0.7, 0.08)
        if ls is None:
            continue
        jx, jy = jitter(t, (txt, i), 5)
        draw(c, sp, W / 2 + dx + jx, 420 + jy, ls, -4 + jitter(t, (txt, i, "r"), 3)[0], shadow=(10, 14, BLACK, 0.8))
    doodle(c, "arrow", 230, 700, t, 60, 1.4, (u - 0.12) / 0.15, color=BLACK if plate == "cream" else WHITE, key=txt)
    doodle(c, "star", 900, 720, t, 0, 1.2, (u - 0.16) / 0.12, color=YELLOW, key=txt)


COLLAGE = [
    # landing time, what, x, y, scale, rot, depth (parallax)
    (8.00, "ink", 560, 1160, 0.95, 0, 0.5),
    (8.25, "greenhat", 255, 500, 0.52, -10, 1.2),
    (8.50, "niss", 835, 540, 0.52, 9, 1.2),
    (8.75, "boxface", 215, 1130, 0.44, -6, 1.0),
    (9.00, "filmstrip", 875, 1150, 0.44, 7, 1.0),
    (9.25, "topdown", 560, 1540, 0.5, -3, 1.4),
    (9.50, "hand", 930, 1700, 0.62, -26, 1.6),
    (9.75, "niss_tag", 560, 270, 1.0, -8, 1.3),
]
MONITOR_OFFSET = (212, 97)  # the poster's computer screen, relative to the ink sprite centre (scale 1)
MONITOR_PT = [W / 2, H / 2]
EXPLODE = (MONITOR[0] - 0.15, 0.4)  # stickers blast off the page right before the dive (start, length)


def scene_collage(c, A, t):
    c[:] = A.plates["orange"]
    p = A.audio.at(t)
    camx = 36 * math.sin((t - 8.0) * 0.9)
    camy = 60 * math.sin((t - 8.0) * 1.3)
    blast = ease_in((t - EXPLODE[0]) / EXPLODE[1])
    for i, (t0, what, x, y, sc, rot, depth) in enumerate(COLLAGE):
        if i == 1 and blast < 1:
            ribbon(c, A, "black", 1420 + camy * 0.8 + 900 * blast, 9 + 20 * blast, t)
        s = slam(t - t0, 0.5, 0.1)
        if s is None:
            continue
        px, py = x + camx * depth, y + camy * depth
        if what != "ink" and blast > 0:  # fly outward from the centre, spinning
            if blast >= 1:
                continue
            dx, dy = px - W / 2, py - H / 2
            ln = math.hypot(dx, dy) or 1
            px += dx / ln * 1500 * blast
            py += dy / ln * 1500 * blast
            s *= 1 + 0.7 * blast
            rot += (40 if i % 2 else -40) * blast
        jx, jy = jitter(t, what, 4)
        jr = jitter(t, (what, "r"), 1.2)[0]
        pulse = 1 + 0.035 * p * depth
        if what == "ink":
            draw(c, A.ink, px + jx, py + jy, sc * s, rot + jr)
            MONITOR_PT[0] = px + MONITOR_OFFSET[0] * sc
            MONITOR_PT[1] = py + MONITOR_OFFSET[1] * sc
        elif what == "niss_tag":
            draw(c, A.niss_tag[boil_step(t) % 3], px + jx, py + jy, sc * s, rot + jr, shadow=(10, 12, BLACK, 0.5))
            doodle(c, "crown", px + 170, py - 90, t, 14, 1.0, (t - t0 - 0.05) / 0.15, color=YELLOW, key="tag")
        else:
            draw(c, A.st(what, t), px + jx, py + jy, sc * s * pulse, rot + jr, shadow=(16, 20, BLACK, 0.5))
        rings(c, px, py, t0, t, CREAM, n=1, life=0.3, rmax=380, thick=16)
        particles(c, px, py, t0, t, seed=10 + i, n=10, life=0.5, speed=(400, 1100))
    if blast < 1:
        eq_bars(c, A, t, y_base=int(H + 320 * blast), height=200)
    rings(c, W / 2, H / 2, EXPLODE[0], t, WHITE, n=2, life=0.4, rmax=1200)


def scene_logo(c, A, t):
    c[:] = A.plates["black"]
    p = A.audio.at(t)
    sunburst(c, (20, 36, 90), t * 0.6, opacity=0.65, cy=760)
    u = t - LOGO
    for t0, big in ((LOGO, True), (MINI_HIT, False), (FINAL_HIT, True)):
        rings(c, W / 2, 760, t0, t, YELLOW if big else CREAM, life=0.6 if big else 0.4, rmax=1400 if big else 700)
        particles(c, W / 2, 760, t0, t, seed=int(t0 * 10), n=46 if big else 18)
    for i, (who, hx, hr) in enumerate((("greenhat", 150, 8), ("niss", 410, -6), ("boxface", 670, 6),
                                        ("filmstrip", 930, -8))):
        t0 = 12.5 + 0.25 * i
        if t >= t0:
            rise = ease_out((t - t0) / 0.2)
            jump = 120 * math.exp(-(t - MINI_HIT) / 0.15) if t >= MINI_HIT else 0
            jump += 160 * math.exp(-(t - FINAL_HIT) / 0.18) if t >= FINAL_HIT else 0
            draw(c, A.st(who, t), hx, 1600 + (1 - rise) * 700 - 34 * p - jump, 0.5, hr, shadow=(12, 16, BLACK, 0.5))
    s = slam(u, 0.6, 0.14) * (1 + 0.05 * p)
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
        cut = int(A.handle.w * n / len(HANDLE))
        ts = slam(tu, 0.25, 0.08)
        draw(c, tape, W / 2, 1000, ts, 2, shadow=(10, 12, BLACK, 0.6))
        if cut > 2:
            sub = Sprite(A.handle.rgb[:, :cut], A.handle.a[:, :cut])
            off = (sub.w - A.handle.w) / 2  # left-align the typed part inside the tape
            c2, s2 = math.cos(math.radians(-2)), math.sin(math.radians(-2))
            draw(c, sub, W / 2 + off * c2 * ts, 1000 + off * s2 * ts, ts, 2)
    if t >= 13.5:
        draw(c, A.follow, 300, 905, slam(t - 13.5, 0.4), -10)
        doodle(c, "arrow", 150, 1000, t, 20, 0.9, (t - 13.55) / 0.15, color=YELLOW, key="follow")


SCENES = [(0.0, scene_hook), (DROP, scene_drop), (4.0, scene_words), (6.0, scene_who),
          (8.0, scene_collage), (LOGO, scene_logo)]


def scene_at(c, A, t):
    fn = [f for t0, f in SCENES if t >= t0][-1]
    fn(c, A, t)


# ----------------------------------------------------------------------------------------------
# transitions (3 frames either side of the cut)
HALF = 0.1


def whip(a, b, p, axis):
    if p < 0.5:
        q, img, sign = ease_in(p / 0.5), a, -1
    else:
        q, img, sign = 1 - ease_out((p - 0.5) / 0.5), b, 1
    d = sign * q * (W if axis == "h" else H) * 0.55
    M = np.float32([[1, 0, d if axis == "h" else 0], [0, 1, d if axis == "v" else 0]])
    img = cv2.warpAffine(img, M, (W, H), borderMode=cv2.BORDER_REFLECT)
    k = int(8 + 150 * q)
    return cv2.blur(img, (k, 1) if axis == "h" else (1, k))


def zoom_blur(img, z, cx=W / 2, cy=H / 2, spread=(1.0, 1.035, 1.07)):
    acc = np.zeros_like(img)
    for f in spread:
        zz = z * f
        M = np.float32([[zz, 0, W / 2 - zz * cx], [0, zz, H / 2 - zz * cy]])
        acc += cv2.warpAffine(img, M, (W, H), borderMode=cv2.BORDER_REFLECT)
    return acc / len(spread)


def zoom_through(a, b, p):
    if p < 0.5:
        q = ease_in(p / 0.5)
        return zoom_blur(a, 1 + 2.2 * q)
    q = 1 - ease_out((p - 0.5) / 0.5)
    return zoom_blur(b, 1 + 0.5 * q, spread=(1.0, 1.03, 1.06) if q > 0.05 else (1.0,))


def render_scene(A, t):
    c = np.empty((H, W, 3), np.float32)
    scene_at(c, A, t)
    for b, axis in WHIPS:
        if b - HALF <= t < b + HALF:
            other = np.empty_like(c)
            if t < b:
                scene_at(other, A, b)
                return whip(c, other, (t - b + HALF) / (2 * HALF), axis)
            scene_at(other, A, b - 1 / FPS)
            return whip(other, c, (t - b + HALF) / (2 * HALF), axis)
    for b in ZOOMS:
        if b - HALF <= t < b + HALF:
            other = np.empty_like(c)
            if t < b:
                scene_at(other, A, b)
                return zoom_through(c, other, (t - b + HALF) / (2 * HALF))
            scene_at(other, A, b - 1 / FPS)
            return zoom_through(other, c, (t - b + HALF) / (2 * HALF))
    return c


# impact effects: (time, strength)
IMPACTS = ([(0.5, 0.12), (1.0, 0.15), (1.5, 0.2), (1.75, 0.4), (DROP, 1.3), (2.5, 0.5), (3.0, 0.5), (3.5, 0.5),
            (4.0, 0.6), (4.5, 0.6), (5.0, 0.6), (5.5, 1.1), (6.0, 0.6), (6.5, 0.6), (7.0, 0.6)]
           + [(RAPID[0] + 0.125 * k, 0.4) for k in range(4)]
           + [(t0, 0.35) for t0, *_ in COLLAGE] + [(EXPLODE[0], 0.7)]
           + [(LOGO, 1.3), (13.0, 0.3), (MINI_HIT, 0.6), (FINAL_HIT, 1.1)])


def post(c, A, t, i):
    zoom, cx, cy = 1.0, W / 2, H / 2
    if MONITOR[0] <= t < LOGO:  # dive into the poster's computer screen
        p = (t - MONITOR[0]) / (LOGO - MONITOR[0])
        zoom = math.exp(math.log(11) * ease_in(p) ** 0.9)
        m = ease_in_out(min(p * 1.6, 1.0))
        cx = W / 2 + (MONITOR_PT[0] - W / 2) * m
        cy = H / 2 + (MONITOR_PT[1] - H / 2) * m
    elif 8.0 <= t < MONITOR[0]:
        zoom = 1.0 + 0.06 * ease_in_out((t - 8.0) / (MONITOR[0] - 8.0))
    elif t >= FINAL_HIT:
        zoom = 1.0 + 0.06 * ease_out((t - FINAL_HIT) / 0.3)
    sx = sy = 0.0
    split = 1.0
    flash = 0.0
    for ti, k in IMPACTS:
        d = t - ti
        if 0 <= d < 0.4:
            e = math.exp(-d / 0.09)
            r = np.random.default_rng(int(ti * 1000) + i)
            sx += r.uniform(-1, 1) * 30 * k * e
            sy += r.uniform(-1, 1) * 30 * k * e
            split += 18 * k * math.exp(-d / 0.07)
            flash = max(flash, 0.5 * k * math.exp(-d / 0.035))
    if 1.6 <= t < DROP:  # tension before the drop
        e = ease_in((t - 1.6) / 0.4)
        r = np.random.default_rng(i)
        sx += r.uniform(-1, 1) * 16 * e
        split += 14 * e
    if zoom > 1.6:
        c = zoom_blur(c, zoom, cx, cy, spread=(1.0, 1.05, 1.1))
    elif zoom != 1.0:
        M = np.float32([[zoom, 0, W / 2 - zoom * cx], [0, zoom, H / 2 - zoom * cy]])
        c = cv2.warpAffine(c, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    if sx or sy:
        M = np.float32([[1, 0, sx], [0, 1, sy]])
        c = cv2.warpAffine(c, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    k = int(round(split))
    if k > 0:
        b, g, r_ = cv2.split(c)
        c = cv2.merge([np.roll(b, -k, axis=1), g, np.roll(r_, k, axis=1)])
    if flash > 0:
        c += (255 - c) * flash
    st = 0.0
    if any(a <= t < b for a, b in GAPS):
        st = 0.9
    elif t < 0.12:
        st = 0.5 * (1 - t / 0.12)
    if st > 0:
        noise = np.random.default_rng(i + 999).uniform(0, 255, (H // 3, W // 3)).astype(np.float32)
        noise = cv2.resize(noise, (W, H), interpolation=cv2.INTER_NEAREST)[:, :, None]
        c = c * (1 - st) + noise * st
    if t >= MONITOR[1] - 0.35:  # CRT: scanlines + glow
        bloom = cv2.GaussianBlur(cv2.resize(np.clip(c - 150, 0, 255), (W // 4, H // 4)), (0, 0), 6)
        c = c * A.scanlines + cv2.resize(bloom, (W, H)) * 0.6
    c = c * A.vignette + A.grain[boil_step(t) % len(A.grain)][:, :, None]
    if t > LENGTH - 0.25:
        c *= clamp01((LENGTH - t) / 0.25)
    return np.clip(c, 0, 255).astype(np.uint8)


def render(A, t, i):
    return post(render_scene(A, t), A, t, i)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="launch-intro.mp4")
    ap.add_argument("--preview", help="comma-separated seconds: contact sheet PNG instead of a video")
    ap.add_argument("--music", default=MUSIC)
    args = ap.parse_args()
    if not os.path.exists(args.music):
        sys.exit(f"missing {args.music}: run music.py first")
    A = Assets(args.music)

    if args.preview:
        times = [float(x) for x in args.preview.split(",")]
        tiles = []
        if any(MONITOR[0] <= p < LOGO for p in times):  # the dive needs the collage's monitor position
            render(A, MONITOR[0] - 1 / FPS, 0)
        for p in times:
            i = round(p * FPS)
            img = cv2.resize(render(A, i / FPS, i), (W // 3, H // 3), interpolation=cv2.INTER_AREA)
            cv2.putText(img, f"{p:.2f}s", (10, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
            tiles.append(img)
        while len(tiles) % 5:
            tiles.append(np.zeros_like(tiles[0]))
        cv2.imwrite(args.out, np.vstack([np.hstack(tiles[r:r + 5]) for r in range(0, len(tiles), 5)]))
        print(f"Saved preview {args.out}")
        return

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
