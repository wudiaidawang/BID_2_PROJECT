# -*- coding: utf-8 -*-
"""统一路由模块 —— BinaryRouter(3路投票) + IntentRouter(意图分类) + Planner接口"""

import json
import re
import numpy as np
import httpx
from typing import Dict, Any, List, Optional
from config import settings

# ── SQL 模板库（约 20 条统计类标准问法 + 绑定 SQL） ──
# 当 is_sql=True 且余弦相似度 > 阈值时，直接复用绑定的 SQL，跳过 LLM 生成
SQL_TEMPLATES: List[Dict[str, str]] = [
    {"question": "一共有多少条招标数据", "sql": "SELECT COUNT(*) FROM bids"},
    {"question": "统计所有项目的总数量", "sql": "SELECT COUNT(*) FROM bids"},
    {"question": "平均中标金额是多少", "sql": "SELECT AVG(amount) FROM bids"},
    {"question": "哪个公司中标数量最多",
     "sql": "SELECT supplier, COUNT(*) AS cnt FROM bids GROUP BY supplier ORDER BY cnt DESC LIMIT 1"},
    {"question": "汇总一下今年的招标情况",
     "sql": "SELECT COUNT(*), SUM(amount) FROM bids WHERE publish_date LIKE '2025%'"},
    {"question": "中标金额最高的前三个项目",
     "sql": "SELECT project_name, amount FROM bids ORDER BY amount DESC LIMIT 3"},
    {"question": "统计一下去年有多少家企业来投标",
     "sql": "SELECT COUNT(DISTINCT supplier) FROM bids WHERE publish_date LIKE '2024%'"},
    {"question": "今年工程类项目有多少个",
     "sql": "SELECT COUNT(*) FROM bids WHERE category='工程' AND publish_date LIKE '2025%'"},
    {"question": "中标金额超过一千万的项目有哪些",
     "sql": "SELECT project_name, amount FROM bids WHERE amount > 10000000"},
    {"question": "各类型项目的总中标金额",
     "sql": "SELECT category, SUM(amount) FROM bids GROUP BY category"},
    {"question": "列出所有工程类的项目", "sql": "SELECT * FROM bids WHERE category='工程'"},
    {"question": "中标金额最高的是哪个项目",
     "sql": "SELECT project_name, amount FROM bids ORDER BY amount DESC LIMIT 1"},
    {"question": "哪个月份的招标项目最多",
     "sql": "SELECT SUBSTR(publish_date, 1, 7) AS month, COUNT(*) FROM bids GROUP BY month ORDER BY COUNT(*) DESC"},
    {"question": "各供应商的中标总金额排名",
     "sql": "SELECT supplier, SUM(amount) AS total FROM bids GROUP BY supplier ORDER BY total DESC"},
    {"question": "今年货物类的中标总额",
     "sql": "SELECT SUM(amount) FROM bids WHERE category='货物' AND publish_date LIKE '2025%'"},
    {"question": "去年中标金额排名前十的项目",
     "sql": "SELECT project_name, amount FROM bids WHERE publish_date LIKE '2024%' ORDER BY amount DESC LIMIT 10"},
    {"question": "各省份的项目数量统计",
     "sql": "SELECT province, COUNT(*) FROM bids GROUP BY province"},
    {"question": "去年的中标总金额是多少",
     "sql": "SELECT SUM(amount) FROM bids WHERE publish_date LIKE '2024%'"},
    {"question": "哪种类型的项目数量最多",
     "sql": "SELECT category, COUNT(*) AS cnt FROM bids GROUP BY category ORDER BY cnt DESC LIMIT 1"},
    {"question": "项目数量超过一百个的省份有哪些",
     "sql": "SELECT province, COUNT(*) AS cnt FROM bids GROUP BY province HAVING cnt > 100"},
]

# ── 法规模板库 ──
# 用于 Embedding 双塔对比：query 同时与 SQL 模板和法规模板比相似度
COMPLIANCE_TEMPLATES = [
    "投标保证金可以没收吗",
    "围标串标怎么认定",
    "招标文件歧视性条款怎么维权",
    "中标后可以废标吗",
    "分包转包有什么区别",
    "投标有效期过了怎么办",
    "招标公告发布要求是什么",
    "评标委员会怎么组成",
    "低于成本价投标怎么处理",
    "联合体投标有什么资质要求",
    "质疑和投诉的流程是什么",
    "招标投标保密要求有哪些",
    "合同签订期限是多久",
    "履约保证金怎么退",
    "招标投标违法行为怎么处罚",
    "投标人弄虚作假怎么处理",
    "招标文件澄清或修改有什么规定",
    "法定否决投标的情形有哪些",
    "投标人少于三个怎么办",
    "招标代理机构有什么禁止行为",
]

