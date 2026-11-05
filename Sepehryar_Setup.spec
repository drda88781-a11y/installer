# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['D:/New folder (4)/INSTALLER/setup_launcher.py'],
    pathex=[],
    binaries=[],
    datas=[('D:/New folder (4)/INSTALLER/scratch/payload.zip', '.'), ('D:/New folder (4)/INSTALLER/assets', 'assets'), ('D:/New folder (4)/INSTALLER/AradVF.ttf', '.')],
    hiddenimports=['psutil', 'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets'],
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
    a.binaries,
    a.datas,
    [],
    name='Sepehryar_Setup',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,
    icon=['D:/New folder (4)/INSTALLER/assets/icons/app_icon.ico'],
)
