MHeatmap 1.1.0 — axis picking, palettes, background opacity, merged scripts
==============================================================================

New in 1.1.0
------------

- **Axis selection** — after loading a multi-axis set, toggle L0/L1/L2/R0/R1/R2
  (and vib/pump when present) in the sidebar; only the chosen axes are drawn and
  the image gets shorter automatically.
- **Five palettes** — OFS Rainbow (default), Classic, Inferno, Viridis,
  Grayscale. Each ramp has its own gamma so low speeds still show colour.
- **Background opacity slider** — 0…100 %. 0 = fully transparent PNG,
  100 = solid, in between is allowed. Output names carry `_bg<value>` when it is
  not 100 (e.g. `_Axes_bg50.png`), so different settings do not overwrite each
  other.
- **Merge into one multi-axis script** — tick “Also export one multi-axis
  .funscript” to also write `xxx_merged.funscript` in funscript **1.1** form:
  `actions` is the stroke axis (L0 by default) and `axes` holds the other
  channels as `{id, actions}` — the same single-file layout MultiFunPlayer uses.
- Remembered per-install: width, palette, background opacity, selected axes,
  merge switch, language, output folder.

Still the same
--------------

One row per axis with a translucent filename banner (`name.surge.funscript::surge`),
Duration / Actions / MaxSpeed / AvgSpeed stats, heat band and speed curve.
English + 中文 UI, English by default, first launch asks for the language.

Install (Windows)
-----------------

1. Download `MHeatmap.zip`, unpack it anywhere.
2. Run `MHeatmap.exe`.
3. If SmartScreen shows up: *More info → Run anyway* (unsigned exe, normal).

Checks
------

`python tools/run_checks.py` covers parsing, rendering, palettes, alpha values,
axis filtering, the merge output and the Tk flow.
