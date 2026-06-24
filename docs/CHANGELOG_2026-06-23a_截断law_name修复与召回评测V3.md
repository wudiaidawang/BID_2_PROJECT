
# 更新日志 15 — 截断 law_name 修复与召回评测 V3

**日期**: 2026-06-22  
**版本**: v5.3.2

---

## 一、截断 law_name 修复（Part 1）

### 问题

大合集 PDF (`中华人民共和国招标投标法律法规全书`) 解析时，3 个法规名称被截断：
- `和服务定点采购管理办法` → 应为 `中央国家机关政府采购中心货物和服务定点采购管理办法`
- `及评标专家管理办法` → 应为 `铁路建设工程评标专家库及评标专家管理办法`
- `与招投标挂钩办法` → 应为 `铁路建设工程质量安全事故与招投标挂钩办法`

### 根因（两个 Parser Bug）

**Bug 1: 跨行标题未合并**

PDF 提取将长标题断为两行：
```
铁路建设工程质量安全事故
与招投标挂钩办法
```
解析器只逐行匹配标题，第一行不以标题后缀结尾 → 不识别，第二行以"与"开头 → 被截断。

**修复**: `legal_structure_parser.py` `_split_by_document_title()` — 新增跨行合并逻辑：当前行是纯中文且不以标题后缀结尾时，尝试与下一行合并后匹配。新增 `_is_partial_title_start()` 方法判断前段。

**Bug 2: 无章节法律直接丢弃**

`_parse_single_law()` 只有 `_split_by_chapter()` 分支。没有"第X章"标题的法律（如《铁路建设工程质量安全事故与招投标挂钩办法》）直接返回空 chapters → 整部法律丢弃。

**修复**: `_parse_single_law()` 新增 fallback 分支：无章节时直接从全文按"第X条"切分，创建虚拟章节（chapter_id=0）容纳法条。

### 修复后效果

- 大合集 PDF 重解析：154 部法律、530 章、4226 条 → 4639 chunks
- 新增 37 部之前被丢弃的无章节法律（510 条法条）

---

## 二、手术式修复策略

不重导所有数据，只精确定点修复：

1. **删除旧 chunks**: 按 `source_doc` 过滤删除大合集 PDF 的全部 4022 条旧 chunks + 截断 name 安全网删除
2. **重导入**: 仅大合集 PDF 用修正后解析器重切重入（4639 chunks）
3. **Benchmark ID 修复**: `fix_benchmark_v3.py` — 从 Milvus 查询新 chunk ID 映射（旧 article_id → 新 chunk ID），替换 benchmark 中 32 个失效 ID
4. **2 个归属错误修正**: qa_v2_0369/0393 的 article 19/20 被旧解析器错误归属到"与招投标挂钩办法"，实际属于相邻法律，手动替换为正确 chunk ID
5. **law_name 字段同步**: 28 个 QA 的 law_name 从截断名更新为完整名

### 工具脚本

| 文件 | 用途 |
|------|------|
| `fix_truncated_law_names.py` | 删除旧 chunks + 重处理大合集 PDF |
| `fix_benchmark_v3.py` | 修复 benchmark 中的 chunk ID 映射 + law_name 同步 |
| `tunnel.py` | SSH 隧道自动重连（paramiko + keepalive 30s） |

---

## 三、policy_doc / opinion_news law_name 同步（Part 2）

### 问题

policy_doc 和 opinion_news 类型的 chunk 在 Milvus 中没有 `law_name` 字段（只有 `title`），导致召回评测中只能 exact match，无法做文档级 parent 匹配。

### 修复

**`init_policy_collection.py`**: policy_doc 的 `政策标题` → `law_name` + `title`；opinion_news 的 `舆情标题` → `law_name` + `title`

**`run_recall_eval_full.py`** `classify_hit()`: 新增文档级匹配分支 — 当 chunk 无 article_id 但有 law_name（policy_doc / opinion_news / pdf_case），按 law_name 做 parent 级命中判断。

**Benchmark 同步**: `fix_benchmark_v3.py` — 从 Milvus 批量查询 98 个 opinion/policy chunk 的 law_name，写入 benchmark JSON。

---

## 四、余弦相似度召回评测（Part 3）

### 改动

**`run_recall_eval_full.py`**:

1. 新增 `COSINE_THRESHOLD = 0.85`
2. `resolve_expected_chunks()` 返回值增加 `retrieval_text` 字段
3. 新增 `precompute_expected_embeddings()` — 批量编码所有预期 chunk 文本
4. 新增 `_cosine()` 辅助函数
5. `evaluate()`: 对 ID-based 匹配失败的结果，做余弦相似度 fallback；≥ 0.85 算 `cosine_hit`
6. 报告新增指标: `cosine_hit@1`、`cosine_hit@5`、`cosine_hits` 详情列表

### 四级命中体系

```
exact → parent → soft → cosine
  │        │        │        │
  │        │        │        └── 语义相似 ≥ 0.85 (向量比对)
  │        │        └─────────── 条款号/关键词部分匹配
  │        └──────────────────── 同法律/同文档(article_id不同)
  └───────────────────────────── chunk ID 精确匹配
```

---

## 五、Benchmark 版本演进

| 版本 | 题目数 | 说明 |
|------|--------|------|
| V1 | 457 | 单级精确命中体系 |
| V2 | 898 | 三级命中体系 (exact/parent/soft) |
| **V3** | **772** | 修正截断 law_name + opinion/policy 同步 law_name + 余弦命中体系 |

V3 题目减少原因：V2 中有 126 题对应已删除的旧 `pdf_case_sliding` 滑动窗口 chunks（实务 PDF 重切为 `pdf_case_paragraph` 后旧 ID 全部失效），后续需为新的 pdf_case_paragraph chunks 重新生成 QA。

---

## 六、版本标记

```
v5.3.2 — 2026-06-22
  - fix: 跨行PDF标题合并 (_is_partial_title_start + 跨行合并)
  - fix: 无章节法律保留 (direct article parsing fallback)
  - fix: 3个截断law_name修正 (TOC模糊匹配 + 手工映射)
  - add: policy_doc/opinion_news 父块名同步 (law_name字段)
  - add: 余弦相似度召回评测 (cosine_hit@1/@5, threshold=0.85)
  - add: benchmark V3 (772题, 四级命中体系)
  - add: SSH隧道自动重连 (tunnel.py, keepalive 30s)
```
