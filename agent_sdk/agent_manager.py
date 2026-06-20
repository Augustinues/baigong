"""Agent 管理——生命周期管理"""

import uuid
import json
import time
import asyncio
from datetime import datetime
from typing import Optional

from .models import AgentConfig, AgentStatus, RoleDefinition, ModelConfig, MemoryType
from .agent_runtime import AgentRuntime
from .memory.long_term import LongTermMemory
from .message_bus import MessageBus
from .task_board import TaskBoard
from .database import get_db, now


class AgentManager:
    """Agent 管理器——创建/启动/暂停/停止/销毁"""

    def __init__(self, message_bus: MessageBus, task_board: TaskBoard):
        self.message_bus = message_bus
        self.task_board = task_board
        self.agents: dict[str, AgentRuntime] = {}
        self.role_definitions: dict[str, RoleDefinition] = {}
        self.restart_counts: dict[str, int] = {}

    # ── 角色管理 ──

    def register_role(self, role: RoleDefinition):
        self.role_definitions[role.role_id] = role

    def load_roles_from_yaml(self, path: str):
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        for role_id, cfg in data.get("roles", {}).items():
            role = RoleDefinition(
                role_id=role_id,
                display_name=cfg.get("display_name", role_id),
                description=cfg.get("description", ""),
                icon=cfg.get("icon", "🤖"),
                responsibilities=cfg.get("responsibilities", []),
                limitations=cfg.get("limitations", []),
                system_prompt_template=cfg.get("system_prompt_template", ""),
                work_mode=cfg.get("work_mode", "mixed"),
                communication_style=cfg.get("communication_style", "brief"),
                decision_bias=cfg.get("decision_bias", "balanced"),
                check_interval=cfg.get("check_interval", 5),
                default_tools=cfg.get("default_tools", []),
                forbidden_tools=cfg.get("forbidden_tools", []),
                reports_to=cfg.get("reports_to", "ceo"),
                task_acquisition=cfg.get("task_acquisition", "both"),
                conflict_resolution=cfg.get("conflict_resolution", "obey_superior"),
                reflection_frequency=cfg.get("reflection_frequency", "after_task"),
            )
            self.register_role(role)

    # ── Agent 创建 ──

    async def create_agent(
        self,
        name: str,
        role_id: str,
        model_config: ModelConfig | None = None,
        tools: list[str] | None = None,
    ) -> AgentRuntime:
        role = self.role_definitions.get(role_id)
        if not role:
            raise ValueError(f"未知角色: {role_id}")

        agent_id = f"{role_id}_{uuid.uuid4().hex[:6]}"

        config = AgentConfig(
            agent_id=agent_id,
            name=name,
            role_id=role_id,
            role=role,
            model_config=model_config or ModelConfig(),
            tools=tools or role.default_tools.copy(),
        )

        # 保存到数据库
        conn = get_db()
        conn.execute(
            """INSERT OR REPLACE INTO agents (agent_id, name, role_id, config, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (agent_id, name, role_id, json.dumps({
                "model_config": {
                    "provider": config.model_config.provider,
                    "model": config.model_config.model,
                },
                "tools": config.tools,
            }), "created", datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

        agent = AgentRuntime(config, self.message_bus, self.task_board)
        self.agents[agent_id] = agent
        return agent

    # ── 启动 ──

    async def start_agent(self, agent_id: str):
        agent = self.agents.get(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} 不存在")
        if agent.status not in (AgentStatus.BOOTING, AgentStatus.OFFLINE):
            return
        if not agent.llm:
            raise ValueError(f"Agent {agent_id} 没有设置 LLM 客户端")

        agent._loop_task = asyncio.create_task(agent.run_loop())
        agent.status = AgentStatus.IDLE
        agent.started_at = time.time()

        await self.message_bus.send_to_ceo(
            agent_id, f"{agent.config.name}({agent.config.role_id}) 已上线"
        )

    # ── 暂停/恢复 ──

    async def pause_agent(self, agent_id: str, reason: str = ""):
        agent = self.agents.get(agent_id)
        if not agent:
            return
        agent.status = AgentStatus.PAUSED
        agent.pause_reason = reason
        await self.message_bus.send_to_ceo(agent_id, f"{agent.config.name} 已暂停: {reason}")

    async def resume_agent(self, agent_id: str):
        agent = self.agents.get(agent_id)
        if agent and agent.status == AgentStatus.PAUSED:
            agent.status = AgentStatus.IDLE

    # ── 停止 ──

    async def stop_agent(self, agent_id: str, reason: str = "CEO 操作"):
        """停止 Agent——取消后台循环，保存状态"""
        agent = self.agents.get(agent_id)
        if not agent:
            return

        # 取消后台任务
        if agent._loop_task and not agent._loop_task.done():
            agent._loop_task.cancel()
            try:
                await asyncio.wait_for(agent._loop_task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

        agent.status = AgentStatus.OFFLINE
        agent.working_memory.clear()

        conn = get_db()
        conn.execute("UPDATE agents SET status=?, last_seen=? WHERE agent_id=?",
                     ("offline", now(), agent_id))
        conn.commit()
        conn.close()

        await self.message_bus.broadcast(agent_id, f"{agent.config.name} 已下线。原因: {reason}")

    # ── 销毁 ──

    async def destroy_agent(self, agent_id: str, confirm: bool = False):
        if not confirm:
            raise ValueError("销毁 Agent 需要确认")
        agent = self.agents.get(agent_id)
        if agent and agent.status not in (AgentStatus.OFFLINE, AgentStatus.DEAD):
            await self.stop_agent(agent_id, "Agent 被销毁")

        conn = get_db()
        for table in ["agents", "memory_nodes", "memory_links", "short_term_memory", "skills"]:
            conn.execute(f"DELETE FROM {table} WHERE agent_id=?", (agent_id,))
        conn.commit()
        conn.close()

        self.agents.pop(agent_id, None)

    # ── 崩溃恢复 ──

    async def on_agent_crash(self, agent_id: str):
        agent = self.agents.get(agent_id)
        if not agent or not agent.config.auto_restart:
            return

        rc = self.restart_counts.get(agent_id, 0)
        if rc >= 3:
            agent.status = AgentStatus.FROZEN
            await self.message_bus.send_to_ceo(agent_id, f"{agent.config.name} 已冻结")
            return

        self.restart_counts[agent_id] = rc + 1
        new_agent = AgentRuntime(agent.config, self.message_bus, self.task_board)
        new_agent.llm = agent.llm
        self.agents[agent_id] = new_agent
        await self.start_agent(agent_id)
        await self.message_bus.send_to_ceo(agent_id, f"{agent.config.name} 已自动重启 (第{rc+1}次)")

    # ── 查询 ──

    def get_agent(self, agent_id: str) -> AgentRuntime | None:
        return self.agents.get(agent_id)

    def get_agents_by_role(self, role_id: str) -> list[AgentRuntime]:
        return [a for a in self.agents.values() if a.config.role_id == role_id]

    def get_status_summary(self) -> dict:
        agents = self.agents.values()
        status_counts = {}
        for a in agents:
            s = a.status.value
            status_counts[s] = status_counts.get(s, 0) + 1

        return {
            "total": len(agents),
            "by_status": status_counts,
            "details": [
                {
                    "id": a.agent_id,
                    "name": a.config.name,
                    "role": a.config.role_id,
                    "status": a.status.value,
                    "current_task": a.working_memory.current_task_id,
                    "uptime": time.time() - a.started_at if a.started_at else 0,
                    "llm_calls": a.llm_call_count,
                    "tool_calls": a.tool_call_count,
                    "tasks": a.task_count,
                    "skills": len(a.skills),
                    "errors": a.consecutive_errors,
                }
                for a in agents
            ]
        }
