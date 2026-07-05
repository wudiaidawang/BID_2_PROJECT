# V9 召回评测报告 — Chunk ID 匹配（加权融合 + 法条Boost + Parent上下文增强）

**评测集**: v8_canonical.jsonl, 2832 题
**评测方式**: 纯 chunk ID 匹配（expected_chunk_id / acceptable_chunk_ids）
**融合策略**: Weighted Fusion（Min-Max 归一化 + 动态权重 semantic 0.55/0.45 + 法条检测 Boost）
**统一口径**: Pool@30 = 各阶段取 top 30 看 target 是否在池中（与 reranker 入口对齐）
**BM25**: 本地 jieba 分词

## 各阶段召回率对比

| 阶段 | Recall@1 | Recall@3 | Recall@5 | Pool@30 |
|------|----------|----------|----------|---------|
| Dense only | 52.9% | 72.8% | 78.0% | 92.7% |
| BM25 (jieba) | 62.1% | 80.3% | 86.4% | 96.8% |
| Weighted fused | 62.4% | 81.0% | 87.2% | 97.7% |
| Parent expanded | 62.4% | 81.0% | 87.2% | 97.7% |
| Reranker final | 70.5% | 88.3% | 92.0% | 92.0% |

## 最终召回率 (Reranker 后)

| 指标 | 命中 | 总数 | 比率 |
|------|------|------|------|
| Recall@1 | 1997 | 2832 | **70.5%** |
| Recall@3 | 2502 | 2832 | **88.3%** |
| Recall@5 | 2606 | 2832 | **92.0%** |

## 按 benchmark_level (改写层次)

| 类型 | 题数 | Recall@1 | Recall@3 | Recall@5 |
|------|------|----------|----------|----------|
| canonical | 2832 | 70.5% | 88.3% | **92.0%** |

## 按 chunk_type

| 类型 | 题数 | Recall@1 | Recall@3 | Recall@5 |
|------|------|----------|----------|----------|
| opinion_news | 130 | 97.7% | 98.5% | **100.0%** |
| pdf_case_sliding | 223 | 49.8% | 80.3% | **90.6%** |
| pdf_case_structured | 428 | 63.6% | 89.3% | **90.7%** |
| pdf_law_child | 235 | 65.1% | 82.6% | **90.2%** |
| pdf_law_parent | 1075 | 66.5% | 84.6% | **89.1%** |
| policy_doc | 741 | 83.5% | 95.8% | **96.6%** |

## 按 question_type (题型)

| 类型 | 题数 | Recall@1 | Recall@3 | Recall@5 |
|------|------|----------|----------|----------|
| announcement_interpretation | 88 | 90.9% | 95.5% | **98.9%** |
| case_reasoning | 147 | 54.4% | 81.6% | **90.5%** |
| condition_check | 548 | 69.0% | 87.4% | **90.3%** |
| definition | 212 | 68.9% | 90.1% | **92.5%** |
| procedure | 1087 | 68.8% | 86.7% | **91.0%** |
| responsibility | 364 | 75.0% | 92.3% | **94.5%** |
| scenario_judgment | 386 | 75.6% | 90.7% | **93.8%** |

## 按 retrieval_difficulty (检索难度)

| 类型 | 题数 | Recall@1 | Recall@3 | Recall@5 |
|------|------|----------|----------|----------|
| direct | 208 | 67.3% | 87.0% | **88.9%** |
| scenario | 12 | 83.3% | 91.7% | **91.7%** |
| synonym | 2612 | 70.7% | 88.4% | **92.3%** |

## 按 span

| 类型 | 题数 | Recall@1 | Recall@3 | Recall@5 |
|------|------|----------|----------|----------|
| cross_chunk | 517 | 63.2% | 81.2% | **86.5%** |
| cross_doc | 51 | 37.3% | 52.9% | **70.6%** |
| single | 2264 | 72.9% | 90.8% | **93.8%** |

## 交叉分析: chunk_type × question_type

| chunk_type \ question_type | announcement_interpretation | case_reasoning | condition_check | definition | procedure | responsibility | scenario_judgment |
|---|---|---|---|---|---|---|---|
## Miss 样本

共 226 条 (R@5 仍未命中):

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

6. [scenario_judgment][synonym] 上海市公共资源交易平台包含哪些分平台？
   - expected: `policy_67`
   - top1: `policy_125`
   - law: `【国有产权】市国资委关于延长上海市产权交易场所管理实施办法(暂行)有效期的通知`
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

9. [scenario_judgment][synonym] 上海市公共资源交易平台建设工程招投标分平台属于哪个系统？
   - expected: `policy_100`
   - top1: `policy_0`
   - law: `【建设工程】勘察电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

10. [scenario_judgment][synonym] 上海市公共资源交易平台包含哪些分平台？
   - expected: `policy_76`
   - top1: `policy_125`
   - law: `【拍卖服务】上海市人民政府关于延长《上海市交易场所管理暂行办法》有效期的通知`
   - type: `policy_doc` | span: `single`

11. [scenario_judgment][synonym] 上海市公共资源交易平台包含哪些分平台？
   - expected: `policy_5`
   - top1: `policy_125`
   - law: `上海市公共资源场内交易信用记分管理办法（试行）`
   - type: `policy_doc` | span: `single`

12. [definition][direct] 《评标专家和评标专家库管理办法》是什么文件？
   - expected: `policy_6`
   - top1: `policy_4`
   - law: `《评标专家和评标专家库管理办法》 2024年第26号令`
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
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0061`
   - law: `评标委员会和评标方法暂行规定`
   - type: `policy_doc` | span: `single`

19. [responsibility][synonym] 评标委员会的职责是什么？
   - expected: `policy_20`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0555`
   - law: `评标委员会和评标方法暂行规定`
   - type: `policy_doc` | span: `single`

20. [procedure][synonym] 上海市公共资源交易平台包含哪些分平台？
   - expected: `policy_1`
   - top1: `policy_125`
   - law: `关于印发《2023年上海市公共资源“一网交易”改革重点工作安排》的通知`
   - type: `policy_doc` | span: `single`

21. [condition_check][synonym] 工程建设项目招标投标中，哪些施工单项合同需要依法进行招标？
   - expected: `policy_68`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0119`
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

24. [procedure][synonym] 庄某某施工队完成部分的总造价是多少？
   - expected: `pdf_建设工程施工合同纠纷案_19_1689`
   - top1: `pdf_建设工程施工合同纠纷案_7_821`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

25. [procedure][synonym] 庄某某施工队完成地下部分和地上四层以上部分的工程款分别应如何计算？
   - expected: `pdf_建设工程施工合同纠纷案_11_4184`
   - top1: `pdf_建设工程施工合同纠纷案_27_5942`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

26. [definition][synonym] 在串通投标不正当竞争纠纷案中，法院如何认定标底降幅的法律性质？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_16_4494`
   - top1: `pdf_运输服务公司串通投标不正当竞争纠纷案_7_8767`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `cross_chunk`

27. [definition][synonym] 串通投标罪的构成要件是什么？
   - expected: `pdf_非国家工作人员行贿案_5_3262`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0835`
   - law: `非国家工作人员行贿案`
   - type: `pdf_case_sliding` | span: `single`

28. [responsibility][synonym] 建设工程施工合同纠纷中，法院如何确定已完成工程部分的工程款利息？
   - expected: `pdf_建设工程施工合同纠纷案_27_5942`
   - top1: `pdf_建设工程施工合同纠纷案_29_5006`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

