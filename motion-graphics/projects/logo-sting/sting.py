#!/usr/bin/env python3
"""LET'S MAKE SOME NOISE - 4 s logo sting (bumper / end tag), built with MOTION_PRINCIPLES.md.

  python3 motion-graphics/projects/logo-sting/sting.py --out sting_16x9.mp4
  python3 motion-graphics/projects/logo-sting/sting.py --size reel --out sting_9x16.mp4
  python3 motion-graphics/projects/logo-sting/sting.py --preview 0.4,0.75,1.0,1.4,2.5 --out sheet.png

Idea ("the underline is the character"): the logo's own hand-drawn underline zips in on an arc, lands
with a squash, dips (anticipation) and springs the four words up out of itself one after another
(3-frame overlap). "noise" gets one extra kick, then the logo holds clean for 2.3 s with one small
secondary wiggle and one 2-frame glitch tick. Only the logo's own pieces are used (no fan art).

Needs ../show-intro/assets/logo-hires.png (git-ignored). Sound is synthesised here.
"""
import argparse
import math
import os
import subprocess
import sys

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SHOW = os.path.join(HERE, "..", "show-intro")
sys.path.insert(0, SHOW)
import intro as base  # noqa: E402  (draw, Layer, glitch helpers, logo cut points)
import sound as sfx  # noqa: E402  (synth building blocks)

FPS = 30
LENGTH = 4.0
N = int(LENGTH * FPS)
BOIL = 8  # hand-made boil rate (the school's cartoon stylization steps at 5 fps)

# ---------------------------------------------------------------- timing (frames)
F_FLY = (6, 21)            # underline flies in on an arc
F_LAND = 21                # touch-down: 3-frame squash
F_DIP = (24, 27)           # anticipation: the line dips before it throws the words
F_WORDS = [27, 30, 33, 36]  # Let's / make / some / noise pop up, 3-frame overlap
F_KICK = 48                # "noise" extra kick
F_WIGGLE = (76, 86)        # secondary action during the hold
F_TICK = (106, 108)        # 2-frame glitch tick (the brand is never fully under control)


def t2f(t):
    return t * FPS


def spring(u, freq=2.6, damp=7.0):
    """0 -> 1 with overshoot. u in seconds since start."""
    if u <= 0:
        return 0.0
    return 1 - math.exp(-damp * u) * math.cos(2 * math.pi * freq * u)


# ---------------------------------------------------------------- assets
class Assets:
    def __init__(self, W, H):
        im = cv2.imread(base.LOGO_PATH, cv2.IMREAD_UNCHANGED)
        if im is None:
            sys.exit(f"missing {base.LOGO_PATH}: extract the logo first (see show-intro/TREATMENT.md)")
        a = im[:, :, 3].astype(np.float32) / 255
        self.lw, self.lh = a.shape[1], a.shape[0]
        self.scale = W * 0.7 / self.lw if W > H else W * 0.86 / self.lw  # keep the action inside a marked area
        white = lambda arr: base.Layer(np.broadcast_to(np.array(base.WHITE, np.float32), arr.shape + (3,)).copy(), arr)
        ux0, ux1, uy0, uy1 = base.UNDERLINE
        ul = a[uy0:uy1, ux0:ux1].copy()
        self.underline = white(np.pad(ul, 10))
        # a bolder "pen" version for the flight; it thins back to the real underline on landing
        bold = cv2.dilate(np.pad(ul, 10), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13)))
        self.underline_bold = white(cv2.GaussianBlur(bold, (0, 0), 1.0))
        self.ul_center = ((ux0 + ux1) / 2, (uy0 + uy1) / 2)  # in logo px
        self.ul_top = uy0
        text = a[base.TEXT_ROWS[0]:base.TEXT_ROWS[1]]
        self.words = []
        cuts = base.WORD_CUTS
        for i in range(4):
            x0, x1 = cuts[i], cuts[i + 1]
            crop = text[:, x0:x1].copy()
            n, lab, st, _ = cv2.connectedComponentsWithStats((crop > 0.15).astype(np.uint8), 8)
            for j in range(1, n):
                x, _, w_, _, _ = st[j]
                if (x == 0 or x + w_ >= crop.shape[1]) and w_ < 30:
                    crop[lab == j] = 0
            cx = (x0 + x1) / 2
            cy = (base.TEXT_ROWS[0] + base.TEXT_ROWS[1]) / 2
            self.words.append((white(np.pad(crop, 8)), cx, cy))
        r = np.random.default_rng(3)
        self.grain = [cv2.GaussianBlur(r.normal(0, 7.0, (H, W)).astype(np.float32), (0, 0), 0.8) for _ in range(6)]
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        rr = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2) / math.sqrt(2)
        self.vignette = (1.0 - 0.4 * np.clip((rr - 0.35) / 0.65, 0, 1) ** 1.4).astype(np.float32)[:, :, None]

    def to_screen(self, lx, ly, W, H):
        """Logo pixel -> screen position (logo centred)."""
        return W / 2 + (lx - self.lw / 2) * self.scale, H / 2 + (ly - self.lh / 2) * self.scale


