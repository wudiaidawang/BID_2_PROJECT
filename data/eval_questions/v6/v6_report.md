# V6 召回评测报告 — Chunk ID 匹配

**评测集**: v6_benchmark.json, 2908 题
**评测方式**: 纯 chunk ID 匹配（expected_chunk_id / acceptable_chunk_ids）

## 整体召回率

| 指标 | 命中 | 总数 | 比率 |
|------|------|------|------|
| Recall@1 | 1010 | 2908 | **34.7%** |
| Recall@3 | 1445 | 2908 | **49.7%** |
| Recall@5 | 1586 | 2908 | **54.5%** |
## 按 chunk_type

| 类型 | 题数 | Recall@1 | Recall@3 | Recall@5 |
|------|------|----------|----------|----------|
| cross_doc | 46 | 23.9% | 32.6% | **34.8%** |
| opinion_news | 266 | 18.8% | 24.4% | **25.6%** |
| pdf_case_paragraph | 669 | 43.8% | 59.2% | **66.2%** |
| pdf_case_sliding | 252 | 15.9% | 36.5% | **44.4%** |
| pdf_law_parent | 584 | 51.7% | 70.0% | **74.7%** |
| policy_doc | 1091 | 28.8% | 42.9% | **46.8%** |

## 按 question_type (题型)

| 类型 | 题数 | Recall@1 | Recall@3 | Recall@5 |
|------|------|----------|----------|----------|
| announcement_interpretation | 29 | 51.7% | 62.1% | **69.0%** |
| case_reasoning | 78 | 33.3% | 55.1% | **65.4%** |
| comparison | 150 | 28.7% | 42.7% | **44.7%** |
| condition_check | 327 | 33.0% | 50.8% | **53.5%** |
| definition | 281 | 43.8% | 63.3% | **68.0%** |
| procedure | 582 | 30.1% | 39.0% | **43.6%** |
| responsibility | 264 | 33.0% | 48.9% | **54.9%** |
| scenario_judgment | 1197 | 36.2% | 51.8% | **57.1%** |

## 按 retrieval_difficulty (检索难度)

| 类型 | 题数 | Recall@1 | Recall@3 | Recall@5 |
|------|------|----------|----------|----------|
| cross_reference | 169 | 26.6% | 43.2% | **47.9%** |
| direct | 765 | 40.8% | 55.0% | **59.7%** |
| scenario | 1414 | 33.0% | 48.0% | **53.7%** |
| synonym | 560 | 33.2% | 48.6% | **51.6%** |

## 按 span

| 类型 | 题数 | Recall@1 | Recall@3 | Recall@5 |
|------|------|----------|----------|----------|
| cross_doc | 46 | 23.9% | 32.6% | **34.8%** |
| single | 2862 | 34.9% | 50.0% | **54.9%** |

## 交叉分析: chunk_type × question_type

| chunk_type \ question_type | announcement_interpretation | case_reasoning | comparison | condition_check | definition | procedure | responsibility | scenario_judgment |
|---|---|---|---|---|---|---|---|---|
## Miss 样本

共 1322 条 (R@5 仍未命中):

1. [scenario_judgment][scenario] 我们公司作为经营主体，在市交易中心场内交易中，信用记分的结果会影响什么方面？
   - expected: `policy_40`
   - top1: `policy_121`

2. [procedure][scenario] 我们公司在采购项目中标后，需要多久必须完成合同签订？
   - expected: `policy_40`
   - top1: `parent_中华人民共和国政府采购法_46_3003_3920`

3. [scenario_judgment][scenario] 我们公司在市交易中心进行场内交易时，如果出现不良行为会被怎么记分？
   - expected: `policy_40`
   - top1: `policy_129`

4. [scenario_judgment][scenario] 我们公司想做工程总承包项目，需要了解哪些电子招标投标的要求？
   - expected: `policy_123`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0060`

5. [procedure][direct] 我们公司中标项目后发起支付申请应该，应该通过什么方式操作呢？
   - expected: `policy_15`
   - top1: `parent_出口商品配额招标办法_22_2751_4543`

6. [scenario_judgment][scenario] 企业在招投标项目中，若未招标或中标无效，合同效力如何？
   - expected: `policy_63`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0117`

7. [scenario_judgment][scenario] 企业在工程项目建设中，若中标人和中标人另行签订合同实质性内容不一致，应如何认定？
   - expected: `policy_63`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0628`

8. [scenario_judgment][scenario] 企业在工程款支付时，若承包人未取得资质或超越资质等级，该如何处理？
   - expected: `policy_63`
   - top1: `pdf_建设工程施工合同纠纷案_17_1012`

9. [scenario_judgment][scenario] 企业在工程项目建设中，若项目必须招标而未招标，合同效力如何？
   - expected: `policy_63`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0116`