29. [definition][synonym] 串通投标罪的构成要件是什么？
   - expected: `pdf_非国家工作人员行贿案_4_4553`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0835`
   - law: `非国家工作人员行贿案`
   - type: `pdf_case_sliding` | span: `single`

30. [definition][synonym] 标底降幅为何被认定为商业秘密？
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_9_1875`
   - top1: `pdf_运输服务公司串通投标不正当竞争纠纷案_17_9444`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `single`

31. [definition][synonym] 串通投标罪的构成要件是什么？
   - expected: `pdf_非国家工作人员行贿案_3_3318`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0835`
   - law: `非国家工作人员行贿案`
   - type: `pdf_case_sliding` | span: `single`

32. [case_reasoning][synonym] 2009年12月验收合格的工程，吉林某房地产公司最终需要支付东北某建设公司多少工程款？
   - expected: `pdf_建设工程施工合同纠纷案_13_9572`
   - top1: `pdf_建设工程施工合同纠纷案_4_3890`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

33. [case_reasoning][synonym] 在国有建设用地使用权挂牌出让过程中，竞买人通过给付补偿金的方式让其他公司放弃竞买，这种行为同时构成串通投标罪和非国家工作人员行贿罪，应如何处罚？
   - expected: `pdf_非国家工作人员行贿案_0_4758`
   - top1: `pdf_非国家工作人员行贿案_4_4553`
   - law: `非国家工作人员行贿案`
   - type: `pdf_case_sliding` | span: `cross_chunk`

34. [procedure][synonym] 庄某某借用吉林某建设公司资质进行投标后，与吉林某房地产公司签订了什么合同？
   - expected: `pdf_建设工程施工合同纠纷案_1_6506`
   - top1: `pdf_建设工程施工合同纠纷案_2_4194`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

35. [case_reasoning][synonym] 某建设公司向吉林某房地产公司主张的工程款总额是多少？利息从何时开始计算？
   - expected: `pdf_建设工程施工合同纠纷案_1_6506`
   - top1: `pdf_建设工程施工合同纠纷案_29_5006`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

36. [procedure][synonym] 某建设公司向吉林某房地产公司主张的工程款包括哪些部分？
   - expected: `pdf_建设工程施工合同纠纷案_1_6506`
   - top1: `pdf_建设工程施工合同纠纷案_20_5595`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

37. [procedure][synonym] 庄某某借用吉林某建设公司资质进行投标后，与吉林某房地产公司签订了什么合同？
   - expected: `pdf_建设工程施工合同纠纷案_1_6506`
   - top1: `pdf_建设工程施工合同纠纷案_2_4194`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

38. [case_reasoning][synonym] 本案一审和二审的法院及案号是什么？
   - expected: `pdf_建设工程施工合同纠纷案_33_9795`
   - top1: `pdf_建设工程施工合同纠纷案_34_7213`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

39. [condition_check][synonym] 投标人在投标过程中有哪些行为会导致投标无效？
   - expected: `parent_中华人民共和国道路运输条例_50_643_3802`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0856`
   - law: `中华人民共和国道路运输条例`
   - type: `pdf_law_parent` | span: `single`

40. [responsibility][synonym] 各级政府部门在招标投标活动中的职责是什么？
   - expected: `parent_明确或实际投标人报名数量未达到招标公告中_41_386_1667`
   - top1: `parent_电子招标投标办法_4_244_2005`
   - law: `明确或实际投标人报名数量未达到招标公告中规定`
   - type: `pdf_law_parent` | span: `single`

41. [procedure][synonym] 采购代理机构在收到供应商的询问或质疑后应当如何处理？
   - expected: `parent_中华人民共和国政府采购法_51_1077_8459`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0775`
   - law: `中华人民共和国政府采购法`
   - type: `pdf_law_parent` | span: `single`

42. [condition_check][synonym] 哪些情况下招标人可以不经随机抽取方式确定专家？
   - expected: `parent_民航专业工程建设项目招标投标管理办法_36_798_4903`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0548`
   - law: `民航专业工程建设项目招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

43. [procedure][synonym] 政府采购活动中采购人有哪些禁止行为？
   - expected: `parent_中华人民共和国政府采购法实施条例_11_1093_1402`
   - top1: `parent_政府采购货物和服务招标投标管理办法_4_1201_9622`
   - law: `中华人民共和国政府采购法实施条例`
   - type: `pdf_law_parent` | span: `single`

44. [procedure][synonym] 联合体投标有哪些规定，资格预审后联合体增减、更换成员会有什么后果？
   - expected: `parent_民航专业工程建设项目招标投标管理办法_28_795_7248`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0885`
   - law: `民航专业工程建设项目招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

45. [condition_check][synonym] 评审专家库的专家需要满足哪些条件？
   - expected: `parent_道路旅客运输班线经营权招标投标办法_30_638_3963`
   - top1: `parent_评标专家和评标专家库管理暂行办法_5_159_6981`
   - law: `道路旅客运输班线经营权招标投标办法`
   - type: `pdf_law_parent` | span: `single`

46. [procedure][synonym] 评标委员会的组成有哪些要求？
   - expected: `parent_道路旅客运输班线经营权招标投标办法_30_638_3963`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0061`
   - law: `道路旅客运输班线经营权招标投标办法`
   - type: `pdf_law_parent` | span: `single`

47. [condition_check][synonym] 招标文件的收费有什么限制？
   - expected: `parent_工程建设项目勘察设计招标投标办法_12_205_3641`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0299`
   - law: `工程建设项目勘察设计招标投标办法`
   - type: `pdf_law_parent` | span: `single`

48. [responsibility][synonym] 采购当事人有哪些行为会被依法追究责任？
   - expected: `parent_国有金融企业集中采购管理暂行规定_29_1394_2601`
   - top1: `parent_政府采购货物和服务招标投标管理办法_71_1232_1756`
   - law: `国有金融企业集中采购管理暂行规定`
   - type: `pdf_law_parent` | span: `single`

49. [procedure][synonym] 招标人如何合理划分标包？
   - expected: `parent_工程建设项目货物招标投标办法_21_229_9962`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0271`
   - law: `工程建设项目货物招标投标办法`
   - type: `pdf_law_parent` | span: `single`

50. [procedure][synonym] 招标人应当在招标文件中如何规定实质性要求和条件？
   - expected: `parent_工程建设项目施工招标投标办法_23_10_4291`
   - top1: `parent_工程建设项目货物招标投标办法_21_229_9962`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `single`

51. [condition_check][synonym] 哪些情况下投标人不得参加同一招标项目包投标？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_32_463_2329`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0382`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `single`