# ---------------------------------------------------------------- picture
def underline_state(f, A, W, H):
    """Position, rotation, stretch (sx, sy) of the underline at frame f."""
    hx, hy = A.to_screen(*A.ul_center, W, H)
    if f < F_FLY[0]:
        return None
    if f < F_FLY[1]:
        p = (f - F_FLY[0]) / (F_FLY[1] - F_FLY[0])
        e = base.ease_in_out(p) * 0.85 + p * 0.15  # never fully stops mid-flight
        # arc from off-screen top-left, dipping below, landing at home
        sx0, sy0 = -0.25 * W, H * 0.15
        cx, cy = W * 0.35, H * 1.05                 # control point of the quadratic arc
        x = (1 - e) ** 2 * sx0 + 2 * (1 - e) * e * cx + e ** 2 * hx
        y = (1 - e) ** 2 * sy0 + 2 * (1 - e) * e * cy + e ** 2 * hy
        dx = 2 * (1 - e) * (cx - sx0) + 2 * e * (hx - cx)
        dy = 2 * (1 - e) * (cy - sy0) + 2 * e * (hy - cy)
        rot = -math.degrees(math.atan2(dy, dx)) * (1 - e ** 3)  # auto-orient, settling to flat
        speed = math.sin(math.pi * p)
        grow = math.exp(math.log(2.4) * (1 - base.ease_out(p)))  # big while it travels, exponential shrink to size
        return x, y, rot, (1 + 0.9 * speed) * grow, (1 - 0.35 * speed) * grow  # smear along the motion
    sx, sy, dy = 1.0, 1.0, 0.0
    if F_LAND <= f < F_LAND + 3:                      # squash on landing
        k = 1 - (f - F_LAND) / 3
        sx, sy = 1 + 0.18 * k, 1 - 0.45 * k
    elif F_DIP[0] <= f < F_DIP[1]:                    # anticipation dip
        k = math.sin(math.pi * (f - F_DIP[0]) / (F_DIP[1] - F_DIP[0]))
        dy, sy = 26 * k * A.scale, 1 - 0.4 * k
    elif F_DIP[1] <= f < F_DIP[1] + 4:                # release: stretch up
        k = 1 - (f - F_DIP[1]) / 4
        sy, sx = 1 + 0.3 * k, 1 - 0.06 * k
    elif F_WIGGLE[0] <= f < F_WIGGLE[1]:              # secondary action in the hold
        u = (f - F_WIGGLE[0]) / (F_WIGGLE[1] - F_WIGGLE[0])
        return hx, hy, 4 * math.sin(u * math.pi * 3) * (1 - u), 1.0, 1.0
    return hx, hy + dy, 0.0, sx, sy


