# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

root = Path(SPECPATH).parent.parent
desktop = root / "desktop"

a = Analysis(
    [str(desktop / "run_app.py")],
    pathex=[str(desktop)],
    binaries=[],
    datas=[
        (str(desktop / "restaurant_manager/web"), "restaurant_manager/web"),
        (str(desktop / "app-manifest.json"), "."),
    ],
    hiddenimports=["PyQt5.QtWebEngineWidgets", "openpyxl"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="RestaurantManager", console=False, icon=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="RestaurantManager")
