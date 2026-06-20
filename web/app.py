"""百工 Web Demo — FastAPI 应用"""

import asyncio
import json
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .simulator import Simulator, format_state

app = FastAPI(title="百工 Baigong Demo", version="0.2.1")

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=str(HERE / "templates"))
app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")

sim = Simulator(speed=1.0)
sim_task: asyncio.Task | None = None


# ── 页面 ──

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/state")
async def get_state():
    """获取完整状态（JSON）"""
    return format_state(sim)


# ── 控制 ──

@app.post("/start")
async def start():
    global sim, sim_task
    if sim.running:
        return {"ok": False, "error": "已经在运行中"}

    # 新模拟器（重置状态）
    sim = Simulator(speed=sim.speed)

    sim_task = asyncio.create_task(sim.run())
    return {"ok": True}


@app.post("/stop")
async def stop():
    global sim_task
    if sim_task:
        sim_task.cancel()
        sim_task = None
    sim.running = False
    return {"ok": True}


@app.post("/speed/{value}")
async def set_speed(value: float):
    sim.speed = max(0.1, min(10.0, value))
    return {"ok": True, "speed": sim.speed}


# ── SSE 实时推送 ──

@app.get("/events")
async def sse_events(request: Request):
    async def event_stream():
        # 先发当前状态
        yield f"data: {json.dumps(format_state(sim), ensure_ascii=False)}\n\n"
        last_step = sim.step

        while True:
            if await request.is_disconnected():
                break

            # 等新事件
            try:
                await asyncio.wait_for(sim._event.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                # 超时也推送一次（心跳）
                pass

            if sim.step != last_step or sim.finished:
                last_step = sim.step
                yield f"data: {json.dumps(format_state(sim), ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
