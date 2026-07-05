# 招投标智能问答系统 v5.6 — 召回率 93.5%（绝对命中 89.5%）

RAG + SQL 双引擎招投标智能问答平台 — 基于 FastAPI，Milvus 向量库 + BGE-M3 远程 Embedding，三库检索（regulations + bids + policy），6 大数据分类，fast/think 双模自适应路由。

## 功能特性

- **Milvus 向量库**：3 个 collection（bids / regulations / policy），HNSW Dense 向量检索 + 本地 jieba BM25 关键词检索，SSH 隧道连接远程服务
- **BGE-M3 远程 Embedding**：1024 维，Embedding / Reranker 均走远程模型服务 API，失败自动 fallback 本地
- **fast/think 双模路由**：FastRouter 关键词+三路投票直判 SQL/RAG (0~1 LLM)，ThinkRouter TaskAnalysis 分解 → 按实际 task 数量自适应分流 Planner DAG (1~2 LLM)
- **6 大数据分类**：政策信息 + 招标公告 + 舆情信息 + 企业画像 + 价格信息 + 商品参数，覆盖招投标全链条
- **Memory 模块**：Buffer + Summary 双缓冲 + Entity 实体追踪，SQLite 持久化，跨 session 知识积累
- **法规检索**：基于《招标投标法》《政府采购法》等 PDF 法规库 + 实务法律解读，支持概念定义、处罚规定、操作流程等自然语言提问
- **数据统计 (NL2SQL)**：LLM 生成 SQL → SQLite 执行（5 张表：bids + enterprise + price + product + policy），含模板短路优化
- **混合检索 Pipeline**：5 阶段可观测管道 — 查询改写 → 分库召回 (Dense + BM25) → RRF/Weighted 融合 → Parent-Context 扩展 → BGE-Reranker 精排，含条款号精确匹配 boost
- **Query 改写**：中文数字→阿拉伯数字规范化（"第三十七条"→"第37条"）+ 口语→书面语 + 冗余精简 + 同义词替换，法规名称保护
- **断点续跑**：每步自动保存状态快照，崩溃后自动恢复未完成的 Agent/Planner 执行，任务完成或会话删除时自动清理
- **Agent 工具**：search_regulations（法规检索）、get_article（法条精确查询）、sql_query（NL2SQL 统计）、search_market_price（市场行情，待接入）、search_qualification（企业资质，待接入）
- **Parent-Child Chunking**：法律条文结构化切块（法律→章→条），自然段归并切分，child chunk 检索后自动补全 parent context
- **多轮对话**：Redis / SQLite 双后端会话管理 + 指代消解 + 实体提取，Redis 不可用时自动降级
- **多厂商 LLM**：混元 / DeepSeek / OpenAI 兼容 API，改 `config.yaml` 一行切换

## 架构

