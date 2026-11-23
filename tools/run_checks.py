"""MHeatmap 功能检查：解析 / 渲染 / 透明度 / 轴选择 / 合并 / 剪贴板 / 双语界面。

用法：py -3 tools/run_checks.py
"""
from __future__ import annotations

import ast
import ctypes
import json
import os
import shutil
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mheatmap import core  # noqa: E402
from mheatmap.i18n import STRINGS, text  # noqa: E402

FAILS: list[str] = []
SAMPLES = Path(r"D:\AI自写软件\heatmapgen-ui\refs\reference_like")
SIMPLE = Path(r"D:\AI自写软件\heatmapgen-ui\samples")


def check(name: str, condition, detail: str = "") -> None:
    print(("  ok   " if condition else "  FAIL ") + name + (f"  [{detail}]" if detail else ""))
    if not condition:
        FAILS.append(name)


def curve_calls_with_stops(path: Path) -> list[int]:
    """AST 扫描：给 draw_curve 传 stops（第 9 个位置参数或关键字）的调用点都算回归。"""
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))  # core.py 带 BOM
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
        if name != "draw_curve":
            continue
        if len(node.args) > 8 or any(keyword.arg == "stops" for keyword in node.keywords):
            hits.append(node.lineno)
    return hits


def curve_pixels(image) -> list[tuple[int, int, int]]:
    """透明底下按 alpha 找出曲线像素，避免把黑底当成黑线。"""
    pixels = image.load()
    top = core.TOP_MARGIN + core.BAND_HEIGHT + 4
    return [pixels[x, y][:3]
            for y in range(top, top + 40)
            for x in range(core.AXIS_COLUMN + 2, image.size[0] - 6)
            if pixels[x, y][3] > 40]


def write_settings(**values) -> None:
    path = Path(os.environ.get("APPDATA") or Path.home()) / "MHeatmap" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(values, ensure_ascii=False), encoding="utf-8")


def clipboard_formats() -> dict:
    user32 = ctypes.windll.user32
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    user32.RegisterClipboardFormatW.restype = wintypes.UINT
    user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
    result = {"open": False, "dib": False, "png": False}
    if not user32.OpenClipboard(None):
        return result
    result["open"] = True
    try:
        result["dib"] = bool(user32.IsClipboardFormatAvailable(8))
        png_format = user32.RegisterClipboardFormatW("PNG")
        result["png"] = bool(user32.IsClipboardFormatAvailable(png_format)) if png_format else False
    finally:
        user32.CloseClipboard()
    return result


def test_core():
    print("\n[1] 解析与分组")
    actions, duration = core.read_funscript(next(SAMPLES.glob("*.funscript")))
    check("读取 funscript", len(actions) > 100 and duration > 0, f"{len(actions)} actions, {duration:.0f} ms")
    check("轴后缀识别 surge", core.split_axis(Path("a.surge.funscript")) == ("L1", "a"))
    check("轴后缀识别 .l0", core.split_axis(Path("b.L0.funscript")) == ("L0", "b"))
    check("无后缀按主轴处理", core.split_axis(Path("c.funscript")) == ("L0", "c"))
    check("行标签带 ::token", core.row_label(Path("a.roll.funscript")) == "a.roll.funscript::roll")
    files = core.collect_inputs([SAMPLES])
    groups = core.group_files(files)
    check("一组 6 轴", len(groups) == 1 and len(groups[0]["axes"]) == 6, f"{len(groups)} group(s)")
    single = core.collect_inputs([next(SAMPLES.glob("*.funscript"))])
    check("拖单个文件带出同组", len(single) == 6, str(len(single)))
    check("同一文件不会重复", len(core.collect_inputs([SAMPLES, SAMPLES])) == len(files))
    check("只剩一套配色", list(core.PALETTES) == ["ofs"], str(list(core.PALETTES)))


