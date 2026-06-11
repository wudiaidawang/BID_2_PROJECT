"""
检索器 —— VectorRetriever + BM25Retriever，底层 LangChain 驱动
"""

import jieba
from typing import List, Dict
from langchain_community.retrievers import BM25Retriever as LCBm25Retriever
from langchain_core.documents import Document

from app.storage.chroma_store import ChromaStore
from app.schema.metadata import normalize_chunks
from config import settings


def chinese_tokenize(text: str) -> List[str]:
    """jieba 中文分词"""
    if not text:
        return []
    return [w for w in jieba.cut(str(text)) if w.strip()]


class VectorRetriever:
    """向量检索 —— 封装 langchain_chroma.Chroma 查询"""

    def __init__(self, chroma_store: ChromaStore = None):
        self.store = chroma_store or ChromaStore()

    def search(self, query: str, collection: str, top_k: int = None) -> List[Dict]:
        k = top_k or settings.vector_recall
        results = self.store.search(collection, query, top_k=k)
        return normalize_chunks(results)

    def get_all(self, collection: str) -> List[Dict]:
        return self.store.get_all_documents(collection)


class BM25Retriever:
    """BM25 关键词检索 —— 底层使用 langchain_community.retrievers.BM25Retriever"""

    def __init__(self):
        self._indices: Dict[str, LCBm25Retriever] = {}
        self._documents: Dict[str, List[Document]] = {}

    def build_index(self, collection: str, documents: List[Dict]):
        """为 collection 构建 langchain BM25 索引"""
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

    def search(self, query: str, collection: str, documents: List[Dict],
               top_k: int = None) -> List[Dict]:
        k = top_k or settings.bm25_recall

        if collection not in self._indices:
            self.build_index(collection, documents)

        lc_retriever = self._indices.get(collection)
        if lc_retriever is None:
            return []

        # 临时修改 k 值
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

    def has_index(self, collection: str) -> bool:
        return collection in self._indices
