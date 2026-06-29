# V5 召回评测报告 — Chunk ID 匹配

**评测集**: eval_benchmark_v5.json, 2174 题
**评测方式**: 纯 chunk ID 匹配（expected_chunk_id / acceptable_chunk_ids）

## 整体召回率

| 指标 | 命中 | 总数 | 比率 |
|------|------|------|------|
| Recall@1 | 1555 | 2174 | **71.5%** |
| Recall@3 | 2093 | 2174 | **96.3%** |
| Recall@5 | 2174 | 2174 | **100.0%** |

## 按 chunk_type

| 类型 | 题数 | Recall@1 | Recall@3 | Recall@5 |
|------|------|----------|----------|----------|
| cross_chunk | 169 | 60.4% | 92.3% | **100.0%** |
| opinion_news | 437 | 93.8% | 100.0% | **100.0%** |
| parent_child | 368 | 67.7% | 97.0% | **100.0%** |
| pdf_case_paragraph | 151 | 58.9% | 97.4% | **100.0%** |
| pdf_law_parent | 1023 | 66.9% | 94.8% | **100.0%** |
| policy_doc | 26 | 80.8% | 100.0% | **100.0%** |

## 按 span

| 类型 | 题数 | Recall@1 | Recall@3 | Recall@5 |
|------|------|----------|----------|----------|
| cross | 169 | 60.4% | 92.3% | **100.0%** |
| parent_child | 368 | 67.7% | 97.0% | **100.0%** |
| single | 1637 | 73.5% | 96.5% | **100.0%** |


---

## 审查记录（2026-06-27）

### Recall@5=100% 归因分析

**1. acceptable_chunk_ids 分布**

2174 题中 317 题（14.6%）带有备选 chunk ID，降低了命中难度：

| span | 总数 | 有备选 ID | 占比 | 平均备选数 |
|------|------|-----------|------|------------|
| cross | 169 | 169 | 100% | 1.18 |
| parent_child | 368 | 148 | 40.2% | 1.79 |
| single | 1637 | 0 | 0% | 0 |

所有 169 条 cross_chunk 题都至少有 1 个备选 ID。手动抽样验证：qa_v5_2006（农业建设项目招标，article 17+18），expected chunk（第17条）在 reranker top 5 中未命中，但 acceptable chunk（第18条）排第 5 位，计为命中。跨条款题目本质上有多个正确答案，用备选 ID 合理，但客观上抬高了 Recall@5。

**2. Reranker 输入字段差异**

eval 脚本（eval_standalone.py L138）与项目 pipeline（app/pipeline/pipeline.py L310）使用的字段不同：

- eval: r.get("text", "")[:1024] — 纯法条正文，无法律名/章节前缀
- pipeline: d.get("parent_content") or d.get("retrieval_text", d.get("text", "")) — 优先 parent_content，其次 retrieval_text，最后 text

同一 chunk 实测：retrieval_text 322 字符（含 law_name / 章节 / 条号前缀），text 261 字符（仅法条正文）。eval 未输出 parent_content 字段，无法验证影响幅度。

**结论：eval 和 pipeline 的 reranker 输入不一致，评测结果不等同于生产管线表现。**

**3. 自评测天花板**

题目由 LLM 从 chunk 生成，question 与 source chunk 的 embedding 天然高度相似。Dense recall=50 + BM25 recall=50 + RRF 融合 + Rerank top 5 的管线在自评测场景下天花板很高。2174 条 100% 在技术上是可能的，但不应等同于对未见问题的真实召回率。

**4. single 类 1637 题零备选仍达 100%**

这是最值得关注的部分。1637 条 single 题没有备选 ID，全部在 top 5 命中。建议后续抽取 pdf_case_paragraph（R@1 仅 58.9%，单 chunk 类型中最难）做交叉验证，确认无数据泄露。
