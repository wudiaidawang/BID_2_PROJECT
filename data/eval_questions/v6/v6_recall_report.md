# V6 召回评测报告 — Chunk ID 匹配（本地 jieba BM25）

**评测集**: v6_benchmark.json, 2908 题
**评测方式**: 纯 chunk ID 匹配（expected_chunk_id / acceptable_chunk_ids）
**BM25**: 本地 jieba 分词（与生产管线一致），替代 Milvus 内置字符 n-gram

## 各阶段召回率对比

| 阶段 | Recall@1 | Recall@3 | Recall@5 |
|------|----------|----------|----------|
| Dense only | 29.3% | 42.6% | 47.5% |
| BM25 (jieba) | 31.6% | 44.6% | 49.9% |
| RRF fused | 30.5% | 47.8% | 53.4% |
| Parent expanded | 30.5% | 47.8% | 53.4% |
| Reranker final | 39.4% | 56.1% | 61.7% |

## 最终召回率 (Reranker 后)

| 指标 | 命中 | 总数 | 比率 |
|------|------|------|------|
| Recall@1 | 1146 | 2908 | **39.4%** |
| Recall@3 | 1632 | 2908 | **56.1%** |
| Recall@5 | 1794 | 2908 | **61.7%** |

## 按 chunk_type

| 类型 | 题数 | Recall@1 | Recall@3 | Recall@5 |
|------|------|----------|----------|----------|
| cross_doc | 46 | 26.1% | 39.1% | **41.3%** |
| opinion_news | 266 | 26.7% | 39.8% | **44.7%** |
| pdf_case_paragraph | 669 | 45.6% | 63.7% | **70.4%** |
| pdf_case_sliding | 252 | 19.0% | 40.5% | **50.8%** |
| pdf_law_parent | 584 | 59.4% | 75.0% | **78.3%** |
| policy_doc | 1091 | 33.3% | 49.7% | **55.0%** |

## 按 question_type (题型)

| 类型 | 题数 | Recall@1 | Recall@3 | Recall@5 |
|------|------|----------|----------|----------|
| announcement_interpretation | 29 | 51.7% | 62.1% | **65.5%** |
| case_reasoning | 78 | 37.2% | 60.3% | **69.2%** |
| comparison | 150 | 36.0% | 49.3% | **56.0%** |
| condition_check | 327 | 38.8% | 56.3% | **61.5%** |
| definition | 281 | 47.3% | 63.7% | **71.9%** |
| procedure | 582 | 34.0% | 49.0% | **52.9%** |
| responsibility | 264 | 34.1% | 53.0% | **60.2%** |
| scenario_judgment | 1197 | 41.8% | 58.9% | **64.1%** |

## 按 retrieval_difficulty (检索难度)

| 类型 | 题数 | Recall@1 | Recall@3 | Recall@5 |
|------|------|----------|----------|----------|
| cross_reference | 169 | 35.5% | 51.5% | **54.4%** |
| direct | 765 | 43.4% | 59.6% | **64.2%** |
| scenario | 1414 | 37.3% | 55.5% | **62.0%** |
| synonym | 560 | 40.5% | 54.3% | **59.8%** |

## 按 span

| 类型 | 题数 | Recall@1 | Recall@3 | Recall@5 |
|------|------|----------|----------|----------|
| cross_doc | 46 | 26.1% | 39.1% | **41.3%** |
| single | 2862 | 39.6% | 56.4% | **62.0%** |

## 交叉分析: chunk_type × question_type

| chunk_type \ question_type | announcement_interpretation | case_reasoning | comparison | condition_check | definition | procedure | responsibility | scenario_judgment |
|---|---|---|---|---|---|---|---|---|
## Miss 样本

共 1114 条 (R@5 仍未命中):

1. [procedure][scenario] 我们公司在采购项目中标后，需要多久必须完成合同签订？
   - expected: `policy_40`
   - top1: `parent_中华人民共和国政府采购法_46_3003_3920`
   - law: `财政部关于印发《政府采购评审专家管理办法》的通知`
   - type: `policy_doc` | span: `single`

2. [scenario_judgment][scenario] 我们公司在市交易中心进行场内交易时，如果出现不良行为会被怎么记分？
   - expected: `policy_40`
   - top1: `policy_129`
   - law: `财政部关于印发《政府采购评审专家管理办法》的通知`
   - type: `policy_doc` | span: `single`

3. [scenario_judgment][scenario] 我们公司作为经营主体，在市交易中心场内交易中，信用记分的结果会影响什么方面？
   - expected: `policy_40`
   - top1: `policy_121`
   - law: `财政部关于印发《政府采购评审专家管理办法》的通知`
   - type: `policy_doc` | span: `single`

4. [scenario_judgment][scenario] 我们公司想做工程总承包项目，需要了解哪些电子招标投标的要求？
   - expected: `policy_123`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0080`
   - law: `上海市公共资源交易中心场内交易信用记分实施细则`
   - type: `policy_doc` | span: `single`

5. [scenario_judgment][scenario] 企业在招投标项目中，若未招标或中标无效，合同效力如何？
   - expected: `policy_63`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0117`
   - law: `最高人民法院关于审理建设工程施工合同纠纷案件适用法律问题的解释(一)`
   - type: `policy_doc` | span: `single`

6. [scenario_judgment][scenario] 企业在工程项目建设中，若中标人和中标人另行签订合同实质性内容不一致，应如何认定？
   - expected: `policy_63`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0628`
   - law: `最高人民法院关于审理建设工程施工合同纠纷案件适用法律问题的解释(一)`
   - type: `policy_doc` | span: `single`

7. [scenario_judgment][scenario] 企业在工程项目建设中，若项目必须招标而未招标，合同效力如何？
   - expected: `policy_63`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0116`
   - law: `最高人民法院关于审理建设工程施工合同纠纷案件适用法律问题的解释(一)`
   - type: `policy_doc` | span: `single`

8. [procedure][scenario] 我们公司中标疫苗项目后，多久内必须完成合同签订？
   - expected: `policy_105`
   - top1: `parent_中华人民共和国政府采购法_46_3003_3920`
   - law: `【药械采购】上海市人民政府办公厅关于进一步加强本市疫苗流通和预防接种管理工作的通`
   - type: `policy_doc` | span: `single`

9. [scenario_judgment][scenario] 我们公司在做政府采购电子卖场项目时，需要关注哪些合规要点？
   - expected: `policy_148`
   - top1: `parent_中央国家机关政府采购电子卖场管理办法_3_3629_828`
   - law: `财政部办公厅关于印发《政府采购电子卖场产品分...`
   - type: `policy_doc` | span: `single`

10. [definition][direct] 政府采购电子卖场的项目分类有哪些具体规定？
   - expected: `policy_148`
   - top1: `policy_205`
   - law: `财政部办公厅关于印发《政府采购电子卖场产品分...`
   - type: `policy_doc` | span: `single`

11. [comparison][scenario] 政府采购电子卖场的流程与传统采购方式相比有什么优势？
   - expected: `policy_148`
   - top1: `parent_中央国家机关政府采购电子卖场管理办法_26_3660_9966`
   - law: `财政部办公厅关于印发《政府采购电子卖场产品分...`
   - type: `policy_doc` | span: `single`

12. [procedure][direct] 企业在使用政府采购电子卖场时，如何保障交易安全？
   - expected: `policy_148`
   - top1: `parent_中央国家机关政府采购电子卖场管理办法_3_3629_828`
   - law: `财政部办公厅关于印发《政府采购电子卖场产品分...`
   - type: `policy_doc` | span: `single`

13. [scenario_judgment][scenario] 我们公司想做公路相关的政府采购项目，需要了解哪些支持政策？
   - expected: `policy_151`
   - top1: `policy_158`
   - law: `财政部 交通运输部关于组织开展“政府采购支持公...`
   - type: `policy_doc` | span: `single`

14. [procedure][direct] 政府采购支持公路项目的申请流程是怎样的？
   - expected: `policy_151`
   - top1: `parent_交通运输部部属单位政府采购管理办法_32_3949_1910`
   - law: `财政部 交通运输部关于组织开展“政府采购支持公...`
   - type: `policy_doc` | span: `single`

15. [responsibility][scenario] 公路项目中的政府采购支持政策对企业中小企业有什么优惠？
   - expected: `policy_151`
   - top1: `parent_《中华人民共和国中小企业促进法》等有关法_4_3973_1234`
   - law: `财政部 交通运输部关于组织开展“政府采购支持公...`
   - type: `policy_doc` | span: `single`

16. [condition_check][cross_reference] 这类政府采购支持在评标时有没有特殊要求？
   - expected: `policy_151`
   - top1: `parent_政府采购货物和服务招标投标管理办法_64_47_8673`
   - law: `财政部 交通运输部关于组织开展“政府采购支持公...`
   - type: `policy_doc` | span: `single`

17. [scenario_judgment][scenario] 我们公司想做政府购买服务项目，需要先了解哪些关键信息？
   - expected: `policy_214`
   - top1: `parent_政府购买服务管理办法_16_4353_5607`
   - law: `重庆市进一步加强政府购买服务管理`
   - type: `policy_doc` | span: `single`

18. [scenario_judgment][scenario] 我们公司在购买服务时，是否可以随意选择供应商？
   - expected: `policy_214`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_17_3745_633`
   - law: `重庆市进一步加强政府购买服务管理`
   - type: `policy_doc` | span: `single`

19. [procedure][direct] 我们公司想了解政府购买服务的具体流程是怎样的？
   - expected: `policy_214`
   - top1: `parent_政府购买服务管理办法_11_4348_4471`
   - law: `重庆市进一步加强政府购买服务管理`
   - type: `policy_doc` | span: `single`

20. [scenario_judgment][scenario] 如果我们在政府购买服务过程中出现违规情况，会有什么处罚？
   - expected: `policy_214`
   - top1: `parent_政府购买服务管理办法_31_4369_5534`
   - law: `重庆市进一步加强政府购买服务管理`
   - type: `policy_doc` | span: `single`

21. [condition_check][direct] 我们公司作为服务提供方，需要满足哪些资质要求？
   - expected: `policy_214`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0542`
   - law: `重庆市进一步加强政府购买服务管理`
   - type: `policy_doc` | span: `single`

22. [scenario_judgment][scenario] 我们公司想参与政府购买服务，需要提前做哪些准备工作？
   - expected: `policy_214`
   - top1: `parent_政府购买服务管理办法_14_4351_5332`
   - law: `重庆市进一步加强政府购买服务管理`
   - type: `policy_doc` | span: `single`

23. [procedure][direct] 我们公司即将开展政府采购项目，在需求编制阶段需要注意哪些核心要点？
   - expected: `policy_227`
   - top1: `parent_《中华人民共和国政府采购法实施条例》等有_9_3999_7727`
   - law: `黑龙江省财政厅关于加强政府采购项目需求编制与公示工...`
   - type: `policy_doc` | span: `single`

24. [procedure][scenario] 政府采购项目从需求编制到最终公示，整个流程大致需要多长时间？各个环节的时效性要求是什么？
   - expected: `policy_227`
   - top1: `parent_中华人民共和国政府采购法实施条例_31_43_7159`
   - law: `黑龙江省财政厅关于加强政府采购项目需求编制与公示工...`
   - type: `policy_doc` | span: `single`

25. [responsibility][direct] 如果企业在政府采购项目中出现质疑情况，应该向哪个部门提出投诉？投诉流程有什么要求？
   - expected: `policy_143`
   - top1: `parent_政府采购质疑和投诉办法_24_3484_1330`
   - law: `中华人民共和国财政部令第94号《政府采购质疑和...`
   - type: `policy_doc` | span: `single`

26. [scenario_judgment][scenario] 当政府采购项目出现违规情况时，企业应该如何应对和处理，避免受到处罚？
   - expected: `policy_143`
   - top1: `parent_政府购买服务管理办法_31_4369_5534`
   - law: `中华人民共和国财政部令第94号《政府采购质疑和...`
   - type: `policy_doc` | span: `single`

27. [scenario_judgment][scenario] 我们企业在年度预算编制时，需要遵循哪些预算法的要求？
   - expected: `policy_195`
   - top1: `parent_中华人民共和国预算法_12_3145_3935`
   - law: `中华人民共和国预算法`
   - type: `policy_doc` | span: `single`

28. [procedure][scenario] 若公司出现预算超支情况，预算法规定的处理程序是什么？
   - expected: `policy_195`
   - top1: `parent_中华人民共和国预算法_66_3201_4370`
   - law: `中华人民共和国预算法`
   - type: `policy_doc` | span: `single`

29. [responsibility][cross_reference] 公司建立内部财务制度时，预算法有哪些需要遵守的条款？
   - expected: `policy_195`
   - top1: `parent_中华人民共和国预算法_12_3145_3935`
   - law: `中华人民共和国预算法`
   - type: `policy_doc` | span: `single`

30. [case_reasoning][direct] 财政部制定该通知的主要目的是什么？
   - expected: `policy_29`
   - top1: `policy_40`
   - law: `财政部关于进一步明确国有金融企业增资扩股股权管理有关问题的通知`
   - type: `policy_doc` | span: `single`

31. [procedure][scenario] 企业参与政府采购框架协议项目，前期需要准备哪些资质？
   - expected: `policy_162`
   - top1: `parent_中华人民共和国政府采购法实施条例_22_19_7099`
   - law: `财政部有关负责人就制定《政府采购框架协议采购...`
   - type: `policy_doc` | span: `single`

32. [procedure][direct] 企业遇到政府采购框架协议纠纷，该如何投诉？
   - expected: `policy_162`
   - top1: `parent_政府采购质疑和投诉办法_8_3464_8323`
   - law: `财政部有关负责人就制定《政府采购框架协议采购...`
   - type: `policy_doc` | span: `single`

33. [definition][direct] 政府采购框架协议适用于哪些类型的采购项目？
   - expected: `policy_162`
   - top1: `parent_政府采购框架协议采购方式管理暂行办法_3_4242_7627`
   - law: `财政部有关负责人就制定《政府采购框架协议采购...`
   - type: `policy_doc` | span: `single`

34. [procedure][scenario] 企业参与上海市公共资源“一网交易”改革后，办理流程有何变化？
   - expected: `policy_1`
   - top1: `policy_74`
   - law: `关于印发《2023年上海市公共资源“一网交易”改革重点工作安排》的通知`
   - type: `policy_doc` | span: `single`

35. [procedure][direct] 参与上海市公共资源交易的单位，如何适应“一网交易”新模式？
   - expected: `policy_1`
   - top1: `policy_78`
   - law: `关于印发《2023年上海市公共资源“一网交易”改革重点工作安排》的通知`
   - type: `policy_doc` | span: `single`

36. [responsibility][direct] 企业在上海市公共资源交易中遇到问题，该找哪个部门咨询？
   - expected: `policy_1`
   - top1: `policy_85`
   - law: `关于印发《2023年上海市公共资源“一网交易”改革重点工作安排》的通知`
   - type: `policy_doc` | span: `single`

37. [scenario_judgment][scenario] 投资审批制度改革后，企业开展新项目需要满足哪些条件？
   - expected: `policy_134`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0138`
   - law: `国务院办公厅关于深化投资审批制度改革的意见`
   - type: `policy_doc` | span: `single`

38. [procedure][cross_reference] 如果我们的项目涉及多个部门审批，应该怎么协调？
   - expected: `policy_134`
   - top1: `parent_政府投资条例_10_342_1287`
   - law: `国务院办公厅关于深化投资审批制度改革的意见`
   - type: `policy_doc` | span: `single`

39. [procedure][direct] 我们公司想了解投资审批改革后的项目备案流程。
   - expected: `policy_134`
   - top1: `parent_政府投资条例_10_342_1287`
   - law: `国务院办公厅关于深化投资审批制度改革的意见`
   - type: `policy_doc` | span: `single`

40. [procedure][direct] 我们在上海做招投标项目，需要准备哪些材料？
   - expected: `policy_85`
   - top1: `parent_水利工程建设项目招标投标管理规定_15_2248_6341`
   - law: `上海市公共资源交易管理办法`
   - type: `policy_doc` | span: `single`

41. [responsibility][direct] 公共资源交易中遇到违规情况，该找哪个部门投诉？
   - expected: `policy_85`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_36_4105_195`
   - law: `上海市公共资源交易管理办法`
   - type: `policy_doc` | span: `single`

42. [procedure][direct] 上海市公共资源交易的流程是怎样的？
   - expected: `policy_85`
   - top1: `policy_88`
   - law: `上海市公共资源交易管理办法`
   - type: `policy_doc` | span: `single`

43. [responsibility][direct] 公共资源交易平台的监管部门是谁？
   - expected: `policy_85`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_6_4075_2228`
   - law: `上海市公共资源交易管理办法`
   - type: `policy_doc` | span: `single`

44. [scenario_judgment][direct] 企业在公共资源交易中遇到纠纷怎么解决？
   - expected: `policy_85`
   - top1: `parent_中央国家机关政府采购电子卖场管理办法_23_3649_2626`
   - law: `上海市公共资源交易管理办法`
   - type: `policy_doc` | span: `single`

45. [scenario_judgment][scenario] 投资审批制度改革后，企业开展新项目需要满足哪些条件？
   - expected: `policy_134`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0138`
   - law: `国务院办公厅关于深化投资审批制度改革的意见`
   - type: `policy_doc` | span: `single`

46. [procedure][direct] 我们公司中标一个投资项目后，需要多长时间内完成审批手续？
   - expected: `policy_134`
   - top1: `parent_经营性公路建设项目投资人招标投标管理规定_34_1753_9064`
   - law: `国务院办公厅关于深化投资审批制度改革的意见`
   - type: `policy_doc` | span: `single`

47. [procedure][scenario] 如果我们的项目涉及多个部门审批，应该怎么协调？
   - expected: `policy_134`
   - top1: `parent_政府投资条例_10_342_1287`
   - law: `国务院办公厅关于深化投资审批制度改革的意见`
   - type: `policy_doc` | span: `single`

48. [procedure][direct] 我们公司想了解投资审批改革后的项目备案流程。
   - expected: `policy_134`
   - top1: `parent_政府投资条例_10_342_1287`
   - law: `国务院办公厅关于深化投资审批制度改革的意见`
   - type: `policy_doc` | span: `single`

49. [procedure][direct] 我们在上海做招投标项目，需要准备哪些材料？
   - expected: `policy_85`
   - top1: `parent_水利工程建设项目招标投标管理规定_15_2248_6341`
   - law: `上海市公共资源交易管理办法`
   - type: `policy_doc` | span: `single`

50. [responsibility][direct] 公共资源交易中遇到违规情况，该找哪个部门投诉？
   - expected: `policy_85`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_36_4105_195`
   - law: `上海市公共资源交易管理办法`
   - type: `policy_doc` | span: `single`

51. [procedure][direct] 上海市公共资源交易的流程是怎样的？
   - expected: `policy_85`
   - top1: `policy_88`
   - law: `上海市公共资源交易管理办法`
   - type: `policy_doc` | span: `single`

52. [responsibility][scenario] 公共资源交易平台的监管部门是谁？
   - expected: `policy_85`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_6_4075_2228`
   - law: `上海市公共资源交易管理办法`
   - type: `policy_doc` | span: `single`

53. [scenario_judgment][scenario] 企业在公共资源交易中遇到纠纷怎么解决？
   - expected: `policy_85`
   - top1: `parent_中央国家机关政府采购电子卖场管理办法_23_3649_2626`
   - law: `上海市公共资源交易管理办法`
   - type: `policy_doc` | span: `single`

54. [condition_check][scenario] 投资审批制度改革后，企业开展新项目需要满足哪些条件？
   - expected: `policy_134`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0138`
   - law: `国务院办公厅关于深化投资审批制度改革的意见`
   - type: `policy_doc` | span: `single`

55. [procedure][direct] 我们公司中标一个投资项目后，需要多长时间内完成审批手续？
   - expected: `policy_134`
   - top1: `parent_经营性公路建设项目投资人招标投标管理规定_34_1753_9064`
   - law: `国务院办公厅关于深化投资审批制度改革的意见`
   - type: `policy_doc` | span: `single`

56. [procedure][direct] 如果我们的项目涉及多个部门审批，应该怎么协调？
   - expected: `policy_134`
   - top1: `parent_政府投资条例_10_342_1287`
   - law: `国务院办公厅关于深化投资审批制度改革的意见`
   - type: `policy_doc` | span: `single`

57. [procedure][direct] 我们公司想了解投资审批改革后的项目备案流程。
   - expected: `policy_134`
   - top1: `parent_政府投资条例_10_342_1287`
   - law: `国务院办公厅关于深化投资审批制度改革的意见`
   - type: `policy_doc` | span: `single`

58. [responsibility][direct] 公共资源交易中遇到违规情况，该找哪个部门投诉？
   - expected: `policy_85`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_36_4105_195`
   - law: `上海市公共资源交易管理办法`
   - type: `policy_doc` | span: `single`

59. [procedure][direct] 我们在上海做招投标项目，需要准备哪些材料？
   - expected: `policy_85`
   - top1: `parent_水利工程建设项目招标投标管理规定_15_2248_6341`
   - law: `上海市公共资源交易管理办法`
   - type: `policy_doc` | span: `single`

60. [procedure][direct] 上海市公共资源交易的流程是怎样的？
   - expected: `policy_85`
   - top1: `policy_88`
   - law: `上海市公共资源交易管理办法`
   - type: `policy_doc` | span: `single`

61. [responsibility][direct] 公共资源交易平台的监管部门是谁？
   - expected: `policy_85`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_6_4075_2228`
   - law: `上海市公共资源交易管理办法`
   - type: `policy_doc` | span: `single`

62. [procedure][direct] 企业在公共资源交易中遇到纠纷怎么解决？
   - expected: `policy_85`
   - top1: `parent_中央国家机关政府采购电子卖场管理办法_23_3649_2626`
   - law: `上海市公共资源交易管理办法`
   - type: `policy_doc` | span: `single`

63. [definition][direct] 行政复议的申请范围包括哪些情况？
   - expected: `policy_176`
   - top1: `parent_华人民共和国招标投标法实施条例》及其他有_25_1004_108`
   - law: `中华人民共和国行政复议法`
   - type: `policy_doc` | span: `single`

64. [procedure][direct] 企业遇到行政决定不服，想申请行政复议应该怎么做？
   - expected: `policy_176`
   - top1: `parent_监督处理中华人民共和国行政处罚法_73_895_572`
   - law: `中华人民共和国行政复议法`
   - type: `policy_doc` | span: `single`

65. [definition][direct] 行政复议的审理期限是多少？
   - expected: `policy_176`
   - top1: `parent_监督处理中华人民共和国行政处罚法_85_910_9950`
   - law: `中华人民共和国行政复议法`
   - type: `policy_doc` | span: `single`

66. [procedure][direct] 我们公司中标后，需要通过什么方式来进行交易价款的结算呢？
   - expected: `policy_82`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0652`
   - law: `【综合管理】关于印发《市公共资源交易平台与财政国库集中支付平台对接方案》的通知`
   - type: `policy_doc` | span: `single`

67. [scenario_judgment][scenario] 我们公司在处理客户数据时，需要满足哪些数据安全方面的合规要求？
   - expected: `policy_180`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_28_4097_3258`
   - law: `中华人民共和国数据安全法`
   - type: `policy_doc` | span: `single`

68. [condition_check][scenario] 企业在进行数据跨境传输时，需要准备哪些合规文件？
   - expected: `policy_180`
   - top1: `parent_出口商品配额管理办法_25_2718_8629`
   - law: `中华人民共和国数据安全法`
   - type: `policy_doc` | span: `single`

69. [procedure][direct] 若发现数据泄露事件，企业需要在多长时间内向监管部门报告？
   - expected: `policy_180`
   - top1: `parent_铁路工程建设项目招标投标管理办法_48_2125_8967`
   - law: `中华人民共和国数据安全法`
   - type: `policy_doc` | span: `single`

70. [procedure][scenario] 中标项目后我们需要多久完成采购信息公告？
   - expected: `policy_221`
   - top1: `parent_政府采购货物和服务招标投标管理办法_69_74_9402`
   - law: `四川省财政厅关于进一步做好政府采购信息公告管理工作...`
   - type: `policy_doc` | span: `single`

71. [procedure][scenario] 做政府采购时怎么处理信息公告环节？
   - expected: `policy_221`
   - top1: `parent_财政部关于做好政府采购信息公开工作的通知_31_4396_9219`
   - law: `四川省财政厅关于进一步做好政府采购信息公告管理工作...`
   - type: `policy_doc` | span: `single`

72. [responsibility][scenario] 公司中标后公告采购信息的部门是哪个？
   - expected: `policy_221`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_40_3869_605`
   - law: `四川省财政厅关于进一步做好政府采购信息公告管理工作...`
   - type: `policy_doc` | span: `single`

73. [scenario_judgment][scenario] 我们公司需要注意哪些公告管理的合规事项？
   - expected: `policy_221`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0033`
   - law: `四川省财政厅关于进一步做好政府采购信息公告管理工作...`
   - type: `policy_doc` | span: `single`

74. [case_reasoning][scenario] 如果技术交易出现纠纷该怎么处理？
   - expected: `policy_116`
   - top1: `parent_中央国家机关政府采购电子卖场管理办法_23_3649_2626`
   - law: `【技术交易】关于印发《上海市技术交易场所管理细则》的通知`
   - type: `policy_doc` | span: `single`

75. [procedure][scenario] 我们公司做工业项目，中标后多久要签合同？
   - expected: `policy_38`
   - top1: `parent_投资项目招标投标管理办法_23_2560_3953`
   - law: `国土资源部、监察部关于落实工业用地招标拍卖挂牌出让制度有关问题的通知`
   - type: `policy_doc` | span: `single`

76. [procedure][direct] 工业用地招标拍卖挂牌后，后续有哪些关键流程？
   - expected: `policy_38`
   - top1: `parent_招标拍卖挂牌出让国有建设用地使用权规定_17_1027_9667`
   - law: `国土资源部、监察部关于落实工业用地招标拍卖挂牌出让制度有关问题的通知`
   - type: `policy_doc` | span: `single`

77. [scenario_judgment][scenario] 企业在进行政府采购项目时，如何确保合规操作？
   - expected: `policy_142`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_18_3794_7185`
   - law: `中华人民共和国财政部令第101号《政府采购信息发...`
   - type: `policy_doc` | span: `single`

78. [responsibility][direct] 企业在参与政府采购项目时，需要关注哪些政策要点？
   - expected: `policy_142`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0289`
   - law: `中华人民共和国财政部令第101号《政府采购信息发...`
   - type: `policy_doc` | span: `single`

79. [scenario_judgment][scenario] 如果我们的国企项目涉及采购流程，遇到供应商报价过低的情况，应该怎么处理？
   - expected: `policy_150`
   - top1: `parent_政务信息系统政府采购管理暂行办法_11_3352_2547`
   - law: `关于推动解决政府采购异常低价问题的通知`
   - type: `policy_doc` | span: `single`

80. [scenario_judgment][scenario] 我们公司涉及公共资源交易，想知道整合后的服务保障有哪些？
   - expected: `policy_47`
   - top1: `policy_80`
   - law: `国务院国有资产监督管理委员会关于印发《企业国有产权无偿划转工作指引》的通知`
   - type: `policy_doc` | span: `single`

81. [scenario_judgment][scenario] 企业在公共资源交易中出现纠纷，该怎么投诉或解决？
   - expected: `policy_47`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_36_4105_195`
   - law: `国务院国有资产监督管理委员会关于印发《企业国有产权无偿划转工作指引》的通知`
   - type: `policy_doc` | span: `single`

82. [scenario_judgment][scenario] 公共资源交易整合后，各交易服务机构的服务范围有何变化？
   - expected: `policy_47`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_48_4119_8963`
   - law: `国务院国有资产监督管理委员会关于印发《企业国有产权无偿划转工作指引》的通知`
   - type: `policy_doc` | span: `single`

83. [procedure][direct] 公共资源交易整合后，各分中心的运营情况如何报告？
   - expected: `policy_47`
   - top1: `policy_80`
   - law: `国务院国有资产监督管理委员会关于印发《企业国有产权无偿划转工作指引》的通知`
   - type: `policy_doc` | span: `single`

84. [scenario_judgment][scenario] 公司在公共资源交易中遇到问题，该找哪个部门投诉或协调？
   - expected: `policy_80`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_36_4105_195`
   - law: `【综合管理】上海市公共资源交易整合共享工作协调机制关于同意在上海联合产权交易所加`
   - type: `policy_doc` | span: `single`

85. [responsibility][scenario] 如果我们的企业在政府采购中遇到纠纷，应该找哪个部门投诉？
   - expected: `policy_202`
   - top1: `parent_政府采购质疑和投诉办法_6_3474_4159`
   - law: `赵乐际主持召开十四届全国人大常委会...`
   - type: `policy_doc` | span: `single`

86. [condition_check][scenario] 我们在进行政府采购项目时，需要满足哪些基本条件？
   - expected: `policy_182`
   - top1: `parent_中华人民共和国政府采购法实施条例_22_19_7099`
   - law: `欧盟《政府采购公共指令》`
   - type: `policy_doc` | span: `single`

87. [procedure][direct] 企业在参与政府采购时，需要准备哪些材料？
   - expected: `policy_182`
   - top1: `parent_中华人民共和国政府采购法实施条例_22_19_7099`
   - law: `欧盟《政府采购公共指令》`
   - type: `policy_doc` | span: `single`

88. [procedure][direct] 作为企业负责人，中标后应该怎么处理合同签署事宜？
   - expected: `policy_182`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0622`
   - law: `欧盟《政府采购公共指令》`
   - type: `policy_doc` | span: `single`

89. [scenario_judgment][scenario] 政府采购项目中，中小企业有哪些扶持政策？
   - expected: `policy_182`
   - top1: `parent_《中华人民共和国中小企业促进法》等有关法_4_3973_1234`
   - law: `欧盟《政府采购公共指令》`
   - type: `policy_doc` | span: `single`

90. [condition_check][direct] 政府采购中的评审标准主要包含哪些方面？
   - expected: `policy_182`
   - top1: `parent_《中华人民共和国政府采购法实施条例》等有_31_4022_3036`
   - law: `欧盟《政府采购公共指令》`
   - type: `policy_doc` | span: `single`

91. [scenario_judgment][direct] 对于进口产品，政府采购中有何特殊规定？
   - expected: `policy_135`
   - top1: `parent_政府采购进口产品管理办法_14_4055_6773`
   - law: `国务院办公厅关于在政府采购中实施本国产品标准...`
   - type: `policy_doc` | span: `single`

92. [procedure][direct] 企业如何申请本国产品的政府采购资格？
   - expected: `policy_135`
   - top1: `parent_交通运输部部属单位政府采购管理办法_32_3949_1910`
   - law: `国务院办公厅关于在政府采购中实施本国产品标准...`
   - type: `policy_doc` | span: `single`

93. [scenario_judgment][direct] 政府采购协议对企业资质有什么要求？
   - expected: `policy_183`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_19_3795_3923`
   - law: `政府采购协议(上)`
   - type: `policy_doc` | span: `single`

94. [scenario_judgment][direct] 企业在政府采购协议框架下开展业务时，需要遵循哪些原则？
   - expected: `policy_183`
   - top1: `parent_中华人民共和国政府采购法_3_2959_5335`
   - law: `政府采购协议(上)`
   - type: `policy_doc` | span: `single`

95. [scenario_judgment][direct] 企业在协议下的政府采购项目中，如何保障权益？
   - expected: `policy_183`
   - top1: `parent_中华人民共和国政府采购法实施条例_11_12_400`
   - law: `政府采购协议(上)`
   - type: `policy_doc` | span: `single`

96. [scenario_judgment][direct] 政府采购协议对本国企业的支持措施有哪些？
   - expected: `policy_183`
   - top1: `parent_促进残疾人就业政府采购政策的通知_77_4038_9674`
   - law: `政府采购协议(上)`
   - type: `policy_doc` | span: `single`

97. [scenario_judgment][direct] 企业在协议框架内遇到争议怎么办？
   - expected: `policy_183`
   - top1: `parent_中央国家机关政府采购电子卖场管理办法_28_3654_4155`
   - law: `政府采购协议(上)`
   - type: `policy_doc` | span: `single`

98. [scenario_judgment][direct] 机电产品国际招标属于公共资源交易吗？还有其他哪些类型的交易也属于呢？
   - expected: `policy_18`
   - top1: `parent_进一步规范机电产品国际招标投标活动有关规_6_1299_711`
   - law: `国家发展改革委关于印发《全国公共资源交易目录指引》的通知`
   - type: `policy_doc` | span: `single`

99. [responsibility][direct] 我们公司参与政府采购类项目，需要注意哪些政府部门的监管要求？
   - expected: `policy_146`
   - top1: `parent_中华人民共和国政府采购法实施条例_63_68_7528`
   - law: `财政部 公安部 市场监管总局关于开展2026年政府...`
   - type: `policy_doc` | span: `single`

100. [responsibility][direct] 开展政府相关业务时，不同政府部门之间的协作流程是怎样的？
   - expected: `policy_146`
   - top1: `parent_中华人民共和国预算法_62_3197_5369`
   - law: `财政部 公安部 市场监管总局关于开展2026年政府...`
   - type: `policy_doc` | span: `single`

101. [scenario_judgment][direct] 机电产品国际招标属于公共资源交易吗？还有其他哪些类型的交易也属于呢？
   - expected: `policy_18`
   - top1: `parent_进一步规范机电产品国际招标投标活动有关规_6_1299_711`
   - law: `国家发展改革委关于印发《全国公共资源交易目录指引》的通知`
   - type: `policy_doc` | span: `single`

102. [scenario_judgment][scenario] 我们企业在参与政府采购类项目时，需要哪些政府部门监管要求？
   - expected: `policy_146`
   - top1: `parent_中华人民共和国政府采购法实施条例_63_68_7528`
   - law: `财政部 公安部 市场监管总局关于开展2026年政府...`
   - type: `policy_doc` | span: `single`

103. [procedure][direct] 开展政府相关业务时，不同政府部门之间的协作流程是怎样的？
   - expected: `policy_146`
   - top1: `parent_中华人民共和国预算法_62_3197_5369`
   - law: `财政部 公安部 市场监管总局关于开展2026年政府...`
   - type: `policy_doc` | span: `single`

104. [scenario_judgment][scenario] 如果我们的办公设备采购存在违规情况，会有什么法律后果？
   - expected: `policy_137`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_30_3691_5917`
   - law: `中共中央 国务院印发党政机关厉行节约反对浪费条例`
   - type: `policy_doc` | span: `single`

105. [scenario_judgment][scenario] 政府采购项目电子化后，对我们的申报材料有什么新要求吗？
   - expected: `policy_220`
   - top1: `parent_中华人民共和国政府采购法实施条例_22_19_7099`
   - law: `新疆印发《关于实行自治区政府采购项目电子化的通知》`
   - type: `policy_doc` | span: `single`

106. [scenario_judgment][scenario] 如果我们单位作为政府采购方，如何确保电子化流程合规？
   - expected: `policy_220`
   - top1: `parent_中华人民共和国政府采购法实施条例_10_11_3700`
   - law: `新疆印发《关于实行自治区政府采购项目电子化的通知》`
   - type: `policy_doc` | span: `single`

107. [procedure][direct] 我们公司采购工作站需要遵循哪些政府采购程序？
   - expected: `policy_173`
   - top1: `parent_交通运输部部属单位政府采购管理办法_29_3946_7341`
   - law: `财政部 工业和信息化部关于印发《工作站政府采购...`
   - type: `policy_doc` | span: `single`

108. [procedure][direct] 中标后多久必须签订合同？
   - expected: `policy_173`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0625`
   - law: `财政部 工业和信息化部关于印发《工作站政府采购...`
   - type: `policy_doc` | span: `single`

109. [scenario_judgment][direct] 工作站政府采购有什么注意事项？
   - expected: `policy_173`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_4_3699_4327`
   - law: `财政部 工业和信息化部关于印发《工作站政府采购...`
   - type: `policy_doc` | span: `single`

110. [scenario_judgment][direct] 如果工作站政府采购出现违规情况会怎样处理？
   - expected: `policy_173`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_20_3715_9262`
   - law: `财政部 工业和信息化部关于印发《工作站政府采购...`
   - type: `policy_doc` | span: `single`

111. [procedure][direct] 如何确保工作站政府采购符合规定？
   - expected: `policy_173`
   - top1: `parent_交通运输部部属单位政府采购管理办法_41_3958_9251`
   - law: `财政部 工业和信息化部关于印发《工作站政府采购...`
   - type: `policy_doc` | span: `single`

