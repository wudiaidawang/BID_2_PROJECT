"""加权融合检索器 — 动态权重 + Boost/Penalty评分 + 法条聚合"""
import re
import jieba
from typing import List, Dict, Tuple
from collections import Counter

from config import settings
from app.storage.chroma_store import ChromaStore
from app.core.embedding import EmbeddingService


class BM25Cache:
    """BM25 索引缓存（单例）"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._indices = {}
        return cls._instance

    def get_or_build(self, collection: str, texts: List[str]):
        from rank_bm25 import BM25Okapi
        if collection not in self._indices:
            print(f"[BM25Cache] Building index for '{collection}' ({len(texts)} docs)...")
            tokenized = [self._chinese_tokenize(t) for t in texts]
            self._indices[collection] = BM25Okapi(tokenized)
            print(f"[BM25Cache] Index ready.")
        return self._indices[collection]

    @staticmethod
    def _chinese_tokenize(text: str) -> List[str]:
        if not text:
            return []
        return [w for w in jieba.cut(str(text)) if w.strip()]

    def get_stats(self) -> dict:
        return {k: "cached" for k in self._indices}


# ── 招投标领域关键词 Boost 表 ──
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

PENALTY_PATTERNS = [
    (r"^第[一二三四五六七八九十]+页$", -0.2),
    (r"^\s*目录\s*$", -0.2),
    (r"^[（(]?\d+[）)]?\s*$", -0.2),
    (r"(版权所有|All Rights Reserved)", -0.15),
]

# ── 问题类型识别模式 ──
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


class HybridFusionV2:
    """加权融合检索器（队友方案移植） — Min-Max归一化 + 动态权重 + Boost + Penalty"""

    def __init__(self, chroma_store: ChromaStore = None, bm25_cache: BM25Cache = None):
        self.chroma_store = chroma_store or ChromaStore()
        self.bm25_cache = bm25_cache or BM25Cache()

    def _chinese_tokenize(self, text: str) -> List[str]:
        return BM25Cache._chinese_tokenize(text)

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

    def _get_dynamic_weights(self, query: str) -> Tuple[float, float]:
        qtype = self._detect_query_type(query)
        if qtype == "keyword_heavy":
            return (0.75, 0.25)
        elif qtype == "semantic_heavy":
            return (0.40, 0.60)
        return (0.65, 0.35)

    def _compute_boost(self, text: str, metadata: Dict = None) -> float:
        boost = 0.0
        md = metadata or {}

        if md.get("type") == "law_article":
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

        reg_cnt = sum(1 for kw in REGULATION_KEYWORDS["high"] if kw in text)
        if reg_cnt >= 1:
            boost += 0.05

        return min(boost, 0.2)

    def _compute_penalty(self, text: str) -> float:
        penalty = 0.0
        for pattern, val in PENALTY_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                penalty += val
                break
        return max(penalty, -0.3)

    def search(self, query: str, collection: str, top_k: int = 5,
               texts: List[str] = None, all_docs: List[Dict] = None) -> List[Dict]:
        """加权融合检索"""

        # Dense 召回
        dense_raw = self.chroma_store.search(
            collection=collection, query=query, top_k=settings.vector_recall
        )
        if not dense_raw:
            return []

        # 如果没有传入 texts/docs，从 Chroma 获取
        if texts is None or all_docs is None:
            all_docs = self.chroma_store.get_all_documents(collection)
            if not all_docs:
                return dense_raw[:top_k]
            texts = [doc["text"] for doc in all_docs]

        # BM25 召回
        bm25 = self.bm25_cache.get_or_build(collection, texts)
        tokenized = self._chinese_tokenize(query)
        bm25_scores_raw = bm25.get_scores(tokenized)

        import numpy as np
        top_bm25_indices = np.argsort(bm25_scores_raw)[-settings.vector_recall:][::-1]

        bm25_raw = []
        for idx in top_bm25_indices:
            if bm25_scores_raw[idx] > 0:
                bm25_raw.append({
                    "id": all_docs[idx]["id"],
                    "score": float(bm25_scores_raw[idx]),
                    "data": all_docs[idx]["metadata"],
                    "text": all_docs[idx]["text"],
                })

        # Min-Max 归一化
        dense_scores = [r.get("score", 0) for r in dense_raw]
        bm25_scores = [r["score"] for r in bm25_raw]
        dense_norm = self._min_max_normalize(dense_scores)
        bm25_norm = self._min_max_normalize(bm25_scores)

        for i, r in enumerate(dense_raw):
            r["norm_score"] = dense_norm[i] if i < len(dense_norm) else 0
        for i, r in enumerate(bm25_raw):
            r["norm_score"] = bm25_norm[i] if i < len(bm25_norm) else 0

        # 动态权重
        bm25_w, dense_w = self._get_dynamic_weights(query)
        query_type = self._detect_query_type(query)
        print(f"  [Fusion] 动态权重: BM25={bm25_w}, Dense={dense_w} (类型: {query_type})")

        # 融合 + Boost/Penalty
        all_results = {}

        for r in dense_raw:
            doc_id = r.get("id") or hash(r.get("text", ""))
            base_score = dense_w * r.get("norm_score", 0)

            is_law = r.get("data", {}).get("type") == "law_article"
            if is_law and query_type == "semantic_heavy":
                base_score *= 0.5

            boost = self._compute_boost(r.get("text", ""), r.get("data", {}))
            penalty = self._compute_penalty(r.get("text", ""))
            final = base_score + boost + penalty

            if final < 0.1:
                continue
            all_results[doc_id] = {
                "id": doc_id, "text": r.get("text", ""),
                "data": r.get("data", {}), "score": final,
                "source": "dense",
            }

        for r in bm25_raw:
            doc_id = r.get("id") or hash(r.get("text", ""))
            base_score = bm25_w * r.get("norm_score", 0)

            is_law = r.get("data", {}).get("type") == "law_article"
            if is_law and query_type == "semantic_heavy":
                base_score *= 0.5

            boost = self._compute_boost(r.get("text", ""), r.get("data", {}))
            penalty = self._compute_penalty(r.get("text", ""))
            final = base_score + boost + penalty

            if final < 0.1:
                continue

            if doc_id in all_results:
                existing = all_results[doc_id]
                if final > existing["score"]:
                    existing["score"] = final
                    existing["source"] = "both"
            else:
                all_results[doc_id] = {
                    "id": doc_id, "text": r.get("text", ""),
                    "data": r.get("data", {}), "score": final,
                    "source": "bm25",
                }

        sorted_results = sorted(all_results.values(), key=lambda x: x["score"], reverse=True)
        print(f"  [Fusion] 加权融合: {len(sorted_results)} 条 → Top-{min(top_k, len(sorted_results))}")

        return sorted_results[:top_k]


# 全局单例
bm25_cache = BM25Cache()
