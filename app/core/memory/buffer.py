"""对话记忆 — ConversationBufferWindowMemory + ConversationSummaryMemory"""

import json
import os
import time
from typing import Any, Dict, List, Optional

from app.core.memory.base import BaseMemory


class ConversationBufferWindowMemory(BaseMemory):
    """保留最近 K 轮对话原文，持久化 JSON 文件

    存储格式:
        {session_id}/conversation.json →
        [{"human": "...", "ai": "...", "ts": 1.7e9}, ...]
    """

    def __init__(self, k: int = 5, storage_dir: str = "./memory_store"):
        self.k = k
        self._storage_dir = storage_dir

    def _path(self, session_id: str) -> str:
        sid = session_id or "default"
        return os.path.join(self._storage_dir, sid, "conversation.json")

    def _load(self, session_id: str) -> List[Dict]:
        path = self._path(session_id)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return []

    def _save(self, session_id: str, turns: List[Dict]) -> None:
        path = self._path(session_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(turns, f, ensure_ascii=False, indent=2)

    # ── Memory 接口 ──────────────────────────

    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        session_id = inputs.get("session_id", "default")
        turns = self._load(session_id)[-self.k:]

        if not turns:
            return {"history": "（无历史记录）"}

        lines = ["以下是最近的对话历史："]
        for t in turns:
            lines.append(f"[用户]: {t.get('human', '')[:500]}")
            lines.append(f"[助手]: {t.get('ai', '')[:500]}")
        return {"history": "\n".join(lines)}

    def save_context(self, inputs: Dict[str, Any],
                     outputs: Dict[str, Any]) -> None:
        session_id = inputs.get("session_id", "default")
        turns = self._load(session_id)
        turns.append({
            "human": inputs.get("question", ""),
            "ai": outputs.get("answer", ""),
            "ts": time.time(),
        })
        if len(turns) > self.k * 2:
            turns = turns[-self.k:]
        self._save(session_id, turns)

    def clear(self, session_id: str = "") -> None:
        path = self._path(session_id)
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


# ──────────────────────────────────────────────────────
# 摘要记忆
# ──────────────────────────────────────────────────────

SUMMARY_PROMPT = """将以下对话历史压缩为一小段摘要（不超过 200 字），保留关键信息:

{dialog}

摘要：
- 用户问了什么主题
- 讨论了哪些关键实体/概念
- 有什么未解决的追问

直接输出摘要文本，不要前缀。"""


class ConversationSummaryMemory(BaseMemory):
    """超出窗口的旧对话自动压缩为 LLM 摘要

    与 ConversationBufferWindowMemory 配合使用:
        buffer 保留最近 K 轮原文
        超出 K 轮的旧消息交给 summarizer 压缩

    存储格式:
        {session_id}/summary.json → {"summary": "...", "compressed_turns": N}
    """

    def __init__(self, llm=None, buffer_window: int = 5,
                 storage_dir: str = "./memory_store"):
        self.llm = llm
        self.buffer_window = buffer_window
        self._storage_dir = storage_dir
        self._pending: Dict[str, List[Dict]] = {}

    def _path(self, session_id: str) -> str:
        sid = session_id or "default"
        return os.path.join(self._storage_dir, sid, "summary.json")

    def _load_summary(self, session_id: str) -> Dict:
        path = self._path(session_id)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"summary": "", "compressed_turns": 0}

    def _save_summary(self, session_id: str, data: Dict) -> None:
        path = self._path(session_id)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    async def _summarize(self, messages: List[Dict]) -> str:
        """LLM 压缩多条消息为一个摘要"""
        if not self.llm:
            return ""

        dialog_lines = []
        for m in messages:
            dialog_lines.append(f"用户: {m.get('human', '')}")
            dialog_lines.append(f"助手: {m.get('ai', '')}")
        dialog_text = "\n".join(dialog_lines)

        try:
            prompt = SUMMARY_PROMPT.format(dialog=dialog_text[:3000])
            summary = await self.llm._call_llm(prompt)
            return summary.strip()[:300]
        except Exception:
            return ""

    # ── Memory 接口 ──────────────────────────

    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        session_id = inputs.get("session_id", "default")
        data = self._load_summary(session_id)
        summary = data.get("summary", "")
        if summary:
            return {"summary": f"历史摘要: {summary}"}
        return {"summary": ""}

    def save_context(self, inputs: Dict[str, Any],
                     outputs: Dict[str, Any]) -> None:
        """收集对话轮次，不下发摘要 — _maybe_compress 由外部在 save_turn 时调用"""
        session_id = inputs.get("session_id", "default")
        if session_id not in self._pending:
            self._pending[session_id] = []
        self._pending[session_id].append({
            "human": inputs.get("question", ""),
            "ai": outputs.get("answer", ""),
        })

    async def maybe_compress(self, session_id: str) -> Optional[str]:
        """检查是否需要压缩，返回新摘要（如果有的话）"""
        pending = self._pending.get(session_id, [])
        extra = len(pending) - self.buffer_window
        if extra <= 0:
            return None

        to_compress = pending[:extra]
        self._pending[session_id] = pending[extra:]

        new_summary = await self._summarize(to_compress)
        if not new_summary:
            return None

        data = self._load_summary(session_id)
        old = data.get("summary", "")
        if old:
            data["summary"] = old + " | " + new_summary
        else:
            data["summary"] = new_summary
        data["compressed_turns"] = data.get("compressed_turns", 0) + len(to_compress)
        self._save_summary(session_id, data)
        return data["summary"]

    def clear(self, session_id: str = "") -> None:
        self._pending.pop(session_id, None)
        path = self._path(session_id)
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