112. [procedure][direct] 公司中标后多久需要在平台上完成合同签订？(假设涉及该政策下的交易)
   - expected: `policy_84`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0625`
   - law: `【综合管理】上海市公共资源交易整合共享工作协调机制关于同意在上海联合产权交易所加`
   - type: `policy_doc` | span: `single`

113. [scenario_judgment][direct] 企业在编制政府采购信息时，需要注意哪些关键要点？
   - expected: `policy_41`
   - top1: `parent_中华人民共和国政府采购法实施条例_15_16_4367`
   - law: `财政部办公厅关于印发《政府采购公告和公示信息格式规范(2020年版)》的通知`
   - type: `policy_doc` | span: `single`

114. [responsibility][direct] 我们公司作为中小企业参与政府采购项目，需要满足哪些条件？
   - expected: `policy_218`
   - top1: `parent_《中华人民共和国中小企业促进法》等有关法_11_3981_2942`
   - law: `北京市财政局关于落实好政府采购支持中小企业发展的通知`
   - type: `policy_doc` | span: `single`

115. [scenario_judgment][direct] 中标后多久需要签订合同？
   - expected: `policy_218`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0625`
   - law: `北京市财政局关于落实好政府采购支持中小企业发展的通知`
   - type: `policy_doc` | span: `single`

116. [scenario_judgment][direct] 支持中小企业发展的采购项目有哪些具体流程？
   - expected: `policy_218`
   - top1: `parent_《中华人民共和国中小企业促进法》等有关法_8_3977_3117`
   - law: `北京市财政局关于落实好政府采购支持中小企业发展的通知`
   - type: `policy_doc` | span: `single`

117. [scenario_judgment][scenario] 企业在做这类采购时需要注意哪些合规要点？
   - expected: `policy_218`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_4_3699_4327`
   - law: `北京市财政局关于落实好政府采购支持中小企业发展的通知`
   - type: `policy_doc` | span: `single`

118. [scenario_judgment][scenario] 如果我们的项目涉及中小企业采购，应该怎么操作更合适？
   - expected: `policy_218`
   - top1: `parent_《中华人民共和国中小企业促进法》等有关法_12_3982_2799`
   - law: `北京市财政局关于落实好政府采购支持中小企业发展的通知`
   - type: `policy_doc` | span: `single`

119. [scenario_judgment][scenario] 政府采购中支持中小企业的政策对我们公司有什么实际帮助？
   - expected: `policy_218`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0246`
   - law: `北京市财政局关于落实好政府采购支持中小企业发展的通知`
   - type: `policy_doc` | span: `single`

120. [scenario_judgment][scenario] 公共资源'一网交易'改革对我们的招标流程有什么影响？
   - expected: `policy_8`
   - top1: `policy_74`
   - law: `关于印发《上海深化公共资源“一网交易”改革三年行动方案（2021-2023年）》`
   - type: `policy_doc` | span: `single`

121. [condition_check][direct] 我们公司的招标项目在'一网交易'平台上办理吗？
   - expected: `policy_8`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_8_4077_3222`
   - law: `关于印发《上海深化公共资源“一网交易”改革三年行动方案（2021-2023年）》`
   - type: `policy_doc` | span: `single`

122. [procedure][direct] 做公共资源项目时，'一网交易'平台的使用指南在哪里？
   - expected: `policy_8`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_5_4074_6582`
   - law: `关于印发《上海深化公共资源“一网交易”改革三年行动方案（2021-2023年）》`
   - type: `policy_doc` | span: `single`

123. [condition_check][direct] 企业参与上海公共资源项目，现在需要通过什么平台操作？
   - expected: `policy_8`
   - top1: `policy_81`
   - law: `关于印发《上海深化公共资源“一网交易”改革三年行动方案（2021-2023年）》`
   - type: `policy_doc` | span: `single`

124. [responsibility][scenario] 企业在公共资源配置项目中遇到问题该如何投诉？
   - expected: `policy_9`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_36_4105_195`
   - law: `信息来源：国家    浏览次数：`
   - type: `policy_doc` | span: `single`

125. [scenario_judgment][scenario] 我们公司想做节能产品相关的政府采购项目，需要满足哪些条件？
   - expected: `policy_155`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0290`
   - law: `市场监管总局关于发布参与实施政府采购节能产品...`
   - type: `policy_doc` | span: `single`

126. [procedure][scenario] 参与政府采购节能产品项目后，合同签订有时间限制吗？
   - expected: `policy_155`
   - top1: `parent_政府购买服务管理办法_24_4362_1067`
   - law: `市场监管总局关于发布参与实施政府采购节能产品...`
   - type: `policy_doc` | span: `single`

127. [scenario_judgment][scenario] 公司在节能产品政府采购中如果违规了会有什么后果？
   - expected: `policy_155`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0290`
   - law: `市场监管总局关于发布参与实施政府采购节能产品...`
   - type: `policy_doc` | span: `single`

128. [definition][direct] 节能产品政府采购的政策主要包含哪些方面？
   - expected: `policy_155`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0290`
   - law: `市场监管总局关于发布参与实施政府采购节能产品...`
   - type: `policy_doc` | span: `single`

129. [procedure][direct] 公司开展节能产品政府采购项目需要注意哪些合规步骤？
   - expected: `policy_155`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0290`
   - law: `市场监管总局关于发布参与实施政府采购节能产品...`
   - type: `policy_doc` | span: `single`

130. [comparison][scenario] 政府采购节能产品的政策与普通政府采购有什么区别？
   - expected: `policy_155`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0290`
   - law: `市场监管总局关于发布参与实施政府采购节能产品...`
   - type: `policy_doc` | span: `single`

131. [scenario_judgment][scenario] 我们公司做拍卖服务业务，需要注意哪些新的政策要求？
   - expected: `policy_76`
   - top1: `policy_114`
   - law: `【拍卖服务】上海市人民政府关于延长《上海市交易场所管理暂行办法》有效期的通知`
   - type: `policy_doc` | span: `single`

132. [scenario_judgment][scenario] 公司参与拍卖服务项目时，需要遵守哪些新的管理规定？
   - expected: `policy_76`
   - top1: `policy_113`
   - law: `【拍卖服务】上海市人民政府关于延长《上海市交易场所管理暂行办法》有效期的通知`
   - type: `policy_doc` | span: `single`

133. [scenario_judgment][scenario] 我们公司作为招标方，组建评标委员会需要注意哪些要求？
   - expected: `policy_20`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0457`
   - law: `评标委员会和评标方法暂行规定`
   - type: `policy_doc` | span: `single`

134. [scenario_judgment][scenario] 评标过程中如果发现违规情况，该怎么处理？
   - expected: `policy_20`
   - top1: `parent_铁路建设工程评标专家库及评标专家管理办法_25_2050_9141`
   - law: `评标委员会和评标方法暂行规定`
   - type: `policy_doc` | span: `single`

135. [scenario_judgment][scenario] 评标结束后如何确定中标人，公司需要关注哪些环节？
   - expected: `policy_20`
   - top1: `parent_政府采购货物和服务招标投标管理办法_68_3433_3506`
   - law: `评标委员会和评标方法暂行规定`
   - type: `policy_doc` | span: `single`

136. [scenario_judgment][scenario] 评标委员会成员构成有什么规定，对我们的招标工作有帮助吗？
   - expected: `policy_20`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0451`
   - law: `评标委员会和评标方法暂行规定`
   - type: `policy_doc` | span: `single`

137. [scenario_judgment][scenario] 评标过程中出现争议应该找哪个部门解决？
   - expected: `policy_20`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0531`
   - law: `评标委员会和评标方法暂行规定`
   - type: `policy_doc` | span: `single`

138. [procedure][direct] 如何提升我们企业的信用记分？
   - expected: `policy_128`
   - top1: `policy_123`
   - law: `【综合采购】上海市公共资源交易中心响应方信用记分评估标准（试行）`
   - type: `policy_doc` | span: `single`

139. [comparison][direct] 不同扣分程度的处罚措施有什么区别？
   - expected: `policy_128`
   - top1: `policy_129`
   - law: `【综合采购】上海市公共资源交易中心响应方信用记分评估标准（试行）`
   - type: `policy_doc` | span: `single`

140. [condition_check][direct] 我们公司在招投标项目中，评标专家的选择有什么要求？
   - expected: `policy_4`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0452`
   - law: `国家发展改革委法规司负责同志就《评标专家和评标专家库管理办法》答记者问`
   - type: `policy_doc` | span: `single`

141. [scenario_judgment][scenario] 评标专家出现违规情况会怎样处理？
   - expected: `policy_4`
   - top1: `parent_铁路建设工程评标专家库及评标专家管理办法_26_2051_7318`
   - law: `国家发展改革委法规司负责同志就《评标专家和评标专家库管理办法》答记者问`
   - type: `policy_doc` | span: `single`

142. [procedure][direct] 评标专家库的使用流程是怎样的？
   - expected: `policy_4`
   - top1: `parent_公路建设项目评标专家库管理办法_17_1633_2690`
   - law: `国家发展改革委法规司负责同志就《评标专家和评标专家库管理办法》答记者问`
   - type: `policy_doc` | span: `single`

143. [definition][direct] 评标专家的资质审核包括哪些方面？
   - expected: `policy_4`
   - top1: `parent_民航专业工程及货物招标投标评标专家和专家_8_2146_6546`
   - law: `国家发展改革委法规司负责同志就《评标专家和评标专家库管理办法》答记者问`
   - type: `policy_doc` | span: `single`

144. [scenario_judgment][scenario] 政府采购协议签订后，我们企业在执行过程中需要注意哪些合规要点？
   - expected: `policy_184`
   - top1: `parent_政府购买服务管理办法_25_4363_3900`
   - law: `政府采购协议(下)`
   - type: `policy_doc` | span: `single`

145. [condition_check][direct] 企业在参与政府采购项目时，需要满足哪些基本资质条件？
   - expected: `policy_184`
   - top1: `parent_中华人民共和国政府采购法实施条例_22_19_7099`
   - law: `政府采购协议(下)`
   - type: `policy_doc` | span: `single`

146. [scenario_judgment][scenario] 政府采购协议签订后，若出现违约情况，应如何处理？
   - expected: `policy_184`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_14_3709_3363`
   - law: `政府采购协议(下)`
   - type: `policy_doc` | span: `single`

147. [procedure][direct] 企业在执行政府采购项目时，需要关注哪些流程环节？
   - expected: `policy_184`
   - top1: `parent_政府购买服务管理办法_19_4356_8473`
   - law: `政府采购协议(下)`
   - type: `policy_doc` | span: `single`

148. [condition_check][direct] 政府采购协议中的价格条款如何执行？
   - expected: `policy_184`
   - top1: `parent_政府采购框架协议采购方式管理暂行办法_13_4254_8399`
   - law: `政府采购协议(下)`
   - type: `policy_doc` | span: `single`

149. [scenario_judgment][scenario] 财政厅的举措对公司中标后运营有什么影响？
   - expected: `policy_216`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0679`
   - law: `新疆维吾尔自治区财政厅：持续加强“...`
   - type: `policy_doc` | span: `single`

150. [scenario_judgment][scenario] 我们公司在业务中涉及国家安全相关内容，需要特别注意什么？
   - expected: `policy_201`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0122`
   - law: `中华人民共和国国家安全法`
   - type: `policy_doc` | span: `single`

151. [scenario_judgment][direct] 国家安全法对企业运营的限制有哪些？
   - expected: `policy_201`
   - top1: `parent_政府采购进口产品管理办法_27_4068_1592`
   - law: `中华人民共和国国家安全法`
   - type: `policy_doc` | span: `single`

152. [scenario_judgment][direct] 如果我们在政府采购中有失信行为，会怎么样？
   - expected: `policy_37`
   - top1: `parent_严重违法失信行为信息记录的通知_78_4399_2219`
   - law: `财政部关于在政府采购活动中查询及使用信用记录有关问题的通知`
   - type: `policy_doc` | span: `single`

153. [scenario_judgment][scenario] 我们公司想做政府购买服务项目，需要先了解哪些流程和注意事项？
   - expected: `policy_212`
   - top1: `parent_政府购买服务管理办法_16_4353_5607`
   - law: `坚定改革信心 走深走实北京政府购买服...`
   - type: `policy_doc` | span: `single`

154. [procedure][direct] 我们公司参与政府购买服务后，如何保障预算绩效？
   - expected: `policy_212`
   - top1: `parent_政府购买服务管理办法_20_4357_6874`
   - law: `坚定改革信心 走深走实北京政府购买服...`
   - type: `policy_doc` | span: `single`

155. [procedure][direct] 我和对方有合同纠纷，应该怎么申请仲裁？
   - expected: `policy_198`
   - top1: `parent_中央国家机关政府采购电子卖场管理办法_23_3649_2626`
   - law: `中华人民共和国仲裁法`
   - type: `policy_doc` | span: `single`

156. [procedure][direct] 申请仲裁前我需要做哪些准备工作？
   - expected: `policy_198`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_23_3852_6178`
   - law: `中华人民共和国仲裁法`
   - type: `policy_doc` | span: `single`

157. [condition_check][direct] 如果我想撤销仲裁裁决，需要满足什么条件？
   - expected: `policy_198`
   - top1: `parent_中华人民共和国预算法_81_3218_3668`
   - law: `中华人民共和国仲裁法`
   - type: `policy_doc` | span: `single`

158. [scenario_judgment][direct] 仲裁过程中我的合法权益如何得到保护？
   - expected: `policy_198`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0621`
   - law: `中华人民共和国仲裁法`
   - type: `policy_doc` | span: `single`

159. [procedure][direct] 公共资源交易项目出现争议时，应该如何投诉或申诉？
   - expected: `policy_14`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_36_4105_195`
   - law: `上海市人民政府办公厅关于印发《整合建立本市统一公共资源交易平台实施方案》的通知`
   - type: `policy_doc` | span: `single`

160. [scenario_judgment][direct] 我们在做公共资源交易项目时，需要注意哪些合规要点？
   - expected: `policy_14`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_11_4080_1566`
   - law: `上海市人民政府办公厅关于印发《整合建立本市统一公共资源交易平台实施方案》的通知`
   - type: `policy_doc` | span: `single`

161. [scenario_judgment][scenario] 公共资源交易的电子化实施对企业操作有何影响？
   - expected: `policy_14`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_45_4116_2787`
   - law: `上海市人民政府办公厅关于印发《整合建立本市统一公共资源交易平台实施方案》的通知`
   - type: `policy_doc` | span: `single`

162. [scenario_judgment][scenario] 我们企业在做工程总承包项目时，需要注意哪些合规要点？
   - expected: `policy_208`
   - top1: `parent_事业项目范围规定》实施工作的通知_2_389_1431`
   - law: `海岱雄秀 数治山东 ——齐鲁政采绘就...`
   - type: `policy_doc` | span: `single`

163. [scenario_judgment][scenario] 如果我们在山东政府采购项目中出现违规，会有怎样的处罚？
   - expected: `policy_208`
   - top1: `parent_中华人民共和国政府采购法实施条例_72_72_1748`
   - law: `海岱雄秀 数治山东 ——齐鲁政采绘就...`
   - type: `policy_doc` | span: `single`

164. [scenario_judgment][scenario] 企业在执行住建部工程总承包项目时，如何避免法律风险？
   - expected: `policy_157`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0151`
   - law: `住房城乡建设部办公厅关于工程总承包项目和政府...`
   - type: `policy_doc` | span: `single`

165. [scenario_judgment][scenario] 工程总承包项目在政府项目中如何保障中小企业权益？
   - expected: `policy_157`
   - top1: `parent_《中华人民共和国中小企业促进法》等有关法_4_3973_1234`
   - law: `住房城乡建设部办公厅关于工程总承包项目和政府...`
   - type: `policy_doc` | span: `single`

166. [scenario_judgment][scenario] 如果评审专家存在违规行为，我们企业该怎么应对？
   - expected: `policy_210`
   - top1: `parent_政府采购评审专家管理办法_28_3559_8632`
   - law: `山东推行评审专家联合惩戒机制`
   - type: `policy_doc` | span: `single`

167. [scenario_judgment][scenario] 企业参与山东政府采购项目时，评审专家的选择标准是什么？
   - expected: `policy_210`
   - top1: `parent_政府采购竞争性磋商采购方式管理暂行办法_3_4139_6636`
   - law: `山东推行评审专家联合惩戒机制`
   - type: `policy_doc` | span: `single`

168. [scenario_judgment][scenario] 如果供应商提供的声明存在虚假情况，会有什么后果？
   - expected: `policy_115`
   - top1: `parent_《中华人民共和国中小企业促进法》等有关法_20_3990_3608`
   - law: `【政府采购】关于简化政府采购供应商资格审查有关事项的通知`
   - type: `policy_doc` | span: `single`

169. [scenario_judgment][scenario] 我们公司作为投标人，在政府采购项目中如何落实对中小企业支持的政策？
   - expected: `policy_167`
   - top1: `parent_政府采购货物和服务招标投标管理办法_5_3363_5617`
   - law: `北京市财政局关于落实好政府采购支持中小企业发...`
   - type: `policy_doc` | span: `single`

170. [scenario_judgment][scenario] 我们公司在执行政府采购项目时，对中小企业合作的政策程序是怎样的？
   - expected: `policy_167`
   - top1: `parent_《中华人民共和国中小企业促进法》等有关法_8_3977_3117`
   - law: `北京市财政局关于落实好政府采购支持中小企业发...`
   - type: `policy_doc` | span: `single`

171. [scenario_judgment][scenario] 若我们在政府采购中出现失信情况，后续如何处理以恢复信誉？
   - expected: `policy_219`
   - top1: `parent_严重违法失信行为信息记录的通知_78_4399_2219`
   - law: `山西省财政厅关于印发《政府采购失信行为管理暂行办法...`
   - type: `policy_doc` | span: `single`

172. [scenario_judgment][scenario] 在政府购买服务合同执行过程中，如何保证合规性？
   - expected: `policy_141`
   - top1: `parent_政府购买服务管理办法_28_4366_1085`
   - law: `中华人民共和国财政部令第102号《政府购买服务管...`
   - type: `policy_doc` | span: `single`

173. [scenario_judgment][scenario] 如果我们的政府购买服务项目出现纠纷，该找哪个部门解决？
   - expected: `policy_141`
   - top1: `parent_中央国家机关政府采购电子卖场管理办法_23_3649_2626`
   - law: `中华人民共和国财政部令第102号《政府购买服务管...`
   - type: `policy_doc` | span: `single`

174. [scenario_judgment][scenario] 我们公司想开展政府购买服务项目，需要先了解什么前期准备？
   - expected: `policy_141`
   - top1: `parent_政府购买服务管理办法_20_4357_6874`
   - law: `中华人民共和国财政部令第102号《政府购买服务管...`
   - type: `policy_doc` | span: `single`

175. [scenario_judgment][scenario] 政府购买服务项目的验收标准通常有哪些？
   - expected: `policy_141`
   - top1: `parent_《中华人民共和国政府采购法实施条例》等有_24_4015_7724`
   - law: `中华人民共和国财政部令第102号《政府购买服务管...`
   - type: `policy_doc` | span: `single`

176. [procedure][scenario] 企业作为政府购买服务供应商，需要遵守哪些关键时间节点？
   - expected: `policy_141`
   - top1: `parent_政府购买服务管理办法_6_4343_6400`
   - law: `中华人民共和国财政部令第102号《政府购买服务管...`
   - type: `policy_doc` | span: `single`

177. [scenario_judgment][scenario] 开展政府购买服务项目对企业资质有什么影响？
   - expected: `policy_141`
   - top1: `parent_政府购买服务管理办法_20_4357_6874`
   - law: `中华人民共和国财政部令第102号《政府购买服务管...`
   - type: `policy_doc` | span: `single`

178. [procedure][scenario] 我们公司想开展产权交易项目合作，需要遵循哪些具体流程？
   - expected: `policy_67`
   - top1: `policy_55`
   - law: `【国有产权】市国资委关于延长上海市产权交易场所管理实施办法(暂行)有效期的通知`
   - type: `policy_doc` | span: `single`

179. [scenario_judgment][scenario] 如果在产权交易中出现违规操作，会有怎样的处罚措施？
   - expected: `policy_67`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_18_4109_5696`
   - law: `【国有产权】市国资委关于延长上海市产权交易场所管理实施办法(暂行)有效期的通知`
   - type: `policy_doc` | span: `single`

180. [condition_check][direct] 我们公司想要入驻产权交易相关平台，需要满足什么基本条件？
   - expected: `policy_67`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_8_4077_3222`
   - law: `【国有产权】市国资委关于延长上海市产权交易场所管理实施办法(暂行)有效期的通知`
   - type: `policy_doc` | span: `single`

181. [definition][direct] 英国政府采购制度中对环保产品的优先级是怎样的？
   - expected: `policy_187`
   - top1: `parent_交通运输部部属单位政府采购管理办法_33_3950_5324`
   - law: `英国政府采购制度（上）`
   - type: `policy_doc` | span: `single`

182. [responsibility][direct] 我们公司在国际项目中涉及英国政府采购，需要遵守哪些规定？
   - expected: `policy_187`
   - top1: `parent_中华人民共和国政府采购法_84_3043_8912`
   - law: `英国政府采购制度（上）`
   - type: `policy_doc` | span: `single`

183. [responsibility][direct] 如果我们的铁路建设项目中标后，应该找哪个部门办理相关手续呢？
   - expected: `policy_131`
   - top1: `parent_铁路建设工程招标投标监管暂行办法_10_2066_2437`
   - law: `【交通系统】关于在上海市公共资源交易中心开展中国铁路上海局集团有限公司铁路建设项`
   - type: `policy_doc` | span: `single`

184. [procedure][direct] 我们公司中标后多久必须签合同？
   - expected: `policy_131`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0625`
   - law: `【交通系统】关于在上海市公共资源交易中心开展中国铁路上海局集团有限公司铁路建设项`
   - type: `policy_doc` | span: `single`

185. [scenario_judgment][scenario] 如果我们的企业在参与过程中不符合条件，会有什么后果？
   - expected: `policy_60`
   - top1: `parent_出口商品配额招标办法_36_2765_9454`
   - law: `财政部、民政部、中国残疾人联合会关于促进残疾人就业政府采购政策的通知`
   - type: `policy_doc` | span: `single`

186. [case_reasoning][synonym] 如果我们公司遇到行政争议，可以通过什么法律途径解决？
   - expected: `policy_199`
   - top1: `parent_监督处理中华人民共和国行政处罚法_25_841_1502`
   - law: `中华人民共和国行政诉讼法`
   - type: `policy_doc` | span: `single`

187. [procedure][direct] 我们公司想了解行政诉讼的基本流程是怎样的？
   - expected: `policy_199`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0713`
   - law: `中华人民共和国行政诉讼法`
   - type: `policy_doc` | span: `single`

188. [responsibility][direct] 如果我们的案件涉及行政诉讼，应该找哪个法院管辖？
   - expected: `policy_199`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0713`
   - law: `中华人民共和国行政诉讼法`
   - type: `policy_doc` | span: `single`

189. [procedure][scenario] 当我们的企业与政府部门发生纠纷时，应该先做哪些准备工作？
   - expected: `policy_199`
   - top1: `parent_中央国家机关政府采购电子卖场管理办法_23_3649_2626`
   - law: `中华人民共和国行政诉讼法`
   - type: `policy_doc` | span: `single`

190. [responsibility][direct] 我们公司中标后，应该找哪个部门办理相关手续？
   - expected: `policy_131`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0157`
   - law: `【交通系统】关于在上海市公共资源交易中心开展中国铁路上海局集团有限公司铁路建设项`
   - type: `policy_doc` | span: `single`

191. [procedure][direct] 我们公司中标后多久必须签合同？
   - expected: `policy_131`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0625`
   - law: `【交通系统】关于在上海市公共资源交易中心开展中国铁路上海局集团有限公司铁路建设项`
   - type: `policy_doc` | span: `single`

192. [scenario_judgment][scenario] 我们公司作为普通企业，想知道如何能获得这类政府采购的支持？
   - expected: `policy_60`
   - top1: `parent_《中华人民共和国中小企业促进法》等有关法_4_3973_1234`
   - law: `财政部、民政部、中国残疾人联合会关于促进残疾人就业政府采购政策的通知`
   - type: `policy_doc` | span: `single`

193. [scenario_judgment][scenario] 如果我们在参与过程中不符合条件，会有什么后果？
   - expected: `policy_60`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0715`
   - law: `财政部、民政部、中国残疾人联合会关于促进残疾人就业政府采购政策的通知`
   - type: `policy_doc` | span: `single`

194. [definition][direct] 当我们公司与政府部门发生行政争议时，可以通过什么法律途径解决？
   - expected: `policy_199`
   - top1: `parent_监督处理中华人民共和国行政处罚法_25_841_1502`
   - law: `中华人民共和国行政诉讼法`
   - type: `policy_doc` | span: `single`

195. [procedure][scenario] 当企业与政府部门发生纠纷时，应该先做哪些准备工作？
   - expected: `policy_199`
   - top1: `parent_中央国家机关政府采购电子卖场管理办法_23_3649_2626`
   - law: `中华人民共和国行政诉讼法`
   - type: `policy_doc` | span: `single`

196. [responsibility][direct] 如果我们的案件涉及行政诉讼，应该找哪个法院管辖？
   - expected: `policy_199`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0713`
   - law: `中华人民共和国行政诉讼法`
   - type: `policy_doc` | span: `single`

197. [procedure][direct] 我们想了解行政诉讼的基本流程是怎样的？
   - expected: `policy_199`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0017`
   - law: `中华人民共和国行政诉讼法`
   - type: `policy_doc` | span: `single`

198. [responsibility][direct] 中标后应该找哪个部门办理相关手续？
   - expected: `policy_131`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0157`
   - law: `【交通系统】关于在上海市公共资源交易中心开展中国铁路上海局集团有限公司铁路建设项`
   - type: `policy_doc` | span: `single`

199. [procedure][direct] 中标后多久必须签合同？
   - expected: `policy_131`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0625`
   - law: `【交通系统】关于在上海市公共资源交易中心开展中国铁路上海局集团有限公司铁路建设项`
   - type: `policy_doc` | span: `single`

200. [responsibility][direct] 参与这类政府采购要先联系哪个部门？
   - expected: `policy_60`
   - top1: `parent_政府采购质疑和投诉办法_7_3463_4857`
   - law: `财政部、民政部、中国残疾人联合会关于促进残疾人就业政府采购政策的通知`
   - type: `policy_doc` | span: `single`

201. [scenario_judgment][direct] 不符合条件的话会有什么后果？
   - expected: `policy_60`
   - top1: `parent_建筑工程施工许可管理办法_16_1199_9426`
   - law: `财政部、民政部、中国残疾人联合会关于促进残疾人就业政府采购政策的通知`
   - type: `policy_doc` | span: `single`

202. [scenario_judgment][scenario] 普通企业如何能获得这类政府采购的支持？
   - expected: `policy_60`
   - top1: `parent_《中华人民共和国中小企业促进法》等有关法_4_3973_1234`
   - law: `财政部、民政部、中国残疾人联合会关于促进残疾人就业政府采购政策的通知`
   - type: `policy_doc` | span: `single`

203. [case_reasoning][scenario] 这类政策对我们企业的业务意味着什么？
   - expected: `policy_60`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0239`
   - law: `财政部、民政部、中国残疾人联合会关于促进残疾人就业政府采购政策的通知`
   - type: `policy_doc` | span: `single`

204. [procedure][scenario] 行政争议解决前的准备工作有哪些？
   - expected: `policy_199`
   - top1: `parent_监督处理中华人民共和国行政处罚法_25_841_1502`
   - law: `中华人民共和国行政诉讼法`
   - type: `policy_doc` | span: `single`

205. [definition][direct] 当我们公司与政府部门发生行政争议时，可以通过什么法律途径解决？
   - expected: `policy_199`
   - top1: `parent_监督处理中华人民共和国行政处罚法_25_841_1502`
   - law: `中华人民共和国行政诉讼法`
   - type: `policy_doc` | span: `single`

206. [procedure][direct] 行政诉讼需要准备哪些证据？
   - expected: `policy_199`
   - top1: `parent_监督处理中华人民共和国行政处罚法_46_862_4732`
   - law: `中华人民共和国行政诉讼法`
   - type: `policy_doc` | span: `single`

207. [procedure][direct] 行政诉讼的基本流程是怎样的？
   - expected: `policy_199`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0017`
   - law: `中华人民共和国行政诉讼法`
   - type: `policy_doc` | span: `single`

208. [responsibility][direct] 行政诉讼应由哪个法院管辖？
   - expected: `policy_199`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0713`
   - law: `中华人民共和国行政诉讼法`
   - type: `policy_doc` | span: `single`

209. [responsibility][direct] 中标后应该找哪个部门办理相关手续？
   - expected: `policy_131`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0157`
   - law: `【交通系统】关于在上海市公共资源交易中心开展中国铁路上海局集团有限公司铁路建设项`
   - type: `policy_doc` | span: `single`

210. [procedure][scenario] 中标后多久必须签合同？
   - expected: `policy_131`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0625`
   - law: `【交通系统】关于在上海市公共资源交易中心开展中国铁路上海局集团有限公司铁路建设项`
   - type: `policy_doc` | span: `single`

211. [responsibility][direct] 参与这类政府采购要先联系哪个部门？
   - expected: `policy_60`
   - top1: `parent_政府采购质疑和投诉办法_7_3463_4857`
   - law: `财政部、民政部、中国残疾人联合会关于促进残疾人就业政府采购政策的通知`
   - type: `policy_doc` | span: `single`

212. [scenario_judgment][synonym] 普通企业如何能获得这类政府采购的支持？
   - expected: `policy_60`
   - top1: `parent_《中华人民共和国中小企业促进法》等有关法_4_3973_1234`
   - law: `财政部、民政部、中国残疾人联合会关于促进残疾人就业政府采购政策的通知`
   - type: `policy_doc` | span: `single`

213. [scenario_judgment][synonym] 不符合条件的话会有什么后果？
   - expected: `policy_60`
   - top1: `parent_建筑工程施工许可管理办法_16_1199_9426`
   - law: `财政部、民政部、中国残疾人联合会关于促进残疾人就业政府采购政策的通知`
   - type: `policy_doc` | span: `single`

214. [case_reasoning][synonym] 这类政策对我们企业的业务意味着什么？
   - expected: `policy_60`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0239`
   - law: `财政部、民政部、中国残疾人联合会关于促进残疾人就业政府采购政策的通知`
   - type: `policy_doc` | span: `single`

215. [procedure][direct] 行政争议解决前的准备工作有哪些？
   - expected: `policy_199`
   - top1: `parent_监督处理中华人民共和国行政处罚法_25_841_1502`
   - law: `中华人民共和国行政诉讼法`
   - type: `policy_doc` | span: `single`

216. [scenario_judgment][direct] 当我们公司与政府部门发生行政争议时，可以通过什么法律途径解决？
   - expected: `policy_199`
   - top1: `parent_监督处理中华人民共和国行政处罚法_25_841_1502`
   - law: `中华人民共和国行政诉讼法`
   - type: `policy_doc` | span: `single`

217. [responsibility][direct] 行政诉讼应由哪个法院管辖？
   - expected: `policy_199`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0713`
   - law: `中华人民共和国行政诉讼法`
   - type: `policy_doc` | span: `single`

218. [procedure][direct] 行政诉讼需要准备哪些证据？
   - expected: `policy_199`
   - top1: `parent_监督处理中华人民共和国行政处罚法_46_862_4732`
   - law: `中华人民共和国行政诉讼法`
   - type: `policy_doc` | span: `single`

219. [procedure][direct] 行政诉讼的基本流程是怎样的？
   - expected: `policy_199`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0017`
   - law: `中华人民共和国行政诉讼法`
   - type: `policy_doc` | span: `single`

220. [responsibility][direct] 我们公司想入驻政府采购电子卖场，需要满足什么条件？
   - expected: `policy_206`
   - top1: `parent_中央国家机关政府采购电子卖场管理办法_7_3633_2582`
   - law: `财政部 市场监管总局关于推进地方政府...`
   - type: `policy_doc` | span: `single`

221. [comparison][direct] 电子卖场的采购流程和我们传统采购方式相比有什么不同？
   - expected: `policy_206`
   - top1: `parent_中央国家机关政府采购电子卖场管理办法_20_3646_3690`
   - law: `财政部 市场监管总局关于推进地方政府...`
   - type: `policy_doc` | span: `single`

222. [scenario_judgment][direct] 如果我们在电子卖场中标后，合同签订有时间限制吗？
   - expected: `policy_206`
   - top1: `parent_中华人民共和国政府采购法_46_3003_3920`
   - law: `财政部 市场监管总局关于推进地方政府...`
   - type: `policy_doc` | span: `single`

223. [scenario_judgment][direct] '一网交易'改革后，中小企业在项目中有什么新的机会？
   - expected: `policy_0`
   - top1: `policy_74`
   - law: `关于印发《上海市深化公共资源“一网交易”改革三年行动方案（2024-2026年）`
   - type: `policy_doc` | span: `single`

224. [scenario_judgment][direct] 上海公共资源‘一网交易’改革后，我们公司的项目申报流程变简单了吗？
   - expected: `policy_0`
   - top1: `policy_74`
   - law: `关于印发《上海市深化公共资源“一网交易”改革三年行动方案（2024-2026年）`
   - type: `policy_doc` | span: `single`

225. [responsibility][direct] 公司在招标投标中遇到违规行为，该找哪个部门投诉？
   - expected: `policy_2`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0686`
   - law: `国务院办公厅关于创新完善体制机制推动招标投标市场规范健康发展的意见`
   - type: `policy_doc` | span: `single`

226. [procedure][direct] ‘一网交易’改革后，我们公司如何更方便地使用各资源交易平台？
   - expected: `policy_0`
   - top1: `policy_74`
   - law: `关于印发《上海市深化公共资源“一网交易”改革三年行动方案（2024-2026年）`
   - type: `policy_doc` | span: `single`

227. [procedure][direct] 招标投标数字化改革后，我们的投标流程有什么变化？
   - expected: `policy_2`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0060`
   - law: `国务院办公厅关于创新完善体制机制推动招标投标市场规范健康发展的意见`
   - type: `policy_doc` | span: `single`

228. [scenario_judgment][direct] 这种招标项目如果违规会有什么处罚？
   - expected: `policy_156`
   - top1: `parent_出口商品配额招标办法_38_2767_4966`
   - law: `国家发展改革委关于印发《必须招标的基础设施和...`
   - type: `policy_doc` | span: `single`

229. [procedure][direct] 我们公司准备开展基础设施招标项目，需要先做什么准备工作？
   - expected: `policy_156`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0140`
   - law: `国家发展改革委关于印发《必须招标的基础设施和...`
   - type: `policy_doc` | span: `single`

230. [procedure][direct] 做这类招标项目需要多长时间？
   - expected: `policy_156`
   - top1: `parent_工程建设项目施工招标投标办法_31_33_5342`
   - law: `国家发展改革委关于印发《必须招标的基础设施和...`
   - type: `policy_doc` | span: `single`

231. [scenario_judgment][direct] 我们公司在招标过程中发现违规行为该如何处理？
   - expected: `policy_156`
   - top1: `parent_出口商品配额招标办法_38_2767_4966`
   - law: `国家发展改革委关于印发《必须招标的基础设施和...`
   - type: `policy_doc` | span: `single`

232. [scenario_judgment][direct] 如果中标后没及时签合同会怎样？
   - expected: `policy_156`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0625`
   - law: `国家发展改革委关于印发《必须招标的基础设施和...`
   - type: `policy_doc` | span: `single`

233. [procedure][direct] 中标后多久必须签订合同？
   - expected: `policy_156`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0625`
   - law: `国家发展改革委关于印发《必须招标的基础设施和...`
   - type: `policy_doc` | span: `single`

234. [scenario_judgment][direct] 开展这类招标项目有哪些注意事项？
   - expected: `policy_156`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0122`
   - law: `国家发展改革委关于印发《必须招标的基础设施和...`
   - type: `policy_doc` | span: `single`

235. [scenario_judgment][direct] 做技术交易项目需要注意哪些合规要求？
   - expected: `policy_87`
   - top1: `policy_95`
   - law: `【技术交易】上海技术交易所交易档案管理暂行办法`
   - type: `policy_doc` | span: `single`

236. [scenario_judgment][scenario] 工程建设项目招标需要多长时间？
   - expected: `policy_7`
   - top1: `parent_工程建设项目施工招标投标办法_31_33_5342`
   - law: `中华人民共和国招标投标法实施条例`
   - type: `policy_doc` | span: `single`

237. [scenario_judgment][scenario] 做工程建设项目招标需要注意哪些合规要求？
   - expected: `policy_7`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0151`
   - law: `中华人民共和国招标投标法实施条例`
   - type: `policy_doc` | span: `single`

238. [scenario_judgment][scenario] 工程建设项目招标违规会有什么法律后果？
   - expected: `policy_7`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0116`
   - law: `中华人民共和国招标投标法实施条例`
   - type: `policy_doc` | span: `single`

239. [scenario_judgment][scenario] 中标后未及时签订合同会有什么后果？
   - expected: `policy_7`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0639`
   - law: `中华人民共和国招标投标法实施条例`
   - type: `policy_doc` | span: `single`

