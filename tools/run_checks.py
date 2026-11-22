"""MHeatmap 功能检查：核心解析 / 渲染 / 透明 / 双语界面。

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
    print("\n[2] 渲染")
    files = core.collect_inputs([SAMPLES])
    group = core.group_files(files)[0]
    image = core.render_group(group["axes"], 1380, False)
    check("默认尺寸 1380x628", image.size == (1380, 628), str(image.size))
    check("不透明版 alpha 全 255", image.getchannel("A").getextrema() == (255, 255),
          str(image.getchannel("A").getextrema()))
    transparent = core.render_group(group["axes"], 1380, True)
    alpha = transparent.getchannel("A").getextrema()
    check("透明版含 alpha=0", alpha[0] == 0 and alpha[1] == 255, str(alpha))
    check("透明版角落透明", transparent.getpixel((0, 0))[3] == 0, str(transparent.getpixel((0, 0))))
    check("透明版轴块不透明", transparent.getpixel((10, 60))[3] == 255, str(transparent.getpixel((10, 60))))

    one_axis = {"L0": group["axes"]["L0"]}
    single = core.render_group(one_axis, 1380, False)
    check("单轴只画一行", single.size == (1380, 108), str(single.size))
    wide = core.render_group(group["axes"], 3000, False)
    check("宽度可调", wide.size == (3000, 628), str(wide.size))
    clamped = core.render_group(group["axes"], 100, False)
    check("宽度下限 640", clamped.size == (640, 628), str(clamped.size))

    files2 = core.collect_inputs([SIMPLE])
    group2 = core.group_files(files2)[0]
    image2 = core.render_group(group2["axes"], 1380, False)
    check("同一份数据渲染稳定", image2.size == (1380, 628))
    stats_max, stats_avg = core.speed_stats(core.read_funscript(SIMPLE / "sample.l0.funscript")[0])
    check("速度统计合理", stats_max >= stats_avg > 0, f"max={stats_max} avg={stats_avg}")


def test_i18n():
    print("\n[3] 双语词条")
    missing = [key for key, value in STRINGS.items() if len(value) != 2 or not all(value)]
    check("每条都有中英文", not missing, str(missing[:4]))
    check("英文默认文案", text("en", "preview") == "Preview")
    check("中文文案", text("zh", "preview") == "预览")
    check("带参数格式化", text("en", "summary", n=1, m=6, k=1) == "1 input(s) · 6 script(s) · 1 group(s)",
          text("en", "summary", n=1, m=6, k=1))


def test_ui(work: Path):
    print("\n[4] 界面流程")
    write_settings(language="en", width=1380)
    import app as gui

    root = gui.TkinterDnD.Tk() if gui.HAS_DND else gui.tk.Tk()
    application = gui.App(root, [])
    root.update()

    check("默认英文界面", application.lang == "en")
    check("语言按钮存在", application.lang == "en" and application.status_var.get().startswith("Ready"))

    application.add_inputs([str(SAMPLES)])
    root.update()
    check("输入统计", "6 script(s)" in application.summary_var.get(), application.summary_var.get())

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
    check("预览状态行", "Preview ready" in application.status_var.get(), application.status_var.get())

    application.transparent_var.set(True)
    application._start(False)
    check("透明预览任务结束", pump())
    check("透明预览带 alpha", application.image.mode == "RGBA"
          and application.image.getchannel("A").getextrema()[0] == 0,
          str(application.image.getchannel("A").getextrema()))

    out_dir = work / "out"
    application.out_override = str(out_dir)
    application._start(True)
    check("保存任务结束", pump())
    saved = list(out_dir.glob("*.png"))
    check("保存出 PNG", len(saved) == 1 and saved[0].name.endswith("_transparent.png"),
          str([p.name for p in saved]))

    application._switch_language("zh")
    root.update()
    check("切到中文", application.lang == "zh" and application.preview_button["text"] == "预览",
          application.preview_button["text"])
    saved_settings = json.loads((Path(os.environ["APPDATA"]) / "MHeatmap" / "settings.json")
                                .read_text(encoding="utf-8"))
    check("语言写入配置", saved_settings.get("language") == "zh")

    application._switch_language("en")
    root.update()
    check("切回英文", application.preview_button["text"] == "Preview")
    application.on_close()


def walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from walk(child)


def test_first_run():
    print("\n[5] 首次启动的语言选择")
    write_settings()  # 没有任何设置 → 应弹出选择框
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
          and application.preview_button["text"] == "预览",
          application.preview_button["text"])
    settings_path = Path(os.environ["APPDATA"]) / "MHeatmap" / "settings.json"
    check("选择写入配置", json.loads(settings_path.read_text(encoding="utf-8")).get("language") == "zh")
    application.on_close()
    write_settings(language="en", width=1380)


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="mheatmap-test-"))
    print(f"临时目录：{work}")
    test_core()
    test_render()
    test_i18n()
    test_ui(work)
    test_first_run()
    shutil.rmtree(work, ignore_errors=True)
    print("\n结果：" + ("全部通过" if not FAILS else f"{len(FAILS)} 项失败 → {FAILS}"))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    sys.exit(main())
