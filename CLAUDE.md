# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

招投标智能问答系统 (Bidding & Tendering Intelligent Q&A System) — a RAG + SQL dual-engine Q&A service built on FastAPI. Answers both statistical questions (e.g., "how many bids last year?") via SQLite and regulatory/compliance questions via hybrid retrieval from PDF law books.

## Start & Develop

```bash
pip install -r requirements.txt

# Initialize data stores (order matters)
python init_db.py      # Load bid_data.xlsx into ChromaDB 'bids' collection
python init_pdf.py     # Chunk PDFs into ChromaDB 'regulations' collection

# Start the API server
python main.py         # Runs on 0.0.0.0:8000 by default, with hot-reload

# Interactive CLI client (requires server running)
python ask_cli.py

# Run retrieval accuracy evaluation
python eval_retrieval_accuracy.py
```

A local Redis instance is required for session management. The embedding model (`BAAI/bge-small-zh`) downloads on first use via `HF_ENDPOINT=https://hf-mirror.com`.

## Architecture (Three-Layer)

```
main.py                           # FastAPI app + lifespan (init components in order)
│
├── app/api/                      # ── API Layer ── HTTP interface
│   ├── routes.py                 # POST /api/v1/ask, GET /api/v1/health, DELETE /session/{id}
│   ├── schemas.py                # Pydantic models: AskRequest, AskResponse, SourceInfo
│   └── session_manager.py        # Redis-backed multi-turn session + query rewriting
│
├── app/agent/                    # ── Agent Layer ── Decision-making, planning, routing
│   ├── router.py                 # AutoRouter/BinaryRouter/IntentRouter/PlannerRouter (3-mode)
│   ├── router_graph.py           # LangGraph-based ThinkRouter (TaskAnalysis→ToolRouter→DAG)
│   ├── langgraph_agent.py        # LangGraph ReActAgent + PlannerAgent (StateGraph + RePlan)
│   ├── planner.py                # PlannerExecutor: DAG-scheduled multi-step execution
│   ├── react_agent.py            # ReActAgent: Thought→Action→Observation loop
│   ├── agent_tools.py            # Tools: rag_search / sql_search / tender / company
│   ├── agent_state.py            # AgentState: serializable execution trace + checkpoint
│   ├── tool_registry.py          # ToolRouter: 3-level routing (Rule→Embedding→LLM)
│   ├── task_cache.py             # TaskAnalysis cache (SQLite top-50 by frequency)
│   └── context_resolver.py       # Anaphora resolution (Rule First, LLM Fallback)
│
└── app/data/                     # ── Data Layer ── Storage, retrieval, processing
    ├── storage/                  # Vector store backends
    │   ├── chroma_store.py       # ChromaDB persistent client
    │   ├── milvus_store.py       # Milvus REST API v2 client (HNSW + BM25)
    │   └── redis_client.py       # Async Redis singleton
    ├── pipeline/                 # 5-stage retrieval pipeline
    │   ├── pipeline.py           # SearchPipeline orchestrator + StageRunner (circuit breakers)
    │   ├── preprocessor.py       # Stage 1: Query normalization + synonym expansion
    │   ├── retrievers.py         # Stage 2: VectorRetriever + BM25Retriever (dual backend)
    │   ├── fusion.py             # Stage 3: RRF + Weighted fusion (dynamic weights)
    │   ├── expanders.py          # Stage 4: ParentContextExpander (parent-child chunks)
    │   └── rerankers.py          # Stage 5: BgeReranker (CrossEncoder)
    ├── sql/                      # SQL engine (read-only, AST-validated)
    │   ├── gateway.py            # ReadOnlySQLGateway: generate → validate → execute → audit
    │   ├── validator.py          # SqlglotValidator: AST security (DELETE/DROP blocked)
    │   ├── catalog.py            # View schema catalog (bids, supplier_profile)
    │   └── schemas.py            # SQL validation/audit data classes
    ├── schema/                   # Data schemas
    │   ├── evidence.py           # Evidence + Citation unified output format
    │   └── metadata.py           # Chunk schema normalization
    ├── memory/                   # LangGraph Memory (Buffer + Summary, SQLite-backed)
    │   ├── manager.py            # MemoryManager: load_context / save_turn
    │   ├── buffer.py             # ConversationBufferWindowMemory + SummaryMemory
    │   ├── store.py              # MemoryStore: SQLite persistence
    │   └── base.py / entity.py   # Base classes
    ├── embedding.py              # EmbeddingService singleton
    ├── generator.py              # LLMGenerator: Tencent Hunyuan API for final answer
    ├── langchain_llm.py          # HunyuanChatModel LangChain adapter
    ├── retriever.py              # HybridRetriever — thin wrapper for SearchPipeline
    ├── sql_engine.py             # SQLEngine compat layer → ReadOnlySQLGateway
    ├── query_normalizer.py       # Colloquial→formal Chinese
    ├── query_rewriter.py         # 3-layer query rewriting
    ├── evidence_adapter.py       # RAG/SQL results → Evidence unified format
    ├── fusion_weighted.py        # HybridFusionV2 weighted fusion
    ├── *_chunk_builder.py        # Legal document parent-child chunking
    ├── legal_structure_parser.py # PDF law book structure parser
    └── config_loader.py          # YAML config loader
```

