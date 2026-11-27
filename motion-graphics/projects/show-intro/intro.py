#!/usr/bin/env python3
"""LET'S MAKE SOME NOISE - cinematic show intro, 1920x1080 @ 30 fps. Concept "MIC CHECK -> OVERLOAD".

  python3 motion-graphics/projects/show-intro/sound.py            # build/mix.wav + stems
  python3 motion-graphics/projects/show-intro/intro.py --out LMSN_intro.mp4
  python3 motion-graphics/projects/show-intro/intro.py --preview 1.6,2.8,5,8.2,10 --out sheet.png
  python3 motion-graphics/projects/show-intro/intro.py --still 10.9 --out end_frame.png

Built only from the owner's logo (assets/logo-hires.png, git-ignored) and the synthesised sound:
the logo's own letterforms are cut into its four words, traced into frame-by-frame scribbles,
displaced, glitched, burned and finally revealed out of procedural smoke. The oscilloscope line is
the real soundtrack, so every wiggle on screen is the sound you hear. Timing lives in timeline.py.
"""
import argparse
import math
import os
import subprocess
import sys
import zlib

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from timeline import (CUT, DROP, FEEDBACK, GAP1, GLITCH_TICKS, IMPLODE, LENGTH, LINE_IN, REVEAL,  # noqa: E402
                      SILENCE, STUTTER, TAPS, UNDERLINE_SETTLE, WORDS)

W, H, FPS = 1920, 1080, 30
BOIL = 12  # scribbles / weave re-jitter at 12 fps: hand-made, frame-by-frame feel
LOGO_PATH = os.path.join(HERE, "assets", "logo-hires.png")
AUDIO_PATH = os.path.join(HERE, "build", "mix.wav")

WHITE = (240, 242, 244)
INK = (12, 12, 12)
RED = (60, 40, 230)
BURN_CORE = (215, 240, 255)
BURN_MID = (40, 140, 255)
BURN_EDGE = (20, 30, 160)

LOGO_CENTER = (W / 2, H / 2)
WORD_CUTS = [18, 353, 745, 1113, 1490]   # x cuts between Let's | make | some | noise in the logo
TEXT_ROWS = (0, 195)
UNDERLINE = (520, 985, 205, 286)         # x0, x1, y0, y1 of the hand-drawn underline in the logo


# ---------------------------------------------------------------------------------------------- utils
def clamp01(x):
    return min(max(x, 0.0), 1.0)


def ease_out(x):
    return 1 - (1 - clamp01(x)) ** 3


def ease_in(x):
    return clamp01(x) ** 3


