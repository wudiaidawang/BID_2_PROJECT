"""Embedding 服务 — 优先调用远程服务器 M3E，失败时 fallback 到本地模型"""

from typing import List
from config import settings


class EmbeddingService:
    """Embedding 服务（单例模式）"""

    _instance = None
    _local_model = None
    _use_remote: bool = True

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _try_remote(self, texts: List[str]) -> List[List[float]]:
        from app.core.model_client import remote_embed
        return remote_embed(texts)

    @property
    def model(self):
        """兼容旧 API（BinaryRouter._warmup 等直接调用 .model.encode 的代码）"""
        return self._get_local_model()

    def _get_local_model(self):
        if self._local_model is None:
            from sentence_transformers import SentenceTransformer
            print(f"[Embedding] Loading local fallback: {settings.embedding_model}")
            self._local_model = SentenceTransformer(settings.embedding_model)
        return self._local_model

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if self._use_remote:
            try:
                result = self._try_remote(texts)
                return result
            except Exception as e:
                print(f"[Embedding] Remote failed: {e}, using local for this batch")

        vectors = self._get_local_model().encode(texts, show_progress_bar=False)
        return vectors.tolist()

    def embed_query(self, query: str) -> List[float]:
        return self.embed_batch([query])[0]
