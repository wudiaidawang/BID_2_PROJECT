"""
精排器 —— BgeReranker + NoopReranker

独立于检索和融合，只做"给定候选集，返回重排后的 top_k"。
"""

from typing import List

from config import settings


class NoopReranker:
    """空精排器 —— 不做重排，直接截断"""

    def rerank(self, query: str, documents: List[str],
               top_k: int = 5) -> List[int]:
        return list(range(min(top_k, len(documents))))


class BgeReranker:
    """BGE-Reranker 精排 —— 使用本地 BAAI/bge-reranker-base"""

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
                    settings.reranker_model,
                    device="cpu",
                    trust_remote_code=True
                )
                print(f"[BgeReranker] {settings.reranker_model} loaded (cpu)")
            except Exception as e:
                print(f"[BgeReranker] Failed to load: {e}")
                print("[BgeReranker] Will use NoopReranker (no rerank)")
                self._model = None
        return self._model

    def rerank(self, query: str, documents: List[str],
               top_k: int = 5) -> List[int]:
        """对 documents 重排，返回 top_k 个原始索引"""
        model = self._get_model()
        if model is None or len(documents) <= 1:
            return list(range(min(top_k, len(documents))))

        try:
            pairs = [[query, doc[:settings.reranker_max_input_length]]
                     for doc in documents]
            scores = model.predict(pairs, show_progress_bar=False)
            ranked = sorted(range(len(scores)),
                            key=lambda i: scores[i], reverse=True)
            return ranked[:top_k]
        except Exception as e:
            print(f"[BgeReranker] Rerank failed: {e}")
            return list(range(min(top_k, len(documents))))
