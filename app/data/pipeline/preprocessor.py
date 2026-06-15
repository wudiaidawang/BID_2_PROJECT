"""
查询预处理器 —— 归一化 + 同义词扩展

纯函数管线：str → str
不依赖 ChromaDB、LLM 或任何外部服务。
"""

import re
from typing import List, Dict

from app.data.query_rewriter import query_rewriter

# ── 招投标领域同义词对（用于 BM25 查询扩展）──
SYNONYMS: Dict[str, List[str]] = {
    "投标人": ["供应商", "潜在投标人", "投标方"],
    "排斥": ["限制", "排除", "歧视"],
    "处罚": ["罚款", "处分", "惩戒"],
    "没收": ["不予退还", "不退还"],
    "禁止": ["不得", "不允许", "严禁"],
    "透露": ["泄露", "泄漏", "泄密"],
    "保证金": ["投标保证金", "履约保证金"],
    "撤回": ["撤销", "收回"],
    "分包": ["转包", "分包人"],
    "废标": ["流标", "无效投标"],
    "围标": ["串标", "串通投标"],
    "指定": ["标明", "要求", "限定"],
    "品牌": ["厂家", "制造商", "生产商"],
    "资质": ["资格", "资信"],
}


class QueryPreprocessor:
    """查询预处理器 —— 归一化 + 同义词扩展"""

    def __init__(self, enable_synonym_expansion: bool = True):
        self.enable_synonyms = enable_synonym_expansion

    def process(self, query: str) -> str:
        """
        预处理管线：
        1. 口语→书面语（QueryRewriter 3层规则）
        2. 同义词扩展（BM25 召回增强）
        """
        if not query:
            return ""

        # Step 1: 归一化
        normalized = query_rewriter.rewrite(query)

        # Step 2: 同义词扩展
        if self.enable_synonyms:
            normalized = self._expand_synonyms(normalized)

        return normalized

    def _expand_synonyms(self, query: str) -> str:
        """双向同义词扩展，提升 BM25 召回率"""
        expanded = query
        for term, synonyms in SYNONYMS.items():
            if term in query:
                for syn in synonyms:
                    if syn not in expanded:
                        expanded += " " + syn
            else:
                for syn in synonyms:
                    if syn in query:
                        if term not in expanded:
                            expanded += " " + term
                        break
        return expanded


# 模块级快捷函数
_preprocessor = QueryPreprocessor()

def preprocess_query(query: str) -> str:
    return _preprocessor.process(query)
