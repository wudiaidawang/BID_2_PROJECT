# 更新日志 — 2026-06-24

## 1. BM25 检索恢复

**原因**: 远程 Milvus 服务曾因 SSH 隧道状态异常返回 502，导致 `search_keyword()` 失败，BM25 稀疏向量检索恒返回 0 条结果。

**修复**:
- 杀掉旧隧道进程 (PID 15384)，`python tunnel.py 090903` 重启
- 确认端口 19531 (Milvus) 和 8210 (Embedding/Reranker) 恢复正常

**验证**: `ServerBM25Retriever` 对 policy 库返回非零 BM25 分数（示例：8.34, 8.28, 8.06），`search_keyword` 正常返回 50 条候选。

## 2. 召回评估 V4 完整报告

**工具**: `run_recall_eval_full.py`（1001 题，RRF 融合 + BGE-Reranker 精排）

| 指标 | BM25=0 (之前) | BM25 正常 (现在) | 提升 |
|------|-------------|----------------|------|
| parent_hit@5 | 78.5% | **90.0%** | +11.5pp |
| exact_hit@5 | 69.7% | **80.4%** | +10.7pp |
| MRR | -- | **0.6788** | -- |
| Miss | 19.4% | **6.2%** | -13.2pp |

按类别 parent_hit@5：
| 类别 | 数量 | 命中率 |
|------|------|--------|
| opinion_news | 86 | **100%** |
| pdf_case_paragraph | 215 | 93.0% |
| pdf_law_parent | 558 | 90.7% |
| policy_doc | 54 | 88.9% |
| pdf_law_child | 88 | 69.3% |

child chunk 的 exact_hit=2.3% 是预期行为（滑动窗口子块 ID 无法精确匹配，但 parent 级命中仍为 69.3%）。

**输出**: `data/QA_report/eval_recall_report_v4.json`

## 3. Reranker 本地加载修复

**文件**: `app/pipeline/pipeline.py`, `app/pipeline/rerankers.py`

- `_do_rerank()`: 移除预先调用 `_get_model()` 的逻辑。原代码在每次 rerank 前都加载本地 BGE 模型（即使远程 reranker 正常工作），改为仅检查 `settings.reranker_enabled`
- `BgeReranker.rerank()`: 远程失败时才调用 `_get_model()` 加载本地 fallback，不再在对象构造时预加载
- 实际本次评估中远程 reranker **0 次失败**，本地模型虽被加载但未用于推理

## 4. 文件变更

| 文件 | 变更 |
|------|------|
| `app/pipeline/pipeline.py` | `_do_rerank` 移除本地模型预加载 |
| `app/pipeline/rerankers.py` | 远程优先，失败时才加载本地模型 |
| `data/QA_report/eval_recall_report_v4.json` | V4 完整评估报告 (1001 题) |

## 5. 下一步建议

- pdf_law_child (69.3%) 是召回瓶颈 — 可考虑在 child→parent 扩展阶段优化 article_id 匹配逻辑
- 62 条 miss 中 46 条来自 regulation_article，可进一步分析根因
