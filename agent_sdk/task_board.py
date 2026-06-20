"""任务看板——共享任务空间"""

import uuid
import json
import time
from datetime import datetime
from typing import Optional

from .models import Task, TaskStatus
from .database import get_db


class TaskBoard:
    """任务看板——所有任务共享"""

    def __init__(self):
        pass

    def create_task(
        self,
        goal: str,
        creator: str = "ceo",
        assignee: str = "",
        parent_task_id: str = "",
        description: str = "",
    ) -> Task:
        """创建新任务"""
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        task = Task(
            id=task_id,
            goal=goal,
            creator=creator,
            assignee=assignee,
            parent_task_id=parent_task_id,
            description=description,
            created_at=datetime.now(),
            status=TaskStatus.PENDING,
        )
        task.log("创建", creator)

        conn = get_db()
        conn.execute(
            """INSERT INTO tasks
               (id, goal, status, progress, creator, assignee, parent_task_id,
                description, attachments, created_at, flow_log)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (task.id, task.goal, task.status.value, task.progress,
             task.creator, task.assignee, task.parent_task_id,
             task.description, json.dumps(task.attachments),
             task.created_at.isoformat(), json.dumps(task.flow_log))
        )
        conn.commit()
        conn.close()
        return task

    def get_task(self, task_id: str) -> Task | None:
        """获取任务"""
        conn = get_db()
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        conn.close()
        return self._row_to_task(row) if row else None

    def update_task(self, task_id: str, **kwargs):
        """更新任务字段"""
        allowed = {"status", "progress", "assignee", "description", "attachments"}
        conn = get_db()
        for key, value in kwargs.items():
            if key in allowed:
                if key == "status" and isinstance(value, TaskStatus):
                    value = value.value
                if key in ("attachments",):
                    value = json.dumps(value)
                conn.execute(f"UPDATE tasks SET {key}=? WHERE id=?", (value, task_id))
        conn.commit()
        conn.close()

    def claim_task(self, task_id: str, agent_id: str) -> bool:
        """领取任务（返回是否成功）"""
        conn = get_db()
        row = conn.execute(
            "SELECT status, assignee FROM tasks WHERE id=?", (task_id,)
        ).fetchone()
        if not row:
            conn.close()
            return False

        # 已被认领
        if row["assignee"] and row["assignee"] != agent_id:
            conn.close()
            return False

        conn.execute(
            "UPDATE tasks SET assignee=?, status=?, started_at=? WHERE id=?",
            (agent_id, TaskStatus.IN_PROGRESS.value, datetime.now().isoformat(), task_id)
        )
        conn.commit()
        conn.close()

        # 记录日志
        task = self.get_task(task_id)
        if task:
            task.log(f"被 {agent_id} 领取", agent_id)
            self._save_flow_log(task)
        return True

    def complete_task(self, task_id: str, result: str = ""):
        """完成任务"""
        conn = get_db()
        conn.execute(
            "UPDATE tasks SET status=?, progress=1.0, completed_at=? WHERE id=?",
            (TaskStatus.COMPLETED.value, datetime.now().isoformat(), task_id)
        )
        conn.commit()
        conn.close()

        task = self.get_task(task_id)
        if task:
            task.log(f"完成: {result[:100]}", task.assignee)
            self._save_flow_log(task)

    def fail_task(self, task_id: str, reason: str = ""):
        """标记任务失败"""
        conn = get_db()
        conn.execute("UPDATE tasks SET status=? WHERE id=?", (TaskStatus.FAILED.value, task_id))
        conn.commit()
        conn.close()

        task = self.get_task(task_id)
        if task:
            task.log(f"失败: {reason[:100]}", task.assignee)
            self._save_flow_log(task)

    def get_pending_tasks(self, limit: int = 20) -> list[Task]:
        """获取待处理任务"""
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM tasks WHERE status=? ORDER BY created_at ASC LIMIT ?",
            (TaskStatus.PENDING.value, limit)
        ).fetchall()
        conn.close()
        return [self._row_to_task(r) for r in rows]

    def get_active_tasks(self, limit: int = 20) -> list[Task]:
        """获取进行中的任务"""
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM tasks WHERE status=? ORDER BY created_at ASC LIMIT ?",
            (TaskStatus.IN_PROGRESS.value, limit)
        ).fetchall()
        conn.close()
        return [self._row_to_task(r) for r in rows]

    def get_tasks_by_assignee(self, agent_id: str) -> list[Task]:
        """获取分配给某个 Agent 的任务"""
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM tasks WHERE assignee=? ORDER BY created_at DESC",
            (agent_id,)
        ).fetchall()
        conn.close()
        return [self._row_to_task(r) for r in rows]

    def _save_flow_log(self, task: Task):
        conn = get_db()
        conn.execute(
            "UPDATE tasks SET flow_log=? WHERE id=?",
            (json.dumps(task.flow_log), task.id)
        )
        conn.commit()
        conn.close()

    def _row_to_task(self, row) -> Task:
        return Task(
            id=row["id"],
            goal=row["goal"],
            status=TaskStatus(row["status"]),
            progress=row["progress"],
            creator=row["creator"],
            assignee=row["assignee"],
            parent_task_id=row["parent_task_id"],
            description=row["description"],
            attachments=json.loads(row["attachments"]) if isinstance(row["attachments"], str) else [],
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            flow_log=json.loads(row["flow_log"]) if isinstance(row["flow_log"], str) else [],
        )