52. [procedure][synonym] 招标人可以对潜在投标人进行资格审查吗？
   - expected: `parent_工程建设项目货物招标投标办法_15_227_3433`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0251`
   - law: `工程建设项目货物招标投标办法`
   - type: `pdf_law_parent` | span: `single`

53. [condition_check][synonym] 政府采购货物和服务的招标投标应遵循什么规定
   - expected: `parent_中华人民共和国招标投标法实施条例_82_57_7179`
   - top1: `parent_政府采购货物和服务招标投标管理办法_4_2_9279`
   - law: `中华人民共和国招标投标法实施条例`
   - type: `pdf_law_parent` | span: `single`

54. [condition_check][direct] 招标人设有标底时，在评标中如何使用？
   - expected: `parent_工程建设项目施工招标投标办法_54_22_3648`
   - top1: `parent_水利工程建设项目招标投标管理规定_35_822_7254`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `single`

55. [condition_check][direct] 供应商在采购活动中禁止什么行为？
   - expected: `parent_中央国家机关政府采购中心货物和服务定点采_14_1352_5266`
   - top1: `parent_中华人民共和国政府采购法实施条例_19_9_2895`
   - law: `中央国家机关政府采购中心货物和服务定点采购管理办法`
   - type: `pdf_law_parent` | span: `single`

56. [condition_check][direct] 评标委员会推荐的中标候选人应当限定在多少人？
   - expected: `parent_工程建设项目施工招标投标办法_54_22_3648`
   - top1: `parent_评标委员会和评标方法暂行规定_44_152_8491`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `single`

57. [procedure][synonym] 依法必须进行招标的项目，招标人收到评标报告后何时公示中标候选人？
   - expected: `parent_工程建设项目施工招标投标办法_54_22_3648`
   - top1: `parent_中华人民共和国招标投标法实施条例_54_44_2074`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `single`

58. [responsibility][scenario] 评标委员会成员有哪些行为会被禁止参加评标？
   - expected: `parent_工程建设项目施工招标投标办法_76_31_7419`
   - top1: `parent_评标委员会和评标方法暂行规定_53_154_1711`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `single`

59. [condition_check][synonym] 在什么情况下，招标人可以终止招标？
   - expected: `parent_工程建设项目施工招标投标办法_14_176_6158`
   - top1: `parent_工程建设项目勘察设计招标投标办法_20_207_2444`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `single`

60. [condition_check][synonym] 重新评标专家不得包含哪些人员？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_31_435_8601`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0553`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `single`

61. [responsibility][synonym] 行政监督部门对电子招标投标活动有哪些监督职责？
   - expected: `parent_电子招标投标办法_46_259_1595`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0092`
   - law: `电子招标投标办法`
   - type: `pdf_law_parent` | span: `single`

62. [procedure][synonym] 投诉人投诉时应当提供哪些材料？
   - expected: `parent_机电产品国际招标评标专家及专家库管理办法_83_476_400`
   - top1: `parent_政府采购质疑和投诉办法_17_1241_5099`
   - law: `机电产品国际招标评标专家及专家库管理办法`
   - type: `pdf_law_parent` | span: `single`

63. [responsibility][synonym] 评标委员会成员在评标过程中不得有哪些行为？
   - expected: `parent_铁路工程建设项目招标投标管理办法_32_762_9770`
   - top1: `parent_政府采购货物和服务招标投标管理办法_61_24_4000`
   - law: `铁路工程建设项目招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

64. [condition_check][synonym] 评标委员会在什么情况下可以否决所有投标？
   - expected: `parent_中华人民共和国招标投标法_32_11_8897`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0647`
   - law: `中华人民共和国招标投标法`
   - type: `pdf_law_parent` | span: `cross_chunk`

65. [procedure][synonym] 评标委员会在评标过程中可以要求投标人进行哪些澄清说明？
   - expected: `parent_铁路工程建设项目招标投标管理办法_32_762_9770`
   - top1: `parent_公路工程建设项目评标工作细则_24_538_8292`
   - law: `铁路工程建设项目招标投标管理办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

66. [condition_check][synonym] 招标人对投标人的资格条件有哪些要求？
   - expected: `parent_房屋建筑和市政基础设施工程施工招标投标管_22_397_9260`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0253`
   - law: `房屋建筑和市政基础设施工程施工招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

67. [condition_check][synonym] 关于标底的规定有哪些？
   - expected: `parent_中华人民共和国招标投标法实施条例_25_33_6740`
   - top1: `parent_铁路建设工程招标投标实施办法_43_702_7498`
   - law: `中华人民共和国招标投标法实施条例`
   - type: `pdf_law_parent` | span: `single`

68. [condition_check][direct] 投标保证金的有效期应当与什么一致？
   - expected: `parent_中华人民共和国招标投标法实施条例_25_33_6740`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0454`
   - law: `中华人民共和国招标投标法实施条例`
   - type: `pdf_law_parent` | span: `single`

69. [condition_check][synonym] 招标人自行办理招标事宜需要具备什么条件？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_11_455_8051`
   - top1: `parent_房屋建筑和市政基础设施工程施工招标投标管_11_392_9716`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `single`

70. [condition_check][synonym] 哪些投标行为是被法律明确禁止的？
   - expected: `parent_标法》《中华人民共和国招标投标法实施条例_41_661_440`
   - top1: `parent_中华人民共和国招标投标法_32_11_8897`
   - law: `标法》《中华人民共和国招标投标法实施条例》等法`
   - type: `pdf_law_parent` | span: `single`

71. [condition_check][synonym] 招标人设有标底时，标底在评标中应如何使用？
   - expected: `parent_国家对潜在投标人或者投标人的资格条件有规_54_185_9797`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0600`
   - law: `国家对潜在投标人或者投标人的资格条件有规定`
   - type: `pdf_law_parent` | span: `single`

72. [procedure][synonym] 评标委员会推荐的中标候选人人数限制是多少？
   - expected: `parent_国家对潜在投标人或者投标人的资格条件有规_54_185_9797`
   - top1: `parent_评标委员会和评标方法暂行规定_44_152_8491`
   - law: `国家对潜在投标人或者投标人的资格条件有规定`
   - type: `pdf_law_parent` | span: `single`

73. [procedure][synonym] 评标报告应当包含哪些内容？
   - expected: `parent_政府采购货物和服务招标投标管理办法_56_22_3619`
   - top1: `parent_通信工程建设项目招标投标管理办法_36_895_5437`
   - law: `政府采购货物和服务招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

74. [procedure][synonym] 招标文件应当包括哪些内容？
   - expected: `parent_房屋建筑和市政基础设施工程施工招标投标管_16_394_602`
   - top1: `parent_水利工程建设项目监理招标投标管理办法_19_836_2124`
   - law: `房屋建筑和市政基础设施工程施工招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

75. [procedure][direct] 招标人收到投标文件后应当如何处理？
   - expected: `parent_工程建设项目施工招标投标办法_37_16_391`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0419`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `single`

76. [condition_check][direct] 招标人应当根据什么编制招标文件？
   - expected: `parent_房屋建筑和市政基础设施工程施工招标投标管_16_394_602`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0263`
   - law: `房屋建筑和市政基础设施工程施工招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

77. [condition_check][direct] 招标人可以在招标文件中要求投标人提交什么？
   - expected: `parent_工程建设项目施工招标投标办法_37_16_391`
   - top1: `parent_国家对潜在投标人或者投标人的资格条件有规_37_179_2747`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `single`

78. [procedure][direct] 招标人应当如何编制招标文件？
   - expected: `parent_房屋建筑和市政基础设施工程施工招标投标管_16_394_602`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0263`
   - law: `房屋建筑和市政基础设施工程施工招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

79. [procedure][direct] 资格预审不合格的投标申请人，招标人应当告知什么？
   - expected: `parent_房屋建筑和市政基础设施工程施工招标投标管_16_394_602`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0244`
   - law: `房屋建筑和市政基础设施工程施工招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

80. [condition_check][direct] 招标人应当根据什么编制招标文件？
   - expected: `parent_房屋建筑和市政基础设施工程施工招标投标管_16_394_602`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0263`
   - law: `房屋建筑和市政基础设施工程施工招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

81. [condition_check][direct] 招标人可以在招标文件中要求投标人提交什么？
   - expected: `parent_工程建设项目施工招标投标办法_37_16_391`
   - top1: `parent_国家对潜在投标人或者投标人的资格条件有规_37_179_2747`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `single`

82. [procedure][direct] 招标人应当如何编制招标文件？
   - expected: `parent_房屋建筑和市政基础设施工程施工招标投标管_16_394_602`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0263`
   - law: `房屋建筑和市政基础设施工程施工招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

83. [procedure][direct] 资格预审不合格的投标申请人，招标人应当告知什么？
   - expected: `parent_房屋建筑和市政基础设施工程施工招标投标管_16_394_602`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0244`
   - law: `房屋建筑和市政基础设施工程施工招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

84. [procedure][synonym] 评标委员会对投标文件进行初步评审的目的是什么？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_15_445_6061`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0546`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `single`

85. [condition_check][synonym] 评标专家有哪些情形需要主动回避？
   - expected: `parent_通信工程建设项目评标专家及评标专家库管理_11_906_9474`
   - top1: `parent_评标专家和评标专家库管理暂行办法_37_162_3496`
   - law: `通信工程建设项目评标专家及评标专家库管理办法`
   - type: `pdf_law_parent` | span: `single`

86. [procedure][synonym] 招标公告应当载明哪些内容？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_13_456_1994`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0219`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `single`

87. [procedure][synonym] 招标人应如何保证评标工作的保密性？
   - expected: `parent_公路工程建设项目评标工作细则_4_528_260`
   - top1: `parent_中华人民共和国招标投标法_38_13_6425`
   - law: `公路工程建设项目评标工作细则`
   - type: `pdf_law_parent` | span: `single`

88. [responsibility][synonym] 评标委员会成员有违反规定行为时，应如何处理？
   - expected: `parent_政府采购货物和服务招标投标管理办法_71_1232_1756`
   - top1: `parent_建筑工程设计招标投标管理办法_34_369_5661`
   - law: `政府采购货物和服务招标投标管理办法`
   - type: `pdf_law_parent` | span: `single`

89. [procedure][synonym] 投标人认为招标投标活动不符合规定时，应该如何投诉？
   - expected: `parent_工程建设项目施工招标投标办法_88_36_631`
   - top1: `parent_中华人民共和国招标投标法实施条例_60_47_1119`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `single`

90. [procedure][synonym] 联合体投标应当如何确定牵头人？牵头人的职责是什么？
   - expected: `parent_工程建设项目施工招标投标办法_43_18_5397`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0432`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `single`

