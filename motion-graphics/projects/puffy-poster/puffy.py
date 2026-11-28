"""Puffy 3D type and the 2D layers around it (shared by poster.py).

The owner's logo letterforms are inflated into soft pink clay with a height field:
distance transform -> pillow profile -> surface bumps -> normals -> diffuse + specular + AO,
plus a contact shadow. No 3D package needed; the inflation amount can be animated.
"""
import math
import os

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LOGO = os.path.join(HERE, "..", "show-intro", "assets", "logo-hires.png")
CUTS = [18, 353, 745, 1113, 1490]  # Let's | make | some | noise (in the 1506 px logo master)
TEXT_ROWS = (0, 198)

PINK = np.array((196, 140, 246), np.float32)      # BGR, bubblegum (reference is ~ (202,153,234))
PINK_DEEP = np.array((140, 70, 214), np.float32)
BLUE = np.array((122, 80, 44), np.float32)
BLUE_DARK = np.array((90, 52, 24), np.float32)
WHITE = (245, 245, 245)


def logo_words():
    """The four words of the logo as float alpha masks (holes closed so they inflate smoothly)."""
    a = cv2.imread(LOGO, cv2.IMREAD_UNCHANGED)
    if a is None:
        raise SystemExit(f"missing {LOGO}")
    a = a[TEXT_ROWS[0]:TEXT_ROWS[1], :, 3].astype(np.float32) / 255
    words = []
    for i in range(4):
        w = a[:, CUTS[i]:CUTS[i + 1]].copy()
        n, lab, st, _ = cv2.connectedComponentsWithStats((w > 0.15).astype(np.uint8), 8)
        for j in range(1, n):  # slivers of neighbouring letters
            x, _, ww, _, _ = st[j]
            if (x == 0 or x + ww >= w.shape[1]) and ww < 30:
                w[lab == j] = 0
        words.append(w)
    return words


def prep_mask(alpha, scale, close=7):
    """Scale up; return (silhouette, groove). The silhouette has small scratch holes closed so the
    word inflates as one pillow; the groove map keeps the logo's own inner lines as creases."""
    m0 = cv2.resize(alpha, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    m = (m0 > 0.45).astype(np.uint8)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close, close))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k)
    inv = 1 - m
    n, lab, st, _ = cv2.connectedComponentsWithStats(inv, 4)
    for j in range(1, n):  # fill small enclosed holes, keep counters (o, e, a)
        x, y, w, h, area = st[j]
        if area < 700 * scale * scale and x > 0 and y > 0 and x + w < m.shape[1] and y + h < m.shape[0]:
            m[lab == j] = 1
    sil = cv2.GaussianBlur(m.astype(np.float32), (0, 0), 1.2)
    groove = np.clip(sil - cv2.GaussianBlur(np.clip(m0, 0, 1), (0, 0), 1.0) * 1.15, 0, 1)
    groove = cv2.GaussianBlur(groove, (0, 0), 2.6)
    return np.pad(sil, 40), np.pad(groove, 40)


class Puffy:
    """A pre-computed inflated word: render(inflate) gives BGR + alpha for any inflation 0..1.2."""

    def __init__(self, mask, groove=None, color=PINK, deep=PINK_DEEP, seed=0, radius=None, bump=1.0):
        self.mask = mask.astype(np.float32)
        self.groove = np.zeros_like(self.mask) if groove is None else groove.astype(np.float32)
        inside = (mask > 0.5).astype(np.uint8)
        d = cv2.distanceTransform(inside, cv2.DIST_L2, 5)
        r = radius or max(float(np.percentile(d[inside > 0], 92)), 4.0)
        # soft pillow: blur the distance field so the medial-axis ridges melt into round tops
        ds = cv2.GaussianBlur(np.minimum(d, r * 1.2), (0, 0), r * 0.45)
        prof = np.clip(ds / (r * 0.85), 0, 1)
        self.profile = (1 - (1 - prof) ** 2.2) * cv2.GaussianBlur(self.mask, (0, 0), 1.0)
        self.profile *= 1 - 0.22 * np.clip(self.groove * 1.2, 0, 1)        # soft creases from the logo's lines
        rng = np.random.default_rng(seed)
        b1 = cv2.GaussianBlur(rng.normal(0, 1, mask.shape).astype(np.float32), (0, 0), 3.0)
        b2 = cv2.GaussianBlur(rng.normal(0, 1, mask.shape).astype(np.float32), (0, 0), 0.9)
        self.bump = (b1 * 0.05 + b2 * 0.012) * bump * inside                # foam / clay surface
        self.r = r
        self.color, self.deep = color, deep

    def render(self, inflate=1.0, light=(-0.35, -0.6, 0.72)):
        k = min(max(inflate, 0.0), 1.3)
        h = (self.profile * k + self.bump * min(k, 1.0)) * self.r * 1.4
        gy, gx = np.gradient(h)
        n = np.dstack([-gx, -gy, np.ones_like(h)])
        n /= np.linalg.norm(n, axis=2, keepdims=True)
        L = np.array(light, np.float32)
        L /= np.linalg.norm(L)
        diff = np.clip(n @ L, 0, 1)
        Hv = L + np.array([0, 0, 1], np.float32)
        Hv /= np.linalg.norm(Hv)
        spec = np.clip(n @ Hv, 0, 1) ** 22 * min(k, 1.0)
        rim = np.clip(1 - n[:, :, 2], 0, 1) ** 1.5                          # sides turn deeper pink
        ao = 0.7 + 0.3 * np.clip(self.profile * 2, 0, 1)
        col = self.color * (0.62 + 0.5 * diff[:, :, None]) * ao[:, :, None]
        col = col * (1 - rim[:, :, None] * 0.55) + self.deep * rim[:, :, None] * 0.55
        col = col + 255 * spec[:, :, None] * 0.35
        g = np.clip(self.groove * 1.4, 0, 1)[:, :, None]
        col = col * (1 - g * 0.16) + self.deep * 0.6 * g * 0.16              # creases read a little darker
        return np.clip(col, 0, 255), self.mask


