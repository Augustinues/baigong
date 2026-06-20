"""百工 Baigong — macOS 应用启动器

作为 py2app 的入口点，自动启动服务器并打开浏览器。
双击 .app 即可使用，无需终端。
"""

import os
import sys
import time
import threading
import webbrowser

# 确保能找到 agent_sdk
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# ── 自动打开浏览器（延迟 2 秒等服务器就绪） ──
def _open_browser(host: str, port: int):
    time.sleep(2.0)
    url = f"http://{host}:{port}"
    webbrowser.open(url)


def main():
    host = "127.0.0.1"
    port = int(os.environ.get("PORT", 8000))

    # 后台线程打开浏览器
    threading.Thread(target=_open_browser, args=(host, port), daemon=True).start()

    # 启动 uvicorn
    import uvicorn
    uvicorn.run(
        "server.main:app",
        host=host,
        port=port,
        log_level="info",
        reload=False,
    )


if __name__ == "__main__":
    main()
