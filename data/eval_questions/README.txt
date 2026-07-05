评估问答集 & 报告

版本演进:
  V1 (已废弃) — 457题, 单级精确命中体系
  V2 (已评测) — 772题, 三级命中体系 (exact/parent/soft)
  V3 (待评测) — 772题, 四级命中体系 (exact/parent/soft/cosine)
  V4 (已评测) — 1000题, 纯 chunk ID 匹配
  V5 (已评测) — 2174题, chunk ID 匹配 (expected + acceptable)

双 Benchmark 策略 (2026-06-28):
  Regression: v5_regression.json (当前版本, Chunk改写生成, Recall偏高)
  Realistic:  v6_benchmark.json (待构建, 真实用户风格, 用于论文/最终评测)

文件:
  V2: eval_benchmark_v2.json
  V3: eval_benchmark_v3.json
  V4: eval_benchmark_v4.json
  V5: v5_benchmark.json / v5_chunks.json / v5_regression.json
  V6: v6_benchmark.json / v6_chunks.json (待生成)
  报告: v4_report.md / v5_report.md / v6_report.md (待生成)
  提示词: prompts/v6_prompt.md