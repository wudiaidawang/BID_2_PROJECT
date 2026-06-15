"""Agent 工具定义 — LangChain @tool 装饰器 + 闭包依赖注入

消除全局变量：所有工具通过 create_agent_tools() 工厂创建，依赖通过闭包注入。
"""

from typing import List

from langchain_core.tools import tool

from config import settings


def create_agent_tools(retriever, llm=None, sql_engine=None):
    """工厂函数 — 通过闭包注入所有依赖。

    两个工具覆盖全部数据源:
        rag_search — RAG 混合检索（法规条文 + 招标项目案例 + 法条精确查询）
        sql_search — SQL 统计查询（数量/金额/排名等结构化数据）
    """

    @tool
    def rag_search(query: str, collection: str = "unified") -> str:
        """RAG 混合检索 — 查询招投标知识库（法规条文 + 招标项目案例）。

适用场景:
  - 概念定义: "什么是围标串标"
  - 处罚规定: "串通投标罚款多少"
  - 流程步骤: "开标流程是怎样的"
  - 具体法条: "政府采购法第33条"
  - 项目案例: "四川省学校类项目有哪些"

参数:
  query: 自然语言查询（查法条时用 "法条关键词 第X条" 格式）
  collection: unified(全部) / regulations(仅法规) / bids(仅招标项目)，默认 unified"""
        if not query:
            return "错误：请提供检索关键词"

        if collection == "unified":
            results = retriever.search_unified(query, top_k=settings.top_k)
        else:
            results = retriever.search(query, collection, top_k=settings.top_k)

        if not results:
            return f"未找到与「{query}」相关的信息"

        output_parts = []
        for i, r in enumerate(results[:settings.top_k], 1):
            text = r.get("parent_content") or r.get("text", "")[:600]
            meta = r.get("metadata", {}) or r.get("data", {})
            law_name = meta.get("law_name", "")
            article = meta.get("article", "")
            article_id = meta.get("article_id", "")
            project_name = meta.get("项目名称", "")
            winner = meta.get("中标人", "")

            if law_name or article or article_id:
                clean = (law_name or "").replace("《", "").replace("》", "")
                if article:
                    source = f"[法规] {clean} {article}"
                elif article_id:
                    source = f"[法规] {clean} 第{article_id}条"
                else:
                    source = f"[法规] {clean}"
            elif project_name:
                source = f"[项目] {project_name}"
                if winner:
                    source += f" | 中标: {winner}"
            else:
                source = meta.get("source", "未知来源")
            output_parts.append(f"[{i}] {source}\n{text}")

        return "\n\n".join(output_parts)

    @tool
    def sql_search(query: str) -> str:
        """SQL 统计查询 — 对招标数据库执行聚合统计。

适用场景:
  - 数量统计: "2024年有多少项目"
  - 金额排名: "中标金额最高的10个项目"
  - 分组汇总: "各省份项目数量排名"
  - 条件筛选: "工程类项目的平均中标金额"

参数:
  query: 自然语言统计问题"""
        if not query:
            return "错误：请提供统计查询问题"
        if sql_engine is None:
            return "SQL引擎未初始化，无法执行统计查询"

        try:
            sql, data = sql_engine.execute_query(query)
            if data:
                return f"SQL: {sql}\n结果: {data}"
            return f"SQL: {sql}\n结果: 未查询到数据"
        except Exception as e:
            return f"SQL查询失败: {str(e)}"

    return [rag_search, sql_search]


# ============================================================================
# 兼容旧代码（planner.py / react_agent.py 为手写实现，不再使用但保留引用）
# ============================================================================

def set_tool_dependencies(retriever, llm=None):
    """已废弃 — 保留仅为兼容旧代码。新代码请使用 create_agent_tools()。"""
    pass


# 旧模块引用的空壳
AGENT_TOOLS: List = []
TOOL_CLASSES: dict = {}
BaseTool = None
