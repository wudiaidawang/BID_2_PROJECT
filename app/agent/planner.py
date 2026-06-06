"""Planner Executor — 执行 LLM 生成的计划，DAG 调度 + 重规划

与 ReActAgent 的区别:
    - ReActAgent: 一步一步思考，每步看到 Observation 再决定下一步
    - PlannerExecutor: 先 Task 分析 → 再工具规划 → DAG 调度 → 按 Task 汇总

两层架构:
    Task 层（用户要什么）:   "对比工程类和货物类的中标金额"
    Plan 层（怎么做到）:     Step1: sql_query(工程类) + Step2: sql_query(货物类)

流程:
    PlannerRouter.plan() → {tasks: [...], plan: [...], confidence: 0.9}
    → PlannerExecutor.execute() → DAG 调度（根据 depends_on 自动串/并行）
    → PlannerExecutor.aggregate() → 按 Task 分组汇总 → 最终答案
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.agent.agent_tools import TOOL_CLASSES, BaseTool
from app.agent.agent_state import AgentState, StepRecord


class DAGDeadlockError(Exception):
    """DAG 调度死锁：存在循环依赖或依赖链断裂，无法继续执行"""
    def __init__(self, remaining_tasks: set, completed_tasks: set):
        self.remaining_tasks = remaining_tasks
        self.completed_tasks = completed_tasks
        super().__init__(
            f"死锁：{len(remaining_tasks)} 个任务无法执行 "
            f"(remaining={remaining_tasks}, completed={completed_tasks})"
        )


# ---------------------------------------------------------------------------
# 计划的数据结构
# ---------------------------------------------------------------------------
@dataclass
class PlannedTask:
    """用户意图中的一个任务（Task 层）

    对应 LLM 输出的 tasks[] 数组元素。
    """
    task_id: str                           # "t1", "t2"
    goal: str                              # 用户想达成的目标，如"查询围标的处罚规定"
    depends_on: List[str] = field(default_factory=list)  # 依赖的 task_id 列表


@dataclass
class PlannedStep:
    """一个工具调用步骤（Plan 层）

    每个 step 属于一个 task，由 task_id 关联。
    """
    step_num: int
    task_id: str = ""                      # 关联的 task_id
    tool_name: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""


@dataclass
class StepResult:
    """一个步骤的执行结果"""
    step_num: int
    task_id: str = ""
    tool_name: str = ""
    success: bool = False
    result: str = ""
    error: str = ""
    duration_ms: float = 0.0


# ---------------------------------------------------------------------------
# LLM 重规划的 prompt
# ---------------------------------------------------------------------------
REPLAN_PROMPT = """原计划部分步骤失败了，需要修正剩余步骤。

## 原始问题
{question}

## 原始任务
{original_tasks}

## 原始计划
{original_plan}

## 已成功执行的步骤
{completed_steps}

## 失败步骤
{failed_steps}

请输出修正后的计划 JSON（包含 tasks 和 plan）：
{{"tasks": [{{"task_id": "...", "goal": "..."}}], "plan": [{{"step": N, "task_id": "...", "tool": "工具名", "params": {{...}}, "reason": "..."}}]}}

可用工具：{tools_description}

只输出 JSON。"""


# ---------------------------------------------------------------------------
# 结果聚合 prompt
# ---------------------------------------------------------------------------
AGGREGATE_PROMPT = """基于以下执行结果，直接回答用户问题。

## 用户问题
{question}

## 用户想达成的任务
{tasks_summary}

## 各任务执行结果
{task_results}

