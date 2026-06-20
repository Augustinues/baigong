"""
百工 Baigong — macOS 应用打包脚本

构建 .app:
    python setup.py py2app

构建 .dmg:
    python setup.py py2app
    # 然后手动或使用 create-dmg 制作 DMG
"""

import sys
import os
from setuptools import setup

APP_NAME = "百工 Baigong"
APP = ['run.py']

OPTIONS = {
    'argv_emulation': False,
    'iconfile': os.path.join(os.path.dirname(__file__), 'baigong.icns') if os.path.exists('baigong.icns') else None,
    'packages': [
        'uvicorn', 'fastapi', 'jinja2', 'httpx',
        'agent_sdk', 'server',
    ],
    'includes': [
        'asyncio', 'logging', 'json', 'os', 'sys', 'time',
    ],
    'excludes': ['tkinter', 'PyQt5', 'PyQt6', 'wx'],
    'plist': {
        'CFBundleName': APP_NAME,
        'CFBundleDisplayName': APP_NAME,
        'CFBundleIdentifier': 'com.baigong.agent',
        'CFBundleVersion': '0.1.0',
        'CFBundleShortVersionString': '0.1.0',
        'CFBundleExecutable': APP_NAME,
        'NSHighResolutionCapable': True,
    },
    'site_packages': True,
}

setup(
    name=APP_NAME,
    version='0.1.0',
    description='百工 Baigong — 多 Agent 协作系统',
    app=APP,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
