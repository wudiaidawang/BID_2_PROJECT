# V9 召回评测报告 — Chunk ID 匹配（加权融合 + 法条Boost + Parent上下文增强）

**评测集**: v8_canonical.jsonl, 3146 题
**评测方式**: 纯 chunk ID 匹配（expected_chunk_id / acceptable_chunk_ids）
**融合策略**: Weighted Fusion（Min-Max 归一化 + 动态权重 semantic 0.55/0.45 + 法条检测 Boost）
**统一口径**: Pool@30 = 各阶段取 top 30 看 target 是否在池中（与 reranker 入口对齐）
**BM25**: 本地 jieba 分词

## 各阶段召回率对比

| 阶段 | Recall@1 | Recall@3 | Recall@5 | Pool@30 |
|------|----------|----------|----------|---------|
| Dense only | 51.0% | 69.5% | 75.5% | 90.3% |
| BM25 (jieba) | 57.8% | 74.8% | 81.0% | 94.8% |
| Weighted fused | 58.0% | 75.6% | 82.1% | 95.7% |
| Parent expanded | 58.0% | 75.6% | 82.1% | 95.7% |
| Reranker final | 68.5% | 85.0% | 89.5% | 89.5% |

## 最终召回率 (Reranker 后)

| 指标 | 命中 | 总数 | 比率 |
|------|------|------|------|
| Recall@1 | 2155 | 3146 | **68.5%** |
| Recall@3 | 2673 | 3146 | **85.0%** |
| Recall@5 | 2816 | 3146 | **89.5%** |

## 按 benchmark_level (改写层次)

| 类型 | 题数 | Recall@1 | Recall@3 | Recall@5 |
|------|------|----------|----------|----------|
| canonical | 3146 | 68.5% | 85.0% | **89.5%** |

## 按 chunk_type

| 类型 | 题数 | Recall@1 | Recall@3 | Recall@5 |
|------|------|----------|----------|----------|
| opinion_news | 135 | 96.3% | 97.8% | **99.3%** |
| pdf_case_paragraph | 664 | 58.3% | 75.9% | **82.4%** |
| pdf_case_sliding | 228 | 49.6% | 79.8% | **89.9%** |
| pdf_law_child | 238 | 65.1% | 83.6% | **89.9%** |
| pdf_law_parent | 1083 | 67.3% | 84.6% | **89.5%** |
| policy_doc | 798 | 80.3% | 92.7% | **93.6%** |

## 按 question_type (题型)

| 类型 | 题数 | Recall@1 | Recall@3 | Recall@5 |
|------|------|----------|----------|----------|
| announcement_interpretation | 92 | 87.0% | 94.6% | **96.7%** |
| case_reasoning | 181 | 54.7% | 76.8% | **85.6%** |
| comparison | 98 | 44.9% | 64.3% | **65.3%** |
| condition_check | 578 | 66.8% | 83.6% | **88.8%** |
| definition | 209 | 67.5% | 90.0% | **92.3%** |
| procedure | 1237 | 69.3% | 84.8% | **89.7%** |
| responsibility | 394 | 71.6% | 87.6% | **90.4%** |
| scenario_judgment | 357 | 74.5% | 89.4% | **94.1%** |

## 按 retrieval_difficulty (检索难度)

| 类型 | 题数 | Recall@1 | Recall@3 | Recall@5 |
|------|------|----------|----------|----------|
| direct | 223 | 62.3% | 80.7% | **87.4%** |
| scenario | 15 | 66.7% | 93.3% | **93.3%** |
| synonym | 2908 | 69.0% | 85.2% | **89.6%** |

## 按 span

| 类型 | 题数 | Recall@1 | Recall@3 | Recall@5 |
|------|------|----------|----------|----------|
| cross_chunk | 525 | 62.7% | 81.7% | **86.9%** |
| cross_doc | 66 | 53.0% | 65.2% | **78.8%** |
| single | 2555 | 70.1% | 86.1% | **90.3%** |

## 交叉分析: chunk_type × question_type

| chunk_type \ question_type | announcement_interpretation | case_reasoning | comparison | condition_check | definition | procedure | responsibility | scenario_judgment |
|---|---|---|---|---|---|---|---|---|
## Miss 样本

共 330 条 (R@5 仍未命中):

1. [scenario_judgment][synonym] 上海市公共资源交易中心包含哪些分平台？
   - expected: `policy_67`
   - top1: `policy_0`
   - law: `【国有产权】市国资委关于延长上海市产权交易场所管理实施办法(暂行)有效期的通知`
   - type: `policy_doc` | span: `single`

2. [scenario_judgment][synonym] 上海市公共资源交易平台建设工程招投标分平台属于哪个系统？
   - expected: `policy_100`
   - top1: `policy_0`
   - law: `【建设工程】勘察电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

3. [scenario_judgment][synonym] 上海市公共资源交易平台包含哪些分平台？
   - expected: `policy_67`
   - top1: `policy_125`
   - law: `【国有产权】市国资委关于延长上海市产权交易场所管理实施办法(暂行)有效期的通知`
   - type: `policy_doc` | span: `single`

4. [scenario_judgment][synonym] 上海市公共资源交易平台建设工程招投标分平台属于哪个系统？
   - expected: `policy_100`
   - top1: `policy_0`
   - law: `【建设工程】勘察电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

5. [scenario_judgment][synonym] 上海市公共资源交易平台包含哪些分平台？
   - expected: `policy_67`
   - top1: `policy_125`
   - law: `【国有产权】市国资委关于延长上海市产权交易场所管理实施办法(暂行)有效期的通知`
   - type: `policy_doc` | span: `single`

6. [scenario_judgment][synonym] 上海市公共资源交易平台建设工程招投标分平台属于哪个系统？
   - expected: `policy_100`
   - top1: `policy_0`
   - law: `【建设工程】勘察电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

7. [scenario_judgment][synonym] 上海市公共资源交易平台建设工程招投标分平台属于哪个系统？
   - expected: `policy_100`
   - top1: `policy_0`
   - law: `【建设工程】勘察电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

8. [scenario_judgment][synonym] 上海市公共资源交易平台包含哪些分平台？
   - expected: `policy_67`
   - top1: `policy_125`
   - law: `【国有产权】市国资委关于延长上海市产权交易场所管理实施办法(暂行)有效期的通知`
   - type: `policy_doc` | span: `single`

9. [scenario_judgment][synonym] 上海市公共资源交易平台包含哪些分平台？
   - expected: `policy_67`
   - top1: `policy_125`
   - law: `【国有产权】市国资委关于延长上海市产权交易场所管理实施办法(暂行)有效期的通知`
   - type: `policy_doc` | span: `single`

10. [scenario_judgment][synonym] 上海市公共资源交易平台包含哪些分平台？
   - expected: `policy_76`
   - top1: `policy_125`
   - law: `【拍卖服务】上海市人民政府关于延长《上海市交易场所管理暂行办法》有效期的通知`
   - type: `policy_doc` | span: `single`

11. [definition][direct] 《评标专家和评标专家库管理办法》是什么文件？
   - expected: `policy_6`
   - top1: `policy_4`
   - law: `《评标专家和评标专家库管理办法》 2024年第26号令`
   - type: `policy_doc` | span: `single`

12. [scenario_judgment][synonym] 上海市公共资源交易平台包含哪些分平台？
   - expected: `policy_5`
   - top1: `policy_125`
   - law: `上海市公共资源场内交易信用记分管理办法（试行）`
   - type: `policy_doc` | span: `single`

13. [definition][synonym] 上海市公共资源交易平台包含哪些分平台？
   - expected: `policy_103`
   - top1: `policy_125`
   - law: `【建设工程】工程总承包电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

14. [scenario_judgment][synonym] 上海市公共资源交易平台包含哪些分平台？
   - expected: `policy_101`
   - top1: `policy_125`
   - law: `【建设工程】施工电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

15. [procedure][synonym] 上海市公共资源交易中心各分平台在实施信用记分评估时，如果无法适用市交易中心的标准，应该怎么做？
   - expected: `policy_129`
   - top1: `policy_126`
   - law: `【综合采购】上海市公共资源交易中心中介机构和中介机构从业人员信用记分评估标准（试`
   - type: `policy_doc` | span: `cross_chunk`

16. [procedure][synonym] 根据《评标专家和评标专家库管理办法》，评标专家库管理的主要机制包括哪些？
   - expected: `policy_4`
   - top1: `parent_通信工程建设项目评标专家及评标专家库管理_1_902_2667`
   - law: `国家发展改革委法规司负责同志就《评标专家和评标专家库管理办法》答记者问`
   - type: `policy_doc` | span: `single`

17. [procedure][synonym] 根据《评标专家和评标专家库管理办法》，评标专家库管理的主要内容包括哪些？
   - expected: `policy_4`
   - top1: `parent_通信工程建设项目评标专家及评标专家库管理_1_902_2667`
   - law: `国家发展改革委法规司负责同志就《评标专家和评标专家库管理办法》答记者问`
   - type: `policy_doc` | span: `single`

18. [condition_check][synonym] 评标委员会的组成要求是什么？
   - expected: `policy_20`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0457`
   - law: `评标委员会和评标方法暂行规定`
   - type: `policy_doc` | span: `single`

19. [responsibility][synonym] 评标委员会的职责是什么？
   - expected: `policy_20`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0450`
   - law: `评标委员会和评标方法暂行规定`
   - type: `policy_doc` | span: `single`

20. [procedure][synonym] 上海市公共资源交易平台包含哪些分平台？
   - expected: `policy_1`
   - top1: `policy_125`
   - law: `关于印发《2023年上海市公共资源“一网交易”改革重点工作安排》的通知`
   - type: `policy_doc` | span: `single`

21. [condition_check][synonym] 工程建设项目招标投标中，哪些施工单项合同需要依法进行招标？
   - expected: `policy_68`
   - top1: `parent_工程建设项目施工招标投标办法_12_175_9134`
   - law: `关于印发《上海市公共资源交易目录（2024年版）》的通知`
   - type: `policy_doc` | span: `single`

22. [definition][direct] 上海市公共资源交易平台包含哪些分平台？
   - expected: `policy_108`
   - top1: `policy_125`
   - law: `【建设工程】电子招标投标交易平台招标人操作指南`
   - type: `policy_doc` | span: `single`

23. [definition][direct] 上海市公共资源交易平台建设工程招投标分平台属于哪个系统？
   - expected: `policy_108`
   - top1: `policy_0`
   - law: `【建设工程】电子招标投标交易平台招标人操作指南`
   - type: `policy_doc` | span: `single`

