"""
HybridRetriever —— 兼容层

内部委托给 SearchPipeline 5 阶段管线:
  preprocess → retrieve → fuse → expand → rerank

保留旧 API (search / search_unified / get_stats) 确保向后兼容。
"""

from typing import List, Dict

from app.data.pipeline.pipeline import SearchPipeline


class HybridRetriever:
    """
    混合检索器（兼容封装）。

    全部检索逻辑已迁移至 app.pipeline.SearchPipeline。
    此类仅保留旧 API 接口，内部委托给管线。
    """

    def __init__(self):
        self._pipeline = SearchPipeline()

    def search(self, query: str, collection: str, top_k: int = 5) -> List[Dict]:
        """单库混合检索（向后兼容，供 Agent 工具调用）"""
        return self._pipeline.search(query, collection, top_k)

    def search_unified(self, query: str, top_k: int = 5) -> List[Dict]:
        """统一跨库检索 —— regulations + bids 双库（向后兼容）"""
        return self._pipeline.search_unified(query, top_k)

    def get_stats(self) -> dict:
        """获取各库文档数"""
        return self._pipeline.get_stats()
