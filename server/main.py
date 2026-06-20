"""百工 Baigong — FastAPI 服务端（真实 Agent 管理 API）"""

import asyncio
import json
import logging
import os
import shutil
import sys
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel

from agent_sdk import ToolRegistry
from .config import config, PROVIDER_DEFAULTS
from .orchestrator import RealOrchestrator
from .real_tools import (
    WebSearch, WebExtract, FileRead, FileWrite, CodeExec,
)

# ── 版本信息 ──
VERSION = "0.5.0"
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
    provider: str = ""
    api_key: str = ""
    base_url: str = ""

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    tools: Optional[list[str]] = None
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

class ConfigUpdate(BaseModel):
    key: str
    value: str

class ThemeUpdate(BaseModel):
    accent: str


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
        provider=agent.provider,
        api_key=agent.api_key,
        base_url=agent.base_url,
    )
    return {"ok": True, "agent": result}

@app.delete("/api/agents/{agent_id}")
async def api_delete_agent(agent_id: str):
    if agent_id not in orchestrator.agents:
        raise HTTPException(404, "Agent 不存在")
    orchestrator.delete_agent(agent_id)
    return {"ok": True}

@app.get("/api/agents/{agent_id}")
async def api_get_agent(agent_id: str):
    if agent_id not in orchestrator.agents:
        raise HTTPException(404, "Agent 不存在")
    return orchestrator.agents[agent_id].to_dict()

@app.get("/api/providers")
async def api_get_providers():
    return PROVIDER_DEFAULTS

@app.post("/api/theme")
async def api_set_theme(theme: ThemeUpdate):
    config.set("theme.accent", theme.accent)
    return {"ok": True, "accent": theme.accent}

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

    # 检测运行模式
    is_frozen = getattr(sys, "frozen", False)

    # 构建代理配置（先检查环境变量再检查配置文件）
    proxy_url = os.environ.get("ALL_PROXY") or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or ""
    client_kwargs = {"timeout": 15}
    if proxy_url:
        client_kwargs["proxies"] = proxy_url

    try:
        async with httpx_module.AsyncClient(**client_kwargs) as client:
            resp = await client.get(
                f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                headers={"Accept": "application/vnd.github+json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                latest = data.get("tag_name", "").lstrip("v")
                # 找到下载链接（DMG 资产）
                download_url = ""
                for asset in data.get("assets", []):
                    if asset.get("name", "").lower().endswith(".dmg"):
                        download_url = asset.get("browser_download_url", "")
                        break
                return {
                    "current": VERSION,
                    "latest": latest,
                    "has_update": latest != VERSION,
                    "html_url": data.get("html_url", ""),
                    "download_url": download_url,
                    "is_frozen": is_frozen,
                    "body": (data.get("body") or "")[:500],
                }
            # 如果 /latest 失败（比如 token 不足），尝试列出所有 release
            resp2 = await client.get(
                f"https://api.github.com/repos/{GITHUB_REPO}/releases?per_page=1",
                headers={"Accept": "application/vnd.github+json"},
            )
            if resp2.status_code == 200:
                releases = resp2.json()
                if releases:
                    data = releases[0]
                    latest = data.get("tag_name", "").lstrip("v")
                    download_url = ""
                    for asset in data.get("assets", []):
                        if asset.get("name", "").lower().endswith(".dmg"):
                            download_url = asset.get("browser_download_url", "")
                            break
                    return {
                        "current": VERSION,
                        "latest": latest,
                        "has_update": latest != VERSION,
                        "html_url": data.get("html_url", ""),
                        "download_url": download_url,
                        "is_frozen": is_frozen,
                        "body": (data.get("body") or "")[:500],
                    }
            return {"current": VERSION, "latest": VERSION, "has_update": False, "is_frozen": is_frozen, "error": f"GitHub API {resp.status_code}"}
    except Exception as e:
        return {"current": VERSION, "latest": VERSION, "has_update": False, "is_frozen": is_frozen, "error": str(e)[:150]}


@app.post("/api/update/apply")
async def api_apply_update():
    """应用更新：打包版下载 DMG，源码版 git pull"""
    global _current_task
    import subprocess

    is_frozen = getattr(sys, "frozen", False)
    download_url = ""  # 前端在调用前应先调 check 获取 download_url

    # 构建代理配置
    proxy_url = os.environ.get("ALL_PROXY") or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or ""

    if is_frozen:
        # ── 打包版：从 GitHub 下载最新 DMG ──
        # 先获取 download_url
        import httpx as httpx_module
        client_kwargs = {"timeout": 15}
        if proxy_url:
            client_kwargs["proxies"] = proxy_url
        download_path = os.path.expanduser("~/Downloads/Baigong.dmg")
        try:
            async with httpx_module.AsyncClient(**client_kwargs) as client:
                # 获取最新 release 信息
                resp = await client.get(
                    f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                    headers={"Accept": "application/vnd.github+json"},
                )
                if resp.status_code != 200:
                    return {"ok": False, "error": f"无法获取版本信息 (HTTP {resp.status_code})"}
                data = resp.json()
                download_url = ""
                for asset in data.get("assets", []):
                    if asset.get("name", "").lower().endswith(".dmg"):
                        download_url = asset.get("browser_download_url", "")
                        break
                if not download_url:
                    return {"ok": False, "error": "未找到 DMG 下载链接"}

                # 下载
                latest_ver = data.get("tag_name", "?").lstrip("v")
                logger.info(f"开始下载 v{latest_ver} → {download_path}")
                dl_resp = await client.get(download_url, follow_redirects=True)
                if dl_resp.status_code != 200:
                    return {"ok": False, "error": f"下载失败 (HTTP {dl_resp.status_code})"}
                with open(download_path, "wb") as f:
                    f.write(dl_resp.content)
        except Exception as e:
            return {"ok": False, "error": f"下载失败: {str(e)[:150]}"}

        size_mb = os.path.getsize(download_path) / (1024 * 1024)
        return {
            "ok": True,
            "message": f"✅ 已下载最新版 v{latest_ver} ({size_mb:.0f}MB)\n"
                       f"下载位置：{download_path}\n"
                       f"请关闭本应用，打开 {download_path} 安装新版",
            "download_path": download_path,
        }

    # ── 源码版：git pull + 模块重载 ──
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
            index_path.stat()

        return {"ok": True, "message": f"更新完成\n{result.stdout[:200]}"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "git pull 超时"}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


@app.get("/api/update/status")
async def api_update_status():
    """查看当前版本信息"""
    is_frozen = getattr(sys, "frozen", False)
    if is_frozen:
        return {"version": VERSION, "frozen": True, "mode": "app打包版"}
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
        return {"version": VERSION, "frozen": False, "commits": "?", "modified": ""}


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