24. [comparison][synonym] 上海市公共资源交易平台建设工程招投标分平台和公共资源交易平台国有企业采购分平台有什么区别？
   - expected: `policy_108`
   - top1: `policy_45`
   - law: `【建设工程】电子招标投标交易平台招标人操作指南`
   - type: `policy_doc` | span: `single`

25. [procedure][synonym] 评标过程中发现招标文件错误应该如何处理？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0009`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0512`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

26. [condition_check][synonym] 招标人自行招标需要具备哪些条件？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0152`
   - top1: `parent_农业基本建设项目招标投标管理规定_15_1020_4436`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

27. [procedure][synonym] 招标人应当如何确定中标人？排名第一的中标候选人放弃中标时怎么办？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0596`
   - top1: `parent_经营性公路建设项目投资人招标投标管理规定_29_623_1826`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

28. [case_reasoning][synonym] 在招标投标过程中，投标人资质不符合要求会导致什么法律后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0042`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0217`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

29. [procedure][synonym] 招标投标中，投标保证金的有效期与投标有效期有何关系？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0373`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0372`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

30. [condition_check][synonym] 招标投标中，投标人应具备哪些基本条件？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0042`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0292`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

31. [definition][synonym] 招标投标中，投标保证金的作用是什么？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0373`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0360`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

32. [case_reasoning][synonym] 招标投标中，投标人资格不符合要求会导致什么法律后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0042`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0217`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

33. [procedure][synonym] 招标人可以在招标文件中要求投标人提交投标保证金吗？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0362`
   - top1: `parent_国家对潜在投标人或者投标人的资格条件有规_37_179_2747`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

34. [condition_check][synonym] 招标人在发布招标公告或者发出投标邀请时，应具备哪些基本条件？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0158`
   - top1: `parent_进一步规范机电产品国际招标投标活动有关规_13_456_1994`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

35. [responsibility][synonym] 招标代理机构有哪些权利？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0166`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0045`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

36. [procedure][direct] 投标人在投标截止时间前可以采取哪些行动？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0340`
   - top1: `parent_电子招标投标办法_27_252_372`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

37. [responsibility][synonym] 招标代理机构有哪些权利？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0166`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0045`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

38. [procedure][direct] 投标人在投标截止时间前可以采取哪些行动？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0340`
   - top1: `parent_电子招标投标办法_27_252_372`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

39. [responsibility][synonym] 招标代理机构有哪些权利？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0166`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0045`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

40. [procedure][direct] 投标人在投标截止时间前可以采取哪些行动？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0340`
   - top1: `parent_电子招标投标办法_27_252_372`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

41. [condition_check][synonym] 开标过程中如果投标人少于3个应该如何处理？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0421`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0384`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

42. [procedure][synonym] 开标过程中如果投标人对开标有异议应该如何处理？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0421`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0446`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

43. [responsibility][synonym] 在招标过程中，招标人如何确保评标委员会独立评标？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0039`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0467`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

44. [condition_check][synonym] 在评标过程中，如何处理不同投标人的投标文件异常一致的情况？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0391`
   - top1: `parent_政府采购货物和服务招标投标管理办法_35_14_920`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

45. [responsibility][synonym] 在招标过程中，招标人如何确保评标委员会独立评标？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0039`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0467`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

46. [responsibility][synonym] 在招标过程中，招标人如何确保招标具有竞争性？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0039`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0399`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

47. [procedure][synonym] 在招标过程中，如何确保招标文件发售、澄清和修改的时间符合规定？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0227`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0275`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

48. [procedure][synonym] 在招标过程中，如何确保潜在投标人足够时间准备投标文件？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0204`
   - top1: `parent_工程建设项目货物招标投标办法_28_232_2514`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

49. [procedure][synonym] 在招标过程中，如何确保潜在投标人足够时间准备投标文件？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0204`
   - top1: `parent_工程建设项目货物招标投标办法_28_232_2514`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

50. [procedure][synonym] 在招标过程中，如何确保潜在投标人足够时间准备投标文件？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0204`
   - top1: `parent_工程建设项目货物招标投标办法_28_232_2514`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

51. [condition_check][synonym] 招标文件对投标人业绩加分有什么限制？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0228`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0227`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

52. [procedure][synonym] 招标人对资格预审文件或招标文件的澄清或修改应提前多久通知投标人？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0285`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0279`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

53. [procedure][synonym] 招标人签订合同后通常还需要投标人提供什么？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0071`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0241`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

54. [procedure][synonym] 招标人对资格预审文件或招标文件的澄清或修改应提前多久通知投标人？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0285`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0279`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

55. [condition_check][synonym] 联合体投标在什么情况下会被认定为无效投标？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0359`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0543`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

56. [condition_check][synonym] 境内投标单位提交投标保证金有什么特殊要求？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0549`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0363`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

57. [definition][direct] 哪些行为属于招标投标中的串通投标行为？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0725`
   - top1: `parent_工程建设项目施工招标投标办法_47_19_206`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

58. [scenario_judgment][synonym] 哪些项目必须进行招标？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0111`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0108`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

59. [procedure][direct] 招标人应该如何处理未中标人的投标保证金？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0610`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0642`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

60. [condition_check][direct] 招标人可以随意泄露标底信息吗？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0725`
   - top1: `parent_工程建设项目施工招标投标办法_70_28_2078`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

61. [condition_check][direct] 招标人可以随意在评标委员会推荐的中标候选人以外确定中标人吗？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0725`
   - top1: `parent_经营性公路建设项目投资人招标投标管理规定_29_623_1826`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

62. [procedure][direct] 招标人可以随意拒绝退还投标保证金吗？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0610`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0377`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

63. [procedure][direct] 招标人可以随意拒绝退还投标保证金吗？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0610`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0377`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

64. [procedure][direct] 招标人可以随意拒绝退还投标保证金吗？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0610`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0377`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

65. [responsibility][synonym] 投标人拒绝签订合同的情况有哪些？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0523`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0638`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

66. [procedure][synonym] 评标委员会在什么情况下可以要求投标人澄清？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0523`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0525`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

67. [condition_check][synonym] 哪些情况下投诉不予受理？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0700`
   - top1: `parent_工程建设项目招标投标活动投诉处理办法_12_342_4132`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

68. [responsibility][synonym] 投标人如何防范因'重大偏差'导致投标被否决？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0321`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0318`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

69. [condition_check][synonym] 评标委员会在什么情况下可以否决投标？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0532`
   - top1: `parent_建筑工程设计招标投标管理办法_17_364_7404`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

70. [condition_check][synonym] 哪些情况下可以不进行施工招标？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0127`
   - top1: `parent_工程建设项目施工招标投标办法_12_5_8741`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

71. [procedure][synonym] 行政监督部门应当在收到投诉后多长时间内作出处理决定？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0710`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0705`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

72. [procedure][synonym] 行政监督部门对投诉事项可作出哪些处理决定？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0710`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0705`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

73. [procedure][synonym] 招标人应当如何处理投标文件？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0338`
   - top1: `parent_铁路建设工程招标投标实施办法_38_699_2698`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

74. [procedure][synonym] 招标人应当如何处理投标文件？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0338`
   - top1: `parent_铁路建设工程招标投标实施办法_38_699_2698`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

75. [procedure][synonym] 招标人应当如何处理投标文件？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0338`
   - top1: `parent_铁路建设工程招标投标实施办法_38_699_2698`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

76. [procedure][synonym] 招标人应当如何处理投标文件？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0338`
   - top1: `parent_铁路建设工程招标投标实施办法_38_699_2698`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

77. [procedure][synonym] 招标人应当如何处理投标文件？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0338`
   - top1: `parent_铁路建设工程招标投标实施办法_38_699_2698`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

78. [procedure][synonym] 招标人应当如何处理投标文件？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0338`
   - top1: `parent_铁路建设工程招标投标实施办法_38_699_2698`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

79. [responsibility][synonym] 招标人对投标文件签收和保存有什么要求？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0334`
   - top1: `parent_铁路建设工程招标投标实施办法_38_699_2698`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

80. [scenario_judgment][synonym] 投标人在投标过程中如何避免投标报价失误？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0316`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0322`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

81. [procedure][synonym] 投标人在投标过程中如何避免投标文件被拒收？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0316`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0332`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

82. [announcement_interpretation][synonym] 公路工程建设项目招标投标管理办法的发布时间和文号是什么？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0756`
   - top1: `parent_公路工程建设项目招标投标管理办法_1_501_4761`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

83. [condition_check][synonym] 招标文件中投标人资格条件和技术参数设置应遵循什么原则？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0388`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0253`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

84. [procedure][synonym] 评标委员会推荐中标候选人后，招标人应如何确定最终中标人？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0567`
   - top1: `parent_法定代表人为同一个人的两个及两个以上法_46_237_2463`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

85. [procedure][synonym] 投标截止时间后收到的投标文件应如何处理？为什么？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0430`
   - top1: `parent_电子招标投标办法_27_252_372`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

86. [procedure][synonym] 评标报告应包含哪些内容？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0567`
   - top1: `parent_标法》《中华人民共和国招标投标法实施条例_55_667_4483`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

87. [procedure][synonym] 招标代理服务费应如何计算和支付？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0178`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0171`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

88. [condition_check][synonym] 招标文件中投标人资格条件设置不合理会导致什么后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0388`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0380`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

89. [procedure][synonym] 招标文件对投标文件格式有哪些具体要求？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0311`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0229`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

90. [condition_check][synonym] 招标人组织现场踏勘的法律依据是什么？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0311`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0280`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

91. [condition_check][synonym] 中标通知书应由谁发出？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0593`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0606`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

92. [condition_check][synonym] 哪些情况下可以否决投标人的投标？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0621`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0534`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

93. [announcement_interpretation][synonym] 政府采购相关的法规有哪些？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0757`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0758`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

94. [condition_check][synonym] 招标投标过程中，哪些行为可能构成合同诈骗？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0750`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0731`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

95. [responsibility][synonym] 评标专家未依法评审应承担什么法律责任？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0476`
   - top1: `parent_中华人民共和国政府采购法实施条例_75_30_4724`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

96. [responsibility][synonym] 招标人代表在评标委员会中应如何履行职责？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0452`
   - top1: `parent_公路工程建设项目评标工作细则_7_529_6770`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

