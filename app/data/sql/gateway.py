"""ReadOnlySQLGateway — SQL 生成 → 校验 → 执行 → 审计（同步版本）"""

import json
import time
import sqlite3
from typing import Protocol

from config import settings
from app.data.sql.schemas import (
    ViewSchema, SQLCandidate, SQLValidationResult, SQLAuditEvent,
)
from app.data.sql.validator import SqlglotValidator, SQLValidationError


class SQLAuditSink(Protocol):
    """审计记录接口"""
    def record(self, event: SQLAuditEvent) -> None: ...


class _PrintAuditSink:
    """默认审计实现：打印到控制台"""
    def record(self, event: SQLAuditEvent) -> None:
        print(f"[SQL-Audit] {event.status} | task={event.task_id} | "
              f"{event.duration_ms:.0f}ms | rows={event.row_count}")


class ReadOnlySQLGateway:
    """只读 SQL 网关：LLM 生成 → AST 校验 → SQLite 执行 → 审计"""

    def __init__(
        self,
        validator: SqlglotValidator = None,
        schemas: dict[str, ViewSchema] = None,
        audit_sink: SQLAuditSink = None,
    ):
        from app.data.sql.catalog import build_default_schema_catalog
        self.validator = validator or SqlglotValidator(
            dialect="sqlite",
            max_rows=settings.sql_max_rows if hasattr(settings, 'sql_max_rows') else 200,
            max_joins=settings.sql_max_joins if hasattr(settings, 'sql_max_joins') else 4,
            max_subqueries=settings.sql_max_subqueries if hasattr(settings, 'sql_max_subqueries') else 4,
        )
        self.schemas = schemas or build_default_schema_catalog()
        self.audit_sink = audit_sink or _PrintAuditSink()
        self.db_path = settings.db_path

    def execute(self, user_question: str, task_id: str = "",
                session_id: str = "") -> tuple[str, list[dict]]:
        """
        主入口：NL → SQL → 校验 → 执行 → 审计
        返回 (final_sql, data_rows)
        """
        feedback = ""
        allowed_views = list(self.schemas.keys())
        selected_schemas = [self.schemas[name] for name in allowed_views]

        for attempt in range(2):
            # 1. LLM 生成 SQL
            candidate = self._generate(user_question, selected_schemas, feedback)

            started = time.perf_counter()
            try:
                # 2. AST 校验
                validated = self.validator.validate(
                    candidate.statement, selected_schemas
                )
            except SQLValidationError as exc:
                self.audit_sink.record(SQLAuditEvent(
                    task_id=task_id, session_id=session_id,
                    statement=candidate.statement,
                    parameter_names=sorted(candidate.parameters),
                    status="validation_failed",
                    duration_ms=(time.perf_counter() - started) * 1000,
                    error_type=str(exc),
                ))
                print(f"[SQL-Gateway] Validation failed (attempt {attempt+1}/2): {exc}")
                feedback = f"上一候选SQL未通过校验：{exc}。请严格修正，只生成单条SELECT语句，只使用允许的表和字段。"
                continue

            try:
                # 3. 执行
                data = self._execute_sqlite(validated.statement)
                elapsed = (time.perf_counter() - started) * 1000
                self.audit_sink.record(SQLAuditEvent(
                    task_id=task_id, session_id=session_id,
                    statement=validated.statement,
                    parameter_names=sorted(candidate.parameters),
                    status="completed",
                    duration_ms=elapsed,
                    row_count=len(data),
                ))
                print(f"[SQL-Gateway] OK ({elapsed:.0f}ms, {len(data)} rows)")
                return validated.statement, data

            except Exception as exc:
                self.audit_sink.record(SQLAuditEvent(
                    task_id=task_id, session_id=session_id,
                    statement=validated.statement,
                    parameter_names=sorted(candidate.parameters),
                    status="execution_failed",
                    duration_ms=(time.perf_counter() - started) * 1000,
                    error_type=exc.__class__.__name__,
                ))
                print(f"[SQL-Gateway] Execution failed: {exc}")
                raise

        raise SQLValidationError("SQL generation failed after 2 attempts")

    def _generate(self, user_question: str,
                  schemas: list[ViewSchema],
                  feedback: str) -> SQLCandidate:
        """调用 LLM 生成 SQL（同步）"""
        import requests

        # 构建 schema 描述
        schema_desc = "\n".join(
            f"【{s.name}】{s.description}\n"
            + "\n".join(f"  - {col}: {desc}" for col, desc in s.columns.items())
            for s in schemas
        )

        system_prompt = f"""你是 SQLite 专家。只生成单条 SELECT 或只读 CTE。
严格使用以下视图/表的字段，禁止写操作、DDL、系统表、文件函数、未授权字段。
用户值使用命名参数（如 :category_name），不要直接拼接字符串。
聚合函数使用 COUNT(*)、SUM()、AVG() 等标准写法。
不要在 SQL 前后添加任何解释文本。

可用 schema：
{schema_desc}"""

        user_prompt = f"请将以下问题转为 SQL：{user_question}"
        if feedback:
            user_prompt = f"{feedback}\n\n{user_prompt}"

        api_key = settings.llm_api_key
        api_url = settings.llm_api_url.rstrip('/')
        if not api_url.endswith("/chat/completions"):
            api_url = f"{api_url}/chat/completions"

        response = requests.post(
            api_url,
            json={
                "model": settings.llm_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.0,
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=settings.llm_timeout,
        )

        if response.status_code != 200:
            raise SQLValidationError(f"LLM API error: {response.status_code}")

        body = response.json()
        raw = body["choices"][0]["message"]["content"]

        # 清洗 SQL
        clean = raw.strip()
        clean = clean.replace("```sql", "").replace("```", "").strip()
        clean = clean.split(";")[0].strip()
        if not clean:
            raise SQLValidationError("Empty SQL generated")

        return SQLCandidate(statement=clean, parameters={})

    def _execute_sqlite(self, sql: str) -> list[dict]:
        """执行 SQL 并返回字典列表"""
        print(f"[SQL-Gateway] Executing: {sql[:200]}")
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(sql)
            rows = [dict(row) for row in cursor.fetchall()]
            return rows
        finally:
            conn.close()
