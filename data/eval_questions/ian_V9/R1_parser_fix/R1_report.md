# ian_V9 R1 — parser body 否决机制

## 改动
`legal_structure_parser.py`: BODY_PATTERN_WORDS 检查移到正则匹配之前

## 结果
| 指标 | 值 |
|:----|:----:|
| exact_hit@5 | **76.1%（83/109）** |
| parent_hit@5 | 87.2% |
| Miss | 7（6.4%） |

## 说明
- 109题全新评测集（V9 chunks基于，10000条）
- parser改了文档结构，与V8不可直接比较
- 需要基于此基线继续迭代

## 文件清单
| 文件 | 说明 |
|:----|:-----|
| R1_eval_output.log | 评估日志 |
| R1_eval_recall_report.json | 评估报告 |
