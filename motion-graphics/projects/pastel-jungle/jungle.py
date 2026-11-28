#!/usr/bin/env python3
"""PASTEL JUNGLE: a hand-drawn-FX style reel (1080x1920, 6 s) for LET'S MAKE SOME NOISE.

  python3 motion-graphics/projects/pastel-jungle/jungle.py --out pastel_jungle.mp4
  python3 motion-graphics/projects/pastel-jungle/jungle.py --preview 0.6,1.2,1.8,2.4,4,5.5 --out sheet.png

Style studied from Motion Design School's "Frame by Frame Handdrawn FX" examples (flat painterly shapes,
one inner shade, chalky grain, a deep teal-green jungle, animated "on threes" = 10 drawings per second,
liquid that morphs into a character). The scene and everything in it are original:
  0.0  quiet jungle, vines sway                  0.5  orange paint splashes in from the bottom-left
  1.4  the paint gathers on the branch and morphs into the owner's bucket-hat head (pastel-painted photo)
  2.2  pop, droplets fly, the head swings from the branch like it is hanging there
  3.3  a white paint splash from the right morphs into the LET'S MAKE SOME NOISE logo (kept as-is)
  4.3  hold; the head keeps swinging, one drip falls

Needs the cutout ../launch-intro/assets/ready/greenhat.png and ../show-intro/assets/logo-hires.png
(owner media, git-ignored). Sound is synthesised here.
"""
import argparse
import math
import os
import subprocess
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "show-intro"))
import sound as sfx  # noqa: E402

W, H, FPS = 1080, 1920, 30
LENGTH = 6.0
N = int(LENGTH * FPS)
STEP = 3          # "on threes": a new drawing every 3 frames (10 fps), like hand-drawn FX
Q = 4             # liquid fields are computed at 1/4 resolution

HEAD_PATH = os.path.join(HERE, "..", "launch-intro", "assets", "ready", "greenhat.png")
LOGO_PATH = os.path.join(HERE, "..", "show-intro", "assets", "logo-hires.png")

# palette (BGR) sampled from the reference jungle, plus the paint colours
BG = (60, 63, 28)
BG2 = (80, 84, 43)
LEAF = (112, 171, 117)
LEAF_LIGHT = (136, 207, 148)
LEAF_DARK = (98, 119, 74)
BRANCH = (135, 141, 85)
BRANCH_DARK = (92, 100, 52)
PAINT = (72, 145, 242)
PAINT_SHADE = (40, 96, 205)
PAINT_HI = (137, 226, 248)
WHITE = (238, 242, 245)
WHITE_SHADE = (190, 200, 205)

T_SPLASH = (0.4, 1.4)
T_MORPH = (1.75, 2.2)
T_POP = 2.2
T_LOGO_SPLASH = (3.0, 3.8)
T_LOGO_MORPH = (3.95, 4.3)
T_DRIP = 4.6

HEAD_C = (540, 910)      # where the head hangs (centre)
PIVOT = (540, 430)       # the branch point it hangs from (a vine holds the hat)
LOGO_C = (540, 1520)


def clamp01(x):
    return min(max(x, 0.0), 1.0)


def ease_out(x):
    return 1 - (1 - clamp01(x)) ** 3