10. [responsibility][direct] 疫苗流通过程中出现安全问题，我们应该向哪个部门投诉？
   - expected: `policy_105`
   - top1: `parent_中华人民共和国招标投标法实施条例_61_136_9767`

11. [procedure][scenario] 我们公司中标疫苗项目后，多久内必须完成合同签订？
   - expected: `policy_105`
   - top1: `parent_投资项目招标投标管理办法_23_2560_3953`

12. [procedure][direct] 开展集体经济项目时，需要遵循哪些程序？
   - expected: `policy_104`
   - top1: `parent_政府投资条例_9_341_863`

13. [scenario_judgment][scenario] 我们公司在做政府采购电子卖场项目时，需要关注哪些合规要点？
   - expected: `policy_148`
   - top1: `parent_中央国家机关政府采购电子卖场管理办法_3_3629_828`

14. [definition][direct] 政府采购电子卖场的项目分类有哪些具体规定？
   - expected: `policy_148`
   - top1: `policy_205`

15. [procedure][direct] 企业在使用政府采购电子卖场时，如何保障交易安全？
   - expected: `policy_148`
   - top1: `parent_中央国家机关政府采购电子卖场管理办法_5_3631_2591`

16. [comparison][scenario] 政府采购电子卖场的流程与传统采购方式相比有什么优势？
   - expected: `policy_148`
   - top1: `parent_中央国家机关政府采购电子卖场管理办法_2_3628_7620`

17. [scenario_judgment][scenario] 我们公司想做公路相关的政府采购项目，需要了解哪些支持政策？
   - expected: `policy_151`
   - top1: `policy_158`

18. [procedure][direct] 政府采购支持公路项目的申请流程是怎样的？
   - expected: `policy_151`
   - top1: `parent_经营性公路建设项目投资人招标投标管理规定_12_1731_3226`

19. [responsibility][scenario] 公路项目中的政府采购支持政策对企业中小企业有什么优惠？
   - expected: `policy_151`
   - top1: `parent_《中华人民共和国中小企业促进法》等有关法_4_3973_1234`

20. [condition_check][cross_reference] 这类政府采购支持在评标时有没有特殊要求？
   - expected: `policy_151`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0295`

21. [scenario_judgment][scenario] 我们公司想做政府购买服务项目，需要先了解哪些关键信息？
   - expected: `policy_214`
   - top1: `parent_政府购买服务管理办法_16_4353_5607`

22. [scenario_judgment][scenario] 我们公司在购买服务时，是否可以随意选择供应商？
   - expected: `policy_214`
   - top1: `parent_中央国家机关政府采购中心货物和服务定点采_17_3745_633`

23. [scenario_judgment][scenario] 如果我们在政府购买服务过程中出现违规情况，会有什么处罚？
   - expected: `policy_214`
   - top1: `parent_政府购买服务管理办法_31_4369_5534`

24. [procedure][direct] 我们公司想了解政府购买服务的具体流程是怎样的？
   - expected: `policy_214`
   - top1: `parent_政府购买服务管理办法_11_4348_4471`

25. [condition_check][direct] 我们公司作为服务提供方，需要满足哪些资质要求？
   - expected: `policy_214`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0542`

26. [scenario_judgment][scenario] 我们公司想参与政府购买服务，需要提前做哪些准备工作？
   - expected: `policy_214`
   - top1: `parent_政府购买服务管理办法_14_4351_5332`

27. [procedure][direct] 我们公司即将开展政府采购项目，在需求编制阶段需要注意哪些核心要点？
   - expected: `policy_227`
   - top1: `parent_中华人民共和国政府采购法实施条例_15_16_4367`

28. [responsibility][direct] 如果企业在政府采购项目中出现质疑情况，应该向哪个部门提出投诉？投诉流程有什么要求？
   - expected: `policy_143`
   - top1: `pdf_招标投标法律解读与风险防范实务_para_0684`

29. [procedure][scenario] 政府采购项目从需求编制到最终公示，整个流程大致需要多长时间？各个环节的时效性要求是什么？
   - expected: `policy_227`
   - top1: `parent_财政部关于做好政府采购信息公开工作的通知_31_4396_9219`

30. [scenario_judgment][scenario] 当政府采购项目出现违规情况时，企业应该如何应对和处理，避免受到处罚？
   - expected: `policy_143`
   - top1: `parent_《中华人民共和国政府采购法实施条例》等有_38_4030_8696`
