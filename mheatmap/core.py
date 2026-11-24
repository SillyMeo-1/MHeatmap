"""MHeatmap — core rendering.

Reads .funscript files and draws the row-style heatmap: one row per axis,
a filename banner, speed stats, a heat band and a speed curve.

This module is self-contained (Pillow only). It does not import anything from
the original heatmapgen projects; the palette / axis table are kept as data so
the output looks the same.
"""
from __future__ import annotations

import bisect
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

APP_NAME = "MHeatmap"
VERSION = "1.2.4"

# ------------------------------------------------------------------ geometry
TOP_MARGIN = 4
ROW_HEIGHT = 104
BAND_HEIGHT = 56
BAND_SOLID = 40
BANNER_HEIGHT = 44
AXIS_COLUMN = 96
RIGHT_PAD = 5
STATS_WIDTH = 400
MIN_WIDTH = 640
MAX_WIDTH = 4096
DEFAULT_WIDTH = 1380
DEFAULT_MAX_SPEED = 2000.0
BAND_ALPHA = 212          # 色带主体固定不透明度（参考图实测 202）
BAND_TAIL_ALPHA = 0.21    # 色带底部 16 行的不透明度比例

# ------------------------------------------------------------------ axes
# (name, label colour, filename tokens)
AXES = (
    ("L0", (213, 126, 18), ("l0", "stroke")),
    ("L1", (16, 196, 53), ("l1", "surge")),
    ("L2", (218, 88, 18), ("l2", "sway")),
    ("R0", (205, 166, 0), ("r0", "twist")),
    ("R1", (53, 153, 154), ("r1", "roll")),
    ("R2", (20, 205, 20), ("r2", "pitch")),
    ("vib", (155, 98, 220), ("vib",)),
    ("pump", (48, 178, 214), ("pump",)),
)
AXIS_TOKENS = {token: name for name, _colour, tokens in AXES for token in tokens}
SEPARATORS = (".", "_", "-", " ")

# ------------------------------------------------------------------ palettes
# Each palette is a 0..1 ramp. "ofs" is the familiar OFS rainbow.
OFS_STOPS = (
    (0.000, (0, 0, 0)),
    (0.025, (0, 128, 122)),
    (0.050, (0, 255, 138)),
    (0.075, (0, 247, 0)),
    (0.100, (120, 224, 0)),
    (0.125, (232, 189, 0)),
    (0.150, (255, 140, 0)),
    (0.175, (255, 64, 0)),
    (0.200, (255, 0, 0)),
    (0.225, (255, 0, 30)),
    (0.250, (255, 0, 171)),
    (0.275, (255, 0, 196)),
    (0.300, (150, 0, 197)),
    (0.325, (119, 0, 249)),
    (0.350, (82, 0, 255)),
    (0.375, (0, 0, 255)),
    (0.400, (0, 3, 254)),
    (0.425, (0, 90, 155)),
    (0.450, (0, 87, 88)),
    (0.500, (4, 87, 45)),
    (0.550, (74, 76, 0)),
    (0.600, (105, 60, 0)),
    (0.650, (116, 46, 39)),
    (0.700, (109, 46, 82)),
    (0.750, (84, 55, 114)),
    (0.800, (42, 69, 125)),
    (0.850, (0, 82, 110)),
    (0.900, (0, 88, 74)),
    (0.950, (41, 84, 25)),
    (1.000, (87, 70, 0)),
)

PALETTES = {
    "ofs": ("OFS Rainbow", "OFS 彩虹", OFS_STOPS, 1.0),
}
DEFAULT_PALETTE = "ofs"

# Backwards compatibility: the old single-palette names.
PALETTE = OFS_STOPS
CURVE_PALETTE = (
    (0.000, (0, 238, 255)),
    (0.075, (0, 247, 0)),
    (0.125, (232, 189, 0)),
    (0.200, (255, 0, 0)),
    (0.300, (150, 0, 197)),
    (0.400, (0, 3, 254)),
    (0.600, (105, 60, 0)),
    (1.000, (0, 88, 74)),
)


