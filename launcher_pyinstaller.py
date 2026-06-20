"""
百工 Baigong — macOS 原生应用入口 (PyInstaller 版)
"""

import os
import sys
import time
import threading
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("baigong")

HERE = os.path.dirname(os.path.abspath(__file__))

# 确保配置了源码目录（用于 git 更新）
from server.config import config
source = os.path.expanduser("~/Desktop/涂涂/项目开发/agent-company")
if os.path.isdir(os.path.join(source, ".git")):
    config.set("system.source_dir", source)


def wait_for_server(url: str, timeout: int = 20) -> bool:
    """等待服务就绪"""
    import urllib.request
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = urllib.request.urlopen(url, timeout=2)
            if r.status == 200:
                return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


def start_server():
    import uvicorn
    host = "127.0.0.1"
    port = 8000
    logger.info(f"启动百工服务端 http://{host}:{port}")
    uvicorn.run(
        "server.main:app",
        host=host,
        port=port,
        log_level="warning",
        reload=False,
    )


def main():
    # 无需 psutil，直接启动服务
    t = threading.Thread(target=start_server, daemon=True)
    t.start()

    # 等待服务就绪（最多 20 秒）
    ready = wait_for_server("http://127.0.0.1:8000/", timeout=20)
    if not ready:
        logger.warning("服务启动超时（可能端口被占用），仍尝试打开界面")

    import webview
    window = webview.create_window(
        title="百工 Baigong",
        url="http://127.0.0.1:8000",
        width=1280,
        height=800,
        min_size=(800, 600),
        resizable=True,
        fullscreen=False,
        text_select=True,
        confirm_close=True,
    )
    webview.start(
        debug=False,
        http_server=False,
        storage_path=os.path.join(HERE, ".webview_cache"),
    )


if __name__ == "__main__":
    main()
