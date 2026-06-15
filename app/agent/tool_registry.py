"""ToolRouter — 三级路由（Rule → Embedding → LLM）+ Task 定义"""

import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from config import settings


# ═════════════════════════════════════════════════════════════
# Task 结构
# ═════════════════════════════════════════════════════════════

@dataclass
class Task:
    """业务任务 — TaskAnalysis 的产出单元"""
    task_id: str                          # "T1"
    goal: str                             # "统计工程类项目金额"
    depends_on: List[str] = field(default_factory=list)  # ["T1", "T2"]


# ═════════════════════════════════════════════════════════════
# ToolDef + 注册表
# ═════════════════════════════════════════════════════════════

@dataclass
class ToolDef:
    """工具定义"""
    name: str                             # "sql"
    display_name: str                     # "SQL统计查询"
    description: str                      # 给 Embedding+LLM 看
    keywords: List[str]                   # 给 Rule Router
    embedding: Optional[np.ndarray] = None  # 延迟加载


TOOL_REGISTRY: Dict[str, ToolDef] = {
    "sql": ToolDef(
        name="sql",
        display_name="SQL统计查询",
        description="查询结构化统计数据：金额、数量、排名、占比、趋势、平均值",
        keywords=["金额", "数量", "统计", "排名", "占比", "趋势", "多少", "最高", "最低",
                  "平均", "总共", "合计", "总计", "大于", "小于", "超过", "小于", "前",
                  "最多", "最少", "总和", "汇总", "查询", "筛选"],
    ),
    "rag": ToolDef(
        name="rag",
        display_name="RAG法规检索",
        description="检索法规条款、定义、处罚规定、资质要求、流程步骤",
        keywords=["规定", "条款", "定义", "罚则", "资质", "要求", "流程",
                  "什么是", "如何", "怎么", "条件", "标准", "法规", "法律",
                  "投标人", "招标人", "评标", "开标", "串通", "围标"],
    ),
    "tender": ToolDef(
        name="tender",
        display_name="招标公告查询",
        description="查询招标公告、中标结果、开标信息、项目详情",
        keywords=["招标", "中标", "开标", "公告", "投标", "项目名称", "中标人",
                  "中标金额", "发布"],
    ),
    "company": ToolDef(
        name="company",
        display_name="企业信息查询",
        description="查询企业资质、信用信息、中标历史、供应商画像",
        keywords=["企业", "公司", "供应商", "中标人", "信用", "资质", "注册",
                  "业绩", "能力"],
    ),
}


def _get_tool_embedding(store_index: dict, tool_key: str):
    """延迟加载tool embedding"""
    cached = store_index.get(f"tool_embed_{tool_key}")
    if cached is not None:
        return cached
    tool_def = TOOL_REGISTRY.get(tool_key)
    if not tool_def:
        return None
    from app.data.embedding import EmbeddingService
    emb = EmbeddingService().embed_query(tool_def.description)
    store_index[f"tool_embed_{tool_key}"] = emb
    return emb


# ═════════════════════════════════════════════════════════════
# ToolRouter — 三级路由
# ═════════════════════════════════════════════════════════════

class ToolRouter:
    """三级路由：Rule → Embedding → LLM

    用法:
        router = ToolRouter(llm=generator)
        tool, confidence = router.route(task)
    """

    def __init__(self, llm=None):
        self.llm = llm
        self._store_index: dict = {}  # tool embedding + task cache

    def route(self, task: Task) -> Tuple[str, float]:
        """返回 (tool_name, confidence)"""
        goal = task.goal

        # Level 1: Rule Router
        tool_name, confidence = self._rule_route(goal)
        if tool_name:
            print(f"[ToolRouter] Level1 Rule hit: {tool_name} (confidence={confidence:.2f})")
            return tool_name, confidence

        # Level 2: Embedding Router → Top-K
        candidates = self._embedding_route(goal, top_k=3)
        if not candidates:
            return "rag", 0.5

        # 只有一个候选，直接返回
        if len(candidates) == 1:
            print(f"[ToolRouter] Level2 Embedding single: {candidates[0][0]}")
            return candidates[0]

        # Level 3: LLM Select (仅对 Top-K)
        if self.llm and len(candidates) > 1:
            tool_name, confidence = self._llm_select(goal, candidates)
            print(f"[ToolRouter] Level3 LLM: {tool_name} (confidence={confidence:.2f})")
            return tool_name, confidence

        # Fallback: 取最高分
        return candidates[0]

    # ── Level 1: Rule ──────────────────────

    def _rule_route(self, goal: str) -> Tuple[Optional[str], float]:
        """关键词直接命中，未命中返回 (None, 0)"""
        best_tool = None
        best_count = 0

        for tool_key, tool_def in TOOL_REGISTRY.items():
            count = sum(1 for kw in tool_def.keywords if kw in goal)
            if count > best_count:
                best_count = count
                best_tool = tool_key

        if best_tool and best_count >= 2:
            confidence = min(0.95, 0.7 + 0.05 * best_count)
            return best_tool, confidence

        return None, 0.0

    # ── Level 2: Embedding ──────────────────

    def _embedding_route(self, goal: str, top_k: int = 3
                         ) -> List[Tuple[str, float]]:
        """Task embedding vs Tool description embedding → Top-K"""
        from app.data.embedding import EmbeddingService
        task_emb = EmbeddingService().embed_query(goal)

        scores = []
        for tool_key, tool_def in TOOL_REGISTRY.items():
            tool_emb = _get_tool_embedding(self._store_index, tool_key)
            if tool_emb is None:
                continue
            sim = self._cosine_sim(task_emb, tool_emb)
            # 关键词加分
            kw_bonus = sum(1 for kw in tool_def.keywords if kw in goal) * 0.03
            scores.append((tool_key, sim + kw_bonus))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    # ── Level 3: LLM ──────────────────────

    def _llm_select(self, goal: str, candidates: List[Tuple[str, float]]
                    ) -> Tuple[str, float]:
        """LLM 在 Top-K 候选中做最终选择（同步）"""
        candidate_desc = "\n".join(
            f"- {name}: {TOOL_REGISTRY[name].description}"
            for name, score in candidates
        )
        prompt = f"""用户任务目标：
{goal}

可用工具（候选）：
{candidate_desc}

请选择最适合完成该任务的工具。只输出工具名称，不要解释。"""

        try:
            import httpx
            import requests

            # 简化：同步 LLM 调用
            api_key = settings.llm_api_key
            api_url = settings.llm_api_url.rstrip('/')
            if not api_url.endswith("/chat/completions"):
                api_url = f"{api_url}/chat/completions"

            resp = requests.post(
                api_url,
                json={
                    "model": settings.llm_model,
                    "messages": [
                        {"role": "system", "content": "你是一个任务-工具匹配路由。只输出工具名称。"},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.0,
                    "max_tokens": 10,
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=10,
            )

            if resp.status_code == 200:
                body = resp.json()
                answer = body["choices"][0]["message"]["content"].strip().lower()
                # 匹配候选工具名
                for name, score in candidates:
                    if name in answer:
                        return name, 0.85
                return candidates[0][0], 0.7
        except Exception as e:
            print(f"[ToolRouter] LLM select failed: {e}")

        return candidates[0][0], 0.6

    # ── 工具函数 ──────────────────────────

    @staticmethod
    def _cosine_sim(a, b) -> float:
        a = np.array(a)
        b = np.array(b)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))
