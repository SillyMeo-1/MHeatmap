MHeatmap 1.2.0 — new UI, copy to clipboard, standalone merge
============================================================

New in 1.2.0
------------

- **Copy image** button (and `Ctrl+C`): the current preview goes to the Windows
  clipboard as CF_DIB **and** PNG, so Paint / Word / browsers / chat apps can
  paste it directly.
- **Merge .funscript is its own button** — it only writes
  `xxx_merged.funscript` for the selected axes; no PNG has to be generated.
  The file stays funscript **1.1** (`actions` = stroke axis, `axes` = the other
  channels as `{id, actions}`), the same single-file layout MultiFunPlayer uses.
- **Palette selector removed** — back to the single OFS rainbow ramp, as asked.
- **New UI**: rounded buttons and pills with hover/press feedback, a card layout,
  mint accent colour, a status dot that pulses while rendering, toast messages
  for copy / save / merge, and double-click-to-fit on the preview.
- Background opacity slider, axis pills, bilingual UI and the first-run language
  picker are all still there.

Install (Windows)
-----------------

1. Download `MHeatmap.zip`, unpack it anywhere.
2. Run `MHeatmap.exe`.
3. If SmartScreen shows up: *More info → Run anyway* (unsigned exe, normal).

Checks
------

`python tools/run_checks.py` covers rendering, background alpha, axis filtering,
merge output, clipboard formats (CF_DIB + PNG) and the Tk flow.
