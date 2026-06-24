# 更新日志索引

按日期倒序排列。

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
