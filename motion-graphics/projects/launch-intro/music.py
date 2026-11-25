#!/usr/bin/env python3
"""Original background track for the launch intro, synthesised from scratch (no samples, no licence issues).

  python3 motion-graphics/projects/launch-intro/music.py out.wav

120 BPM, F minor, 8 bars = 16 s. Arrangement is locked to the video's beat grid (intro.py):
  bar 1  countdown: crackle + riser, three rising stamp hits, a gap before the drop
  bar 2  drop: kick / clap / hats, distorted 808, bitcrushed stabs
  bar 3  "LET'S MAKE SOME NOISE": one big hit per word, no hats
  bar 4  groove, then a snare roll into the collage
  bar 5-6 full groove; riser + roll at the end of bar 6
  bar 7  logo: huge impact, then a filtered half-time groove
  bar 8  groove, final impact on beat 31, tail to 16 s
"""
import sys

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, fftconvolve, sosfilt

SR = 48000
BPM = 120
BEAT = 60 / BPM
STEP = BEAT / 4  # 16th note
BARS = 8
LENGTH = BARS * 4 * BEAT
RNG = np.random.default_rng(42)

F2, DB2, AB2, EB2 = 87.31, 69.30, 103.83, 77.78
CHORDS = {
    "Fm": [349.23, 415.30, 523.25],
    "Db": [277.18, 349.23, 415.30],
    "Ab": [207.65, 261.63, 311.13],
    "Eb": [311.13, 392.00, 466.16],
}
BAR_HARMONY = [("Fm", F2), ("Fm", F2), ("Db", DB2), ("Ab", AB2), ("Eb", EB2), ("Fm", F2), ("Db", DB2), ("Fm", F2)]


def t_of(n):
    return np.arange(n) / SR


def filt(x, kind, freq, order=2):
    sos = butter(order, freq, btype=kind, fs=SR, output="sos")
    return sosfilt(sos, x)


def kick():
    t = t_of(int(0.5 * SR))
    f = 46 + 120 * np.exp(-t / 0.032)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.26)
    click = RNG.normal(0, 1, t.size) * np.exp(-t / 0.003) * 0.35
    return np.tanh(1.8 * (body + click)) * 0.95


def clap():
    n = int(0.35 * SR)
    t = t_of(n)
    noise = RNG.normal(0, 1, n)
    env = sum(np.where(t >= o, np.exp(-(t - o) / 0.006), 0) for o in (0, 0.011, 0.022))
    env = env + np.where(t >= 0.03, np.exp(-(t - 0.03) / 0.09), 0) * 0.7
    x = filt(noise * env, "bandpass", [850, 3400])
    body = np.sin(2 * np.pi * 185 * t) * np.exp(-t / 0.05) * 0.5
    return np.tanh(2.2 * (x * 1.4 + body)) * 0.8


def hat(open_=False):
    n = int((0.16 if open_ else 0.05) * SR)
    t = t_of(n)
    x = filt(RNG.normal(0, 1, n), "highpass", 7200, 4)
    return x * np.exp(-t / (0.09 if open_ else 0.018)) * 0.3


def bass(freq, dur):
    n = int(dur * SR)
    t = t_of(n)
    f = freq * (1 + 0.6 * np.exp(-t / 0.025))
    x = np.sin(2 * np.pi * np.cumsum(f) / SR)
    env = np.minimum(t / 0.004, 1) * (0.35 + 0.65 * np.exp(-t / 0.45))
    env *= np.clip((dur - t) / 0.03, 0, 1)
    main = np.tanh(2.4 * x * env) * 0.26
    crunch = filt(np.tanh(7 * x * env), "bandpass", [180, 1600]) * 0.16  # harmonics phones can play
    return main + crunch


def bitcrush(x, bits=5, hold=6):
    y = np.round(x * (2 ** bits)) / (2 ** bits)
    return np.repeat(y[::hold], hold)[: x.size]


def stab(freqs, dur=0.2):
    n = int(dur * SR)
    t = t_of(n)
    x = np.zeros(n)
    for f in freqs:
        for cents in (-9, 0, 9):
            fr = f * 2 ** (cents / 1200)
            x += 2 * ((t * fr) % 1) - 1  # saw
    x = filt(x / (len(freqs) * 3), "lowpass", 2600)
    x *= np.exp(-t / 0.12) * np.minimum(t / 0.002, 1)
    return (0.5 * x + 0.5 * bitcrush(x)) * 0.9


