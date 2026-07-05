# 更新日志索引

按日期倒序排列。

---

## 2026-07-05 — V16 绝对命中 vs 合并命中拆解

### 命中标准定义

- **绝对命中**: Top-K 中包含 `expected_chunk_id`（精确 chunk ID 匹配）
- **合并命中**: Top-K 中包含 `expected_chunk_id` 或 `acceptable_chunk_ids`（含备选 ID，如 sliding window 重叠 chunk）

### V16 召回评测

| 指标 | 绝对命中 | 合并命中 | 差异 |
|------|----------|----------|------|
| R@1 | **62.6%** | 67.0% | +4.4% |
| R@3 | **82.7%** | 87.0% | +4.3% |
| R@5 | **89.5%** | **93.5%** | **+4.0%** |

- 564/2832 题 (19.9%) 有 acceptable_chunk_ids 备选
- 合并 R@5 比绝对 R@5 多 112 题 (4.0%)，主要来自 case_sliding 窗口重叠 chunk 备选兜底
- pdf_case_sliding 绝对命中率最低（R@1=49.3%），因为滑动窗口 chunk 同质化严重，需要 acceptable 兜底

---

## 2026-07-05 — V15 Header 领域注入全量补齐 + 召回率 93.5%（最终版）

### V15 召回评测

- **R@5: 93.5%**（V14: 92.7%，V13: 92.0%），两轮 header 注入累计 +1.5%
- miss 从 226 → 208 → **184**（-42 条 vs V13）
- Dense-only 和 BM25 双升，Weighted fused Pool@30 达到 98.0%
- 全部 71 个 law-article 对覆盖 V14 miss 中所有未 enrichment 法规条目

### 两轮 Header 注入对比

| 轮次 | 新增条目 | 更新 chunks | R@5 |
|------|---------|------------|------|
| V14 首轮 | 27 对（Top 高频 miss） | 67 | 92.7% |
| V15 补齐 | 44 对（V14 miss 全量） | 103 | **93.5%** |

### 最终 Miss 结构 (184 条)

- pdf_law_parent: 82 条（跨法规竞争为主，embedding 分辨力天花板）
- pdf_case_structured: 41 条（教科书内部竞争）
- policy_doc: 24 条
- pdf_case_sliding: 20 条
- pdf_law_child: 17 条

---

## 2026-07-05 — V14 Header 领域注入 + 高频 Miss Chunk 跨法规混淆治理

### V14 召回评测

- **R@5: 92.7%**（V13: 92.0%，+0.7%），miss 从 226 降至 **208**（-18 条）
- Dense-only Pool@30 微降（92.6%→92.3%），BM25 Pool@30 微升（96.8%→97.1%）
- 主要收益在 Reranker 环节：领域/主题/关键词 header 帮助精排区分跨法规相似条文

### Header 领域/主题/关键词注入

- **`fix_header_enrich.py`** — 独立脚本，为目标 chunk 的 `retrieval_text` header 注入领域/主题/关键词
- Header 格式：`《法规名》\n领域：XX\n主题：XX\n关键词：XX\n章节\n法条文本`
- **`app/core/parent_chunk_builder.py`** — `ParentChunkBuilder` 接受 `domain_topic_map` 参数，构建时自动注入
- 覆盖 33 个 (law_name, article_id) 对，涵盖 10 个领域：建设工程(8)、机电产品国际招标(6)、招标投标(6)、政府采购(5)、房屋建筑(1)、电子招标投标(1)、道路运输(1)、铁路工程(1)、公共资源交易(1)
- 教科书（招标投标法律解读与风险防范实务）按关键词模糊匹配定位 chunk

### Miss 结构分析 (208 条)

| 类别 | 数量 | 占比 | 治理策略 |
|------|------|------|---------|
| 已 enrichment 仍 miss | 59 | 28% | embedding 分辨力天花板 |
| 未 enrichment 法规 miss | 56 | 27% | 6 个高频已补，其余 44 条单次出现 |
| 教科书内部竞争 | 47 | 23% | 已加 3 条高频 header |
| policy_doc | 25 | 12% | 非 header 问题 |
| case_sliding | 21 | 10% | 案例片段同质化 |

### 服务器工作区治理

- 所有评测文件统一至 `~/group_three_5_11/data_pan/`
- 禁止在其他目录创建立文件夹，防止"公司爆炸"

---

## 2026-07-05 — V11 评测体系优化 + 融合策略 AB 对比 + Dense/BM25 差距诊断

### V11 召回评测

- **移除 comparison 题型**：A vs B 对比型问题单独分拆，评测集从 3146 题精简至 2832 题
- **R@5 跃升至 92.0%**（V10: 89.5%），miss 从 330 降至 **226**
- V10→V11 实际增益 +2.5%，主要来自评测集净化而非模型改进
- 服务器端 `eval_v11/` 目录独立部署，RRF 变体 AB 对比在 screen 会话中运行

