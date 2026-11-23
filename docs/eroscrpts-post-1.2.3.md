# MHeatmap 1.2.3 — Funscript Heatmap Generator (Windows)

**GitHub:** https://github.com/SillyMeo-1/MHeatmap
**Download:** https://github.com/SillyMeo-1/MHeatmap/releases/tag/v1.2.3

MHeatmap turns `.funscript` files into a compact heatmap image: one row per axis,
with the filename in a banner, per-axis speed statistics, a colour-coded heat band
and a speed curve underneath. It is a small Windows app — single `.exe`, no
installer, no Python.

Useful when you want to check a script at a glance: where the fast sections are,
whether a channel is dead, whether two axes line up in time, or which parts of a
14-minute file are worth keeping.

Runs on Windows 10 / 11 (64-bit). Everything happens locally — no script is uploaded
anywhere, and the tool works offline.

---

## Screenshots

![Main window](ui-result.png)

*One image per script set. Every axis gets its own row: L0 / L1 / L2 / R0 / R1 / R2
(and vib / pump when present).*

![Example output](curve-fixed.png)

*The exported PNG: 1380 × 628 for six axes. Heat band on top, speed curve below,
stats on the right.*

---

## Features

- **One row per axis** — L0/L1/L2/R0/R1/R2 plus vib/pump, with the filename banner
  (`name.surge.funscript::surge`) and Duration / Actions / MaxSpeed / AvgSpeed.
- **Pick the axes** — toggle the L0…R2 pills; only the selected axes are drawn and
  the image height follows (two axes → 1380 × 212).
- **Background opacity** — 0–100 %. 0 % gives a transparent PNG you can lay over a
  thumbnail or a player UI.
- **Copy image** (`Ctrl+C`) — straight to the clipboard as CF_DIB **and** PNG, so it
  pastes into Paint, Word, a browser or the forum editor.
- **Merge to one file** (`Ctrl+M`) — writes a single-file multi-axis `.funscript`
  (funscript 1.1: `actions` for the stroke, `axes` for every other channel) without
  generating any PNG. Files merged with 1.2.2 or older should be regenerated.
- **Batch** — drop a folder, get one image per script set.
- **English + 中文 UI**, English by default, and the first launch asks which one you
  want. Switch anytime from the top bar.
- **Remembers your setup** — width, opacity, selected axes, output folder and
  language are stored in `%APPDATA%\MHeatmap\settings.json`.

---

## Download & install

1. Open the release page and download **`MHeatmap.zip`**.
2. Unpack it anywhere and run **`MHeatmap.exe`**.
3. Windows may show *"Windows protected your PC"* — click **More info → Run anyway**.
   That is the normal SmartScreen prompt for a small unsigned app; there is no
   installer and nothing is written outside `%APPDATA%\MHeatmap`.

---

## Quick start

![First launch](first-run-language.png)

1. **Launch** and pick a language (English / 中文).
2. **Add your scripts** — drag `.funscript` files or a folder onto the window, or use
   **Add files / Add folder**. Dropping a single file also pulls in the other axes of
   the same script, so one drag gives you the whole set.
3. **Choose the axes** — click the L0…R2 pills. Grayed-out pills mean that axis is not
   in the current input.
4. **Set the width** — default 1380 px; anything from 640 to 4096 works.
5. **Background** — 100 % for a solid image, 0 % for a transparent PNG, or anywhere in
   between.
6. **Preview** (`F5`) to look at the result, then **Generate & save** (`Ctrl+S`) to write
   the files.

Output goes to `<script folder>\heatmaps` by default. **Change** picks another folder,
**Auto** goes back to the default.

![Chinese UI](ui-chinese.png)

### Other things worth knowing

- **Zoom / pan** the preview with the mouse wheel and drag; double-click to fit.
- **Copy image** puts the current preview on the clipboard — handy for posting a quick
  before/after in a thread.
