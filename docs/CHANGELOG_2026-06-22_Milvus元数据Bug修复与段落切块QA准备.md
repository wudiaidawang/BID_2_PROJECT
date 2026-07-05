# 更新日志 14 — Milvus 元数据 Bug 修复与段落切块 QA 准备

**日期**: 2026-06-22  
**版本**: v5.3.1

---

## 一、Bug 发现与修复

### Bug 1: `get_count()` 始终返回 0 或 1

| 项目 | 内容 |
|------|------|
| **文件** | `app/storage/milvus_store.py:149-162` |
| **严重程度** | 高 |
| **根因** | 原代码 `q_payload["limit"] = 1`，然后 `return len(result)`。Milvus query 最多返回 1 条记录，`len()` 永远是 0 或 1 |
| **影响** | `rebuild_from_excel` 安全检查看到 1 条数据仍触发跳过（恰好 > 0）；但所有 init 脚本打印的总数全是 0 或 1，无法确认入库是否成功；`pipeline.py` 的 collection 统计展示错误 |
| **修复** | 改用轻量分页：`outputFields=["id"]` + `limit=10000`，逐页累加。只用 `id` 字段避免响应体积过大触发 Milvus `query results exceed the limit size` 错误 |

### Bug 2: `_entity_to_doc()` 将所有字段嵌套在 metadata 子字典

| 项目 | 内容 |
|------|------|
| **文件** | `app/storage/milvus_store.py:344-368` |
| **严重程度** | 高 |
| **根因** | `_entity_to_doc` 只把 `id`/`retrieval_text`/`text` 提升到顶层，其余字段（`chunk_type`、`law_name`、`article_id`、`parent_id` 等 16 个关键字段）全部塞进 `metadata` 子字典。而 `_build_row` 写入时这些字段同时以顶层列和 JSON blob 两种形态存在 |
| **影响** | 所有通过 `_entity_to_doc` 返回的文档，`doc["chunk_type"]` 返回空，必须用 `doc["metadata"]["chunk_type"]`。`gen_eval_benchmark_v2.py` 的 `c.get("chunk_type")` 全部返回 `"other"`，抽样完全失败。`policy_chunks_export.json` 导出的 chunks 字段在错误层级 |
| **修复** | 关键字段同时保留在**顶层**和 **metadata 子字典**，向前兼容 `doc["chunk_type"]` 也兼容 `doc["metadata"]["chunk_type"]` |

### Bug 3: `query()` 大分页触发 Milvus 响应体积限制

| 项目 | 内容 |
|------|------|
| **文件** | `app/storage/milvus_store.py:131-147` |
| **严重程度** | 中 |
| **根因** | `get_all_documents` 用 `limit=1000` + 所有 `outputFields`（含 `retrieval_text`/`text` 长文本字段）。offset 到 3000+ 时响应体积超过 Milvus 服务端限制 `query results exceed the limit size` |
| **影响** | 全量导出只能拿到前 3000-3200 条，无法获取完整 collection |
| **修复** | 两步策略：(1) 先 `outputFields=["id"]` + `limit=10000` 轻量取所有 ID；(2) 按 ID 批量（50/批）`get_by_ids` 取完整文档 |

### Bug 4: `infer_source_type()` 不再能识别扁平字段

| 项目 | 内容 |
|------|------|
| **文件** | `app/schema/metadata.py:149`、`app/pipeline/pipeline.py:270` |
| **严重程度** | 中 |
| **根因** | 函数签名只接收 `metadata: dict` 子字典。修复 Bug 2 后关键字段在顶层，`metadata` 子字典可能缺少它们，导致 `source_type` 推断错误 |
| **影响** | `source_type_boost` 阶段权重提升失效（如 `regulation_article` +1.15 提升无法应用） |
| **修复** | 改为接收完整 `chunk: dict`，内部 `_get()` 优先顶层字段，fallback 到 metadata 子字典 |

---

## 二、关联修复

