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

    async def route(self, query: str, **kwargs) -> Dict[str, Any]:
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


def quick_intercept(question: str) -> Optional[Dict]:
    """快速拦截问候/致谢/告别/无关问题 — 纯关键词，零 LLM 调用"""
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


class IntentRouter:
    """LLM 意图分类器 — 判断问题类型和复杂度 (保留向后兼容)"""

    def __init__(self, llm=None):
        self.llm = llm

    async def route(self, question: str, session_id: str = "", session_manager=None) -> Dict:
        """LLM 意图分类"""
        intercepted = quick_intercept(question)
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
# PlannerRouter — Agent 决策体（LLM-as-Planner）
# mode=planner 时使用，LLM 看到工具列表后自行规划执行步骤
# ═══════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════
# Planner 两阶段 Prompt
#   阶段1: TaskAnalysis  — 只分析用户意图，拆任务 + 依赖关系（不涉及工具）
#   阶段2: ToolPlanning  — 根据任务列表 + 工具描述，规划执行步骤
# ═══════════════════════════════════════════════════════════════════════

TASK_ANALYSIS_PROMPT = """你是招投标问答系统的任务分析器。你的工作只有一个：理解用户问题，拆解为需要完成的任务。

不要考虑用什么工具、怎么执行。只思考：回答这个问题，需要收集哪些数据？

## 依赖关系 (depends_on)
有些任务需要等前序任务的结果才能开始。例如：
- "围标和串标的区别" → 先查围标(t1)、再查串标(t2)、最后对比(t3)，t3 依赖 t1 和 t2

用 depends_on 标注这种关系：tasks 里排在前面的 task_id，后面的可以引用。

## 输出格式
{{
    "analysis": "一句话说清用户想干什么",
    "tasks": [
        {{"task_id": "t1", "goal": "需要收集什么数据", "depends_on": []}},
        {{"task_id": "t2", "goal": "...", "depends_on": ["t1"]}}
    ],
    "confidence": 0.85
}}

边界情况：
- 简单问题 1 个 task，depends_on 为空
- 复合问题拆多个 task，互不依赖的不写 depends_on
- 对比类问题的最后一步（对比本身）依赖前面的数据收集步骤
- 问题模糊无法确定意图 → confidence < 0.4，按最合理解读拆
- 明显不涉及招投标 → tasks 为空，confidence < 0.3

只输出 JSON，不要 markdown，不要额外解释。"""


TOOL_PLANNING_PROMPT = """你是招投标问答系统的工具规划器。你的工作：根据任务列表，为每个任务选择合适的工具和执行步骤。

## 可用工具
{tools_description}

## 需要完成的任务
{tasks_json}

## 用户原始问题
{question}

## 输出格式
{{
    "plan": [
        {{"step": 1, "task_id": "t1", "tool": "工具名", "params": {{"key": "value"}}, "reason": "这个工具如何服务于 task goal"}}
    ]
}}

规划要点：
- 每个 task 至少 1 个 step，匹配最合适的工具
- params 要具体化（"去年"→"2025年"，"围标"→"串通投标围标"）
- 如果 task goal 没有完美匹配的工具，选最接近的，在 reason 里说明

只输出 JSON。"""


