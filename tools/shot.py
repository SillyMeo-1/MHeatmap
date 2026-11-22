"""启动 MHeatmap 并用 PrintWindow 抓窗口图（不抢前台、DPI 正确）。

用法：
    py -3 tools/shot.py out.png [--lang en|zh] [--inputs PATH] [--first-run] [--wait 12]
"""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PIL import Image  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TITLE = "MHeatmap"
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


def user32():
    return ctypes.windll.user32


def gdi32():
    return ctypes.windll.gdi32


def window_title(hwnd) -> str:
    buffer = ctypes.create_unicode_buffer(512)
    user32().GetWindowTextW(hwnd, buffer, 512)
    return buffer.value


def find_window(prefix: str):
    user32().EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
    found = []

    def callback(hwnd, _param):
        if user32().IsWindowVisible(hwnd) and window_title(hwnd).startswith(prefix):
            found.append(hwnd)
        return True

    user32().EnumWindows(WNDENUMPROC(callback), 0)
    return found[-1] if found else None


def capture(hwnd) -> Image.Image:
    user32().GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    rect = wintypes.RECT()
    user32().GetWindowRect(hwnd, ctypes.byref(rect))
    width, height = rect.right - rect.left, rect.bottom - rect.top
    if width <= 0 or height <= 0:
        raise ValueError(f"bad window size {width}x{height}")

    window_dc = user32().GetWindowDC(hwnd)
    mem_dc = gdi32().CreateCompatibleDC(window_dc)
    bitmap = gdi32().CreateCompatibleBitmap(window_dc, width, height)
    gdi32().SelectObject(mem_dc, bitmap)
    try:
        if not user32().PrintWindow(hwnd, mem_dc, 2):
            raise RuntimeError("PrintWindow failed")
        info = BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        buffer = ctypes.create_string_buffer(width * height * 4)
        rows = gdi32().GetDIBits(mem_dc, bitmap, 0, height, buffer, ctypes.byref(info), 0)
        if rows != height:
            raise RuntimeError(f"GetDIBits rows {rows}/{height}")
        return Image.frombuffer("RGBA", (width, height), buffer, "raw", "BGRA", 0, 1).convert("RGB")
    finally:
        gdi32().DeleteObject(ctypes.c_void_p(bitmap))
        gdi32().DeleteDC(mem_dc)
        user32().ReleaseDC(hwnd, window_dc)


def main() -> int:
    args = sys.argv[1:]
    out = Path(args[0]) if args and not args[0].startswith("--") else Path("shot.png")
    lang = None
    inputs = None
    first_run = "--first-run" in args
    exe_path = None
    wait = 14.0
    for index, arg in enumerate(args):
        if arg == "--lang" and index + 1 < len(args):
            lang = args[index + 1]
        if arg == "--inputs" and index + 1 < len(args):
            inputs = args[index + 1]
        if arg == "--exe" and index + 1 < len(args):
            exe_path = Path(args[index + 1])
        if arg == "--wait" and index + 1 < len(args):
            wait = float(args[index + 1])

    if sys.platform == "win32":
        ctypes.windll.shcore.SetProcessDpiAwareness(1)

    settings = Path(os.environ.get("APPDATA") or Path.home()) / "MHeatmap" / "settings.json"
    if first_run:
        settings.unlink(missing_ok=True)
    elif lang:
        settings.parent.mkdir(parents=True, exist_ok=True)
        existing = {}
        try:
            existing = json.loads(settings.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        existing["language"] = lang
        settings.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")

    command = [str(exe_path)] if exe_path else [sys.executable, str(ROOT / "app.py")]
    if inputs:
        command.append(inputs)
    process = subprocess.Popen(command, cwd=str(ROOT), creationflags=0x08000000)

    hwnd = None
    deadline = time.time() + 60
    while time.time() < deadline and hwnd is None:
        time.sleep(0.4)
        hwnd = find_window(TITLE)
    if hwnd is None:
        process.kill()
        print("window not found")
        return 1

    time.sleep(wait)
    image = capture(hwnd)
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)
    print(f"saved {out} ({image.width}x{image.height})")
    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
