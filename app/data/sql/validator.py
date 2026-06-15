"""SqlglotValidator — SQL AST 级安全校验"""

from app.data.sql.schemas import SQLValidationResult, ViewSchema


class SqlglotValidator:
    """AST validator for read-only SELECT/CTE statements."""

    forbidden_function_names = {
        "LOAD_FILE",
        "PG_READ_FILE",
        "PG_READ_BINARY_FILE",
        "LO_IMPORT",
        "LO_EXPORT",
        "READ_CSV",
        "READ_JSON",
        "READ_PARQUET",
    }

    def __init__(self, dialect: str = "sqlite", max_rows: int = 200,
                 max_joins: int = 4, max_subqueries: int = 4):
        try:
            import sqlglot
            from sqlglot import exp
        except ImportError as exc:
            raise RuntimeError("sqlglot is required for SQL validation. pip install sqlglot") from exc
        self.sqlglot = sqlglot
        self.exp = exp
        self.dialect = dialect
        self.max_rows = max_rows
        self.max_joins = max_joins
        self.max_subqueries = max_subqueries

    def validate(self, statement: str,
                 view_schemas: list[ViewSchema]) -> SQLValidationResult:
        """校验 SQL 语句的安全性并注入 LIMIT"""

        # 1. 解析
        try:
            expressions = self.sqlglot.parse(statement, read=self.dialect)
        except Exception as exc:
            raise SQLValidationError(f"SQL parse error: {exc}")

        if len(expressions) != 1:
            raise SQLValidationError("Only single statement allowed")

        tree = expressions[0]

        # 2. 只读检查：仅允许 SELECT / UNION
        if not isinstance(tree, (self.exp.Select, self.exp.Union)):
            raise SQLValidationError("Only SELECT/UNION allowed")

        forbidden_types = tuple(
            t for name in [
                "Insert", "Update", "Delete", "Create", "Drop", "Alter",
                "Command", "Copy", "Merge", "Transaction", "Use",
            ]
            if (t := getattr(self.exp, name, None)) is not None
        )
        if forbidden_types and any(tree.find_all(*forbidden_types)):
            raise SQLValidationError("Write/DDL operations forbidden")

        # 3. 表白名单检查
        schema_map = {schema.name: schema for schema in view_schemas}
        tables = sorted({table.name for table in tree.find_all(self.exp.Table)})
        if not tables:
            raise SQLValidationError("No table referenced")
        if any(table not in schema_map for table in tables):
            raise SQLValidationError(
                f"Unknown table(s): {[t for t in tables if t not in schema_map]}"
            )

        # 4. 列白名单 + 敏感列检查
        columns = sorted({
            column.name for column in tree.find_all(self.exp.Column)
            if column.name != "*"
        })
        allowed_columns = set()
        sensitive_columns = set()
        for table in tables:
            allowed_columns.update(schema_map[table].columns)
            sensitive_columns.update(schema_map[table].sensitive_columns)
        if any(column not in allowed_columns for column in columns):
            bad = [c for c in columns if c not in allowed_columns]
            raise SQLValidationError(f"Unknown column(s): {bad}")
        if any(column in sensitive_columns for column in columns):
            raise SQLValidationError("Sensitive column access denied")

        # 5. 复杂度检查
        join_count = sum(1 for _ in tree.find_all(self.exp.Join))
        if join_count > self.max_joins:
            raise SQLValidationError(
                f"Too many JOINs ({join_count} > {self.max_joins})"
            )
        subquery_count = sum(1 for _ in tree.find_all(self.exp.Subquery))
        if subquery_count > self.max_subqueries:
            raise SQLValidationError(
                f"Too many subqueries ({subquery_count} > {self.max_subqueries})"
            )

        # 6. 禁用函数检查
        for func in tree.find_all(self.exp.Anonymous):
            if func.name.upper() in self.forbidden_function_names:
                raise SQLValidationError(
                    f"Forbidden function: {func.name}"
                )

        # 7. LIMIT 强制
        limit = self._enforce_limit(tree)

        return SQLValidationResult(
            statement=tree.sql(dialect=self.dialect),
            tables=tables,
            columns=columns,
            limit=limit,
        )

    def _enforce_limit(self, tree) -> int:
        limit_expr = tree.args.get("limit")
        if limit_expr is None:
            tree.set("limit", self.exp.Limit(
                expression=self.exp.Literal.number(self.max_rows)
            ))
            return self.max_rows

        value_expr = limit_expr.expression
        if (not isinstance(value_expr, self.exp.Literal)
                or not value_expr.is_int):
            raise SQLValidationError("LIMIT must be an integer")

        value = int(value_expr.this)
        if value <= 0:
            raise SQLValidationError("LIMIT must be positive")
        if value > self.max_rows:
            limit_expr.set("expression",
                           self.exp.Literal.number(self.max_rows))
            return self.max_rows
        return value


class SQLValidationError(Exception):
    """SQL 校验失败"""
    pass