class PlannerRouter:
    """Agent 决策体 — LLM 生成执行计划

    与 ReActAgent 的分工:
        PlannerRouter: 只负责"想" — LLM 分析问题，输出计划 JSON
        PlannerExecutor: 只负责"做" — 解析 JSON，执行工具，汇总结果

    用法:
        router = PlannerRouter(llm=generator)
        router.set_tools({...})
        plan = await router.plan("围标怎么处罚")
        # plan = {"analysis": "...", "tasks": [...], "plan": [...], "confidence": 0.9}
    """

    def __init__(self, llm=None):
        self.llm = llm
        self._tools_description = ""

    def set_tools(self, tools: Dict[str, str]):
        """注册可用工具及其描述

        Args:
            tools: {"search_regulations": "描述...", "sql_query": "描述..."}
        """
        lines = [f"- {name}: {desc}" for name, desc in tools.items()]
        self._tools_description = "\n".join(lines)

    def _default_tools_description(self) -> str:
        """默认工具描述（确保即使没调用 set_tools 也能工作）"""
        return (
            "search_regulations: 语义检索招投标法规知识库，查询概念定义、处罚规定、操作流程\n"
            "get_article: 精确查询特定法条的第X条完整内容\n"
            "sql_query: 对招标数据库执行统计查询，返回数量、金额、排名等结构化数据\n"
            "summarize: 将多段检索结果归纳总结成结构化回答"
        )

    async def plan(self, question: str) -> Dict:
        """两阶段规划: Task分析 → 工具规划

        Call 1 (Task Analysis): 理解用户意图，拆解任务 + 依赖关系
        Call 2 (Tool Planning): 根据任务列表 + 工具描述，规划具体执行步骤

        Returns:
            {"analysis": "...", "tasks": [...], "plan": [...], "confidence": 0.9}
            失败时返回降级计划（一条 search_regulations）
        """
        if not self.llm:
            return self._fallback_plan(question, reason="LLM 未初始化")

        try:
            # ── Call 1: Task Analysis ──
            task_prompt = TASK_ANALYSIS_PROMPT + f"\n\n用户问题：{question}\n请输出任务JSON："
            task_response = await self.llm._call_llm(
                prompt=task_prompt,
                temperature=getattr(settings, 'planner_temperature', 0.2),
            )
            task_result = self._parse_plan_response(task_response, question)

            if not task_result or not task_result.get("tasks"):
                print(f"[Planner] Task分析失败，LLM原始响应({len(task_response)} chars): {task_response[:200]}")
                return self._fallback_plan(question, reason="Task分析失败 - 无有效tasks")

            tasks = task_result["tasks"]
            analysis = task_result.get("analysis", "")
            confidence = task_result.get("confidence", 0.5)

            print(f"[Planner] Task分析: {len(tasks)} 任务, confidence={confidence:.2f}")
            for t in tasks:
                deps = f" ⬅ {t.get('depends_on', [])}" if t.get("depends_on") else ""
                print(f"  {t['task_id']}: {t['goal']}{deps}")

            # ── Call 2: Tool Planning ──
            tasks_json = json.dumps(tasks, ensure_ascii=False)
            tools_desc = self._tools_description or self._default_tools_description()
            plan_prompt = TOOL_PLANNING_PROMPT.format(
                tools_description=tools_desc,
                tasks_json=tasks_json,
                question=question,
            )
            plan_response = await self.llm._call_llm(
                prompt=plan_prompt,
                temperature=getattr(settings, 'planner_temperature', 0.2),
            )
            plan_result = self._parse_plan_response(plan_response, question)

            if not plan_result or not plan_result.get("plan"):
                print(f"[Planner] Tool规划失败，LLM原始响应({len(plan_response)} chars): {plan_response[:200]}")
                return self._fallback_plan(question, reason="Tool规划失败 - 无有效plan")

            plan_steps = plan_result.get("plan", [])

            result = {
                "analysis": analysis,
                "tasks": tasks,
                "plan": plan_steps,
                "confidence": confidence,
            }
            print(f"[Planner] 规划完成: {len(plan_steps)} 步, "
                  f"{len(tasks)} 任务, confidence={confidence:.2f}")
            return result

        except Exception as e:
            print(f"[Planner] 规划异常: {type(e).__name__}: {e}")

        return self._fallback_plan(question, reason="LLM 规划失败")

    async def plan_from_tasks(self, tasks: List[Dict], question: str) -> Dict:
        """跳过 TaskAnalysis，直接从已有 tasks 做 ToolPlanning

        ThinkRouter 已做完 Task 分解，这里只需补上工具规划。
        """
        if not self.llm:
            return self._fallback_plan(question, reason="LLM未初始化")

        try:
            tasks_json = json.dumps(tasks, ensure_ascii=False)
            tools_desc = self._tools_description or self._default_tools_description()
            plan_prompt = TOOL_PLANNING_PROMPT.format(
                tools_description=tools_desc,
                tasks_json=tasks_json,
                question=question,
            )
            plan_response = await self.llm._call_llm(
                prompt=plan_prompt,
                temperature=getattr(settings, 'planner_temperature', 0.2),
            )
            plan_result = self._parse_plan_response(plan_response, question)

            if plan_result and plan_result.get("plan"):
                return {
                    "analysis": "",
                    "tasks": tasks,
                    "plan": plan_result.get("plan", []),
                    "confidence": 0.8,
                }
        except Exception as e:
            print(f"[Planner] plan_from_tasks 失败: {e}")

        return self._fallback_plan(question, reason="Tool规划失败")

    def _parse_plan_response(self, response: str, question: str) -> Optional[Dict]:
        """从 LLM 原始输出中提取计划 JSON

        处理常见 LLM 输出瑕疵:
        - ```json ... ``` 代码块包裹
        - 多余的空白字符
        - JSON 尾部多余逗号
        - 嵌套在说明文字中的 JSON
        """
        # 1. 去掉 markdown 代码块
        cleaned = re.sub(r'```(?:json)?\s*', '', response)
        cleaned = re.sub(r'```', '', cleaned)

        # 2. 提取 JSON 对象
        json_match = re.search(r'\{[\s\S]*\}', cleaned)
        if not json_match:
            return None

        json_str = json_match.group()

        # 3. 修复尾部多余逗号（LLM 常见错误）
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # 4. 更激进的修复: 尝试逐行清理
            try:
                # 移除非 JSON 行
                lines = json_str.split('\n')
                clean_lines = []
                in_json = False
                for line in lines:
                    if '{' in line:
                        in_json = True
                    if in_json:
                        clean_lines.append(line)
                    if '}' in line:
                        break
                return json.loads('\n'.join(clean_lines))
            except json.JSONDecodeError:
                pass

        return None

    def _fallback_plan(self, question: str, reason: str = "") -> Dict:
        """当 LLM 规划失败时，生成降级计划

        降级策略: 用 search_regulations 直接检索，保证系统可用
        """
        print(f"[Planner] 使用降级计划 (reason={reason})")
        return {
            "analysis": f"降级: {reason}",
            "tasks": [
                {"task_id": "t1", "goal": "直接检索相关信息", "depends_on": []}
            ],
            "plan": [
                {
                    "step": 1,
                    "task_id": "t1",
                    "tool": "search_regulations",
                    "params": {"query": question},
                    "reason": f"自动降级检索 ({reason})",
                }
            ],
            "confidence": 0.3,
            "fallback": True,
            "fallback_reason": reason,
        }

    async def route(self, question: str, **kwargs) -> Dict:
        """统一路由接口 — 与 BinaryRouter.route() 保持接口兼容

        Returns:
            {"mode": "planner", "plan": {...}, "is_sql": None}
            is_sql 为 None 表示由 Planner 自行决定（可能混合 SQL + RAG）
        """
        plan = await self.plan(question)
        return {
            "mode": "planner",
            "is_sql": None,          # Planner 模式下不预判，交给计划决定
            "plan": plan,
            "votes": {"planner": True},
        }


