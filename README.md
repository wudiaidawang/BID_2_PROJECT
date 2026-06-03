# 基于Agent + Hybrid RAG双引擎的招投标智能问答系统

Bidding & Tendering Intelligent Q&A System — 基于 RAG + SQL 双引擎的招投标法规与数据智能问答平台。

## 功能

- **法规检索问答**：基于《招标投标法》《政府采购法》等 PDF 法规库，支持概念定义、处罚规定、操作流程等自然语言提问
- **数据统计查询**：基于 SQLite 数据库，支持"去年有多少项目""中标金额最高的是哪个"等统计类 NL2SQL 查询
- **混合检索**：向量检索 (ChromaDB) + 关键词检索 (BM25/jieba) + RRF 融合 + BGE-Reranker 精排
- **Query 改写**：口语转书面语、指代消解、同义词扩展
- **Parent-Child Chunking**：法律条文结构化切块，检索 child chunk → 补全 parent context
- **多轮对话**：Redis 会话管理，支持上下文理解和追问
- **Agent 模式**：ReAct 循环 (Thought → Action → Observation)，支持多工具调用

## 架构

```
main.py                     FastAPI 入口
├── app/api/routes.py       POST /api/v1/ask  问答接口
│                           GET  /api/v1/health  健康检查
├── app/core/
│   ├── router.py           路由层 (Binary/Intent/Planner 三种模式)
│   ├── retriever.py        混合检索器 (ChromaDB + BM25 + RRF + Reranker)
│   ├── sql_engine.py       NL2SQL 引擎 (LLM 生成 SQL → SQLite 执行)
│   ├── generator.py        LLM 生成器 (支持多厂商 API)
│   ├── embedding.py        Embedding 服务 (BGE/M3E 系列)
│   ├── session_manager.py  Redis 多轮会话管理
│   └── query_rewriter.py   Query 改写 (口语化→书面语)
├── app/agent/
│   ├── react_agent.py      ReAct Agent (Thought → Action → Observation)
│   └── agent_tools.py      工具集 (法规检索/法条查询/SQL统计/摘要)
├── app/pipeline/           可观测检索 Pipeline (preprocess → retrieve → rerank)
├── app/storage/
│   ├── chroma_store.py     ChromaDB 持久化客户端
│   └── redis_client.py     Redis 连接管理
└── app/utils/              中文数字转换等工具
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

```bash
# 复制配置模板
cp config.yaml.example config.yaml

# 编辑 .env 填入 API Key
cp .env.example .env
# 编辑 .env → 填入 LLM_API_KEY
```

配置优先级：**环境变量 (.env) > config.yaml > 代码默认值**

多厂商支持：修改 `config.yaml` 中 `llm.provider` 即可在混元 / DeepSeek / OpenAI / 本地模型间切换。

### 初始化数据

```bash
# 1. 导入招标数据 Excel → SQLite + ChromaDB
python init_db.py

# 2. 切块 PDF 法规 → ChromaDB
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

## 评估结果

基于 100 条手工标注的 RAG 问答对评测：

| 指标 | 分数 |
|------|------|
| 路由分类准确率 | **99.0%** |
| 检索 Top-5 Recall (Embedding) | **92.0%** |
| 检索 Top-3 Recall (Embedding) | **89.0%** |
| 检索 Top-1 Recall (Embedding) | **83.0%** |

评判标准：expected_answer 与检索结果文本的余弦相似度 ≥ 0.70。

运行评估：

```bash
python eval_retrieval_accuracy.py
```

## 配置说明

全部配置在 `config.yaml` 中集中管理，无需改动代码：

| 模块 | 可配置项 |
|------|---------|
| LLM | provider, model, temperature, max_tokens, timeout |
| Embedding | model_name (bge-small/bge-large/m3e/gte-large), device |
| Reranker | enabled, model, max_input_length, candidate_pool |
| 检索 | top_k, vector_recall, bm25_recall, fusion_strategy (rrf/weighted/smart) |
| 路由 | mode (binary/intent/planner), template_match_threshold |
| Agent | enabled, max_steps, tools (声明式注册) |
| 会话 | backend (redis/sqlite), ttl, max_history |
| Pipeline | 各阶段独立开关 + 断路器 (fail_open/fail_close) |

## 项目结构

```
.
├── main.py                  FastAPI 入口
├── config.py                pydantic-settings 配置定义
├── config.yaml.example      配置文件模板
├── requirements.txt         Python 依赖
├── init_db.py               数据库初始化
├── init_pdf.py              PDF 法规导入
├── ask_cli.py               命令行客户端
├── eval_retrieval_accuracy.py  检索评估
├── app/                     核心应用代码
├── data/
│   ├── bid_data.xlsx        招标项目数据
│   ├── pdfs/                PDF 法规文件
│   ├── colloquial_map.json  口语→书面语映射
│   └── eval_questions/      评估问答集
├── docs/                    开发文档
├── scripts/                 辅助脚本
└── chroma_db/               向量数据库 (本地生成)
```

## License

MIT
