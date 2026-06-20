"""百工真实编排器 — DeepSeek 驱动 Agent 思考-行动循环 + 任务拆解 + 自动创建子Agent"""

import asyncio
import json
import logging
import os
import re
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
                 tools: list[str], system_prompt: str, llm: LLMClient,
                 provider: str = "", api_key: str = "", base_url: str = "",
                 temperature: float = 0.0, max_tokens: int = 0,
                 is_temporary: bool = False, creator: str = ""):  # 新增 is_temporary/creator
        self.id = agent_id
        self.name = name
        self.role = role
        self.model = model
        self.tools = tools
        self.system_prompt = system_prompt
        self.llm = llm
        self.provider = provider
        self.api_key = api_key
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.is_temporary = is_temporary
        self.creator = creator  # 谁创建了这个 Agent

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
            "system_prompt": self.system_prompt,
            "provider": self.provider,
            "api_key": self.api_key,
            "base_url": self.base_url,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "is_temporary": self.is_temporary,
            "creator": self.creator,
        }


class RealOrchestrator:
    """真正的编排器，用 LLM 驱动 Agent——主管拆解 + 自动创建子 Agent + 并行执行"""

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
        # 如果没有任何 Agent，自动创建默认主管
        if not self.agents:
            self._log("system", "🏮 没有配置 Agent，自动创建默认主管", "action")
            self.create_agent(
                name="主管",
                role="manager",
                tools=["web_search", "web_extract", "file_read", "file_write", "code_exec"],
                system_prompt="""你是百工系统的主管（Manager），负责接收用户任务并进行以下工作：

1. **分析任务** — 理解用户需求，判断需要哪些角色协作
2. **拆解步骤** — 将大任务拆分为若干可并行执行的子任务
3. **招聘人员** — 为每个子任务创建合适的 Agent（研究员、编辑、质检等）
4. **分配任务** — 将子任务分配给对应的 Agent
5. **汇总结果** — 所有子任务完成后，汇总最终报告给用户

你的输出必须是以下格式之一：

**任务拆解**：
```json
{"thought": "分析过程", "action": "decompose", "steps": [
  {"role": "researcher", "name": "王研究员", "goal": "搜索翡翠鉴别资料", "tools": ["web_search","web_extract"], "prompt": "你是一个专业研究员..."},
  {"role": "editor", "name": "李编辑", "goal": "整理去重分类", "tools": ["file_read","file_write"], "prompt": "你是一个认真仔细的编辑..."}
]}

**任务完成**：
```json
{"thought": "任务已全部完成", "action": "complete", "result": "最终报告"}
```""",
            )
            # 保存到配置
            for a_id, a in self.agents.items():
                config.add_agent({
                    "id": a.id, "name": a.name, "role": a.role,
                    "tools": a.tools, "system_prompt": a.system_prompt,
                })

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
            provider=agent_cfg.get("provider", ""),
            api_key=agent_cfg.get("api_key", ""),
            base_url=agent_cfg.get("base_url", ""),
            temperature=agent_cfg.get("temperature", 0.0),
            max_tokens=agent_cfg.get("max_tokens", 0),
            is_temporary=agent_cfg.get("is_temporary", False),
            creator=agent_cfg.get("creator", ""),
        )
        self.agents[agent_id] = agent
        return agent

    def _log(self, agent_id: str, msg: str, type: str = "action"):
        a = self.agents.get(agent_id)
        t = time.strftime("%H:%M:%S")
        entry = {"t": t, "agent": a.name if a else agent_id, "role": a.role if a else "", "msg": msg, "type": type}
        self.global_logs.append(entry)
        if a:
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
                     system_prompt: str = "", model: str = "",
                     provider: str = "", api_key: str = "",
                     base_url: str = "", temperature: float = 0.0,
                     max_tokens: int = 0, is_temporary: bool = False,
                     creator: str = "") -> dict:
        agent_id = f"agent_{uuid.uuid4().hex[:6]}"
        agent_cfg = {
            "id": agent_id,
            "name": name,
            "role": role,
            "tools": tools,
            "system_prompt": system_prompt or f"你是{name}，你的角色是{role}。使用可用工具完成任务。",
            "model": model or config.get("llm.model", "deepseek-v4-flash"),
            "provider": provider,
            "api_key": api_key,
            "base_url": base_url,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "is_temporary": is_temporary,
            "creator": creator,
        }
        self._create_agent_instance(agent_cfg)
        # 只保存非临时 Agent 到配置
        if not is_temporary:
            config.add_agent(agent_cfg)
        src = f"(由 {creator} 创建)" if creator else ""
        self._log(agent_id, f"🆕 Agent 已创建: {name} ({role}) {src}", "action")
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

    # ── 任务处理：主管拆解 + 自动招聘 + 并行执行 ──

    async def process_task(self, goal: str, agent_id: str = ""):
        """主管接收任务 → 拆解 → 创建子 Agent → 并行执行 → 汇总"""
        if not self.llm_client:
            if not await self.initialize():
                self._log("system", "❌ API Key 未配置，无法执行任务", "error")
                return

        # 找主管（manager 角色的 Agent）
        manager = None
        for aid, a in self.agents.items():
            if a.role == "manager" and a.status == "idle":
                manager = a
                break
        if not manager:
            # 用第一个闲置的 Agent
            manager_id = next((aid for aid, a in self.agents.items() if a.status == "idle"),
                             next(iter(self.agents), None))
            if not manager_id:
                self._log("system", "❌ 没有可用 Agent", "error")
                return
            manager = self.agents[manager_id]

        manager_id = manager.id
        manager_name = manager.name
        manager.current_task = goal
        self._set_status(manager_id, "thinking", f"分析任务: {goal[:40]}...")

        # 创建根任务
        root_task = self.board.create_task(goal=goal, creator="user", assignee=manager_name)
        self._log(manager_id, f"📋 {manager_name} 收到任务: {goal}", "action")

        # ── 第一步：主管拆解任务 ──
        self._log(manager_id, f"🧠 {manager_name} 正在分析任务并拆解步骤...", "thought")
        self._set_status(manager_id, "thinking", "拆解任务中...")

        decompose_prompt = f"""你是一个AI系统的主管（Manager），名字是「{manager_name}」。

用户交付的任务：{goal}

请分析这个任务，将其拆解为若干可并行执行的子任务。每个子任务需要一个独立的 Agent 来处理。

对于每个子任务，指定：
1. **role** — 角色（researcher/editor/admin/qa/coder/analyst 等）
2. **name** — 给这个 Agent 起个名字（中文名，如王研究员）
3. **goal** — 这个子任务的具体目标
4. **tools** — 需要的工具列表
5. **prompt** — 这个 Agent 的系统提示词（简短描述其职责和权限）

只输出 JSON，不要其他文字：
```json
{{"thought": "你的思考过程", "action": "decompose", "steps": [
  {{"role": "researcher", "name": "王研究员", "goal": "子任务目标", "tools": ["web_search","web_extract"], "prompt": "你是研究员..."}},
  ...
]}}
```
如果任务很简单不需要拆解，直接输出 complete。"""

        decomp_messages = [
            {"role": "system", "content": decompose_prompt},
            {"role": "user", "content": f"请分析并拆解任务：{goal}"},
        ]

        try:
            decomp_resp = await self.llm_client.chat(decomp_messages)
        except Exception as e:
            self._log(manager_id, f"❌ 拆解失败: {str(e)[:80]}", "error")
            self._set_status(manager_id, "error", "拆解失败")
            return

        self._log(manager_id, f"[LLM拆解] {decomp_resp[:200]}...", "thought")

        # 解析拆解结果
        decomp_json = self._extract_json(decomp_resp)
        if not decomp_json or decomp_json.get("action") != "decompose":
            # 不拆解，直接交给主管执行
            self._log(manager_id, "任务不需要拆解，由主管直接执行", "thought")
            await self._run_agent_task(manager_id, goal, root_task)
            return

        steps = decomp_json.get("steps", [])
        if not steps:
            self._log(manager_id, "拆解结果无步骤，主管直接执行", "thought")
            await self._run_agent_task(manager_id, goal, root_task)
            return

        self._set_status(manager_id, "waiting", f"已拆解为{len(steps)}个步骤，正在招聘人员...")
        self._log(manager_id, f"📋 任务拆解为 {len(steps)} 个子步骤", "action")
        for i, step in enumerate(steps):
            self._log(manager_id, f"  步骤{i+1}: {step.get('name','?')} → {step.get('goal','?')[:40]}...", "action")

        # ── 第二步：招聘（创建子 Agent） ──
        sub_agent_ids = []
        sub_tasks = []

        for i, step in enumerate(steps):
            role = step.get("role", "worker")
            sub_name = step.get("name", f"助手{i+1}")
            sub_goal = step.get("goal", f"子任务{i+1}")
            sub_tools = step.get("tools", ["web_search", "file_read"])
            sub_prompt = step.get("prompt", f"你是{sub_name}，你的角色是{role}。")

            # 创建子 Agent（临时标记）
            sub_id = f"sub_{uuid.uuid4().hex[:4]}"
            agent_cfg = {
                "id": sub_id,
                "name": sub_name,
                "role": role,
                "tools": sub_tools,
                "system_prompt": sub_prompt,
                "model": config.get("llm.model", "deepseek-v4-flash"),
                "is_temporary": True,
                "creator": manager_name,
            }
            self._create_agent_instance(agent_cfg)
            sub_agent_ids.append(sub_id)

            # 创建子任务
            sub_task = self.board.create_task(goal=sub_goal, creator=manager_name, assignee=sub_name, parent_task_id=root_task.id)
            sub_tasks.append((sub_id, sub_task, sub_goal))

            self._log(sub_id, f"🎯 收到子任务: {sub_goal}", "action")
            self._set_status(sub_id, "idle", "就绪")

        self._log(manager_id, f"✅ 已招聘 {len(sub_agent_ids)} 名成员，开始分配任务", "action")
        self._set_status(manager_id, "waiting", f"子 Agent 工作中 ({len(sub_agent_ids)}名)")

        # ── 第三步：并行执行子任务 ──
        async def run_sub(sub_id, sub_task, sub_goal):
            try:
                await self._run_agent_task(sub_id, sub_goal, sub_task)
            except Exception as e:
                self._log(sub_id, f"❌ 任务执行异常: {str(e)[:80]}", "error")

        await asyncio.gather(*[run_sub(sid, st, sg) for sid, st, sg in sub_tasks])

        # ── 第四步：主管汇总 ──
        self._set_status(manager_id, "thinking", "汇总子任务结果中...")
        self._log(manager_id, "📊 所有子任务完成，正在汇总结果...", "action")

        # 收集子任务结果
        results = []
        for sid, st, sg in sub_tasks:
            agent = self.agents.get(sid)
            result_text = st.result if hasattr(st, 'result') and st.result else "已完成"
            tool_count = agent.tool_calls if agent else 0
            results.append(f"- {agent.name if agent else sid}: {result_text[:100]} (调用工具{tool_count}次)")
            if agent:
                self._set_status(sid, "done", f"✅ {result_text[:30]}")

        summary = "\n".join(results)
        self._log(manager_id, f"📊 汇总报告:\n{summary}", "result")

        # 完成根任务
        final_report = f"任务「{goal}」已完成。\n拆分为 {len(steps)} 个子任务，由 {len(sub_agent_ids)} 名 Agent 协作完成。\n\n{summary}"
        self.board.complete_task(root_task.id, final_report)
        self._set_status(manager_id, "done", f"✅ 全部完成 ({len(sub_agent_ids)}名Agent)")
        self._log(manager_id, f"🎉 全部任务完成！{len(sub_agent_ids)} 名 Agent 协作完成", "result")

        # 记忆巩固
        self._consolidate_memory(manager_id, goal, final_report)

        # 重置主管状态
        manager.current_task = None
        self._set_status(manager_id, "idle", "等待任务...")

    # ── 单个 Agent 思考-行动循环 ──

    async def _run_agent_task(self, agent_id: str, goal: str, task):
        """运行单个 Agent 的思考-行动循环（子任务/直接任务通用）"""
        agent = self.agents.get(agent_id)
        if not agent:
            return
        agent.current_task = goal
        self._set_status(agent_id, "thinking", f"开始处理: {goal[:40]}...")

        tools_desc = "\n".join([
            f"- {t.metadata.name}: {t.metadata.description}"
            for t in ToolRegistry.list_all()
            if t.metadata.name in agent.tools
        ])

        sys_prompt = f"""{agent.system_prompt}

你是一个 AI Agent，名字是「{agent.name}」，角色是「{agent.role}」。

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
```

注意：只输出 JSON，不要其他文字。"""

        max_steps = 10
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": f"请完成这个任务：{goal}"},
        ]

        for step in range(max_steps):
            self._set_status(agent_id, "thinking", f"第{step+1}/{max_steps}步思考中...")
            self._log(agent_id, f"[思考] 第{step+1}轮", "thought")

            try:
                response = await self.llm_client.chat(messages, model=agent.model)
            except Exception as e:
                self._log(agent_id, f"❌ LLM 调用失败: {str(e)[:80]}", "error")
                self._set_status(agent_id, "error", "LLM错误")
                break

            content = response.strip()
            self._log(agent_id, f"[LLM] {content[:120]}...", "thought")

            json_match = self._extract_json(content)
            if not json_match:
                self._log(agent_id, "⚠️ LLM 输出格式异常，继续", "error")
                messages.append({"role": "assistant", "content": content})
                continue

            thought = json_match.get("thought", "")
            action = json_match.get("action", "")
            params = json_match.get("params", {})
            result_text = json_match.get("result", "")

            self._log(agent_id, f"🧠 {thought}", "thought")

            # 完成
            if action == "complete":
                self._set_status(agent_id, "done", f"✅ {result_text[:40]}")
                self._log(agent_id, f"✅ 完成: {result_text}", "result")
                if task:
                    self.board.complete_task(task.id, result_text or "完成")
                agent.tasks_done += 1
                self._consolidate_memory(agent_id, goal, result_text)
                break

            # 执行工具
            tool = ToolRegistry.get(action)
            if not tool:
                self._log(agent_id, f"❌ 未知工具: {action}", "error")
                messages.append({"role": "user", "content": f"工具 `{action}` 不存在。可用: {', '.join(agent.tools)}"})
                continue

            if action not in agent.tools:
                self._log(agent_id, f"❌ 无权使用: {action}", "error")
                messages.append({"role": "user", "content": f"无权使用 `{action}`。你的工具: {', '.join(agent.tools)}"})
                continue

            self._set_status(agent_id, "acting", f"🔧 调用 {action}...")
            self._log(agent_id, f"🔧 调用: {action}({json.dumps(params, ensure_ascii=False)[:80]})", "action")
            agent.tool_calls += 1

            try:
                result = await tool.execute(**params)
            except Exception as e:
                self._log(agent_id, f"❌ 工具失败: {str(e)[:80]}", "error")
                messages.append({"role": "user", "content": f"工具 `{action}` 执行失败: {str(e)[:200]}"})
                continue

            result_str = json.dumps({"success": result.success, "data": result.data, "error": result.error}, ensure_ascii=False)[:500]
            self._log(agent_id, f"[结果] {result_str[:120]}...", "result")

            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": f"工具 `{action}` 返回结果：\n{result_str}"})

            if task:
                progress = (step + 1) / max_steps
                try:
                    self.board.update_task(task.id, progress=min(progress, 0.95))
                except:
                    pass

        else:
            self._set_status(agent_id, "done", "⚠️ 达到最大步数")
            self._log(agent_id, "⚠️ 最大步数，任务未完成", "error")

        agent.current_task = None
        if agent.status != "error":
            self._set_status(agent_id, "idle", "等待任务...")

    def _extract_json(self, text: str) -> Optional[dict]:
        """从 LLM 输出中提取 JSON"""
        import re
        match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        return None

    def _consolidate_memory(self, agent_id: str, task: str, result: str):
        agent = self.agents.get(agent_id)
        if not agent:
            return
        summary = f"完成了任务「{task}」: {result[:100]}"
        agent.memories.append({"type": "task", "task": task, "result": result[:200], "time": time.strftime("%H:%M:%S")})
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
            return {t.metadata.name: {"name": t.metadata.name, "display_name": t.metadata.display_name, "description": t.metadata.description, "category": t.metadata.category} for t in ToolRegistry.list_all()}
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
        for t in self.board.get_completed_tasks(50):
            tasks.append(t.to_dict() if hasattr(t, 'to_dict') else {"goal": t.goal, "status": str(t.status)})

        return {
            "running": self.running,
            "agents": [a.to_dict() for a in self.agents.values()],
            "tasks": tasks,
            "logs": self.global_logs[-100:],
            "tools": {t.metadata.name: {"name": t.metadata.name, "display_name": t.metadata.display_name, "description": t.metadata.description, "category": t.metadata.category} for t in ToolRegistry.list_all()},
            "skills": [{"name": s} for s in self.skills],
        }

    async def reset(self):
        self.running = False
        # 清理临时 Agent
        to_delete = [aid for aid, a in self.agents.items() if a.is_temporary]
        for aid in to_delete:
            del self.agents[aid]
        for agent in self.agents.values():
            agent.status = "idle"
            agent.action = ""
            agent.current_task = None
        self.global_logs.clear()
        self.skills.clear()
