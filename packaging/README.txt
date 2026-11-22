MHeatmap — Funscript Heatmap Generator
=======================================

Double-click MHeatmap.exe. No installer, no Python needed.

HOW TO USE
1. Drop .funscript files (or a folder) onto the window, or use "Add files" /
   "Add folder". Dropping one file also loads the other axes of the same script.
2. Tick the axis buttons (L0…R2) you want in the picture; only those rows are drawn.
3. Pick a palette: OFS Rainbow, Classic, Inferno, Viridis or Grayscale.
4. "Background" slider: 100% = solid, 0% = transparent PNG, anything in between.
   File names get _bg<value> (e.g. _Axes_bg50.png) when it is not 100.
5. Tick "Also export one multi-axis .funscript" to also write xxx_merged.funscript
   (funscript 1.1: actions = stroke axis, axes = the other channels).
6. Press "Preview" to see the image, "Generate & save" to write files.
7. Output goes to <script folder>\heatmaps by default; "Change" picks another
   folder, "Auto" goes back to the default.
8. Language: English / 中文 buttons in the top bar. First launch asks once and
   remembers your choice (%APPDATA%\MHeatmap\settings.json).

QUICK KEYS
F5 preview · Ctrl+S generate & save · Ctrl+O add files

WINDOWS TIP
If Windows shows "Windows protected your PC", click "More info" -> "Run anyway".
That is the normal prompt for a small app without a code-signing certificate.

---
MHeatmap 使用说明

双击 MHeatmap.exe 即可运行，不用安装，也不用装 Python。

用法
1. 把 .funscript 文件（或文件夹）拖进窗口，或点「添加文件 / 添加文件夹」。
   拖单个文件会自动带上同组的其他轴。
2. 点轴按钮（L0…R2）选择要画哪些轴，只画选中的行。
3. 配色可选：OFS 彩虹、经典、熔岩、青绿、灰度。
4. 「背景」滑块：100% 不透明，0% 全透明，中间值也可以；
   非 100% 时文件名会带 _bg<数值>（例如 _Axes_bg50.png）。
5. 勾选「同时导出单文件多轴 .funscript」会额外生成 xxx_merged.funscript
   （funscript 1.1：actions 是行程轴，axes 是其余通道）。
6. 点「预览」看图，点「生成并保存」导出文件。
7. 默认输出到 <脚本目录>\heatmaps；「更改」可以换目录，「自动」恢复默认。
8. 语言：右上角 English / 中文 随时切换；第一次打开会问一次并记住选择
   （存于 %APPDATA%\MHeatmap\settings.json）。

快捷键：F5 预览 · Ctrl+S 生成 · Ctrl+O 加文件

提示
若出现「Windows 已保护你的电脑」，点「更多信息」→「仍要运行」即可
（没有数字签名的小程序都会这样提示）。