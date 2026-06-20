#!/usr/bin/env bash
cd "$(dirname "$0")"
echo "🏮 百工 Baigong Demo 启动中..."
echo "浏览器打开: http://localhost:8000"
pip install -q fastapi uvicorn jinja2 2>/dev/null
python3 run_demo.py
