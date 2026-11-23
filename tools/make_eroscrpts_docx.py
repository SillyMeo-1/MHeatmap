"""Build the EroScripts post document (DOCX) for MHeatmap 1.2.3."""
from __future__ import annotations

import json
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(r"D:\AI自写软件\MHeatmap")
SHOTS = ROOT / "shots"
OUT = ROOT / "docs" / "MHeatmap-1.2.3-EroScripts-post.docx"

GITHUB = "https://github.com/SillyMeo-1/MHeatmap"
RELEASE = "https://github.com/SillyMeo-1/MHeatmap/releases/tag/v1.2.3"

doc = Document()

# ---- base styles
normal = doc.styles["Normal"]
normal.font.name = "Calibri"
normal.font.size = Pt(10.5)
normal.paragraph_format.space_after = Pt(6)
normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")

for name, size in (("Title", 24), ("Heading 1", 15), ("Heading 2", 12.5)):
    style = doc.styles[name]
    style.font.name = "Calibri Light" if name == "Title" else "Calibri"
    style.font.size = Pt(size)
    style.font.color.rgb = RGBColor(0x1F, 0x2A, 0x37)


def para(text: str, *, bold_prefix: str | None = None, size: float | None = None,
         italic: bool = False, space_after: float = 6, style: str | None = None):
    p = doc.add_paragraph(style=style)
    if bold_prefix:
        run = p.add_run(bold_prefix)
        run.bold = True
    run = p.add_run(text)
    if size:
        run.font.size = Pt(size)
    run.italic = italic
    p.paragraph_format.space_after = Pt(space_after)
    return p


def bullets(items: list[str]):
    for item in items:
        p = doc.add_paragraph(style="List Bullet")
        parts = item.split(" — ", 1)
        run = p.add_run(parts[0])
        run.bold = True
        if len(parts) == 2:
            p.add_run(" — " + parts[1])
        p.paragraph_format.space_after = Pt(3)


def numbered(items: list[str]):
    """Manual numbering so each list restarts at 1."""
    for index, item in enumerate(items, 1):
        p = doc.add_paragraph()
        fmt = p.paragraph_format
        fmt.left_indent = Inches(0.32)
        fmt.first_line_indent = Inches(-0.32)
        fmt.space_after = Pt(3)
        p.add_run(f"{index}.")
        p.add_run("\t")
        parts = item.split(" — ", 1)
        run = p.add_run(parts[0])
        run.bold = True
        if len(parts) == 2:
            p.add_run(" — " + parts[1])


def figure(path: Path, caption: str, width: float = 6.2):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(str(path), width=Inches(width))
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.keep_together = True
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = cap.add_run(caption)
    run.italic = True
    run.font.size = Pt(9)
    run.font.color.rgb = RGBColor(0x5A, 0x63, 0x72)


def shade(cell, colour: str):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), colour)
    tc_pr.append(shd)


def table(headers: list[str], rows: list[list[str]], widths: list[float]):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    head = t.rows[0].cells
    for index, text in enumerate(headers):
        head[index].text = ""
        run = head[index].paragraphs[0].add_run(text)
        run.bold = True
        run.font.size = Pt(9.5)
        shade(head[index], "EEF1F5")
    for row in rows:
        cells = t.add_row().cells
        for index, text in enumerate(row):
            cells[index].text = ""
            run = cells[index].paragraphs[0].add_run(text)
            run.font.size = Pt(9.5)
    for row in t.rows:
        for index, width in enumerate(widths):
            row.cells[index].width = Inches(width)
        tr_pr = row._tr.get_or_add_trPr()
        tr_pr.append(OxmlElement("w:cantSplit"))
    header_tr = t.rows[0]._tr.get_or_add_trPr()
    header_tr.append(OxmlElement("w:tblHeader"))
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


# =====================================================================
doc.add_heading("MHeatmap 1.2.3 — Funscript Heatmap Generator (Windows)", level=0)

link_para = doc.add_paragraph()
for label, url in (("GitHub: ", GITHUB), ("   Download: ", RELEASE)):
    run = link_para.add_run(label)
    run.bold = True
    run.font.size = Pt(9.5)
    link = link_para.add_run(url)
    link.font.size = Pt(9.5)
    link.font.color.rgb = RGBColor(0x0B, 0x63, 0xB0)

para("MHeatmap turns .funscript files into a compact heatmap image: one row per axis, "
     "with the filename in a banner, per-axis speed statistics, a colour-coded heat band "
     "and a speed curve underneath. It is a small Windows app — single .exe, no installer, "
     "no Python.")

para("Useful when you want to check a script at a glance: where the fast sections are, "
     "whether a channel is dead, whether two axes line up in time, or which parts of a "
     "14-minute file are worth keeping.")

