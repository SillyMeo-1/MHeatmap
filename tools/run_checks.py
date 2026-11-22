"""MHeatmap 功能检查：解析 / 渲染 / 配色 / 透明度 / 轴选择 / 合并 / 双语界面。

用法：py -3 tools/run_checks.py
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
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


def write_settings(**values) -> None:
    path = Path(os.environ.get("APPDATA") or Path.home()) / "MHeatmap" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(values, ensure_ascii=False), encoding="utf-8")


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


def test_render():
    print("\n[2] 渲染 / 配色 / 透明度")
    files = core.collect_inputs([SAMPLES])
    group = core.group_files(files)[0]
    axes = group["axes"]

    image = core.render_group(axes, 1380, bg_opacity=100)
    check("默认尺寸 1380x628", image.size == (1380, 628), str(image.size))
    check("不透明版 alpha 全 255", image.getchannel("A").getextrema() == (255, 255),
          str(image.getchannel("A").getextrema()))

    transparent = core.render_group(axes, 1380, bg_opacity=0)
    alpha = transparent.getchannel("A").getextrema()
    check("透明度 0 = 全透明底", alpha[0] == 0 and alpha[1] == 255, str(alpha))
    check("透明版角落 alpha=0", transparent.getpixel((0, 0))[3] == 0, str(transparent.getpixel((0, 0))))
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

    colours = {}
    for name in core.PALETTES:
        img = core.render_group(axes, 900, palette=name)
        colours[name] = img.getpixel((400, 30))
        check(f"配色 {name} 可渲染", img.size == (900, 628))
    check("不同配色出不同像素", len(set(colours.values())) >= 3, str(len(set(colours.values()))))

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
    check("metadata 记录生成器", data["metadata"]["generator"].startswith("MHeatmap"))

    path = core.write_funscript(work / "demo_merged.funscript", data)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    check("落盘后可解析", loaded["axes"][0]["id"] == "R0" and loaded["actions"])
    check("actions 是 [at, pos]", loaded["actions"][0] and len(loaded["actions"][0]) == 2)

    only = core.merge_axes(axes, enabled={"R1"})
    check("只选一个轴也能合并", only["axes"] == [] and only["version"] == "1.1")


def test_i18n():
    print("\n[4] 双语词条")
    missing = [key for key, value in STRINGS.items() if len(value) != 2 or not all(value)]
    check("每条都有中英文", not missing, str(missing[:4]))
    check("英文默认文案", text("en", "preview") == "Preview")
    check("中文文案", text("zh", "preview") == "预览")
    check("带参数格式化", text("en", "summary", n=1, m=6, k=1) == "1 input(s) · 6 script(s) · 1 group(s)")
    check("轴选择文案", text("en", "axes_selected", n=3) == "3 selected")


def test_ui(work: Path):
    print("\n[5] 界面流程")
    write_settings(language="en", width=1380, bg_opacity=100, palette="ofs")
    import app as gui

    root = gui.TkinterDnD.Tk() if gui.HAS_DND else gui.tk.Tk()
    application = gui.App(root, [])
    root.update()

    check("默认英文界面", application.lang == "en")
    application.add_inputs([str(SAMPLES)])
    root.update()
    check("输入统计", "6 script(s)" in application.summary_var.get(), application.summary_var.get())
    check("轴按钮全部可用", all(application.axis_buttons[name]["state"] == "normal"
                              for name in ("L0", "L1", "L2", "R0", "R1", "R2")))

    def pump(timeout=120.0):
        end = time.time() + timeout
        while time.time() < end:
            root.update()
            if not application.busy:
                return True
            time.sleep(0.02)
        return False

    application._start(False)
    check("预览任务结束", pump())
    check("预览得到图片", application.image is not None and application.image.size == (1380, 628),
          str(application.image.size if application.image else None))

    # 只保留 L0 + R1
    for name in ("L1", "L2", "R0", "R2"):
        application._toggle_axis(name)
    root.update()
    application._start(False)
    check("选轴后预览任务结束", pump())
    check("只画 2 行", application.image.size == (1380, 212), str(application.image.size))

    # 换配色 + 背景 50% + 合并
    application.palette_var.set(gui.core.palette_label("classic", "en"))
    application._on_palette()
    application.opacity_var.set(50)
    application._on_opacity(50)
    application.merge_var.set(True)
    out_dir = work / "out"
    application.out_override = str(out_dir)
    application._start(True)
    check("保存任务结束", pump())
    png = sorted(out_dir.glob("*.png"))
    merged = sorted(out_dir.glob("*.funscript"))
    check("文件名带背景透明度", png and png[0].name.endswith("_Axes_bg50.png"),
          str([p.name for p in png]))
    check("同时导出合并脚本", len(merged) == 1 and merged[0].name.endswith("_merged.funscript"),
          str([m.name for p in merged for m in [p]]))
    if merged:
        data = json.loads(merged[0].read_text(encoding="utf-8"))
        check("合并脚本含 2 个轴", data["version"] == "1.1"
              and [a["id"] for a in data["axes"]] == ["R1"], str([a["id"] for a in data["axes"]]))

    application._switch_language("zh")
    root.update()
    check("切到中文", application.preview_button["text"] == "预览", application.preview_button["text"])
    check("配色下拉本地化", application.palette_var.get() in
          [gui.core.palette_label(key, "zh") for key in gui.core.PALETTES], application.palette_var.get())
    settings = json.loads((Path(os.environ["APPDATA"]) / "MHeatmap" / "settings.json")
                          .read_text(encoding="utf-8"))
    check("语言写入配置", settings.get("language") == "zh")
    check("轴选择写入配置", settings.get("axes") is not None, str(settings.get("axes")))
    check("透明度写入配置", settings.get("bg_opacity") == 50, str(settings.get("bg_opacity")))
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
                    if isinstance(button, gui.tk.Button) and button.cget("text") == "中文":
                        picked["found"] = True
                        button.invoke()
                        return

    root.after(500, choose)
    application = gui.App(root, [])
    root.update()
    check("首次启动弹出语言选择", bool(picked.get("found")))
    check("点中文后界面变中文", application.lang == "zh"
          and application.preview_button["text"] == "预览", application.preview_button["text"])
    application.on_close()
    write_settings(language="en", width=1380)


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="mheatmap-test-"))
    print(f"临时目录：{work}")
    test_core()
    test_render()
    test_merge(work)
    test_i18n()
    test_ui(work)
    test_first_run()
    shutil.rmtree(work, ignore_errors=True)
    print("\n结果：" + ("全部通过" if not FAILS else f"{len(FAILS)} 项失败 → {FAILS}"))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
