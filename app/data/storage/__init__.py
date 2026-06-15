"""存储层 — 向量库工厂"""

from config import settings


def get_vector_store():
    """根据 config 返回 ChromaStore 或 MilvusStore"""
    backend = settings.vector_store_backend
    if backend == "milvus":
        from app.data.storage.milvus_store import MilvusStore
        return MilvusStore()
    else:
        from app.data.storage.chroma_store import ChromaStore
        return ChromaStore()


def get_vector_store_class():
    """返回当前使用的 Store 类"""
    backend = settings.vector_store_backend
    if backend == "milvus":
        from app.data.storage.milvus_store import MilvusStore
        return MilvusStore
    else:
        from app.data.storage.chroma_store import ChromaStore
        return ChromaStore
