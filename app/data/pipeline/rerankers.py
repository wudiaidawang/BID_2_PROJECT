"""
精排器 —— BgeReranker + NoopReranker
BgeReranker 继承 LangChain BaseDocumentCompressor，模块级单例管理。
"""

from typing import List, Sequence, Optional
from langchain_core.documents import BaseDocumentCompressor, Document

from config import settings


# 模块级缓存
_reranker_model: Optional["CrossEncoder"] = None  # noqa: F821
_load_attempted: bool = False


def _get_model():
    """模块级模型加载，避免 Pydantic singleton 冲突"""
    global _reranker_model, _load_attempted
    if _reranker_model is None and not _load_attempted:
        _load_attempted = True
        try:
            from sentence_transformers import CrossEncoder
            _reranker_model = CrossEncoder(
                settings.reranker_model,
                device="cpu",
                trust_remote_code=True
            )
            print(f"[BgeReranker] {settings.reranker_model} loaded (cpu)")
        except Exception as e:
            print(f"[BgeReranker] Failed to load: {e}")
            print("[BgeReranker] Will use NoopReranker (no rerank)")
            _reranker_model = None
    return _reranker_model


class NoopReranker:
    """空精排器"""

    def rerank(self, query: str, documents: List[str],
               top_k: int = 5) -> List[int]:
        return list(range(min(top_k, len(documents))))


class BgeReranker(BaseDocumentCompressor):
    """BGE-Reranker 精排器，继承 LangChain BaseDocumentCompressor"""

    def compress_documents(self, documents: Sequence[Document],
                           query: str) -> Sequence[Document]:
        """LangChain 标准接口"""
        model = _get_model()
        if model is None or len(documents) <= 1:
            return list(documents)

        try:
            doc_texts = [
                doc.page_content[:settings.reranker_max_input_length]
                for doc in documents
            ]
            pairs = [[query, t] for t in doc_texts]
            scores = model.predict(pairs, show_progress_bar=False)
            ranked = sorted(
                range(len(scores)), key=lambda i: scores[i], reverse=True
            )
            result = [documents[i] for i in ranked]
            for i, idx in enumerate(ranked):
                if hasattr(result[i], 'metadata') and result[i].metadata is not None:
                    result[i].metadata['rerank_score'] = float(scores[idx])
                    result[i].metadata['rerank_rank'] = i
            return result
        except Exception as e:
            print(f"[BgeReranker] compress_documents failed: {e}")
            return list(documents)

    def _get_model(self):
        """向后兼容: 供 Pipeline._do_rerank 调用"""
        return _get_model()

    def rerank(self, query: str, documents: List[str],
               top_k: int = 5) -> List[int]:
        """向后兼容: 传入文本列表，返回排序后的原始索引"""
        model = _get_model()
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
