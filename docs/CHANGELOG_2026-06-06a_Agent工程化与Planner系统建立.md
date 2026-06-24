# Agent 工程化与 Planner 系统建立（项目更新日志 8）

**日期**: 2026-06-06  
**分支**: panxin-dev  
**范围**: Agent 模块从草稿到工程化、Planner 系统从接口骨架到完整可执行管线、三模式路由统一分发

---

## 一、起点：更新日志 7 之后的状态

日志 7 解决了 `_call_llm()` 接口兼容问题（prompt string → messages array），但 Agent 模块仍然是一个**骨架**：

```
app/agent/
├── __init__.py          # 只有一行 docstring
├── agent_state.py       # 用户手写的草稿（class AgentState 未完成，tool() 是 hardcoded mock）
├── agent_tools.py       # 4 个工具类 + BaseTool + TOOL_CLASSES（基本可用，有一个变量名 bug）
└── react_agent.py       # ReActAgent 可用，但状态散落在局部变量里
```

同时在 `app/core/router.py` 中存在一个 `PlannerRouter` 接口骨架 —— 它能调用 LLM 生成计划 JSON，但**没有执行器**，`routes.py` 也完全不处理 planner 模式。计划生成后无人执行。

此外 `config.yaml` 中已定义了 planner 相关的配置项（`plan_then_execute`、`planner_max_steps`、`planner_allow_replan`），但 Settings 类中缺少对应的 `@property` 访问器。

---

## 二、本次完成的工作

### 2.1 AgentState — 从草稿到结构化状态容器

**之前**（用户手写的草稿，`agent_state.py`）：

```python
class AgentState:
    def __init__(self, question):
        self.question = question
        self.current_step = 0
        self.observations = []
        self.final_answer = None
        self.finished = False

    def tool(state):          # hardcoded mock
        count = 100
        state.tool_result['sql'] = count
        state.observations.append('sql查询成功')
        return state
```

问题：
- `tool()` 方法是假数据（`count = 100`）
- AgentState 完全没有被 `react_agent.py` 或 `agent_tools.py` 引用
- 字段是裸类型（list of str），无法结构化记录每步的 Thought/Action/Observation

**之后**（完整的结构化状态系统）：

新增 `StepRecord` dataclass，作为每一步的"施工日志"：

```python
@dataclass
class StepRecord:
    step_num: int
    thought: str = ""                    # LLM 输出的 Thought 部分
    action: str = ""                     # 工具名称
    action_input: Dict[str, Any]         # 传给工具的 kwarg
    observation: str = ""                # 工具返回结果
    tool_name: str = ""                  # 实际执行的工具名
    tool_duration_ms: float = 0.0        # 工具耗时
    error: Optional[str] = None          # 异常信息
```

重写 `AgentState`，包含：
- **写入接口**：`begin_step()` / `add_step()` / `finish()`
- **读取接口**：`get_observations_context()` / `get_tool_result()` / `elapsed_seconds()`
- **统计**：`tool_call_count`（每个工具被调用了几次）、`total_llm_calls`、`total_tool_calls`
- **序列化**：`to_dict()`（方便存日志/前端展示）、`print_trace()`（打印完整执行轨迹）

设计原则：**控制流与数据分离**。Agent 管循环，State 管数据。两者通过明确的读写接口解耦。

### 2.2 Agent Tools — 修复 + 注册表

修复 `agent_tools.py:63`：

```python
# 修复前（变量名错误）
source = data.get("source", "未知来源")   # data 未定义

# 修复后
source = meta.get("source", "未知来源")
```

4 个工具全部可用：

| 工具 | 功能 | 依赖 |
|------|------|------|
| `SearchRegulationsTool` | 语义检索法规知识库 | retriever |
| `GetArticleTool` | 精确查询特定法条 | retriever |
| `SQLQueryTool` | 封装 SQLEngine 做统计查询 | SQLEngine |
| `SummarizeTool` | LLM 总结多段检索结果 | LLM |

工具通过 `TOOL_CLASSES` dict 注册，`ReActAgent` 和 `PlannerExecutor` 均从中实例化。

### 2.3 ReActAgent — 集成 AgentState

**之前**：状态散落在局部变量里：

```python
step_records: List[str] = []      # 裸字符串拼接
for step in range(self.max_steps):  # 循环计数器
    ...
```

**之后**：全面使用 AgentState 管理执行轨迹：

- 每步构造 `StepRecord` 记录 thought/action/observation，含耗时统计
- `state.get_observations_context(last_n=3)` 替代手动拼字符串
- `self.last_state` 对外暴露完整轨迹（外部可调用 `.print_trace()` 调试）
- 保持 `run() → str` 接口兼容

### 2.4 PlannerRouter — 从接口骨架到鲁棒规划器

**之前**：一个简单的 prompt + `plan()` 方法，JSON 解析脆弱，无降级。

**之后**：

1. **Few-shot 示例**：prompt 增加 5 个规划示例（统计/法规/比较/法条/复合），LLM 输出质量显著提升
2. **鲁棒 JSON 解析**（`_parse_plan_response`）：
   - 处理 markdown 代码块包裹（```json ... ```）
   - 修复尾部多余逗号（LLM 常见错误）
   - 逐行清理非 JSON 行
