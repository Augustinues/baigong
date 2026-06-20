"""百工 Demo 模拟器 — 让 Agent 像游戏一样协作"""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentState:
    id: str
    name: str
    role: str
    icon: str
    status: str = "idle"       # idle | working | waiting | done
    action: str = ""
    task_id: str = ""
    tool_calls: int = 0
    tasks_done: int = 0
    memory_nodes: int = 0
    color: str = "#6b7280"


@dataclass
class TaskCard:
    id: str
    goal: str
    status: str                 # pending | in_progress | done | failed
    assignee: str = ""
    progress: float = 0.0
    result: str = ""
    parent: str = ""


@dataclass
class LogEntry:
    time: str
    agent: str
    icon: str
    text: str
    type: str                   # action | thought | result | skill | memory


@dataclass
class MemoryEntry:
    agent: str
    icon: str
    concept: str
    summary: str
    confidence: float


class Simulator:
    """运行一次完整的百工演示场景"""

    def __init__(self, speed: float = 1.0):
        self.speed = speed
        self.running = False
        self.paused = False
        self.finished = False
        self.step = 0

        # Agents
        self.agents: dict[str, AgentState] = {}
        self._init_agents()

        # Tasks
        self.tasks: dict[str, TaskCard] = {}
        self.task_order: list[str] = []

        # Logs
        self.logs: list[LogEntry] = []
        self.max_logs = 200

        # Memory
        self.memories: list[MemoryEntry] = []

        # Waiters for SSE
        self._event = asyncio.Event()
        self._log_event = asyncio.Event()

    def _init_agents(self):
        roles = [
            ("manager", "张经理", "主管", "👔", "#f59e0b"),
            ("researcher", "王研究员", "研究员", "🔍", "#3b82f6"),
            ("editor", "李编辑", "编辑", "✏️", "#10b981"),
            ("admin", "陈管理员", "管理员", "📚", "#8b5cf6"),
            ("qa", "赵质检", "质检", "✅", "#ef4444"),
        ]
        for rid, name, role, icon, color in roles:
            self.agents[rid] = AgentState(
                id=rid, name=name, role=role, icon=icon, color=color
            )

    def _log(self, agent_id: str, text: str, type: str = "action"):
        agent = self.agents.get(agent_id)
        t = time.strftime("%H:%M:%S")
        entry = LogEntry(
            time=t,
            agent=agent.name if agent else "",
            icon=agent.icon if agent else "•",
            text=text,
            type=type,
        )
        self.logs.append(entry)
        if len(self.logs) > self.max_logs:
            self.logs.pop(0)
        self._log_event.set()
        self._log_event.clear()

    def _add_task(self, goal: str, status: str = "pending", assignee: str = ""):
        tid = f"task_{uuid.uuid4().hex[:6]}"
        task = TaskCard(id=tid, goal=goal, status=status, assignee=assignee)
        self.tasks[tid] = task
        self.task_order.append(tid)
        return task

    def _update_task(self, tid: str, **kw):
        if tid in self.tasks:
            for k, v in kw.items():
                setattr(self.tasks[tid], k, v)

    def _add_memory(self, agent_id: str, concept: str, summary: str, confidence: float = 0.5):
        agent = self.agents.get(agent_id)
        self.memories.append(MemoryEntry(
            agent=agent.name if agent else "",
            icon=agent.icon if agent else "",
            concept=concept,
            summary=summary,
            confidence=confidence,
        ))

    def _set_action(self, agent_id: str, action: str, status: str = "working"):
        agent = self.agents.get(agent_id)
        if agent:
            agent.action = action
            agent.status = status

    async def _wait(self, seconds: float):
        if not self.running:
            raise asyncio.CancelledError()
        while self.paused:
            await asyncio.sleep(0.1)
            if not self.running:
                raise asyncio.CancelledError()
        await asyncio.sleep(seconds / self.speed)
        self.step += 1
        self._event.set()
        self._event.clear()

    async def run(self):
        """运行完整的演示流程"""
        self.running = True
        self.finished = False
        self.logs.clear()
        self.tasks.clear()
        self.memories.clear()
        self.step = 0

        try:
            await self._scene()
        except asyncio.CancelledError:
            pass
        finally:
            self.running = False
            self.finished = True
            self._event.set()
            self._event.clear()

    async def _scene(self):
        """翡翠知识库入库演示场景"""
        s = self._wait

        self._log("manager", "🏮 百工系统启动，各位工匠就位", "thought")

        # ── CEO 下任务 ──
        await s(1.5)
        root_task = self._add_task("收集10篇翡翠鉴别资料并入库", "in_progress", "manager")
        self._log("manager", "📋 CEO 下派新任务：收集10篇翡翠鉴别资料并入库", "action")

        # ── 主管拆解 ──
        await s(1.0)
        self._set_action("manager", "拆解任务中...")
        self._log("manager", "分析任务 → 拆解为3个子任务", "thought")
        self._log("manager", "① 搜索翡翠鉴别资料 → 王研究员", "action")
        self._log("manager", "② 整理去重分类 → 李编辑", "action")
        self._log("manager", "③ 写入知识库 → 陈管理员", "action")
        await s(1.0)

        sub1 = self._add_task("搜索翡翠鉴别资料", "in_progress", "researcher")
        sub2 = self._add_task("整理去重分类", "pending", "editor")
        sub3 = self._add_task("写入知识库", "pending", "admin")
        self._update_task(root_task.id, progress=0.1)

        # ── 研究员搜索 ──
        await s(0.5)
        self._set_action("manager", "等待子任务完成", "waiting")
        self._set_action("researcher", "搜索中...", "working")
        self._log("researcher", "领取任务：搜索翡翠鉴别资料", "action")

        await s(1.2)
        self._log("researcher", "🔧 调用 web_search('翡翠鉴别 A货 B货')", "action")
        self.agents["researcher"].tool_calls += 1
        await s(1.0)
        self._log("researcher", "找到 5 条结果，含百度百科、知乎、小红书文章", "result")
        self._log("researcher", "🔧 调用 web_search('翡翠真假鉴别方法')", "action")
        self.agents["researcher"].tool_calls += 1
        await s(1.0)
        self._log("researcher", "找到 7 条结果，其中2条与前面重复", "result")

        # 记忆巩固
        self._log("researcher", "💭 发现百度百科的翡翠资料质量最高，记住这个经验", "memory")
        self._add_memory("researcher", "翡翠搜索", "百度百科质量最高，用'鉴别 A货 B货'关键词效果好", 0.7)
        self.agents["researcher"].memory_nodes += 1

        await s(0.8)
        self._log("researcher", "搜索完成，共找到 10 篇不重复资料，写上看板", "result")
        self._update_task(sub1.id, status="done", result="10篇资料已搜索完成")
        self._update_task(root_task.id, progress=0.4)
        self._set_action("researcher", "任务完成 ✅", "done")
        self.agents["researcher"].tasks_done += 1

        # ── 编辑整理 ──
        await s(0.8)
        self._set_action("editor", "整理中...", "working")
        self._log("editor", "从看板读取研究员的结果...", "action")
        self._log("editor", "开始整理：去重、分类、格式化", "action")
        await s(1.0)
        self._log("editor", "去重完成：10 → 8 篇（2篇内容高度重复）", "result")
        self._log("editor", "分类整理：科普类3篇 | 鉴定方法类3篇 | 市场行情类2篇", "result")
        await s(0.8)
        self._log("editor", "整理完毕，8篇资料已标准化格式", "result")
        self._update_task(sub2.id, status="done", result="8篇已整理分类")
        self._update_task(root_task.id, progress=0.7)
        self._set_action("editor", "任务完成 ✅", "done")
        self.agents["editor"].tasks_done += 1

        # ── 管理员入库 ──
        await s(0.8)
        self._set_action("admin", "入库中...", "working")
        self._log("admin", "开始写入知识库...", "action")
        await s(0.5)
        self._log("admin", "🔧 调用 kb_write('翡翠鉴别方法汇总')", "action")
        self.agents["admin"].tool_calls += 1
        await s(1.0)
        self._log("admin", "✅ 翡翠鉴别方法汇总 已写入知识库（8篇，3420字）", "result")
        self._log("admin", "🔧 调用 kb_write('翡翠市场行情分析')", "action")
        self.agents["admin"].tool_calls += 1
        await s(0.6)
        self._log("admin", "✅ 翡翠市场行情分析 已写入知识库", "result")
        self._update_task(sub3.id, status="done", result="资料已入库")
        self._update_task(root_task.id, progress=0.9)
        self._set_action("admin", "任务完成 ✅", "done")
        self.agents["admin"].tasks_done += 1

        # ── 质检复核 ──
        await s(0.6)
        self._set_action("qa", "质检中...", "working")
        self._log("qa", "复核入库内容质量...", "action")
        await s(0.8)
        self._log("qa", "抽查完成，内容质量合格，无格式问题", "result")
        self._set_action("qa", "质检通过 ✅", "done")
        self.agents["qa"].tasks_done += 1

        # ── 主管收尾 ──
        await s(0.8)
        self._set_action("manager", "汇总报告中...", "working")
        self._log("manager", "所有子任务完成，汇总报告...", "thought")
        await s(1.0)
        self._log("manager", "📊 最终报告：10篇→整理8篇→入库2篇→全部通过质检", "result")
        self._update_task(root_task.id, status="done", progress=1.0, result="全部完成")

        # 技能挖掘
        self._log("manager", "🎯 技能系统检测到：'搜索'类任务出现3次以上 → 自动形成 Skill", "skill")
        self._log("manager", "🎯 新技能'翡翠搜索'已形成（置信度 0.6，可复用）", "skill")

        # 知识传承
        await s(0.6)
        self._log("researcher", "📤 知识导出：翡翠知识子树的 6 个节点已导出", "memory")
        self._add_memory("researcher", "翡翠知识树", "翡翠根节点下挂搜索经验、来源评估、分类体系", 0.8)
        self.agents["researcher"].memory_nodes += 2

        await s(0.5)
        self._set_action("manager", "全部完成 🎉", "done")
        self._log("manager", "🎉 百工协作完成！8篇翡翠资料已入库", "result")
        self.agents["manager"].tasks_done += 1


def format_state(sim: Simulator) -> dict:
    """将模拟器状态序列化给 Web 前端"""
    return {
        "running": sim.running,
        "paused": sim.paused,
        "finished": sim.finished,
        "step": sim.step,
        "agents": [
            {
                "id": a.id,
                "name": a.name,
                "role": a.role,
                "icon": a.icon,
                "status": a.status,
                "action": a.action,
                "tool_calls": a.tool_calls,
                "tasks_done": a.tasks_done,
                "memory_nodes": a.memory_nodes,
                "color": a.color,
            }
            for a in sim.agents.values()
        ],
        "tasks": [
            {
                "id": t.id,
                "goal": t.goal,
                "status": t.status,
                "assignee": t.assignee,
                "progress": t.progress,
                "result": t.result,
            }
            for t in (sim.tasks.get(tid) for tid in sim.task_order)
            if t
        ],
        "logs": [
            {"time": l.time, "agent": l.agent, "icon": l.icon, "text": l.text, "type": l.type}
            for l in sim.logs[-50:]
        ],
        "memories": [
            {
                "agent": m.agent, "icon": m.icon,
                "concept": m.concept, "summary": m.summary,
                "confidence": round(m.confidence * 100),
            }
            for m in sim.memories[-10:]
        ],
    }
