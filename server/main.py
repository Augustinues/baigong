"""百工 Baigong — FastAPI 服务端（真实 Agent 管理 API）"""

import asyncio
import json
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel

from agent_sdk import ToolRegistry
from .config import config
from .orchestrator import RealOrchestrator
from .real_tools import (
    WebSearch, WebExtract, FileRead, FileWrite, CodeExec,
)

# ── 版本信息 ──
VERSION = "0.1.0"
GITHUB_REPO = "Augustinues/baigong"
HERE = Path(__file__).parent.parent
DOCS = HERE / "docs"

logger = logging.getLogger("baigong.server")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="百工 Baigong Server", version=VERSION)

# 前端路径
FRONTEND_PATH = DOCS / "index.html"
SETUP_PATH = DOCS / "setup.html"

# 注册真实工具
ToolRegistry.register(WebSearch())
ToolRegistry.register(WebExtract())
ToolRegistry.register(FileRead())
ToolRegistry.register(FileWrite())
ToolRegistry.register(CodeExec())

# 编排器
orchestrator = RealOrchestrator()
_current_task: Optional[asyncio.Task] = None

# ── 请求模型 ──

class TaskInput(BaseModel):
    goal: str
    agent_id: str = ""

class AgentCreate(BaseModel):
    name: str
    role: str = "worker"
    tools: list[str] = ["web_search", "file_read"]
    system_prompt: str = ""
    model: str = ""

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    tools: Optional[list[str]] = None
    system_prompt: Optional[str] = None
    model: Optional[str] = None

class ConfigUpdate(BaseModel):
    key: str
    value: str


# ── 前端 ──

