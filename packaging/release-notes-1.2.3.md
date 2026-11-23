MHeatmap 1.2.3 — merged .funscript format fix
=============================================

Fix
---

The merged single-file multi-axis script wrote every action as a compact
`[at, pos]` array and `metadata.duration` in milliseconds. The funscript 1.1
layout used by the heatmap web tool (`@eroscripts/funlib`) needs
`{"at": <ms>, "pos": <0-100>}` objects and a duration in seconds — with arrays,
a parser reads every action as time 0 / position 0, so the script never moves.

Merged files now use that layout:

- `actions` and every `axes[].actions` entry are `{at, pos}` objects;
- `metadata.duration` is in seconds (235.265 for a 3:55 script);
- the default `inverted` / `range` fields and the extra `generator` field are not
  written.

Verified by parsing the output with that library: 2395 main actions with real
timestamps, plus the surge / sway / twist / roll / pitch channels.

**Files merged with 1.2.2 or older should be regenerated with this version.**

Everything else from 1.2.2
--------------------------

- Heat band drawn at a constant opacity, linear palette lookup, black canvas,
  hard band edge, 2 px speed curve.
- Speed curve uses the cyan ramp (holding sections are cyan, not black).
- Axis pills, background-opacity slider, copy image (CF_DIB + PNG), standalone
  merge button, new rounded UI, English + 中文.

Install (Windows)
-----------------

1. Download `MHeatmap.zip`, unpack it anywhere.
2. Run `MHeatmap.exe`.
3. If SmartScreen shows up: *More info → Run anyway* (unsigned exe, normal).
