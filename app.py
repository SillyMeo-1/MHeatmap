#!/usr/bin/env python3
"""MHeatmap — Funscript Heatmap Generator (GUI).

English + 中文 UI, English by default, first launch asks for the language.

    py -3 app.py
    py -3 app.py --selftest <file-or-folder>
"""
from __future__ import annotations

import ctypes
import json
import os
import queue
import random
import struct
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from io import BytesIO
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
UI_VERSION = "1.2.1"

# ---------------------------------------------------------------- theme
BG = "#0e1116"
SURFACE = "#151922"
CARD = "#1b2029"
CARD_HOVER = "#232a35"
FIELD = "#141922"
BORDER = "#2a3140"
TEXT = "#e8ecf3"
MUTED = "#97a1b2"
DIM = "#6b7484"
ACCENT = "#5eead4"
ACCENT_HOVER = "#8ff5e4"
ACCENT_PRESS = "#3ecbb6"
ACCENT_TEXT = "#06231f"
WARM = "#f472b6"
WARM_HOVER = "#f795c8"
WARM_PRESS = "#d9559a"
WARM_TEXT = "#29071a"
OK = "#4ade80"
WARN = "#fbbf24"
ERR = "#f87171"
CANVAS_BG = "#0b0e13"
SELECT_BG = "#0f6f63"

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


def copy_image_to_clipboard(image: Image.Image) -> bool:
    """Put the image on the Windows clipboard as CF_DIB plus a PNG flavour."""
    if sys.platform != "win32":
        return False
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    user32.RegisterClipboardFormatW.restype = wintypes.UINT
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]

    rgba = image.convert("RGBA")
    width, height = rgba.size
    background = Image.new("RGBA", rgba.size, (14, 17, 22, 255))
    flat = Image.alpha_composite(background, rgba)
    pixels = flat.tobytes()

    header = struct.pack("<IiiHHIIiiII", 40, width, height, 1, 32, 0, 0, 0, 0, 0, 0)
    rows = []
    stride = width * 4
    for y in range(height - 1, -1, -1):
        row = pixels[y * stride:(y + 1) * stride]
        converted = bytearray(stride)
        converted[0::4] = row[2::4]
        converted[1::4] = row[1::4]
        converted[2::4] = row[0::4]
        converted[3::4] = b"\xff" * width
        rows.append(bytes(converted))
    dib = header + b"".join(rows)

    png_buffer = BytesIO()
    rgba.save(png_buffer, format="PNG")
    png_bytes = png_buffer.getvalue()

    GMEM_MOVEABLE, CF_DIB = 0x0002, 8

    def global_block(data: bytes):
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not handle:
            return None
        pointer = kernel32.GlobalLock(handle)
        ctypes.memmove(pointer, data, len(data))
        kernel32.GlobalUnlock(handle)
        return handle

    if not user32.OpenClipboard(None):
        return False
    ok = False
    try:
        user32.EmptyClipboard()
        handle = global_block(dib)
        if handle and user32.SetClipboardData(CF_DIB, handle):
            ok = True
        png_format = user32.RegisterClipboardFormatW("PNG")
        if png_format:
            png_handle = global_block(png_bytes)
            if png_handle:
                user32.SetClipboardData(png_format, png_handle)
    finally:
        user32.CloseClipboard()
    return ok


def enable_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:  # noqa: BLE001
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:  # noqa: BLE001
            pass


def register_bundled_font() -> None:
    if sys.platform != "win32":
        return
    try:
        path = core.resource_path(core.BUNDLED_FONT)
        if path.exists():
            ctypes.windll.gdi32.AddFontResourceExW(str(path), 0x10, 0)
    except Exception:  # noqa: BLE001
        pass


