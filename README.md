# 招投标智能问答系统 v5.1

RAG + SQL 双引擎招投标智能问答平台 — 基于 FastAPI，支持法规检索、数据统计、Agent 规划三种模式自适应路由。

## 功能特性

- **fast/think 双模路由**：快速模式 BinaryRouter 直判 SQL/RAG (0~1 LLM)，思考模式 TaskAnalysis 分解 → 基于 task 数量自适应分流 Planner DAG (1~2 LLM)；复杂度不再拍脑袋
- **法规检索**：基于《招标投标法》《政府采购法》等 PDF 法规库，支持概念定义、处罚规定、操作流程等自然语言提问
- **数据统计 (NL2SQL)**：LLM 生成 SQL → SQLite 执行，支持"去年有多少项目""中标金额最高的是哪个"等聚合查询，含模板短路优化
- **混合检索 Pipeline**：5 阶段可观测管道 — 查询改写 → 分库召回 (ChromaDB + BM25) → RRF/Weighted 融合 → Parent-Context 扩展 → BGE-Reranker 精排
- **Query 改写**：3 层规则管道 — 口语→书面语 + 冗余精简 + 行业同义词替换，零 API 调用
- **双模路由 (fast/think)**：快速模式 BinaryRouter 直判 SQL/RAG，思考模式 TaskAnalysis → 基于实际 task 数量分流 Planner DAG；复杂度不再"拍脑袋"
- **断点续跑**：每步自动保存状态快照，崩溃后自动恢复未完成的 Agent/Planner 执行，任务完成或会话删除时自动清理
- **4 个 Agent 工具**：search_regulations（双库统一检索）、get_article（法条精确查询）、sql_query（NL2SQL 统计）、summarize（多段归纳）
- **Parent-Child Chunking**：法律条文结构化切块（法律→章→条），child chunk 检索后自动补全 parent context
- **多轮对话**：Redis 会话管理 + 指代消解 + 实体提取
- **多厂商 LLM**：混元 / DeepSeek / OpenAI 兼容 API，改 `config.yaml` 一行切换

## 架构

```
main.py                         FastAPI 入口 (lifespan 初始化 6 组件)
├── app/api/routes.py           POST /api/v1/ask         问答接口
│                               GET  /api/v1/health       健康检查
│                               DELETE /api/v1/session/{id} 会话+断点清理
├── app/core/
│   ├── router.py               路由层 — ThinkRouter / FastRouter / BinaryRouter / PlannerRouter
│   ├── retriever.py            混合检索器 — search_unified() 跨库召回
│   ├── sql_engine.py           NL2SQL 引擎 — LLM 生成 SQL → SQLite 执行 → 空结果自动降级
│   ├── generator.py            LLM 生成器 — 多厂商 API (OpenAI 兼容)，统一 _call_llm 接口
│   ├── embedding.py            Embedding 服务 — BGE/M3E/GTE 系列，HF 镜像加速
│   ├── session_manager.py      Redis 多轮会话 + 指代消解 + 实体提取
│   └── query_rewriter.py       3 层 Query 改写管道 (口语→书面语 + 冗余精简 + 同义词)
├── app/agent/
│   ├── react_agent.py          ReAct Agent — Thought→Action→Observation 循环 (max 5 steps)
│   ├── planner.py              PlannerExecutor — DAG 调度 + 自动重规划 + 并行执行
│   ├── agent_state.py          AgentState — 结构化执行轨迹 + 断点序列化/恢复/清理
│   └── agent_tools.py          4 工具: search_regulations / get_article / sql_query / summarize
├── app/pipeline/               可观测检索 Pipeline (preprocess→retrieve→fuse→merge→expand→rerank)
├── app/storage/                ChromaDB 持久化 + Redis 连接管理
├── app/schema/                 Chunk 元数据规范化
├── config.yaml                 统一配置文件 (LLM/Embedding/检索/路由/Agent/Pipeline)
├── config.py                   pydantic-settings 配置定义
├── init_db.py                  招标数据导入 (Excel → SQLite + ChromaDB 'bids')
├── init_pdf.py                 PDF 法规导入 (结构化切块 → ChromaDB 'regulations')
└── ask_cli.py                  命令行交互客户端
```

### 请求流程

