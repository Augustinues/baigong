"""百工 Baigong Server — 启动入口

运行方式：
    python run.py

浏览器打开 http://localhost:8000
"""

import os
import sys

# 确保能导入 agent_sdk
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))

    print("🏮 百工 Baigong — 多 Agent 协作系统")
    print("=" * 50)
    print(f"  浏览器打开: http://localhost:{port}")
    print(f"  按 Ctrl+C 停止")
    print("=" * 50)

    uvicorn.run(
        "server.main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False,
    )
