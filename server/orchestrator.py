"""百工真实编排器 — DeepSeek 驱动 Agent 思考-行动循环"""

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Optional

from agent_sdk import ToolRegistry, TaskBoard, TaskStatus
from .config import config
from .llm_client import LLMClient

logger = logging.getLogger("baigong.orchestrator")


class AgentInstance:
    """一个真实的 Agent 实例"""

    def __init__(self, agent_id: str, name: str, role: str, model: str,
                 tools: list[str], system_prompt: str, llm: LLMClient):
        self.id = agent_id
        self.name = name
        self.role = role
        self.model = model
        self.tools = tools
        self.system_prompt = system_prompt
        self.llm = llm

        # 运行时状态
        self.status = "idle"  # idle / thinking / acting / done / error
        self.current_task = None
        self.action = "等待任务..."
        self.tool_calls = 0
        self.tasks_done = 0
        self.messages: list[dict] = []  # 思考日志
        self.memories: list[dict] = []

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "model": self.model,
            "tools": self.tools,
            "status": self.status,
            "action": self.action,
            "tool_calls": self.tool_calls,
            "tasks_done": self.tasks_done,
            "messages": self.messages[-20:],
            "memories": self.memories[-10:],
            "system_prompt": self.system_prompt[:200],
        }


class RealOrchestrator:
    """真正的编排器，用 LLM 驱动 Agent"""

    def __init__(self):
        self.agents: dict[str, AgentInstance] = {}
        self.board = TaskBoard()
        self.llm_client: Optional[LLMClient] = None
        self.running = False

        # SSE 事件
        self._update_event = asyncio.Event()
        self.global_logs: list[dict] = []
        self.skills: list[str] = []

    # ── 初始化 ──

    async def initialize(self):
        """初始化 LLM 客户端"""
        api_key = config.get("llm.api_key", "")
        if not api_key:
            logger.warning("未配置 API Key")
            return False

        self.llm_client = LLMClient()
        return True

    def load_agents_from_config(self):
        """从配置加载 Agent"""
        agents_config = config.get("agents", [])
        for a in agents_config:
            self._create_agent_instance(a)

    def _create_agent_instance(self, agent_cfg: dict) -> AgentInstance:
        agent_id = agent_cfg.get("id", str(uuid.uuid4())[:8])
        agent = AgentInstance(
            agent_id=agent_id,
            name=agent_cfg.get("name", "无名Agent"),
            role=agent_cfg.get("role", "worker"),
            model=agent_cfg.get("model", config.get("llm.model", "deepseek-v4-flash")),
            tools=agent_cfg.get("tools", ["web_search", "file_read"]),
            system_prompt=agent_cfg.get("system_prompt", "你是一个AI助手。"),
            llm=self.llm_client,
        )
        self.agents[agent_id] = agent
        return agent

    def _log(self, agent_id: str, msg: str, type: str = "action"):
        a = self.agents.get(agent_id)
        if not a:
            return
        t = time.strftime("%H:%M:%S")
        self.global_logs.append({
            "t": t, "agent": a.name, "role": a.role, "msg": msg, "type": type
        })
        a.messages.append({"t": t, "type": type, "msg": msg})
        if len(self.global_logs) > 500:
            self.global_logs = self.global_logs[-300:]
        self._notify()

    def _notify(self):
        self._update_event.set()
        self._update_event.clear()

    def _set_status(self, agent_id: str, status: str, action: str = ""):
        a = self.agents.get(agent_id)
        if not a:
            return
        a.status = status
        if action:
            a.action = action
        self._notify()

    # ── Agent CRUD ──

    def create_agent(self, name: str, role: str, tools: list[str],
                     system_prompt: str = "", model: str = "") -> dict:
        agent_id = f"agent_{uuid.uuid4().hex[:6]}"
        agent_cfg = {
            "id": agent_id,
            "name": name,
            "role": role,
            "tools": tools,
            "system_prompt": system_prompt or f"你是{name}，你的角色是{role}。使用可用工具完成任务。",
            "model": model or config.get("llm.model", "deepseek-v4-flash"),
        }
        self._create_agent_instance(agent_cfg)
        config.add_agent(agent_cfg)
        self._log(agent_id, f"🆕 Agent 已创建: {name} ({role})", "action")
        return agent_cfg

    def delete_agent(self, agent_id: str):
        if agent_id in self.agents:
            name = self.agents[agent_id].name
            del self.agents[agent_id]
            config.remove_agent(agent_id)
            self._log(agent_id, f"🗑️ Agent 已删除: {name}", "action")

    def update_agent(self, agent_id: str, updates: dict):
        if agent_id in self.agents:
            a = self.agents[agent_id]
            for k, v in updates.items():
                if hasattr(a, k):
                    setattr(a, k, v)
            config.update_agent(agent_id, updates)
            self._log(agent_id, f"✏️ Agent 已更新", "action")

    # ── 任务处理 ──

    async def process_task(self, goal: str, agent_id: str = ""):
        """用真实 LLM 驱动 Agent 完成任务"""
        if not self.llm_client:
            if not await self.initialize():
                self._log("system", "❌ API Key 未配置，无法执行任务", "error")
                return

        # 找执行 Agent
        if not agent_id or agent_id not in self.agents:
            # 用第一个空闲的 Agent
            agent_id = next((aid for aid, a in self.agents.items() if a.status == "idle"),
                            next(iter(self.agents), None))
        if not agent_id:
            self._log("system", "❌ 没有可用 Agent", "error")
            return

        agent = self.agents[agent_id]
        agent.current_task = goal
        self._set_status(agent_id, "thinking", f"思考任务: {goal[:40]}...")

        # 创建任务
        task = self.board.create_task(goal=goal, creator="user", assignee=agent.name)
        self._log(agent_id, f"📋 收到任务: {goal}", "action")

        # 构建系统 Prompt
        tools_desc = "\n".join([
            f"- {t.metadata.name}: {t.metadata.description}"
            for t in ToolRegistry.list_all()
            if t.metadata.name in agent.tools
        ])
        sys_prompt = f"""{agent.system_prompt}

你是一个 AI Agent，你的名字是「{agent.name}」，角色是「{agent.role}」。

可用的工具：
{tools_desc}

工作流程：
1. 思考（Think）— 分析当前任务，决定下一步做什么
2. 行动（Act）— 调用一个工具来执行
3. 观察（Observe）— 查看工具返回的结果
4. 重复 1-3 直到任务完成

输出格式：
每次输出一个 JSON 对象：
```json
{{"thought": "你的思考过程", "action": "工具名", "params": {{"参数名": "参数值"}}}}
```
如果任务完成，输出：
```json
{{"thought": "任务已完成", "action": "complete", "result": "任务结果总结"}}
```"""

        # 思考-行动循环（最多 10 步）
        max_steps = 10
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": f"请完成这个任务：{goal}"},
        ]

        for step in range(max_steps):
            self._set_status(agent_id, "thinking", f"第{step+1}步思考中...")
            self._log(agent_id, f"[思考] 第{step+1}/{max_steps}轮思考", "thought")

            # 调用 LLM
            try:
                response = await self.llm_client.chat(messages, model=agent.model)
            except Exception as e:
                self._log(agent_id, f"❌ LLM 调用失败: {str(e)[:80]}", "error")
                self._set_status(agent_id, "error", "LLM 错误")
                break

            # 解析响应
            content = response.strip()
            self._log(agent_id, f"[LLM] {content[:150]}...", "thought")

            # 提取 JSON
            json_match = self._extract_json(content)
            if not json_match:
                self._log(agent_id, f"⚠️ LLM 输出格式异常，尝试继续", "error")
                messages.append({"role": "assistant", "content": content})
                continue

            thought = json_match.get("thought", "")
            action = json_match.get("action", "")
            params = json_match.get("params", {})
            result_text = json_match.get("result", "")

            self._log(agent_id, f"🧠 {thought}", "thought")

            # 完成
            if action == "complete":
                self._set_status(agent_id, "done", f"✅ 完成: {result_text[:50]}")
                self._log(agent_id, f"✅ 任务完成: {result_text}", "result")
                self.board.complete_task(task.id, result_text or "完成")
                agent.tasks_done += 1

                # 记忆巩固
                self._consolidate_memory(agent_id, goal, result_text)
                break

            # 执行工具
            tool = ToolRegistry.get(action)
            if not tool:
                self._log(agent_id, f"❌ 未知工具: {action}", "error")
                messages.append({
                    "role": "user",
                    "content": f"工具 `{action}` 不存在。可用工具: {', '.join(agent.tools)}"
                })
                continue

            if action not in agent.tools:
                self._log(agent_id, f"❌ 无权使用工具: {action}", "error")
                messages.append({
                    "role": "user",
                    "content": f"你没有权限使用工具 `{action}`。你的工具: {', '.join(agent.tools)}"
                })
                continue

            self._set_status(agent_id, "acting", f"🔧 调用 {action}...")
            self._log(agent_id, f"🔧 调用工具: {action}({json.dumps(params, ensure_ascii=False)[:100]})", "action")
            agent.tool_calls += 1

            try:
                result = await tool.execute(**params)
            except Exception as e:
                self._log(agent_id, f"❌ 工具执行失败: {str(e)[:100]}", "error")
                messages.append({
                    "role": "user",
                    "content": f"工具 `{action}` 执行失败: {str(e)[:200]}"
                })
                continue

            # 记录结果
            result_str = json.dumps({
                "success": result.success,
                "data": result.data,
                "error": result.error,
            }, ensure_ascii=False)[:500]
            self._log(agent_id, f"[结果] {result_str[:150]}...", "result")

            # 继续对话
            messages.append({"role": "assistant", "content": content})
            messages.append({
                "role": "user",
                "content": f"工具 `{action}` 返回结果：\n{result_str}"
            })

            # 更新进度
            progress = (step + 1) / max_steps
            self.board.update_task(task.id, progress=min(progress, 0.95))

        else:
            # 超步数
            self._set_status(agent_id, "done", "⚠️ 达到最大思考步数")
            self._log(agent_id, "⚠️ 达到最大思考步数，任务未完成", "error")

        # 重置状态
        agent.current_task = None
        self._set_status(agent_id, "idle", "等待任务...")

    def _extract_json(self, text: str) -> Optional[dict]:
        """从 LLM 输出中提取 JSON"""
        import re
        # 先找 ```json ... ```
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        # 直接找 {...}
        match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return None

    def _consolidate_memory(self, agent_id: str, task: str, result: str):
        """记忆巩固"""
        agent = self.agents.get(agent_id)
        if not agent:
            return
        summary = f"完成了任务「{task}」: {result[:100]}"
        agent.memories.append({
            "type": "task",
            "task": task,
            "result": result[:200],
            "time": time.strftime("%H:%M:%S"),
        })
        self._log(agent_id, f"🧠 [记忆巩固] {summary[:80]}", "memory")

    # ── 系统数据查询 ──

    def get_system_data(self, target: str) -> dict:
        if target == "agents":
            return {aid: a.to_dict() for aid, a in self.agents.items()}
        elif target == "tasks":
            return {
                "pending": [{"id": t.id, "goal": t.goal, "status": t.status.value if hasattr(t.status, 'value') else str(t.status)} for t in self.board.get_pending_tasks(50)],
                "active": [{"id": t.id, "goal": t.goal, "status": t.status.value if hasattr(t.status, 'value') else str(t.status)} for t in self.board.get_active_tasks(50)],
            }
        elif target == "tools":
            return {
                t.metadata.name: {
                    "name": t.metadata.name,
                    "display_name": t.metadata.display_name,
                    "description": t.metadata.description,
                    "category": t.metadata.category,
                }
                for t in ToolRegistry.list_all()
            }
        elif target == "skills":
            return {"skills": self.skills}
        elif target == "config":
            return config.load()
        return {}

    def get_state(self) -> dict:
        tasks = []
        for t in self.board.get_pending_tasks(50):
            tasks.append(t.to_dict() if hasattr(t, 'to_dict') else {"goal": t.goal, "status": str(t.status)})
        for t in self.board.get_active_tasks(50):
            tasks.append(t.to_dict() if hasattr(t, 'to_dict') else {"goal": t.goal, "status": str(t.status)})

        return {
            "running": self.running,
            "agents": [a.to_dict() for a in self.agents.values()],
            "tasks": tasks,
            "logs": self.global_logs[-100:],
            "tools": {
                t.metadata.name: {
                    "name": t.metadata.name,
                    "display_name": t.metadata.display_name,
                    "description": t.metadata.description,
                    "category": t.metadata.category,
                }
                for t in ToolRegistry.list_all()
            },
            "skills": [{"name": s} for s in self.skills],
        }

    async def reset(self):
        self.running = False
        for agent in self.agents.values():
            agent.status = "idle"
            agent.action = ""
            agent.current_task = None
        self.global_logs.clear()
        self.skills.clear()
