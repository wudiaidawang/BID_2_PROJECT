# RAG 系统 Chunk 切分与检索问题报告

**日期**: 2026-05-28  
**分支**: panxin-dev  
**检查范围**: init_pdf.py → LegalStructureParser → ParentChunkBuilder → ChildChunkBuilder → SearchPipeline → ParentContextExpander → LLMGenerator

---

## 一、问题总览

| # | 问题 | 严重程度 | 影响范围 | 状态 |
|---|------|----------|----------|------|
| 1 | max_tokens 硬编码 500 | **高** | 所有法规类回答的输出完整性 | ✅ 已修复 |
| 2 | Reranker 输入截断 512 chars | **中** | 长法条排序准确性 | ✅ 已修复 |
| 3 | 滑动窗口 chunk 无来源上下文 | **中** | 法律解读类 PDF 的检索溯源 | ✅ 已修复 |
| 4 | 短法条 header 稀释 embedding | **低** | 短法条（<200字）检索精度 | ✅ 已修复 |
| 5 | 多片段整合能力不足 | **中** | 需要跨法条综合回答的场景 | ✅ 已修复 |

---

## 二、父子块映射核实

### 结论：父子块映射机制真实存在，完整链路如下。

### 入库链路

```
PDF 原始文本
   │
   ▼
LegalStructureParser.parse()
   ├── 按文档标题切分多部法律
   ├── 按"第X章"切分章节
   └── 按"第X条"切分法条 → LawDocument[] → ArticleInfo[]
   │
   ▼
ParentChunkBuilder.build()
   ├── 每条法条 → 1 个 parent chunk
   ├── chunk_type = "parent"
   ├── content = header + 完整法条正文
   ├── raw_content = 不含 header 的正文
   └── header_for_embedding = 层级头信息
   │
   ▼
ChildChunkBuilder.build_all(parents)
   ├── 短法条 (≤400 chars) → searchable_parents → 直接入库参与检索
   └── 长法条 (>400 chars) → children (按子项/段落/句子拆分)
         ├── chunk_type = "child"
         ├── parent_id = parent.chunk_id
         ├── content = header + 子段内容
         └── parent 完整内容 → parent_only_chunks → 入库但不参与检索
```

### 检索链路

```
用户问题
   │
   ▼
SearchPipeline.search_unified()
   ├── Stage 1: preprocess (查询预处理)
   ├── Stage 2: retrieve + fuse (Vector + BM25 → RRF 融合)
   ├── Stage 3: merge (跨库合并去重)
   ├── Stage 4: expand ← ParentContextExpander
   │     ├── 识别 chunk_type="child" 的结果
   │     ├── 按 parent_id 批量查 ChromaDB
   │     ├── 附加 parent_content (完整法条) 到 child
   │     └── 按 article_id 去重
   ├── Stage 5: rerank (BGE-reranker 精排)
   └── 返回 top_k 结果
   │
   ▼
LLMGenerator.generate_with_history()
   ├── 取 context[:5]
   ├── 优先使用 parent_content（完整法条）
   ├── 每条截断 1500 chars
   └── 构建 prompt → 调用 LLM
```

### 关键文件定位

| 组件 | 文件 | 行号 |
|------|------|------|
| 结构解析 | `app/core/legal_structure_parser.py` | :95 |
| Parent 构建 | `app/core/parent_chunk_builder.py` | :20 |
| Child 构建 | `app/core/child_chunk_builder.py` | :31 |
| Parent 扩展 | `app/pipeline/expanders.py` | :44 |
| 管线编排 | `app/pipeline/pipeline.py` | :197 |
| 生成使用 | `app/core/generator.py` | :70 |

---

## 三、各问题详细分析

### 问题 1：max_tokens 硬编码 500（已修复）

**现象**：`generator.py:47` 硬编码 `"max_tokens": 500`，完全忽略 `config.yaml` 中的 `llm.max_tokens: 2000`。

**代码对比**：

```python
# 修复前 (generator.py:47)
"max_tokens": 500

# 修复后
"max_tokens": settings.llm_max_tokens  # -> 2000
```

**影响**：
- LLM 输出被限制为 500 tokens，约 750 中文字符
- 当问题需要综合多个法条（如"招标阶段的违规行为有哪些？"）时，500 tokens 根本无法覆盖
- `settings.llm_max_tokens` 属性 (config.py:44-45) 正确读到了 2000，但从未被使用

**修复**：
- `generator.py:47`: `max_tokens` → `settings.llm_max_tokens`
- `generator.py:46`: `temperature` → `settings.llm_temperature`（同步修复）
- `generator.py:49`: `timeout` → `settings.llm_timeout`（同步修复）

---

### 问题 2：Reranker 输入截断 512 chars（已修复）

**现象**：`config.yaml` 中 `reranker.max_input_length: 512`，`pipeline.py:298` 按此截断文本后重排。

**问题链路**：
```
检索结果 (parent_content 可能 1500+ chars)
  → 截断到 512 chars
  → BGE-reranker 打分
  → 排序可能不准确（因为后文关键信息被切掉）
```

**影响**：
- 长法条的前 512 字符通常是"第X条 + 前半句"，关键规定可能在 512 字符之后
- 重排是最终排序依据，排序错误直接导致生成质量下降

