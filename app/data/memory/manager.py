"""MemoryManager — 统一协调 Buffer + Summary，SQLite 持久化"""

from typing import Any, Dict, Optional

from app.data.memory.buffer import (
    ConversationBufferWindowMemory,
    ConversationSummaryMemory,
)


class MemoryManager:
    """记忆管理器 — Buffer（近期对话）+ Summary（长期摘要）

    用法:
        mm = MemoryManager(llm=generator)

        # 提问前
        ctx = mm.load_context(session_id, question)

        # 回答后
        mm.save_turn(session_id, question, answer)

        # 清理
        mm.forget_session(session_id)
    """

    def __init__(
        self,
        llm=None,
        buffer_k: int = 5,
        summary_enabled: bool = True,
    ):
        self.llm = llm
        self.buffer = ConversationBufferWindowMemory(k=buffer_k)
        self.summary = ConversationSummaryMemory(
            llm=llm, buffer_window=buffer_k
        ) if summary_enabled else None

    def load_context(self, session_id: str, question: str) -> Dict[str, str]:
        """获取可注入 LLM prompt 的记忆上下文"""
        sid = session_id or "default"
        inputs = {"session_id": sid, "question": question}

        history_vars = self.buffer.load_memory_variables(inputs)
        history = history_vars.get("history", "")

        summary = ""
        if self.summary:
            summary_vars = self.summary.load_memory_variables(inputs)
            summary = summary_vars.get("summary", "")

        parts = []
        if summary:
            parts.append(summary)
        if history and "无历史记录" not in history:
            parts.append(history)
        full_context = "\n".join(parts)

        return {
            "history": history,
            "summary": summary,
            "full_context": full_context,
        }

    def save_turn(
        self,
        session_id: str,
        question: str,
        answer: str,
        entities: Optional[Dict] = None,
    ) -> None:
        """保存一轮对话"""
        sid = session_id or "default"
        inputs = {"session_id": sid, "question": question}
        outputs = {"answer": answer, "entities": entities or {}}

        self.buffer.save_context(inputs, outputs)
        if self.summary:
            self.summary.save_context(inputs, outputs)

    async def maybe_summarize(self, session_id: str) -> None:
        if self.summary:
            await self.summary.maybe_compress(session_id)

    def forget_session(self, session_id: str) -> None:
        sid = session_id or "default"
        self.buffer.clear(sid)
        if self.summary:
            self.summary.clear(sid)

    def clear_all(self) -> None:
        """清空所有记忆（保留后端 SQLite 表结构）"""
        for sid in ["default"]:  # 简化：只清理默认 session
            self.forget_session(sid)