97. [condition_check][synonym] 评标委员会在要求投标人澄清时有哪些限制？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0527`
   - top1: `parent_公路工程建设项目评标工作细则_24_538_8292`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

98. [condition_check][synonym] 招标人设置哪些条件会被认定为以不合理条件限制或排斥潜在投标人？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0240`
   - top1: `parent_标法》《中华人民共和国招标投标法实施条例_34_657_9917`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

99. [condition_check][synonym] 招标文件中关于投标金额不一致时如何处理？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0230`
   - top1: `parent_政府采购货物和服务招标投标管理办法_59_1222_1844`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

100. [condition_check][synonym] 招标人未依法履行职责的具体表现有哪些？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0736`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0732`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

101. [responsibility][synonym] 评标委员会成员在评标过程中应遵循什么原则？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0466`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0467`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

102. [responsibility][synonym] 评标委员会成员应如何履行职责？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0466`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0467`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

103. [condition_check][synonym] 招标人未依法履行职责的具体表现有哪些？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0736`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0732`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

104. [responsibility][synonym] 评标委员会成员在评标过程中应遵循什么原则？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0466`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0467`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

105. [condition_check][synonym] 如何判断一个项目是否属于必须招标的工程建设项目？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0109`
   - top1: `parent_工程建设项目施工招标投标办法_11_4_6255`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

106. [responsibility][synonym] 招标代理的常见问题有哪些？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0005`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0268`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

107. [definition][synonym] 电子招标投标系统的三大平台是什么？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0005`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0078`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

108. [condition_check][synonym] 评标委员会在什么情况下可以否决投标？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0530`
   - top1: `parent_建筑工程设计招标投标管理办法_17_364_7404`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

109. [procedure][synonym] 评标委员会完成评标后，应当向招标人提交哪些内容？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0570`
   - top1: `parent_铁路工程建设项目招标投标管理办法_35_763_7912`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

110. [procedure][synonym] 货物招标的评标方法有哪些？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0051`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0487`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

111. [condition_check][synonym] 工程招标必须具备哪些条件？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0051`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0161`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

112. [condition_check][synonym] 哪些情况下投标会被认定为无效？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0543`
   - top1: `parent_政府采购货物和服务招标投标管理办法_63_1224_8606`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

113. [case_reasoning][synonym] 在评标过程中，哪些行为属于违法？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0572`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0732`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

114. [comparison][synonym] 在评标过程中，对细微偏差和重大偏差的处理有何不同？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0572`
   - top1: `parent_评标委员会和评标方法暂行规定_23_146_7844`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

115. [procedure][synonym] 在招标过程中，如果投标人发现招标文件不允许提交备选方案，应该如何处理以避免被否决投标的风险？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0324`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0509`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

116. [case_reasoning][synonym] 在招标过程中，如果评标委员会的组建程序违反法律规定，会导致什么后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0456`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0455`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

117. [procedure][synonym] 在招标过程中，评标专家的抽取程序有哪些具体要求？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0456`
   - top1: `parent_通信工程建设项目评标专家及评标专家库管理_10_905_6365`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

118. [case_reasoning][synonym] 在招标过程中，如果招标人未按照规定程序随机抽取评标专家，而是自行确定，会导致什么后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0456`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0452`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

119. [procedure][synonym] 在招标过程中，评标专家的抽取程序有哪些具体要求？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0456`
   - top1: `parent_通信工程建设项目评标专家及评标专家库管理_10_905_6365`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

120. [procedure][synonym] 在招标过程中，如果投标人发现招标文件不允许提交备选方案，应该如何处理以避免被否决投标的风险？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0324`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0509`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

121. [case_reasoning][synonym] 在招标过程中，如果评标委员会的组建程序违反法律规定，会导致什么后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0456`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0455`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

122. [case_reasoning][synonym] 在招标过程中，如果招标人未按照规定程序随机抽取评标专家，而是自行确定，会导致什么后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0456`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0452`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

123. [procedure][synonym] 在招标过程中，如果投标人发现招标文件不允许提交备选方案，应该如何处理以避免被否决投标的风险？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0324`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0509`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

124. [case_reasoning][synonym] 在招标过程中，如果评标委员会的组建程序违反法律规定，会导致什么后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0456`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0455`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

125. [procedure][synonym] 在招标过程中，评标专家的抽取程序有哪些具体要求？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0456`
   - top1: `parent_通信工程建设项目评标专家及评标专家库管理_10_905_6365`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

126. [case_reasoning][synonym] 在招标过程中，如果招标人未按照规定程序随机抽取评标专家，而是自行确定，会导致什么后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0456`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0452`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

127. [procedure][synonym] 在招标过程中，如果投标人发现招标文件不允许提交备选方案，应该如何处理以避免被否决投标的风险？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0324`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0509`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

128. [procedure][synonym] 在招标过程中，评标专家的抽取程序有哪些具体要求？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0456`
   - top1: `parent_通信工程建设项目评标专家及评标专家库管理_10_905_6365`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

129. [case_reasoning][synonym] 在招标过程中，如果招标人未按照规定程序随机抽取评标专家，而是自行确定，会导致什么后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0456`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0452`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

130. [condition_check][synonym] 招标文件中哪些条件属于不合理限制潜在供应商的情形？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0244`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0295`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

131. [procedure][synonym] 招标人如何处理投标人对招标文件的疑问？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0281`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0282`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

132. [responsibility][synonym] 招标人无正当理由不与中标人签订合同会有什么后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0632`
   - top1: `parent_房屋建筑和市政基础设施工程施工招标投标管_45_406_947`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

133. [procedure][synonym] 投标人如何准备投标文件以提高中标概率？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0327`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0319`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

134. [procedure][synonym] 招标文件澄清与修改的时间要求是什么？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0278`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0273`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

135. [condition_check][synonym] 招标文件中哪些内容属于实质性要求？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0327`
   - top1: `parent_工程建设项目货物招标投标办法_21_229_9962`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

136. [responsibility][synonym] 中标后，招标人能否改变中标结果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0632`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0639`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

137. [comparison][synonym] 招标文件中哪些内容属于实质性要求，哪些属于非实质性要求？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0327`
   - top1: `parent_工程建设项目货物招标投标办法_21_229_9962`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

138. [responsibility][synonym] 招标人无正当理由不与中标人签订合同会有什么后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0632`
   - top1: `parent_房屋建筑和市政基础设施工程施工招标投标管_45_406_947`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

139. [comparison][synonym] 招标文件中哪些内容属于实质性要求，哪些属于非实质性要求？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0327`
   - top1: `parent_工程建设项目货物招标投标办法_21_229_9962`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

140. [responsibility][synonym] 招标人无正当理由不与中标人签订合同会有什么后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0632`
   - top1: `parent_房屋建筑和市政基础设施工程施工招标投标管_45_406_947`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

141. [procedure][synonym] 庄某某施工队完成部分的总造价是多少？
   - expected: `pdf_建设工程施工合同纠纷案_19_1689`
   - top1: `pdf_建设工程施工合同纠纷案_7_821`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

142. [procedure][synonym] 庄某某施工队完成地下部分和地上四层以上部分的工程款分别应如何计算？
   - expected: `pdf_建设工程施工合同纠纷案_11_4184`
   - top1: `pdf_建设工程施工合同纠纷案_27_5942`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

143. [definition][synonym] 在串通投标不正当竞争纠纷案中，法院如何认定标底降幅的法律性质？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_16_4494`
   - top1: `pdf_运输服务公司串通投标不正当竞争纠纷案_7_8767`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `cross_chunk`

144. [definition][synonym] 串通投标罪的构成要件是什么？
   - expected: `pdf_非国家工作人员行贿案_5_3262`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0729`
   - law: `非国家工作人员行贿案`
   - type: `pdf_case_sliding` | span: `single`

145. [responsibility][synonym] 建设工程施工合同纠纷中，法院如何确定已完成工程部分的工程款利息？
   - expected: `pdf_建设工程施工合同纠纷案_27_5942`
   - top1: `pdf_建设工程施工合同纠纷案_29_5006`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

146. [definition][synonym] 串通投标罪的构成要件是什么？
   - expected: `pdf_非国家工作人员行贿案_4_4553`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0729`
   - law: `非国家工作人员行贿案`
   - type: `pdf_case_sliding` | span: `single`

147. [case_reasoning][synonym] 在建设工程合同纠纷中，如何认定因发包方资金问题导致的停工损失？
   - expected: `pdf_建工集团公司建设工程施工合同纠纷案_7_3630`
   - top1: `pdf_建工集团公司建设工程施工合同纠纷案_8_8439`
   - law: `建工集团公司建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

148. [definition][synonym] 标底降幅为何被认定为商业秘密？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_9_1875`
   - top1: `pdf_运输服务公司串通投标不正当竞争纠纷案_17_9444`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

149. [definition][synonym] 串通投标罪的构成要件是什么？
   - expected: `pdf_非国家工作人员行贿案_3_3318`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0729`
   - law: `非国家工作人员行贿案`
   - type: `pdf_case_sliding` | span: `single`

150. [case_reasoning][synonym] 2009年12月验收合格的工程，吉林某房地产公司最终需要支付东北某建设公司多少工程款？
   - expected: `pdf_建设工程施工合同纠纷案_13_9572`
   - top1: `pdf_建设工程施工合同纠纷案_4_3890`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

151. [case_reasoning][synonym] 在国有建设用地使用权挂牌出让过程中，竞买人通过给付补偿金的方式让其他公司放弃竞买，这种行为同时构成串通投标罪和非国家工作人员行贿罪，应如何处罚？
   - expected: `pdf_非国家工作人员行贿案_0_4758`
   - top1: `pdf_非国家工作人员行贿案_4_4553`
   - law: `非国家工作人员行贿案`
   - type: `pdf_case_sliding` | span: `cross_chunk`

152. [procedure][synonym] 庄某某借用吉林某建设公司资质进行投标后，与吉林某房地产公司签订了什么合同？
   - expected: `pdf_建设工程施工合同纠纷案_1_6506`
   - top1: `pdf_建设工程施工合同纠纷案_2_4194`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

153. [case_reasoning][synonym] 某建设公司向吉林某房地产公司主张的工程款总额是多少？利息从何时开始计算？
   - expected: `pdf_建设工程施工合同纠纷案_1_6506`
   - top1: `pdf_建设工程施工合同纠纷案_29_5006`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

154. [procedure][synonym] 某建设公司向吉林某房地产公司主张的工程款包括哪些部分？
   - expected: `pdf_建设工程施工合同纠纷案_1_6506`
   - top1: `pdf_建设工程施工合同纠纷案_20_5595`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

