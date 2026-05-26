# -*- coding: utf-8 -*-
"""混合检索器 - 向量检索 + BM25关键词检索 + RRF融合 + Reranker"""

import jieba
from typing import List, Dict
import numpy as np
from rank_bm25 import BM25Okapi

from config import settings
from app.storage.chroma_store import ChromaStore
from app.core.embedding import EmbeddingService
from app.core.fusion_weighted import HybridFusionV2, bm25_cache


def chinese_tokenize(text):
    """中文分词工具函数"""
    if not text:
        return []
    return [word for word in jieba.cut(str(text)) if word.strip()]


# domain synonym pairs for query expansion (bidding/legal)
SYNONYMS = {
    "投标人": ["供应商", "潜在投标人", "投标方"],
    "排斥": ["限制", "排除", "歧视"],
    "处罚": ["罚款", "处分", "惩戒"],
    "没收": ["不予退还", "不退还"],
    "禁止": ["不得", "不允许", "严禁"],
    "透露": ["泄露", "泄漏", "泄密"],
    "保证金": ["投标保证金", "履约保证金"],
    "撤回": ["撤销", "收回"],
    "分包": ["转包", "分包人"],
    "废标": ["流标", "无效投标"],
    "围标": ["串标", "串通投标"],
    "指定": ["标明", "要求", "限定"],
    "品牌": ["厂家", "制造商", "生产商"],
    "资质": ["资格", "资信"],
}


def expand_query(query: str) -> str:
    """对查询进行双向同义词扩展，提升 BM25 召回率"""
    expanded = query
    for term, synonyms in SYNONYMS.items():
        if term in query:
            for syn in synonyms:
                if syn not in expanded:
                    expanded += " " + syn
        else:
            for syn in synonyms:
                if syn in query:
                    if term not in expanded:
                        expanded += " " + term
                    break
    return expanded


class Reranker:
    """重排模型 - 使用本地缓存的 BAAI/bge-reranker-base"""

    _instance = None
    _model = None
    _load_attempted = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _get_model(self):
        if self._model is None and not self._load_attempted:
            self._load_attempted = True
            try:
                from sentence_transformers import CrossEncoder
                self._model = CrossEncoder(
                    "BAAI/bge-reranker-base",
                    device="cpu",
                    trust_remote_code=True
                )
                print("[Reranker] BAAI/bge-reranker-base loaded (cpu)")
            except Exception as e:
                print(f"[Reranker] Failed to load model: {e}")
                print("[Reranker] Will use RRF-only mode (no rerank)")
                self._model = None
        return self._model

    def rerank(self, query: str, documents: List[str], top_k: int = 5) -> List[int]:
        model = self._get_model()
        if model is None or len(documents) <= 1:
            return list(range(min(top_k, len(documents))))

        try:
            pairs = [[query, doc[:512]] for doc in documents]
            scores = model.predict(pairs, show_progress_bar=False)
            # higher score = more relevant
            ranked = sorted(
                range(len(scores)),
                key=lambda i: scores[i],
                reverse=True
            )
            return ranked[:top_k]
        except Exception as e:
            print(f"[Reranker] Rerank failed: {e}")
            return list(range(min(top_k, len(documents))))