# ═══════════════════════════════════════════════════════════════════════
# AutoRouter — 自适应路由: IntentRouter 判复杂度 → 简单直走, 复杂走 Planner
# ═══════════════════════════════════════════════════════════════════════

class AutoRouter:
    """自适应路由: 意图分类 → 按复杂度分流

    Question
      → IntentRouter (type + complexity)
          ├─ greeting/thanks/unrelated → 快速响应
          ├─ stat_query → SQL 路径 (BinaryRouter 模板匹配)
          ├─ single_step → 直接 RAG (search_unified)
          └─ multi_step  → PlannerRouter 规划 → PlannerExecutor DAG 执行
    """

    def __init__(self, llm=None):
        self.intent_router = IntentRouter(llm=llm)
        self.planner_router = PlannerRouter(llm=llm)
        self.planner_router.set_tools({
            "search_regulations": "统一检索招投标知识库（法规条文 + 招标项目案例）",
            "get_article": "精确查询特定法条的第X条完整内容",
            "sql_query": "对招标数据库执行统计查询，返回数量、金额、排名等结构化数据",
        })
        self._binary_router = None

    @property
    def binary_router(self):
        if self._binary_router is None:
            self._binary_router = BinaryRouter()
        return self._binary_router

    async def route(self, question: str, session_id: str = "",
                    session_manager=None) -> Dict:
        """自适应路由：意图分类 → 按复杂度分流"""
        # ── Step 1: 意图分类 ──
        intent = await self.intent_router.route(
            question, session_id, session_manager
        )

        intent_type = intent.get("type", "other")
        complexity = intent.get("complexity", "single_step")

        print(f"[AutoRouter] type={intent_type}, complexity={complexity}")

        # ── 快速响应 (问候/致谢/无关) ──
        if intent_type in ("quick_response", "unrelated"):
            return {
                "mode": "direct",
                "is_sql": False,
                "intent": intent,
                "direct_answer": intent.get("response", ""),
            }

        # ── 统计类 → SQL 路径 ──
        if intent_type == "stat_query":
            binary = await self.binary_router.route(question)
            print(f"[AutoRouter] 统计类 → SQL路径 "
                  f"(match={binary.get('match_score', 0):.3f})")
            return {
                "mode": "auto",
                "is_sql": True,
                "sql_template": binary.get("sql_template"),
                "match_score": binary.get("match_score", 0),
                "intent": intent,
            }

        # ── 复杂问题 → Planner DAG ──
        if complexity == "multi_step":
            print(f"[AutoRouter] 复杂问题 → Planner 路径")
            plan = await self.planner_router.plan(question)
            return {
                "mode": "planner",
                "is_sql": None,
                "plan": plan,
                "intent": intent,
            }

        # ── 简单问题 → 直接 RAG ──
        print(f"[AutoRouter] 简单问题 → 直接 RAG")
        return {
            "mode": "auto",
            "is_sql": False,
            "intent": intent,
        }


