# CHANGELOG — 2026-06-21

## 1. 实务PDF重新切分入库

**文件**: `rechunk_shiwu.py`（新建）

- 旧 `pdf_case_sliding` 滑动窗口切法 → 自然段归并切法
- 切分逻辑：`\n\n` 分自然段 → 过滤 <50字短段 → 相邻段归并至 ~500字
- 删除旧 chunks: **1969条** (source_doc=招标投标法律解读与风险防范实务, chunk_type=pdf_case_sliding)
- 新增 chunks: **770条** (chunk_type=pdf_case_paragraph)
- 每个新 chunk 带 `law_name: "招标投标法律解读与风险防范实务"`，现在可参与 parent 级命中

## 2. Query 中文数字→阿拉伯数字规范化

**文件**: `app/core/query_rewriter.py`

- 新增 `_normalize_article_numbers()` 方法
- "第三十七条" → "第37条"、"第五十五条" → "第55条"
- 在 `rewrite()` pipeline 标点规范化之后、受保护名称检查之前执行
- 依赖 `app/utils/chinese_number.py` 的 `ChineseNumberConverter`

## 3. Pipeline 条款号精确匹配 boost

**文件**: `app/pipeline/pipeline.py`

- 新增 `_extract_query_article_id()` 方法：从 query 提取条款号（统一为阿拉伯数字）
- 在 `_do_rerank()` 中，source_type boost 之后：
  - 若 query 含条款号，对 `article_id` 匹配的 chunk 做 **1.2x** 分数 boost
  - 重新按 score 降序排列
- **不需要重新入库**，纯检索时后处理

## 4. 评测脚本 bug 修复

**文件**: `run_recall_eval_full.py`

- `_derive_source_type()`: `chunk_type=""` 时返回 `"unknown"` 而非 `"bid"`（修复旧实务ID找不到时误判为bid的问题）
- `_parse_chunk_id()`: 新增 `pdf_*` 前缀兼容（旧格式 `pdf_{name}_{number}` → `pdf_case_sliding`）

## 5. 评测文件版本对齐

**目录**: `data/eval_questions/`

| 文件 | 说明 |
|------|------|
| `eval_benchmark_v1.json` | V1 问答对（457题，单级精确命中体系） |
| `eval_recall_report_v1.json` | V1 评测报告 |
| `eval_benchmark_v2.json` | **V2 问答对（898题，三级命中体系）← 当前使用** |
| `eval_recall_report_v2.json` | V2 评测报告 |
| `eval_recall_report_v2_analysis.md` | V2 根因分析报告 |

删除的冗余文件：
- `policy_chunks_export.json` (15MB) + `.ids` + `.tmp` — Milvus导出中间文件
- `hybrid_test_cases_modified.json` — 旧测试用例
- 旧命名 `eval_benchmark_manual_v1.json` → `eval_benchmark_v1.json`
- 旧命名 `eval_recall_report_full.json` → `eval_recall_report_v1.json`

## 6. 其他修复

- `app/core/model_client.py`: `remote_rerank()` 索引映射 bug 修复（content→index mapping 替代 enumerate）

## 评测结果摘要（V2 benchmark，需隧道稳定后重跑确认）

上次有效跑（隧道掉线前）：
| 指标 | 值 | 变化 |
|------|-----|------|
| parent_hit@5 | 74.2% | ↓（因实务旧ID 192/199失效） |
| pdf_law_parent miss | **25** | ↓3（条款号boost有效） |
| pdf_law_child miss | **10** | ↓2 |
| pdf_case_sliding miss | 192 | ↑133（旧ID全删，需重新生成QA） |

## 明日待办

- [ ] 确认隧道稳定后重跑 V2 评测
- [ ] 为新的 `pdf_case_paragraph` chunks 重新生成 QA 对
- [ ] 评测报告 + 根因分析更新
