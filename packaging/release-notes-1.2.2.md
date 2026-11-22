MHeatmap 1.2.2 — curve colour fix
=================================

Fix
---

The speed curve was drawing with the *heat* palette, whose zero value is black and
whose upper half is dark, so flat/holding sections came out as **black lines**. It
now uses the dedicated cyan ramp: holding = cyan, movement = green/yellow, fast =
red/purple.

Also in this version (since 1.0.0)
----------------------------------

- Constant opaque heat band (alpha 212), linear palette lookup, pure-black canvas,
  hard 40 px band edge with a 21 % tail, 2 px speed curve.
- Axis pills (L0…R2): draw only the selected axes, image height follows.
- Background opacity slider 0–100 % with `_bg<value>` output suffix.
- Copy image button / `Ctrl+C` — clipboard gets CF_DIB **and** PNG.
- Merge .funscript button / `Ctrl+M` — single-file multi-axis funscript
  (version 1.1, `actions` + `axes`), no PNG generated.
- New UI: rounded pills with hover/press feedback, card layout, pulsing status dot,
  toast messages, double-click-to-fit preview.
- Single OFS palette; English + 中文 with first-run language picker.

Install (Windows)
-----------------

1. Download `MHeatmap.zip`, unpack it anywhere.
2. Run `MHeatmap.exe`.
3. If SmartScreen shows up: *More info → Run anyway* (unsigned exe, normal).
