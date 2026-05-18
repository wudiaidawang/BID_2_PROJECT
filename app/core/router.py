# -*- coding: utf-8 -*-
"""意图路由器 - 增强版"""

import re
from typing import Dict, Any

class IntentRouter:
    """
    意图路由器
    优先级：SQL统计 > 法规查询 > 价格查询 > 招标查询（默认）
    """

    # 1. SQL 统计关键词：增加更多变体，防止漏网
    SQL_KEYWORDS = [
        r"一共", r"总共", r"多少条", r"总数", r"统计",
        r"数据量", r"平均", r"最高", r"最低", r"汇总", r"数量"
    ]

    # 2. 法规关键词
    REGULATION_KEYWORDS = [
        "招标法", "投标法", "采购法", "条例", "规定", "法律", "条款"
    ]

    def __init__(self):
        # 使用 | 拼接正则，注意 SQL 关键词使用更宽松的匹配
        self.sql_pattern = re.compile("|".join(self.SQL_KEYWORDS), re.IGNORECASE)
        self.reg_pattern = re.compile("|".join(self.REGULATION_KEYWORDS), re.IGNORECASE)

    def route(self, query: str) -> Dict[str, Any]:
        """路由决策逻辑"""

        # 移除空格和标点，防止干扰匹配
        clean_query = re.sub(r"[^\w]", "", query)

        print(f"DEBUG [Router]: 正在路由问题 -> {clean_query}")

        # --- 核心拦截逻辑 ---

        # 优先判断 SQL
        if self.sql_pattern.search(clean_query):
            print("[Router] 匹配到 SQL 模式")
            return {
                "intent": "statistics",
                "collection": "bids",
                "method": "sql"
            }

        # 其次判断法规
        if self.reg_pattern.search(clean_query):
            print("[Router] 匹配到法规模式")
            return {
                "intent": "regulations",
                "collection": "regulations",
                "method": "hybrid"
            }

        # 默认模式
        print("[Router] 默认 RAG 模式")
        return {
            "intent": "bids",
            "collection": "bids",
            "method": "hybrid"
        }
