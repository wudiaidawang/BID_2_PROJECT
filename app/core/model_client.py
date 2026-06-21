"""
远程模型服务客户端
调用服务器上的 M3E (embedding) 和 BGE-Reranker (rerank) HTTP API
"""

import httpx
from typing import List


def _get_server_url() -> str:
    from config import settings
    return getattr(settings, "model_service_url", "http://127.0.0.1:8210")


def remote_embed(texts: List[str], timeout: int = 60) -> List[List[float]]:
    """调用服务器 embedding"""
    url = f"{_get_server_url()}/embed"
    resp = httpx.post(url, json={"texts": texts}, timeout=timeout)
    resp.raise_for_status()
    return resp.json()["embeddings"]


def _get_reranker_url() -> str:
    from config import settings
    return getattr(settings, "reranker_service_url", "http://127.0.0.1:8001")


def remote_rerank(query: str, documents: List[str],
                  top_k: int = 5, timeout: int = 30) -> List[dict]:
    """调用服务器 reranker (8001)，返回兼容旧格式: [{"index": int, "score": float}, ...]"""
    url = f"{_get_reranker_url()}/rerank"
    resp = httpx.post(url, json={
        "query": query,
        "candidates": [{"content": d} for d in documents],
        "top_k": top_k,
    }, timeout=timeout)
    resp.raise_for_status()
    raw = resp.json()["results"]
    # API 返回结果按 score 降序排列，需通过 content 匹配回原始 documents 的索引
    content_to_idx = {d: i for i, d in enumerate(documents)}
    return [{"index": content_to_idx.get(r.get("content", ""), i),
             "score": r.get("rerank_score", r.get("score", 0))}
            for i, r in enumerate(raw)]