91. [condition_check][synonym] 联合体投标在资格预审后增减、更换成员会有什么后果？
   - expected: `parent_工程建设项目施工招标投标办法_43_18_5397`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0885`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `single`

92. [condition_check][synonym] 评标或评审时，专家应如何确定？
   - expected: `parent_公共资源交易平台公共资源交易平台管理暂行_47_1472_7867_child9`
   - top1: `parent_公路建设项目评标专家库管理办法_11_578_8402`
   - law: `公共资源交易平台公共资源交易平台管理暂行办法`
   - type: `pdf_law_child` | span: `single`

93. [procedure][synonym] 电子招标投标需要遵循哪些规定
   - expected: `parent_铁路工程建设项目招标投标管理办法_59_775_2092_child0`
   - top1: `parent_电子招标投标办法_5_245_2944`
   - law: `铁路工程建设项目招标投标管理办法`
   - type: `pdf_law_child` | span: `single`

94. [condition_check][direct] 招标文件对备选方案有什么要求
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_20_458_676_child4`
   - top1: `parent_进一步规范机电产品国际招标投标活动有关规_4_425_361`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_child` | span: `single`

95. [scenario_judgment][synonym] 整合建立统一的公共资源交易平台有什么重要性？
   - expected: `parent_公共资源交易平台公共资源交易平台管理暂行_47_1472_7867_child1`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_47_1472_7867_child16`
   - law: `公共资源交易平台公共资源交易平台管理暂行办法`
   - type: `pdf_law_child` | span: `single`

96. [condition_check][synonym] 公共资源交易平台整合前存在哪些突出问题？
   - expected: `parent_公共资源交易平台公共资源交易平台管理暂行_47_1472_7867_child1`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_47_1472_7867_child16`
   - law: `公共资源交易平台公共资源交易平台管理暂行办法`
   - type: `pdf_law_child` | span: `single`

97. [procedure][synonym] 招标代理机构不得有哪些违规行为？
   - expected: `parent_机电产品国际招标评标专家及专家库管理办法_99_484_5044_child5`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0217`
   - law: `机电产品国际招标评标专家及专家库管理办法`
   - type: `pdf_law_child` | span: `single`

98. [responsibility][synonym] 哪些机关使用财政性资金购买服务时需要参照政府购买服务管理办法执行？
   - expected: `parent_政府购买服务管理办法_33_1568_1497_child0`
   - top1: `parent_政府购买服务管理办法_33_1568_1497_child6`
   - law: `政府购买服务管理办法`
   - type: `pdf_law_child` | span: `single`

99. [procedure][synonym] 政府采购资格预审公告中应包含哪些主要内容？
   - expected: `parent_《中华人民共和国政府采购法实施条例》等有_22_1573_8167_child0`
   - top1: `parent_政府采购货物和服务招标投标管理办法_15_6_7294`
   - law: `《中华人民共和国政府采购法实施条例》等有关法`
   - type: `pdf_law_child` | span: `single`

100. [procedure][synonym] 资格预审评审委员会如何处理投标人的资格预审？
   - expected: `parent_民政部工程建设项目招标投标管理办法_7_1045_547_child2`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0243`
   - law: `民政部工程建设项目招标投标管理办法`
   - type: `pdf_law_child` | span: `single`

101. [scenario_judgment][synonym] 铁路工程建设项目招标投标的基本原则是什么？
   - expected: `parent_铁路工程建设项目招标投标管理办法_59_775_2092_child2`
   - top1: `parent_铁路建设工程招标投标实施办法_4_684_4947`
   - law: `铁路工程建设项目招标投标管理办法`
   - type: `pdf_law_child` | span: `single`

102. [definition][synonym] 最低评标价法的定义是什么？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_20_458_676_child0`
   - top1: `parent_政府采购货物和服务招标投标管理办法_52_21_6029`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_child` | span: `single`

103. [responsibility][synonym] 评标委员会成员不按照招标文件规定的评标方法和标准评标会有什么处罚？
   - expected: `parent_机电产品国际招标评标专家及专家库管理办法_99_484_5044_child2`
   - top1: `parent_评标委员会和评标方法暂行规定_53_154_1711`
   - law: `机电产品国际招标评标专家及专家库管理办法`
   - type: `pdf_law_child` | span: `single`

104. [scenario_judgment][synonym] 铁路工程项目进入地方公共资源交易市场招投标的重要意义是什么？
   - expected: `parent_铁路工程建设项目招标投标管理办法_59_775_2092_child1`
   - top1: `parent_铁路工程建设项目招标投标管理办法_59_775_2092_child3`
   - law: `铁路工程建设项目招标投标管理办法`
   - type: `pdf_law_child` | span: `single`

105. [responsibility][synonym] 评标委员会成员向招标人征询确定中标人意向会受到什么处罚？
   - expected: `parent_机电产品国际招标评标专家及专家库管理办法_99_484_5044_child2`
   - top1: `parent_评标委员会和评标方法暂行规定_53_154_1711`
   - law: `机电产品国际招标评标专家及专家库管理办法`
   - type: `pdf_law_child` | span: `single`

106. [definition][direct] 上海公共资源交易平台包含哪些分平台？
   - expected: `policy_111`
   - top1: `policy_125`
   - law: `【建设工程】监理电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

107. [definition][direct] 上海公共资源交易平台建设工程招投标分平台属于哪个交易平台的一部分？
   - expected: `policy_111`
   - top1: `policy_45`
   - law: `【建设工程】监理电子招标投标应用指南`
   - type: `policy_doc` | span: `single`

108. [procedure][synonym] 本案经历了哪些审级程序？
   - expected: `pdf_建设工程施工合同纠纷案_34_7213`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0278`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `single`

109. [procedure][synonym] 招标文件补充说明的修改时限是什么？违反招标规定的行为有哪些？
   - expected: `parent_公路养护工程施工招标投标管理暂行规定_19_564_3661`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0306`
   - law: `公路养护工程施工招标投标管理暂行规定`
   - type: `pdf_law_parent` | span: `cross_chunk`

