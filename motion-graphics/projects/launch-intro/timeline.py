"""Beat grid and event times shared by music.py and intro.py, so sound and picture stay locked."""

BPM = 120
BEAT = 60 / BPM          # 0.5 s = 15 frames at 30 fps
LENGTH = 16.0            # 8 bars

DROP = 2.0               # muffled "SOUND ON" intro opens into the full track here
GAPS = [(1.875, 2.0), (11.875, 12.0)]  # an 1/8-note of silence right before each big drop

WHIPS = [(2.5, "h"), (3.0, "h"), (3.5, "h"), (6.5, "v"), (7.0, "v")]  # whip-pan transitions
ZOOMS = [4.0, 4.5, 5.0, 5.5, 6.0]                                       # zoom-through transitions
RAPID = (7.5, 8.0)       # 16th-note photo stutter
MONITOR = (10.9, 12.0)   # camera dives into the poster's computer screen
LOGO = 12.0
MINI_HIT = 14.0
FINAL_HIT = 15.0