def draw_stretched(c, sp, x, y, rot, sx, sy, scale, alpha=1.0):
    """draw() with independent x/y stretch along the sprite's own axes."""
    M = cv2.getRotationMatrix2D((sp.w / 2, sp.h / 2), rot, 1.0)
    S = np.array([[sx * scale, 0], [0, sy * scale]], np.float32)
    R = M[:, :2]
    A2 = R @ S
    M2 = np.zeros((2, 3), np.float32)
    M2[:, :2] = A2
    M2[:, 2] = [x, y] - A2 @ np.array([sp.w / 2, sp.h / 2], np.float32)
    H, W = c.shape[:2]
    a = cv2.warpAffine(sp.a, M2, (W, H), flags=cv2.INTER_LINEAR)[:, :, None] * alpha
    rgb = cv2.warpAffine(sp.rgb, M2, (W, H), flags=cv2.INTER_LINEAR)
    c *= 1 - a
    c += rgb * a


def burst_lines(c, x, y, f0, f, scale, color=base.WHITE):
    """Three short dashes popping out (thickness taken from the logo's outline weight)."""
    u = (f - f0) / 9
    if not 0 <= u < 1:
        return
    th = max(int(7 * scale), 2)
    for ang, ln in ((-35, 1.0), (-10, 1.25), (15, 1.0)):
        a = math.radians(ang)
        r0 = (40 + 120 * base.ease_out(u)) * scale
        r1 = r0 + 70 * ln * scale * (1 - u)
        p0 = (int(x + math.cos(a) * r0), int(y + math.sin(a) * r0))
        p1 = (int(x + math.cos(a) * r1), int(y + math.sin(a) * r1))
        cv2.line(c, p0, p1, color, th, cv2.LINE_AA)


def render(A, f, W, H):
    c = np.zeros((H, W, 3), np.float32)
    s = A.scale
    clip_y = A.to_screen(0, A.ul_top, W, H)[1]
    # words pop out of the line (masked above the underline while rising)
    for k, (sp, lx, ly) in enumerate(A.words):
        f0 = F_WORDS[k]
        if f < f0:
            continue
        u = (f - f0) / FPS
        p = spring(u, freq=2.4, damp=7.5)
        tx, ty = A.to_screen(lx, ly, W, H)
        rise = (1 - p) * 120 * s                   # comes up from behind the line, overshoots, settles
        rot = (1 - p) * (-14 if k % 2 else 12)    # arcs: a little rotation that settles
        sc = s * (0.55 + 0.45 * min(p, 1.25))
        sy_ = 1 + 0.35 * max(0.0, 1 - u / 0.12) if u < 0.12 else 1.0  # stretch while launching
        jx = jy = 0.0
        if k == 3 and F_KICK <= f < F_KICK + 8:   # extra kick on "noise"
            e = 1 - (f - F_KICK) / 8
            r = base.frame_rng(f, "kick")
            jx, jy = r.normal(0, 9 * e * s, 2)
            sc *= 1 + 0.1 * e
        layer = np.zeros_like(c)
        draw_stretched(layer, sp, tx + jx, ty + rise + jy, rot, 1.0, sy_, sc)
        if u < 0.5:
            layer[int(clip_y):] = 0
        np.maximum(c, layer, out=c)
    burst_lines(c, *A.to_screen(A.words[3][1] + 210, A.words[3][2] - 60, W, H), F_KICK, f, s)
    # the underline (with echo trails while flying)
    st = underline_state(f, A, W, H)
    if st:
        flying = F_FLY[0] <= f < F_FLY[1]
        if flying:
            for g, al in ((3, 0.12), (2, 0.22), (1, 0.4)):
                pst = underline_state(f - g * 0.5, A, W, H)
                if pst:
                    draw_stretched(c, A.underline_bold, pst[0], pst[1], pst[2], pst[3], pst[4], s, al)
        bold = 1.0 if flying else max(0.0, 1 - (f - F_LAND) / 4)  # bold pen thins to the real line
        if bold > 0:
            draw_stretched(c, A.underline_bold, st[0], st[1], st[2], st[3], st[4], s, bold)
        draw_stretched(c, A.underline, st[0], st[1], st[2], st[3], st[4], s, 1 - bold)
    # faint boil on the finished logo (8 fps)
    if f >= F_WORDS[-1] + 12:
        lx0, ly0 = A.to_screen(A.lw / 2, A.lh / 2, W, H)
        trace_layer = np.zeros_like(c)
        t_boil = math.floor(f * BOIL / FPS) / base.BOIL  # base.trace re-jitters per base.BOIL step -> 8 fps
        base.trace(trace_layer, LogoContours.get(), t_boil, lx0, ly0, s, 0, progress=1,
                   thick=2, amp=2.2, alpha=0.2, key="sting")
        np.maximum(c, trace_layer, out=c)
    return c


