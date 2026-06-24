# Planner 职责分离与 DAG 调度（项目更新日志 9）

**日期**: 2026-06-06
**分支**: panxin-dev
**范围**: TaskAnalysis 去工具化、删除 parallel 字段、DAG 调度器、DAGDeadlockError 死锁处理

---

## 一、起点：日志 8 架构中存在的问题

日志 8 搭建了"两阶段规划 + PlannerExecutor 执行"管线，但各层职责边界模糊：

```
TASK_ANALYSIS_PROMPT
    ↓ 要求 LLM 输出 type: stat_query|regulation_lookup|article_lookup|comparison
    ↓ 这本质上是让 Task Analysis 阶段偷偷做 Tool Selection

TOOL_PLANNING_PROMPT
    ↓ 要求 LLM 输出 parallel: [[1,2]]
    ↓ 这本质上是让 Tool Planning 阶段偷偷做 Execution Scheduling
```

具体问题：

| 问题 | 说明 |
|------|------|
| TaskAnalysis 带 type 字段 | `stat_query ≈ SQL`, `regulation_lookup ≈ RAG`，What 和 How 混淆 |
| parallel 字段依赖 LLM 判断 | 并行/串行是 DAG 拓扑问题，不应由语言模型决定 |
| depends_on 只展示不执行 | PlannerExecutor 读取 parallel_groups 决定调度，depends_on 被忽略 |
| 死锁静默丢失 | 循环依赖时只 break，卡住的任务不报错 |

---

## 二、改动1：删除 parallel 字段，调度权回归代码

### 修改内容

**`app/core/router.py`**:
- `TOOL_PLANNING_PROMPT` 输出格式移除 `"parallel": [[1, 2]]` 及相关规划要点
- `PlannerRouter.plan()` 删除整个 `filtered_parallel` 冲突校验逻辑（18 行）
- `_fallback_plan()` 不再包含 `"parallel": []`
- 方法 docstring 同步更新

**`app/agent/planner.py`**:
- `_parse_plan()` 返回值从 `Tuple[List[PlannedTask], List[PlannedStep], List[List[int]]]` 简化为 `Tuple[List[PlannedTask], List[PlannedStep]]`
- `_parse_plan()` 内部删除 `parallel_groups = plan_dict.get("parallel", [])`
- `REPLAN_PROMPT` 移除 `"parallel": []`
- 模块 docstring 更新

**`test_agent.py`**: 移除 parallel 引用

### 设计理由

并行与串行不是语言规划问题，而是任务依赖关系问题。只要存在 `t2.depends_on = ["t1"]`，代码天然知道 t1 先执行、t2 后执行、无依赖的 t3 可与 t1 并行。不需要 LLM 再额外输出 parallel 字段。

---

## 三、改动2：DAG 调度器根据 depends_on 自动编排

### 修改内容

**`PlannerExecutor.execute()` 核心逻辑重写**:

```python
# 按 task_id 分组步骤
task_steps: Dict[str, List[PlannedStep]] = defaultdict(list)
for s in steps:
    task_steps[s.task_id].append(s)

completed_tasks: set = set()
remaining_tasks = set(task_steps.keys())

while remaining_tasks:
    # 找出所有依赖已满足的任务
    ready_tasks = [
        tid for tid in remaining_tasks
        if all(dep in completed_tasks for dep in task_map[tid].depends_on)
    ]

    if not ready_tasks:
        # 死锁 → 记录 error → 抛异常
        ...

    # 收集就绪任务的全部步骤，并行执行
    ready_steps = [s for tid in ready_tasks for s in task_steps[tid]]
    batch_results = await self._execute_parallel(ready_steps)

    completed_tasks.update(ready_tasks)
    remaining_tasks.difference_update(ready_tasks)
```

### 调度效果

| 拓扑 | 示例 | 调度结果 |
|------|------|----------|
| 全独立 | A, B, C 无依赖 | A、B、C 一轮并行 |
| 链式 | A → B → C | A → B → C 三轮串行 |
| 混合 | A → (B, C) | A → B/C 并行 |

Scheduler 根据图自动决定执行顺序，不再依赖 Prompt 输出。

### 死锁处理

```python
if not ready_tasks:
    state.errors.append({
        "type": "dag_deadlock",
        "remaining": list(remaining_tasks),
        "completed": list(completed_tasks),
    })
    self._last_state = state
    raise DAGDeadlockError(remaining_tasks, completed_tasks)
```

- `AgentState.errors` 新增 `List[Dict]` 字段，`to_dict()` 同步输出
- `DAGDeadlockError` 包含 `remaining_tasks` 和 `completed_tasks` 上下文
- `PlannerExecutor.run()` 捕获异常后继续走 `aggregate()`，汇总已完成结果，不静默丢失
- 导出到 `app/agent/__init__.py`

---

## 四、改动3：TaskAnalysis 去工具化

### 修改内容

**`app/core/router.py` — `TASK_ANALYSIS_PROMPT`**:
- 移除整段任务类型描述（`stat_query: 从数据库统计...`, `regulation_lookup: 查法规概念...` 等 4 个类型）
- 输出格式从 `{"task_id": "t1", "goal": "...", "type": "...", "depends_on": []}` 简化为 `{"task_id": "t1", "goal": "...", "depends_on": []}`
- `_fallback_plan()` 同步移除 `type`

**`app/agent/planner.py`**:
- `PlannedTask` 删除 `type: str = "unknown"` 字段
- 删除 `_infer_task_type()` 方法（12 行关键词匹配逻辑）
- `_parse_plan()` 不再将 type 传给 PlannedTask，不再调用类型推断
- `aggregate()` 摘要行从 `[t.type] t.goal` 改为 `t.goal`

### 设计理由

TaskAnalysis 阶段应该只回答"需要什么数据"，不要回答"用什么方式获取"。`type` 字段中的 `stat_query ≈ SQL`、`regulation_lookup ≈ RAG` 等映射属于 Tool Selection 的职责，应留给 Tool Planner 完成。

---

## 五、最终架构

```
Question
    ↓
Task Analyzer (What — 需要哪些数据)
    → {task_id, goal, depends_on}
    ↓
Tool Planner (How — 怎么获取)
    → {step, tool, params}
    ↓
DAG Scheduler (When — depends_on 自动编排)
    → asyncio.gather 并行就绪任务
    ↓
Executor → Aggregate
```

每层职责单一：Analyzer 只管 What，Planner 只管 How，Scheduler 只管 When。

---

## 六、涉及文件

| 文件 | 变更类型 |
|------|----------|
| `app/core/router.py` | TASK_ANALYSIS_PROMPT/TOOL_PLANNING_PROMPT 精简，删除 filtered_parallel 逻辑 |
| `app/agent/planner.py` | DAG 调度器，删除 parallel_groups/_infer_task_type，新增 DAGDeadlockError |
| `app/agent/agent_state.py` | 新增 `errors: List[Dict]` 字段，to_dict() 包含 errors |
| `app/agent/__init__.py` | 导出 DAGDeadlockError |
| `test_agent.py` | 移除 parallel/type 引用 |
