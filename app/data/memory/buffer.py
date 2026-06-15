"""对话记忆 — Buffer + Summary，SQLite 持久化"""

from typing import Any, Dict, List, Optional

from app.data.memory.base import BaseMemory
from app.data.memory.store import MemoryStore


class ConversationBufferWindowMemory(BaseMemory):
    """保留最近 K 轮对话原文，SQLite 持久化"""

    def __init__(self, k: int = 5):
        self.k = k
        self._store = MemoryStore()

    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        session_id = inputs.get("session_id", "default")
        turns = self._store.get_turns(session_id, last_n=self.k)

        if not turns:
            return {"history": "（无历史记录）"}

        lines = ["以下是最近的对话历史："]
        for t in turns:
            role_label = "用户" if t["role"] == "human" else "助手"
            lines.append(f"[{role_label}]: {t['content'][:500]}")
        return {"history": "\n".join(lines)}

    def save_context(self, inputs: Dict[str, Any],
                     outputs: Dict[str, Any]) -> None:
        session_id = inputs.get("session_id", "default")
        self._store.add_turn(
            session_id,
            human=inputs.get("question", ""),
            ai=outputs.get("answer", ""),
        )

    def clear(self, session_id: str = "") -> None:
        self._store.delete_turns(session_id)


SUMMARY_PROMPT = """将以下对话历史压缩为一小段摘要（不超过 200 字），保留关键信息:

{dialog}

摘要：
- 用户问了什么主题
- 讨论了哪些关键实体/概念
- 有什么未解决的追问

直接输出摘要文本，不要前缀。"""


class ConversationSummaryMemory(BaseMemory):
    """超出窗口的旧对话自动压缩为 LLM 摘要，SQLite 持久化"""

    def __init__(self, llm=None, buffer_window: int = 5):
        self.llm = llm
        self.buffer_window = buffer_window
        self._store = MemoryStore()
        self._pending: Dict[str, List[Dict]] = {}

    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        session_id = inputs.get("session_id", "default")
        summary = self._store.get_summary(session_id)
        if summary:
            return {"summary": f"历史摘要: {summary}"}
        return {"summary": ""}

    def save_context(self, inputs: Dict[str, Any],
                     outputs: Dict[str, Any]) -> None:
        session_id = inputs.get("session_id", "default")
        if session_id not in self._pending:
            self._pending[session_id] = []
        self._pending[session_id].append({
            "human": inputs.get("question", ""),
            "ai": outputs.get("answer", ""),
        })

    async def maybe_compress(self, session_id: str) -> Optional[str]:
        """检查是否需要压缩，返回新摘要"""
        pending = self._pending.get(session_id, [])
        extra = len(pending) - self.buffer_window
        if extra <= 0:
            return None

        to_compress = pending[:extra]
        self._pending[session_id] = pending[extra:]

        new_summary = await self._summarize(to_compress)
        if not new_summary:
            return None

        self._store.save_summary(session_id, new_summary)
        return new_summary

    async def _summarize(self, messages: List[Dict]) -> str:
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

    def clear(self, session_id: str = "") -> None:
        self._pending.pop(session_id, None)
        self._store.delete_summary(session_id)
