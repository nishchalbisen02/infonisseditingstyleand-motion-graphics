#!/usr/bin/env python3
"""Sound design for the LET'S MAKE SOME NOISE show intro, synthesised from scratch (no samples, no licences).

  python3 motion-graphics/projects/show-intro/sound.py [build_dir]

Writes build/mix.wav plus dry stems build/sfx.wav and build/music.wav (48 kHz, 32-bit) on the hit map
in timeline.py:
  0.0   room tone, mains hum, vinyl dust
  0.8   mic taps, speeding up                       2.0  feedback starts to howl and climb
  2.8   one metallic hit per word, "noise" biggest   4.2  beat-repeat stutter, faster and faster
  4.75  a breath                                     4.8  drop: distorted half-time groove, 808 sliding a b2
  7.2   implosion: tape stop + reverse cymbal        7.6  dead silence
  7.8   reveal: sub boom, crash, shimmer, smoke whoosh panned L->R, crowd-like applause swell, drone tail
"""
import os
import sys

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, fftconvolve, sosfilt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from timeline import (BEAT, DROP, FEEDBACK, GAP1, GLITCH_TICKS, IMPLODE, LENGTH, REVEAL, SILENCE,  # noqa: E402
                      STUTTER, TAPS, WORDS)

SR = 48000
STEP = BEAT / 4
RNG = np.random.default_rng(7)
N = int((LENGTH + 0.5) * SR)


def tt(n):
    return np.arange(n) / SR


def filt(x, kind, f, order=2):
    return sosfilt(butter(order, f, btype=kind, fs=SR, output="sos"), x)


def sweep_filter(x, kind, f0, f1, curve=1.0, block=512):
    """Time-varying filter: cutoff moves f0 -> f1 across the sound."""
    out = np.empty_like(x)
    zi = None
    n = x.size
    for i in range(0, n, block):
        p = (i / n) ** curve
        f = f0 * (f1 / f0) ** p
        if kind == "bandpass":
            f = [f, min(f * 2.2, SR / 2 - 100)]
        sos = butter(2, f, btype=kind, fs=SR, output="sos")
        if zi is None:
            zi = np.zeros((sos.shape[0], 2))
        out[i:i + block], zi = sosfilt(sos, x[i:i + block], zi=zi)
    return out


# ---------------------------------------------------------------- sources
def room_tone(n):
    pink = filt(RNG.normal(0, 1, n), "lowpass", 2500) * 0.012
    hum = (np.sin(2 * np.pi * 50 * tt(n)) + 0.4 * np.sin(2 * np.pi * 150 * tt(n))) * 0.006
    return pink, hum


def crackle(n, rate=18):
    x = np.zeros(n)
    idx = RNG.integers(0, n, int(n / SR * rate))
    x[idx] = RNG.uniform(-1, 1, idx.size) * RNG.uniform(0.2, 1, idx.size)
    return filt(x, "bandpass", [900, 7000]) * 0.5


def mic_tap(gain=1.0):
    n = int(0.45 * SR)
    t = tt(n)
    thump = np.sin(2 * np.pi * np.cumsum(60 + 50 * np.exp(-t / 0.02)) / SR) * np.exp(-t / 0.09)
    click = filt(RNG.normal(0, 1, n) * np.exp(-t / 0.007), "bandpass", [400, 3500]) * 2.2  # the mic body knock
    boom = np.sin(2 * np.pi * 38 * t) * np.exp(-t / 0.2) * 0.5
    return np.tanh(1.4 * (thump + click + boom)) * 0.7 * gain


def feedback(dur):
    n = int(dur * SR)
    t = tt(n)
    p = t / dur
    f = 2300 * (1.8 ** (p ** 1.6))
    vib = 1 + (0.004 + 0.02 * p ** 2) * np.sin(2 * np.pi * (5 + 3 * p) * t)
    ph = 2 * np.pi * np.cumsum(f * vib) / SR
    x = np.sin(ph) + 0.35 * np.sin(2 * ph + 0.5) + 0.15 * np.sin(0.5 * ph)
    env = (p ** 2.2) * np.clip((dur - t) / 0.004, 0, 1)
    return np.tanh(2.5 * x * env) * 0.5


def kick(drive=2.0):
    n = int(0.5 * SR)
    t = tt(n)
    f = 44 + 130 * np.exp(-t / 0.03)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.24)
    click = RNG.normal(0, 1, n) * np.exp(-t / 0.003) * 0.4
    return np.tanh(drive * (body + click)) * 0.9