```
用户问题
  → Session 管理 (Redis 获取/创建 + 指代消解)
    → 断点续跑检查 (存在未完成 checkpoint? → 自动恢复)
      → 路由判定 (ThinkRouter)
          ├─ greeting/thanks    → 直接响应 (0 LLM 调用)
          ├─ 低置信度/0 task    → 降级 BinaryRouter → SQL or RAG
          ├─ 1 task             → BinaryRouter → SQL or RAG (兼容输出)
          └─ 2+ tasks           → ToolPlanning → PlannerExecutor DAG 执行
            → LLM 生成最终答案
              → 实体提取 → 保存 Session → 清理 Checkpoint
```

## 快速开始

### 环境要求

- Python 3.10+
- Redis (会话管理)
- 8GB+ 内存 (本地运行 embedding & reranker 模型)

### 安装

```bash
git clone https://github.com/wudiaidawang/BID_2_PROJECT.git
cd BID_2_PROJECT
pip install -r requirements.txt
```

### 配置

```bash
# 编辑 config.yaml — 修改 llm.provider、router.mode、检索参数等
# 编辑 .env — 填入 LLM_API_KEY 或各 provider 的 api_key
```

配置优先级：**环境变量 > config.yaml > 代码默认值**

```yaml
# config.yaml 关键配置
router:
  mode: think        # fast / think

llm:
  provider: hunyuan   # hunyuan / deepseek / openai
  model: hunyuan-lite

agent:
  enabled: false      # 启用 ReAct Agent (备选执行器)
  max_steps: 5
  checkpoint:
    enabled: true     # 断点续跑
    dir: "./checkpoints"
```

### 初始化数据

```bash
python init_db.py      # Excel → SQLite + ChromaDB 'bids' 集合
python init_pdf.py     # PDF 法规切块 → ChromaDB 'regulations' 集合
```

### 启动

```bash
python main.py
# 服务运行在 http://0.0.0.0:8000
# Swagger: http://0.0.0.0:8000/docs
```

### 命令行交互

```bash
python ask_cli.py
```

## API

### POST /api/v1/ask

```json
{
  "question": "串通投标的行政处罚是什么？",
  "top_k": 5,
  "session_id": "optional-session-id"
}
```

Response:

```json
{
  "answer": "根据《招标投标法》第五十三条，投标人相互串通投标...",
  "sources": [
    {
      "title": "招标投标法 第五十三条",
      "project_name": "",
      "winner": "",
      "winner_amount": 0.0,
      "content_preview": "投标人相互串通投标的，中标无效...",
      "source_type": "regulations",
      "score": 0.92
    }
  ],
  "processing_time": 1.23,
  "session_id": "abc123-def456"
}
```

### GET /api/v1/health

### DELETE /api/v1/session/{session_id}

删除会话及其关联的 checkpoint 文件。

## Agent 模式

### fast / think 双模路由

| 模式 | 说明 | LLM 调用 | config.yaml |
|------|------|----------|-------------|
| **fast** | 不走 Agent 规划，BinaryRouter 3路投票直判 SQL/RAG | 0~1 次 | `router.mode: fast` |
| **think** | TaskAnalysis 分解 → 基于实际 task 数量分流 | 1~2 次 | `router.mode: think` |

**fast 模式流程:** quick_intercept(关键词) → BinaryRouter(3路投票) → SQL or RAG

**think 模式流程:** quick_intercept → TaskAnalysis → 
- confidence < 0.3 或 0 task → 降级 BinaryRouter
- 1 task → BinaryRouter 判 SQL/RAG（兼容输出）
- 2+ tasks → ToolPlanning → PlannerExecutor DAG

**复杂度判定不再"拍脑袋"**——think 模式先做 Task 分解，基于实际需要几个 task 来决定走单步还是多步。

**ReAct Agent** — 一步一步思考，每步看到 Observation 再决定下一步：

```python
from app.agent.react_agent import ReActAgent

agent = ReActAgent(retriever, llm, max_steps=5, session_manager=sm)
answer = await agent.run("围标和串标的处罚有什么区别", session_id="abc123")

# 完整执行轨迹
agent.last_state.print_trace()
print(agent.last_state.tool_call_count)  # {"search_regulations": 2}
```

**PlannerExecutor** — 先规划再执行，DAG 调度自动并行：