155. [procedure][synonym] 庄某某借用吉林某建设公司资质进行投标后，与吉林某房地产公司签订了什么合同？
   - expected: `pdf_建设工程施工合同纠纷案_1_6506`
   - top1: `pdf_建设工程施工合同纠纷案_2_4194`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

156. [case_reasoning][synonym] 本案一审和二审的法院及案号是什么？
   - expected: `pdf_建设工程施工合同纠纷案_33_9795`
   - top1: `pdf_建设工程施工合同纠纷案_34_7213`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

157. [condition_check][synonym] 投标人在投标过程中有哪些行为会导致投标无效？
   - expected: `parent_中华人民共和国道路运输条例_50_643_3802`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0740`
   - law: `中华人民共和国道路运输条例`
   - type: `pdf_law_parent` | span: `single`

158. [responsibility][synonym] 各级政府部门在招标投标活动中的职责是什么？
   - expected: `parent_明确或实际投标人报名数量未达到招标公告中_41_386_1667`
   - top1: `parent_电子招标投标办法_4_244_2005`
   - law: `明确或实际投标人报名数量未达到招标公告中规定`
   - type: `pdf_law_parent` | span: `single`

159. [condition_check][synonym] 哪些情况下招标人可以不经随机抽取方式确定专家？
   - expected: `parent_民航专业工程建设项目招标投标管理办法_36_798_4903`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0455`
   - law: `民航专业工程建设项目招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

160. [procedure][synonym] 采购代理机构在收到供应商的询问或质疑后应当如何处理？
   - expected: `parent_中华人民共和国政府采购法_51_1077_8459`
   - top1: `parent_政府采购质疑和投诉办法_16_1240_1316`
   - law: `中华人民共和国政府采购法`
   - type: `pdf_law_parent` | span: `single`

161. [procedure][synonym] 政府采购活动中采购人有哪些禁止行为？
   - expected: `parent_中华人民共和国政府采购法实施条例_11_1093_1402`
   - top1: `parent_政府采购货物和服务招标投标管理办法_4_1201_9622`
   - law: `中华人民共和国政府采购法实施条例`
   - type: `pdf_law_parent` | span: `single`

162. [procedure][synonym] 联合体投标有哪些规定，资格预审后联合体增减、更换成员会有什么后果？
   - expected: `parent_民航专业工程建设项目招标投标管理办法_28_795_7248`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0356`
   - law: `民航专业工程建设项目招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

163. [condition_check][synonym] 评审专家库的专家需要满足哪些条件？
   - expected: `parent_道路旅客运输班线经营权招标投标办法_30_638_3963`
   - top1: `parent_评标专家和评标专家库管理暂行办法_5_159_6981`
   - law: `道路旅客运输班线经营权招标投标办法`
   - type: `pdf_law_parent` | span: `single`

164. [procedure][synonym] 评标委员会的组成有哪些要求？
   - expected: `parent_道路旅客运输班线经营权招标投标办法_30_638_3963`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0457`
   - law: `道路旅客运输班线经营权招标投标办法`
   - type: `pdf_law_parent` | span: `single`

165. [procedure][synonym] 招标人应如何对待资格预审合格的潜在投标人？
   - expected: `parent_工程建设项目勘察设计招标投标办法_12_205_3641`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0222`
   - law: `工程建设项目勘察设计招标投标办法`
   - type: `pdf_law_parent` | span: `single`

166. [condition_check][synonym] 招标文件的收费有什么限制？
   - expected: `parent_工程建设项目勘察设计招标投标办法_12_205_3641`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0271`
   - law: `工程建设项目勘察设计招标投标办法`
   - type: `pdf_law_parent` | span: `single`

167. [responsibility][synonym] 采购当事人有哪些行为会被依法追究责任？
   - expected: `parent_国有金融企业集中采购管理暂行规定_29_1394_2601`
   - top1: `parent_政府采购货物和服务招标投标管理办法_71_1232_1756`
   - law: `国有金融企业集中采购管理暂行规定`
   - type: `pdf_law_parent` | span: `single`

168. [procedure][synonym] 资格预审公告应当包含哪些内容？
   - expected: `parent_中华人民共和国政府采购法实施条例_21_10_6131`
   - top1: `parent_政府采购货物和服务招标投标管理办法_15_1205_7147`
   - law: `中华人民共和国政府采购法实施条例`
   - type: `pdf_law_parent` | span: `single`

169. [procedure][synonym] 招标人应当在招标文件中如何规定实质性要求和条件？
   - expected: `parent_工程建设项目施工招标投标办法_23_10_4291`
   - top1: `parent_工程建设项目货物招标投标办法_21_229_9962`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `single`

170. [condition_check][synonym] 哪些情况下投标人不得参加同一招标项目包投标？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_32_463_2329`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0304`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `single`

171. [procedure][synonym] 招标人可以对潜在投标人进行资格审查吗？
   - expected: `parent_工程建设项目货物招标投标办法_15_227_3433`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0214`
   - law: `工程建设项目货物招标投标办法`
   - type: `pdf_law_parent` | span: `single`

172. [condition_check][synonym] 政府采购货物和服务的招标投标应遵循什么规定
   - expected: `parent_中华人民共和国招标投标法实施条例_82_57_7179`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0028`
   - law: `中华人民共和国招标投标法实施条例`
   - type: `pdf_law_parent` | span: `single`

173. [condition_check][direct] 招标人设有标底时，在评标中如何使用？
   - expected: `parent_工程建设项目施工招标投标办法_54_22_3648`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0516`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `single`

174. [condition_check][direct] 供应商在采购活动中禁止什么行为？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_14_1352_5266`
   - top1: `parent_中华人民共和国政府采购法实施条例_19_9_2895`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

175. [procedure][synonym] 依法必须进行招标的项目，招标人收到评标报告后何时公示中标候选人？
   - expected: `parent_工程建设项目施工招标投标办法_54_22_3648`
   - top1: `parent_中华人民共和国招标投标法实施条例_54_44_2074`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `single`

176. [condition_check][direct] 评标委员会推荐的中标候选人应当限定在多少人？
   - expected: `parent_工程建设项目施工招标投标办法_54_22_3648`
   - top1: `parent_评标委员会和评标方法暂行规定_44_152_8491`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `single`

177. [responsibility][scenario] 评标委员会成员有哪些行为会被禁止参加评标？
   - expected: `parent_工程建设项目施工招标投标办法_76_31_7419`
   - top1: `parent_评标委员会和评标方法暂行规定_53_154_1711`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `single`

178. [condition_check][synonym] 在什么情况下，招标人可以终止招标？
   - expected: `parent_工程建设项目施工招标投标办法_14_176_6158`
   - top1: `parent_工程建设项目勘察设计招标投标办法_20_207_2444`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `single`

179. [condition_check][synonym] 重新评标专家不得包含哪些人员？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_31_435_8601`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0462`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `single`

180. [procedure][synonym] 投诉人投诉时应当提供哪些材料？
   - expected: `parent_机电产品国际招标评标专家及专家库管理办法_83_476_400`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0698`
   - law: `机电产品国际招标评标专家及专家库管理办法`
   - type: `pdf_law_parent` | span: `single`

181. [responsibility][synonym] 评标委员会成员在评标过程中不得有哪些行为？
   - expected: `parent_铁路工程建设项目招标投标管理办法_32_762_9770`
   - top1: `parent_政府采购货物和服务招标投标管理办法_61_24_4000`
   - law: `铁路工程建设项目招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

182. [condition_check][synonym] 评标委员会在什么情况下可以否决所有投标？
   - expected: `parent_中华人民共和国招标投标法_32_11_8897`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0561`
   - law: `中华人民共和国招标投标法`
   - type: `pdf_law_parent` | span: `cross_chunk`

183. [procedure][synonym] 评标委员会在评标过程中可以要求投标人进行哪些澄清说明？
   - expected: `parent_铁路工程建设项目招标投标管理办法_32_762_9770`
   - top1: `parent_公路工程建设项目评标工作细则_24_538_8292`
   - law: `铁路工程建设项目招标投标管理办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

184. [condition_check][synonym] 招标人对投标人的资格条件有哪些要求？
   - expected: `parent_房屋建筑和市政基础设施工程施工招标投标管_22_397_9260`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0218`
   - law: `房屋建筑和市政基础设施工程施工招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

185. [condition_check][direct] 投标保证金的有效期应当与什么一致？
   - expected: `parent_中华人民共和国招标投标法实施条例_25_33_6740`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0372`
   - law: `中华人民共和国招标投标法实施条例`
   - type: `pdf_law_parent` | span: `single`

186. [condition_check][synonym] 关于标底的规定有哪些？
   - expected: `parent_中华人民共和国招标投标法实施条例_25_33_6740`
   - top1: `parent_铁路建设工程招标投标实施办法_43_702_7498`
   - law: `中华人民共和国招标投标法实施条例`
   - type: `pdf_law_parent` | span: `single`

187. [condition_check][synonym] 哪些投标行为是被法律明确禁止的？
   - expected: `parent_标法》《中华人民共和国招标投标法实施条例_41_661_440`
   - top1: `parent_中华人民共和国招标投标法_32_11_8897`
   - law: `标法》《中华人民共和国招标投标法实施条例》等法`
   - type: `pdf_law_parent` | span: `single`

188. [condition_check][synonym] 招标人自行办理招标事宜需要具备什么条件？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_11_455_8051`
   - top1: `parent_房屋建筑和市政基础设施工程施工招标投标管_11_392_9716`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `single`

189. [procedure][synonym] 评标委员会推荐的中标候选人人数限制是多少？
   - expected: `parent_国家对潜在投标人或者投标人的资格条件有规_54_185_9797`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0570`
   - law: `国家对潜在投标人或者投标人的资格条件有规定`
   - type: `pdf_law_parent` | span: `single`

190. [condition_check][synonym] 招标人设有标底时，标底在评标中应如何使用？
   - expected: `parent_国家对潜在投标人或者投标人的资格条件有规_54_185_9797`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0516`
   - law: `国家对潜在投标人或者投标人的资格条件有规定`
   - type: `pdf_law_parent` | span: `single`

191. [procedure][synonym] 评标报告应当包含哪些内容？
   - expected: `parent_政府采购货物和服务招标投标管理办法_56_22_3619`
   - top1: `parent_通信工程建设项目招标投标管理办法_36_895_5437`
   - law: `政府采购货物和服务招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

192. [procedure][synonym] 评标完成后，评标委员会应当向招标人提交什么内容？
   - expected: `parent_通信工程建设项目招标投标管理办法_34_894_8314`
   - top1: `parent_铁路工程建设项目招标投标管理办法_35_763_7912`
   - law: `通信工程建设项目招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

