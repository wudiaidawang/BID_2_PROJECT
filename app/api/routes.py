# -*- coding: utf-8 -*-
"""API路由 —— 二分类网关 + SQL容错降级 + 统一混合检索"""

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
    """问答接口 —— 二分类网关 + SQL容错降级"""
    start_time = time.time()

    # 1. 会话管理
    session_id, is_new = await session_manager.get_or_create_session(req.session_id)
    history = await session_manager.get_history(session_id, last_n=settings.max_history)

    # 2. 二分类路由：is_sql 判定
    route = await request.app.state.router.route(req.question)  # .route 三边并行判定

    # 获取重写后的问题（用于检索和生成）
    rewritten_question = await session_manager.rewrite_query_with_context(
        session_id, req.question
    )

    results = []
    source_collection = "unified"  # 统一检索标识

    # 3. SQL 路径（带容错降级）
    if route.get("is_sql"):
        print(f"[SQL模式] 拦截到统计需求: {req.question}")

        # SQL 短路优化：若模板匹配度极高，直接复用绑定 SQL
        if route.get("sql_template"):
            print(f"[SQL短路] 模板匹配度={route.get('match_score', 0):.3f}，直接复用 SQL")
            try:
                db_data = sql_engine._execute_local_sql(route["sql_template"])
            except Exception:
                db_data = [{"error": "SQL template execution failed"}]
        else:
            _, db_data = sql_engine.execute_query(req.question)

        # 容错降级判断
        sql_failed = (
            isinstance(db_data, list) and len(db_data) == 0
        ) or any("error" in str(r).lower() for r in (db_data or []))

        if sql_failed:
            print(f"[SQL降级] SQL 执行失败或返回空数据，转入统一混合检索")
            results = request.app.state.retriever.search_unified(
                query=rewritten_question,
                top_k=req.top_k
            )  # .search_unified 跨 regulations+bids 双库混合检索
            source_collection = "unified"
        else:
            results = [{
                "text": f"系统数据库实时统计结果：{db_data}",
                "score": 1.0,
                "data": {
                    "title": "数据库精准统计",
                    "source": "sql",
                    "project_name": "系统统计",
                    "winner": "N/A",
                    "winner_amount": 0.0
                }
            }]
            source_collection = "sql"
    else:
        # 4. 非 SQL 路径：统一混合检索（法规+项目）
        print(f"[统一检索] 非SQL查询，跨库混合检索")
        results = request.app.state.retriever.search_unified(
            query=rewritten_question,
            top_k=req.top_k
        )  # .search_unified 跨 regulations+bids 双库混合检索

    # 5. LLM 生成
    answer = await request.app.state.generator.generate_with_history(
        query=req.question,
        context=results,
        collection=source_collection,
        history=history
    )

    # 6. 提取实体 & 保存会话
    entities = await session_manager.extract_entities(rewritten_question, answer, results)
    await session_manager.add_turn(session_id, req.question, answer, entities)

    # 7. 构建返回 Source 列表
    sources = []
    for r in results[:req.top_k]:
        meta = r.get("metadata", {}) or r.get("data", {})
        raw_amount = meta.get("winner_amount") or meta.get("amount") or 0.0
        try:
            clean_amount = float(raw_amount)
        except (ValueError, TypeError):
            clean_amount = 0.0

        sources.append(SourceInfo(
            title=str(meta.get("title") or meta.get("项目名称") or "查询结果"),
            project_name=str(meta.get("project_name", meta.get("项目名称", ""))),
            winner=str(meta.get("winner", meta.get("中标人", ""))),
            winner_amount=clean_amount,
            content_preview=str(r.get("text", ""))[:200],
            source_type=source_collection,
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
