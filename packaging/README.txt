MHeatmap — Funscript Heatmap Generator
=======================================

Double-click MHeatmap.exe. No installer, no Python needed.

HOW TO USE
1. Drop .funscript files (or a folder) onto the window, or use "Add files" /
   "Add folder". Dropping one file also loads the other axes of the same script.
2. Toggle the axis pills (L0…R2) to choose which rows are drawn.
3. "Background" slider: 100% = solid, 0% = transparent PNG, anything in between.
   File names get _bg<value> (e.g. _Axes_bg50.png) when it is not 100.
4. Buttons:
   - Preview           — draw the image, nothing is written.
   - Generate & save   — write the PNG(s).
   - Copy image        — put the preview on the clipboard (Ctrl+C), paste it
                         into Paint, Word, a browser or a chat window.
   - Merge .funscript  — only export one multi-axis funscript per group
                         (funscript 1.1: actions = stroke axis, axes = the other
                         channels). No PNG is generated for this.
5. Output goes to <script folder>\heatmaps by default; "Change" picks another
   folder, "Auto" goes back to the default.
6. Language: English / 中文 buttons in the top bar. First launch asks once and
   remembers your choice (%APPDATA%\MHeatmap\settings.json).

KEYS
F5 preview · Ctrl+S generate & save · Ctrl+O add files · Ctrl+C copy · Ctrl+M merge

WINDOWS TIP
If Windows shows "Windows protected your PC", click "More info" -> "Run anyway".
That is the normal prompt for a small app without a code-signing certificate.

---
MHeatmap 使用说明

双击 MHeatmap.exe 即可运行，不用安装，也不用装 Python。

用法
1. 把 .funscript 文件（或文件夹）拖进窗口，或点「添加文件 / 添加文件夹」。
   拖单个文件会自动带上同组的其他轴。
2. 点轴按钮（L0…R2）选择要画哪些行。
3. 「背景」滑块：100% 不透明，0% 全透明，中间值也可以；
   非 100% 时文件名会带 _bg<数值>（例如 _Axes_bg50.png）。
4. 按钮：
   - 预览          — 只画图，不写文件。
   - 生成并保存    — 写出 PNG。
   - 复制图片      — 把预览放进剪贴板（Ctrl+C），可直接粘到画图、Word、
                     浏览器或聊天窗口。
   - 合并脚本      — 只导出单文件多轴 funscript（1.1 格式：actions 是行程轴，
                     axes 是其余通道），不会生成图片。
5. 默认输出到 <脚本目录>\heatmaps；「更改」可以换目录，「自动」恢复默认。
6. 语言：右上角 English / 中文 随时切换；第一次打开会问一次并记住选择
   （存于 %APPDATA%\MHeatmap\settings.json）。

快捷键
F5 预览 · Ctrl+S 生成 · Ctrl+O 加文件 · Ctrl+C 复制 · Ctrl+M 合并

提示
若出现「Windows 已保护你的电脑」，点「更多信息」→「仍要运行」即可
（没有数字签名的小程序都会这样提示）。
