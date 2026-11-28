# Infoniss workspace: instructions for Claude

The owner works almost entirely from their phone (Claude app) and writes in Hindi.
This repo is their workspace for two kinds of work: **meetings** and **motion graphics**.

## How to work here

- Reply in simple Hindi (Devanagari), short and clear. Explain any technical step in one plain line.
- The owner cannot run commands or open a computer. Do the whole job yourself, then **send finished
  files (videos, images, documents) to the user with the file-sending tool** so they open in the app.
- **Save every piece of work:** at the end of each task, commit and push to `main` directly
  (single-owner repo, phone workflow; no PRs unless asked). Unpushed work is lost when the cloud session ends.
- Ask only when the answer changes the result (e.g. the exact name/text to show). Otherwise use
  sensible defaults and say what you chose.
- **This repo is public.** Never commit the owner's own footage, photos, voice or unreleased edits
  (e.g. a launch reel before launch) without asking. Commit the edit scripts; send the media directly.

## Meetings (`meetings/`)

- Templates: `meetings/templates/agenda.md`, `meetings/templates/minutes.md`.
- One file per meeting: `meetings/YYYY-MM-DD-<short-topic>.md`. Agenda first; add the notes/MoM to the
  same file after the meeting.
- Typical requests: agenda, MoM with action items from pasted notes or a transcript, follow-up message
  (WhatsApp/email text), reminders, scheduling.
- Google Calendar / Gmail: use the connectors when they are available. Always show the details and get a
  clear "yes" before creating an event, inviting people or sending an email. Prefer a Gmail draft over sending.

## Motion graphics (`motion-graphics/`)

**Read `motion-graphics/MOTION_PRINCIPLES.md` before any motion job** and run its pre-delivery checklist
before sending a video (timing, easing, logo rules, transitions, sound, process).

Templates are HTML + CSS animations in `motion-graphics/templates/`, rendered frame by frame to video:

```bash
node motion-graphics/render.js motion-graphics/templates/<name>.html -p key=value -p key2=value2
```

- Options: `--size hd|reel|square|WxH`, `--green` (flat chroma-key MP4 for phone editors like CapCut/KineMaster/VN),
  `--alpha` (transparent ProRes 4444 `.mov` for Premiere/AE/DaVinci/Final Cut), `--still <sec>` (one PNG frame),
  `--out <file>`. Run `--help` for the full list.
- Workflow: render a `--still` and look at it yourself, fix layout, render the video, pull 3–6 frames with
  ffmpeg (`-vf "select=...,tile=3x2"`) to check the motion, then send the MP4 to the user.
- Overlays (lower thirds, callouts): if unknown, ask once whether they edit on phone (`--green`) or computer (`--alpha`).
- Output goes to `motion-graphics/output/`. Commit MP4s under ~50 MB. `.mov` files are git-ignored: send them directly.

### Editing the owner's footage (`motion-graphics/projects/`)

- One folder per edit with a re-runnable script; uploads only live for one session, so the script takes the
  source path as an argument. Example: `projects/launch-reel/edit.py` (16:9 to 9:16 reel: face-following crop,
  punch-in zooms in speech pauses, end-card pull-back, grade, grain, handle watermark, -14 LUFS audio).
- Use `--preview t1,t2,...` to get a contact sheet before the full render.
- Speech-to-text models can't be downloaded here (Hugging Face is blocked), so captions need the
  owner to type the words, or the environment's network to allow the model host.
- `projects/launch-intro/`: photo-only motion graphics launch reel (no footage). `prep.py` cuts out
  backgrounds with rembg (models come from GitHub releases, which are reachable; isnet-general-use, and
  birefnet-portrait for B&W photos on dark backgrounds; load only one BiRefNet session at a time or the
  container runs out of memory). `music.py` synthesises an original 120 BPM track (no licensed music).
  `intro.py` renders scenes locked to that beat grid. Photos go in `assets/src/` (git-ignored).
- `projects/show-intro/`: the official 16:9 show opener (concept "MIC CHECK -> OVERLOAD"), see its
  `TREATMENT.md`. `timeline.py` holds every hit time for both `sound.py` and `intro.py`; edit it, then
  re-render both. Needs `assets/logo-hires.png` (git-ignored; median-stacked from the original intro's end card).
- `projects/logo-sting/sting.py`: 4 s logo sting / end tag (`--size hd|reel`), the playbook applied
  (the underline is the character: arc + smear flight, squash, anticipation, 3-frame overlap, overshoot,
  one accent, clean hold). Reuses show-intro's logo, helpers and synth.

### Writing a new template

- Copy the structure of an existing template: `<meta name="mg-duration|mg-size|mg-fps">`, load
  `../assets/fonts/fonts.css` and `../assets/mg.js`, read text/colours with `mg.params({...defaults})`.
- Animate with CSS animations/transitions only, or define `window.renderFrame(t)` for JS/canvas work.
  `render.js` pauses every animation and seeks it to each frame's time; setTimeout/rAF-driven motion will not render.
- Entrance animations use fill `both`. Put exit animations on a wrapper element with fill `forwards`
  (a `both` exit on the same element hides the entrance).
- Size everything from the `--u` unit so hd, reel and square all work.
- Split Hindi text on spaces only (`mg.splitWords`), never per character: that breaks conjuncts and matras.
- Avoid big `filter: blur()` on large elements; it made renders ~6x slower. Soft radial gradients look the same.
- Give background-only layers the `backdrop` class so `--alpha` and `--green` remove them.
- Fonts: bundled Poppins (Latin + Devanagari) in `assets/fonts/`. Don't rely on web fonts at render time;
  to add a font, download its woff2 files (free/OFL licence) into `assets/fonts/` and add `@font-face` rules.
- Make original designs only; don't copy another creator's or brand's graphics.
