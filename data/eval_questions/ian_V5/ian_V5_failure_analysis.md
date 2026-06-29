# ian_V5 — 失败案例分析

## 改动内容
1. 修复 `_TRUNCATED_NAME_FIXES` 增加2条映射
2. Header injection: policy_doc + opinion_news + pdf_case_sliding
3. 过滤 policy_doc 正文 < 100字的垃圾数据
4. fusion: RRF + article_id boost（rerank 1.5x）
5. ef=128, search_ef: 128

## 评测结果

| 指标 | V4（RRF基线） | V5 |
|:----|:---:|:---:|
| exact_hit@5 | 82.4%（84/102） | **88.7%（126/142）** |
| parent_hit@5 | 89.2% | 94.4% |
| Miss | 5.9%（6/102） | 4.9%（7/142） |

## 剩余7个miss分析

| 类型 | 数量 | 说明 |
|:----|:---:|:-----|
| law_name截断 | 4 | 解析器未能正确拼接跨行截断的法规名 |
| 跨法混淆 | 2 | 语义相近的不同法规 |
| 实务书被淹 | 1 | pdf_case_paragraph被法条覆盖 |

**主要瓶颈**: law_name 截断仍是最大问题，`_TRUNCATED_NAME_FIXES` 只能修已知模式，PDF解析器的跨行拼接需要更系统的方案。

## 文件清单
| 文件 | 说明 |
|:----|:-----|
| ian_V5_eval_recall_report.json | 完整评估报告 |
| ian_V5_eval_benchmark.json | 142题评测集 |
| ian_V5_policy_chunks_export.json | 全量chunks导出（18MB） |
