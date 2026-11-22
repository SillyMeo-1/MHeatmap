#!/usr/bin/env python3
"""MHeatmap — Funscript Heatmap Generator (GUI).

English + 中文 UI, English by default, first launch asks for the language.

Run from source:   py -3 app.py
Self test:         py -3 app.py --selftest <file-or-folder>
"""
from __future__ import annotations

import json
import os
import queue
import random
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import filedialog, ttk

from PIL import Image, ImageDraw, ImageTk

from mheatmap import core
from mheatmap.i18n import DEFAULT_LANGUAGE, LANGUAGES, text

try:  # drag & drop is optional
    from tkinterdnd2 import DND_FILES, TkinterDnD

    HAS_DND = True
except Exception:  # noqa: BLE001
    DND_FILES = None
    TkinterDnD = None
    HAS_DND = False

APP_TITLE = "MHeatmap"
UI_VERSION = "1.0"

# ---------------------------------------------------------------- theme
BG = "#14161a"
PANEL = "#1b1e23"
CARD = "#15171b"
BORDER = "#2e323a"
TEXT = "#e8eaef"
MUTED = "#98a0ab"
DIM = "#767e89"
ACCENT = "#00b6cc"
ACCENT_DARK = "#00798a"
PINK = "#e9308f"
OK = "#4cd7a0"
WARN = "#f4bd4a"
ERR = "#ff7b7b"

FONT_UI = "Segoe UI"
FONT_MONO = "Consolas"
SCALE = 1.0


def px(value: float) -> int:
    return int(round(value * SCALE))


def font(size: int, weight: str = "normal", mono: bool = False) -> tuple:
    return (FONT_MONO if mono else FONT_UI, size, weight)


# ---------------------------------------------------------------- settings
def config_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    folder = Path(base) / "MHeatmap"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "settings.json"


