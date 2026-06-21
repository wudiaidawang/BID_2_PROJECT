# 项目启动与服务器连接手册

## 一、手动启动本项目（问答）

### 1. 环境准备

```bash
cd E:\BID_3_PROJECT_langchain
pip install -r requirements.txt
```

### 2. 配置

编辑 `.env` 填入 API Key，编辑 `config.yaml` 切换后端/模型。

关键配置项（`config.yaml`）：

| 配置路径 | 当前值 | 说明 |
|----------|--------|------|
| `llm.provider` | `hunyuan` | LLM 厂商 |
| `vector_store.backend` | `milvus` | 向量库：chroma / milvus |
| `vector_store.milvus.uri` | `http://localhost:19531` | Milvus 地址 |
| `embedding.model_name` | `bge-m3` | Embedding 模型 |
| `embedding.model_service_url` | `http://localhost:8210` | 远程模型服务 |
| `session.backend` | `redis` | 会话存储：redis / sqlite |

### 3. 初始化数据（仅首次或数据变更后）

```bash
python init_db.py                      # Excel → SQLite + 向量库 'bids' 集合 (8,789条)
python init_policy_collection.py       # 全部PDF → 向量库 'policy' 集合
```

数据流向：本地读取 Excel/PDF → 服务器 BGE-M3 Embedding → 服务器 Milvus 存储。

### 4. 启动

```bash
python main.py
# 服务: http://0.0.0.0:8000
# Swagger 文档: http://0.0.0.0:8000/docs
```

### 5. 命令行测试

```bash
python ask_cli.py
```

---

## 二、服务器连接 — 需要挂载的服务/接口

### 概览

```
本地机器                          服务器 (47.117.173.99)
┌─────────────┐     SSH 隧道       ┌──────────────────────┐
│ main.py     │ ──► :8210 ────────►│ 模型服务 :8210        │
│ (FastAPI)   │                    │  ├── /embed (POST)    │
│             │                    │  └── /rerank (POST)   │
│ :8000       │ ──► :19531 ───────►│ Milvus :19530/:19531  │
│             │                    │  (向量数据库)          │
│             │ ──► LLM API ──────►│ 混元 API (外部)       │
│             │                    │ tokenhub.tencentmaas  │
│             │ ──► Redis :6379 ──►│ Redis (会话管理)       │
└─────────────┘                    └──────────────────────┘
```

### 2.1 SSH 隧道（连接到服务器）

```bash
ssh -L 19531:127.0.0.1:19531 -L 8001:127.0.0.1:8001 -L 8002:127.0.0.1:8002 admin@47.117.173.99 -N
```

该命令将服务器的 Milvus (19531) 和模型服务 (8210) 端口映射到本地。

---

### 2.2 远程模型服务 — 端口 8210

提供 Embedding 和 Reranker 两个 HTTP API。

| 接口 | 方法 | 路径 | 请求体 | 响应 |
|------|------|------|--------|------|
| Embedding | POST | `/embed` | `{"texts": ["文本1", "文本2"]}` | `{"embeddings": [[0.1, 0.2, ...], ...]}` |
| Rerank | POST | `/rerank` | `{"query": "...", "documents": [...], "top_k": 5}` | `{"results": [{"index": 0, "document": "...", "score": 0.92}, ...]}` |

**调用方：** `app/core/model_client.py` 中的 `remote_embed()` 和 `remote_rerank()`

> **【待补充】请本地模型补充以下信息：**
> - 服务端是什么项目/框架部署的（FastAPI? vllm? Ollama?）？
> - 启动命令是什么？
> - 加载了哪些模型文件（BGE-M3? BGE-Reranker-base? 路径？）？
> - 运行在什么设备上（GPU型号/显存）？

---

### 2.3 Milvus 向量数据库 — 端口 19531

REST v2 API，Dense (HNSW) + Sparse (BM25) 双向量检索。

当前数据库：`panxin_bid_rag_v1`
当前集合：`bids` (招标项目) + `regulations` (法律法规)

| Dense 字段 | `dense_vector` | 1024 维 (BGE-M3) |
| Sparse 字段 | `sparse_vector` | BM25 向量 |
| 主键 | `id` | VarChar |
| 索引类型 | HNSW | M=16, ef_construction=200 |

**调用方：** `app/storage/milvus_store.py` 中的 `MilvusStore`

> **【待补充】请本地模型补充以下信息：**
> - Milvus 是怎么部署的（Docker Compose? 裸机？）？Docker 命令/镜像版本？
> - Collection Schema 定义（字段列表、类型、索引配置）
> - 是否需要在本地预先创建 collection，还是代码自动创建？

---

### 2.4 LLM 外部 API

| 项目 | 值 |
|------|-----|
| 当前厂商 | 混元 (Hunyuan) |
| API 地址 | `https://tokenhub.tencentmaas.com/v1/chat/completions` |
| 模型 | `hy3-preview` |
| 认证方式 | `.env` 中 `LLM_API_KEY` |
| 兼容协议 | OpenAI Chat Completions 兼容 |

**可切换厂商（改 `config.yaml` 一行）：**
- DeepSeek: `https://api.deepseek.com/v1/chat/completions`
- OpenAI: `https://api.openai.com/v1/chat/completions`
- Custom: 任意 OpenAI 兼容接口（如 Ollama `http://localhost:11434/v1/chat/completions`）

---

### 2.5 Redis 会话管理 — 端口 6379

| 项目 | 值 |
|------|-----|
| 地址 | `localhost:6379` |
| DB | 0 |
| 会话 TTL | 1800 秒 (30分钟) |

**可切换为 SQLite（改 `config.yaml`）：** `session.backend: sqlite`

> **【待补充】请本地模型补充以下信息：**
> - Redis 是服务器上的还是本地的？是否需要也在 SSH 隧道里转发？

---

## 三、待补充问题清单

以下是我不确定的部分，请交给本地模型补充：

1. **模型服务（端口 8210）的完整部署方式**
   - 用什么框架跑的？源码在哪个目录？
   - 启动命令？
   - 加载的模型文件列表和路径？
   - GPU/显存配置？

2. **Milvus（端口 19531）的完整部署方式**
   - Docker 还是裸机安装？版本？
   - Collection Schema 完整定义（所有字段、类型、索引）？
   - Collection 需要预先手动创建还是代码第一次运行时自动创建？
   - 有 Web 管理界面吗（如 Attu）？地址？

3. **Redis 部署位置**
   - 服务器上的 Redis 还是本地 Docker？
   - 如果在服务器上，是否需要额外的 SSH 端口转发？

4. **环境变量补充**
   - `.env.example` 中缺少 `milvus` 和 `model_service_url` 相关的环境变量说明

---

## 四、完整启动检查清单

- [ ] SSH 隧道已建立（端口 19531 + 8210）
- [ ] Redis 可连接（`redis-cli ping`）
- [ ] Milvus 可连接（`curl http://localhost:19531/api/v1/health`）
- [ ] 模型服务可连接（`curl http://localhost:8210/embed` 测试）
- [ ] LLM API Key 已配置（`.env` 中 `LLM_API_KEY`）
- [ ] `config.yaml` 已检查关键配置项
- [ ] 向量库数据已初始化（`init_db.py` + `init_policy_collection.py`）
- [ ] `main.py` 启动成功
- [ ] `http://localhost:8000/docs` 可访问
- [ ] `ask_cli.py` 测试问答正常
