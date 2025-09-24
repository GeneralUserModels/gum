# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_submodules

SPEC_PATH = Path(globals().get('__file__', sys.argv[0])).resolve()
APP_DIR = SPEC_PATH.parent
PROJECT_ROOT = APP_DIR.parent.parent

APP_NAME = os.environ.get("PYINSTALLER_APP_NAME", "Gum Recorder")
BUNDLE_IDENTIFIER = os.environ.get("PYINSTALLER_BUNDLE_IDENTIFIER", "com.local.gumrecorder")

datas = []
hiddenimports = ['Quartz', 'AppKit', 'Foundation', 'dotenv', 'gum.observers.base.observer', 'gum.observers.base.screen', 'gum.observers.base.keyboard', 'gum.observers.base.mouse', 'gum.observers.base.screenshots', 'gum.observers.macos.keyboard', 'gum.observers.macos.mouse', 'gum.observers.macos.screenshots', 'gum.observers.macos.app_and_browser_logging', 'gum.observers.fallback.keyboard', 'gum.observers.fallback.mouse', 'gum.observers.fallback.screenshots']
datas += collect_data_files('shapely')
hiddenimports += collect_submodules('sqlalchemy')
hiddenimports += collect_submodules('gum.observers')
hiddenimports += collect_submodules('gum.cli')
hiddenimports += collect_submodules('sqlalchemy_utils')
hiddenimports += collect_submodules('pydantic')
hiddenimports += collect_submodules('aiosqlite')
hiddenimports += collect_submodules('shapely')
hiddenimports += collect_submodules('pynput')
hiddenimports += collect_submodules('mss')
# Include tkinter since the macOS app uses Tk for the UI
hiddenimports += collect_submodules('tkinter')


a = Analysis(
    [str(APP_DIR / 'app_entry.py')],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_NAME,
)
app = BUNDLE(
    coll,
    name=f'{APP_NAME}.app',
    icon=None,
    bundle_identifier=BUNDLE_IDENTIFIER,
)