193. [procedure][synonym] 招标文件应当包括哪些内容？
   - expected: `parent_房屋建筑和市政基础设施工程施工招标投标管_16_394_602`
   - top1: `parent_水利工程建设项目监理招标投标管理办法_19_836_2124`
   - law: `房屋建筑和市政基础设施工程施工招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

194. [responsibility][synonym] 采购人未在规定时间内确定中标人会有什么后果？
   - expected: `parent_政府采购货物和服务招标投标管理办法_77_1230_9691`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0602`
   - law: `政府采购货物和服务招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

195. [procedure][direct] 招标人收到投标文件后应当如何处理？
   - expected: `parent_工程建设项目施工招标投标办法_37_16_391`
   - top1: `parent_铁路建设工程招标投标实施办法_38_699_2698`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `single`

196. [condition_check][direct] 招标人应当根据什么编制招标文件？
   - expected: `parent_房屋建筑和市政基础设施工程施工招标投标管_16_394_602`
   - top1: `parent_中华人民共和国招标投标法_19_7_8052`
   - law: `房屋建筑和市政基础设施工程施工招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

197. [condition_check][direct] 招标人可以在招标文件中要求投标人提交什么？
   - expected: `parent_工程建设项目施工招标投标办法_37_16_391`
   - top1: `parent_国家对潜在投标人或者投标人的资格条件有规_37_179_2747`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `single`

198. [procedure][direct] 招标人应当如何编制招标文件？
   - expected: `parent_房屋建筑和市政基础设施工程施工招标投标管_16_394_602`
   - top1: `parent_中华人民共和国招标投标法_19_7_8052`
   - law: `房屋建筑和市政基础设施工程施工招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

199. [condition_check][direct] 招标人应当根据什么编制招标文件？
   - expected: `parent_房屋建筑和市政基础设施工程施工招标投标管_16_394_602`
   - top1: `parent_中华人民共和国招标投标法_19_7_8052`
   - law: `房屋建筑和市政基础设施工程施工招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

200. [condition_check][direct] 招标人可以在招标文件中要求投标人提交什么？
   - expected: `parent_工程建设项目施工招标投标办法_37_16_391`
   - top1: `parent_国家对潜在投标人或者投标人的资格条件有规_37_179_2747`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `single`

201. [procedure][direct] 招标人应当如何编制招标文件？
   - expected: `parent_房屋建筑和市政基础设施工程施工招标投标管_16_394_602`
   - top1: `parent_中华人民共和国招标投标法_19_7_8052`
   - law: `房屋建筑和市政基础设施工程施工招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

202. [procedure][synonym] 评标委员会对投标文件进行初步评审的目的是什么？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_15_445_6061`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0450`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `single`

203. [responsibility][synonym] 评标委员会成员在评分过程中应当遵循什么原则？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_15_445_6061`
   - top1: `parent_进一步规范机电产品国际招标投标活动有关规_12_443_181`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `single`

204. [condition_check][synonym] 评标专家有哪些情形需要主动回避？
   - expected: `parent_通信工程建设项目评标专家及评标专家库管理_11_906_9474`
   - top1: `parent_评标专家和评标专家库管理暂行办法_37_162_3496`
   - law: `通信工程建设项目评标专家及评标专家库管理办法`
   - type: `pdf_law_parent` | span: `single`

205. [procedure][synonym] 招标公告应当载明哪些内容？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_13_456_1994`
   - top1: `parent_招标公告和公示信息发布管理办法_5_267_7639`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `single`

206. [responsibility][synonym] 评标委员会成员有违反规定行为时，应如何处理？
   - expected: `parent_政府采购货物和服务招标投标管理办法_71_1232_1756`
   - top1: `parent_建筑工程设计招标投标管理办法_34_369_5661`
   - law: `政府采购货物和服务招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

207. [procedure][synonym] 投标人认为招标投标活动不符合规定时，应该如何投诉？
   - expected: `parent_工程建设项目施工招标投标办法_88_36_631`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0685`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `single`

208. [condition_check][synonym] 联合体投标在资格预审后增减、更换成员会有什么后果？
   - expected: `parent_工程建设项目施工招标投标办法_43_18_5397`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0356`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `single`

209. [condition_check][synonym] 评标或评审时，专家应如何确定？
   - expected: `parent_公共资源交易平台公共资源交易平台管理暂行_47_1472_7867_child9`
   - top1: `parent_公路建设项目评标专家库管理办法_11_578_8402`
   - law: `公共资源交易平台公共资源交易平台管理暂行办法`
   - type: `pdf_law_child` | span: `single`

210. [procedure][synonym] 电子招标投标需要遵循哪些规定
   - expected: `parent_铁路工程建设项目招标投标管理办法_59_775_2092_child0`
   - top1: `parent_电子招标投标办法_5_245_2944`
   - law: `铁路工程建设项目招标投标管理办法`
   - type: `pdf_law_child` | span: `single`

211. [condition_check][direct] 招标文件对备选方案有什么要求
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_20_458_676_child4`
   - top1: `parent_进一步规范机电产品国际招标投标活动有关规_4_425_361`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_child` | span: `single`

212. [scenario_judgment][synonym] 整合建立统一的公共资源交易平台有什么重要性？
   - expected: `parent_公共资源交易平台公共资源交易平台管理暂行_47_1472_7867_child1`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_47_1472_7867_child16`
   - law: `公共资源交易平台公共资源交易平台管理暂行办法`
   - type: `pdf_law_child` | span: `single`

213. [condition_check][synonym] 公共资源交易平台整合前存在哪些突出问题？
   - expected: `parent_公共资源交易平台公共资源交易平台管理暂行_47_1472_7867_child1`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_47_1472_7867_child16`
   - law: `公共资源交易平台公共资源交易平台管理暂行办法`
   - type: `pdf_law_child` | span: `single`

214. [procedure][synonym] 招标代理机构不得有哪些违规行为？
   - expected: `parent_机电产品国际招标评标专家及专家库管理办法_99_484_5044_child5`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0180`
   - law: `机电产品国际招标评标专家及专家库管理办法`
   - type: `pdf_law_child` | span: `single`

215. [responsibility][synonym] 哪些机关使用财政性资金购买服务时需要参照政府购买服务管理办法执行？
   - expected: `parent_政府购买服务管理办法_33_1568_1497_child0`
   - top1: `parent_政府购买服务管理办法_33_1568_1497_child6`
   - law: `政府购买服务管理办法`
   - type: `pdf_law_child` | span: `single`

216. [procedure][synonym] 政府采购资格预审公告中应包含哪些主要内容？
   - expected: `parent_《中华人民共和国政府采购法实施条例》等有_22_1573_8167_child0`
   - top1: `parent_政府采购货物和服务招标投标管理办法_15_6_7294`
   - law: `《中华人民共和国政府采购法实施条例》等有关法`
   - type: `pdf_law_child` | span: `single`

217. [procedure][synonym] 资格预审评审委员会如何处理投标人的资格预审？
   - expected: `parent_民政部工程建设项目招标投标管理办法_7_1045_547_child2`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0206`
   - law: `民政部工程建设项目招标投标管理办法`
   - type: `pdf_law_child` | span: `single`

218. [scenario_judgment][synonym] 铁路工程建设项目招标投标的基本原则是什么？
   - expected: `parent_铁路工程建设项目招标投标管理办法_59_775_2092_child2`
   - top1: `parent_铁路建设工程招标投标实施办法_4_684_4947`
   - law: `铁路工程建设项目招标投标管理办法`
   - type: `pdf_law_child` | span: `single`

219. [definition][synonym] 最低评标价法的定义是什么？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_20_458_676_child0`
   - top1: `parent_政府采购货物和服务招标投标管理办法_52_21_6029`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_child` | span: `single`

220. [procedure][synonym] 机电产品国际招标的评标方法有哪些？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_20_458_676_child0`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0481`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_child` | span: `single`

221. [responsibility][synonym] 评标委员会成员不按照招标文件规定的评标方法和标准评标会有什么处罚？
   - expected: `parent_机电产品国际招标评标专家及专家库管理办法_99_484_5044_child2`
   - top1: `parent_评标委员会和评标方法暂行规定_53_154_1711`
   - law: `机电产品国际招标评标专家及专家库管理办法`
   - type: `pdf_law_child` | span: `single`

222. [procedure][synonym] 单一来源采购的公示内容应包括哪些信息？
   - expected: `parent_财政部关于做好政府采购信息公开工作的通知_31_1574_8412_child0`
   - top1: `parent_政府采购非招标采购方式管理办法_38_1510_7264`
   - law: `财政部关于做好政府采购信息公开工作的通知`
   - type: `pdf_law_child` | span: `single`

223. [responsibility][synonym] 评标委员会成员向招标人征询确定中标人意向会受到什么处罚？
   - expected: `parent_机电产品国际招标评标专家及专家库管理办法_99_484_5044_child2`
   - top1: `parent_评标委员会和评标方法暂行规定_53_154_1711`
   - law: `机电产品国际招标评标专家及专家库管理办法`
   - type: `pdf_law_child` | span: `single`

224. [scenario_judgment][synonym] 铁路工程项目进入地方公共资源交易市场招投标的重要意义是什么？
   - expected: `parent_铁路工程建设项目招标投标管理办法_59_775_2092_child1`
   - top1: `parent_铁路工程建设项目招标投标管理办法_59_775_2092_child3`
   - law: `铁路工程建设项目招标投标管理办法`
   - type: `pdf_law_child` | span: `single`

225. [comparison][synonym] 哪些公告涉及了医疗或教育领域的采购项目？
   - expected: `opinion_301`
   - top1: `opinion_1194`
   - law: `北京大学第一医院2025年医疗设备更新项目眼科眼底成像系统中标公告`
   - type: `opinion_news` | span: `cross_chunk`

226. [definition][direct] 上海公共资源交易平台包含哪些分平台？
   - expected: `policy_111`
   - top1: `policy_125`
   - law: `【建设工程】监理电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

227. [definition][direct] 上海公共资源交易平台建设工程招投标分平台属于哪个交易平台的一部分？
   - expected: `policy_111`
   - top1: `policy_45`
   - law: `【建设工程】监理电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

228. [comparison][synonym] 上海市公共资源交易平台建设工程招投标分平台与农村土地经营权流转管理办法有什么关系？
   - expected: `policy_23`
   - top1: `policy_80`
   - law: `农村土地经营权流转管理办法`
   - type: `policy_doc` | span: `single`

229. [comparison][synonym] 上海市公共资源交易平台建设工程招投标分平台与上海市公共资源交易平台管理暂行办法有什么关系？
   - expected: `policy_111`
   - top1: `policy_45`
   - law: `【建设工程】监理电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