240. [scenario_judgment][scenario] 工程建设项目招标有哪些注意事项？
   - expected: `policy_7`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0151`
   - law: `中华人民共和国招标投标法实施条例`
   - type: `policy_doc` | span: `single`

241. [procedure][direct] 工程建设项目招标中如何保障公平性？
   - expected: `policy_7`
   - top1: `parent_工程建设项目施工招标投标办法_4_4_7577`
   - law: `中华人民共和国招标投标法实施条例`
   - type: `policy_doc` | span: `single`

242. [procedure][direct] 工程建设项目招标违规后如何整改？
   - expected: `policy_7`
   - top1: `parent_工程建设项目施工招标投标办法_68_70_4296`
   - law: `中华人民共和国招标投标法实施条例`
   - type: `policy_doc` | span: `single`

243. [procedure][direct] 如果我们公司要使用这个新的公共资源交易平台，需要提前做好哪些准备工作？
   - expected: `policy_11`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_48_4119_8963`
   - law: `上海市发展和改革委员会关于印发《上海市公共资源交易平台升级改造工作方案》的通知`
   - type: `policy_doc` | span: `single`

244. [definition][direct] 信用记分的满分和扣分等级是如何规定的？
   - expected: `policy_132`
   - top1: `policy_129`
   - law: `【综合采购】上海市公共资源交易中心发起方信用记分评估标准（试行）`
   - type: `policy_doc` | span: `single`

245. [scenario_judgment][scenario] 信用记分结果会对我们的投标产生影响吗？
   - expected: `policy_132`
   - top1: `parent_设计施工总承包招标的评标采用综合评分法_69_1488_4775`
   - law: `【综合采购】上海市公共资源交易中心发起方信用记分评估标准（试行）`
   - type: `policy_doc` | span: `single`

246. [scenario_judgment][scenario] 如果我们的交易行为被扣分了，应该如何处理？
   - expected: `policy_72`
   - top1: `policy_129`
   - law: `关于印发《上海市公共资源场内交易信用记分管理办法》的通知`
   - type: `policy_doc` | span: `single`

247. [procedure][direct] 中标后签署政务信息系统采购合同的期限一般是多久？
   - expected: `policy_34`
   - top1: `parent_政务信息系统政府采购管理暂行办法_16_3357_6856`
   - law: `财政部关于印发《政务信息系统政府采购管理暂行办法》的通知`
   - type: `policy_doc` | span: `single`

248. [scenario_judgment][scenario] 我们公司要做政务信息系统项目，需要遵循哪些政府采购流程？
   - expected: `policy_34`
   - top1: `parent_政务信息系统政府采购管理暂行办法_4_3345_5605`
   - law: `财政部关于印发《政务信息系统政府采购管理暂行办法》的通知`
   - type: `policy_doc` | span: `single`

249. [procedure][direct] 企业在政务信息系统采购中需要提供哪些资质证明材料？
   - expected: `policy_34`
   - top1: `parent_中华人民共和国政府采购法实施条例_22_19_7099`
   - law: `财政部关于印发《政务信息系统政府采购管理暂行办法》的通知`
   - type: `policy_doc` | span: `single`

250. [procedure][direct] 当我们公司中标项目后需要安排评标，怎么确定评标专家？
   - expected: `policy_28`
   - top1: `parent_评标委员会和评标方法暂行规定_10_401_4260`
   - law: `评标专家和评标专家库管理办法`
   - type: `policy_doc` | span: `single`

251. [condition_check][direct] 评标专家的选聘条件有哪些？
   - expected: `policy_28`
   - top1: `parent_评标专家和评标专家库管理暂行办法_7_462_6660`
   - law: `评标专家和评标专家库管理办法`
   - type: `policy_doc` | span: `single`

252. [condition_check][direct] 政府采购中促进中小企业发展的政策主要针对哪些采购环节？
   - expected: `policy_163`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0289`
   - law: `财政部发布《政府采购促进中小企业发展政策问答》`
   - type: `policy_doc` | span: `single`

253. [procedure][direct] 中小企业在政府采购中遇到投诉问题该怎么处理？
   - expected: `policy_163`
   - top1: `parent_《中华人民共和国中小企业促进法》等有关法_16_3986_9220`
   - law: `财政部发布《政府采购促进中小企业发展政策问答》`
   - type: `policy_doc` | span: `single`

254. [case_reasoning][scenario] 评标专家库的组建和共享对实际业务意味着什么？
   - expected: `policy_164`
   - top1: `policy_28`
   - law: `安徽省财政厅 安徽省工业和信息化厅关于在政府采...`
   - type: `policy_doc` | span: `single`

255. [scenario_judgment][scenario] 我们企业在政府采采购项目时，需要注意哪些合规要点？
   - expected: `policy_164`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0289`
   - law: `安徽省财政厅 安徽省工业和信息化厅关于在政府采...`
   - type: `policy_doc` | span: `single`

256. [responsibility][cross_reference] 政府在采购项目中组建评标专家库需要哪些部门配合？
   - expected: `policy_164`
   - top1: `parent_评标专家和评标专家库管理暂行办法_6_461_4185`
   - law: `安徽省财政厅 安徽省工业和信息化厅关于在政府采...`
   - type: `policy_doc` | span: `single`

257. [procedure][scenario] 如果我们公司中标后，评标专家库的使用需要注意哪些事项？
   - expected: `policy_6`
   - top1: `parent_系统工程综合评标专家库管理办法_9_1894_6479`
   - law: `《评标专家和评标专家库管理办法》 2024年第26号令`
   - type: `policy_doc` | span: `single`

258. [scenario_judgment][direct] 评标专家和评标专家库管理办法对我们的招标工作流程有何影响？
   - expected: `policy_6`
   - top1: `policy_28`
   - law: `《评标专家和评标专家库管理办法》 2024年第26号令`
   - type: `policy_doc` | span: `single`

259. [procedure][direct] 我们公司参与招标项目时，评标专家抽取和使用的相关规定有哪些？
   - expected: `policy_6`
   - top1: `parent_进一步规范机电产品国际招标投标活动有关规_51_1347_5859`
   - law: `《评标专家和评标专家库管理办法》 2024年第26号令`
   - type: `policy_doc` | span: `single`

260. [condition_check][direct] 企业在招标项目评标阶段，评标专家的选择标准是什么？
   - expected: `policy_6`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0452`
   - law: `《评标专家和评标专家库管理办法》 2024年第26号令`
   - type: `policy_doc` | span: `single`

261. [responsibility][direct] 我们公司参与竞争性磋商项目时，遇到供应商不足的情况该向谁咨询？
   - expected: `policy_45`
   - top1: `parent_政府采购竞争性磋商采购方式管理暂行办法_17_4142_7325`
   - law: `财政部关于政府采购竞争性磋商采购方式管理暂行办法有关问题的补充通知`
   - type: `policy_doc` | span: `single`

262. [scenario_judgment][direct] 中标后如果出现信用问题会怎样处理？
   - expected: `policy_69`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0622`
   - law: `【综合管理】关于印发《上海市公共资源场内交易信用记分管理办法（试行）》的通知`
   - type: `policy_doc` | span: `single`

263. [condition_check][direct] 我们要邀请专家参与评标，需要满足什么条件？
   - expected: `policy_130`
   - top1: `parent_评标委员会和评标方法暂行规定_11_402_4204`
   - law: `【综合采购】上海市公共资源交易中心综合采购专家库管理实施规则(试行)`
   - type: `policy_doc` | span: `single`

264. [responsibility][direct] 专家抽取和管理由哪个部门负责？
   - expected: `policy_130`
   - top1: `parent_政府采购评审专家管理办法_12_3542_4707`
   - law: `【综合采购】上海市公共资源交易中心综合采购专家库管理实施规则(试行)`
   - type: `policy_doc` | span: `single`

265. [procedure][direct] 我们公司想加入专家库需要怎么做？
   - expected: `policy_130`
   - top1: `parent_评标专家和评标专家库管理暂行办法_9_465_9475`
   - law: `【综合采购】上海市公共资源交易中心综合采购专家库管理实施规则(试行)`
   - type: `policy_doc` | span: `single`

266. [scenario_judgment][direct] 不同类型的工程招标对应哪个平台？
   - expected: `policy_102`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_8_4077_3222`
   - law: `【建设工程】材料设备电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

267. [procedure][direct] 企业如何使用这些平台进行招标？
   - expected: `policy_102`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0078`
   - law: `【建设工程】材料设备电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

268. [condition_check][direct] 这些平台是否支持电子招标投标？
   - expected: `policy_102`
   - top1: `parent_电子招标投标办法_3_696_101`
   - law: `【建设工程】材料设备电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

269. [procedure][scenario] 我们公司准备开展金融企业非上市国有产权交易，需要提前做好哪些准备工作？
   - expected: `policy_139`
   - top1: `policy_30`
   - law: `国务院办公厅关于印发《政府采购领域“整顿市场...`
   - type: `policy_doc` | span: `single`

270. [scenario_judgment][scenario] 我们公司作为金融企业，在非上市国有产权交易中，选择合适的产权交易机构有哪些要点？
   - expected: `policy_139`
   - top1: `policy_30`
   - law: `国务院办公厅关于印发《政府采购领域“整顿市场...`
   - type: `policy_doc` | span: `single`

271. [scenario_judgment][scenario] 在金融企业非上市国有产权交易过程中，若发现交易存在违规行为，应该如何处理？
   - expected: `policy_139`
   - top1: `policy_30`
   - law: `国务院办公厅关于印发《政府采购领域“整顿市场...`
   - type: `policy_doc` | span: `single`

272. [procedure][scenario] 金融企业非上市国有产权交易完成后，后续还需要关注哪些法律事务？
   - expected: `policy_139`
   - top1: `policy_30`
   - law: `国务院办公厅关于印发《政府采购领域“整顿市场...`
   - type: `policy_doc` | span: `single`

273. [procedure][scenario] 我们公司参与建设工程施工电子招标投标，需要了解哪些关键的投标流程？
   - expected: `policy_101`
   - top1: `parent_电子招标投标办法_24_717_8229`
   - law: `【建设工程】施工电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

274. [procedure][direct] 施工电子招标投标结束后，我们该如何获取中标结果？
   - expected: `policy_101`
   - top1: `parent_电子招标投标办法_36_729_9259`
   - law: `【建设工程】施工电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

275. [scenario_judgment][scenario] 在施工电子招标投标中，如果我们的投标文件有问题，能否修改？修改有什么限制？
   - expected: `policy_101`
   - top1: `parent_工程建设项目施工招标投标办法_39_41_9502`
   - law: `【建设工程】施工电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

276. [condition_check][direct] 我们公司作为投标人，在建设工程施工电子招标投标中，需要满足哪些资质条件？
   - expected: `policy_101`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0217`
   - law: `【建设工程】施工电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

277. [procedure][scenario] 远程异地评标项目需要企业提前做什么准备工作？
   - expected: `policy_152`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_23_3852_6178`
   - law: `关于加快推广远程异地评标的通知`
   - type: `policy_doc` | span: `single`

278. [comparison][direct] 远程异地评标相比传统评标，有哪些优势？
   - expected: `policy_152`
   - top1: `parent_系统工程综合评标专家库管理办法_7_1892_1878`
   - law: `关于加快推广远程异地评标的通知`
   - type: `policy_doc` | span: `single`

279. [scenario_judgment][scenario] 企业参与远程异地评标项目后，若遇技术故障该怎么处理？
   - expected: `policy_152`
   - top1: `parent_机电产品国际招标评标专家及专家库管理办法_86_1372_7924`
   - law: `关于加快推广远程异地评标的通知`
   - type: `policy_doc` | span: `single`

280. [condition_check][direct] 使用上海市公共资源交易中心的各平台，企业需要满足什么基本条件？
   - expected: `policy_73`
   - top1: `policy_71`
   - law: `【综合管理】上海市公共资源交易中心公共服务清单(2024年版)`
   - type: `policy_doc` | span: `single`

281. [procedure][direct] 我们公司在上海做工程招标，该用上海市公共资源交易中心的哪个平台？
   - expected: `policy_73`
   - top1: `policy_101`
   - law: `【综合管理】上海市公共资源交易中心公共服务清单(2024年版)`
   - type: `policy_doc` | span: `single`

282. [responsibility][direct] 在交易过程中有问题，企业找哪个部门投诉更合适？
   - expected: `policy_73`
   - top1: `parent_政府采购质疑和投诉办法_6_3474_4159`
   - law: `【综合管理】上海市公共资源交易中心公共服务清单(2024年版)`
   - type: `policy_doc` | span: `single`

283. [scenario_judgment][scenario] 我们公司中标政府购买服务项目后，在合同签署方面有什么时间要求吗？
   - expected: `policy_215`
   - top1: `parent_中华人民共和国政府采购法_46_3003_3920`
   - law: `重庆政府购买服务“花钱买服务、办事...`
   - type: `policy_doc` | span: `single`

284. [definition][direct] 政府购买服务中不能纳入的事项有哪些类型呢？
   - expected: `policy_215`
   - top1: `parent_政府购买服务管理办法_10_4347_7228`
   - law: `重庆政府购买服务“花钱买服务、办事...`
   - type: `policy_doc` | span: `single`

285. [scenario_judgment][scenario] 我们公司要做一体式计算机政府采购，需要注意哪些合规要求？
   - expected: `policy_174`
   - top1: `parent_政务信息系统政府采购管理暂行办法_7_3348_3411`
   - law: `财政部 工业和信息化部关于印发《一体式计算机政...`
   - type: `policy_doc` | span: `single`

286. [scenario_judgment][scenario] 企业在参与农村集体资产项目时，需要关注哪些交易流程规范？
   - expected: `policy_17`
   - top1: `policy_106`
   - law: `上海市发展和改革委员会关于印发《上海市公共资源交易目录(2020年版)》的通知`
   - type: `policy_doc` | span: `single`

287. [scenario_judgment][scenario] 企业在参与公共资源交易时，需要关注哪些平台运营规则？
   - expected: `policy_17`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_7_4076_6256`
   - law: `上海市发展和改革委员会关于印发《上海市公共资源交易目录(2020年版)》的通知`
   - type: `policy_doc` | span: `single`

288. [scenario_judgment][scenario] 企业在参与公共资源交易时，需要了解哪些数据利用和监管要求？
   - expected: `policy_17`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_33_4102_3804`
   - law: `上海市发展和改革委员会关于印发《上海市公共资源交易目录(2020年版)》的通知`
   - type: `policy_doc` | span: `single`

289. [scenario_judgment][scenario] 企业在参与公共资源交易时，需要关注哪些服务环境要求？
   - expected: `policy_17`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_12_4081_7377`
   - law: `上海市发展和改革委员会关于印发《上海市公共资源交易目录(2020年版)》的通知`
   - type: `policy_doc` | span: `single`

290. [responsibility][direct] 如果在公共资源交易平台办理业务时遇到投诉，应该向哪个部门反映？
   - expected: `policy_19`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_36_4105_195`
   - law: `上海市发展和改革委员会、上海市财政局、上海市住房和城乡建设管理委员会等关于印发《`
   - type: `policy_doc` | span: `single`

291. [scenario_judgment][scenario] 公共资源交易平台管理的核心原则是什么，对我们的业务合规性有什么帮助？
   - expected: `policy_19`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_4_4073_9127`
   - law: `上海市发展和改革委员会、上海市财政局、上海市住房和城乡建设管理委员会等关于印发《`
   - type: `policy_doc` | span: `single`

292. [scenario_judgment][scenario] 实行政府采购项目电子化对企业的投标工作有什么便利之处？
   - expected: `policy_169`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0060`
   - law: `新疆印发《关于实行自治区政府采购项目电子化的...`
   - type: `policy_doc` | span: `single`

293. [scenario_judgment][scenario] 政府采购项目电子化对企业的成本控制有什么影响？
   - expected: `policy_169`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0290`
   - law: `新疆印发《关于实行自治区政府采购项目电子化的...`
   - type: `policy_doc` | span: `single`

294. [responsibility][direct] 政府采购中出现供应商失信情况后，我们公司应该怎么应对？
   - expected: `policy_168`
   - top1: `parent_中央国家机关政府采购电子卖场管理办法_28_3654_4155`
   - law: `山西省财政厅关于印发《政府采购失信行为管理暂...`
   - type: `policy_doc` | span: `single`

295. [scenario_judgment][scenario] 如果我们的供应商在政府采购中被认定为失信，应该如何处理？
   - expected: `policy_168`
   - top1: `parent_中央国家机关政府采购电子卖场管理办法_28_3654_4155`
   - law: `山西省财政厅关于印发《政府采购失信行为管理暂...`
   - type: `policy_doc` | span: `single`

296. [scenario_judgment][scenario] 中标后发现供应商存在失信记录，我们应该怎么办？
   - expected: `policy_168`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0035`
   - law: `山西省财政厅关于印发《政府采购失信行为管理暂...`
   - type: `policy_doc` | span: `single`

297. [procedure][scenario] 政府采购中的失信行为处理流程是怎样的？
   - expected: `policy_168`
   - top1: `parent_严重违法失信行为信息记录的通知_78_4399_2219`
   - law: `山西省财政厅关于印发《政府采购失信行为管理暂...`
   - type: `policy_doc` | span: `single`

298. [scenario_judgment][scenario] 如果在政府采购项目中出现违规情况会有什么后果？
   - expected: `policy_145`
   - top1: `parent_中华人民共和国政府采购法_73_3031_5251`
   - law: `中华人民共和国财政部令第74号《政府采购非招标...`
   - type: `policy_doc` | span: `single`

299. [procedure][direct] 政府采购项目的招标周期一般需要多长时间？
   - expected: `policy_145`
   - top1: `parent_中华人民共和国政府采购法_35_2992_8808`
   - law: `中华人民共和国财政部令第74号《政府采购非招标...`
   - type: `policy_doc` | span: `single`

300. [procedure][direct] 我们公司要做政府采购项目，需要注意哪些前期准备？
   - expected: `policy_145`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_23_3852_6178`
   - law: `中华人民共和国财政部令第74号《政府采购非招标...`
   - type: `policy_doc` | span: `single`

301. [procedure][direct] 我们公司中标后多久需要签订合同？
   - expected: `policy_145`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0625`
   - law: `中华人民共和国财政部令第74号《政府采购非招标...`
   - type: `policy_doc` | span: `single`

302. [condition_check][direct] 政府采购项目的评标主要依据哪些标准和要求？
   - expected: `policy_145`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0493`
   - law: `中华人民共和国财政部令第74号《政府采购非招标...`
   - type: `policy_doc` | span: `single`

303. [condition_check][direct] 企业在政府采购中选择招标方式时应该考虑哪些因素？
   - expected: `policy_145`
   - top1: `parent_《中华人民共和国政府采购法实施条例》等有_19_4009_2382`
   - law: `中华人民共和国财政部令第74号《政府采购非招标...`
   - type: `policy_doc` | span: `single`

304. [procedure][direct] 企业在平台操作过程中遇到服务问题该怎么解决？
   - expected: `policy_75`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_36_4105_195`
   - law: `【综合管理】关于印发《上海市公共资源交易平台服务标准（试行）》的通知`
   - type: `policy_doc` | span: `single`

305. [procedure][direct] 公共资源交易平台的投诉渠道和流程是怎样的？
   - expected: `policy_75`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_36_4105_195`
   - law: `【综合管理】关于印发《上海市公共资源交易平台服务标准（试行）》的通知`
   - type: `policy_doc` | span: `single`

306. [scenario_judgment][direct] 平台的服务标准对企业的操作有什么影响？
   - expected: `policy_75`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_38_4107_6494`
   - law: `【综合管理】关于印发《上海市公共资源交易平台服务标准（试行）》的通知`
   - type: `policy_doc` | span: `single`

307. [definition][direct] 企业在平台开展项目时，信息安全和保密要求是什么？
   - expected: `policy_75`
   - top1: `parent_通信工程建设项目评标专家及评标专家库管理_26_2535_5243`
   - law: `【综合管理】关于印发《上海市公共资源交易平台服务标准（试行）》的通知`
   - type: `policy_doc` | span: `single`

308. [procedure][direct] 办理招标投标公证大概需要多长时间？
   - expected: `policy_10`
   - top1: `parent_药品集中采购监督管理办法_55_2645_8383`
   - law: `司法部关于印发《招标投标公证程序细则》的通知`
   - type: `policy_doc` | span: `single`

309. [scenario_judgment][scenario] 如果我们的招标项目出现违规行为，招标投标公证会有什么影响？
   - expected: `policy_10`
   - top1: `parent_水利工程建设项目招标投标管理规定_56_2289_9150`
   - law: `司法部关于印发《招标投标公证程序细则》的通知`
   - type: `policy_doc` | span: `single`

310. [scenario_judgment][scenario] 公司员工在使用便携式计算机时，需要注意哪些保密和安全规定？
   - expected: `policy_191`
   - top1: `policy_175`
   - law: `中华人民共和国保守国家秘密法`
   - type: `policy_doc` | span: `single`

311. [procedure][direct] 我们企业在采购便携式计算机时，需要准备哪些相关证明材料？
   - expected: `policy_175`
   - top1: `parent_中华人民共和国政府采购法实施条例_22_19_7099`
   - law: `财政部 工业和信息化部关于印发《便携式计算机政...`
   - type: `policy_doc` | span: `single`

312. [scenario_judgment][scenario] 如果公司发生泄密事件，应该如何处理并遵守法律？
   - expected: `policy_191`
   - top1: `parent_中华人民共和国招标投标法_50_53_5141`
   - law: `中华人民共和国保守国家秘密法`
   - type: `policy_doc` | span: `single`

313. [procedure][scenario] 我们在处理涉密便携式计算机时，有哪些具体的管理要求？
   - expected: `policy_191`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_28_4097_3258`
   - law: `中华人民共和国保守国家秘密法`
   - type: `policy_doc` | span: `single`

314. [condition_check][scenario] 公司采购涉密便携式计算机时，需要满足哪些特殊合规要求？
   - expected: `policy_191`
   - top1: `parent_政务信息系统政府采购管理暂行办法_8_3349_8414`
   - law: `中华人民共和国保守国家秘密法`
   - type: `policy_doc` | span: `single`

315. [scenario_judgment][scenario] 我们企业在使用便携式计算机进行日常办公时，如何平衡便利性与保密要求？
   - expected: `policy_191`
   - top1: `policy_59`
   - law: `中华人民共和国保守国家秘密法`
   - type: `policy_doc` | span: `single`

316. [responsibility][direct] 我们公司在政府采购项目中，遇到妨碍公平竞争的情况应该找哪个部门投诉？
   - expected: `policy_222`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0686`
   - law: `湖北省财政厅关于开展政府采购领域妨碍公平竞争清理工...`
   - type: `policy_doc` | span: `single`

317. [definition][direct] 该清理工作对公司投标文件的要求有哪些变化？
   - expected: `policy_222`
   - top1: `parent_房屋建筑和市政基础设施工程施工招标投标管_19_1142_3072`
   - law: `湖北省财政厅关于开展政府采购领域妨碍公平竞争清理工...`
   - type: `policy_doc` | span: `single`

318. [procedure][scenario] 该政策实施后，我们公司在项目中标后的后续工作中需要注意哪些方面？
   - expected: `policy_222`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_26_3721_9324`
   - law: `湖北省财政厅关于开展政府采购领域妨碍公平竞争清理工...`
   - type: `policy_doc` | span: `single`

319. [procedure][direct] 我们公司如何确保在政府采购中不出现妨碍公平竞争的行为？
   - expected: `policy_222`
   - top1: `parent_财政部关于促进政府采购公平竞争优化营商环_68_4037_2542`
   - law: `湖北省财政厅关于开展政府采购领域妨碍公平竞争清理工...`
   - type: `policy_doc` | span: `single`

320. [scenario_judgment][scenario] 如果我们公司的PPP项目出现违规情况，会有什么法律后果？
   - expected: `policy_188`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_18_4109_5696`
   - law: `政府和社会资本合作`
   - type: `policy_doc` | span: `single`

321. [procedure][direct] 我们企业在参与PPP项目时，需要关注哪些核心环节？
   - expected: `policy_188`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_48_4119_8963`
   - law: `政府和社会资本合作`
   - type: `policy_doc` | span: `single`

322. [definition][direct] 我们公司想了解广东省政府采购评审专家的管理要求有哪些？
   - expected: `policy_217`
   - top1: `parent_政府采购评审专家管理办法_18_3549_1195`
   - law: `广东省财政厅关于印发《广东省政府采购评审专家管理实...`
   - type: `policy_doc` | span: `single`

323. [procedure][direct] 企业在邀请广东省政府采购评审专家时，需要注意哪些流程？
   - expected: `policy_217`
   - top1: `parent_政府采购评审专家管理办法_18_3549_1195`
   - law: `广东省财政厅关于印发《广东省政府采购评审专家管理实...`
   - type: `policy_doc` | span: `single`

324. [scenario_judgment][scenario] 如果企业在评审专家管理中出现违规情况，会有什么后果？
   - expected: `policy_217`
   - top1: `parent_政府采购评审专家管理办法_31_3562_9890`
   - law: `广东省财政厅关于印发《广东省政府采购评审专家管理实...`
   - type: `policy_doc` | span: `single`

325. [condition_check][scenario] 中标项目完成后，我们多久必须完成产权登记？需要满足什么前提条件？
   - expected: `policy_61`
   - top1: `parent_经营性公路建设项目投资人招标投标管理规定_34_1753_9064`
   - law: `国务院国有资产监督管理委员会关于印发《国家出资企业产权登记管理工作指引》的通知`
   - type: `policy_doc` | span: `single`

326. [scenario_judgment][scenario] 我们公司在与供应商合作时，如何确保按时收到付款？需要注意哪些合规要点？
   - expected: `policy_138`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_7_3702_8081`
   - law: `国务院公布《保障中小企业款项支付条例》`
   - type: `policy_doc` | span: `single`

327. [scenario_judgment][scenario] 当供应商投诉我们的付款不及时时，我们应该如何处理这种情况？
   - expected: `policy_138`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0684`
   - law: `国务院公布《保障中小企业款项支付条例》`
   - type: `policy_doc` | span: `single`

328. [procedure][direct] 作为企业负责人，我们在签订合同时，应该如何约定付款时间以规避风险？
   - expected: `policy_138`
   - top1: `parent_《中华人民共和国政府采购法实施条例》等有_23_4013_35`
   - law: `国务院公布《保障中小企业款项支付条例》`
   - type: `policy_doc` | span: `single`

329. [scenario_judgment][scenario] 中小企业在采购项目中，如何确保供应商能及时获得款项？需要做好哪些准备工作？
   - expected: `policy_138`
   - top1: `parent_《中华人民共和国中小企业促进法》等有关法_12_3982_2799`
   - law: `国务院公布《保障中小企业款项支付条例》`
   - type: `policy_doc` | span: `single`

330. [condition_check][scenario] 中标项目完成后，我们多久必须完成产权登记？需要满足什么前提条件？
   - expected: `policy_61`
   - top1: `parent_经营性公路建设项目投资人招标投标管理规定_34_1753_9064`
   - law: `国务院国有资产监督管理委员会关于印发《国家出资企业产权登记管理工作指引》的通知`
   - type: `policy_doc` | span: `single`

331. [scenario_judgment][scenario] 我们公司在与供应商合作时，如何确保按时收到付款？需要注意哪些合规要点？
   - expected: `policy_138`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_7_3702_8081`
   - law: `国务院公布《保障中小企业款项支付条例》`
   - type: `policy_doc` | span: `single`

332. [scenario_judgment][scenario] 作为企业负责人，我们在签订合同时，应该如何约定付款时间以规避风险？
   - expected: `policy_138`
   - top1: `parent_《中华人民共和国政府采购法实施条例》等有_23_4013_35`
   - law: `国务院公布《保障中小企业款项支付条例》`
   - type: `policy_doc` | span: `single`

333. [scenario_judgment][scenario] 当供应商投诉我们的付款不及时时，我们应该如何处理这种情况？
   - expected: `policy_138`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0684`
   - law: `国务院公布《保障中小企业款项支付条例》`
   - type: `policy_doc` | span: `single`

334. [scenario_judgment][scenario] 中小企业在采购项目中，如何确保供应商能及时获得款项？需要做好哪些准备工作？
   - expected: `policy_138`
   - top1: `parent_《中华人民共和国中小企业促进法》等有关法_12_3982_2799`
   - law: `国务院公布《保障中小企业款项支付条例》`
   - type: `policy_doc` | span: `single`

335. [scenario_judgment][scenario] 投标人拒绝澄清投标文件会咋处理呢？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0552`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0317`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

336. [scenario_judgment][scenario] 投标人投标文件中出现可识别身份的信息，评标委员会应该怎样处理？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0584`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0485`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

337. [scenario_judgment][scenario] 评标委员会在判断投标人技术标是否符合要求时，有哪些客观依据可以遵循？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0584`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0493`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

338. [scenario_judgment][scenario] 我们公司在招标后，评标委员会推荐的候选人不符合预期，能否重新招标？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0590`
   - top1: `parent_建筑工程设计招标投标管理办法_21_1059_2889`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

339. [scenario_judgment][scenario] 招标文件中没有明确规定评标标准和办法，这种情况下容易出现什么问题？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0248`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0485`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

340. [responsibility][scenario] 企业在招标项目中选择招标文件时，通常会参考哪些类型的规范文件？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0764`
   - top1: `parent_工程建设项目施工招标投标办法_24_26_8439`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

341. [comparison][scenario] 不同行业的招标文件有什么明显区别？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0764`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0232`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

342. [scenario_judgment][direct] 企业如何预防虚假投标这类违法行为？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0416`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0417`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

343. [procedure][scenario] 我们公司的招标项目采用资格后审，那投标人需要在什么阶段准备资格证明材料呢？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0194`
   - top1: `parent_水利工程建设项目重要设备材料采购招标投标_15_2377_4779`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

344. [scenario_judgment][direct] 如果我们公司搞招标项目时选择资格后审，那投标人有可能因资格问题被淘汰吗？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0194`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0196`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

345. [condition_check][direct] 如果我们对资格预审文件有异议，多久能提出？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0674`
   - top1: `parent_标法》《中华人民共和国招标投标法实施条例_25_1833_82`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

346. [scenario_judgment][scenario] 若在招标投标中发现投标文件存在重大偏差，该如何处理？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0433`
   - top1: `parent_政府采购货物和服务招标投标管理办法_65_68_8178`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

347. [procedure][cross_reference] 企业在招标投标中使用哪种评标方法更合适？需要注意什么？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0478`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0481`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

348. [scenario_judgment][scenario] 如果我们的分包单位违反了规定，招标人可以通过哪些方式维权？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0661`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0685`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

349. [scenario_judgment][scenario] 在工程分包过程中，哪些类型的分包是不允许的？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0661`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0655`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

350. [scenario_judgment][scenario] 联合体投标在工程总承包项目中如何合法开展？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0062`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0347`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

351. [scenario_judgment][scenario] 如果监理单位和我们公司存在利害关系，这对招标过程有什么影响？？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0062`
   - top1: `parent_标法》《中华人民共和国招标投标法实施条例_35_1843_5062`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

352. [scenario_judgment][scenario] 投标人弄虚作假骗取中标会有什么法律后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0412`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0415`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

353. [scenario_judgment][scenario] 发现投标文件存在问题，如何核实其真实性？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0412`
   - top1: `parent_机电产品国际招标投标“双随机一公开”监管_15_1415_870`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

354. [scenario_judgment][scenario] 我们在选聘物业公司的时候，如果投标人不够3个，能不能用协议方式？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0111`
   - top1: `parent_政府采购货物和服务招标投标管理办法_43_44_215`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

355. [definition][cross_reference] 我们公司准备参与招标项目，需要遵守哪些监管方面的规定？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0760`
   - top1: `parent_机电产品国际招标投标“双随机一公开”监管_9_1408_8170`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

356. [definition][direct] 招标公告发布有哪些合规要求？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0187`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0189`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

357. [scenario_judgment][scenario] 我们公司招标公告应该在哪里发布才符合规定？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0187`
   - top1: `parent_招标公告和公示信息发布管理办法_8_776_9206`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

358. [scenario_judgment][scenario] 如果不按规定发布招标公告，会带来什么后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0187`
   - top1: `parent_中华人民共和国招标投标法实施条例_51_139_300`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

359. [definition][scenario] 企业在招标过程中如何判断招标文件是否符合法律规定？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0285`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0499`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

360. [scenario_judgment][cross_reference] 企业在招标过程中遇到评标委员会错误处理，应该如何应对？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0473`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0512`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

361. [definition][direct] 评标委员会的工作性质是怎样的？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0473`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0450`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

362. [condition_check][direct] 招标人在制定招标文件时，需要注意哪些技术指标方面的要求？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0255`
   - top1: `parent_工程建设项目施工招标投标办法_26_28_732`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

363. [responsibility][direct] 我们公司的评标专家是怎么确定的？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0453`
   - top1: `parent_评标委员会和评标方法暂行规定_10_401_4260`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

364. [scenario_judgment][scenario] 评标专家如果被串通，会导致什么后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0453`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0470`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

365. [scenario_judgment][scenario] 我们公司招标时，如果所有投标都不符合要求，该怎么办？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0563`
   - top1: `parent_中华人民共和国招标投标法_42_45_6937`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

366. [scenario_judgment][scenario] 我们公司评标时，评标专家抽取应该注意什么事项？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0453`
   - top1: `parent_及教学资源招标采购管理办法_13_2893_5954`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

367. [scenario_judgment][scenario] 招标过程中出现重大变故需要取消招标时，我们应该怎么做？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0563`
   - top1: `parent_政府采购货物和服务招标投标管理办法_29_30_6977`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

368. [scenario_judgment][scenario] 我们公司在招标过程中，中标后的样品应该如何保管和封存呢？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0242`
   - top1: `parent_政府采购货物和服务招标投标管理办法_22_3381_6565`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

369. [definition][direct] 招标过程中存在哪些不合理条件限制投标人的情况呢？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0242`
   - top1: `parent_中华人民共和国招标投标法实施条例_32_105_5144`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

370. [condition_check][scenario] 企业在招标项目中使用哪些标准文件比较合适呢？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0761`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0232`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

371. [scenario_judgment][scenario] 这些招标投标通知和文件对企业有什么帮助呢？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0761`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0239`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

372. [scenario_judgment][scenario] 投标人弄虚作假骗取中标会面临怎样的处罚？我们企业在投标前该如何防范这类风险？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0410`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0416`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

373. [scenario_judgment][scenario] 招标文件的商务条款不合理的话，会给我们的招标项目带来什么后果呀？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0388`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0380`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

374. [procedure][direct] 招标投标活动的核心流程都有哪些呀？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0002`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0450`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

375. [scenario_judgment][scenario] 我们公司参与招标投标项目后，如果对采购过程有疑问该怎么处理？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0754`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0683`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

376. [scenario_judgment][scenario] 我们公司在招标过程中遇到质疑或投诉，应该怎么规范处理？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0677`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0709`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

377. [scenario_judgment][scenario] 我们公司投标时需要检查哪些方面的资质和文件呢？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0498`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0496`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

378. [condition_check][scenario] 招标人在发布招标前需要满足哪些基本条件呀？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0158`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0161`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

379. [scenario_judgment][scenario] 我们公司作为投标人，招标人没发中标通知就取消项目，还能索赔吗？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0158`
   - top1: `parent_工程建设项目施工招标投标办法_81_85_4421`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

380. [scenario_judgment][scenario] 如果招标被认定为无效，我们需要怎么做呢？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0739`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0746`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

381. [scenario_judgment][scenario] 招标机构如果有违规行为，会有什么后果呀？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0739`
   - top1: `parent_出口商品配额招标办法_38_2767_4966`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

382. [condition_check][scenario] 我们公司投标时需要检查哪些方面的资质和文件呢？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0498`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0496`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

383. [condition_check][scenario] 招标人在发布招标前需要满足哪些基本条件呀？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0158`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0161`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

384. [scenario_judgment][scenario] 我们公司作为投标人，招标人没发中标通知就取消项目，还能索赔吗？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0158`
   - top1: `parent_工程建设项目施工招标投标办法_81_85_4421`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

385. [scenario_judgment][scenario] 招标机构如果有违规行为，会有什么后果呀？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0739`
   - top1: `parent_出口商品配额招标办法_38_2767_4966`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

386. [scenario_judgment][scenario] 如果招标被认定为无效，我们需要怎么做呢？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0739`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0746`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

387. [condition_check][scenario] 我们公司投标时需要检查哪些方面的资质和文件呢？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0498`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0496`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

388. [condition_check][scenario] 招标人在发布招标前需要满足哪些基本条件呀？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0158`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0161`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

389. [scenario_judgment][scenario] 我们公司作为投标人，招标人没发中标通知就取消项目，还能索赔吗？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0158`
   - top1: `parent_工程建设项目施工招标投标办法_81_85_4421`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

390. [scenario_judgment][direct] 招标机构如果有违规行为，会有什么后果呀？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0739`
   - top1: `parent_出口商品配额招标办法_38_2767_4966`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