# ═══════════════════════════════════════════════════════════════════════
# FastRouter — 快速模式: 不走 Agent 规划，BinaryRouter 直接判 SQL vs RAG
# ═══════════════════════════════════════════════════════════════════════

class FastRouter:
    """快速模式: 关键词拦截 + BinaryRouter 三路投票判 SQL/RAG

    零 LLM 规划开销，适合大多数简单问答和统计查询。
    """

    def __init__(self, llm=None):
        self.llm = llm
        self._binary = None

    @property
    def binary(self):
        if self._binary is None:
            self._binary = BinaryRouter()
        return self._binary

    async def route(self, question: str, session_id: str = "",
                    session_manager=None) -> Dict:
        # ── 1. 关键词快速拦截 ──
        intercepted = quick_intercept(question)
        if intercepted:
            if intercepted.get("type") == "quick_response":
                return {
                    "mode": "direct",
                    "is_sql": False,
                    "direct_answer": intercepted.get("response", ""),
                }
            if intercepted.get("type") == "unrelated":
                return {
                    "mode": "direct",
                    "is_sql": False,
                    "direct_answer": "抱歉，我是招投标领域的智能助手，无法回答这个问题。",
                }

        # ── 2. BinaryRouter 判 SQL vs RAG ──
        result = await self.binary.route(question)
        is_sql = result["is_sql"]
        print(f"[FastRouter] is_sql={is_sql} "
              f"(rule={'Y' if result['votes'].get('rule') else 'N'} "
              f"emb={'Y' if result['votes'].get('embedding') else 'N'} "
              f"llm={'Y' if result['votes'].get('llm') else 'N'})")

        return {
            "mode": "auto",
            "is_sql": is_sql,
            "sql_template": result.get("sql_template"),
            "match_score": result.get("match_score", 0),
            "votes": result.get("votes", {}),
        }


# ═══════════════════════════════════════════════════════════════════════
# ThinkRouter — 思考模式: TaskAnalysis → task 数量 → 分流
# ═══════════════════════════════════════════════════════════════════════

