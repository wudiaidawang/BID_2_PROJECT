# 更新日志 — 2026-06-25

## 1. BM25 本地化改造

**原因**: Milvus 内置 BM25 使用字符级 n-gram 中文分析器，对自然语言问句（如"道路客运班线经营许可期限多久"）返回 0 条结果。`tools/test_bm25_sparse_analysis.py` 量化诊断确认：仅短关键词（2-4 字）和含《》法规名能命中，自然语言问句全部失效。

**修改**: `app/pipeline/pipeline.py`
- `ServerBM25Retriever`（Milvus REST API sparse_vector）→ `BM25Retriever`（本地 jieba 分词）
- BM25 召回前通过 `_get_all_docs(collection)` 拉取全库文档构建本地索引（带缓存）
- 与 vector 召回结果经 RRF/Weighted 融合后进入 reranker，流程不变

**诊断脚本**: `tools/test_bm25_sparse_analysis.py` — 10 种 query 类型逐测 Milvus BM25 命中数，量化内置分析器失效范围，保留作为改造证据。

## 2. V4 Benchmark ID 修复

验证全部 1000 条 `expected_chunk_id` 在 Milvus 中实际存在，修复 3 条不匹配：

| QA ID | 问题 | 修复 |
|-------|------|------|
| qa_v4_0462 | child1 → child0 编号偏移（重新 embedding 后 chunk 顺序变化） | 改为 `_child0` |
| qa_v4_0527 | 对应 chunk 为附录模板页（空白占位符），已从 Milvus 清除 | 删除该 QA |
| qa_v4_0536 | law_name 缺少 `等有` 后缀，与 Milvus 实际 ID 不一致 | 补充为 `条例》等有_31` |

**验证结果**: 1000/1000 完全匹配，零缺失。

## 3. 空白门控附录检测器

**新增文件**: `app/core/appendix_detector.py`

**机制**: 先检测空白占位符（`______`、`___`、`年 月 日`、`地址：_`）作为门控条件 → 通过后计算附录得分 = 格式分 × min(长度/400, 4) × (含附录关键词则 1.3) → 阈值 ≥ 1.0 判定为附录。

**集成**: `init_policy_collection.py` 在 parser 和 parent_builder 之间调用 `remove_appendix_articles()`，3952 个 parent chunks 中检出 3 个含空白占位符、2 个高置信度附录、0 误判。清除 15 个模板 chunks（2 parents + 13 children）。

## 4. 文件变更

| 文件 | 变更 |
|------|------|
| `app/pipeline/pipeline.py` | BM25 从 Milvus Sparse 切换为本地 jieba |
| `app/core/appendix_detector.py` | 新增空白门控附录检测器 |
| `init_policy_collection.py` | 集成附录检测到切块流程 |
| `data/eval_questions/eval_benchmark_v4.json` | 3 条 ID 修复，总计 1000 条 |
| `tools/test_bm25_sparse_analysis.py` | 新增 BM25 失效诊断脚本 |
