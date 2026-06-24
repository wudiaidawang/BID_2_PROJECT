评估问答集 & 报告

版本演进:
  V1 (已废弃) — 457题, 单级精确命中体系 (exact only)
  V2 (已评测) — 772题, 三级命中体系 (exact/parent/soft), 含截断law_name问题
  V3 (待评测) — 772题, 四级命中体系 (exact/parent/soft/cosine)
             — 修复: 截断law_name(3个→完整) + opinion/policy 同步law_name
             — 新增: 余弦相似度命中 (cosine_hit, threshold=0.85)

文件对照:
  问答对 (V2): eval_benchmark_v2.json
  问答对 (V3): eval_benchmark_v3.json
  报告 (V2):   eval_recall_report_v2.json
  报告 (V3):   eval_recall_report_v3.json  (待生成)

运行评测:
  python run_recall_eval_full.py
  读取: config.yaml 中的 benchmark_file 路径
  输出: eval_recall_report_v3.json
