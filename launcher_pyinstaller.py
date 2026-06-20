"""
百工 Baigong — macOS 原生应用入口 (PyInstaller 版)
"""

import os
import sys
import signal
import subprocess
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


def kill_old_process():
    """杀掉旧版本的 百工 Baigong 进程"""
    import psutil
    current_pid = os.getpid()
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            info = proc.info
            if info["pid"] == current_pid:
                continue
            cmd = " ".join(info["cmdline"] or [])
            if "百工 Baigong" in cmd or "baigong" in cmd.lower():
                logger.info(f"发现旧进程 PID {info['pid']}，正在关闭...")
                proc.terminate()
                proc.wait(timeout=3)
                logger.info(f"已关闭旧进程 PID {info['pid']}")
        except (psutil.NoSuchProcess, psutil.AccessDenied, subprocess.TimeoutExpired):
            pass


def wait_for_server(url: str, timeout: int = 15) -> bool:
    """等待服务就绪"""
    import httpx
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = httpx.get(url, timeout=2)
            if r.status_code == 200:
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
    # 启动前先杀掉旧进程
    try:
        kill_old_process()
    except Exception as e:
        logger.warning(f"清理旧进程失败: {e}")

    # 启动服务端线程
    t = threading.Thread(target=start_server, daemon=True)
    t.start()

    # 等待服务就绪
    import httpx
    ready = wait_for_server("http://127.0.0.1:8000/", timeout=15)
    if not ready:
        logger.error("服务启动超时，仍然尝试打开界面")

    # 启动 WebView
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
