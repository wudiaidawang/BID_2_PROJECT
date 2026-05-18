# -*- coding: utf-8 -*-
"""混合检索器 - 向量检索 + BM25关键词检索 + RRF融合 + Reranker"""

import jieba
from typing import List, Dict
import numpy as np
from rank_bm25 import BM25Okapi

from config import settings
from app.storage.chroma_store import ChromaStore
from app.core.embedding import EmbeddingService


def chinese_tokenize(text):
    """中文分词工具函数"""
    if not text:
        return []
    # 使用 jieba 进行分词，并过滤掉空字符
    return [word for word in jieba.cut(str(text)) if word.strip()]


class Reranker:
    """重排模型 - 已禁用以防止网络超时"""

    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _get_model(self):
        """
        【重要修改】：强制返回 None。
        原因：防止 BAAI/bge-reranker-base 模型在启动或调用时尝试连接 HuggingFace 导致死锁。
        """
        return None

    def rerank(self, query: str, documents: List[str], top_k: int = 5) -> List[int]:
        """
        由于模型已禁用，直接返回原始顺序的索引
        """
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

        # BM25索引缓存
        self._bm25_indices = {}
        self._bm25_texts = {}

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
        混合检索
        """
        # 1. 向量检索（召回数量由配置决定，通常为 50）
        vector_results = self.chroma_store.search(
            collection=collection,
            query=query,
            top_k=settings.vector_recall
        )

        if not vector_results:
            return []

        # 2. 获取所有文档用于构建/匹配 BM25
        all_docs = self.chroma_store.get_all_documents(collection)
        if not all_docs:
            return vector_results[:top_k]

        texts = [doc["text"] for doc in all_docs]
        bm25 = self._get_bm25(collection, texts)

        # 3. BM25关键词检索
        tokenized_query = chinese_tokenize(query)
        bm25_scores = bm25.get_scores(tokenized_query)

        # 获取得分最高的索引
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

        # 4. RRF融合（合并向量结果和关键词结果）
        fused = self._rrf_fusion(vector_results, keyword_results, k=60)

        # 5. Reranker精排（如果模型被禁用，这里会保持 fused 的顺序）
        model = self.reranker._get_model()
        if model and len(fused) > 0:
            documents = [f["text"][:500] for f in fused[:30]]
            rerank_indices = self.reranker.rerank(query, documents, top_k)
            fused = [fused[i] for i in rerank_indices if i < len(fused)]

        # 6. 返回最终 Top-K 结果
        return fused[:top_k]

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
            "prices": self.chroma_store.get_count("prices"),
        }