"""
检索器 —— VectorRetriever + BM25Retriever，底层支持 ChromaDB / Milvus
"""

import jieba
from typing import List, Dict, Optional
from langchain_community.retrievers import BM25Retriever as LCBm25Retriever
from langchain_core.documents import Document

from app.data.schema.metadata import normalize_chunks
from config import settings


def chinese_tokenize(text: str) -> List[str]:
    """jieba 中文分词"""
    if not text:
        return []
    return [w for w in jieba.cut(str(text)) if w.strip()]


class VectorRetriever:
    """向量检索 —— 封装 ChromaDB / Milvus 查询"""

    def __init__(self, store=None):
        if store is not None:
            self.store = store
        else:
            from app.data.storage import get_vector_store
            self.store = get_vector_store()

    def search(self, query: str, collection: str, top_k: int = None) -> List[Dict]:
        k = top_k or settings.vector_recall
        results = self.store.search(collection, query, top_k=k)
        return normalize_chunks(results)

    def get_all(self, collection: str) -> List[Dict]:
        return self.store.get_all_documents(collection)


class BM25Retriever:
    """BM25 关键词检索 —— ChromaDB 用 jieba+langchain，Milvus 用内置 BM25"""

    def __init__(self, store=None):
        if store is not None:
            self._store = store
        else:
            from app.data.storage import get_vector_store
            self._store = get_vector_store()
        self._backend = settings.vector_store_backend
        self._indices: Dict[str, LCBm25Retriever] = {}
        self._documents: Dict[str, List[Document]] = {}

    def build_index(self, collection: str, documents: List[Dict]):
        """为 collection 构建 BM25 索引（仅 Chroma 后端需要）"""
        if self._backend == "milvus":
            return  # Milvus 内置 BM25，无需本地索引
        docs = [
            Document(page_content=d.get("text", ""), metadata=d.get("metadata", {}),
                     id=d.get("id", ""))
            for d in documents
        ]
        if not docs:
            return
        self._indices[collection] = LCBm25Retriever.from_documents(
            docs, preprocess_func=chinese_tokenize,
            k=settings.bm25_recall,
        )
        self._documents[collection] = docs
        print(f"[BM25Retriever] Index for '{collection}': {len(docs)} docs (langchain)")

    def search(self, query: str, collection: str, documents: Optional[List[Dict]] = None,
               top_k: int = None) -> List[Dict]:
        k = top_k or settings.bm25_recall

        if self._backend == "milvus":
            return self._search_milvus(query, collection, k)

        # ChromaDB 后端：使用 langchain BM25
        if collection not in self._indices:
            if documents:
                self.build_index(collection, documents)
            else:
                return []

        lc_retriever = self._indices.get(collection)
        if lc_retriever is None:
            return []

        old_k = lc_retriever.k
        lc_retriever.k = k
        try:
            lc_docs = lc_retriever.invoke(query)
        finally:
            lc_retriever.k = old_k

        results = []
        for doc in lc_docs:
            score = doc.metadata.get("score", 0.0) if doc.metadata else 0.0
            results.append({
                "id": doc.id or "",
                "text": doc.page_content,
                "metadata": doc.metadata or {},
                "score": float(score),
            })
        return normalize_chunks(results)

    def _search_milvus(self, query: str, collection: str, top_k: int) -> List[Dict]:
        """通过 Milvus 内置 BM25 函数进行关键词搜索"""
        from app.data.storage.milvus_store import MilvusStore
        store = self._store if isinstance(self._store, MilvusStore) else MilvusStore()
        results = store.search_keyword(collection, query, top_k)
        return normalize_chunks(results)

    def has_index(self, collection: str) -> bool:
        if self._backend == "milvus":
            return True  # Milvus 始终可用
        return collection in self._indices
