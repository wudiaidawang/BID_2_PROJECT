# -*- coding: utf-8 -*-
"""API路由 — 支持四种路由模式：binary / intent / planner / auto"""

import time
import os
import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

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

    binary  模式: 3路投票判定 is_sql → SQL 或 RAG
    intent  模式: LLM 意图分类 → SQL 或 RAG
    planner 模式: LLM 规划 → PlannerExecutor DAG 执行
    auto    模式: IntentRouter 判复杂度 → 简单直走 RAG/SQL, 复杂走 Planner DAG
    """
    start_time = time.time()

    # 1. 会话管理
    session_id, is_new = await session_manager.get_or_create_session(req.session_id)
    history = await session_manager.get_history(session_id, last_n=settings.max_history)

    # 1.2 Memory 上下文 — 从 memory 模块加载历史和实体
    memory = getattr(request.app.state, 'memory', None)
    memory_context = {}
    if memory:
        memory_context = memory.load_context(session_id, req.question)

    # 1.5 断点续跑检查 — 如果存在未完成的 checkpoint，尝试恢复
    if settings.checkpoint_enabled and not is_new:
        checkpoint_result = await _try_resume_checkpoint(
            request, session_id, start_time
        )
        if checkpoint_result is not None:
            return checkpoint_result

    # 2. 路由判定 (auto 模式需要 session 来做指代消解上下文)
    route = await request.app.state.router.route(
        req.question,
        session_id=session_id,
        session_manager=session_manager,
    )

    # 2.1 获取改写后的问题
    rewritten_question = await session_manager.rewrite_query_with_context(
        session_id, req.question
    )

    # ── 直接响应 (问候/致谢/无关) ──
    if route.get("mode") == "direct":
        return _handle_direct(
            req, route, session_id, start_time
        )

    # ── Planner 模式 (auto 的复杂问题 或 planner 模式) ──
    if route.get("mode") == "planner":
        return await _handle_planner(
            request, req, route, session_id, rewritten_question, history,
            memory_context, start_time
        )

    # ── 简单问题: auto / binary / intent 模式 ──
    return await _handle_binary(
        request, req, route, session_id, rewritten_question, history,
        memory_context, start_time
    )


# ---------------------------------------------------------------------------
# POST /api/v1/chat/stream — 流式问答（SSE/NDJSON）
# ---------------------------------------------------------------------------

@router.post("/chat/stream")
async def chat_stream(request: Request):
    """流式问答接口 — 逐 token 返回 NDJSON，适配 Streamlit 前端"""
    body = await request.json()
    session_id_in = body.get("session_id")
    user_message = (body.get("user_message") or body.get("question") or "").strip()
    if not user_message:
        async def _err():
            yield json.dumps({"type": "error", "content": "输入为空"}, ensure_ascii=False) + "\n"
        return StreamingResponse(_err(), media_type="application/x-ndjson")

    # 1. 会话管理
    session_id, is_new = await session_manager.get_or_create_session(session_id_in)
    history = await session_manager.get_history(session_id, last_n=settings.max_history)

    # 2. 查询改写
    rewritten = await session_manager.rewrite_query_with_context(session_id, user_message)

    # 3. 路由判定
    route = await request.app.state.router.route(
        rewritten, session_id=session_id, session_manager=session_manager
    )

    # 4. 获取检索器 & 生成器
    retriever = request.app.state.retriever
    generator = request.app.state.generator
    memory = getattr(request.app.state, 'memory', None)
    memory_ctx = ""
    if memory:
        mc = memory.load_context(session_id, rewritten)
        memory_ctx = mc.get("full_context", "")

    async def event_stream():
        full_answer = ""

        try:
            # ── 直接响应（问候/致谢） ──
            if route.get("mode") == "direct":
                answer = route.get("direct_answer", "您好！我是招投标智能助手，请问有什么可以帮您？")
                full_answer = answer
                yield json.dumps({"type": "assistant", "content": answer}, ensure_ascii=False) + "\n"

            # ── SQL 路径 ──
            elif route.get("is_sql"):
                print(f"[Stream SQL] 拦截统计需求: {user_message}")
                if route.get("sql_template"):
                    print(f"[Stream SQL] 模板匹配度={route.get('match_score', 0):.3f}")
                    db_data = sql_engine._execute_local_sql(route["sql_template"])
                else:
                    _, db_data = await sql_engine.execute_query(user_message)

                sql_failed = (
                    isinstance(db_data, list) and len(db_data) == 0
                ) or any("error" in str(r).lower() for r in (db_data or []))

                if sql_failed:
                    print("[Stream SQL] SQL失败,降级RAG")
                    results = retriever.search_unified(query=rewritten, top_k=5)
                    async for typ, token in generator._call_llm_stream(
                        messages=[{"role": "system", "content": generator._system_prompt()},
                                  {"role": "user", "content": generator._build_prompt(
                                      rewritten, results, "unified", history, memory_ctx)}]
                    ):
                        full_answer += token
                        yield json.dumps({"type": typ, "content": token}, ensure_ascii=False) + "\n"
                else:
                    # 让 LLM 把 SQL 结果转成自然语言
                    summary_prompt = f"用户问题：{user_message}\n\n数据库查询结果：{db_data}\n\n请用自然语言把查询结果总结给用户。"
                    async for typ, token in generator._call_llm_stream(prompt=summary_prompt):
                        full_answer += token
                        yield json.dumps({"type": typ, "content": token}, ensure_ascii=False) + "\n"

            # ── RAG 路径 ──
            else:
                print(f"[Stream RAG] 混合检索: {rewritten}")
                results = retriever.search_unified(query=rewritten, top_k=5)
                async for typ, token in generator.generate_stream(
                    query=user_message, context=results, collection="unified",
                    history=history, memory_context=memory_ctx
                ):
                    full_answer += token
                    yield json.dumps({"type": typ, "content": token}, ensure_ascii=False) + "\n"

        except Exception as e:
            print(f"[Stream] 错误: {e}")
            yield json.dumps({"type": "error", "content": str(e)}, ensure_ascii=False) + "\n"

        # 5. 保存会话
        try:
            results_for_entity = retriever.search_unified(query=rewritten, top_k=3) if not route.get("is_sql") else []
            entities = await session_manager.extract_entities(rewritten, full_answer, results_for_entity)
            await session_manager.add_turn(session_id, user_message, full_answer, entities)
            if memory:
                memory.save_turn(session_id, user_message, full_answer, entities)
                await memory.maybe_summarize(session_id)
        except Exception as e:
            print(f"[Stream] 保存会话失败: {e}")

        # 发送结束信号（包含 session_id）
        yield json.dumps({"type": "done", "session_id": session_id}, ensure_ascii=False) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson",
                            headers={"X-Session-Id": session_id})


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
    memory_context: dict,
    start_time: float,
) -> AskResponse:
    """Planner 模式: 计划 → 执行 → 汇总"""
    plan_dict = route.get("plan", {})
    executor = request.app.state.planner_executor
    memory_ctx = memory_context.get("full_context", "")

    if executor is None:
        # 降级: 没有 executor 时走普通 RAG
        print("[Planner] executor 未初始化，降级到统一检索")
        results = request.app.state.retriever.search_unified(
            query=rewritten_question, top_k=req.top_k
        )
        answer = await request.app.state.generator.generate_with_history(
            query=req.question, context=results, collection="unified",
            history=history, memory_context=memory_ctx
        )
    else:
        # 执行计划
        from app.agent.planner import PlannerExecutor
        state = await executor.execute(plan_dict, rewritten_question,
                                        session_id=session_id)
        answer = await executor.aggregate(state, rewritten_question)

        # 构建 results（从 state 提取，供 SourceInfo 和 entity 提取使用）
        results = _state_to_results(state)

    # 实体提取 & 保存会话
    entities = await session_manager.extract_entities(rewritten_question, answer, results)
    await session_manager.add_turn(session_id, req.question, answer, entities)

    # Memory 模块: 保存本轮对话
    memory = getattr(request.app.state, 'memory', None)
    if memory:
        memory.save_turn(session_id, req.question, answer, entities)
        await memory.maybe_summarize(session_id)

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
    memory_context: dict,
    start_time: float,
) -> AskResponse:
    """Binary/Intent 模式: is_sql 判定 → SQL 或 RAG 路径（带容错降级）"""
    results = []
    source_collection = "unified"
    memory_ctx = memory_context.get("full_context", "")

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
            _, db_data = await sql_engine.execute_query(req.question)

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
        memory_context=memory_ctx,
    )

    # 实体提取 & 保存会话
    entities = await session_manager.extract_entities(rewritten_question, answer, results)
    await session_manager.add_turn(session_id, req.question, answer, entities)

    # Memory 模块: 保存本轮对话
    memory = getattr(request.app.state, 'memory', None)
    if memory:
        memory.save_turn(session_id, req.question, answer, entities)
        await memory.maybe_summarize(session_id)

    # 构建 Source 列表
    sources = _build_sources(results, req.top_k, source_collection)

    return AskResponse(
        answer=answer,
        sources=sources,
        processing_time=time.time() - start_time,
        session_id=session_id,
    )


# ---------------------------------------------------------------------------
# Direct 响应 — 问候/致谢/无关问题无需经过 LLM 生成
# ---------------------------------------------------------------------------

def _handle_direct(
    req: AskRequest,
    route: dict,
    session_id: str,
    start_time: float,
) -> AskResponse:
    """直接返回预设响应，不调用检索和 LLM"""
    answer = route.get("direct_answer", "您好！我是招投标智能助手，请问有什么可以帮您？")

    return AskResponse(
        answer=answer,
        sources=[],
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


async def _try_resume_checkpoint(
    request: Request,
    session_id: str,
    start_time: float,
):
    """检查是否存在未完成的 checkpoint，有则尝试恢复执行"""
    checkpoint_path = os.path.join(
        settings.checkpoint_dir, f"{session_id}.json"
    )
    if not os.path.exists(checkpoint_path):
        return None

    try:
        from app.agent.agent_state import AgentState
        state = AgentState.load_checkpoint(settings.checkpoint_dir, session_id)
    except Exception:
        return None

    if state.finished:
        # 已完成但没被清理的残留文件，直接删除
        AgentState.delete_checkpoint(settings.checkpoint_dir, session_id)
        return None

    print(f"[Checkpoint] 发现未完成断点 (session={session_id}, "
          f"step={state.step_count()}), 尝试恢复...")

    agent = getattr(request.app.state, 'agent', None)
    executor = getattr(request.app.state, 'planner_executor', None)

    try:
        # 优先用 Agent 恢复（ReAct 循环可以接续）
        if agent is not None:
            answer = await agent.resume(session_id)
        elif executor is not None:
            # Planner 模式: 直接聚合已有结果
            executor._session_id = session_id
            answer = await executor.aggregate(state, state.question)
        else:
            # 没有可用的执行器，清理断点，走正常流程
            AgentState.delete_checkpoint(settings.checkpoint_dir, session_id)
            return None

        sources = _state_to_results(state)

        return AskResponse(
            answer=answer,
            sources=_build_sources(sources, 5),
            processing_time=time.time() - start_time,
            session_id=session_id,
        )
    except Exception as e:
        print(f"[Checkpoint] 恢复失败: {e}，清理断点，正常处理")
        AgentState.delete_checkpoint(settings.checkpoint_dir, session_id)
        return None


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

@router.get("/sessions/{session_id}")
async def get_session_info(request: Request, session_id: str):
    """获取会话详情和消息历史"""
    session = await session_manager.get_session(session_id)
    if not session:
        return {"session_id": session_id, "messages": []}

    messages = []
    for turn in session.get("history", []):
        messages.append({"type": "user", "content": turn.get("question", "")})
        messages.append({"type": "assistant", "content": turn.get("answer", "")})

    return {
        "session_id": session_id,
        "title": session.get("last_question", "New Chat")[:30],
        "messages": messages,
    }


@router.delete("/session/{session_id}")
async def delete_session(request: Request, session_id: str):
    """删除会话"""
    await session_manager.delete_session(session_id)
    # 同步清理 checkpoint 文件
    if settings.checkpoint_enabled:
        try:
            from app.agent.agent_state import AgentState
            AgentState.delete_checkpoint(settings.checkpoint_dir, session_id)
        except Exception:
            pass
    # 同步清理 memory
    memory = getattr(request.app.state, 'memory', None)
    if memory:
        memory.forget_session(session_id)
    return {"status": "deleted", "session_id": session_id}


@router.get("/sessions")
async def list_sessions(request: Request):
    """获取所有会话列表"""
    sessions = await session_manager.list_sessions()
    return {"sessions": sessions}


@router.get("/health", response_model=HealthResponse)
async def health(request: Request):
    """健康检查"""
    return HealthResponse(
        status="ok",
        collections=request.app.state.retriever.get_stats(),
        embedding_model=settings.embedding_model,
    )
