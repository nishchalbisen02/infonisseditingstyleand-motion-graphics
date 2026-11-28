# Motion design playbook

Rules Claude follows for every motion graphics job in this repo. Distilled from the public material of
Motion Design School ([motiondesign.school](https://motiondesign.school/), read 2026-11-28): 158 blog
articles and the syllabi of 14 courses. Paraphrased in our own words; links point to the sources.

What this is **not**: their courses themselves. The real lessons are paid video courses, and most free
tutorials are videos too, so the text pages give the principles and the map of the craft, not the full
lessons.

## 1. The map of the craft (what "all of motion design" covers)

From the core course syllabus (Motion Beast), in learning order:
1. **Basics:** transform properties, layers and timeline.
2. **Shapes and modifiers:** shape layers, masks, shape modifiers (trim paths, offset, repeater, wiggle).
3. **Easing:** the single most important skill.
4. **Look:** stylization and effects, glitch and liquid.
5. **Building blocks:** loops, text animation, morphing, lettering, logo animation.
6. **Automation:** expressions (animation without keyframes, links between parameters).
7. **The 12 animation principles.**
8. **Characters:** walks, runs, rigging, pseudo-3D, face rigs and facial animation.
9. **Hand-made:** path animation, frame-by-frame (pose-to-pose).

Specialist tracks around it: logo animation, UI animation, animated typefaces, loops, frame-by-frame
FX (smoke, liquid, energy), VFX and glitch, 3D (C4D, Blender), sound design.

## 2. Timing and easing

- **Plan the rhythm first.** Before animating, mark how many bars or beats the piece gets, then fit the
  action into them. Overlong animation is the most common mistake: "don't make the scene any longer than it has to be".
  Here: every project gets a `timeline.py` / beat grid before any visuals
  ([logo mistakes](https://motiondesign.school/blog/5-mistakes-in-logo-animation/)).
- **Beginners animate too slowly** because they want every detail seen. A practical rule: make it
  about **30% faster** than feels right
  ([UI tips](https://motiondesign.school/blog/3-tips-on-user-interface-animation/)).
- **Nudge keyframes a few frames at a time**: the right feel is often "just a few frames away".
  To retime a whole block, time-remap the pre-comp (here: scale the times in the timeline, not each key).
- **Peaks never stop dead.** An object thrown up slows on the way up and speeds up falling, and its
  speed at the top of the arc is **not zero**, or it looks stuck in the air.
- Constant speed (linear) only where physics demands it: a foot planted on the ground moves linearly,
  with no easing ([walk cycle mistakes](https://motiondesign.school/blog/7-walk-cycles-mistakes/)).
- Real things rarely move at constant speed; use acceleration and deceleration to show weight,
  gravity and impact ([keyframe velocity](https://motiondesign.school/blog/keyframe-velocity/)).
- **Exponential scale** for zooms: a linear scale looks like it slows down as it grows
  ([exponential scale](https://motiondesign.school/blog/exponential-scale-in-after-effects/)).
  Here: interpolate scale in log space (as `show-intro` and `launch-reel` already do).

## 3. The 12 principles, as used here

The ones the school stresses for graphics and logos:
- **Easing** (slow in, slow out).
- **Arcs:** organic paths; a straight arm waving is an arc around the shoulder.
- **Squash and stretch:** controls weight and material. Gum, slime and rubber all stretch differently.
- **Stretch on one axis:** the logo-animation version of smear.
- **Anticipation:** a small opposite move before the main one.
- **Follow-through and overlapping action:** parts lag behind the driver by 2–3 frames.
  Nothing moves in perfect sync unless it is a robot.
- **Secondary action:** for example smears.
- **Exaggeration:** "animation is about expression and exaggeration".

[Source: logo animation principles](https://motiondesign.school/blog/animation-principles-in-logo-animation/)

## 4. Logo animation rules

- **One major action at a time.** Several big moves at once confuse the viewer.
- **Show the logo in its original form** for a beat, before or after the animation, so it is recognised.
- **Stagger elements** in a clear order, or with small offsets, so the viewer does not tire.
- **Use the frame wisely:** mark an area around the logo and keep the action inside it. Small details
  should not fly far apart.
- **Match the logo's DNA:** any added element uses the logo's own palette, line thicknesses and level
  of detail. Compare additions with the biggest and smallest detail in the logo.
- **No fan art:** do not draw new icons or people in the logo's style unless asked. Work with what you were given.
- Course topics worth mastering: idea generation (write a mini-scenario first), clean reveals, morphing,
  stroke-style animation, monoline and classic lettering, glitch (basic, stylized, pro), liquids,
  mascots, and export to code.

[Sources: logo mistakes](https://motiondesign.school/blog/5-mistakes-in-logo-animation/), [course syllabus](https://motiondesign.school/courses/logo-animation-in-after-effects/)

## 5. Transitions and morphing

Three kinds of morph:
- **Direct:** a real shape-to-shape morph. It can be slow, because nothing needs hiding.
- **At max speed:** swap the object mid-motion, and the eye fills in the gap.
- **50/50:** a partial morph, plus masks, distracting elements and a strong direction of motion.
  It looks direct for a fraction of the work.

Workflow for a scene-to-scene transition:
1. Find 1–3 pairs of objects that match in at least two of **colour, shape, volume**.
2. Rough out only their transformation. Everything else follows their timing.
3. Add the largest objects, moving in the **same direction and speed**.
4. Detail the key objects.
5. Add small elements last.

Keep the paths simple and clear. Know the difference between a **morph** and a **match cut**.

[Source: morphing study](https://motiondesign.school/blog/morphing-study-how-to-create-animated-transition/)

## 6. Look and stylization

- **Hand-made, boiling texture:** displace or roughen the edges and update the noise at a low frame
  rate. The school's cartoon stylization steps the noise at **5 fps**. Here we boil at 10–12 fps,
  and 5–8 fps reads as more hand-drawn.
- **Brush look:** scatter, bilateral blur, emboss, radial blur, turbulent displace.
- **Smears and trails:** for fast moves, use echo trails, dashed strokes or stretched in-between
  frames instead of plain motion blur. Speed lines sell superluminal speed.
- **Depth without 3D:** parallax (layers moving at different speeds), gradients as a light system, and
  "solid drawing" (spheres, cubes or cylinders shaded so they read as 3D).
- **Loops:** theory first, overlapping action so short cycles feel continuous, constant-speed zooms,
  looping particles, and design for GIF compression.

## 7. Sound design

- Sound design is three jobs: **ambience** (where are we), **foley** (footsteps, cloth, doors) and
  **designed sounds** that do not exist in nature.
- **Layering** makes unique and legally safe textures: combine several sources, pitch-shift and mix.
  Their examples: a roar from a shout through a balloon, pitched down, plus animals plus a synth;
  rain that sounds like frying bacon.
- The skill is association: matching a sound to an image. Build a personal library over time.
- The final mix sets the balance and meets each **platform's loudness standard**. Here we use -14 LUFS for
  Instagram and YouTube, with a true-peak limit.

[Source: sound design interview](https://motiondesign.school/blog/sound-design-by-daruma-audio/), [course syllabus](https://motiondesign.school/courses/sound-design-for-animation/)

## 8. Process

1. **Idea first:** write a mini-scenario, and make several rough versions instead of polishing the
   first one ("more iterations and variations").
2. **Simple beats clever.** Do not use a newly learned trick just because it is new.
3. **Check with fresh eyes:** look away, work on another scene, then come back to spot mistakes.
4. **Pose-to-pose** for complex frame-by-frame work: key poses first, in-betweens later.

## 9. How their work actually looks

Observed from about 114 example GIFs on their course pages (logo, FX, glitch, type, loops, UI),
studied frame by frame:

- **Logo pieces are short.** The logo is readable by about 0.7–2.5 s, the whole piece runs 3–5 s, and the
  last ~1–1.5 s is a clean hold, often with one small secondary action (a beam, a blink, a wiggle).
- **The logo is built from its own primitives:** dots, bars and strokes that are already in the mark.
  Examples: bars glitch into "LOGO", strokes draw "NEON", one red stroke becomes "deadline" letter by
  letter, a UFO "character" beams the logo into place.
- **Reduced palette:** a dark navy or flat background, white plus 1–2 accent colours, flat vector shapes.
- **Glitch is chunky and rhythmic:** big horizontal slice offsets in bursts, separated by clean frames.
- **Hand-drawn FX** (liquid, smoke, energy) are flat shapes with one inner shade, animated on 2s or 3s
  (about 10–12 fps), with paper grain. The rough blue/red construction drawing comes first, clean colour after.
- **Typography motion is graphic:** letters wipe or split with accent colours sliding through them,
  on a strong single-colour field.
- **Delivery format:** most examples run at 24–25 fps; the hand-drawn work is about 10–12 fps.

## 10. Pre-delivery checklist

- [ ] The beat grid / timeline was planned before animating. Nothing is longer than it needs to be.
- [ ] Tried it ~30% faster. Every ease checked; no element hangs still at the top of an arc.
- [ ] One major action at a time; parts overlap by 2–3 frames instead of moving in sync.
- [ ] Logo shown clean for at least a beat; added elements match its palette and line weight.
- [ ] Transitions hand off on a matching colour, shape or volume, in one clear direction.
- [ ] Sound: ambience, hits and designed layers; mix at -14 LUFS with a true-peak limit.
- [ ] Watched once with fresh eyes (contact sheet plus consecutive frames around every cut).
