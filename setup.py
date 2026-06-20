"""
百工 Baigong — macOS 应用打包脚本

构建 .app:
    python setup.py py2app

构建 .dmg（自动）:
    python setup.py py2app
    python setup.py dmg
"""

import sys
import os
from setuptools import setup

APP_NAME = "百工 Baigong"
APP = ['launcher.py']

DATA_FILES = [
    # 前端文件
    ('docs', ['docs/index.html']),
]

OPTIONS = {
    'argv_emulation': False,
    'iconfile': 'baigong.icns',
    'packages': [
        'uvicorn', 'fastapi', 'starlette', 'pydantic',
        'agent_sdk', 'server',
        'jinja2', 'markupsafe', 'yaml',
        'webview', 'pywebview',
    ],
    'includes': [
        'asyncio', 'logging', 'json', 'os', 'sys', 'time',
        'threading', 'webbrowser', 're',
    ],
    'excludes': [
        'tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
        'wx', 'matplotlib', 'scipy', 'pandas',
        'numpy', 'notebook', 'jupyter',
    ],
    'plist': {
        'CFBundleName': APP_NAME,
        'CFBundleDisplayName': APP_NAME,
        'CFBundleIdentifier': 'com.baigong.agent',
        'CFBundleVersion': '0.2.2',
        'CFBundleShortVersionString': '0.2.2',
        'CFBundleExecutable': APP_NAME,
        'CFBundlePackageType': 'APPL',
        'NSHighResolutionCapable': True,
        'NSHumanReadableCopyright': '© 2025 百工 Baigong',
        'LSBackgroundOnly': False,
        'LSUIElement': False,  # 显示 Dock 图标
    },
    'site_packages': True,
    'resources': ['docs/index.html'],
}

setup(
    name=APP_NAME,
    version='0.2.2',
    description='百工 Baigong — 多 Agent 协作系统',
    long_description='自我进化的多Agent协作系统。每个Agent是独立个体，通过消息和看板异步协作。',
    author='百工 Team',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
)