def palette_stops(name: str):
    return PALETTES.get(name, PALETTES[DEFAULT_PALETTE])[2]


def palette_gamma(name: str) -> float:
    """Gamma applied before the colour lookup, so every ramp uses its full range
    even when most speed values are low."""
    return PALETTES.get(name, PALETTES[DEFAULT_PALETTE])[3]


def palette_label(name: str, lang: str = "en") -> str:
    entry = PALETTES.get(name, PALETTES[DEFAULT_PALETTE])
    return entry[1] if lang == "zh" else entry[0]


BUNDLED_FONT = "assets/NotoSansCJKsc-Regular.otf"
_font_cache: dict[int, ImageFont.FreeTypeFont] = {}
_font_source: Path | None = None


def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / relative


def _font_candidates() -> list[Path]:
    return [
        resource_path(BUNDLED_FONT),
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/YuGothR.ttc"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
    ]


def load_font(size: int) -> ImageFont.FreeTypeFont:
    global _font_source
    if size in _font_cache:
        return _font_cache[size]
    for candidate in _font_candidates():
        try:
            font = ImageFont.truetype(str(candidate), size)
            if _font_source is None:
                _font_source = candidate
            _font_cache[size] = font
            return font
        except OSError:
            continue
    font = ImageFont.load_default()
    _font_cache[size] = font
    return font


