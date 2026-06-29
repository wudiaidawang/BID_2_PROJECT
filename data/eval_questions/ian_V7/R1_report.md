# ian_V7 — 修复 law_name 误识别

## 改动内容
1. `legal_structure_parser.py`: 增加 `BODY_PATTERN_WORDS` 过滤，正文特征词（投标人、招标人等）+ 无法规后缀 + 长度>20 → 拒绝作为标题
2. `init_policy_collection.py`: 简化 `_repair_law_names()`，只保留硬编码映射（去掉拼接/符号清理）
3. 其余配置同 V5（header injection + RRF + rerank 1.5x + ef=128）

## 评测结果

| 指标 | V5 | V7 | 变化 |
|:----|:---:|:---:|:---:|
| exact_hit@5 | 88.7%（126/142） | **88.7%**（126/142） | = |
| parent_hit@5 | 94.4% | 92.3% | -2.1% |
| Miss | 7 | 7 | = |

## 剩余7个miss

| 类型 | 数量 | 说明 |
|:----|:---:|:------|
| 同法不同条（排序精度） | 3 | 价格法_6→_18、金融企业_32→_28等 |
| 跨法混淆 | 2 | 通信工程评标办法、竞争性磋商管理办法 |
| law_name截断 | 1 | `加配件或者售后服务量以及其他超出招标文件_59` |
| policy_doc混入 | 1 | policy_111 |

## 结论
parser 修复成功（无报错、pdf_law_parent 正常生成），但指标未提升。瓶颈已从 law_name 误识别转移到**排序精度**和**跨法混淆**。

## 文件清单
| 文件 | 说明 |
|:----|:-----|
| R1_eval_recall_report.json | 完整评估报告 |
| R1_eval_benchmark.json | 142题评测集 |
| R1_eval_output.log | 评估日志 |
| ian_V7_policy_chunks_export.json | 全量chunks导出 |