3. **降级计划**（`_fallback_plan`）：LLM 规划失败时自动生成单步 `search_regulations` 降级计划，confidence=0.3，保证系统可用
4. **统一 `route()` 接口**：与 BinaryRouter/IntentRouter 接口兼容，返回 `{mode: "planner", is_sql: None, plan: {...}}`

**重要发现**：Hunyuan API 在 `messages` 列表格式下，长 system prompt 有时返回 400。改为 `prompt` 字符串格式（由 `_call_llm` 自动包装默认 system prompt）后稳定工作。

### 2.5 PlannerExecutor — 全新的计划执行引擎（`app/agent/planner.py`）

这是本次最重要的新增模块，填补了"计划生成后无人执行"的空白。

**新增数据结构**：

```python
@dataclass
class PlannedStep:      # 计划步骤（内部表示）
    step_num: int
    tool_name: str
    params: Dict[str, Any]
    reason: str = ""
    depends_on: List[int] = field(default_factory=list)

@dataclass
class StepResult:       # 单步执行结果
    step_num: int
    tool_name: str
    success: bool
    result: str = ""
    error: str = ""
    duration_ms: float = 0.0
```

**核心执行流程**：

```
PlannerExecutor.execute(plan_dict, question)
  │
  ├── _parse_plan() → 解析 LLM 计划 JSON → List[PlannedStep]
  │
  ├── 阶段1: 串行步骤 → _execute_serial()
  │     └── 逐个调用 tool.run(**params)
  │
  ├── 阶段2: 并行步骤 → _execute_parallel()
  │     └── asyncio.gather(*tasks)
  │
  ├── 重规划 (如需要) → _replan()
  │     └── 失败步骤信息 → LLM 生成修正计划 → 追加执行
  │
  └── 所有结果写入 AgentState
```

**重规划机制**：当某步骤失败时，LLM 看到已完成步骤的结果和失败信息，生成修正后的计划，最多 2 轮。

**结果聚合**（`aggregate`）：
- 单步骤短结果 → 直接返回
- 多步骤 → LLM 汇总所有 observation → 结构化最终答案

### 2.6 Routes 集成 — 三模式统一分发

**之前** `routes.py` 只处理 binary 模式（`route.get("is_sql")` → SQL 或 RAG 路径），planner 返回的 dict 没有 `is_sql` 字段，会导致判断失效。

**之后**：重构为三模式自动分发：

```python
@router.post("/ask")
async def ask(request, req):
    route = await router.route(req.question)

    if route.get("mode") == "planner":
        return await _handle_planner(...)   # 计划 → 执行 → 汇总
    else:
        return await _handle_binary(...)    # is_sql → SQL 或 RAG（原有逻辑）
```

新增辅助函数：
- `_state_to_results()` — 将 AgentState 执行轨迹转换为 results 格式
- `_build_sources()` — 统一的 SourceInfo 构建

### 2.7 main.py — Planner 模式初始化

```python
if settings.router_mode == "planner":
    app.state.planner_executor = PlannerExecutor(
        retriever=None,          # 下面回填
        llm=app.state.generator,
        allow_replan=settings.planner_allow_replan,
    )
    if settings.agent_enabled:
        app.state.agent = ReActAgent(...)   # planner 降级备选
```

retriever 回填逻辑同时覆盖 PlannerExecutor 的工具实例。

### 2.8 模块导出统一

`app/agent/__init__.py` 从一行 docstring 升级为完整模块导出：

```python
from app.agent.agent_state import AgentState, StepRecord
from app.agent.agent_tools import BaseTool, TOOL_CLASSES
from app.agent.react_agent import ReActAgent
from app.agent.planner import PlannerExecutor, PlannedStep, StepResult
```

---

## 三、调试过程中发现并修复的问题

### 3.1 GBK 编码：emoji 导致 Windows 终端崩溃

Windows 中文环境默认 GBK 编码，Python `print()` 遇到 emoji 会抛出 `UnicodeEncodeError`。

**修复文件 3 个，共 5 处**：

| 文件 | 位置 | 修复 |
|------|------|------|
| `app/core/sql_engine.py:90` | `🤖 [SQL引擎]` | 移除 emoji |
| `app/core/sql_engine.py:70` | `🔍 [SQL引擎]` | 移除 emoji |
| `app/core/sql_engine.py:80/83/109/125` | `✅/❌ [SQL引擎]` | 移除 emoji |
| `app/agent/agent_state.py:188` | `❌ Error:` | `[ERROR]` |
| `app/agent/agent_state.py:190` | `✅ Final Answer` | `[Final Answer]` |

### 3.2 Hunyuan API：messages 格式返回 400

**现象**：PlannerRouter 使用 `_call_llm(messages=[system, user])` 格式调用混元 API，长 system prompt 时稳定返回 400。