230. [comparison][synonym] 上海市公共资源交易平台建设工程招投标分平台与上海市深化公共资源"一网交易"改革三年行动方案有什么关系？
   - expected: `policy_74`
   - top1: `policy_0`
   - law: `【综合管理】上海市深化公共资源“一网交易”改革 三年行动方案（2024-2026`
   - type: `policy_doc` | span: `single`

231. [comparison][synonym] 上海市公共资源交易平台建设工程招投标分平台与农村土地经营权流转管理办法有什么共同点？
   - expected: `policy_111`
   - top1: `policy_80`
   - law: `【建设工程】监理电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

232. [comparison][synonym] 上海市公共资源交易平台建设工程招投标分平台与北京市民营经济促进条例有什么共同点？
   - expected: `policy_211`
   - top1: `policy_13`
   - law: `北京拟立法护航民企参与政府采购`
   - type: `policy_doc` | span: `single`

233. [comparison][synonym] 上海市公共资源交易平台建设工程招投标分平台与农村土地经营权流转管理办法有什么不同点？
   - expected: `policy_23`
   - top1: `policy_84`
   - law: `农村土地经营权流转管理办法`
   - type: `policy_doc` | span: `single`

234. [comparison][synonym] 上海市公共资源交易平台建设工程招投标分平台与北京市民营经济促进条例有什么不同点？
   - expected: `policy_211`
   - top1: `policy_125`
   - law: `北京拟立法护航民企参与政府采购`
   - type: `policy_doc` | span: `single`

235. [comparison][synonym] 上海市公共资源交易平台建设工程招投标分平台与上海市公共资源交易平台管理暂行办法有什么不同点？
   - expected: `policy_111`
   - top1: `policy_19`
   - law: `【建设工程】监理电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

236. [comparison][synonym] 上海市公共资源交易平台建设工程招投标分平台与农村土地经营权流转管理办法有什么联系？
   - expected: `policy_23`
   - top1: `policy_80`
   - law: `农村土地经营权流转管理办法`
   - type: `policy_doc` | span: `single`

237. [comparison][synonym] 上海市公共资源交易平台建设工程招投标分平台与北京市民营经济促进条例有什么联系？
   - expected: `policy_211`
   - top1: `policy_0`
   - law: `北京拟立法护航民企参与政府采购`
   - type: `policy_doc` | span: `single`

238. [comparison][synonym] 上海市公共资源交易平台建设工程招投标分平台与上海市深化公共资源"一网交易"改革三年行动方案有什么联系？
   - expected: `policy_74`
   - top1: `policy_0`
   - law: `【综合管理】上海市深化公共资源“一网交易”改革 三年行动方案（2024-2026`
   - type: `policy_doc` | span: `single`

239. [comparison][synonym] 上海市公共资源交易平台建设工程招投标分平台与上海市公共资源交易平台管理暂行办法有什么联系？
   - expected: `policy_111`
   - top1: `policy_45`
   - law: `【建设工程】监理电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

240. [comparison][synonym] 上海市公共资源交易平台建设工程招投标分平台与农村土地经营权流转管理办法有什么区别？
   - expected: `policy_23`
   - top1: `policy_0`
   - law: `农村土地经营权流转管理办法`
   - type: `policy_doc` | span: `single`

241. [comparison][synonym] 上海市公共资源交易平台建设工程招投标分平台与北京市民营经济促进条例有什么区别？
   - expected: `policy_211`
   - top1: `policy_125`
   - law: `北京拟立法护航民企参与政府采购`
   - type: `policy_doc` | span: `single`

242. [comparison][synonym] 上海市公共资源交易平台建设工程招投标分平台与上海市公共资源交易平台管理暂行办法有什么区别？
   - expected: `policy_111`
   - top1: `policy_45`
   - law: `【建设工程】监理电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

243. [comparison][synonym] 上海市公共资源交易平台建设工程招投标分平台与农村土地经营权流转管理办法有什么异同？
   - expected: `policy_23`
   - top1: `policy_27`
   - law: `农村土地经营权流转管理办法`
   - type: `policy_doc` | span: `single`

244. [comparison][synonym] 上海市公共资源交易平台建设工程招投标分平台与北京市民营经济促进条例有什么异同？
   - expected: `policy_211`
   - top1: `policy_13`
   - law: `北京拟立法护航民企参与政府采购`
   - type: `policy_doc` | span: `single`

245. [comparison][synonym] 上海市公共资源交易平台建设工程招投标分平台与上海市深化公共资源"一网交易"改革三年行动方案有什么异同？
   - expected: `policy_74`
   - top1: `policy_0`
   - law: `【综合管理】上海市深化公共资源“一网交易”改革 三年行动方案（2024-2026`
   - type: `policy_doc` | span: `single`

246. [comparison][synonym] 上海市公共资源交易平台建设工程招投标分平台与上海市公共资源交易平台管理暂行办法有什么异同？
   - expected: `policy_111`
   - top1: `policy_45`
   - law: `【建设工程】监理电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

247. [comparison][synonym] 上海市公共资源交易平台建设工程招投标分平台与农村土地经营权流转管理办法有什么关系和区别？
   - expected: `policy_23`
   - top1: `policy_84`
   - law: `农村土地经营权流转管理办法`
   - type: `policy_doc` | span: `single`

248. [comparison][synonym] 上海市公共资源交易平台建设工程招投标分平台与北京市民营经济促进条例有什么关系和区别？
   - expected: `policy_211`
   - top1: `policy_27`
   - law: `北京拟立法护航民企参与政府采购`
   - type: `policy_doc` | span: `single`

249. [comparison][synonym] 上海市公共资源交易平台建设工程招投标分平台与上海市公共资源交易平台管理暂行办法有什么关系和区别？
   - expected: `policy_111`
   - top1: `policy_45`
   - law: `【建设工程】监理电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

250. [comparison][synonym] 上海市公共资源交易平台建设工程招投标分平台与农村土地经营权流转管理办法有什么联系和差异？
   - expected: `policy_23`
   - top1: `policy_0`
   - law: `农村土地经营权流转管理办法`
   - type: `policy_doc` | span: `single`

251. [comparison][synonym] 上海市公共资源交易平台建设工程招投标分平台与北京市民营经济促进条例有什么联系和差异？
   - expected: `policy_211`
   - top1: `policy_85`
   - law: `北京拟立法护航民企参与政府采购`
   - type: `policy_doc` | span: `single`

252. [comparison][synonym] 上海市公共资源交易平台建设工程招投标分平台与上海市深化公共资源"一网交易"改革三年行动方案有什么联系和差异？
   - expected: `policy_74`
   - top1: `policy_0`
   - law: `【综合管理】上海市深化公共资源“一网交易”改革 三年行动方案（2024-2026`
   - type: `policy_doc` | span: `single`

253. [procedure][synonym] 本案经历了哪些审级程序？
   - expected: `pdf_建设工程施工合同纠纷案_34_7213`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0559`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

254. [comparison][synonym] 电子招标投标公共服务平台与纸质文件的关系如何？当两者不一致时如何处理？技术规范在电子招标投标中的法律地位是什么？
   - expected: `parent_电子招标投标办法_43_257_4773`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0078`
   - law: `电子招标投标办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

255. [procedure][synonym] 招标文件补充说明的修改时限是什么？违反招标规定的行为有哪些？
   - expected: `parent_公路养护工程施工招标投标管理暂行规定_19_564_3661`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0275`
   - law: `公路养护工程施工招标投标管理暂行规定`
   - type: `pdf_law_parent` | span: `cross_chunk`

256. [procedure][synonym] 采购活动结束后，采购人需要完成哪些后续工作？同时，哪些类型的政府采购项目可以采用询价方式采购？
   - expected: `parent_交通运输部部属单位政府采购管理办法_44_1412_4260`
   - top1: `parent_中华人民共和国政府采购法_32_1070_7465`
   - law: `交通运输部部属单位政府采购管理办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

257. [procedure][synonym] 招标公告应当载明哪些内容？招标网在招标过程中有哪些信息发布要求？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_31_435_8601`
   - top1: `parent_招标公告和公示信息发布管理办法_5_267_7639`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `cross_chunk`

258. [condition_check][synonym] 招标人自行办理招标事宜需要具备哪些条件？同时，评标委员会在评标过程中应当遵循哪些步骤？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_11_455_8051`
   - top1: `parent_铁路建设工程招标投标实施办法_14_687_3428`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `cross_chunk`

259. [procedure][synonym] 招标机构在评标过程中应当如何处理投标文件，以及招标公告应当包含哪些内容？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_15_445_6061`
   - top1: `parent_标法》《中华人民共和国招标投标法实施条例_55_667_4483`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `cross_chunk`

260. [procedure][synonym] 评标委员会如何处理投标文件，以及招标文件对重要条款有什么特殊要求？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_15_445_6061`
   - top1: `parent_农业基本建设项目招标投标管理规定_39_1028_7333`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `cross_chunk`

261. [procedure][synonym] 评标委员会如何对投标文件进行评分，以及招标文件对备选方案有什么规定？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_15_445_6061`
   - top1: `parent_进一步规范机电产品国际招标投标活动有关规_15_429_5111`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `cross_chunk`

262. [procedure][synonym] 招标公告应当载明哪些内容？招标文件对内容有哪些要求？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_13_456_1994`
   - top1: `parent_投资项目招标投标管理办法_11_916_305`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `cross_chunk`

263. [procedure][synonym] 招标公告中应当包含哪些基本信息？招标文件中对重要条款有什么特殊要求？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_13_456_1994`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0229`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `cross_chunk`

264. [procedure][synonym] 招标公告中需要包含哪些基本信息？机电产品国际招标的评标方法有哪些规定？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_13_456_1994`
   - top1: `parent_进一步规范机电产品国际招标投标活动有关规_20_458_676_child4`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `cross_chunk`

265. [procedure][synonym] 投标人在投标截止时间前可以如何处理已提交的投标文件？如果招标文件允许提供备选方案，有什么具体规定？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_38_465_1367`
   - top1: `parent_工程建设项目施工招标投标办法_39_17_9795`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `cross_chunk`

266. [condition_check][synonym] 招标文件中关于评标方法和标准的规定有哪些具体要求？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_20_458_676_child3`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0488`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_child` | span: `cross_chunk`