def load_settings() -> dict:
    try:
        with config_path().open("r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(settings: dict) -> None:
    try:
        with config_path().open("w", encoding="utf-8") as handle:
            json.dump(settings, handle, indent=2, ensure_ascii=False)
    except OSError:
        pass


def atomic_save(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(f".mheatmap-{os.getpid()}-{random.randrange(1000)}.png")
    try:
        image.save(pending)
        pending.replace(path)
    finally:
        pending.unlink(missing_ok=True)


def enable_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa: BLE001
        try:
            import ctypes

            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:  # noqa: BLE001
            pass


def register_bundled_font() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        path = core.resource_path(core.BUNDLED_FONT)
        if path.exists():
            ctypes.windll.gdi32.AddFontResourceExW(str(path), 0x10, 0)
    except Exception:  # noqa: BLE001
        pass


def app_icon(size: int = 64) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((1, 1, size - 2, size - 2), radius=size // 5, fill=(21, 23, 27, 255))
    bars = ((213, 126, 18), (16, 196, 53), (53, 153, 154))
    pad = size // 7
    height = max(3, size // 12)
    for index, colour in enumerate(bars):
        top = pad + index * (height + max(2, size // 22))
        draw.rounded_rectangle((pad, top, size - pad, top + height), radius=height // 2, fill=(*colour, 255))
    draw.rounded_rectangle((pad, size - pad - max(2, height // 2), size - pad, size - pad),
                           radius=max(1, height // 4), fill=(236, 47, 160, 255))
    return image


def checkerboard(size, cell: int = 12, light=(88, 90, 98), dark=(52, 54, 60)) -> Image.Image:
    board = Image.new("RGBA", size, (*dark, 255))
    draw = ImageDraw.Draw(board)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if ((x // cell) + (y // cell)) % 2 == 0:
                draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=(*light, 255))
    return board


# ---------------------------------------------------------------- app
class App:
    def __init__(self, root, initial_paths=()):
        self.root = root
        self.settings = load_settings()
        self.lang = self.settings.get("language") or DEFAULT_LANGUAGE
        self.inputs: list[str] = []
        self.width = int(self.settings.get("width") or core.DEFAULT_WIDTH)
        self.transparent = bool(self.settings.get("transparent", False))
        self.out_override = str(self.settings.get("out_dir") or "")
        self.results: list[dict] = []
        self.current = -1
        self.image: Image.Image | None = None
        self.zoom: float | None = None
        self._last_scale = 1.0
        self._photo = None
        self._image_item = None
        self._image_pos = (0.0, 0.0)
        self._drag_origin = None
        self._redraw_job = None
        self._board = None
        self.busy = False
        self.queue: queue.Queue = queue.Queue()

        root.title(APP_TITLE)
        root.configure(bg=BG)
        self._init_scale()
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.report_callback_exception = self._on_tk_error
        try:
            self._icon = ImageTk.PhotoImage(app_icon(px(64)), master=root)
            root.iconphoto(True, self._icon)
        except Exception:  # noqa: BLE001
            self._icon = None

        self._build_style()
        root.withdraw()
        if not self.settings.get("language"):
            self._ask_language()
        self._build()
        if initial_paths:
            self.add_inputs(list(initial_paths))
            if self.inputs:
                root.after(300, self._startup_preview)
        root.deiconify()
        root.after(120, lambda: self.root.focus_force())

    def _startup_preview(self):
        """Opened by dropping a script onto the exe → render it right away."""
        if self.inputs and not self.busy and not self.results:
            self._start(False)

    # ------------------------------------------------------------ setup
    def _init_scale(self):
        global SCALE, FONT_UI, FONT_MONO
        try:
            dpi = float(self.root.winfo_fpixels("1i"))
        except Exception:  # noqa: BLE001
            dpi = 96.0
        SCALE = max(1.0, min(2.0, dpi / 96.0))
        screen_w, screen_h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        width = min(px(1120), screen_w - px(40))
        height = min(px(760), screen_h - px(90))
        left = max(0, (screen_w - width) // 2)
        top = max(px(8), (screen_h - height) // 2 - px(24))
        self.root.geometry(f"{width}x{height}+{left}+{top}")
        self.root.minsize(px(900), px(580))

        families = set(tkfont.families(self.root))
        preferred = ("Microsoft YaHei UI", "Microsoft YaHei") if self.lang == "zh" else ("Segoe UI",)
        for candidate in (*preferred, "Microsoft YaHei UI", "Segoe UI", "Tahoma"):
            if candidate in families:
                FONT_UI = candidate
                break
        for candidate in ("Consolas", "Cascadia Mono", "Courier New"):
            if candidate in families:
                FONT_MONO = candidate
                break

    def _build_style(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:  # noqa: BLE001
            pass
        self.root.option_add("*TCombobox*Listbox.background", PANEL)
        style.configure(".", background=PANEL, foreground=TEXT, fieldbackground=CARD,
                        bordercolor=BORDER, lightcolor=CARD, darkcolor=CARD)
        style.configure("TFrame", background=PANEL)
        style.configure("TLabel", background=PANEL, foreground=TEXT)
        style.configure("Dark.TEntry", fieldbackground=CARD, foreground=TEXT, insertcolor=TEXT,
                        bordercolor=BORDER, lightcolor=CARD, darkcolor=CARD, padding=px(5))
        style.map("Dark.TEntry", bordercolor=[("focus", ACCENT)], foreground=[("disabled", DIM)])
        style.configure("Dark.TCheckbutton", background=PANEL, foreground=TEXT, focuscolor=PANEL,
                        indicatorbackground=CARD, indicatorforeground=TEXT, indicatormargin=px(4))
        style.map("Dark.TCheckbutton", background=[("active", PANEL)],
                  indicatorbackground=[("selected", ACCENT), ("active", CARD)])
        style.configure("Dark.Vertical.TScrollbar", background=CARD, troughcolor=BG,
                        bordercolor=BG, arrowcolor=MUTED, darkcolor=CARD, lightcolor=CARD,
                        width=px(10))
        style.map("Dark.Vertical.TScrollbar", background=[("active", BORDER)])
        style.configure("Dark.Horizontal.TProgressbar", troughcolor=CARD, background=ACCENT,
                        bordercolor=CARD, lightcolor=ACCENT, darkcolor=ACCENT, thickness=px(5))

    # ------------------------------------------------------------ language
    def _ask_language(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("MHeatmap")
        dialog.configure(bg=BG)
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)

        frame = tk.Frame(dialog, bg=BG, padx=px(34), pady=px(26))
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text="MHeatmap", bg=BG, fg=TEXT, font=font(18, "bold")).pack(anchor="w")
        tk.Label(frame, text=text(self.lang, "tagline"), bg=BG, fg=PINK,
                 font=font(10, "bold")).pack(anchor="w", pady=(px(2), px(18)))
        tk.Label(frame, text=f'{text(self.lang, "choose_language")} / 选择语言',
                 bg=BG, fg=TEXT, font=font(11)).pack(anchor="w")
        tk.Label(frame, text=f'{text(self.lang, "choose_hint")} / 之后随时可以在顶部切换。',
                 bg=BG, fg=DIM, font=font(9)).pack(anchor="w", pady=(px(4), px(18)))

        row = tk.Frame(frame, bg=BG)
        row.pack(fill="x")
        for code, label in LANGUAGES:
            tk.Button(row, text=label, command=lambda c=code: self._choose_language(c, dialog),
                      bg=ACCENT if code == DEFAULT_LANGUAGE else PANEL, fg="#04252a" if code == DEFAULT_LANGUAGE else TEXT,
                      activebackground=ACCENT_DARK, activeforeground="#ffffff", bd=0,
                      relief="flat", highlightthickness=0, cursor="hand2",
                      font=font(11, "bold"), padx=px(26), pady=px(9)).pack(side="left", padx=(0, px(10)))

        dialog.update_idletasks()
        width, height = dialog.winfo_reqwidth(), dialog.winfo_reqheight()
        screen_w, screen_h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        dialog.geometry(f"+{(screen_w - width) // 2}+{(screen_h - height) // 2}")
        dialog.grab_set()
        dialog.protocol("WM_DELETE_WINDOW", lambda: self._choose_language(DEFAULT_LANGUAGE, dialog))
        self.root.wait_window(dialog)

    def _choose_language(self, code: str, dialog: tk.Toplevel):
        self.lang = code
        self.settings["language"] = code
        save_settings(self.settings)
        dialog.destroy()

    def _switch_language(self, code: str):
        if code == self.lang:
            return
        self.lang = code
        self.settings["language"] = code
        save_settings(self.settings)
        self._build()
        if self.results:
            self._show(self.current)

    def _t(self, key: str, **kwargs) -> str:
        return text(self.lang, key, **kwargs)

    # ------------------------------------------------------------ layout
    def _build(self):
        for child in self.root.winfo_children():
            child.destroy()
        self._build_style()

        header = tk.Frame(self.root, bg=BG)
        header.pack(side="top", fill="x", padx=px(16), pady=(px(12), px(8)))
        tk.Label(header, text="MHeatmap", bg=BG, fg=TEXT, font=font(16, "bold")).pack(side="left")
        tk.Label(header, text=text(self.lang, "tagline"), bg=BG, fg=PINK,
                 font=font(9, "bold")).pack(side="left", padx=(px(10), 0), pady=(px(5), 0))

        langs = tk.Frame(header, bg=BG)
        langs.pack(side="right")
        for code, label in LANGUAGES:
            active = code == self.lang
            tk.Button(langs, text=label, command=lambda c=code: self._switch_language(c),
                      bg=ACCENT if active else PANEL, fg="#04252a" if active else MUTED,
                      activebackground=ACCENT, activeforeground="#04252a", bd=0, relief="flat",
                      highlightthickness=0, cursor="hand2", font=font(9, "bold" if active else "normal"),
                      padx=px(10), pady=px(3)).pack(side="left", padx=(px(4), 0))

        self.status_var = tk.StringVar(value=text(self.lang, "ready"))
        status = tk.Frame(self.root, bg="#101216")
        status.pack(side="bottom", fill="x")
        tk.Label(status, textvariable=self.status_var, bg="#101216", fg=MUTED, font=font(9),
                 anchor="w").pack(side="left", padx=px(14), pady=px(5))
        tk.Label(status, text=f"MHeatmap {UI_VERSION}", bg="#101216", fg=DIM,
                 font=font(8)).pack(side="right", padx=px(14))
        self.progress = ttk.Progressbar(status, style="Dark.Horizontal.TProgressbar",
                                        length=px(140), mode="determinate")
        self.progress.pack(side="right", padx=px(8), pady=px(5))

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=px(14), pady=(0, px(10)))
        body.grid_columnconfigure(0, minsize=px(330))
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self.sidebar = tk.Frame(body, bg=PANEL)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, px(8)))
        self.preview = tk.Frame(body, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        self.preview.grid(row=0, column=1, sticky="nsew")

        self._build_sidebar()
        self._build_preview()
        self._enable_dnd()
        self._bind_shortcuts()
        self._refresh_list()

    def _build_sidebar(self):
        pad = px(14)
        footer = tk.Frame(self.sidebar, bg=PANEL)
        footer.pack(side="bottom", fill="x")
        tk.Frame(footer, bg=BORDER, height=1).pack(fill="x")
        box = tk.Frame(footer, bg=PANEL)
        box.pack(fill="x", padx=pad, pady=px(9))
        self.preview_button = self._button(box, text(self.lang, "preview"), lambda: self._start(False),
                                           kind="accent", size=10, pady=px(8))
        self.preview_button.pack(side="left", fill="x", expand=True)
        self.save_button = self._button(box, text(self.lang, "save"), lambda: self._start(True),
                                        kind="pink", size=10, pady=px(8))
        self.save_button.pack(side="left", fill="x", expand=True, padx=(px(7), 0))

        self.drop_zone = tk.Frame(self.sidebar, bg=CARD, highlightthickness=1,
                                  highlightbackground=BORDER, height=px(64))
        self.drop_zone.pack(fill="x", padx=pad, pady=(px(12), px(8)))
        self.drop_zone.pack_propagate(False)
        self.drop_hint = tk.Label(self.drop_zone, text=text(self.lang, "drop_hint"),
                                  bg=CARD, fg=MUTED, font=font(9))
        self.drop_hint.pack(expand=True)
        self.drop_sub = tk.Label(self.drop_zone, text=text(self.lang, "drop_sub"),
                                 bg=CARD, fg=DIM, font=font(8))
        self.drop_sub.pack(expand=True)

        row = tk.Frame(self.sidebar, bg=PANEL)
        row.pack(fill="x", padx=pad)
        self._button(row, text(self.lang, "add_files"), self.choose_files).pack(side="left")
        self._button(row, text(self.lang, "add_folder"), self.choose_folder).pack(side="left", padx=(px(6), 0))
        self._button(row, text(self.lang, "clear"), self.clear_inputs, kind="ghost").pack(side="right")

        holder = tk.Frame(self.sidebar, bg=PANEL)
        holder.pack(fill="x", padx=pad, pady=(px(8), 0))
        self.listbox = tk.Listbox(holder, height=5, bg=CARD, fg=TEXT, font=font(9), bd=0,
                                  highlightthickness=1, highlightbackground=BORDER,
                                  selectbackground=ACCENT_DARK, selectforeground="#ffffff",
                                  activestyle="none", exportselection=False)
        self.listbox.pack(side="left", fill="both", expand=True)
        bar = ttk.Scrollbar(holder, orient="vertical", command=self.listbox.yview,
                            style="Dark.Vertical.TScrollbar")
        bar.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=bar.set)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)
        self.listbox.bind("<Double-Button-1>", self._on_open_input)

        self.summary_var = tk.StringVar(value=text(self.lang, "summary_empty"))
        tk.Label(self.sidebar, textvariable=self.summary_var, bg=PANEL, fg=MUTED, font=font(8),
                 anchor="w", justify="left", wraplength=px(300)).pack(fill="x", padx=pad, pady=(px(6), 0))

        tk.Frame(self.sidebar, bg=BORDER, height=1).pack(fill="x", padx=pad, pady=(px(10), 0))
        tk.Label(self.sidebar, text=text(self.lang, "settings"), bg=PANEL, fg=MUTED,
                 font=font(8, "bold")).pack(anchor="w", padx=pad, pady=(px(8), px(4)))

        options = tk.Frame(self.sidebar, bg=PANEL)
        options.pack(fill="x", padx=pad)
        tk.Label(options, text=text(self.lang, "width"), bg=PANEL, fg=MUTED,
                 font=font(8)).pack(side="left")
        self.width_var = tk.StringVar(value=str(self.width))
        ttk.Entry(options, textvariable=self.width_var, style="Dark.TEntry", font=font(9),
                  width=7).pack(side="left", padx=(px(6), px(12)))
        self.transparent_var = tk.BooleanVar(value=self.transparent)
        ttk.Checkbutton(options, text=text(self.lang, "transparent"), variable=self.transparent_var,
                        style="Dark.TCheckbutton").pack(side="left")

        out_row = tk.Frame(self.sidebar, bg=PANEL)
        out_row.pack(fill="x", padx=pad, pady=(px(6), 0))
        tk.Label(out_row, text=text(self.lang, "output"), bg=PANEL, fg=MUTED,
                 font=font(8)).pack(side="left")
        self.out_var = tk.StringVar(value=self._out_text())
        tk.Label(out_row, textvariable=self.out_var, bg=PANEL, fg=TEXT, font=font(8),
                 anchor="w").pack(side="left", padx=(px(6), 0), fill="x", expand=True)
        self._button(out_row, text(self.lang, "change"), self.choose_out_dir, kind="ghost",
                     padx_=px(6), pady=px(1)).pack(side="right")
        self._button(out_row, self._t("reset"), self.reset_out_dir,
                     kind="ghost", padx_=px(6), pady=px(1)).pack(side="right", padx=(0, px(2)))

    def _build_preview(self):
        toolbar = tk.Frame(self.preview, bg=PANEL)
        toolbar.pack(fill="x", padx=px(12), pady=(px(9), px(7)))
        self.zoom_label = tk.Label(toolbar, text="—", bg=PANEL, fg=DIM, font=font(8), width=5)
        self.zoom_label.pack(side="right")
        for label, command in (("100%", lambda: self.set_zoom(1.0)),
                               ("＋", lambda: self.zoom_by(1.25)),
                               (self._t("fit"), self.fit_zoom),
                               ("－", lambda: self.zoom_by(0.8))):
            self._button(toolbar, label, command, kind="ghost", padx_=px(8),
                         pady=px(2)).pack(side="right", padx=(px(4), 0))
        tk.Label(toolbar, text=self._t("zoom_hint"), bg=PANEL, fg=DIM,
                 font=font(8)).pack(side="left")

        holder = tk.Frame(self.preview, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        holder.pack(fill="both", expand=True, padx=px(12))
        self.canvas = tk.Canvas(holder, bg=CARD, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<MouseWheel>", self._on_wheel)

        log_head = tk.Frame(self.preview, bg=PANEL)
        log_head.pack(fill="x", padx=px(12), pady=(px(6), px(3)))
        tk.Label(log_head, text=self._t("log"), bg=PANEL, fg=MUTED,
                 font=font(8, "bold")).pack(side="left")
        self._button(log_head, self._t("clear_log"), self.clear_log, kind="ghost",
                     padx_=px(7), pady=px(1)).pack(side="right")
        self._button(log_head, self._t("open_folder"),
                     self.open_out_dir, kind="ghost", padx_=px(7),
                     pady=px(1)).pack(side="right", padx=(0, px(4)))

        log_holder = tk.Frame(self.preview, bg=PANEL)
        log_holder.pack(fill="x", padx=px(12), pady=(0, px(9)))
        self.log_text = tk.Text(log_holder, height=4, bg=CARD, fg=TEXT, insertbackground=TEXT,
                                bd=0, highlightthickness=1, highlightbackground=BORDER,
                                font=font(9, mono=True), wrap="word", state="disabled",
                                padx=px(8), pady=px(5))
        self.log_text.pack(side="left", fill="both", expand=True)
        log_bar = ttk.Scrollbar(log_holder, orient="vertical", command=self.log_text.yview,
                                style="Dark.Vertical.TScrollbar")
        log_bar.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=log_bar.set)
        for tag, colour in (("info", TEXT), ("dim", DIM), ("ok", OK), ("warn", WARN),
                            ("err", ERR), ("time", DIM)):
            self.log_text.tag_configure(tag, foreground=colour)
        self._draw()

    def _button(self, parent, text_: str, command, kind="normal", size=9, padx_=None, pady=None):
        styles = {
            "normal": dict(bg="#262a31", fg=TEXT,
                           activebackground="#333842", activeforeground=TEXT),
            "accent": dict(bg=ACCENT, fg="#04252a", activebackground="#3fd2e4", activeforeground="#04252a"),
            "pink": dict(bg=PINK, fg="#2b0517", activebackground="#ff5db0", activeforeground="#2b0517"),
            "ghost": dict(bg=PANEL, fg=MUTED, activebackground="#262a31", activeforeground=TEXT),
        }
        options = styles.get(kind, styles["normal"])
        weight = "bold" if kind in ("accent", "pink") else "normal"
        return tk.Button(parent, text=text_, command=command, bd=0, relief="flat",
                         highlightthickness=0, font=font(size, weight), cursor="hand2",
                         padx=px(padx_ if padx_ is not None else 10),
                         pady=px(pady if pady is not None else 4), **options)

    # ------------------------------------------------------------ inputs
    def _enable_dnd(self):
        if not HAS_DND:
            return
        for widget in (self.root, self.canvas, self.drop_zone):
            try:
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", self._on_drop)
                widget.dnd_bind("<<DropEnter>>", lambda _e: self._drop_active(True))
                widget.dnd_bind("<<DropLeave>>", lambda _e: self._drop_active(False))
            except Exception:  # noqa: BLE001
                continue

    def _drop_active(self, active: bool):
        try:
            bg = "#1f2a2d" if active else CARD
            self.drop_zone.configure(bg=bg, highlightbackground=ACCENT if active else BORDER)
            self.drop_hint.configure(bg=bg, fg=TEXT if active else MUTED)
            self.drop_sub.configure(bg=bg)
        except tk.TclError:
            pass

    def _on_drop(self, event):
        try:
            paths = list(self.root.tk.splitlist(event.data))
        except Exception:  # noqa: BLE001
            paths = [str(event.data)]
        self._drop_active(False)
        self.add_inputs(paths)

    def add_inputs(self, paths):
        added, skipped, missing = 0, 0, 0
        known = {item.casefold() for item in self.inputs}
        for raw in paths:
            path = Path(str(raw).strip().strip('"'))
            if path.is_dir() or (path.is_file() and path.suffix.lower() == ".funscript"):
                key = str(path.resolve())
                if key.casefold() in known:
                    continue
                self.inputs.append(key)
                known.add(key.casefold())
                added += 1
            elif not path.exists():
                missing += 1
            else:
                skipped += 1
        self._refresh_list()
        if added:
            self._log(text(self.lang, "added", n=added), "info")
        if skipped:
            self._log(text(self.lang, "skipped", n=skipped), "warn")
        if missing:
            self._log(text(self.lang, "missing", n=missing), "warn")

    def choose_files(self):
        paths = filedialog.askopenfilenames(
            title=".funscript", filetypes=[("Funscript", "*.funscript"), ("All files", "*.*")])
        if paths:
            self.add_inputs(paths)

    def choose_folder(self):
        path = filedialog.askdirectory(title=".funscript")
        if path:
            self.add_inputs([path])

    def clear_inputs(self):
        self.inputs.clear()
        self._refresh_list()

    def _refresh_list(self):
        if hasattr(self, "listbox"):
            self.listbox.delete(0, "end")
            for index, raw in enumerate(self.inputs, 1):
                path = Path(raw)
                kind = "DIR" if path.is_dir() else "FILE"
                self.listbox.insert("end", f"{index:02d}  {kind}  {path.name or path}")
        self._refresh_summary()

    def _refresh_summary(self):
        if not hasattr(self, "summary_var"):
            return
        groups = core.group_files(core.collect_inputs(self.inputs)) if self.inputs else []
        scripts = len(core.collect_inputs(self.inputs)) if self.inputs else 0
        if not self.inputs:
            self.summary_var.set(text(self.lang, "summary_empty"))
        else:
            self.summary_var.set(text(self.lang, "summary", n=len(self.inputs), m=scripts, k=len(groups)))

    def _on_select(self, _event=None):
        selection = self.listbox.curselection()
        if selection and 0 <= selection[0] < len(self.inputs):
            self.status_var.set(self.inputs[selection[0]])

    def _on_open_input(self, _event=None):
        selection = self.listbox.curselection()
        if not selection or not (0 <= selection[0] < len(self.inputs)):
            return
        path = Path(self.inputs[selection[0]])
        folder = path if path.is_dir() else path.parent
        try:
            os.startfile(str(folder))
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------ output dir
    def _first_folder(self) -> Path | None:
        for raw in self.inputs:
            path = Path(raw)
            if path.is_file():
                return path.parent
            if path.is_dir():
                return path
        return None

    def _out_dir(self) -> Path:
        if self.out_override:
            return Path(self.out_override)
        folder = self._first_folder()
        return (folder or Path.cwd()) / "heatmaps"

    def _out_text(self) -> str:
        if self.out_override:
            return self.out_override
        return text(self.lang, "output_auto")

    def choose_out_dir(self):
        path = filedialog.askdirectory(title=text(self.lang, "output"))
        if path:
            self.out_override = path
            self.settings["out_dir"] = path
            save_settings(self.settings)
            self.out_var.set(self._out_text())

    def reset_out_dir(self):
        self.out_override = ""
        self.settings["out_dir"] = ""
        save_settings(self.settings)
        self.out_var.set(self._out_text())

    def open_out_dir(self):
        folder = self._out_dir()
        try:
            if folder.is_dir():
                os.startfile(str(folder))
            else:
                self._log(f"{folder} — not created yet", "warn")
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------ rendering
    def _start(self, save: bool):
        if self.busy:
            return
        if not self.inputs:
            self.status_var.set(text(self.lang, "no_input"))
            self._log(text(self.lang, "no_input"), "warn")
            return
        try:
            width = int(self.width_var.get().strip())
        except ValueError:
            width = -1
        if not core.MIN_WIDTH <= width <= core.MAX_WIDTH:
            message = text(self.lang, "invalid_width", min=core.MIN_WIDTH, max=core.MAX_WIDTH)
            self.status_var.set(message)
            self._log(message, "err")
            return
        self.width = width
        self.transparent = bool(self.transparent_var.get())
        self.settings.update(width=self.width, transparent=self.transparent)
        save_settings(self.settings)

        files = core.collect_inputs(self.inputs)
        if not files:
            self.status_var.set(text(self.lang, "no_scripts"))
            self._log(text(self.lang, "no_scripts"), "warn")
            return
        groups = core.group_files(files)
        out_dir = self._out_dir()

        self.busy = True
        self._sync_buttons()
        self.progress.configure(maximum=max(1, len(groups)), value=0)
        self.status_var.set(text(self.lang, "rendering"))
        thread = threading.Thread(target=self._work, args=(groups, out_dir, save), daemon=True)
        thread.start()
        self.root.after(60, self._poll)

    def _work(self, groups, out_dir: Path, save: bool):
        results = []
        for index, group in enumerate(groups, 1):
            try:
                image = core.render_group(group["axes"], self.width, self.transparent)
                path = None
                if save:
                    name = f"{group['name']}_Axes{'_transparent' if self.transparent else ''}.png"
                    path = out_dir / name
                    atomic_save(image, path)
                results.append({"label": group["label"], "image": image, "path": path, "ok": True})
                self.queue.put(("log", text(self.lang, "done_group",
                                            label=group["label"], name=path.name if path else "preview"), "ok"))
            except Exception as exc:  # noqa: BLE001
                self.queue.put(("log", text(self.lang, "group_failed", label=group["label"], msg=exc), "err"))
                results.append({"label": group["label"], "image": None, "path": None, "ok": False})
            self.queue.put(("progress", index, len(groups)))
        self.queue.put(("done", results, out_dir, save))

    def _poll(self):
        try:
            while True:
                message = self.queue.get_nowait()
                kind = message[0]
                if kind == "log":
                    self._log(message[1], message[2])
                elif kind == "progress":
                    self.progress.configure(maximum=max(1, message[2]), value=message[1])
                elif kind == "done":
                    self._finish(*message[1:])
                    return
        except queue.Empty:
            pass
        if self.busy:
            self.root.after(70, self._poll)

    def _finish(self, results, out_dir: Path, save: bool):
        self.busy = False
        self._sync_buttons()
        self.progress.configure(value=self.progress["maximum"])
        self.results = results
        ok = [item for item in results if item["ok"]]
        if not ok:
            self.status_var.set(text(self.lang, "failed", msg="—"))
            return
        self._show(0)
        if save:
            self.status_var.set(text(self.lang, "saved", n=len(ok), path=out_dir))
        else:
            image = ok[0]["image"]
            self.status_var.set(text(self.lang, "preview_ready", w=image.width, h=image.height))

    def _sync_buttons(self):
        state = "disabled" if self.busy else "normal"
        for button in (getattr(self, "preview_button", None), getattr(self, "save_button", None)):
            if button is not None:
                button.configure(state=state)

    # ------------------------------------------------------------ preview
    def _show(self, index: int):
        if not (0 <= index < len(self.results)):
            return
        self.current = index
        item = self.results[index]
        self.image = item["image"]
        self.zoom = None
        self._draw()

    def _draw(self):
        if not hasattr(self, "canvas"):
            return
        canvas = self.canvas
        canvas.delete("all")
        self._image_item = None
        width = max(canvas.winfo_width(), px(80))
        height = max(canvas.winfo_height(), px(80))
        if self.image is None:
            canvas.create_text(width / 2, height / 2 - px(12), text="MHeatmap",
                               fill=MUTED, font=font(15, "bold"))
            canvas.create_text(width / 2, height / 2 + px(16),
                               text=text(self.lang, "drop_hint"), fill=DIM, font=font(9))
            self.zoom_label.configure(text="—")
            return

        source_w, source_h = self.image.size
        scale = self.zoom if self.zoom is not None else min(
            (width - px(24)) / source_w, (height - px(24)) / source_h, 2.0)
        scale = max(0.01, min(8.0, scale))
        self._last_scale = scale
        target = (max(1, int(round(source_w * scale))), max(1, int(round(source_h * scale))))

        display = self.image
        if self.image.mode == "RGBA" and self.image.getchannel("A").getextrema()[0] < 255:
            if self._board is None or self._board.size != self.image.size:
                self._board = checkerboard(self.image.size)
            display = Image.alpha_composite(self._board, self.image)
        resized = display.resize(target, Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(resized, master=self.root)
        self._image_pos = self._clamp((width - target[0]) / 2, (height - target[1]) / 2)
        self._image_item = canvas.create_image(*self._image_pos, image=self._photo, anchor="nw")
        self.zoom_label.configure(text=f"{round(scale * 100)}%")

    def _clamp(self, x, y):
        view_w, view_h = self.canvas.winfo_width(), self.canvas.winfo_height()
        if self._photo is None:
            return (x, y)
        photo_w, photo_h = self._photo.width(), self._photo.height()
        x = (view_w - photo_w) / 2 if photo_w <= view_w else min(0, max(view_w - photo_w, x))
        y = (view_h - photo_h) / 2 if photo_h <= view_h else min(0, max(view_h - photo_h, y))
        return (x, y)

    def _on_resize(self, _event=None):
        if self._redraw_job is not None:
            self.root.after_cancel(self._redraw_job)
        self._redraw_job = self.root.after(90, self._redraw)

    def _redraw(self):
        self._redraw_job = None
        self._draw()

    def fit_zoom(self):
        self.zoom = None
        self._draw()

    def set_zoom(self, value: float):
        if self.image is None:
            return
        self.zoom = value
        self._draw()

    def zoom_by(self, factor: float):
        if self.image is None:
            return
        self.zoom = max(0.05, min(8.0, (self._last_scale or 1.0) * factor))
        self._draw()

    def _on_wheel(self, event):
        if self.image is None:
            return
        self.zoom_by(1.12 if event.delta > 0 else 1 / 1.12)

    def _on_press(self, event):
        self._drag_origin = (event.x, event.y, self._image_pos[0], self._image_pos[1])

    def _on_drag(self, event):
        if not self._drag_origin or self._image_item is None:
            return
        start_x, start_y, image_x, image_y = self._drag_origin
        self._image_pos = self._clamp(image_x + event.x - start_x, image_y + event.y - start_y)
        self.canvas.coords(self._image_item, *self._image_pos)

    # ------------------------------------------------------------ log / misc
    def _log(self, message: str, level: str = "info"):
        if not hasattr(self, "log_text"):
            return
        stamp = time.strftime("%H:%M:%S")
        widget = self.log_text
        widget.configure(state="normal")
        widget.insert("end", f"[{stamp}] ", "time")
        widget.insert("end", f"{message}\n", level)
        widget.see("end")
        widget.configure(state="disabled")

    def clear_log(self):
        if hasattr(self, "log_text"):
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            self.log_text.configure(state="disabled")

    def _on_tk_error(self, exc_type, exc_value, exc_tb):
        self._log(f"{exc_value}", "err")
        import traceback

        traceback.print_exception(exc_type, exc_value, exc_tb)

    def _bind_shortcuts(self):
        self.root.bind("<F5>", lambda _e: self._start(False))
        self.root.bind("<Control-s>", lambda _e: self._start(True))
        self.root.bind("<Control-o>", lambda _e: self.choose_files())
        self.root.bind("<Control-S>", lambda _e: self._start(True))

    def on_close(self):
        self.root.destroy()


# ---------------------------------------------------------------- cli
def selftest(paths) -> int:
    if not paths:
        print("usage: app.py --selftest <file-or-folder> [...]")
        return 2
    files = core.collect_inputs(paths)
    if not files:
        print("no .funscript files found")
        return 1
    groups = core.group_files(files)
    print(f"files={len(files)} groups={len(groups)}")
    ok = True
    for group in groups:
        image = core.render_group(group["axes"], core.DEFAULT_WIDTH, False)
        alpha = image.convert("RGBA").getchannel("A").getextrema()
        print(f"  {group['label']}: {image.width}x{image.height} alpha={alpha}")
        transparent = core.render_group(group["axes"], core.DEFAULT_WIDTH, True)
        t_alpha = transparent.getchannel("A").getextrema()
        print(f"  transparent: {transparent.width}x{transparent.height} alpha={t_alpha}")
        if not (image.width == core.DEFAULT_WIDTH and alpha[0] == 255 and t_alpha[0] == 0):
            ok = False
    print("selftest", "OK" if ok else "FAILED")
    return 0 if ok else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--selftest" in argv:
        argv.remove("--selftest")
        return selftest(argv)
    if "--version" in argv:
        print(f"MHeatmap {UI_VERSION}")
        return 0

    enable_dpi_awareness()
    register_bundled_font()
    try:
        root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
    except Exception:  # noqa: BLE001
        root = tk.Tk()
    App(root, argv)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