391. [scenario_judgment][direct] 如果招标被认定为无效，我们需要怎么做呢？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0739`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0746`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

392. [scenario_judgment][scenario] 我们公司在招标的时候，如果发现招标文件里的评标标准有问题，应该怎么处理比较好呀？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0488`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0512`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

393. [condition_check][direct] 招标人在编制标底的时候，有没有必要一定要编制呢？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0514`
   - top1: `parent_工程建设项目施工招标投标办法_34_36_4527`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

394. [scenario_judgment][direct] 联合体投标时，如果后来更换了成员，投标还有效吗？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0543`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0356`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

395. [scenario_judgment][direct] 如果我们的投标人最近发生了合并，投标还有效吗？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0543`
   - top1: `parent_中华人民共和国招标投标法实施条例_38_111_378`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

396. [responsibility][scenario] 招标代理机构主要帮助我们做什么？有没有必要委托他们？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0161`
   - top1: `parent_国家食品药品监督管理总局采购与招标管理办_8_2682_2158`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

397. [condition_check][scenario] 如果是小型项目招标，还需要像大项目一样满足那么多条件吗？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0161`
   - top1: `parent_政府投资条例_4_376_2634`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

398. [case_reasoning][cross_reference] 当联合体投标出现违规情况时，投诉后会怎么处理？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0693`
   - top1: `parent_工程建设项目招标投标活动投诉处理办法_14_993_7276`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

399. [procedure][direct] 我们公司已经完成评标，想知道定标后多久要给中标人发中标通知书呀？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0070`
   - top1: `parent_工程建设项目施工招标投标办法_56_58_1319`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

400. [condition_check][direct] 中标通知书发出后，双方还能不能就合同实质性内容谈判呀？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0070`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0615`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

401. [procedure][direct] 开标时需要满足哪些条件和流程呀？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0069`
   - top1: `parent_房屋建筑和市政基础设施工程施工招标投标管_7_1128_3130`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

402. [procedure][direct] 评标委员会如何组建呀？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0069`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0450`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

403. [condition_check][direct] 开标后投标人还能修改投标文件吗？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0069`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0489`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

404. [case_reasoning][scenario] 虚假投标会导致哪些法律后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0413`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0416`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

405. [scenario_judgment][direct] 普通员工想了解开标时发现投标文件有问题怎么办？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0429`
   - top1: `parent_政府采购货物和服务招标投标管理办法_65_68_8178`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

406. [scenario_judgment][direct] 法务人员想了解政府采购招标确定中标人的规定？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0597`
   - top1: `parent_法定代表人为同一个人的两个及两个以上法_48_682_6775`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

407. [condition_check][direct] 招标文件收费有什么限制吗？我们该怎么操作？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0267`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0271`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

408. [scenario_judgment][scenario] 如果在招标过程中发现招标文件有设定不合理条件的情况，我们应该如何处理？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0244`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0227`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

409. [condition_check][direct] 我们公司在中标后，通常需要多长时间和对方签订合同呢？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0134`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0625`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

410. [scenario_judgment][scenario] 遇到招标文件有指定特定品牌产品的条款时我们该如何应对？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0244`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0254`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

411. [scenario_judgment][scenario] 招标投标过程中，评标委员会选择中标人时，是否一定要选报价最低者呢？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0134`
   - top1: `parent_房屋建筑和市政基础设施工程施工招标投标管_42_1166_7860`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

412. [scenario_judgment][scenario] 评标中发现评委收受投标人好处，，我们应该怎么处理？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0469`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0461`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

413. [procedure][scenario] 如果我们在招标项目中组成联合体，成员单位之间的合同纠纷该怎么解决呢？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0357`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0358`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

414. [procedure][scenario] 联合体投标时，各成员单位的职责分工应该怎么明确？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0357`
   - top1: `parent_标法》《中华人民共和国招标投标法实施条例_36_1844_346`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

415. [procedure][scenario] 编制招标文件时，如何确保提供的信息符合真实性和完整性要求？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0250`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0264`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

416. [scenario_judgment][scenario] 投标人以行贿手段谋取中标会有什么后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0556`
   - top1: `parent_工程建设项目施工招标投标办法_74_78_3994`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

417. [procedure][direct] 我们公司在招标项目中，开标的时间和地点应该怎么确定？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0008`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0421`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

418. [procedure][direct] 遇到开标现场出现异常情况，我们应该如何处理？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0008`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0431`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

419. [definition][synonym] 评标委员会成员调整有哪些规定？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0008`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0462`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

420. [procedure][direct] 我们公司做招标项目，评标报告要包含哪些内容？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0567`
   - top1: `parent_标法》《中华人民共和国招标投标法实施条例_55_1864_7367`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

421. [scenario_judgment][scenario] 之前因为没有招投标签的协议，现在想追回之前垫付的资金应该怎么做？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0118`
   - top1: `parent_工程建设项目施工招标投标办法_62_64_5846`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

422. [condition_check][direct] 企业在开展项目采购时，如何判断哪些部分需要招标呢？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0109`
   - top1: `parent_政府投资条例_5_377_4537`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

423. [scenario_judgment][scenario] 招标项目中涉及合同主要条款的澄清，应该如何处理？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0288`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0278`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

424. [procedure][direct] 招标文件澄清后，投标人如何确认其投标文件是否符合要求？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0288`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0529`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

425. [scenario_judgment][scenario] 招标文件澄清对投标截止时间的影响是什么？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0288`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0278`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

426. [procedure][direct] 招标项目中涉及合同主要条款的澄清，应该如何处理？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0288`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0278`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

427. [procedure][direct] 招标文件澄清后，投标人如何确认其投标文件是否符合要求？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0288`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0529`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

428. [scenario_judgment][direct] 招标文件澄清对投标截止时间的影响是什么？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0288`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0278`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

429. [condition_check][direct] 招标人在确定中标前能和投标人谈价格吗？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0619`
   - top1: `parent_中华人民共和国招标投标法_43_46_7961`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

430. [scenario_judgment][direct] 如果我们公司中标后拒绝签订合同，会有哪些后果呢？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0619`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0641`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

431. [scenario_judgment][direct] 如果联合体成员不符合招标文件资格条件，会有什么后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0351`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0350`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

432. [scenario_judgment][scenario] 评标委员会否定所有投标时，有没有合法理由？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0517`
   - top1: `parent_工程建设项目勘察设计招标投标办法_42_615_9792`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

433. [scenario_judgment][scenario] 如果发现招标公告发布的范围有限导致投标人不足，我们应该采取什么措施来解决这个问题？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0094`
   - top1: `parent_政府采购货物和服务招标投标管理办法_43_44_215`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

434. [definition][scenario] 财政部门处理政府采购投诉事项的时限是多久呢？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0706`
   - top1: `parent_政府采购质疑和投诉办法_26_3486_1880`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

435. [scenario_judgment][direct] 如果我们公司对招标文件中的某些条款有异议，应该如何向招标人提出呢？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0283`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0674`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

436. [responsibility][direct] 我们企业在招标投标中，遇到投标文件问题该找哪个部门咨询？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0341`
   - top1: `parent_政府采购货物和服务招标投标管理办法_51_3412_1994`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

437. [scenario_judgment][scenario] 我们公司在招标项目发售招标文件时，发现不同投标人获得的资料不一致，这种情况违反了什么法律原则？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0133`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0268`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

438. [procedure][direct] 如果中标候选人排序存在问题，招标人应该如何处理呀？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0574`
   - top1: `parent_标法》《中华人民共和国招标投标法实施条例_57_1866_2405`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

439. [procedure][direct] 我们公司在招标过程中，发现有个投标人的资格有问题，这时候能做啥处理呀？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0574`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0196`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

440. [scenario_judgment][scenario] 我们公司参与招标投标项目，需要防范哪些串通投标类的风险呀？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0730`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0398`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

441. [scenario_judgment][scenario] 如果我们的招标投标行为涉及串通投标，会面临什么样的法律后果呀？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0730`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0397`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

442. [scenario_judgment][scenario] 我们公司在做工程建设项目时，总承包范围内暂估价的货物达到一定规模后该怎么处理？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0151`
   - top1: `parent_工程建设项目货物招标投标办法_5_644_9138`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

443. [condition_check][direct] 我们公司在投标时发现投标文件被否决，可能是什么原因？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0042`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0315`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

444. [scenario_judgment][scenario] 投标文件出现漏项会导致什么后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0042`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0251`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

445. [scenario_judgment][scenario] 投标文件中资质证明过期会带来什么风险？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0042`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0328`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

446. [scenario_judgment][direct] 投标保证金提交方式有哪些？需要注意什么？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0373`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0363`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

447. [scenario_judgment][scenario] 投标文件不符合招标要求会面临什么处罚？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0315`
   - top1: `parent_工程建设项目勘察设计招标投标办法_55_634_1639`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

448. [responsibility][scenario] 我们公司中标后发现招标流程有问题，能去投诉吗？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0672`
   - top1: `parent_中华人民共和国招标投标法实施条例_60_134_2768`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

449. [scenario_judgment][scenario] 如果我们的投标过程中出现与其他投标方串通报价的情况，这属于什么违法行为？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0731`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0729`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

450. [definition][direct] 在招投标过程中，常见的串通投标表现形式有哪些？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0731`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0391`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

451. [scenario_judgment][scenario] 当发现存在串通投标行为时，我们应该采取怎样的合规处理措施？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0731`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0398`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

452. [condition_check][scenario] 我们公司的工程建设项目是否属于必须进行招标的项目？需要满足哪些基本条件？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0105`
   - top1: `parent_工程建设项目施工招标投标办法_8_8_8831`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

453. [procedure][direct] 我们公司在招标过程中需要遵循哪些主要的招标投标管理办法？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0755`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0028`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

454. [procedure][scenario] 如果我们的项目不属于强制招标项目，确定承包商的方式有哪些？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0105`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0120`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

455. [scenario_judgment][scenario] 水利工程的招标投标需要遵循哪些具体的管理规定？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0755`
   - top1: `parent_水利工程建设项目招标投标管理规定_4_2234_4677`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

456. [scenario_judgment][scenario] 不同类型的工程建设项目对应不同的招标管理办法，我们该如何选择合适的招标管理规范？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0755`
   - top1: `parent_工程建设项目勘察设计招标投标办法_7_582_6295`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

457. [scenario_judgment][scenario] 如果招标人在开标前弄虚作假导致中标无效，会有什么后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0719`
   - top1: `parent_工程建设项目施工招标投标办法_75_79_4642`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

458. [responsibility][scenario] 招标项目投诉分包投诉需要特别注意什么？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0702`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0699`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

459. [scenario_judgment][scenario] 做招标项目时，怎么平衡效率和合规性要求？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0025`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0104`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

460. [scenario_judgment][scenario] 当我们公司中标后发现是通过虚假手段获取的，合同效力会怎么样，工程款应该怎么处理？
   - expected: `pdf_建设工程施工合同纠纷案_14_3117`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0412`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

461. [scenario_judgment][scenario] 企业在工程投标过程中，如何避免出现中标属于骗取中标的情况？
   - expected: `pdf_建设工程施工合同纠纷案_14_3117`
   - top1: `parent_中华人民共和国招标投标法_33_36_3698`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

462. [scenario_judgment][scenario] 当发现中标无效导致合同无效时，工程款结算的依据是什么？
   - expected: `pdf_建设工程施工合同纠纷案_14_3117`
   - top1: `pdf_建设工程施工合同纠纷案_32_2531`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

463. [scenario_judgment][scenario] 遇到竞争对手可能串通投标的情况，我们应该怎么做来保障自身权益？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_0_6530`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0399`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

464. [scenario_judgment][scenario] 施工项目中途因设计变更导致工程量变化，这类情况下的合同履行需要注意哪些合规点？
   - expected: `pdf_建设工程施工合同纠纷案_6_2065`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0668`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

465. [scenario_judgment][scenario] 我们在招投标过程中发现招标人可能存在串通行为，作为企业负责人应该怎么做来规避风险？
   - expected: `pdf_串通投标、受贿案_4_779`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0398`
   - law: `串通投标、受贿案`
   - type: `pdf_case_sliding` | span: `single`

466. [scenario_judgment][scenario] 施工项目部分工程已完成但存在质量争议，该如何处理后续工程款的结算？
   - expected: `pdf_建设工程施工合同纠纷案_6_2065`
   - top1: `pdf_建设工程施工合同纠纷案_31_3224`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

467. [scenario_judgment][scenario] 如果标书被泄露，我们能通过什么法律手段维权？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_17_5691`
   - top1: `parent_工程建设项目施工招标投标办法_69_71_5902`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

468. [scenario_judgment][scenario] 我们公司做建筑工程项目，和施工单位签合同时要注意哪些合规风险？
   - expected: `pdf_建设工程施工合同纠纷案_1_8560`
   - top1: `pdf_建设工程施工合同纠纷案_26_5099`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

469. [scenario_judgment][scenario] 遇到施工合同纠纷且工程已验收，应该如何处理工程款问题？
   - expected: `pdf_建设工程施工合同纠纷案_1_8560`
   - top1: `pdf_建设工程施工合同纠纷案_17_1012`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

470. [condition_check][scenario] 建筑工程施工合同中，施工单位没资质或借资质会有什么法律后果？
   - expected: `pdf_建设工程施工合同纠纷案_1_8560`
   - top1: `pdf_建设工程施工合同纠纷案_33_3584`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

471. [scenario_judgment][scenario] 如果我们公司的运输车辆参与招标时，发现其他公司存在串通报价情况，我们应该如何应对以避免损失？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_15_3967`
   - top1: `pdf_运输服务公司串通投标不正当竞争纠纷案_12_9047`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

472. [scenario_judgment][scenario] 运输服务公司在招标过程中发现竞争对手互相透露报价信息，我们该如何维护自身合法权益？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_15_3967`
   - top1: `pdf_运输服务公司串通投标不正当竞争纠纷案_1_7779`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

473. [scenario_judgment][scenario] 我们公司在参与国有建设用地使用权挂牌竞买时，需要关注哪些合规要点？
   - expected: `pdf_非国家工作人员行贿案_5_6500`
   - top1: `parent_招标拍卖挂牌出让国有建设用地使用权规定_17_1027_9667`
   - law: `非国家工作人员行贿案`
   - type: `pdf_case_sliding` | span: `single`

474. [scenario_judgment][scenario] 碰到施工合同纠纷，关于工程款和资质争议该怎么处理呀？
   - expected: `pdf_建设工程施工合同纠纷案_8_7290`
   - top1: `pdf_建设工程施工合同纠纷案_32_2531`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

475. [case_reasoning][scenario] 这个案例对企业在土地出让方式选择和竞买过程中的风险防控有何借鉴？
   - expected: `pdf_非国家工作人员行贿案_5_6500`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0419`
   - law: `非国家工作人员行贿案`
   - type: `pdf_case_sliding` | span: `single`

476. [scenario_judgment][scenario] 我们公司在签大项目合同时，要注意哪些合同条款和潜在风险呢？
   - expected: `pdf_建设工程施工合同纠纷案_8_7290`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0634`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

477. [scenario_judgment][scenario] 我们公司在招投标和保护商业秘密方面需要注意啥？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_12_9047`
   - top1: `pdf_运输服务公司串通投标不正当竞争纠纷案_5_1403`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

478. [scenario_judgment][scenario] 遇到竞争对手在招投标中存在串通行为，对企业经营意味着什么？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_12_9047`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0391`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

479. [scenario_judgment][scenario] 招投标过程中如果担心被串通，我们应该从哪些方面完善内部管理？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_16_7898`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0399`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

480. [definition][direct] 投标文件属于什么性质的信息，泄露后会有什么法律后果？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_16_7898`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0316`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

481. [scenario_judgment][scenario] 如果发现竞争对手在招标前泄露标底信息，我们作为企业应该如何应对？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_16_7898`
   - top1: `parent_工程建设项目施工招标投标办法_71_73_9080`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

482. [scenario_judgment][scenario] 遇到招投标串通情况，企业可以通过哪些途径维护自身合法权益？
   - expected: `pdf_串通投标、受贿案_1_7412`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0391`
   - law: `串通投标、受贿案`
   - type: `pdf_case_sliding` | span: `single`

483. [scenario_judgment][scenario] 当招投标项目存在串通行为时，企业的中标结果是否有效？
   - expected: `pdf_串通投标、受贿案_1_7412`
   - top1: `parent_中华人民共和国招标投标法_50_53_5141`
   - law: `串通投标、受贿案`
   - type: `pdf_case_sliding` | span: `single`

484. [scenario_judgment][scenario] 招投标中若发现工作人员收受投标人贿赂，企业应采取什么措施防范风险？
   - expected: `pdf_串通投标、受贿案_1_7412`
   - top1: `pdf_串通投标、受贿案_4_779`
   - law: `串通投标、受贿案`
   - type: `pdf_case_sliding` | span: `single`

485. [procedure][scenario] 如果在工程中标后发现对方资金有问题导致停工，我们已经完成了部分工程，应该怎么维护自己的工程款权益？
   - expected: `pdf_建工集团公司建设工程施工合同纠纷案_7_6100`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0157`
   - law: `建工集团公司建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

486. [definition][direct] 投标文件属于什么性质的信息，泄露后会有什么法律后果？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_16_7898`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0316`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

487. [scenario_judgment][scenario] 招投标过程中如果担心被串通，我们应该从哪些方面完善内部管理？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_16_7898`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0399`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

488. [scenario_judgment][scenario] 如果发现竞争对手在招标前泄露标底信息，我们作为企业应该如何应对？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_16_7898`
   - top1: `parent_工程建设项目施工招标投标办法_71_73_9080`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

489. [scenario_judgment][scenario] 遇到招投标串通情况，企业可以通过哪些途径维护自身合法权益？
   - expected: `pdf_串通投标、受贿案_1_7412`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0391`
   - law: `串通投标、受贿案`
   - type: `pdf_case_sliding` | span: `single`

490. [scenario_judgment][scenario] 招投标中若发现工作人员收受投标人贿赂，企业应采取什么措施防范风险？
   - expected: `pdf_串通投标、受贿案_1_7412`
   - top1: `pdf_串通投标、受贿案_4_779`
   - law: `串通投标、受贿案`
   - type: `pdf_case_sliding` | span: `single`

491. [scenario_judgment][scenario] 当招投标项目存在串通行为时，企业的中标结果是否有效？
   - expected: `pdf_串通投标、受贿案_1_7412`
   - top1: `parent_中华人民共和国招标投标法_50_53_5141`
   - law: `串通投标、受贿案`
   - type: `pdf_case_sliding` | span: `single`

492. [scenario_judgment][scenario] 运输服务公司在投标过程中出现串通行为，会面临怎样的法律后果呀？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_6_5005`
   - top1: `pdf_运输服务公司串通投标不正当竞争纠纷案_1_7779`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

493. [scenario_judgment][scenario] 如果投标中标书被泄露，对我们的业务会有什么影响呀？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_6_5005`
   - top1: `parent_工程建设项目施工招标投标办法_69_71_5902`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

494. [scenario_judgment][scenario] 中标后如果出现工程款拖欠问题，参考这类案例我们应该如何维权？
   - expected: `pdf_建设工程施工合同纠纷案_13_142`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0625`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

495. [scenario_judgment][scenario] 工程已经验收合格但对方拖欠款项，这类案件的工程款结算依据是什么？
   - expected: `pdf_建设工程施工合同纠纷案_13_142`
   - top1: `pdf_建设工程施工合同纠纷案_0_8849`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

496. [scenario_judgment][scenario] 遇到这类施工合同纠纷，我们公司应该先收集哪些关键证据？
   - expected: `pdf_建设工程施工合同纠纷案_13_142`
   - top1: `pdf_建设工程施工合同纠纷案_32_2531`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

497. [scenario_judgment][scenario] 工程合同无效情况下，我们该如何保障工程款的合法权益？
   - expected: `pdf_建设工程施工合同纠纷案_0_8849`
   - top1: `pdf_建设工程施工合同纠纷案_32_2531`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

498. [responsibility][direct] 遇到运输服务领域的串通投标纠纷，我们公司应该联系哪个部门投诉？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_9_9233`
   - top1: `parent_标法》《中华人民共和国招标投标法实施条例_63_1872_9013`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

499. [comparison][synonym] 招投标纠纷中，串通投标与普通侵权行为的法律后果有什么区别？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_2_4762`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0720`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

500. [scenario_judgment][scenario] 招投标过程中若发现投标书内容被泄露，我们应该如何处理这类争议？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_2_4762`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0340`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

501. [scenario_judgment][scenario] 我们公司在招投标过程中发现竞争对手可能串通中标，该怎么维护自身合法权益？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_2_4762`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0399`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

502. [scenario_judgment][scenario] 我们公司因为招投标串通输了，中标后对方没完全履行合同，我们能索赔多少损失呀？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_14_4391`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0722`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

503. [case_reasoning][scenario] 案例里说合同没全部履行的情况，我们公司这种情况应该怎么判断自己有没有损失呢？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_14_4391`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0669`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

504. [responsibility][synonym] 如果招投标中出现串通行为，中标后发现对方没签合同也没履行，我们应该找哪个部门投诉？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_14_4391`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0398`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

505. [scenario_judgment][scenario] 如果发现供应商在投标过程中存在串通行为，我们公司应该怎么处理以避免法律风险？
   - expected: `pdf_串通投标、受贿案_2_5418`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0398`
   - law: `串通投标、受贿案`
   - type: `pdf_case_sliding` | span: `single`

506. [scenario_judgment][scenario] 企业在投标过程中发现供应商存在串通迹象，应该如何合法维护自身的投标权益？
   - expected: `pdf_串通投标、受贿案_2_5418`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0398`
   - law: `串通投标、受贿案`
   - type: `pdf_case_sliding` | span: `single`

507. [scenario_judgment][scenario] 遇到承包商挂靠情况，我们该如何保障自己能及时收回工程款？
   - expected: `pdf_建工集团公司建设工程施工合同纠纷案_0_2457`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0404`
   - law: `建工集团公司建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

508. [procedure][scenario] 在建筑工程项目中，如果发现承包商存在资质挂靠情况，我们应该从哪些方面完善管理流程？
   - expected: `pdf_建设工程施工合同纠纷案_19_1663`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0404`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

509. [case_reasoning][cross_reference] 这种串通竞标的法律后果有哪些？
   - expected: `pdf_非国家工作人员行贿案_0_3216`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0729`
   - law: `非国家工作人员行贿案`
   - type: `pdf_case_sliding` | span: `single`

510. [scenario_judgment][scenario] 如果我们公司在土地招标时，想让竞争对手主动放弃，该怎么做才合法？
   - expected: `pdf_非国家工作人员行贿案_0_3216`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0385`
   - law: `非国家工作人员行贿案`
   - type: `pdf_case_sliding` | span: `single`

511. [case_reasoning][cross_reference] 案例中公司的上诉结果如何？
   - expected: `pdf_非国家工作人员行贿案_2_9833`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0695`
   - law: `非国家工作人员行贿案`
   - type: `pdf_case_sliding` | span: `single`

512. [case_reasoning][direct] 案例中被处罚的人员获得了多少赔偿？
   - expected: `pdf_非国家工作人员行贿案_2_9833`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0719`
   - law: `非国家工作人员行贿案`
   - type: `pdf_case_sliding` | span: `single`

513. [scenario_judgment][scenario] 这种行贿行为会导致哪些法律后果？
   - expected: `pdf_非国家工作人员行贿案_2_9833`
   - top1: `parent_中华人民共和国招标投标法_53_56_3085`
   - law: `非国家工作人员行贿案`
   - type: `pdf_case_sliding` | span: `single`

514. [scenario_judgment][scenario] 这种招标过程中的不正当手段有什么法律风险？
   - expected: `pdf_非国家工作人员行贿案_1_4620`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0130`
   - law: `非国家工作人员行贿案`
   - type: `pdf_case_sliding` | span: `single`

515. [scenario_judgment][scenario] 案例中公司给竞标方的总金额是多少？这种行为合法吗？
   - expected: `pdf_非国家工作人员行贿案_1_4620`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0658`
   - law: `非国家工作人员行贿案`
   - type: `pdf_case_sliding` | span: `single`

516. [procedure][direct] 工程款执行完毕后还需要关注哪些后续事宜？
   - expected: `pdf_建设工程施工合同纠纷案_11_5255`
   - top1: `parent_中华人民共和国预算法实施条例_87_3331_2774`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

517. [procedure][scenario] 我们公司在工程投标过程中，担心竞争对手获取标底影响公平竞争，有什么合规建议？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_8_322`
   - top1: `parent_工程建设项目施工招标投标办法_71_73_9080`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

518. [responsibility][scenario] 如果我们的公司参与招投标项目时，发现竞争对手可能获取了标底信息，应该怎么维护自身权益？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_8_322`
   - top1: `parent_工程建设项目施工招标投标办法_71_73_9080`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

519. [scenario_judgment][scenario] 我们公司在建筑工程项目中，遇到工程量鉴定定的争议，应该如何处理？
   - expected: `pdf_建设工程施工合同纠纷案_10_42`
   - top1: `pdf_建设工程施工合同纠纷案_5_6392`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

520. [scenario_judgment][scenario] 在建设工程施工合同纠纷中，当双方对工程量鉴定结果有分歧时，我们应该如何维权？
   - expected: `pdf_建设工程施工合同纠纷案_10_42`
   - top1: `pdf_建设工程施工合同纠纷案_20_7528`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

521. [scenario_judgment][scenario] 当竞争对手获取了我们的投标商业秘密后，对我们的投标竞争力会产生怎样的影响？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_4_1138`
   - top1: `pdf_运输服务公司串通投标不正当竞争纠纷案_5_1403`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

522. [scenario_judgment][scenario] 如果我们的公司作为投标人，在投标过程中发现竞争对手可能窃取了我们的商业秘密，应该采取哪些措施？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_4_1138`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0282`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

523. [scenario_judgment][scenario] 我们公司在招投标过程中，担心竞争对手获取标底信息，该怎样保障自身合法权益？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_8_322`
   - top1: `parent_中华人民共和国招标投标法_22_25_5839`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

524. [scenario_judgment][scenario] 如果发现竞争对手获取了我们的投标商业秘密，应该怎么维护公司利益？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_8_322`
   - top1: `pdf_运输服务公司串通投标不正当竞争纠纷案_5_1403`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

525. [scenario_judgment][scenario] 我们公司在工程项目建设中，遇到工程量鉴定争议，应该如何处理？
   - expected: `pdf_建设工程施工合同纠纷案_10_42`
   - top1: `pdf_建设工程施工合同纠纷案_5_6392`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

526. [scenario_judgment][scenario] 作为投标人，如果发现竞争对手窃取了我们的商业秘密，应该采取哪些措施？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_4_1138`
   - top1: `pdf_运输服务公司串通投标不正当竞争纠纷案_5_1403`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

527. [scenario_judgment][scenario] 竞争对手获取了我们的投标商业秘密后，对我们的投标竞争力会有什么影响？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_4_1138`
   - top1: `pdf_运输服务公司串通投标不正当竞争纠纷案_5_1403`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

528. [scenario_judgment][scenario] 如果发现竞争对手获取了我们的投标商业秘密，应该怎么维护公司利益？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_8_322`
   - top1: `pdf_运输服务公司串通投标不正当竞争纠纷案_5_1403`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

529. [scenario_judgment][scenario] 我们公司在招投标过程中，担心竞争对手获取标底信息，该怎样保障自身合法权益？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_8_322`
   - top1: `parent_中华人民共和国招标投标法_22_25_5839`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

530. [scenario_judgment][scenario] 我们公司在工程项目建设中，遇到工程量鉴定争议，应该如何处理？
   - expected: `pdf_建设工程施工合同纠纷案_10_42`
   - top1: `pdf_建设工程施工合同纠纷案_5_6392`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

531. [scenario_judgment][scenario] 作为投标人，如果发现竞争对手窃取了我们的商业秘密，应该采取哪些措施？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_4_1138`
   - top1: `pdf_运输服务公司串通投标不正当竞争纠纷案_5_1403`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

532. [case_reasoning][scenario] 竞争对手获取了我们的投标商业秘密后，对我们的投标竞争力会有什么影响？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_4_1138`
   - top1: `pdf_运输服务公司串通投标不正当竞争纠纷案_5_1403`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

533. [scenario_judgment][scenario] 工程款拖欠后，我们该如何维护自身合法权益？
   - expected: `pdf_建工集团公司建设工程施工合同纠纷案_1_6151`
   - top1: `parent_华人民共和国招标投标法实施条例》及其他有_25_1004_108`
   - law: `建工集团公司建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

534. [condition_check][direct] 工程验收后对方拖欠工程款，合同里有没有约定结算方式？
   - expected: `pdf_建设工程施工合同纠纷案_5_6392`
   - top1: `pdf_建设工程施工合同纠纷案_0_8849`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

535. [condition_check][direct] 针对该工程拖欠情况，合同条款是否具有约束力？
   - expected: `pdf_建设工程施工合同纠纷案_5_6392`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0633`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

536. [procedure][direct] 工程款拖欠后，我们应通过何种方式确定工程款金额？
   - expected: `pdf_建设工程施工合同纠纷案_5_6392`
   - top1: `pdf_建设工程施工合同纠纷案_20_7528`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

537. [scenario_judgment][direct] 合同里的价款约定出现争议时，应该如何解决？
   - expected: `pdf_建设工程施工合同纠纷案_21_6686`
   - top1: `pdf_建设工程施工合同纠纷案_3_1293`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

538. [scenario_judgment][scenario] 在投标项目中，如果发现竞争对手存在串通投标行为，企业该如何合法维护自身权益？
   - expected: `pdf_串通投标、受贿案_0_5058`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0398`
   - law: `串通投标、受贿案`
   - type: `pdf_case_sliding` | span: `single`

539. [scenario_judgment][scenario] 员工因为投标时泄露标书信息导致公司中标失败，企业应该采取哪些合规措施来避免类似问题？
   - expected: `pdf_串通投标、受贿案_0_5058`
   - top1: `parent_中华人民共和国招标投标法_52_55_1901`
   - law: `串通投标、受贿案`
   - type: `pdf_case_sliding` | span: `single`

540. [scenario_judgment][scenario] 当我们在投标中发现竞争对手可能通过泄露标书信息获得优势，应该如何保护自身商业信息？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_7_1704`
   - top1: `pdf_运输服务公司串通投标不正当竞争纠纷案_9_9233`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

541. [scenario_judgment][scenario] 当我们公司投标后发现竞争对手中标是因为泄露了我们的投标方案，该怎么合法解决纠纷？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_1_7779`
   - top1: `parent_中华人民共和国招标投标法_52_55_1901`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

542. [case_reasoning][scenario] 如果投标项目里出现多家公司串通中标的情况，对我们公司意味着什么法律风险？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_7_1704`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0731`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

543. [procedure][direct] 建筑工程合同无效后，工程款利息应该从什么时候开始计算？
   - expected: `pdf_建设工程施工合同纠纷案_16_2787`
   - top1: `pdf_建设工程施工合同纠纷案_0_8849`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

544. [scenario_judgment][scenario] 如果公司投标前发现内部人员可能将标书信息透露给竞争对手，应该先做哪项工作？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_1_7779`
   - top1: `parent_工程建设项目施工招标投标办法_71_73_9080`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

545. [scenario_judgment][scenario] 我们公司在招投标过程中，如果工作人员和投标人存在串通行为，会面临怎样的法律后果？
   - expected: `pdf_串通投标、受贿案_5_8627`
   - top1: `pdf_串通投标、受贿案_4_779`
   - law: `串通投标、受贿案`
   - type: `pdf_case_sliding` | span: `single`

546. [scenario_judgment][scenario] 如果我们公司参与工程中标后，发现对方拖欠工程款，像案例里那样，我们应该怎么维护自己的合法权益呢？
   - expected: `pdf_建工集团公司建设工程施工合同纠纷案_2_629`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0625`
   - law: `建工集团公司建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

547. [scenario_judgment][scenario] 案例里的逾期付款利息计算方式，在实际业务操作中，我们能提前做哪些准备来规避高额利息呢？
   - expected: `pdf_建工集团公司建设工程施工合同纠纷案_2_629`
   - top1: `pdf_建工集团公司建设工程施工合同纠纷案_6_3374`
   - law: `建工集团公司建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

548. [scenario_judgment][scenario] 我们公司在工程项目中遇到实际施工人相关的纠纷，这类情况该如何处理呢？
   - expected: `pdf_建设工程施工合同纠纷案_9_4409`
   - top1: `pdf_建工集团公司建设工程施工合同纠纷案_10_1965`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

549. [scenario_judgment][scenario] 运输服务公司在招标项目中与其他公司串通投标，这种行为对实际业务意味着什么？我们公司应该如何防范此类不正当竞争？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_5_1403`
   - top1: `pdf_运输服务公司串通投标不正当竞争纠纷案_7_1704`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

550. [announcement_interpretation][scenario] 工程合同纠纷从一审到再审的流程是怎样的，像这个案例中的处理过程能参考吗？
   - expected: `pdf_建设工程施工合同纠纷案_9_4409`
   - top1: `pdf_建设工程施工合同纠纷案_34_5720`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

551. [responsibility][scenario] 企业在处理工程合同纠纷时，如何有效保护自身合法权益？
   - expected: `pdf_建设工程施工合同纠纷案_9_4409`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0156`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

552. [scenario_judgment][scenario] 建筑工程合同中如果施工队伍中途变更，签合同时需要注意哪些合规事项？
   - expected: `pdf_建设工程施工合同纠纷案_24_7451`
   - top1: `pdf_建设工程施工合同纠纷案_26_5099`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

553. [scenario_judgment][scenario] 建筑工程中标后更换施工队伍签合同时，之前的中标内容是否有效？
   - expected: `pdf_建设工程施工合同纠纷案_3_1293`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0666`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

554. [scenario_judgment][scenario] 建筑工程中标后签合同时，施工队伍变更后签合同需要注意什么？
   - expected: `pdf_建设工程施工合同纠纷案_3_1293`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0622`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

555. [scenario_judgment][scenario] 我们公司在进行建筑工程项目后，确定最终工程款的结算需要注意哪些环节呢？
   - expected: `pdf_建设工程施工合同纠纷案_30_6102`
   - top1: `pdf_建设工程施工合同纠纷案_32_2531`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

556. [scenario_judgment][scenario] 如果发现施工方存在质量争议，我们应该怎么处理这种情况？
   - expected: `pdf_建设工程施工合同纠纷案_30_6102`
   - top1: `parent_建设工程质量保证金管理办法_12_1216_8865`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

557. [scenario_judgment][scenario] 遇到工程质量争议时，应该如何有效举证？
   - expected: `pdf_建设工程施工合同纠纷案_20_7528`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0699`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

558. [definition][scenario] 国有建设用地使用权挂牌出让属于哪种竞拍形式？
   - expected: `pdf_非国家工作人员行贿案_4_7744`
   - top1: `parent_招标拍卖挂牌出让国有建设用地使用权规定_2_1012_9039`
   - law: `非国家工作人员行贿案`
   - type: `pdf_case_sliding` | span: `single`

559. [responsibility][direct] 采购项目中遇到违规情况，该找哪个部门投诉？
   - expected: `parent_集中采购机构是设区的市级以上人民政府依法_65_3106_1321`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0686`
   - law: `集中采购机构是设区的市级以上人民政府依法`
   - type: `pdf_law_parent` | span: `single`

560. [scenario_judgment][scenario] 如果我们在中标后超过规定时间才签订合同，会有什么后果吗？
   - expected: `parent_投资项目招标投标管理办法_23_2560_3953`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0626`
   - law: `投资项目招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

561. [condition_check][direct] 中标后签订合同有没有时间限制？签订合同时不能做什么类型的协议？
   - expected: `parent_投资项目招标投标管理办法_23_2560_3953`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0625`
   - law: `投资项目招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

562. [case_reasoning][direct] 机电产品国际招标中采用综合评价法有什么好处？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_6_1270_9673`
   - top1: `parent_进一步规范机电产品国际招标投标活动有关规_2_1266_709`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `single`

563. [scenario_judgment][direct] 如果中标后没按时签成交确认书，保证金会退回来吗？
   - expected: `parent_国家技术创新项目招标投标管理办法_20_2793_2111`
   - top1: `parent_中华人民共和国招标投标法实施条例_74_154_4698`
   - law: `国家技术创新项目招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

564. [scenario_judgment][direct] 如果中标后没按时签成交确认书，保证金会退回来吗？
   - expected: `parent_国家技术创新项目招标投标管理办法_20_2793_2111`
   - top1: `parent_中华人民共和国招标投标法实施条例_74_154_4698`
   - law: `国家技术创新项目招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

565. [scenario_judgment][scenario] 当我们公司中标供应商出现虚假承诺或违约情况，相关管理部门会如何处置？
   - expected: `parent_中央预算单位批量集中采购管理暂行办法_12_4336_8975`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_29_3724_2087`
   - law: `中央预算单位批量集中采购管理暂行办法`
   - type: `pdf_law_parent` | span: `single`

