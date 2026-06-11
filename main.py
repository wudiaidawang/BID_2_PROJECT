#!/usr/bin/env python
"""API服务入口 — 招投标智能问答系统 v6.0 (LangChain/LangGraph 重构版)"""
import os

os.environ['HF_ENDPOINT'] = os.getenv('HF_ENDPOINT', 'https://hf-mirror.com')

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.retriever import HybridRetriever
from app.core.generator import LLMGenerator
from app.core.router import create_router
from app.storage.redis_client import redis_client
from config import settings
from app.core.sql_engine import SQLEngine


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 60)
    print(f"招投标智能问答系统 v6.0 (LangChain/LangGraph 重构版) 启动中...")
    print(f"  路由模式: {settings.router_mode}")
    print(f"  融合策略: {settings.fusion_strategy}")
    print(f"  Embedding: {settings.embedding_model} ({settings.embedding_dimension}d)")
    print(f"  LLM: {settings.llm_provider}/{settings.llm_model}")
    print("=" * 60)

    # [1/7] SQL 引擎
    print("\n[1/7] 加载 SQL 引擎...")
    app.state.sql_engine = SQLEngine()

    # [2/7] Redis
    print("\n[2/7] 连接 Redis...")
    await redis_client._get_client()

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

    # [4/7] 混合检索器 (先初始化，后续组件需要它)
    print("\n[4/7] 加载混合检索器...")
    app.state.retriever = HybridRetriever()

    # 初始化工具依赖 (注入 retriever + llm 给 LangChain @tool)
    from app.agent.agent_tools import set_tool_dependencies
    set_tool_dependencies(app.state.retriever, app.state.generator)
    print("   Tool dependencies 已注入")

    # [5/7] 路由 (LangGraph Router)
    print(f"\n[5/7] 加载路由器 (mode={settings.router_mode})...")
    router_instance = create_router(llm=app.state.generator)
    app.state.router = router_instance

    # [6/7] Planner + Agent (LangGraph)
    if settings.router_mode in ("planner", "auto", "think"):
        from app.agent.langgraph_agent import (
            LangGraphPlannerAgent, LangGraphReActAgent
        )
        app.state.planner_executor = LangGraphPlannerAgent(
            retriever=app.state.retriever,
            llm=app.state.generator,
            allow_replan=settings.planner_allow_replan,
        )
        print("   LangGraphPlannerAgent 已初始化 "
              f"(allow_replan={settings.planner_allow_replan})")

        if settings.agent_enabled:
            app.state.agent = LangGraphReActAgent(
                retriever=app.state.retriever,
                llm=app.state.generator,
                max_steps=settings.agent_max_steps,
            )
            print("   LangGraphReActAgent 已初始化 (planner降级备选)")
        else:
            app.state.agent = None
    else:
        app.state.planner_executor = None
        app.state.agent = None

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
    description="基于 RAG + SQL + LangGraph Agent 三引擎架构的招投标问答服务",
    version="6.0.0",
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
        "version": "6.0.0 (LangChain/LangGraph)",
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
            "LangGraph ThinkRouter (TaskAnalysis → 按task数自动分流)",
            "双引擎: SQL统计 + RAG混合检索 (LCEL链)",
            "LangChain ChromaDB + HuggingFaceEmbeddings",
            "langchain_community BM25Retriever",
            "BaseDocumentCompressor BGE-Reranker",
            "RedisChatMessageHistory 会话管理",
            "LangGraph ReActAgent + Planner DAG",
            "3层查询改写: 口语→书面语 + 冗余精简 + 同义词替换",
            "4个LangChain @tool: search_regulations / get_article / sql_query / summarize",
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