## Retrieval Pipeline (5-stage, per-collection)

```
search_unified(query)
  │
  ├─ Stage 1: preprocess  → 口语→书面语 + 同义词扩展 (bidirectional synonym expansion)
  │
  ├─ Stage 2: retrieve    → 对每个 collection (regulations, bids) 分别执行:
  │    per-collection:       vector(ChromaDB, recall=50) + BM25(jieba, recall=50)
  │                          → fusion (RRF 或 Weighted) → 各库 top_k*3 候选项
  │                          → 两库候选项合并 (extend)
  │    ★ 这就是"分库召回" — 各库独立检索，结果层合并
  │
  ├─ Stage 3: merge       → 跨库合并 + 按 score 降序 + 按 id 去重
  │
  ├─ Stage 4: expand      → ParentContextExpander: child chunk 查找 parent，附加完整法条
  │                         按 article_id 去重（仅 regulations 库启用）
  │
  └─ Stage 5: rerank      → BGE-reranker-base CrossEncoder 精排 → 返回 top_k
```

**Fusion strategies** (configurable via `retrieval.fusion_strategy`):
- `rrf`: Reciprocal Rank Fusion — pure rank-based, no normalization needed
- `weighted` / `smart`: WeightedFusion — Min-Max normalize scores → dynamic weights based on query type (keyword_heavy: BM25=0.75/dense=0.25, semantic_heavy: BM25=0.40/dense=0.60) → keyword boost/penalty tables → filter score < 0.1

**Circuit breaker pattern**: Each stage has `enabled` + `circuit_breaker` config (`fail_close` for core stages preprocess/retrieve; `fail_open` for fusion/expand/rerank — skip on error instead of crash).

**Single-collection search** (`search()`): Same pipeline but only one collection, skips merge stage. Used by Agent tools directly.

## Request Flow

1. **Session**: get-or-create Redis session, fetch history, rewrite anaphora ("那个项目" → actual name)
2. **Routing**: configured via `router.mode` in config.yaml, 4 options:
   - `auto` **(推荐)**: AutoRouter — IntentRouter 先判意图+复杂度 → greeting/thanks 秒回, stat_query 走 SQL, single_step 直接 RAG, multi_step 走 Planner DAG。零手动开关，自适应分流
   - `binary`: BinaryRouter — 3-way parallel voting (rule-based keywords + embedding similarity against template banks + LLM), 2/3 majority decides `is_sql`. SQL template match ≥ 92% → reuse pre-baked SQL ("SQL shortcut")
   - `intent`: IntentRouter — LLM classifies into 6 types (definition/procedure/penalty/provision/stat_query/other) + complexity (single_step/multi_step). Quick-intercept for greetings/thanks/off-topic
   - `planner`: PlannerRouter — 2-call LLM pipeline: TaskAnalysis (decompose into tasks with depends_on DAG) → ToolPlanning (map tasks to tools). Falls back to search_regulations on failure
