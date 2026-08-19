# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

root = Path(SPECPATH).parent.parent
desktop = root / "desktop"
a = Analysis([str(desktop / "run_updater.py")], pathex=[str(desktop)], binaries=[], datas=[], hiddenimports=[])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="RestaurantManagerUpdater", console=True, upx=False)