# ── SQL 判定边界 ──
# 必须命中聚合/时间触发词，且不含合规判定阻断词
AGGREGATION_TRIGGERS = [
    "总共", "一共", "最高", "最低", "平均", "最多", "最少",
    "排名", "汇总", "统计", "数量", "总金额", "多少条",
    "多少个", "多少家", "哪家", "哪些公司", "列出",
]
TIME_TRIGGERS = [
    "去年", "今年", "本月", "上个月",
    "2023", "2024", "2025", "上一年", "本年度", "近期",
]
# 合规阻断词 —— 出现任意一个即判定为非 SQL
COMPLIANCE_BLOCKERS = [
    "才能", "才可以", "可以吗", "算违规", "有效吗", "合法吗",
    "符合规定", "应当", "不得", "依法", "必须招标",
    "禁止", "责令", "处罚", "罚款",
]

# 余弦匹配阈值：超过此值直接复用模板 SQL，不走 LLM
TEMPLATE_MATCH_THRESHOLD = 0.92


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """计算余弦相似度 —— 用 .dot 和 .linalg.norm 做纯 CPU 数学计算"""
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


class BinaryRouter:
    """二分类意图网关：is_sql 判定 + SQL 模板匹配"""

    def __init__(self):
        self._template_vectors: List[np.ndarray] = []  # SQL 模板库的 embedding 向量
        self._compliance_vectors: List[np.ndarray] = []  # 法规模板库的 embedding 向量
        self._embedding_service = None
        self._ready = False

    def _warmup(self):
        """延迟加载 embedding 模型并预计算 SQL 模板库向量"""
        if self._ready:
            return
        from app.core.embedding import EmbeddingService
        self._embedding_service = EmbeddingService()

        sql_questions = [t["question"] for t in SQL_TEMPLATES]
        sql_vectors = self._embedding_service.model.encode(
            sql_questions, show_progress_bar=False
        )
        self._template_vectors = [np.array(v) for v in sql_vectors]

        compliance_vectors = self._embedding_service.model.encode(
            COMPLIANCE_TEMPLATES, show_progress_bar=False
        )
        self._compliance_vectors = [np.array(v) for v in compliance_vectors]

        self._ready = True
        print("[Gateway] Three-way router ready "
              f"({len(SQL_TEMPLATES)} SQL + {len(COMPLIANCE_TEMPLATES)} compliance templates loaded)")

    def _check_is_sql(self, query: str) -> bool:
        """规则边界判定：命中聚合/时间触发词 且 不含合规阻断词 → is_sql=True"""
        has_agg = any(t in query for t in AGGREGATION_TRIGGERS)
        has_time = any(t in query for t in TIME_TRIGGERS)
        has_blocker = any(t in query for t in COMPLIANCE_BLOCKERS)
        return (has_agg or has_time) and not has_blocker

    def _embedding_classify(self, query: str) -> bool:
        """Embedding 双塔对比：query 与 SQL 模板库 vs 法规模板库的最高相似度"""
        query_vec = np.array(self._embedding_service.embed_query(query))

        sql_max = max(
            _cosine_similarity(query_vec, tv) for tv in self._template_vectors
        )
        compliance_max = max(
            _cosine_similarity(query_vec, cv) for cv in self._compliance_vectors
        )
        return sql_max > compliance_max

    async def _llm_classify(self, query: str) -> Optional[bool]:
        """LLM 分类：调用混元判 SQL 还是 RAG，失败返回 None 弃票"""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    settings.llm_api_url,
                    headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                    json={
                        "model": settings.llm_model,
                        "messages": [
                            {"role": "system", "content": (
                                "你是招投标问答系统的意图分类器。"
                                "判断用户问题应该用哪种方式回答：\n"
                                "- SQL：问题需要统计数据库中的招标项目数量、金额、排名等\n"
                                "- RAG：问题在问招投标法律法规、合规要求、操作流程等\n"
                                "只回复 'SQL' 或 'RAG'，不要解释。"
                            )},
                            {"role": "user", "content": query}
                        ],
                        "temperature": 0,
                        "max_tokens": 5
                    },
                    timeout=15
                )
                if resp.status_code == 200:
                    answer = resp.json()["choices"][0]["message"]["content"].strip()
                    return answer.upper().startswith("SQL")
        except Exception:
            pass
        return None

    async def route(self, query: str) -> Dict[str, Any]:
        """三边并行路由 —— 规则 + Embedding双塔 + LLM，2/3 多数投票"""
        self._warmup()

        # 三边并行
        rule_is_sql = self._check_is_sql(query)
        embedding_is_sql = self._embedding_classify(query)
        llm_is_sql = await self._llm_classify(query)

        # 投票（2/3 多数，LLM 挂掉自动降级）
        votes = [rule_is_sql, embedding_is_sql, llm_is_sql]
        valid = [v for v in votes if v is not None]
        is_sql = sum(valid) >= len(valid) / 2

        # SQL 模板匹配（is_sql=True 时找最近的 SQL 模板）
        sql_template = None
        match_score = 0.0
        if is_sql:
            query_vec = np.array(self._embedding_service.embed_query(query))
            best_score = -1.0
            best_idx = -1
            for i, tv in enumerate(self._template_vectors):
                sim = _cosine_similarity(query_vec, tv)
                if sim > best_score:
                    best_score = sim
                    best_idx = i
            match_score = best_score
            if best_score >= TEMPLATE_MATCH_THRESHOLD and best_idx >= 0:
                sql_template = SQL_TEMPLATES[best_idx]["sql"]

        print(f"[Gateway] is_sql={is_sql} "
              f"(rule={'Y' if rule_is_sql else 'N'} "
              f"emb={'Y' if embedding_is_sql else 'N'} "
              f"llm={'Y' if llm_is_sql else 'N' if llm_is_sql is None else 'N'})"
              + (f" match={match_score:.3f}" if is_sql else ""))

        return {
            "is_sql": is_sql,
            "sql_template": sql_template,
            "match_score": match_score,
            "votes": {"rule": rule_is_sql, "embedding": embedding_is_sql, "llm": llm_is_sql},
        }


