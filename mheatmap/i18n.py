"""MHeatmap — UI strings (English / 中文)."""
from __future__ import annotations

LANGUAGES = (("en", "English"), ("zh", "中文"))
DEFAULT_LANGUAGE = "en"

STRINGS = {
    "tagline": ("Funscript Heatmap Generator", "Funscript 热力图生成器"),
    "drop_hint": ("Drop .funscript files or a folder", "把 .funscript 或文件夹拖到这里"),
    "drop_sub": ("One file also loads the other axes of the same script",
                 "拖单个文件会自动带上同组的其他轴"),
    "drop_release": ("Release to add", "松手即可添加"),
    "add_files": ("Add files", "添加文件"),
    "add_folder": ("Add folder", "添加文件夹"),
    "clear": ("Clear", "清空"),
    "inputs": ("Inputs", "输入"),
    "summary": ("{n} input(s) · {m} script(s) · {k} group(s)",
                "{n} 项输入 · {m} 个脚本 · {k} 组"),
    "summary_empty": ("No input yet", "还没有输入"),
    "settings": ("Settings", "设置"),
    "width": ("Width", "宽度"),
    "axes": ("Axes", "轴"),
    "axes_selected": ("{n} selected", "已选 {n} 个"),
    "bg_opacity": ("Background", "背景"),
    "output": ("Output", "输出"),
    "output_auto": ("scripts folder / heatmaps", "脚本目录 / heatmaps"),
    "change": ("Change", "更改"),
    "reset": ("Auto", "自动"),
    "open_folder": ("Open folder", "打开目录"),
    "preview": ("Preview", "预览"),
    "save": ("Generate & save", "生成并保存"),
    "copy": ("Copy image", "复制图片"),
    "merge": ("Merge .funscript", "合并脚本"),
    "rendering": ("Rendering…", "正在渲染…"),
    "merging": ("Merging…", "正在合并…"),
    "ready": ("Ready — add a script to begin", "就绪 · 先添加脚本"),
    "preview_ready": ("Preview ready · {w}×{h}", "预览完成 · {w}×{h}"),
    "saved": ("Saved {n} image(s) to {path}", "已保存 {n} 张到 {path}"),
    "merged": ("Merged {n} script(s) to {path}", "已合并 {n} 个脚本到 {path}"),
    "copied": ("Image copied to clipboard", "图片已复制到剪贴板"),
    "copy_empty": ("Preview an image first", "先预览一张图"),
    "copy_failed": ("Could not access the clipboard", "无法访问剪贴板"),
    "failed": ("Failed: {msg}", "失败：{msg}"),
    "no_scripts": ("No .funscript files found", "没有找到 .funscript 文件"),
    "no_input": ("Add a .funscript file or folder first", "请先添加 .funscript 文件或文件夹"),
    "invalid_width": ("Width must be {min}–{max}", "宽度需要在 {min}–{max} 之间"),
    "added": ("Added {n} input(s)", "已添加 {n} 项"),
    "skipped": ("Skipped {n} non-funscript item(s)", "跳过 {n} 个非 .funscript 项"),
    "missing": ("{n} path(s) not found", "{n} 个路径不存在"),
    "log": ("Log", "日志"),
    "zoom_hint": ("Wheel to zoom · drag to pan · double-click to fit",
                  "滚轮缩放 · 拖动平移 · 双击适应窗口"),
    "fit": ("Fit", "适应"),
    "clear_log": ("Clear", "清空"),
    "language": ("Language", "语言"),
    "choose_language": ("Choose your language", "选择语言"),
    "choose_hint": ("You can switch anytime from the top bar.",
                    "之后随时可以在顶部切换。"),
    "done_group": ("{label} → {name}", "{label} → {name}"),
    "merge_done": ("{label} → {name}", "{label} → {name}"),
    "group_failed": ("{label}: {msg}", "{label}：{msg}"),
    "merge_failed": ("Merge failed: {msg}", "合并失败：{msg}"),
    "no_axis": ("Select at least one axis", "至少选一个轴"),
    "busy": ("Working…", "处理中…"),
    "new_version": ("v{version}", "v{version}"),
}


def text(lang: str, key: str, **kwargs) -> str:
    entry = STRINGS.get(key)
    if entry is None:
        return key
    template = entry[1] if lang == "zh" else entry[0]
    return template.format(**kwargs) if kwargs else template
