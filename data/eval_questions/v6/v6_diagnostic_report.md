# V6 召回评测诊断报告

**日期**: 2026-06-29
**评测集**: v6_benchmark.json, 2908 题
**管线**: 预处理(jieba词边界) → Dense + BM25(jieba本地) → RRF(k=60) → Parent Expand → BGE-reranker-v2-m3

## 最终召回率

| 指标 | 命中 | 总数 | 比率 |
|------|------|------|------|
| Recall@1 | 1794 | 2908 | **61.7%** |
| Recall@5 | 1794 | 2908 | **61.7%** |

## 各阶段召回率对比

| 阶段 | Recall@1 | Recall@3 | Recall@5 | 说明 |
|------|----------|----------|----------|------|
| Dense only | 29.3% | 42.6% | 47.5% | Milvus COSINE 向量检索 |
| BM25 (jieba) | 31.6% | 44.6% | 49.9% | 本地 jieba 分词 BM25 |
| RRF fused | 30.5% | 47.8% | 53.4% | RRF k=60 融合 |
| Parent expanded | 30.5% | 47.8% | 53.4% | 注入 parent_content，不去重 |
| **Reranker final** | **39.4%** | **56.1%** | **61.7%** | BGE-reranker-v2-m3 精排 |

## 按 chunk_type 细分

| chunk_type | 数量 | R@1 | R@5 | 分析 |
|------|------|------|------|------|
| pdf_law_parent | 584 | 59.4% | 78.3% | 法条原文 parent chunk，效果最好 |
| pdf_case_paragraph | 669 | 45.6% | 70.4% | 案例段落，效果良好 |
| opinion_news | 266 | 26.7% | 44.7% | 解读/新闻类，效果偏差 |
| policy_doc | 1091 | 33.3% | 55.0% | 政策文档，占比最大但效果中等 |
| pdf_case_sliding | 252 | 19.0% | 50.8% | 滑动窗口案例，效果最差 |
| cross_doc | 46 | 26.1% | 41.3% | 跨文档，样本少效果一般 |

## 按 question_type 细分

| question_type | 数量 | R@1 | R@5 | 分析 |
|------|------|------|------|------|
| announcement_interpretation | 29 | 51.7% | 65.5% | 公示解读，样本少效果最好 |
| definition | 281 | 47.3% | 71.9% | 定义类，预处理跳过了同义词扩展 |
| scenario_judgment | 1197 | 41.8% | 64.1% | 场景判断，最大类别 |
| condition_check | 327 | 38.8% | 61.5% | 条件检查 |
| case_reasoning | 78 | 37.2% | 69.2% | 案例推理 |
| comparison | 150 | 36.0% | 56.0% | 对比类，效果低于均值 |
| responsibility | 264 | 34.1% | 60.2% | 责任判定 |
| procedure | 582 | 34.0% | 52.9% | 流程类，效果最差 |

## 按 retrieval_difficulty 细分

| 难度 | 数量 | R@1 | R@5 |
|------|------|------|------|
| direct | 765 | 43.4% | 64.2% |
| scenario | 1414 | 37.3% | 62.0% |
| synonym | 560 | 38.1% | 62.5% |
| cross_reference | 169 | 35.5% | 54.4% |

## Miss 分布分析

### 总览：1114 条 R@5 未命中

### 按 question_type 分布

| question_type | Miss 数 | 占总 Miss 比例 |
|------|------|------|
| scenario_judgment | 430 | 38.6% |
| procedure | 274 | 24.6% |
| condition_check | 126 | 11.3% |
| responsibility | 105 | 9.4% |
| definition | 79 | 7.1% |
| comparison | 66 | 5.9% |
| case_reasoning | 24 | 2.2% |
| announcement_interpretation | 10 | 0.9% |

### 按 difficulty 分布

| difficulty | Miss 数 | 占总 Miss 比例 |
|------|------|------|
| scenario | 538 | 48.3% |
| direct | 274 | 24.6% |
| synonym | 225 | 20.2% |
| cross_reference | 77 | 6.9% |

### 最多被 Miss 的 expected chunk (Top 15)

