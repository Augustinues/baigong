"""短期记忆和工作记忆"""

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

from ..database import get_db, now


# ═══════════════════════════════════════════
# 工作记忆（内存级，不持久化）
# ═══════════════════════════════════════════

@dataclass
class WorkingMemory:
    """工作记忆——Agent 当前正在做的事（内存中）"""

    current_task_id: str | None = None
    current_action: str | None = None
    task_progress: float = 0.0
    task_context: dict = field(default_factory=dict)
    pending_actions: list[str] = field(default_factory=list)
    last_action_result: str | None = None

    # 暂挂事项（等会要处理的）
    parked: list[dict] = field(default_factory=list)

    # 最近几次思考（最多 5 条）
    recent_thoughts: deque = field(default_factory=lambda: deque(maxlen=5))

    def set_task(self, task_id: str, context: dict = None):
        """切换到新任务——自动保存当前上下文到摘要"""
        self.current_task_id = task_id
        self.task_context = context or {}
        self.task_progress = 0.0
        self.pending_actions.clear()

    def add_thought(self, thought: str):
        """记录一次思考"""
        self.recent_thoughts.append(f"[{time.strftime('%H:%M:%S')}] {thought}")

    def to_prompt(self) -> str:
        """拼装成 LLM prompt 的一部分"""
        lines = ["【当前状态】"]
        if self.current_task_id:
            lines.append(f"任务: {self.current_task_id} ({self.task_progress:.0%})")
        if self.current_action:
            lines.append(f"正在: {self.current_action}")
        if self.pending_actions:
            lines.append(f"下一步: {', '.join(self.pending_actions[:3])}")
        if self.parked:
            lines.append(f"暂挂事项: {len(self.parked)} 件")
        if self.recent_thoughts:
            lines.append("最近思考:")
            lines.extend(f"  {t}" for t in self.recent_thoughts)
        return '\n'.join(lines)

    def clear(self):
        """清空工作记忆（任务切换时）"""
        self.current_task_id = None
        self.current_action = None
        self.task_progress = 0.0
        self.task_context.clear()
        self.pending_actions.clear()
        self.parked.clear()
        self.recent_thoughts.clear()

    def compress_to_summary(self) -> str:
        """压缩成摘要（用于任务切换时保存）"""
        return (
            f"任务 {self.current_task_id}: "
            f"进度 {self.task_progress:.0%}, "
            f"下一步: {', '.join(self.pending_actions[:2])}"
        )


# ═══════════════════════════════════════════
# 短期记忆（会话级，内存+SQLite）
# ═══════════════════════════════════════════

@dataclass
class ShortTermEntry:
    timestamp: float
    type: str          # thought | action | message | tool_call | result | error
    summary: str
    detail: str = ""
    task_id: str = ""
    importance: float = 0.3


class ShortTermMemory:
    """短期记忆——时间线式存储"""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self._buffer: list[ShortTermEntry] = []
        self._buffer_size = 20

    def record(self, type: str, summary: str, detail: str = "",
               task_id: str = "", importance: float = 0.3):
        """记录一条短期记忆"""
        entry = ShortTermEntry(
            timestamp=now(),
            type=type,
            summary=summary,
            detail=detail,
            task_id=task_id,
            importance=importance,
        )
        self._buffer.append(entry)

        # 缓冲满 → 刷盘
        if len(self._buffer) >= self._buffer_size:
            self._flush()

    def _flush(self):
        """批量写入 SQLite"""
        if not self._buffer:
            return
        conn = get_db()
        for entry in self._buffer:
            conn.execute(
                """INSERT INTO short_term_memory
                   (agent_id, timestamp, type, summary, detail, task_id, importance)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (self.agent_id, entry.timestamp, entry.type, entry.summary,
                 entry.detail, entry.task_id, entry.importance)
            )
        conn.commit()
        conn.close()
        self._buffer.clear()

    def get_timeline(self, hours: int = 24) -> str:
        """获取时间线"""
        # 先刷盘
        self._flush()

        conn = get_db()
        cutoff = now() - hours * 3600
        rows = conn.execute(
            """SELECT timestamp, type, summary FROM short_term_memory
               WHERE agent_id=? AND timestamp > ? ORDER BY timestamp ASC LIMIT 200""",
            (self.agent_id, cutoff)
        ).fetchall()
        conn.close()

        lines = []
        for row in rows:
            t = time.strftime("%H:%M", time.localtime(row["timestamp"]))
            icon = {"thought": "💭", "action": "🛠", "message": "📨",
                    "tool_call": "🔧", "result": "📝", "error": "❌",
                    "reflection": "📌"}.get(row["type"], "•")
            lines.append(f"[{t}] {icon} {row['summary']}")

        return '\n'.join(lines)

    def search_recent(self, query: str, limit: int = 10) -> list[ShortTermEntry]:
        """搜索近期记忆"""
        self._flush()
        conn = get_db()
        rows = conn.execute(
            """SELECT * FROM short_term_memory
               WHERE agent_id=? AND (summary LIKE ? OR detail LIKE ?)
               ORDER BY timestamp DESC LIMIT ?""",
            (self.agent_id, f"%{query}%", f"%{query}%", limit)
        ).fetchall()
        conn.close()
        return [
            ShortTermEntry(
                timestamp=r["timestamp"],
                type=r["type"],
                summary=r["summary"],
                detail=r["detail"],
                task_id=r["task_id"],
                importance=r["importance"],
            )
            for r in rows
        ]

    def get_unconsolidated(self) -> list[ShortTermEntry]:
        """获取尚未巩固到长期的记忆"""
        self._flush()
        conn = get_db()
        rows = conn.execute(
            """SELECT * FROM short_term_memory
               WHERE agent_id=? AND consolidated=0 AND importance >= 0.4
               ORDER BY importance DESC LIMIT 50""",
            (self.agent_id,)
        ).fetchall()
        conn.close()
        return [
            ShortTermEntry(
                timestamp=r["timestamp"],
                type=r["type"],
                summary=r["summary"],
                detail=r["detail"],
                task_id=r["task_id"],
                importance=r["importance"],
            )
            for r in rows
        ]

    def mark_consolidated(self, entry_ids: list[int]):
        """标记已巩固"""
        conn = get_db()
        for eid in entry_ids:
            conn.execute(
                "UPDATE short_term_memory SET consolidated=1 WHERE id=? AND agent_id=?",
                (eid, self.agent_id)
            )
        conn.commit()
        conn.close()

    def clear(self):
        """清空（关闭时调用）"""
        self._flush()
        conn = get_db()
        conn.execute("DELETE FROM short_term_memory WHERE agent_id=?", (self.agent_id,))
        conn.commit()
        conn.close()
