# ian_V7 R2 — 场景化评测集 + 分类型prompt

## 改动内容
1. `gen_eval_benchmark_v4.py`: 4种chunk_type各自独立的prompt模板
   - pdf_law_parent → definition（法条精确查询）
   - pdf_case_paragraph → scenario_judgment（场景式，以"我们公司"开头）
   - policy_doc → condition_check（政策条件）
   - cross_chunk → comparison（跨法条对比）
2. 调整抽样分布：实务书从12题提升到19题

## 评测结果（RRF最优配置）
| 指标 | 旧评测集（142题） | 新评测集（146题） |
|:----|:---:|:---:|
| exact_hit@5 | 90.1%（128/142） | **90.4%（132/146）** |
| parent_hit@5 | 95.1% | 95.2% |
| MRR | — | — |
| Miss | 2.1%（3/142） | 3.4%（5/146） |

## 分类型结果
| chunk_type | 题数 | exact_hit@5 | 题型 |
|:----|:---:|:--------:|:-----|
| pdf_law_parent（法条） | 121 | **95.0%** | definition |
| pdf_case_paragraph（实务书） | 19 | **78.9%** | scenario_judgment |
| cross_chunk（跨法条） | 5 | 100% | comparison |
| policy_doc | 2 | 100% | condition_check |
| pdf_law_child | 4 | 0% | procedure |

## Weighted 对比
| 配置 | exact_hit@5 | 说明 |
|:----|:--------:|:-----|
| RRF（最优） | **90.4%** | 当前默认 |
| Weighted + 无boost | 88.4% | -2% |
| Weighted + rerank boost | 88.4% | 无效 |

结论：Weighted 不如 RRF，保持 RRF。

## 文件清单
| 文件 | 说明 |
|:----|:-----|
| benchmark_scene_146.json | 场景化评测集（146题，含19道实务书场景题） |
| R2_weighted/R2_eval_with_new_benchmark.log | 评估日志 |
| R2_weighted/R2_eval_recall_report.json | 完整评估报告 |