3. **Execution**:
   - **Auto mode**: `AutoRouter` returns `mode` field → `direct` (greeting秒回, 0次LLM), `auto`+`is_sql` (走 _handle_binary), `planner` (走 _handle_planner)
   - **Binary/Intent modes**: If `is_sql`, SQLEngine generates SQL → SQLite → if empty/error, falls back to unified hybrid retrieval. If not `is_sql`, RAG path via `search_unified()`
   - **Planner mode**: `PlannerExecutor` runs DAG-scheduled execution — respects `depends_on` to parallelize independent tasks, serial for dependencies. Auto-replan on step failures (up to 1 replan). Aggregates per-task results into final answer
   - **Agent mode** (`agent.enabled=true`): ReActAgent — Thought→Action→Observation loop (max 5 steps), state checkpointed per step
4. **Generation**: LLMGenerator builds prompt from top-3 context + last 3 conversation turns, calls Hunyuan API
5. **Response**: extracts entities (project name, winner) for next-turn context, saves to Redis

## Configuration

All settings driven by `config.yaml` + `.env`, accessed via `config.py` `Settings` class (pydantic-settings). Key config paths:

| YAML path | Default | Purpose |
|-----------|---------|---------|
| `llm.provider` | hunyuan | LLM provider selection |
| `llm.providers.<name>.api_key` | (env LLM_API_KEY) | API key per provider |
| `embedding.model_name` | bge-small | Which embedding model preset |
| `embedding.models.<name>.name` | BAAI/bge-small-zh | Actual model name |
| `embedding.models.<name>.dimension` | 512 | Embedding dimension |
| `retrieval.top_k` | 5 | Final results returned |
| `retrieval.vector_recall` | 50 | Candidate pool from vector search |
| `retrieval.bm25_recall` | 50 | Candidate pool from BM25 |
| `retrieval.fusion_strategy` | rrf | rrf / weighted / smart |
| `retrieval.weighted.bm25_weight` | 0.65 | BM25 weight in weighted fusion |
| `retrieval.weighted.dense_weight` | 0.35 | Dense weight in weighted fusion |
| `reranker.enabled` | true | Enable BGE reranker |
| `reranker.model_name` | BAAI/bge-reranker-base | Reranker CrossEncoder model |
| `reranker.candidate_pool` | 30 | Max candidates fed to reranker |
| `router.mode` | auto | auto / binary / intent / planner |
| `router.binary.template_match_threshold` | 0.92 | Cosine threshold for SQL template reuse |
| `agent.enabled` | false | Enable ReAct Agent mode |
| `agent.max_steps` | 5 | Max ReAct loop iterations |
| `agent.checkpoint.enabled` | true | Persist agent state per step |
| `legal_chunking.parent_context_enabled` | true | Parent-child chunk expansion |
| `query_rewriter.*` | various | 3-layer query rewriting toggles |
| `pipeline.tracing.enabled` | true | Print per-stage I/O counts and timing |
| `pipeline.stages.<name>.enabled` | true | Per-stage enable/disable |
| `pipeline.stages.<name>.circuit_breaker` | fail_open | fail_close / fail_open |
| `data.chroma_persist_dir` | ./chroma_db | ChromaDB storage |
| `data.db_path` | ./data/bid_data.db | SQLite database |
| `data.collections` | bids, regulations | ChromaDB collection definitions |
| `session.redis.host` | localhost | Redis host |
| `server.host` / `server.port` | 0.0.0.0 / 8000 | API server bind |

## Data

- `data/bid_data.xlsx` — ~8000+ bidding project records (columns: 项目名称, 中标人, 中标金额, 省份, 市区, 发布时间, 类别)
- `data/pdfs/` — 2 legal reference PDFs chunked into `regulations` collection
- `data/colloquial_map.json` — 66 colloquial→formal Chinese term mappings for query normalization
- `data/eval_questions/` — JSON eval sets for retrieval accuracy benchmarking
- `config.yaml` — main configuration file (LLM providers, retrieval params, pipeline stages, etc.)