def test_render(work: Path):
    print("\n[2] 渲染 / 背景透明度 / 轴筛选")
    files = core.collect_inputs([SAMPLES])
    axes = core.group_files(files)[0]["axes"]

    image = core.render_group(axes, 1380, bg_opacity=100)
    check("默认尺寸 1380x628", image.size == (1380, 628), str(image.size))
    check("不透明版 alpha 全 255", image.getchannel("A").getextrema() == (255, 255),
          str(image.getchannel("A").getextrema()))

    transparent = core.render_group(axes, 1380, bg_opacity=0)
    alpha = transparent.getchannel("A").getextrema()
    check("透明度 0 = 全透明底", alpha[0] == 0 and alpha[1] == 255, str(alpha))
    check("透明版角落 alpha=0", transparent.getpixel((0, 0))[3] == 0)
    check("透明版轴块不透明", transparent.getpixel((10, 60))[3] == 255)

    half = core.render_group(axes, 1380, bg_opacity=50)
    check("透明度 50 = alpha≈127", half.getpixel((0, 0))[3] == 127, str(half.getpixel((0, 0))))

    subset = core.render_group(axes, 1380, enabled={"L0", "R2"})
    check("只画选中的 2 个轴", subset.size == (1380, 212), str(subset.size))
    none_error = False
    try:
        core.render_group(axes, 1380, enabled=set())
    except ValueError:
        none_error = True
    check("一个轴都不选时报错", none_error)

    # 曲线配色回归防线：按住不动的段必须是青色，绝不能黑（1.2.1 把热力色板喂给曲线，
    # OFS 强度 0 是纯黑，静止段整段变黑）。透明底 + alpha 隔离曲线像素，黑底不会冒充黑线。
    hold_actions = [{"at": 0, "pos": 50}, {"at": 6000, "pos": 50},
                    {"at": 6400, "pos": 10}, {"at": 12000, "pos": 10}]
    hold_path = work / "hold.funscript"
    hold_path.write_text(json.dumps({"version": "1.0", "actions": hold_actions},
                                    ensure_ascii=False), encoding="utf-8")
    hold_image = core.render_group({"L0": hold_path}, 900, bg_opacity=0)
    colours = curve_pixels(hold_image)
    black = [colour for colour in colours if sum(colour) < 60]
    cyan = [colour for colour in colours if colour[1] > 120 and colour[2] > 120 and colour[0] < 90]
    check("静止段曲线画得出来", len(colours) > 200, str(len(colours)))
    check("静止段曲线不是黑色", len(black) * 50 <= len(colours),
          f"black={len(black)}/{len(colours)}")
    check("静止段曲线是青色系", len(cyan) * 2 > len(colours),
          f"cyan={len(cyan)}/{len(colours)}")
    check("draw_curve 默认用速度色阶",
          core.draw_curve.__defaults__[-1] is core.CURVE_PALETTE,
          str(core.draw_curve.__defaults__[-1][:1]))
    leaked = curve_calls_with_stops(ROOT / "mheatmap" / "core.py")
    check("没有调用点给曲线传 stops", not leaked, str(leaked))
    check("热力色板仍是 OFS 数据",
          core.draw_band.__defaults__[0] is core.OFS_STOPS
          and len(core.OFS_STOPS) == 30
          and core.OFS_STOPS[0] == (0.0, (0, 0, 0))
          and core.OFS_STOPS[-1] == (1.0, (87, 70, 0)),
          str(len(core.OFS_STOPS)))
    check("曲线色阶与热力色板是两套",
          core.CURVE_PALETTE is not core.OFS_STOPS
          and core.CURVE_PALETTE[0][1] == (0, 238, 255),
          str(core.CURVE_PALETTE[0][1]))
    # 横幅（BANNER_HEIGHT=44）盖住色带主体，所以在色带下沿取样；
    # 前 5 秒是纯静止段，这些列的色带 alpha 必须是 0（0 强度不代表黑色块）
    band_pixels = hold_image.load()
    held_alpha = [band_pixels[x, core.TOP_MARGIN + 48][3]
                  for x in range(core.AXIS_COLUMN + 2, 420)]
    check("静止段热力带不画黑块", all(alpha == 0 for alpha in held_alpha),
          str(sorted(set(held_alpha))))

    single = core.render_group({"L0": axes["L0"]}, 1380)
    check("单轴只画一行", single.size == (1380, 108), str(single.size))
    check("宽度可调", core.render_group(axes, 3000).size == (3000, 628))
    check("宽度下限 640", core.render_group(axes, 100).size == (640, 628))


