"""
百工 Baigong — DMG 制作脚本

用法：
    # 先构建 .app
    python setup.py py2app

    # 然后制作 .dmg
    python make_dmg.py
"""

import os
import subprocess
import shutil
import sys

APP_NAME = "百工 Baigong"
HERE = os.path.dirname(os.path.abspath(__file__))
APP_PATH = os.path.join(HERE, "dist", f"{APP_NAME}.app")
DMG_PATH = os.path.join(HERE, "dist", f"{APP_NAME}.dmg")
STAGING = os.path.join(HERE, "dist", "dmg_staging")


def create_dmg():
    if not os.path.isdir(APP_PATH):
        print(f"❌ 未找到 .app: {APP_PATH}")
        print("   请先运行: python setup.py py2app")
        sys.exit(1)

    # 清理
    if os.path.isdir(STAGING):
        shutil.rmtree(STAGING)
    if os.path.exists(DMG_PATH):
        os.remove(DMG_PATH)

    # 创建暂存目录并复制 .app
    os.makedirs(STAGING)
    dst = os.path.join(STAGING, f"{APP_NAME}.app")
    print(f"📦 复制 .app 到暂存目录...")
    shutil.copytree(APP_PATH, dst, symlinks=True)

    # 创建 Applications 别名
    os.symlink("/Applications", os.path.join(STAGING, "Applications"))

    # 使用 hdiutil 创建 DMG
    print(f"💿 制作 DMG...")
    subprocess.run([
        "hdiutil", "create",
        "-volname", APP_NAME,
        "-srcfolder", STAGING,
        "-ov",
        "-format", "UDZO",
        "-imagekey", "zlib-level=9",
        DMG_PATH,
    ], check=True)

    # 清理
    shutil.rmtree(STAGING)

    size = os.path.getsize(DMG_PATH) / (1024*1024)
    print(f"✅ DMG 制作完成: {DMG_PATH}")
    print(f"   大小: {size:.1f} MB")
    print(f"   打开即可安装到 Applications 文件夹")


if __name__ == "__main__":
    create_dmg()
