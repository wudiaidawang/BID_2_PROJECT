"""Embedding服务 — LangChain HuggingFaceEmbeddings 封装"""

from typing import List
from langchain_huggingface import HuggingFaceEmbeddings

from config import settings


class EmbeddingService:
    """Embedding服务（单例模式），底层使用 LangChain HuggingFaceEmbeddings"""

    _instance = None
    _embeddings: HuggingFaceEmbeddings = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _get_embeddings(self) -> HuggingFaceEmbeddings:
        if self._embeddings is None:
            self._embeddings = HuggingFaceEmbeddings(
                model_name=settings.embedding_model,
                model_kwargs={"device": settings.embedding_device},
                encode_kwargs={"batch_size": settings.embedding_batch_size},
            )
            print(f"Loading embedding model (via HuggingFaceEmbeddings): {settings.embedding_model}")
        return self._embeddings

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """批量向量化"""
        return self._get_embeddings().embed_documents(texts)

    def embed_query(self, query: str) -> List[float]:
        """查询向量化"""
        return self._get_embeddings().embed_query(query)
