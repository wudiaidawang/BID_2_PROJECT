# -*- coding: utf-8 -*-
"""API路由 - 修正路由逻辑版"""

import time
from fastapi import APIRouter, Request

from app.api.schemas import AskRequest, AskResponse, SourceInfo, HealthResponse
from app.core.session_manager import SessionManager
from config import settings

from app.core.sql_engine import SQLEngine
sql_engine = SQLEngine()
router = APIRouter(prefix="/api/v1", tags=["rag"])
session_manager = SessionManager()


@router.post("/ask", response_model=AskResponse)
async def ask(request: Request, req: AskRequest):
    """问答接口"""
    start_time = time.time()

    # 1. 会话管理
    session_id, is_new = await session_manager.get_or_create_session(req.session_id)
    history = await session_manager.get_history(session_id, last_n=settings.max_history)

    # 【学习点】：先用原始问题判断意图，防止 LLM 重写把“一共”这种关键词改掉
    route = request.app.state.router.route(req.question)

    # 获取重写后的问题（仅用于检索和生成）
    rewritten_question = await session_manager.rewrite_query_with_context(
        session_id, req.question
    )

    results = []

    # 2. 模式切换
    if route.get("method") == "sql":
        print(f"📊 [SQL模式] 拦截到统计需求: {req.question}")
        # 执行 SQL 查询
        sql, db_results = sql_engine.execute_query(req.question) # 建议这里也用原话

        # 包装成 LLM 能理解的上下文
        results = [{
            "text": f"系统数据库实时统计结果：{db_results}",
            "score": 1.0,
            "data": {
                "title": "数据库精准统计",
                "source": "sql",
                "project_name": "系统统计",
                "winner": "N/A",
                "winner_amount": 0.0
            }
        }]
    else:
        print(f"🔎 [RAG模式] 正在检索知识库: {rewritten_question}")
        # 走原有的混合检索
        results = request.app.state.retriever.search(
            query=rewritten_question,
            collection=route["collection"],
            top_k=req.top_k
        )

    # 3. LLM生成（将统计结果或检索结果喂给 LLM）
    answer = await request.app.state.generator.generate_with_history(
        query=req.question, # 用原话问，效果更直接
        context=results,
        collection=route["collection"],
        history=history
    )

    # 4. 提取实体 & 保存会话
    entities = await session_manager.extract_entities(rewritten_question, answer, results)
    await session_manager.add_turn(session_id, req.question, answer, entities)

    # 5. 构建返回 Source 列表
    sources = []
    for r in results[:req.top_k]:
        data = r.get("data", {})
        # 处理金额类型转换
        raw_amount = data.get("winner_amount") or data.get("amount") or 0.0
        try:
            clean_amount = float(raw_amount)
        except (ValueError, TypeError):
            clean_amount = 0.0

        sources.append(SourceInfo(
            title=str(data.get("title") or data.get("项目名称") or "查询结果"),
            project_name=str(data.get("project_name", data.get("项目名称", ""))),
            winner=str(data.get("winner", data.get("中标人", ""))),
            winner_amount=clean_amount,
            content_preview=str(r.get("text", ""))[:200],
            source_type=str(route.get("collection", "bids")),
            score=float(r.get("score", 0))
        ))

    return AskResponse(
        answer=answer,
        sources=sources,
        processing_time=time.time() - start_time,
        session_id=session_id
    )

@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    await session_manager.delete_session(session_id)
    return {"status": "deleted", "session_id": session_id}


@router.get("/health", response_model=HealthResponse)
async def health(request: Request):
    """健康检查"""
    return HealthResponse(
        status="ok",
        collections=request.app.state.retriever.get_stats(),
        embedding_model=settings.embedding_model
    )