def ease_in_out(x):
    x = clamp01(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def hsh(x):
    return zlib.crc32(repr(x).encode())


def step(t, fps=BOIL):
    return int(t * fps + 1e-6)


def rng_at(t, key, fps=BOIL):
    return np.random.default_rng((step(t, fps) * 7919 + hsh(key)) & 0xFFFFFFFF)


def frame_rng(i, key):
    return np.random.default_rng((i * 104729 + hsh(key)) & 0xFFFFFFFF)


class Layer:
    """A sprite: float32 BGR + alpha."""

    def __init__(self, rgb, a):
        self.rgb = np.ascontiguousarray(rgb, np.float32)
        self.a = np.ascontiguousarray(a, np.float32)

    @property
    def w(self):
        return self.a.shape[1]

    @property
    def h(self):
        return self.a.shape[0]


def draw(c, sp, x, y, scale=1.0, rot=0.0, alpha=1.0, sx=1.0):
    """Composite sprite centred at (x, y); sx stretches horizontally."""
    if scale <= 0.005 or alpha <= 0.003:
        return
    M = cv2.getRotationMatrix2D((sp.w / 2, sp.h / 2), rot, scale)
    M[0, :2] *= sx  # horizontal stretch, then re-centre on (x, y)
    M[0, 2] = x - (M[0, 0] * sp.w / 2 + M[0, 1] * sp.h / 2)
    M[1, 2] = y - (M[1, 0] * sp.w / 2 + M[1, 1] * sp.h / 2)
    corners = np.array([[0, 0, 1], [sp.w, 0, 1], [0, sp.h, 1], [sp.w, sp.h, 1]], np.float32) @ M.T
    x0, y0 = np.floor(corners.min(axis=0)).astype(int) - 2
    x1, y1 = np.ceil(corners.max(axis=0)).astype(int) + 2
    x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
    if x1 <= x0 or y1 <= y0:
        return
    M[0, 2] -= x0
    M[1, 2] -= y0
    size = (x1 - x0, y1 - y0)
    a = cv2.warpAffine(sp.a, M, size, flags=cv2.INTER_LINEAR)[:, :, None] * alpha
    rgb = cv2.warpAffine(sp.rgb, M, size, flags=cv2.INTER_LINEAR)
    roi = c[y0:y1, x0:x1]
    roi *= 1 - a
    roi += rgb * a


def lighten(c, layer):
    np.maximum(c, layer, out=c)


# ---------------------------------------------------------------------------------------------- assets
class Audio:
    def __init__(self, path):
        from scipy.io import wavfile

        sr, x = wavfile.read(path)
        self.sr = sr
        x = x.astype(np.float32)
        x = x.mean(axis=1) / np.abs(x).max()
        self.x = x
        n = int(LENGTH * FPS) + 2
        hop = sr // FPS
        xp = np.pad(x, (0, (n + 1) * hop))  # frames past the end of the audio read silence, not NaN
        rms = np.array([np.sqrt(np.mean(xp[i * hop:(i + 1) * hop] ** 2) + 1e-12) for i in range(n)])
        self.level = np.clip(rms / np.percentile(rms, 98), 0, 1.2)

    def window(self, t, width=W):
        c = int(t * self.sr)
        seg = self.x[max(c - width // 2, 0):c + width // 2]
        if seg.size < width:
            seg = np.pad(seg, (0, width - seg.size))
        return seg

    def lvl(self, t):
        return float(self.level[min(int(t * FPS), len(self.level) - 1)])


class Assets:
    def __init__(self, audio_path):
        im = cv2.imread(LOGO_PATH, cv2.IMREAD_UNCHANGED)
        if im is None:
            sys.exit(f"missing {LOGO_PATH}: extract the logo first (see README in this folder)")
        a = im[:, :, 3].astype(np.float32) / 255
        white = np.empty(a.shape + (3,), np.float32)
        white[:] = WHITE
        self.logo = Layer(white, a)
        no_ul = a.copy()
        ux0, ux1, uy0, uy1 = UNDERLINE
        no_ul[uy0:uy1] = 0
        self.logo_text = Layer(white, no_ul)
        ul = np.zeros_like(a)
        ul[uy0:uy1, ux0:ux1] = a[uy0:uy1, ux0:ux1]
        self.underline = Layer(white, ul)
        # the underline's centreline, for the scope line to settle onto
        cols = np.arange(ux0, ux1)
        ys = []
        for x in cols:
            col = a[uy0:uy1, x]
            ys.append(uy0 + (np.arange(col.size) * col).sum() / col.sum() if col.sum() > 0.5 else np.nan)
        ys = np.array(ys)
        ok = ~np.isnan(ys)
        self.ul_x = cols[ok]
        self.ul_y = ys[ok]
        # the four words, cut from the logo itself
        self.words = {}
        text = a[TEXT_ROWS[0]:TEXT_ROWS[1]]
        cuts = WORD_CUTS
        for i, (_, name) in enumerate(WORDS):
            x0, x1 = cuts[i], cuts[i + 1]
            crop = text[:, x0:x1].copy()
            n, lab, st, _ = cv2.connectedComponentsWithStats((crop > 0.15).astype(np.uint8), 8)
            for j in range(1, n):  # slivers of the neighbouring letters
                x, _, w_, _, area = st[j]
                if (x == 0 or x + w_ >= crop.shape[1]) and w_ < 30:
                    crop[lab == j] = 0
            wa = np.pad(crop, 8)
            wrgb = np.empty(wa.shape + (3,), np.float32)
            wrgb[:] = WHITE
            self.words[name] = Layer(wrgb, wa)
        # scribble contours of the lettering, for the frame-by-frame trace
        mask = (no_ul > 0.5).astype(np.uint8)
        cs, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        self.contours = []
        for cnt in cs:
            if len(cnt) < 24:
                continue
            p = cv2.approxPolyDP(cnt, 1.2, True)[:, 0, :].astype(np.float32)
            self.contours.append(np.vstack([p, p[:1]]) - [a.shape[1] / 2, a.shape[0] / 2])
        self.contour_len = [float(np.linalg.norm(np.diff(c_, axis=0), axis=1).sum()) for c_ in self.contours]
        self.audio = Audio(audio_path)
        r = np.random.default_rng(3)
        self.grain = [cv2.GaussianBlur(r.normal(0, 9.0, (H, W)).astype(np.float32), (0, 0), 0.8) for _ in range(8)]
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        rr = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / math.sqrt(2)
        self.vignette = (1.0 - 0.45 * np.clip((rr - 0.3) / 0.7, 0, 1) ** 1.4).astype(np.float32)[:, :, None]
        self.smoke = Smoke()


# ---------------------------------------------------------------------------------------------- elements
def scope(c, A, t, y=H / 2, gain=300.0, thick=3, alpha=1.0, glow=True, x0=0, x1=W):
    """Oscilloscope: the actual soundtrack around time t, drawn as a white line."""
    if alpha <= 0:
        return
    seg = A.audio.window(t, x1 - x0)
    ys = np.clip(y - seg * gain, 0, H - 1)
    pts = np.stack([np.arange(x0, x1, dtype=np.float32), ys], axis=1).astype(np.int32)
    layer = np.zeros((H, W), np.float32)
    cv2.polylines(layer, [pts], False, 1.0, thick, cv2.LINE_AA)
    if glow:
        g = cv2.GaussianBlur(layer, (0, 0), 6) * 1.6
        layer = np.maximum(layer, g)
    m = np.clip(layer * alpha, 0, 1)[:, :, None]
    c[:] = c * (1 - m) + np.array(WHITE, np.float32) * m


def scope_ring(c, A, t, r0=300, gain=160, alpha=1.0, cx=W / 2, cy=H / 2):
    seg = A.audio.window(t, 1440)
    ang = np.linspace(0, 2 * math.pi, seg.size, endpoint=False)
    r = r0 + seg * gain
    pts = np.stack([cx + np.cos(ang) * r, cy + np.sin(ang) * r], axis=1).astype(np.int32)
    layer = np.zeros((H, W), np.float32)
    cv2.polylines(layer, [pts], True, 1.0, 3, cv2.LINE_AA)
    layer = np.maximum(layer, cv2.GaussianBlur(layer, (0, 0), 5) * 1.4)
    m = np.clip(layer * alpha, 0, 1)[:, :, None]
    c[:] = c * (1 - m) + np.array(WHITE, np.float32) * m


def trace(c, A, t, cx, cy, scale, rot=0.0, progress=1.0, thick=2, amp=2.5, color=WHITE, alpha=1.0, key="tr"):
    """Frame-by-frame scribble trace of the logo's lettering (boils at 12 fps)."""
    if progress <= 0:
        return
    r = rng_at(t, key)
    a = math.radians(-rot)
    R = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]], np.float32) * scale
    total = sum(A.contour_len)
    budget = total * clamp01(progress)
    layer = np.zeros((H, W), np.float32)
    for cnt, ln in zip(A.contours, A.contour_len):
        if budget <= 0:
            break
        keep = cnt if budget >= ln else cnt[: max(int(len(cnt) * budget / ln), 2)]
        budget -= ln
        off = r.normal(0, amp, 2).astype(np.float32)
        wob = r.normal(0, amp * 0.35, keep.shape).astype(np.float32)
        pts = ((keep + wob + off) @ R.T + [cx, cy]).astype(np.int32)
        cv2.polylines(layer, [pts], False, 1.0, thick, cv2.LINE_AA)
    m = np.clip(layer * alpha, 0, 1)[:, :, None]
    c[:] = c * (1 - m) + np.array(color, np.float32) * m


