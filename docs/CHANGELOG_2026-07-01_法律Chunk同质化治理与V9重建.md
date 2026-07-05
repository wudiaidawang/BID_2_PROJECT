# 2026-07-01 — 法律 Chunk 同质化治理与 policy_v9 重建

## 背景

V6 评测体系中法律检索（pdf_law_child）存在严重的 chunk 同质化问题：同一 parent 下的多个 child 共享相同的 header，导致 embedding 区分度极低，检索时容易召回错误 child。邀请智谱（GLM-4.5-Flash）审查了真实 chunk 数据后，给出了针对性建议。

## Zhipu v2 审查发现

将 33,284 字符的真实 chunk 数据 + 当前切块代码 + 统计指标发送智谱审查，核心发现：

1. **Header 重复** — 同 parent 下 3-5 个 child 共享完全相同的 header，embedding 几乎相同
2. **实体密度低** — 平均每 chunk 仅 3.3 个实体关键词，7% 的 chunk 完全无实体
3. **子条款区分度低** — 连续子条款（一）（二）（三）被切成不同 child 但结构高度相似

## 修改内容

### 1. 差异化 Child Header（child_chunk_builder.py:199-206）

```python
# 每个 child 的 header 包含子块序号和内容预览，避免同 parent 下各 child 同质化
if self.header_enabled and header:
    preview = seg[:25].replace("\n", "")
    child_header = f"{header} [子{i+1}: {preview}...]"
    retrieval_text = f"{child_header}\n[SEP]\n{seg}"
```

### 2. [SEP] 分隔符 — retrieval_text / text 解耦（parent_chunk_builder.py:64, child_chunk_builder.py:199）

```python
# parent
retrieval_text = f"{embedding_header}\n[SEP]\n{content}"

# child
retrieval_text = f"{child_header}\n[SEP]\n{seg}"
```

正文与 header 用 `[SEP]` 明确分隔，text 字段保持干净原文用于展示。

### 3. child_split_threshold: 400 → 1000（config.yaml:383）

减少不必要的拆分。1000 字符以下的法条不再拆 child，直接以 parent 参与检索。

### 4. child_overlap: 40 → 50（config.yaml:387）

适度增加 child 间重叠以保留语义连续性。

### 5. 文档边界检测（legal_structure_parser.py）

- **法规结束标识**: `本办法自...施行。` 正则，检测法律正文结束
- **附件略写检测**: `附件：(略)` / `附件（略）` 正则，防止附件标记被误认为新法条
- **部委文档标题**: 新增 `部/局/委/办/厅/署/院/会关于...` 模式的部委文档标题识别

### 6. 禁用 _merge_short_articles（服务器 init_policy_collection.py）

服务器端 init 脚本中存在 `_merge_short_articles` 函数（连续短文合并，min 300 字符，max 5 篇），这是 child 数量从 438 → 1,461 爆炸的根因。合并后的大 chunk 必然超过 threshold，被拆成多个 child，但这些 child 来自不同法条，语义不连贯。**已注释掉该调用**。

## 重建结果

服务器 `policy_v9` collection 重建完成（数据库 panxin_dev）：

| chunk_type | 旧 (policy) | 新 (policy_v9) | 变化 |
|------------|:-----------:|:-------------:|:----:|
| pdf_law_parent | 4,682 | 1,680 | -3,002 |
| pdf_law_child | 438 | **155** | -283 |
| pdf_case_paragraph | 770 | 770 | 不变 |
| pdf_case_sliding | 78 | 78 | 不变 |
| opinion_news | 2,014 | 2,014 | 不变 |
| policy_doc | 149 | 149 | 不变 |
| **总计** | **8,131** | **4,846** | **-3,285** |

- **child 从 1,461 → 155**，下降 90%（归因：禁用 merge + 阈值 1000）
- **parent 从 4,682 → 1,680**，策略从段落级 → 法条级（一个法条一个 parent）
- 总 chunk 减少不意味着信息丢失——parent 保留完整法条内容，只是检索粒度改变

## 附带清理

- 本地 3 个旧会话残留 Python 进程已停（sync_and_rebuild ×2、fix_merge）
- 远程 `rerank`(2082786) 和 `planC`(2705184) screen 未动（用户要求不碰远程）
- `eval_standalone.py` 指向 `policy_v9`
- `current_chunks.json` 已从新 collection 重新导出

## 待办

- [ ] 跑 `gen_eval_benchmark_v7.py` 重新生成 benchmark（chunk ID 已变，老 benchmark 不匹配）
- [ ] 跑 V7 召回评测，对比新旧 Recall 变化