110. [procedure][synonym] 采购活动结束后，采购人需要完成哪些后续工作？同时，哪些类型的政府采购项目可以采用询价方式采购？
   - expected: `parent_交通运输部部属单位政府采购管理办法_44_1412_4260`
   - top1: `parent_中华人民共和国政府采购法_32_1070_7465`
   - law: `交通运输部部属单位政府采购管理办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

111. [condition_check][synonym] 招标文件对联合体投标和备选方案有什么规定？投标人如何处理重要条款？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_32_463_2329`
   - top1: `parent_进一步规范机电产品国际招标投标活动有关规_4_425_361`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `cross_chunk`

112. [procedure][synonym] 招标公告应当载明哪些内容？招标网在招标过程中有哪些信息发布要求？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_31_435_8601`
   - top1: `parent_招标公告和公示信息发布管理办法_5_267_7639`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `cross_chunk`

113. [procedure][synonym] 当发现招标文件重要商务或技术条款出现错误、矛盾或不一致时，主管部门会如何处理？同时，评标方法有哪些类型，各自适用于什么情况？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_31_435_8601`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0573`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `cross_chunk`

114. [condition_check][synonym] 招标人自行办理招标事宜需要具备哪些条件？同时，评标委员会在评标过程中应当遵循哪些步骤？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_11_455_8051`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0188`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `cross_chunk`

115. [procedure][synonym] 招标人如何选择招标机构，以及招标机构在发布招标公告前需要完成哪些准备工作？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_11_455_8051`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0202`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `cross_chunk`

116. [procedure][synonym] 招标机构在评标过程中应当如何处理投标文件，以及招标公告应当包含哪些内容？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_15_445_6061`
   - top1: `parent_评标委员会和评标方法暂行规定_15_142_501`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `cross_chunk`

117. [procedure][synonym] 评标委员会如何处理投标文件，以及招标文件对重要条款有什么特殊要求？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_15_445_6061`
   - top1: `parent_明确或实际投标人报名数量未达到招标公告中_30_380_7706`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `cross_chunk`

118. [procedure][synonym] 评标委员会如何进行价格评价，以及招标文件对投标人的资质有什么要求？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_15_445_6061`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0321`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `cross_chunk`

119. [procedure][synonym] 评标委员会如何对投标文件进行评分，以及招标文件对备选方案有什么规定？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_15_445_6061`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0597`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `cross_chunk`

120. [procedure][synonym] 招标公告应当载明哪些内容？招标文件对内容有哪些要求？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_13_456_1994`
   - top1: `parent_投资项目招标投标管理办法_11_916_305`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `cross_chunk`

121. [procedure][synonym] 招标公告中应当包含哪些基本信息？招标文件中对重要条款有什么特殊要求？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_13_456_1994`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0219`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `cross_chunk`

122. [procedure][synonym] 招标公告中需要包含哪些基本信息？机电产品国际招标的评标方法有哪些规定？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_13_456_1994`
   - top1: `parent_进一步规范机电产品国际招标投标活动有关规_20_458_676_child4`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `cross_chunk`

123. [procedure][synonym] 投标人在投标截止时间前可以如何处理已提交的投标文件？如果招标文件允许提供备选方案，有什么具体规定？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_38_465_1367`
   - top1: `parent_工程建设项目施工招标投标办法_39_17_9795`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_parent` | span: `cross_chunk`

124. [condition_check][direct] 招标文件内容应当符合哪些法律法规的规定？同时，招标人设有最高投标限价时应当如何处理？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_20_458_676_child4`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0603`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_child` | span: `cross_chunk`

125. [condition_check][synonym] 招标文件中关于评标方法和标准的规定有哪些具体要求？
   - expected: `parent_进一步规范机电产品国际招标投标活动有关规_20_458_676_child3`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0573`
   - law: `进一步规范机电产品国际招标投标活动有关规定`
   - type: `pdf_law_child` | span: `cross_chunk`

126. [responsibility][synonym] 采购代理机构向评标委员会作倾向性说明会有什么后果？同时，未依法从政府采购评审专家库中抽取专家又会面临什么处罚？
   - expected: `parent_中华人民共和国政府采购法实施条例_42_17_1441`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0560`
   - law: `中华人民共和国政府采购法实施条例`
   - type: `pdf_law_parent` | span: `cross_chunk`

127. [procedure][synonym] 公共资源交易平台应遵循哪些法律法规和规则，以及如何整合各类交易市场？
   - expected: `parent_公共资源交易平台公共资源交易平台管理暂行_7_1457_6263`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_47_1472_7867_child10`
   - law: `公共资源交易平台公共资源交易平台管理暂行办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

128. [scenario_judgment][synonym] 公共资源交易平台整合的背景和必要性是什么，以及平台运行应遵循哪些规则？
   - expected: `parent_公共资源交易平台公共资源交易平台管理暂行_7_1457_6263`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_47_1472_7867_child8`
   - law: `公共资源交易平台公共资源交易平台管理暂行办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

129. [scenario_judgment][synonym] 整合建立统一的公共资源交易平台的重要性和具体措施是什么？
   - expected: `parent_公共资源交易平台公共资源交易平台管理暂行_47_1472_7867_child10`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_47_1472_7867_child16`
   - law: `公共资源交易平台公共资源交易平台管理暂行办法`
   - type: `pdf_law_child` | span: `cross_chunk`

130. [scenario_judgment][synonym] 整合建立统一的公共资源交易平台的重要性和背景是什么？
   - expected: `parent_公共资源交易平台公共资源交易平台管理暂行_47_1472_7867_child9`
   - top1: `parent_公共资源交易平台公共资源交易平台管理暂行_47_1472_7867_child16`
   - law: `公共资源交易平台公共资源交易平台管理暂行办法`
   - type: `pdf_law_child` | span: `cross_chunk`

131. [procedure][synonym] 评标委员会如何编写评标报告并确定中标候选人？如果采购人未在规定时间内确定中标人，会有什么后果？
   - expected: `parent_政府采购货物和服务招标投标管理办法_56_22_3619`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0654`
   - law: `政府采购货物和服务招标投标管理办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

132. [procedure][synonym] 评标报告应当包含哪些内容？如果评标委员会成员对评标报告有不同意见应该如何处理？
   - expected: `parent_政府采购货物和服务招标投标管理办法_56_22_3619`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0653`
   - law: `政府采购货物和服务招标投标管理办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

133. [responsibility][synonym] 评标委员会成员违反评标纪律会有什么后果？采购人在评标过程中未在规定时间内确定中标人将面临什么处罚？
   - expected: `parent_政府采购货物和服务招标投标管理办法_77_1230_9691`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0562`
   - law: `政府采购货物和服务招标投标管理办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

134. [responsibility][synonym] 采购人违反政府采购招标投标管理办法会有什么处罚？评标委员会成员在评标过程中擅离职守会有什么后果？
   - expected: `parent_政府采购货物和服务招标投标管理办法_77_1230_9691`
   - top1: `parent_政府采购货物和服务招标投标管理办法_71_1232_1756`
   - law: `政府采购货物和服务招标投标管理办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

135. [procedure][synonym] 开标过程中发现评标委员会成员有需要回避的情形，应如何处理？
   - expected: `parent_政府采购货物和服务招标投标管理办法_39_16_643`
   - top1: `parent_公路工程建设项目评标工作细则_33_535_3041`
   - law: `政府采购货物和服务招标投标管理办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

136. [responsibility][synonym] 评标委员会成员在评标过程中擅离职守，且私下接触投标人，应承担什么责任？
   - expected: `parent_政府采购货物和服务招标投标管理办法_39_16_643`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0560`
   - law: `政府采购货物和服务招标投标管理办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

137. [responsibility][synonym] 评标委员会成员私下接触投标人并接受与投标文件不一致的澄清，应承担什么责任？
   - expected: `parent_政府采购货物和服务招标投标管理办法_61_1223_5706`
   - top1: `parent_工程建设项目施工招标投标办法_76_31_7419`
   - law: `政府采购货物和服务招标投标管理办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