```
main.py                         FastAPI 入口 (lifespan 初始化 7 组件)
├── app/api/routes.py           POST /api/v1/ask         问答接口
│                               GET  /api/v1/health       健康检查
│                               DELETE /api/v1/session/{id} 会话+断点清理
├── app/core/
│   ├── router.py               路由层 — ThinkRouter / FastRouter / BinaryRouter / PlannerRouter
│   ├── retriever.py            混合检索器 — search_unified() 三库召回 (regulations + bids + policy)
│   ├── sql_engine.py           NL2SQL 引擎 — LLM 生成 SQL → SQLite 5 表执行 → 空结果自动降级 RAG
│   ├── generator.py            LLM 生成器 — 多厂商 API (OpenAI 兼容)，统一 _call_llm 接口
│   ├── embedding.py            Embedding 服务 — 远程优先 (BGE-M3 API) + 本地 fallback (M3E)
│   ├── model_client.py         远程模型服务客户端 — HTTP API 调用 embedding / rerank
│   ├── session_manager.py      会话管理 + 指代消解 + 实体提取，Redis 不可用时自动降级
│   ├── memory/                 Memory 模块 — Buffer+Summary 双缓冲 + SQLite/JSON 持久化
│   │   ├── manager.py          MemoryManager — 加载/保存对话上下文
│   │   ├── buffer.py           ConversationBuffer + SummaryMemory
│   │   └── entity.py           实体追踪 (项目名/中标人/时间/金额/法条号)
│   └── query_rewriter.py       3 层 Query 改写管道 + 中文数字规范化 + 法规名称保护
├── app/agent/
│   ├── react_agent.py          ReAct Agent — Thought→Action→Observation 循环 (max 5 steps)
│   ├── planner.py              PlannerExecutor — DAG 调度 + 检索合并 + 自动重规划 + 并行执行
│   ├── agent_state.py          AgentState — 结构化执行轨迹 + 断点序列化/恢复/清理
│   └── agent_tools.py          5 工具: search_regulations / get_article / sql_query / search_market_price / search_qualification
├── app/pipeline/               可观测检索 Pipeline (preprocess→retrieve→fuse→merge→expand→rerank)
├── app/storage/
│   ├── __init__.py             向量库工厂 — backend 配置自动切换 ChromaStore / MilvusStore
│   ├── chroma_store.py         ChromaDB 持久化客户端
│   ├── milvus_store.py         Milvus REST v2 客户端 (Dense HNSW + Sparse BM25)
│   └── redis_client.py         Redis 连接管理，不可用时自动降级
├── app/schema/                 Chunk 元数据规范化
├── config.yaml                 统一配置文件 (LLM/Embedding/向量库/检索/路由/Agent/Pipeline)
├── config.py                   pydantic-settings 配置定义
├── init_db.py                  招标数据导入 (Excel → SQLite + VectorStore 'bids')
├── init_policy_collection.py   政策+舆情+PDF 全量导入 (Excel+PDF → VectorStore 'policy')
├── init_sqlite_tables.py       SQLite enterprise/price/product 建表 + 聚合导入
├── rechunk_shiwu.py            实务 PDF 重新切分 (自然段归并)
└── ask_cli.py                  命令行交互客户端
```

### 请求流程

```
用户问题
  → Session 管理 (Redis/SQLite 获取/创建 + context_resolver 指代消解)
    → Memory 模块加载历史上下文 (Buffer + Summary + 实体追踪)
      → 断点续跑检查 (存在未完成 checkpoint? → 自动恢复)
        → 路由判定 (ThinkRouter)
            ├─ greeting/thanks    → 直接响应 (0 LLM 调用)
            ├─ 低置信度/0 task    → 降级 BinaryRouter → SQL or RAG
            ├─ 1 task             → BinaryRouter → SQL or RAG (兼容输出)
            └─ 2+ tasks           → ToolPlanning → PlannerExecutor DAG 执行
              → LLM 生成最终答案
                → 实体提取 → 保存 Memory → 保存 Session → 清理 Checkpoint
```

## 快速开始

### 环境要求

- Python 3.10+
- Redis (可选，会话管理；不可用时自动降级)
- SSH 隧道到服务器 (Milvus + Embedding/Reranker 服务)

### 安装

```bash
git clone https://github.com/wudiaidawang/BID_3_PROJECT_langchain.git
cd BID_3_PROJECT_langchain
pip install -r requirements.txt
```

### 配置

```bash
# 编辑 config.yaml — 修改 llm.provider、vector_store.backend、router.mode 等
# 编辑 .env — 填入 LLM_API_KEY 或各 provider 的 api_key
```

配置优先级：**环境变量 > config.yaml > 代码默认值**

```yaml
# config.yaml 关键配置
router:
  mode: think          # fast / think

llm:
  provider: hunyuan    # hunyuan / deepseek / openai
  model: hy3-preview

vector_store:
  backend: milvus      # chroma / milvus — 向量库后端切换

embedding:
  model_name: bge-m3   # bge-m3 (1024维) / bge-small (512维) / m3e (768维)
  model_service_url: localhost:8210  # 远程 Embedding API

session:
  backend: redis       # redis / sqlite — 会话存储后端切换

agent:
  enabled: false       # 启用 ReAct Agent (备选执行器)
  max_steps: 5
  checkpoint:
    enabled: true      # 断点续跑
    dir: "./checkpoints"
```

