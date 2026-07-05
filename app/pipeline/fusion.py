"""
融合层 —— RRF 融合 + 加权融合

每个融合策略是独立类，只做"多路结果合并"这一件事。
不碰 ChromaDB，不关心 metadata schema。
"""

import re
import numpy as np
from typing import List, Dict, Tuple

from config import settings
from app.core.legal_entity_registry import detect_regulation_entity, detect_domain_entity
from app.pipeline.retrievers import chinese_tokenize, VectorRetriever, BM25Retriever


# ── 加权融合用的关键词 Boost 表 ──
TENDER_KEYWORDS = {
    "high": ["招标编号", "项目编号", "标段", "分包", "招标项目编号", "采购项目编号"],
    "medium": ["资质要求", "业绩要求", "注册资本", "建造师", "评标办法", "限价",
               "招标控制价", "保证金", "投标保证金", "资格条件", "资质等级"],
    "low": ["投标人", "招标人", "开标时间", "截止时间", "递交截止", "投标截止"],
}

REGULATION_KEYWORDS = {
    "high": ["民法典", "招标投标法", "政府采购法", "招标投标法实施条例"],
    "medium": ["管理办法", "指导意见", "通知", "规定"],
}

# ── 法规实体检测 —— 统一注册中心（legal_entity_registry.py）──

PENALTY_PATTERNS = [
    (r"^第[一二三四五六七八九十]+页$", -0.2),
    (r"^\s*目录\s*$", -0.2),
    (r"^[（(]?\d+[）)]?\s*$", -0.2),
    (r"(版权所有|All Rights Reserved)", -0.15),
]

KEYWORD_HEAVY_PATTERNS = [
    r"第\d+条", r"编号|标段|资质|建造师|注册资本",
    r"限价|保证金|资格条件",
]

SEMANTIC_HEAVY_PATTERNS = [
    r"什么是|是什么|定义|解释|含义|概念|意思",
    r"如何|怎么|怎样|步骤|流程|操作|办理",
    r"背景|原因|目的|意义|解读|分析",
    r"区别|不同|对比|比较",
    r"串通|围标|陪标|挂靠",
    r"投标人|招标人|评标",
]


class RRFFusion:
    """RRF (Reciprocal Rank Fusion) —— 纯函数融合"""

    @staticmethod
    def merge(results_a: List[Dict], results_b: List[Dict],
              k: int = 60) -> List[Dict]:
        """合并两路结果，按 RRF 得分降序"""
        scores: Dict[str, float] = {}
        result_map: Dict[str, Dict] = {}

        for rank, r in enumerate(results_a, 1):
            doc_id = r.get("id") or str(hash(r.get("text", "")))
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)
            result_map[doc_id] = r

        for rank, r in enumerate(results_b, 1):
            doc_id = r.get("id") or str(hash(r.get("text", "")))
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)
            if doc_id not in result_map:
                result_map[doc_id] = r

        sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        results = []
        for did, score in sorted_ids:
            if did in result_map:
                result_map[did]["score"] = score
                results.append(result_map[did])
        return results


