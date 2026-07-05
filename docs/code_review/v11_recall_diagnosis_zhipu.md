# 智谱 V11 召回诊断

> 待发送至智谱分析

---

## 背景

招投标法规智能问答系统 RAG 召回评测。5 阶段管线：Query预处理 → Dense+BM25双路召回 → Weighted Fusion → Parent上下文扩展 → BGE Reranker。

数据：4984 chunks（法条1680+子155 / 案例908+78 / 政策149 / 舆情2014），BGE-M3 embedding 1024维，Milvus向量库。

## V11 评测结果（去 comparison 后）

- 总题数：2832，R@5=92.0%，miss=226
- 各阶段：Dense 78.0% → BM25 86.4% → Fusion 87.2% → Reranker 92.0%
- BM25 单独 R@5=86.4%，显著强于 Dense 的 78.0%，融合后仅 +0.8%

### 按 span

| span | 题数 | R@5 | miss |
|------|------|-----|------|
| single | 2264 | 93.8% | 141 |
| cross_chunk | 517 | 86.5% | 70 |
| cross_doc | 51 | 70.6% | 15 |

### 按 chunk_type

| type | 题数 | R@5 |
|------|------|-----|
| opinion_news | 130 | 100.0% |
| policy_doc | 741 | 96.6% |
| pdf_case_structured | 428 | 90.7% |
| pdf_case_sliding | 223 | 90.6% |
| pdf_law_child | 235 | 90.2% |
| **pdf_law_parent** | **1075** | **89.1%** |

### 按 question_type

| type | 题数 | R@5 |
|------|------|-----|
| announcement | 88 | 98.9% |
| scenario_judgment | 386 | 93.8% |
| responsibility | 364 | 94.5% |
| definition | 212 | 92.5% |
| procedure | 1087 | 91.0% |
| case_reasoning | 147 | 90.5% |
| condition_check | 548 | 90.3% |

### 按难度

| difficulty | 题数 | R@5 |
|-------------|------|-----|
| scenario | 12 | 91.7% |
| direct | 208 | 88.9% |
| **synonym** | **2612** | **92.3%** |

## 关键观察

1. **BM25 主导，Dense 弱势**：BM25 单路 R@5=86.4% vs Dense 78.0%，融合后仅 87.2%（+0.8%），融合几乎无增益

2. **Reranker 贡献大**：87.2% → 92.0%（+4.8%），是最大单一提升源

3. **法条父块最差**：pdf_law_parent R@5=89.1%（1075题），是除 100% 舆情外最低的

4. **synonym 主导**：92.3% 题目 difficulty=synonym，direct 反而更低 88.9%

5. **procedure 是最大的 miss 源**：98/226 miss，占 43%

6. **高频 miss 目标**：
   - `工程施工招标投标办法_23` 被 miss 9 次
   - `房屋建筑和市政工程招标办法_16` 被 miss 7 次
   - `电子招标投标办法_43` 被 miss 6 次
   - `policy_67`（上海公共资源交易平台）被 miss 5 次

7. **教科书 `招标投标法律解读与风险防范实务` 是 top-1 抢占王**：
   - `struct_0482` 抢走 6 次 top-1
   - `struct_0263` 抢走 5 次
   - `struct_0835` 抢走 4 次

8. **Parent Expansion 零贡献**：扩展前后 R@5 完全不变（87.2%→87.2%）

9. **跨文档惨淡**：51 题 cross_doc，R@1=37.3%, R@3=52.9%, R@5=70.6%

## 分析问题

请从以下角度分析并给出具体改进建议：

1. **融合失效根因**：Dense+BM25 融合后仅 +0.8%，为什么？是归一化问题（Min-Max）、权重问题（当前 semantic 0.55/0.45）、还是两路召回重叠度过高？

2. **法条父块召回瓶颈**：pdf_law_parent 的 R@5=89.1% 是所有活跃类型中最低的，可能原因是什么？父块文本长导致向量表示稀释？BM25 关键词匹配不够精确？

3. **教科书抢占问题**：`招标投标法律解读与风险防范实务` 多次成为 miss 的 top-1，如何在不降低教科书本身召回的前提下，让真正的法条原文/案例也能进入 top-5？

4. **Parent Expansion 为何零贡献**：R@5 扩展前后无变化，是 child chunk 数量太少（155/4984），还是扩展逻辑有问题？

5. **synonym 与 direct 倒挂**：为什么 direct（直白问题）R@5=88.9% 反而不如 synonym（同义词问题）的 92.3%？

6. **procedure 题型优化**：procedure 占 miss 的 43%，这类问题有什么共同特征？如何针对性改善？

7. **优先级建议**：在 226 miss 中，哪些改进方向投入产出比最高？