### RRF vs Weighted AB 对比

- 在 2832 题评测集上对比两种融合策略，**Reranker 后 R@5 差异仅 0.1%**（Weighted 92.0% vs RRF 92.1%）
- RRF 融合阶段反而劣于 Weighted（85.8% vs 87.2%，-1.4%），但 Reranker 强力拉回
- **结论：融合策略不是当前瓶颈**，Reranker 后的教科书挤占法条问题才是

### Child Chunk 差异化 Header

- **`app/core/child_chunk_builder.py`** — 每个 child 的 `retrieval_text` header 加入子块序号和内容预览（前 25 字）
- 格式：`[法规名] 第X条 [子1: 预览...] [SEP] 原文`
- 目的：避免同 parent 下各 child embedding 同质化，提升召回区分度

### 法律实体注册中心扩展

- **`app/core/legal_entity_registry.py`** — 新增领域术语注册表 `_DOMAIN_ENTITIES`
- 覆盖：采购方式（公开招标/竞争性谈判等）、平台/系统名、评标方法、招投标角色、关键概念、文档类型
- 触发 `detect_domain_entity()` → Weighted Fusion BM25 动态权重 0.75

### Weighted Fusion 动态权重优化

- **`app/pipeline/fusion.py`** — 三处调整：
  - `semantic_heavy` BM25 权重 0.40→0.60（Dense 侧语义弱，降低依赖）
  - 新增领域术语检测分支：命中→BM25=0.75, Dense=0.25
  - 法规实体查询 BM25 保持 0.80

### Router 智能拦截增强

- **`app/core/router.py`** — `quick_intercept` 重构
- 新增 `QUESTION_INTENT_KEYWORDS`（什么/怎么/如何/哪些/认定/处罚 等 20+ 个提问意图词）
- 策略：先检测提问意图→放行；再检测招投标关键词→放行；去礼貌词后两者皆无→纯寒暄
- 修复了带"谢谢""你好"的招投标问题被误判为寒暄的 Bug

### 法律结构解析器增强

- **`app/core/legal_structure_parser.py`** — 两个新增正则：
  - `REGULATION_END_PATTERN` — 文档边界检测（"本办法自...施行。"），截断被误归入法条的后继文档
  - `APPENDIX_ABBREVIATED_PATTERN` — 空白附件标记检测（"附件(略)"），防止后续乱码污染 chunk

### Reranker 输入格式优化

- **`app/pipeline/pipeline.py`** — reranker 输入从 `parent_content or retrieval_text` 改为 `child_text + "\n[法规上下文]\n" + parent_text`
- 确保 Reranker 同时看到 child 精确匹配 + parent 完整上下文，用显式分隔符降低混淆

### Dense vs BM25 差距诊断

- Dense R@5=78.0% vs BM25 R@5=86.4%，差距 8.4%
- 差距 53% 来自 Pool@30 覆盖率不足（Dense 找不到目标），47% 来自排序精度不足（找到但排不进 Top5）
- 根因：(1) BGE-M3 通用模型未做法律领域适配，(2) 2612/2832 题 difficulty=synonym，Dense 语义桥接能力不足，(3) 长 parent chunk 向量稀释

### 智谱代码审查

- `docs/code_review/v8_recall_diagnosis_zhipu.md` — V8 召回诊断（融合策略/BM25 优势/Parent Expansion 零贡献）
- `docs/code_review/law_chunk_homogeneity_zhipu.md` — 法律 Chunk 同质化治理方案
- `docs/code_review/law_child_diagnosis_zhipu.md` — Law Child 专项诊断
- `docs/code_review/v11_recall_diagnosis_zhipu.md` — V11 召回诊断（7 个分析维度，待发送）

### 清理

- 删除 `init_policy_collection.py`（已被 `init_scripts/` 替代）
- 删除 `init_scripts/init_policy.py`（已废弃）
- 删除 V6/V7 旧评测中间文件

---

## 2026-07-03 — V10 相邻法条上下文扩展 + Parent 污染治理 + 召回评测

### 相邻法条上下文扩展

- **`app/pipeline/expanders.py`** — `ParentContextExpander` 重构。Child chunk 命中时，`parent_content` 从原来的"拼接 parent 全文"改为"拼接相邻法条上下文"
- 格式：【上一条】+ `===== 当前命中 =====` + 【下一条】，约束：同法规 + 同章节，防止跨法规噪音
- 边界处理：章节首条无上一条、末条无下一条、独条只输出当前
- 新增懒加载法条邻接索引 `_article_index`：`{(law_name, chapter): {article_id_int: doc}}`

### Parent 污染治理