267. [procedure][synonym] 资格预审公告应当包括哪些内容，以及中标、成交结果公告应当包括哪些内容？
   - expected: `parent_中华人民共和国政府采购法实施条例_21_10_6131`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0182`
   - law: `中华人民共和国政府采购法实施条例`
   - type: `pdf_law_parent` | span: `cross_chunk`

268. [responsibility][synonym] 采购代理机构向评标委员会作倾向性说明会有什么后果？同时，未依法从政府采购评审专家库中抽取专家又会面临什么处罚？
   - expected: `parent_中华人民共和国政府采购法实施条例_42_17_1441`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0469`
   - law: `中华人民共和国政府采购法实施条例`
   - type: `pdf_law_parent` | span: `cross_chunk`

269. [procedure][synonym] 公共资源交易平台应遵循哪些法律法规和规则，以及如何整合各类交易市场？
   - expected: `parent_公共资源交易平台公共资源交易平台管理暂行_7_1457_6263`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_47_1472_7867_child10`
   - law: `公共资源交易平台公共资源交易平台管理暂行办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

270. [scenario_judgment][synonym] 公共资源交易平台整合的背景和必要性是什么，以及平台运行应遵循哪些规则？
   - expected: `parent_公共资源交易平台公共资源交易平台管理暂行_7_1457_6263`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_47_1472_7867_child8`
   - law: `公共资源交易平台公共资源交易平台管理暂行办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

271. [scenario_judgment][synonym] 整合建立统一的公共资源交易平台的重要性和具体措施是什么？
   - expected: `parent_公共资源交易平台公共资源交易平台管理暂行_47_1472_7867_child10`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_47_1472_7867_child16`
   - law: `公共资源交易平台公共资源交易平台管理暂行办法`
   - type: `pdf_law_child` | span: `cross_chunk`

272. [scenario_judgment][synonym] 整合建立统一的公共资源交易平台的重要性和背景是什么？
   - expected: `parent_公共资源交易平台公共资源交易平台管理暂行_47_1472_7867_child9`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_47_1472_7867_child16`
   - law: `公共资源交易平台公共资源交易平台管理暂行办法`
   - type: `pdf_law_child` | span: `cross_chunk`

273. [procedure][synonym] 评标委员会如何编写评标报告并确定中标候选人？如果采购人未在规定时间内确定中标人，会有什么后果？
   - expected: `parent_政府采购货物和服务招标投标管理办法_56_22_3619`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0567`
   - law: `政府采购货物和服务招标投标管理办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

274. [procedure][synonym] 评标报告应当包含哪些内容？如果评标委员会成员对评标报告有不同意见应该如何处理？
   - expected: `parent_政府采购货物和服务招标投标管理办法_56_22_3619`
   - top1: `parent_铁路工程建设项目招标投标管理办法_35_763_7912`
   - law: `政府采购货物和服务招标投标管理办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

275. [responsibility][synonym] 评标委员会成员违反评标纪律会有什么后果？采购人在评标过程中未在规定时间内确定中标人将面临什么处罚？
   - expected: `parent_政府采购货物和服务招标投标管理办法_77_1230_9691`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0743`
   - law: `政府采购货物和服务招标投标管理办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

276. [responsibility][synonym] 采购人违反政府采购招标投标管理办法会有什么处罚？评标委员会成员在评标过程中擅离职守会有什么后果？
   - expected: `parent_政府采购货物和服务招标投标管理办法_77_1230_9691`
   - top1: `parent_政府采购货物和服务招标投标管理办法_71_33_9354`
   - law: `政府采购货物和服务招标投标管理办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

277. [responsibility][synonym] 评标委员会成员在评标过程中擅离职守，且私下接触投标人，应承担什么责任？
   - expected: `parent_政府采购货物和服务招标投标管理办法_39_16_643`
   - top1: `parent_工程建设项目施工招标投标办法_76_31_7419`
   - law: `政府采购货物和服务招标投标管理办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

278. [procedure][synonym] 开标过程中发现评标委员会成员有需要回避的情形，应如何处理？
   - expected: `parent_政府采购货物和服务招标投标管理办法_39_16_643`
   - top1: `parent_公路工程建设项目评标工作细则_33_535_3041`
   - law: `政府采购货物和服务招标投标管理办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

279. [responsibility][synonym] 评标委员会成员私下接触投标人并接受与投标文件不一致的澄清，应承担什么责任？
   - expected: `parent_政府采购货物和服务招标投标管理办法_61_1223_5706`
   - top1: `parent_工程建设项目施工招标投标办法_76_31_7419`
   - law: `政府采购货物和服务招标投标管理办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

280. [announcement_interpretation][direct] 水利工程建设项目招标投标审计办法的执行时间和解释权归属是什么？
   - expected: `parent_水利工程建设项目招标投标审计办法_7_874_8025`
   - top1: `parent_水利工程建设项目招标投标审计办法_20_880_2122_child0`
   - law: `水利工程建设项目招标投标审计办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

281. [procedure][synonym] 水利工程建设项目招标投标审计办法中关于招标投标行为规范的具体要求
   - expected: `parent_水利工程建设项目招标投标审计办法_20_880_2122_child6`
   - top1: `parent_水利工程建设项目招标投标审计办法_7_874_8025`
   - law: `水利工程建设项目招标投标审计办法`
   - type: `pdf_law_child` | span: `cross_chunk`

282. [procedure][synonym] 水利工程建设项目招标投标审计办法中关于招标投标方面的审计重点
   - expected: `parent_水利工程建设项目招标投标审计办法_20_880_2122_child0`
   - top1: `parent_水利工程建设项目招标投标审计办法_7_874_8025`
   - law: `水利工程建设项目招标投标审计办法`
   - type: `pdf_law_child` | span: `cross_chunk`

283. [procedure][synonym] 评标过程中，评标委员会发现投标人以他人的名义投标、串通投标、以行贿手段谋取中标或者以其他弄虚作假方式投标的，应当如何处理？如果投标人的报价明显低于其他投标报价或者在设有标底时明显低于标底，使得其投标报
   - expected: `parent_监督处理中华人民共和国行政处罚法_25_289_464`
   - top1: `parent_评标委员会和评标方法暂行规定_20_144_777`
   - law: `监督处理中华人民共和国行政处罚法`
   - type: `pdf_law_parent` | span: `cross_chunk`

284. [responsibility][synonym] 承接主体在政府购买服务项目实施过程中应当履行哪些义务，以及事业单位政府购买服务改革的总体目标是什么？
   - expected: `parent_政府购买服务管理办法_26_1566_4159`
   - top1: `parent_政府购买服务管理办法_33_1568_1497_child6`
   - law: `政府购买服务管理办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

285. [condition_check][synonym] 哪些事业单位可以作为政府购买服务的购买主体，承接主体在提供服务时有什么限制？
   - expected: `parent_政府购买服务管理办法_26_1566_4159`
   - top1: `parent_政府购买服务管理办法_5_1560_5404`
   - law: `政府购买服务管理办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

286. [procedure][synonym] 事业单位政府购买服务改革的总体目标是什么，以及这项改革工作的实施方案需要何时提交备案？
   - expected: `parent_政府购买服务管理办法_33_1568_1497_child3`
   - top1: `parent_政府购买服务管理办法_33_1568_1497_child13`
   - law: `政府购买服务管理办法`
   - type: `pdf_law_child` | span: `cross_chunk`

287. [scenario_judgment][synonym] 事业单位政府购买服务改革的指导思想是什么？
   - expected: `parent_政府购买服务管理办法_33_1568_1497_child1`
   - top1: `parent_政府购买服务管理办法_33_1568_1497_child6`
   - law: `政府购买服务管理办法`
   - type: `pdf_law_child` | span: `cross_chunk`

288. [condition_check][synonym] 不同类型的事业单位在政府购买服务中分别扮演什么角色？
   - expected: `parent_政府购买服务管理办法_33_1568_1497_child4`
   - top1: `parent_政府购买服务管理办法_33_1568_1497_child6`
   - law: `政府购买服务管理办法`
   - type: `pdf_law_child` | span: `cross_chunk`

289. [procedure][synonym] 政府采购信息发布有哪些规定，以及采购需求和采购实施计划的管理要求是什么？
   - expected: `parent_《中华人民共和国政府采购法实施条例》等有_15_1572_581`
   - top1: `parent_《中华人民共和国政府采购法实施条例》等有_2_1569_9196`
   - law: `《中华人民共和国政府采购法实施条例》等有关法`
   - type: `pdf_law_parent` | span: `cross_chunk`

290. [procedure][synonym] 政府采购信息发布有哪些规定，以及政府采购资格预审公告应包含哪些内容？
   - expected: `parent_《中华人民共和国政府采购法实施条例》等有_15_1572_581`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0182`
   - law: `《中华人民共和国政府采购法实施条例》等有关法`
   - type: `pdf_law_parent` | span: `cross_chunk`

291. [procedure][synonym] 资格预审适用于什么情况，以及对于潜在投标人在阅读招标文件时提出的疑问，招标人应如何处理？
   - expected: `parent_工程建设项目货物招标投标办法_15_227_3433`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0192`
   - law: `工程建设项目货物招标投标办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

292. [procedure][synonym] 招标文件应当包含哪些实质性要求和条件？招标人如何确保这些要求被投标人充分理解？
   - expected: `parent_工程建设项目施工招标投标办法_23_10_4291`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0258`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

293. [procedure][synonym] 招标文件中应当包含哪些内容？评标委员会如何确定中标人？
   - expected: `parent_工程建设项目施工招标投标办法_23_10_4291`
   - top1: `parent_中华人民共和国招标投标法_38_13_6425`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

294. [case_reasoning][synonym] 招标文件应当包含哪些内容？招标人与投标人进行实质性内容谈判会有什么法律后果？
   - expected: `parent_工程建设项目施工招标投标办法_23_10_4291`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0616`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

295. [procedure][synonym] 招标文件应当包含哪些内容？投标保证金有哪些要求和限制？
   - expected: `parent_工程建设项目施工招标投标办法_23_10_4291`
   - top1: `parent_工程建设项目货物招标投标办法_26_231_7260`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

296. [procedure][synonym] 招标文件应当包含哪些内容？对招标投标活动有异议时如何投诉？
   - expected: `parent_工程建设项目施工招标投标办法_23_10_4291`
   - top1: `parent_设计施工总承包招标的评标采用综合评分法_63_521_8535`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

297. [condition_check][synonym] 哪些情况下投标无效？评标委员会成员有哪些行为会被禁止担任评标工作？
   - expected: `parent_工程建设项目施工招标投标办法_35_15_4605`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0742`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

