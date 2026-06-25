"""
独立检索器 —— VectorRetriever + BM25Retriever

每个检索器只做一件事：给定 query，返回 List[Dict]。
不知道 fusion/expand/rerank 的存在。
"""

import jieba
import numpy as np
from typing import List, Dict, Optional
from rank_bm25 import BM25Okapi

from app.storage import get_vector_store
from app.schema.metadata import normalize_chunks
from config import settings


def chinese_tokenize(text: str) -> List[str]:
    """jieba 中文分词"""
    if not text:
        return []
    return [w for w in jieba.cut(str(text)) if w.strip()]


class VectorRetriever:
    """纯向量检索 —— 自动适配 ChromaDB / Milvus 后端"""

    def __init__(self, store=None):
        self.store = store or get_vector_store()

    def search(self, query: str, collection: str, top_k: int = None,
               query_vec: List[float] = None) -> List[Dict]:
        """向量检索，返回统一 schema 的 chunk 列表"""
        k = top_k or settings.vector_recall
        results = self.store.search(collection, query, top_k=k, query_vec=query_vec)
        return normalize_chunks(results)

    def get_all(self, collection: str) -> List[Dict]:
        """获取集合全部文档（供 BM25 建索引）"""
        return self.store.get_all_documents(collection)


class ServerBM25Retriever:
    """服务端 BM25 关键词检索 —— 走 Milvus sparse_vector 字段，零客户端开销"""

    def __init__(self, store=None):
        self.store = store or get_vector_store()

    def search(self, query: str, collection: str, top_k: int = None) -> List[Dict]:
        k = top_k or settings.bm25_recall
        try:
            results = self.store.search_keyword(collection, query, top_k=k)
        except Exception:
            return []
        return normalize_chunks(results)


class BM25Retriever:
    """纯 BM25 关键词检索 —— 管理索引缓存"""

    def __init__(self):
        self._indices: Dict[str, BM25Okapi] = {}
        self._texts: Dict[str, List[str]] = {}

    def build_index(self, collection: str, documents: List[Dict]):
        """为 collection 构建 BM25 索引 —— 使用 retrieval_text"""
        texts = [d.get("retrieval_text", d.get("text", "")) for d in documents]
        if not texts:
            return
        tokenized = [chinese_tokenize(t) for t in texts]
        self._indices[collection] = BM25Okapi(tokenized)
        self._texts[collection] = texts
        print(f"[BM25Retriever] Index for '{collection}': {len(texts)} docs")

    def search(self, query: str, collection: str, documents: List[Dict],
               top_k: int = None) -> List[Dict]:
        """BM25 检索，返回统一 schema 的 chunk 列表"""
        k = top_k or settings.bm25_recall

        # 确保索引存在
        if collection not in self._indices:
            self.build_index(collection, documents)

        idx = self._indices.get(collection)
        if idx is None:
            return []

        tokenized = chinese_tokenize(query)
        scores = idx.get_scores(tokenized)
        top_indices = np.argsort(scores)[-k:][::-1]

        results = []
        for i in top_indices:
            if scores[i] > 0 and i < len(documents):
                doc = documents[i]
                results.append({
                    "id": doc.get("id", ""),
                    "text": doc.get("text", ""),
                    "metadata": doc.get("metadata", {}),
                    "score": float(scores[i]),
                })

        return normalize_chunks(results)

    def has_index(self, collection: str) -> bool:
        return collection in self._indices
