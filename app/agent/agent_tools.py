"""Agent 工具定义 — 4个工具（法规检索 + 法条查询 + SQL统计 + RAG总结）"""
from typing import List, Dict, Any, Callable
from config import settings


class BaseTool:
    """工具基类"""
    name: str = ""
    description: str = ""

    def __init__(self, retriever, llm=None):
        self.retriever = retriever
        self.llm = llm

    async def run(self, **kwargs) -> str:
        raise NotImplementedError


class SearchRegulationsTool(BaseTool):
    """语义检索法规工具"""
    name = "search_regulations"
    description = """语义检索招投标法规知识库。
适用场景：问概念定义（什么是围标）、问处罚规定（串通投标罚款多少）、问流程步骤（如何开标）。
输入：query（自然语言问题）
输出：相关法规片段（最多3条）"""

    async def run(self, query: str = "", **kwargs) -> str:
        if not query:
            return "错误：请提供检索关键词"

        top_k = settings.top_k
        results = self.retriever.search(query, "regulations", top_k=top_k)

        if not results:
            return f"未找到与「{query}」相关的法规信息"

        output_parts = []
        max_len = 500
        for i, r in enumerate(results[:top_k], 1):
            text = r.get("text", "")[:max_len]
            source = self._format_source(r)
            output_parts.append(f"[{i}] 来源：{source}\n{text}")

        return "\n\n".join(output_parts)

    def _format_source(self, chunk: Dict) -> str:
        data = chunk.get("data", {})
        doc_title = data.get("doc_title", "")
        article_num = data.get("article_num", "")
        if doc_title and doc_title != "unknown":
            clean = doc_title.replace("《", "").replace("》", "")
            if article_num and article_num not in ("unknown", "full"):
                return f"{clean} 第{article_num}条"
            return clean
        source = data.get("source", "未知来源")
        if article_num and article_num not in ("unknown", "full"):
            return f"{source} 第{article_num}条"
        return source


class GetArticleTool(BaseTool):
    """精确法条查询工具"""
    name = "get_article"
    description = """精确查询招投标法规的特定条款。
适用场景：用户明确问到「第X条」的时候使用。
输入：article_num（条款号，如"33"），可选 law_name（法律名称）
输出：该条款的完整内容"""

    async def run(self, article_num: str = "", law_name: str = "", **kwargs) -> str:
        if not article_num:
            return "错误：请提供条款号"

        results = self.retriever.search_article_exact(law_name, article_num)

        if not results:
            fallback_query = f"{law_name} 第{article_num}条" if law_name else f"第{article_num}条"
            results = self.retriever.search(fallback_query, "regulations", top_k=3)
            if not results:
                return f"未找到第{article_num}条的相关内容"

        output_parts = []
        for i, r in enumerate(results[:2], 1):
            text = r.get("text", "")[:800]
            data = r.get("data", {})
            doc = data.get("doc_title", data.get("source", "未知"))
            clean = doc.replace("《", "").replace("》", "")
            output_parts.append(f"[{i}] 来源：{clean} 第{article_num}条\n{text}")

        return "\n\n".join(output_parts)


class SQLQueryTool(BaseTool):
    """SQL 统计查询工具 — 你的 SQL Engine 封装"""
    name = "sql_query"
    description = """对招标数据库执行统计查询，返回数量、金额、排名等结构化数据。
适用场景：问"去年有多少项目"、"中标金额最高的是哪个"、"各省份项目数量排名"等统计类问题。
输入：query（自然语言统计问题）
输出：数据库查询结果"""

    async def run(self, query: str = "", **kwargs) -> str:
        if not query:
            return "错误：请提供统计查询问题"

        try:
            from app.core.sql_engine import SQLEngine
            engine = SQLEngine()
            sql, data = engine.execute_query(query)
            if data:
                return f"SQL查询: {sql}\n结果: {data}"
            return f"SQL查询: {sql}\n结果: 未查询到数据"
        except Exception as e:
            return f"SQL查询失败: {str(e)}"


class SummarizeTool(BaseTool):
    """多段检索结果归纳总结"""
    name = "summarize"
    description = "将多段检索结果归纳总结成结构化回答"

    async def run(self, query: str = "", chunks_text: str = "", **kwargs) -> str:
        if not self.llm:
            return chunks_text
        prompt = f"""基于以下检索结果回答问题。
用户问题：{query}
检索结果：{chunks_text[:3000]}
请给出结构化的答案，标注信息来源。如果信息不足以回答问题，请如实说明。"""
        return await self.llm.generate(prompt)


# ── 工具注册表 ──
TOOL_CLASSES: Dict[str, type] = {
    "search_regulations": SearchRegulationsTool,
    "get_article": GetArticleTool,
    "sql_query": SQLQueryTool,
    "summarize": SummarizeTool,
}