### SSH 隧道

Milvus 和远程模型服务通过 SSH 隧道访问：

```bash
ssh -L 19531:localhost:19531 -L 8210:localhost:8210 admin@47.117.173.99 -N
```

### 初始化数据

```bash
python init_db.py                     # Excel → SQLite + VectorStore 'bids' (8,789 条)
python init_policy_collection.py      # 政策+舆情+PDF → VectorStore 'policy' (~9,800 chunks)
python init_sqlite_tables.py          # SQLite enterprise/price/product 建表 + 数据导入
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

## 数据体系

### Milvus 向量库 (panxin_bid_rag_v1)

| 集合 | 条数 | 来源 |
|------|------|------|
| `bids` | 8,789 | 招标项目 Excel |
| `regulations` | ~7,300 | 2 本 PDF 法规 (Parent-Child 结构化 + 自然段归并) |
| `policy` | 8,225 | 政策 Excel + 舆情 Excel + 10 个 PDF + 大合集法律法规全书 |

### SQLite 数据库 (data/bid_data.db)

| 表 | 条数 | 说明 |
|------|------|------|
| `bids` | 8,789 | 招标项目明细 |
| `enterprise` | 4,157 | 企业画像 (从 bids 聚合) |
| `price` | 588 | 物资报价 (28 品类) |
| `product` | 207 | 商品参数 (品牌/规格) |

### 6 大数据分类

| 数据集 | 条数 | 采集方式 |
|--------|------|----------|
| 政策信息 | 228 | shggzy.com + ccgp.gov.cn |
| 招标补充 | 200 | ccgp.gov.cn 最新中标公告 |
| 舆情信息 | 2,014 | ccgp.gov.cn 5 大公告栏目列表页 |
| 企业信息 | 4,157 | bid_data 深度聚合 (中标次数/金额/领域/城市) |
| 价格信息 | 588 | bid_data 深度提取 (28 品类+品牌识别) |
| 商品信息 | 207 | bid_data 正则提取 (品牌/规格/功率/电压) |

所有爬虫脚本位于 `data/scrapers/`。

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

## 路由模式

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

### Agent 模式

**ReAct Agent** — 一步一步思考，每步看到 Observation 再决定下一步：

```python
from app.agent.react_agent import ReActAgent

agent = ReActAgent(retriever, llm, max_steps=5, session_manager=sm)
answer = await agent.run("围标和串标的处罚有什么区别", session_id="abc123")

# 完整执行轨迹
agent.last_state.print_trace()
print(agent.last_state.tool_call_count)  # {"search_regulations": 2}
```

**PlannerExecutor** — 先规划再执行，DAG 调度自动并行，支持检索合并优化：

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
    - name: "search_market_price"
      class_path: "app.agent.tools.MarketPriceTool"
      enabled: false
    - name: "search_qualification"
      class_path: "app.agent.tools.QualificationTool"
      enabled: false
```

## 检索 Pipeline

```
search_unified(query)
  │
  ├─ Stage 1: preprocess  → 中文数字规范化 + 口语→书面语 + 同义词扩展
  │
  ├─ Stage 2: retrieve    → 对每个 collection (regulations, bids, policy) 分别执行:
  │    per-collection:       vector(Milvus HNSW, recall=50) + BM25(本地 jieba 分词, recall=50)
  │                          → fusion (RRF 或 Weighted) → 各库 top_k*3 候选项
  │                          → 三库候选项合并 (extend)
  │    ★ 分库召回 — 各库独立检索，结果层合并
  │
  ├─ Stage 3: merge       → 跨库合并 + 按 score 降序 + 按 id 去重
  │
  ├─ Stage 4: expand      → ParentContextExpander: child chunk 查找 parent，附加完整法条
  │                         按 article_id 去重（仅 regulations/policy 库启用）
  │
  └─ Stage 5: rerank      → BGE-Reranker CrossEncoder 精排
                            → 条款号精确匹配 boost (1.2x) → 返回 top_k
```