para("Runs on Windows 10 / 11 (64-bit). Everything happens locally — no script is uploaded "
     "anywhere, and the tool works offline.")

# ---------------------------------------------------------------- screenshots
doc.add_heading("Screenshots", level=1)
figure(SHOTS / "ui-result.png",
       "Main window — one image per script set, every axis on its own row "
       "(L0 / L1 / L2 / R0 / R1 / R2, plus vib / pump when present).")
figure(SHOTS / "curve-fixed.png",
       "Exported PNG — 1380 × 628 for six axes. Heat band on top, speed curve below, "
       "stats on the right.")

# ---------------------------------------------------------------- features
doc.add_heading("Features", level=1)
bullets([
    "One row per axis — L0/L1/L2/R0/R1/R2 plus vib/pump, with the filename banner "
    "(name.surge.funscript::surge) and Duration / Actions / MaxSpeed / AvgSpeed.",
    "Pick the axes — toggle the L0…R2 pills; only the selected axes are drawn and the "
    "image height follows (two axes → 1380 × 212).",
    "Background opacity — 0–100 %. 0 % gives a transparent PNG for overlaying on a "
    "thumbnail or player UI.",
    "Copy image (Ctrl+C) — straight to the clipboard as CF_DIB and PNG, so it pastes into "
    "Paint, Word, a browser or this forum's editor.",
    "Merge to one file (Ctrl+M) — writes a single-file multi-axis .funscript (funscript 1.1: "
    "actions for the stroke, axes for every other channel) without generating any PNG.",
    "Batch — drop a folder, get one image per script set.",
    "English + 中文 UI — English by default; the first launch asks which one you want and "
    "you can switch from the top bar at any time.",
    "Remembers your setup — width, opacity, selected axes, output folder and language live "
    "in %APPDATA%\\MHeatmap\\settings.json.",
])

# ---------------------------------------------------------------- install
doc.add_heading("Download & install", level=1)
numbered([
    "Download — open the release page and grab MHeatmap.zip.",
    "Unpack — anywhere you like, then run MHeatmap.exe.",
    "SmartScreen — Windows may show “Windows protected your PC”; click More info → Run "
    "anyway. That is the normal prompt for a small unsigned app. There is no installer and "
    "nothing is written outside %APPDATA%\\MHeatmap.",
])

# ---------------------------------------------------------------- quick start
doc.add_heading("Quick start", level=1)
figure(SHOTS / "first-run-language.png",
       "First launch — pick English or 中文 once; the choice is remembered.", width=3.6)
numbered([
    "Launch and pick a language.",
    "Add your scripts — drag .funscript files or a folder onto the window, or use Add "
    "files / Add folder. Dropping a single file also pulls in the other axes of the same "
    "script, so one drag gives you the whole set.",
    "Choose the axes — click the L0…R2 pills. Grayed-out pills mean that axis is not in the "
    "current input.",
    "Set the width — default 1380 px; anything from 640 to 4096 works.",
    "Background — 100 % for a solid image, 0 % for a transparent PNG, or anywhere in "
    "between.",
    "Preview (F5) to look at the result, then Generate & save (Ctrl+S) to write the files.",
])
para("Output goes to <script folder>\\heatmaps by default. Change picks another folder, "
     "Auto goes back to the default.")

doc.add_heading("Other things worth knowing", level=2)
bullets([
    "Zoom / pan — mouse wheel to zoom, drag to pan, double-click to fit the preview.",
    "Copy image — puts the current preview on the clipboard, handy for posting a quick "
    "before/after in a thread.",
    "Merge .funscript — only writes the merged script; it does not touch the PNGs.",
    "Drag & drop — accepts several files and folders at once.",
])

figure(SHOTS / "ui-chinese.png",
       "The same window in Chinese — the language can be switched from the top bar.")

# ---------------------------------------------------------------- output
doc.add_heading("Output files", level=1)
table(
    ["File", "When"],
    [
        ["<group>_Axes.png", "solid background (100 %)"],
        ["<group>_Axes_bg<value>.png", "any other opacity, e.g. _Axes_bg50.png; _bg0 is transparent"],
        ["<group>_merged.funscript", "when you press Merge .funscript"],
    ],
    [2.4, 4.2],
)
para("The group name is the common base name of the scripts in the folder.", size=9.5, italic=True)

doc.add_heading("Filename / axis mapping", level=1)
table(
    ["Axis", "Suffix accepted in the filename"],
    [
        ["L0 (stroke)", ".l0, .stroke, or a plain name.funscript"],
        ["L1 (surge)", ".l1, .surge"],
        ["L2 (sway)", ".l2, .sway"],
        ["R0 (twist)", ".r0, .twist"],
        ["R1 (roll)", ".r1, .roll"],
        ["R2 (pitch)", ".r2, .pitch"],
        ["vib / pump", ".vib, .pump"],
    ],
    [1.6, 5.0],
)
para("Scripts in the same folder with the same base name are grouped into one image.",
     size=9.5, italic=True)

