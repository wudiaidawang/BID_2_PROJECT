"""LangChain ChatModel 适配器 — 将混元 LLMGenerator 适配为 LangChain BaseChatModel"""

from typing import Any, List, Optional, Iterator
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.callbacks import CallbackManagerForLLMRun

from config import settings


class HunyuanChatModel(BaseChatModel):
    """腾讯混元 ChatModel 适配器 — 桥接 LLMGenerator._call_llm 到 LangChain"""

    _llm: Any = None  # 注入的 LLMGenerator 引用

    class Config:
        arbitrary_types_allowed = True

    def set_llm(self, llm):
        """注入现有的 LLMGenerator 实例"""
        self._llm = llm

    @property
    def _llm_type(self) -> str:
        return "hunyuan"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs,
    ) -> ChatResult:
        """同步生成 — LangGraph 节点要求同步"""
        if not self._llm:
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content="LLM未初始化"))])

        msg_list = []
        for m in messages:
            if isinstance(m, SystemMessage):
                msg_list.append({"role": "system", "content": m.content})
            elif isinstance(m, AIMessage):
                msg_list.append({"role": "assistant", "content": m.content})
            else:
                msg_list.append({"role": "user", "content": m.content})

        try:
            import httpx
            resp = httpx.post(
                settings.llm_api_url,
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json={
                    "model": settings.llm_model,
                    "messages": msg_list,
                    "temperature": kwargs.get("temperature", settings.llm_temperature),
                    "max_tokens": kwargs.get("max_tokens", settings.llm_max_tokens),
                },
                timeout=settings.llm_timeout,
            )
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=f"API错误: {resp.status_code}"))])
        except Exception as e:
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=f"调用失败: {str(e)}"))])

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs,
    ) -> ChatResult:
        """异步生成 — 委托给同步版本（LangGraph 用 invoke 调同步，ainvoke 调异步）"""
        return self._generate(messages, stop, **kwargs)
