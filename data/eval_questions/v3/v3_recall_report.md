# V3 召回率测试报告

## 测试概况

| 项目 | 值 |
|------|-----|
| 测试时间 | 2026-06-23 00:23 |
| Benchmark | eval_benchmark_v3 |
| 题目总数 | 772 |
| Top-K | 5 |
| Pipeline | BM25 + Vector + RRF + Reranker + source_type_boost |
| Fusion | RRF (k=60) |
| 权重 (sparse/dense) | 0.65 / 0.35 (加权融合未启用) |

## 总体结果

| 指标 | 数值 |
|------|------|
| **parent_hit@1** | 304/772 = **39.4%** |
| **parent_hit@5** | 503/772 = **65.2%** |
| Recall@5 (parent) | 0.6392 |
| MRR (parent) | 0.4790 |
| exact_hit@1 | 119/772 = 15.4% |
| exact_hit@5 | 227/772 = 29.4% |
| cosine_hit@5 | 6/772 = 0.8% |
| **True Miss** | **263/772 = 34.1%** |

## 按 chunk 类型

| 类型 | 数量 | parent_hit@5 | recall@5 | MRR | Miss |
|------|------|-------------|----------|-----|------|
| opinion_news | 80 | 93.8% | 0.9375 | 0.8550 | 2 |
| pdf_case_paragraph | 144 | 91.7% | 0.9167 | 0.3978 | 11 |
| policy_doc | 18 | 83.3% | 0.8333 | 0.5361 | 3 |
| pdf_law_parent | 466 | 55.4% | 0.5333 | 0.4694 | 206 |
| pdf_law_child | 64 | 35.9% | 0.3594 | 0.2458 | 41 |

## 按 source_type

| 类型 | 数量 | parent_hit@5 | recall@5 | MRR | Miss |
|------|------|-------------|----------|-----|------|
| regulation_opinion | 80 | 93.8% | 0.9375 | 0.8550 | 2 |
| regulation_case | 144 | 91.7% | 0.9167 | 0.3978 | 11 |
| regulation_policy | 18 | 83.3% | 0.8333 | 0.5361 | 3 |
| regulation_article | 530 | 53.0% | 0.5123 | 0.4424 | 247 |

## 按跨段 vs 单段

| 跨度 | 数量 | parent_hit@5 | recall@5 | Miss |
|------|------|-------------|----------|------|
| single (单段) | 687 | 66.5% | 0.6652 | 224 |
| cross (跨段) | 85 | 54.1% | 0.4294 | 39 |

## 数据质量

| 指标 | 数值 |
|------|------|
| 唯一 source_chunks | 833 |
| DB 中存在 | 808 (97.0%) |
| DB 中缺失 | 25 (3.0%) — 全部为截断 law_name 导致 |

---

## V3 → V4 期间变更记录

### 本次 session (2026-06-23 上午)

| 变更 | 文件 | 影响 |
|------|------|------|
| 稀疏/稠密权重调整 | `config.yaml` | bm25_weight: 0.65→0.45, dense_weight: 0.35→0.55 |
| benchmark chunk ID 修复 | `eval_benchmark_v3.json` | 25个截断 law_name 修复为完整名，source_chunks DB 匹配率 97%→100% |
| law_name 正则放宽 | `legal_structure_parser.py` | 标题匹配上限 16→24 字符，支持长法规名 |
| TOC 目录解析 | `legal_structure_parser.py` | 新增目录页扫描，从 TOC 提取完整法规名修正截断标题 |
| 实务 PDF 重切 | `init_policy_collection.py` | 新切块逻辑适配段落 QA |
| 召回评测脚本更新 | `run_recall_eval_full.py` | 评测逻辑调整 |
| v1 遗留文件清理 | `data/eval_questions/` | 删除 v1 benchmark / report / analysis |

### 上次 commit (9f51880, 2026-06-22)

- Milvus 元数据 Bug 修复
- bids 向量库重建
- 段落切块 QA 适配

---

## V4 准备建议

### 题目是否需要重新生成？

**不需要。** benchmark v3 的 source_chunk IDs 已全部修复（815 个唯一 ID，100% DB 匹配）。法律条文 parent/child、案例段落、舆情新闻、政策文件四类题目的 chunk ID 均已与 DB 对齐。

### 权重变更预期影响

| 参数 | V3 | V4 | 预期 |
|------|----|----|------|
| bm25_weight | 0.65 | 0.45 | 关键词精确匹配权重下降 |
| dense_weight | 0.35 | 0.55 | 语义匹配权重上升 |

**注意**：当前 `fusion_strategy` 为 `rrf`，权重参数仅在切换为 `weighted` 或 `smart` 时生效。若 V4 继续使用 RRF，需改为 `weighted` 才能体现权重变化。

### chunk ID 有无变化？

有变化。V3 报告中 benchmark 有 25 个 source_chunks 因 law_name 截断与 DB 不匹配，现已修复。V4 测试时 exact_hit 指标会因 chunk ID 对齐而略有提升。
