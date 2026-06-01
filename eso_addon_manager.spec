# -*- mode: python ; coding: utf-8 -*-
import sys

a = Analysis(
    ['run.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'lxml.etree',
        'lxml._elementpath',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'unittest'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ESO Addon Manager',
    debug=False,
    strip=False,
    upx=True,
    console=False,           # no console window on Windows
    argv_emulation=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='ESO Addon Manager',
)
