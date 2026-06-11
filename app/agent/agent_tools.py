"""Agent 工具定义 — LangChain @tool 装饰器 + 工具注册表"""

from typing import List, Dict, Any
from langchain_core.tools import tool

from config import settings


# Module-level references (injected at startup)
_retriever = None
_llm = None


def set_tool_dependencies(retriever, llm=None):
    """在应用启动时注入 retriever 和 llm 实例"""
    global _retriever, _llm
    _retriever = retriever
    _llm = llm


@tool
def search_regulations(query: str) -> str:
    """语义检索招投标知识库（法规条文 + 招标项目案例）。
适用场景：问概念定义（什么是围标）、问处罚规定（串通投标罚款多少）、问流程步骤（如何开标）、问类似项目案例。
输入：query（自然语言问题）
输出：相关法规片段和项目案例"""
    if not query:
        return "错误：请提供检索关键词"

    results = _retriever.search_unified(query, top_k=settings.top_k)
    if not results:
        return f"未找到与「{query}」相关的信息"

    output_parts = []
    for i, r in enumerate(results[:settings.top_k], 1):
        text = r.get("text", "")[:500]
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
        output_parts.append(f"[{i}] 来源：{source}\n{text}")

    return "\n\n".join(output_parts)


@tool
def get_article(article_num: str, law_name: str = "") -> str:
    """精确查询招投标法规的特定条款。
适用场景：用户明确问到「第X条」的时候使用。
输入：article_num（条款号，如"33"），可选 law_name（法律名称）
输出：该条款的完整内容"""
    if not article_num:
        return "错误：请提供条款号"

    query = f"{law_name} 第{article_num}条" if law_name else f"第{article_num}条"
    results = _retriever.search(query, "regulations", top_k=5)

    if not results:
        return f"未找到第{article_num}条的相关内容"

    filtered = []
    for r in results:
        meta = r.get("metadata", {}) or r.get("data", {})
        rid = str(meta.get("article_id", ""))
        if rid == str(article_num):
            filtered.append(r)

    if not filtered:
        filtered = results[:3]

    output_parts = []
    for i, r in enumerate(filtered[:2], 1):
        text = r.get("parent_content") or r.get("text", "")[:800]
        meta = r.get("metadata", {}) or r.get("data", {})
        law = meta.get("law_name", meta.get("source", "未知"))
        art = meta.get("article", f"第{article_num}条")
        output_parts.append(f"[{i}] 来源：{law} {art}\n{text}")

    return "\n\n".join(output_parts)


@tool
def sql_query(query: str) -> str:
    """对招标数据库执行统计查询，返回数量、金额、排名等结构化数据。
适用场景：问"去年有多少项目"、"中标金额最高的是哪个"、"各省份项目数量排名"等统计类问题。
输入：query（自然语言统计问题）
输出：数据库查询结果"""
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


@tool
def summarize(query: str, chunks_text: str) -> str:
    """将多段检索结果归纳总结成结构化回答"""
    if not _llm:
        return chunks_text
    prompt = f"""基于以下检索结果回答问题。
用户问题：{query}
检索结果：{chunks_text[:3000]}
请给出结构化的答案，标注信息来源。如果信息不足以回答问题，请如实说明。"""
    return _llm._call_llm(prompt=prompt)


# 工具注册表
AGENT_TOOLS = [search_regulations, get_article, sql_query, summarize]

# 兼容旧代码的类引用
TOOL_CLASSES: Dict[str, Any] = {}
