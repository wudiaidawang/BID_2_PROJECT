"""ContextResolver — 指代消解（Rule First, LLM Fallback）

流程:
  Question → 规则扫描（正则匹配指代词）
    ├─ 无指代 → 跳过，返回原文
    ├─ 候选实体=1 → 自动补全（从 Redis 历史提取）
    └─ 候选实体>1 → LLM 消歧（带候选列表）
                      必要时反问用户
"""

import re
import json
from typing import Dict, List, Optional, Tuple

from app.data.storage.redis_client import redis_client
from config import settings


# ── 指代词模式 ──
REFERENCE_PATTERNS = [
    (re.compile(r"(那个|这个)项目"), "project"),
    (re.compile(r"(那个|这个)公司|(那个|这个)企业|(那个|这个)供应商"), "company"),
    (re.compile(r"(那个|这个)标段|(那个|这个)包|(那个|这个)批次"), "bid_lot"),
    (re.compile(r"(该项目|此项目|本项目|该工程|此工程)"), "project"),
    (re.compile(r"(该公司|该企业|该供应商|此公司)"), "company"),
    (re.compile(r"(上述|以上|前述|前面提到)"), "ambiguous"),  # 需要 LLM
    (re.compile(r"它(们?)\s*(的|在|是|有|被)?"), "ambiguous"),  # 需要更多上下文
]


