"""Evidence Schema — 所有数据源的统一输出格式"""

from datetime import datetime, timezone
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class SourceType(str):
    """来源类型枚举"""
    RAG = "rag"
    SQL = "sql"
    WEBSITE = "website"
    SEARCH = "search"


class Citation(BaseModel):
    """证据引用"""
    source_type: str = ""          # rag / sql / website / search
    title: str = ""                # 文档标题
    source_name: str = ""          # 来源名称（法规名、数据库名等）
    source_url: str = ""           # 来源 URL
    article_id: str = ""           # 法条编号
    law_name: str = ""             # 法规名称
    retrieval_timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class Evidence(BaseModel):
    """统一证据结构 — 所有检索/查询结果的标准输出"""

    id: str = ""                   # 稳定 ID
    content: str = ""              # 主要内容（给 LLM 阅读）
    title: str = ""                # 标题
    source_type: str = ""          # rag / sql / website / search
    authority_level: int = 1       # 权威等级 0-3（3=官方/最高）
    freshness_level: int = 1       # 新鲜度 0-3
    score: float = 0.0             # 检索得分
    citation: Citation = Field(default_factory=Citation)
    metadata: dict = Field(default_factory=dict)
    retrieval_timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
