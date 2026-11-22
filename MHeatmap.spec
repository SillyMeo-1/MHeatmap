# -*- mode: python ; coding: utf-8 -*-
# MHeatmap — build:  py -3 -m PyInstaller --noconfirm MHeatmap.spec
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
)

app_name = "MHeatmap"
release_version = "1.2.0"
fixed = FixedFileInfo(
    filevers=(1, 2, 0, 0), prodvers=(1, 2, 0, 0), mask=0x3f, flags=0,
    OS=0x40004, fileType=1, subtype=0, date=(0, 0),
)
version = VSVersionInfo(
    ffi=fixed,
    kids=[
        StringFileInfo([StringTable("080404B0", [
            StringStruct("FileDescription", "MHeatmap - Funscript Heatmap Generator"),
            StringStruct("FileVersion", release_version),
            StringStruct("OriginalFilename", app_name + ".exe"),
            StringStruct("ProductName", "MHeatmap"),
            StringStruct("ProductVersion", release_version),
        ])]),
        VarFileInfo([VarStruct("Translation", [0x0804, 1200])]),
    ],
)

a = Analysis(
    ["app.py"],
    datas=[("assets/NotoSansCJKsc-Regular.otf", "assets"), ("assets/OFL.txt", "assets")],
    hiddenimports=[],
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=app_name,
    version=version,
    icon="assets/icon.ico",
    console=False,
    upx=False,
)
