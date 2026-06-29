# ian_V8 R4 — child chunk 修复 + 检索侧 law_name修复

## 改动
1. `expanders.py`: child chunk 不再被 parent 跳过，保留自身 ID 参与 rerank
2. `pipeline.py`: 检索侧修复截断的 law_name（硬编码映射）

## 结果

| 指标 | R3（560题） | R4（child fix） |
|:----|:---:|:---:|
| exact_hit@5 | 85.7%（480/560） | **90.7%（508/560）** |
| parent_hit@5 | 96.1% | 96.6% |
| Miss | 12（2.1%） | **9（1.6%）** |

| chunk_type | R3 | R4 |
|:----|:---:|:---:|
| pdf_law_parent（法条） | 93.4% | 91.6% |
| pdf_law_child | 14.3% | **95.2%** 🚀 |
| pdf_case_paragraph（实务书） | 88.7% | 88.2% |
| policy_doc | 92.6% | 92.6% |

## 剩余9个miss
- 同法不同条：~4
- law_name截断/误识别：~3
- 跨法混淆：~2

## 全版本汇总
| 版本 | 改动 | exact_hit@5 |
|:----|:----|:--------:|
| V4 | 基线 | 74.5%（142题）|
| V5 | law_name修复 | 88.7%（142题）|
| V7 | parser + 场景化评测 | 90.4%（146题）|
| V8 R1 | 短条文合并 | 91.1%（146题）|
| V8 R2 | RRF k=20 | 93.2%（146题）|
| V8 R3 | 扩展560题 | 85.7%（560题）|
| **V8 R4** | **child chunk修复** | **90.7%（560题）** |