def test_merge(work: Path):
    print("\n[3] 合并多轴")
    files = core.collect_inputs([SAMPLES])
    axes = core.group_files(files)[0]["axes"]

    data = core.merge_axes(axes, enabled={"L0", "R0", "R1", "R2"}, title="demo")
    check("version 1.1", data["version"] == "1.1", data["version"])
    check("主轴用 L0 的 actions", len(data["actions"]) == len(core.read_funscript(axes["L0"])[0]))
    check("附加轴 id 正确", [axis["id"] for axis in data["axes"]] == ["R0", "R1", "R2"],
          str([axis["id"] for axis in data["axes"]]))
    check("附加轴带 actions", all(axis["actions"] for axis in data["axes"]))
    check("轴对象只有 id/actions", all(set(axis) == {"id", "actions"} for axis in data["axes"]),
          str([sorted(axis) for axis in data["axes"]]))

    # funscript 1.1：actions 必须是 {"at","pos"} 对象，duration 是秒
    def action_ok(items):
        return all(isinstance(item, dict) and set(item) == {"at", "pos"}
                   and isinstance(item["at"], int) and isinstance(item["pos"], int)
                   for item in items)

    check("主轴 actions 是 at/pos 对象", action_ok(data["actions"]), str(data["actions"][:1]))
    check("附加轴 actions 是 at/pos 对象",
          all(action_ok(axis["actions"]) for axis in data["axes"]))
    main_times = [item["at"] for item in data["actions"]]
    check("时间单调不回退", all(a <= b for a, b in zip(main_times, main_times[1:])))
    check("位置在 0-100", all(0 <= item["pos"] <= 100 for item in data["actions"]))
    check("metadata.duration 用秒", abs(data["metadata"]["duration"] - 880.0) < 1.0,
          str(data["metadata"]["duration"]))
    check("metadata 不写生成器", "generator" not in data["metadata"], str(list(data["metadata"])))

    path = core.write_funscript(work / "demo_merged.funscript", data)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    check("落盘后可解析", loaded["axes"][0]["id"] == "R0" and loaded["actions"])
    check("落盘后仍是 at/pos 对象", isinstance(loaded["actions"][0], dict)
          and set(loaded["actions"][0]) == {"at", "pos"}, str(loaded["actions"][0]))

    # 按 @eroscripts/funlib 的解析方式模拟：Object.assign(this, action) 后读 at/pos
    check("符合 funlib 反序列化前提（对象字段）",
          all("at" in item and "pos" in item for item in loaded["actions"]))

    only = core.merge_axes(axes, enabled={"R1"})
    check("只选一个轴也能合并", only["axes"] == [] and only["version"] == "1.1")


def test_i18n():
    print("\n[4] 双语词条")
    missing = [key for key, value in STRINGS.items() if len(value) != 2 or not all(value)]
    check("每条都有中英文", not missing, str(missing[:4]))
    check("英文默认文案", text("en", "preview") == "Preview")
    check("中文文案", text("zh", "preview") == "预览")
    check("新增按钮文案", text("en", "copy") == "Copy image" and text("zh", "merge") == "合并脚本")