class WeightedFusion:
    """加权融合 —— Min-Max 归一化 + 动态权重 + Boost/Penalty"""

    def __init__(self, vector_retriever: VectorRetriever = None,
                 bm25_retriever: BM25Retriever = None):
        self.vector = vector_retriever or VectorRetriever()
        self.bm25 = bm25_retriever or BM25Retriever()

    def _min_max_normalize(self, scores: List[float]) -> List[float]:
        if not scores:
            return []
        mn, mx = min(scores), max(scores)
        if mx == mn:
            return [0.5] * len(scores)
        return [(s - mn) / (mx - mn) for s in scores]

    def _detect_query_type(self, query: str) -> str:
        for pattern in KEYWORD_HEAVY_PATTERNS:
            if re.search(pattern, query):
                return "keyword_heavy"
        for pattern in SEMANTIC_HEAVY_PATTERNS:
            if re.search(pattern, query):
                return "semantic_heavy"
        return "balanced"

    def _detect_regulation_entity(self, query: str) -> bool:
        """检测 query 是否明确指向法规法条 → 委托统一注册中心"""
        return detect_regulation_entity(query)

    def _get_dynamic_weights(self, query: str) -> Tuple[float, float]:
        qtype = self._detect_query_type(query)
        has_reg = self._detect_regulation_entity(query)
        has_domain = detect_domain_entity(query)

        # 法规实体查询 → BM25 最重（法条号/法规名精确匹配 BM25 更强）
        if has_reg:
            return (0.80, 0.20)
        # 领域术语查询 → BM25 加重（采购方式/平台名/评标方法等关键字匹配更可靠）
        if has_domain:
            return (0.75, 0.25)
        if qtype == "keyword_heavy":
            return (0.75, 0.25)
        elif qtype == "semantic_heavy":
            return (0.60, 0.40)
        return (0.65, 0.35)

    def _compute_boost(self, text: str, metadata: Dict = None,
                       has_regulation: bool = False) -> float:
        boost = 0.0
        md = metadata or {}
        chunk_type = md.get("chunk_type", "")

        # 法律父子 chunk 基础加分
        if chunk_type in ("parent", "child", "pdf_law_child", "pdf_law_parent"):
            boost += 0.08
        if re.match(r"^第\d+条", text.strip()):
            boost += 0.05

        high_cnt = sum(1 for kw in TENDER_KEYWORDS["high"] if kw in text)
        med_cnt = sum(1 for kw in TENDER_KEYWORDS["medium"] if kw in text)
        low_cnt = sum(1 for kw in TENDER_KEYWORDS["low"] if kw in text)

        if high_cnt >= 1:
            boost += 0.06
        if med_cnt >= 2:
            boost += 0.04
        if low_cnt >= 2:
            boost += 0.03

        # 法规 Boost 仅当 query 含法规实体时启用
        boost_cap = 0.25
        if has_regulation:
            boost_cap = 0.35  # 法规查询放宽上限，让法条片段更容易突破阈值

            reg_cnt = sum(1 for kw in REGULATION_KEYWORDS["high"] if kw in text)
            if reg_cnt >= 1:
                boost += 0.05
            # 法条号精确匹配 → 强加分
            if re.search(r"第[一二三四五六七八九十百零\d]+条", text):
                boost += 0.10
            # law_child / law_parent 在法规查询时额外加权（补齐切分过碎的短板）
            if chunk_type in ("pdf_law_child", "pdf_law_parent"):
                boost += 0.05
            # 含 article_id 元数据的 chunk → 额外加权
            if md.get("article_id"):
                boost += 0.03

        return min(boost, boost_cap)

    def _compute_penalty(self, text: str) -> float:
        for pattern, val in PENALTY_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return max(val, -0.3)
        return 0.0

    def merge(self, query: str, collection: str,
              dense_results: List[Dict], bm25_results: List[Dict],
              top_k: int = None) -> List[Dict]:
        """加权融合两路结果"""
        k = top_k or settings.top_k

        if not dense_results:
            return bm25_results[:k]

        # Min-Max 归一化
        dense_scores = [r.get("score", 0) for r in dense_results]
        bm25_scores = [r["score"] for r in bm25_results]
        dense_norm = self._min_max_normalize(dense_scores)
        bm25_norm = self._min_max_normalize(bm25_scores)

        for i, r in enumerate(dense_results):
            r["norm_score"] = dense_norm[i] if i < len(dense_norm) else 0
        for i, r in enumerate(bm25_results):
            r["norm_score"] = bm25_norm[i] if i < len(bm25_norm) else 0

        # 动态权重 + 法规实体检测
        bm25_w, dense_w = self._get_dynamic_weights(query)
        query_type = self._detect_query_type(query)
        has_regulation = self._detect_regulation_entity(query)
        print(f"  [WeightedFusion] BM25={bm25_w}, Dense={dense_w} "
              f"(type: {query_type}, reg_entity: {has_regulation})")

        # 融合 + Boost/Penalty
        all_results: Dict[str, Dict] = {}

        for r in dense_results:
            doc_id = r.get("id") or str(hash(r.get("text", "")))
            base_score = dense_w * r.get("norm_score", 0)

            # 法规实体查询: Dense 的 law child/parent 降权 (BM25 更可靠)
            if has_regulation and r.get("metadata", {}).get("chunk_type") in ("pdf_law_child", "pdf_law_parent"):
                base_score *= 0.8
            elif r.get("metadata", {}).get("chunk_type") in ("parent", "child") \
                 and query_type == "semantic_heavy":
                base_score *= 0.5

            boost = self._compute_boost(r.get("text", ""), r.get("metadata", {}),
                                        has_regulation=has_regulation)
            penalty = self._compute_penalty(r.get("text", ""))
            final = base_score + boost + penalty

            if final < 0.1:
                continue
            all_results[doc_id] = {
                "id": doc_id, "text": r.get("text", ""),
                "metadata": r.get("metadata", {}), "score": final,
            }

        for r in bm25_results:
            doc_id = r.get("id") or str(hash(r.get("text", "")))
            base_score = bm25_w * r.get("norm_score", 0)

            if r.get("metadata", {}).get("chunk_type") in ("parent", "child") \
               and query_type == "semantic_heavy":
                base_score *= 0.5

            boost = self._compute_boost(r.get("text", ""), r.get("metadata", {}),
                                        has_regulation=has_regulation)
            penalty = self._compute_penalty(r.get("text", ""))
            final = base_score + boost + penalty

            if final < 0.1:
                continue

            if doc_id in all_results:
                if final > all_results[doc_id]["score"]:
                    all_results[doc_id]["score"] = final
            else:
                all_results[doc_id] = {
                    "id": doc_id, "text": r.get("text", ""),
                    "metadata": r.get("metadata", {}), "score": final,
                }

        sorted_results = sorted(all_results.values(),
                                key=lambda x: x["score"], reverse=True)
        print(f"  [WeightedFusion] {len(sorted_results)} candidates → Top-{min(k, len(sorted_results))}")
        return sorted_results[:k]