def blip(freq):
    n = int(0.3 * SR)
    t = t_of(n)
    x = np.sign(np.sin(2 * np.pi * freq * t)) * 0.5 + np.sin(2 * np.pi * freq * 2 * t) * 0.3
    return bitcrush(x * np.exp(-t / 0.08), 4, 8) * 0.55


def riser(dur):
    n = int(dur * SR)
    out = np.zeros(n)
    noise = RNG.normal(0, 1, n)
    block = 1024
    zi = None
    for i in range(0, n, block):
        frac = i / n
        lo = 300 * (20 ** frac)
        sos = butter(2, [lo, min(lo * 2.2, 20000)], btype="bandpass", fs=SR, output="sos")
        seg = noise[i:i + block]
        if zi is None:
            zi = np.zeros((sos.shape[0], 2))
        y, zi = sosfilt(sos, seg, zi=zi)
        out[i:i + block] = y
    t = t_of(n)
    sweep = np.sin(2 * np.pi * np.cumsum(220 * (8 ** (t / dur))) / SR) * 0.15
    return (out * 1.6 + sweep) * (t / dur) ** 2


def impact(big=True):
    n = int((2.2 if big else 1.0) * SR)
    t = t_of(n)
    f = 28 + 40 * np.exp(-t / 0.12)
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / (0.9 if big else 0.35))
    crash = filt(RNG.normal(0, 1, n), "highpass", 2500) * np.exp(-t / (0.7 if big else 0.25)) * 0.35
    return np.tanh(1.5 * (boom + crash)) * (1.0 if big else 0.7)


def crackle(dur):
    n = int(dur * SR)
    x = np.zeros(n)
    idx = RNG.integers(0, n, int(dur * 40))
    x[idx] = RNG.uniform(-1, 1, idx.size)
    x = filt(x, "bandpass", [1000, 8000])
    hiss = filt(RNG.normal(0, 1, n), "bandpass", [3000, 9000]) * 0.03
    return x * 0.6 + hiss


def reverb_ir(seconds=1.4, seed=0):
    r = np.random.default_rng(seed)
    t = t_of(int(seconds * SR))
    ir = r.normal(0, 1, t.size) * np.exp(-t / 0.32)
    return filt(ir, "lowpass", 6000) / np.sqrt(np.sum(ir ** 2))


class Track:
    def __init__(self):
        self.n = int((LENGTH + 2.5) * SR)
        self.bus = {k: np.zeros(self.n) for k in ("kick", "drums", "bass", "stab", "fx", "send")}

    def add(self, bus, sound, at, gain=1.0, send=0.0):
        i = int(round(at * SR))
        j = min(i + sound.size, self.n)
        if i >= self.n:
            return
        self.bus[bus][i:j] += sound[: j - i] * gain
        if send:
            self.bus["send"][i:j] += sound[: j - i] * gain * send