138. [announcement_interpretation][direct] 水利工程建设项目招标投标审计办法的执行时间和解释权归属是什么？
   - expected: `parent_水利工程建设项目招标投标审计办法_7_874_8025`
   - top1: `parent_水利工程建设项目招标投标审计办法_20_880_2122_child0`
   - law: `水利工程建设项目招标投标审计办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

139. [procedure][synonym] 水利工程建设项目招标投标审计办法中关于招标投标行为规范的具体要求
   - expected: `parent_水利工程建设项目招标投标审计办法_20_880_2122_child6`
   - top1: `parent_水利工程建设项目招标投标审计办法_7_874_8025`
   - law: `水利工程建设项目招标投标审计办法`
   - type: `pdf_law_child` | span: `cross_chunk`

140. [procedure][synonym] 水利工程建设项目招标投标审计办法中关于招标投标方面的审计重点
   - expected: `parent_水利工程建设项目招标投标审计办法_20_880_2122_child0`
   - top1: `parent_水利工程建设项目招标投标审计办法_7_874_8025`
   - law: `水利工程建设项目招标投标审计办法`
   - type: `pdf_law_child` | span: `cross_chunk`

141. [procedure][synonym] 评标过程中，评标委员会发现投标人以他人的名义投标、串通投标、以行贿手段谋取中标或者以其他弄虚作假方式投标的，应当如何处理？如果投标人的报价明显低于其他投标报价或者在设有标底时明显低于标底，使得其投标报
   - expected: `parent_监督处理中华人民共和国行政处罚法_25_289_464`
   - top1: `parent_评标委员会和评标方法暂行规定_20_144_777`
   - law: `监督处理中华人民共和国行政处罚法`
   - type: `pdf_law_parent` | span: `cross_chunk`

142. [responsibility][synonym] 承接主体在政府购买服务项目实施过程中应当履行哪些义务，以及事业单位政府购买服务改革的总体目标是什么？
   - expected: `parent_政府购买服务管理办法_26_1566_4159`
   - top1: `parent_政府购买服务管理办法_33_1568_1497_child6`
   - law: `政府购买服务管理办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

143. [procedure][synonym] 事业单位政府购买服务改革的总体目标是什么，以及这项改革工作的实施方案需要何时提交备案？
   - expected: `parent_政府购买服务管理办法_33_1568_1497_child3`
   - top1: `parent_政府购买服务管理办法_33_1568_1497_child13`
   - law: `政府购买服务管理办法`
   - type: `pdf_law_child` | span: `cross_chunk`

144. [condition_check][synonym] 哪些事业单位可以作为政府购买服务的购买主体，承接主体在提供服务时有什么限制？
   - expected: `parent_政府购买服务管理办法_26_1566_4159`
   - top1: `parent_政府购买服务管理办法_5_1560_5404`
   - law: `政府购买服务管理办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

145. [scenario_judgment][synonym] 事业单位政府购买服务改革的指导思想是什么？
   - expected: `parent_政府购买服务管理办法_33_1568_1497_child1`
   - top1: `parent_政府购买服务管理办法_33_1568_1497_child6`
   - law: `政府购买服务管理办法`
   - type: `pdf_law_child` | span: `cross_chunk`

146. [condition_check][synonym] 不同类型的事业单位在政府购买服务中分别扮演什么角色？
   - expected: `parent_政府购买服务管理办法_33_1568_1497_child4`
   - top1: `parent_政府购买服务管理办法_33_1568_1497_child6`
   - law: `政府购买服务管理办法`
   - type: `pdf_law_child` | span: `cross_chunk`

147. [procedure][synonym] 政府采购信息发布有哪些规定，以及政府采购资格预审公告应包含哪些内容？
   - expected: `parent_《中华人民共和国政府采购法实施条例》等有_15_1572_581`
   - top1: `parent_政府采购货物和服务招标投标管理办法_15_1205_7147`
   - law: `《中华人民共和国政府采购法实施条例》等有关法`
   - type: `pdf_law_parent` | span: `cross_chunk`

148. [procedure][synonym] 政府采购信息发布有哪些规定，以及采购需求和采购实施计划的管理要求是什么？
   - expected: `parent_《中华人民共和国政府采购法实施条例》等有_15_1572_581`
   - top1: `parent_《中华人民共和国政府采购法实施条例》等有_2_1569_9196`
   - law: `《中华人民共和国政府采购法实施条例》等有关法`
   - type: `pdf_law_parent` | span: `cross_chunk`

149. [procedure][synonym] 资格预审适用于什么情况，以及对于潜在投标人在阅读招标文件时提出的疑问，招标人应如何处理？
   - expected: `parent_工程建设项目货物招标投标办法_15_227_3433`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0232`
   - law: `工程建设项目货物招标投标办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

150. [procedure][synonym] 招标文件中应当包含哪些内容？评标委员会如何确定中标人？
   - expected: `parent_工程建设项目施工招标投标办法_23_10_4291`
   - top1: `parent_中华人民共和国招标投标法_38_13_6425`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

151. [procedure][synonym] 招标文件应当包含哪些实质性要求和条件？招标人如何确保这些要求被投标人充分理解？
   - expected: `parent_工程建设项目施工招标投标办法_23_10_4291`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0263`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

152. [procedure][synonym] 招标文件应当包含哪些内容？对招标投标活动有异议时如何投诉？
   - expected: `parent_工程建设项目施工招标投标办法_23_10_4291`
   - top1: `parent_设计施工总承包招标的评标采用综合评分法_63_521_8535`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

153. [case_reasoning][synonym] 招标文件应当包含哪些内容？招标人与投标人进行实质性内容谈判会有什么法律后果？
   - expected: `parent_工程建设项目施工招标投标办法_23_10_4291`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0704`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

154. [procedure][synonym] 招标文件应当包含哪些内容？投标保证金有哪些要求和限制？
   - expected: `parent_工程建设项目施工招标投标办法_23_10_4291`
   - top1: `parent_工程建设项目货物招标投标办法_26_231_7260`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

155. [condition_check][synonym] 哪些情况下投标无效？评标委员会成员有哪些行为会被禁止担任评标工作？
   - expected: `parent_工程建设项目施工招标投标办法_35_15_4605`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0858`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

156. [procedure][synonym] 评标委员会完成评标后应向招标人提交什么文件？如果招标投标活动不符合国家规定，投标人或者其他利害关系人可以采取什么措施？
   - expected: `parent_工程建设项目施工招标投标办法_54_22_3648`
   - top1: `parent_中华人民共和国招标投标法实施条例_52_43_9726`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

157. [procedure][synonym] 评标委员会成员不公正履行职责会受到什么处罚？如果发现招标投标活动不符合规定，应该如何投诉？
   - expected: `parent_工程建设项目施工招标投标办法_76_31_7419`
   - top1: `parent_评标委员会和评标方法暂行规定_53_154_1711`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

158. [procedure][synonym] 评标委员会成员收受投标人财物会有什么处罚？投标保证金有什么规定？
   - expected: `parent_工程建设项目施工招标投标办法_76_31_7419`
   - top1: `parent_评标委员会应组织全体评标委员学习有关规定_71_712_9976`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

