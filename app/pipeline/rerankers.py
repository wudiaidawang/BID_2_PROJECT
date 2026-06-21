"""
精排器 —— BgeReranker + NoopReranker

远程优先（服务器 BGE-Reranker），失败 fallback 到本地模型。
"""

from typing import List

from config import settings


class NoopReranker:
    """空精排器 —— 不做重排，直接截断"""

    def rerank(self, query: str, documents: List[str],
               top_k: int = 5) -> List[int]:
        return list(range(min(top_k, len(documents))))


class BgeReranker:
    """BGE-Reranker 精排 —— 远程优先，本地 fallback"""

    _instance = None
    _model = None
    _load_attempted = False
    _use_remote: bool = True

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
                    device=settings.reranker_device if hasattr(settings, 'reranker_device') else "cpu",
                    trust_remote_code=True
                )
                print(f"[BgeReranker] Local {settings.reranker_model} loaded")
            except Exception as e:
                print(f"[BgeReranker] Failed to load local model: {e}")
                self._model = None
        return self._model

    def _try_remote_rerank(self, query: str, documents: List[str],
                           top_k: int) -> List[int]:
        from app.core.model_client import remote_rerank
        results = remote_rerank(query, documents, top_k)
        return [r["index"] for r in results if r.get("index") is not None]

    def rerank(self, query: str, documents: List[str],
               top_k: int = 5) -> List[int]:
        if len(documents) <= 1:
            return list(range(min(top_k, len(documents))))

        # 远程优先
        if self._use_remote:
            try:
                ranked = self._try_remote_rerank(query, documents, top_k)
                if ranked:
                    return ranked[:top_k]
            except Exception as e:
                print(f"[BgeReranker] Remote rerank failed: {e}, falling back to local")
                self._use_remote = False

        # 本地 fallback
        model = self._get_model()
        if model is None:
            return list(range(min(top_k, len(documents))))

        try:
            pairs = [[query, doc[:settings.reranker_max_input_length]]
                     for doc in documents]
            scores = model.predict(pairs, show_progress_bar=False)
            ranked = sorted(range(len(scores)),
                            key=lambda i: scores[i], reverse=True)
            return ranked[:top_k]
        except Exception as e:
            print(f"[BgeReranker] Local rerank failed: {e}")
            return list(range(min(top_k, len(documents))))
