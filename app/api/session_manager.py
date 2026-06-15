"""会话管理器 — LangChain RedisChatMessageHistory + 实体追踪"""

import re
import uuid
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage

from app.data.storage.redis_client import redis_client
from config import settings


class ChatHistory:
    """会话历史包装，提供 .messages 属性访问"""

    def __init__(self, messages: List = None):
        self.messages = messages or []


class SessionManager:
    """会话管理器 — 底层使用 LangChain RedisChatMessageHistory + 自定义实体层"""

    def __init__(self):
        self.redis = redis_client
        self.ttl = settings.session_ttl
        self.max_history = settings.max_history

    def _key_chat(self, session_id: str) -> str:
        return f"chat:{session_id}"

    def _key_meta(self, session_id: str) -> str:
        return f"session_meta:{session_id}"

    def _get_message_history(self, session_id: str) -> RedisChatMessageHistory:
        return RedisChatMessageHistory(
            session_id=session_id,
            url=f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}",
            key_prefix="chat:",
            ttl=self.ttl,
        )

    async def get_or_create_session(self, session_id: Optional[str] = None) -> Tuple[str, bool]:
        if session_id and await self.session_exists(session_id):
            return session_id, False
        new_id = f"session_{uuid.uuid4().hex[:16]}"
        return new_id, True

    async def session_exists(self, session_id: str) -> bool:
        key = self._key_chat(session_id)
        return await self.redis.exists(key)

    async def get_chat_history(self, session_id: str) -> ChatHistory:
        """获取 LangChain 消息历史，返回 ChatHistory 包装"""
        history = self._get_message_history(session_id)
        messages = history.messages
        return ChatHistory(messages)

    async def add_turn(self, session_id: str, question: str, answer: str,
                       entities: Dict = None):
        """追加一轮对话"""
        history = self._get_message_history(session_id)
        history.add_user_message(question)
        history.add_ai_message(answer)

        # 存储最新实体信息
        meta_key = self._key_meta(session_id)
        meta = {
            "last_question": question,
            "last_answer": answer,
            "last_entities": entities or {},
            "updated_at": datetime.now().isoformat(),
        }
        from app.data.storage.redis_client import redis_client as rc
        import json
        await rc.set(meta_key, json.dumps(meta, ensure_ascii=False), self.ttl)

    async def get_session(self, session_id: str) -> Optional[Dict]:
        meta_key = self._key_meta(session_id)
        data = await self.redis.get(meta_key)
        from json import loads
        return loads(data) if data else None

    async def get_history(self, session_id: str, last_n: int = 3) -> List[Dict]:
        """返回最近 N 轮对话，兼容格式"""
        history = self._get_message_history(session_id)
        messages = history.messages

        result = []
        for i in range(0, len(messages) - 1, 2):
            if i + 1 < len(messages):
                q_msg = messages[i]
                a_msg = messages[i + 1]
                result.append({
                    "question": q_msg.content if hasattr(q_msg, 'content') else str(q_msg),
                    "answer": a_msg.content if hasattr(a_msg, 'content') else str(a_msg),
                })

        return result[-last_n:] if result else []

    async def rewrite_query_with_context(self, session_id: str, query: str) -> str:
        session = await self.get_session(session_id)
        if not session:
            return query
        last_entities = session.get("last_entities", {})
        project_name = last_entities.get("project_name") or last_entities.get("title", "")
        if project_name:
            if "那个项目" in query:
                query = query.replace("那个项目", project_name)
            if "该项目" in query:
                query = query.replace("该项目", project_name)
            if "它" in query and len(query) < 20:
                query = query.replace("它", project_name)
        return query

    async def extract_entities(self, question: str, answer: str,
                               retrieved_context: List) -> Dict:
        entities = {}
        for ctx in retrieved_context[:1]:
            data = ctx.get("data", {})
            if data.get("project_name"):
                entities["project_name"] = data["project_name"]
            if data.get("winner"):
                entities["winner"] = data["winner"]
        match = re.search(r'【([^】]+)】', answer)
        if match and not entities.get("project_name"):
            entities["project_name"] = match.group(1)
        return entities

    async def delete_session(self, session_id: str):
        # 删除聊天历史
        chat_key = self._key_chat(session_id)
        await self.redis.delete(chat_key)
        # 删除元数据
        meta_key = self._key_meta(session_id)
        await self.redis.delete(meta_key)