566. [scenario_judgment][scenario] 我们公司作为招标方，如果出现和投标人串通搞虚假招标的行为，会有什么处罚？
   - expected: `parent_机电产品国际招标评标专家及专家库管理办法_100_1390_9578`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0396`
   - law: `机电产品国际招标评标专家及专家库管理办法`
   - type: `pdf_law_parent` | span: `single`

567. [scenario_judgment][scenario] 评标委员会成员私自接触投标人会有怎样的处罚？
   - expected: `parent_机电产品国际招标评标专家及专家库管理办法_100_1390_9578`
   - top1: `parent_工程建设项目施工招标投标办法_78_82_5872`
   - law: `机电产品国际招标评标专家及专家库管理办法`
   - type: `pdf_law_parent` | span: `single`

568. [responsibility][direct] 如果发现招标投标活动存在违规情况，应该向哪个部门反映？
   - expected: `parent_标活动行政监督的职责分工意见的通知》等有_12_2009_5960`
   - top1: `parent_招标公告和公示信息发布管理办法_17_788_8139`
   - law: `标活动行政监督的职责分工意见的通知》等有关法`
   - type: `pdf_law_parent` | span: `single`

569. [scenario_judgment][direct] 我们公司作为招标方，如果出现和投标人串通搞虚假招标的行为，会有什么处罚？
   - expected: `parent_机电产品国际招标评标专家及专家库管理办法_100_1390_9578`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0396`
   - law: `机电产品国际招标评标专家及专家库管理办法`
   - type: `pdf_law_parent` | span: `single`

570. [scenario_judgment][direct] 评标委员会成员私自接触投标人会有怎样的处罚？
   - expected: `parent_机电产品国际招标评标专家及专家库管理办法_100_1390_9578`
   - top1: `parent_工程建设项目施工招标投标办法_78_82_5872`
   - law: `机电产品国际招标评标专家及专家库管理办法`
   - type: `pdf_law_parent` | span: `single`

571. [responsibility][direct] 如果发现招标投标活动存在违规情况，应该向哪个部门反映？
   - expected: `parent_标活动行政监督的职责分工意见的通知》等有_12_2009_5960`
   - top1: `parent_招标公告和公示信息发布管理办法_17_788_8139`
   - law: `标活动行政监督的职责分工意见的通知》等有关法`
   - type: `pdf_law_parent` | span: `single`

572. [procedure][direct] 我们公司在开展政府采购评审时，专家劳务费管理有哪些具体规定？
   - expected: `parent_中央国家机关政府采购中心专家劳务费管理办_1_3568_8243`
   - top1: `parent_中央国家机关政府采购中心专家劳务费管理办_7_3574_6706`
   - law: `中央国家机关政府采购中心专家劳务费管理办法`
   - type: `pdf_law_parent` | span: `single`

573. [procedure][direct] 水利工程招投标后，招标人对中标候选人有什么流程要求？
   - expected: `parent_水利工程建设项目招标投标管理规定_56_2289_9150`
   - top1: `parent_水利工程建设项目招标投标管理规定_51_2284_1799`
   - law: `水利工程建设项目招标投标管理规定`
   - type: `pdf_law_parent` | span: `single`

574. [procedure][direct] 水利项目招投标后，招标人对中标候选人的处理流程是怎样的？
   - expected: `parent_国家对潜在投标人或者投标人的资格条件有规_56_537_7734`
   - top1: `parent_水利工程建设项目招标投标管理规定_49_2282_3450`
   - law: `国家对潜在投标人或者投标人的资格条件有规定`
   - type: `pdf_law_parent` | span: `single`

575. [procedure][direct] 水利项目评标完成后，招标人需要完成哪些后续步骤？
   - expected: `parent_国家对潜在投标人或者投标人的资格条件有规_56_537_7734`
   - top1: `parent_水利工程建设项目重要设备材料采购招标投标_55_2420_6567`
   - law: `国家对潜在投标人或者投标人的资格条件有规定`
   - type: `pdf_law_parent` | span: `single`

576. [responsibility][direct] 水利项目招投标中，评标委员会提交报告后招标人有何义务？
   - expected: `parent_国家对潜在投标人或者投标人的资格条件有规_56_537_7734`
   - top1: `parent_水利工程建设项目重要设备材料采购招标投标_55_2420_6567`
   - law: `国家对潜在投标人或者投标人的资格条件有规定`
   - type: `pdf_law_parent` | span: `single`

577. [scenario_judgment][scenario] 我们公司在开展政府采购评审时，专家劳务费管理有哪些具体规定？
   - expected: `parent_中央国家机关政府采购中心专家劳务费管理办_1_3568_8243`
   - top1: `parent_中央国家机关政府采购中心专家劳务费管理办_7_3574_6706`
   - law: `中央国家机关政府采购中心专家劳务费管理办法`
   - type: `pdf_law_parent` | span: `single`

578. [procedure][scenario] 水利工程招投标后，招标人对中标候选人有什么流程要求？
   - expected: `parent_水利工程建设项目招标投标管理规定_56_2289_9150`
   - top1: `parent_水利工程建设项目招标投标管理规定_51_2284_1799`
   - law: `水利工程建设项目招标投标管理规定`
   - type: `pdf_law_parent` | span: `single`

579. [procedure][scenario] 水利项目招投标后，招标人对中标候选人的处理流程是怎样的？
   - expected: `parent_国家对潜在投标人或者投标人的资格条件有规_56_537_7734`
   - top1: `parent_水利工程建设项目招标投标管理规定_49_2282_3450`
   - law: `国家对潜在投标人或者投标人的资格条件有规定`
   - type: `pdf_law_parent` | span: `single`

580. [procedure][scenario] 水利项目评标完成后，招标人需要完成哪些后续步骤？
   - expected: `parent_国家对潜在投标人或者投标人的资格条件有规_56_537_7734`
   - top1: `parent_水利工程建设项目重要设备材料采购招标投标_55_2420_6567`
   - law: `国家对潜在投标人或者投标人的资格条件有规定`
   - type: `pdf_law_parent` | span: `single`

581. [procedure][scenario] 水利项目招投标中，评标委员会提交报告后招标人有何义务？
   - expected: `parent_国家对潜在投标人或者投标人的资格条件有规_56_537_7734`
   - top1: `parent_水利工程建设项目重要设备材料采购招标投标_55_2420_6567`
   - law: `国家对潜在投标人或者投标人的资格条件有规定`
   - type: `pdf_law_parent` | span: `single`

582. [responsibility][scenario] 我们公司与招标招标代理机构合作时，委托合同需要遵循什么规定？
   - expected: `parent_工程建设项目施工招标投标办法_23_25_3777`
   - top1: `parent_铁路建设工程招标投标实施办法_18_1922_8104`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `single`

583. [case_reasoning][scenario] 作为中标供应商，我们该如何做才能被评为优秀供应商？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_22_3717_1511`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_21_3716_9599`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

584. [procedure][direct] 我们进行该类采购项目时，需要遵循什么操作规程？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_43_3775_2327`
   - top1: `parent_交通运输部部属单位政府采购管理办法_29_3946_7341`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

585. [scenario_judgment][scenario] 作为中标供应商，我们该如何做才能被评为优秀供应商？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_22_3717_1511`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_21_3716_9599`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

586. [procedure][direct] 我们进行该类采购项目时，需要遵循什么操作规程？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_43_3775_2327`
   - top1: `parent_交通运输部部属单位政府采购管理办法_29_3946_7341`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

587. [scenario_judgment][scenario] 作为中标供应商，我们该如何做才能被评为优秀供应商？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_22_3717_1511`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_21_3716_9599`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

588. [procedure][direct] 我们进行该类采购项目时，需要遵循什么操作规程？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_43_3775_2327`
   - top1: `parent_交通运输部部属单位政府采购管理办法_29_3946_7341`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

589. [scenario_judgment][scenario] 作为中标供应商，我们该如何做才能被评为优秀供应商？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_22_3717_1511`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_21_3716_9599`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

590. [procedure][direct] 我们进行该类采购项目时，需要遵循什么操作规程？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_43_3775_2327`
   - top1: `parent_交通运输部部属单位政府采购管理办法_29_3946_7341`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

591. [scenario_judgment][scenario] 作为中标供应商，我们该如何做才能被评为优秀供应商？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_22_3717_1511`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_21_3716_9599`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

592. [procedure][direct] 我们进行该类采购项目时，需要遵循什么操作规程？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_43_3775_2327`
   - top1: `parent_交通运输部部属单位政府采购管理办法_29_3946_7341`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

593. [scenario_judgment][scenario] 作为中标供应商，我们该如何做才能被评为优秀供应商？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_22_3717_1511`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_21_3716_9599`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

594. [procedure][direct] 我们进行该类采购项目时，需要遵循什么操作规程？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_43_3775_2327`
   - top1: `parent_交通运输部部属单位政府采购管理办法_29_3946_7341`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

595. [scenario_judgment][scenario] 作为中标供应商，我们该如何做才能被评为优秀供应商？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_22_3717_1511`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_21_3716_9599`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

596. [procedure][scenario] 关于这个采购项目的操作流程，我们还需要注意哪些事项？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_43_3775_2327`
   - top1: `parent_交通运输部部属单位政府采购管理办法_29_3946_7341`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

597. [procedure][direct] 我们进行该类采购项目时，需要遵循什么操作规程？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_43_3775_2327`
   - top1: `parent_交通运输部部属单位政府采购管理办法_29_3946_7341`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

598. [procedure][scenario] 关于这个采购项目的操作流程，我们还应该关注哪些方面？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_43_3775_2327`
   - top1: `parent_交通运输部部属单位政府采购管理办法_29_3946_7341`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

599. [scenario_judgment][direct] 作为中标供应商，我们该如何做才能被评为优秀供应商？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_22_3717_1511`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_21_3716_9599`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

600. [procedure][direct] 我们进行该类采购项目时，需要遵循什么操作规程？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_43_3775_2327`
   - top1: `parent_交通运输部部属单位政府采购管理办法_29_3946_7341`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

601. [scenario_judgment][direct] 关于这个采购项目的操作流程，我们还需要了解哪些配套规定？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_43_3775_2327`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0102`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

602. [scenario_judgment][direct] 作为中标供应商，我们该如何做才能被评为优秀供应商？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_22_3717_1511`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_21_3716_9599`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

603. [procedure][direct] 我们进行该类采购项目时，需要遵循什么操作规程？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_43_3775_2327`
   - top1: `parent_交通运输部部属单位政府采购管理办法_29_3946_7341`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

604. [scenario_judgment][direct] 关于这个采购项目的操作流程，我们还应该关注哪些配套文件？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_43_3775_2327`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_9_3838_4467`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

605. [scenario_judgment][direct] 作为中标供应商，我们该如何做才能被评为优秀供应商？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_22_3717_1511`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_21_3716_9599`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

606. [procedure][direct] 我们进行该类采购项目时，需要遵循什么操作规程？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_43_3775_2327`
   - top1: `parent_交通运输部部属单位政府采购管理办法_29_3946_7341`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

607. [scenario_judgment][direct] 作为中标供应商，我们该如何做才能被评为优秀供应商？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_22_3717_1511`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_21_3716_9599`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

608. [scenario_judgment][direct] 关于这个采购项目的操作流程，我们还应该了解哪些配套文件？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_43_3775_2327`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_9_3838_4467`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

609. [procedure][direct] 我们进行该类采购项目时，需要遵循什么操作规程？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_43_3775_2327`
   - top1: `parent_交通运输部部属单位政府采购管理办法_29_3946_7341`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

610. [procedure][direct] 关于这个采购项目的操作流程，我们还应该关注哪些配套文件？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_43_3775_2327`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_9_3838_4467`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

611. [scenario_judgment][direct] 如果有人非法干预我们的评标过程，会有什么后果吗？
   - expected: `parent_道路旅客运输班线经营权招标投标办法_37_1797_6405`
   - top1: `parent_政府采购非招标采购方式管理办法_58_4235_5825`
   - law: `道路旅客运输班线经营权招标投标办法`
   - type: `pdf_law_parent` | span: `single`

612. [scenario_judgment][direct] 如果有人非法干预我们的评标过程，会有什么后果吗？
   - expected: `parent_道路旅客运输班线经营权招标投标办法_37_1797_6405`
   - top1: `parent_政府采购非招标采购方式管理办法_58_4235_5825`
   - law: `道路旅客运输班线经营权招标投标办法`
   - type: `pdf_law_parent` | span: `single`

613. [scenario_judgment][direct] 如果有人非法干预我们的评标过程，会有什么后果吗？
   - expected: `parent_道路旅客运输班线经营权招标投标办法_37_1797_6405`
   - top1: `parent_政府采购非招标采购方式管理办法_58_4235_5825`
   - law: `道路旅客运输班线经营权招标投标办法`
   - type: `pdf_law_parent` | span: `single`

614. [condition_check][synonym] 什么情况下这些平台会要求采用电子招标投标的方式呀？
   - expected: `policy_103`
   - top1: `parent_电子招标投标办法_6_699_4136`
   - law: `【建设工程】工程总承包电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

615. [procedure][scenario] 中标之后，在哪些平台上还需要继续办理后续的合同签订手续呀？
   - expected: `policy_103`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0087`
   - law: `【建设工程】工程总承包电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

616. [responsibility][scenario] 工程总承包项目的招标投标工作一般由哪个部门来负责安排呀？
   - expected: `policy_103`
   - top1: `parent_工程建设项目施工招标投标办法_6_504_922`
   - law: `【建设工程】工程总承包电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

617. [scenario_judgment][synonym] 政府采购领域整顿市场秩序后，我们公司在参与政府采购时需要注意哪些合规要求呀？
   - expected: `policy_161`
   - top1: `parent_财政部关于促进政府采购公平竞争优化营商环_68_4037_2542`
   - law: `财政部有关负责人就《政府采购领域 “整顿市场秩...`
   - type: `policy_doc` | span: `single`

618. [comparison][cross_reference] 工程总承包电子招标投标和我们平时说的传统招标投标有什么不同呀？
   - expected: `policy_103`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0059`
   - law: `【建设工程】工程总承包电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

619. [responsibility][scenario] 政府采购中投标人异议应该找哪个部门投诉呀？
   - expected: `policy_161`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0686`
   - law: `财政部有关负责人就《政府采购领域 “整顿市场秩...`
   - type: `policy_doc` | span: `single`

620. [condition_check][scenario] 什么情况下政府采购可以不用公开招标直接指定供应商呀？
   - expected: `policy_161`
   - top1: `parent_中华人民共和国政府采购法实施条例_32_27_3943`
   - law: `财政部有关负责人就《政府采购领域 “整顿市场秩...`
   - type: `policy_doc` | span: `single`

621. [procedure][scenario] 政府采购整顿市场秩序后，中标后签合同之前还要走哪些流程呀？
   - expected: `policy_161`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_10_3705_3409`
   - law: `财政部有关负责人就《政府采购领域 “整顿市场秩...`
   - type: `policy_doc` | span: `single`

622. [definition][synonym] 政府采购领域‘整顿市场秩序’具体指哪些违规行为呀？
   - expected: `policy_161`
   - top1: `policy_203`
   - law: `财政部有关负责人就《政府采购领域 “整顿市场秩...`
   - type: `policy_doc` | span: `single`

623. [scenario_judgment][scenario] 中央国家机关政府集中采购目录实施后，我们公司采购时需要注意哪些目录内的项目呀？
   - expected: `policy_154`
   - top1: `parent_中华人民共和国政府采购法实施条例_3_4_3325`
   - law: `关于印发《中央国家机关政府集中采购目录实施方...`
   - type: `policy_doc` | span: `single`

624. [condition_check][synonym] 什么情况下政府采购项目必须纳入中央国家机关政府集中采购目录呀？
   - expected: `policy_154`
   - top1: `parent_中华人民共和国政府采购法_18_2974_9255`
   - law: `关于印发《中央国家机关政府集中采购目录实施方...`
   - type: `policy_doc` | span: `single`

625. [procedure][scenario] 中标后，在中央国家机关政府集中采购目录项目上签合同前还要走哪些流程呀？
   - expected: `policy_154`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_10_3705_3409`
   - law: `关于印发《中央国家机关政府集中采购目录实施方...`
   - type: `policy_doc` | span: `single`

626. [comparison][cross_reference] 中央国家机关政府集中采购目录和我们普通的政府采购目录有什么区别呀？
   - expected: `policy_154`
   - top1: `parent_中华人民共和国政府采购法_7_2963_5636`
   - law: `关于印发《中央国家机关政府集中采购目录实施方...`
   - type: `policy_doc` | span: `single`

627. [scenario_judgment][direct] 我们公司中标后多久需要提交投标电子保函？
   - expected: `policy_3`
   - top1: `parent_水利工程建设项目招标投标管理规定_52_2285_5052`
   - law: `关于印发《上海市公共资源交易中心公共服务清单 （2024年版）》的通知`
   - type: `policy_doc` | span: `single`

628. [condition_check][synonym] 政府采购分平台在什么条件下可以使用竞争性磋商方式？
   - expected: `policy_3`
   - top1: `parent_政府采购竞争性磋商采购方式管理暂行办法_3_4126_5145`
   - law: `关于印发《上海市公共资源交易中心公共服务清单 （2024年版）》的通知`
   - type: `policy_doc` | span: `single`

629. [procedure][scenario] 中标后签订合同前，还需要经过哪些公共服务流程？
   - expected: `policy_3`
   - top1: `parent_评标委员会应组织全体评标委员学习有关规定_60_1961_7592`
   - law: `关于印发《上海市公共资源交易中心公共服务清单 （2024年版）》的通知`
   - type: `policy_doc` | span: `single`

630. [responsibility][direct] 哪个部门负责监督政府采购分平台的公共服务工作？
   - expected: `policy_3`
   - top1: `parent_《中华人民共和国政府采购法实施条例》等有_6_4378_9721`
   - law: `关于印发《上海市公共资源交易中心公共服务清单 （2024年版）》的通知`
   - type: `policy_doc` | span: `single`

631. [comparison][scenario] 公开招标和邀请招标在公共服务流程上的区别是什么？
   - expected: `policy_3`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0054`
   - law: `关于印发《上海市公共资源交易中心公共服务清单 （2024年版）》的通知`
   - type: `policy_doc` | span: `single`

632. [definition][synonym] 什么是政府采购公共服务清单？其作用是什么？
   - expected: `policy_3`
   - top1: `parent_政府购买服务管理办法_11_4348_4471`
   - law: `关于印发《上海市公共资源交易中心公共服务清单 （2024年版）》的通知`
   - type: `policy_doc` | span: `single`

633. [scenario_judgment][synonym] 监察法中关于公职人员廉洁自律的规定有哪些？
   - expected: `policy_196`
   - top1: `parent_中华人民共和国政府采购法_69_3027_9438`
   - law: `中华人民共和国监察法`
   - type: `policy_doc` | span: `single`

634. [condition_check][synonym] 什么情况下公职人员会被监察机关调查？
   - expected: `policy_196`
   - top1: `parent_标活动行政监督的职责分工意见的通知》等有_24_2021_1528`
   - law: `中华人民共和国监察法`
   - type: `policy_doc` | span: `single`

635. [procedure][scenario] 监察调查的程序是怎样的？从受理到结论需要多长时间？
   - expected: `policy_196`
   - top1: `parent_机电产品国际招标评标专家及专家库管理办法_84_1369_8556`
   - law: `中华人民共和国监察法`
   - type: `policy_doc` | span: `single`

636. [responsibility][synonym] 哪个部门负责监察公职人员的责任？
   - expected: `policy_196`
   - top1: `parent_标活动行政监督的职责分工意见的通知》等有_24_2021_1528`
   - law: `中华人民共和国监察法`
   - type: `policy_doc` | span: `single`

637. [definition][synonym] 什么是监察法中的'公职人员'？
   - expected: `policy_196`
   - top1: `parent_中华人民共和国政府采购法_69_3027_9438`
   - law: `中华人民共和国监察法`
   - type: `policy_doc` | span: `single`

638. [comparison][scenario] 监察法和刑法在惩处公职人员腐败方面的区别是什么？
   - expected: `policy_196`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0750`
   - law: `中华人民共和国监察法`
   - type: `policy_doc` | span: `single`

639. [definition][synonym] 哪些行为会被认定为间谍活动？
   - expected: `policy_177`
   - top1: `parent_及教学资源招标采购管理办法_19_2899_9454`
   - law: `中华人民共和国反间谍法`
   - type: `policy_doc` | span: `single`

640. [procedure][scenario] 发现间谍活动后，第一步该联系哪个部门？
   - expected: `policy_177`
   - top1: `parent_监督处理中华人民共和国行政处罚法_50_866_2349`
   - law: `中华人民共和国反间谍法`
   - type: `policy_doc` | span: `single`

641. [scenario_judgment][scenario] 发现有人试图获取我公司的商业机密信息，我们应该怎么做？
   - expected: `policy_177`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0749`
   - law: `中华人民共和国反间谍法`
   - type: `policy_doc` | span: `single`

642. [responsibility][cross_reference] 企业负责人在防范间谍风险方面有哪些责任？
   - expected: `policy_177`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0298`
   - law: `中华人民共和国反间谍法`
   - type: `policy_doc` | span: `single`

643. [comparison][synonym] 间谍活动和其他违法活动有什么区别？
   - expected: `policy_177`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0727`
   - law: `中华人民共和国反间谍法`
   - type: `policy_doc` | span: `single`

644. [condition_check][direct] 普通群众发现间谍活动能帮忙吗？
   - expected: `policy_177`
   - top1: `parent_监督处理中华人民共和国行政处罚法_54_871_1569`
   - law: `中华人民共和国反间谍法`
   - type: `policy_doc` | span: `single`

645. [condition_check][synonym] 什么情况下工程招标必须使用电子平台？
   - expected: `policy_81`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0087`
   - law: `【建设工程】电子招标投标交易平台投标人操作指南`
   - type: `policy_doc` | span: `single`

646. [procedure][scenario] 中标后签合同前，还需要走哪些流程？
   - expected: `policy_81`
   - top1: `parent_评标委员会应组织全体评标委员学习有关规定_60_1961_7592`
   - law: `【建设工程】电子招标投标交易平台投标人操作指南`
   - type: `policy_doc` | span: `single`

647. [procedure][scenario] 我们公司参与工程投标，需要提前做哪些准备工作？
   - expected: `policy_81`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_14_3843_6875`
   - law: `【建设工程】电子招标投标交易平台投标人操作指南`
   - type: `policy_doc` | span: `single`

648. [responsibility][scenario] 投标人在工程招标中有什么权利和义务？
   - expected: `policy_81`
   - top1: `parent_铁路建设工程招标投标实施办法_36_1943_2773`
   - law: `【建设工程】电子招标投标交易平台投标人操作指南`
   - type: `policy_doc` | span: `single`

649. [comparison][synonym] 公开招标和邀请招标在投标人准备上有什么不同？
   - expected: `policy_81`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0054`
   - law: `【建设工程】电子招标投标交易平台投标人操作指南`
   - type: `policy_doc` | span: `single`

650. [procedure][scenario] 投标截止前修改投标文件怎么操作？
   - expected: `policy_81`
   - top1: `parent_政府采购货物和服务招标投标管理办法_34_3393_3187`
   - law: `【建设工程】电子招标投标交易平台投标人操作指南`
   - type: `policy_doc` | span: `single`

651. [condition_check][synonym] 什么情况下土地交易必须采用招标拍卖挂牌方式？
   - expected: `policy_90`
   - top1: `parent_招标拍卖挂牌出让国有建设用地使用权规定_4_1014_2021`
   - law: `【土地交易】关于印发《上海市国有建设用地使用权招标拍卖挂牌出让业务流程及操作规范`
   - type: `policy_doc` | span: `single`

652. [procedure][scenario] 土地交易公告发布后，投标人如何参与？
   - expected: `policy_90`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0015`
   - law: `【土地交易】关于印发《上海市国有建设用地使用权招标拍卖挂牌出让业务流程及操作规范`
   - type: `policy_doc` | span: `single`

653. [comparison][synonym] 招标和拍卖在土地交易中有何不同？
   - expected: `policy_90`
   - top1: `parent_招标拍卖挂牌出让国有建设用地使用权规定_2_1012_9039`
   - law: `【土地交易】关于印发《上海市国有建设用地使用权招标拍卖挂牌出让业务流程及操作规范`
   - type: `policy_doc` | span: `single`

654. [scenario_judgment][scenario] 我们企业在参与英国政府采购项目时，需要提前准备哪些必要的资质证明文件？
   - expected: `policy_186`
   - top1: `parent_中华人民共和国政府采购法实施条例_22_19_7099`
   - law: `英国政府采购制度（下）`
   - type: `policy_doc` | span: `single`

655. [scenario_judgment][synonym] 如果在英国政府采购过程中使用不符合规范的专家进行评审，企业会面临怎样的处罚后果？
   - expected: `policy_186`
   - top1: `parent_政府采购评审专家管理办法_29_3541_2977`
   - law: `英国政府采购制度（下）`
   - type: `policy_doc` | span: `single`

656. [procedure][scenario] 英国政府采购项目的中标公示一般需要多长时间？中标后还需要经过哪些后续流程？
   - expected: `policy_186`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0578`
   - law: `英国政府采购制度（下）`
   - type: `policy_doc` | span: `single`

657. [responsibility][synonym] 企业在申请加入英国政府采购专家库时，需要向哪个政府部门提交申请材料？
   - expected: `policy_186`
   - top1: `parent_政府采购评审专家管理办法_9_3537_1266`
   - law: `英国政府采购制度（下）`
   - type: `policy_doc` | span: `single`

658. [definition][synonym] 英国政府采购中所说的‘合规性审查’具体包含哪些方面的内容？
   - expected: `policy_186`
   - top1: `parent_《中华人民共和国政府采购法实施条例》等有_30_4021_6418`
   - law: `英国政府采购制度（下）`
   - type: `policy_doc` | span: `single`

659. [comparison][cross_reference] 英国政府采购中的‘竞争性谈判’和‘公开招标’相比，对企业投标有什么不同影响？
   - expected: `policy_186`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0023`
   - law: `英国政府采购制度（下）`
   - type: `policy_doc` | span: `single`

660. [definition][synonym] 综合专家库内的专家在评标评审时，主要负责完成哪些核心工作？
   - expected: `policy_12`
   - top1: `parent_系统工程综合评标专家库管理办法_12_1897_3188`
   - law: `上海市公共资源交易综合专家库管理规则（试行）`
   - type: `policy_doc` | span: `single`

661. [scenario_judgment][scenario] 我们公司被国家审计部门选中进行审计，需要提前做好哪些准备工作？
   - expected: `policy_178`
   - top1: `parent_中华人民共和国审计法实施条例_35_306_4697`
   - law: `中华人民共和国审计法`
   - type: `policy_doc` | span: `single`

662. [procedure][scenario] 公司接受审计后，审计机构给出的整改期限一般是多久？需要提交什么样的整改方案？
   - expected: `policy_178`
   - top1: `parent_中华人民共和国审计法实施条例_35_306_4697`
   - law: `中华人民共和国审计法`
   - type: `policy_doc` | span: `single`

663. [scenario_judgment][synonym] 审计过程中如果发现公司存在违反审计法的行为，会采取什么样的处罚和整改措施？
   - expected: `policy_178`
   - top1: `parent_中华人民共和国审计法实施条例_47_318_4976`
   - law: `中华人民共和国审计法`
   - type: `policy_doc` | span: `single`

664. [responsibility][synonym] 审计专家是由哪个政府部门任命和管理的？
   - expected: `policy_178`
   - top1: `parent_中华人民共和国审计法_8_225_2224`
   - law: `中华人民共和国审计法`
   - type: `policy_doc` | span: `single`

665. [scenario_judgment][scenario] 公司完成审计整改后，如何跟踪和验证整改效果？
   - expected: `policy_178`
   - top1: `parent_中华人民共和国审计法_4_221_7643`
   - law: `中华人民共和国审计法`
   - type: `policy_doc` | span: `single`

666. [definition][synonym] 审计法中对‘审计监督’的定义是什么？具体包含哪些内容？
   - expected: `policy_178`
   - top1: `parent_中华人民共和国审计法_12_229_4614`
   - law: `中华人民共和国审计法`
   - type: `policy_doc` | span: `single`

667. [scenario_judgment][synonym] 如果我们公司在政府采购中使用差别歧视条款，会面临什么样的处罚或后果？
   - expected: `policy_203`
   - top1: `parent_工程建设项目施工招标投标办法_70_72_2124`
   - law: `财政部 公安部 市场监管总局关于开展2...`
   - type: `policy_doc` | span: `single`

668. [condition_check][scenario] 政府采购项目在什么情况下可以不招标直接指定供应商？
   - expected: `policy_203`
   - top1: `parent_政府采购活动有关问题的通知_27_4121_9390`
   - law: `财政部 公安部 市场监管总局关于开展2...`
   - type: `policy_doc` | span: `single`

669. [procedure][scenario] 政府采购项目从启动到中标，一般需要经过哪些主要流程？
   - expected: `policy_203`
   - top1: `parent_交通运输部部属单位政府采购管理办法_29_3946_7341`
   - law: `财政部 公安部 市场监管总局关于开展2...`
   - type: `policy_doc` | span: `single`

670. [responsibility][scenario] 企业在政府采购过程中发现代理机构乱收费，应该向哪个部门举报或投诉？
   - expected: `policy_203`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0686`
   - law: `财政部 公安部 市场监管总局关于开展2...`
   - type: `policy_doc` | span: `single`

671. [scenario_judgment][scenario] 企业在参与西班牙政府采购项目时，需要注意哪些合规要求？
   - expected: `policy_185`
   - top1: `parent_《中华人民共和国政府采购法实施条例》等有_9_3999_7727`
   - law: `西班牙政府采购制度`
   - type: `policy_doc` | span: `single`

672. [definition][synonym] 西班牙的政府采购制度有什么特点？
   - expected: `policy_185`
   - top1: `parent_财政部关于推进和完善服务项目政府采购有关_27_3501_7020`
   - law: `西班牙政府采购制度`
   - type: `policy_doc` | span: `single`

673. [procedure][scenario] 西班牙政府采购项目的评标流程是怎样的？
   - expected: `policy_185`
   - top1: `parent_集中采购机构是设区的市级以上人民政府依法_34_3074_5699`
   - law: `西班牙政府采购制度`
   - type: `policy_doc` | span: `single`

674. [scenario_judgment][synonym] 如果我们公司在政府采购中使用差别歧视条款，会面临什么样的处罚或后果？
   - expected: `policy_203`
   - top1: `parent_工程建设项目施工招标投标办法_70_72_2124`
   - law: `财政部 公安部 市场监管总局关于开展2...`
   - type: `policy_doc` | span: `single`

675. [condition_check][scenario] 政府采购项目在什么情况下可以不招标直接指定供应商？
   - expected: `policy_203`
   - top1: `parent_政府采购活动有关问题的通知_27_4121_9390`
   - law: `财政部 公安部 市场监管总局关于开展2...`
   - type: `policy_doc` | span: `single`

676. [procedure][scenario] 政府采购项目从启动到中标，一般需要经过哪些主要流程？
   - expected: `policy_203`
   - top1: `parent_交通运输部部属单位政府采购管理办法_29_3946_7341`
   - law: `财政部 公安部 市场监管总局关于开展2...`
   - type: `policy_doc` | span: `single`

677. [responsibility][scenario] 企业在政府采购过程中发现代理机构乱收费，应该向哪个部门举报或投诉？
   - expected: `policy_203`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0686`
   - law: `财政部 公安部 市场监管总局关于开展2...`
   - type: `policy_doc` | span: `single`

678. [definition][synonym] 西班牙的政府采购制度有什么特点？
   - expected: `policy_185`
   - top1: `parent_财政部关于推进和完善服务项目政府采购有关_27_3501_7020`
   - law: `西班牙政府采购制度`
   - type: `policy_doc` | span: `single`

679. [scenario_judgment][scenario] 企业在参与西班牙政府采购项目时，需要注意哪些合规要求？
   - expected: `policy_185`
   - top1: `parent_《中华人民共和国政府采购法实施条例》等有_9_3999_7727`
   - law: `西班牙政府采购制度`
   - type: `policy_doc` | span: `single`

680. [procedure][scenario] 西班牙政府采购项目的评标流程是怎样的？
   - expected: `policy_185`
   - top1: `parent_集中采购机构是设区的市级以上人民政府依法_34_3074_5699`
   - law: `西班牙政府采购制度`
   - type: `policy_doc` | span: `single`

681. [scenario_judgment][synonym] 如果我们公司在政府采购中使用差别歧视条款，会面临什么样的处罚或后果？
   - expected: `policy_203`
   - top1: `parent_工程建设项目施工招标投标办法_70_72_2124`
   - law: `财政部 公安部 市场监管总局关于开展2...`
   - type: `policy_doc` | span: `single`

682. [condition_check][scenario] 政府采购项目在什么情况下可以不招标直接指定供应商？
   - expected: `policy_203`
   - top1: `parent_政府采购活动有关问题的通知_27_4121_9390`
   - law: `财政部 公安部 市场监管总局关于开展2...`
   - type: `policy_doc` | span: `single`

683. [procedure][scenario] 政府采购项目从启动到中标，一般需要经过哪些主要流程？
   - expected: `policy_203`
   - top1: `parent_交通运输部部属单位政府采购管理办法_29_3946_7341`
   - law: `财政部 公安部 市场监管总局关于开展2...`
   - type: `policy_doc` | span: `single`

684. [responsibility][scenario] 企业在政府采购过程中发现代理机构乱收费，应该向哪个部门举报或投诉？
   - expected: `policy_203`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0686`
   - law: `财政部 公安部 市场监管总局关于开展2...`
   - type: `policy_doc` | span: `single`

685. [definition][synonym] 西班牙的政府采购制度有什么特点？
   - expected: `policy_185`
   - top1: `parent_财政部关于推进和完善服务项目政府采购有关_27_3501_7020`
   - law: `西班牙政府采购制度`
   - type: `policy_doc` | span: `single`

686. [scenario_judgment][scenario] 企业在参与西班牙政府采购项目时，需要注意哪些合规要求？
   - expected: `policy_185`
   - top1: `parent_《中华人民共和国政府采购法实施条例》等有_9_3999_7727`
   - law: `西班牙政府采购制度`
   - type: `policy_doc` | span: `single`

687. [procedure][scenario] 西班牙政府采购项目的评标流程是怎样的？
   - expected: `policy_185`
   - top1: `parent_集中采购机构是设区的市级以上人民政府依法_34_3074_5699`
   - law: `西班牙政府采购制度`
   - type: `policy_doc` | span: `single`

688. [scenario_judgment][scenario] 我们公司在做政府采购项目时，需要注意哪些合规要求？
   - expected: `policy_225`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_4_3699_4327`
   - law: `海南省财政厅关于切实做好2018年政府采购项目实施工作...`
   - type: `policy_doc` | span: `single`

689. [condition_check][synonym] 在广东省政府采购评审专家相关工作中，什么情况下可以调整评审专家？
   - expected: `policy_166`
   - top1: `parent_政府采购评审专家管理办法_17_3548_3703`
   - law: `广东省财政厅关于印发《广东省政府采购评审专家...`
   - type: `policy_doc` | span: `single`

690. [procedure][synonym] 政府采购项目中标后，我们需要多久完成合同签订？
   - expected: `policy_225`
   - top1: `parent_中华人民共和国政府采购法_46_3003_3920`
   - law: `海南省财政厅关于切实做好2018年政府采购项目实施工作...`
   - type: `policy_doc` | span: `single`

691. [responsibility][synonym] 政府采购过程中，哪些部门负责监督采购流程？
   - expected: `policy_36`
   - top1: `parent_中华人民共和国政府采购法_13_2969_6954`
   - law: `财政部关于加强政府采购活动内部控制管理的指导意见`
   - type: `policy_doc` | span: `single`

692. [scenario_judgment][cross_reference] 政府采购项目出现违规行为时，该怎么处理？
   - expected: `policy_225`
   - top1: `parent_《中华人民共和国政府采购法实施条例》等有_38_4030_8696`
   - law: `海南省财政厅关于切实做好2018年政府采购项目实施工作...`
   - type: `policy_doc` | span: `single`

693. [procedure][scenario] 中标后签节能产品采购合同之前，还要走哪些流程？
   - expected: `policy_33`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_10_3705_3409`
   - law: `财政部、发展改革委关于印发节能产品政府采购品目清单的通知`
   - type: `policy_doc` | span: `single`

694. [condition_check][synonym] 什么情况下政府采购可以不采用公开招标方式而采用其他方式？
   - expected: `policy_170`
   - top1: `parent_中华人民共和国政府采购法实施条例_32_27_3943`
   - law: `财政部 工业和信息化部关于印发《数据库政府采购...`
   - type: `policy_doc` | span: `single`