请直接给出答案，不要复述"步骤1返回了..."。要求：
1. 如果涉及法规，注明法律名称和条款号
2. 如果涉及统计数据，列出具体数字
3. 如果是对比类问题，先各自陈述再给出对比结论
4. 如果某个任务没有获取到信息，明确说"关于XX暂时没有查到"
5. 不要编造检索结果中没有的信息
"""


# ---------------------------------------------------------------------------
# PlannerExecutor
# ---------------------------------------------------------------------------
class PlannerExecutor:
    """计划执行器 — 解析 LLM 计划 → 执行工具 → 汇总答案

    用法:
        executor = PlannerExecutor(retriever, llm)
        plan = await router.plan(question)       # PlannerRouter 生成计划
        state = await executor.execute(plan, question)  # 执行计划
        answer = await executor.aggregate(state)  # 汇总答案
    """

    def __init__(self, retriever, llm, allow_replan: bool = True):
        self.retriever = retriever
        self.llm = llm
        self.allow_replan = allow_replan

        # 实例化工具
        self.tools: Dict[str, BaseTool] = {}
        for tool_name, tool_class in TOOL_CLASSES.items():
            self.tools[tool_name] = tool_class(retriever, llm)

    # ── 计划解析 ───────────────────────────────────────

    def _parse_plan(self, plan_dict: Dict) -> Tuple[List[PlannedTask], List[PlannedStep]]:
        """将 LLM 输出的 JSON 解析为 Task + Step 两层结构

        Args:
            plan_dict: {"tasks": [...], "plan": [...], "confidence": 0.9}

        Returns:
            (tasks, steps)
        """
        raw_tasks = plan_dict.get("tasks", [])
        raw_steps = plan_dict.get("plan", [])
        # 解析 Task 层
        tasks: List[PlannedTask] = []
        task_id_set: set = set()
        for raw in raw_tasks:
            tid = raw.get("task_id", f"t{len(tasks)+1}")
            if tid in task_id_set:
                continue  # 去重
            task_id_set.add(tid)
            tasks.append(PlannedTask(
                task_id=tid,
                goal=raw.get("goal", ""),
                depends_on=raw.get("depends_on", []),
            ))

        # 解析 Plan 层，关联 task_id
        steps: List[PlannedStep] = []
        for raw in raw_steps:
            tid = raw.get("task_id", "")
            # 如果 LLM 没输出 task_id，尝试从 step 顺序匹配 task
            if not tid and tasks and len(steps) < len(tasks):
                tid = tasks[len(steps)].task_id

            params = raw.get("params", raw.get("action_input", {}))
            # 规范化：params 为空时用 reason 补 query
            if not params.get("query") and not params.get("article_num"):
                reason = raw.get("reason", "")
                if reason:
                    params["query"] = reason

            steps.append(PlannedStep(
                step_num=int(raw.get("step", len(steps) + 1)),
                task_id=tid,
                tool_name=raw.get("tool", "search_regulations"),
                params=params,
                reason=raw.get("reason", ""),
            ))

        return tasks, steps

    def _get_tools_description(self) -> str:
        lines = []
        for name, tool in self.tools.items():
            lines.append(f"- {name}: {tool.description}")
        return "\n".join(lines)

    # ── 步骤执行 ───────────────────────────────────────

    async def _execute_step(self, step: PlannedStep) -> StepResult:
        """执行单个步骤"""
        t_start = time.time()

        if step.tool_name not in self.tools:
            return StepResult(
                step_num=step.step_num,
                task_id=step.task_id,
                tool_name=step.tool_name,
                success=False,
                error=f"未知工具: {step.tool_name}",
            )

        try:
            tool = self.tools[step.tool_name]
            result = await tool.run(**step.params)
            return StepResult(
                step_num=step.step_num,
                task_id=step.task_id,
                tool_name=step.tool_name,
                success=True,
                result=str(result),
                duration_ms=(time.time() - t_start) * 1000,
            )
        except Exception as e:
            return StepResult(
                step_num=step.step_num,
                task_id=step.task_id,
                tool_name=step.tool_name,
                success=False,
                error=str(e),
                duration_ms=(time.time() - t_start) * 1000,
            )

    async def _execute_serial(self, steps: List[PlannedStep]) -> List[StepResult]:
        """串行执行一组步骤"""
        results = []
        for step in steps:
            result = await self._execute_step(step)
            results.append(result)
        return results

    async def _execute_parallel(self, steps: List[PlannedStep]) -> List[StepResult]:
        """并行执行一组步骤"""
        tasks = [self._execute_step(s) for s in steps]
        return list(await asyncio.gather(*tasks))

    # ── 重规划 ─────────────────────────────────────────

    async def _replan(
        self, question: str, original_plan: Dict, results: List[StepResult]
    ) -> Optional[Dict]:
        """执行出现问题时，让 LLM 重新规划剩余步骤"""
        if not self.llm or not self.allow_replan:
            return None

        completed = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        completed_str = "\n".join(
            f"Step{r.step_num} ({r.tool_name}): {r.result[:300]}" for r in completed
        )
        failed_str = "\n".join(
            f"Step{r.step_num} ({r.tool_name}): {r.error}" for r in failed
        )

        # 原始 tasks 信息
        tasks = getattr(self, '_last_tasks', [])
        tasks_str = "\n".join(
            f"{t.task_id}: {t.goal}" for t in tasks
        ) if tasks else "（无）"

        prompt = REPLAN_PROMPT.format(
            question=question,
            original_tasks=tasks_str,
            original_plan=json.dumps(original_plan, ensure_ascii=False, indent=2),
            completed_steps=completed_str or "（无）",
            failed_steps=failed_str or "（无）",
            tools_description=self._get_tools_description(),
        )

        try:
            response = await self.llm._call_llm(prompt)
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            print(f"[PlannerExecutor] 重规划失败: {e}")

        return None

    # ── 核心执行流程 ──────────────────────────────────

    async def execute(
        self,
        plan_dict: Dict,
        question: str,
        max_replan: int = 1,
    ) -> AgentState:
        """执行计划，DAG 调度：根据 depends_on 自动决定串行/并行"""
        state = AgentState(question)
        confidence = plan_dict.get("confidence", 0.5)
        tasks, steps = self._parse_plan(plan_dict)

        print(f"\n[PlannerExecutor] 执行计划 (confidence={confidence:.2f})")

        # 打印 Task 层
        if tasks:
            print(f"  [Tasks] {len(tasks)} 个:")
            for t in tasks:
                deps = f" depends_on={t.depends_on}" if t.depends_on else ""
                print(f"    {t.task_id} {t.goal}{deps}")

        if not steps:
            print("[PlannerExecutor] 空计划，降级到 search_regulations")
            state.begin_step()
            t_start = time.time()
            try:
                result = await self.tools["search_regulations"].run(query=question)
                observation = str(result)
            except Exception as e:
                observation = f"降级检索失败: {e}"
            state.add_step(StepRecord(
                step_num=1,
                action="search_regulations",
                action_input={"query": question},
                observation=observation[:800],
                tool_name="search_regulations",
                tool_duration_ms=(time.time() - t_start) * 1000,
            ))
            state.finish(observation)
            return state

        # task_id → PlannedTask 映射
        task_map: Dict[str, PlannedTask] = {t.task_id: t for t in tasks}
        self._last_tasks = tasks

        # 按 task_id 分组步骤，组内按 step_num 排序
        from collections import defaultdict
        task_steps: Dict[str, List[PlannedStep]] = defaultdict(list)
        for s in steps:
            task_steps[s.task_id].append(s)
        for tid in task_steps:
            task_steps[tid].sort(key=lambda s: s.step_num)

        # ── DAG 调度 ──
        completed_tasks: set = set()
        remaining_tasks = set(task_steps.keys())

        # 记录 step 顺序计数（跨 batch 递增）
        step_counter = 0
        all_results: List[StepResult] = []

        while remaining_tasks:
            # 找到所有依赖已满足的任务
            ready_tasks = []
            for tid in remaining_tasks:
                task = task_map.get(tid)
                if not task or not task.depends_on:
                    ready_tasks.append(tid)
                elif all(dep in completed_tasks for dep in task.depends_on):
                    ready_tasks.append(tid)

            if not ready_tasks:
                state.errors.append({
                    "type": "dag_deadlock",
                    "remaining": list(remaining_tasks),
                    "completed": list(completed_tasks),
                })
                self._last_state = state
                raise DAGDeadlockError(remaining_tasks, completed_tasks)

            # 收集所有就绪任务的步骤，跨任务并行执行
            ready_steps = []
            for tid in sorted(ready_tasks):
                ready_steps.extend(task_steps.get(tid, []))

            # 分配 step_num（执行顺序号）
            for s in ready_steps:
                step_counter += 1
                s.step_num = step_counter

            print(f"  [DAG] 本轮就绪任务: {ready_tasks}, {len(ready_steps)} 步并行")
            batch_results = await self._execute_parallel(ready_steps)
            all_results.extend(batch_results)

            # 标记完成
            for tid in ready_tasks:
                completed_tasks.add(tid)
                remaining_tasks.discard(tid)

        # 按执行顺序写入 AgentState
        for sr in all_results:
            state.begin_step()
            state.add_step(StepRecord(
                step_num=sr.step_num,
                task_id=sr.task_id,
                action=sr.tool_name,
                action_input=next((s.params for s in steps if s.step_num == sr.step_num), {}),
                observation=(sr.result if sr.success else f"错误: {sr.error}")[:800],
                tool_name=sr.tool_name,
                tool_duration_ms=sr.duration_ms,
                error=sr.error if not sr.success else None,
            ))

        # 重规划
        failed_count = sum(1 for r in all_results if not r.success)
        replan_count = 0
        while failed_count > 0 and replan_count < max_replan:
            print(f"  [重规划] {failed_count} 步失败 (第{replan_count+1}次)")
            new_plan = await self._replan(question, plan_dict, all_results)
            if not new_plan or not new_plan.get("plan"):
                break

            _, new_steps = self._parse_plan(new_plan)
            if not new_steps:
                break

            max_num = max((r.step_num for r in all_results), default=0)
            for ns in new_steps:
                ns.step_num += max_num

            print(f"  [重规划] 新增 {len(new_steps)} 步")
            retry_results = await self._execute_serial(new_steps)
            all_results.extend(retry_results)

            for sr in retry_results:
                state.begin_step()
                state.add_step(StepRecord(
                    step_num=sr.step_num,
                    task_id=sr.task_id,
                    action=sr.tool_name,
                    observation=(sr.result if sr.success else f"错误: {sr.error}")[:800],
                    tool_name=sr.tool_name,
                    tool_duration_ms=sr.duration_ms,
                    error=sr.error if not sr.success else None,
                ))

            failed_count = sum(1 for r in retry_results if not r.success)
            replan_count += 1

        print(f"  [完成] {len(all_results)} 步, "
              f"{sum(1 for r in all_results if r.success)} 成功, "
              f"{sum(1 for r in all_results if not r.success)} 失败, "
              f"总耗时 {state.elapsed_seconds():.1f}s")

        return state

    async def aggregate(self, state: AgentState, question: str) -> str:
        """按 Task 分组汇总结果，生成最终答案"""
        if state.finished and state.final_answer:
            return state.final_answer

        successful = [s for s in state.steps if not s.error and s.observation]
        if not successful:
            fallback = "抱歉，所有检索步骤均未成功获取信息。请稍后重试或换一种问法。"
            state.finish(fallback)
            return fallback

        if len(successful) == 1 and len(successful[0].observation) < 500:
            answer = successful[0].observation
            state.finish(answer)
            return answer

        if self.llm:
            # 构建 Task 摘要
            tasks = getattr(self, '_last_tasks', [])
            tasks_summary = "\n".join(
                f"- {t.goal}" for t in tasks
            ) if tasks else "（无任务分解信息）"

            # 按 task 分组结果
            from collections import defaultdict
            by_task = defaultdict(list)
            for s in successful:
                tid = getattr(s, 'task_id', '') or 'unknown'
                by_task[tid].append(s)

            task_results_parts = []
            for tid, steps_list in by_task.items():
                label = tid
                task = next((t for t in tasks if t.task_id == tid), None)
                if task:
                    label = f"{tid}: {task.goal}"
                for s in steps_list:
                    task_results_parts.append(
                        f"### {label}\n步骤{s.step_num} ({s.action}): {s.observation[:600]}"
                    )
            task_results_text = "\n\n".join(task_results_parts)

            prompt = AGGREGATE_PROMPT.format(
                question=question,
                tasks_summary=tasks_summary,
                task_results=task_results_text,
            )
            try:
                answer = await self.llm._call_llm(prompt)
                state.finish(answer)
                return answer
            except Exception:
                answer = "\n\n".join(f"【{s.action}】{s.observation}" for s in successful)
                state.finish(answer)
                return answer

        answer = "\n\n".join(f"【{s.action}】{s.observation}" for s in successful)
        state.finish(answer)
        return answer

    async def run(self, question: str, plan_dict: Dict) -> str:
        """一站式执行: 计划 → 执行 → 汇总 → 答案

        这是最常用的入口，封装了 execute + aggregate。
        """
        try:
            state = await self.execute(plan_dict, question)
        except DAGDeadlockError:
            state = self._last_state  # execute 已写 state.errors + _last_state
        answer = await self.aggregate(state, question)
        self.last_state = state
        return answer