class HybridRetriever:
    """
    混合检索器

    检索策略：
    1. 向量检索（Chroma）
    2. 关键词检索（BM25）
    3. RRF融合
    4. 返回结果
    """

    def __init__(self):
        self.chroma_store = ChromaStore()
        self.embedding_service = EmbeddingService()
        self.reranker = Reranker()
        from app.core.query_normalizer import QueryNormalizer
        self._normalizer = QueryNormalizer()

        # BM25索引缓存
        self._bm25_indices = {}
        self._bm25_texts = {}

        # 加权融合器（按配置启用）
        self._fusion_v2: HybridFusionV2 = None
        if settings.fusion_strategy in ("weighted", "smart"):
            self._fusion_v2 = HybridFusionV2(
                chroma_store=self.chroma_store,
                bm25_cache=bm25_cache
            )
            print(f"[Retriever] 融合策略: {settings.fusion_strategy} (动态权重 + Boost/Penalty)")
        else:
            print(f"[Retriever] 融合策略: RRF")

    def _get_bm25(self, collection: str, texts: List[str]):
        """获取或创建BM25索引（使用jieba分词）"""
        if collection not in self._bm25_indices:
            # 【学习点】：增加日志提示，因为几千条数据的分词在初次运行时会耗时几秒
            print(f"[BM25] Building index for '{collection}' ({len(texts)} documents)...")

            tokenized = [chinese_tokenize(text) for text in texts]
            self._bm25_indices[collection] = BM25Okapi(tokenized)
            self._bm25_texts[collection] = texts

            print(f"[BM25] Index for '{collection}' ready.")

        return self._bm25_indices[collection]

    def search(self, query: str, collection: str, top_k: int = 5) -> List[Dict]:
        """
        单库混合检索（保留向后兼容）
        """
        normalized = self._normalizer.normalize(query)
        return self._search_collection(normalized, collection, query, top_k)

    def _search_collection(self, normalized_query: str, collection: str,
                           original_query: str, top_k: int) -> List[Dict]:
        """对单个 collection 执行向量+BM25混合检索的内部方法"""
        # ── 加权融合路径 ──
        if self._fusion_v2 is not None:
            all_docs = self.chroma_store.get_all_documents(collection)
            texts = [doc["text"] for doc in all_docs] if all_docs else []
            fused = self._fusion_v2.search(
                query=normalized_query, collection=collection,
                top_k=top_k * 3, texts=texts, all_docs=all_docs
            )
            # Reranker 精排
            model = self.reranker._get_model()
            if model and len(fused) > 1:
                documents = [f["text"][:1000] for f in fused[:settings.reranker_candidate_pool]]
                rerank_indices = self.reranker.rerank(original_query, documents, top_k)
                fused = [fused[i] for i in rerank_indices if i < len(fused)]
            return fused[:top_k]

        # ── 经典 RRF 融合路径 ──
        vector_results = self.chroma_store.search(
            collection=collection,
            query=normalized_query,
            top_k=settings.vector_recall
        )

        if not vector_results:
            return []

        all_docs = self.chroma_store.get_all_documents(collection)
        if not all_docs:
            return vector_results[:top_k]

        texts = [doc["text"] for doc in all_docs]
        bm25 = self._get_bm25(collection, texts)
        expanded_query = expand_query(normalized_query)
        tokenized_query = chinese_tokenize(expanded_query)
        bm25_scores = bm25.get_scores(tokenized_query)

        top_bm25_indices = np.argsort(bm25_scores)[-settings.vector_recall:][::-1]

        keyword_results = []
        for idx in top_bm25_indices:
            if bm25_scores[idx] > 0:
                keyword_results.append({
                    "id": all_docs[idx]["id"],
                    "score": float(bm25_scores[idx]),
                    "data": all_docs[idx]["metadata"],
                    "text": all_docs[idx]["text"]
                })

        fused = self._rrf_fusion(vector_results, keyword_results, k=60)

        model = self.reranker._get_model()
        if model and len(fused) > 0:
            documents = [f["text"][:1000] for f in fused[:30]]
            rerank_indices = self.reranker.rerank(original_query, documents, top_k)
            fused = [fused[i] for i in rerank_indices if i < len(fused)]

        return fused[:top_k]

    def search_unified(self, query: str, top_k: int = 5) -> List[Dict]:
        """统一混合检索 —— 跨 regulations + bids 双库，RRF 合并 + Reranker 精排"""
        normalized = self._normalizer.normalize(query)

        # 分别对两个库做向量+BM25检索，每个库返回 top_k*3 候选
        all_candidates = []
        for collection in ["regulations", "bids"]:
            try:
                col_results = self._search_collection(
                    normalized, collection, query, top_k * 3
                )  # 每个库召回 3x 候选
                all_candidates.extend(col_results)
            except Exception:
                continue

        if not all_candidates:
            return []

        # 按内部 score 降序，去重
        all_candidates.sort(key=lambda x: x.get("score", 0), reverse=True)  # .sort 按分数降序排列
        seen = set()
        deduped = []
        for c in all_candidates:
            cid = c.get("id") or str(hash(c.get("text", "")))
            if cid not in seen:
                seen.add(cid)
                deduped.append(c)

        # Reranker 跨库精排 —— 由精排模型自行筛选最相关片段
        model = self.reranker._get_model()
        if model and len(deduped) > 1:
            documents = [d["text"][:1000] for d in deduped[:30]]
            rerank_indices = self.reranker.rerank(query, documents, top_k)
            deduped = [deduped[i] for i in rerank_indices if i < len(deduped)]

        return deduped[:top_k]

    def _rrf_fusion(self, results_a: List, results_b: List, k: int = 60) -> List:
        """RRF融合算法：根据排名分配权重，实现搜索结果互补"""
        scores = {}
        result_map = {}

        for rank, r in enumerate(results_a, 1):
            doc_id = r.get("id") or r.get("data", {}).get("id") or str(hash(r.get("text", "")))
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)
            result_map[doc_id] = r

        for rank, r in enumerate(results_b, 1):
            doc_id = r.get("id") or r.get("data", {}).get("id") or str(hash(r.get("text", "")))
            scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank)
            if doc_id not in result_map:
                result_map[doc_id] = r

        sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [result_map[doc_id] for doc_id, _ in sorted_ids if doc_id in result_map]
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "bids": self.chroma_store.get_count("bids"),
            "regulations": self.chroma_store.get_count("regulations"),
        }