class ContextResolver:
    """指代消解 — Rule First, LLM Fallback"""

    def __init__(self, llm=None):
        self.llm = llm
        self.redis = redis_client

    async def resolve(self, session_id: str, question: str) -> dict:
        """消解指代，返回消解后的 context

        Returns:
            {
                "resolved_question": str,   # 消解后的问题
                "needs_clarify": bool,      # 是否需要反问用户
                "clarify_message": str,     # 反问消息
                "resolved_entities": list,  # 消解出的实体列表
                "method": str,              # "none" | "rule" | "llm"
            }
        """
        # Step 1: 规则检测指代词
        references = self._detect_references(question)
        if not references:
            return {
                "resolved_question": question,
                "needs_clarify": False,
                "clarify_message": "",
                "resolved_entities": [],
                "method": "none",
            }

        # Step 2: 从 Redis 历史中提取候选实体
        candidates = await self._get_candidate_entities(session_id)

        if not candidates:
            return self._default(question)

        # Step 3: 根据候选实体数量决定策略
        if len(candidates) == 1:
            # 单实体：自动补全
            resolved = self._auto_resolve(question, references, candidates)
            resolved["method"] = "rule"
            return resolved

        # Step 4: 多实体 → LLM 消歧
        if self.llm:
            return await self._llm_resolve(question, references, candidates)
        else:
            # 无 LLM → 用最近的一个
            resolved = self._auto_resolve(question, references, candidates[:1])
            resolved["method"] = "rule"
            return resolved

    # ── 内部方法 ──────────────────────────

    def _detect_references(self, question: str) -> list:
        """检测问题中的指代词"""
        found = []
        for pattern, ref_type in REFERENCE_PATTERNS:
            match = pattern.search(question)
            if match:
                found.append({
                    "text": match.group(0),
                    "type": ref_type,
                    "span": match.span(),
                })
        return found

    async def _get_candidate_entities(self, session_id: str) -> list:
        """从 Redis 历史获取候选实体"""
        meta_key = f"session_meta:{session_id}"
        try:
            data = await self.redis.get(meta_key)
            if data:
                meta = json.loads(data)
                return self._extract_entities_from_meta(meta)
        except Exception:
            pass

        # Fallback: 从 chat history 中提取
        return await self._extract_from_chat_history(session_id)

    def _extract_entities_from_meta(self, meta: dict) -> list:
        """从 session meta 中提取实体"""
        entities = []

        # 最近问题中可能包含的实体
        last_q = meta.get("last_question", "")
        last_a = meta.get("last_answer", "")
        last_entities = meta.get("last_entities", {})

        # 项目名
        project = last_entities.get("project_name", "")
        if project:
            entities.append({"name": project, "type": "project"})

        # 公司名
        winner = last_entities.get("winner", "")
        if winner and winner != project:
            entities.append({"name": winner, "type": "company"})

        # 从上次问答中正则提取补充
        combined = f"{last_q} {last_a}"
        projects = re.findall(r'【([^】]{2,30})】', combined)
        for p in projects:
            if p not in [e["name"] for e in entities]:
                entities.append({"name": p, "type": "project"})

        companies = re.findall(
            r'中标人[：:]\s*([^\s，,。]{2,20})', combined
        )
        for c in companies:
            if c not in [e["name"] for e in entities]:
                entities.append({"name": c, "type": "company"})

        return entities

    async def _extract_from_chat_history(self, session_id: str) -> list:
        """从 chat history 中提取实体（备用路径）"""
        from langchain_community.chat_message_histories import RedisChatMessageHistory
        try:
            history = RedisChatMessageHistory(
                session_id=session_id,
                url=f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}",
                key_prefix="chat:",
                ttl=settings.session_ttl,
            )
            messages = history.messages
            combined = "\n".join(
                m.content if hasattr(m, 'content') else str(m)
                for m in messages[-6:]  # 最近 3 轮
            )

            entities = []
            projects = re.findall(r'【([^】]{2,30})】', combined)
            for p in projects[:3]:
                entities.append({"name": p, "type": "project"})
            companies = re.findall(r'中标人[：:]\s*([^\s，,。]{2,20})', combined)
            for c in companies[:2]:
                if c not in [e["name"] for e in entities]:
                    entities.append({"name": c, "type": "company"})
            return entities
        except Exception:
            return []

    def _auto_resolve(self, question: str, references: list,
                      candidates: list) -> dict:
        """规则自动补全指代"""
        resolved = question
        used = []

        # 按指代在问题中的位置排序
        references.sort(key=lambda r: r["span"][0])

        for ref in references:
            ref_text = ref["text"]
            ref_type = ref["type"]

            if ref_type == "ambiguous":
                # 用最近实体
                if candidates:
                    resolved = resolved.replace(ref_text, candidates[0]["name"])
                    used.append(candidates[0])
                continue

            # 按类型匹配
            matching = [c for c in candidates if c["type"] == ref_type]
            entity = matching[0] if matching else (candidates[0] if candidates else None)

            if entity:
                resolved = resolved.replace(ref_text, entity["name"])
                if entity not in used:
                    used.append(entity)

        return {
            "resolved_question": resolved,
            "needs_clarify": False,
            "clarify_message": "",
            "resolved_entities": used,
        }

    async def _llm_resolve(self, question: str, references: list,
                           candidates: list) -> dict:
        """LLM 消歧"""
        ref_texts = [r["text"] for r in references]
        candidate_texts = "\n".join(
            f"- {c['name']} (类型: {c['type']})" for c in candidates
        )

        prompt = f"""用户在追问中使用了指代词：{ref_texts}

候选实体列表（来自历史对话）：
{candidate_texts}

用户当前问题：
{question}

请判断这些指代词分别指代哪个候选实体。
- 如果能确定，返回消解后的问题。
- 如果无法确定（多个候选都有可能），设置 needs_clarify=true 并给出反问消息。

按 JSON 格式输出：
{{"resolved_question": "消解后的问题", "needs_clarify": false, "clarify_message": ""}}"""

        try:
            result = await self.llm._call_llm(prompt)
            # 尝试解析 JSON
            json_match = re.search(r'\{[^}]+\}', result)
            if json_match:
                data = json.loads(json_match.group())
                return {
                    "resolved_question": data.get("resolved_question", question),
                    "needs_clarify": data.get("needs_clarify", False),
                    "clarify_message": data.get("clarify_message", ""),
                    "resolved_entities": [],
                    "method": "llm",
                }
        except Exception:
            pass

        # LLM 失败 → 规则兜底
        result = self._auto_resolve(question, references, candidates[:1])
        result["method"] = "rule"
        return result

    def _default(self, question: str) -> dict:
        return {
            "resolved_question": question,
            "needs_clarify": False,
            "clarify_message": "",
            "resolved_entities": [],
            "method": "none",
        }
