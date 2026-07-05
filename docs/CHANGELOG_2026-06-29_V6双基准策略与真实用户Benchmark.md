# 2026-06-29 — V6 双基准策略与真实用户 Benchmark

## 背景

V5 评测（2174 题）Recall@5=96.3%，召回率严重通胀，无法有效衡量检索改进。通胀根源：

1. **Chunk 改写式问题** — 改几个字就出题，与原文高度重叠，BM25 轻松命中
2. **专有名词依赖** — 问题包含法律全称、完整项目名、医院名，直接定位唯一 Chunk
3. **缺乏真实用户模拟** — 不会问法条号、不会用公文腔

## 双基准策略

| 基准 | 文件 | 定位 | 用途 |
|------|------|------|------|
| **V5** | `v5_regression.json` | 回归测试 | 确保改动不破坏原有能力 |
| **V6** | `v6_benchmark.json` | 真实用户模拟 | 衡量真实检索能力，有区分度 |

## V6 Prompt 设计（10 节）

固化至 `data/eval_questions/prompts/v6_prompt.md`，生成脚本从文件动态读取：

1. **禁止 Chunk 改写** — 不能改几个字就生成问题
2. **摆脱 Chunk 原文** — 禁止连续复用原文短语
3. **减少专有名词** — 不用完整法律名/项目名，用口语替代
4. **模拟真实用户（6 角色）** — 企业员工/管理者/法务/个体户/新人/合规
5. **多样化表达** — 同义词替换、口语化、场景化、反问、间接指代
6. **优先生成业务场景化问题** — "我的项目……该怎么办？"
7. **题型覆盖（建议比例）** — 8 种 question_type
8. **检索难度标注** — 4 级 retrieval_difficulty
9. **按 Chunk Type 策略** — policy_doc 最难（4-6 题），opinion_news 最轻（1-2 题）
10. **输出格式** — 严格 JSON

## V6 QA 生成

- **模型**: GLM-4.1V-Thinking-FlashX（智谱 Thinking）
- **脚本**: `gen_eval_benchmark_v6.py`（断点续跑）
- **跨文档**: `gen_v6_cross_doc.py`（46/100 题）
- **标注修复**: `fix_v6_annotations.py`（回填缺失 + 修正 LLM 拼写）
- **最终题数**: 2908 QA

### 字段结构

```json
{
  "id": "qa_v6_0001",
  "question": "我们公司中标后多久必须签合同？",
  "answer": "...",
  "expected_chunk_id": "policy_40",
  "acceptable_chunk_ids": [],
  "chunk_type": "policy_doc",
  "span": "single",
  "question_type": "procedure",
  "retrieval_difficulty": "scenario"
}
```

### 标注体系

**question_type（8 种）**: scenario_judgment, condition_check, procedure, responsibility, definition, comparison, case_reasoning, announcement_interpretation

**retrieval_difficulty（4 级）**: direct, synonym, scenario, cross_reference

### acceptable_chunk_ids 策略

- single / parent_child: 关闭（不设候选）
- cross_doc: 保留（跨文档需多个 Chunk 共同回答）

## V6 评测

- **脚本**: `eval_standalone.py`（3 并发，直连 Milvus + Embedding/Reranker）
- **Bug 修复**: `hit_rank <= 3` → `hit_rank == 2 or hit_rank == 3`（miss 误计为 R@3 命中）
- **新增维度**: 按 question_type、retrieval_difficulty 分组统计

## V6 召回结果

### 整体

| 指标 | 命中 | 比率 |
|------|------|------|
| Recall@1 | 1010/2908 | **34.7%** |
| Recall@3 | 1445/2908 | **49.7%** |
| Recall@5 | 1586/2908 | **54.5%** |

对比 V5（R@1=71.5%, R@5=96.3%），V6 区分度大幅提升。

### 按 chunk_type

| 类型 | 题数 | R@1 | R@5 |
|------|------|-----|-----|
| pdf_law_parent | 584 | 51.7% | 74.7% |
| pdf_case_paragraph | 669 | 43.8% | 66.2% |
| policy_doc | 1091 | 28.8% | 46.8% |
| pdf_case_sliding | 252 | 15.9% | 44.4% |
| cross_doc | 46 | 23.9% | 34.8% |
| opinion_news | 266 | 18.8% | 25.6% |

### 按检索难度

| 难度 | 题数 | R@1 | R@5 |
|------|------|-----|-----|
| direct | 765 | 40.8% | 59.7% |
| scenario | 1414 | 33.0% | 53.7% |
| synonym | 560 | 33.2% | 51.6% |
| cross_reference | 169 | 26.6% | 47.9% |

标注与实际 Recall 排序一致（direct > scenario ≈ synonym > cross_reference），验证标注质量。

### 按题型

| 题型 | 题数 | R@1 | R@5 |
|------|------|-----|-----|
| announcement_interpretation | 29 | 51.7% | 69.0% |
| definition | 281 | 43.8% | 68.0% |
| case_reasoning | 78 | 33.3% | 65.4% |
| scenario_judgment | 1197 | 36.2% | 57.1% |
| responsibility | 264 | 33.0% | 54.9% |
| condition_check | 327 | 33.0% | 53.5% |
| comparison | 150 | 28.7% | 44.7% |
| procedure | 582 | 30.1% | 43.6% |

procedure（流程）和 comparison（对比）召回最低，需跨 Chunk 信息综合。

## 文件清单

| 文件 | 说明 |
|------|------|
| `data/eval_questions/prompts/v6_prompt.md` | V6 系统提示词 |
| `gen_eval_benchmark_v6.py` | V6 主生成脚本 |
| `gen_v6_cross_doc.py` | 跨文档题目生成 |
| `fix_v6_annotations.py` | 标注修复工具 |
| `v6_benchmark.json` | V6 评测集（2908 题） |
| `eval_standalone.py` | 独立评测脚本 |
| `v6_report.md` | 评测报告 |

## 已知问题：Standalone Eval 的 BM25 不一致

**发现时间**: 2026-06-29

**问题**: `eval_standalone.py` 的 BM25 检索走的是 Milvus 服务端内置分词器（字符 n-gram），而不是生产管线 `app/pipeline/retrievers.py` 使用的本地 jieba 分词 BM25。

**影响**:
- 生产管线：jieba 分词 → "疫苗" 完整命中
- Standalone eval：Milvus 内置 → "疫苗" 盲区，BM25 零命中
- 结果：V6 Recall 数据偏低，BM25 那条腿在评测中实际是无效的
- 典型 case：6 道"疫苗"题 all miss，dense 排第 1 但被 BM25 噪音 + reranker 稀释

**待修复**: 将本地 jieba BM25 接入 `eval_standalone.py`，确保评测管线与生产管线一致。修复后需重新跑 V6 评测。