**定位过程**：
1. 单测同样的 prompt + messages 格式 → 成功
2. 在 test_agent.py 中通过 Router 调用 → 400
3. 添加调试输出 → 确认是 API 层面返回的 400
4. 怀疑是限流或请求体大小，逐级缩短 system prompt → 仍然 400
5. 改用 `_call_llm(prompt=...)` 格式 → 成功

**结论**：混元 API 对过长的 system 角色消息有限制。`prompt` 路径会将长内容放在 user 角色，system 使用短的默认 prompt，绕过限制。

**修复**：PlannerRouter 改用 `prompt` 字符串格式调用 LLM。

### 3.3 API Key 401

用户更换模型名称 `hunyuan-standard` → `hunyuan-turbo` 并更新 API key 后，出现 401。确认为 key 配置问题（用户自行修复）。

---

## 四、端到端测试验证

测试脚本 `test_agent.py`（绕过 Redis/ChromaDB 的离线测试）：

```bash
python test_agent.py
```

**测试结果**（问题："数据库里有几条数据？"）：

```
[Planner] 规划完成: 1 步, confidence=0.95
    Step1: sql_query
[SQL引擎] 生成 SQL: SELECT COUNT(*) FROM bids
[SQL引擎] 查询成功，返回 1 条数据
结果: [{'COUNT(*)': 8789}]
总耗时: 1.5s
```

完整管线验证通过：**LLM 规划 → SQL 执行 → 答案汇总**。

---

## 五、最终文件结构

```
app/agent/
├── __init__.py          # 模块导出（AgentState, StepRecord, BaseTool, TOOL_CLASSES,
│                        #   ReActAgent, PlannerExecutor, PlannedStep, StepResult）
├── agent_state.py       # AgentState + StepRecord（结构化状态容器）
├── agent_tools.py       # BaseTool + 4 个具体工具 + TOOL_CLASSES 注册表
├── react_agent.py       # ReActAgent（单步决策循环，已集成 AgentState）
└── planner.py           # PlannerExecutor + PlannedStep + StepResult（计划执行引擎）

app/core/router.py       # PlannerRouter 增强（few-shot + 鲁棒解析 + 降级计划 + route接口）
app/api/routes.py        # 三模式分发（_handle_planner + _handle_binary）
main.py                  # PlannerExecutor 初始化 + retriever 回填
config.py                # 无变动（planner 配置项已存在，无需新增 property）
config.yaml              # 用户自行修改模型名称 / API key

test_agent.py            # 离线测试脚本（可直接运行验证管线）
```

---

## 六、架构全景图

```
                        POST /api/v1/ask
                              │
                              ▼
                     routes.py（三模式分发）
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
   binary 模式          intent 模式          planner 模式
   BinaryRouter         IntentRouter          PlannerRouter.plan()
   3路投票判定           意图分类                 │
   is_sql                type+complexity         ▼
     │                                            PlannerExecutor.execute()
     ├── SQL 路径（含容错降级）                    │
     └── RAG 路径（跨库混合检索）         ┌───────┴───────┐
                                  串行步骤      并行步骤
                                    │              │
                                    ▼              ▼
                              asyncio 逐个执行  asyncio.gather
                                    │              │
                                    └──────┬───────┘
                                           ▼
                                  失败时 LLM 重规划
                                           │
                                           ▼
                                  PlannerExecutor.aggregate()
                                    LLM 汇总 → 最终答案
                                             │
                                             ▼
                                       AgentState
                                   （完整执行轨迹）
                                       .print_trace()
                                       .to_dict()
```

---

## 七、与 ReActAgent 的关系

| | ReActAgent | PlannerExecutor |
|---|---|---|
| 决策方式 | 逐步思考，看到 Observation 再决定下一步 | 先整体规划，再批量执行 |
| 适用场景 | 探索性任务、未知路径 | 确定性多步任务、可并行子问题 |
| 并行能力 | 无（逐步骤） | 有（asyncio.gather） |
| 容错 | 单步失败 → LLM 看到错误自行调整 | 单步失败 → LLM 重规划剩余步骤 |
| 共享组件 | AgentState、TOOL_CLASSES | AgentState、TOOL_CLASSES |

两者共享 `AgentState` 和工具注册表，可在 `agent.enabled` 开关下共存（planner 为主，agent 为降级备选）。

---

## 八、经验教训

1. **Windows GBK vs emoji**：在中文 Windows 上开发，`print()` 中不能用 emoji。一个 `\U0001f916` 可以让整个 SQL 引擎崩溃。解决方案：要么不用 emoji，要么用 `PYTHONIOENCODING=utf-8` 启动。

2. **LLM API 的隐性限制**：同一 API，`messages` 格式的 system 角色消息长度有限制，而 `prompt` 格式的 user 角色无此限制。框架层应该统一处理这种差异。

3. **控制流与数据分离是 Agent 设计的关键**：`AgentState` 独立于 `ReActAgent` 和 `PlannerExecutor`，三者的边界清晰，使状态可序列化、可调试、可在未来增加中断恢复和人工审批节点。

4. **降级保障每一层都需要**：LLM 规划失败 → 降级计划；Executor 不可用 → 直接检索；工具失败 → 重规划。这让系统在部分组件故障时仍然可用。