# ------------------------------------------------------------------ helpers
def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def smoothstep(t: float) -> float:
    t = clamp(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def color_at(value: float, stops) -> tuple[int, int, int]:
    value = clamp(value, 0.0, 1.0)
    for index in range(1, len(stops)):
        prev_pos, prev_color = stops[index - 1]
        next_pos, next_color = stops[index]
        if value <= next_pos:
            span = next_pos - prev_pos
            t = 0.0 if span <= 0 else (value - prev_pos) / span
            t = smoothstep(t)
            return tuple(int(round(lerp(prev_color[i], next_color[i], t))) for i in range(3))
    return stops[-1][1]


def format_duration(duration_ms: float) -> str:
    total = int(math.ceil(duration_ms / 1000.0))
    return f"{total // 60}:{total % 60:02d}"


# ------------------------------------------------------------------ funscript io
def read_funscript(path) -> tuple[list[tuple[float, float]], float]:
    with Path(path).open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    actions = []
    for item in data.get("actions") or []:
        if not isinstance(item, dict):
            continue
        at, pos = item.get("at"), item.get("pos")
        if not isinstance(at, (int, float)) or not isinstance(pos, (int, float)):
            continue
        actions.append((float(max(0, round(at))), float(max(0, min(100, round(pos))))))
    actions.sort(key=lambda action: action[0])
    duration = actions[-1][0] if actions else 0.0
    return actions, duration


def split_axis(path) -> tuple[str, str]:
    """a.surge.funscript -> ("L1", "a"); a.funscript -> ("L0", "a")."""
    stem = Path(path).stem
    lowered = stem.casefold()
    for token, axis in sorted(AXIS_TOKENS.items(), key=lambda item: len(item[0]), reverse=True):
        for separator in SEPARATORS:
            if lowered.endswith(separator + token):
                group = stem[: -len(separator + token)].rstrip(" ._-")
                if group:
                    return axis, group
    return "L0", stem


def row_label(path) -> str:
    """Full file name plus the axis token that was found, e.g. a.surge.funscript::surge."""
    name = Path(path).name
    lowered = Path(path).stem.casefold()
    for token in sorted(AXIS_TOKENS, key=len, reverse=True):
        for separator in SEPARATORS:
            if lowered.endswith(separator + token):
                return f"{name}::{token}"
    return name


def group_files(files) -> list[dict]:
    """Group scripts that belong together (same folder, same base name)."""
    buckets: dict[tuple[str, str], dict] = {}
    for path in files:
        path = Path(path)
        axis, group = split_axis(path)
        key = (str(path.parent).casefold(), group.casefold())
        entry = buckets.setdefault(key, {"group": group, "folder": path.parent, "axes": {}})
        entry["axes"].setdefault(axis, path)

    counts: dict[str, int] = {}
    for entry in buckets.values():
        counts[entry["group"]] = counts.get(entry["group"], 0) + 1

    used: dict[str, int] = {}
    groups = []
    for entry in sorted(buckets.values(), key=lambda e: (e["group"].casefold(), str(e["folder"]).casefold())):
        name, label = entry["group"], entry["group"]
        if counts[name] > 1:
            used[name] = used.get(name, 0) + 1
            name = f"{name}_{used[name]}"
            label = f"{entry['group']} ({used[name]}) · {entry['folder']}"
        groups.append({"name": name, "label": label, "folder": entry["folder"], "axes": entry["axes"]})
    return groups


def collect_inputs(paths) -> list[Path]:
    """Expand files/folders into .funscript files; a single file pulls in its sibling axes."""
    found: list[Path] = []
    for raw in paths:
        path = Path(raw)
        try:
            if path.is_file():
                if path.suffix.lower() != ".funscript":
                    continue
                _axis, group = split_axis(path)
                for sibling in sorted(path.parent.glob("*.funscript")):
                    if split_axis(sibling)[1].casefold() == group.casefold():
                        found.append(sibling)
            elif path.is_dir():
                found.extend(sorted(path.glob("*.funscript")))
        except OSError:
            continue

    unique: list[Path] = []
    seen: set[str] = set()
    for path in found:
        key = str(path.resolve()).casefold()
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def speed_segments(actions) -> list[float]:
    speeds = []
    for (a0, p0), (a1, p1) in zip(actions, actions[1:]):
        delta = a1 - a0
        if delta > 0:
            speeds.append(abs(p1 - p0) * 1000.0 / delta)
        else:
            speeds.append(0.0)
    return speeds


def speed_stats(actions) -> tuple[int, int]:
    speeds = [speed for speed in speed_segments(actions) if speed > 0]
    if not speeds:
        return 0, 0
    return int(round(max(speeds))), int(round(sum(speeds) / len(speeds)))


# ------------------------------------------------------------------ drawing
def draw_glow_text(image: Image.Image, xy, text, font, fill=(16, 16, 16),
                   glow=(255, 255, 255), anchor=None, blur: float = 1.2,
                   glow_alpha: int = 200, stroke_width: int = 1) -> None:
    """Black text with a white halo; everything goes through alpha_composite so the
    destination keeps its own alpha (important for transparent exports)."""
    glow_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow_layer).text(xy, text, font=font, fill=(*glow, glow_alpha), anchor=anchor)
    if blur > 0:
        glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(blur))
    image.alpha_composite(glow_layer)

    text_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    ImageDraw.Draw(text_layer).text(
        xy, text, font=font, fill=(*fill, 255), anchor=anchor,
        stroke_width=stroke_width, stroke_fill=(*glow, 255),
    )
    image.alpha_composite(text_layer)


def draw_stats(image, x, y, w, actions, duration_ms) -> None:
    max_speed, avg_speed = speed_stats(actions)
    cells = (
        ("Duration", format_duration(duration_ms)),
        ("Actions", str(len(actions))),
        ("MaxSpeed", str(max_speed)),
        ("AvgSpeed", str(avg_speed)),
    )
    cell_w = w // len(cells)
    for index, (label, value) in enumerate(cells):
        cx = x + index * cell_w + cell_w // 2
        draw_glow_text(image, (cx, y + 1), label, load_font(15), anchor="mt",
                       blur=1.0, glow_alpha=205, stroke_width=1)
        draw_glow_text(image, (cx, y + 15), value, load_font(27), anchor="mt",
                       blur=1.4, glow_alpha=230, stroke_width=2)