def composite(c, rgb, a, x, y, scale=1.0, rot=0.0, shadow=True, shadow_offset=(14, 22), shadow_alpha=0.55):
    """Paste a layer centred at (x, y) with optional soft contact shadow."""
    H, W = c.shape[:2]
    M = cv2.getRotationMatrix2D((a.shape[1] / 2, a.shape[0] / 2), rot, scale)
    M[0, 2] += x - a.shape[1] / 2
    M[1, 2] += y - a.shape[0] / 2
    aw = cv2.warpAffine(a, M, (W, H), flags=cv2.INTER_LINEAR)
    if shadow:
        sh = cv2.GaussianBlur(aw, (0, 0), 10)
        sh = np.roll(np.roll(sh, shadow_offset[1], 0), shadow_offset[0], 1)
        c *= 1 - (sh * shadow_alpha)[:, :, None]
    rw = cv2.warpAffine(rgb, M, (W, H), flags=cv2.INTER_LINEAR)
    c[:] = c * (1 - aw[:, :, None]) + rw * aw[:, :, None]
    return aw


def blue_wall(W, H, seed=1):
    """Grungy blue wall / denim paper like the reference."""
    r = np.random.default_rng(seed)

    def noise(cell, sigma=0):
        g = r.normal(0, 1, (H // cell + 3, W // cell + 3)).astype(np.float32)
        n = cv2.resize(g, (W + cell * 3, H + cell * 3), interpolation=cv2.INTER_CUBIC)[:H, :W]
        return cv2.GaussianBlur(n, (0, 0), sigma) if sigma else n

    blot = noise(160) * 0.6 + noise(60) * 0.3
    fiber = cv2.blur(r.normal(0, 1, (H, W)).astype(np.float32), (1, 9)) * 0.5 + cv2.blur(
        r.normal(0, 1, (H, W)).astype(np.float32), (9, 1)) * 0.5
    grain = cv2.GaussianBlur(r.normal(0, 1, (H, W)).astype(np.float32), (0, 0), 0.7)
    t = np.clip(0.5 + blot * 0.35, 0, 1)[:, :, None]
    c = BLUE_DARK * (1 - t) + BLUE * t
    c = c * (1 + fiber[:, :, None] * 0.06 + grain[:, :, None] * 0.05)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    rr = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / math.sqrt(2)
    return c * (1 - 0.35 * np.clip((rr - 0.4) / 0.6, 0, 1) ** 1.4)[:, :, None]


def smoke(W, H, cx, cy, radius, t=0.0, seed=3, strength=0.5):
    """Soft white haze behind the type (like the cloud in the reference)."""
    r = np.random.default_rng(seed)
    g = r.normal(0, 1, (H // 90 + 4, W // 90 + 4)).astype(np.float32)
    n = cv2.resize(g, (W + 360, H + 360), interpolation=cv2.INTER_CUBIC)
    ox, oy = int(30 * t) % 180, int(18 * t) % 180
    n = n[oy:oy + H, ox:ox + W]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    m = np.exp(-(((xx - cx) / radius) ** 2 + ((yy - cy) / (radius * 0.7)) ** 2))
    return np.clip((n * 0.5 + 0.55) * m * strength, 0, 0.8)
