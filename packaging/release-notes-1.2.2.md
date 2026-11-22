MHeatmap 1.2.2 — curve colour fix
=================================

What was wrong
--------------

The speed curve was passed the *heat* palette instead of the cyan curve ramp.
The heat palette is black at zero intensity and dark from 0.4 upwards, so any
flat/holding section of a script drew a **black line** (and fast sections drew
dark olive/teal) — exactly the “some lines turned black” report.

Fix
---

- `draw_curve` now always uses the dedicated curve ramp (the original
  LINE_COLOR_STOPS: cyan → green → yellow → red → purple), so:
  - zero-speed / holding segments are **cyan**,
  - normal movement is green/yellow,
  - only really fast segments go red/purple.
- Added a regression check: a script made of holding segments must produce
  cyan curve pixels, never black ones.

Still in place from 1.2.1
-------------------------

Opaque heat band (212 alpha), linear palette lookup, pure-black canvas, hard
40 px band edge with a 21 % tail, 2 px curve. Copy-to-clipboard, standalone
merge, single OFS palette, background-opacity slider, axis pills, EN/中文.
