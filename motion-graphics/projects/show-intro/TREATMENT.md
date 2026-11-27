# LET'S MAKE SOME NOISE: show intro treatment

16:9 · 1920×1080 · 30 fps · 11.2 s · original sound design · no hook, no CTA, no tagline. The name is the hero.

## 1. Analysis

**The logo**
- One word with no spaces ("Let'smakesomenoise") in a thick, distressed, hand-cut sans. Every letter has
  rough, double-stroked outlines, like it was traced over twice with a marker that was running out.
- A small hand-drawn squiggle underline sits off-centre under "makesome". It is the only gesture in
  the mark, and it reads like a pen check or a signal blip.
- White on black. It already feels like a photocopy of a photocopy, so it can take heavy grain,
  glitch and displacement without losing identity.
- Technical note: the letters touch, so the four words can only be separated with vertical cuts
  (x = 353 / 745 / 1113 in the 1506 px master). The intro uses those cuts to hit the name word by word
  while every pixel of type is still the owner's own logo.

**The existing intro (posted)**
- Strengths: real-life, close-up, handheld, a little chaotic. The end card (smoke clearing to the logo)
  is the strongest moment, so the new intro keeps "smoke → logo" as its payoff.
- Weaknesses for a show opener: it is a vlog clip, not an identity. The logo appears only at the very
  end, and the sound is a phone mic. A show needs a repeatable, ownable sound-and-picture signature.

**Brand words → design rules**

| Brand word | Rule |
|---|---|
| Unfiltered | Only the logo, the waveform and noise; no stock elements |
| Unpredictable | No cut lands on the same treatment twice |
| Raw, not over-polished | Grain, gate weave, dust, 12 fps boil; nothing perfectly smooth |
| A little madness | The intro has to genuinely lose control, then snap back |

## 2. Three concepts

### A. MIC CHECK → OVERLOAD ✅ (chosen)
- **Idea:** "Making noise" taken literally. A mic is checked, the signal overloads, and the show bursts out of it.
- **Visual treatment:** Pure black. The only light source is a white oscilloscope line drawn from
  the actual soundtrack. Logo words are displaced, smeared, torn and quaked. Ends in film burn, smoke, grain and VU meters.
- **Sequence:** flatline → mic taps (the line jumps) → feedback climbs → LET'S / MAKE / SOME / NOISE,
  one hit and one distortion each → stutter → DROP, 12 cuts in 2.4 s → implosion to a dot → dead air → logo
  detonates out of smoke → the waveform calms into the logo's own underline.
- **Transitions:** inverted frames on hits, beat-repeat stutter, row tears, block glitch, a single
  white flash, an implosion zoom.
- **Sound:** room tone and mains hum, mic thumps, feedback howl, FM metal hits, beat-repeat, a
  150 BPM distorted half-time drop, tape stop, silence, a sub boom with crash and shimmer, an
  applause swell and a drone tail.
- **Why it wins:** It is about noise, so the design carries the name's meaning. It is fully ownable:
  no footage, no stock, and the picture *is* the sound. The logo's underline becomes a story beat.
  It also scales to the whole show (see section 4).

### B. PHOTOCOPY RIOT
- **Idea:** The logo runs through a broken photocopier until it falls apart, like a zine.
- **Visual:** Xerox toner, misregistration, staples, torn paper strips, halftone blow-ups,
  scribble animation on a lightbox.
- **Sequence:** scanner light sweeps → copies stack up faster and dirtier → paper jam → shredder
  → the strips fall and land as the clean logo.
- **Sound:** copier motor and clunks, paper rips, a stamp hit per word, a breakbeat.
- **Why not:** Strong texture, but it says "print / design studio" more than "noise / entertainment".
  The grammar is kept inside A (scribble trace, macro type, stamp hits).

### C. LIVE FEED LOST
- **Idea:** A broadcast feed hijacked by the show.
- **Visual:** a TV test pattern, a countdown leader, signal loss and VHS tracking errors; the logo
  burns in like a CRT afterimage.
- **Sequence:** "normal" broadcast → interference → the frame rolls → static → the logo takes over the channel.
- **Sound:** 1 kHz tone, channel hiss, a modem squeal, a bass drop.
- **Why not:** "Signal hijack" is a well-worn intro trope and close to generic YouTube templates. It
  is also less tied to the name. Its VHS / CRT language survives only as texture in A.

## 3. Chosen direction: storyboard and hit map (150 BPM, 1 beat = 12 frames)

