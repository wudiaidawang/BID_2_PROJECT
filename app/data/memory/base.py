"""Memory 抽象基类 — 仿 LangChain 的 BaseMemory 接口"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseMemory(ABC):
    """所有 memory 后端的抽象基类

    三个标准接口:
        load_memory_variables — 读取记忆，返回可注入 prompt 的文本
        save_context — 保存新一轮对话
        clear — 清除记忆
    """

    @abstractmethod
    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """从记忆加载变量，返回 {key: value} 字典

        Args:
            inputs: 调用方传入的上下文，可能含 question / session_id 等

        Returns:
            dict，如 {"history": "...", "summary": "..."}
        """

    @abstractmethod
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> None:
        """保存新一轮对话到记忆

        Args:
            inputs: {"question": str, "session_id": str}
            outputs: {"answer": str, "entities": dict}
        """

    @abstractmethod
    def clear(self, session_id: str = "") -> None:
        """清除指定会话的记忆"""
