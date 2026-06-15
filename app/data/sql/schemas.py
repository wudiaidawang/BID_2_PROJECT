"""SQL模块 — Pydantic schemas"""

from typing import Any, Literal
from pydantic import BaseModel, Field


class ViewSchema(BaseModel):
    """视图/表 schema 定义，用于 SQL 校验"""
    name: str
    description: str
    columns: dict[str, str]
    sensitive_columns: list[str] = Field(default_factory=list)


class SQLCandidate(BaseModel):
    """LLM 生成的 SQL 候选"""
    statement: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    selected_views: list[str] = Field(default_factory=list)


class SQLValidationResult(BaseModel):
    """SQL 校验结果"""
    statement: str           # 可能被修改（如注入 LIMIT）
    tables: list[str]
    columns: list[str]
    limit: int


class SQLAuditEvent(BaseModel):
    """SQL 审计事件"""
    task_id: str
    session_id: str
    statement: str
    parameter_names: list[str]
    status: Literal["validation_failed", "execution_failed", "completed"]
    duration_ms: float
    row_count: int | None = None
    query_id: str | None = None
    error_type: str | None = None
