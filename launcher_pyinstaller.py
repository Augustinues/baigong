"""百工 Baigong — macOS 原生应用入口 (PySide6 版)
纯 Python 桌面 GUI，不再依赖 pywebview / HTML / JS
"""

import os
import sys
import time
import threading
import logging

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
logger.info(f"=== 百工 Baigong v0.8.0 启动 (纯 Python PySide6) ===")
logger.info(f"PID: {os.getpid()}")
logger.info(f"HERE: {os.path.dirname(os.path.abspath(__file__))}")

HERE = os.path.dirname(os.path.abspath(__file__))

# 确保配置了源码目录
from server.config import config
source = os.path.expanduser("~/Desktop/涂涂/项目开发/agent-company")
if os.path.isdir(os.path.join(source, ".git")):
    config.set("system.source_dir", source)


def wait_for_server(url: str, timeout: int = 30) -> bool:
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
    # 启动 FastAPI 服务端
    t = threading.Thread(target=start_server, daemon=True)
    t.start()

    # 等待服务就绪
    url = "http://127.0.0.1:8000"
    ready = wait_for_server(url, timeout=30)
    if not ready:
        logger.warning("服务启动超时，仍尝试打开窗口")
    else:
        logger.info("服务就绪")

    # 启动 PySide6 主窗口（纯 Python GUI）
    logger.info("正在创建 PySide6 主窗口...")
    try:
        from PySide6.QtWidgets import QApplication
        from frontend.main_window import BaigongMainWindow

        # 确保 QApplication 是唯一的
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        app.setApplicationName("百工 Baigong")
        app.setOrganizationName("Baigong")

        window = BaigongMainWindow()
        window.show()

        logger.info("PySide6 窗口创建成功，进入事件循环...")
        sys.exit(app.exec())
    except Exception as e:
        logger.exception(f"PySide6 启动失败: {e}")
        # 兜底：打开浏览器
        import subprocess
        logger.info("降级：用浏览器打开")
        subprocess.run(["open", url], check=False)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