doc.add_heading("Keyboard shortcuts", level=1)
table(
    ["Key", "Action"],
    [
        ["F5", "Preview"],
        ["Ctrl+S", "Generate & save"],
        ["Ctrl+O", "Add files"],
        ["Ctrl+C", "Copy the preview to the clipboard"],
        ["Ctrl+M", "Merge .funscript"],
    ],
    [1.4, 5.2],
)

# ---------------------------------------------------------------- merge
doc.add_heading("About the merged multi-axis file", level=1)
para("The Merge .funscript button writes one file that carries every channel:")

code = """{
  "version": "1.1",
  "actions": [{ "at": 0, "pos": 70 }, { "at": 250, "pos": 20 }],
  "axes": [
    { "id": "L1", "actions": [{ "at": 0, "pos": 50 }] },
    { "id": "R1", "actions": [{ "at": 0, "pos": 50 }] }
  ],
  "metadata": { "title": "…", "duration": 235.265 }
}"""
cell = doc.add_table(rows=1, cols=1).rows[0].cells[0]
cell.text = ""
shade(cell, "F4F6F8")
for index, line in enumerate(code.splitlines()):
    p = cell.paragraphs[0] if index == 0 else cell.add_paragraph()
    run = p.add_run(line)
    run.font.name = "Consolas"
    run.font.size = Pt(8.5)
    p.paragraph_format.space_after = Pt(0)

doc.add_paragraph()
bullets([
    "actions — the stroke axis (L0, or the first selected axis when L0 is not in the set).",
    "axes — the other selected channels; ids use the usual L1 / L2 / R0 / R1 / R2 names.",
    "Layout — actions are {at, pos} objects and metadata.duration is in seconds, the "
    "structure multi-axis readers expect.",
    "Non-destructive — only selected axes are merged; the original per-axis files are left alone.",
])

# ---------------------------------------------------------------- FAQ
doc.add_heading("FAQ", level=1)
faq = [
    ("The exe is unsigned — is that a problem?",
     "No. It is a plain PyInstaller build. If SmartScreen complains, More info → Run anyway. "
     "You can also run it from source: pip install -r requirements.txt, then python app.py."),
    ("Where are my settings?",
     "%APPDATA%\\MHeatmap\\settings.json. Delete the file to get the language prompt again."),
    ("The image has fewer rows than six axes.",
     "Rows follow what was found in the input: missing channels get no row and their pills "
     "are disabled. Use the pills if you want fewer rows."),
    ("The transparent PNG looks black in my viewer.",
     "The PNG really is transparent (_bg0). Viewers that ignore alpha show the band's base "
     "colour; drop it on a light or checkered background to confirm."),
    ("The merged file does not play.",
     "Regenerate it with 1.2.3 or newer — merged files from 1.2.2 and older used the wrong "
     "action layout and load as a script that never moves."),
]
for question, answer in faq:
    p = doc.add_paragraph()
    run = p.add_run(question)
    run.bold = True
    p.paragraph_format.space_after = Pt(1)
    para(answer, space_after=8)

# ---------------------------------------------------------------- links
doc.add_heading("Links", level=1)
bullets([
    "Source, issues, releases — " + GITHUB,
    "Latest build — " + RELEASE,
    "License — MIT; the bundled font is Noto Sans CJK SC under the SIL Open Font License.",
])
para("Feedback and bug reports are welcome — especially odd scripts where the heatmap looks "
     "wrong, since a real file is the best test case.")

# ---------------------------------------------------------------- posting notes
doc.add_page_break()
doc.add_heading("Posting notes (delete before posting)", level=1)
bullets([
    "Images — upload ui-result.png, curve-fixed.png, first-run-language.png and "
    "ui-chinese.png from the shots folder where the four figures are.",
    "Formatting — tables and the code block are plain Markdown and render as-is in the "
    "Discourse editor.",
    "Suggested title — “MHeatmap 1.2.3 — funscript heatmap generator for Windows "
    "(multi-axis, clipboard, single-file merge)”.",
    "Suggested tags — funscript, tool, windows, heatmap, multi-axis.",
])

OUT.parent.mkdir(parents=True, exist_ok=True)
doc.save(OUT)
print("saved", OUT, OUT.stat().st_size, "bytes")

# ---- verify
check = Document(OUT)
print("paragraphs:", len(check.paragraphs), "tables:", len(check.tables),
      "inline shapes:", len(check.inline_shapes))
texts = [p.text for p in check.paragraphs]
assert any("GitHub" in t for t in texts)
assert any("Quick start" in t for t in texts)
print("verify ok")
