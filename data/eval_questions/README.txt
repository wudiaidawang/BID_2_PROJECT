评估问答集 & 报告 — 版本对齐

================================================
V2 (当前)
  问答对: eval_benchmark_v2.json  (898 题, 三级命中体系)
  报告:   eval_recall_report_v2.json
  分析:   eval_recall_report_v2_analysis.md

V1 (旧版)
  问答对: eval_benchmark_v1.json  (457 题, 单级精确命中)
  报告:   eval_recall_report_v1.json

================================================
运行评测:
  python run_recall_eval_full.py
  输出: eval_recall_report_v2.json

V2 数据格式 (eval_benchmark_v2.json):
  {
    "qa_pairs": [
      {
        "id": "qa_v2_0001",
        "question": "问题文本",
        "answer": "参考答案",
        "source_chunks": ["parent_xxx_27_1_1234"],
        "chunk_count": 1,
        "category": "pdf_law_parent"
      }
    ]
  }

V1 数据格式 (eval_benchmark_v1.json):
  {
    "qa_pairs": [
      {
        "qa_id": "qa_0001",
        "question": "问题文本",
        "answer": "参考答案",
        "expected_chunk_ids": ["bids_0"],
        "chunk_count": 1,
        "chunk_type": "bid_project"
      }
    ]
  }