def test_ui(work: Path):
    print("\n[5] 界面流程")
    write_settings(language="en", width=1380, bg_opacity=100)
    import app as gui

    root = gui.TkinterDnD.Tk() if gui.HAS_DND else gui.tk.Tk()
    application = gui.App(root, [])
    root.update()

    check("默认英文界面", application.lang == "en")
    application.add_inputs([str(SAMPLES)])
    root.update()
    check("输入统计", "6 script(s)" in application.summary_var.get(), application.summary_var.get())
    check("轴按钮全部可用", all(application.axis_pills[name]._enabled
                              for name in ("L0", "L1", "L2", "R0", "R1", "R2")))
    check("缺失轴被禁用", not application.axis_pills["vib"]._enabled)

    def pump(timeout=120.0):
        end = time.time() + timeout
        while time.time() < end:
            root.update()
            if not application.busy:
                return True
            time.sleep(0.02)
        return False

    application._start("preview")
    check("预览任务结束", pump())
    check("预览得到图片", application.image is not None and application.image.size == (1380, 628),
          str(application.image.size if application.image else None))

    # 只保留 L0 + R1
    for name in ("L1", "L2", "R0", "R2"):
        application._toggle_axis(name)
    root.update()
    application._start("preview")
    check("选轴后预览结束", pump())
    check("只画 2 行", application.image.size == (1380, 212), str(application.image.size))

    # 复制到剪贴板
    application.copy_image()
    root.update()
    formats = clipboard_formats()
    check("剪贴板拿到 CF_DIB", formats["open"] and formats["dib"], str(formats))
    check("剪贴板同时有 PNG", formats["png"], str(formats))

    # 背景 50% + 保存
    application.opacity_var.set(50)
    application._on_opacity(50)
    out_dir = work / "out"
    application.out_override = str(out_dir)
    application._start("save")
    check("保存任务结束", pump())
    png = sorted(out_dir.glob("*.png"))
    check("文件名带背景透明度", png and png[0].name.endswith("_Axes_bg50.png"),
          str([p.name for p in png]))

    # 单独合并：不生成图片
    application.image = None
    application._start("merge")
    check("合并任务结束", pump())
    merged = sorted(out_dir.glob("*.funscript"))
    png_after = sorted(out_dir.glob("*.png"))
    check("合并只写 funscript", len(merged) == 1 and len(png_after) == len(png),
          f"{len(merged)} funscript / {len(png_after)} png")
    if merged:
        data = json.loads(merged[0].read_text(encoding="utf-8"))
        check("合并脚本含选中轴", [a["id"] for a in data["axes"]] == ["R1"],
              str([a["id"] for a in data["axes"]]))
        check("合并脚本 actions 为对象",
              isinstance(data["actions"][0], dict) and set(data["actions"][0]) == {"at", "pos"},
              str(data["actions"][0]))
    check("合并后状态栏有提示", "Merged" in application.status_var.get(), application.status_var.get())

    application._switch_language("zh")
    root.update()
    check("切到中文", application.preview_button._label == "预览", application.preview_button._label)
    settings = json.loads((Path(os.environ["APPDATA"]) / "MHeatmap" / "settings.json")
                          .read_text(encoding="utf-8"))
    check("语言写入配置", settings.get("language") == "zh")
    check("轴选择写入配置", settings.get("axes") is not None, str(settings.get("axes")))
    application._switch_language("en")
    root.update()
    application.on_close()


def walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from walk(child)


def test_first_run():
    print("\n[6] 首次启动的语言选择")
    write_settings()
    import app as gui

    root = gui.TkinterDnD.Tk() if gui.HAS_DND else gui.tk.Tk()
    picked = {}

    def choose():
        for widget in walk(root):
            if isinstance(widget, gui.tk.Toplevel):
                for button in walk(widget):
                    if isinstance(button, gui.Pill) and button._label == "中文":
                        picked["found"] = True
                        button._command()
                        return

    root.after(500, choose)
    application = gui.App(root, [])
    root.update()
    check("首次启动弹出语言选择", bool(picked.get("found")))
    check("点中文后界面变中文", application.lang == "zh"
          and application.preview_button._label == "预览", application.preview_button._label)
    application.on_close()
    write_settings(language="en", width=1380)


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="mheatmap-test-"))
    print(f"临时目录：{work}")
    test_core()
    test_render(work)
    test_merge(work)
    test_i18n()
    test_ui(work)
    test_first_run()
    shutil.rmtree(work, ignore_errors=True)
    print("\n结果：" + ("全部通过" if not FAILS else f"{len(FAILS)} 项失败 → {FAILS}"))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
