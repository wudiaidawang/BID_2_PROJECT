"""MemoryManager — 统一协调所有 memory 后端"""

import os
from typing import Any, Dict, List, Optional

from app.core.memory.buffer import (
    ConversationBufferWindowMemory,
    ConversationSummaryMemory,
)
from app.core.memory.entity import EntityMemory


class MemoryManager:
    """记忆管理器 — 协调 buffer / summary / entity 三个后端

    用法:
        mm = MemoryManager(llm=generator, storage_dir="./memory_store")

        # 提问前
        ctx = mm.load_context(session_id, question)
        # ctx["full_context"] 可直接注入 generator prompt

        # 回答后
        mm.save_turn(session_id, question, answer, entities)
        # 自动触发: buffer 保存 + 实体提取 + 摘要压缩(异步)

        # 清理
        mm.forget_session(session_id)
    """

    def __init__(
        self,
        llm=None,
        storage_dir: str = "./memory_store",
        buffer_k: int = 5,
        summary_enabled: bool = True,
    ):
        self.llm = llm
        self._storage_dir = storage_dir

        self.buffer = ConversationBufferWindowMemory(
            k=buffer_k, storage_dir=storage_dir
        )
        self.summary = ConversationSummaryMemory(
            llm=llm, buffer_window=buffer_k, storage_dir=storage_dir
        ) if summary_enabled else None
        self.entity = EntityMemory(storage_dir=storage_dir)

    # ── 读: 提问前获取上下文 ────────────────────

    def load_context(self, session_id: str, question: str) -> Dict[str, str]:
        """获取可注入 LLM prompt 的记忆上下文

        Args:
            session_id: 会话 ID
            question: 用户当前问题

        Returns:
            {"history": ..., "summary": ..., "entities": ..., "full_context": ...}
        """
        sid = session_id or "default"
        inputs = {"session_id": sid, "question": question}

        history_vars = self.buffer.load_memory_variables(inputs)
        history = history_vars.get("history", "")

        summary = ""
        if self.summary:
            summary_vars = self.summary.load_memory_variables(inputs)
            summary = summary_vars.get("summary", "")

        entity_vars = self.entity.load_memory_variables(inputs)
        entities_text = entity_vars.get("entities", "")

        # 拼接完整上下文
        parts = []
        if summary:
            parts.append(summary)
        if history and history != "（无历史记录）":
            parts.append(history)
        full_context = "\n".join(parts)

        return {
            "history": history,
            "summary": summary,
            "entities": entities_text,
            "full_context": full_context,
        }

    # ── 写: 回答后保存 ────────────────────────

    def save_turn(
        self,
        session_id: str,
        question: str,
        answer: str,
        entities: Optional[Dict] = None,
    ) -> None:
        """保存一轮对话到所有后端

        Args:
            session_id: 会话 ID
            question: 用户问题
            answer: 系统回答
            entities: 提取的实体信息
        """
        sid = session_id or "default"
        inputs = {"session_id": sid, "question": question}
        outputs = {"answer": answer, "entities": entities or {}}

        # Buffer: 保存对话原文
        self.buffer.save_context(inputs, outputs)

        # Summary: 收集待压缩对话
        if self.summary:
            self.summary.save_context(inputs, outputs)

        # Entity: 提取并记住实体
        self.entity.save_context(inputs, outputs)

    async def maybe_summarize(self, session_id: str) -> None:
        """检查是否需要摘要压缩（在 save_turn 后调用）"""
        if self.summary:
            await self.summary.maybe_compress(session_id)

    # ── 清理 ──────────────────────────────────

    def forget_session(self, session_id: str) -> None:
        """删除指定会话的所有记忆"""
        sid = session_id or "default"
        self.buffer.clear(sid)
        if self.summary:
            self.summary.clear(sid)
        # Entity 不清除（跨 session 积累）

    def clear_all(self) -> None:
        """清空所有记忆（慎用）"""
        self.entity.clear()
        # 清理所有 session 目录
        import shutil
        try:
            shutil.rmtree(self._storage_dir)
        except FileNotFoundError:
            pass
