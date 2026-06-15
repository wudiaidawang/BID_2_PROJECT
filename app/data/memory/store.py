"""Memory SQLite 存储后端 — 与 LangGraph Checkpoint 同库"""

import json
import sqlite3
import threading
from typing import Any, Dict, List, Optional

from config import settings


class MemoryStore:
    """SQLite 记忆存储（单例），线程安全"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def _ensure_schema(self):
        if self._initialized:
            return
        db_path = settings.checkpoint_db_path
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_turns (
                    session_id TEXT NOT NULL,
                    turn_index INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    ts REAL NOT NULL,
                    PRIMARY KEY (session_id, turn_index)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_summary (
                    session_id TEXT PRIMARY KEY,
                    summary TEXT NOT NULL DEFAULT '',
                    compressed_turns INTEGER NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL
                )
            """)
            conn.commit()
        self._initialized = True

    def _get_conn(self) -> sqlite3.Connection:
        db_path = settings.checkpoint_db_path
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ── Buffer 操作 ──────────────────────────

    def get_turns(self, session_id: str, last_n: int = 10) -> List[Dict]:
        """获取最近 N 轮对话"""
        self._ensure_schema()
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT role, content, turn_index FROM memory_turns "
                "WHERE session_id = ? ORDER BY turn_index DESC LIMIT ?",
                (session_id, last_n * 2)
            ).fetchall()
        turns = []
        for row in reversed(rows):
            turns.append({
                "role": row["role"],
                "content": row["content"],
                "turn_index": row["turn_index"],
            })
        return turns

    def add_turn(self, session_id: str, human: str, ai: str) -> None:
        """添加一轮对话（human + ai 两条记录）"""
        self._ensure_schema()
        ts = __import__("time").time()
        with self._get_conn() as conn:
            # 获取下一个 turn_index
            max_idx = conn.execute(
                "SELECT COALESCE(MAX(turn_index), -1) FROM memory_turns WHERE session_id = ?",
                (session_id,)
            ).fetchone()[0]
            nxt = max_idx + 1
            conn.execute(
                "INSERT INTO memory_turns VALUES (?, ?, ?, ?, ?)",
                (session_id, nxt, "human", human, ts)
            )
            conn.execute(
                "INSERT INTO memory_turns VALUES (?, ?, ?, ?, ?)",
                (session_id, nxt + 1, "ai", ai, ts)
            )
            # 只在超过 50 条时清理旧记录（保留最近 20 轮 = 40 条）
            count = conn.execute(
                "SELECT COUNT(*) FROM memory_turns WHERE session_id = ?",
                (session_id,)
            ).fetchone()[0]
            if count > 50:
                min_keep = conn.execute(
                    "SELECT turn_index FROM memory_turns WHERE session_id = ? "
                    "ORDER BY turn_index DESC LIMIT 1 OFFSET 39",
                    (session_id,)
                ).fetchone()
                if min_keep:
                    conn.execute(
                        "DELETE FROM memory_turns WHERE session_id = ? AND turn_index < ?",
                        (session_id, min_keep[0])
                    )
            conn.commit()

    def delete_turns(self, session_id: str) -> None:
        """删除会话的所有对话记录"""
        self._ensure_schema()
        with self._get_conn() as conn:
            conn.execute("DELETE FROM memory_turns WHERE session_id = ?",
                        (session_id,))
            conn.commit()

    # ── Summary 操作 ──────────────────────────

    def get_summary(self, session_id: str) -> Optional[str]:
        """获取会话摘要"""
        self._ensure_schema()
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT summary FROM memory_summary WHERE session_id = ?",
                (session_id,)
            ).fetchone()
        if row and row["summary"]:
            return row["summary"]
        return None

    def save_summary(self, session_id: str, summary: str) -> None:
        """保存或更新会话摘要"""
        self._ensure_schema()
        ts = __import__("time").time()
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO memory_summary (session_id, summary, compressed_turns, updated_at) "
                "VALUES (?, ?, 1, ?) ON CONFLICT(session_id) DO UPDATE SET "
                "summary = memory_summary.summary || ' | ' || excluded.summary, "
                "compressed_turns = memory_summary.compressed_turns + 1, "
                "updated_at = excluded.updated_at",
                (session_id, summary, ts)
            )
            conn.commit()

    def delete_summary(self, session_id: str) -> None:
        """删除会话摘要"""
        self._ensure_schema()
        with self._get_conn() as conn:
            conn.execute("DELETE FROM memory_summary WHERE session_id = ?",
                        (session_id,))
            conn.commit()