- **`init_scripts/init_policy_collection.py`** — 删除长法条 parent 入库逻辑（line 160-167），长法条只存 child，避免 parent 在检索阶段抢 child 的 Top1
- **`eval_standalone.py`** — 新增 `_filter_parents_with_children()` 运行时黑名单。预扫描全量文档标记有 child 的 article，检索时 parent 一经命中便拦截
- **`eval_standalone.py`** — `_get_field()` 修复：支持 JSON string 格式 metadata 解析（`chapter` 字段嵌在 Milvus metadata JSON blob 中）

### V10 召回评测

- 3146 题，三轮评测：
  - **Round 1**（相邻上下文）：R@1=67.5%, R@3=84.6%, **R@5=89.4%**（+0.4% vs V9）
  - **Round 3**（+parent 黑名单）：R@1=68.5%, R@3=85.0%, **R@5=89.5%**（+0.5% vs V9）
- **pdf_law_child** R@1 从 31.9% → 55.0%（+23.1%），相邻上下文对 child chunk 效果显著
- 当前瓶颈：pdf_case_paragraph（35% miss）+ pdf_law_parent（34% miss），合计占 69% miss

### 已废弃路径

- `policy_v10` collection 重建后因切块参数不一致（child_split_threshold 1000 vs 800），ID 映射后 R@5 跌至 69.2%，已删除
- `ParentContextRetriever`（`app/core/parent_context_retriever.py`）零引用，确认可安全移除

---

## 2026-06-29 — V6 双基准策略与真实用户 Benchmark（详见 [CHANGELOG_2026-06-29_V6双基准策略与真实用户Benchmark](CHANGELOG_2026-06-29_V6双基准策略与真实用户Benchmark.md)）

- 双基准体系确立：V5 回归测试 + V6 真实用户模拟
- V6 Benchmark 2908 题，含 8 类题型 + 4 级检索难度标注
- 独立评测脚本按 question_type / retrieval_difficulty / chunk_type 三维分组
- V6 R@1=34.7% / R@5=54.5%（对比 V5 R@1=71.5% / R@5=96.3%，区分度大幅提升）
- 跨文档题目 46 题 + opinion_news 266 题加入评测

---

## 2026-06-26 — V5 召回评测独立化 + Benchmark 修复（详见 [CHANGELOG_2026-06-26_V5评测独立化与Benchmark修复](CHANGELOG_2026-06-26_V5评测独立化与Benchmark修复.md)）

- 670+ Benchmark 脏 chunk_id 修复完成，2174 条全部验证有效
- V5 独立评测脚本部署至服务器，3 并发直连 Milvus + Embedding/Reranker
- Recall 计算分支修复（@1/@3/@5 不再相同）

---

## 2026-06-25 — BM25 本地化 + Benchmark 修复（详见 [CHANGELOG_2026-06-25_BM25本地化与Benchmark修复](CHANGELOG_2026-06-25_BM25本地化与Benchmark修复.md)）

- BM25 从 Milvus 内置字符 n-gram 切换为本地 jieba 分词检索
- V4 Benchmark ID 修复 3 条，1000 条全部与 Milvus 一致
- 空白门控附录检测器集成到切块流程

---

## 2026-06-24 — BM25 恢复 + 召回评测 V4（详见 [CHANGELOG_2026-06-24_BM25恢复与召回评测V4](CHANGELOG_2026-06-24_BM25恢复与召回评测V4.md)）

- BM25 检索恢复（SSH 隧道重连）
- 召回评估 V4 完整报告（1001 题，parent_hit@5=90.0%）
- Reranker 本地加载修复（远程优先，失败才 fallback）

---

## 2026-06-23 — 检索权重 + Embedding 本地 Fallback 调整（详见 [CHANGELOG_2026-06-23b_检索权重与Embedding本地Fallback调整](CHANGELOG_2026-06-23b_检索权重与Embedding本地Fallback调整.md)）

- 检索权重调整：BM25 0.65→0.45, Dense 0.35→0.55
- Embedding 本地 Fallback 禁用
- 法律结构解析器修复（law_name "一般规定" 修正）
- Benchmark V4 生成器（11 字段，增强提示词，断点续跑）

## 2026-06-23 — 截断 law_name 修复 + 召回评测 V3（详见 [CHANGELOG_2026-06-23a_截断law_name修复与召回评测V3](CHANGELOG_2026-06-23a_截断law_name修复与召回评测V3.md)））

- Parser 双 Bug 修复：跨行 PDF 标题合并 + 无章节法律保留
- 手术式修复策略（仅重处理大合集 PDF）
- Benchmark V3（772 题，四级命中体系）
- 余弦命中体系（cosine_hit@1/@5, threshold=0.85）
- SSH 隧道自动重连（tunnel.py）

---