def _get_frontend() -> HTMLResponse:
    """根据是否已配置返回对应前端"""
    if not config.get("llm.api_key"):
        setup_path = HERE / "docs" / "setup.html"
        if setup_path.exists():
            return HTMLResponse(setup_path.read_text(encoding="utf-8"))
    if FRONTEND_PATH.exists():
        return HTMLResponse(FRONTEND_PATH.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>百工 Baigong</h1><p>前端文件未找到</p>")

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    return _get_frontend()


# ── 配置 API ──

@app.get("/api/config")
async def api_get_config():
    return config.load()

@app.post("/api/config")
async def api_set_config(update: ConfigUpdate):
    config.set(update.key, update.value)
    return {"ok": True}

@app.post("/api/config/init")
async def api_init_config(data: dict):
    """初始化配置（首次设置向导用）"""
    for key, value in data.items():
        config.set(key, value)
    # 如果配了 API Key，初始化 LLM
    if data.get("llm.api_key"):
        await orchestrator.initialize()
    return {"ok": True}


# ── 系统 API ──

@app.get("/api/state")
async def api_state():
    return orchestrator.get_state()

@app.post("/api/start")
async def api_start():
    """启动系统"""
    if not config.get("llm.api_key"):
        return JSONResponse({"ok": False, "error": "请先配置 API Key"}, status_code=400)

    ok = await orchestrator.initialize()
    if not ok:
        return JSONResponse({"ok": False, "error": "LLM 初始化失败"}, status_code=500)

    orchestrator.running = True
    # 从配置加载 Agent
    orchestrator.load_agents_from_config()

    # 如果没有 Agent，创建默认的
    if not orchestrator.agents:
        orchestrator.create_agent(name="助手", role="通用助手",
                                   tools=["web_search", "web_extract", "file_read", "file_write", "code_exec"],
                                   system_prompt="你是一个全能 AI 助手。使用工具帮助用户完成各种任务。")

    orchestrator._log("system", "🏮 百工系统就绪", "thought")
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


# ── Agent CRUD API ──

@app.get("/api/agents")
async def api_list_agents():
    return {aid: a.to_dict() for aid, a in orchestrator.agents.items()}

@app.post("/api/agents")
async def api_create_agent(agent: AgentCreate):
    if not orchestrator.running:
        # 允许在未启动时创建（存配置）
        pass
    result = orchestrator.create_agent(
        name=agent.name,
        role=agent.role,
        tools=agent.tools,
        system_prompt=agent.system_prompt,
        model=agent.model,
    )
    return {"ok": True, "agent": result}

@app.delete("/api/agents/{agent_id}")
async def api_delete_agent(agent_id: str):
    if agent_id not in orchestrator.agents:
        raise HTTPException(404, "Agent 不存在")
    orchestrator.delete_agent(agent_id)
    return {"ok": True}

@app.patch("/api/agents/{agent_id}")
async def api_update_agent(agent_id: str, update: AgentUpdate):
    if agent_id not in orchestrator.agents:
        raise HTTPException(404, "Agent 不存在")
    updates = {k: v for k, v in update.model_dump().items() if v is not None}
    orchestrator.update_agent(agent_id, updates)
    return {"ok": True}


# ── 任务 API ──

@app.post("/api/task")
async def api_task(input: TaskInput):
    global _current_task
    if not orchestrator.running:
        return JSONResponse({"ok": False, "error": "系统未启动"}, status_code=400)
    if not orchestrator.llm_client:
        return JSONResponse({"ok": False, "error": "LLM 未就绪"}, status_code=400)

    orchestrator._log("system", f"📋 下发任务: {input.goal}", "action")
    _current_task = asyncio.create_task(
        orchestrator.process_task(input.goal, input.agent_id)
    )
    return {"ok": True, "task_id": f"task_{uuid.uuid4().hex[:6]}"}


# ── SSE 实时推送 ──

@app.get("/api/update/check")
async def api_check_update():
    """检查 GitHub 是否有新版本"""
    import httpx as httpx_module
    try:
        async with httpx_module.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                headers={"Accept": "application/vnd.github+json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                latest = data.get("tag_name", "").lstrip("v")
                return {
                    "current": VERSION,
                    "latest": latest,
                    "has_update": latest != VERSION,
                    "html_url": data.get("html_url", ""),
                    "body": (data.get("body") or "")[:300],
                }
            return {"current": VERSION, "latest": VERSION, "has_update": False, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"current": VERSION, "latest": VERSION, "has_update": False, "error": str(e)[:100]}


@app.post("/api/update/apply")
async def api_apply_update():
    """从 GitHub 拉取最新代码并重启"""
    global _current_task
    import subprocess, sys

    source_dir = config.get("system.source_dir", str(HERE))
    if not os.path.isdir(os.path.join(source_dir, ".git")):
        return {"ok": False, "error": "未找到 git 仓库，无法更新"}

    try:
        # 停止当前任务
        if _current_task and not _current_task.done():
            _current_task.cancel()
            try:
                await _current_task
            except:
                pass

        # git pull
        result = subprocess.run(
            ["git", "pull"],
            cwd=source_dir,
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return {"ok": False, "error": f"git pull 失败: {result.stderr[:200]}"}

        # 重新加载模块
        import importlib
        for mod_name in list(sys.modules.keys()):
            if mod_name.startswith("server.") or mod_name.startswith("agent_sdk"):
                importlib.reload(sys.modules[mod_name])

        # 清除 docs 文件缓存
        index_path = DOCS / "index.html"
        if index_path.exists():
            index_path.stat()  # 刷新 stat 缓存

        return {"ok": True, "message": f"更新完成\n{result.stdout[:200]}"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "git pull 超时"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


@app.get("/api/update/status")
async def api_update_status():
    """查看当前版本和 git 状态"""
    import subprocess
    source_dir = config.get("system.source_dir", str(HERE))
    try:
        r = subprocess.run(["git", "log", "--oneline", "-3"], cwd=source_dir,
                          capture_output=True, text=True, timeout=5)
        commits = r.stdout.strip()
        r2 = subprocess.run(["git", "status", "--short"], cwd=source_dir,
                           capture_output=True, text=True, timeout=5)
        modified = r2.stdout.strip()
        return {"version": VERSION, "commits": commits, "modified": modified}
    except:
        return {"version": VERSION, "commits": "?", "modified": ""}


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