def snap(dur=0.25):
    n = int(dur * SR)
    t = tt(n)
    x = filt(RNG.normal(0, 1, n), "bandpass", [1100, 6500]) * np.exp(-t / 0.045)
    body = np.sin(2 * np.pi * 200 * t) * np.exp(-t / 0.04) * 0.6
    return np.tanh(2.5 * (x * 1.3 + body)) * 0.75


def clang(f=210, dur=1.0, index=6):
    """FM metal hit."""
    n = int(dur * SR)
    t = tt(n)
    mod = np.sin(2 * np.pi * f * 1.414 * t) * index * np.exp(-t / 0.12)
    x = np.sin(2 * np.pi * f * t + mod) * np.exp(-t / 0.35)
    return x * 0.5


def sub_drop(f0=70, f1=32, dur=0.8):
    n = int(dur * SR)
    t = tt(n)
    f = f1 + (f0 - f1) * np.exp(-t / 0.15)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / (dur * 0.5)) * 0.8


def crash(dur=1.6):
    n = int(dur * SR)
    t = tt(n)
    return filt(RNG.normal(0, 1, n), "highpass", 3000) * np.exp(-t / (dur * 0.35)) * 0.35


def riser(dur):
    n = int(dur * SR)
    t = tt(n)
    x = sweep_filter(RNG.normal(0, 1, n), "bandpass", 250, 7000, 1.3)
    tone = np.sin(2 * np.pi * np.cumsum(110 * 8 ** ((t / dur) ** 1.3)) / SR) * 0.25
    return (x * 1.5 + tone) * (t / dur) ** 2.4


def hat(open_=False):
    n = int((0.15 if open_ else 0.04) * SR)
    t = tt(n)
    return filt(RNG.normal(0, 1, n), "highpass", 7500, 4) * np.exp(-t / (0.07 if open_ else 0.014)) * 0.35


def bass808(f, dur, slide_to=None):
    n = int(dur * SR)
    t = tt(n)
    ff = f * (1 + 0.7 * np.exp(-t / 0.02))
    if slide_to:
        ff = ff + (slide_to - f) * np.clip((t - dur * 0.4) / (dur * 0.3), 0, 1)
    x = np.sin(2 * np.pi * np.cumsum(ff) / SR)
    env = np.minimum(t / 0.003, 1) * (0.4 + 0.6 * np.exp(-t / 0.35)) * np.clip((dur - t) / 0.02, 0, 1)
    main = np.tanh(2.6 * x * env) * 0.26
    grit = filt(np.tanh(8 * x * env), "bandpass", [200, 1800]) * 0.3
    return main + grit


def bitcrush(x, bits=4, hold=7):
    y = np.round(x * 2 ** bits) / 2 ** bits
    return np.repeat(y[::hold], hold)[: x.size]


def stab(freqs, dur=0.16):
    n = int(dur * SR)
    t = tt(n)
    x = sum(2 * ((t * f * 2 ** (c / 1200)) % 1) - 1 for f in freqs for c in (-12, 0, 12))
    x = filt(x / (3 * len(freqs)), "lowpass", 3000) * np.exp(-t / 0.06)
    return bitcrush(x) * 0.8


def growl(dur, f=87.31, wobble_hz=5.0):
    """Distorted detuned-saw mid growl with an 8th-note wobble (150 BPM)."""
    n = int(dur * SR)
    t = tt(n)
    x = sum(2 * ((t * f * m * 2 ** (c / 1200)) % 1) - 1 for m in (1, 2) for c in (-14, 0, 14))
    x = np.tanh(4 * x / 6)
    lfo = 0.5 + 0.5 * np.sin(2 * np.pi * wobble_hz * t - np.pi / 2)
    lo = filt(x, "bandpass", [250, 900])
    hi = filt(x, "bandpass", [900, 2600])
    y = lo * (1 - lfo) + hi * lfo
    env = np.minimum(t / 0.01, 1) * np.clip((dur - t) / 0.05, 0, 1)
    return y * env * 0.5


def whoosh(dur, up=True):
    n = int(dur * SR)
    t = tt(n)
    x = sweep_filter(RNG.normal(0, 1, n), "bandpass", 400 if up else 6000, 6000 if up else 300, 1.0)
    return x * np.sin(np.pi * t / dur) ** 2 * 1.6


def reverse_cymbal(dur):
    c = crash(dur * 1.2)[: int(dur * SR)]
    return c[::-1] * 1.6