```python
from app.agent.planner import PlannerExecutor
from app.core.router import PlannerRouter

router = PlannerRouter(llm=llm)
plan = await router.plan("工程类和货物类去年的中标金额对比")

executor = PlannerExecutor(retriever, llm)
state = await executor.execute(plan, question, session_id="abc123")
answer = await executor.aggregate(state, question)
```

### 断点续跑

Agent 每执行一步自动保存状态快照。进程崩溃后，下次请求同一 session 自动恢复：

```python
# 手动恢复
from app.agent.agent_state import AgentState

state = AgentState.load_checkpoint("./checkpoints", session_id="abc123")
print(f"已完成 {state.step_count()} 步, 当前第 {state.current_step} 步")

# ReActAgent 恢复
answer = await agent.resume("abc123")
```

配置：

```yaml
agent:
  checkpoint:
    enabled: true       # 开启断点续跑
    dir: "./checkpoints"  # 断点文件目录
```

### 工具注册

工具声明式管理，增删改查只需修改 `config.yaml`：

```yaml
agent:
  tools:
    - name: "search_regulations"
      class_path: "app.agent.tools.SearchRegulationsTool"
      enabled: true
    - name: "get_article"
      class_path: "app.agent.tools.GetArticleTool"
      enabled: true
    - name: "sql_query"
      class_path: "app.agent.tools.SQLQueryTool"
      enabled: true
    - name: "summarize"
      class_path: "app.agent.tools.SummarizeTool"
      enabled: true
```

## 模型基准测试

`model_benchmark/` 是独立于主项目的模型评估工具：

```bash
cd model_benchmark
pip install -r requirements.txt
python run.py --model glm-4-9b --api-url http://localhost:8000/v1
```

结果按模型归档到 `model_benchmark/output/{model}/{timestamp}.json`。

## 评估

```bash
python eval_retrieval_accuracy.py
```

| 指标 | 分数 |
|------|------|
| 路由分类准确率 | 99.0% |
| 检索 Top-5 Recall | 92.0% |
| 检索 Top-3 Recall | 89.0% |
| 检索 Top-1 Recall | 83.0% |

## 配置总览

| 模块 | 可配置项 |
|------|---------|
| LLM | provider, api_url, api_key, model, temperature, max_tokens, timeout |
| Embedding | model_name (bge-small/bge-large/m3e/gte-large), dimension, device |
| Reranker | enabled, model (bge-reranker-base), max_input_length, candidate_pool |
| 检索 | top_k, vector_recall, bm25_recall, fusion_strategy (rrf/weighted/smart), 分数阈值 |
| 路由 | mode (fast/think), template_match_threshold, 三路投票 |
| Agent | enabled, max_steps, temperature, tools 声明式注册, checkpoint (enabled/dir) |
| 会话 | Redis host/port/db, ttl, max_history |
| Query 改写 | colloquial_to_formal, redundancy_removal, synonym_expansion |
| 法律切块 | parent_context_enabled, child_split_threshold |
| Pipeline | 各阶段独立开关 + 断路器 (fail_open/fail_close) + 可观测性追踪 |

## 项目结构

```
.
├── main.py                     FastAPI 入口
├── config.py                   pydantic-settings 配置
├── config.yaml                 统一配置文件
├── requirements.txt            Python 依赖
├── init_db.py                  招标数据导入 (Excel → SQLite + ChromaDB)
├── init_pdf.py                 PDF 法规导入 (结构化切块 → ChromaDB)
├── ask_cli.py                  命令行交互客户端
├── eval_retrieval_accuracy.py  检索精度评估
├── app/
│   ├── api/                    FastAPI 路由 + Schema
│   ├── core/                   检索引擎 / 路由 / LLM / SQL / 查询改写
│   ├── agent/                  Agent 模式 (ReAct + Planner + State + Tools)
│   ├── pipeline/               可观测检索 Pipeline
│   ├── storage/                ChromaDB + Redis
│   ├── schema/                 元数据规范化
│   └── utils/                  工具函数
├── data/
│   ├── bid_data.xlsx           招标项目数据 (~8000条)
│   ├── bid_data.db             SQLite 数据库
│   ├── pdfs/                   PDF 法规文件
│   ├── colloquial_map.json     口语→书面语映射 (66条)
│   └── eval_questions/         评估问答集
├── model_benchmark/            模型基准测试工具 (独立)
├── checkpoints/                断点文件目录
└── chroma_db/                  向量数据库 (本地生成)
```

## License

MIT
