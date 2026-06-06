# 基于Agent + Hybrid RAG双引擎的招投标智能问答系统

Bidding & Tendering Intelligent Q&A System — 基于 RAG + SQL 双引擎的招投标法规与数据智能问答平台。

## 功能

- **法规检索问答**：基于《招标投标法》《政府采购法》等 PDF 法规库，支持概念定义、处罚规定、操作流程等自然语言提问
- **数据统计查询**：基于 SQLite 数据库，支持"去年有多少项目""中标金额最高的是哪个"等统计类 NL2SQL 查询
- **混合检索**：向量检索 (ChromaDB) + 关键词检索 (BM25/jieba) + RRF/Weighted 融合 + BGE-Reranker 精排
- **Query 改写管道**：标点规范化 → 冗余精简 → 口语转书面语 → 行业同义词替换，纯规则零 API 调用
- **Parent-Child Chunking**：法律条文结构化切块（法律→章→条），检索 child chunk → 补全 parent context
- **多轮对话**：Redis 会话管理 + 指代消解，支持上下文理解和追问
- **Agent 模式**：ReAct 循环 (Thought → Action → Observation) + Planner DAG 调度，支持多工具调用与断点续跑
- **多厂商 LLM**：混元 / DeepSeek / OpenAI / 本地模型，改 `config.yaml` 一行切换
- **模型基准测试**：独立 benchmark 工具，固定问题集 + 多模型对比 + 结果归档

## 架构

```
main.py                     FastAPI 入口
├── app/api/routes.py       POST /api/v1/ask  问答接口
│                           GET  /api/v1/health  健康检查
│                           DELETE /api/v1/session/{id}  会话管理
├── app/core/
│   ├── router.py           路由层 (Binary 三路投票 / Intent 意图分类 / Planner 两阶段规划)
│   ├── retriever.py        混合检索器 (ChromaDB + BM25 + RRF + Reranker)
│   ├── sql_engine.py       NL2SQL 引擎 (LLM 生成 SQL → SQLite 执行)
│   ├── generator.py        LLM 生成器 (支持多厂商 API，OpenAI 兼容)
│   ├── embedding.py        Embedding 服务 (BGE/M3E/GTE 系列，HF 镜像)
│   ├── session_manager.py  Redis 多轮会话管理 + 指代消解
│   ├── query_rewriter.py   4 层 Query 改写管道 (标点→冗余→口语→同义词)
│   ├── query_normalizer.py 向后兼容旧接口
│   ├── config_loader.py    YAML 配置加载器
│   └── fusion_weighted.py  Weighted 融合策略 (BM25/向量动态权重)
├── app/agent/
│   ├── react_agent.py      ReAct Agent (Thought → Action → Observation 循环)
│   ├── planner.py          Planner Executor (Task 分析 → 工具规划 → DAG 调度 → 汇总)
│   ├── agent_state.py      结构化状态容器 + 断点续跑 (checkpoint)
│   └── agent_tools.py      工具集 (法规检索/法条查询/SQL统计/RAG总结)
├── app/pipeline/           可观测检索 Pipeline (preprocess → retrieve → fuse → merge → expand → rerank)
├── app/storage/
│   ├── chroma_store.py     ChromaDB 持久化客户端 (多集合)
│   └── redis_client.py     Redis 异步连接管理
├── app/schema/             Chunk 元数据规范化
├── app/utils/              中文数字转换等工具
└── model_benchmark/        模型基准测试工具 (独立于主项目)
```

## 快速开始

### 环境要求

- Python 3.10+
- Redis (会话管理)
- 8GB+ 内存 (本地运行 embedding & reranker 模型)

### 安装

```bash
git clone https://github.com/your-org/bid-qa-system.git
cd bid-qa-system
pip install -r requirements.txt
```

### 配置

所有配置集中在 `config.yaml`，支持环境变量覆盖 (`.env`)：

```bash
# 编辑 config.yaml → 修改 llm.provider、embedding.model_name 等
# 编辑 .env → 填入 LLM_API_KEY (或直接在 config.yaml 对应 provider 下填 api_key)
```

配置优先级：**环境变量 > config.yaml > 代码默认值**

### 初始化数据

```bash
# 1. 导入招标数据 Excel → SQLite + ChromaDB 'bids' 集合
python init_db.py

# 2. 切块 PDF 法规 → ChromaDB 'regulations' 集合
python init_pdf.py
```

### 启动

```bash
python main.py
# 服务运行在 http://0.0.0.0:8000
# API 文档 http://0.0.0.0:8000/docs
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
  "session_id": "optional-session-id"
}
```

Response:

```json
{
  "answer": "根据《招标投标法》第五十三条...",
  "source": "regulations",
  "is_sql": false,
  "sources": [...]
}
```

### GET /api/v1/health

### DELETE /api/v1/session/{session_id}

## Agent 模式

### ReAct Agent

```python
from app.agent.react_agent import ReActAgent

agent = ReActAgent(retriever, llm, max_steps=5)
answer = await agent.run("围标怎么处罚")
# agent.last_state 包含完整执行轨迹 + 统计
agent.last_state.print_trace()
```

### Planner (DAG 调度)

```python
from app.agent.planner import PlannerExecutor
from app.core.router import PlannerRouter

router = PlannerRouter(llm=llm)
plan = await router.plan("工程类和货物类去年的中标金额对比")

executor = PlannerExecutor(retriever=None, llm=llm)
state = await executor.execute(plan, question)
answer = await executor.aggregate(state, question)
```

### 断点续跑 (Checkpoint)

Agent 每执行一步自动保存状态快照到本地文件，进程崩溃后可从中断处恢复：

```python
from app.agent.agent_state import AgentState

# 崩溃后恢复
state = AgentState.load_checkpoint("./checkpoints", session_id="abc123")
# state.steps 包含所有已完成步骤，state.current_step 指向最后一步
```

配置：`config.yaml` → `agent.checkpoint.enabled: true`

### 工具注册

工具声明式管理，增删改查只需修改 `config.yaml` 的 `agent.tools` 部分：

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
```

## 模型基准测试

`model_benchmark/` 是独立于主项目的模型评估工具，固定问题集 + 多模型/多 API 对比：

```bash
cd model_benchmark
pip install -r requirements.txt
python run.py --model glm-4-9b --api-url http://localhost:8000/v1
```

结果按模型归档到 `model_benchmark/output/{model}/{timestamp}.json`。

## 评估

基于手工标注的 RAG 问答对评测：

| 指标 | 分数 |
|------|------|
| 路由分类准确率 | **99.0%** |
| 检索 Top-5 Recall | **92.0%** |
| 检索 Top-3 Recall | **89.0%** |
| 检索 Top-1 Recall | **83.0%** |

```bash
python eval_retrieval_accuracy.py
```

## 配置总览

全部配置在 `config.yaml` 中集中管理：

| 模块 | 可配置项 |
|------|---------|
| LLM | provider, api_url, api_key, model, temperature, max_tokens, timeout |
| Embedding | model_name (bge-small/bge-large/m3e/gte-large/custom), dimension, device |
| Reranker | enabled, model, max_input_length, candidate_pool, device |
| 检索 | top_k, vector_recall, bm25_recall, fusion_strategy (rrf/weighted/smart), 分数阈值 |
| 路由 | mode (binary/intent/planner), template_match_threshold, 三路投票 |
| Agent | enabled, max_steps, temperature, tools 声明式注册, checkpoint 配置 |
| 会话 | backend (redis/sqlite), ttl, max_history |
| 查询改写 | colloquial_to_formal, redundancy_removal, synonym_expansion, llm_reference_resolution |
| 法律切块 | parent_context_enabled, child_split_threshold, header_injection_enabled |
| Pipeline | 各阶段独立开关 + 断路器 (fail_open/fail_close) + 可观测性追踪 |
| 中文数字 | 映射表 + 动态转换 |

## 项目结构

```
.
├── main.py                    FastAPI 入口
├── config.py                  pydantic-settings 配置定义
├── config.yaml                统一配置文件
├── requirements.txt           Python 依赖
├── init_db.py                 招标数据导入 (Excel → SQLite + ChromaDB)
├── init_pdf.py                PDF 法规导入 (结构化切块 → ChromaDB)
├── ask_cli.py                 命令行交互客户端
├── test_agent.py              Agent Planner 端到端测试
├── eval_retrieval_accuracy.py 检索精度评估
├── app/                       核心应用代码
│   ├── api/                   FastAPI 路由 + Schema
│   ├── core/                  检索引擎 / 路由 / LLM / 查询改写
│   ├── agent/                 Agent 模式 (ReAct + Planner + State)
│   ├── pipeline/              可观测检索 Pipeline
│   ├── storage/               ChromaDB + Redis
│   ├── schema/                元数据规范化
│   └── utils/                 工具函数
├── data/
│   ├── bid_data.xlsx          招标项目数据
│   ├── bid_data.db            SQLite 数据库
│   ├── pdfs/                  PDF 法规文件
│   ├── colloquial_map.json    口语→书面语映射 (66条)
│   └── eval_questions/        评估问答集
├── model_benchmark/           模型基准测试工具 (独立)
└── chroma_db/                 向量数据库 (本地生成)
```

## License

MIT