def applause(dur, density=2500):
    """Crowd-like applause: thousands of tiny filtered hand-claps, returned as stereo."""
    n = int(dur * SR)
    t = tt(n)
    env = np.minimum(t / 0.25, 1) * np.exp(-np.maximum(t - 0.4, 0) / 1.0)
    out = np.zeros((2, n))
    k = int(0.004 * SR)
    kernel = RNG.normal(0, 1, k) * np.exp(-np.arange(k) / (0.0012 * SR))
    for ch in range(2):
        rate = density * env / SR
        hits = (RNG.random(n) < rate) * RNG.uniform(0.3, 1, n)
        x = fftconvolve(hits, kernel)[:n]
        out[ch] = filt(x, "bandpass", [700, 6000]) * 0.5
    roar = filt(RNG.normal(0, 1, n), "bandpass", [250, 2200]) * env * (0.7 + 0.3 * np.sin(2 * np.pi * 0.7 * t)) * 0.08
    return out + roar


def drone(dur):
    n = int(dur * SR)
    t = tt(n)
    x = sum(a * np.sin(2 * np.pi * f * t) for f, a in ((43.65, 0.5), (65.41, 0.3), (87.31, 0.25), (130.8, 0.1)))
    saw = filt(2 * ((t * 87.31) % 1) - 1, "lowpass", 600) * 0.15
    env = np.minimum(t / 0.6, 1) * np.clip((dur - t) / 1.5, 0, 1)
    return (x + saw) * env * 0.35


def reverb(x, seconds=2.6, decay=0.6, seed=1):
    r = np.random.default_rng(seed)
    t = tt(int(seconds * SR))
    ir = filt(r.normal(0, 1, t.size) * np.exp(-t / decay), "lowpass", 5500)
    ir /= np.sqrt(np.sum(ir ** 2))
    return fftconvolve(x, ir)[: x.size]


# ---------------------------------------------------------------- arrangement
class Bus:
    def __init__(self):
        self.m = np.zeros((2, N))

    def add(self, sound, at, gain=1.0, pan=0.0):
        """Mono or stereo sound at time `at` (s); pan -1 (L) .. 1 (R)."""
        i = int(round(at * SR))
        if i >= N:
            return
        s = np.atleast_2d(sound)
        if s.shape[0] == 1:
            s = np.vstack([s[0] * min(1, 1 - pan), s[0] * min(1, 1 + pan)])
        j = min(i + s.shape[1], N)
        self.m[:, i:j] += s[:, : j - i] * gain


def build():
    sfx, music, send = Bus(), Bus(), Bus()

    pink, hum = room_tone(N)
    sfx.add(pink, 0)
    sfx.add(hum * np.clip(1 - np.maximum(tt(N) - GAP1[0], 0) / 0.05, 0, 1), 0)
    sfx.add(crackle(N), 0, 0.6)

    for k, at in enumerate(TAPS):
        g = 0.55 + 0.45 * k / (len(TAPS) - 1)
        tap = mic_tap(g)
        sfx.add(tap, at)
        send.add(tap, at, 0.5)

    fb = feedback(FEEDBACK[1] - FEEDBACK[0])
    sfx.add(fb, FEEDBACK[0], 1.0)
    send.add(fb, FEEDBACK[0], 0.3)
    sfx.add(riser(GAP1[0] - WORDS[0][0]), WORDS[0][0], 0.45)

    for k, (at, word) in enumerate(WORDS):
        big = word == "noise"
        sfx.add(kick(2.6), at, 0.65)
        sfx.add(snap(), at, 1.1)
        sfx.add(sub_drop(80, 34, 1.0 if big else 0.5), at, 0.45)
        c = clang(180 + 40 * k, 1.2 if big else 0.7)
        sfx.add(c, at, 1.1)
        send.add(c, at, 0.6)
        if big:
            sfx.add(crash(1.8), at, 0.9)
            send.add(crash(1.8), at, 0.5)

    # drop: half-time, 150 BPM, 808 sliding up a b2, dissonant crushed stabs
    F1, GB1 = 87.31, 92.50
    K, S = kick(2.2), snap(0.3)
    bar0 = DROP[0]
    for bar in range(2):  # the second bar keeps going under the tape stop
        b0 = bar0 + bar * 16 * STEP
        for s in (0, 6, 10):
            music.add(K, b0 + s * STEP, 0.7)
        music.add(S, b0 + 8 * STEP, 1.2)
        send.add(S, b0 + 8 * STEP, 0.4)
        for s in range(16):
            music.add(hat(open_=s in (7, 15)), b0 + s * STEP, 0.9 if s % 2 == 0 else 0.6, pan=-0.3 if s % 4 == 1 else 0.3)
        music.add(bass808(F1, 6 * STEP), b0)
        music.add(bass808(F1, 4 * STEP, slide_to=GB1), b0 + 6 * STEP)
        music.add(bass808(GB1, 6 * STEP, slide_to=F1), b0 + 10 * STEP)
        for s in (3, 11, 14):
            music.add(stab([349.2, 370.0, 523.3]), b0 + s * STEP, 1.5, pan=-0.4 if s == 3 else 0.4)
    music.add(growl(2 * 16 * STEP), bar0, 1.0)
    for s in range(4, 8):  # fill into the implosion
        music.add(S, bar0 + 16 * STEP + s * STEP, 0.4 + 0.12 * (s - 4))
    sfx.add(crash(1.2), DROP[0], 0.6)
    sfx.add(sub_drop(70, 30, 1.0), DROP[0], 0.5)

    # implosion + reveal
    sfx.add(reverse_cymbal(IMPLODE[1] - IMPLODE[0]), IMPLODE[0], 0.7)
    sfx.add(whoosh(IMPLODE[1] - IMPLODE[0], up=False), IMPLODE[0], 0.6)
    sfx.add(sub_drop(60, 24, 2.8), REVEAL, 0.65)
    sfx.add(kick(3.0), REVEAL, 0.75)
    sfx.add(snap(0.4), REVEAL, 1.1)
    big_crash = crash(3.0)
    sfx.add(big_crash, REVEAL, 1.0)
    send.add(big_crash, REVEAL, 0.6)
    shimmer = clang(880, 2.4, 3) * 0.5 + clang(1320, 2.4, 2) * 0.3
    sfx.add(shimmer, REVEAL, 0.9)
    send.add(shimmer, REVEAL, 0.7)
    wh = whoosh(1.1)
    pan = np.linspace(-0.9, 0.9, wh.size)
    sfx.add(np.vstack([wh * np.clip(1 - pan, 0, 1), wh * np.clip(1 + pan, 0, 1)]), REVEAL - 0.05, 0.55)
    sfx.add(applause(LENGTH - REVEAL + 0.3), REVEAL + 0.15, 1.1)
    music.add(drone(LENGTH - REVEAL + 0.3), REVEAL, 0.8)
    for at in GLITCH_TICKS:
        sfx.add(bitcrush(RNG.normal(0, 1, int(0.06 * SR)), 3, 12) * 0.25, at)
    return sfx.m, music.m, send.m


