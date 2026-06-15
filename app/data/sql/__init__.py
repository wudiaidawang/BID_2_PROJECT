"""SQL 模块 — 只读 SQL 生成、校验、审计"""

from app.data.sql.schemas import ViewSchema, SQLCandidate, SQLValidationResult, SQLAuditEvent
from app.data.sql.validator import SqlglotValidator, SQLValidationError
from app.data.sql.gateway import ReadOnlySQLGateway
from app.data.sql.catalog import build_default_schema_catalog

__all__ = [
    "ViewSchema", "SQLCandidate", "SQLValidationResult", "SQLAuditEvent",
    "SqlglotValidator", "SQLValidationError",
    "ReadOnlySQLGateway",
    "build_default_schema_catalog",
]
