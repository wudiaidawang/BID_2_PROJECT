# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

招投标智能问答系统 (Bidding & Tendering Intelligent Q&A System) — a RAG + SQL dual-engine Q&A service built on FastAPI. Answers both statistical questions (e.g., "how many bids last year?") via SQLite and regulatory/compliance questions via hybrid retrieval from PDF law books.

## Start & Develop

```bash
# Install dependencies
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

## Architecture

```
main.py                    # FastAPI app + lifespan (init 6 components in order)
├── app/api/routes.py      # POST /api/v1/ask — the main Q&A endpoint
│                          # GET /api/v1/health, DELETE /session/{id}
├── app/api/schemas.py     # Pydantic models: AskRequest, AskResponse, SourceInfo
├── app/core/
│   ├── router.py          # BinaryRouter: 3-way voting (rule + embedding + LLM)
│   │                      #   classifies query as is_sql or not
│   ├── retriever.py       # HybridRetriever: vector(Chroma) + BM25(jieba) + RRF fusion
│   │                      #   + optional BGE-reranker; search_unified()跨库查询
│   ├── sql_engine.py      # SQLEngine: LLM-generates SQL from NL, executes on SQLite
│   ├── generator.py       # LLMGenerator: calls Tencent Hunyuan API for final answer
│   ├── embedding.py       # EmbeddingService: singleton wrapping BAAI/bge-small-zh
│   ├── session_manager.py # Redis-backed multi-turn session + query rewriting
│   └── query_normalizer.py# Colloquial→formal Chinese via data/colloquial_map.json
└── app/storage/
    ├── chroma_store.py    # ChromaDB persistent client (2 collections: bids, regulations)
    └── redis_client.py    # Async Redis singleton
```

## Request Flow

1. **Session**: get-or-create Redis session, fetch history, rewrite anaphora ("那个项目" → actual name)
2. **Routing**: `BinaryRouter.route()` runs 3 classifiers in parallel (rule-based keywords, embedding similarity against template banks, LLM) — majority vote decides `is_sql`
3. **Retrieval**:
   - **SQL path**: if template match ≥ 92%, reuse pre-baked SQL ("SQL shortcut"); otherwise LLM generates SQL → SQLite → if empty/error, falls back to unified hybrid retrieval
   - **RAG path**: `search_unified()` queries both `regulations` and `bids` collections, merges with RRF, re-ranks, deduplicates
4. **Generation**: `LLMGenerator` builds prompt from top-3 context + last 3 conversation turns, calls Hunyuan API
5. **Response**: extracts entities (project name, winner) for next-turn context, saves to Redis

## Configuration

All settings in `config.py` via `pydantic-settings`, with `.env` file support. Key settings:

| Setting | Default | Purpose |
|---------|---------|---------|
| `llm_api_key` | hardcoded | Tencent Hunyuan API key |
| `llm_api_url` | hunyuan.cloud.tencent.com | LLM endpoint |
| `embedding_model` | BAAI/bge-small-zh | Local embedding model |
| `top_k` | 5 | Final results returned |
| `vector_recall` | 50 | Candidate pool size from vector search |
| `chroma_persist_dir` | ./chroma_db | ChromaDB storage |
| `db_path` | ./data/bid_data.db | SQLite database path |

## Data

- `data/bid_data.xlsx` — ~8000+ bidding project records (columns: 项目名称, 中标人, 中标金额, 省份, 市区, 发布时间, 类别)
- `data/pdfs/` — 2 legal reference PDFs chunked into `regulations` collection
- `data/colloquial_map.json` — 66 colloquial→formal Chinese term mappings for query normalization
- `data/eval_questions/` — JSON eval sets for retrieval accuracy benchmarking
