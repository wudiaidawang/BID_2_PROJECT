# 更新日志 — 2026-06-23

## 1. 检索权重调整

**文件**: `config.yaml`

- BM25（稀疏）权重: 0.65 → **0.45**
- Dense（稠密）权重: 0.35 → **0.55**
- 权重在 `fusion_strategy: weighted` 时生效

## 2. Embedding 本地 Fallback 禁用

**文件**: `app/core/embedding.py`

- `embed_batch()` 移除远程失败时的静默本地回退逻辑
- 远程 embedding 失败直接抛出异常，不再加载本地 BGE-M3 模型
- 原则：未经用户明确同意，不使用本地服务

## 3. 法律结构解析器修复

**文件**: `app/core/legal_structure_parser.py`

三处修正：
- **标题正则放宽**: `{2,16}` → `{2,24}`，容纳"中央国家机关政府采购和服务定点采购管理办法"等长法规名
- **TOC 目录解析**: 新增 `_parse_toc()` 方法，从目录页提取完整法规名，用于修正后续截断标题
- **黑名单扩充**: `TITLE_BLACKLIST` 新增 `"一般规定"`、`"串通投标"`，防止章节名被误判为法规标题（548 条 chunk 的 law_name 从"一般规定"修正为正确法规名）

## 4. 服务器 Milvus 大合集 PDF 重建

**工具**: `fix_truncated_law_names.py`

- 删除大合集 PDF（中华人民共和国招标投标法律法规全书）全部旧 chunk → 重解析 → 重入库
- 修复前：154 部法律、4,639 chunks，含 548 条 law_name="一般规定"
- 修复后：118 部法律、4,843 chunks，law_name 全部为正确法规名
- Policy collection: 8,021 → **8,225** chunks

## 5. Benchmark v4 生成器

**新文件**: `gen_eval_benchmark_v4.py`

核心升级 vs v2 生成器：
- **目标**: 1,000 题（等比缩放原计划分布）
- **增强提示词**: 精准锚定原则、唯一区分信息检查、禁止通用词拼接
- **新输出格式**: 11 字段（expected_chunk_id / acceptable_chunk_ids / type / category / sub_category / expected_source_type / expected_answer_text / is_regulatory_strict 等）
- **acceptable 去重**: 自动从 acceptable_chunk_ids 中移除 expected_chunk_id
- **source_chunks 合并**: source_chunks = [expected] + acceptable，评测脚本可直接使用
- **断点续跑**: `--resume` 支持中断接续

## 6. 评测脚本适配 V4

**文件**: `run_recall_eval_full.py`

- `QA_PATH`: v3 → v4
- 输出路径: `data/eval_questions/` → `data/QA_report/eval_recall_report_v4.json`

## 7. 数据文件

| 文件 | 变更 |
|------|------|
| `policy_chunks_export.json` | 重新导出 8,225 条（修复 law_name 后） |
| `eval_benchmark_v3.json` | 修复 25 个截断 chunk ID → 100% DB 匹配 |
| `eval_benchmark_v4.json` | **新建**，基于修复后 chunks 重新生成（生成中） |
| `eval_recall_report_v3.json` | 保留，V3 最终报告 |
| `QA_report/v3_recall_report.md` | V3 回顾报告 |

## 8. Session 重要规则

- **永远不要**在用户同意之前使用本地服务（embedding / reranker / LLM 等本地模型）
