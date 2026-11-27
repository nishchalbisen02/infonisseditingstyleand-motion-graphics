"""LET'S MAKE SOME NOISE - show intro hit map. Shared by sound.py and intro.py so picture and sound lock.

Concept "MIC CHECK -> OVERLOAD": silence, a single white line, a mic being tapped. The taps speed up,
feedback starts to scream, the show's name is hit word by word, the signal overloads and the
screen loses control, everything implodes to a dot, one beat of dead silence, then the logo
detonates out of smoke and the line settles back into the logo's own underline.

150 BPM: one beat = 0.4 s = 12 frames at 30 fps. Total 28 beats = 11.2 s.
"""

FPS = 30
BPM = 150
BEAT = 60 / BPM
LENGTH = 28 * BEAT                     # 11.2 s

LINE_IN = 0.4                          # the flatline appears
TAPS = [0.8, 1.6, 2.0, 2.2, 2.4, 2.5, 2.6, 2.7]   # mic taps, accelerating
FEEDBACK = (2.0, 4.75)                 # feedback squeal rises
WORDS = [(2.8, "Let's"), (3.2, "make"), (3.6, "some"), (4.0, "noise")]
STUTTER = (4.2, 4.75)                  # "noise" beat-repeat, faster and faster
GAP1 = (4.75, 4.8)                     # a breath before the drop
DROP = (4.8, 7.2)                      # out of control: cuts every 8th note
CUT = BEAT / 2                         # 0.2 s = 6 frames
IMPLODE = (7.2, 7.6)                   # everything sucked into a dot, tape stop
SILENCE = (7.6, 7.8)                   # dead air
REVEAL = 7.8                           # the logo detonates out of smoke
UNDERLINE_SETTLE = (8.0, 9.0)          # the scope line calms into the logo's underline
GLITCH_TICKS = [9.8, 10.6]             # tiny reminders that it is not under control
