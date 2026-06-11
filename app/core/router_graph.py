# -*- coding: utf-8 -*-
"""LangGraph 路由状态机 — ThinkRouter: TaskAnalysis → 按task数分流

Graph flow:
    quick_intercept
      ├─ greeting/unrelated → direct_response → END
      └─ (need analysis) → task_analysis
                              ├─ low conf / 0 tasks → binary_classify → END
                              ├─ 1 task → binary_classify → END
                              └─ 2+ tasks → tool_planning → END
"""

import json
import re
from typing import TypedDict, Optional, List, Dict, Any

import numpy as np
import httpx

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from config import settings


def _sync_llm_call(messages: List[Dict], temperature: float = 0.2, max_tokens: int = 500) -> str:
    """同步 LLM 调用 — 供 LangGraph 节点使用（节点必须同步）"""
    try:
        resp = httpx.post(
            settings.llm_api_url,
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json={
                "model": settings.llm_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=settings.llm_timeout,
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        return ""
    except Exception as e:
        print(f"[sync_llm_call] Error: {e}")
        return ""


# ═══════════════════════════════════════════════════════════════════
# State Definition
# ═══════════════════════════════════════════════════════════════════

class RouterState(TypedDict, total=False):
    question: str
    session_id: str
    session_manager: Any
    llm: Any
    # Intercept outputs
    intercepted_type: str           # "quick_response" | "unrelated" | None
    direct_answer: str
    # Task analysis outputs
    tasks: List[Dict]
    confidence: float
    analysis: str
    # Binary classify outputs
    is_sql: bool
    sql_template: Optional[str]
    match_score: float
    votes: Dict[str, Any]
    # Tool planning outputs
    plan: Dict
    # Final routing decision
    mode: str                       # "direct" | "auto" | "planner"


# ═══════════════════════════════════════════════════════════════════
# Prompt Templates
# ═══════════════════════════════════════════════════════════════════

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
- 统计类问题（"多少"、"排名"、"汇总"）→ 1 个 task, confidence ≥ 0.8

只输出 JSON，不要 markdown，不要额外解释。"""


TOOL_PLANNING_PROMPT = """你是招投标问答系统的工具规划器。根据任务列表，为每个任务选择合适的工具和执行步骤。

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


# ═══════════════════════════════════════════════════════════════════
# Keyword Intercept (zero LLM)
# ═══════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════
# SQL Template Bank + Binary Classification
# ═══════════════════════════════════════════════════════════════════

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

COMPLIANCE_TEMPLATES = [
    "投标保证金可以没收吗", "围标串标怎么认定", "招标文件歧视性条款怎么维权",
    "中标后可以废标吗", "分包转包有什么区别", "投标有效期过了怎么办",
    "招标公告发布要求是什么", "评标委员会怎么组成", "低于成本价投标怎么处理",
    "联合体投标有什么资质要求", "质疑和投诉的流程是什么", "招标投标保密要求有哪些",
    "合同签订期限是多久", "履约保证金怎么退", "招标投标违法行为怎么处罚",
    "投标人弄虚作假怎么处理", "招标文件澄清或修改有什么规定",
    "法定否决投标的情形有哪些", "投标人少于三个怎么办", "招标代理机构有什么禁止行为",
]

AGGREGATION_TRIGGERS = [
    "总共", "一共", "最高", "最低", "平均", "最多", "最少",
    "排名", "汇总", "统计", "数量", "总金额", "多少条",
    "多少个", "多少家", "哪家", "哪些公司", "列出",
]
TIME_TRIGGERS = [
    "去年", "今年", "本月", "上个月",
    "2023", "2024", "2025", "上一年", "本年度", "近期",
]
COMPLIANCE_BLOCKERS = [
    "才能", "才可以", "可以吗", "算违规", "有效吗", "合法吗",
    "符合规定", "应当", "不得", "依法", "必须招标",
    "禁止", "责令", "处罚", "罚款",
]

TEMPLATE_MATCH_THRESHOLD = 0.92


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


# ═══════════════════════════════════════════════════════════════════
# BinaryRouter embedding warmup (module-level cache)
# ═══════════════════════════════════════════════════════════════════

_template_vectors: List[np.ndarray] = []
_compliance_vectors: List[np.ndarray] = []
_warmup_done = False


def _warmup():
    global _template_vectors, _compliance_vectors, _warmup_done
    if _warmup_done:
        return
    from app.core.embedding import EmbeddingService
    es = EmbeddingService()
    sql_questions = [t["question"] for t in SQL_TEMPLATES]
    sql_vectors = es.embed_batch(sql_questions)
    _template_vectors = [np.array(v) for v in sql_vectors]
    compliance_vectors = es.embed_batch(COMPLIANCE_TEMPLATES)
    _compliance_vectors = [np.array(v) for v in compliance_vectors]
    _warmup_done = True
    print(f"[RouterGraph] Warmup done ({len(SQL_TEMPLATES)} SQL + {len(COMPLIANCE_TEMPLATES)} compliance templates)")


# ═══════════════════════════════════════════════════════════════════
# Graph Nodes
# ═══════════════════════════════════════════════════════════════════

def _quick_intercept_node(state: RouterState) -> dict:
    """Zero-LLM keyword intercept for greetings/thanks/unrelated"""
    if not settings.intent_quick_intercept:
        return {"intercepted_type": None, "direct_answer": ""}

    q = state["question"].strip().lower()
    q_clean = re.sub(r'[^一-龥a-zA-Z0-9]', '', q)

    for kw in GREETING_KEYWORDS:
        if kw in q_clean:
            return {"intercepted_type": "quick_response",
                    "direct_answer": "您好！我是招投标智能助手，请问有什么可以帮您？"}

    for kw in THANKS_KEYWORDS:
        if kw in q_clean:
            return {"intercepted_type": "quick_response",
                    "direct_answer": "不客气，有问题随时问我！"}

    for kw in GOODBYE_KEYWORDS:
        if kw in q_clean:
            return {"intercepted_type": "quick_response",
                    "direct_answer": "再见！如有问题，随时回来咨询。"}

    has_bidding = any(kw in q for kw in BIDDING_KEYWORDS)
    if not has_bidding:
        for kw in UNRELATED_KEYWORDS:
            if kw in q:
                return {"intercepted_type": "unrelated",
                        "direct_answer": "抱歉，我是招投标领域的智能助手，无法回答这个问题。"}

    return {"intercepted_type": None, "direct_answer": ""}


def _task_analysis_node(state: RouterState) -> dict:
    """LLM Task Analysis — 分解用户问题为任务列表"""
    question = state["question"]

    prompt = TASK_ANALYSIS_PROMPT + f"\n\n用户问题：{question}\n请输出任务JSON："
    response = _sync_llm_call(
        [{"role": "user", "content": prompt}],
        temperature=getattr(settings, 'planner_temperature', 0.2),
    )

    if not response:
        return {"tasks": [], "confidence": 0.0, "analysis": "LLM调用失败"}

    json_match = re.search(r'\{[\s\S]*\}', response)
    if json_match:
        try:
            json_str = json_match.group()
            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)
            result = json.loads(json_str)
            tasks = result.get("tasks", [])
            confidence = result.get("confidence", 0.5)
            analysis = result.get("analysis", "")
            print(f"[RouterGraph] TaskAnalysis: {len(tasks)} tasks, confidence={confidence:.2f}")
            for t in tasks:
                deps = f" < {t.get('depends_on', [])}" if t.get("depends_on") else ""
                print(f"  {t['task_id']}: {t['goal']}{deps}")
            return {"tasks": tasks, "confidence": confidence, "analysis": analysis}
        except json.JSONDecodeError:
            pass

    return {"tasks": [], "confidence": 0.0, "analysis": "Task分析JSON解析失败"}


def _binary_classify_node(state: RouterState) -> dict:
    """3-way vote: rule + embedding + LLM → is_sql + template match"""
    _warmup()
    question = state["question"]

    # Rule-based
    has_agg = any(t in question for t in AGGREGATION_TRIGGERS)
    has_time = any(t in question for t in TIME_TRIGGERS)
    has_blocker = any(t in question for t in COMPLIANCE_BLOCKERS)
    rule_is_sql = (has_agg or has_time) and not has_blocker

    # Embedding-based
    from app.core.embedding import EmbeddingService
    es = EmbeddingService()
    query_vec = np.array(es.embed_query(question))

    sql_max = max(_cosine_similarity(query_vec, tv) for tv in _template_vectors) if _template_vectors else 0
    compliance_max = max(_cosine_similarity(query_vec, cv) for cv in _compliance_vectors) if _compliance_vectors else 0
    embedding_is_sql = sql_max > compliance_max

    # LLM-based (sync HTTP)
    llm_is_sql = None
    response = _sync_llm_call(
        [
            {"role": "system", "content": (
                "你是招投标问答系统的意图分类器。"
                "判断用户问题应该用哪种方式回答：\n"
                "- SQL：问题需要统计数据库中的招标项目数量、金额、排名等\n"
                "- RAG：问题在问招投标法律法规、合规要求、操作流程等\n"
                "只回复 'SQL' 或 'RAG'，不要解释。"
            )},
            {"role": "user", "content": question}
        ],
        temperature=0, max_tokens=5,
    )
    if response:
        llm_is_sql = response.strip().upper().startswith("SQL")

    # Vote
    votes = [rule_is_sql, embedding_is_sql, llm_is_sql]
    valid = [v for v in votes if v is not None]
    is_sql = sum(valid) >= len(valid) / 2

    # SQL template match
    sql_template = None
    match_score = 0.0
    if is_sql:
        best_score = -1.0
        best_idx = -1
        for i, tv in enumerate(_template_vectors):
            sim = _cosine_similarity(query_vec, tv)
            if sim > best_score:
                best_score = sim
                best_idx = i
        match_score = best_score
        if best_score >= TEMPLATE_MATCH_THRESHOLD and best_idx >= 0:
            sql_template = SQL_TEMPLATES[best_idx]["sql"]

    print(f"[RouterGraph] BinaryClassify: is_sql={is_sql} "
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


def _tool_planning_node(state: RouterState) -> dict:
    """LLM Tool Planning — 为多任务场景规划工具步骤"""
    tasks = state.get("tasks", [])
    question = state["question"]

    if not tasks:
        return {"plan": _fallback_plan(question, "无tasks")}

    tools_description = (
        "search_regulations: 语义检索招投标法规知识库，查询概念定义、处罚规定、操作流程\n"
        "get_article: 精确查询特定法条的第X条完整内容\n"
        "sql_query: 对招标数据库执行统计查询，返回数量、金额、排名等结构化数据\n"
        "summarize: 将多段检索结果归纳总结成结构化回答"
    )

    tasks_json = json.dumps(tasks, ensure_ascii=False)
    prompt = TOOL_PLANNING_PROMPT.format(
        tools_description=tools_description,
        tasks_json=tasks_json,
        question=question,
    )

    response = _sync_llm_call(
        [{"role": "user", "content": prompt}],
        temperature=getattr(settings, 'planner_temperature', 0.2),
    )

    if response:
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                json_str = json_match.group()
                json_str = re.sub(r',\s*}', '}', json_str)
                json_str = re.sub(r',\s*]', ']', json_str)
                result = json.loads(json_str)
                plan_steps = result.get("plan", [])
                print(f"[RouterGraph] ToolPlanning: {len(plan_steps)} steps")
                return {
                    "plan": {
                        "analysis": state.get("analysis", ""),
                        "tasks": tasks,
                        "plan": plan_steps,
                        "confidence": state.get("confidence", 0.8),
                    }
                }
            except json.JSONDecodeError:
                pass

    return {"plan": _fallback_plan(question, "Tool规划失败")}


def _fallback_plan(question: str, reason: str) -> dict:
    return {
        "analysis": f"降级: {reason}",
        "tasks": [{"task_id": "t1", "goal": "直接检索相关信息", "depends_on": []}],
        "plan": [{"step": 1, "task_id": "t1", "tool": "search_regulations",
                  "params": {"query": question}, "reason": f"自动降级 ({reason})"}],
        "confidence": 0.3,
        "fallback": True,
        "fallback_reason": reason,
    }


# ═══════════════════════════════════════════════════════════════════
# Conditional Edge Functions
# ═══════════════════════════════════════════════════════════════════

def _route_after_intercept(state: RouterState) -> str:
    itype = state.get("intercepted_type")
    if itype in ("quick_response", "unrelated"):
        return "direct"
    return "task_analysis"


def _route_after_task_analysis(state: RouterState) -> str:
    tasks = state.get("tasks", [])
    confidence = state.get("confidence", 0.5)

    if confidence < 0.3 or not tasks:
        print(f"[RouterGraph] Low confidence / 0 tasks → BinaryClassify")
        return "binary_classify"

    if len(tasks) == 1:
        print(f"[RouterGraph] 1 task → BinaryClassify (SQL/RAG)")
        return "binary_classify"

    print(f"[RouterGraph] {len(tasks)} tasks → ToolPlanning (Planner DAG)")
    return "tool_planning"


# ═══════════════════════════════════════════════════════════════════
# Graph Construction
# ═══════════════════════════════════════════════════════════════════

def build_think_router_graph() -> CompiledStateGraph:
    """构建 ThinkRouter LangGraph: TaskAnalysis → 按 task 数分流"""
    graph = StateGraph(RouterState)

    # Add nodes
    graph.add_node("quick_intercept", _quick_intercept_node)
    graph.add_node("task_analysis", _task_analysis_node)
    graph.add_node("binary_classify", _binary_classify_node)
    graph.add_node("tool_planning", _tool_planning_node)

    # Set entry
    graph.set_entry_point("quick_intercept")

    # Conditional edge from quick_intercept
    graph.add_conditional_edges(
        "quick_intercept",
        _route_after_intercept,
        {"direct": END, "task_analysis": "task_analysis"}
    )

    # Conditional edge from task_analysis
    graph.add_conditional_edges(
        "task_analysis",
        _route_after_task_analysis,
        {"binary_classify": "binary_classify", "tool_planning": "tool_planning"}
    )

    # Binary classify and tool planning both go to END
    graph.add_edge("binary_classify", END)
    graph.add_edge("tool_planning", END)

    return graph.compile()


# ═══════════════════════════════════════════════════════════════════
# Compatibility Wrapper — implements .route() for routes.py
# ═══════════════════════════════════════════════════════════════════

class LangGraphRouter:
    """LangGraph 路由器 — 替代旧 BinaryRouter/IntentRouter/PlannerRouter/AutoRouter/ThinkRouter"""

    def __init__(self, llm=None):
        self.llm = llm
        self._graph = build_think_router_graph()
        print("[LangGraphRouter] ThinkRouter graph compiled")

    async def route(self, question: str, session_id: str = "",
                    session_manager=None) -> dict:
        """执行 LangGraph 路由，返回兼容旧格式的 dict"""
        state: RouterState = {
            "question": question,
            "session_id": session_id,
            "session_manager": session_manager,
            "llm": self.llm,
            # Defaults
            "intercepted_type": None,
            "direct_answer": "",
            "tasks": [],
            "confidence": 0.0,
            "analysis": "",
            "is_sql": False,
            "sql_template": None,
            "match_score": 0.0,
            "votes": {},
            "plan": {},
            "mode": "auto",
        }

        result = self._graph.invoke(state)

        # Determine final mode from graph output
        itype = result.get("intercepted_type")
        if itype in ("quick_response", "unrelated"):
            return {
                "mode": "direct",
                "is_sql": False,
                "direct_answer": result.get("direct_answer", ""),
            }

        tasks = result.get("tasks", [])
        if len(tasks) >= 2 and result.get("plan", {}).get("plan"):
            return {
                "mode": "planner",
                "is_sql": None,
                "plan": result.get("plan", {}),
                "analysis": result.get("analysis", ""),
            }

        # Single task or low confidence → SQL/RAG
        is_sql = result.get("is_sql", False)
        return {
            "mode": "auto",
            "is_sql": is_sql,
            "sql_template": result.get("sql_template"),
            "match_score": result.get("match_score", 0.0),
            "votes": result.get("votes", {}),
            "analysis": result.get("analysis", ""),
            "tasks": tasks,
        }
