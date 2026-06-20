"""百工系统启动器 — 初始化 Agent 集群"""

import json
import time
import asyncio
import logging
from typing import Optional

from agent_sdk import (
    AgentManager, AgentStatus, MessageBus, TaskBoard,
    RoleDefinition, ModelConfig, BaseTool, ToolRegistry,
    ToolMetadata, ToolParam, ToolResult,
    init_db, BaseLLMClient,
)

from .llm_client import DeepSeekClient

logger = logging.getLogger("baigong.system")

# 全局单例
_manager: Optional[AgentManager] = None
_bus: Optional[MessageBus] = None
_board: Optional[TaskBoard] = None
_llm_client: Optional[BaseLLMClient] = None
_running = False


# ── 模拟工具（作为示例，用户可替换） ──

class MockWebSearch(BaseTool):
    @property
    def metadata(self):
        return ToolMetadata(
            name="web_search", display_name="网络搜索",
            description="搜索网络获取信息。输入关键词，返回结果列表。",
            parameters=[
                ToolParam(name="query", type="string", description="搜索关键词", required=True),
                ToolParam(name="limit", type="integer", description="返回结果数", default=5),
            ],
            category="search",
        )
    async def execute(self, query: str, limit: int = 5) -> ToolResult:
        logger.info(f"[web_search] query='{query}', limit={limit}")
        await asyncio.sleep(1.5)
        return ToolResult(success=True, data={
            "results": [
                {"title": f"关于「{query}」的结果", "url": "https://example.com/1", "snippet": f"这是关于{query}的详细内容..."},
                {"title": f"{query} 最新资讯", "url": "https://example.com/2", "snippet": f"{query}的最新行业动态..."},
            ]
        })


class MockKnowledgeWrite(BaseTool):
    @property
    def metadata(self):
        return ToolMetadata(
            name="kb_write", display_name="知识库写入",
            description="将内容写入知识库并返回链接。",
            parameters=[
                ToolParam(name="title", type="string", description="标题", required=True),
                ToolParam(name="content", type="string", description="内容", required=True),
            ],
            category="knowledge",
        )
    async def execute(self, title: str, content: str) -> ToolResult:
        logger.info(f"[kb_write] '{title}' ({len(content)}字)")
        await asyncio.sleep(1.0)
        return ToolResult(success=True, data={"status": "written", "title": title, "size": len(content)})


# ── 角色定义 ──

ROLES = [
    RoleDefinition(
        role_id="manager", display_name="主管", icon="👔",
        description="负责分析任务、拆解分配、跟踪进度",
        responsibilities=["分析CEO下发的任务，拆解为合适的子任务", "分配子任务给合适的Agent", "跟踪全部进度并汇总报告"],
        limitations=["不直接执行具体搜索或写入工作"],
        work_mode="proactive", communication_style="executive", decision_bias="conservative",
        default_tools=["send_message"],
        reports_to="ceo", task_acquisition="self_claim",
    ),
    RoleDefinition(
        role_id="researcher", display_name="研究员", icon="🔍",
        description="负责收集、搜索、提取信息",
        responsibilities=["根据任务要求搜索相关信息", "对收集到的信息做初步质量评估"],
        limitations=["不直接修改文件", "不写入知识库"],
        work_mode="mixed", communication_style="brief", decision_bias="balanced",
        default_tools=["web_search", "send_message"],
        task_acquisition="both",
    ),
    RoleDefinition(
        role_id="editor", display_name="编辑", icon="✏️",
        description="负责整理、去重、分类、格式化信息",
        responsibilities=["对收集来的资料进行去重", "分类和标准化格式"],
        limitations=["不主动搜索信息", "不写入知识库"],
        work_mode="passive", communication_style="brief", decision_bias="balanced",
        default_tools=["send_message"],
        task_acquisition="assigned",
    ),
    RoleDefinition(
        role_id="knowledge_admin", display_name="知识库管理员", icon="📚",
        description="负责将处理好的信息写入知识库",
        responsibilities=["将标准化后的资料写入知识库"],
        limitations=["不主动搜索信息"],
        work_mode="passive", communication_style="brief", decision_bias="conservative",
        default_tools=["kb_write", "send_message"],
        task_acquisition="assigned",
    ),
    RoleDefinition(
        role_id="qa", display_name="质检", icon="✅",
        description="负责检查任务成果的质量",
        responsibilities=["检查入库内容的格式和质量", "标记不合格内容要求返工"],
        limitations=["不执行搜索和编辑任务"],
        work_mode="passive", communication_style="brief", decision_bias="balanced",
        default_tools=["send_message"],
        task_acquisition="assigned",
    ),
]


async def start_system(api_key: str = "", model: str = "deepseek-v4-flash") -> dict:
    """启动百工系统，返回 agent_id → Agent 信息"""
    global _manager, _bus, _board, _llm_client, _running

    if _running:
        return get_status()

    init_db()
    _bus = MessageBus()
    _board = TaskBoard()
    _manager = AgentManager(_bus, _board)

    # 注册工具
    ToolRegistry.register(MockWebSearch())
    ToolRegistry.register(MockKnowledgeWrite())

    # 注册角色
    for role in ROLES:
        _manager.register_role(role)

    # 创建 LLM 客户端
    _llm_client = DeepSeekClient(api_key=api_key, model=model)

    # 创建 Agent
    agent_info = {}
    agent_specs = [
        ("张经理", "manager"),
        ("王研究员", "researcher"),
        ("李编辑", "editor"),
        ("陈管理员", "knowledge_admin"),
        ("赵质检", "qa"),
    ]
    for name, role_id in agent_specs:
        agent = await _manager.create_agent(name, role_id)
        agent.llm = _llm_client
        await _manager.start_agent(agent.agent_id)
        agent_info[agent.agent_id] = {
            "id": agent.agent_id,
            "name": name,
            "role": role_id,
            "icon": agent.config.role.icon if agent.config.role else "🤖",
        }

    _running = True
    return agent_info


async def stop_system():
    """停止所有 Agent"""
    global _running
    if _manager:
        for agent_id in list(_manager.agents.keys()):
            await _manager.stop_agent(agent_id, "系统关闭")
    _running = False


def get_status() -> dict:
    """获取系统当前状态"""
    if not _manager:
        return {"running": False, "agents": [], "tasks": []}

    summary = _manager.get_status_summary()
    agents = []
    for d in summary["details"]:
        agent = _manager.get_agent(d["id"])
        role = agent.config.role if agent else None
        agents.append({
            "id": d["id"],
            "name": d["name"],
            "role": d["role"],
            "icon": role.icon if role else "🤖",
            "status": d["status"],
            "action": agent.working_memory.current_action if agent else "",
            "tool_calls": d["tool_calls"],
            "tasks_done": d["tasks"],
            "memory_nodes": len(agent.long_term._node_cache) if agent and hasattr(agent.long_term, '_node_cache') else 0,
            "color": {
                "manager": "#f59e0b", "researcher": "#3b82f6",
                "editor": "#10b981", "knowledge_admin": "#8b5cf6",
                "qa": "#ef4444",
            }.get(d["role"], "#6b7280"),
        })

    stored_tasks = _board.get_pending_tasks(50) + _board.get_active_tasks(50)
    tasks = []
    for t in stored_tasks:
        tasks.append({
            "id": t.id, "goal": t.goal, "status": t.status.value,
            "assignee": t.assignee, "progress": t.progress, "result": "",
        })

    return {
        "running": _running,
        "agents": agents,
        "tasks": tasks,
    }