# ═══════════════════════════════════════════════════════════════════════
# IntentRouter — 队友风格的 LLM 意图分类（type + complexity）
# ═══════════════════════════════════════════════════════════════════════

INTENT_PROMPT = """判断以下招标投标问题的类型和复杂度。

## 历史对话（仅最近一轮）
{history}

## 当前问题
{question}

输出JSON：{{"type": "definition|procedure|penalty|provision|stat_query|other", "complexity": "single_step|multi_step"}}

类型说明：
- definition: 问概念定义（什么是X、如何理解X）
- procedure: 问流程操作（如何X、步骤、流程）
- penalty: 问处罚后果（违反会怎样、罚款多少）
- provision: 问具体法条（第X条、规定）
- stat_query: 问统计数据（多少、排名、汇总）★ 新增
- other: 其他

复杂度说明：
- single_step: 一次检索就能回答
- multi_step: 需要多次检索/多步推理

示例：
"什么是串通投标？" → {{"type": "definition", "complexity": "single_step"}}
"围标的定义和处罚" → {{"type": "definition", "complexity": "multi_step"}}
"去年有多少项目" → {{"type": "stat_query", "complexity": "single_step"}}
"""

# 快速拦截关键词
GREETING_KEYWORDS = ["你好", "您好", "hi", "hello", "嗨", "在吗", "在不在", "有人吗"]
THANKS_KEYWORDS = ["谢谢", "感谢", "thanks", "thank"]
GOODBYE_KEYWORDS = ["再见", "拜拜", "bye", "goodbye"]
UNRELATED_KEYWORDS = [
    "天气", "气温", "下雨", "晴天", "台风", "温度",
    "股票", "基金", "理财", "投资", "涨跌", "股价",
    "美食", "餐厅", "外卖", "菜谱",
    "电影", "电视", "综艺", "娱乐", "明星", "八卦",
    "游戏", "足球", "篮球", "体育", "比赛", "比分",
]
BIDDING_KEYWORDS = [
    "招标", "投标", "采购", "围标", "串标", "中标",
    "标书", "标段", "评标", "开标",
]