class LogoContours:
    """Contours of the lettering for base.trace(), built once."""
    _a = None

    @classmethod
    def get(cls):
        if cls._a is None:
            im = cv2.imread(base.LOGO_PATH, cv2.IMREAD_UNCHANGED)
            a = im[:, :, 3].astype(np.float32) / 255
            ux0, ux1, uy0, uy1 = base.UNDERLINE
            a[uy0:uy1] = 0
            cs, _ = cv2.findContours((a > 0.5).astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
            obj = type("C", (), {})()
            obj.contours = []
            for cnt in cs:
                if len(cnt) < 24:
                    continue
                p = cv2.approxPolyDP(cnt, 1.2, True)[:, 0, :].astype(np.float32)
                obj.contours.append(np.vstack([p, p[:1]]) - [a.shape[1] / 2, a.shape[0] / 2])
            obj.contour_len = [float(np.linalg.norm(np.diff(x, axis=0), axis=1).sum()) for x in obj.contours]
            cls._a = obj
        return cls._a


def post(c, A, f, W, H):
    if F_TICK[0] <= f < F_TICK[1]:
        r = base.frame_rng(f, "tick")
        for _ in range(7):
            y0, h = int(r.integers(0, H - 30)), int(r.integers(6, 28))
            c[y0:y0 + h] = np.roll(c[y0:y0 + h], int(r.integers(-60, 60)), axis=1)
        b, g, r_ = cv2.split(c)
        c = cv2.merge([np.roll(b, -8, axis=1), g, np.roll(r_, 8, axis=1)])
    if F_KICK <= f < F_KICK + 2:
        c = c * 1.3  # punch the whites only; black stays black
    bloom = cv2.GaussianBlur(cv2.resize(np.clip(c - 170, 0, 255), (W // 4, H // 4)), (0, 0), 6)
    c = c + cv2.resize(bloom, (W, H)) * 0.4
    c = c * A.vignette + A.grain[(f // 2) % len(A.grain)][:, :, None]
    return np.clip(c, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- sound
def bloop(freq):
    n = int(0.22 * sfx.SR)
    t = sfx.tt(n)
    f = freq * (1 + 0.9 * np.exp(-t / 0.018))
    x = np.sin(2 * np.pi * np.cumsum(f) / sfx.SR) * np.exp(-t / 0.07)
    click = sfx.filt(np.random.default_rng(int(freq)).normal(0, 1, n) * np.exp(-t / 0.002), "highpass", 2000) * 0.3
    return (x + click) * 0.6


def build_sound(path):
    SR = sfx.SR
    n = int((LENGTH + 0.3) * SR)
    mix = np.zeros((2, n))
    send = np.zeros(n)

    def add(s, t, g=1.0, pan=0.0, wet=0.0):
        i = int(t * SR)
        s = np.atleast_2d(s)
        if s.shape[0] == 1:
            s = np.vstack([s[0] * min(1, 1 - pan), s[0] * min(1, 1 + pan)])
        j = min(i + s.shape[1], n)
        mix[:, i:j] += s[:, :j - i] * g
        send[i:j] += s.mean(axis=0)[:j - i] * g * wet

    fly0, fly1 = F_FLY[0] / FPS, F_FLY[1] / FPS
    wh = sfx.whoosh(fly1 - fly0 + 0.05)
    pan = np.linspace(-0.8, 0.1, wh.size)
    add(np.vstack([wh * np.clip(1 - pan, 0, 1), wh * np.clip(1 + pan, 0, 1)]), fly0, 0.7)
    add(sfx.snap(0.12), F_LAND / FPS, 0.6, wet=0.2)
    add(sfx.sub_drop(90, 50, 0.25), F_LAND / FPS, 0.4)
    for k, (f0, fr) in enumerate(zip(F_WORDS, (523.3, 622.3, 698.5, 830.6))):
        add(bloop(fr), f0 / FPS, 0.9, pan=(-0.45, -0.15, 0.15, 0.45)[k], wet=0.25)
    t = F_KICK / FPS
    add(sfx.kick(2.6), t, 0.8)
    add(sfx.snap(0.3), t, 1.0, wet=0.4)
    add(sfx.clang(240, 0.9), t, 0.8, wet=0.5)
    add(sfx.crash(1.6), t, 0.5, wet=0.3)
    add(sfx.sub_drop(70, 30, 1.2), t, 0.5)
    w0 = F_WIGGLE[0] / FPS
    add(bloop(1046.5) * 0.4, w0, 0.6, wet=0.3)
    add(sfx.bitcrush(np.random.default_rng(2).normal(0, 1, int(0.07 * SR)), 3, 12) * 0.3, F_TICK[0] / FPS)
    add(sfx.drone(LENGTH - t + 0.2) * 0.6, t, 0.7)
    wet = np.vstack([sfx.reverb(send, seed=1), sfx.reverb(send, seed=2)]) * 0.5
    out = mix + wet
    out = np.tanh(out * 0.7) / 0.7
    end = int(LENGTH * SR)
    out = out[:, :end] * np.clip((end - np.arange(end)) / (0.2 * SR), 0, 1)
    out *= 0.89 / (np.abs(out).max() + 1e-9)
    sfx.write(path, out)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="sting.mp4")
    ap.add_argument("--size", default="hd", help="hd (1920x1080) or reel (1080x1920)")
    ap.add_argument("--preview")
    args = ap.parse_args()
    W, H = (1920, 1080) if args.size == "hd" else (1080, 1920)
    base.W, base.H = W, H  # base helpers clip to these
    A = Assets(W, H)

    if args.preview:
        tiles = []
        for p in (float(x) for x in args.preview.split(",")):
            f = round(p * FPS)
            img = post(render(A, f, W, H), A, f, W, H)
            img = cv2.resize(img, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
            cv2.putText(img, f"{p:.2f}s f{f}", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            tiles.append(img)
        cols = 5 if W > H else 8
        while len(tiles) % cols:
            tiles.append(np.zeros_like(tiles[0]))
        cv2.imwrite(args.out, np.vstack([np.hstack(tiles[r:r + cols]) for r in range(0, len(tiles), cols)]))
        print(f"Saved preview {args.out}")
        return

    wav = os.path.splitext(args.out)[0] + ".wav"
    build_sound(wav)
    vid = args.out + ".video.mp4"
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "16",
                            "-pix_fmt", "yuv420p", "-tune", "grain", "-movflags", "+faststart", vid], stdin=subprocess.PIPE)
    for f in range(N):
        enc.stdin.write(post(render(A, f, W, H), A, f, W, H).tobytes())
    enc.stdin.close()
    if enc.wait() != 0:
        sys.exit("ffmpeg failed")
    gain = base.mux(vid, wav, args.out)
    os.remove(vid)
    print(f"Saved {args.out} ({N} frames, {LENGTH}s, {W}x{H}, audio {gain:+.1f} dB to -14 LUFS)")


if __name__ == "__main__":
    main()