| 文件 | 修改 |
|------|------|
| `app/schema/metadata.py` | `normalize_chunk()` — 将顶层已知字段同步到 metadata（保持三方调用兼容）；`CHUNK_TYPES` 新增 `pdf_case_paragraph` |
| `app/pipeline/pipeline.py` | `infer_source_type` 调用改为传入完整 chunk |
| `gen_eval_benchmark_v2.py` | `pdf_case_sliding` → `pdf_case_paragraph`（含 DISTRIBUTION、抽样逻辑、生成循环） |
| `policy_chunks_export.json` | 重新导出 7832 chunks（扁平结构，关键字段在顶层） |
| `config.yaml` | `data.collections` 新增 `bids`（使 pipeline 语义搜索能检索招标数据） |
| `init_db.py:53` | `panxin_bid_rag_v1` → `bids`（修复旧库名残留） |
| `app/pipeline/pipeline.py:198` | `"regulations"` → `"policy"`（parent expander 指向正确的 collection） |
| `app/pipeline/pipeline.py:336` | `get_stats()` 改为动态遍历 `settings.collections` |

---

### 三-A、bids 向量库重建

**触发原因**: 之前的 `panxin_bid_rag_v1` Milvus 数据库被删除，bids collection 丢失。

**执行**: `python init_db.py` — 读取 8789 条 `bid_data.xlsx` → 远端 BGE-M3 embedding → Milvus `bids` collection

**结果**: 8789 条招标项目已入库，`chunk_type: bid_project`，`retrieval_text` 包含项目名+中标人+金额+省份+日期+类别的拼接文本。

### 三-B、SSH 隧道僵死进程问题

**症状**: 远端 embedding 服务返回 502，但隧道端口 LISTENING。

**根因**: 旧 `tunnel.py` 进程 (PID 20028) 僵死但未释放端口，新连接被旧进程拦截。`taskkill` 后恢复正常。

---

## 三、当前数据状态

### Milvus `panxin_dev`

| Collection | 条数 | 状态 |
|------------|------|------|
| **bids** | 8789 | ✅ 刚重建 |
| **policy** | 7832 | ✅ 正常 |

### policy 内部分布

| chunk_type | 数量 | 说明 |
|------------|------|------|
| pdf_law_parent | 4369 | PDF 法律条文父块 |
| opinion_news | 2014 | 舆情新闻 |
| pdf_case_paragraph | 770 | 实务段落归并（新） |
| pdf_law_child | 373 | PDF 法律条文子块 |
| policy_doc | 228 | 政策文件 |
| pdf_case_sliding | 78 | 旧滑动窗口（5 份判决书） |

### SQLite `bid_data.db`

| 表 | 条数 | 状态 |
|----|------|------|
| bids | 8789 | ✅ |
| enterprise | 4157 | ✅ |
| price | 588 | ✅ |
| product | 207 | ✅ |

### ChromaDB 本地

| 路径 | 状态 |
|------|------|
| `./chroma_db/` | 空（不存在） |

---

## 四、待办

1. ~~重建 bids 向量库~~ ✅ 已完成（8789 条）
2. **运行 QA 生成** — `python gen_eval_benchmark_v2.py`，为 770 个 `pdf_case_paragraph` 生成 200 个 QA 对
3. **运行评估** — `python run_recall_eval_full.py`，用新 QA 集评测检索召回率
4. ~~修复 `infer_source_type` pipeline 调用~~ ✅ 已完成

---

## 五、版本标记

```
v5.3.1 — 2026-06-22
  - fix: get_count 返回真实总数（修复 limit=1 bug）
  - fix: _entity_to_doc 关键字段提升到顶层，向前兼容
  - fix: get_all_documents 两阶段导出避免响应超限
  - fix: infer_source_type 兼容扁平结构
  - add: pdf_case_paragraph chunk type 枚举 + QA 生成器适配
  - chore: policy_chunks_export.json 重新导出（7832 条）
```