**Fusion strategies** (configurable via `retrieval.fusion_strategy`):
- `rrf`: Reciprocal Rank Fusion — pure rank-based, no normalization needed
- `weighted` / `smart`: WeightedFusion — Min-Max normalize scores → dynamic weights based on query type → keyword boost/penalty tables → filter score < 0.1

**Circuit breaker pattern**: Each stage has `enabled` + `circuit_breaker` config (`fail_close` for core stages; `fail_open` for fusion/expand/rerank — skip on error instead of crash).

## 评估

### V16 召回评测 (2026-07-05) — 绝对命中 vs 合并命中拆解

**评测集**: V9 Canonical, 2832 题 | **管线**: Dense + BM25 → Weighted Fusion → Parent Context → BGE-Reranker | **Collection**: policy_v9

**命中标准**:
- **绝对命中** = Top-K 中包含 `expected_chunk_id`（精确 chunk ID 匹配）
- **合并命中** = Top-K 中包含 `expected_chunk_id` 或 `acceptable_chunk_ids`

| 指标 | 绝对 R@1 | 绝对 R@3 | 绝对 R@5 | 合并 R@1 | 合并 R@3 | 合并 R@5 | Miss |
|------|----------|----------|----------|----------|----------|----------|------|
| 最终 (Reranker) | 62.6% | 82.7% | **89.5%** | 67.0% | 87.0% | **93.5%** | 184 |
| Dense only | 49.6% | 69.0% | 74.3% | 52.9% | 72.7% | 77.9% | — |
| BM25 (jieba) | 58.3% | 75.8% | 82.3% | 63.1% | 81.2% | 87.1% | — |
| Weighted fused | 58.2% | 76.9% | 83.6% | 63.3% | 82.0% | 88.0% | — |

- 564/2832 题 (19.9%) 有 acceptable_chunk_ids 备选，合并-绝对差异 @5 = 4.0% (112 题)
- pdf_case_sliding 绝对命中率最低，因滑动窗口 chunk 同质化需要备选 ID 兜底

**按 chunk_type R@5**: opinion_news 100.0% | policy_doc 96.6% | pdf_law_child 93.6% | pdf_law_parent 92.9% | pdf_case_sliding 90.6% | pdf_case_structured 89.0%

**按 question_type R@5**: announcement_interpretation 100.0% | responsibility 95.1% | procedure 93.5% | condition_check 93.1% | definition 92.5% | scenario_judgment 92.5% | case_reasoning 91.8%

### Header 领域注入

71 个高频跨法规混淆 (law, article_id) 对的 `retrieval_text` header 已添加领域/主题/关键词前缀，覆盖 10 个领域。参见 `fix_header_enrich.py`。

### Benchmark 版本演进

| 版本 | 题数 | R@5 | 关键改进 |
|------|------|-----|---------|
| V4 | 1000 | 90.0% | RRF + BGE-Reranker |
| V9 | 2832 | 89.0% | 新评测体系 + Parent-Child Chunk |
| V10 | 3146 | 89.5% | 相邻法条上下文 + Parent 黑名单 |
| V11 | 2832 | 92.0% | 评测集净化 + 三路动态权重 |
| V13 | 2832 | 92.0% | source_type_boost + textbook 1.03x |
| V14 | 2832 | 92.7% | Header 领域注入 27 对 (首轮) |
| **V15** | **2832** | **93.5%** | **Header 领域注入 71 对全量补齐** |
| **V16** | **2832** | **93.5% / 89.5%** | **合并/绝对命中拆解 (564 题含备选 ID)** |

### 评测文件

评测数据位于 `data/eval_questions/`，报告位于 `data/eval_questions/v*/`。

### 评测脚本

```bash
python eval_standalone.py    # 服务器端直连 Milvus + Embedding/Reranker
python deploy_eval.py        # 部署到服务器
```