def arrange():
    tr = Track()
    K, C, H, HO = kick(), clap(), hat(), hat(True)
    bar = lambda b: b * 4 * BEAT
    step = lambda b, s: bar(b) + s * STEP

    def groove(b, stabs=True, hats=True, halftime=False):
        chord, root = BAR_HARMONY[b]
        kicks = [0, 10] if halftime else [0, 7, 10]
        claps = [8] if halftime else [4, 12]
        for s in kicks:
            tr.add("kick", K, step(b, s))
        for s in claps:
            tr.add("drums", C, step(b, s), 0.9, send=0.25)
        if hats:
            for s in range(0, 16, 2):
                tr.add("drums", HO if s == 14 else H, step(b, s), 0.8 if s % 4 else 0.5)
        tr.add("bass", bass(root, 7 * STEP), step(b, 0))
        tr.add("bass", bass(root, 6 * STEP), step(b, 10))
        if stabs:
            for s in (0, 3, 6, 10, 12):
                tr.add("stab", stab(CHORDS[chord]), step(b, s), 0.55, send=0.35)
            # crunchy hook an octave up on the chord tones
            notes = CHORDS[chord]
            for k, s in enumerate((0, 3, 6, 8, 11, 14)):
                tr.add("stab", blip(notes[(2, 1, 0, 1, 2, 0)[k]] * 2), step(b, s), 0.32, send=0.25)

    # bar 0: countdown
    tr.add("fx", crackle(2.0), 0, 0.5)
    tr.add("fx", riser(1.88), 0.0, 0.55)
    tr.add("fx", impact(False), 0.0, 0.5, send=0.4)
    for k, f in enumerate((415.30, 466.16, 523.25)):
        at = (k + 1) * BEAT
        tr.add("kick", K, at, 0.8)
        tr.add("drums", C, at, 0.7, send=0.3)
        tr.add("stab", blip(f), at, 0.8, send=0.3)

    # bar 1: drop
    tr.add("fx", impact(True), bar(1), 0.6, send=0.3)
    groove(1)

    # bar 2: one hit per word
    chord, root = BAR_HARMONY[2]
    for k in range(4):
        at = bar(2) + k * BEAT
        tr.add("kick", K, at)
        tr.add("drums", C, at, 0.9, send=0.3)
        tr.add("bass", bass(root, 3 * STEP), at)
        tr.add("stab", stab(CHORDS[chord], 0.3), at, 0.6, send=0.5)
    tr.add("fx", impact(False), bar(2) + 3 * BEAT, 0.8, send=0.5)

    # bar 3: groove then a roll
    groove(3)
    for s in range(8, 16):
        tr.add("drums", C, step(3, s), 0.3 + 0.06 * (s - 8))

    # bars 4-5: collage
    tr.add("fx", impact(False), bar(4), 0.5, send=0.4)
    groove(4)
    groove(5)
    tr.add("fx", riser(2.0 - 0.06), bar(5), 0.45)
    for s in range(8, 16):
        tr.add("drums", C, step(5, s) + STEP / 2, 0.15 + 0.04 * (s - 8))

    # bar 6: logo
    tr.add("fx", impact(True), bar(6), 1.0, send=0.5)
    tr.add("kick", K, bar(6))
    groove(6, stabs=False, halftime=True)

    # bar 7: groove, final hit on beat 31 (bar 7, beat 3)
    groove(7, halftime=True)
    tr.add("fx", impact(True), bar(7) + 2 * BEAT, 0.9, send=0.6)
    tr.add("kick", K, bar(7) + 2 * BEAT)
    tr.add("stab", stab(CHORDS["Fm"], 0.6), bar(7) + 2 * BEAT, 0.7, send=0.7)
    return tr


def mix(tr):
    n = tr.n
    t = t_of(n)
    # sidechain: duck bass + stabs under each kick
    duck = np.ones(n)
    hits = np.flatnonzero(np.diff((np.abs(tr.bus["kick"]) > 0.2).astype(int)) == 1)
    for h in hits:
        seg = t[: int(0.22 * SR)]
        duck[h:h + seg.size] = np.minimum(duck[h:h + seg.size], 1 - 0.6 * np.exp(-seg / 0.07))

    dry = (tr.bus["kick"] * 0.6 + tr.bus["drums"] * 1.1 + tr.bus["bass"] * duck
           + tr.bus["stab"] * duck * 5.0 + tr.bus["fx"] * 0.7)
    left = dry.copy()
    right = dry.copy()
    haas = int(0.011 * SR)  # widen the stabs
    right[haas:] += tr.bus["stab"][:-haas] * duck[:-haas] * 1.6
    left += tr.bus["stab"] * duck * 1.6
    send = tr.bus["send"]
    left += fftconvolve(send, reverb_ir(seed=1))[:n] * 0.5
    right += fftconvolve(send, reverb_ir(seed=2))[:n] * 0.5

    out = np.stack([left, right], axis=1)
    out = filt(out.T, "highpass", 28).T
    out = np.tanh(out * 0.6) / 0.6  # gentle glue / crunch, keeps the hits punchy
    end = int(LENGTH * SR)
    fade = np.clip((end - np.arange(n)) / (0.35 * SR), 0, 1)  # gentle tail fade to 16 s
    out = out[:end] * fade[:end, None]
    return out / (np.abs(out).max() + 1e-9) * 0.89


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "music.wav"
    audio = mix(arrange())
    wavfile.write(path, SR, (audio * 32767).astype(np.int16))
    print(f"Saved {path} ({audio.shape[0] / SR:.2f}s, {SR} Hz stereo)")
