评估问答集目录
================

此目录用于存放评估用的问答对文件。

文件格式：
- JSON 数组，每个元素包含 question（问题）和 expected_answer（期望答案关键词/原文）
- 支持多个 .json 文件，评估时会合并加载

示例格式见 data/template.json.backup。

使用方式：
  将你的问答 .json 文件放入此目录，然后运行：
  python eval_retrieval_accuracy.py
  python test_accuracy.py

数据结构说明：
  {
    "question": "问题文本",          // 必填
    "expected_answer": "答案文本",    // 必填，用于提取关键词验证检索结果
    "source": "来源标识",            // 可选
    "full_chunk": "完整原文段落"      // 可选
  }
