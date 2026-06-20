"""
百工 Baigong — macOS .app & .dmg 构建脚本 (PyInstaller)

用法：
    python build_app.py
"""

import os
import shutil
import subprocess
import plistlib

APP_NAME = "百工 Baigong"
HERE = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(HERE, "dist")
APP_PATH = os.path.join(DIST, f"{APP_NAME}.app")
DMG_PATH = os.path.join(DIST, f"{APP_NAME}.dmg")
PLIST_PATH = os.path.join(APP_PATH, "Contents", "Info.plist")


def build():
    if os.path.isdir(DIST):
        for f in os.listdir(DIST):
            fp = os.path.join(DIST, f)
            if f.endswith(".app") or f.endswith(".dmg") or f == "build":
                p = os.path.join(DIST, f)
                if os.path.isdir(p):
                    shutil.rmtree(p)
                else:
                    os.remove(p)

    print("🏗️  使用 PyInstaller 构建 .app...")
    subprocess.run([
        "/Users/geogre/.browser-use-env/bin/python3", "-m", "PyInstaller",
        "--name", APP_NAME,
        "--onedir",
        "--windowed",
        "--icon", "baigong.icns",
        "--add-data", "docs:docs",
        "--hidden-import", "server.main",
        "--hidden-import", "agent_sdk",
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.loops.asyncio",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.http.h11_impl",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--hidden-import", "uvicorn.protocols.websockets.wsproto_impl",
        "--collect-all", "webview",
        "launcher_pyinstaller.py",
    ], check=True, cwd=HERE)

    # 修复 Info.plist
    print("🔧 修复 Info.plist...")
    with open(PLIST_PATH, "rb") as f:
        plist = plistlib.load(f)

    # 1. 确保 bundle identifier 正确（启动台显示）
    plist["CFBundleIdentifier"] = "com.baigong.agent"
    plist["CFBundleDisplayName"] = "百工 Baigong"
    plist["CFBundleName"] = "百工 Baigong"
    plist["CFBundleShortVersionString"] = "0.6.1"
    plist["CFBundleVersion"] = "0.6.1"

    # 2. 添加 NSAllowsLocalNetworking — WKWebView 需要才能连 localhost HTTP
    if "NSAppTransportSecurity" not in plist:
        plist["NSAppTransportSecurity"] = {}
    plist["NSAppTransportSecurity"]["NSAllowsLocalNetworking"] = True

    with open(PLIST_PATH, "wb") as f:
        plistlib.dump(plist, f)
    print("  ✅ Info.plist 已更新")

    # 3. 重新签名（修改 Info.plist 后会破坏签名）
    print("🔏 重新签名...")
    subprocess.run([
        "codesign", "--force", "--deep", "--sign", "-",
        "--preserve-metadata=identifier,entitlements",
        APP_PATH,
    ], check=True, capture_output=True)
    print("  ✅ 签名完成")

    # 计算大小
    total = 0
    for dirpath, dirnames, filenames in os.walk(APP_PATH):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                total += os.path.getsize(fp)
            except:
                pass
    print(f"✅ .app 构建完成: {APP_PATH} ({total/1024/1024:.0f} MB)")
    return True


def make_dmg():
    if not os.path.isdir(APP_PATH):
        print("❌ 未找到 .app")
        return False

    print("💿 制作 DMG...")
    staging = os.path.join(DIST, "dmg_staging")
    if os.path.isdir(staging):
        shutil.rmtree(staging)
    os.makedirs(staging)

    shutil.copytree(APP_PATH, os.path.join(staging, f"{APP_NAME}.app"), symlinks=True)
    os.symlink("/Applications", os.path.join(staging, "Applications"))

    if os.path.exists(DMG_PATH):
        os.remove(DMG_PATH)

    subprocess.run([
        "hdiutil", "create",
        "-volname", APP_NAME,
        "-srcfolder", staging,
        "-ov",
        "-format", "UDZO",
        "-imagekey", "zlib-level=9",
        DMG_PATH,
    ], check=True)

    shutil.rmtree(staging)

    dmg_size = os.path.getsize(DMG_PATH) / (1024*1024)
    print(f"✅ DMG 完成: {DMG_PATH} ({dmg_size:.0f} MB)")
    return True


if __name__ == "__main__":
    build()
    make_dmg()
