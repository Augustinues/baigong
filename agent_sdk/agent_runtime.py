"""Agent 运行时——思考-行动循环"""

import asyncio
import json
import time
import uuid
import traceback
from typing import Optional

from .models import (
    AgentConfig, AgentStatus, Message, MessageType,
    Task, TaskStatus, MemoryType, Skill, SkillStep,
)
from .memory.long_term import LongTermMemory
from .memory.short_term import WorkingMemory, ShortTermMemory
from .message_bus import MessageBus
from .task_board import TaskBoard
from .tool_base import ToolRegistry
from .database import now


class AgentRuntime:
    """Agent 运行时——独立的思考-行动循环"""

    def __init__(
        self,
        config: AgentConfig,
        message_bus: MessageBus,
        task_board: TaskBoard,
    ):
        self.config = config
        self.message_bus = message_bus
        self.task_board = task_board
        self.agent_id = config.agent_id

        # 状态
        self.status = AgentStatus.BOOTING
        self.started_at: float | None = None
        self.last_cycle_at: float = 0.0
        self.consecutive_errors = 0

        # 记忆系统
        self.working_memory = WorkingMemory()
        self.short_term = ShortTermMemory(self.agent_id)
        self.long_term = LongTermMemory(self.agent_id)

        # 技能缓存（自动从记忆树中挖掘）
        self.skills: dict[str, Skill] = {}

        # 计数器
        self.llm_call_count = 0
        self.tool_call_count = 0
        self.task_count = 0

        # LLM 客户端（由外部注入）
        self.llm = None

        # asyncio Task handle（用于停止）
        self._loop_task: asyncio.Task | None = None

        # 注册到消息总线
        self.message_bus.subscribe(self.agent_id, self._on_message)

    # ═══════════════════════════════════════════
    # 主循环
    # ═══════════════════════════════════════════

    async def run_loop(self):
        """思考-行动主循环"""
        self.status = AgentStatus.IDLE
        self.started_at = time.time()

        while self.status not in (AgentStatus.OFFLINE, AgentStatus.DEAD, AgentStatus.FROZEN):
            try:
                await self._cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.consecutive_errors += 1
                self.short_term.record("error", f"循环异常: {str(e)[:80]}", traceback.format_exc())
                if self.consecutive_errors >= 5:
                    self.status = AgentStatus.ERROR
                    await self.message_bus.send_to_ceo(
                        self.agent_id,
                        f"连续5次错误，进入 ERROR 状态"
                    )
                    await asyncio.sleep(30)

            # 循环间隔——根据状态调整频率
            await asyncio.sleep(self._get_interval())

    async def _cycle(self):
        """一轮思考-行动"""
        self.last_cycle_at = time.time()

        # ── 第 0 步：检查是否有 Skill 可以匹配 ──
        if await self._try_match_skill():
            return  # skill 执行完毕，下一轮再感知

        # ── 第 1 步：感知 ──
        perception = await self._collect_perception()
        if perception["is_empty"] and self.status == AgentStatus.IDLE:
            return  # 没新消息，继续空闲

        # ── 第 2 步：思考（调 LLM） ──
        if not self.llm:
            return

        # 拼装 context
        context = self._build_context(perception)
        self.working_memory.add_thought("开始思考")
        self.short_term.record("thought", "开始新一轮思考")

        # 调 LLM
        try:
            response = await self.llm.think(
                system_prompt=self.config.system_prompt or self._default_prompt(),
                context=context,
            )
            self.llm_call_count += 1
            self.consecutive_errors = 0
        except Exception as e:
            self.short_term.record("error", f"LLM 思考失败: {str(e)[:80]}")
            self.consecutive_errors += 1
            if self.consecutive_errors >= 3:
                self.status = AgentStatus.DEGRADED
            return

        # ── 第 3 步：决策执行 ──
        decision = self._parse_decision(response)
        if decision:
            await self._execute_decision(decision)

        # ── 第 4 步：检查是否需要巩固记忆 ──
        if self._should_consolidate():
            await self._consolidate()

        # ── 第 5 步：检查是否需要挖掘 Skill ──
        if self._should_mine():
            await self._mine_skills()

    # ═══════════════════════════════════════════
    # 感知
    # ═══════════════════════════════════════════

    async def _collect_perception(self) -> dict:
        """收集当前环境信息"""
        result = {"messages": [], "board_changes": [], "is_empty": True}

        # 检查信箱（通过 message_bus 直接推送，这里略）
        # 感知在 _on_message 中处理

        # 检查看板上有无未处理的任务
        pending = self.task_board.get_pending_tasks(limit=5)
        for task in pending:
            if self._relevant_to_me(task):
                result["board_changes"].append({
                    "type": "new_task",
                    "task_id": task.id,
                    "goal": task.goal,
                    "creator": task.creator,
                })
                result["is_empty"] = False

        return result

    async def _on_message(self, message: Message):
        """收到消息时的回调"""
        self.short_term.record(
            "message",
            f"从 {message.sender} 收到: {message.body[:60]}",
            detail=message.body,
            importance=0.5,
        )

    # ═══════════════════════════════════════════
    # Skill 匹配和执行
    # ═══════════════════════════════════════════

    async def _try_match_skill(self) -> bool:
        """尝试匹配一个 Skill 来执行当前任务"""
        if not self.working_memory.current_task_id:
            return False

        task = self.task_board.get_task(self.working_memory.current_task_id)
        if not task:
            return False

        # 找匹配的 skill
        for skill in self.skills.values():
            if skill.confidence < 0.6:
                continue
            for trigger in skill.triggers:
                if trigger.lower() in task.goal.lower():
                    # 匹配！直接执行 skill
                    await self._execute_skill(skill, task)
                    return True
        return False

    async def _execute_skill(self, skill: Skill, task: Task):
        """执行一个 Skill"""
        self.short_term.record("action", f"执行 Skill: {skill.name}")

        for step in skill.steps:
            self.working_memory.current_action = step.description or step.tool_name

            if step.type == "tool_call":
                tool = ToolRegistry.get(step.tool_name)
                if tool:
                    result = await tool.execute(**step.params)
                    self.tool_call_count += 1
                    if not result.success:
                        # 异常 → 让 LLM 处理
                        context = self._build_context({"error": result.error, "step": step})
                        response = await self.llm.think(
                            system_prompt=self.config.system_prompt or "",
                            context=context,
                        )
                        self.llm_call_count += 1
                        # 根据 LLM 建议继续
                        decision = self._parse_decision(response)
                        if decision:
                            await self._execute_decision(decision)

        # 完成
        self.task_board.complete_task(task.id, f"通过 skill {skill.name} 完成")
        skill.use_count += 1
        skill.last_used = time.time()
        self.working_memory.clear()

    # ═══════════════════════════════════════════
    # 决策执行
    # ═══════════════════════════════════════════

    def _parse_decision(self, llm_response: str) -> dict | None:
        """解析 LLM 返回的决策"""
        # 尝试提取 JSON 格式的决策
        try:
            # 找第一个 { 和最后一个 }
            start = llm_response.find('{')
            end = llm_response.rfind('}')
            if start >= 0 and end > start:
                return json.loads(llm_response[start:end + 1])
        except (json.JSONDecodeError, ValueError):
            pass
        return None

    async def _execute_decision(self, decision: dict):
        """执行决策"""
        action = decision.get("action", "")

        if action == "tool_call":
            tool_name = decision.get("tool")
            params = decision.get("params", {})
            tool = ToolRegistry.get(tool_name)
            if tool:
                self.working_memory.current_action = f"调用 {tool_name}"
                result = await tool.execute(**params)
                self.tool_call_count += 1
                self.short_term.record(
                    "tool_call",
                    f"调用 {tool_name}: {'成功' if result.success else '失败'}",
                    detail=str(result.data)[:200],
                    importance=0.4,
                )
                self.working_memory.last_action_result = str(result.data)[:200]

        elif action == "send_message":
            recipient = decision.get("recipient", "")
            content = decision.get("content", "")
            await self.message_bus.send(Message(
                id=f"msg_{uuid.uuid4().hex[:12]}",
                type=MessageType(decision.get("msg_type", "notification")),
                sender=self.agent_id,
                recipients=[recipient],
                body=content,
                created_at=time.time(),
            ))
            self.short_term.record("action", f"发消息给 {recipient}: {content[:50]}")

        elif action == "claim_task":
            task_id = decision.get("task_id", "")
            if task_id:
                success = self.task_board.claim_task(task_id, self.agent_id)
                if success:
                    task = self.task_board.get_task(task_id)
                    if task:
                        self.working_memory.set_task(task_id, {"goal": task.goal})
                        self.status = AgentStatus.WORKING
                        self.short_term.record("action", f"领取任务: {task.goal[:50]}")

        elif action == "complete_task":
            task_id = decision.get("task_id", "") or self.working_memory.current_task_id
            if task_id:
                self.task_board.complete_task(task_id, decision.get("result", ""))
                self.working_memory.clear()
                self.status = AgentStatus.IDLE
                self.task_count += 1

        elif action == "create_subtask":
            goal = decision.get("goal", "")
            assignee = decision.get("assignee", "")
            parent = decision.get("parent_task_id", "") or self.working_memory.current_task_id
            if goal and assignee:
                subtask = self.task_board.create_task(
                    goal=goal, creator=self.agent_id,
                    assignee=assignee, parent_task_id=parent,
                )
                await self.message_bus.send(Message(
                    id=f"msg_{uuid.uuid4().hex[:12]}",
                    type=MessageType.TASK_ASSIGN,
                    sender=self.agent_id,
                    recipients=[assignee],
                    body=f"新任务: {goal}",
                    parent_task_id=subtask.id,
                    created_at=time.time(),
                ))
                self.short_term.record("action", f"创建子任务: {goal[:50]} → {assignee}")

        elif action == "wait":
            self.status = AgentStatus.WAITING

        elif action == "self_reflect":
            await self._consolidate()

    # ═══════════════════════════════════════════
    # 上下文拼装
    # ═══════════════════════════════════════════

    def _build_context(self, perception: dict) -> str:
        """拼装发给 LLM 的上下文"""
        parts = [
            f"你是一个 {self.config.role_id}，名字是 {self.config.name}。",
            "",
            self.working_memory.to_prompt(),
            "",
        ]

        # 短期记忆（最近 1 小时的时间线）
        timeline = self.short_term.get_timeline(hours=1)
        if timeline:
            parts.append(f"【近期时间线】\n{timeline}\n")

        # 长期记忆联想检索（如果正在做任务）
        if self.working_memory.current_task_id:
            task = self.task_board.get_task(self.working_memory.current_task_id)
            if task:
                related = self.long_term.associative_recall(task.goal, depth=1, max_nodes=5)
                if related:
                    mem_lines = ["【相关记忆】"]
                    for m in related[:5]:
                        mem_lines.append(f"- [{m.type.value}] {m.summary} (置信度: {m.confidence:.0%})")
                    parts.append('\n'.join(mem_lines) + '\n')

        # 感知信息
        if perception.get("board_changes"):
            parts.append("【看板变化】")
            for change in perception["board_changes"]:
                parts.append(f"- 新任务: {change['goal']} (来自 {change['creator']})")
            parts.append("")

        # 可用的技能
        if self.skills:
            parts.append("【已掌握的技能】")
            for s in self.skills.values():
                if s.confidence >= 0.6:
                    parts.append(f"- {s.name}: {s.description} (置信度: {s.confidence:.0%})")
            parts.append("")

        # 可用工具
        tool_names = self.config.tools
        if tool_names:
            parts.append("【可用工具】")
            for name in tool_names:
                tool = ToolRegistry.get(name)
                if tool:
                    m = tool.metadata
                    params = ", ".join(f"{p.name}({p.type})" for p in m.parameters)
                    parts.append(f"- {m.name}: {m.description} 参数: {params}")
            parts.append("")

        parts.append("请输出 JSON 格式的决策，包含 action 字段。")
        parts.append("可用的 action: tool_call, send_message, claim_task, complete_task, create_subtask, wait, self_reflect")

        return '\n'.join(parts)

    def _default_prompt(self) -> str:
        """默认系统 prompt"""
        return f"""你是一个 {self.config.name}（{self.config.role_id}）。

你的职责：
{chr(10).join(f'- {r}' for r in (self.config.role.responsibilities if self.config.role else []))}

你的限制：
{chr(10).join(f'- {l}' for l in (self.config.role.limitations if self.config.role else []))}

工作原则：
1. 完成分派的任务，主动报告进度
2. 遇到解决不了的问题，及时向主管求助
3. 每次完成任务后进行简要反思
4. 对于做过多次的同类任务，优先使用已掌握的 Skill"""

    # ═══════════════════════════════════════════
    # 记忆巩固
    # ═══════════════════════════════════════════

    def _should_consolidate(self) -> bool:
        """检查是否需要巩固记忆"""
        return self.consecutive_errors == 0 and (
            self.task_count % 3 == 0  # 每 3 个任务巩固一次
        )

    async def _consolidate(self):
        """记忆巩固——从短期提取到长期"""
        unconsolidated = self.short_term.get_unconsolidated()
        if not unconsolidated:
            return

        for entry in unconsolidated:
            if entry.importance < 0.4:
                continue

            # 提取关键概念
            concepts = self._extract_concepts(entry.summary)
            for concept in concepts[:3]:
                existing = self.long_term.find_node_by_name(concept)
                if existing:
                    # 已有 → 加强链接
                    self.long_term.reinforce_link(entry.summary[:20], concept)
                else:
                    # 新概念 → 创建节点
                    self.long_term.create_node(
                        content=entry.detail or entry.summary,
                        type=MemoryType.EPISODIC,
                        summary=concept,
                        importance=entry.importance,
                        source_task=entry.task_id,
                    )

        self.short_term.mark_consolidated([e.id for e in unconsolidated if hasattr(e, 'id')])
        self.short_term.record("reflection", f"巩固了 {len(unconsolidated)} 条短期记忆")

    def _extract_concepts(self, text: str) -> list[str]:
        """简单概念提取（后续可调用 LLM 做更好的）"""
        # 简单分词 + 取名词性内容
        import re
        # 匹配中英文词汇
        words = re.findall(r'[\u4e00-\u9fff\w]+', text)
        # 过滤太短的
        return [w for w in words if len(w) >= 2][:5]

    # ═══════════════════════════════════════════
    # Skill 挖掘
    # ═══════════════════════════════════════════

    def _should_mine(self) -> bool:
        """检查是否需要挖掘 Skill"""
        return self.task_count > 0 and self.task_count % 5 == 0

    async def _mine_skills(self):
        """从记忆树中挖掘 Skill"""
        # 查找高频模式——同类型任务出现多次
        recent_tasks = self.short_term.search_recent("task", limit=20)
        task_goals = [t.summary for t in recent_tasks if t.task_id]

        # 简单模式：找到重复出现的任务关键词
        from collections import Counter
        words = []
        for goal in task_goals:
            words.extend(self._extract_concepts(goal))
        common = Counter(words).most_common(3)

        for word, count in common:
            if count >= 3 and word not in self.skills:
                # 创建新 Skill
                skill = Skill(
                    name=word,
                    description=f"处理 {word} 相关任务",
                    triggers=[word],
                    confidence=0.4,
                    use_count=count,
                    formed_at=time.time(),
                )
                self.skills[word] = skill
                self.short_term.record(
                    "reflection",
                    f"新技能形成: {word} (出现 {count} 次，置信度 0.4)",
                    importance=0.6,
                )

    # ═══════════════════════════════════════════
    # 辅助方法
    # ═══════════════════════════════════════════

    def _relevant_to_me(self, task: Task) -> bool:
        """这个任务是否与我相关"""
        if task.assignee == self.agent_id:
            return True
        if not task.assignee and self.config.role:
            # 未分配的任务，看角色是否匹配
            if self.config.role.task_acquisition in ("self_claim", "both"):
                return True
        return False

    def _get_interval(self) -> int:
        """根据状态获取循环间隔"""
        intervals = {
            AgentStatus.IDLE: 5,
            AgentStatus.WORKING: 2,
            AgentStatus.WAITING: 10,
            AgentStatus.DEGRADED: 15,
            AgentStatus.ERROR: 30,
            AgentStatus.PAUSED: 60,
        }
        return intervals.get(self.status, 5)

    # ═══════════════════════════════════════════
    # 状态查询
    # ═══════════════════════════════════════════

    def get_status_dict(self) -> dict:
        """获取状态信息"""
        return {
            "agent_id": self.agent_id,
            "name": self.config.name,
            "role": self.config.role_id,
            "status": self.status.value,
            "current_task": self.working_memory.current_task_id,
            "uptime": time.time() - self.started_at if self.started_at else 0,
            "llm_calls": self.llm_call_count,
            "tool_calls": self.tool_call_count,
            "tasks_completed": self.task_count,
            "skills": len(self.skills),
            "memory_nodes": self._count_memory_nodes(),
            "errors": self.consecutive_errors,
        }

    def _count_memory_nodes(self) -> int:
        conn = get_db()
        row = conn.execute(
            "SELECT COUNT(*) FROM memory_nodes WHERE agent_id=?",
            (self.agent_id,)
        ).fetchone()
        conn.close()
        return row[0] if row else 0