298. [procedure][synonym] 评标委员会完成评标后应向招标人提交什么文件？如果招标投标活动不符合国家规定，投标人或者其他利害关系人可以采取什么措施？
   - expected: `parent_工程建设项目施工招标投标办法_54_22_3648`
   - top1: `parent_中华人民共和国招标投标法实施条例_52_43_9726`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

299. [procedure][synonym] 评标委员会成员收受投标人财物会有什么处罚？投标保证金有什么规定？
   - expected: `parent_工程建设项目施工招标投标办法_76_31_7419`
   - top1: `parent_评标委员会应组织全体评标委员学习有关规定_71_712_9976`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

300. [procedure][synonym] 评标委员会成员不公正履行职责会受到什么处罚？如果发现招标投标活动不符合规定，应该如何投诉？
   - expected: `parent_工程建设项目施工招标投标办法_76_31_7419`
   - top1: `parent_评标委员会和评标方法暂行规定_53_154_1711`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

301. [procedure][synonym] 招标文件售出后是否可以退还？如果发现招标投标活动不符合规定，应该如何投诉？
   - expected: `parent_工程建设项目施工招标投标办法_14_176_6158`
   - top1: `parent_工程建设项目施工招标投标办法_14_6_8122`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

302. [comparison][synonym] 招标人违法与投标人谈判会有什么后果？哪些行为属于投标人串通投标报价？
   - expected: `parent_工程建设项目施工招标投标办法_76_31_7419`
   - top1: `parent_工程建设项目施工招标投标办法_47_19_206`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

303. [procedure][synonym] 投标人提交投标保证金有哪些要求？联合体投标时提交投标保证金有什么特殊规定？
   - expected: `parent_工程建设项目施工招标投标办法_37_16_391`
   - top1: `parent_进一步规范机电产品国际招标投标活动有关规_22_459_6846`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

304. [procedure][synonym] 投标人提交投标保证金的方式有哪些？金额限制是多少？联合体投标时应当以谁的名义提交投标保证金？
   - expected: `parent_工程建设项目施工招标投标办法_37_16_391`
   - top1: `parent_进一步规范机电产品国际招标投标活动有关规_22_459_6846`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

305. [procedure][synonym] 采购人在验收供应商履约时有哪些具体要求？
   - expected: `parent_政府采购非招标采购方式管理办法_22_1502_7260`
   - top1: `parent_中央国家机关政府采购电子卖场管理办法_21_1301_9856`
   - law: `政府采购非招标采购方式管理办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

306. [condition_check][synonym] 政府采购货物和服务的招标投标活动应遵循什么特别规定？
   - expected: `parent_中华人民共和国招标投标法实施条例_82_57_7179`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0028`
   - law: `中华人民共和国招标投标法实施条例`
   - type: `pdf_law_parent` | span: `cross_chunk`

307. [responsibility][synonym] 招标代理机构在招标过程中有哪些禁止行为？
   - expected: `parent_中华人民共和国招标投标法实施条例_82_57_7179`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0180`
   - law: `中华人民共和国招标投标法实施条例`
   - type: `pdf_law_parent` | span: `cross_chunk`

308. [definition][synonym] 《招标投标法实施条例》的适用范围是什么？
   - expected: `parent_中华人民共和国招标投标法实施条例_82_57_7179`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0091`
   - law: `中华人民共和国招标投标法实施条例`
   - type: `pdf_law_parent` | span: `cross_chunk`

309. [procedure][synonym] 评标委员会的专家成员如何确定？有哪些规定？
   - expected: `parent_中华人民共和国招标投标法实施条例_44_40_4303`
   - top1: `parent_评标委员会和评标方法暂行规定_7_139_1404`
   - law: `中华人民共和国招标投标法实施条例`
   - type: `pdf_law_parent` | span: `cross_chunk`

310. [procedure][synonym] 招标代理机构在代理招标业务时，如果发现有投标人串通投标，应当如何处理？
   - expected: `parent_中华人民共和国招标投标法实施条例_11_29_2401`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0398`
   - law: `中华人民共和国招标投标法实施条例`
   - type: `pdf_law_parent` | span: `cross_chunk`

311. [procedure][synonym] 在招标投标过程中，如果投标人串通投标，招标人应当如何处理？
   - expected: `parent_中华人民共和国招标投标法实施条例_44_40_4303`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0398`
   - law: `中华人民共和国招标投标法实施条例`
   - type: `pdf_law_parent` | span: `cross_chunk`

312. [comparison][synonym] 在依法必须进行招标的项目中，评标委员会专家成员的确定方式与招标代理机构的专业人员要求有何不同？
   - expected: `parent_中华人民共和国招标投标法实施条例_44_40_4303`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0451`
   - law: `中华人民共和国招标投标法实施条例`
   - type: `pdf_law_parent` | span: `cross_chunk`

313. [procedure][synonym] 招标人在招标文件中要求投标人提交投标保证金时，如果发现投标人串通投标，保证金将如何处理？
   - expected: `parent_中华人民共和国招标投标法实施条例_53_51_6303`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0364`
   - law: `中华人民共和国招标投标法实施条例`
   - type: `pdf_law_parent` | span: `cross_chunk`

314. [procedure][synonym] 在依法必须进行招标的项目中，如果投标人串通投标，招标代理机构应当如何处理？
   - expected: `parent_中华人民共和国招标投标法实施条例_53_51_6303`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0398`
   - law: `中华人民共和国招标投标法实施条例`
   - type: `pdf_law_parent` | span: `cross_chunk`

315. [procedure][synonym] 成为评标专家需要满足哪些基本条件，同时评标专家有哪些义务？
   - expected: `parent_系统工程综合评标专家库管理办法_12_680_7250`
   - top1: `parent_铁路建设工程评标专家库及评标专家管理办法_5_732_3944`
   - law: `系统工程综合评标专家库管理办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

316. [procedure][synonym] 招标人在什么情况下可以终止招标？终止招标后应如何处理已收取的费用和保证金？如果评标委员会认为投标人的报价明显低于其他投标报价，应如何处理？
   - expected: `parent_铁路工程建设项目招标投标管理办法_19_757_2288`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0522`
   - law: `铁路工程建设项目招标投标管理办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

317. [procedure][synonym] 在电子招标投标公共服务平台上发现串通投标行为后，应该如何处理？
   - expected: `parent_电子招标投标办法_43_257_4773`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0398`
   - law: `电子招标投标办法`
   - type: `pdf_law_parent` | span: `cross_doc`

318. [case_reasoning][synonym] 在电子招标投标公共服务平台上发现串通竞买行为时，应如何认定和处理？
   - expected: `parent_电子招标投标办法_43_257_4773`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0395`
   - law: `电子招标投标办法`
   - type: `pdf_law_parent` | span: `cross_doc`

319. [procedure][synonym] 电子招标投标公共服务平台应如何处理供应商资格预审问题？
   - expected: `parent_电子招标投标办法_43_257_4773`
   - top1: `parent_电子招标投标办法_22_250_5263`
   - law: `电子招标投标办法`
   - type: `pdf_law_parent` | span: `cross_doc`

320. [case_reasoning][synonym] 在电子招标投标公共服务平台上发现串通投标行为导致评标结果不公时，应如何处理？
   - expected: `parent_电子招标投标办法_43_257_4773`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0402`
   - law: `电子招标投标办法`
   - type: `pdf_law_parent` | span: `cross_doc`

321. [case_reasoning][synonym] 在建设工程施工合同纠纷中，如果承包范围存在争议，法院如何认定已完成工程的比例？如果招标文件中对实质性要求和条件未明确标明，可能导致什么后果？
   - expected: `parent_工程建设项目施工招标投标办法_23_10_4291`
   - top1: `pdf_建设工程施工合同纠纷案_10_4916`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `cross_doc`

322. [case_reasoning][synonym] 在建设工程施工合同纠纷中，承包人如何主张工程款和履约保证金？招标文件中应当包含哪些实质性内容，以避免后续合同纠纷？
   - expected: `parent_工程建设项目施工招标投标办法_23_10_4291`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0628`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `cross_doc`

323. [case_reasoning][synonym] 在招投标活动中，如何认定串通投标行为？招标文件中应当如何规定评标标准和方法，以防止串通投标？
   - expected: `parent_工程建设项目施工招标投标办法_23_10_4291`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0401`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `cross_doc`

324. [case_reasoning][synonym] 在招投标过程中，如果评标人员发现投标人有串通投标行为，应该如何处理？串通投标行为会对评标结果产生什么影响？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0574`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0398`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `cross_doc`

325. [procedure][synonym] 在建设工程施工合同纠纷中，如果承包人完成的工程部分比例不同，应如何计算工程款？法院如何确定最终应付工程款金额？
   - expected: `pdf_建设工程施工合同纠纷案_11_4184`
   - top1: `pdf_建设工程施工合同纠纷案_27_5942`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `cross_doc`

326. [case_reasoning][synonym] 在招投标过程中，如果投标人的联系人同时是竞争对手公司的发起人，这种行为是否构成串通投标？法院如何认定？
   - expected: `pdf_建设工程施工合同纠纷案_11_4184`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0730`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `cross_doc`

327. [case_reasoning][synonym] 在招投标过程中，如何认定串通投标行为？请结合案例说明。
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_10_4535`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0391`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `cross_doc`

328. [comparison][synonym] 在国有建设用地使用权出让过程中，挂牌出让与招标出让的法律适用有何不同？
   - expected: `pdf_非国家工作人员行贿案_7_4005`
   - top1: `parent_招标拍卖挂牌出让国有建设用地使用权规定_1_349_7`
   - law: `非国家工作人员行贿案`
   - type: `pdf_case_sliding` | span: `cross_doc`

329. [case_reasoning][synonym] 串通投标行为在法律上可能面临哪些刑事处罚？
   - expected: `pdf_串通投标、受贿案_1_8873`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0731`
   - law: `串通投标、受贿案`
   - type: `pdf_case_sliding` | span: `cross_doc`

330. [case_reasoning][synonym] 招投标活动中，评标人员与投标人之间存在利益输送关系时，如何认定其行为的违法性？
   - expected: `pdf_串通投标、受贿案_1_8873`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0732`
   - law: `串通投标、受贿案`
   - type: `pdf_case_sliding` | span: `cross_doc`
