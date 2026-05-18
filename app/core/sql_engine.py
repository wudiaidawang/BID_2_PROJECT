import sqlite3
import requests
import json
import re
from config import settings


class SQLEngine:
    def __init__(self):
        # 从 settings 中读取路径和 API 配置
        self.db_path = settings.db_path
        self.api_key = settings.llm_api_key
        # 兼容处理 URL，确保以 /chat/completions 结尾
        base_url = settings.llm_api_url.rstrip('/')
        if not base_url.endswith("/chat/completions"):
            self.url = f"{base_url}/chat/completions"
        else:
            self.url = base_url

        self.model = settings.llm_model

        # 定义 SQL 生成的提示词（基于你之前的 project.md 逻辑）
        self.system_prompt = """你是一个专业的 SQLite 专家。
当前数据库有一张表：bids
字段及说明：
- project_name (项目名称): 字符串
- category (类别): 字符串 (工程, 服务, 货物)
- publish_date (发布时间): 字符串 (YYYY-MM-DD)
- amount (中标金额): 浮点数 (单位：元)
- supplier (中标人): 字符串 (也叫供应商)
- city (市区): 字符串

【输出规则】：
1. 只输出 SQL 语句，不要任何解释。
2. 必须使用 SQLite 语法。
3. 统计数量使用 COUNT(*)，计算金额使用 SUM(amount)。
4. 如果问题涉及多个条件，请使用 AND 连接。
5. 严禁输出包含分号(;)的多条语句。
"""

    def _execute_local_sql(self, sql: str):
        """执行本地 SQLite 查询"""
        print(f"🔍 [SQL引擎] 正在执行 SQL: {sql}")
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # 使返回结果可以通过字段名访问
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            # 转换成字典列表
            results = [dict(row) for row in rows]
            conn.close()
            print(f"✅ [SQL引擎] 查询成功，返回 {len(results)} 条数据")
            return results
        except Exception as e:
            print(f"❌ [SQL引擎] 数据库执行出错: {str(e)}")
            return [{"error": str(e)}]

    def execute_query(self, user_question: str):
        """
        核心方法：自然语言 -> SQL -> 执行结果
        """
        print(f"🤖 [SQL引擎] 正在请求 LLM 生成 SQL，问题: {user_question}")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"请将该问题转为 SQL：{user_question}"}
            ],
            "temperature": 0.0  # 保持 SQL 生成的稳定性
        }

        try:
            response = requests.post(self.url, json=payload, headers=headers, timeout=15)
            if response.status_code != 200:
                print(f"❌ [SQL引擎] API 请求失败: {response.text}")
                return "API_ERROR", []

            res_json = response.json()
            raw_content = res_json['choices'][0]['message']['content']

            # 清洗生成的 SQL (去掉 Markdown 标签)
            clean_sql = raw_content.strip().replace("```sql", "").replace("```", "").strip()
            # 截断分号后的内容防止注入
            clean_sql = clean_sql.split(";")[0]

            # 执行查询
            db_data = self._execute_local_sql(clean_sql)
            return clean_sql, db_data

        except Exception as e:
            print(f"❌ [SQL引擎] 流程发生异常: {str(e)}")
            return "EXCEPTION", []