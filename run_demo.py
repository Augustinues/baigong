"""百工 Baigong Demo Web 服务器

运行方式：
    python run_demo.py

然后在浏览器打开 http://localhost:8000
"""

import uvicorn

if __name__ == "__main__":
    print("🏮 百工 Baigong Demo")
    print("=" * 40)
    print("浏览器打开: http://localhost:8000")
    print("按 Ctrl+C 停止")
    print("=" * 40)
    import uvicorn
    uvicorn.run("web.app:app", host="0.0.0.0", port=8000, reload=False)