def tape_stop(x, start, dur):
    """Slow the audio from `start` to a halt over `dur` seconds (pitch falls like a stopping deck)."""
    i0, n = int(start * SR), int(dur * SR)
    rate = (1 - np.linspace(0, 1, n)) ** 1.3
    pos = i0 + np.cumsum(rate)
    out = np.empty((x.shape[0], n))
    for ch in range(x.shape[0]):
        out[ch] = np.interp(pos, np.arange(x.shape[1]), x[ch])
    x[:, i0:i0 + n] = out * np.linspace(1, 0.2, n)
    x[:, i0 + n:] = 0
    return x


def stutter(x, src, start, end):
    """Beat-repeat: replay the slice at `src`, the repeats getting shorter."""
    t = start
    for length, count in ((0.1, 2), (0.05, 4), (0.025, 6)):
        for _ in range(count):
            if t >= end:
                break
            i, n = int(t * SR), int(length * SR)
            j = int(src * SR)
            x[:, i:i + n] = x[:, j:j + n] * np.linspace(1, 0.6, n)
            t += length
    return x


def master(sfx, music, send):
    music = tape_stop(music, IMPLODE[0], IMPLODE[1] - IMPLODE[0])
    wet = np.vstack([reverb(send[0], seed=1), reverb(send[1], seed=2)]) * 0.55
    mix = sfx + music + wet
    mix = stutter(mix, WORDS[3][0], STUTTER[0], STUTTER[1])
    for a, b in (GAP1, SILENCE):
        i, j = int(a * SR), int(b * SR)
        mix[:, i:j] *= 0
    mix = filt(mix, "highpass", 25)
    mix = np.tanh(mix * 0.6) / 0.6
    end = int(LENGTH * SR)
    fade = np.clip((end - np.arange(N)) / (0.25 * SR), 0, 1)
    mix = mix[:, :end] * fade[:end]
    peak = np.abs(mix).max() + 1e-9
    gain = 0.89 / peak
    return mix * gain, sfx[:, :end] * gain, music[:, :end] * gain


def write(path, x):
    wavfile.write(path, SR, (np.clip(x.T, -1, 1) * (2 ** 31 - 1)).astype(np.int32))


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "build")
    os.makedirs(out, exist_ok=True)
    sfx, music, send = build()
    mix, sfx_s, music_s = master(sfx, music, send)
    write(os.path.join(out, "mix.wav"), mix)
    write(os.path.join(out, "sfx.wav"), sfx_s)
    write(os.path.join(out, "music.wav"), music_s)
    print(f"Saved {out}/mix.wav, sfx.wav, music.wav ({mix.shape[1] / SR:.2f}s)")