**修复**：`config.yaml:83` `max_input_length: 512` → `1024`

---

### 问题 3：滑动窗口 chunk 无来源上下文（已修复）

**现象**：`sliding_window_chunk` (`init_pdf.py:39`) 是纯字符级切块，不注入任何来源信息。用于"招标投标法律解读与风险防范实务"这本非法律条文类 PDF。

**问题**：
- Chunk 检索出来就是一段裸文本，LLM 不知道出自哪本书、哪个章节
- 与结构化切块形成鲜明对比——结构化块有完整的 header 注入

**修复**：`sliding_window_chunk` 新增 `source_label` 参数，在每个 chunk 前注入 `【来源书名】` 标签：
```python
# 修复前
chunk = "根据招标投标法规定，招标人应当..."

# 修复后
chunk = "【招标投标法律解读与风险防范实务】\n根据招标投标法规定，招标人应当..."
```

---

### 问题 4：短法条 Header 稀释 Embedding（已修复）

**现象**：短法条（如 80 字的法条），header 约 50 字，占 embedding 文本的 38%。

```
Embedding 文本 ≈ 50% header + 50% 法条正文
→ 检索时 header 部分的语义权重过高
→ 不同章节但同样叫"第二十七条"的法条会被错误拉近
```

**修复**：`ParentChunkBuilder._build_parent` 对短法条（<200 chars）使用紧凑 header：
```python
# 标准 header（长法条）
《中华人民共和国招标投标法》
第二章 招标
第十条 招标方式

# 紧凑 header（短法条，<200 chars）
《招标投标法》 / 第二章 招标 / 第十条
```
同时 `header_for_embedding` 仍保存完整 header，供 child chunks 继承和显示使用。

---

### 问题 5：多片段整合能力不足（已修复）

**现象**：原代码取 `context[:3]`，每条截断 800 字符。system prompt 无明确的多片段整合指令。

**影响**：跨法条问题（"招标阶段和评标阶段各有哪些违规情形？"）可能只获得部分法条的上下文。

**修复**：
1. **System prompt 增强**（`generator.py:57-63`）：
   - 明确要求整合所有相关片段
   - 要求引用法律出处（名称+条款号）
2. **上下文扩大**：`context[:3]` → `context[:5]`，每条 `800` → `1500` 字符

---

## 四、当前 Chunk 配置参数（config.yaml）

```yaml
legal_chunking:
  parent_context_enabled: true    # 父子映射开关
  child_split_threshold: 400      # 法条超过 400 字符才拆 child
  child_target_size: 300          # child chunk 目标大小
  child_overlap: 40               # child 间重叠字符数
  header_injection_enabled: true  # embedding 前注入法律层级信息

reranker:
  max_input_length: 1024          # ✅ 已从 512 调至 1024

llm:
  max_tokens: 2000                # ✅ 已在 generator.py 中引用
```

---

## 五、架构评价

### 做得好的方面

1. **Parent-Child 架构设计合理**：先入库 child（小粒度检索），检索后回补 parent（完整法条生成），既保证召回精度又保证生成完整度
2. **拆分层级优先级正确**：（一）（二）子项 → 自然段落 → 句子边界，优先在语义边界切割
3. **article_id 去重**：避免同一法条的多个 child 占据 top-k 位置
4. **管道断路器设计**：每阶段独立断路器，非核心阶段失败不会导致整体崩溃
5. **配置驱动**：chunk 大小/阈值/策略均可通过 config.yaml 调整

### 仍需关注的风险点

1. **BGE-small-zh 维度仅 512**：对于 300-400 chars 的中文法律 chunk，512 维 embedding 的区分度可能不足，长法条的语义信息密度高，512 维可能丢失细节。如需提升精度可考虑 `bge-large-zh-v1.5` (1024 维)
2. **ParentContextExpander 的缓存策略**：首次查询时预加载全部 parent 到内存，collections 增长后会有内存压力
3. **滑动窗口的 500 chars 与结构化块的 300 chars 不一致**：两种切块策略的粒度不同，在 RRF 融合时可能偏向粒度更匹配 query 的块

---

## 六、修改文件清单

| 文件 | 变更 |
|------|------|
| `app/core/generator.py` | max_tokens/temperature/timeout 改用 settings；prompt 增强多片段整合；context 扩大至 top-5 每条 1500 chars |
| `config.yaml` | reranker.max_input_length 512→1024 |
| `app/core/parent_chunk_builder.py` | 新增紧凑 header 方法；短法条自动切换紧凑 header；保留完整 header 供 child 和显示 |
| `init_pdf.py` | sliding_window_chunk 新增 source_label 参数；两处调用点传入 PDF 名称 |

---

## 七、下一步建议

1. **重新初始化 PDF 库**：运行 `python init_pdf.py` 以应用滑动窗口的来源标签和紧凑 header
2. **A/B 测试 retrieval 精度**：使用 `eval_retrieval_accuracy.py` 对比修复前后的 recall@5
3. **监控 LLM 输出质量**：关注 max_tokens 从 500 调至 2000 后，长回答是否有编造内容的风险
4. **考虑升级 embedding 模型**：如果 embedding 区分度仍不足，在 `config.yaml` 中将 `embedding.model_name` 从 `bge-small` 切换到 `bge-large`
