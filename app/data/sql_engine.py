"""SQL引擎 — 委托给 ReadOnlySQLGateway（生成→校验→执行→审计）"""

from config import settings


class SQLEngine:
    """SQL 引擎（兼容封装），内部委托给 ReadOnlySQLGateway"""

    def __init__(self):
        self._gateway = None

    def _get_gateway(self):
        if self._gateway is None:
            from app.data.sql.gateway import ReadOnlySQLGateway
            self._gateway = ReadOnlySQLGateway()
        return self._gateway

    def execute_query(self, user_question: str):
        """
        核心方法：自然语言 → SQL → 执行结果
        返回 (sql_string, data_list)
        """
        gateway = self._get_gateway()
        try:
            sql, data = gateway.execute(
                user_question,
                task_id="",
                session_id="",
            )
            return sql, data
        except Exception as e:
            print(f"[SQL引擎] 流程异常: {e}")
            return "EXCEPTION", []
