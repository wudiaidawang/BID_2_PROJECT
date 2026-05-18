#!/usr/bin/env python
"""API服务入口"""
import os

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.retriever import HybridRetriever
from app.core.generator import LLMGenerator
from app.core.router import IntentRouter
from app.storage.redis_client import redis_client
from config import settings
# 导入你的模块
from app.core.sql_engine import SQLEngine


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 60)
    print("招投标智能问答系统 (SQL + RAG 混合版) 启动中...")
    print("=" * 60)

    # --- 新增：初始化 SQL 引擎 ---
    print("\n[1/6] 加载 SQL 引擎 (精准计算模块)...")
    app.state.sql_engine = SQLEngine()

    print("\n[2/6] 连接 Redis...")
    await redis_client._get_client()

    print("\n[3/6] 加载意图路由器 (含 SQL 拦截规则)...")
    app.state.router = IntentRouter()

    print("\n[4/6] 加载混合检索器...")
    app.state.retriever = HybridRetriever()

    print("\n[5/6] 加载 LLM 生成器...")
    app.state.generator = LLMGenerator()

    print("\n[6/6] 获取统计信息...")
    stats = app.state.retriever.get_stats()

    print("\n" + "=" * 60)
    print("系统启动成功!")
    print(f"  SQL 数据库路径: {settings.db_path}")  # 显示数据库位置
    print(f"  招标库(bids): {stats.get('bids', 0)} 条")
    print(f"  法规库(regulations): {stats.get('regulations', 0)} 条")
    print(f"  API地址: http://{settings.host}:{settings.port}")
    print(f"  功能模式: 向量搜索 + SQL 精准计算")  # 明确双引擎模式
    print("=" * 60)

    yield

    print("\n系统关闭...")
    await redis_client.close()


app = FastAPI(
    title="招投标智能问答系统",
    description="基于 RAG + SQL 双引擎架构的招投标问答服务",
    version="4.1.0",  # 既然加入了 SQL，算是一次版本升级
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
        "version": "4.1.0",
        "features": [
            "双引擎路由：精准计算(SQL) + 模糊搜索(RAG)",
            "纯关键词意图路由（100% 可控拦截）",
            "Chroma 向量数据库 + SQLite 关系数据库",
            "混合检索（向量 + BM25 + jieba 分词）",
            "多轮对话会话管理（基于 Redis）"
        ],
        "endpoints": [
            {"path": "POST /api/v1/ask", "description": "问答接口"},
            {"path": "GET /api/v1/health", "description": "健康检查"}
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

