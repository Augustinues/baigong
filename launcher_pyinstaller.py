"""
百工 Baigong — macOS 原生应用入口 (PyInstaller 版)
改用默认浏览器打开，替代 pywebview（WKWebView 不稳定）
"""

import os
import sys
import time
import threading
import logging
import subprocess

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
    # 启动服务
    t = threading.Thread(target=start_server, daemon=True)
    t.start()

    # 等待服务就绪（最多 20 秒）
    ready = wait_for_server("http://127.0.0.1:8000/", timeout=20)
    if not ready:
        logger.warning("服务启动超时（可能端口被占用），仍尝试打开浏览器")
    else:
        logger.info("服务就绪")

    # 用默认浏览器打开
    url = "http://127.0.0.1:8000"
    logger.info(f"在默认浏览器中打开 {url}")
    subprocess.run(["open", url], check=False)

    # 保持进程存活（浏览器关闭后保留服务）
    print(f"\n百工 Baigong 服务已启动: {url}")
    print("按 Ctrl+C 停止服务")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("服务停止")
        sys.exit(0)


if __name__ == "__main__":
    main()
