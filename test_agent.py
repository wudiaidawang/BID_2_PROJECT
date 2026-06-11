"""Agent Planner 端到端测试 — 两阶段规划: Task分析 → Tool规划 → 执行 → 汇总"""
import asyncio
import sys
sys.path.insert(0, '.')

from app.agent.planner import PlannerExecutor
from app.core.router import PlannerRouter
from app.core.generator import LLMGenerator


async def test(question: str):
    print(f"\n{'='*60}")
    print(f"Test: {question}")
    print(f"{'='*60}")

    llm = LLMGenerator()
    router = PlannerRouter(llm=llm)
    router.set_tools({
        "search_regulations": "语义检索招投标法规知识库，查询概念定义、处罚规定、操作流程",
        "get_article": "精确查询特定法条的第X条完整内容",
        "sql_query": "对招标数据库(bids表)执行统计查询。bids表字段: project_name, supplier, amount, province, city, publish_date, category",
        "summarize": "将多段检索结果归纳总结成结构化回答",
    })

    # ── 两阶段规划 ──
    print(f"\n[阶段1] Task分析...")
    plan = await router.plan(question)

    # Task 层
    tasks = plan.get('tasks', [])
    print(f"\n[Task层] {len(tasks)} 任务, confidence={plan.get('confidence',0):.2f}")
    if plan.get('analysis'):
        print(f"  analysis: {plan['analysis']}")
    for t in tasks:
        deps = f" depends_on={t.get('depends_on', [])}" if t.get('depends_on') else ""
        print(f"  {t['task_id']}: {t['goal']}{deps}")

    # Plan 层
    plan_steps = plan.get('plan', [])
    print(f"\n[Plan层] {len(plan_steps)} 步骤")
    for s in plan_steps:
        print(f"  Step{s['step']} ({s.get('task_id','?')}): {s['tool']}({s.get('params',{})}) reason={s.get('reason','')[:50]}")

    # ── 执行 ──
    executor = PlannerExecutor(retriever=None, llm=llm, allow_replan=True)
    state = await executor.execute(plan, question)
    answer = await executor.aggregate(state, question)

    print(f"\n>>> FINAL ANSWER:\n{answer}")
    print(f"\n耗时: {state.elapsed_seconds():.1f}s | 步数: {state.step_count()} | 工具: {dict(state.tool_call_count)}")


if __name__ == "__main__":
    # 简单统计查询
    asyncio.run(test("你好呀"))
    # 复杂问题 — 涉及 depends_on
    asyncio.run(test("工程类和货物类项目的中标金额对比"))
