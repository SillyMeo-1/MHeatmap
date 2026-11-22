MHeatmap 1.0.0 — Funscript Heatmap Generator
============================================

First public release.

**What it does**

- One row per axis (L0/L1/L2/R0/R1/R2 + vib/pump): translucent filename banner
  (`name.surge.funscript::surge`), Duration / Actions / MaxSpeed / AvgSpeed,
  heat band and a speed curve — one image per script set.
- Transparent background: PNG keeps the alpha channel, output gets a
  `_transparent` suffix so the opaque version is kept.
- English + 中文 UI, **English by default**; the first launch asks for the
  language and remembers it.
- Drag & drop, preview with zoom/pan, batch save, remembered width/transparency.
- Single-file Windows build: no installer, no Python.

**Install (Windows)**

1. Download `MHeatmap.zip`, unpack it anywhere.
2. Run `MHeatmap.exe`.
3. If SmartScreen shows up: *More info → Run anyway* (unsigned exe, normal).

**Output**

`<group>_Axes.png` (opaque) / `<group>_Axes_transparent.png`, default 1380 px
wide, 104 px per row (six axes → 1380×628).

**Checks**

`python tools/run_checks.py` — parsing, geometry, alpha, bilingual strings and
the Tk flow. `python app.py --selftest <folder>` renders without opening a window.
