"""SQL 引擎 — 自然语言转 SQL（异步 httpx）"""

import sqlite3
import json
import re
import httpx

from config import settings


class SQLEngine:
    def __init__(self):
        self.db_path = settings.db_path
        self.api_key = settings.llm_api_key
        base_url = settings.llm_api_url.rstrip('/')
        if not base_url.endswith("/chat/completions"):
            self.url = f"{base_url}/chat/completions"
        else:
            self.url = base_url
        self.model = settings.llm_model

        self.system_prompt = """你是一个专业的 SQLite 专家。
当前数据库有5张可查询对象：

【表1：bids — 招标项目明细表】
字段及说明：
- project_name (项目名称): 字符串
- category (类别): 字符串。有效值: 学校, 政府, 货物, 医院, 工程, 项目管理, 服务, 监理, 施工, 设计, 咨询, 土地, 勘察, 项目评估, 招标代理。注意：用户说的"XX类"要去掉"类"字，如"工程类"→"工程"
- publish_date (发布时间): 字符串 (YYYY-MM-DD)
- amount (中标金额): 浮点数 (单位：元)
- supplier (中标人): 字符串 (也叫供应商)
- city (市区): 字符串

【表2：supplier_profile — 供应商画像视图（已预聚合）】
字段及说明：
- supplier (中标人): 字符串
- total_bids (累计中标次数): 整数
- total_amount (累计中标总金额): 浮点数 (单位：元)
- avg_amount (平均中标金额): 浮点数
- category_count (涉及项目种类数·去重): 整数
- categories (涉及项目类别列表): 逗号分隔字符串，如 "工程,服务,货物"
- city_count (覆盖城市数·去重): 整数
- latest_bid_date (最近中标日期): 字符串 (YYYY-MM-DD)
- earliest_bid_date (最早中标日期): 字符串 (YYYY-MM-DD)

【表3：enterprise — 企业画像表】
字段及说明：
- company_name (企业名称): 字符串
- role (角色): 字符串，固定值"中标单位"
- bid_count (中标次数): 整数
- total_amount (中标总金额): 浮点数 (单位：元)
- avg_amount (平均中标金额): 浮点数 (单位：元)
- city (活跃城市): 逗号分隔字符串
- industry (主要行业): 字符串
- categories (涉及类别): 逗号分隔字符串
- latest_bid_date (最近中标日期): 字符串 (YYYY-MM-DD)
- earliest_bid_date (最早中标日期): 字符串 (YYYY-MM-DD)

【表4：price — 物资报价表】
字段及说明：
- material_name (物资名称): 字符串
- brand (品牌): 字符串
- supplier (供应商): 字符串
- category (产品分类): 字符串
- budget_price (预算价): 浮点数 (单位：元)
- bid_price (中标价): 浮点数 (单位：元)
- province (省份): 字符串
- city (市区): 字符串
- collect_date (采集时间): 字符串

【表5：product — 商品参数表】
字段及说明：
- product_name (商品名称): 字符串
- brand (品牌): 字符串
- product_type (产品类型): 字符串
- supplier (供应商): 字符串
- spec_params (产品参数): 字符串 (JSON格式)
- province (省份): 字符串
- city (市区): 字符串

【路由规则——选哪张表】：
1. 涉及供应商/企业实力的问题 → enterprise 或 supplier_profile：
   - "哪些企业中标最多"、"XX公司实力如何"、"中标金额排名" → enterprise
   - "供应商交易额排名"、"覆盖类别最多的" → supplier_profile
2. 涉及具体项目明细的问题 → bids
3. 涉及价格/报价/预算的问题 → price：
   - "XX物资的平均价格"、"哪个品牌最贵"、"价格区间"
4. 涉及商品/产品参数的问题 → product：
   - "有哪些品牌的XX"、"XX型号的规格参数"
5. 企业比较、按条件筛选企业 → enterprise

【输出规则】：
1. 只输出 SQL 语句，不要任何解释。
2. 必须使用 SQLite 语法。
3. 统计数量使用 COUNT(*)，计算金额使用 SUM(amount) 或 SUM(bid_price)。
4. 查类别时用 LIKE '%关键词%'。
5. 严禁输出包含分号(;)的多条语句。
"""

    def _execute_local_sql(self, sql: str):
        """执行本地 SQLite 查询"""
        print(f"[SQL引擎] 正在执行 SQL: {sql}")
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            results = [dict(row) for row in rows]
            conn.close()
            print(f"[SQL引擎] 查询成功，返回 {len(results)} 条数据")
            return results
        except Exception as e:
            print(f"[SQL引擎] 数据库执行出错: {str(e)}")
            return [{"error": str(e)}]

    async def execute_query(self, user_question: str):
        """核心方法：自然语言 → SQL → 执行结果（异步）"""
        print(f"[SQL引擎] 正在请求 LLM 生成 SQL，问题: {user_question}")

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
            "temperature": 0.0,
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    self.url, json=payload, headers=headers,
                    timeout=settings.llm_timeout
                )
            if resp.status_code != 200:
                print(f"[SQL引擎] API 请求失败: {resp.text[:300]}")
                return "API_ERROR", []

            res_json = resp.json()
            raw_content = res_json['choices'][0]['message']['content']

            clean_sql = raw_content.strip().replace("```sql", "").replace("```", "").strip()
            clean_sql = clean_sql.split(";")[0]

            db_data = self._execute_local_sql(clean_sql)
            return clean_sql, db_data

        except httpx.TimeoutException:
            print(f"[SQL引擎] LLM 超时 (>{settings.llm_timeout}s)，返回空")
            return "API_TIMEOUT", []
        except Exception as e:
            print(f"[SQL引擎] 流程发生异常: {str(e)}")
            return "EXCEPTION", []
