# -*- coding: utf-8 -*-
"""口语化查询归一化 — 委托给统一 QueryRewriter（保持向后兼容）"""

from app.core.query_rewriter import query_rewriter


class QueryNormalizer:
    """口语化查询归一化（兼容旧接口，内部委托给 QueryRewriter）"""

    def __init__(self, dict_path: str = None):
        # dict_path 保留用于兼容，实际映射由 QueryRewriter 统一管理
        self._rewriter = query_rewriter

    def normalize(self, query: str) -> str:
        """归一化查询（委托给统一改写管道）"""
        return self._rewriter.rewrite(query)