def app_icon(size: int = 64) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((1, 1, size - 2, size - 2), radius=size // 5, fill=(21, 25, 34, 255))
    bars = ((213, 126, 18), (16, 196, 53), (53, 153, 154))
    pad = size // 7
    height = max(3, size // 12)
    for index, colour in enumerate(bars):
        top = pad + index * (height + max(2, size // 22))
        draw.rounded_rectangle((pad, top, size - pad, top + height), radius=height // 2,
                               fill=(*colour, 255))
    draw.rounded_rectangle((pad, size - pad - max(2, height // 2), size - pad, size - pad),
                           radius=max(1, height // 4), fill=(244, 114, 182, 255))
    return image


def checkerboard(size, cell: int = 12, light=(88, 90, 98), dark=(52, 54, 60)) -> Image.Image:
    board = Image.new("RGBA", size, (*dark, 255))
    draw = ImageDraw.Draw(board)
    for y in range(0, size[1], cell):
        for x in range(0, size[0], cell):
            if ((x // cell) + (y // cell)) % 2 == 0:
                draw.rectangle((x, y, x + cell - 1, y + cell - 1), fill=(*light, 255))
    return board


# ---------------------------------------------------------------- widgets
def rounded_rect(canvas: tk.Canvas, x1, y1, x2, y2, radius, **kwargs):
    points = [
        x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
        x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
        x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


class Pill(tk.Canvas):
    """Rounded button / toggle with hover and press feedback."""

    KINDS = {
        "primary": dict(fill=ACCENT, hover=ACCENT_HOVER, press=ACCENT_PRESS, fg=ACCENT_TEXT),
        "warm": dict(fill=WARM, hover=WARM_HOVER, press=WARM_PRESS, fg=WARM_TEXT),
        "plain": dict(fill="#2a3342", hover="#354052", press="#212836", fg=TEXT),
        "soft": dict(fill="#232c3a", hover="#2d3847", press="#1c2430", fg=MUTED),
        "ghost": dict(fill="#1f2733", hover="#2a3342", press="#1a212b", fg=MUTED),
        "on": dict(fill=ACCENT, hover=ACCENT_HOVER, press=ACCENT_PRESS, fg=ACCENT_TEXT),
    }

    def __init__(self, master, text_, command=None, kind="plain", font_=None,
                 width=120, height=34, radius=None):
        self._host_bg = master.cget("bg")
        super().__init__(master, width=width, height=height, bg=self._host_bg,
                         highlightthickness=0, bd=0, cursor="hand2")
        self._command = command
        self._kind = kind
        self._label = text_
        self._font = font_ or font(9, "bold")
        self._radius = radius if radius is not None else max(6, height // 3)
        self._enabled = True
        self._hover = False
        self._pressed = False
        self._draw()
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    # ---- public
    def set_label(self, value: str):
        self._label = value
        self._draw()

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
        self.configure(cursor="hand2" if enabled else "")
        self._draw()

    def set_kind(self, kind: str):
        self._kind = kind
        self._draw()

    def set_selected(self, selected: bool, text_: str | None = None):
        self._kind = "on" if selected else "plain"
        if text_ is not None:
            self._label = text_
        self._draw()

    # ---- drawing
    def _draw(self):
        self.delete("all")
        width = int(float(self["width"]))
        height = int(float(self["height"]))
        spec = self.KINDS.get(self._kind, self.KINDS["plain"])
        if not self._enabled:
            fill = "#20262f" if self._kind in ("plain", "ghost", "soft") else "#20303a"
            label_colour = DIM
        elif self._pressed:
            fill, label_colour = spec["press"], spec["fg"]
        elif self._hover:
            fill, label_colour = spec["hover"], spec["fg"]
        else:
            fill, label_colour = spec["fill"], spec["fg"]
        pad = 1 if self._kind in ("plain", "soft", "ghost") else 0
        rounded_rect(self, 0.5 + pad, 0.5 + pad, width - 0.5 - pad, height - 0.5 - pad,
                     self._radius, fill=fill, outline="")
        self.create_text(width / 2, height / 2 - 0.5, text=self._label,
                         fill=label_colour, font=self._font)

    # ---- events
    def _on_enter(self, _event=None):
        if not self._enabled:
            return
        self._hover = True
        self._draw()

    def _on_leave(self, _event=None):
        self._hover = False
        self._pressed = False
        self._draw()

    def _on_press(self, _event=None):
        if not self._enabled:
            return
        self._pressed = True
        self._draw()

    def _on_release(self, event=None):
        if not self._enabled:
            return
        was_pressed = self._pressed
        self._pressed = False
        self._draw()
        inside = True
        if event is not None:
            inside = 0 <= event.x <= int(float(self["width"])) and 0 <= event.y <= int(float(self["height"]))
        if was_pressed and inside and self._command:
            self._command()


class Toast:
    """Small message bubble over the preview area."""

    def __init__(self, root: tk.Misc):
        self.root = root
        self.label = tk.Label(root, text="", font=font(9, "bold"), bd=0,
                              padx=px(14), pady=px(8))
        self._job = None

    def show(self, message: str, kind: str = "info"):
        colours = {
            "info": (CARD, TEXT),
            "ok": ("#123222", OK),
            "warn": ("#3a2c12", WARN),
            "err": ("#3a1a1a", ERR),
        }
        bg, fg = colours.get(kind, colours["info"])
        self.label.configure(text=message, bg=bg, fg=fg)
        self.label.place(relx=0.985, rely=0.97, anchor="se")
        self.label.lift()
        if self._job:
            self.root.after_cancel(self._job)
        self._job = self.root.after(2400, self.hide)

    def hide(self):
        self._job = None
        self.label.place_forget()


# ---------------------------------------------------------------- app
class App:
    def __init__(self, root, initial_paths=()):
        self.root = root
        self.settings = load_settings()
        self.lang = self.settings.get("language") or DEFAULT_LANGUAGE
        self.inputs: list[str] = []
        self.width = int(self.settings.get("width") or core.DEFAULT_WIDTH)
        legacy_alpha = 0 if self.settings.get("transparent") else 100
        self.bg_opacity = int(self.settings.get("bg_opacity", legacy_alpha))
        stored_axes = self.settings.get("axes")
        self.axes_enabled = (set(stored_axes) if isinstance(stored_axes, list)
                             else {axis[0] for axis in core.AXES})
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
        self._pulse_job = None
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
        if self.inputs and not self.busy and not self.results:
            self._start("preview")

    # ------------------------------------------------------------ setup
    def _init_scale(self):
        global SCALE, FONT_UI, FONT_MONO
        try:
            dpi = float(self.root.winfo_fpixels("1i"))
        except Exception:  # noqa: BLE001
            dpi = 96.0
        SCALE = max(1.0, min(2.0, dpi / 96.0))
        screen_w, screen_h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        width = min(px(1160), screen_w - px(40))
        height = min(px(780), screen_h - px(90))
        left = max(0, (screen_w - width) // 2)
        top = max(px(8), (screen_h - height) // 2 - px(24))
        self.root.geometry(f"{width}x{height}+{left}+{top}")
        self.root.minsize(px(960), px(620))

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
        self.root.option_add("*TCombobox*Listbox.background", CARD)
        self.root.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.root.option_add("*TCombobox*Listbox.selectForeground", ACCENT_TEXT)

        style.configure(".", background=SURFACE, foreground=TEXT, fieldbackground=FIELD,
                        bordercolor=BORDER, lightcolor=FIELD, darkcolor=FIELD)
        style.configure("TFrame", background=SURFACE)
        style.configure("TLabel", background=SURFACE, foreground=TEXT)
        style.configure("Dark.TEntry", fieldbackground=FIELD, foreground=TEXT, insertcolor=ACCENT,
                        bordercolor=BORDER, lightcolor=FIELD, darkcolor=FIELD, padding=px(5))
        style.map("Dark.TEntry", bordercolor=[("focus", ACCENT)],
                  lightcolor=[("focus", ACCENT)], foreground=[("disabled", DIM)])
        style.configure("Dark.Vertical.TScrollbar", background=CARD, troughcolor=SURFACE,
                        bordercolor=SURFACE, arrowcolor=MUTED, darkcolor=CARD, lightcolor=CARD,
                        width=px(9))
        style.map("Dark.Vertical.TScrollbar", background=[("active", CARD_HOVER)])
        style.configure("Dark.Horizontal.TProgressbar", troughcolor=FIELD, background=ACCENT,
                        bordercolor=FIELD, lightcolor=ACCENT, darkcolor=ACCENT, thickness=px(4))
        style.configure("Dark.Horizontal.TScale", background=CARD, troughcolor=FIELD,
                        bordercolor=CARD, lightcolor=ACCENT, darkcolor=ACCENT)

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
        tk.Label(frame, text=text(self.lang, "tagline"), bg=BG, fg=ACCENT,
                 font=font(10, "bold")).pack(anchor="w", pady=(px(2), px(18)))
        tk.Label(frame, text=f'{text(self.lang, "choose_language")} / 选择语言',
                 bg=BG, fg=TEXT, font=font(11)).pack(anchor="w")
        tk.Label(frame, text=f'{text(self.lang, "choose_hint")} / 之后随时可以在顶部切换。',
                 bg=BG, fg=DIM, font=font(9)).pack(anchor="w", pady=(px(4), px(18)))

        row = tk.Frame(frame, bg=BG)
        row.pack(fill="x")
        for code, label in LANGUAGES:
            Pill(row, label, lambda c=code: self._choose_language(c, dialog),
                 kind="primary" if code == DEFAULT_LANGUAGE else "plain",
                 font_=font(11, "bold"), width=px(124), height=px(40),
                 radius=px(10)).pack(side="left", padx=(0, px(10)))

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
        self._build_header()
        self._build_status_bar()

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=px(14), pady=(0, px(10)))
        body.grid_columnconfigure(0, minsize=px(350))
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self.sidebar = tk.Frame(body, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        self.sidebar.grid(row=0, column=0, sticky="nsew", padx=(0, px(10)))
        self.preview = tk.Frame(body, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        self.preview.grid(row=0, column=1, sticky="nsew")

        self._build_sidebar()
        self._build_preview()
        self._enable_dnd()
        self._bind_shortcuts()
        self._refresh_list()
        self.root.after(60, self._focus_canvas)

    def _focus_canvas(self):
        try:
            self.canvas.focus_set()
        except Exception:  # noqa: BLE001
            pass

    def _build_header(self):
        header = tk.Frame(self.root, bg=BG)
        header.pack(side="top", fill="x", padx=px(18), pady=(px(12), px(10)))

        mark = tk.Canvas(header, width=px(28), height=px(28), bg=BG, highlightthickness=0, bd=0)
        mark.pack(side="left", padx=(0, px(10)))
        rounded_rect(mark, 1, 1, px(27), px(27), px(7), fill=CARD, outline=BORDER)
        for index, colour in enumerate(((213, 126, 18), (16, 196, 53), (53, 153, 154))):
            y = px(7) + index * px(5)
            mark.create_rectangle(px(7), y, px(21), y + px(3), fill="#{:02x}{:02x}{:02x}".format(*colour), width=0)

        tk.Label(header, text="MHeatmap", bg=BG, fg=TEXT, font=font(16, "bold")).pack(side="left")
        tk.Label(header, text=self._t("tagline"), bg=BG, fg=ACCENT,
                 font=font(9, "bold")).pack(side="left", padx=(px(10), 0), pady=(px(5), 0))

        langs = tk.Frame(header, bg=BG)
        langs.pack(side="right")
        for code, label in LANGUAGES:
            selected = code == self.lang
            pill = Pill(langs, label, lambda c=code: self._switch_language(c),
                        kind="on" if selected else "ghost",
                        font_=font(9, "bold" if selected else "normal"),
                        width=px(74), height=px(28), radius=px(8))
            pill.pack(side="left", padx=(px(4), 0))

    def _build_status_bar(self):
        bar = tk.Frame(self.root, bg="#0a0d12", height=px(30))
        bar.pack(side="bottom", fill="x")
        bar.pack_propagate(False)

        self.status_dot = tk.Canvas(bar, width=px(16), height=px(16), bg="#0a0d12",
                                    highlightthickness=0, bd=0)
        self.status_dot.pack(side="left", padx=(px(16), px(2)), pady=px(6))
        self._dot_item = self.status_dot.create_oval(px(4), px(4), px(12), px(12),
                                                     fill=DIM, outline="")

        self.status_var = tk.StringVar(value=self._t("ready"))
        tk.Label(bar, textvariable=self.status_var, bg="#0a0d12", fg=MUTED,
                 font=font(9)).pack(side="left")

        tk.Label(bar, text=f"MHeatmap {UI_VERSION}", bg="#0a0d12", fg=DIM,
                 font=font(8)).pack(side="right", padx=px(16))
        self.progress = ttk.Progressbar(bar, style="Dark.Horizontal.TProgressbar",
                                        length=px(150), mode="determinate")
        self.progress.pack(side="right", padx=px(10), pady=px(10))

    # ------------------------------------------------------------ sidebar
    def _card(self, parent, title: str | None = None, top: int = 10):
        outer = tk.Frame(parent, bg=SURFACE)
        outer.pack(fill="x", padx=px(12), pady=(px(top), 0))
        card = tk.Frame(outer, bg=CARD)
        card.pack(fill="x")
        inner = tk.Frame(card, bg=CARD)
        inner.pack(fill="x", padx=px(12), pady=px(10))
        head = None
        if title:
            head = tk.Frame(inner, bg=CARD)
            head.pack(fill="x", pady=(0, px(6)))
            tk.Label(head, text=title, bg=CARD, fg=MUTED,
                     font=font(8, "bold")).pack(side="left")
        return inner, head

    def _build_sidebar(self):
        # -------- drop zone
        holder = tk.Frame(self.sidebar, bg=SURFACE)
        holder.pack(fill="x", padx=px(12), pady=(px(12), 0))
        self.drop_zone = tk.Canvas(holder, height=px(78), bg=SURFACE,
                                   highlightthickness=0, bd=0, cursor="hand2")
        self.drop_zone.pack(fill="x")
        self._drop_rect = rounded_rect(self.drop_zone, 1, 1, 1, 1, px(10), fill=FIELD, outline=BORDER)
        self.drop_hint = self.drop_zone.create_text(0, 0, text=self._t("drop_hint"),
                                                    fill=MUTED, font=font(9, "bold"))
        self.drop_sub = self.drop_zone.create_text(0, 0, text=self._t("drop_sub"),
                                                   fill=DIM, font=font(8))
        self.drop_zone.bind("<Configure>", self._layout_drop_zone)
        self.drop_zone.bind("<Enter>", lambda _e: self._drop_hover(True))
        self.drop_zone.bind("<Leave>", lambda _e: self._drop_hover(False))

        # -------- inputs
        inner, head = self._card(self.sidebar, self._t("inputs"), top=10)
        self.input_count = tk.Label(head, text="", bg=CARD, fg=DIM, font=font(8))
        self.input_count.pack(side="right")

        listbox_holder = tk.Frame(inner, bg=FIELD, highlightthickness=1, highlightbackground=BORDER)
        listbox_holder.pack(fill="x")
        self.listbox = tk.Listbox(listbox_holder, height=4, bg=FIELD, fg=TEXT, font=font(9), bd=0,
                                  highlightthickness=0, selectbackground=SELECT_BG,
                                  selectforeground="#ffffff", activestyle="none", exportselection=False)
        self.listbox.pack(side="left", fill="both", expand=True, padx=px(4), pady=px(3))
        bar = ttk.Scrollbar(listbox_holder, orient="vertical", command=self.listbox.yview,
                            style="Dark.Vertical.TScrollbar")
        bar.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=bar.set)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)
        self.listbox.bind("<Double-Button-1>", self._on_open_input)

        self.summary_var = tk.StringVar(value=self._t("summary_empty"))
        tk.Label(inner, textvariable=self.summary_var, bg=CARD, fg=DIM, font=font(8),
                 anchor="w", justify="left", wraplength=px(290)).pack(fill="x", pady=(px(6), px(6)))

        row = tk.Frame(inner, bg=CARD)
        row.pack(fill="x")
        Pill(row, self._t("add_files"), self.choose_files, kind="plain",
             font_=font(8, "bold"), width=px(86), height=px(26), radius=px(7)).pack(side="left")
        Pill(row, self._t("add_folder"), self.choose_folder, kind="plain",
             font_=font(8, "bold"), width=px(96), height=px(26), radius=px(7)).pack(side="left", padx=(px(6), 0))
        Pill(row, self._t("clear"), self.clear_inputs, kind="ghost",
             font_=font(8), width=px(56), height=px(26), radius=px(7)).pack(side="right")

        # -------- axes
        inner, head = self._card(self.sidebar, self._t("axes"), top=10)
        self.axes_hint = tk.Label(head, text="", bg=CARD, fg=DIM, font=font(8))
        self.axes_hint.pack(side="right")

        grid = tk.Frame(inner, bg=CARD)
        grid.pack(fill="x")
        self.axis_pills = {}
        for index, (axis_name, colour, _tokens) in enumerate(core.AXES):
            pill = Pill(grid, axis_name, lambda name=axis_name: self._toggle_axis(name),
                        kind="plain", font_=font(8, "bold"), width=px(46), height=px(26), radius=px(7))
            row_index, column = divmod(index, 6)
            pill.grid(row=row_index, column=column, padx=(0, px(4)), pady=(0, px(4)), sticky="w")
            self.axis_pills[axis_name] = pill

        # -------- settings
        inner, head = self._card(self.sidebar, self._t("settings"), top=10)

        width_row = tk.Frame(inner, bg=CARD)
        width_row.pack(fill="x", pady=(0, px(8)))
        tk.Label(width_row, text=self._t("width"), bg=CARD, fg=MUTED, font=font(8),
                 width=9, anchor="w").pack(side="left")
        self.width_var = tk.StringVar(value=str(self.width))
        ttk.Entry(width_row, textvariable=self.width_var, style="Dark.TEntry",
                  font=font(9), width=8).pack(side="left")

        opacity_row = tk.Frame(inner, bg=CARD)
        opacity_row.pack(fill="x", pady=(0, px(8)))
        tk.Label(opacity_row, text=self._t("bg_opacity"), bg=CARD, fg=MUTED, font=font(8),
                 width=9, anchor="w").pack(side="left")
        self.opacity_var = tk.DoubleVar(value=self.bg_opacity)
        self.opacity_scale = ttk.Scale(opacity_row, from_=0, to=100, orient="horizontal",
                                       variable=self.opacity_var, style="Dark.Horizontal.TScale",
                                       command=self._on_opacity)
        self.opacity_scale.pack(side="left", fill="x", expand=True)
        self.opacity_label = tk.Label(opacity_row, text=f"{self.bg_opacity}%", bg=CARD, fg=TEXT,
                                      font=font(8, "bold"), width=4, anchor="e")
        self.opacity_label.pack(side="right")

        out_row = tk.Frame(inner, bg=CARD)
        out_row.pack(fill="x")
        tk.Label(out_row, text=self._t("output"), bg=CARD, fg=MUTED, font=font(8),
                 width=9, anchor="w").pack(side="left")
        self.out_var = tk.StringVar(value=self._out_text())
        tk.Label(out_row, textvariable=self.out_var, bg=CARD, fg=TEXT, font=font(8),
                 anchor="w").pack(side="left", fill="x", expand=True)
        Pill(out_row, self._t("change"), self.choose_out_dir, kind="ghost",
             font_=font(8), width=px(52), height=px(24), radius=px(6)).pack(side="right")
        Pill(out_row, self._t("reset"), self.reset_out_dir, kind="ghost",
             font_=font(8), width=px(46), height=px(24), radius=px(6)).pack(side="right", padx=(0, px(4)))

        # -------- actions (fixed at the bottom)
        footer = tk.Frame(self.sidebar, bg=SURFACE)
        footer.pack(side="bottom", fill="x")
        tk.Frame(footer, bg=BORDER, height=1).pack(fill="x")
        actions = tk.Frame(footer, bg=SURFACE)
        actions.pack(fill="x", padx=px(12), pady=px(10))
        actions.grid_columnconfigure(0, weight=1)
        actions.grid_columnconfigure(1, weight=1)

        self.preview_button = Pill(actions, self._t("preview"), lambda: self._start("preview"),
                                   kind="plain", font_=font(10, "bold"),
                                   width=px(148), height=px(38), radius=px(9))
        self.preview_button.grid(row=0, column=0, sticky="ew", padx=(0, px(5)))
        self.save_button = Pill(actions, self._t("save"), lambda: self._start("save"),
                                kind="primary", font_=font(10, "bold"),
                                width=px(148), height=px(38), radius=px(9))
        self.save_button.grid(row=0, column=1, sticky="ew", padx=(px(5), 0))

        self.copy_button = Pill(actions, self._t("copy"), self.copy_image, kind="soft",
                                font_=font(9), width=px(148), height=px(30), radius=px(8))
        self.copy_button.grid(row=1, column=0, sticky="ew", padx=(0, px(5)), pady=(px(7), 0))
        self.merge_button = Pill(actions, self._t("merge"), lambda: self._start("merge"),
                                 kind="soft", font_=font(9), width=px(148), height=px(30), radius=px(8))
        self.merge_button.grid(row=1, column=1, sticky="ew", padx=(px(5), 0), pady=(px(7), 0))

    def _layout_drop_zone(self, event=None):
        width = self.drop_zone.winfo_width()
        height = self.drop_zone.winfo_height()
        if width <= 4 or height <= 4:
            return
        self.drop_zone.coords(self._drop_rect, *self._rounded_points(1, 1, width - 1, height - 1, px(10)))
        self.drop_zone.coords(self.drop_hint, width / 2, height / 2 - px(9))
        self.drop_zone.coords(self.drop_sub, width / 2, height / 2 + px(12))

    @staticmethod
    def _rounded_points(x1, y1, x2, y2, radius):
        return [
            x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
            x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
            x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
        ]

    def _drop_hover(self, active: bool, drop: bool = False):
        if not hasattr(self, "drop_zone") or not self.drop_zone.winfo_exists():
            return
        fill = "#1c2b32" if active else FIELD
        outline = ACCENT if active else BORDER
        self.drop_zone.itemconfigure(self._drop_rect, fill=fill, outline=outline)
        if drop:
            self.drop_zone.itemconfigure(self.drop_hint, text=self._t("drop_release"), fill=ACCENT)
        else:
            self.drop_zone.itemconfigure(self.drop_hint, text=self._t("drop_hint"),
                                         fill=TEXT if active else MUTED)
        self.drop_zone.itemconfigure(self.drop_sub, fill=MUTED if active else DIM)

    # ------------------------------------------------------------ preview
    def _build_preview(self):
        toolbar = tk.Frame(self.preview, bg=SURFACE)
        toolbar.pack(fill="x", padx=px(12), pady=(px(10), px(8)))

        self.zoom_label = tk.Label(toolbar, text="—", bg=SURFACE, fg=DIM, font=font(8, "bold"),
                                   width=5)
        self.zoom_label.pack(side="right", padx=(px(6), 0))
        for label, command in (("100%", lambda: self.set_zoom(1.0)),
                               ("＋", lambda: self.zoom_by(1.25)),
                               (self._t("fit"), self.fit_zoom),
                               ("－", lambda: self.zoom_by(0.8))):
            Pill(toolbar, label, command, kind="ghost", font_=font(8),
                 width=px(34) if len(label) <= 1 else px(52), height=px(24),
                 radius=px(6)).pack(side="right", padx=(px(4), 0))

        Pill(toolbar, self._t("open_folder"), self.open_out_dir, kind="ghost", font_=font(8),
             width=px(88), height=px(24), radius=px(6)).pack(side="left", padx=(px(10), 0))
        Pill(toolbar, self._t("clear_log"), self.clear_log, kind="ghost", font_=font(8),
             width=px(52), height=px(24), radius=px(6)).pack(side="left", padx=(px(4), 0))
        tk.Label(toolbar, text=self._t("zoom_hint"), bg=SURFACE, fg=DIM,
                 font=font(8)).pack(side="left", padx=(px(12), 0))

        holder = tk.Frame(self.preview, bg=CANVAS_BG, highlightthickness=1, highlightbackground=BORDER)
        holder.pack(fill="both", expand=True, padx=px(12))
        self.canvas = tk.Canvas(holder, bg=CANVAS_BG, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Double-Button-1>", lambda _e: self.fit_zoom())

        log_holder = tk.Frame(self.preview, bg=SURFACE)
        log_holder.pack(fill="x", padx=px(12), pady=(px(8), px(10)))
        self.log_text = tk.Text(log_holder, height=4, bg=FIELD, fg=MUTED, insertbackground=TEXT,
                                bd=0, highlightthickness=1, highlightbackground=BORDER,
                                font=font(9, mono=True), wrap="word", state="disabled",
                                padx=px(9), pady=px(6))
        self.log_text.pack(side="left", fill="both", expand=True)
        log_bar = ttk.Scrollbar(log_holder, orient="vertical", command=self.log_text.yview,
                                style="Dark.Vertical.TScrollbar")
        log_bar.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=log_bar.set)
        for tag, colour in (("info", TEXT), ("dim", DIM), ("ok", OK), ("warn", WARN),
                            ("err", ERR), ("time", DIM)):
            self.log_text.tag_configure(tag, foreground=colour)

        self.toast = Toast(self.preview)
        self._draw()

    # ------------------------------------------------------------ drag & drop
    def _enable_dnd(self):
        if not HAS_DND:
            return
        for widget in (self.root, self.drop_zone, self.canvas):
            try:
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", self._on_drop)
                widget.dnd_bind("<<DropEnter>>", lambda _e: self._drop_hover(True, drop=True))
                widget.dnd_bind("<<DropLeave>>", lambda _e: self._drop_hover(False))
            except Exception:  # noqa: BLE001
                continue

    def _on_drop(self, event):
        try:
            paths = list(self.root.tk.splitlist(event.data))
        except Exception:  # noqa: BLE001
            paths = [str(event.data)]
        self._drop_hover(False)
        self.add_inputs(paths)

    # ------------------------------------------------------------ inputs
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
            self._log(self._t("added", n=added), "info")
        if skipped:
            self._log(self._t("skipped", n=skipped), "warn")
        if missing:
            self._log(self._t("missing", n=missing), "warn")

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
        self.results = []
        self.image = None
        self.current = -1
        self._refresh_list()
        self._draw()

    def _refresh_list(self):
        if not hasattr(self, "listbox"):
            return
        self.listbox.delete(0, "end")
        for index, raw in enumerate(self.inputs, 1):
            path = Path(raw)
            kind = "DIR " if path.is_dir() else "FILE"
            self.listbox.insert("end", f"{index:02d}  {kind}  {path.name or path}")
        self._refresh_summary()

    def _refresh_summary(self):
        if not hasattr(self, "summary_var"):
            return
        files = core.collect_inputs(self.inputs) if self.inputs else []
        groups = core.group_files(files) if files else []
        if not self.inputs:
            self.summary_var.set(self._t("summary_empty"))
        else:
            self.summary_var.set(self._t("summary", n=len(self.inputs), m=len(files), k=len(groups)))
        if hasattr(self, "input_count"):
            self.input_count.configure(text=str(len(self.inputs)) if self.inputs else "")
        self._refresh_axis_pills()

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

    # ------------------------------------------------------------ axes
    def _available_axes(self) -> set:
        if not self.inputs:
            return set()
        groups = core.group_files(core.collect_inputs(self.inputs))
        available = set()
        for group in groups:
            available.update(group["axes"].keys())
        return available

    def _selected_axes(self) -> set:
        return set(self.axes_enabled) & self._available_axes()

    def _refresh_axis_pills(self):
        if not hasattr(self, "axis_pills"):
            return
        available = self._available_axes()
        for name, pill in self.axis_pills.items():
            if name not in available:
                pill.set_enabled(False)
                continue
            pill.set_enabled(True)
            pill.set_kind("on" if name in self.axes_enabled else "plain")
        selected = len(self._selected_axes())
        self.axes_hint.configure(text=self._t("axes_selected", n=selected) if available else "")

    def _toggle_axis(self, name: str):
        if name not in self._available_axes():
            return
        if name in self.axes_enabled:
            self.axes_enabled.discard(name)
        else:
            self.axes_enabled.add(name)
        self._save_ui_settings()
        self._refresh_axis_pills()

    # ------------------------------------------------------------ settings
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
        return self._t("output_auto")

    def choose_out_dir(self):
        path = filedialog.askdirectory(title=self._t("output"))
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

    def _on_opacity(self, value):
        try:
            self.bg_opacity = max(0, min(100, int(round(float(value)))))
        except (TypeError, ValueError):
            return
        if hasattr(self, "opacity_label"):
            self.opacity_label.configure(text=f"{self.bg_opacity}%")
        self._save_ui_settings()

    def _save_ui_settings(self):
        self.settings.update(
            language=self.lang,
            width=self.width,
            bg_opacity=self.bg_opacity,
            axes=sorted(self.axes_enabled),
        )
        save_settings(self.settings)

    # ------------------------------------------------------------ clipboard
    def copy_image(self):
        if self.image is None:
            self.toast.show(self._t("copy_empty"), "warn")
            self._log(self._t("copy_empty"), "warn")
            return
        try:
            ok = copy_image_to_clipboard(self.image)
        except Exception:  # noqa: BLE001
            ok = False
        if ok:
            self.toast.show(self._t("copied"), "ok")
            self.status_var.set(self._t("copied"))
            self._log(self._t("copied"), "ok")
        else:
            self.toast.show(self._t("copy_failed"), "err")
            self._log(self._t("copy_failed"), "err")

    # ------------------------------------------------------------ jobs
    def _start(self, action: str):
        if self.busy:
            return
        if not self.inputs:
            self.status_var.set(self._t("no_input"))
            self._log(self._t("no_input"), "warn")
            self.toast.show(self._t("no_input"), "warn")
            return

        if action != "merge":
            try:
                width = int(self.width_var.get().strip())
            except ValueError:
                width = -1
            if not core.MIN_WIDTH <= width <= core.MAX_WIDTH:
                message = self._t("invalid_width", min=core.MIN_WIDTH, max=core.MAX_WIDTH)
                self.status_var.set(message)
                self._log(message, "err")
                self.toast.show(message, "err")
                return
            self.width = width
        self.bg_opacity = max(0, min(100, int(round(self.opacity_var.get()))))
        self._save_ui_settings()

        enabled = self._selected_axes()
        if not enabled:
            message = self._t("no_axis")
            self.status_var.set(message)
            self._log(message, "warn")
            self.toast.show(message, "warn")
            return

        files = core.collect_inputs(self.inputs)
        if not files:
            self.status_var.set(self._t("no_scripts"))
            self._log(self._t("no_scripts"), "warn")
            return
        groups = core.group_files(files)
        out_dir = self._out_dir()

        self.busy = True
        self._sync_buttons()
        self.progress.configure(maximum=max(1, len(groups)), value=0)
        self.status_var.set(self._t("merging") if action == "merge" else self._t("rendering"))
        self._start_pulse()
        thread = threading.Thread(
            target=self._work,
            args=(groups, out_dir, action, set(enabled), self.width, self.bg_opacity),
            daemon=True,
        )
        thread.start()
        self.root.after(60, self._poll)

    def _work(self, groups, out_dir: Path, action: str, enabled, width: int, opacity: int):
        results = []
        merged_count = 0
        for index, group in enumerate(groups, 1):
            try:
                if action == "merge":
                    data = core.merge_axes(group["axes"], enabled=enabled, title=group["name"])
                    merged_path = out_dir / f"{group['name']}_merged.funscript"
                    core.write_funscript(merged_path, data)
                    merged_count += 1
                    self.queue.put(("log", text(self.lang, "merge_done", label=group["label"],
                                                name=merged_path.name), "ok"))
                    results.append({"label": group["label"], "image": None, "path": None,
                                    "merged": merged_path, "ok": True})
                else:
                    image = core.render_group(group["axes"], width, bg_opacity=opacity,
                                              enabled=enabled)
                    path = None
                    if action == "save":
                        suffix = "" if opacity >= 100 else f"_bg{opacity}"
                        path = out_dir / f"{group['name']}_Axes{suffix}.png"
                        atomic_save(image, path)
                    results.append({"label": group["label"], "image": image, "path": path,
                                    "merged": None, "ok": True})
                    self.queue.put(("log", text(self.lang, "done_group", label=group["label"],
                                                name=path.name if path else "preview"), "ok"))
            except Exception as exc:  # noqa: BLE001
                self.queue.put(("log", text(self.lang, "group_failed",
                                            label=group["label"], msg=exc), "err"))
                results.append({"label": group["label"], "image": None, "path": None,
                                "merged": None, "ok": False})
            self.queue.put(("progress", index, len(groups)))
        self.queue.put(("done", results, out_dir, action, merged_count))

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

    def _finish(self, results, out_dir: Path, action: str, merged_count: int):
        self.busy = False
        self._stop_pulse()
        self._sync_buttons()
        self.progress.configure(value=self.progress["maximum"])
        self.results = [item for item in results if item["ok"]]
        failed = [item for item in results if not item["ok"]]

        if action == "merge":
            if merged_count:
                message = self._t("merged", n=merged_count, path=out_dir)
                self.status_var.set(message)
                self.toast.show(message, "ok")
            elif failed:
                self.status_var.set(self._t("failed", msg="—"))
                self.toast.show(self._t("failed", msg="—"), "err")
            return

        ok = [item for item in self.results if item["image"] is not None]
        if not ok:
            self.status_var.set(self._t("failed", msg="—"))
            self.toast.show(self._t("failed", msg="—"), "err")
            return
        self._show(0)
        if action == "save":
            message = self._t("saved", n=len(ok), path=out_dir)
            self.status_var.set(message)
            self.toast.show(message, "ok")
        else:
            image = ok[0]["image"]
            self.status_var.set(self._t("preview_ready", w=image.width, h=image.height))

    def _sync_buttons(self):
        state = not self.busy
        for button in (getattr(self, "preview_button", None), getattr(self, "save_button", None),
                       getattr(self, "merge_button", None), getattr(self, "copy_button", None)):
            if button is not None:
                button.set_enabled(state and (button is not getattr(self, "copy_button", None)
                                              or self.image is not None))

    def _start_pulse(self):
        self._stop_pulse()

        def step(colour_index=0):
            colours = (ACCENT, "#2f6f68")
            if not self.busy:
                return
            try:
                self.status_dot.itemconfigure(self._dot_item,
                                              fill=colours[colour_index % len(colours)])
            except tk.TclError:
                return
            self._pulse_job = self.root.after(420, lambda: step(colour_index + 1))

        step()

    def _stop_pulse(self):
        if self._pulse_job:
            try:
                self.root.after_cancel(self._pulse_job)
            except Exception:  # noqa: BLE001
                pass
            self._pulse_job = None
        try:
            self.status_dot.itemconfigure(self._dot_item, fill=OK if self.results else DIM)
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------ preview
    def _show(self, index: int):
        if not (0 <= index < len(self.results)):
            return
        self.current = index
        item = self.results[index]
        self.image = item["image"]
        self.zoom = None
        self._sync_buttons()
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
                               fill=DIM, font=font(16, "bold"))
            canvas.create_text(width / 2, height / 2 + px(16),
                               text=self._t("drop_hint"), fill=DIM, font=font(9))
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
        if not getattr(self, "canvas", None) or not self.canvas.winfo_exists():
            return
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

    # ------------------------------------------------------------ log
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

    # ------------------------------------------------------------ misc
    def _bind_shortcuts(self):
        self.root.bind("<F5>", lambda _e: self._start("preview"))
        self.root.bind("<Control-s>", lambda _e: self._start("save"))
        self.root.bind("<Control-S>", lambda _e: self._start("save"))
        self.root.bind("<Control-o>", lambda _e: self.choose_files())
        self.root.bind("<Control-c>", lambda _e: self.copy_image())
        self.root.bind("<Control-m>", lambda _e: self._start("merge"))

    def on_close(self):
        self._stop_pulse()
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
        axes = group["axes"]
        image = core.render_group(axes, core.DEFAULT_WIDTH, bg_opacity=100)
        alpha = image.convert("RGBA").getchannel("A").getextrema()
        print(f"  {group['label']}: {image.width}x{image.height} alpha={alpha}")

        transparent = core.render_group(axes, core.DEFAULT_WIDTH, bg_opacity=0)
        t_alpha = transparent.getchannel("A").getextrema()
        print(f"  transparent: {transparent.width}x{transparent.height} alpha={t_alpha}")

        half = core.render_group(axes, core.DEFAULT_WIDTH, bg_opacity=50)
        print(f"  background 50%: corner alpha={half.getpixel((0, 0))[3]}")

        subset = core.render_group(axes, core.DEFAULT_WIDTH, enabled={"L0"})
        print(f"  axis filter: {subset.width}x{subset.height}")

        merged = core.merge_axes(axes, enabled=set(axes))
        print(f"  merged: version={merged['version']} axes={[axis['id'] for axis in merged['axes']]}")

        if not (image.width == core.DEFAULT_WIDTH and alpha[0] == 255
                and t_alpha[0] == 0 and half.getpixel((0, 0))[3] == 127
                and subset.height == core.TOP_MARGIN + core.ROW_HEIGHT):
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