def ease_in_out(x):
    x = clamp01(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def drawing_time(f):
    """Animation time for frame f, held for STEP frames (on threes)."""
    return (f // STEP) * STEP / FPS


def drawing_index(f):
    return f // STEP


# ---------------------------------------------------------------- textures
def paper(seed):
    r = np.random.default_rng(seed)
    n = cv2.GaussianBlur(r.normal(0, 1, (H, W)).astype(np.float32), (0, 0), 1.1)
    streak = cv2.blur(r.normal(0, 1, (H, W)).astype(np.float32), (1, 21))  # pastel strokes, vertical
    blot = cv2.resize(r.normal(0, 1, (H // 60, W // 60)).astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)
    return (1 + 0.05 * n + 0.06 * streak + 0.04 * blot)[:, :, None]


def pastelize(path, height):
    """Owner's cutout -> flat painted illustration with a light outline (k-means palette)."""
    im = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if im is None:
        sys.exit(f"missing {path}: re-upload the photos and run launch-intro/prep.py")
    f = height / im.shape[0]
    im = cv2.resize(im, (int(im.shape[1] * f), height), interpolation=cv2.INTER_AREA)
    rgb, a = im[:, :, :3], im[:, :, 3].astype(np.float32) / 255
    sm = cv2.pyrMeanShiftFiltering(rgb, 18, 38, maxLevel=2)
    sm = cv2.bilateralFilter(sm, 9, 60, 9)
    lab = cv2.cvtColor(sm, cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
    m = a.reshape(-1) > 0.5
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
    _, lab_k, cen = cv2.kmeans(lab[m], 7, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    cen[:, 0] = np.clip(cen[:, 0] * 0.85 + 40, 0, 255)  # lift values a little: pastel
    out = lab.copy()
    out[m] = cen[lab_k.ravel()]
    flat = cv2.medianBlur(cv2.cvtColor(out.reshape(sm.shape).astype(np.uint8), cv2.COLOR_LAB2BGR), 7)
    edges = cv2.Canny(cv2.cvtColor(flat, cv2.COLOR_BGR2GRAY), 30, 90)
    edges = cv2.dilate(edges, np.ones((2, 2), np.uint8)).astype(np.float32)[:, :, None] / 255 * 0.35
    flat = flat.astype(np.float32) * (1 - edges) + np.array((40, 50, 30), np.float32) * edges
    return flat, a


# ---------------------------------------------------------------- jungle
class Jungle:
    """Static layers + swaying vines and leaves, all re-drawn per drawing with a little boil."""

    def __init__(self):
        r = np.random.default_rng(4)
        yy = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
        self.base = (np.array(BG, np.float32) * (1 - yy * 0.25) + np.array(BG2, np.float32) * yy * 0.25)
        self.base = np.broadcast_to(self.base, (H, W, 3)).copy() * paper(1)
        # hanging vines from the top: (x, length, thickness, phase)
        self.vines = [(x, r.uniform(200, 760), r.uniform(9, 17), r.uniform(0, 6.28))
                      for x in (-10, 95, 230, 330, 760, 870, 990, 1080) + r.uniform(-30, 30, 8)]
        # leaf clusters (x, y, size, angle, colour index)
        self.leaves = []
        for cx, cy, n in ((40, 330, 14), (1040, 300, 14), (20, 1120, 7), (1060, 1060, 7), (540, 90, 16),
                          (40, 1830, 14), (1050, 1850, 14), (300, 1940, 8), (800, 1950, 8)):
            for _ in range(n):
                self.leaves.append((cx + r.normal(0, 90), cy + r.normal(0, 80), r.uniform(90, 190),
                                    r.uniform(0, 360), int(r.integers(0, 3))))
        self.tex = paper(2)

    def leaf_poly(self, x, y, size, ang, jit):
        t = np.linspace(0, math.pi, 14)
        pts = np.stack([np.sin(t) * size * 0.38, -np.cos(t) * size * 0.5 - size * 0.5], axis=1)
        pts = np.vstack([pts, pts[::-1] * [-1, 1]])
        pts += jit.normal(0, 2.2, pts.shape)
        a = math.radians(ang)
        R = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
        return (pts @ R.T + [x, y]).astype(np.int32)

    def render(self, f):
        t = drawing_time(f)
        jit = np.random.default_rng(1000 + drawing_index(f))
        c = self.base.copy()
        layer = np.zeros((H, W, 3), np.uint8)
        # vines
        for x, ln, th, ph in self.vines:
            ys = np.linspace(-20, ln, 24)
            sway = 18 * math.sin(t * 1.3 + ph)
            xs = x + sway * np.clip(ys / ln, 0, 1) ** 1.5 + jit.normal(0, 1.2, ys.size)
            pts = np.stack([xs, ys], axis=1).astype(np.int32)
            cv2.polylines(layer, [pts], False, LEAF_DARK, int(th), cv2.LINE_AA)
            cv2.polylines(layer, [pts + [int(th * 0.25), 0]], False, LEAF, max(int(th * 0.35), 2), cv2.LINE_AA)
            for k in range(4, 24, 5):  # small leaves on the vine
                lx, ly = pts[k]
                col = (LEAF, LEAF_LIGHT, LEAF_DARK)[k % 3]
                cv2.fillPoly(layer, [self.leaf_poly(lx, ly, 48, (70 if k % 2 else -70) + sway, jit)], col, cv2.LINE_AA)
        # leaf clusters
        for x, y, s, ang, ci in self.leaves:
            sway = 6 * math.sin(t * 1.7 + x * 0.01)
            poly = self.leaf_poly(x, y, s, ang + sway, jit)
            cv2.fillPoly(layer, [poly], (LEAF, LEAF_LIGHT, LEAF_DARK)[ci], cv2.LINE_AA)
            half = poly[: len(poly) // 2 + 1]
            cv2.fillPoly(layer, [np.vstack([half, poly[:1]])], LEAF_DARK if ci != 2 else BRANCH_DARK, cv2.LINE_AA)
        # the branch the head hangs from
        xs = np.linspace(-40, W + 40, 30)
        ys = PIVOT[1] - 18 + 22 * np.sin(xs / 210 + 0.6) - 22 * np.sin(0.6 + 540 / 210) + jit.normal(0, 1.0, xs.size)
        pts = np.stack([xs, ys], axis=1).astype(np.int32)
        cv2.polylines(layer, [pts], False, BRANCH_DARK, 60, cv2.LINE_AA)
        cv2.polylines(layer, [pts - [0, 13]], False, BRANCH, 22, cv2.LINE_AA)
        m = (layer.max(axis=2) > 0).astype(np.float32)[:, :, None]
        c = c * (1 - m) + layer.astype(np.float32) * self.tex * m
        return c


# ---------------------------------------------------------------- liquid
class ParticlePaint:
    """Paint as particles: launched as a splash, swirled by curl noise, then pulled onto points inside a
    target silhouette, so the splash streams, curls, breaks into droplets and finally fills the shape.
    Rendered as metaballs at quarter resolution, one drawing per STEP frames."""

    def __init__(self, target_mask, center, source, launch, t_splash, t_morph, n, rad, seed, color, shade, hi):
        r = np.random.default_rng(seed)
        self.w, self.h = W // Q, H // Q
        yy, xx = np.mgrid[0:self.h, 0:self.w].astype(np.float32)
        self.xx, self.yy = xx * Q + Q / 2, yy * Q + Q / 2
        small = cv2.resize(target_mask, (self.w, self.h), interpolation=cv2.INTER_AREA) > 0.5
        din = cv2.distanceTransform(small.astype(np.uint8), cv2.DIST_L2, 5)
        dout = cv2.distanceTransform((~small).astype(np.uint8), cv2.DIST_L2, 5)
        self.target = np.clip(0.5 + (din - dout) / 6.0, 0, 1.5).astype(np.float32)
        ys, xs = np.nonzero(target_mask > 0.5)
        pick = r.choice(len(xs), n, replace=len(xs) < n)
        goals = np.stack([xs[pick], ys[pick]], axis=1).astype(np.float32)
        self.center, self.t_splash, self.t_morph = center, t_splash, t_morph
        self.color, self.shade, self.hi = (np.array(c, np.float32) for c in (color, shade, hi))
        self.rad = r.uniform(*rad, n).astype(np.float32)
        # simulate once at 240 Hz, store positions at every drawing time
        dt = 1 / 240
        spawn = t_splash[0] + r.uniform(0, 0.55, n) ** 1.5
        pos = np.tile(np.array(source, np.float32), (n, 1)) + r.normal(0, 25, (n, 2))
        vel = np.stack([r.normal(launch[0], abs(launch[0]) * 0.3, n), r.normal(launch[1], abs(launch[1]) * 0.25, n)], 1)
        self.track = {}
        steps = int(LENGTH / dt) + 1
        for k in range(steps):
            t = k * dt
            alive = t >= spawn
            g = clamp01((t - t_splash[1] + 0.35) / 0.6)          # how strongly particles seek their goal
            curl_a = 2 * math.pi * (0.7 * t) + pos[:, 1] / 260   # cheap curl noise: swirling field
            curl = np.stack([np.cos(curl_a), np.sin(curl_a * 1.3)], 1) * 1500 * (1 - g)
            acc = np.array([0, 1500], np.float32) * (1 - g) + curl
            # spring-damper to the goal (critically damped as it settles)
            k_spring = 55 * g ** 2
            acc = acc + (goals - pos) * k_spring - vel * (2 * math.sqrt(k_spring) + 0.6 * (1 - g))
            vel = np.where(alive[:, None], vel + acc * dt, vel)
            pos = np.where(alive[:, None], pos + vel * dt, pos)
            if k % int(STEP / FPS / dt) == 0:
                di = int(round(t * FPS / STEP))
                self.track[di] = (pos.copy(), vel.copy(), alive.copy())

    def field(self, di):
        pos, vel, alive = self.track.get(di, self.track[max(self.track)])
        f = np.zeros((self.h, self.w), np.float32)
        for (px, py), (vx, vy), a, rr in zip(pos, vel, alive, self.rad):
            if not a or px < -200 or px > W + 200 or py < -200 or py > H + 300:
                continue
            sp = math.hypot(vx, vy)
            stretch = 1 + min(sp / 1600, 1.6)                # elongate along the motion: streams and tendrils
            ca, sa = (vx / sp, vy / sp) if sp > 1 else (1.0, 0.0)
            x0, x1 = int(max((px - rr * 5) / Q, 0)), int(min((px + rr * 5) / Q + 1, self.w))
            y0, y1 = int(max((py - rr * 5) / Q, 0)), int(min((py + rr * 5) / Q + 1, self.h))
            if x1 <= x0 or y1 <= y0:
                continue
            dx = self.xx[y0:y1, x0:x1] - px
            dy = self.yy[y0:y1, x0:x1] - py
            u = (dx * ca + dy * sa) / stretch
            v = (-dx * sa + dy * ca) * (1 + 0.25 * (stretch - 1))
            f[y0:y1, x0:x1] += rr * rr / (u * u + v * v + 4.0)
        return f / 2.8

    def render(self, c, t, di):
        a, b = self.t_morph
        m = ease_in_out((t - a) / (b - a))
        if t < self.t_splash[0] or t >= b:
            return m
        occ = self.field(di) * (1 - m) + self.target * m
        if occ.max() < 0.5:
            return m
        jit = np.random.default_rng(5000 + di)
        occ = occ + cv2.GaussianBlur(jit.normal(0, 1, (self.h, self.w)).astype(np.float32), (0, 0), 2.5) * 0.1
        mask = np.clip((occ - 0.5) * 6 + 0.5, 0, 1)
        shifted = cv2.warpAffine(occ, np.float32([[1, 0, -4], [0, 1, -6]]), (self.w, self.h))
        inner = mask * (1 - np.clip((shifted - 0.5) * 6 + 0.5, 0, 1))            # one inner shade
        shifted2 = cv2.warpAffine(occ, np.float32([[1, 0, 3], [0, 1, 5]]), (self.w, self.h))
        hi = mask * (1 - np.clip((shifted2 - 0.5) * 6 + 0.5, 0, 1)) * 0.8        # light rim, upper-left
        up = lambda x: cv2.resize(x, (W, H), interpolation=cv2.INTER_CUBIC)[:, :, None]
        mask, inner, hi = up(mask), up(inner), up(hi)
        col = self.color * (1 - inner) + self.shade * inner
        col = col * (1 - hi) + self.hi * hi
        alpha = np.clip(mask, 0, 1)
        c[:] = c * (1 - alpha) + col * alpha
        return m


def droplets(c, t, t0, center, color, seed, n=16):
    """Droplets flung off when a shape pops into place (flat, with gravity)."""
    u = t - t0
    if not 0 <= u < 1.0:
        return
    r = np.random.default_rng(seed)
    for _ in range(n):
        ang, sp, rad = r.uniform(0, 2 * math.pi), r.uniform(500, 1300), r.uniform(9, 20)
        x = center[0] + math.cos(ang) * sp * u
        y = center[1] + math.sin(ang) * sp * u * 0.8 + 1600 * u * u
        rr = rad * (1 - u * 0.7)
        cv2.ellipse(c, (int(x), int(y)), (int(rr * 1.3), int(rr)), math.degrees(ang), 0, 360, color, -1, cv2.LINE_AA)


def blotch_reveal(mask_shape, progress, seed):
    """Painterly reveal: blotchy noise threshold, like paint being laid down."""
    r = np.random.default_rng(seed)
    n = cv2.resize(r.normal(0, 1, (mask_shape[0] // 70 + 2, mask_shape[1] // 70 + 2)).astype(np.float32),
                   (mask_shape[1], mask_shape[0]), interpolation=cv2.INTER_CUBIC)
    n = (n - n.min()) / (n.max() - n.min() + 1e-6)
    return np.clip((progress * 1.3 - n) * 8, 0, 1)


# ---------------------------------------------------------------- scene
class Scene:
    def __init__(self):
        self.jungle = Jungle()
        flat, a = pastelize(HEAD_PATH, 820)
        self.head_rgb, self.head_a = flat, a
        hh, hw = a.shape
        head_mask = np.zeros((H, W), np.float32)
        x0, y0 = HEAD_C[0] - hw // 2, HEAD_C[1] - hh // 2
        head_mask[y0:y0 + hh, x0:x0 + hw] = a
        lg = cv2.imread(LOGO_PATH, cv2.IMREAD_UNCHANGED)
        if lg is None:
            sys.exit(f"missing {LOGO_PATH}")
        s = 960 / lg.shape[1]
        la = cv2.resize(lg[:, :, 3], (960, int(lg.shape[0] * s)), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
        self.logo_a = la
        logo_mask = np.zeros((H, W), np.float32)
        lx0, ly0 = LOGO_C[0] - la.shape[1] // 2, LOGO_C[1] - la.shape[0] // 2
        logo_mask[ly0:ly0 + la.shape[0], lx0:lx0 + la.shape[1]] = la
        logo_mask = cv2.dilate(logo_mask, np.ones((9, 9), np.uint8))  # the paint fills a slightly fatter shape
        logo_fill = cv2.dilate(logo_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31)))
        self.paint = ParticlePaint(head_mask, HEAD_C, source=(-80, 1650), launch=(1500, -2300), t_splash=T_SPLASH,
                                   t_morph=T_MORPH, n=130, rad=(15, 34), seed=7, color=PAINT, shade=PAINT_SHADE, hi=PAINT_HI)
        self.white = ParticlePaint(logo_fill, LOGO_C, source=(W + 80, 1900), launch=(-1700, -1700), t_splash=T_LOGO_SPLASH,
                                   t_morph=T_LOGO_MORPH, n=170, rad=(14, 24), seed=9, color=WHITE, shade=WHITE_SHADE,
                                   hi=(255, 255, 255))
        self.tex = paper(3)

    def head_angle(self, t):
        if t < T_POP:
            return 0.0
        u = t - T_POP
        return 9 * math.exp(-u * 0.9) * math.sin(u * 4.2 + 0.3)  # pendulum, damped

    def draw_head(self, c, t, f_index, reveal):
        if reveal <= 0:
            return
        ang = self.head_angle(t)
        hh, hw = self.head_a.shape
        squash = 1.0
        if T_POP <= t < T_POP + 0.3:  # pop: squash then settle
            squash = 1 + 0.08 * math.sin((t - T_POP) / 0.3 * math.pi * 2) * (1 - (t - T_POP) / 0.3)
        # rotate around the branch pivot
        M = cv2.getRotationMatrix2D((PIVOT[0] - (HEAD_C[0] - hw / 2), PIVOT[1] - (HEAD_C[1] - hh / 2)), ang, 1.0)
        M[0, 2] += HEAD_C[0] - hw / 2
        M[1, 2] += HEAD_C[1] - hh / 2
        M[0, :2] *= 1 / squash
        M[1, :2] *= squash
        jit = np.random.default_rng(9000 + f_index)
        # the vine that holds the hat
        hat_top = M @ np.array([hw / 2, 18, 1.0])
        rope = np.array([[PIVOT[0], PIVOT[1] - 10], [(PIVOT[0] + hat_top[0]) / 2 + 6, (PIVOT[1] + hat_top[1]) / 2], hat_top[:2]])
        rope = rope + jit.normal(0, 1.2, rope.shape)
        cv2.polylines(c, [rope.astype(np.int32)], False, LEAF_DARK, 14, cv2.LINE_AA)
        cv2.polylines(c, [rope.astype(np.int32) + [3, 0]], False, LEAF, 5, cv2.LINE_AA)
        a = cv2.warpAffine(self.head_a, M, (W, H), flags=cv2.INTER_LINEAR)
        rgb = cv2.warpAffine(self.head_rgb, M, (W, H), flags=cv2.INTER_LINEAR)
        # boil: tiny displacement of the drawing, new every drawing
        dx = cv2.resize(jit.normal(0, 1, (H // 40, W // 40)).astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC) * 1.6
        dy = cv2.resize(jit.normal(0, 1, (H // 40, W // 40)).astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC) * 1.6
        gx, gy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
        a = cv2.remap(a, gx + dx, gy + dy, cv2.INTER_LINEAR)
        rgb = cv2.remap(rgb, gx + dx, gy + dy, cv2.INTER_LINEAR)
        sh = cv2.GaussianBlur(a, (0, 0), 14)
        sh = np.roll(np.roll(sh, 26, 0), 14, 1)[:, :, None] * 0.35 * reveal
        c[:] = c * (1 - sh)
        if reveal < 1:
            a = a * blotch_reveal(a.shape, reveal, 11)
        a = a[:, :, None]
        c[:] = c * (1 - a) + rgb * self.tex * a

    def draw_logo(self, c, t, f_index, reveal):
        if reveal <= 0:
            return
        la = self.logo_a
        jit = np.random.default_rng(7000 + f_index)
        ox, oy = jit.normal(0, 1.0, 2)
        x0, y0 = int(LOGO_C[0] - la.shape[1] / 2 + ox), int(LOGO_C[1] - la.shape[0] / 2 + oy)
        a = np.zeros((H, W), np.float32)
        a[y0:y0 + la.shape[0], x0:x0 + la.shape[1]] = la
        sh = np.roll(np.roll(cv2.GaussianBlur(a, (0, 0), 6), 10, 0), 6, 1)[:, :, None] * 0.45 * reveal
        c[:] = c * (1 - sh)
        if reveal < 1:
            a = a * blotch_reveal(a.shape, reveal, 12)
        a = a[:, :, None]
        c[:] = c * (1 - a) + np.array(WHITE, np.float32) * a

    def drip(self, c, t):
        u = t - T_DRIP
        if not 0 <= u < 1.0:
            return
        ang = math.radians(self.head_angle(t))
        x = HEAD_C[0] + 60 + math.sin(ang) * 300
        y0 = HEAD_C[1] + 330
        y = y0 + 80 * clamp01(u / 0.25) + 2200 * max(0, u - 0.25) ** 2
        r = 11 + 6 * clamp01(u / 0.25)
        if y < LOGO_C[1] - 70:
            cv2.ellipse(c, (int(x), int(y)), (int(r), int(r * (1.2 + 0.6 * clamp01(u * 3)))), 0, 0, 360, PAINT, -1, cv2.LINE_AA)
        elif u < 0.9:  # it splats on the logo
            k = clamp01((y - (LOGO_C[1] - 70)) / 200)
            cv2.ellipse(c, (int(x), int(LOGO_C[1] - 70)), (int(18 + 30 * k), int(8 - 4 * k) + 2), 0, 0, 360, PAINT, -1, cv2.LINE_AA)

    def render(self, f):
        t = drawing_time(f)
        di = drawing_index(f)
        c = self.jungle.render(f)
        head_reveal = clamp01((t - (T_MORPH[0] + 0.4 * (T_MORPH[1] - T_MORPH[0]))) / (0.6 * (T_MORPH[1] - T_MORPH[0])))
        if t < T_MORPH[1]:
            self.paint.render(c, t, di)  # paint first; the painted head is laid on top of it
        self.draw_head(c, t, di, head_reveal if t < T_MORPH[1] else 1.0)
        droplets(c, t, T_POP, HEAD_C, PAINT, 21)
        if t < T_LOGO_MORPH[1]:
            self.white.render(c, t, di)
        logo_reveal = clamp01((t - (T_LOGO_MORPH[0] + 0.5 * (T_LOGO_MORPH[1] - T_LOGO_MORPH[0]))) /
                              (0.5 * (T_LOGO_MORPH[1] - T_LOGO_MORPH[0])))
        self.draw_logo(c, t, di, logo_reveal if t < T_LOGO_MORPH[1] else 1.0)
        droplets(c, t, T_LOGO_MORPH[1], LOGO_C, WHITE, 22, n=10)
        self.drip(c, t)
        return c


def post(c, f):
    r = np.random.default_rng(f // STEP)
    grain = cv2.GaussianBlur(r.normal(0, 6, (H, W)).astype(np.float32), (0, 0), 0.9)[:, :, None]
    yy, xx = np.ogrid[0:H, 0:W]
    v = 1 - 0.3 * np.clip((np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / 1.41 - 0.35) / 0.65, 0, 1) ** 1.5
    c = c * v[:, :, None].astype(np.float32) + grain
    if f < 6:
        c *= f / 6
    if f > N - 6:
        c *= (N - f) / 6
    return np.clip(c, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- sound
def build_sound(path):
    SR = sfx.SR
    n = int((LENGTH + 0.4) * SR)
    rng = np.random.default_rng(3)
    mix = np.zeros((2, n))
    send = np.zeros(n)

    def add(s, t, g=1.0, pan=0.0, wet=0.0):
        i = int(t * SR)
        s = np.atleast_2d(s)
        if s.shape[0] == 1:
            s = np.vstack([s[0] * min(1, 1 - pan), s[0] * min(1, 1 + pan)])
        j = min(i + s.shape[1], n)
        if j > i:
            mix[:, i:j] += s[:, :j - i] * g
            send[i:j] += s.mean(axis=0)[:j - i] * g * wet

    tt = sfx.tt
    # jungle ambience: soft air + insects + birds
    air = sfx.filt(rng.normal(0, 1, n), "bandpass", [300, 2500]) * 0.025
    insects = sfx.filt(rng.normal(0, 1, n), "bandpass", [4500, 6500]) * (0.5 + 0.5 * np.sin(2 * np.pi * 7 * tt(n))) * 0.012
    add(air + insects, 0)

    def bird(f0, dur=0.12):
        m = int(dur * SR)
        t = tt(m)
        f = f0 * (1 + 0.5 * np.sin(np.pi * t / dur))
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / dur) ** 2 * 0.25

    for at, f0, pan in ((0.2, 2600, -0.6), (0.34, 3100, -0.6), (1.0, 2400, 0.7), (2.9, 2900, 0.5), (3.05, 3300, 0.5),
                        (5.0, 2700, -0.4), (5.12, 3200, -0.4)):
        add(bird(f0), at, 0.8, pan, wet=0.4)

    def splash(dur=0.6):
        m = int(dur * SR)
        t = tt(m)
        x = sfx.filt(rng.normal(0, 1, m), "bandpass", [500, 5000]) * np.exp(-t / 0.18)
        thump = np.sin(2 * np.pi * np.cumsum(120 * np.exp(-t / 0.05) + 50) / SR) * np.exp(-t / 0.1)
        return x * 0.6 + thump * 0.5

    def gloop(f0, dur=0.18):
        m = int(dur * SR)
        t = tt(m)
        f = f0 * (1 + 1.5 * (t / dur) ** 2)
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / dur) * 0.45

    def pluck(f0, dur=0.5):
        m = int(dur * SR)
        t = tt(m)
        return (np.sin(2 * np.pi * f0 * t) + 0.35 * np.sin(2 * np.pi * f0 * 4 * t) * np.exp(-t / 0.03)) * np.exp(-t / 0.16) * 0.4

    add(splash(), T_SPLASH[0], 1.0, -0.5, wet=0.3)
    for k, at in enumerate(np.arange(T_SPLASH[0] + 0.15, T_MORPH[1], 0.13)):
        add(gloop(180 + 70 * (k % 4)), at, 0.7, -0.4 + 0.1 * k, wet=0.3)
    add(pluck(523.3) + pluck(784.0) * 0.6, T_POP, 1.0, wet=0.4)
    add(sfx.snap(0.15), T_POP, 0.5)
    for k, at in enumerate((T_POP + 0.12, T_POP + 0.22, T_POP + 0.35)):
        add(gloop(700 + 200 * k, 0.08), at, 0.5, (-0.5, 0.5, 0)[k])
    # a little marimba-ish motif while the head swings
    for k, (at, f0) in enumerate(((2.6, 392.0), (2.85, 440.0), (3.1, 523.3))):
        add(pluck(f0), at, 0.7, (-0.3, 0, 0.3)[k], wet=0.3)
    add(splash(0.5), T_LOGO_SPLASH[0], 0.9, 0.5, wet=0.3)
    for k, at in enumerate(np.arange(T_LOGO_SPLASH[0] + 0.12, T_LOGO_MORPH[1], 0.12)):
        add(gloop(220 + 60 * (k % 3)), at, 0.6, 0.4 - 0.1 * k, wet=0.3)
    add(sfx.kick(2.2), T_LOGO_MORPH[1], 0.6)
    add(pluck(392.0) + pluck(523.3) * 0.8 + pluck(659.3) * 0.6, T_LOGO_MORPH[1], 1.0, wet=0.5)
    add(gloop(900, 0.06), T_DRIP + 0.55, 0.6, 0.1, wet=0.4)
    for k, (at, f0) in enumerate(((5.0, 523.3), (5.25, 659.3), (5.5, 784.0))):
        add(pluck(f0) * 0.8, at, 0.6, (-0.3, 0, 0.3)[k], wet=0.4)
    wet = np.vstack([sfx.reverb(send, seed=1), sfx.reverb(send, seed=2)]) * 0.45
    out = np.tanh((mix + wet) * 0.8) / 0.8
    end = int(LENGTH * SR)
    out = out[:, :end] * np.clip((end - np.arange(end)) / (0.3 * SR), 0, 1)
    out *= 0.89 / (np.abs(out).max() + 1e-9)
    sfx.write(path, out)


def mux(video, audio, out, target=-14.0):
    import json

    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", audio, "-af", "loudnorm=print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True)
    gain = target - float(json.loads(r.stderr[r.stderr.rindex("{"):])["input_i"])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-i", audio, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-af", f"volume={gain:.2f}dB,alimiter=limit=0.75:attack=1:release=50:level=false",
                    "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-movflags", "+faststart", "-shortest", out], check=True)
    return gain


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="pastel_jungle.mp4")
    ap.add_argument("--preview")
    args = ap.parse_args()
    sc = Scene()
    if args.preview:
        tiles = []
        for p in (float(x) for x in args.preview.split(",")):
            f = round(p * FPS)
            img = cv2.resize(post(sc.render(f), f), (W // 4, H // 4), interpolation=cv2.INTER_AREA)
            cv2.putText(img, f"{p:.2f}s", (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            tiles.append(img)
        while len(tiles) % 6:
            tiles.append(np.zeros_like(tiles[0]))
        cv2.imwrite(args.out, np.vstack([np.hstack(tiles[r:r + 6]) for r in range(0, len(tiles), 6)]))
        print(f"Saved preview {args.out}")
        return
    wav = os.path.splitext(args.out)[0] + ".wav"
    build_sound(wav)
    vid = args.out + ".video.mp4"
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "18",
                            "-pix_fmt", "yuv420p", "-tune", "animation", "-movflags", "+faststart", vid], stdin=subprocess.PIPE)
    cache = {}
    for f in range(N):
        key = f // STEP  # on threes: every drawing is rendered once and held
        if key not in cache:
            cache = {key: post(sc.render(f), f)}
        enc.stdin.write(cache[key].tobytes())
        if f % 30 == 0:
            print(f"\rframe {f}/{N}", end="", flush=True)
    enc.stdin.close()
    if enc.wait() != 0:
        sys.exit("ffmpeg failed")
    gain = mux(vid, wav, args.out)
    os.remove(vid)
    print(f"\rSaved {args.out} ({N} frames, {LENGTH}s, audio {gain:+.1f} dB to -14 LUFS)")


if __name__ == "__main__":
    main()