class ThinkRouter:
    """思考模式: 先做 Task 分解 → 基于实际 task 数量决定路由

    - 1 个 task: 兼容输出，BinaryRouter 判 SQL vs RAG
    - 2+ 个 task: PlannerRouter ToolPlanning → PlannerExecutor DAG
    - 低置信度 / 0 task: 降级到 BinaryRouter

    复杂度判定不再"拍脑袋"——先分解再决定。
    """

    def __init__(self, llm=None):
        self.llm = llm
        self._binary = None
        self._planner = None

    @property
    def binary(self):
        if self._binary is None:
            self._binary = BinaryRouter()
        return self._binary

    @property
    def planner_router(self):
        if self._planner is None:
            self._planner = PlannerRouter(llm=self.llm)
        return self._planner

    async def route(self, question: str, session_id: str = "",
                    session_manager=None) -> Dict:
        # ── 1. 关键词快速拦截 ──
        intercepted = quick_intercept(question)
        if intercepted:
            if intercepted.get("type") == "quick_response":
                return {
                    "mode": "direct",
                    "is_sql": False,
                    "direct_answer": intercepted.get("response", ""),
                }
            if intercepted.get("type") == "unrelated":
                return {
                    "mode": "direct",
                    "is_sql": False,
                    "direct_answer": "抱歉，我是招投标领域的智能助手，无法回答这个问题。",
                }

        # ── 2. TaskAnalysis — 1 次 LLM 调用 ──
        task_result = await self._task_analysis(question)
        tasks = task_result.get("tasks", [])
        confidence = task_result.get("confidence", 0.5)
        analysis = task_result.get("analysis", "")

        print(f"[ThinkRouter] {len(tasks)} tasks, confidence={confidence:.2f}")

        # ── 3. 低置信度或无任务 → 降级 BinaryRouter ──
        if confidence < 0.3 or not tasks:
            print(f"[ThinkRouter] 降级到快速路由 (confidence={confidence:.2f})")
            result = await self.binary.route(question)
            return {
                "mode": "auto",
                "is_sql": result["is_sql"],
                "sql_template": result.get("sql_template"),
                "match_score": result.get("match_score", 0),
            }

        # ── 4. 单任务 → 兼容输出: BinaryRouter 判 SQL/RAG ──
        if len(tasks) == 1:
            task = tasks[0]
            search_query = task.get("goal", question)
            result = await self.binary.route(search_query)
            print(f"[ThinkRouter] 单任务 '{task.get('task_id', 't1')}' → "
                  f"is_sql={result['is_sql']}")
            return {
                "mode": "auto",
                "is_sql": result["is_sql"],
                "sql_template": result.get("sql_template"),
                "match_score": result.get("match_score", 0),
                "analysis": analysis,
                "tasks": tasks,
            }

        # ── 5. 多任务 → Planner DAG ──
        for t in tasks:
            deps = f" ← {t.get('depends_on', [])}" if t.get("depends_on") else ""
            print(f"  {t['task_id']}: {t['goal']}{deps}")

        plan = await self.planner_router.plan_from_tasks(tasks, question)
        print(f"[ThinkRouter] → Planner DAG ({len(plan.get('plan', []))} steps)")
        return {
            "mode": "planner",
            "plan": plan,
            "analysis": analysis,
        }

    async def _task_analysis(self, question: str) -> Dict:
        """调用 LLM 做 Task 分解"""
        if not self.llm:
            return {"tasks": [], "confidence": 0.0}

        prompt = TASK_ANALYSIS_PROMPT + f"\n\n用户问题：{question}\n请输出任务JSON："
        try:
            response = await self.llm._call_llm(
                prompt=prompt,
                temperature=getattr(settings, 'planner_temperature', 0.2),
            )
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                json_str = json_match.group()
                json_str = re.sub(r',\s*}', '}', json_str)
                json_str = re.sub(r',\s*]', ']', json_str)
                return json.loads(json_str)
        except Exception as e:
            print(f"[ThinkRouter] Task分析失败: {e}")

        return {"tasks": [], "confidence": 0.0}


# ═══════════════════════════════════════════════════════════════════════
# 统一路由工厂
# ═══════════════════════════════════════════════════════════════════════

def create_router(llm=None):
    """根据配置创建路由实例"""
    mode = settings.router_mode

    if mode == "fast":
        print("[RouterFactory] 创建 FastRouter (快速模式: BinaryRouter 判 SQL/RAG)")
        return FastRouter(llm=llm)

    elif mode == "think":
        print("[RouterFactory] 创建 ThinkRouter (思考模式: TaskAnalysis → 按 task 数分流)")
        router = ThinkRouter(llm=llm)
        router.planner_router.set_tools({
            "search_regulations": "统一检索招投标知识库（法规条文 + 招标项目案例）",
            "get_article": "精确查询特定法条的第X条完整内容",
            "sql_query": "对招标数据库执行统计查询",
        })
        return router

    elif mode == "binary":
        print("[RouterFactory] 创建 BinaryRouter (3路投票, is_sql判定)")
        return BinaryRouter()

    elif mode == "intent":
        print("[RouterFactory] 创建 IntentRouter (LLM意图分类)")
        return IntentRouter(llm=llm)

    elif mode == "planner":
        print("[RouterFactory] 创建 PlannerRouter (Agent决策体)")
        router = PlannerRouter(llm=llm)
        router.set_tools({
            "search_regulations": "语义检索招投标法规知识库",
            "get_article": "精确查询特定法条的第X条内容",
            "sql_query": "对招标数据库执行统计查询",
        })
        return router

    elif mode == "auto":
        print("[RouterFactory] 创建 AutoRouter (自适应路由: Intent判复杂度 → 简单/复杂分流)")
        return AutoRouter(llm=llm)

    else:
        print(f"[RouterFactory] 未知模式 '{mode}'，使用 BinaryRouter")
        return BinaryRouter()
