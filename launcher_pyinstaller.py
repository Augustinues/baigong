"""
百工 Baigong — macOS 原生应用入口 (PyInstaller 版)
"""

import os
import sys
import threading
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("baigong")

HERE = os.path.dirname(os.path.abspath(__file__))


def start_server():
    """在后台线程启动 uvicorn 服务器"""
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
    t = threading.Thread(target=start_server, daemon=True)
    t.start()

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
