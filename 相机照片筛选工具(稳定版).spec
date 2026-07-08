# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main_stable.py'],
    pathex=[],
    binaries=[],
    datas=[('web_app', 'web_app'), ('tkinter_app', 'tkinter_app')],
    hiddenimports=['flask', 'flask_cors', 'PIL._tkinter_finder'],
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
    name='相机照片筛选工具(稳定版)',
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
    icon='app.ico',  # 添加图标文件路径
)
