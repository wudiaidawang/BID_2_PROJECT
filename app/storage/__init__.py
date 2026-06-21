"""向量存储后端工厂"""

from config import settings


def get_vector_store():
    """根据 config 返回 ChromaStore 或 MilvusStore 实例"""
    backend = settings.vector_store_backend
    if backend == "milvus":
        from app.storage.milvus_store import MilvusStore
        return MilvusStore()
    else:
        from app.storage.chroma_store import ChromaStore
        return ChromaStore()
