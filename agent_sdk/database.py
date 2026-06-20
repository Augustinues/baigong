"""数据库层——SQLite 存储记忆树 + 任务 + 配置"""

import sqlite3
import json
import os
import time
from typing import Optional
from pathlib import Path


DB_PATH = Path.home() / ".agent-company" / "data.db"


def get_db() -> sqlite3.Connection:
    """获取数据库连接（线程级单例）"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化数据库——建表"""
    conn = get_db()
    conn.executescript("""
        -- 记忆节点（树的节点）
        CREATE TABLE IF NOT EXISTS memory_nodes (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            type TEXT NOT NULL,
            content TEXT NOT NULL,
            summary TEXT DEFAULT '',
            tags TEXT DEFAULT '[]',
            parent_id TEXT,
            level INTEGER DEFAULT 0,
            confidence REAL DEFAULT 0.5,
            importance REAL DEFAULT 0.3,
            access_count INTEGER DEFAULT 0,
            last_accessed REAL,
            source_task TEXT DEFAULT '',
            source_agent TEXT DEFAULT '',
            created_at REAL NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_mn_agent ON memory_nodes(agent_id);
        CREATE INDEX IF NOT EXISTS idx_mn_type ON memory_nodes(type);
        CREATE INDEX IF NOT EXISTS idx_mn_parent ON memory_nodes(parent_id);
        CREATE INDEX IF NOT EXISTS idx_mn_tags ON memory_nodes(tags);

        -- 记忆链接（节点间关系）
        CREATE TABLE IF NOT EXISTS memory_links (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            source_id TEXT NOT NULL REFERENCES memory_nodes(id),
            target_id TEXT NOT NULL REFERENCES memory_nodes(id),
            link_type TEXT NOT NULL,
            strength REAL DEFAULT 0.5,
            context TEXT DEFAULT '',
            created_at REAL NOT NULL,
            last_reinforced REAL,
            UNIQUE(agent_id, source_id, target_id, link_type)
        );

        CREATE INDEX IF NOT EXISTS idx_ml_agent ON memory_links(agent_id);
        CREATE INDEX IF NOT EXISTS idx_ml_source ON memory_links(source_id);
        CREATE INDEX IF NOT EXISTS idx_ml_target ON memory_links(target_id);

        -- 全文搜索
        CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
            content, summary, tags,
            content='memory_nodes',
            content_rowid='rowid'
        );

        -- 短期记忆（会话级）
        CREATE TABLE IF NOT EXISTS short_term_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            timestamp REAL NOT NULL,
            type TEXT NOT NULL,
            summary TEXT NOT NULL,
            detail TEXT DEFAULT '',
            task_id TEXT DEFAULT '',
            importance REAL DEFAULT 0.3,
            consolidated INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_stm_agent ON short_term_memory(agent_id);
        CREATE INDEX IF NOT EXISTS idx_stm_time ON short_term_memory(timestamp);

        -- 任务
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            goal TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            progress REAL DEFAULT 0.0,
            creator TEXT DEFAULT '',
            assignee TEXT DEFAULT '',
            parent_task_id TEXT DEFAULT '',
            description TEXT DEFAULT '',
            attachments TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            flow_log TEXT DEFAULT '[]'
        );

        -- Agent 注册表
        CREATE TABLE IF NOT EXISTS agents (
            agent_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            role_id TEXT NOT NULL,
            config TEXT NOT NULL,
            status TEXT DEFAULT 'offline',
            created_at TEXT NOT NULL,
            last_seen REAL
        );

        -- Skill
        CREATE TABLE IF NOT EXISTS skills (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            triggers TEXT DEFAULT '[]',
            steps TEXT DEFAULT '[]',
            confidence REAL DEFAULT 0.5,
            use_count INTEGER DEFAULT 0,
            success_count INTEGER DEFAULT 0,
            formed_at REAL NOT NULL,
            last_used REAL
        );

        CREATE INDEX IF NOT EXISTS idx_skill_agent ON skills(agent_id);
    """)
    conn.commit()
    conn.close()


def now():
    return time.time()
