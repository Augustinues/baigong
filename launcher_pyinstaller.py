"""
百工 Baigong — macOS 原生应用入口 (PyInstaller 版)
使用 pywebview 创建原生 macOS 窗口（WKWebView）
"""

import os
import sys
import time
import threading
import logging

# 日志写到文件，方便排查（--windowed 模式下控制台不可用）
LOG_FILE = os.path.expanduser("~/Library/Logs/baigong.log")
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("baigong")
logger.info(f"=== 百工 Baigong v0.2.3 启动 ===")
logger.info(f"PID: {os.getpid()}")
logger.info(f"HERE: {os.path.dirname(os.path.abspath(__file__))}")

HERE = os.path.dirname(os.path.abspath(__file__))

# 确保配置了源码目录（用于 git 更新）
from server.config import config
source = os.path.expanduser("~/Desktop/涂涂/项目开发/agent-company")
if os.path.isdir(os.path.join(source, ".git")):
    config.set("system.source_dir", source)


def wait_for_server(url: str, timeout: int = 30) -> bool:
    """等待服务就绪"""
    import urllib.request
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = urllib.request.urlopen(url, timeout=2)
            if r.status == 200:
                return True
        except Exception as e:
            logger.debug(f"等待服务... {e}")
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

    # 等待服务就绪（最多 30 秒）
    url = "http://127.0.0.1:8000"
    ready = wait_for_server(url, timeout=30)
    if not ready:
        logger.warning("服务启动超时，仍尝试打开窗口")
    else:
        logger.info("服务就绪")

    # 创建原生 macOS 窗口（WKWebView）
    logger.info("正在创建 pywebview 窗口...")
    try:
        import webview
        logger.info(f"pywebview 版本: {getattr(webview, '__version__', '?')}")

        window = webview.create_window(
            title="百工 Baigong",
            url=url,
            width=1280,
            height=800,
            min_size=(800, 600),
            resizable=True,
            fullscreen=False,
            text_select=True,
            confirm_close=True,
        )
        logger.info("窗口创建成功，启动事件循环...")
        webview.start(
            debug=True,
            http_server=False,
            storage_path=os.path.join(HERE, ".webview_cache"),
        )
    except Exception as e:
        logger.exception(f"pywebview 启动失败: {e}")
        # 兜底：打开浏览器
        import subprocess
        logger.info("降级：用浏览器打开")
        subprocess.run(["open", url], check=False)
        # 保持进程存活
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