def draw_band(image, actions, duration_ms, x, y, width, max_speed, stops=OFS_STOPS,
              gamma: float = 1.0) -> None:
    """Heat band: one column per pixel, alpha fades out towards the bottom."""
    if len(actions) < 2 or duration_ms <= 0 or width <= 0:
        return
    # 每一列取「该时刻所在那一段」的速度；不要把跨列的短促段按最大速度糊到整列上
    times = [item[0] for item in actions]
    speeds = [0.0] * width
    last = len(actions) - 2
    for column in range(width):
        moment = (column + 0.5) * duration_ms / width
        index = bisect.bisect_right(times, moment) - 1
        index = 0 if index < 0 else min(index, last)
        a0, p0 = actions[index]
        a1, p1 = actions[index + 1]
        delta = a1 - a0
        if delta > 0:
            speeds[column] = abs(p1 - p0) * 1000.0 / delta

    columns = []
    for speed in speeds:
        intensity = clamp(speed / max_speed, 0.0, 1.0) if speed else 0.0
        if not speed:
            columns.append((0, 0, 0, 0))
            continue
        color = color_at(clamp(intensity ** gamma, 0.0, 1.0), stops)
        columns.append((color[0], color[1], color[2], BAND_ALPHA))

    data = []
    for row in range(BAND_HEIGHT):
        factor = 1.0 if row < BAND_SOLID else BAND_TAIL_ALPHA
        for red, green, blue, alpha in columns:
            data.append((red, green, blue, int(alpha * factor)))
    band = Image.new("RGBA", (width, BAND_HEIGHT))
    band.putdata(data)
    image.alpha_composite(band, (x, y))