159. [procedure][synonym] 投标人提交投标保证金的方式有哪些？金额限制是多少？联合体投标时应当以谁的名义提交投标保证金？
   - expected: `parent_工程建设项目施工招标投标办法_37_16_391`
   - top1: `parent_进一步规范机电产品国际招标投标活动有关规_22_459_6846`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

160. [procedure][synonym] 招标文件售出后是否可以退还？如果发现招标投标活动不符合规定，应该如何投诉？
   - expected: `parent_工程建设项目施工招标投标办法_14_176_6158`
   - top1: `parent_工程建设项目施工招标投标办法_14_6_8122`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

161. [procedure][synonym] 投标人提交投标保证金有哪些要求？联合体投标时提交投标保证金有什么特殊规定？
   - expected: `parent_工程建设项目施工招标投标办法_37_16_391`
   - top1: `parent_进一步规范机电产品国际招标投标活动有关规_22_459_6846`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

162. [procedure][synonym] 采购人在验收供应商履约时有哪些具体要求？
   - expected: `parent_政府采购非招标采购方式管理办法_22_1502_7260`
   - top1: `parent_中央国家机关政府采购电子卖场管理办法_21_1301_9856`
   - law: `政府采购非招标采购方式管理办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

163. [condition_check][synonym] 政府采购货物和服务的招标投标活动应遵循什么特别规定？
   - expected: `parent_中华人民共和国招标投标法实施条例_82_57_7179`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0027`
   - law: `中华人民共和国招标投标法实施条例`
   - type: `pdf_law_parent` | span: `cross_chunk`

164. [procedure][synonym] 招标代理机构在代理招标业务时，如果发现有投标人串通投标，应当如何处理？
   - expected: `parent_中华人民共和国招标投标法实施条例_11_29_2401`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0482`
   - law: `中华人民共和国招标投标法实施条例`
   - type: `pdf_law_parent` | span: `cross_chunk`

165. [procedure][synonym] 评标委员会的专家成员如何确定？有哪些规定？
   - expected: `parent_中华人民共和国招标投标法实施条例_44_40_4303`
   - top1: `parent_评标委员会和评标方法暂行规定_7_139_1404`
   - law: `中华人民共和国招标投标法实施条例`
   - type: `pdf_law_parent` | span: `cross_chunk`

166. [procedure][synonym] 在招标投标过程中，如果投标人串通投标，招标人应当如何处理？
   - expected: `parent_中华人民共和国招标投标法实施条例_44_40_4303`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0482`
   - law: `中华人民共和国招标投标法实施条例`
   - type: `pdf_law_parent` | span: `cross_chunk`

167. [procedure][synonym] 招标代理机构在代理招标业务时，如果发现投标人以行贿谋取中标，应当如何处理？
   - expected: `parent_中华人民共和国招标投标法实施条例_53_51_6303`
   - top1: `parent_中华人民共和国招标投标法实施条例_65_50_4352`
   - law: `中华人民共和国招标投标法实施条例`
   - type: `pdf_law_parent` | span: `cross_chunk`

168. [procedure][synonym] 招标人在招标文件中要求投标人提交投标保证金时，如果发现投标人串通投标，保证金将如何处理？
   - expected: `parent_中华人民共和国招标投标法实施条例_53_51_6303`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0445`
   - law: `中华人民共和国招标投标法实施条例`
   - type: `pdf_law_parent` | span: `cross_chunk`

169. [procedure][synonym] 在依法必须进行招标的项目中，如果投标人串通投标，招标代理机构应当如何处理？
   - expected: `parent_中华人民共和国招标投标法实施条例_53_51_6303`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0482`
   - law: `中华人民共和国招标投标法实施条例`
   - type: `pdf_law_parent` | span: `cross_chunk`

170. [procedure][synonym] 成为评标专家需要满足哪些基本条件，同时评标专家有哪些义务？
   - expected: `parent_系统工程综合评标专家库管理办法_12_680_7250`
   - top1: `parent_铁路建设工程评标专家库及评标专家管理办法_5_732_3944`
   - law: `系统工程综合评标专家库管理办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

171. [procedure][synonym] 招标人在什么情况下可以终止招标？终止招标后应如何处理已收取的费用和保证金？如果评标委员会认为投标人的报价明显低于其他投标报价，应如何处理？
   - expected: `parent_铁路工程建设项目招标投标管理办法_19_757_2288`
   - top1: `parent_标法》《中华人民共和国招标投标法实施条例_32_656_4034`
   - law: `铁路工程建设项目招标投标管理办法`
   - type: `pdf_law_parent` | span: `cross_chunk`

172. [procedure][synonym] 电子招标投标公共服务平台如何支持评标结果公示，与招标投标法律解读中对中标候选人排序的要求有何关联？
   - expected: `parent_电子招标投标办法_43_257_4773`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0656`
   - law: `电子招标投标办法`
   - type: `pdf_law_parent` | span: `cross_doc`

173. [procedure][synonym] 在电子招标投标公共服务平台上发现串通投标行为后，应该如何处理？
   - expected: `parent_电子招标投标办法_43_257_4773`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0482`
   - law: `电子招标投标办法`
   - type: `pdf_law_parent` | span: `cross_doc`

174. [case_reasoning][synonym] 在电子招标投标公共服务平台上发现串通竞买行为时，应如何认定和处理？
   - expected: `parent_电子招标投标办法_43_257_4773`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0482`
   - law: `电子招标投标办法`
   - type: `pdf_law_parent` | span: `cross_doc`

175. [procedure][synonym] 电子招标投标公共服务平台应如何处理供应商资格预审问题？
   - expected: `parent_电子招标投标办法_43_257_4773`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0094`
   - law: `电子招标投标办法`
   - type: `pdf_law_parent` | span: `cross_doc`

176. [procedure][synonym] 在电子招标投标公共服务平台上发现评标委员会组成不符合规定时，应如何处理？
   - expected: `parent_电子招标投标办法_43_257_4773`
   - top1: `parent_政府采购货物和服务招标投标管理办法_49_20_3828`
   - law: `电子招标投标办法`
   - type: `pdf_law_parent` | span: `cross_doc`

177. [case_reasoning][synonym] 在电子招标投标公共服务平台上发现串通投标行为导致评标结果不公时，应如何处理？
   - expected: `parent_电子招标投标办法_43_257_4773`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0482`
   - law: `电子招标投标办法`
   - type: `pdf_law_parent` | span: `cross_doc`

178. [procedure][synonym] 资格审查贯穿于招标投标整个过程，在推荐中标候选人时发现个别投标人资格不符合要求应如何处理？采购人应在多长时间内确定中标人？
   - expected: `parent_中华人民共和国政府采购法实施条例_21_10_6131`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0655`
   - law: `中华人民共和国政府采购法实施条例`
   - type: `pdf_law_parent` | span: `cross_doc`

179. [case_reasoning][synonym] 在建设工程施工合同纠纷中，如果承包范围存在争议，法院如何认定已完成工程的比例？如果招标文件中对实质性要求和条件未明确标明，可能导致什么后果？
   - expected: `parent_工程建设项目施工招标投标办法_23_10_4291`
   - top1: `pdf_建设工程施工合同纠纷案_10_4916`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `cross_doc`

180. [case_reasoning][synonym] 在招投标活动中，如何认定串通投标行为？招标文件中应当如何规定评标标准和方法，以防止串通投标？
   - expected: `parent_工程建设项目施工招标投标办法_23_10_4291`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0475`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `cross_doc`

181. [case_reasoning][synonym] 在建设工程施工合同纠纷中，承包人如何主张工程款和履约保证金？招标文件中应当包含哪些实质性内容，以避免后续合同纠纷？
   - expected: `parent_工程建设项目施工招标投标办法_23_10_4291`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0713`
   - law: `工程建设项目施工招标投标办法`
   - type: `pdf_law_parent` | span: `cross_doc`

182. [case_reasoning][synonym] 在招投标过程中，如果投标人的联系人同时是竞争对手公司的发起人，这种行为是否构成串通投标？法院如何认定？
   - expected: `pdf_建设工程施工合同纠纷案_11_4184`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0836`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `cross_doc`

