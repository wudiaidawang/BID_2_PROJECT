# -*- coding: utf-8 -*-
"""API路由 — 支持三种路由模式：binary / intent / planner"""

import time
from fastapi import APIRouter, Request

from app.api.schemas import AskRequest, AskResponse, SourceInfo, HealthResponse
from app.core.session_manager import SessionManager
from config import settings

from app.core.sql_engine import SQLEngine
sql_engine = SQLEngine()
router = APIRouter(prefix="/api/v1", tags=["rag"])
session_manager = SessionManager()


# ---------------------------------------------------------------------------
# POST /api/v1/ask — 核心问答入口
# ---------------------------------------------------------------------------

@router.post("/ask", response_model=AskResponse)
async def ask(request: Request, req: AskRequest):
    """问答接口 — 根据 router_mode 自动选择执行路径

    binary 模式: 3路投票判定 is_sql → SQL 路径或 RAG 路径
    intent 模式: LLM 意图分类 → SQL 或 RAG 路径
    planner 模式: LLM 规划步骤 → PlannerExecutor 执行 → 汇总答案
    """
    start_time = time.time()

    # 1. 会话管理
    session_id, is_new = await session_manager.get_or_create_session(req.session_id)
    history = await session_manager.get_history(session_id, last_n=settings.max_history)

    # 2. 路由判定
    route = await request.app.state.router.route(req.question)

    # 2.1 获取改写后的问题
    rewritten_question = await session_manager.rewrite_query_with_context(
        session_id, req.question
    )

    # ── Planner 模式 ────────────────────────────────────
    if route.get("mode") == "planner":
        return await _handle_planner(
            request, req, route, session_id, rewritten_question, history, start_time
        )

    # ── Binary / Intent 模式（原有逻辑）─────────────────
    return await _handle_binary(
        request, req, route, session_id, rewritten_question, history, start_time
    )


# ---------------------------------------------------------------------------
# Planner 执行路径
# ---------------------------------------------------------------------------

async def _handle_planner(
    request: Request,
    req: AskRequest,
    route: dict,
    session_id: str,
    rewritten_question: str,
    history: list,
    start_time: float,
) -> AskResponse:
    """Planner 模式: 计划 → 执行 → 汇总"""
    plan_dict = route.get("plan", {})
    executor = request.app.state.planner_executor

    if executor is None:
        # 降级: 没有 executor 时走普通 RAG
        print("[Planner] executor 未初始化，降级到统一检索")
        results = request.app.state.retriever.search_unified(
            query=rewritten_question, top_k=req.top_k
        )
        answer = await request.app.state.generator.generate_with_history(
            query=req.question, context=results, collection="unified", history=history
        )
    else:
        # 执行计划
        from app.agent.planner import PlannerExecutor
        state = await executor.execute(plan_dict, rewritten_question)
        answer = await executor.aggregate(state, rewritten_question)

        # 构建 results（从 state 提取，供 SourceInfo 和 entity 提取使用）
        results = _state_to_results(state)

    # 实体提取 & 保存会话
    entities = await session_manager.extract_entities(rewritten_question, answer, results)
    await session_manager.add_turn(session_id, req.question, answer, entities)

    # 构建 Source 列表
    sources = _build_sources(results, req.top_k)

    return AskResponse(
        answer=answer,
        sources=sources,
        processing_time=time.time() - start_time,
        session_id=session_id,
    )


# ---------------------------------------------------------------------------
# Binary / Intent 执行路径（原有逻辑）
# ---------------------------------------------------------------------------

async def _handle_binary(
    request: Request,
    req: AskRequest,
    route: dict,
    session_id: str,
    rewritten_question: str,
    history: list,
    start_time: float,
) -> AskResponse:
    """Binary/Intent 模式: is_sql 判定 → SQL 或 RAG 路径（带容错降级）"""
    results = []
    source_collection = "unified"

    if route.get("is_sql"):
        print(f"[SQL模式] 拦截到统计需求: {req.question}")

        # SQL 短路优化
        if route.get("sql_template"):
            print(f"[SQL短路] 模板匹配度={route.get('match_score', 0):.3f}")
            try:
                db_data = sql_engine._execute_local_sql(route["sql_template"])
            except Exception:
                db_data = [{"error": "SQL template execution failed"}]
        else:
            _, db_data = sql_engine.execute_query(req.question)

        # 容错降级
        sql_failed = (
            isinstance(db_data, list) and len(db_data) == 0
        ) or any("error" in str(r).lower() for r in (db_data or []))

        if sql_failed:
            print(f"[SQL降级] SQL 执行失败，转入统一混合检索")
            results = request.app.state.retriever.search_unified(
                query=rewritten_question, top_k=req.top_k
            )
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
                    "winner_amount": 0.0,
                },
            }]
            source_collection = "sql"
    else:
        print(f"[统一检索] 非SQL查询，跨库混合检索")
        results = request.app.state.retriever.search_unified(
            query=rewritten_question, top_k=req.top_k
        )

    # LLM 生成
    answer = await request.app.state.generator.generate_with_history(
        query=req.question,
        context=results,
        collection=source_collection,
        history=history,
    )

    # 实体提取 & 保存会话
    entities = await session_manager.extract_entities(rewritten_question, answer, results)
    await session_manager.add_turn(session_id, req.question, answer, entities)

    # 构建 Source 列表
    sources = _build_sources(results, req.top_k, source_collection)

    return AskResponse(
        answer=answer,
        sources=sources,
        processing_time=time.time() - start_time,
        session_id=session_id,
    )


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _state_to_results(state) -> list:
    """将 AgentState 的执行轨迹转换为 results 格式"""
    results = []
    for step in state.steps:
        if step.error or not step.observation:
            continue
        results.append({
            "text": step.observation,
            "score": 0.85,
            "data": {
                "title": f"步骤{step.step_num}: {step.action}",
                "source": step.tool_name or step.action,
                "project_name": "",
                "winner": "",
                "winner_amount": 0.0,
            },
            "metadata": {"tool": step.tool_name, "step": step.step_num},
        })
    return results


def _build_sources(results: list, top_k: int, collection: str = "unified") -> list:
    """构建 SourceInfo 列表"""
    sources = []
    for r in results[:top_k]:
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
            source_type=meta.get("source", collection),
            score=float(r.get("score", 0)),
        ))
    return sources


# ---------------------------------------------------------------------------
# 其他端点
# ---------------------------------------------------------------------------

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
        embedding_model=settings.embedding_model,
    )
