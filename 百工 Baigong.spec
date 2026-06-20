# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['launcher_pyinstaller.py'],
    pathex=[],
    binaries=[],
    datas=[('docs', 'docs')],
    hiddenimports=['server.main', 'agent_sdk', 'uvicorn.logging', 'uvicorn.loops.auto', 'uvicorn.loops.asyncio', 'uvicorn.protocols.http.auto', 'uvicorn.protocols.http.h11_impl', 'uvicorn.protocols.websockets.auto', 'uvicorn.protocols.websockets.wsproto_impl'],
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
    name='百工 Baigong',
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
    icon=['baigong.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='百工 Baigong',
)
app = BUNDLE(
    coll,
    name='百工 Baigong.app',
    icon='baigong.icns',
    bundle_identifier=None,
)