| chunk_id | Miss 次数 |
|------|------|
| opinion_1460 | 34 |
| policy_199 | 18 |
| parent_中央国家机关政府采购中心货物和服务定点采_43_3775_2327 | 17 |
| policy_85 | 15 |
| opinion_1422 | 14 |
| policy_203 | 12 |
| policy_197 | 12 |
| policy_134 | 11 |
| policy_60 | 11 |
| parent_中央国家机关政府采购中心货物和服务定点采_22_3717_1511 | 11 |
| policy_171 | 10 |
| pdf_招标投标法律解读与风险防范实务_para_0689 | 10 |
| policy_185 | 9 |
| policy_131 | 8 |
| policy_138 | 8 |

### 最多被误返回的 top1 chunk (Top 15)

| chunk_id | 出现次数 |
|------|------|
| parent_中央国家机关政府采购中心货物和服务定点采_14_3843_6875 | 19 |
| parent_交通运输部部属单位政府采购管理办法_29_3946_7341 | 17 |
| pdf_招标投标法律解读与风险防范实务_para_0054 | 16 |
| pdf_招标投标法律解读与风险防范实务_para_0625 | 15 |
| parent_中央国家机关政府采购中心货物和服务定点采_15_3844_2075 | 15 |
| parent_明确或实际投标人报名数量未达到招标公告中_24_1098_2416 | 14 |
| parent_中央国家机关政府采购中心货物和服务定点采_21_3716_9599 | 12 |
| parent_中华人民共和国政府采购法实施条例_32_27_3943 | 12 |
| parent_公共资源交易平台公共资源交易平台管理暂行_36_4105_195 | 10 |
| pdf_招标投标法律解读与风险防范实务_para_0398 | 10 |
| parent_中华人民共和国政府采购法实施条例_22_19_7099 | 9 |
| parent_中央国家机关政府采购电子卖场管理办法_23_3649_2626 | 8 |
| pdf_招标投标法律解读与风险防范实务_para_0686 | 8 |
| pdf_运输服务公司串通投标不正当竞争纠纷案_5_1403 | 8 |
| parent_中央国家机关政府采购中心货物和服务定点采_10_3705_3409 | 8 |

## 根因分析

### 1. 预处理 (口语→书面语) 仍然是召回瓶颈

- Dense R@5=47.5% + BM25 R@5=49.9% 说明单路检索本身有天花板
- RRF 融合后 R@5=53.4%，比单路好但提升有限
- 口语→书面语映射虽然加了词边界保护，但仍然改变了查询语义
- **建议**: 对比测试关闭预处理后的召回率

### 2. 同义词扩展可能过度泛化

- 预处理中同义词双向扩展（如"投标人"→添加"供应商""潜在投标人""投标方"）
- 定义类问题已跳过同义词扩展，但非定义类问题仍受影响
- **建议**: 根据 question_type 选择性启用同义词扩展

### 3. policy_doc 类召回偏低 (R@5=55.0%)

- 1091 题属于 policy_doc，占总数的 37.5%，但召回明显低于 pdf_law_parent (78.3%)
- policy_doc 是 Markdown 格式的政策文档，可能与 PDF 法条的文本特征不同
- **建议**: 检查 policy_doc 的 chunking 策略和 embedding 质量

### 4. procedure 类问题召回最低 (R@5=52.9%)

- 流程类问题通常需要多步推理，单个 chunk 难以完整回答
- **建议**: 考虑对 procedure 类启用多 chunk 拼接或 chain 式检索

### 5. Reranker 提升显著但仍有空间

- Reranker 将 R@5 从 53.4% 提升到 61.7% (+8.3pp)
- R@1 提升更明显：30.5% → 39.4% (+8.9pp)
- 扩大 RERANK_POOL 或使用更强的 reranker 模型可能有进一步提升

## 已修复的 Bug (本轮评测)

1. **Milvus 内置 BM25 → 本地 jieba BM25**: Milvus 字符 n-gram 分词不符合中文语义
2. **口语→书面语盲替换**: 单字词 ("交"→"提交") 破坏复合词 ("交易"→"提交易")，已加 jieba 词边界保护
3. **Parent Expand article_id 去重**: 同法条不同段落被错误去重，已移除（评测用）
4. **RRF 分数未注入**: fusion 结果排序使用原始 Dense/BM25 分数而非 RRF 分数，已修复