def draw_curve(image, actions, duration_ms, x, y, width, height, max_speed,
               stops=CURVE_PALETTE) -> None:
    if len(actions) < 2 or duration_ms <= 0:
        return
    scale = 3
    overlay = Image.new("RGBA", (max(1, width * scale), max(1, height * scale)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    def point(action):
        at, pos = action
        px = clamp(at / duration_ms, 0.0, 1.0) * width * scale
        py = (1.0 - clamp(pos / 100.0, 0.0, 1.0)) * height * scale
        return (round(px), round(py))

    for (a0, p0), (a1, p1) in zip(actions, actions[1:]):
        delta = a1 - a0
        if delta <= 0:
            continue
        speed = abs(p1 - p0) * 1000.0 / delta
        rgb = color_at(clamp(speed / max_speed, 0.0, 1.0), stops)
        draw.line((point((a0, p0)), point((a1, p1))), fill=(*rgb, 215), width=scale * 2)
    overlay = overlay.resize((width, height), Image.LANCZOS)
    image.alpha_composite(overlay, (x, y))


def render_group(axes: dict[str, Path], width: int = DEFAULT_WIDTH, bg_opacity: int = 100,
                 palette: str = DEFAULT_PALETTE, enabled=None,
                 max_speed: float = DEFAULT_MAX_SPEED) -> Image.Image:
    """Draw one image for a group of axis scripts.

    bg_opacity: 0 = fully transparent background, 100 = opaque.
    enabled: optional set of axis names to draw (default: every axis present).
    """
    wanted = set(enabled) if enabled is not None else None
    rows = [axis for axis in AXES
            if axis[0] in axes and (wanted is None or axis[0] in wanted)]
    if not rows:
        raise ValueError("no axis scripts selected")

    width = int(clamp(int(width), MIN_WIDTH, MAX_WIDTH))
    height = TOP_MARGIN + ROW_HEIGHT * len(rows)
    bg_alpha = int(clamp(int(bg_opacity), 0, 100) * 255 // 100)
    image = Image.new("RGBA", (width, height), (0, 0, 0, bg_alpha))
    draw = ImageDraw.Draw(image)
    plot_x = AXIS_COLUMN
    plot_w = width - plot_x - RIGHT_PAD
    stats_w = min(STATS_WIDTH, max(220, plot_w // 3))

    loaded: dict[str, tuple] = {}
    duration = 0.0
    for axis_name, _colour, _tokens in rows:
        actions, duration_ms = read_funscript(axes[axis_name])
        loaded[axis_name] = (actions, duration_ms)
        duration = max(duration, duration_ms)
    duration = duration or 1.0
    stops = palette_stops(palette)
    gamma = palette_gamma(palette)

    for index, (axis_name, axis_colour, _tokens) in enumerate(rows):
        y = TOP_MARGIN + index * ROW_HEIGHT
        actions, axis_duration = loaded[axis_name]
        use_duration = duration or axis_duration

        if bg_alpha:
            draw.rectangle((0, y, width, y + ROW_HEIGHT), fill=(0, 0, 0, bg_alpha))
        draw.rectangle((0, y, plot_x, y + ROW_HEIGHT), fill=(*axis_colour, 255))
        font_axis = load_font(56)
        while font_axis.size > 18 and draw.textlength(axis_name, font=font_axis) > plot_x - 10:
            font_axis = load_font(font_axis.size - 2)
        draw.text((plot_x / 2, y + ROW_HEIGHT / 2), axis_name, font=font_axis,
                  fill=(0, 0, 0, 255), anchor="mm")

        banner = Image.new("RGBA", (plot_w, BANNER_HEIGHT), (0, 0, 0, 0))
        ImageDraw.Draw(banner).rounded_rectangle(
            (0, 0, plot_w - 1, BANNER_HEIGHT - 1), radius=3, fill=(202, 202, 202, 80),
        )
        image.alpha_composite(banner, (plot_x, y))

        draw_band(image, actions, use_duration, plot_x, y, plot_w, max_speed, stops, gamma)

        label = row_label(axes[axis_name])
        max_text = plot_w - stats_w - 24
        font_file = load_font(20)
        for size in range(20, 11, -1):
            font_file = load_font(size)
            if draw.textlength(label, font=font_file) <= max_text:
                break
        else:
            font_file = load_font(12)
            while label and draw.textlength(label + "…", font=font_file) > max_text:
                label = label[:-1]
            label += "…"
        draw_glow_text(image, (plot_x + 10, y + 7), label, font_file,
                       anchor="lt", blur=1.0, glow_alpha=190, stroke_width=1)

        draw_stats(image, plot_x + plot_w - stats_w - 4, y + 2, stats_w, actions, use_duration)
        draw_curve(image, actions, use_duration, plot_x, y + BAND_HEIGHT + 4, plot_w,
                   ROW_HEIGHT - BAND_HEIGHT - 8, max_speed)
        draw.line((plot_x, y + ROW_HEIGHT - 1, plot_x + plot_w, y + ROW_HEIGHT - 1),
                  fill=(0, 150, 170, 255), width=1)

    return image


# ------------------------------------------------------------------ merging
def merge_axes(axes: dict[str, Path], enabled=None, title: str = "") -> dict:
    """Build a single-file multi-axis funscript (funscript 1.1 style).

    The main ``actions`` array is the stroke axis (L0 when selected, otherwise the
    first selected axis); the other axes go into ``axes`` as {id, actions}.
    Actions are ``{"at": ms, "pos": 0-100}`` objects and ``metadata.duration`` is in
    seconds, as in the funscript 1.1 layout used by @eroscripts/funlib.
    """
    wanted = set(enabled) if enabled is not None else None
    order = [axis[0] for axis in AXES
             if axis[0] in axes and (wanted is None or axis[0] in wanted)]
    if not order:
        raise ValueError("no axis scripts selected")

    main_axis = "L0" if "L0" in order else order[0]
    main_actions, duration = read_funscript(axes[main_axis])
    others = []
    for axis_name in order:
        if axis_name == main_axis:
            continue
        actions, axis_duration = read_funscript(axes[axis_name])
        others.append({"id": axis_name,
                      "actions": [{"at": int(at), "pos": int(pos)} for at, pos in actions]})
        duration = max(duration, axis_duration)

    data = {
        # 与 @eroscripts/funlib 的 1.1 输出一致：默认值 inverted/range 不写
        "version": "1.1",
        "actions": [{"at": int(at), "pos": int(pos)} for at, pos in main_actions],
        "axes": others,
        "metadata": {
            "title": title or Path(axes[main_axis]).stem,
            "duration": round(duration / 1000.0, 3),
        },
    }
    return data


def write_funscript(path, data: dict) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(f".{path.name}.tmp")
    try:
        with pending.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))
        pending.replace(path)
    finally:
        pending.unlink(missing_ok=True)
    return path

