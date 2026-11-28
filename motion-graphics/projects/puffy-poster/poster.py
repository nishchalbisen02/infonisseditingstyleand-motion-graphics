#!/usr/bin/env python3
"""PUFFY NOISE: 2D x 3D motion poster for LET'S MAKE SOME NOISE (1080x1920, 8 s, 30 fps).

  python3 motion-graphics/projects/puffy-poster/poster.py --out puffy.mp4          # video + sound
  python3 motion-graphics/projects/puffy-poster/poster.py --still 7.6 --out poster.png
  python3 motion-graphics/projects/puffy-poster/poster.py --layers out_dir          # PNG layers for Canva
  python3 motion-graphics/projects/puffy-poster/poster.py --preview 0.6,1.2,2.5,4.9,6.1 --out sheet.png

Look (from the owner's reference): bubblegum-pink puffy 3D type on a grungy blue wall, white hand-drawn
doodles, soft haze, and a real photo cut out in front. Here the 3D type is the owner's own logo
letterforms inflated into clay (puffy.py), the photo is the owner leaning on the blue auto.

Motion: words drop in deflated and get pumped up on landing (squash + spring), the photo pops up from
the bottom, doodles draw on at 12 fps, then a 2.5D parallax drift with a moving light (the 3D shading
really changes), beat bounces at 100 BPM, a squeeze-and-pop on "noise" and a final hit.
Needs assets/ready/person-auto.png and ../show-intro/assets/logo-hires.png (owner media, git-ignored).
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
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "show-intro"))
import puffy as P  # noqa: E402
import sound as sfx  # noqa: E402

W, H, FPS = 1080, 1920, 30
LENGTH = 8.0
N = int(LENGTH * FPS)
BOIL = 12
BPM = 100
BEAT = 60 / BPM
G0 = 1.8                      # groove starts when the photo lands
POKE = G0 + 5 * BEAT          # 4.8 s: squeeze-and-pop on "noise"
HIT = G0 + 7 * BEAT           # 6.0 s: final hit
WORD_T = [0.35, 0.5, 0.8, 0.95]
PHOTO_T = 1.35
FONTS = os.path.join(HERE, "..", "..", "assets", "fonts")
INTER = "/usr/share/fonts/opentype/inter/"
WHITE = (245, 245, 245)

LINES = [(0, 1, 520), (2, 3, 835)]   # (word, word, centre y)
PHOTO_C, PHOTO_H = (640, 1915), 900  # photo bottom-centre and height


def clamp01(x):
    return min(max(x, 0.0), 1.0)


def ease_out(x):
    return 1 - (1 - clamp01(x)) ** 3


def ease_in(x):
    return clamp01(x) ** 2


def spring(u, freq=2.2, damp=6.0):
    if u <= 0:
        return 0.0
    return 1 - math.exp(-damp * u) * math.cos(2 * math.pi * freq * u)


def font(name, size):
    for path in (os.path.join(INTER, name), os.path.join(FONTS, name)):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.truetype(os.path.join(FONTS, "Anton-Regular.ttf"), size)


def hsh(x):
    return zlib.crc32(repr(x).encode())


# ---------------------------------------------------------------- doodles (white, hand-drawn, boiling)
def wobble(pts, rng, step=7.0, amp=2.0):
    out = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        n = max(int(math.hypot(x1 - x0, y1 - y0) / step), 1)
        nx, ny = -(y1 - y0), x1 - x0
        ln = math.hypot(nx, ny) or 1
        for i in range(n):
            f = i / n
            w = amp * math.sin(f * math.pi * 2 + rng.uniform(0, 6.28)) * rng.uniform(0.4, 1)
            out.append((x0 + (x1 - x0) * f + nx / ln * w, y0 + (y1 - y0) * f + ny / ln * w))
    out.append(pts[-1])
    return np.array(out, np.float32)


def ellipse_pts(cx, cy, rx, ry, a0=0.15, a1=2 * math.pi + 0.5, n=40, tilt=-6):
    t = np.linspace(a0, a1, n)
    c, s = math.cos(math.radians(tilt)), math.sin(math.radians(tilt))
    x, y = rx * np.cos(t), ry * np.sin(t)
    return list(zip(cx + x * c - y * s, cy + x * s + y * c))


def arc_pts(cx, cy, r, a0, a1, n=12):
    t = np.radians(np.linspace(a0, a1, n))
    return list(zip(cx + r * np.cos(t), cy + r * np.sin(t)))


DOODLES = [
    # (start time, draw duration, [polylines], thickness)
    (2.0, 0.15, [[(975, 650), (1045, 720)], [(1045, 650), (975, 720)]], 6),                               # X
    (2.15, 0.3, [[(1010, 930), (1040, 990), (1035, 1050), (990, 1100)], [(975, 1072), (988, 1103), (1022, 1090)]], 5),  # arrow
    (2.3, 0.35, [ellipse_pts(190, 1095, 178, 72)], 5),                                                     # bubble
    (2.2, 0.2, [arc_pts(185, 1690, 120, 235, 305), arc_pts(185, 1690, 155, 238, 302), arc_pts(185, 1690, 190, 241, 299)], 6),  # sound waves
    (2.55, 0.12, [[(110, 700), (110, 745)], [(88, 722), (132, 722)]], 5),                                  # sparkle
]


def draw_partial(layer, lines, progress, thick, rng):
    total = sum(float(np.linalg.norm(np.diff(np.array(l), axis=0), axis=1).sum()) for l in lines)
    budget = total * clamp01(progress)
    for l in lines:
        if budget <= 0:
            break
        pts = wobble(l, rng)
        seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        keep = int(np.searchsorted(np.cumsum(seg), budget)) + 2
        budget -= float(seg.sum())
        cv2.polylines(layer, [(pts[:keep] * 4).astype(np.int32)], False, 1.0, thick, cv2.LINE_AA, shift=2)


# ---------------------------------------------------------------- assets
class Assets:
    def __init__(self):
        self.bg = P.blue_wall(W, H)
        self.haze = P.smoke(W, H, 760, 600, 420, strength=0.5)
        words = P.logo_words()
        self.puffs = []
        kern = 6
        for li, (a, b, cy) in enumerate(LINES):
            raw = sum(words[k].shape[1] for k in (a, b))
            scale = (1000 - kern) / raw
            x = (W - 1000) / 2
            for wi in (a, b):
                sil, groove = P.prep_mask(words[wi], scale)
                pf = P.Puffy(sil, groove, seed=wi)
                content = words[wi].shape[1] * scale
                self.puffs.append((pf, x + content / 2, cy))
                x += content + kern
        im = compose_person_auto() if os.path.exists(asset("gen-auto.png")) else cv2.imread(
            asset("person-auto.png"), cv2.IMREAD_UNCHANGED)
        if im is None:
            sys.exit("missing assets/ready/gen-auto.png + gen-person.png or person-auto.png (see README)")
        s = PHOTO_H / im.shape[0]
        im = cv2.resize(im, (int(im.shape[1] * s), PHOTO_H), interpolation=cv2.INTER_AREA)
        rgb = im[:, :, :3].astype(np.float32)
        # match the photo to the scene: a touch cooler and more contrast, like it was shot there
        rgb = np.clip((rgb - 128) * 1.06 + 128 + np.array([8, 0, -6], np.float32), 0, 255)
        self.photo = (rgb, im[:, :, 3].astype(np.float32) / 255)
        self.props = []
        for name, width, flip in (("waves", 330, False), ("megaphone", 300, True), ("boombox", 300, False)):
            sp = load_sprite(asset(f"gen-{name}.png"), width, flip)
            if sp is not None:
                self.props.append((name, sp))
        self.text = self.text_layer()
        r = np.random.default_rng(9)
        self.grain = [cv2.GaussianBlur(r.normal(0, 6, (H, W)).astype(np.float32), (0, 0), 0.8) for _ in range(6)]

    def text_layer(self):
        im = Image.new("L", (W, H), 0)
        d = ImageDraw.Draw(im)
        light, bold = font("Inter-Light.otf", 44), font("Inter-ExtraBold.otf", 44)
        parts = [("ZINDAGI ", light), ("THODI LOUD", bold), (" HONE WALI HAI", light)]
        total = sum(d.textlength(t, font=f) for t, f in parts)
        x = (W - total) / 2
        for t, f in parts:
            d.text((x, 92), t, font=f, fill=255)
            x += d.textlength(t, font=f)
        hand = font("Mali-Regular.ttf", 29)
        for i, line in enumerate(("sound on karo,", "baaki hum dekh lenge")):
            tw = d.textlength(line, font=hand)
            d.text((190 - tw / 2, 1058 + i * 38), line, font=hand, fill=255)
        return np.asarray(im, np.float32) / 255

    def text_mask(self, t):
        """Top line wipes in; bubble text types in after the bubble is drawn."""
        m = self.text.copy()
        top = clamp01((t - 0.15) / 0.45)
        m[:300, int(W * top):] = 0
        bub = clamp01((t - 2.55) / 0.45)
        region = m[1000:1160, :420]
        region[:, int(420 * bub):] = 0
        return m



# ---------------------------------------------------------------- Canva-generated elements
def asset(name):
    return os.path.join(HERE, "assets", "ready", name)


def crop_alpha(im, pad=4):
    ys, xs = np.where(im[:, :, 3] > 12)
    return im[max(ys.min() - pad, 0):ys.max() + pad, max(xs.min() - pad, 0):xs.max() + pad]


def compose_person_auto():
    """Canva-generated full auto behind, the owner (cut out by Canva) standing in front of it, like the photo."""
    auto = crop_alpha(cv2.imread(asset("gen-auto.png"), cv2.IMREAD_UNCHANGED))
    person = crop_alpha(cv2.imread(asset("gen-person.png"), cv2.IMREAD_UNCHANGED))
    ah, aw = auto.shape[:2]
    ph = int(ah * 1.04)
    person = cv2.resize(person, (int(person.shape[1] * ph / person.shape[0]), ph), interpolation=cv2.INTER_AREA)
    pw = person.shape[1]
    cw, chh = max(aw, int(aw * 0.5 + pw * 0.75)) + 20, int(ah * 1.08)
    canvas = np.zeros((chh, cw, 4), np.float32)

    def paste(img, x, y):
        a = img[:, :, 3:4].astype(np.float32) / 255
        roi = canvas[y:y + img.shape[0], x:x + img.shape[1]]
        roi[:, :, :3] = roi[:, :, :3] * (1 - a) + img[:, :, :3] * a
        roi[:, :, 3:] = roi[:, :, 3:] * (1 - a) + 255 * a

    paste(auto, 0, 0)
    # contact shadow of the person on the auto body
    px, py = int(aw * 0.5 - pw * 0.25), chh - ph
    sh = np.zeros((chh, cw), np.float32)
    sh[py:py + ph, px:px + pw] = person[:, :, 3] / 255.0
    sh = np.roll(cv2.GaussianBlur(sh, (0, 0), 22), -30, 1) * 0.45
    canvas[:, :, :3] *= (1 - sh[:, :, None])
    paste(person, px, py)
    return np.clip(canvas, 0, 255).astype(np.uint8)


def load_sprite(path, width, flip=False):
    im = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if im is None:
        return None
    im = crop_alpha(im)
    h = int(im.shape[0] * width / im.shape[1])
    im = cv2.resize(im, (width, h), interpolation=cv2.INTER_AREA)
    if flip:
        im = im[:, ::-1]
    return np.ascontiguousarray(im[:, :, :3], np.float32), np.ascontiguousarray(im[:, :, 3], np.float32) / 255


PROPS = {
    # name: (centre x, centre y, appear time, depth, behind the type?, rest rotation)
    "waves": (185, 300, 1.95, 0.5, True, -6),
    "megaphone": (915, 292, 2.05, 1.3, False, 12),
    "boombox": (175, 1775, 2.15, 1.2, False, -4),
}


def draw_props(c, A, t, behind, layers=None):
    for name, (rgb, a) in A.props:
        x, y, t0, depth, is_behind, rest = PROPS[name]
        if is_behind != behind or t < t0:
            continue
        u = t - t0
        s = spring(u, 1.8, 6.5)                                     # pops in with overshoot
        rot = rest + (1 - min(s, 1.2)) * 25
        ph = {"waves": 0.0, "megaphone": 2.1, "boombox": 4.2}[name]
        y += 10 * math.sin(2 * math.pi * t / 2.4 + ph)              # float
        rot += 4 * math.sin(2 * math.pi * t / 3.1 + ph)
        sx = sy = 1.0
        if t >= G0:                                                 # react to the beat
            b = math.exp(-(((t - G0) % BEAT) / BEAT) * 7)
            if name == "megaphone":
                sx = sy = 1 + 0.08 * b
                x += 8 * b                                          # recoil (it points left)
            elif name == "boombox":
                sx, sy = 1 + 0.05 * b, 1 - 0.07 * b
            else:
                sx = sy = 1 + 0.05 * b
        if name == "megaphone" and POKE - 0.1 <= t < POKE + 0.5:    # it blasts when "noise" gets poked
            z = t - (POKE - 0.1)
            k = math.exp(-z * 6) * math.cos(z * 2 * math.pi * 3)
            sx = sy = sx * (1 + 0.25 * k)
        if t >= HIT:                                                # everything jumps on the final hit
            z = t - HIT
            y -= 60 * math.exp(-z * 7) * abs(math.cos(z * 2 * math.pi * 1.5))
        dx, dy = camera(t, depth)
        M = cv2.getRotationMatrix2D((a.shape[1] / 2, a.shape[0] / 2), rot, s)
        M[0, :2] *= sx
        M[1, :2] *= sy
        M[0, 2] = x + dx - (M[0, 0] * a.shape[1] / 2 + M[0, 1] * a.shape[0] / 2)
        M[1, 2] = y + dy - (M[1, 0] * a.shape[1] / 2 + M[1, 1] * a.shape[0] / 2)
        aw = cv2.warpAffine(a, M, (W, H), flags=cv2.INTER_LINEAR)
        rw = cv2.warpAffine(rgb, M, (W, H), flags=cv2.INTER_LINEAR)
        sh = np.roll(np.roll(cv2.GaussianBlur(aw, (0, 0), 12), 22, 0), 14, 1)
        c *= 1 - (sh * 0.45)[:, :, None]
        c = c * (1 - aw[:, :, None]) + rw * aw[:, :, None]
        if layers is not None:
            layers[f"prop_{name}"] = np.dstack([rw, aw * 255])
    return c

# ---------------------------------------------------------------- picture
def word_state(t, k):
    """(dy, sx, sy, rot, inflate) for word k at time t."""
    t0 = WORD_T[k]
    u = t - t0
    if u < 0:
        return None
    fall = 0.22
    if k < 2 and u < fall:       # line 1 drops in from above the frame, deflated
        p = ease_in(u / fall)
        return -720 * (1 - p), 0.92, 1.1, (8 if k % 2 else -8) * (1 - p), 0.35
    if k >= 2 and u < fall:      # line 2 is pumped up in place like a balloon
        p = ease_out(u / fall)
        return 0.0, 0.15 + 0.85 * p, 0.15 + 0.85 * p, (6 if k % 2 else -6) * (1 - p), 0.1 + 0.3 * p
    v = u - fall
    sq = math.exp(-v * 9) * math.cos(v * 2 * math.pi * 2.6)
    sx, sy = 1 + 0.14 * sq, 1 - 0.2 * sq
    inflate = 0.35 + 0.65 * spring(v, 2.0, 5.0) + 0.2 * math.exp(-v * 6) * math.sin(v * 18)
    # beat bounce (after the groove starts), squeeze-and-pop on "noise", final wave
    if t >= G0:
        b = ((t - G0) % BEAT) / BEAT
        bounce = math.exp(-b * 7)
        sy *= 1 + 0.025 * bounce
        sx *= 1 - 0.015 * bounce
        inflate += 0.03 * bounce
    if k == 3 and t >= POKE - 0.12:
        w = t - (POKE - 0.12)
        if w < 0.12:   # squeezed
            e = w / 0.12
            inflate *= 1 - 0.45 * e
            sx, sy = sx * (1 + 0.12 * e), sy * (1 - 0.3 * e)
        else:          # pops back, overshoots, jiggles
            z = w - 0.12
            j = math.exp(-z * 5) * math.cos(z * 2 * math.pi * 3)
            inflate *= 1 + 0.3 * j
            sx, sy = sx * (1 - 0.08 * j), sy * (1 + 0.16 * j)
    if t >= HIT + 0.04 * k:
        z = t - HIT - 0.04 * k
        j = math.exp(-z * 6) * math.cos(z * 2 * math.pi * 2.5)
        inflate *= 1 + 0.18 * j
        sy *= 1 + 0.1 * j
    return 0.0, sx, sy, 0.0, inflate


def light_at(t):
    th = -2.2 + 0.25 * math.sin(t * 0.7) + (0.6 * clamp01((t - 3.0) / 4.0))
    return (math.cos(th) * 0.55, math.sin(th) * 0.75, 0.62)


def camera(t, depth):
    k = clamp01((t - 1.0) / 1.5)
    return (math.sin(t * 0.55) * 16 * depth * k, math.sin(t * 0.42 + 1) * 12 * depth * k)


def shake(t, i):
    for t0, amp in ((PHOTO_T + 0.45, 10), (HIT, 18), (POKE + 0.12, 6)):
        d = t - t0
        if 0 <= d < 0.3:
            r = np.random.default_rng(i)
            e = math.exp(-d / 0.07)
            return r.uniform(-1, 1) * amp * e, r.uniform(-1, 1) * amp * e
    return 0.0, 0.0


def render(A, f, layers=None):
    t = f / FPS
    db = math.floor(t * BOIL)  # doodle drawing index (12 fps)
    c = A.bg.copy()
    cx, cy = camera(t, 0.3)
    if cx or cy:
        c = cv2.warpAffine(c, np.float32([[1, 0, cx], [0, 1, cy]]), (W, H), borderMode=cv2.BORDER_REFLECT)
    hz = A.haze
    if t > 0:
        hz = cv2.warpAffine(A.haze, np.float32([[1, 0, 20 * math.sin(t * 0.4)], [0, 1, -10 * t]]), (W, H),
                            borderMode=cv2.BORDER_REFLECT)
    c = c * (1 - hz[:, :, None] * 0.7) + 235 * hz[:, :, None] * 0.7
    if layers is not None:
        layers["background"] = c.copy()

    c = draw_props(c, A, t, behind=True, layers=layers)

    # 3D type
    type_rgb = np.zeros((H, W, 3), np.float32)
    type_a = np.zeros((H, W), np.float32)
    tx, ty = camera(t, 0.7)
    L = light_at(t)
    for k, (pf, wx, wy) in enumerate(A.puffs):
        st = word_state(t, k)
        if st is None:
            continue
        dy, sx, sy, rot, inflate = st
        rgb, a = pf.render(inflate, L)
        M = cv2.getRotationMatrix2D((a.shape[1] / 2, a.shape[0] * 0.75), rot, 1.0)   # pivot near the base
        M[0, :2] *= sx
        M[1, :2] *= sy
        M[0, 2] = wx + tx - (M[0, 0] * a.shape[1] / 2 + M[0, 1] * a.shape[0] * 0.75) + (M[0, 0] * 0 + 0)
        M[1, 2] = wy + ty + dy + a.shape[0] * 0.25 - (M[1, 0] * a.shape[1] / 2 + M[1, 1] * a.shape[0] * 0.75)
        aw = cv2.warpAffine(a, M, (W, H), flags=cv2.INTER_LINEAR)
        rw = cv2.warpAffine(rgb, M, (W, H), flags=cv2.INTER_LINEAR)
        type_rgb = type_rgb * (1 - aw[:, :, None]) + rw * aw[:, :, None]
        type_a = np.maximum(type_a, aw)
    # 3D: the whole type block yaws and pitches a little in perspective (it is a real surface)
    k3 = clamp01((t - 2.4) / 1.0)
    yaw = math.radians(16 * math.sin(t * 0.65) * k3)
    pitch = math.radians(8 * math.sin(t * 0.5 + 1.3) * k3)
    if k3 > 0:
        # rotate the type plane about its own centre in 3D, project with a pinhole camera
        cxp, cyp, d = W / 2, 680.0, 2200.0
        Ry = np.array([[math.cos(yaw), 0, math.sin(yaw)], [0, 1, 0], [-math.sin(yaw), 0, math.cos(yaw)]])
        Rx = np.array([[1, 0, 0], [0, math.cos(pitch), -math.sin(pitch)], [0, math.sin(pitch), math.cos(pitch)]])
        src = np.float32([[0, 300], [W, 300], [W, 1060], [0, 1060]])
        p3 = np.c_[src[:, 0] - cxp, src[:, 1] - cyp, np.zeros(4)] @ (Ry @ Rx).T
        dst = np.float32(np.c_[cxp + p3[:, 0] * d / (d + p3[:, 2]), cyp + p3[:, 1] * d / (d + p3[:, 2])])
        Hm = cv2.getPerspectiveTransform(src, dst)
        type_rgb = cv2.warpPerspective(type_rgb, Hm, (W, H), flags=cv2.INTER_LINEAR)
        type_a = cv2.warpPerspective(type_a, Hm, (W, H), flags=cv2.INTER_LINEAR)
    sh = cv2.GaussianBlur(type_a, (0, 0), 14)
    sh = np.roll(np.roll(sh, 30, 0), 18, 1)
    c *= 1 - (sh * 0.55)[:, :, None]
    c = c * (1 - type_a[:, :, None]) + type_rgb * type_a[:, :, None]
    if layers is not None:
        layers["type_3d"] = np.dstack([type_rgb, type_a * 255])

    # photo (front layer, most parallax)
    u = t - PHOTO_T
    if u >= 0:
        rise = spring(u, 1.3, 8.0)
        px, py = camera(t, 1.2)
        rgb, a = A.photo
        x0 = PHOTO_C[0] - a.shape[1] / 2 + px
        y0 = PHOTO_C[1] - a.shape[0] + (1 - rise) * 1000 + py
        rot = -5 * (1 - min(rise, 1.0))
        M = cv2.getRotationMatrix2D((a.shape[1] / 2, a.shape[0]), rot, 1.0)
        M[0, 2] += x0
        M[1, 2] += y0
        aw = cv2.warpAffine(a, M, (W, H), flags=cv2.INTER_LINEAR)
        rw = cv2.warpAffine(rgb, M, (W, H), flags=cv2.INTER_LINEAR)
        shp = np.roll(cv2.GaussianBlur(aw, (0, 0), 18), 26, 1)
        c *= 1 - (shp * 0.5)[:, :, None]
        c = c * (1 - aw[:, :, None]) + rw * aw[:, :, None]
        if layers is not None:
            layers["photo"] = np.dstack([rw, aw * 255])
    c = draw_props(c, A, t, behind=False, layers=layers)

    # doodles + text (top layer)
    ink = np.zeros((H, W), np.float32)
    rng = np.random.default_rng(hsh(("boil", db)))
    for t0, dur, lines, th in DOODLES:
        if t >= t0:
            draw_partial(ink, lines, (t - t0) / dur, th, rng)
    # sound waves pulse on the beat
    if t >= G0:
        b = ((t - G0) % BEAT) / BEAT
        if b < 0.35:
            draw_partial(ink, [arc_pts(185, 1690, 225 + 40 * b, 244, 296)], 1, 5, rng)
    # pop lines when "noise" pops and on the final hit
    for t0 in (POKE, HIT):
        z = t - t0
        if 0 <= z < 0.3:
            pf, wx, wy = A.puffs[3]
            ox, oy = wx + 200, wy - 70
            for ang in (-75, -45, -15):
                a_ = math.radians(ang)
                r0, r1 = 30 + 70 * ease_out(z / 0.3), 70 + 90 * ease_out(z / 0.3)
                draw_partial(ink, [[(ox + math.cos(a_) * r0, oy + math.sin(a_) * r0),
                                    (ox + math.cos(a_) * r1, oy + math.sin(a_) * r1)]], 1, 6, rng)
    dx, dy = camera(t, 1.4)
    ink = np.maximum(ink, A.text_mask(t))
    if dx or dy:
        ink = cv2.warpAffine(ink, np.float32([[1, 0, dx], [0, 1, dy]]), (W, H))
    c = c * (1 - ink[:, :, None]) + np.array(WHITE, np.float32) * ink[:, :, None]
    if layers is not None:
        layers["doodles_text"] = np.dstack([np.full((H, W, 3), WHITE, np.float32), ink * 255])

    # post: double rule under the top line, shake, grain, fade in/out
    sx_, sy_ = shake(t, f)
    if sx_ or sy_:
        c = cv2.warpAffine(c, np.float32([[1, 0, sx_], [0, 1, sy_]]), (W, H), borderMode=cv2.BORDER_REFLECT)
    c = c + A.grain[(f // 2) % len(A.grain)][:, :, None]
    if f < 8:
        c *= f / 8
    return np.clip(c, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- sound
def build_sound(path):
    SR = sfx.SR
    n = int((LENGTH + 0.4) * SR)
    mix = np.zeros((2, n))
    send = np.zeros(n)
    rng = np.random.default_rng(4)
    tt = sfx.tt

    def add(s, t, g=1.0, pan=0.0, wet=0.0):
        i = int(t * SR)
        s = np.atleast_2d(s)
        if s.shape[0] == 1:
            s = np.vstack([s[0] * min(1, 1 - pan), s[0] * min(1, 1 + pan)])
        j = min(i + s.shape[1], n)
        if j > i:
            mix[:, i:j] += s[:, :j - i] * g
            send[i:j] += s.mean(axis=0)[:j - i] * g * wet

    def boing(f0, dur=0.35):
        m = int(dur * SR)
        t = tt(m)
        f = f0 * (1 + 0.6 * np.exp(-t / 0.05)) * (1 + 0.04 * np.sin(2 * np.pi * 14 * t))
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.12) * 0.55

    def plop(dur=0.12):
        m = int(dur * SR)
        t = tt(m)
        f = 300 + 900 * (t / dur)
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / dur) * 0.5

    def scribble(dur):
        m = int(dur * SR)
        t = tt(m)
        x = sfx.filt(rng.normal(0, 1, m), "bandpass", [2500, 8000])
        env = (0.5 + 0.5 * np.abs(np.sin(2 * np.pi * 9 * t))) * np.minimum(t / 0.01, 1) * np.clip((dur - t) / 0.02, 0, 1)
        return x * env * 0.18

    def squeak(dur=0.16, up=True):
        m = int(dur * SR)
        t = tt(m)
        f = (900 + 700 * (t / dur if up else 1 - t / dur)) * (1 + 0.03 * np.sin(2 * np.pi * 40 * t))
        return np.tanh(2 * np.sin(2 * np.pi * np.cumsum(f) / SR)) * np.sin(np.pi * t / dur) * 0.3

    for k, t0 in enumerate(WORD_T):   # words fall, land with a rubbery boing, get pumped up
        add(sfx.whoosh(0.22) * 0.5, t0, 0.6, (-0.4, -0.1, 0.1, 0.4)[k])
        add(boing((196, 247, 294, 392)[k]), t0 + 0.22, 1.0, (-0.4, -0.1, 0.1, 0.4)[k], wet=0.25)
        add(plop(), t0 + 0.26, 0.6, wet=0.2)
    add(sfx.whoosh(0.45), PHOTO_T, 0.7, 0.2)
    for k, (name, (_, _, t0, *_)) in enumerate(PROPS.items()):
        add(plop(0.14), t0, 0.9, (-0.5, 0.5, -0.4)[k], wet=0.3)
        add(boing((523, 659, 440)[k], 0.25), t0 + 0.05, 0.5, (-0.5, 0.5, -0.4)[k], wet=0.3)
    add(sfx.kick(2.4), PHOTO_T + 0.45, 0.9)
    add(sfx.crash(1.0), PHOTO_T + 0.45, 0.35, wet=0.3)
    for t0, dur, *_ in DOODLES:
        add(scribble(dur), t0, 0.9, -0.3 if t0 % 0.3 < 0.15 else 0.3)
    # groove: 100 BPM, kick / snap / hats / round bass / plucks
    K, S = sfx.kick(2.0), sfx.snap(0.25)
    F2, AB2, BB2, C3 = 87.31, 103.83, 116.54, 130.81
    roots = [F2, F2, AB2, BB2]
    beats = int((LENGTH - G0) / BEAT) + 1
    for b in range(beats):
        tb = G0 + b * BEAT
        if tb >= LENGTH - 0.3:
            break
        add(K, tb, 0.6)
        if b % 2 == 1:
            add(S, tb, 0.7, wet=0.3)
        add(sfx.hat(), tb + BEAT / 2, 0.6, 0.3)
        add(sfx.hat(), tb + BEAT / 4 * 3, 0.35, -0.3)
        root = roots[(b // 2) % 4]
        add(sfx.bass808(root, BEAT * 0.9), tb, 0.55)
        if b % 2 == 0:
            add(boing(root * 4, 0.25) * 0.5, tb + BEAT * 0.5, 0.5, 0.35, wet=0.3)
    add(squeak(0.12, up=False), POKE - 0.12, 0.9, 0.3)
    add(squeak(0.18, up=True), POKE, 1.0, 0.3, wet=0.3)
    add(plop(0.16), POKE + 0.05, 0.8, 0.3)
    add(sfx.kick(2.8), HIT, 1.0)
    add(sfx.crash(1.8), HIT, 0.6, wet=0.4)
    for k in range(4):
        add(boing((392, 494, 587, 784)[k], 0.3), HIT + 0.04 * k, 0.6, (-0.4, -0.1, 0.1, 0.4)[k], wet=0.3)
    wet = np.vstack([sfx.reverb(send, seed=1), sfx.reverb(send, seed=2)]) * 0.4
    out = np.tanh((mix + wet) * 0.8) / 0.8
    end = int(LENGTH * SR)
    out = out[:, :end] * np.clip((end - np.arange(end)) / (0.4 * SR), 0, 1)
    out *= 0.89 / (np.abs(out).max() + 1e-9)
    sfx.write(path, out)


def mux(video, audio, out, target=-14.0):
    import json

    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", audio, "-af", "loudnorm=print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True)
    gain = target - float(json.loads(r.stderr[r.stderr.rindex("{"):])["input_i"])
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-i", audio, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    "-af", f"volume={gain:.2f}dB,alimiter=limit=0.6:attack=1:release=50:level=false",
                    "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-movflags", "+faststart", "-shortest", out], check=True)
    return gain


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="puffy.mp4")
    ap.add_argument("--preview")
    ap.add_argument("--still", type=float)
    ap.add_argument("--layers", help="directory: write transparent PNG layers of the final frame (for Canva)")
    args = ap.parse_args()
    A = Assets()
    if args.layers:
        os.makedirs(args.layers, exist_ok=True)
        layers = {}
        f = N - 1
        cv2.imwrite(os.path.join(args.layers, "LMSN_puffy_poster.png"), render(A, f, layers))
        for k, v in layers.items():
            cv2.imwrite(os.path.join(args.layers, f"layer_{k}.png"), np.clip(v, 0, 255).astype(np.uint8))
        print("Saved layers", sorted(layers))
        return
    if args.still is not None:
        cv2.imwrite(args.out, render(A, round(args.still * FPS)))
        print(f"Saved {args.out}")
        return
    if args.preview:
        tiles = []
        for p in (float(x) for x in args.preview.split(",")):
            f = round(p * FPS)
            img = cv2.resize(render(A, f), (W // 4, H // 4), interpolation=cv2.INTER_AREA)
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
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "17",
                            "-pix_fmt", "yuv420p", "-movflags", "+faststart", vid], stdin=subprocess.PIPE)
    for f in range(N):
        enc.stdin.write(render(A, f).tobytes())
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
