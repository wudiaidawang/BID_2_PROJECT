# V4 召回评测报告

**日期**: 2026-06-24  
**Benchmark**: eval_benchmark_v4 (1001 题)  
**Pipeline**: BM25 + Vector → RRF 融合 → BGE-Reranker 精排 + source_type boost  
**top_k**: 5  
**备注**: 已修复 3 条伪 miss (qa_v4_0983/0984 law_name 缺"实务"，qa_v4_0474 引号字符编码)

---

## 一、总览

| 指标 | 值 | 说明 |
|------|-----|------|
| parent_hit@1 | **56.1%** (562/1001) | 首条即命中 |
| parent_hit@5 | **90.0%** (901/1001) | 前5条命中（主指标） |
| exact_hit@1 | 53.0% (531/1001) | 精确 chunk ID 匹配 |
| exact_hit@5 | 80.4% (805/1001) | |
| MRR (parent) | **0.6788** | Mean Reciprocal Rank |
| recall@5 (parent) | 0.8753 | |
| cosine_hit@5 | 4.6% (46/1001) | 余弦 ≥ 0.85（不计入 Miss） |
| soft_hit | 0.0% (0/1001) | 语义等价命中 |
| **Miss 率** | **6.2%** (62/1001) | 修复后 5.9% (59/1001) |

### 四级命中体系

```
exact → parent → cosine → miss
  │        │        │        │
  │        │        │        └── 无任何命中
  │        │        └─────────── 余弦相似度 ≥ 0.85 (语义相近)
  │        └──────────────────── 同法律/同文档 (article_id 相同)
  └───────────────────────────── chunk ID 精确匹配
```

---

## 二、按类别 parent_hit@5

| 类别 | 数量 | parent_hit@1 | parent_hit@5 | exact_hit@5 | MRR | Miss |
|------|------|-------------|-------------|-------------|-----|------|
| opinion_news | 86 | 97.7% | **100.0%** | 100.0% | 0.9855 | 0 |
| pdf_case_paragraph | 215 | 19.1% | **93.0%** | 76.7% | 0.4018 | 11 |
| pdf_law_parent | 558 | 68.8% | **90.7%** | 90.3% | 0.7778 | 23 |
| policy_doc | 54 | 40.7% | **88.9%** | 88.9% | 0.6000 | 5 |
| pdf_law_child | 88 | 35.2% | **69.3%** | 2.3% | 0.4767 | 23 |

---

## 三、按 chunk_count 维度

| 预期 chunk 数 | 题目数 | parent_hit@5 | exact_hit@5 | MRR | Miss |
|-------------|--------|-------------|-------------|-----|------|
| 1 chunk | 893 (89.2%) | 90.5% | 79.7% | 0.6697 | 57 |
| 2 chunks | 97 (9.7%) | 85.6% | 85.6% | 0.7552 | 5 |
| 3 chunks | 11 (1.1%) | 90.9% | 90.9% | 0.7500 | 0 |

---

## 四、Miss 分析 (62 条)

### 按类别分布

| 类别 | Miss 数 | 占比 |
|------|---------|------|
| pdf_law_parent | 23 | 37.1% |
| pdf_law_child | 23 | 37.1% |
| pdf_case_paragraph | 11 | 17.7% |
| policy_doc | 5 | 8.1% |

### pdf_law_child (23 条) — 已确认非数据管道问题

22/23 的 child chunk **在 Milvus 中存在且独立 embed**，但全部不进 top 5。根因：child chunk 检索文本短 (80~440 字)，向量相似度拼不过拥有完整法条的 parent chunk（500~2000 字）。详见 `regulation_miss_analysis.txt`。

- qa_v4_0474: 已修复（引号编码，child 实际在 Milvus 中以中文双引号存在）

### pdf_law_parent (23 条)

需逐条分析根因（语义漂移 / 条款号匹配失效 / 法条不在索引中等）。

### pdf_case_paragraph (11 条)

含 qa_v4_0983/0984（已修复，law_name 缺"实务"），修复后降至 9 条。

### policy_doc (5 条)

qa_v4_0741, qa_v4_0762, qa_v4_0772, qa_v4_0774, qa_v4_0776。

### Miss QA ID 清单

- **pdf_law_parent (23)**: qa_v4_0005, qa_v4_0014, qa_v4_0065, qa_v4_0105, qa_v4_0142, qa_v4_0159, qa_v4_0186, qa_v4_0195, qa_v4_0206, qa_v4_0238, qa_v4_0248, qa_v4_0337, qa_v4_0344, qa_v4_0391, qa_v4_0400, qa_v4_0405, qa_v4_0410, qa_v4_0434, qa_v4_0869, qa_v4_0908, qa_v4_0913, qa_v4_0928, qa_v4_1001
- **pdf_law_child (23)**: qa_v4_0441, qa_v4_0444, qa_v4_0452, qa_v4_0455, qa_v4_0461, qa_v4_0462, qa_v4_0463, qa_v4_0464, qa_v4_0468, qa_v4_0474, qa_v4_0481, qa_v4_0484, qa_v4_0486, qa_v4_0488, qa_v4_0491, qa_v4_0494, qa_v4_0495, qa_v4_0500, qa_v4_0503, qa_v4_0522, qa_v4_0527, qa_v4_0528, qa_v4_0589
- **pdf_case_paragraph (11)**: qa_v4_0548, qa_v4_0551, qa_v4_0668, qa_v4_0670, qa_v4_0672, qa_v4_0723, qa_v4_0724, qa_v4_0727, qa_v4_0979, qa_v4_0983, qa_v4_0984
- **policy_doc (5)**: qa_v4_0741, qa_v4_0762, qa_v4_0772, qa_v4_0774, qa_v4_0776

---

## 五、Parent Resolution（父块解析）

| 指标 | 值 |
|------|-----|
| 唯一预期 chunk 总数 | 1,085 |
| 含 parent_id | 86 (7.9%) |
| 含 article_id | 746 (68.8%) |
| 含 retrieval_text (余弦可用) | 1,081 (99.6%) |
| 无 article_id 或 parent_id | 339 (31.2%) |

---

## 六、与 V3 对比

| 指标 | V3 | V4 | 变化 |
|------|-----|-----|------|
| 题目数 | 772 | 1001 | +229 |
| 命中体系 | 四级 (exact/parent/soft/cosine) | 四级 | 同 |
| parent_hit@5 | — | 90.0% | 新指标 |
| MRR | — | 0.6788 | 新指标 |
| Miss 率 | — | 6.2% | — |

---

## 七、已知问题

1. **pdf_law_child exact_hit@5 = 2.3%**: 非数据管道 bug，child chunk 独立存在但检索排序拼不过 parent。需通过增大 child target_size 或 Reranker boost 改善
2. **3 条伪 miss 已修复**: qa_v4_0983/0984 (law_name缺"实务")、qa_v4_0474 (引号编码)，修复后应从 miss 转为 exact hit
3. **pdf_case_paragraph parent_hit@1 = 19.1%**: 实务段落首条命中率极低，说明段落级检索的语义区分度不足，需多轮精排才能定位

---

## 八、结论

V4 评测整体表现良好，parent_hit@5 达 **90.0%**。主要瓶颈在 pdf_law_child (69.3%) 和 pdf_case_paragraph 的首条命中率 (19.1%)。62 条 miss 中 23 条来自 child chunk（检索排序问题），23 条来自 parent chunk（需逐条分析语义漂移），修复 3 条伪 miss 后 miss 率降至 5.9%。
