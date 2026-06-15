"""LangGraph Agent — 替代手写 ReActAgent + PlannerExecutor

- ReActAgent  → langgraph.prebuilt.create_react_agent + HunyuanChatModel 适配器
- PlannerExecutor → 自定义 DAG StateGraph
- Checkpoint → SqliteSaver (langgraph-checkpoint-sqlite, 磁盘持久化)
"""

import time
from typing import Dict, List, Optional, Any

from langgraph.prebuilt import create_react_agent
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from langchain_core.messages import HumanMessage
from typing import TypedDict

from app.agent.agent_tools import create_agent_tools
from config import settings


REACT_SYSTEM_PROMPT = """你是一个招投标法规专家助手。可以使用工具检索信息，基于检索结果回答问题。

## 重要规则
1. 每轮只能调用一个工具
2. 信息足够时直接输出最终答案
3. 如果用户使用了指代词，请结合历史对话理解问题
4. 比较类问题先分别检索再比较
5. 如果没有找到相关信息，请如实告知
6. 引用法规时注明法律名称和条款号
"""


class LangGraphReActAgent:
    """LangGraph ReAct Agent — 使用 langgraph.prebuilt.create_react_agent + HunyuanChatModel"""

    def __init__(self, retriever, llm, max_steps: int = 5,
                 session_manager=None, checkpointer: BaseCheckpointSaver = None,
                 sql_engine=None):
        self.retriever = retriever
        self.llm = llm
        self.max_steps = max_steps
        self.session_manager = session_manager

        from app.data.langchain_llm import HunyuanChatModel
        self._chat_model = HunyuanChatModel()
        self._chat_model.set_llm(llm)

        if checkpointer:
            self._checkpointer = checkpointer
        else:
            import sqlite3, os as _os
            _db = getattr(settings, 'checkpoint_db_path', './data/checkpoints.db')
            _os.makedirs(_os.path.dirname(_db) or '.', exist_ok=True)
            self._checkpointer = SqliteSaver(sqlite3.connect(_db, check_same_thread=False))
            self._checkpointer.setup()

        self._tools = create_agent_tools(retriever, llm=llm, sql_engine=sql_engine)
        self._graph: CompiledStateGraph = create_react_agent(
            model=self._chat_model,
            tools=self._tools,
            checkpointer=self._checkpointer,
        )
        self.last_state = None

    async def run(self, question: str, session_id: str = None) -> str:
        sid = session_id or "default"
        print(f"\n[LangGraphAgent] Processing: {question}")

        config = {"configurable": {"thread_id": sid}}
        messages = [
            HumanMessage(content=REACT_SYSTEM_PROMPT + "\n\n用户问题：" + question)
        ]

        try:
            result = self._graph.invoke({"messages": messages}, config)
            final_msgs = result.get("messages", [])
            answer = ""
            for m in reversed(final_msgs):
                if hasattr(m, 'content') and m.content and m.type != "tool":
                    # Skip tool calls, find the last AI response
                    pass
                if hasattr(m, 'content') and m.content:
                    answer = m.content
                    break
            if not answer:
                answer = str(final_msgs[-1]) if final_msgs else "Agent未产生输出"
            print(f"  [LangGraphAgent] Final answer: {len(answer)} chars")
            self.last_state = result
            return answer
        except Exception as e:
            print(f"  [LangGraphAgent] Error: {e}")
            import traceback
            traceback.print_exc()
            return f"Agent执行失败: {str(e)}"

    async def resume(self, session_id: str) -> str:
        config = {"configurable": {"thread_id": session_id}}
        try:
            last_state = self._graph.get_state(config)
            if last_state and last_state.values:
                print(f"[LangGraphAgent] Resumed session {session_id}")
                msgs = last_state.values.get("messages", [])
                for m in reversed(msgs):
                    if hasattr(m, 'content') and m.content:
                        return m.content
        except Exception as e:
            print(f"[LangGraphAgent] Resume failed: {e}")
        return "无法恢复历史会话"


# ═══════════════════════════════════════════════════════════════════
# Planner DAG Agent (LangGraph StateGraph)
# ═══════════════════════════════════════════════════════════════════

class PlannerState(TypedDict, total=False):
    question: str
    plan: Dict
    tasks: List[Dict]
    step_results: List[Dict]
    final_answer: str


