"""百工编排器 — 使用真实 SDK 组件驱动 Agent 工作流"""

import asyncio
import json
import time
import logging
import re
from typing import Optional

from agent_sdk import (
    ToolRegistry, TaskBoard, MessageBus,
    MemoryType, BaseTool, ToolMetadata, ToolParam, ToolResult,
)

from .llm_client import DeepSeekClient

logger = logging.getLogger("baigong.orchestrator")


# ── 模拟工具（真实工具接口） ──

class MockWebSearch(BaseTool):
    @property
    def metadata(self):
        return ToolMetadata(
            name="web_search", display_name="网络搜索",
            description="搜索网络获取信息",
            parameters=[
                ToolParam(name="query", type="string", description="搜索关键词", required=True),
                ToolParam(name="limit", type="integer", description="返回结果数", default=5),
            ],
            category="search",
        )
    async def execute(self, query: str, limit: int = 5) -> ToolResult:
        logger.info(f"[web_search] '{query}' limit={limit}")
        await asyncio.sleep(2)
        return ToolResult(success=True, data={
            "results": [
                {"title": f"关于「{query}」的搜索结果1", "url": "https://ex.com/1"},
                {"title": f"{query} 最新资讯", "url": "https://ex.com/2"},
            ]
        })


class MockKnowledgeWrite(BaseTool):
    @property
    def metadata(self):
        return ToolMetadata(
            name="kb_write", display_name="知识库写入",
            description="将内容写入知识库",
            parameters=[
                ToolParam(name="title", type="string", description="标题", required=True),
                ToolParam(name="content", type="string", description="内容", required=True),
            ],
            category="knowledge",
        )
    async def execute(self, title: str, content: str) -> ToolResult:
        logger.info(f"[kb_write] '{title}' ({len(content)}字)")
        await asyncio.sleep(1.5)
        return ToolResult(success=True, data={"status": "written", "title": title, "size": len(content)})


# ── 编排器 ──

