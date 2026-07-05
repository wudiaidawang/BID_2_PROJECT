# 更新日志 11 — Checkpoint 闭环 + fast/think 双模路由 + 原生 Memory 模块

日期: 2026-06-10

## 背景

三个遗留问题集中解决:

1. **Checkpoint 只写不读** — `save_checkpoint()` 每步都在写，但 `load_checkpoint()` 代码库里没有任何调用点，断点续跑形同虚设
2. **复杂度判定拍脑袋** — AutoRouter 的 `IntentRouter` 用一个 LLM 调用同时输出 type + complexity，没有做 Task 分解就判断"这是多步问题"，判定依据不可靠
3. **系统无记忆** — Redis 只存了最近 N 轮 Q&A 文本 + 简单指代消解（"它"→项目名），没有跨 session 知识积累

## 改动

### 一、Checkpoint 系统闭环

**react_agent.py:**
- 修复 `session_id` 默认值 `""` 导致所有断点覆盖 `default.json` 的 bug (改为 `None`)
- 新增 `resume()` 方法: 加载断点 → 检查是否完成 → 未完成则从 `state.current_step` 继续 ReAct 循环
- 核心循环提取为 `_run_loop()`，`run()` 和 `resume()` 共用

**planner.py:**
- `execute()` 新增 `session_id` 参数
- DAG 主阶段完成后、每次重规划后、最终返回前自动保存断点
- `aggregate()` 所有返回路径自动删除断点

**routes.py:**
- 新增 `_try_resume_checkpoint()`: `/ask` 入口自动检测未完成断点并恢复（Agent 优先，Planner 降级）
- `DELETE /session/{id}` 同步清理 checkpoint 文件

### 二、fast/think 双模路由

**问题:** 旧的 `IntentRouter` 用一个 LLM 调用拍脑袋判 single_step vs multi_step，没有任务分解。而 `PlannerRouter` 是先做 TaskAnalysis 再判——但 AutoRouter 恰恰是先判复杂度再决定是否用 Planner，循环依赖。

**router.py 重构:**

| 新增 | 说明 |
|------|------|
| `quick_intercept()` 模块函数 | 从 IntentRouter 提取，FastRouter/ThinkRouter 共用 |
| `FastRouter` | 关键词拦截 → BinaryRouter 三路投票判 SQL/RAG，0~1 次 LLM |
| `ThinkRouter` | 关键词拦截 → TaskAnalysis → 按实际 task 数量分流，1~2 次 LLM |
| `PlannerRouter.plan_from_tasks()` | 跳过 TaskAnalysis，直接从已有 tasks 做 ToolPlanning |

**ThinkRouter 分流逻辑:**
```
TaskAnalysis (1 LLM)
  ├─ confidence < 0.3 或无 tasks → 降级 BinaryRouter
  ├─ 1 task → BinaryRouter 判 SQL/RAG（兼容输出，不浪费 Planner 开销）
  └─ 2+ tasks → plan_from_tasks (1 LLM) → Planner DAG
```

**关键修复:** 复杂度不再拍脑袋。TaskAnalysis 拆出几个 task 就是几步。单任务问题走 BinaryRouter，零 LLM 规划开销。

**config.yaml:** 默认模式改为 `think`，保留旧值兼容

### 三、原生 Memory 模块

仿 LangChain memory API 设计，纯 Python 实现，JSON 文件存储。

**新增 `app/core/memory/` 模块:**

| 文件 | 类 | 功能 |
|------|-----|------|
| `base.py` | `BaseMemory` | 抽象基类 — `load_memory_variables` / `save_context` / `clear` |
| `buffer.py` | `ConversationBufferWindowMemory` | 窗口缓冲最近 K 轮对话，持久化 JSON |
| `buffer.py` | `ConversationSummaryMemory` | 超出窗口的旧对话 LLM 自动压缩为摘要 |
| `entity.py` | `EntityMemory` | 跨 session 实体积累（项目名/公司/法条号），精确查找+模糊搜索 |
| `manager.py` | `MemoryManager` | 统一协调器 — `load_context()` 注入上下文，`save_turn()` 保存对话 |

**存储格式:**
```
memory_store/
  ├── entities.json          # 全局实体库 (跨 session)
  └── {session_id}/
      ├── conversation.json   # 对话轮次
      └── summary.json        # LLM 摘要
```

**集成点:**
- `main.py`: lifespan 初始化 `MemoryManager` 挂到 `app.state.memory`
- `routes.py`: 请求前 `load_context()` 注入 prompt，回答后 `save_turn()` + `maybe_summarize()`
- `generator.py`: `generate_with_history()` 新增 `memory_context` 参数，拼入 prompt 最前端
- `routes.py`: `DELETE /session` 同步调用 `forget_session()`

### 四、README 全面刷新

- API 响应格式修正 (`source`/`is_sql` → `sources`/`processing_time`/`session_id`)
- 新增请求流程图（Session → Checkpoint → Router → Execute → Cleanup）
- fast/think 双模路由文档替换旧 4 模文档
- 断点续跑读写闭环说明（自动保存 → 自动恢复 → 自动清理）
- 项目结构更新

## 文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/agent/react_agent.py` | 重构 | resume() 断点续跑 + session_id bug 修复 |
| `app/agent/planner.py` | 修改 | execute()/aggregate() 全流程接入 checkpoint |
| `app/core/router.py` | 重构 | quick_intercept 提取 + FastRouter + ThinkRouter + plan_from_tasks |
| `app/core/memory/__init__.py` | 新建 | 导出 MemoryManager |
| `app/core/memory/base.py` | 新建 | BaseMemory 抽象基类 |
| `app/core/memory/buffer.py` | 新建 | BufferWindowMemory + SummaryMemory |
| `app/core/memory/entity.py` | 新建 | EntityMemory 跨 session 实体积累 |
| `app/core/memory/manager.py` | 新建 | MemoryManager 统一协调器 |
| `app/core/generator.py` | 修改 | generate_with_history 新增 memory_context 参数 |
| `app/api/routes.py` | 修改 | checkpoint 恢复 + memory 注入 + session 删除清理 |
| `main.py` | 修改 | MemoryManager 初始化 + think 模式 PlannerExecutor 初始化 |
| `config.yaml` | 修改 | router.mode 改为 think |
| `CLAUDE.md` | 修改 | 架构文档更新 |
| `README.md` | 重写 | 全面刷新，API 修正 + fast/think 文档 + 请求流程图 |