695. [responsibility][synonym] 政府采购中，供应商的资质需要满足哪些要求？
   - expected: `policy_170`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0295`
   - law: `财政部 工业和信息化部关于印发《数据库政府采购...`
   - type: `policy_doc` | span: `single`

696. [procedure][scenario] 从发布招标公告到签订合同，政府采购的一般流程是怎样的？
   - expected: `policy_170`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0065`
   - law: `财政部 工业和信息化部关于印发《数据库政府采购...`
   - type: `policy_doc` | span: `single`

697. [scenario_judgment][scenario] 我们公司在编制年度预算时，需要遵循哪些法律依据？
   - expected: `policy_190`
   - top1: `parent_中华人民共和国预算法_32_3166_9265`
   - law: `中华人民共和国预算法实施条例`
   - type: `policy_doc` | span: `single`

698. [responsibility][scenario] 如果我们在政府采购过程中发现供应商存在违规行为，应该找哪个部门投诉？
   - expected: `policy_170`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0686`
   - law: `财政部 工业和信息化部关于印发《数据库政府采购...`
   - type: `policy_doc` | span: `single`

699. [definition][synonym] 预算法实施条例中对政府债务的规定有哪些？
   - expected: `policy_190`
   - top1: `parent_中华人民共和国预算法实施条例_45_3285_8490`
   - law: `中华人民共和国预算法实施条例`
   - type: `policy_doc` | span: `single`

700. [comparison][synonym] 预算法实施条例与企业单位的财务预算有什么关系？
   - expected: `policy_190`
   - top1: `parent_中华人民共和国预算法实施条例_61_3303_1807`
   - law: `中华人民共和国预算法实施条例`
   - type: `policy_doc` | span: `single`

701. [procedure][scenario] 从预算编制到执行，，一般需要经过哪些主要步骤？
   - expected: `policy_190`
   - top1: `parent_中华人民共和国预算法实施条例_53_3294_1607`
   - law: `中华人民共和国预算法实施条例`
   - type: `policy_doc` | span: `single`

702. [scenario_judgment][scenario] 如果我们的预算执行出现偏差，应该如何调整？
   - expected: `policy_190`
   - top1: `parent_中华人民共和国预算法_67_3202_9062`
   - law: `中华人民共和国预算法实施条例`
   - type: `policy_doc` | span: `single`

703. [definition][synonym] 预算法实施条例中关于预算公开的要求是什么？
   - expected: `policy_190`
   - top1: `parent_中华人民共和国预算法实施条例_6_3243_3830`
   - law: `中华人民共和国预算法实施条例`
   - type: `policy_doc` | span: `single`

704. [condition_check][synonym] 我们公司做政府采购项目，什么情况可以直接指定供应商？
   - expected: `policy_144`
   - top1: `parent_中华人民共和国政府采购法实施条例_31_43_7159`
   - law: `中华人民共和国财政部令第87号《政府采购货物和...`
   - type: `policy_doc` | span: `single`

705. [procedure][scenario] 我们公司在参与公共资源交易时，需要注意哪些合规流程？
   - expected: `policy_74`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_18_4087_5620`
   - law: `【综合管理】上海市深化公共资源“一网交易”改革 三年行动方案（2024-2026`
   - type: `policy_doc` | span: `single`

706. [case_reasoning][cross_reference] 政府采购项目出现中标人变更的情况，该怎么处理？
   - expected: `policy_144`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0622`
   - law: `中华人民共和国财政部令第87号《政府采购货物和...`
   - type: `policy_doc` | span: `single`

707. [scenario_judgment][scenario] 我们公司要做招标项目，需要注意哪些合规要求？
   - expected: `policy_197`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0152`
   - law: `中华人民共和国招标投标法`
   - type: `policy_doc` | span: `single`

708. [condition_check][synonym] 什么情况下招标可以直接指定供应商？
   - expected: `policy_197`
   - top1: `parent_国家对潜在投标人或者投标人的资格条件有规_66_547_3745`
   - law: `中华人民共和国招标投标法`
   - type: `policy_doc` | span: `single`

709. [procedure][scenario] 中标后签合同需要经过哪些法定流程？
   - expected: `policy_197`
   - top1: `parent_民政部工程建设项目招标投标管理办法_10_2909_7305`
   - law: `中华人民共和国招标投标法`
   - type: `policy_doc` | span: `single`

710. [responsibility][synonym] 投标人对于评标结果有异议，应该向哪个部门投诉？
   - expected: `policy_197`
   - top1: `parent_铁路工程建设项目招标投标管理办法_38_2114_1384`
   - law: `中华人民共和国招标投标法`
   - type: `policy_doc` | span: `single`

711. [definition][synonym] 什么是招标投标？它包含哪些基本环节？
   - expected: `policy_197`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0065`
   - law: `中华人民共和国招标投标法`
   - type: `policy_doc` | span: `single`

712. [comparison][scenario] 公开招标和邀请招标对企业来说有什么不同？
   - expected: `policy_197`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0054`
   - law: `中华人民共和国招标投标法`
   - type: `policy_doc` | span: `single`

713. [procedure][scenario] 我们公司在参与公共资源交易时，需要注意哪些合规流程？
   - expected: `policy_74`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_18_4087_5620`
   - law: `【综合管理】上海市深化公共资源“一网交易”改革 三年行动方案（2024-2026`
   - type: `policy_doc` | span: `single`

714. [scenario_judgment][scenario] 我们公司要做招标项目，需要注意哪些合规要求？
   - expected: `policy_197`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0152`
   - law: `中华人民共和国招标投标法`
   - type: `policy_doc` | span: `single`

715. [condition_check][synonym] 什么情况下招标可以直接指定供应商？
   - expected: `policy_197`
   - top1: `parent_国家对潜在投标人或者投标人的资格条件有规_66_547_3745`
   - law: `中华人民共和国招标投标法`
   - type: `policy_doc` | span: `single`

716. [procedure][scenario] 中标后签合同需要经过哪些法定流程？
   - expected: `policy_197`
   - top1: `parent_民政部工程建设项目招标投标管理办法_10_2909_7305`
   - law: `中华人民共和国招标投标法`
   - type: `policy_doc` | span: `single`

717. [definition][synonym] 什么是招标投标？它包含哪些基本环节？
   - expected: `policy_197`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0065`
   - law: `中华人民共和国招标投标法`
   - type: `policy_doc` | span: `single`

718. [comparison][scenario] 公开招标和邀请招标对企业来说有什么不同？
   - expected: `policy_197`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0054`
   - law: `中华人民共和国招标投标法`
   - type: `policy_doc` | span: `single`

719. [responsibility][synonym] 投标人对于评标结果有异议，应该向哪个部门投诉？
   - expected: `policy_197`
   - top1: `parent_铁路工程建设项目招标投标管理办法_38_2114_1384`
   - law: `中华人民共和国招标投标法`
   - type: `policy_doc` | span: `single`

720. [announcement_interpretation][scenario] 这个政府采购公告属于什么类型的采购方式？
   - expected: `policy_207`
   - top1: `parent_中华人民共和国政府采购法_26_2983_6166`
   - law: `财政部国库司与英国能源安全与净零部...`
   - type: `policy_doc` | span: `single`

721. [case_reasoning][cross_reference] 如果土地承包合同出现纠纷，应该找哪个部门投诉？
   - expected: `policy_24`
   - top1: `parent_中华人民共和国招标投标法实施条例_62_137_5462`
   - law: `农村土地承包合同管理办法`
   - type: `policy_doc` | span: `single`

722. [comparison][synonym] 公开招标和邀请招标在政府采购中有何不同？
   - expected: `policy_207`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0054`
   - law: `财政部国库司与英国能源安全与净零部...`
   - type: `policy_doc` | span: `single`

723. [procedure][scenario] 中标后开展绿色低碳试点项目，还需履行哪些后续义务？
   - expected: `policy_158`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_21_3716_9599`
   - law: `政府采购支持公路绿色低碳发展试点申报工作政策问答`
   - type: `policy_doc` | span: `single`

724. [condition_check][scenario] 我们企业在做监理电子招标投标时，需要满足什么前提条件？
   - expected: `policy_111`
   - top1: `parent_水利工程建设项目监理招标投标管理办法_11_2305_3028`
   - law: `【建设工程】监理电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

725. [procedure][scenario] 中标后的监理合同签订流程是怎样的？
   - expected: `policy_111`
   - top1: `parent_民政部工程建设项目招标投标管理办法_10_2909_7305`
   - law: `【建设工程】监理电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

726. [comparison][scenario] 监理电子招标投标和传统招标相比，对企业投标人有哪些便利之处？
   - expected: `policy_111`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0059`
   - law: `【建设工程】监理电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

727. [definition][scenario] 监理电子招标投标中，评标标准主要包含哪些内容？
   - expected: `policy_111`
   - top1: `parent_通信工程建设项目招标投标管理办法_17_2471_1159`
   - law: `【建设工程】监理电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

728. [comparison][cross_reference] 勘察电子招标投标和监理电子招标投标在流程上有什么不同？
   - expected: `policy_100`
   - top1: `parent_农业基本建设项目招标投标管理规定_56_2878_255`
   - law: `【建设工程】勘察电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

729. [scenario_judgment][synonym] 监理单位在招标过程中出现违规行为，责任由谁承担？
   - expected: `policy_111`
   - top1: `parent_中华人民共和国招标投标法_63_66_2102`
   - law: `【建设工程】监理电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

730. [procedure][scenario] 中标后签合同前，采购方还需要走哪些流程？
   - expected: `policy_92`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_5_3700_4815`
   - law: `【技术交易】上技所企业技术采购细则`
   - type: `policy_doc` | span: `single`

731. [condition_check][scenario] 什么情况下政府采购可以直接选定投标方而不采用招标？
   - expected: `policy_92`
   - top1: `parent_中华人民共和国政府采购法实施条例_32_27_3943`
   - law: `【技术交易】上技所企业技术采购细则`
   - type: `policy_doc` | span: `single`

732. [comparison][synonym] 公开招标和邀请招标对企业投标人有什么区别？
   - expected: `policy_92`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0054`
   - law: `【技术交易】上技所企业技术采购细则`
   - type: `policy_doc` | span: `single`

733. [responsibility][cross_reference] 投标人对评标结果有异议该找哪个部门投诉？
   - expected: `policy_92`
   - top1: `parent_铁路工程建设项目招标投标管理办法_38_2114_1384`
   - law: `【技术交易】上技所企业技术采购细则`
   - type: `policy_doc` | span: `single`

734. [procedure][scenario] 政府采购中标后签合同前还需走哪些流程？
   - expected: `policy_153`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_10_3705_3409`
   - law: `国家发展改革委关于印发《全国统一大市场建设指...`
   - type: `policy_doc` | span: `single`

735. [condition_check][scenario] 什么条件下政府采购可以使用竞争性磋商而非公开招标？
   - expected: `policy_153`
   - top1: `parent_政府采购非招标采购方式管理办法_27_4197_6120`
   - law: `国家发展改革委关于印发《全国统一大市场建设指...`
   - type: `policy_doc` | span: `single`

736. [responsibility][cross_reference] 全国中，哪个部门负责处理评标异议？
   - expected: `policy_153`
   - top1: `parent_标活动行政监督的职责分工意见的通知》等有_15_2012_2344`
   - law: `国家发展改革委关于印发《全国统一大市场建设指...`
   - type: `policy_doc` | span: `single`

737. [scenario_judgment][synonym] 政府采购操作系统时，需要注意哪些合规要求？
   - expected: `policy_171`
   - top1: `parent_政务信息系统政府采购管理暂行办法_8_3349_8414`
   - law: `财政部 工业和信息化部关于印发《操作系统政府采...`
   - type: `policy_doc` | span: `single`

738. [condition_check][scenario] 什么情况下政府采购可以选择特定供应商而不用招标？
   - expected: `policy_171`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0124`
   - law: `财政部 工业和信息化部关于印发《操作系统政府采...`
   - type: `policy_doc` | span: `single`

739. [procedure][scenario] 中标后签合同前，政府采购方走哪些流程？
   - expected: `policy_171`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_10_3705_3409`
   - law: `财政部 工业和信息化部关于印发《操作系统政府采...`
   - type: `policy_doc` | span: `single`

740. [responsibility][cross_reference] 政府采购中，供应商对评标结果有异议找哪个部门投诉？
   - expected: `policy_171`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0690`
   - law: `财政部 工业和信息化部关于印发《操作系统政府采...`
   - type: `policy_doc` | span: `single`

741. [comparison][synonym] 公开招标和邀请招标在政府采购中有什么不同？
   - expected: `policy_171`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0054`
   - law: `财政部 工业和信息化部关于印发《操作系统政府采...`
   - type: `policy_doc` | span: `single`

742. [condition_check][scenario] 什么情况下政府采购可以直接选定投标方而不采用招标？
   - expected: `policy_92`
   - top1: `parent_中华人民共和国政府采购法实施条例_32_27_3943`
   - law: `【技术交易】上技所企业技术采购细则`
   - type: `policy_doc` | span: `single`

743. [procedure][scenario] 中标后签合同前，采购方还需要走哪些流程？
   - expected: `policy_92`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_5_3700_4815`
   - law: `【技术交易】上技所企业技术采购细则`
   - type: `policy_doc` | span: `single`

744. [responsibility][cross_reference] 投标人对评标结果有异议该找哪个部门投诉？
   - expected: `policy_92`
   - top1: `parent_铁路工程建设项目招标投标管理办法_38_2114_1384`
   - law: `【技术交易】上技所企业技术采购细则`
   - type: `policy_doc` | span: `single`

745. [comparison][synonym] 公开招标和邀请招标对企业投标人有什么区别？
   - expected: `policy_92`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0054`
   - law: `【技术交易】上技所企业技术采购细则`
   - type: `policy_doc` | span: `single`

746. [condition_check][scenario] 什么条件下政府采购可以使用竞争性磋商而非公开招标？
   - expected: `policy_153`
   - top1: `parent_政府采购非招标采购方式管理办法_27_4197_6120`
   - law: `国家发展改革委关于印发《全国统一大市场建设指...`
   - type: `policy_doc` | span: `single`

747. [procedure][scenario] 政府采购中标后签合同前还需走哪些流程？
   - expected: `policy_153`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_10_3705_3409`
   - law: `国家发展改革委关于印发《全国统一大市场建设指...`
   - type: `policy_doc` | span: `single`

748. [responsibility][cross_reference] 政府采购中，哪个部门负责处理评标异议？
   - expected: `policy_153`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0690`
   - law: `国家发展改革委关于印发《全国统一大市场建设指...`
   - type: `policy_doc` | span: `single`

749. [comparison][synonym] 公开招标和邀请招标在政府采购中有什么不同？
   - expected: `policy_153`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0054`
   - law: `国家发展改革委关于印发《全国统一大市场建设指...`
   - type: `policy_doc` | span: `single`

750. [scenario_judgment][synonym] 政府采购操作系统时，需要注意哪些合规要求？
   - expected: `policy_171`
   - top1: `parent_政务信息系统政府采购管理暂行办法_8_3349_8414`
   - law: `财政部 工业和信息化部关于印发《操作系统政府采...`
   - type: `policy_doc` | span: `single`

751. [condition_check][scenario] 什么情况下政府采购可以选择特定供应商而不用招标？
   - expected: `policy_171`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0124`
   - law: `财政部 工业和信息化部关于印发《操作系统政府采...`
   - type: `policy_doc` | span: `single`

752. [responsibility][cross_reference] 政府采购中，供应商对评标结果有异议找哪个部门投诉？
   - expected: `policy_171`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0690`
   - law: `财政部 工业和信息化部关于印发《操作系统政府采...`
   - type: `policy_doc` | span: `single`

753. [procedure][scenario] 中标后签合同前，政府采购还需要走哪些流程？
   - expected: `policy_171`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_10_3705_3409`
   - law: `财政部 工业和信息化部关于印发《操作系统政府采...`
   - type: `policy_doc` | span: `single`

754. [comparison][synonym] 公开招标和邀请招标在政府采购中有什么不同？
   - expected: `policy_171`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0054`
   - law: `财政部 工业和信息化部关于印发《操作系统政府采...`
   - type: `policy_doc` | span: `single`

755. [scenario_judgment][synonym] 生产小麦产品需要满足哪些质量标准？
   - expected: `policy_194`
   - top1: `parent_《中华人民共和国政府采购法实施条例》等有_44_4036_7898`
   - law: `中华人民共和国产品质量法`
   - type: `policy_doc` | span: `single`

756. [condition_check][scenario] 什么情况下生产者不需要承担产品质量责任？
   - expected: `policy_194`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0663`
   - law: `中华人民共和国产品质量法`
   - type: `policy_doc` | span: `single`

757. [definition][direct] 产品质量监督的具体职责是什么？
   - expected: `policy_194`
   - top1: `parent_标活动行政监督的职责分工意见的通知》等有_22_2019_3214`
   - law: `中华人民共和国产品质量法`
   - type: `policy_doc` | span: `single`

758. [responsibility][synonym] 产品质量出现问题后，消费者应该找哪个部门投诉？
   - expected: `policy_194`
   - top1: `parent_中华人民共和国政府采购法实施条例_58_63_5163`
   - law: `中华人民共和国产品质量法`
   - type: `policy_doc` | span: `single`

759. [scenario_judgment][synonym] 生产不符合规定的产品会面临什么处罚？
   - expected: `policy_194`
   - top1: `parent_中华人民共和国价格法_42_211_9549`
   - law: `中华人民共和国产品质量法`
   - type: `policy_doc` | span: `single`

760. [definition][direct] 产品质量法对企业生产的要求主要有哪些？
   - expected: `policy_194`
   - top1: `parent_药品集中采购监督管理办法_40_2630_4258`
   - law: `中华人民共和国产品质量法`
   - type: `policy_doc` | span: `single`

761. [procedure][scenario] 中央企业采购项目中标后签合同之前，还需要走哪些流程？
   - expected: `policy_21`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_10_3705_3409`
   - law: `关于印发《关于规范中央企业采购管理工作的指导意见》的通知`
   - type: `policy_doc` | span: `single`

762. [scenario_judgment][scenario] 天津市公共资源交易平台的服务管理细则里，平台和参与方有什么职责？
   - expected: `policy_226`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_6_4075_2228`
   - law: `天津市公共资源交易平台服务管理细则（试行）`
   - type: `policy_doc` | span: `single`

763. [condition_check][synonym] 什么情况下政府采购项目可以不经过公开招标而直接指定供应商？需要满足哪些前提条件？
   - expected: `policy_27`
   - top1: `parent_中华人民共和国政府采购法实施条例_32_27_3943`
   - law: `财政部 工业和信息化部关于印发《政府采购促进中小企业发展管理办法》的通知`
   - type: `policy_doc` | span: `single`

764. [scenario_judgment][scenario] 如果在政府采购项目中违反了促进中小企业发展的政策，会有怎样的处罚措施？
   - expected: `policy_27`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0246`
   - law: `财政部 工业和信息化部关于印发《政府采购促进中小企业发展管理办法》的通知`
   - type: `policy_doc` | span: `single`

765. [scenario_judgment][scenario] 我们公司的竞争对手搞虚假宣传，夸大产品效果，这种行为属于不正当竞争吗？应该如何处理？
   - expected: `policy_192`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0681`
   - law: `中华人民共和国反不正当竞争法`
   - type: `policy_doc` | span: `single`

766. [definition][synonym] 《中华人民共和国反不正当竞争法》中，什么是垄断行为？我们公司需要注意哪些方面来避免违规？
   - expected: `policy_192`
   - top1: `opinion_1696`
   - law: `中华人民共和国反不正当竞争法`
   - type: `policy_doc` | span: `single`

767. [procedure][scenario] 发现竞争对手存在虚假宣传的不正当竞争行为，应该向哪个部门举报？需要准备哪些证据？
   - expected: `policy_192`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0681`
   - law: `中华人民共和国反不正当竞争法`
   - type: `policy_doc` | span: `single`

768. [scenario_judgment][scenario] 如果我们的公司被认定为实施垄断行为，会有怎样的法律后果？
   - expected: `policy_192`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0749`
   - law: `中华人民共和国反不正当竞争法`
   - type: `policy_doc` | span: `single`

769. [condition_check][scenario] 什么情况下，我们的电子合同需要采用电子签名？有没有必须的情况？
   - expected: `policy_193`
   - top1: `parent_电子招标投标办法_40_733_4486`
   - law: `中华人民共和国电子签名法`
   - type: `policy_doc` | span: `single`

770. [procedure][scenario] 使用电子签名签订合同，我们需要遵循哪些步骤？从开始到完成的过程是怎样的？
   - expected: `policy_193`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0075`
   - law: `中华人民共和国电子签名法`
   - type: `policy_doc` | span: `single`

771. [definition][synonym] 串通投标属于哪种投标行为？会导致什么结果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0740`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0391`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

772. [condition_check][scenario] 依法必须招标的项目一般采用哪种招标方式？特殊情况可改用什么方式？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0055`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0387`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

773. [scenario_judgment][synonym] 我们公司在招标投标过程中遇到违法行为，应该向哪个部门投诉？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0689`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0685`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

774. [scenario_judgment][scenario] 如果我们的招标项目存在串通投标的情况，应该通过什么渠道来投诉？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0689`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0402`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

775. [scenario_judgment][synonym] 投标人在招标投标过程中发现招标方泄露标底，该怎么投诉？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0689`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0685`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

776. [responsibility][synonym] 投标人遇到招标投标违法行为，该向哪些部门投诉？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0689`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0685`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

777. [scenario_judgment][synonym] 我们公司在招标投标中遇到串通投标行为，应该找哪个部门投诉？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0689`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0398`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

778. [scenario_judgment][scenario] 中标人未履行合同义务会面临什么后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0689`
   - top1: `parent_中华人民共和国招标投标法_60_63_6696`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

779. [scenario_judgment][synonym] 我们公司在招标投标中遇到串通投标行为，应该找哪个部门投诉？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0689`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0398`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

780. [scenario_judgment][scenario] 中标人没按时完成招标项目会有什么后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0689`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0669`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

781. [scenario_judgment][synonym] 我们公司在招标投标中遇到串通投标行为，应该找哪个部门投诉？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0689`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0398`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

782. [scenario_judgment][scenario] 中标人没按时完成招标项目会有什么后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0689`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0669`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

783. [scenario_judgment][scenario] 我们公司要做货物招标，应该遵循哪些相关法律法规？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0751`
   - top1: `parent_工程建设项目货物招标投标办法_4_643_4091`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

784. [responsibility][synonym] 负责确定招标适用法律法规的企业部门是什么？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0751`
   - top1: `parent_中华人民共和国招标投标法实施条例_11_84_9484`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

785. [condition_check][synonym] 当我们的招标项目属于货物类且需要政府采购时，应该适用哪几项法律法规？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0751`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0100`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

786. [procedure][scenario] 如果我们公司要做招标项目，需要先经历哪些步骤？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0015`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0065`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

787. [scenario_judgment][synonym] 如果我们公司投标时用了租借来的资质证书，会有什么后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0555`
   - top1: `parent_中华人民共和国招标投标法实施条例_69_148_7130`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

788. [case_reasoning][synonym] 有个项目发现投标人使用了租借的资质证书，这种情况合法吗？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0555`
   - top1: `parent_中华人民共和国招标投标法实施条例_42_115_6858`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

789. [scenario_judgment][synonym] 如果投标人之间协商报价等实质性内容，会有什么法律后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0745`
   - top1: `parent_工程建设项目施工招标投标办法_76_80_8702`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

790. [announcement_interpretation][synonym] 评标委员会成员泄露招标投标秘密导致中标无效的情况，该如何认定？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0745`
   - top1: `parent_评标委员会应组织全体评标委员学习有关规定_65_1966_8910`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

791. [procedure][scenario] 中标候选人经营状况变化时，招标人需在何时进行履约能力审查？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0583`
   - top1: `parent_标法》《中华人民共和国招标投标法实施条例_60_1869_6337`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

792. [condition_check][scenario] 中标候选人财务状况变化时，招标人如何判断是否影响履约？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0583`
   - top1: `parent_中华人民共和国招标投标法实施条例_56_130_5484`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

793. [responsibility][synonym] 招标文件编制时，主要负责的部门通常是哪个？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0252`
   - top1: `parent_中华人民共和国政府采购法实施条例_32_36_639`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

794. [condition_check][synonym] 什么情况下可以不用标准招标文件，而是自己定制招标文件呢
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0252`
   - top1: `parent_投资项目招标投标管理办法_9_2546_1750`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

795. [definition][synonym] 中标通知书无效的情况有哪些？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0592`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0746`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

796. [scenario_judgment][scenario] 招标招标过程中遇到质疑，应该如何处理？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0709`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0683`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

797. [procedure][synonym] 招标投诉处理的流程是怎样的？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0709`
   - top1: `parent_机电产品国际招标评标专家及专家库管理办法_84_1369_8556`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

798. [responsibility][synonym] 投诉处理的责任主体是谁？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0709`
   - top1: `parent_中华人民共和国政府采购法_81_3040_2830`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

799. [responsibility][cross_reference] 如果我们公司的投标被评标专家厚此薄彼导致中标结果不公，该找哪个部门投诉？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0405`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0468`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

800. [definition][synonym] 评标委员会成员需要遵守哪些基本职业规范？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0468`
   - top1: `parent_评标委员会和评标方法暂行规定_13_404_2516`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

801. [scenario_judgment][synonym] 我们公司投标时用了别人资质中标了，会有什么后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0405`
   - top1: `parent_工程建设项目勘察设计招标投标办法_52_631_6700`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

802. [definition][synonym] 评标委员会成员应该如何履行评审职责？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0468`
   - top1: `parent_评标委员会和评标方法暂行规定_13_404_2516`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

803. [responsibility][scenario] 如果中标合同变更出现争议，我们应该找哪个部门投诉？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0665`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0449`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

804. [condition_check][scenario] 什么情况下政府采购必须可以用电子招标代替传统招标？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0074`
   - top1: `parent_中华人民共和国政府采购法实施条例_32_27_3943`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

805. [procedure][scenario] 电子招标投标的具体流程有哪些关键步骤？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0074`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0087`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

806. [procedure][synonym] 评标过程中发现招标文件错误应该怎么处理？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0009`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0512`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

807. [definition][synonym] 什么是‘评标中的澄清’？需要满足什么条件？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0009`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0524`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

808. [scenario_judgment][cross_reference] 如果评标时否决所有投标人，该怎么做？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0009`
   - top1: `parent_中华人民共和国招标投标法_42_45_6937`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

809. [condition_check][scenario] 什么情况下政府采购必须可以用电子招标代替传统招标？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0074`
   - top1: `parent_中华人民共和国政府采购法实施条例_32_27_3943`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

810. [responsibility][scenario] 如果中标合同变更出现争议，我们应该找哪个部门投诉？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0665`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0449`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

811. [procedure][scenario] 电子招标投标的具体流程有哪些关键步骤？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0074`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0087`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

812. [procedure][synonym] 评标过程中发现招标文件错误应该怎么处理？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0009`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0512`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

813. [definition][synonym] 什么是‘评标中的澄清’？需要满足什么条件？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0009`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0524`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

814. [scenario_judgment][scenario] 我们公司在招标中标后，如果不及时签订书面合同，会有什么法律后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0636`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0639`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

815. [scenario_judgment][cross_reference] 如果评标时否决所有投标人，该怎么做？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0009`
   - top1: `parent_中华人民共和国招标投标法_42_45_6937`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

816. [scenario_judgment][scenario] 投标人如果在投标时发表对竞争对手的不实质疑，可能会面临怎样的法律后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0682`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0681`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

817. [scenario_judgment][scenario] 在招标采购中，如何节能等因素提出绿色采购要求，对企业投标人有哪些影响？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0291`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0129`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

818. [procedure][scenario] 采购需求中提出相关标准后，投标人如何确定自己的产品是否符合要求？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0291`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0241`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

819. [procedure][synonym] 中标之后签合同，需要提前做哪些手续呢？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0626`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0615`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

820. [comparison][cross_reference] 公开招标和邀请招标下，投标人的限制条件一样吗？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0541`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0055`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

821. [responsibility][synonym] 如果我们的投标人是经销商，投标资格有没有特殊要求？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0541`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0259`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

822. [scenario_judgment][cross_reference] 我们在招标过程中遇到疑问，应该参考哪些法律依据呀？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0137`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0090`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

823. [condition_check][scenario] 招标文件的制定需要满足哪些法律条款要求？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0137`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0226`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

824. [comparison][cross_reference] 不同版本的招标投标法规有哪些主要变化？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0137`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0751`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

825. [responsibility][cross_reference] 哪个部门或角色负责检查当地招标政策是否存在不公平规范？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0257`
   - top1: `parent_标活动行政监督的职责分工意见的通知》等有_12_2009_5960`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

826. [scenario_judgment][synonym] 招标人代表在评标中有哪些职责？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0452`
   - top1: `parent_公路工程建设项目评标工作细则_16_1509_5413`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

827. [procedure][synonym] 实行电子开标时，投标人需要提前做好哪些准备才能按时参加？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0437`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0426`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

828. [scenario_judgment][scenario] 如果招标项目合同存在转包行为，我们公司该如何处理？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0653`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0651`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

829. [definition][synonym] 招标代理机构在招标过程中有哪些禁止性行为？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0166`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0180`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

830. [scenario_judgment][scenario] 如果招标代理机构违反了招标代理合同的约定，我们公司该怎么处理？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0166`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0169`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

831. [definition][synonym] 招标公告的作用是什么？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0181`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0033`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

832. [definition][synonym] 招标代理机构不能同时做哪些事情？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0166`
   - top1: `parent_工程建设项目施工招标投标办法_22_24_6517`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

833. [comparison][scenario] 招标公告属于哪种招标方式的前置步骤？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0181`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0193`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

834. [definition][synonym] 招标代理机构在招标过程中有哪些禁止性的行为？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0166`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0180`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

835. [definition][synonym] 招标公告的主要作用是什么？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0181`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0021`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

836. [scenario_judgment][scenario] 如果我们公司的招标代理合同没做好，会有什么后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0166`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0169`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

837. [procedure][synonym] 编制招标公告时需要注意哪些要点？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0181`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0319`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

838. [case_reasoning][scenario] 公开招标项目为什么要发布招标公告？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0181`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0184`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

839. [definition][synonym] 招标公告的主要作用是什么？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0181`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0021`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

840. [definition][synonym] 招标代理机构在招标过程中有哪些禁止性的行为？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0166`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0180`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

841. [scenario_judgment][scenario] 如果我们公司的招标代理合同没做好，会有什么后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0166`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0169`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

842. [case_reasoning][scenario] 公开招标项目为什么要发布招标公告？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0181`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0184`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

843. [procedure][synonym] 编制招标公告时需要注意哪些要点？
   - expected: `pdf_招标投标法律解读与风险防范实务_para_0181`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0319`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_paragraph` | span: `single`

844. [scenario_judgment][scenario] 我们公司中标后退出工程，后来其他人中标继续施工，这种情况合法吗？
   - expected: `pdf_建设工程施工合同纠纷案_34_5720`
   - top1: `pdf_建设工程施工合同纠纷案_3_1293`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

845. [condition_check][synonym] 我们公司在投标后，发现工程量估算错误，想退出后换队伍施工，这种情况需要满足什么条件？
   - expected: `pdf_建设工程施工合同纠纷案_2_7334`
   - top1: `parent_公路工程设计施工总承包管理办法_24_1667_702`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

846. [case_reasoning][cross_reference] 这个案件中，施工单位先中标后退出，后来借用资质的单位中标，这种多主体施工的情况，法律上有什么规定？
   - expected: `pdf_建设工程施工合同纠纷案_34_5720`
   - top1: `pdf_建设工程施工合同纠纷案_15_6931`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

847. [scenario_judgment][scenario] 投标时未签订正式合同就施工，后来又更换施工单位，这种情况会有什么法律后果？
   - expected: `pdf_建设工程施工合同纠纷案_2_7334`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0641`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

848. [scenario_judgment][synonym] 如果我们公司在招投标过程中发现竞争对手泄露了标底信息，应该如何处理以维护自身权益？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_11_7204`
   - top1: `parent_中华人民共和国招标投标法_52_55_1901`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

849. [responsibility][scenario] 当施工单位因资质问题无法施工，借用资质中标后出现工程款争议，该如何处理？
   - expected: `pdf_建设工程施工合同纠纷案_23_3029`
   - top1: `pdf_建设工程施工合同纠纷案_0_8849`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

850. [responsibility][scenario] 如果发现招投标过程中存在泄露标底的情况，应该找哪个部门进行投诉？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_11_7204`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0689`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

851. [scenario_judgment][synonym] 招投标过程中泄露标底这类行为通常会有什么法律后果？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_11_7204`
   - top1: `parent_中华人民共和国招标投标法_52_55_1901`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

852. [comparison][synonym] 行贿罪和串通投标罪在法律适用上有何区别？
   - expected: `pdf_非国家工作人员行贿案_3_4432`
   - top1: `pdf_串通投标、受贿案_3_4662`
   - law: `非国家工作人员行贿案`
   - type: `pdf_case_sliding` | span: `single`

853. [scenario_judgment][scenario] 招投标过程中发现竞争对手泄露标底，我们公司中标后还能正常签合同吗？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_10_9006`
   - top1: `parent_中华人民共和国招标投标法_52_55_1901`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

854. [procedure][synonym] 招投标时泄露竞争对手泄露标底，我们应该先做什么？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_10_9006`
   - top1: `parent_工程建设项目施工招标投标办法_71_73_9080`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

855. [definition][synonym] 这个案例里‘泄露标底’的具体表现有哪些？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_10_9006`
   - top1: `parent_中华人民共和国招标投标法_52_55_1901`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

856. [scenario_judgment][synonym] 如果我们在招标时发现中标人没有相应资质，只是挂靠在资质单位名下，这种情况我们能要求中标人重新招标吗？
   - expected: `pdf_建工集团公司建设工程施工合同纠纷案_9_3299`
   - top1: `parent_中华人民共和国招标投标法实施条例_55_129_1017`
   - law: `建工集团公司建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

857. [definition][scenario] 如果我们的供应商没有资质，却挂靠在其他有资质的企业下合作，这种情况我们需要承担什么法律责任？
   - expected: `pdf_建工集团公司建设工程施工合同纠纷案_9_3299`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0404`
   - law: `建工集团公司建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

858. [scenario_judgment][synonym] 如果我们在投标后发现中标人没有资质，只是挂靠在有资质的企业下，这种情况我们可以要求重新招标吗？
   - expected: `pdf_建工集团公司建设工程施工合同纠纷案_9_3299`
   - top1: `parent_中华人民共和国招标投标法实施条例_55_129_1017`
   - law: `建工集团公司建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

859. [definition][scenario] 如果供应商没有资质却挂靠在我们公司旗下合作，这种情况我们公司需要承担什么责任？
   - expected: `pdf_建工集团公司建设工程施工合同纠纷案_9_3299`
   - top1: `pdf_建工集团公司建设工程施工合同纠纷案_10_1965`
   - law: `建工集团公司建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

860. [scenario_judgment][synonym] 如果我们在投标后发现中标人没有资质，只是挂靠在有资质的企业下，这种情况我们可以要求重新招标吗？
   - expected: `pdf_建工集团公司建设工程施工合同纠纷案_9_3299`
   - top1: `parent_中华人民共和国招标投标法实施条例_55_129_1017`
   - law: `建工集团公司建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

861. [definition][scenario] 如果供应商没有资质却挂靠在我们公司旗下合作，这种情况我们公司需要承担什么责任？
   - expected: `pdf_建工集团公司建设工程施工合同纠纷案_9_3299`
   - top1: `pdf_建工集团公司建设工程施工合同纠纷案_10_1965`
   - law: `建工集团公司建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

862. [scenario_judgment][synonym] 如果我们在投标后发现中标人没有资质，只是挂靠在有资质的企业下，这种情况我们可以要求重新招标吗？
   - expected: `pdf_建工集团公司建设工程施工合同纠纷案_9_3299`
   - top1: `parent_中华人民共和国招标投标法实施条例_55_129_1017`
   - law: `建工集团公司建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

863. [scenario_judgment][scenario] 我们公司在投标时用了别人的名义中标，后来实际自己施工，会有什么法律后果？
   - expected: `pdf_建设工程施工合同纠纷案_15_6931`
   - top1: `parent_工程建设项目施工招标投标办法_75_79_4642`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

864. [responsibility][scenario] 遇到投标用他人名义中标的情况，应该找哪个部门投诉？
   - expected: `pdf_建设工程施工合同纠纷案_15_6931`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0690`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

865. [case_reasoning][scenario] 如果我们做项目时没和业主签正式合同，只和中间公司签了，这种情况合法吗？
   - expected: `pdf_建工集团公司建设工程施工合同纠纷案_8_4327`
   - top1: `pdf_建工集团公司建设工程施工合同纠纷案_10_1965`
   - law: `建工集团公司建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

