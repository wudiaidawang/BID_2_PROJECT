# 更新日志 10 — 自适应路由系统 (AutoRouter)

日期: 2026-06-07

## 背景

之前的路由模式 (`binary` / `intent` / `planner`) 是静态配置的——一个问题要么全部走简单 RAG，要么全部走 Planner。实际场景中简单问题和复杂问题交替出现，手动开关不现实。

## 改动

### 新增 `AutoRouter` (`app/core/router.py`)

自适应路由: IntentRouter 先判意图+复杂度 → 按结果自动分流。

```
Question
  ↓
IntentRouter (type + complexity)
  ├─ greeting/thanks/unrelated → 直接返回预设响应 (0次LLM)
  ├─ stat_query               → BinaryRouter 模板匹配 → SQL路径
  ├─ single_step              → 直接 search_unified() RAG
  └─ multi_step               → PlannerRouter 规划 → PlannerExecutor DAG执行
```

### `routes.py` 适配

- `ask()` 支持 4 种 `route.mode`: `direct` / `auto` / `planner` / `binary`
- 新增 `_handle_direct()`: 问候语/致谢/无关问题直接返回，不走检索和LLM

### `main.py` 适配

- `router.mode = "auto"` 时也初始化 `PlannerExecutor`（用于复杂问题分流）

### `config.yaml`

- `router.mode` 默认值改为 `"auto"`
- 文档注释更新

### Agent 工具增强 (`app/agent/agent_tools.py`)

- `SearchRegulationsTool` 从单库 `search("regulations")` 升级为 `search_unified()` 双库统一召回
- `_format_source` 兼容法规和项目两种结果类型的格式化

## 文件变更

| 文件 | 操作 |
|------|------|
| `app/core/router.py` | 新增 AutoRouter 类，create_router 注册 auto 模式 |
| `app/api/routes.py` | ask() 支持 direct/auto/planner 分流，新增 _handle_direct |
| `main.py` | auto 模式初始化 PlannerExecutor |
| `config.yaml` | router.mode 默认值改为 auto |
| `app/agent/agent_tools.py` | SearchRegulationsTool 升级为双库统一召回 |
| `CLAUDE.md` | 更新路由模式文档 |
| `README.md` | 更新架构图/功能/配置说明 |