class IntentRouter:
    """LLM 意图分类器 — 判断问题类型和复杂度"""

    def __init__(self, llm=None):
        self.llm = llm

    def quick_intercept(self, question: str) -> Optional[Dict]:
        """快速拦截问候/致谢/告别/无关问题"""
        if not settings.intent_quick_intercept:
            return None

        q = question.strip().lower()
        q_clean = re.sub(r'[^一-龥a-zA-Z0-9]', '', q)

        for kw in GREETING_KEYWORDS:
            if kw in q_clean:
                return {"type": "quick_response", "complexity": "single_step",
                        "response": "您好！我是招投标智能助手，请问有什么可以帮您？"}

        for kw in THANKS_KEYWORDS:
            if kw in q_clean:
                return {"type": "quick_response", "complexity": "single_step",
                        "response": "不客气，有问题随时问我！"}

        for kw in GOODBYE_KEYWORDS:
            if kw in q_clean:
                return {"type": "quick_response", "complexity": "single_step",
                        "response": "再见！如有问题，随时回来咨询。"}

        # 无关领域检测
        has_bidding = any(kw in q for kw in BIDDING_KEYWORDS)
        if not has_bidding:
            for kw in UNRELATED_KEYWORDS:
                if kw in q:
                    return {"type": "unrelated", "complexity": "single_step"}

        return None

    async def route(self, question: str, session_id: str = "", session_manager=None) -> Dict:
        """LLM 意图分类"""
        # 快速拦截
        intercepted = self.quick_intercept(question)
        if intercepted:
            return intercepted

        if not self.llm:
            return {"type": "other", "complexity": "single_step"}

        history = "（无历史记录）"
        if session_manager and session_id:
            try:
                h = session_manager.get_chat_history(session_id)
                msgs = h.messages[-2:]
                if msgs:
                    history = "\n".join(
                        f"{'用户' if m.type == 'human' else '助手'}: {m.content[:300]}"
                        for m in msgs
                    )
            except Exception:
                pass

        prompt = INTENT_PROMPT.format(history=history, question=question)

        try:
            response = await self.llm._call_llm(
                [{"role": "user", "content": prompt}],
                temperature=0
            )
            json_match = re.search(r'\{[^{}]*\}', response)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "type": result.get("type", "other"),
                    "complexity": result.get("complexity", "single_step"),
                }
        except Exception as e:
            print(f"[IntentRouter] LLM 分类失败: {e}")

        return {"type": "other", "complexity": "single_step"}


# ═══════════════════════════════════════════════════════════════════════
# PlannerRouter — Agent 决策体接口（LLM-as-Planner）
# mode=planner 时使用，LLM 看到工具列表后自行规划步骤
# ═══════════════════════════════════════════════════════════════════════

PLANNER_SYSTEM_PROMPT = """你是招投标智能问答系统的决策体（Planner）。

你的任务是：分析用户问题，规划需要执行哪些步骤，然后输出执行计划。

## 可用工具
{tools_description}

## 输出格式（严格的 JSON）
{{
    "plan": [
        {{"step": 1, "tool": "工具名", "params": {{"参数名": "值"}}, "reason": "为什么需要这一步"}}
    ],
    "parallel": [[1, 2]],  // 哪些步骤可以并行执行
    "confidence": 0.9       // 你对计划的信心程度
}}

## 规则
1. 分析问题包含几个子问题
2. 为每个子问题选择合适的工具
3. 标记可并行的步骤
4. 如果无法确定，confidence 设为 0.5 以下
5. 只输出 JSON，不要输出其他内容
"""


class PlannerRouter:
    """Agent 决策体 — LLM 自己规划步骤"""

    def __init__(self, llm=None):
        self.llm = llm
        self._tools_description = ""

    def set_tools(self, tools: Dict[str, str]):
        """注册可用工具及其描述"""
        lines = [f"- {name}: {desc}" for name, desc in tools.items()]
        self._tools_description = "\n".join(lines)

    async def plan(self, question: str) -> Dict:
        """LLM 规划执行步骤"""
        if not self.llm:
            return {"plan": [], "parallel": [], "confidence": 0}

        prompt = PLANNER_SYSTEM_PROMPT.format(
            tools_description=self._tools_description or "search_regulations: 检索法规\nsql_query: 统计查询\nget_article: 查法条"
        )

        try:
            response = await self.llm._call_llm([
                {"role": "system", "content": prompt},
                {"role": "user", "content": question}
            ], temperature=settings.planner_temperature if hasattr(settings, 'planner_temperature') else 0.2)

            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            print(f"[Planner] 规划失败: {e}")

        return {"plan": [], "parallel": [], "confidence": 0, "error": "planning failed"}


# ═══════════════════════════════════════════════════════════════════════
# 统一路由工厂
# ═══════════════════════════════════════════════════════════════════════

def create_router(llm=None):
    """根据配置创建路由实例"""
    mode = settings.router_mode

    if mode == "binary":
        print("[RouterFactory] 创建 BinaryRouter (3路投票, is_sql判定)")
        return BinaryRouter()

    elif mode == "intent":
        print("[RouterFactory] 创建 IntentRouter (LLM意图分类)")
        return IntentRouter(llm=llm)

    elif mode == "planner":
        print("[RouterFactory] 创建 PlannerRouter (Agent决策体)")
        router = PlannerRouter(llm=llm)
        # 注册默认工具
        router.set_tools({
            "search_regulations": "语义检索招投标法规知识库",
            "get_article": "精确查询特定法条的第X条内容",
            "sql_query": "对招标数据库执行统计查询",
        })
        return router

    else:
        print(f"[RouterFactory] 未知模式 '{mode}'，使用 BinaryRouter")
        return BinaryRouter()
