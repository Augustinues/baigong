"""长期记忆系统——树 + 图结构的记忆网络"""

import uuid
import json
import time
import sqlite3
from typing import Optional
from collections import deque

from ..models import MemoryNode, MemoryLink, MemoryType
from ..database import get_db, now


class LongTermMemory:
    """长期记忆——树+图结构的持久化记忆网络"""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        # 内存缓存（加速频繁访问的节点）
        self._node_cache: dict[str, MemoryNode] = {}
        self._dirty = False

    # ── 节点 CRUD ──

    def create_node(
        self,
        content: str,
        type: MemoryType = MemoryType.SEMANTIC,
        summary: str = "",
        tags: list[str] | None = None,
        parent_id: str | None = None,
        confidence: float = 0.5,
        importance: float = 0.3,
        source_task: str = "",
    ) -> MemoryNode:
        """创建一个新记忆节点"""
        node_id = f"mem_{uuid.uuid4().hex[:12]}"
        node = MemoryNode(
            id=node_id,
            type=type,
            content=content,
            summary=summary or content[:80],
            tags=tags or [],
            parent_id=parent_id,
            level=0,
            confidence=confidence,
            importance=importance,
            source_task=source_task,
            source_agent=self.agent_id,
            created_at=now(),
        )
        # 如果有父节点，继承层级
        if parent_id:
            parent = self.get_node(parent_id)
            if parent:
                node.level = parent.level + 1

        self._save_node(node)
        self._index_fts(node)
        return node

    def get_node(self, node_id: str) -> MemoryNode | None:
        """获取节点"""
        # 缓存命中
        if node_id in self._node_cache:
            return self._node_cache[node_id]

        conn = get_db()
        row = conn.execute(
            "SELECT * FROM memory_nodes WHERE id=? AND agent_id=?",
            (node_id, self.agent_id)
        ).fetchone()
        conn.close()

        if row:
            node = self._row_to_node(row)
            self._node_cache[node_id] = node
            return node
        return None

    def find_node_by_name(self, name: str) -> MemoryNode | None:
        """按名称（summary 或 content 开头）查找节点"""
        conn = get_db()
        row = conn.execute(
            """SELECT * FROM memory_nodes
               WHERE agent_id=? AND (summary=? OR content LIKE ?)
               LIMIT 1""",
            (self.agent_id, name, f"{name}%")
        ).fetchone()
        conn.close()
        return self._row_to_node(row) if row else None

    def search_nodes(
        self, query: str, type: MemoryType | None = None, limit: int = 10
    ) -> list[MemoryNode]:
        """搜索节点（关键词匹配 content + summary + tags）"""
        conn = get_db()
        sql = """SELECT * FROM memory_nodes
                 WHERE agent_id=? AND (content LIKE ? OR summary LIKE ? OR tags LIKE ?)"""
        params = [self.agent_id, f"%{query}%", f"%{query}%", f"%{query}%"]

        if type:
            sql += " AND type=?"
            params.append(type.value)

        sql += " ORDER BY confidence DESC, importance DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [self._row_to_node(r) for r in rows]

    def fts_search(self, query: str, limit: int = 10) -> list[MemoryNode]:
        """全文搜索（更快更准）"""
        conn = get_db()
        try:
            rows = conn.execute(
                """SELECT n.* FROM memory_nodes n
                   JOIN memory_fts f ON n.rowid = f.rowid
                   WHERE memory_fts MATCH ? AND n.agent_id=?
                   LIMIT ?""",
                (query, self.agent_id, limit)
            ).fetchall()
        except sqlite3.OperationalError:
            # FTS 可能还没索引完，fallback 到 LIKE
            rows = conn.execute(
                """SELECT * FROM memory_nodes
                   WHERE agent_id=? AND (content LIKE ? OR summary LIKE ?)
                   LIMIT ?""",
                (self.agent_id, f"%{query}%", f"%{query}%", limit)
            ).fetchall()
        conn.close()
        return [self._row_to_node(r) for r in rows]

    # ── 链接管理 ──

    def create_link(
        self,
        source_id: str,
        target_id: str,
        link_type: str = "reminds_of",
        strength: float = 0.5,
        context: str = "",
    ) -> MemoryLink:
        """创建节点间链接"""
        link = MemoryLink(
            id=f"lnk_{uuid.uuid4().hex[:12]}",
            source_id=source_id,
            target_id=target_id,
            link_type=link_type,
            strength=strength,
            context=context,
            created_at=now(),
            last_reinforced=now(),
        )
        conn = get_db()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO memory_links
                   (id, agent_id, source_id, target_id, link_type, strength, context, created_at, last_reinforced)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (link.id, self.agent_id, source_id, target_id, link_type,
                 strength, context, link.created_at, link.last_reinforced)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            # 已存在——加强
            conn.execute(
                """UPDATE memory_links SET strength=MIN(strength+0.1, 1.0), last_reinforced=?
                   WHERE agent_id=? AND source_id=? AND target_id=? AND link_type=?""",
                (now(), self.agent_id, source_id, target_id, link_type)
            )
            conn.commit()
        finally:
            conn.close()
        return link

    def reinforce_link(self, source_id: str, target_id: str, link_type: str = "reminds_of"):
        """加强一条链接（每次使用都加强）"""
        conn = get_db()
        conn.execute(
            """UPDATE memory_links SET strength=MIN(strength+0.05, 1.0), last_reinforced=?
               WHERE agent_id=? AND source_id=? AND target_id=? AND link_type=?""",
            (now(), self.agent_id, source_id, target_id, link_type)
        )
        conn.commit()
        conn.close()

    def get_links(self, node_id: str, min_strength: float = 0.0) -> list[MemoryLink]:
        """获取一个节点的所有链接"""
        conn = get_db()
        rows = conn.execute(
            """SELECT * FROM memory_links
               WHERE agent_id=? AND (source_id=? OR target_id=?)
               AND strength >= ? ORDER BY strength DESC""",
            (self.agent_id, node_id, node_id, min_strength)
        ).fetchall()
        conn.close()
        return [self._row_to_link(r) for r in rows]

    def get_children(self, parent_id: str) -> list[MemoryNode]:
        """获取父节点的所有子节点"""
        conn = get_db()
        rows = conn.execute(
            "SELECT * FROM memory_nodes WHERE parent_id=? AND agent_id=? ORDER BY importance DESC",
            (parent_id, self.agent_id)
        ).fetchall()
        conn.close()
        return [self._row_to_node(r) for r in rows]

    # ── 联想检索（树+图遍历）──

    def associative_recall(self, seed: str, depth: int = 2, max_nodes: int = 30) -> list[MemoryNode]:
        """
        联想式检索——从 seed 出发，沿树+链接遍历。
        类似人脑想到一个概念时，自动浮现相关概念。
        """
        # ① 找到入口节点
        entry = self.find_node_by_name(seed)
        if not entry:
            # 用全文搜索找最匹配的
            results = self.fts_search(seed, limit=3)
            if not results:
                return []
            entry = results[0]

        # ② BFS 遍历
        activated: set[str] = set()
        queue: list[tuple[MemoryNode, int]] = [(entry, 0)]
        result: list[MemoryNode] = []

        while queue and len(activated) < max_nodes:
            node, distance = queue.pop(0)

            if node.id in activated:
                continue
            activated.add(node.id)
            result.append(node)

            # 更新访问统计
            self._bump_access(node.id)

            if distance < depth:
                # 向下走树（子节点）
                for child in self.get_children(node.id):
                    if child.id not in activated:
                        queue.append((child, distance + 1))

                # 向上走树（父节点）
                if node.parent_id and node.parent_id not in activated:
                    parent = self.get_node(node.parent_id)
                    if parent:
                        queue.append((parent, distance + 1))

                # 走交叉链接
                for link in self.get_links(node.id, min_strength=0.3):
                    other_id = link.target_id if link.source_id == node.id else link.source_id
                    if other_id not in activated:
                        other = self.get_node(other_id)
                        if other:
                            queue.append((other, distance + 1))
                            # 使用链接时加强它
                            self.reinforce_link(link.source_id, link.target_id, link.link_type)

        return result

    def create_shortcut(self, from_id: str, to_id: str, strength: float = 0.9):
        """
        创建快捷方式——当一条路径被频繁使用时，
        直接从起点链接到终点，跳过中间节点。
        这是"熟练"的本质。
        """
        self.create_link(from_id, to_id, link_type="shortcut", strength=strength)

    # ── 知识导入/导出 ──

    def export_subtree(self, root_name: str) -> str:
        """导出根节点及其子树的全部内容（格式化成 markdown）"""
        root = self.find_node_by_name(root_name)
        if not root:
            return f"# 未找到节点: {root_name}\n"

        lines = [f"# {root.summary}", f"置信度: {root.confidence:.0%}", "", root.content, ""]

        def walk(node_id: str, level: int = 1):
            for child in self.get_children(node_id):
                prefix = "#" * (level + 1)
                lines.append(f"{prefix} {child.summary}")
                lines.append(f"类型: {child.type.value}  置信度: {child.confidence:.0%}")
                lines.append("")
                lines.append(child.content)
                lines.append("")
                walk(child.id, level + 1)

        walk(root.id)
        return "\n".join(lines)

    def import_nodes(self, nodes: list[MemoryNode], parent_id: str | None = None):
        """批量导入节点（用于知识传承）"""
        conn = get_db()
        for node in nodes:
            node.source_agent = self.agent_id
            node.created_at = now()
            if parent_id:
                node.parent_id = parent_id
            self._save_node(node, conn=conn)
        conn.commit()
        conn.close()

    # ── 内部方法 ──

    def _save_node(self, node: MemoryNode, conn=None):
        """保存节点到数据库"""
        if conn is None:
            conn = get_db()
            conn.execute(
                """INSERT OR REPLACE INTO memory_nodes
                   (id, agent_id, type, content, summary, tags, parent_id, level,
                    confidence, importance, access_count, last_accessed,
                    source_task, source_agent, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (node.id, self.agent_id, node.type.value, node.content,
                 node.summary, json.dumps(node.tags), node.parent_id, node.level,
                 node.confidence, node.importance, node.access_count, node.last_accessed,
                 node.source_task, node.source_agent, node.created_at)
            )
            conn.commit()
            conn.close()
        else:
            conn.execute(
                """INSERT OR REPLACE INTO memory_nodes
                   (id, agent_id, type, content, summary, tags, parent_id, level,
                    confidence, importance, access_count, last_accessed,
                    source_task, source_agent, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (node.id, self.agent_id, node.type.value, node.content,
                 node.summary, json.dumps(node.tags), node.parent_id, node.level,
                 node.confidence, node.importance, node.access_count, node.last_accessed,
                 node.source_task, node.source_agent, node.created_at)
            )
        self._node_cache[node.id] = node

    def _index_fts(self, node: MemoryNode):
        """更新全文搜索索引"""
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO memory_fts(rowid, content, summary, tags) VALUES (?, ?, ?, ?)",
                (self._get_rowid(node.id), node.content, node.summary, json.dumps(node.tags))
            )
            conn.commit()
        except sqlite3.OperationalError:
            pass  # FTS 可能还没准备好
        finally:
            conn.close()

    def _get_rowid(self, node_id: str) -> int:
        conn = get_db()
        row = conn.execute(
            "SELECT rowid FROM memory_nodes WHERE id=?", (node_id,)
        ).fetchone()
        conn.close()
        return row[0] if row else 0

    def _bump_access(self, node_id: str):
        """增加访问计数"""
        conn = get_db()
        conn.execute(
            "UPDATE memory_nodes SET access_count=access_count+1, last_accessed=? WHERE id=?",
            (now(), node_id)
        )
        conn.commit()
        conn.close()

    def _row_to_node(self, row) -> MemoryNode:
        return MemoryNode(
            id=row["id"],
            type=MemoryType(row["type"]),
            content=row["content"],
            summary=row["summary"],
            tags=json.loads(row["tags"]) if isinstance(row["tags"], str) else [],
            parent_id=row["parent_id"],
            level=row["level"],
            confidence=row["confidence"],
            importance=row["importance"],
            access_count=row["access_count"],
            last_accessed=row["last_accessed"],
            source_task=row["source_task"],
            source_agent=row["source_agent"],
            created_at=row["created_at"],
        )

    def _row_to_link(self, row) -> MemoryLink:
        return MemoryLink(
            id=row["id"],
            source_id=row["source_id"],
            target_id=row["target_id"],
            link_type=row["link_type"],
            strength=row["strength"],
            context=row["context"],
            created_at=row["created_at"],
            last_reinforced=row["last_reinforced"],
        )

    # ── 遗忘（降低不重要节点的强度，不删除）──

    def decay(self, days_threshold: int = 30):
        """降低长期未访问节点的置信度和链接强度"""
        conn = get_db()
        cutoff = now() - days_threshold * 86400

        # 降低未访问节点的置信度
        conn.execute(
            """UPDATE memory_nodes SET confidence=MAX(confidence-0.1, 0.1)
               WHERE agent_id=? AND last_accessed IS NOT NULL AND last_accessed < ?""",
            (self.agent_id, cutoff)
        )

        # 降低未加强的链接强度
        conn.execute(
            """UPDATE memory_links SET strength=MAX(strength-0.05, 0.1)
               WHERE agent_id=? AND last_reinforced IS NOT NULL AND last_reinforced < ?""",
            (self.agent_id, cutoff)
        )

        conn.commit()
        conn.close()