## 配置总览

| 模块 | 可配置项 |
|------|---------|
| LLM | provider, api_url, api_key, model, temperature, max_tokens, timeout |
| Embedding | model_name (bge-m3/bge-small/m3e/gte-large), dimension, model_service_url (远程 API), device |
| 向量库 | backend (chroma/milvus), milvus uri/token/database/metric_type/dense_field/sparse_field, HNSW/BM25 参数 |
| Reranker | enabled, model (bge-reranker-base), max_input_length, candidate_pool, model_service_url (远程 API) |
| 检索 | top_k, vector_recall, bm25_recall, fusion_strategy (rrf/weighted/smart), 分数阈值, 条款号 boost |
| 路由 | mode (fast/think), template_match_threshold, 三路投票 |
| Agent | enabled, max_steps, temperature, tools 声明式注册, checkpoint (enabled/dir) |
| 会话 | backend (redis/sqlite), Redis host/port/db, SQLite db_path, ttl, max_history, 降级策略 |
| Memory | 对话历史 Buffer + Summary 双缓冲, SQLite 持久化, 实体追踪 |
| Query 改写 | 中文数字规范化, colloquial_to_formal, redundancy_removal, synonym_expansion, 法规名称保护 |
| 法律切块 | parent_context_enabled, child_split_threshold |
| Pipeline | 各阶段独立开关 + 断路器 (fail_open/fail_close) + 可观测性追踪 |

## 项目结构

```
.
├── main.py                     FastAPI 入口
├── config.py                   pydantic-settings 配置
├── config.yaml                 统一配置文件
├── requirements.txt            Python 依赖
├── start.bat                   一键启动脚本 (Redis + 服务)
├── tunnel.py                   SSH 隧道守护脚本
├── init_db.py                  招标数据导入 (Excel → SQLite + VectorStore)
├── init_policy_collection.py   政策+舆情+PDF 全量导入 (Excel+PDF → VectorStore)
├── init_sqlite_tables.py       SQLite enterprise/price/product 建表 + 聚合导入
├── rechunk_shiwu.py            实务 PDF 重新切分 (自然段归并)
├── ask_cli.py                  命令行交互客户端
├── run_recall_eval_full.py     召回评测（支持 V2/V3/V4）
├── gen_eval_benchmark_v4.py    V4 评测集生成（11 字段，断点续跑）
├── gen_eval_benchmark_v2.py    V2 评测集生成
├── app/
│   ├── api/                    FastAPI 路由 + Schema
│   ├── core/                   检索引擎 / 路由 / LLM / SQL / 查询改写 / Memory / 附录检测
│   │   ├── memory/             Memory 模块 (Buffer + Summary + Entity)
│   │   └── model_client.py     远程模型服务客户端 (embedding / rerank)
│   ├── agent/                  Agent 模式 (ReAct + Planner + State + Tools)
│   ├── pipeline/               可观测检索 Pipeline
│   ├── storage/                ChromaDB / Milvus 向量库 + Redis
│   ├── schema/                 元数据规范化
│   └── utils/                  工具函数
├── data/
│   ├── bid_data.xlsx           招标项目数据 (8,789条)
│   ├── bid_data.db             SQLite 数据库 (5 张表)
│   ├── pdfs/                   PDF 法规文件
│   ├── raw/                    Excel 原始数据 (policy / opinion / enterprise / price / product)
│   ├── scrapers/               Web 爬虫脚本 (6 大数据分类)
│   ├── colloquial_map.json     口语→书面语映射 (66条)
│   ├── eval_questions/         评估问答集 (V2/V3/V4)
│   └── QA_report/               召回评测报告 (V2/V3/V4)
├── frontend/                   前端界面
├── tools/                      诊断与验证工具
├── init_scripts/               辅助初始化脚本
├── checkpoints/                断点文件目录
├── chroma_db/                  向量数据库 (ChromaDB 模式)
└── memory_store/               Memory 持久化目录
```

## License

MIT
