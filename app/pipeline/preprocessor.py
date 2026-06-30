"""
查询预处理器 —— 归一化 + 同义词扩展

纯函数管线：str → str
不依赖 ChromaDB、LLM 或任何外部服务。
"""

import re
from typing import List, Dict

from app.core.query_rewriter import query_rewriter

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


# ── 定义类问题模式 —— 命中则跳过同义词扩展，避免"围标"被扩展为"串标"后跑偏 ──
DEFINITION_PATTERNS = [
    "是什么", "什么是", "的定义", "定义是",
    "什么意思", "指的是", "是指", "指的是什么",
    "概念", "含义", "如何理解",
]


class QueryPreprocessor:
    """查询预处理器 —— 归一化 + 同义词扩展"""

    def __init__(self, enable_synonym_expansion: bool = True):
        self.enable_synonyms = enable_synonym_expansion

    def process(self, query: str) -> str:
        """
        预处理管线（单路）：
        1. 口语→书面语（QueryRewriter 3层规则）
        2. 同义词扩展（BM25 召回增强）—— 定义类问题跳过
        """
        base, expanded = self.process_variants(query)
        return expanded or base

    def process_variants(self, query: str) -> tuple:
        """
        多路预处理：返回 (base_query, expanded_query_or_None)

        base: 仅口语规范化，不做同义词扩展
        expanded: base + 同义词追加（定义类跳过），None 表示与 base 相同无需第二路

        供 SearchPipeline 多路检索合并使用：
        - base 保证语义不漂移
        - expanded 补充同义词召回
        - 两路结果合并去重，Reranker 精排选出最优
        """
        if not query:
            return ("", None)

        # Step 1: 归一化（口语→书面语 + 法条号规范化）
        normalized = query_rewriter.rewrite(query)

        # Step 2: 生成扩展变体（仅追加同义词，不做替换）
        expanded = None
        if self.enable_synonyms and not self._is_definition_query(query):
            candidates = self._expand_synonyms(normalized)
            if candidates != normalized:
                expanded = candidates

        return (normalized, expanded)

    def _is_definition_query(self, query: str) -> bool:
        """检测是否为定义/概念解释类问题"""
        for pat in DEFINITION_PATTERNS:
            if pat in query:
                return True
        return False

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
