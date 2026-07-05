"""EntityMemory — 跨 session 积累实体知识

存储格式 (entities.json):
    {
      "项目名称": {
        "type": "project",
        "metadata": {"province": "广东", "winner": "XX公司", "amount": 5000000},
        "count": 5,
        "first_seen": 1718000000.0,
        "last_seen": 1718100000.0
      },
      ...
    }
"""

import json
import os
import time
from typing import Any, Dict, List, Optional

from app.core.memory.base import BaseMemory


class EntityMemory(BaseMemory):
    """跨 session 实体记忆 — 积累项目名、公司名、法条号等关键实体

    当同一个实体被多次提及，count 增加，last_seen 更新。
    可以按名称精确查找，也可以按关键词模糊搜索。
    """

    def __init__(self, storage_dir: str = "./memory_store"):
        self._storage_dir = storage_dir
        self._store: Dict[str, Dict] = {}
        self._path = os.path.join(storage_dir, "entities.json")
        self._dirty = False
        self._load()

    # ── 读写接口 ──────────────────────────────

    def remember(self, name: str, etype: str = "unknown",
                 metadata: Optional[Dict] = None) -> None:
        """记住一个实体，重复出现则更新 count"""
        name = name.strip()
        if not name or len(name) < 2:
            return

        now = time.time()
        if name in self._store:
            entry = self._store[name]
            entry["count"] += 1
            entry["last_seen"] = now
            if metadata:
                entry["metadata"].update(metadata)
        else:
            self._store[name] = {
                "type": etype,
                "metadata": metadata or {},
                "count": 1,
                "first_seen": now,
                "last_seen": now,
            }
        self._dirty = True

    def recall(self, name: str) -> Optional[Dict]:
        """按名称精确查找实体"""
        return self._store.get(name.strip())

    def search(self, query: str) -> List[Dict]:
        """模糊搜索实体 — 名称包含 query 子串"""
        q = query.strip().lower()
        results = []
        for name, entry in self._store.items():
            if q in name.lower():
                results.append({"name": name, **entry})
        results.sort(key=lambda r: r["count"], reverse=True)
        return results[:10]

    def get_frequent(self, limit: int = 20) -> List[Dict]:
        """获取最常出现的实体"""
        items = [{"name": k, **v} for k, v in self._store.items()]
        items.sort(key=lambda x: x["count"], reverse=True)
        return items[:limit]

    # ── Memory 接口 ──────────────────────────

    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """从问题中提取提及的实体，返回上下文"""
        question = inputs.get("question", "")
        entities_text = self._format_mentioned(question)
        return {"entities": entities_text}

    def save_context(self, inputs: Dict[str, Any],
                     outputs: Dict[str, Any]) -> None:
        """从答案和检索结果中提取实体"""
        entities = outputs.get("entities", {})
        question = inputs.get("question", "")

        project = entities.get("project_name", "")
        winner = entities.get("winner", "")
        province = entities.get("province", "")

        if project:
            meta = {}
            if winner:
                meta["winner"] = winner
            if province:
                meta["province"] = province
            self.remember(project, etype="project", metadata=meta)
        if winner:
            self.remember(winner, etype="company")

        # 从 question 和 answer 中提取法条号
        answer = outputs.get("answer", "")
        self._extract_articles(question)
        self._extract_articles(answer)

    def clear(self, session_id: str = "") -> None:
        """清空全局实体库"""
        self._store.clear()
        self._dirty = True
        self._save()

    # ── 内部 ─────────────────────────────────

    def _format_mentioned(self, question: str) -> str:
        """从实体库查找问题中提及的实体，返回格式化文本"""
        found = []
        for name, entry in self._store.items():
            if name in question and len(name) >= 2:
                meta = entry.get("metadata", {})
                parts = [name]
                if meta.get("winner"):
                    parts.append(f"(中标人: {meta['winner']})")
                if meta.get("province"):
                    parts.append(f"({meta['province']})")
                parts.append(f"[提及{entry['count']}次]")
                found.append(" ".join(parts))

        if found:
            return "已知实体: " + "; ".join(found[:5])
        return ""

    def _extract_articles(self, text: str) -> None:
        """从文本中提取法条号"""
        import re
        patterns = [
            r'第([一二三四五六七八九十百千\d]+)条',
            r'《([^》]+)》',
        ]
        for pattern in patterns:
            for match in re.findall(pattern, text):
                self.remember(match, etype="legal_reference")

    def _load(self) -> None:
        os.makedirs(self._storage_dir, exist_ok=True)
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._store = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._store = {}

    def _save(self) -> None:
        if not self._dirty:
            return
        os.makedirs(self._storage_dir, exist_ok=True)
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._store, f, ensure_ascii=False, indent=2)
            self._dirty = False
        except IOError:
            pass

    def __del__(self):
        self._save()
