MHeatmap 1.2.1 — heatmap colours / style fixed to match the reference
======================================================================

What changed
------------

The heat band now looks like the reference picture instead of the washed-out
version from 1.2.0:

- **Constant, high band opacity** (212 instead of an intensity-scaled
  92…210 with a 1.35 boost). Slow segments are just as solid as fast ones, so
  the colours stay saturated.
- **Colour lookup is linear again** (no smoothstep) — the band shows the actual
  palette hues (green → yellow → orange → red → magenta) at full strength.
- **Black row background** (pure #000 instead of #181818 / #242424), matching
  the reference’s black canvas.
- **Hard band edge**: 40 px solid band + 16 px at ~21 % instead of a long
  gradient fade.
- **Thicker speed curve** (2 px) with a bit more alpha, like the reference.

Everything else from 1.2.0 is unchanged: new rounded UI, copy-to-clipboard,
standalone “Merge .funscript”, single OFS palette, background-opacity slider,
axis pills, EN/中文.

Also a small robustness fix: after a preview is shown the window re-fits once
the layout settles, so the preview never starts out cropped.

Checks
------

`python tools/run_checks.py` — all green (rendering, background alpha values,
axis filtering, merge output, clipboard formats, UI flow, first-run language).