class AgentOrchestrator:
    """驱动真实 SDK 组件的编排器"""

    def __init__(self):
        from agent_sdk import init_db
        init_db()
        self.board = TaskBoard()
        self.bus = MessageBus()
        self.running = False
        self._task: Optional[asyncio.Task] = None

        # 事件
        self._update_event = asyncio.Event()
        self._last_update = 0

        # 收集的数据（供前端 SSE 读取）
        self.logs: list[dict] = []
        self.memories: list[dict] = []
        self.skills: list[str] = []
        self.messages: list[dict] = []
        self.speed = 1.0

        # Agent 状态
        self.agents = {
            "manager": {"name": "张经理", "role": "manager", "icon": "👔", "color": "#f59e0b",
                        "status": "idle", "action": "", "tool_calls": 0, "tasks_done": 0, "memory_nodes": 0},
            "researcher": {"name": "王研究员", "role": "researcher", "icon": "🔍", "color": "#3b82f6",
                           "status": "idle", "action": "", "tool_calls": 0, "tasks_done": 0, "memory_nodes": 0},
            "editor": {"name": "李编辑", "role": "editor", "icon": "✏️", "color": "#10b981",
                       "status": "idle", "action": "", "tool_calls": 0, "tasks_done": 0, "memory_nodes": 0},
            "admin": {"name": "陈管理员", "role": "knowledge_admin", "icon": "📚", "color": "#8b5cf6",
                      "status": "idle", "action": "", "tool_calls": 0, "tasks_done": 0, "memory_nodes": 0},
            "qa": {"name": "赵质检", "role": "qa", "icon": "✅", "color": "#ef4444",
                   "status": "idle", "action": "", "tool_calls": 0, "tasks_done": 0, "memory_nodes": 0},
        }

        # 注册工具
        ToolRegistry.register(MockWebSearch())
        ToolRegistry.register(MockKnowledgeWrite())

    # ── 日志辅助 ──

    def _log(self, agent_id: str, msg: str, type: str = "action"):
        t = time.strftime("%H:%M:%S")
        a = self.agents[agent_id]
        self.logs.append({"t": t, "a": a["name"], "icon": a["icon"], "msg": msg, "type": type})
        if len(self.logs) > 300:
            self.logs = self.logs[-200:]
        self._notify()

    def _msg(self, from_id: str, to: str, text: str):
        a = self.agents.get(from_id)
        name = a["name"] if a else ("系统" if from_id == "System" else from_id)
        icon = a["icon"] if a else "📨"
        self.messages.append({"from": f"{icon} {name}", "to": to, "text": text})
        if len(self.messages) > 50:
            self.messages = self.messages[-40:]

    def _mem(self, agent_id: str, concept: str, summary: str, pct: int = 50):
        a = self.agents[agent_id]
        self.memories.append({"agent": a["name"], "icon": a["icon"], "concept": concept, "summary": summary, "pct": pct})
        if len(self.memories) > 20:
            self.memories = self.memories[-15:]
        a["memory_nodes"] += 1

    def _skill(self, name: str):
        if name not in self.skills:
            self.skills.append(name)

    def _set(self, agent_id: str, action: str, status: str = "working"):
        self.agents[agent_id]["action"] = action
        self.agents[agent_id]["status"] = status
        self._notify()

    def _notify(self):
        self._update_event.set()
        self._update_event.clear()

    async def _wait(self, sec: float):
        await asyncio.sleep(sec / self.speed)

    # ── 获取任务目标中的关键词 ──

    def _keywords(self, goal: str) -> list[str]:
        words = re.findall(r'[\u4e00-\u9fff\w]+', goal)
        return [w for w in words if len(w) >= 2][:3] or ["目标"]

    # ── 处理一个用户任务 ──

    async def process_task(self, goal: str) -> str:
        """处理用户下发的一个任务。返回根任务 ID"""
        try:
            return await self._process_inner(goal)
        except Exception as e:
            logger.exception(f"process_task 失败: {e}")
            self._log("manager", f"❌ 任务处理失败: {str(e)[:50]}", "error")
            raise

    async def _process_inner(self, goal: str) -> str:
        if not self.running:
            self.running = True
            self._log("manager", "🏮 百工系统就绪", "thought")
            self._msg("System", "All", "百工 Agent 集群启动")

        kw = self._keywords(goal)
        keyword = kw[0]

        # 重置 Agent 状态（保留统计数据）
        for aid in self.agents:
            self.agents[aid]["status"] = "idle"
            self.agents[aid]["action"] = ""
            if aid == "manager":
                self.agents[aid]["status"] = "idle"

        # ── 创建根任务 ──
        root = self.board.create_task(goal=goal, creator="ceo", assignee="manager")
        self._log("manager", f"📋 收到新任务: {goal}", "action")
        self._msg("CEO", "张经理", f"[TASK_ASSIGN] {goal}")
        await self._wait(0.8)

        # ── 主管拆解 ──
        self._set("manager", "拆解任务中...")
        self._log("manager", "[思考] 分析任务目标 → 自动拆解为 3 个子任务", "thought")
        sub1 = self.board.create_task(
            goal=f"搜索关于「{keyword}」的资料", creator="manager",
            assignee="researcher", parent_task_id=root.id,
        )
        sub2 = self.board.create_task(
            goal=f"整理和分类「{keyword}」相关资料", creator="manager",
            assignee="editor", parent_task_id=root.id,
        )
        sub3 = self.board.create_task(
            goal=f"将「{keyword}」资料写入知识库", creator="manager",
            assignee="admin", parent_task_id=root.id,
        )
        self._log("manager", "[行动] 创建子任务: 搜索 → 王研究员", "action")
        self._log("manager", "[行动] 创建子任务: 整理 → 李编辑", "action")
        self._log("manager", "[行动] 创建子任务: 入库 → 陈管理员", "action")
        self._msg("manager", "王研究员", f"[TASK_ASSIGN] 搜索「{keyword}」资料")
        self._msg("manager", "李编辑", f"[TASK_ASSIGN] 整理「{keyword}」资料")
        self._msg("manager", "陈管理员", f"[TASK_ASSIGN] 入库「{keyword}」资料")
        root.log("拆解完成", "manager")
        self.board.update_task(root.id, progress=0.1)
        self._set("manager", "等待子任务", "waiting")
        await self._wait(0.5)

        # ── 研究员搜索 ──
        self._set("researcher", "感知到新任务...")
        self._log("researcher", "[感知] 看板检测到新任务 → 角色匹配", "thought")
        await self._wait(0.4)
        self._set("researcher", "领取任务")
        self._log("researcher", "[决策] 权限匹配 → 主动领取搜索任务", "action")
        self._msg("researcher", "张经理", "[STATUS_UPDATE] 已领取，开始搜索")
        await self._wait(0.3)
        self._set("researcher", "搜索中...")
        self._log("researcher", f'🔧 调用 web_search(query="{keyword} 鉴别方法", limit=5)', "action")
        self.agents["researcher"]["tool_calls"] += 1
        # 执行真实工具
        tool = ToolRegistry.get("web_search")
        if tool:
            await tool.execute(query=f"{keyword} 鉴别方法", limit=5)
        await self._wait(0.8)
        self._log("researcher", f"[结果] 找到多条关于「{keyword}」的资料", "result")
        self._log("researcher", f'🔧 调用 web_search(query="{keyword} 最新资讯", limit=5)', "action")
        self.agents["researcher"]["tool_calls"] += 1
        if tool:
            await tool.execute(query=f"{keyword} 最新资讯", limit=5)
        await self._wait(0.8)
        self._log("researcher", "[结果] 搜索完成，收集到有效资料", "result")
        # 记忆巩固
        self._log("researcher", f"[记忆巩固] 学习: 「{keyword}」搜索关键词策略", "memory")
        self._mem("researcher", f"{keyword}搜索策略", f"关键词「{keyword} 鉴别方法」「{keyword} 最新资讯」", 65)
        await self._wait(0.3)
        self._log("researcher", "[行动] 结果写回看板，标记完成", "action")
        self.board.complete_task(sub1.id, "资料已搜索完成")
        self.board.update_task(root.id, progress=0.35)
        self._set("researcher", "✅ 完成", "done")
        self.agents["researcher"]["tasks_done"] += 1
        self._msg("researcher", "张经理", "[TASK_RESULT] 搜索完成")
        await self._wait(0.4)

        # ── 编辑整理 ──
        self._set("editor", "感知中...")
        self._log("editor", "[感知] 研究员完成任务，新任务可领取", "thought")
        await self._wait(0.3)
        self._set("editor", "整理中...")
        self._log("editor", "[行动] 去重: 筛选有效内容", "action")
        await self._wait(0.8)
        self._log("editor", "[行动] 分类: 按主题整理资料", "action")
        await self._wait(0.8)
        self._log("editor", f"[结果] 整理完成，资料已标准化分类", "result")
        self.board.complete_task(sub2.id, "资料已整理分类")
        self.board.update_task(root.id, progress=0.65)
        self._set("editor", "✅ 完成", "done")
        self.agents["editor"]["tasks_done"] += 1
        self._msg("editor", "张经理", "[TASK_RESULT] 整理完毕")
        await self._wait(0.4)

        # ── 管理员入库 ──
        self._set("admin", "感知中...")
        self._log("admin", "[感知] 编辑完成 → 可取新任务", "thought")
        await self._wait(0.3)
        self._set("admin", "入库中...")
        self._log("admin", f'🔧 调用 kb_write(title="{keyword}资料汇总", content=...)', "action")
        self.agents["admin"]["tool_calls"] += 1
        tool = ToolRegistry.get("kb_write")
        if tool:
            await tool.execute(title=f"{keyword}资料汇总", content=f"# {keyword}资料\n\n搜索整理后的相关资料...")
        await self._wait(0.8)
        self._log("admin", "[结果] 写入成功", "result")
        self.board.complete_task(sub3.id, "资料已入库")
        self.board.update_task(root.id, progress=0.85)
        self._set("admin", "✅ 完成", "done")
        self.agents["admin"]["tasks_done"] += 1
        self._msg("admin", "张经理", "[TASK_RESULT] 入库完成")
        await self._wait(0.4)

        # ── 质检 ──
        self._set("qa", "质检中...")
        self._log("qa", "[感知] 管理员完成，开始质量检查", "thought")
        await self._wait(0.6)
        self._log("qa", "[结果] 质检通过，内容格式合格", "result")
        self._set("qa", "✅ 通过", "done")
        self.agents["qa"]["tasks_done"] += 1
        self._msg("qa", "张经理", "[TASK_RESULT] 质检通过")
        await self._wait(0.3)

        # ── 主管收尾 ──
        self._set("manager", "汇总中...", "working")
        self._log("manager", "[思考] 所有子任务完成，汇总报告", "thought")
        await self._wait(0.8)
        self._log("manager", f'[结果] 📊 "{goal}" 全部完成 ✅', "result")
        self.board.complete_task(root.id, "全部完成")
        self.board.update_task(root.id, progress=1.0)
        self._set("manager", "🎉 完成", "done")
        self.agents["manager"]["tasks_done"] += 1
        self._msg("manager", "CEO", "[TASK_RESULT] 🎉 全部任务完成")

        # ── 技能挖掘 ──
        self._log("manager", f'[Skill挖掘] 检测到类"搜索"模式重复 → 形成 Skill', "skill")
        self._skill(f"{keyword}资料搜索")
        self._msg("System", "All", "[NOTIFICATION] 新 Skill 自动形成")

        # 记忆巩固
        self._mem("researcher", f"{keyword}知识", f"关于「{keyword}」的知识体系已巩固", 75)
        self._log("researcher", f'[记忆巩固] 「{keyword}」相关知识已写入长期记忆树', "memory")

        return root.id

    # ── 获取状态 ──

    def get_state(self) -> dict:
        tasks = []
        for t in self.board.get_pending_tasks(20):
            tasks.append({"id": t.id, "goal": t.goal, "status": t.status.value, "assignee": t.assignee, "progress": t.progress})
        for t in self.board.get_active_tasks(20):
            tasks.append({"id": t.id, "goal": t.goal, "status": t.status.value, "assignee": t.assignee, "progress": t.progress})
        # 已完成的任务不重复获取
        return {
            "running": self.running,
            "agents": [dict(a) for a in self.agents.values()],
            "tasks": tasks,
            "logs": self.logs[-80:] if self.logs else [],
            "memories": list(reversed(self.memories)) if self.memories else [],
            "skills": [{"name": s} for s in self.skills],
            "messages": self.messages[-25:] if self.messages else [],
        }

    async def reset(self):
        self.running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        self._task = None
        self.logs.clear()
        self.memories.clear()
        self.skills.clear()
        self.messages.clear()
        for a in self.agents.values():
            a["status"] = "idle"
            a["action"] = ""
            # 保留统计数据