183. [procedure][synonym] 在建设工程施工合同纠纷中，如果承包人完成的工程部分比例不同，应如何计算工程款？法院如何确定最终应付工程款金额？
   - expected: `pdf_建设工程施工合同纠纷案_11_4184`
   - top1: `pdf_建设工程施工合同纠纷案_27_5942`
   - law: `建设工程施工合同纠纷案`
   - type: `pdf_case_sliding` | span: `cross_doc`

184. [case_reasoning][synonym] 在招投标过程中，如何认定串通投标行为？请结合案例说明。
   - expected: `pdf_运输服务公司串通投标不正当竞争纠纷案_10_4535`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0485`
   - law: `运输服务公司串通投标不正当竞争纠纷案`
   - type: `pdf_case_sliding` | span: `cross_doc`

185. [case_reasoning][synonym] 串通投标行为在法律上可能面临哪些刑事处罚？
   - expected: `pdf_串通投标、受贿案_1_8873`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0835`
   - law: `串通投标、受贿案`
   - type: `pdf_case_sliding` | span: `cross_doc`

186. [case_reasoning][synonym] 招投标活动中，评标人员与投标人之间存在利益输送关系时，如何认定其行为的违法性？
   - expected: `pdf_串通投标、受贿案_1_8873`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0842`
   - law: `串通投标、受贿案`
   - type: `pdf_case_sliding` | span: `cross_doc`

187. [condition_check][synonym] 招标文件不得包含哪些内容？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0263`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0286`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

188. [condition_check][synonym] 招标人以不合理条件限制、排斥潜在投标人的情形有哪些？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0263`
   - top1: `parent_公路工程建设项目招标投标管理办法_20_508_5529`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

189. [responsibility][synonym] 招标代理机构在招标过程中的主要职责是什么？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0205`
   - top1: `parent_及教学资源招标采购管理办法_7_1038_3997`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

190. [condition_check][synonym] 招标文件编制应避免哪些问题？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0263`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0290`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

191. [condition_check][synonym] 招标文件中不得设置哪些不合理条件？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0263`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0275`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

192. [responsibility][synonym] 中标人将中标项目转让给他人会有什么法律后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0748`
   - top1: `parent_国家对潜在投标人或者投标人的资格条件有规_81_196_8593`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

193. [procedure][synonym] 在涉密工程项目招标中，如果有效投标人不足3家，招标人可以采取什么措施？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0133`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0467`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

194. [procedure][synonym] 招标后合同签订有哪些特殊要求？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0703`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0708`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

195. [procedure][synonym] 制定评标标准时应遵循哪些原则？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0344`
   - top1: `parent_铁路建设工程招标投标实施办法_41_701_3383`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

196. [procedure][synonym] 依法必须招标项目的中标结果公示应当载明哪些内容？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0691`
   - top1: `parent_招标公告和公示信息发布管理办法_5_267_7639`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

197. [procedure][synonym] 评标委员会完成评标后，应当向招标人提交什么内容？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0654`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0653`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

198. [definition][synonym] 根据《政府采购法》，工程是指什么？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0056`
   - top1: `parent_中华人民共和国政府采购法_1_1061_3104`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

199. [condition_check][synonym] 投标人伪造资格证明文件的原因是什么？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0496`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0506`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

200. [condition_check][synonym] 政府采购项目对投标人有哪些基本要求？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0048`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0380`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

201. [scenario_judgment][synonym] 在招标过程中，如果投标人的资质不符合招标文件要求，应当如何处理？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0048`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0050`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

202. [procedure][synonym] 在招标投标活动中，投诉人需要提供哪些证明材料？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0808`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0806`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

203. [procedure][synonym] 在政府采购项目中，如何确定评审专家？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0549`
   - top1: `parent_交通运输部部属单位政府采购管理办法_6_1398_7574`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

204. [scenario_judgment][synonym] 在招标过程中，如果招标人发现投标人资格条件不合格，应当如何处理？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0048`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0050`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

205. [procedure][synonym] 招标人核实异议后必须采取什么措施？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0375`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0373`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

206. [condition_check][synonym] 根据《招标投标法》，招标文件要求中标人提交履约保证金的，中标人应该如何做？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0729`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0726`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

207. [procedure][synonym] 投标人在投标截止时间前撤回投标文件后，招标人应当在多长时间内退还投标保证金？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0456`
   - top1: `parent_标法》《中华人民共和国招标投标法实施条例_39_660_7638`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

208. [condition_check][direct] 投标人未按照招标文件要求提交投标保证金，投标是否有效？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0887`
   - top1: `parent_集中采购机构是设区的市级以上人民政府依法_33_1097_133`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

209. [scenario_judgment][synonym] 评标过程中发现投标人存在恶意串通行为，评标委员会应如何处理？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0887`
   - top1: `parent_政府采购货物和服务招标投标管理办法_35_14_920`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

210. [condition_check][synonym] 评标委员会在评标过程中应遵循什么原则？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0151`
   - top1: `parent_明确或实际投标人报名数量未达到招标公告中_28_379_133`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

211. [condition_check][direct] 投诉书的投诉请求应满足什么条件？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0788`
   - top1: `parent_政府采购质疑和投诉办法_19_1242_6204`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

212. [scenario_judgment][synonym] 串通投标会导致什么后果？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0887`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0480`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

213. [scenario_judgment][synonym] 投标人弄虚作假投标，会有什么处罚？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0887`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0502`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

214. [condition_check][synonym] 评标过程中，评标委员会应如何对待所有投标人的投标文件？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0151`
   - top1: `parent_公路工程建设项目评标工作细则_24_538_8292`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

215. [definition][synonym] 招标无效的法律后果是什么？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0879`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0852`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

216. [condition_check][synonym] 招标无效的认定标准是什么？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0879`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0858`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

217. [condition_check][synonym] 在招标文件中设置投标业绩条件时，如何避免被认定为对潜在投标人的不合理限制？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0284`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0278`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `cross_chunk`

218. [procedure][synonym] 投标人编制投标文件时应注意哪些事项？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0399`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0404`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

219. [condition_check][synonym] 在不同媒介发布的同一招标项目的公告内容应当如何处理？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0221`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0226`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

220. [condition_check][synonym] 联合体投标在资格预审方面有哪些规定？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0437`
   - top1: `parent_国家对潜在投标人或者投标人的资格条件有规_43_181_6908`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

221. [responsibility][synonym] 招标人未按法律规定组织招标活动可能面临哪些处罚？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0183`
   - top1: `parent_中华人民共和国招标投标法实施条例_63_49_7406`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

222. [definition][synonym] 招标无效的法律后果是什么？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0848`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0852`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

223. [procedure][synonym] 招标人在招标过程中必须遵守哪些法定义务？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0045`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0205`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

224. [definition][synonym] 在招标投标活动中，哪些行为被视为串通投标？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0476`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0836`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`

225. [condition_check][synonym] 在招标投标活动中，招标人违反哪些法定义务会导致合同无效？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0045`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0856`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `cross_chunk`

226. [procedure][synonym] 根据《招标投标法实施条例》，投诉的期限是如何规定的？
   - expected: `pdf_招标投标法律解读与风险防范实务_struct_0804`
   - top1: `pdf_招标投标法律解读与风险防范实务_struct_0782`
   - law: `招标投标法律解读与风险防范实务`
   - type: `pdf_case_structured` | span: `single`
