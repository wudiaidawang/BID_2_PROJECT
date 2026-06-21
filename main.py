#!/usr/bin/env python
"""API服务入口 — 招投标智能问答系统 v5.1 (Auto自适应路由: SQL + RAG + Planner DAG)"""
import os

os.environ['HF_ENDPOINT'] = os.getenv('HF_ENDPOINT', 'https://hf-mirror.com')

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.retriever import HybridRetriever
from app.core.generator import LLMGenerator
from app.core.router import BinaryRouter, IntentRouter, PlannerRouter, create_router
from app.storage.redis_client import redis_client
from config import settings
from app.core.sql_engine import SQLEngine


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 60)
    print(f"招投标智能问答系统 v5.0 (融合版) 启动中...")
    print(f"  路由模式: {settings.router_mode}")
    print(f"  融合策略: {settings.fusion_strategy}")
    print(f"  Embedding: {settings.embedding_model} ({settings.embedding_dimension}d)")
    print(f"  LLM: {settings.llm_provider}/{settings.llm_model}")
    print("=" * 60)

    # [1/7] SQL 引擎
    print("\n[1/7] 加载 SQL 引擎...")
    app.state.sql_engine = SQLEngine()

    # [2/7] Redis (可选 — 连接失败自动降级，不影响主流程)
    print("\n[2/7] 连接 Redis...")
    await redis_client._get_client()
    if redis_client.available:
        print(f"  Redis 已连接 ({settings.redis_host}:{settings.redis_port})")
    else:
        print(f"  ⚠ Redis 不可用 — 会话持久化已禁用，问答功能正常")

    # [3/7] LLM 生成器
    print("\n[3/7] 加载 LLM 生成器...")
    app.state.generator = LLMGenerator()

    # [3.5/7] Memory 模块
    print("\n[3.5/7] 加载 Memory 模块...")
    from app.core.memory import MemoryManager
    app.state.memory = MemoryManager(
        llm=app.state.generator,
        storage_dir=getattr(settings, 'memory_storage_dir', './memory_store'),
        buffer_k=getattr(settings, 'memory_buffer_k', 5),
    )
    print(f"   MemoryManager 已初始化 (dir={app.state.memory._storage_dir})")

    # [4/7] 路由 (根据配置选择)
    print(f"\n[4/7] 加载路由器 (mode={settings.router_mode})...")
    router_instance = create_router(llm=app.state.generator)
    app.state.router = router_instance

    # 如果是 planner 或 auto 模式，初始化 PlannerExecutor
    if settings.router_mode in ("planner", "auto", "think"):
        from app.agent.planner import PlannerExecutor
        app.state.planner_executor = PlannerExecutor(
            retriever=None,  # 下面回填
            llm=app.state.generator,
            allow_replan=settings.planner_allow_replan,
        )
        print("   PlannerExecutor 已初始化 "
              f"(allow_replan={settings.planner_allow_replan})")

        if settings.agent_enabled:
            from app.agent.react_agent import ReActAgent
            app.state.agent = ReActAgent(
                retriever=None,
                llm=app.state.generator,
                max_steps=settings.agent_max_steps,
            )
            print("   ReActAgent 已初始化 (planner降级备选)")
        else:
            app.state.agent = None
    else:
        app.state.planner_executor = None
        app.state.agent = None

    # [5/7] 混合检索器
    print("\n[5/7] 加载混合检索器...")

    try:
        # 尝试使用新的统一改写器
        from app.core.query_rewriter import query_rewriter
        print(f"   查询改写: 已启用（3层规则管道）")
    except Exception:
        print(f"   查询改写: 使用旧版 Normalizer")

    app.state.retriever = HybridRetriever()

    # 回填 retriever 到需要它的组件
    if app.state.planner_executor and hasattr(app.state.planner_executor, 'retriever'):
        app.state.planner_executor.retriever = app.state.retriever
        # 同时更新所有工具的 retriever
        for tool in app.state.planner_executor.tools.values():
            tool.retriever = app.state.retriever

    if app.state.agent and hasattr(app.state.agent, 'retriever'):
        app.state.agent.retriever = app.state.retriever

    # [6/7] IntentRouter (intent 模式时使用)
    if settings.router_mode == "intent":
        print("\n[6/7] 加载 IntentRouter...")
        app.state.intent_router = IntentRouter(llm=app.state.generator)
    else:
        app.state.intent_router = None

    # [7/7] 统计
    print("\n[7/7] 获取统计信息...")
    stats = app.state.retriever.get_stats()

    print("\n" + "=" * 60)
    print("系统启动成功!")
    print(f"  SQL 数据库: {settings.db_path}")
    print(f"  招标库(bids): {stats.get('bids', 0)} 条")
    print(f"  法规库(regulations): {stats.get('regulations', 0)} 条")
    print(f"  API: http://{settings.host}:{settings.port}")
    print(f"  路由: {settings.router_mode}")
    print(f"  融合: {settings.fusion_strategy}")
    print(f"  Agent: {'启用' if app.state.agent else '未启用'}")
    print("=" * 60)

    yield

    print("\n系统关闭...")
    await redis_client.close()


app = FastAPI(
    title="招投标智能问答系统",
    description="基于 RAG + SQL + Agent 三引擎架构的招投标问答服务",
    version="5.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root():
    return {
        "service": "招投标智能问答系统",
        "version": "5.0.0",
        "router_mode": settings.router_mode,
        "fusion_strategy": settings.fusion_strategy,
        "embedding": {
            "model": settings.embedding_model,
            "dimension": settings.embedding_dimension,
        },
        "llm": {
            "provider": settings.llm_provider,
            "model": settings.llm_model,
        },
        "agent_enabled": settings.agent_enabled,
        "features": [
            "三模式路由: Binary(3路投票) / Intent(意图分类) / Planner(Agent决策体)",
            "双引擎: SQL统计 + RAG混合检索",
            "检索融合: RRF / Weighted(动态权重+Boost/Penalty)",
            "BGE-Reranker 精排",
            "3层查询改写: 口语→书面语 + 冗余精简 + 同义词替换",
            "4个Agent工具: search_regulations / get_article / sql_query / summarize",
            "多轮对话 (Redis, 可选)",
        ],
        "endpoints": [
            {"path": "POST /api/v1/ask", "description": "问答接口"},
            {"path": "GET /api/v1/health", "description": "健康检查"},
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