866. [definition][synonym] 什么叫'投标用他人名义中标'？具体表现有哪些？
   - expected: `pdf_建设工程施工合同纠纷案_15_6931`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0405`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

867. [scenario_judgment][scenario] 我们做项目时没和业主签正式合同，只和中间公司签了，会有什么法律后果？
   - expected: `pdf_建工集团公司建设工程施工合同纠纷案_8_4327`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0626`
   - law: `建工集团公司建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

868. [condition_check][synonym] 什么情况下实际施工人不和业主签合同也能得到工程款？
   - expected: `pdf_建工集团公司建设工程施工合同纠纷案_8_4327`
   - top1: `pdf_建设工程施工合同纠纷案_33_3584`
   - law: `建工集团公司建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

869. [scenario_judgment][synonym] 投标文件没按时送达会有怎样处理？
   - expected: `parent_法定代表人为同一个人的两个及两个以上法_41_675_5728`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0332`
   - law: `法定代表人为同一个人的两个及两个以上法`
   - type: `pdf_law_parent` | span: `single`

870. [scenario_judgment][synonym] 招标代理机构违反本管理规定会有什么处罚？
   - expected: `parent_公路养护工程施工招标投标管理暂行规定_41_1604_4832`
   - top1: `parent_中华人民共和国招标投标法_50_53_5141`
   - law: `公路养护工程施工招标投标管理暂行规定`
   - type: `pdf_law_parent` | span: `single`

871. [condition_check][direct] 这个办法废止了哪些以前的文件？
   - expected: `parent_中央预算单位批量集中采购管理暂行办法_13_4337_3790`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0187`
   - law: `中央预算单位批量集中采购管理暂行办法`
   - type: `pdf_law_parent` | span: `single`

872. [procedure][scenario] 现在执行这个办法后，我们的采购流程有没有变化？
   - expected: `parent_中央预算单位批量集中采购管理暂行办法_13_4337_3790`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_33_3694_8821`
   - law: `中央预算单位批量集中采购管理暂行办法`
   - type: `pdf_law_parent` | span: `single`

873. [condition_check][synonym] 我们公司的采购项目达到公开招标数额标准时，可以不用公开招标吗？
   - expected: `parent_《中华人民共和国政府采购法实施条例》等有_19_4009_2382`
   - top1: `parent_中央预算单位变更政府采购方式审批管理办法_19_4320_5983`
   - law: `《中华人民共和国政府采购法实施条例》等有关法`
   - type: `pdf_law_parent` | span: `single`

874. [scenario_judgment][scenario] 我们公司准备开展电子招标投标项目，需要遵守什么相关规定呀？
   - expected: `parent_电子招标投标办法_2_695_1045`
   - top1: `parent_电子招标投标办法_41_738_8177`
   - law: `电子招标投标办法`
   - type: `pdf_law_parent` | span: `single`

875. [definition][synonym] 我们公司在参与工程建设项目招标时，招标方在资格预审阶段应该公布哪些信息？
   - expected: `parent_工程建设项目施工招标投标办法_13_20_6935`
   - top1: `parent_招标公告和公示信息发布管理办法_5_773_1369`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `single`

876. [scenario_judgment][synonym] 如果在招标过程中开标时间和地点不符合规定，会对我们公司带来什么后果？
   - expected: `parent_投资项目招标投标管理办法_14_2551_8147`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0133`
   - law: `投资项目招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

877. [condition_check][scenario] 什么情况下可以变更招标文件中确定的开标时间和地点？
   - expected: `parent_投资项目招标投标管理办法_14_2551_8147`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0422`
   - law: `投资项目招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

878. [scenario_judgment][synonym] 我们公司要做社会保险相关的项目，需要了解社会保险基金预算是怎么规定的？
   - expected: `parent_金提供方对招标投标的具体条件和程序有不同_83_1984_6314`
   - top1: `parent_中华人民共和国预算法_11_3144_1923`
   - law: `金提供方对招标投标的具体条件和程序有不同规定`
   - type: `pdf_law_parent` | span: `single`

879. [procedure][synonym] 评标专家资格培训后会做什么？
   - expected: `parent_系统工程综合评标专家库管理办法_5_1890_7194`
   - top1: `parent_民航专业工程及货物招标投标评标专家和专家_6_2144_4915`
   - law: `系统工程综合评标专家库管理办法`
   - type: `pdf_law_parent` | span: `single`

880. [scenario_judgment][scenario] 水利工程建设项目的招投标文件备案后有效期限是多少？
   - expected: `parent_水利工程建设项目招标投标审计办法_10_2440_2888`
   - top1: `parent_水利工程建设项目招标投标管理规定_23_2256_472`
   - law: `水利工程建设项目招标投标审计办法`
   - type: `pdf_law_parent` | span: `single`

881. [definition][synonym] 我们公司参与水利工程项目招标投标，有哪些法规依据？
   - expected: `parent_水利工程建设项目招标投标管理规定_1_2231_9274`
   - top1: `parent_水利工程建设项目招标投标管理规定_5_2235_4638`
   - law: `水利工程建设项目招标投标管理规定`
   - type: `pdf_law_parent` | span: `single`

882. [definition][synonym] 水利工程招标投标管理规定的适用范围是什么？
   - expected: `parent_水利工程建设项目招标投标管理规定_1_2231_9274`
   - top1: `parent_水利工程建设项目招标投标管理规定_3_2233_7214`
   - law: `水利工程建设项目招标投标管理规定`
   - type: `pdf_law_parent` | span: `single`

883. [scenario_judgment][synonym] 如果我们公司的招标专家泄露了招标项目的相关信息，会有什么后果？
   - expected: `parent_机电产品国际招标评标专家及专家库管理办法_94_1385_2444`
   - top1: `parent_中华人民共和国招标投标法_52_55_1901`
   - law: `机电产品国际招标评标专家及专家库管理办法`
   - type: `pdf_law_parent` | span: `single`

884. [condition_check][synonym] 什么情况下会被认定为违反招标投标法及相关规定的违规行为？
   - expected: `parent_机电产品国际招标评标专家及专家库管理办法_94_1385_2444`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0732`
   - law: `机电产品国际招标评标专家及专家库管理办法`
   - type: `pdf_law_parent` | span: `single`

885. [responsibility][synonym] 招标专家违规违规行为后，哪个部门负责执行投诉处理决定？
   - expected: `parent_机电产品国际招标评标专家及专家库管理办法_94_1385_2444`
   - top1: `parent_华人民共和国招标投标法实施条例》及其他有_21_1000_6882`
   - law: `机电产品国际招标评标专家及专家库管理办法`
   - type: `pdf_law_parent` | span: `single`

886. [condition_check][synonym] 政府采购的具体实施办法由哪个部门制定？
   - expected: `parent_《中华人民共和国政府采购法实施条例》等有_20_4393_4975`
   - top1: `parent_《中华人民共和国政府采购法实施条例》等有_42_4034_6840`
   - law: `《中华人民共和国政府采购法实施条例》等有关法`
   - type: `pdf_law_parent` | span: `single`

887. [scenario_judgment][synonym] 投标人未提交投标保证金会带来什么后果？
   - expected: `parent_政府采购货物和服务招标投标管理办法_63_66_3049`
   - top1: `parent_集中采购机构是设区的市级以上人民政府依法_33_3073_8030`
   - law: `政府采购货物和服务招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

888. [scenario_judgment][synonym] 投标文件未签署盖章会导致什么结果？
   - expected: `parent_政府采购货物和服务招标投标管理办法_63_66_3049`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_32_3764_4888`
   - law: `政府采购货物和服务招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

889. [scenario_judgment][synonym] 投标人报价超过预算金额会有什么影响？
   - expected: `parent_政府采购货物和服务招标投标管理办法_63_66_3049`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0565`
   - law: `政府采购货物和服务招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

890. [condition_check][scenario] 中标后签订合同时需要注意哪些条件？
   - expected: `parent_机电产品国际招标评标专家及专家库管理办法_97_1387_6702`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0622`
   - law: `机电产品国际招标评标专家及专家库管理办法`
   - type: `pdf_law_parent` | span: `single`

891. [scenario_judgment][synonym] 投标文件投诉处理中提供虚假证明材料会有什么处罚？
   - expected: `parent_机电产品国际招标评标专家及专家库管理办法_97_1387_6702`
   - top1: `parent_中华人民共和国政府采购法实施条例_73_83_8787`
   - law: `机电产品国际招标评标专家及专家库管理办法`
   - type: `pdf_law_parent` | span: `single`

892. [responsibility][scenario] 当我们发现招标投标过程中存在不合理限制投标人情况时，该找哪个部门反映？
   - expected: `parent_铁路工程建设项目招标投标管理办法_51_2128_3264`
   - top1: `parent_工程建设项目施工招标投标办法_70_72_2124`
   - law: `铁路工程建设项目招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

893. [procedure][scenario] 投诉处理部门在处理投诉时需要做哪些步骤？
   - expected: `parent_铁路工程建设项目招标投标管理办法_51_2128_3264`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0705`
   - law: `铁路工程建设项目招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

894. [scenario_judgment][synonym] 我们公司组建评标专家库需要遵循什么规定？
   - expected: `parent_评标专家和评标专家库管理暂行办法_2_457_6718`
   - top1: `parent_评标专家和评标专家库管理暂行办法_3_458_2667`
   - law: `评标专家和评标专家库管理暂行办法`
   - type: `pdf_law_parent` | span: `single`

895. [scenario_judgment][synonym] 评标专家资格认定需要满足什么条件？
   - expected: `parent_评标专家和评标专家库管理暂行办法_2_457_6718`
   - top1: `parent_民航专业工程及货物招标投标评标专家和专家_7_2145_2837`
   - law: `评标专家和评标专家库管理暂行办法`
   - type: `pdf_law_parent` | span: `single`

896. [condition_check][synonym] 什么情况下政府采购可以直接指定供应商而不招标？
   - expected: `parent_国家对潜在投标人或者投标人的资格条件有规_61_542_6292`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0295`
   - law: `国家对潜在投标人或者投标人的资格条件有规定`
   - type: `pdf_law_parent` | span: `single`

897. [definition][synonym] 中央国家机关政府采购中心货物和服务项目评审处的项目经办人做什么？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_30_3859_1776`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_36_3865_2953`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

898. [definition][synonym] 中央国家机关政府采购中心货物和服务项目评审处的项目经办人做什么？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_30_3859_1776`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_36_3865_2953`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

899. [definition][synonym] 中央国家机关政府采购中心货物和服务项目评审处的项目经办人做什么？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_30_3859_1776`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_36_3865_2953`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

900. [scenario_judgment][synonym] 我们公司需要了解省级财政部门制定的具体实施办法有什么要求，应该去哪里找相关信息？
   - expected: `parent_采购人和采购代理机构收到暂停采购活动通知_44_3497_1336`
   - top1: `parent_《中华人民共和国政府采购法实施条例》等有_20_4393_4975`
   - law: `采购人和采购代理机构收到暂停采购活动通知`
   - type: `pdf_law_parent` | span: `single`

901. [condition_check][scenario] 作为投标人，我们想知道集中采购机构的设立是否需要经过特定的审批流程？
   - expected: `parent_集中采购机构是设区的市级以上人民政府依法_29_3062_3152`
   - top1: `parent_中华人民共和国政府采购法_16_2972_3249`
   - law: `集中采购机构是设区的市级以上人民政府依法`
   - type: `pdf_law_parent` | span: `single`

902. [scenario_judgment][synonym] 我们公司中标后，负责这个项目的集中采购机构应该由哪个级别的政府部门设立？
   - expected: `parent_集中采购机构是设区的市级以上人民政府依法_29_3062_3152`
   - top1: `parent_集中采购机构是设区的市级以上人民政府依法_47_3088_6287`
   - law: `集中采购机构是设区的市级以上人民政府依法`
   - type: `pdf_law_parent` | span: `single`

903. [responsibility][scenario] 我们公司在工程评标时有人泄露了评标信息，这种情况应该找哪个部门处理？
   - expected: `parent_公路工程建设项目评标工作细则_40_1538_8938`
   - top1: `parent_评标委员会应组织全体评标委员学习有关规定_65_1966_8910`
   - law: `公路工程建设项目评标工作细则`
   - type: `pdf_law_parent` | span: `single`

904. [scenario_judgment][cross_reference] 如果抽取的评标专家有泄密行为，会有什么后果？
   - expected: `parent_及教学资源招标采购管理办法_13_2893_5954`
   - top1: `parent_进一步规范机电产品国际招标投标活动有关规_21_1244_1527`
   - law: `及教学资源招标采购管理办法`
   - type: `pdf_law_parent` | span: `single`

905. [condition_check][synonym] 获取招标文件需要满足什么前提条件吗？
   - expected: `parent_政府采购货物和服务招标投标管理办法_13_3371_6675`
   - top1: `parent_《中华人民共和国政府采购法实施条例》等有_22_4395_5069`
   - law: `政府采购货物和服务招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

906. [condition_check][direct] 投标时需要提交投标保证金吗？
   - expected: `parent_水利工程建设项目招标投标管理规定_30_2263_594`
   - top1: `parent_中华人民共和国政府采购法实施条例_33_37_6896`
   - law: `水利工程建设项目招标投标管理规定`
   - type: `pdf_law_parent` | span: `single`

907. [condition_check][synonym] 政府项目预算调整方案需要由哪个机构审议批准？
   - expected: `parent_中华人民共和国预算法_20_3153_1373`
   - top1: `parent_中华人民共和国预算法_69_3204_999`
   - law: `中华人民共和国预算法`
   - type: `pdf_law_parent` | span: `single`

908. [responsibility][synonym] 评标委员会编写评标报告的职责是什么？
   - expected: `parent_政府采购货物和服务招标投标管理办法_58_3419_8435`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0567`
   - law: `政府采购货物和服务招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

909. [comparison][synonym] 公开招标和邀请招标的招标公告有什么不同吗？
   - expected: `parent_国家技术创新项目招标投标管理办法_17_2790_6767`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0054`
   - law: `国家技术创新项目招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

910. [scenario_judgment][scenario] 如果我们企业在开标时没有让投标人检查投标文件密封情况，会有什么后果？
   - expected: `parent_中华人民共和国招标投标法_36_39_2806`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0431`
   - law: `中华人民共和国招标投标法`
   - type: `pdf_law_parent` | span: `single`

911. [scenario_judgment][scenario] 若我们在政府采购评审中出现违规情况，相关责任人的处理方式是怎样的？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_29_3858_390`
   - top1: `parent_政府采购非招标采购方式管理办法_58_4235_5825`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

912. [scenario_judgment][direct] 我们公司在参与政府工程项目的投标过程中，发现投标文件没按要求密封，这种情况会被拒收吗？
   - expected: `parent_集中采购机构是设区的市级以上人民政府依法_26_3066_5094`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0432`
   - law: `集中采购机构是设区的市级以上人民政府依法`
   - type: `pdf_law_parent` | span: `single`

913. [scenario_judgment][synonym] 我们公司在政府采购项目中，遇到需要采购艺术品的情况，这种情形属于什么类别，签合同前有什么特殊要求吗？
   - expected: `parent_集中采购机构是设区的市级以上人民政府依法_26_3066_5094`
   - top1: `parent_中华人民共和国政府采购法实施条例_26_30_1293`
   - law: `集中采购机构是设区的市级以上人民政府依法`
   - type: `pdf_law_parent` | span: `single`

914. [scenario_judgment][synonym] 我们公司在投标时，发现其他投标人存在串通投标行为，这种情况评标委员会应如何处理？
   - expected: `parent_国家对潜在投标人或者投标人的资格条件有规_50_531_2753`
   - top1: `parent_政府采购货物和服务招标投标管理办法_36_3395_2907`
   - law: `国家对潜在投标人或者投标人的资格条件有规定`
   - type: `pdf_law_parent` | span: `single`

915. [scenario_judgment][direct] 我们公司在投标时，若投标文件没经过单位负责人签字，评标委员会会如何处理？
   - expected: `parent_国家对潜在投标人或者投标人的资格条件有规_50_531_2753`
   - top1: `parent_工程建设项目勘察设计招标投标办法_36_612_6418`
   - law: `国家对潜在投标人或者投标人的资格条件有规定`
   - type: `pdf_law_parent` | span: `single`

916. [scenario_judgment][synonym] 如果我们公司的投标文件报价低于成本，评标委员会会如何处理？
   - expected: `parent_工程建设项目施工招标投标办法_6_6_3938`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0522`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `single`

917. [scenario_judgment][scenario] 如果我们公司中标后未及时公告成交结果，会面临什么处罚或后果？
   - expected: `parent_政府采购非招标采购方式管理办法_18_4187_8727`
   - top1: `parent_集中采购机构是设区的市级以上人民政府依法_21_3118_7297`
   - law: `政府采购非招标采购方式管理办法`
   - type: `pdf_law_parent` | span: `single`

918. [scenario_judgment][scenario] 如果在公路养护工程招标开标时没有按规定组织，会有什么后果？
   - expected: `parent_公路养护工程施工招标投标管理暂行规定_29_1592_6662`
   - top1: `parent_公路养护工程施工招标投标管理暂行规定_31_1594_9595`
   - law: `公路养护工程施工招标投标管理暂行规定`
   - type: `pdf_law_parent` | span: `single`

919. [scenario_judgment][cross_reference] 如果国采中心的评审委员会推荐了错误的定点供应商，会有什么责任？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_13_3673_8727`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_31_3692_468`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

920. [scenario_judgment][scenario] 如果我们公司中标后未及时公告成交结果，会面临什么处罚或后果？
   - expected: `parent_政府采购非招标采购方式管理办法_18_4187_8727`
   - top1: `parent_集中采购机构是设区的市级以上人民政府依法_21_3118_7297`
   - law: `政府采购非招标采购方式管理办法`
   - type: `pdf_law_parent` | span: `single`

921. [scenario_judgment][scenario] 如果在公路养护工程招标开标时没有按规定组织，会有什么后果？
   - expected: `parent_公路养护工程施工招标投标管理暂行规定_29_1592_6662`
   - top1: `parent_公路养护工程施工招标投标管理暂行规定_31_1594_9595`
   - law: `公路养护工程施工招标投标管理暂行规定`
   - type: `pdf_law_parent` | span: `single`

922. [scenario_judgment][cross_reference] 如果国采中心的评审委员会推荐了错误的定点供应商，会有什么责任？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_13_3673_8727`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_31_3692_468`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

923. [responsibility][synonym] 我们公司作为收支需要向哪个部门提交审计报告？
   - expected: `parent_中华人民共和国审计法_2_219_5435`
   - top1: `parent_中华人民共和国预算法_89_3225_8715`
   - law: `中华人民共和国审计法`
   - type: `pdf_law_parent` | span: `single`

924. [scenario_judgment][scenario] 如果我们的财务收支不符合审计监督要求，会有什么后果？
   - expected: `parent_中华人民共和国审计法_2_219_5435`
   - top1: `parent_中华人民共和国审计法实施条例_45_321_3260`
   - law: `中华人民共和国审计法`
   - type: `pdf_law_parent` | span: `single`

925. [condition_check][cross_reference] 政府采购项目中，哪些情形下不需要通过招标直接指定供应商？
   - expected: `parent_政府采购非招标采购方式管理办法_59_4236_5697`
   - top1: `parent_交通运输部部属单位政府采购管理办法_14_3931_6164`
   - law: `政府采购非招标采购方式管理办法`
   - type: `pdf_law_parent` | span: `single`

926. [condition_check][synonym] 政府采购的情况属于什么类型的财政信息，需要向社会公开吗？
   - expected: `parent_中华人民共和国预算法实施条例_6_3243_3830`
   - top1: `parent_中华人民共和国政府采购法_11_2967_3415`
   - law: `中华人民共和国预算法实施条例`
   - type: `pdf_law_parent` | span: `single`

927. [condition_check][synonym] 什么情况下不用从专家库随机选评审专家？
   - expected: `parent_集中采购机构是设区的市级以上人民政府依法_39_3080_1211`
   - top1: `parent_机电产品国际招标评标专家及专家库管理办法_69_1375_7704`
   - law: `集中采购机构是设区的市级以上人民政府依法`
   - type: `pdf_law_parent` | span: `single`

928. [procedure][synonym] 我们公司在设区市以上集中采购时，评审专家是怎么选的？
   - expected: `parent_集中采购机构是设区的市级以上人民政府依法_39_3080_1211`
   - top1: `parent_政府采购评审专家管理办法_5_3533_9253`
   - law: `集中采购机构是设区的市级以上人民政府依法`
   - type: `pdf_law_parent` | span: `single`

929. [definition][synonym] 我们公司在招标项目里，评审专家来自哪里？
   - expected: `parent_集中采购机构是设区的市级以上人民政府依法_39_3080_1211`
   - top1: `parent_政府采购货物和服务招标投标管理办法_48_50_5741`
   - law: `集中采购机构是设区的市级以上人民政府依法`
   - type: `pdf_law_parent` | span: `single`

930. [procedure][scenario] 我们公司中标后，如果发现之前的招标文件有需要修改的地方，该什么时候通知潜在投标人呢？
   - expected: `parent_政府采购货物和服务招标投标管理办法_27_3386_3771`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0279`
   - law: `政府采购货物和服务招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

931. [scenario_judgment][synonym] 如果我们在做招标项目时，之前发布的招标文件需要修改，应该怎么处理呢？
   - expected: `parent_政府采购货物和服务招标投标管理办法_27_3386_3771`
   - top1: `parent_进一步规范机电产品国际招标投标活动有关规_9_1230_7733`
   - law: `政府采购货物和服务招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

932. [definition][synonym] 招标文件的澄清或修改属于招标流程中的哪个环节？
   - expected: `parent_政府采购货物和服务招标投标管理办法_27_3386_3771`
   - top1: `parent_中华人民共和国招标投标法_23_26_4180`
   - law: `政府采购货物和服务招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

933. [scenario_judgment][cross_reference] 如果招标文件的澄清或修改没及时通知潜在投标人，会有什么后果吗？
   - expected: `parent_政府采购货物和服务招标投标管理办法_27_3386_3771`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0278`
   - law: `政府采购货物和服务招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

934. [scenario_judgment][cross_reference] 招标文件的澄清是否修改是否会影响招标结果？
   - expected: `parent_政府采购货物和服务招标投标管理办法_27_3386_3771`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0278`
   - law: `政府采购货物和服务招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

935. [definition][synonym] 评标委员会成员的回避机制是怎样的？
   - expected: `parent_评标委员会和评标方法暂行规定_12_403_805`
   - top1: `parent_水利工程建设项目监理招标投标管理办法_52_2348_9031`
   - law: `评标委员会和评标方法暂行规定`
   - type: `pdf_law_parent` | span: `single`

936. [scenario_judgment][cross_reference] 评评标委员会成员没有主动回避，会有什么后果？
   - expected: `parent_评标委员会和评标方法暂行规定_12_403_805`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0461`
   - law: `评标委员会和评标方法暂行规定`
   - type: `pdf_law_parent` | span: `single`

937. [procedure][synonym] 我们公司中标后，要先完成什么步骤才能和中标方签订合同呢？
   - expected: `parent_重大装备自主化依托工程设备招标采购活动的_39_2951_8064`
   - top1: `parent_评标委员会和评标方法暂行规定_49_442_1892`
   - law: `重大装备自主化依托工程设备招标采购活动的有关规定`
   - type: `pdf_law_parent` | span: `single`

938. [definition][synonym] 中标通知书对招标人和中标人分别有什么样的法律效力？
   - expected: `parent_重大装备自主化依托工程设备招标采购活动的_39_2951_8064`
   - top1: `parent_工程建设项目施工招标投标办法_60_62_3814`
   - law: `重大装备自主化依托工程设备招标采购活动的有关规定`
   - type: `pdf_law_parent` | span: `single`

939. [procedure][synonym] 我们公司中标后，要先完成什么步骤才能和中标方签订合同呢？
   - expected: `parent_重大装备自主化依托工程设备招标采购活动的_39_2951_8064`
   - top1: `parent_评标委员会和评标方法暂行规定_49_442_1892`
   - law: `重大装备自主化依托工程设备招标采购活动的有关规定`
   - type: `pdf_law_parent` | span: `single`

940. [definition][synonym] 中标通知书对招标人和中标人分别有什么样的法律效力？
   - expected: `parent_重大装备自主化依托工程设备招标采购活动的_39_2951_8064`
   - top1: `parent_工程建设项目施工招标投标办法_60_62_3814`
   - law: `重大装备自主化依托工程设备招标采购活动的有关规定`
   - type: `pdf_law_parent` | span: `single`

941. [comparison][synonym] 这个招投标监管系统项目和我们之前的项目相比，在管理方式上有什么不同？
   - expected: `opinion_1800`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0026`
   - law: `贵州省关于做好政府采购招投标现场监督管理系统项目建...`
   - type: `opinion_news` | span: `single`

942. [condition_check][scenario] 我们单位要参与招投标监管系统项目，需要满足什么条件？
   - expected: `opinion_1800`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0216`
   - law: `贵州省关于做好政府采购招投标现场监督管理系统项目建...`
   - type: `opinion_news` | span: `single`

943. [announcement_interpretation][cross_reference] 这个修缮项目采用竞争性磋商的原因是什么？
   - expected: `opinion_533`
   - top1: `opinion_665`
   - law: `北京师范大学附属中学2026年西校区暑期修缮项目竞争性磋商公告`
   - type: `opinion_news` | span: `single`

944. [scenario_judgment][synonym] 如果我们在投标该黄河水利委员会项目时出现失误，中标后又该如何处理？
   - expected: `opinion_278`
   - top1: `parent_水利工程建设项目监理招标投标管理办法_57_2353_2631`
   - law: `黄河水利委员会黄河水利科学研究院（本级）黄河凌汛多模态协同观测设备购置项目中标公`
   - type: `opinion_news` | span: `single`

945. [responsibility][cross_reference] 如果在投标复旦大学附属中山医院该项目时发现其他供应商违规，该怎么反映？
   - expected: `opinion_1492`
   - top1: `parent_及教学资源招标采购管理办法_19_2899_9454`
   - law: `复旦大学附属中山医院生化分析仪（ISE+P模块）公开招标公告`
   - type: `opinion_news` | span: `single`

946. [condition_check][scenario] 我们公司想承接国家税务局的高级技术服务项目，需要满足哪些资质要求？
   - expected: `opinion_1592`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_10_3670_5391`
   - law: `国家税务总局苏州市税务局2026年数据库、高斯库、内网即时通、数据备份软件等高级`
   - type: `opinion_news` | span: `single`

947. [responsibility][synonym] 若在投标该税务局该项目时遇到疑问，应联系哪个部门咨询？
   - expected: `opinion_1592`
   - top1: `parent_中央国家机关政府采购中心电子竞价采购管理_28_3612_9401`
   - law: `国家税务总局苏州市税务局2026年数据库、高斯库、内网即时通、数据备份软件等高级`
   - type: `opinion_news` | span: `single`

948. [procedure][scenario] 中标后，我们公司在签订合同前需要完成什么手续？
   - expected: `opinion_909`
   - top1: `parent_评标委员会应组织全体评标委员学习有关规定_60_1961_7592`
   - law: `山东省青岛第五十一中学青岛连云港校区食堂厨房设备采购项目中标公告`
   - type: `opinion_news` | span: `single`

949. [condition_check][scenario] 参与这个项目的投标，我们需要满足什么条件？
   - expected: `opinion_1157`
   - top1: `parent_房屋建筑和市政基础设施工程施工招标投标管_7_1128_3130`
   - law: `南四湖乌鳢青虾国家级水产种质资源保护区调整申报材料编制项目（二次）招标公告`
   - type: `opinion_news` | span: `single`

950. [procedure][scenario] 中标后，我们公司在签订合同前需要完成什么手续？
   - expected: `opinion_909`
   - top1: `parent_评标委员会应组织全体评标委员学习有关规定_60_1961_7592`
   - law: `山东省青岛第五十一中学青岛连云港校区食堂厨房设备采购项目中标公告`
   - type: `opinion_news` | span: `single`

951. [condition_check][scenario] 参与这个项目的投标，我们需要满足什么条件？
   - expected: `opinion_1157`
   - top1: `parent_房屋建筑和市政基础设施工程施工招标投标管_7_1128_3130`
   - law: `南四湖乌鳢青虾国家级水产种质资源保护区调整申报材料编制项目（二次）招标公告`
   - type: `opinion_news` | span: `single`

952. [comparison][synonym] 竞争性磋商和公开招标这两种采购方式，对我们投标人来说有什么不同呀？
   - expected: `opinion_810`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0024`
   - law: `河北省遵化市消防救援大队2026年度食堂食材配送服务采购项目竞争性磋商公告`
   - type: `opinion_news` | span: `single`

953. [comparison][synonym] 高校采购设备时选择公开招标，和我们平时购物选商品有什么不一样的地方呀？
   - expected: `opinion_1447`
   - top1: `parent_交通运输部部属单位政府采购管理办法_32_3949_1910`
   - law: `中国矿业大学通风柜采购项目公开招标公告`
   - type: `opinion_news` | span: `single`

954. [scenario_judgment][cross_reference] 如果我们学校没按规范招标就签合同，会有什么后果？
   - expected: `opinion_569`
   - top1: `parent_中华人民共和国招标投标法_59_62_4673`
   - law: `西南民族大学武侯校区、航空港校区、太平园校区视频及门禁出入系统维护保养服务项目（`
   - type: `opinion_news` | span: `single`

955. [condition_check][synonym] 我们公司想做政府采购代理，需要满足江西政府采购代理机构认定办法中的哪些具体条件？
   - expected: `opinion_1854`
   - top1: `parent_政府采购代理机构管理暂行办法_11_3512_3100`
   - law: `江西省政府采购代理机构资格认定办法`
   - type: `opinion_news` | span: `single`

956. [scenario_judgment][cross_reference] 如果中标后我们没按时签合同，会有什么后果？
   - expected: `opinion_236`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0641`
   - law: `东华大学热力学分析仪采购项目中标公告`
   - type: `opinion_news` | span: `single`

957. [condition_check][synonym] 我们公司想做政府采购代理，需要满足江西政府采购代理机构认定办法中的哪些具体条件？
   - expected: `opinion_1854`
   - top1: `parent_政府采购代理机构管理暂行办法_11_3512_3100`
   - law: `江西省政府采购代理机构资格认定办法`
   - type: `opinion_news` | span: `single`

958. [responsibility][synonym] 消防队食堂配送服务项目对我们企业有什么特殊要求吗？
   - expected: `opinion_417`
   - top1: `opinion_570`
   - law: `石家庄高新技术产业开发区消防救援大队食堂主副食品配送服务中标公告`
   - type: `opinion_news` | span: `single`

959. [comparison][scenario] 竞争性磋商和公开招标这两种采购方式，哪种更适合我们公司的这种情况呢？
   - expected: `opinion_754`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0024`
   - law: `昆明铁路公安局2026-2027年定点印刷服务项目竞争性磋商公告`
   - type: `opinion_news` | span: `single`

960. [condition_check][synonym] 我们公司想投标这个交通环境模拟系统项目，需要满足什么条件呀？
   - expected: `opinion_1597`
   - top1: `parent_经营性公路建设项目投资人招标投标管理规定_19_1738_4153`
   - law: `同济大学虚实融合增强混合交通环境模拟系统采购项目(第二次）公开招标公告`
   - type: `opinion_news` | span: `single`

