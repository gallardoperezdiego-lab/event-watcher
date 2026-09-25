# -*- mode: python ; coding: utf-8 -*-
# PyInstaller build for Event Watcher.
# Build with:  pyinstaller --noconfirm --distpath ../release EventWatcher.spec
#   Windows -> release/EventWatcher.exe   (single file)
#   macOS   -> release/EventWatcher.app   (app bundle, runs in the background, no Dock icon)
# Only the program and the web interface are packaged. Personal data is never bundled:
# it is created on first launch in the user's own data folder (see paths.py).

import os
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, '..'))
WEB_DIST = os.path.join(ROOT, 'web', 'dist')
if not os.path.isfile(os.path.join(WEB_DIST, 'index.html')):
    raise SystemExit('web/dist/index.html is missing. Run "npm install" and "npm run build" in the web folder first.')

a = Analysis(
    ['launcher.py'],
    pathex=[SPECPATH],
    binaries=[],
    datas=[(WEB_DIST, 'dist')],
    hiddenimports=['certifi'],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy', 'torch', 'pandas', 'PIL'],
    noarchive=False,
)
pyz = PYZ(a.pure)

if sys.platform == 'darwin':
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name='EventWatcher',
        console=False,
        upx=False,
        argv_emulation=False,
    )
    coll = COLLECT(exe, a.binaries, a.datas, name='EventWatcher', upx=False)
    app = BUNDLE(
        coll,
        name='EventWatcher.app',
        icon=None,
        bundle_identifier='org.eventwatcher.desktop',
        version='1.1.0',
        info_plist={
            'CFBundleDisplayName': 'Event Watcher',
            'CFBundleShortVersionString': '1.1.0',
            'NSHighResolutionCapable': True,
            'LSUIElement': True,  # background utility: the interface lives in the browser
        },
    )
else:
    exe = EXE(
        pyz, a.scripts, a.binaries, a.datas, [],
        name='EventWatcher',
        console=False,  # no black console window; the interface opens in the browser
        upx=False,
        runtime_tmpdir=None,
        icon=None,
    )