class LangGraphPlannerAgent:
    """LangGraph DAG 计划执行器 — 替代手写 PlannerExecutor

    Graph: parse_plan → dag_execute → aggregate → END
    """

    def __init__(self, retriever, llm, allow_replan: bool = True,
                 checkpointer: BaseCheckpointSaver = None, sql_engine=None):
        self.retriever = retriever
        self.llm = llm
        self.allow_replan = allow_replan
        self._session_id = "default"

        self._tools = create_agent_tools(retriever, llm=llm, sql_engine=sql_engine)
        self._tool_map = {t.name: t for t in self._tools}
        if checkpointer:
            self._checkpointer = checkpointer
        else:
            import sqlite3, os as _os
            _db = getattr(settings, 'checkpoint_db_path', './data/checkpoints.db')
            _os.makedirs(_os.path.dirname(_db) or '.', exist_ok=True)
            self._checkpointer = SqliteSaver(sqlite3.connect(_db, check_same_thread=False))
            self._checkpointer.setup()
        self._graph = self._build_graph()
        self.last_state = None

    def _build_graph(self) -> CompiledStateGraph:
        graph = StateGraph(PlannerState)

        graph.add_node("parse_plan", self._parse_plan_node)
        graph.add_node("dag_execute", self._dag_execute_node)
        graph.add_node("replan", self._replan_node)
        graph.add_node("aggregate", self._aggregate_node)

        graph.set_entry_point("parse_plan")
        graph.add_edge("parse_plan", "dag_execute")
        graph.add_conditional_edges(
            "dag_execute",
            self._should_replan,
            {"replan": "replan", "aggregate": "aggregate"},
        )
        graph.add_edge("replan", "dag_execute")
        graph.add_edge("aggregate", END)

        return graph.compile(checkpointer=self._checkpointer)

    def _should_replan(self, state: PlannerState) -> str:
        """条件边：检查是否需要 RePlan"""
        step_results = state.get("step_results", [])
        failures = [r for r in step_results if not r.get("success")]
        if failures and self.allow_replan:
            fail_tasks = {r.get("task_id") for r in failures}
            print(f"[PlannerAgent] RePlan needed: {len(failures)} failed steps across {len(fail_tasks)} tasks")
            return "replan"
        return "aggregate"

    def _replan_node(self, state: PlannerState) -> dict:
        """RePlan 节点：对失败步骤生成补偿计划"""
        step_results = state.get("step_results", [])
        plan_dict = state.get("plan", {})
        tasks = state.get("tasks", [])

        failures = [r for r in step_results if not r.get("success")]
        successful = [r for r in step_results if r.get("success")]

        if not failures:
            return state

        # 构建失败步骤摘要
        fail_summary = "\n".join(
            f"- Task {r['task_id']}: {r['tool_name']} 失败 → {r.get('error', '未知错误')}"
            for r in failures
        )

        success_context = ""
        if successful:
            success_context = "已成功的步骤:\n" + "\n".join(
                f"- {r['task_id']}: {r['tool_name']} → {r.get('result', '')[:200]}"
                for r in successful
            )

        # 用 LLM 生成补偿步骤
        if self.llm:
            prompt = (
                f"用户问题: {state['question']}\n\n"
                f"{success_context}\n\n"
                f"以下步骤执行失败:\n{fail_summary}\n\n"
                f"请为失败的 Task 生成替代步骤。输出格式:\n"
                f'{{"plan": ['
                f'{{"task_id": "T1", "tool": "rag_search", '
                f'"params": {{"query": "..."}}, "reason": "..."}}'
                f']}}\n'
                f"只输出 JSON，不要解释。"
            )
            try:
                import json, re
                result = self.llm._call_llm(prompt=prompt)
                json_match = re.search(r'\{[^{}]*"plan"[^}]*\[.*?\][^}]*\}', result, re.DOTALL)
                if json_match:
                    replan_data = json.loads(json_match.group())
                    new_steps = replan_data.get("plan", [])
                    print(f"[PlannerAgent] RePlan generated {len(new_steps)} compensating steps")
                    # 合并到 plan_dict
                    existing_plan = list(plan_dict.get("plan", []))
                    plan_dict["plan"] = existing_plan + new_steps
            except Exception as e:
                print(f"[PlannerAgent] RePlan failed: {e}")

        # 降级：所有失败 task 改用 rag_search
        if not plan_dict.get("plan"):
            fallback_steps = []
            for r in failures:
                tid = r.get("task_id")
                task_goal = ""
                for t in tasks:
                    if t.get("task_id") == tid:
                        task_goal = t.get("goal", "")
                fallback_steps.append({
                    "task_id": tid,
                    "tool": "rag_search",
                    "params": {"query": task_goal or state["question"]},
                    "reason": f"降级检索(原{r['tool_name']}失败)",
                })
            plan_dict["plan"] = fallback_steps
            print(f"[PlannerAgent] Fallback: {len(fallback_steps)} rag_search steps")

        return {"plan": plan_dict}

    def _parse_plan_node(self, state: PlannerState) -> dict:
        plan_dict = state.get("plan", {})
        tasks = plan_dict.get("tasks", [])
        plan_steps = plan_dict.get("plan", [])

        if not plan_steps and not tasks:
            tasks = [{"task_id": "t1", "goal": "直接检索", "depends_on": []}]
            plan_steps = [{"step": 1, "task_id": "t1", "tool": "rag_search",
                           "params": {"query": state["question"]}, "reason": "降级检索"}]

        print(f"[PlannerAgent] Parsed: {len(tasks)} tasks, {len(plan_steps)} steps")
        return {"tasks": tasks, "plan": plan_dict, "step_results": []}

    def _dag_execute_node(self, state: PlannerState) -> dict:
        tasks = state.get("tasks", [])
        plan_dict = state.get("plan", {})
        plan_steps = plan_dict.get("plan", [])
        step_results: List[Dict] = []

        task_map: Dict[str, Dict] = {t["task_id"]: t for t in tasks}
        completed: set = set()
        remaining: set = set(task_map.keys())
        step_counter = [0]  # mutable counter for thread-safe increment

        from threading import Lock
        _lock = Lock()

        def _exec_task_step(tid: str, s: dict) -> dict:
            """Execute a single task step (thread-safe)."""
            tool_name = s.get("tool", "rag_search")
            params = s.get("params", {})
            t_start = time.time()
            tool = self._tool_map.get(tool_name)
            if not tool:
                return {
                    "task_id": tid, "tool_name": tool_name, "success": False,
                    "result": "", "error": f"未知工具: {tool_name}", "duration_ms": 0,
                }
            try:
                result = tool.invoke(params)
                return {
                    "task_id": tid, "tool_name": tool_name, "success": True,
                    "result": str(result), "error": "",
                    "duration_ms": (time.time() - t_start) * 1000,
                }
            except Exception as e:
                return {
                    "task_id": tid, "tool_name": tool_name, "success": False,
                    "result": "", "error": str(e),
                    "duration_ms": (time.time() - t_start) * 1000,
                }

        from concurrent.futures import ThreadPoolExecutor, as_completed

        while remaining:
            ready = [tid for tid in remaining
                     if all(d in completed for d in task_map.get(tid, {}).get("depends_on", []))]

            if not ready:
                print(f"[PlannerAgent] DAG deadlock, remaining: {remaining}")
                break

            print(f"[PlannerAgent] DAG level: {len(ready)} parallel task(s) — {ready}")

            # Collect all steps for ready tasks
            futures_map: dict = {}
            with ThreadPoolExecutor(max_workers=max(len(ready), 1)) as executor:
                for tid in ready:
                    t_steps = [s for s in plan_steps if s.get("task_id") == tid]
                    if not t_steps:
                        t_steps = [{"task_id": tid, "tool": "rag_search",
                                    "params": {"query": task_map[tid]["goal"]},
                                    "reason": f"为: {task_map[tid]['goal']}"}]
                    for s in t_steps:
                        fut = executor.submit(_exec_task_step, tid, s)
                        futures_map[fut] = (tid, s.get("reason", ""))

                # Collect results as they complete
                for fut in as_completed(futures_map):
                    tid, reason = futures_map[fut]
                    r = fut.result()
                    with _lock:
                        step_counter[0] += 1
                        r["step_num"] = step_counter[0]
                    step_results.append(r)

            for tid in ready:
                completed.add(tid)
                remaining.discard(tid)

        # Sort by step_num for deterministic output
        step_results.sort(key=lambda r: r.get("step_num", 0))

        ns = sum(1 for r in step_results if r["success"])
        nf = len(step_results) - ns
        print(f"[PlannerAgent] Executed {len(step_results)} steps ({len(ready)} parallel/level), {ns} success, {nf} failed")
        return {"step_results": step_results}

    def _aggregate_node(self, state: PlannerState) -> dict:
        question = state["question"]
        step_results = state.get("step_results", [])

        successful = [r for r in step_results if r.get("success")]
        if not successful:
            return {"final_answer": "抱歉，所有检索步骤均未成功获取信息。"}

        if len(successful) == 1 and len(successful[0].get("result", "")) < 500:
            return {"final_answer": successful[0]["result"]}

        if self.llm:
            results_text = "\n\n".join(
                f"### 步骤{r['step_num']} ({r['tool_name']}):\n"
                f"{r.get('result', r.get('error', ''))[:600]}"
                for r in successful
            )
            prompt = (
                f"基于以下执行结果，直接回答用户问题。\n"
                f"## 用户问题\n{question}\n\n"
                f"## 执行结果\n{results_text}\n\n"
                f"请直接给出答案，注明信息来源。不要编造信息。"
            )
            try:
                answer = self.llm._call_llm(prompt=prompt)
                return {"final_answer": answer}
            except Exception:
                pass

        answer = "\n\n".join(
            f"【{r['tool_name']}】{r.get('result', '')[:500]}"
            for r in successful
        )
        return {"final_answer": answer}

    async def execute(self, plan_dict: Dict, question: str,
                      session_id: str = "") -> Any:
        self._session_id = session_id or "default"
        config = {"configurable": {"thread_id": self._session_id}}

        result = self._graph.invoke(
            {"question": question, "plan": plan_dict},
            config,
        )
        self.last_state = result
        return result

    async def aggregate(self, state, question: str) -> str:
        if isinstance(state, dict) and state.get("final_answer"):
            return state["final_answer"]
        return state.get("final_answer", "无法生成答案")

    async def run(self, question: str, plan_dict: Dict) -> str:
        state = await self.execute(plan_dict, question,
                                   session_id=self._session_id)
        return await self.aggregate(state, question)
