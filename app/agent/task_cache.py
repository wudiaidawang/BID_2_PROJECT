"""TaskAnalysis 缓存 — SQLite top 50 频率最高"""

import json
import re
import sqlite3

from config import settings


class TaskAnalysisCache:
    """TaskAnalysis 结果缓存（50条，按 access_count 淘汰）

    Schema:
        CREATE TABLE IF NOT EXISTS task_analysis_cache (
            fingerprint TEXT PRIMARY KEY,
            original TEXT,
            tasks_json TEXT NOT NULL,
            access_count INTEGER DEFAULT 1,
            created_at REAL,
            last_access REAL
        )
    """

    MAX_ENTRIES = 50

    def __init__(self):
        self._initialized = False

    def _ensure_schema(self):
        if self._initialized:
            return
        db_path = settings.checkpoint_db_path
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_analysis_cache (
                    fingerprint TEXT PRIMARY KEY,
                    original TEXT,
                    tasks_json TEXT NOT NULL,
                    access_count INTEGER DEFAULT 1,
                    created_at REAL,
                    last_access REAL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cache_access
                ON task_analysis_cache(access_count DESC)
            """)
            conn.commit()
        self._initialized = True

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(settings.checkpoint_db_path)

    @staticmethod
    def fingerprint(question: str) -> str:
        """归一化 question 为指纹"""
        # 去标点、去空白、小写、截断
        cleaned = re.sub(r'[^\w一-鿿]', '', question.strip().lower())
        return cleaned[:200]

    def get(self, question: str) -> list | None:
        """查询缓存，返回 Task 列表或 None"""
        self._ensure_schema()
        fp = self.fingerprint(question)
        with self._conn() as conn:
            row = conn.execute(
                "SELECT tasks_json FROM task_analysis_cache WHERE fingerprint = ?",
                (fp,)
            ).fetchone()
            if row:
                # 更新访问计数
                import time
                conn.execute(
                    "UPDATE task_analysis_cache SET access_count = access_count + 1, "
                    "last_access = ? WHERE fingerprint = ?",
                    (time.time(), fp)
                )
                conn.commit()
                return json.loads(row[0])
        return None

    def put(self, question: str, tasks: list) -> None:
        """写入或更新缓存"""
        self._ensure_schema()
        import time
        fp = self.fingerprint(question)
        ts = time.time()
        with self._conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO task_analysis_cache "
                "(fingerprint, original, tasks_json, access_count, created_at, last_access) "
                "VALUES (?, ?, ?, "
                "COALESCE((SELECT access_count FROM task_analysis_cache WHERE fingerprint = ?), 0) + 1, "
                "COALESCE((SELECT created_at FROM task_analysis_cache WHERE fingerprint = ?), ?), "
                "?)",
                (fp, question[:200], json.dumps(tasks, ensure_ascii=False),
                 fp, fp, ts, ts)
            )
            conn.commit()

        # 淘汰
        self._evict()

    def _evict(self) -> None:
        """淘汰 access_count 最低的记录（超过 50 条时）"""
        with self._conn() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM task_analysis_cache"
            ).fetchone()[0]
            if count > self.MAX_ENTRIES:
                excess = count - self.MAX_ENTRIES
                conn.execute(
                    "DELETE FROM task_analysis_cache WHERE fingerprint IN "
                    "(SELECT fingerprint FROM task_analysis_cache "
                    "ORDER BY access_count ASC LIMIT ?)",
                    (excess,)
                )
                conn.commit()
                print(f"[TaskCache] Evicted {excess} entries (now {self.MAX_ENTRIES})")