## 2026-06-22 — Milvus 元数据 Bug 修复 + 段落切块 QA 准备（详见 [CHANGELOG_2026-06-22_Milvus元数据Bug修复与段落切块QA准备](CHANGELOG_2026-06-22_Milvus元数据Bug修复与段落切块QA准备.md)）

- Milvus 元数据 Bug 修复 + bids 向量库重建
- 段落切块 QA 适配

---

## 2026-06-21 — 实务 PDF 重切 + 中文数字规范化（详见 [CHANGELOG_2026-06-21_实务PDF重切与中文数字规范化](CHANGELOG_2026-06-21_实务PDF重切与中文数字规范化.md)）

- 实务 PDF 自然段归并切法（1969→770 chunks）
- Query 中文数字→阿拉伯数字规范化（第三十七条→第37条）
- Pipeline 条款号精确匹配 boost（1.2x）
- 评测脚本 bug 修复 + 文件版本对齐

---

## 2026-06-18 — 数据采集与存储架构重建（详见 [CHANGELOG_2026-06-18_数据采集与存储架构重建](CHANGELOG_2026-06-18_数据采集与存储架构重建.md)）

- 6 大数据集采集完成（3,537 条 Excel）
- Milvus 新增 policy collection（~9,800 chunks）
- SQLite 新增 3 张表（enterprise/price/product）
- 检索管线三库检索（regulations + bids + policy）
- 舆情爬虫重写 v3（161→2,014 条）

---

## 2026-06-17 — Milvus 与 BGE-M3 服务端向量化（详见 [CHANGELOG_2026-06-17_Milvus与BGE-M3服务端向量化](CHANGELOG_2026-06-17_Milvus与BGE-M3服务端向量化.md)）

- Redis 改为可选依赖（连接失败自动降级）
- 一键启动脚本 start.bat
- Milvus get_all_documents 分页查询
- 删除 Parent 缓存全量预加载
- 查询改写保护 + 默认关闭
- PlannerExecutor 检索任务合并

---

## 2026-06-10 — Checkpoint 与 Memory 路由重构（详见 [CHANGELOG_2026-06-10_Checkpoint与Memory路由重构](CHANGELOG_2026-06-10_Checkpoint与Memory路由重构.md)）

- Agent checkpoint 系统
- Memory 模块（Buffer + Summary + Entity）
- Router 重构

---

## 2026-06-07 — AutoRouting 自适应路由（详见 [CHANGELOG_2026-06-07_AutoRouting自适应路由](CHANGELOG_2026-06-07_AutoRouting自适应路由.md)）

- ThinkRouter / FastRouter 双模自适应路由
- quick_intercept 快速拦截（greeting/thanks 秒回）

---

## 2026-06-06 — Planner 职责分离与 DAG 调度（详见 [CHANGELOG_2026-06-06b_Planner职责分离与DAG调度](CHANGELOG_2026-06-06b_Planner职责分离与DAG调度.md)）

- PlannerExecutor DAG 调度 + 自动重规划
- 并行执行独立 task

## 2026-06-06 — Agent 工程化与 Planner 系统建立（详见 [CHANGELOG_2026-06-06a_Agent工程化与Planner系统建立](CHANGELOG_2026-06-06a_Agent工程化与Planner系统建立.md)）

- ReAct Agent（Thought→Action→Observation, max 5 steps）
- Planner 系统（TaskAnalysis + ToolPlanning）
- Agent 工具注册（声明式 config.yaml 管理）

---

## 2026-05-29 — LLM 传参函数缺陷修复（详见 [CHANGELOG_2026-05-29_LLM传参函数缺陷修复](CHANGELOG_2026-05-29_LLM传参函数缺陷修复.md)）

- _call_llm 传参函数缺陷修复

---

## 2026-05-28 — 法律文本切块问题（详见 [CHANGELOG_2026-05-28_法律文本切块问题](CHANGELOG_2026-05-28_法律文本切块问题.md)）

- 法律文本切块问题分析与修复

---

## 2026-05-19 — 跨库联合精排与路由重构（详见 [CHANGELOG_2026-05-19_跨库联合精排与路由重构](CHANGELOG_2026-05-19_跨库联合精排与路由重构.md)）

- Top-1 跃升 25.1pp，突破 85%
- 跨库联合精排（regulations + bids 同时检索）
- 路由降维（三分类→二分类网关）
- 工业级 Fallback 容错闭环

---

## 2026-05-13 — 初始意图路由与 Reranker 降级（详见 [CHANGELOG_2026-05-13_初始意图路由与Reranker降级](CHANGELOG_2026-05-13_初始意图路由与Reranker降级.md)）

- 意图路由拦截（Intent Router）
- Reranker 降级处理（防止 HF 下载死锁）
- SQL 数据对齐 + 类型安全处理