def rings(c, cx, cy, t0, t, n=3, life=0.5, rmax=1500, thick=22, color=WHITE):
    for k in range(n):
        u = t - t0 - k * 0.06
        if 0 <= u < life:
            r = 40 + rmax * ease_out(u / life)
            cv2.circle(c, (int(cx), int(cy)), int(r), color, max(int(thick * (1 - u / life)), 1), cv2.LINE_AA)


def meters(c, A, t, boost=1.0):
    """VU meters at both edges, red-lining."""
    lv = clamp01(A.audio.lvl(t) * boost)
    n = 18
    for side in (0, 1):
        x = 70 if side == 0 else W - 70
        lit = int(round(lv * n + rng_at(t, ("m", side), 30).uniform(-1, 1)))
        for k in range(n):
            y = 880 - k * 36
            col = RED if k >= n - 4 else WHITE
            on = k < lit
            cv2.rectangle(c, (x - 26, y - 13), (x + 26, y + 13), col if on else (40, 40, 40), -1)


def fbm_tiles(seed, w, h, cells=(64, 32, 16, 8), amps=(1.0, 0.55, 0.3, 0.16)):
    """Tileable-enough multi-octave value noise at (2h, 2w), normalised to 0..1."""
    r = np.random.default_rng(seed)
    acc = np.zeros((h * 2, w * 2), np.float32)
    for cell, amp in zip(cells, amps):
        g = r.normal(0, 1, (h * 2 // cell + 4, w * 2 // cell + 4)).astype(np.float32)
        acc += cv2.resize(g, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC) * amp
    acc -= acc.min()
    return acc / acc.max()


BURN_NOISE = None


def burn(c, t, seed, strength=1.0, side=0):
    """Film burn eating in from one frame edge: irregular hot hole, orange rim, charred fringe."""
    global BURN_NOISE
    w, h = W // 4, H // 4
    if BURN_NOISE is None:
        BURN_NOISE = fbm_tiles(91, w, h)
    ox = (seed * 37 + int(t * 40)) % w
    oy = (seed * 23 + int(t * 25)) % h
    n = BURN_NOISE[oy:oy + h, ox:ox + w]
    xx = np.linspace(0, 1, w, dtype=np.float32)[None, :]
    dist = xx if side == 0 else 1 - xx            # 0 at the burning edge
    reach = 0.06 + 0.22 * clamp01(strength)       # how far into the frame it eats
    heat = (reach - dist) * 5 + (n - 0.5) * 0.9
    heat = cv2.resize(heat, (W, H), interpolation=cv2.INTER_CUBIC)[:, :, None]
    core = np.clip(heat * 6, 0, 1)
    rim = np.clip(1 - np.abs(heat) * 5, 0, 1) * (heat > -0.2)
    char = np.clip(1 - np.abs(heat + 0.12) * 7, 0, 1)
    c *= 1 - 0.7 * char
    c += np.array(BURN_MID, np.float32) * rim * 1.1 + np.array(BURN_EDGE, np.float32) * char * 0.4
    c[:] = c * (1 - core) + np.array(BURN_CORE, np.float32) * core * 1.1


class Smoke:
    """Wispy smoke: domain-warped fbm at quarter res, pushed outward from a centre like a shockwave."""

    def __init__(self, seed=11):
        self.w, self.h = W // 4, H // 4
        self.base = fbm_tiles(seed, self.w, self.h, cells=(48, 24, 12, 6), amps=(1.0, 0.6, 0.35, 0.18))
        self.wx = fbm_tiles(seed + 1, self.w, self.h, cells=(80, 40), amps=(1.0, 0.5))
        self.wy = fbm_tiles(seed + 2, self.w, self.h, cells=(80, 40), amps=(1.0, 0.5))
        yy, xx = np.mgrid[0:self.h, 0:self.w].astype(np.float32)
        self.xx, self.yy = xx, yy

    def render(self, c, t, cx, cy, radius, density, drift=(0, 0), expand=0.0):
        qx, qy = (cx + drift[0]) / 4, (cy + drift[1]) / 4
        dx, dy = self.xx - qx, self.yy - qy
        k = 1 + expand
        o = 30 * t
        rb = cv2.BORDER_REFLECT_101  # no wrap-around seams
        wx = cv2.remap(self.wx, self.xx * 0.5 + self.w * 0.5 + o, self.yy * 0.5 + self.h * 0.5 + o * 0.6,
                       cv2.INTER_LINEAR, borderMode=rb)
        wy = cv2.remap(self.wy, self.xx * 0.5 + self.w * 0.5 - o * 0.7, self.yy * 0.5 + self.h * 0.5 + o,
                       cv2.INTER_LINEAR, borderMode=rb)
        mx = self.w + dx / k + (wx - 0.5) * 60 + o * 0.8
        my = self.h + dy / k + (wy - 0.5) * 60 - o * 0.5
        f = cv2.remap(self.base, mx.astype(np.float32), my.astype(np.float32), cv2.INTER_LINEAR, borderMode=rb)
        rr = np.sqrt((dx / max(radius / 4, 1)) ** 2 + (dy / max(radius / 4 * 0.62, 1)) ** 2)
        mask = np.exp(-rr * rr * 1.4)
        wisps = np.clip((f - 0.42) / 0.35, 0, 1) ** 1.6
        d = cv2.GaussianBlur(wisps * mask * density, (0, 0), 0.9)
        light = 0.45 + 0.55 * np.clip(f * 1.3 - 0.2, 0, 1)
        d = cv2.resize(np.clip(d, 0, 0.95), (W, H), interpolation=cv2.INTER_CUBIC)[:, :, None]
        light = cv2.resize(light, (W, H), interpolation=cv2.INTER_CUBIC)[:, :, None]
        c[:] = c * (1 - d) + np.array(WHITE, np.float32) * light * d


# ---------------------------------------------------------------------------------------------- glitch
def slices(c, r, n, max_dx, max_h=60):
    for _ in range(n):
        y0 = int(r.integers(0, H - 10))
        h = int(r.integers(4, max_h))
        dx = int(r.integers(-max_dx, max_dx + 1))
        c[y0:y0 + h] = np.roll(c[y0:y0 + h], dx, axis=1)
    return c


def blocks(c, r, n, size=(60, 220)):
    for _ in range(n):
        bw, bh = int(r.integers(*size)), int(r.integers(size[0] // 2, size[1] // 2))
        x0, y0 = int(r.integers(0, W - bw)), int(r.integers(0, H - bh))
        sx, sy = int(np.clip(x0 + r.integers(-200, 200), 0, W - bw)), int(np.clip(y0 + r.integers(-80, 80), 0, H - bh))
        c[y0:y0 + bh, x0:x0 + bw] = c[sy:sy + bh, sx:sx + bw]
    return c


def rgb_split(c, k):
    if k < 1:
        return c
    b, g, r = cv2.split(c)
    return cv2.merge([np.roll(b, -k, axis=1), g, np.roll(r, k, axis=1)])


def displace(layer, amp, freq, phase, axis=1):
    """Sine displacement of a full-frame layer (typography distortion)."""
    if amp < 0.5:
        return layer
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    if axis == 1:
        mx = xx + amp * np.sin(yy * freq + phase)
        my = yy
    else:
        mx = xx
        my = yy + amp * np.sin(xx * freq + phase)
    return cv2.remap(layer, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)


def row_shift(layer, r, amp, band=18):
    out = layer.copy()
    for y0 in range(0, H, band):
        dx = int(r.normal(0, amp))
        out[y0:y0 + band] = np.roll(layer[y0:y0 + band], dx, axis=1)
    return out


# ---------------------------------------------------------------------------------------------- scenes
def word_scale(A, name, height):
    return height / A.words[name].h


def scene_mic(c, A, t):
    """Black, one line, a mic being tapped; feedback starts to scream."""
    if t < LINE_IN:
        return
    fade = ease_out((t - LINE_IN) / 0.3)
    fb = clamp01((t - FEEDBACK[0]) / (WORDS[0][0] - FEEDBACK[0]))
    scope(c, A, t, gain=420 + 900 * fb, thick=2 + int(2 * fb), alpha=fade)
    if fb > 0:  # ghost trace slightly behind, like phosphor persistence
        scope(c, A, t - 0.012, gain=420 + 900 * fb, thick=1, alpha=0.35 * fb, glow=False)
    if 1.6 <= t < 1.6 + 2 / FPS:  # subliminal: the name is in there
        trace(c, A, t, W / 2, H / 2, 1.0, progress=1, alpha=0.5, key="sub")


WORD_FX = {"Let's": "wave", "make": "smear", "some": "rows", "noise": "quake"}


def scene_words(c, A, t):
    k = max(i for i, (t0, _) in enumerate(WORDS) if t >= t0)
    t0, name = WORDS[k]
    u = t - t0
    fx = WORD_FX[name]
    scope(c, A, t, gain=380, thick=2, alpha=0.28, glow=False)
    layer = np.zeros_like(c)
    big = name == "noise"
    sc = word_scale(A, name, 700 if big else 620) * (1 + 0.12 * (1 - ease_out(u / 0.18)))
    if fx == "smear":
        draw(layer, A.words[name], W / 2, H / 2, sc, 0, sx=1 + 1.8 * (1 - ease_out(u / 0.14)))
        k_ = int(1 + 140 * (1 - ease_out(u / 0.16)))
        layer = cv2.blur(layer, (k_, 1))
    else:
        jx, jy = rng_at(t, ("w", name)).normal(0, 6 if big else 3, 2)
        draw(layer, A.words[name], W / 2 + jx, H / 2 + jy, sc, rng_at(t, ("wr", name)).normal(0, 1.2))
    if fx == "wave":
        layer = displace(layer, 70 * (1 - ease_out(u / 0.3)), 0.018, t * 40)
    elif fx == "rows":
        layer = row_shift(layer, rng_at(t, "rows", 30), 60 * (1 - ease_out(u / 0.3)) + 3)
    elif fx == "quake":
        layer = displace(layer, 40 * (1 - ease_out(u / 0.4)) + 6, 0.03, t * 60, axis=0)
    lighten(c, layer)
    if big:
        scope_ring(c, A, t, r0=520, gain=260, alpha=0.6)
        trace(c, A, t, W / 2, H / 2, 1.18, progress=1, thick=2, amp=5, alpha=0.4, key="nz")
    if t >= STUTTER[0]:
        meters(c, A, t, 1.4)


def stutter_variant(t):
    """Which beat-repeat slice we are in (matches sound.py's stutter schedule)."""
    tt_ = STUTTER[0]
    idx = 0
    for length, count in ((0.1, 2), (0.05, 4), (0.025, 6)):
        for _ in range(count):
            if t < tt_ + length:
                return idx
            tt_ += length
            idx += 1
    return idx


CARDS = ["trace", "marquee", "negative", "ring", "blocks", "macro",
         "marquee", "burn", "trace", "strobe", "negative", "marquee"]


def scene_drop(c, A, t):
    k = min(int((t - DROP[0]) / CUT), len(CARDS) - 1)
    u = t - DROP[0] - k * CUT
    kind = CARDS[k]
    card(c, A, t, kind, u, k)


def card(c, A, t, kind, u, k):
    if kind == "trace":
        rot = (-6 if k % 2 else 6) * (1 - u / CUT)
        trace(c, A, t, W / 2, H / 2, 1.25, rot, progress=0.35 + 0.65 * u / CUT, thick=3, amp=4, key=("t", k))
        scope(c, A, t, y=H * 0.82, gain=500, alpha=0.6)
    elif kind == "marquee":
        rows = 3
        hgt = H / rows
        for r_ in range(rows):
            band = np.zeros((int(hgt) + 1, W, 3), np.float32)
            inv = (r_ + k) % 2 == 0
            if inv:
                band[:] = WHITE
            sc = hgt * 0.95 / A.logo_text.h
            lw = A.logo_text.w * sc
            speed = (1700 + 400 * r_) * (1 if r_ % 2 else -1)
            off = (t * speed) % lw
            tmp = np.zeros((int(hgt) + 1, W, 3), np.float32) if not inv else band.copy()
            for i in range(-1, int(W / lw) + 3):
                x = i * lw + off - lw
                sub = Layer(A.logo_text.rgb if not inv else np.zeros_like(A.logo_text.rgb) + INK, A.logo_text.a)
                draw_band(tmp, sub, x + lw / 2, hgt / 2 + 6, sc)
            tmp = cv2.blur(tmp, (19, 1))
            y0 = int(r_ * hgt)
            c[y0:y0 + tmp.shape[0]] = tmp[: H - y0]
    elif kind == "negative":
        c[:] = WHITE
        name = "noise" if k > 5 else "make"
        sp = A.words[name]
        ink = Layer(np.zeros_like(sp.rgb) + INK, sp.a)
        draw(c, ink, W / 2 + 140, H / 2 + 40, word_scale(A, name, 1500) * (1 + 0.15 * u / CUT), -8)
    elif kind == "ring":
        scope_ring(c, A, t, r0=240 + 900 * u, gain=300, alpha=1.0)
        draw(c, A.words["Let's"], W / 2, H / 2, word_scale(A, "Let's", 300) * (1.3 - 0.3 * u / CUT), 0)
        rings(c, W / 2, H / 2, t - u, t, n=2, life=0.2, rmax=900)
    elif kind == "blocks":
        draw(c, A.logo_text, W / 2, H / 2, 1.15, 0)
        r = frame_rng(int(t * FPS), "blk")
        blocks(c, r, 14)
        slices(c, r, 10, 220)
    elif kind == "macro":
        sp = A.words["noise"]
        draw(c, sp, W / 2 - 200, H / 2 + 300, word_scale(A, "noise", 3600), 20 * u / CUT + 8)
        trace(c, A, t, W / 2 + 300, H / 2 - 100, 3.2, 15, progress=1, thick=4, amp=8, alpha=0.6, key="mac")
    elif kind == "burn":
        draw(c, A.words["some"], W / 2, H / 2, word_scale(A, "some", 640), -3)
        burn(c, t, seed=40 + k, strength=0.55 + 0.6 * u / CUT, side=1)
    elif kind == "strobe":
        A.smoke.render(c, t, W / 2, H / 2, 1500, 1.1, expand=0.3)
        if int(t * FPS) % 2 == 0:
            draw(c, A.words["some"], W / 2, H / 2 + 20, word_scale(A, "some", 560), 4)
            c *= 1.25


def draw_band(band, sp, x, y, scale):
    """draw() into a small band buffer (marquee rows)."""
    if scale <= 0:
        return
    M = np.float32([[scale, 0, x - sp.w * scale / 2], [0, scale, y - sp.h * scale / 2]])
    a = cv2.warpAffine(sp.a, M, (band.shape[1], band.shape[0]))[:, :, None]
    rgb = cv2.warpAffine(sp.rgb, M, (band.shape[1], band.shape[0]))
    band *= 1 - a
    band += rgb * a


def scene_implode(c, A, t):
    card(c, A, t, "trace", CUT * 0.9, 99)
    draw(c, A.words["noise"], W / 2, H / 2, word_scale(A, "noise", 420), 0, alpha=0.9)


def scene_reveal(c, A, t):
    u = t - REVEAL
    s = 1 + 0.1 * (1 - ease_out(u / 0.16))
    jx, jy = rng_at(t, "logo").normal(0, 1.2, 2)
    draw(c, A.logo_text, LOGO_CENTER[0] + jx, LOGO_CENTER[1] + jy, s, 0)
    # the scope line becomes the underline
    lx0 = LOGO_CENTER[0] - A.logo.w / 2 * s
    ly0 = LOGO_CENTER[1] - A.logo.h / 2 * s
    m = ease_in_out((t - UNDERLINE_SETTLE[0]) / (UNDERLINE_SETTLE[1] - UNDERLINE_SETTLE[0]))
    if m < 1:
        xs = lx0 + A.ul_x * s
        seg = A.audio.window(t, len(xs))
        wild = ly0 + 245 * s - seg * 130 * (1 - m)
        target = ly0 + A.ul_y * s
        ys = wild * (1 - m) + target * m
        pts = np.stack([xs, ys], axis=1).astype(np.int32)
        layer = np.zeros((H, W), np.float32)
        cv2.polylines(layer, [pts], False, 1.0, int(3 + 9 * m), cv2.LINE_AA)
        layer = np.maximum(layer, cv2.GaussianBlur(layer, (0, 0), 5) * 1.4)
        mm = np.clip(layer * (1 - ease_in((m - 0.8) / 0.2)), 0, 1)[:, :, None]
        c[:] = c * (1 - mm) + np.array(WHITE, np.float32) * mm
    if m > 0.8:
        draw(c, A.underline, LOGO_CENTER[0] + jx, LOGO_CENTER[1] + jy, s, 0, alpha=ease_in_out((m - 0.8) / 0.2))
    # alive: a faint boiling scribble trace riding on the lettering
    trace(c, A, t, LOGO_CENTER[0] + jx, LOGO_CENTER[1] + jy, s, 0, progress=1, thick=2, amp=3,
          alpha=0.22 + 0.25 * math.exp(-u / 0.5), key="hold")
    # smoke detonation, thinning and drifting right
    density = 1.7 * math.exp(-u / 0.42)
    if density > 0.02:
        radius = 200 + 1500 * ease_out(u / 0.55)
        A.smoke.render(c, t, W / 2, H / 2, radius, density, drift=(300 * u, -80 * u), expand=1.4 * ease_out(u / 0.9))
    rings(c, W / 2, H / 2, REVEAL, t, n=3, life=0.55, rmax=1700)
    if u < 0.35:
        burn(c, t, seed=77, strength=0.75 * (1 - u / 0.35), side=0)
        burn(c, t, seed=78, strength=0.6 * (1 - u / 0.35), side=1)
    # embers drifting up
    r = np.random.default_rng(5)
    for _ in range(40):
        x = r.uniform(0, W)
        y0 = r.uniform(H * 0.4, H * 1.1)
        sp = r.uniform(40, 140)
        y = y0 - sp * u
        if 0 < y < H and u > 0.2:
            br = r.uniform(0.3, 1) * min((u - 0.2) / 0.4, 1)
            cv2.circle(c, (int(x + 20 * math.sin(u * 2 + x)), int(y)), int(r.uniform(1, 3)), tuple(v * br for v in WHITE), -1)


SCENES = [(0.0, scene_mic), (WORDS[0][0], scene_words), (DROP[0], scene_drop), (IMPLODE[0], scene_implode),
          (SILENCE[0], None), (REVEAL, scene_reveal)]


def render_scene(A, t):
    c = np.zeros((H, W, 3), np.float32)
    fn = [f for t0, f in SCENES if t >= t0][-1]
    if fn is not None and not (GAP1[0] <= t < GAP1[1]):
        fn(c, A, t)
    return c


# ---------------------------------------------------------------------------------------------- post
IMPACTS = ([(t0, 0.25 + 0.06 * k) for k, t0 in enumerate(TAPS)]
           + [(t0, 0.9 if n == "noise" else 0.7) for t0, n in WORDS]
           + [(DROP[0] + s, 0.8) for s in (0.0, 0.6, 1.0, 1.6, 2.2)]
           + [(DROP[0] + 0.8, 0.6), (DROP[0] + 2.4, 0.6), (REVEAL, 1.6)])
INVERT = [round(t0 * FPS) for t0, _ in WORDS] + [round(DROP[0] * FPS)]
FLASH = [round(REVEAL * FPS)]


def post(c, A, t, i):
    sx = sy = 0.0
    split = 1.5
    flash = 0.0
    for ti, k in IMPACTS:
        d = t - ti
        if 0 <= d < 0.45:
            e = math.exp(-d / 0.08)
            r = frame_rng(i, ("shake", ti))
            sx += r.uniform(-1, 1) * 34 * k * e
            sy += r.uniform(-1, 1) * 22 * k * e
            split += 16 * k * math.exp(-d / 0.06)
            flash = max(flash, 0.35 * k * math.exp(-d / 0.03))
    if DROP[0] <= t < DROP[1]:
        split += 4
    # stutter: alternate treatments on every beat-repeat slice
    if STUTTER[0] <= t < GAP1[0]:
        v = stutter_variant(t)
        r = frame_rng(i, "stut")
        if v % 4 == 1:
            c = 255 - c
        elif v % 4 == 2:
            c = slices(c, r, 24, 300)
        elif v % 4 == 3:
            c = rgb_split(c, 40)
        split += 6 + 2 * v
    if DROP[0] <= t < DROP[1]:
        r = frame_rng(i, "dropglitch")
        if r.random() < 0.35:
            c = slices(c, r, int(r.integers(3, 10)), 160)
    for gt in GLITCH_TICKS:
        if gt <= t < gt + 2 / FPS:
            r = frame_rng(i, "tick")
            c = slices(c, r, 8, 90, max_h=30)
            split += 18
    # implosion: everything collapses into a point, spinning
    if IMPLODE[0] <= t < SILENCE[0]:
        p = (t - IMPLODE[0]) / (SILENCE[0] - IMPLODE[0])
        acc = np.zeros_like(c)
        for f in (1.0, 0.92, 0.85):
            z = max((1 - ease_in(p)) * f, 0.004)
            M = cv2.getRotationMatrix2D((W / 2, H / 2), 220 * ease_in(p) * f, z)
            acc += cv2.warpAffine(c, M, (W, H))
        c = acc / 3
        if p > 0.75:
            cv2.circle(c, (W // 2, H // 2), 7, WHITE, -1, cv2.LINE_AA)
    if SILENCE[0] <= t < REVEAL and i % 3 == 0:
        cv2.circle(c, (W // 2, H // 2), 5, WHITE, -1, cv2.LINE_AA)
    # camera shake + gate weave (12 fps)
    wr = rng_at(t, "weave")
    sx += wr.uniform(-1.4, 1.4)
    sy += wr.uniform(-1.0, 1.0)
    M = np.float32([[1, 0, sx], [0, 1, sy]])
    c = cv2.warpAffine(c, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    c = rgb_split(c, int(round(split)))
    if i in INVERT:
        c = 255 - c
    if i in FLASH:
        c[:] = WHITE
    elif flash > 0:
        c += (255 - c) * flash
    # bloom on the whites
    bloom = cv2.GaussianBlur(cv2.resize(np.clip(c - 170, 0, 255), (W // 4, H // 4)), (0, 0), 8)
    c = c + cv2.resize(bloom, (W, H)) * 0.55
    # analog: flicker, grain, dust, scratches, vignette
    fl = 1 + rng_at(t, "flicker").uniform(-0.045, 0.045)
    c = c * fl * A.vignette + A.grain[step(t, 24) % len(A.grain)][:, :, None]
    dr = rng_at(t, "dust")
    for _ in range(int(dr.integers(2, 7))):
        x, y = int(dr.uniform(0, W)), int(dr.uniform(0, H))
        col = 255 if dr.random() < 0.5 else 0
        if dr.random() < 0.7:
            cv2.circle(c, (x, y), int(dr.integers(1, 4)), (col,) * 3, -1)
        else:
            cv2.line(c, (x, y), (x + int(dr.integers(-25, 25)), y + int(dr.integers(-25, 25))), (col,) * 3, 1)
    if dr.random() < 0.25:
        x = int(dr.uniform(0, W))
        cv2.line(c, (x, 0), (x + int(dr.integers(-6, 6)), H), (200,) * 3, 1)
    return np.clip(c, 0, 255).astype(np.uint8)


def render(A, t, i):
    return post(render_scene(A, t), A, t, i)


def mux(video, audio, out, target=-14.0):
    """Linear loudness normalisation (keeps the quiet opening quiet) + true-peak limiter, then mux."""
    import json

    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", audio, "-af",
                        "loudnorm=print_format=json", "-f", "null", "-"], capture_output=True, text=True)
    meas = json.loads(r.stderr[r.stderr.rindex("{"):])
    gain = target - float(meas["input_i"])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-i", audio, "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-af", f"volume={gain:.2f}dB,alimiter=limit=0.89:attack=1:release=50:level=false",
                    "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-movflags", "+faststart", "-shortest", out],
                   check=True)
    return gain


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="LMSN_intro.mp4")
    ap.add_argument("--preview", help="comma-separated seconds: contact sheet PNG")
    ap.add_argument("--still", type=float, help="one full-size PNG frame at this time")
    ap.add_argument("--audio", default=AUDIO_PATH)
    ap.add_argument("--crf", type=int, default=14)
    args = ap.parse_args()
    if not os.path.exists(args.audio):
        sys.exit(f"missing {args.audio}: run sound.py first")
    A = Assets(args.audio)

    if args.still is not None:
        i = round(args.still * FPS)
        cv2.imwrite(args.out, render(A, i / FPS, i))
        print(f"Saved {args.out}")
        return
    if args.preview:
        tiles = []
        for p in (float(x) for x in args.preview.split(",")):
            i = round(p * FPS)
            img = cv2.resize(render(A, i / FPS, i), (W // 4, H // 4), interpolation=cv2.INTER_AREA)
            cv2.putText(img, f"{p:.2f}s", (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            tiles.append(img)
        while len(tiles) % 4:
            tiles.append(np.zeros_like(tiles[0]))
        cv2.imwrite(args.out, np.vstack([np.hstack(tiles[r:r + 4]) for r in range(0, len(tiles), 4)]))
        print(f"Saved preview {args.out}")
        return

    enc = subprocess.Popen([
        "ffmpeg", "-v", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", "slow", "-crf", str(args.crf), "-pix_fmt", "yuv420p",
        "-profile:v", "high", "-tune", "grain", "-movflags", "+faststart", args.out + ".video.mp4",
    ], stdin=subprocess.PIPE)
    n = int(round(LENGTH * FPS))
    for i in range(n):
        enc.stdin.write(render(A, i / FPS, i).tobytes())
        if i % 30 == 0:
            print(f"\rframe {i}/{n}", end="", flush=True)
    enc.stdin.close()
    if enc.wait() != 0:
        sys.exit("ffmpeg failed")
    gain = mux(args.out + ".video.mp4", args.audio, args.out)
    os.remove(args.out + ".video.mp4")
    print(f"\rSaved {args.out} ({n} frames, {LENGTH:.1f}s, audio gain {gain:+.1f} dB to -14 LUFS)")


if __name__ == "__main__":
    main()