| Time (s) | Picture | Sound |
|---|---|---|
| 0.0–0.4 | Black, grain, dust | Room tone, hum, crackle |
| 0.4 | A white flatline fades on | — |
| 0.8 / 1.6 / 2.0–2.7 | The line jumps on each mic tap; taps get faster; 2-frame subliminal logo trace at 1.6 | Mic thumps, accelerating |
| 2.0–2.8 | The line goes hysterical, with phosphor ghosting | Feedback howl climbs, riser |
| 2.8 / 3.2 / 3.6 / 4.0 | **Let's** (wave) / **make** (horizontal smear) / **some** (row tear) / **noise** (quake + waveform ring + scribble halo); inverted frame on each hit | Kick + snap + FM metal per word; "noise" gets a crash |
| 4.2–4.75 | Stutter: invert, row slices and RGB split alternate per repeat; VU meters red-line | Beat-repeat 1/4 → 1/8 → 1/16 |
| 4.75 | Black frame | 1/32 silence |
| 4.8–7.2 | **DROP**: a new card every 6 frames: scribble trace, logo marquee, negative macro, waveform ring, block glitch, macro "noise", film burn, smoke strobe | 150 BPM half-time, distorted 808 sliding a flat 2nd, crushed stabs, mid growl |
| 7.2–7.6 | Everything spins into a single point | Tape stop + reverse cymbal |
| 7.6–7.8 | Black with one blinking dot | **Dead silence** |
| 7.8 | White flash → the logo detonates out of smoke; shockwave rings; film burn at both edges | Sub boom, crash, shimmer, smoke whoosh panned L→R |
| 8.0–9.0 | The oscilloscope line calms and becomes the logo's underline | Applause-like crowd swell |
| 9.0–11.2 | Clean logo hold; a faint boiling scribble trace keeps it alive; two tiny glitch ticks; embers | Drone tail, two glitch ticks |

The end frame is a clean logo on black, so the show can cut straight in.

## 4. Production workflow

**Source of truth:** `timeline.py`. Every hit time lives there, and both `sound.py` and `intro.py`
read it, so picture and sound cannot drift. To retime the intro, edit `timeline.py` and re-render both.

```bash
python3 motion-graphics/projects/show-intro/sound.py      # build/mix.wav + stems (48 kHz)
python3 motion-graphics/projects/show-intro/intro.py --preview 2.8,4.8,7.8,10 --out sheet.png
python3 motion-graphics/projects/show-intro/intro.py --out LMSN_show_intro_1080p.mp4
```

**Assets:** `assets/logo-hires.png` is git-ignored and is not in the public repo.
- It is a 1506×286 white-alpha logo, median-stacked from 33 end-card frames of the owner's original intro, which removes compression noise.
- To rebuild it, re-upload that video or a high-resolution logo file.

**Pipeline:**
1. Sound first: synthesise the hit map, export the mix and dry stems.
2. Picture renders frame by frame:
   - The waveform elements read the real mix, so every wiggle is the sound you hear.
   - Graphics boil at 12 fps and film grain runs at 24 fps, for a hand-made, analog feel.
3. Post per frame: impact shake, RGB split, inverted and flash frames, bloom, flicker, vignette, gate weave, dust and scratches.
4. Mux: linear gain to -14 LUFS (keeps the quiet opening quiet), true-peak limit, AAC 320k.

**Deliverables:**

| File | Purpose |
|---|---|
| `LMSN_show_intro_1080p.mp4` | Master (CRF 14, grain-tuned) |
| `..._phone.mp4` | Light copy for upload and preview |
| `LMSN_intro_mix_48k24.wav` | 24-bit mix |
| `stem_sfx.wav`, `stem_music.wav` | Dry stems for re-mixing under the episode's audio |
| `LMSN_logo_white_alpha.png` | Logo for lower thirds, thumbnails and bumpers |
| `LMSN_end_frame.png` | Clean end frame |
| `LMSN_storyboard.png` | 18-beat storyboard |

**Editable files:**
- The three Python files are the project. They are parametric, so timings, colours, card order and
  word effects are constants at the top of each file.
- There is no After Effects file. The look depends on per-frame code (audio-driven waveform, boil,
  smoke), so an AE rebuild would start from the stems, the logo PNG and the storyboard above.

**Extending the identity** (same grammar, no new elements):
- 3 s **bumper:** mic tap → "noise" quake → logo.
- **Segment cards:** the waveform line writes a segment name, then calms into the underline.
- **Stinger / transition:** the 12-frame stutter + invert.
- **Sound logo:** the last 1.4 s of the mix (boom + shimmer + crowd), usable on its own.