961. [comparison][scenario] 公开招标和我们通常说的招标方式相比，在投标门槛上有何不同吗？
   - expected: `opinion_1597`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0055`
   - law: `同济大学虚实融合增强混合交通环境模拟系统采购项目(第二次）公开招标公告`
   - type: `opinion_news` | span: `single`

962. [procedure][synonym] 我们公司想投标这个设备采购项目，需要准备哪些投标文件呀？
   - expected: `opinion_1332`
   - top1: `parent_水利工程建设项目重要设备材料采购招标投标_30_2393_5488`
   - law: `新疆维吾尔自治区地质局矿产实验研究中心设备采购项目公开招标公告`
   - type: `opinion_news` | span: `single`

963. [procedure][scenario] 公开招标这种采购方式，中标后多久需要签合同呢？
   - expected: `opinion_1332`
   - top1: `parent_政府采购货物和服务招标投标管理办法_71_76_240`
   - law: `新疆维吾尔自治区地质局矿产实验研究中心设备采购项目公开招标公告`
   - type: `opinion_news` | span: `single`

964. [scenario_judgment][scenario] 如果我们公司有个紧急设备采购项目，是否可以使用非招标采购方式？
   - expected: `opinion_1897`
   - top1: `parent_中华人民共和国政府采购法实施条例_32_27_3943`
   - law: `辽宁省政府采购非招标采购方式管理暂行办法`
   - type: `opinion_news` | span: `single`

965. [comparison][synonym] 这种公开招标的项目和我们之前参与的采购项目相比，流程上有什么不同吗？
   - expected: `opinion_1651`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0055`
   - law: `南京大学低温光学恒温器系统采购公开招标公告`
   - type: `opinion_news` | span: `single`

966. [responsibility][synonym] 使用非招标采购方式的企业，我们需要向哪个部门咨询相关事宜？
   - expected: `opinion_1897`
   - top1: `parent_政府采购非招标采购方式管理办法_4_4172_8040`
   - law: `辽宁省政府采购非招标采购方式管理暂行办法`
   - type: `opinion_news` | span: `single`

967. [scenario_judgment][scenario] 如果我们公司有个紧急设备采购项目，是否可以使用非招标采购方式？
   - expected: `opinion_1897`
   - top1: `parent_中华人民共和国政府采购法实施条例_32_27_3943`
   - law: `辽宁省政府采购非招标采购方式管理暂行办法`
   - type: `opinion_news` | span: `single`

968. [comparison][synonym] 这种公开招标的项目和我们之前参与的采购项目相比，流程上有什么不同吗？
   - expected: `opinion_1651`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0055`
   - law: `南京大学低温光学恒温器系统采购公开招标公告`
   - type: `opinion_news` | span: `single`

969. [responsibility][synonym] 使用非招标采购方式的企业，我们需要向哪个部门咨询相关事宜？
   - expected: `opinion_1897`
   - top1: `parent_政府采购非招标采购方式管理办法_4_4172_8040`
   - law: `辽宁省政府采购非招标采购方式管理暂行办法`
   - type: `opinion_news` | span: `single`

970. [scenario_judgment][scenario] 如果我们公司有个紧急设备采购项目，是否可以使用非招标采购方式？
   - expected: `opinion_1897`
   - top1: `parent_中华人民共和国政府采购法实施条例_32_27_3943`
   - law: `辽宁省政府采购非招标采购方式管理暂行办法`
   - type: `opinion_news` | span: `single`

971. [comparison][synonym] 这种公开招标的项目和我们之前参与的采购项目相比，流程上有什么不同吗？
   - expected: `opinion_1651`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0055`
   - law: `南京大学低温光学恒温器系统采购公开招标公告`
   - type: `opinion_news` | span: `single`

972. [responsibility][synonym] 使用非招标采购方式的企业，我们需要向哪个部门咨询相关事宜？
   - expected: `opinion_1897`
   - top1: `parent_政府采购非招标采购方式管理办法_4_4172_8040`
   - law: `辽宁省政府采购非招标采购方式管理暂行办法`
   - type: `opinion_news` | span: `single`

973. [scenario_judgment][scenario] 如果我们公司有个紧急设备采购项目，是否可以使用非招标采购方式？
   - expected: `opinion_1897`
   - top1: `parent_中华人民共和国政府采购法实施条例_32_27_3943`
   - law: `辽宁省政府采购非招标采购方式管理暂行办法`
   - type: `opinion_news` | span: `single`

974. [comparison][synonym] 这种公开招标的项目和我们之前参与的采购项目相比，流程上有什么不同吗？
   - expected: `opinion_1651`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0055`
   - law: `南京大学低温光学恒温器系统采购公开招标公告`
   - type: `opinion_news` | span: `single`

975. [responsibility][synonym] 使用非招标采购方式的企业，我们需要向哪个部门咨询相关事宜？
   - expected: `opinion_1897`
   - top1: `parent_政府采购非招标采购方式管理办法_4_4172_8040`
   - law: `辽宁省政府采购非招标采购方式管理暂行办法`
   - type: `opinion_news` | span: `single`

976. [comparison][synonym] 这种公开招标的项目和我们之前参与的采购项目相比，流程上有什么不同吗？
   - expected: `opinion_1651`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0055`
   - law: `南京大学低温光学恒温器系统采购公开招标公告`
   - type: `opinion_news` | span: `single`

977. [comparison][synonym] 公开招标和邀请招标在这类项目中有什么区别？
   - expected: `opinion_1474`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0054`
   - law: `国家体育总局体育信息中心国家体育总局综合办公平台运维服务项目公开招标公告`
   - type: `opinion_news` | span: `single`

978. [comparison][synonym] 竞争性磋商的采购流程和我们之前使用的公开招标流程有什么不同？
   - expected: `opinion_656`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0024`
   - law: `SPD黑龙江训练基地维修改造二期工程项目竞争性磋商`
   - type: `opinion_news` | span: `single`

979. [procedure][scenario] 我们中标后签合同前还需要走哪些流程？
   - expected: `opinion_1625`
   - top1: `parent_评标委员会和评标方法暂行规定_49_442_1892`
   - law: `原位双轴力学试验设备公开招标公告`
   - type: `opinion_news` | span: `single`

980. [announcement_interpretation][synonym] 我们想了解这个招标公告属于什么类型的采购方式呀？
   - expected: `opinion_1512`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_6_3732_6517`
   - law: `上海交通大学三重四极杆质谱仪公开招标公告`
   - type: `opinion_news` | span: `single`

981. [condition_check][scenario] 参与这类招标项目需要满足什么条件呀？
   - expected: `opinion_1512`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0161`
   - law: `上海交通大学三重四极杆质谱仪公开招标公告`
   - type: `opinion_news` | span: `single`

982. [procedure][scenario] 中标后还需要进行哪些后续操作呀？
   - expected: `opinion_284`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_26_3721_9324`
   - law: `西安交通大学医学院第一附属医院超声治疗仪采购项目中标公告`
   - type: `opinion_news` | span: `single`

983. [announcement_interpretation][synonym] 竞争性磋商公告适用的项目有什么特点呀？
   - expected: `opinion_808`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0024`
   - law: `科尔沁右翼中旗消防救援大队2026年营区窗户和消防车库门更换工程项目竞争性磋商公`
   - type: `opinion_news` | span: `single`

984. [comparison][synonym] 公开招标和邀请招标这两种政府采购方式，在我们参与超高速摄像机采购项目时有什么不同？
   - expected: `opinion_1506`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0054`
   - law: `清华大学超高速摄像机采购项目公开招标公告`
   - type: `opinion_news` | span: `single`

985. [procedure][cross_reference] 我们公司涉及食品安全检测设备采购，看到财政部等部门的这项公告后，需要关注哪些采购流程变化？
   - expected: `opinion_21`
   - top1: `policy_32`
   - law: `财政部 公安部 市场监管总局关于开展2...`
   - type: `opinion_news` | span: `single`

986. [announcement_interpretation][scenario] 这类由多部门联合发布的公告，对我们的采购项目有什么重要意义？
   - expected: `opinion_21`
   - top1: `parent_政府采购竞争性磋商采购方式管理暂行办法_7_4131_5072`
   - law: `财政部 公安部 市场监管总局关于开展2...`
   - type: `opinion_news` | span: `single`

987. [comparison][synonym] 公开招标和邀请招标这两种方式，在我们参与超高速摄像机采购项目时有什么不同？
   - expected: `opinion_1506`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0054`
   - law: `清华大学超高速摄像机采购项目公开招标公告`
   - type: `opinion_news` | span: `single`

988. [procedure][cross_reference] 我们公司涉及食品安全检测设备采购，看到财政部等多部门的这项公告后，需要关注哪些采购流程变化？
   - expected: `opinion_21`
   - top1: `policy_32`
   - law: `财政部 公安部 市场监管总局关于开展2...`
   - type: `opinion_news` | span: `single`

989. [announcement_interpretation][scenario] 这类由多部门联合发布的公告，对我们的采购项目有什么重要意义？
   - expected: `opinion_21`
   - top1: `parent_政府采购竞争性磋商采购方式管理暂行办法_7_4131_5072`
   - law: `财政部 公安部 市场监管总局关于开展2...`
   - type: `opinion_news` | span: `single`

990. [condition_check][synonym] 在天津地区做工程招标投标时，我们需要遵守哪些监督管理规定？
   - expected: `opinion_1950`
   - top1: `parent_民政部工程建设项目招标投标管理办法_7_2906_1200`
   - law: `天津市建设工程施工招标投标监督管理规定`
   - type: `opinion_news` | span: `single`

991. [procedure][scenario] 学校宿舍维修工程中标后，施工过程中我们需要注意哪些合规流程？
   - expected: `opinion_459`
   - top1: `opinion_272`
   - law: `北京化工大学东校区学生宿舍7号楼维修工程中标结果公示`
   - type: `opinion_news` | span: `single`

992. [condition_check][scenario] 进行省级政府采购项目时，在资金使用方面有哪些管理规定需要注意？
   - expected: `opinion_1876`
   - top1: `parent_政府购买服务管理办法_28_4366_1085`
   - law: `吉林省省级政府采购资金使用管理暂行规定`
   - type: `opinion_news` | span: `single`

993. [responsibility][synonym] 如果发现这个宿舍维修项目存在违规操作，我们应该向哪个部门反映情况？
   - expected: `opinion_459`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_20_4089_987`
   - law: `北京化工大学东校区学生宿舍7号楼维修工程中标结果公示`
   - type: `opinion_news` | span: `single`

994. [procedure][scenario] 我们公司采购红外光谱仪中标后，签合同之前还需要完成哪些手续？
   - expected: `opinion_376`
   - top1: `parent_国有金融企业集中采购管理暂行规定_27_3910_2074`
   - law: `zycgr24041501傅里叶转换红外光谱仪中标公告`
   - type: `opinion_news` | span: `single`

995. [condition_check][synonym] 政府采购资金出现特殊情况是否可以申请灵活使用方式？
   - expected: `opinion_1876`
   - top1: `parent_中华人民共和国政府采购法实施条例_32_27_3943`
   - law: `吉林省省级政府采购资金使用管理暂行规定`
   - type: `opinion_news` | span: `single`

996. [responsibility][synonym] 如果中标结果有问题，我们该怎么投诉？
   - expected: `opinion_376`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0449`
   - law: `zycgr24041501傅里叶转换红外光谱仪中标公告`
   - type: `opinion_news` | span: `single`

997. [procedure][scenario] 这种中标公告意味着我们要开始提供服务了，接下来需要做哪些准备工作？
   - expected: `opinion_1029`
   - top1: `parent_政府采购货物和服务招标投标管理办法_69_3434_4913`
   - law: `浙江省成套工程有限公司关于杭州市公安局上城区分局机房和网络专业技术维护服务项目(`
   - type: `opinion_news` | span: `single`

998. [comparison][synonym] 这种竞争性磋商方式和我们之前参加的公开招标相比，对我们投标人来说有什么不同？
   - expected: `opinion_647`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0024`
   - law: `中山大学2026年东校园公共教学楼公共连廊封窗工程竞争性磋商公告`
   - type: `opinion_news` | span: `single`

999. [responsibility][scenario] 如果我们的项目中标后，出现服务不符合要求的情况，应该找哪个部门投诉？
   - expected: `opinion_1029`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0705`
   - law: `浙江省成套工程有限公司关于杭州市公安局上城区分局机房和网络专业技术维护服务项目(`
   - type: `opinion_news` | span: `single`

1000. [procedure][scenario] 我们想了解这类政府采购项目中标后需要办理哪些后续手续？
   - expected: `opinion_154`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_26_3721_9324`
   - law: `国家税务总局舟山市定海区税务局2026-2027年度机关食堂食材采购及配送服务项`
   - type: `opinion_news` | span: `single`

1001. [comparison][synonym] 这种公开招标和我们之前做的项目招标流程一样吗？需要注意什么特殊点？
   - expected: `opinion_1169`
   - top1: `parent_工程建设项目施工招标投标办法_11_11_7390`
   - law: `山东第一医科大学附属省立医院（山东省立医院）医疗设备维保项目公开招标招标公告`
   - type: `opinion_news` | span: `single`

1002. [condition_check][synonym] 我们想做医疗领域的公开招标采购项目，这类招标对供应商资质有什么要求？
   - expected: `opinion_1405`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_19_3795_3923`
   - law: `西安交通大学第二附属医院中医类耗材采购项目公开招标公告`
   - type: `opinion_news` | span: `single`

1003. [procedure][synonym] 中标后多久需要签订合同？
   - expected: `opinion_409`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0625`
   - law: `北京大学人民医院医疗设备购置项目第七批中标公告`
   - type: `opinion_news` | span: `single`

1004. [condition_check][synonym] 做康复类设备采购项目时，评标标准主要考察哪些方面？
   - expected: `opinion_258`
   - top1: `parent_重大装备自主化依托工程设备招标采购活动的_14_2926_9949`
   - law: `中国中医科学院望京医院国家中医药传承创新中心建设项目(设备采购第二批)一一康复类`
   - type: `opinion_news` | span: `single`

1005. [scenario_judgment][synonym] 中标后如果没及时履约会有什么处罚？
   - expected: `opinion_409`
   - top1: `parent_评标委员会应组织全体评标委员学习有关规定_75_1976_6139`
   - law: `北京大学人民医院医疗设备购置项目第七批中标公告`
   - type: `opinion_news` | span: `single`

1006. [procedure][synonym] 做康复类设备的采购项目，投标人需要提前准备哪些资质？
   - expected: `opinion_258`
   - top1: `parent_重大装备自主化依托工程设备招标采购活动的_10_2922_6010`
   - law: `中国中医科学院望京医院国家中医药传承创新中心建设项目(设备采购第二批)一一康复类`
   - type: `opinion_news` | span: `single`

1007. [procedure][synonym] 这类地价监测评估项目，中标后需要提交哪些报告？
   - expected: `opinion_1678`
   - top1: `parent_电子招标投标办法_34_727_993`
   - law: `105个城市地价监测评估与商品房成本调查（二次招标）公开招标公告`
   - type: `opinion_news` | span: `single`

1008. [scenario_judgment][scenario] 我们公司参与药品集中采购后，配送环节有哪些合规要求？
   - expected: `opinion_1870`
   - top1: `parent_药品集中采购监督管理办法_42_2632_4029`
   - law: `黑龙江省食品药品监督管理局关于下发药品集中采购配送...`
   - type: `opinion_news` | span: `single`

1009. [responsibility][cross_reference] 海关物业服务中标后，出现服务质量问题应该找谁反映？
   - expected: `opinion_205`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_18_3713_4013`
   - law: `北京海关十八里店档案楼及附属楼物业服务采购项目中标公告`
   - type: `opinion_news` | span: `single`

1010. [procedure][scenario] 我们公司中标了海关物业服务项目后，后续还需要完成哪些流程？
   - expected: `opinion_205`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0558`
   - law: `北京海关十八里店档案楼及附属楼物业服务采购项目中标公告`
   - type: `opinion_news` | span: `single`

1011. [scenario_judgment][cross_reference] 药品集中采购配送政策的实施对我们公司中标后的运营有什么影响？
   - expected: `opinion_1870`
   - top1: `parent_国家食品药品监督管理总局采购与招标管理办_18_2692_7033`
   - law: `黑龙江省食品药品监督管理局关于下发药品集中采购配送...`
   - type: `opinion_news` | span: `single`

1012. [definition][synonym] 政府采购中标后，成交结果确定意味着什么？
   - expected: `opinion_1977`
   - top1: `parent_集中采购机构是设区的市级以上人民政府依法_71_3115_163`
   - law: `关于北京市政府采购中标、成交结果确定有关问题的通知`
   - type: `opinion_news` | span: `single`

1013. [procedure][scenario] 我们公司中标北京市政府采购项目中标后，成交结果确定还需要做什么？
   - expected: `opinion_1977`
   - top1: `parent_国家技术创新项目招标投标管理办法_34_2807_2429`
   - law: `关于北京市政府采购中标、成交结果确定有关问题的通知`
   - type: `opinion_news` | span: `single`

1014. [procedure][scenario] 我们公司想做类似公开招标的项目，中标后签合同之前还需要走哪些流程？
   - expected: `opinion_1631`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0558`
   - law: `西北工业大学多频谱目标特征模拟与评估系统公开招标公告`
   - type: `opinion_news` | span: `single`

1015. [comparison][synonym] 这种公开招标和我们常用的邀请招标相比，在投标资格上有何不同？
   - expected: `opinion_1631`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0054`
   - law: `西北工业大学多频谱目标特征模拟与评估系统公开招标公告`
   - type: `opinion_news` | span: `single`

1016. [comparison][synonym] 这种公开招标和我们公司常用的邀请招标方式相比，在投标门槛上有什么区别吗？
   - expected: `opinion_1631`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0055`
   - law: `西北工业大学多频谱目标特征模拟与评估系统公开招标公告`
   - type: `opinion_news` | span: `single`

1017. [procedure][scenario] 我们公司中标了该公开招标项目，合同签订前还需要办理哪些手续？
   - expected: `opinion_1631`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0622`
   - law: `西北工业大学多频谱目标特征模拟与评估系统公开招标公告`
   - type: `opinion_news` | span: `single`

1018. [scenario_judgment][scenario] 我们公司进行政府集中采购时，需要遵循哪些管理规范？
   - expected: `opinion_1782`
   - top1: `parent_国有金融企业集中采购管理暂行规定_3_3886_9161`
   - law: `陕西省省级单位政府集中采购管理办法`
   - type: `opinion_news` | span: `single`

1019. [comparison][synonym] 政府采购使用集中采购和分散采购的区别是什么？
   - expected: `opinion_1782`
   - top1: `parent_交通运输部部属单位政府采购管理办法_5_3922_1992`
   - law: `陕西省省级单位政府集中采购管理办法`
   - type: `opinion_news` | span: `single`

1020. [comparison][synonym] 竞争性磋商和公开招标这两种采购方式，对我们投标人来说有什么不同？
   - expected: `opinion_560`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0024`
   - law: `宁波市消防救援支队宁波前湾新区消防救援大队食堂托管服务项目竞争性磋商公告`
   - type: `opinion_news` | span: `single`

1021. [comparison][synonym] 这种公开招标和我们常用的邀请招标相比，在投标资格上有何不同？
   - expected: `opinion_1631`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0054`
   - law: `西北工业大学多频谱目标特征模拟与评估系统公开招标公告`
   - type: `opinion_news` | span: `single`

1022. [procedure][scenario] 我们公司中标了这个竞争性磋商项目后，合同签订前需要完成哪些工作？
   - expected: `opinion_560`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0621`
   - law: `宁波市消防救援支队宁波前湾新区消防救援大队食堂托管服务项目竞争性磋商公告`
   - type: `opinion_news` | span: `single`

1023. [procedure][scenario] 我们公司中标了这类公开招标项目，合同签订前还需要办理哪些手续？
   - expected: `opinion_1631`
   - top1: `parent_工程建设项目施工招标投标办法_64_66_3671`
   - law: `西北工业大学多频谱目标特征模拟与评估系统公开招标公告`
   - type: `opinion_news` | span: `single`

1024. [comparison][synonym] 政府采购使用集中采购和分散采购的区别是什么？
   - expected: `opinion_1782`
   - top1: `parent_交通运输部部属单位政府采购管理办法_5_3922_1992`
   - law: `陕西省省级单位政府集中采购管理办法`
   - type: `opinion_news` | span: `single`

1025. [comparison][synonym] 竞争性磋商和公开招标这两种采购方式，对我们投标人来说有什么不同？
   - expected: `opinion_560`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0024`
   - law: `宁波市消防救援支队宁波前湾新区消防救援大队食堂托管服务项目竞争性磋商公告`
   - type: `opinion_news` | span: `single`

1026. [scenario_judgment][scenario] 我们公司进行政府集中采购时，需要遵循哪些管理规范？
   - expected: `opinion_1782`
   - top1: `parent_国有金融企业集中采购管理暂行规定_3_3886_9161`
   - law: `陕西省省级单位政府集中采购管理办法`
   - type: `opinion_news` | span: `single`

1027. [procedure][synonym] 办理政府采购信息公告需要准备哪些相关文件？
   - expected: `opinion_2011`
   - top1: `parent_中华人民共和国政府采购法实施条例_22_19_7099`
   - law: `河北省财政厅关于河北省政府采购信息公告管理有关事项...`
   - type: `opinion_news` | span: `single`

1028. [procedure][scenario] 我们公司中标了这个竞争性磋商项目后，合同签订前需要完成哪些工作？
   - expected: `opinion_560`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0621`
   - law: `宁波市消防救援支队宁波前湾新区消防救援大队食堂托管服务项目竞争性磋商公告`
   - type: `opinion_news` | span: `single`

1029. [scenario_judgment][scenario] 我们公司要发布政府采购信息公告，需要遵循哪些管理规定？
   - expected: `opinion_2011`
   - top1: `parent_《中华人民共和国政府采购法实施条例》等有_4_4376_7462`
   - law: `河北省财政厅关于河北省政府采购信息公告管理有关事项...`
   - type: `opinion_news` | span: `single`

1030. [procedure][scenario] 中标后签合同前，该项目还需要经过哪些审批流程？
   - expected: `opinion_1607`
   - top1: `parent_工程建设项目施工招标投标办法_64_66_3671`
   - law: `高温电解池陶瓷热解处理设备公开招标公告`
   - type: `opinion_news` | span: `single`

1031. [responsibility][cross_reference] 中标后，我们该如何确认中标结果的有效性？
   - expected: `opinion_1646`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_21_3850_1390`
   - law: `国家能源局信息中心2026-2027年能源局非涉密网络线路租用项目（二次）公开招`
   - type: `opinion_news` | span: `single`

1032. [announcement_interpretation][scenario] 我们学校食堂的蔬菜水果采购有了中标供应商，这个公告说明什么情况？
   - expected: `opinion_481`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_13_3708_3479`
   - law: `长安大学2026年长安大学后勤管理处学生食堂蔬菜、水果采购项目中标公告`
   - type: `opinion_news` | span: `single`

1033. [announcement_interpretation][scenario] 我们学校食堂的蔬菜水果采购有了中标供应商，这个公告说明什么情况？
   - expected: `opinion_481`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_13_3708_3479`
   - law: `长安大学2026年长安大学后勤管理处学生食堂蔬菜、水果采购项目中标公告`
   - type: `opinion_news` | span: `single`

1034. [procedure][synonym] 我们公司想参加这个医院的设备购置项目投标，需要提前准备什么材料？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_14_3843_6875`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1035. [responsibility][scenario] 我们公司中标了这个食堂换热站工程后，后续需要履行哪些合同义务？
   - expected: `opinion_122`
   - top1: `parent_机电产品国际招标评标专家及专家库管理办法_79_1360_6968`
   - law: `东北林业大学校园西区建设（二期）食堂换热站建设工程中标公告`
   - type: `opinion_news` | span: `single`

1036. [comparison][cross_reference] 这种公开招标的项目和我们之前参与的竞争性磋商项目有什么区别？
   - expected: `opinion_1460`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0023`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1037. [condition_check][scenario] 学校这类基建项目的招标流程一般有多长？
   - expected: `opinion_1422`
   - top1: `parent_明确或实际投标人报名数量未达到招标公告中_24_1098_2416`
   - law: `上海外国语大学松江校区体育馆施工、监理及后续其他子项目招标代理服务项目公开招标公`
   - type: `opinion_news` | span: `single`

1038. [procedure][synonym] 我们公司想参加这个医院的设备购置项目投标，需要提前准备什么材料？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_14_3843_6875`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1039. [procedure][scenario] 中标后我们需要办理哪些手续才能正式开始项目？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_15_3844_2075`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1040. [procedure][synonym] 我们公司想参加这个医院的设备购置项目投标，需要提前准备什么材料？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_14_3843_6875`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1041. [condition_check][scenario] 学校这类大型基建项目的招标流程大概需要多久？
   - expected: `opinion_1422`
   - top1: `parent_明确或实际投标人报名数量未达到招标公告中_24_1098_2416`
   - law: `上海外国语大学松江校区体育馆施工、监理及后续其他子项目招标代理服务项目公开招标公`
   - type: `opinion_news` | span: `single`

1042. [procedure][scenario] 中标后我们需要办理哪些手续才能正式开始项目？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_15_3844_2075`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1043. [condition_check][scenario] 学校这类大型基建项目的招标流程大概需要多久？
   - expected: `opinion_1422`
   - top1: `parent_明确或实际投标人报名数量未达到招标公告中_24_1098_2416`
   - law: `上海外国语大学松江校区体育馆施工、监理及后续其他子项目招标代理服务项目公开招标公`
   - type: `opinion_news` | span: `single`

1044. [procedure][scenario] 中标后我们需要办理哪些手续才能正式开始项目？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_15_3844_2075`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1045. [procedure][synonym] 我们公司想参加这个医院的设备购置项目投标，需要提前准备什么材料？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_14_3843_6875`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1046. [condition_check][scenario] 学校这类大型基建项目的招标流程大概需要多久？
   - expected: `opinion_1422`
   - top1: `parent_明确或实际投标人报名数量未达到招标公告中_24_1098_2416`
   - law: `上海外国语大学松江校区体育馆施工、监理及后续其他子项目招标代理服务项目公开招标公`
   - type: `opinion_news` | span: `single`

1047. [procedure][synonym] 我们公司想参加这个医院的设备购置项目投标，需要提前准备什么材料？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_14_3843_6875`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1048. [procedure][scenario] 中标后我们需要办理哪些手续才能正式开始项目？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_15_3844_2075`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1049. [condition_check][scenario] 学校这类大型基建项目的招标流程大概需要多久？
   - expected: `opinion_1422`
   - top1: `parent_明确或实际投标人报名数量未达到招标公告中_24_1098_2416`
   - law: `上海外国语大学松江校区体育馆施工、监理及后续其他子项目招标代理服务项目公开招标公`
   - type: `opinion_news` | span: `single`

1050. [procedure][synonym] 我们公司想参加这个医院的设备购置项目投标，需要提前准备什么材料？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_14_3843_6875`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1051. [procedure][scenario] 中标后我们需要办理哪些手续才能正式开始项目？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_15_3844_2075`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1052. [condition_check][scenario] 学校这类大型基建项目的招标流程大概需要多久？
   - expected: `opinion_1422`
   - top1: `parent_明确或实际投标人报名数量未达到招标公告中_24_1098_2416`
   - law: `上海外国语大学松江校区体育馆施工、监理及后续其他子项目招标代理服务项目公开招标公`
   - type: `opinion_news` | span: `single`

1053. [procedure][synonym] 我们公司想参加这个医院的设备购置项目投标，需要提前准备什么材料？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_14_3843_6875`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1054. [condition_check][scenario] 学校这类大型基建项目的招标流程大概需要多久？
   - expected: `opinion_1422`
   - top1: `parent_明确或实际投标人报名数量未达到招标公告中_24_1098_2416`
   - law: `上海外国语大学松江校区体育馆施工、监理及后续其他子项目招标代理服务项目公开招标公`
   - type: `opinion_news` | span: `single`

1055. [procedure][synonym] 我们公司想参加这个医院的设备购置项目投标，需要提前准备什么材料？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_14_3843_6875`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1056. [procedure][scenario] 中标后我们需要办理哪些手续才能正式开始项目？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_15_3844_2075`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1057. [procedure][scenario] 中标后我们需要办理哪些手续才能正式开始项目？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_15_3844_2075`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1058. [condition_check][scenario] 学校这类大型基建项目的招标流程大概需要多久？
   - expected: `opinion_1422`
   - top1: `parent_明确或实际投标人报名数量未达到招标公告中_24_1098_2416`
   - law: `上海外国语大学松江校区体育馆施工、监理及后续其他子项目招标代理服务项目公开招标公`
   - type: `opinion_news` | span: `single`

1059. [procedure][synonym] 我们公司想参加这个医院的设备购置项目投标，需要提前准备什么材料？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_14_3843_6875`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1060. [procedure][synonym] 我们公司想参加这个医院的设备购置项目投标，需要提前准备什么材料？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_14_3843_6875`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1061. [condition_check][scenario] 学校这类大型基建项目的招标流程大概需要多久？
   - expected: `opinion_1422`
   - top1: `parent_明确或实际投标人报名数量未达到招标公告中_24_1098_2416`
   - law: `上海外国语大学松江校区体育馆施工、监理及后续其他子项目招标代理服务项目公开招标公`
   - type: `opinion_news` | span: `single`

1062. [procedure][synonym] 我们公司想参加这个医院的设备购置项目投标，需要提前准备什么材料？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_14_3843_6875`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1063. [condition_check][scenario] 学校这类大型基建项目的招标流程大概需要多久？
   - expected: `opinion_1422`
   - top1: `parent_明确或实际投标人报名数量未达到招标公告中_24_1098_2416`
   - law: `上海外国语大学松江校区体育馆施工、监理及后续其他子项目招标代理服务项目公开招标公`
   - type: `opinion_news` | span: `single`

1064. [procedure][scenario] 中标后我们需要办理哪些手续才能正式开始项目？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_15_3844_2075`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1065. [condition_check][scenario] 学校这类大型基建项目的招标流程大概需要多久？
   - expected: `opinion_1422`
   - top1: `parent_明确或实际投标人报名数量未达到招标公告中_24_1098_2416`
   - law: `上海外国语大学松江校区体育馆施工、监理及后续其他子项目招标代理服务项目公开招标公`
   - type: `opinion_news` | span: `single`

1066. [procedure][synonym] 我们公司想参加这个医院的设备购置项目投标，需要提前准备什么材料？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_14_3843_6875`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1067. [procedure][scenario] 中标后我们需要办理哪些手续才能正式开始项目？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_15_3844_2075`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1068. [condition_check][scenario] 学校这类大型基建项目的招标流程大概需要多久？
   - expected: `opinion_1422`
   - top1: `parent_明确或实际投标人报名数量未达到招标公告中_24_1098_2416`
   - law: `上海外国语大学松江校区体育馆施工、监理及后续其他子项目招标代理服务项目公开招标公`
   - type: `opinion_news` | span: `single`

1069. [definition][scenario] 中标后我们需要办理哪些手续才能正式开始项目？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_15_3844_2075`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1070. [definition][synonym] 我们公司想参加这个医院的设备购置项目投标，需要提前准备什么材料？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_14_3843_6875`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1071. [procedure][scenario] 中标后我们需要办理哪些手续才能正式开始项目？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_15_3844_2075`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1072. [procedure][synonym] 我们公司想参加这个医院的设备购置项目投标，需要提前准备什么材料？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_14_3843_6875`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1073. [condition_check][scenario] 学校这类大型基建项目的招标流程大概需要多久？
   - expected: `opinion_1422`
   - top1: `parent_明确或实际投标人报名数量未达到招标公告中_24_1098_2416`
   - law: `上海外国语大学松江校区体育馆施工、监理及后续其他子项目招标代理服务项目公开招标公`
   - type: `opinion_news` | span: `single`

1074. [definition][synonym] 我们公司想参加这个医院的设备购置项目投标，需要提前准备什么材料？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_14_3843_6875`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1075. [definition][scenario] 中标后我们需要办理哪些手续才能正式开始项目？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_15_3844_2075`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1076. [procedure][scenario] 中标后我们需要办理哪些手续才能正式开始项目？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_15_3844_2075`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1077. [procedure][synonym] 我们公司想参加这个医院的设备购置项目投标，需要提前准备什么材料？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_14_3843_6875`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1078. [condition_check][scenario] 学校这类大型基建项目的招标流程大概需要多久？
   - expected: `opinion_1422`
   - top1: `parent_明确或实际投标人报名数量未达到招标公告中_24_1098_2416`
   - law: `上海外国语大学松江校区体育馆施工、监理及后续其他子项目招标代理服务项目公开招标公`
   - type: `opinion_news` | span: `single`

1079. [definition][synonym] 我们公司想参加这个医院的设备购置项目投标，需要提前准备什么材料？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_14_3843_6875`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1080. [definition][scenario] 中标后我们需要办理哪些手续才能正式开始项目？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_15_3844_2075`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1081. [procedure][synonym] 我们公司想参加这个医院的设备购置项目投标，需要提前准备什么材料？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_14_3843_6875`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1082. [procedure][scenario] 中标后我们需要办理哪些手续才能正式开始项目？
   - expected: `opinion_1460`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_15_3844_2075`
   - law: `中国医学科学院北京协和医院流式细胞仪设备购置项目公开招标公告`
   - type: `opinion_news` | span: `single`

1083. [comparison][cross_reference] 这种竞争性磋商招标方式和公开招标相比，对我们投标人来说有什么不同之处呢？
   - expected: `opinion_515`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0024`
   - law: `江西合胜合招标咨询有限公司关于南昌市西湖区消防救援大队2026年车辆维修保养定点`
   - type: `opinion_news` | span: `single`

1084. [condition_check][synonym] 我们公司想做安全生产标准化评审项目，需要满足什么条件才能参与这个招标呢？
   - expected: `opinion_1352`
   - top1: `opinion_1357`
   - law: `湖北省应急管理厅企业安全生产二级标准化定级评审（3包）公开招标公告`
   - type: `opinion_news` | span: `single`

1085. [comparison][synonym] 我们单位要采购FPGA相关技术服务，这种竞争性磋商和公开招标相比有什么不同？
   - expected: `opinion_555`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0023`
   - law: `工业和信息化部电子第五研究所FPGA代码静态分析工具可编程语言语法语义解析引擎算`
   - type: `opinion_news` | span: `single`

1086. [condition_check][scenario] 如果我们公司参与防贫保险项目，需要关注这个公告吗？
   - expected: `opinion_939`
   - top1: `parent_招标公告和公示信息发布管理办法_24_796_6788`
   - law: `2026年防返贫保险项目成交结果公告`
   - type: `opinion_news` | span: `single`

1087. [procedure][scenario] 我们公司想做膜电极采购项目（二次），需要提前了解哪些投标要求？
   - expected: `opinion_1339`
   - top1: `opinion_1397`
   - law: `阿克苏地区某单位2026年大宗生活物资采购项目（标项一：面粉）公开招标公告`
   - type: `opinion_news` | span: `single`

1088. [comparison][cross_reference] 在政府采购中，不同地区和部门是如何开展采购工作的？
   - expected: `opinion_1524`
   - top1: `parent_中华人民共和国政府采购法实施条例_6_3054_6830`
   - law: ``
   - type: `cross_doc` | span: `cross_doc`

1089. [comparison][cross_reference] 这两个政府采购项目在内容和流程上有何异同？
   - expected: `opinion_657`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0101`
   - law: ``
   - type: `cross_doc` | span: `cross_doc`

1090. [procedure][cross_reference] 开展这样的消防站建设项目时，需要参照哪类管理规定？
   - expected: `opinion_1443`
   - top1: `parent_建筑工程施工许可管理办法_18_1201_9185`
   - law: ``
   - type: `cross_doc` | span: `cross_doc`

1091. [comparison][cross_reference] 这两种政府采购项目公告所采用的采购方式有何不同？
   - expected: `opinion_1610`
   - top1: `parent_中华人民共和国政府采购法_26_2983_6166`
   - law: ``
   - type: `cross_doc` | span: `cross_doc`

1092. [procedure][cross_reference] 该气象防灾减灾工程招标项目的招标过程需要遵循招标投标法实施条例中关于投标人参与的规定有哪些？
   - expected: `parent_中华人民共和国招标投标法实施条例_33_106_8063`
   - top1: `parent_标法》《中华人民共和国招标投标法实施条例_32_1840_4576`
   - law: ``
   - type: `cross_doc` | span: `cross_doc`

1093. [procedure][cross_reference] 这两个政府采购项目在流程阶段有什么不同呀？
   - expected: `opinion_125`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0023`
   - law: ``
   - type: `cross_doc` | span: `cross_doc`

1094. [procedure][cross_reference] 盐田区基因科技守护认知健康项目招标中对评审专家有什么管理规定吗？
   - expected: `opinion_1206`
   - top1: `parent_进一步规范机电产品国际招标投标活动有关规_24_1243_8327`
   - law: ``
   - type: `cross_doc` | span: `cross_doc`

1095. [scenario_judgment][cross_reference] 这两个内容分别是什么性质的文件，它们之间有什么关系吗？
   - expected: `opinion_144`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0767`
   - law: ``
   - type: `cross_doc` | span: `cross_doc`

1096. [comparison][cross_reference] 重庆和北京的政府采购管理规定在哪些方面存在差异？
   - expected: `opinion_1748`
   - top1: `policy_214`
   - law: ``
   - type: `cross_doc` | span: `cross_doc`

1097. [procedure][cross_reference] 这两个消防相关的政府采购项目在流程上有什么样的先后或关联关系？
   - expected: `opinion_596`
   - top1: `opinion_648`
   - law: ``
   - type: `cross_doc` | span: `cross_doc`

1098. [condition_check][cross_reference] 关于政府采购，地方法规和具体项目的执行结果之间有什么样的关系？
   - expected: `opinion_1733`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0098`
   - law: ``
   - type: `cross_doc` | span: `cross_doc`

1099. [procedure][cross_reference] 如果在汕头海事局后勤综合保障专项中标后，该项目的服务提供需要进行履约验收，应该如何进行？
   - expected: `parent_财政部关于推进和完善服务项目政府采购有关_27_3501_7020`
   - top1: `parent_交通运输部部属单位政府采购管理办法_39_3956_5595`
   - law: ``
   - type: `cross_doc` | span: `cross_doc`

1100. [procedure][cross_reference] 这两个政府采购项目在流程上有什么区别和联系？
   - expected: `opinion_689`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0023`
   - law: ``
   - type: `cross_doc` | span: `cross_doc`

1101. [procedure][cross_reference] 如果在福州市气象局的该采购项目中涉及到进口产品，需要遵循怎样的审核规定呢？
   - expected: `opinion_753`
   - top1: `parent_政府采购进口产品管理办法_10_4049_438`
   - law: ``
   - type: `cross_doc` | span: `cross_doc`

1102. [comparison][cross_reference] 这两个政府采购项目分别属于什么性质的项目？
   - expected: `opinion_689`
   - top1: `parent_政府采购货物和服务招标投标管理办法_4_3362_6578`
   - law: ``
   - type: `cross_doc` | span: `cross_doc`

1103. [procedure][cross_reference] 这两个政府采购项目在流程上有有什么区别和联系？
   - expected: `opinion_689`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0023`
   - law: ``
   - type: `cross_doc` | span: `cross_doc`

1104. [procedure][cross_reference] 这两个政府采购项目在流程阶段怎样的先后顺序和关系？
   - expected: `opinion_689`
   - top1: `parent_政府采购框架协议采购方式管理暂行办法_32_4275_5314`
   - law: ``
   - type: `cross_doc` | span: `cross_doc`

1105. [scenario_judgment][cross_reference] 这两个政府采购项目分别在政府采购流程的哪个阶段？
   - expected: `opinion_689`
   - top1: `parent_政府采购框架协议采购方式管理暂行办法_32_4275_5314`
   - law: ``
   - type: `cross_doc` | span: `cross_doc`

1106. [scenario_judgment][cross_reference] 这两个政府采购项目在流程上有什么政府采购的哪些阶段？
   - expected: `opinion_689`
   - top1: `parent_政府采购框架协议采购方式管理暂行办法_32_4275_5314`
   - law: ``
   - type: `cross_doc` | span: `cross_doc`

1107. [scenario_judgment][cross_reference] 政府采购的法规政策具体项目中标公告之间有什么关联？
   - expected: `opinion_476`
   - top1: `parent_政府采购货物和服务招标投标管理办法_69_3434_4913`
   - law: ``
   - type: `cross_doc` | span: `cross_doc`

1108. [procedure][cross_reference] 政府采购中的招标项目和规范通知之间是什么关系？
   - expected: `opinion_1278`
   - top1: `parent_政府投资条例_1_372_6925`
   - law: ``
   - type: `cross_doc` | span: `cross_doc`

1109. [comparison][cross_reference] 不同领域的政府采购招标项目在操作上有何共性及差异？
   - expected: `opinion_1443`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0026`
   - law: ``
   - type: `cross_doc` | span: `cross_doc`

1110. [procedure][cross_reference] 这两个公共项目在政府采购流程中处于什么阶段？
   - expected: `opinion_734`
   - top1: `parent_中华人民共和国政府采购法_35_2992_8808`
   - law: ``
   - type: `cross_doc` | span: `cross_doc`

1111. [comparison][cross_reference] 这两个招标项目分别针对什么医疗设备？它们在招标性质上有何不同？
   - expected: `opinion_1270`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0687`
   - law: ``
   - type: `cross_doc` | span: `cross_doc`

1112. [comparison][cross_reference] 这两个政府采购项目在采购方式和采购性质上有哪些不同？
   - expected: `opinion_37`
   - top1: `parent_中华人民共和国政府采购法_27_2984_541`
   - law: ``
   - type: `cross_doc` | span: `cross_doc`

1113. [comparison][cross_reference] 这两个招标公告分别属于哪种类型的政府采购项目？
   - expected: `opinion_1217`
   - top1: `parent_政府采购货物和服务招标投标管理办法_4_4_9067`
   - law: ``
   - type: `cross_doc` | span: `cross_doc`

1114. [procedure][cross_reference] 这两个与政府采购相关的文件分别涉及哪类招标项目？它们在执行过程中有哪些关联？
   - expected: `opinion_1547`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0767`
   - law: ``
   - type: `cross_doc` | span: `cross_doc`