- **Merge .funscript** only writes the merged script; it does not touch the PNGs.
- **Drag & drop** accepts several files and folders at once.

---

## Output files

| File | When |
|---|---|
| `<group>_Axes.png` | solid background (100 %) |
| `<group>_Axes_bg<value>.png` | any other opacity, e.g. `_Axes_bg50.png`; `_bg0` is transparent |
| `<group>_merged.funscript` | when you press **Merge .funscript** |

The group name is the common base name of the scripts in the folder.

## Filename / axis mapping

Scripts in the same folder with the same base name are grouped into one image.

| Axis | Suffix accepted in the filename |
|---|---|
| L0 (stroke) | `.l0`, `.stroke`, or a plain `name.funscript` |
| L1 (surge) | `.l1`, `.surge` |
| L2 (sway) | `.l2`, `.sway` |
| R0 (twist) | `.r0`, `.twist` |
| R1 (roll) | `.r1`, `.roll` |
| R2 (pitch) | `.r2`, `.pitch` |
| vib / pump | `.vib`, `.pump` |

## Keyboard shortcuts

| Key | Action |
|---|---|
| `F5` | Preview |
| `Ctrl+S` | Generate & save |
| `Ctrl+O` | Add files |
| `Ctrl+C` | Copy the preview to the clipboard |
| `Ctrl+M` | Merge `.funscript` |

---

## About the merged multi-axis file

The **Merge .funscript** button writes one file that carries every channel:

```json
{
  "version": "1.1",
  "actions": [{ "at": 0, "pos": 70 }, { "at": 250, "pos": 20 }],
  "axes": [
    { "id": "L1", "actions": [{ "at": 0, "pos": 50 }] },
    { "id": "R1", "actions": [{ "at": 0, "pos": 50 }] }
  ],
  "metadata": { "title": "…", "duration": 235.265 }
}
```

- `actions` is the stroke axis (L0, or the first selected axis when L0 is not in the set).
- `axes` holds the other selected channels; ids use the usual `L1` / `L2` / `R0` / `R1` / `R2` names.
- Actions are `{at, pos}` objects and `metadata.duration` is in **seconds** — the layout
  the heatmap web tool and other multi-axis readers expect.
- Only the selected axes are merged, and the original per-axis files are left alone.

---

## FAQ

**The exe is unsigned — is that a problem?**
No. It is a plain PyInstaller build. If SmartScreen complains, *More info → Run anyway*.
If you prefer, you can run it from source: `pip install -r requirements.txt` then
`python app.py`.

**Where are my settings?**
`%APPDATA%\MHeatmap\settings.json`. Delete the file to get the language prompt again.

**The image says "6 axes" but I only see 4 rows.**
Rows follow what was found in the input: missing channels simply do not get a row, and
their pills are disabled. Use the pills if you want fewer rows.

**Transparent PNG looks black in my viewer.**
The PNG really is transparent (`_bg0`). Viewers that ignore alpha show the band's base
colour; drop it on a light or checkered background to confirm.

**The merged file does not play.**
Regenerate it with 1.2.3 or newer — merged files from 1.2.2 and older used the wrong
action layout and load as a script that never moves.

---

## Links

- Source, issues, releases: https://github.com/SillyMeo-1/MHeatmap
- Latest build: https://github.com/SillyMeo-1/MHeatmap/releases/tag/v1.2.3
- License: MIT. Bundled font is Noto Sans CJK SC under the SIL Open Font License.

Feedback and bug reports are welcome — especially odd scripts where the heatmap looks
wrong, since a real file is the best test case.

---

*Posting notes — delete this section before posting:*
*1) Upload `ui-result.png`, `curve-fixed.png`, `first-run-language.png` and
`ui-chinese.png` (all in the `shots` folder) where the four image links are.*
*2) The tables and code block are Markdown and render as-is in the Discourse editor.*
*3) Suggested title: “MHeatmap 1.2.3 — funscript heatmap generator for Windows
(multi-axis, clipboard, single-file merge)”.*
