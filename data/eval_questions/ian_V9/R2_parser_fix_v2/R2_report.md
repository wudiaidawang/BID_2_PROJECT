# ian_V9 R2 — parser body否决 修正版

## 改动
`legal_structure_parser.py`: body word 检查条件从 `len>20 + 含1个词` → `len>40 + 含至少3个词`

## 结果
| 指标 | R1（太激进） | R2（修正版） |
|:----|:---:|:---:|
| exact_hit@5 | 76.1%（83/109） | **94.3%（133/141）** |
| parent_hit@5 | 87.2% | 96.5% |
| Miss | 7（6.4%） | **1（0.7%）** |

| chunk_type | exact_hit@5 |
|:----|:--------:|
| pdf_law_parent | 95.7% |
| pdf_case_paragraph（实务书） | 84.2% |
| pdf_law_child | 100% |
| policy_doc | 100% |
| cross_chunk | 94.3% |

## 剩余 1 个 miss
