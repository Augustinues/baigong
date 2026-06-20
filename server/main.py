"""百工 Baigong — FastAPI 服务端"""

import asyncio
import json
import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel

from .orchestrator import AgentOrchestrator

logger = logging.getLogger("baigong.server")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="百工 Baigong Server", version="0.1.0")

HERE = Path(__file__).parent.parent
DOCS = HERE / "docs"

orchestrator = AgentOrchestrator()
_current_task: asyncio.Task | None = None

# Frontend
FRONTEND_PATH = DOCS / "index.html"
if FRONTEND_PATH.exists():
    @app.get("/", response_class=HTMLResponse)
    async def serve_frontend():
        return FRONTEND_PATH.read_text(encoding="utf-8")


class TaskInput(BaseModel):
    goal: str


@app.get("/api/state")
async def api_state():
    return orchestrator.get_state()


@app.post("/api/task")
async def api_task(input: TaskInput):
    global _current_task
    # 在后台运行，让 SSE 推送实时更新
    orchestrator._log("manager", f"📋 CEO 下发新任务: {input.goal}", "action")
    _current_task = asyncio.create_task(orchestrator.process_task(input.goal))
    return {"ok": True, "task_id": f"task_{id(input.goal)}"}


@app.post("/api/start")
async def api_start():
    orchestrator.running = True
    orchestrator._log("manager", "🏮 百工系统就绪", "thought")
    return {"ok": True, "agents": list(orchestrator.agents.keys())}


@app.post("/api/stop")
async def api_stop():
    global _current_task
    if _current_task and not _current_task.done():
        _current_task.cancel()
        try:
            await _current_task
        except (asyncio.CancelledError, Exception):
            pass
    await orchestrator.reset()
    return {"ok": True}


@app.get("/api/events")
async def sse_events(request: Request):
    last_state = ""

    async def event_stream():
        nonlocal last_state
        while True:
            if await request.is_disconnected():
                break
            try:
                await asyncio.wait_for(orchestrator._update_event.wait(), timeout=2.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass

            state = orchestrator.get_state()
            payload = json.dumps(state, ensure_ascii=False)
            if payload != last_state:
                last_state = payload
                yield f"data: {payload}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
