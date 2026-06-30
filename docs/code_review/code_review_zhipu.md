### 详细审查报告

---

#### 1. 架构设计缺陷

**eval_standalone.py**
- **问题**：`search_one` 函数职责过重（第200行），混合了预处理、检索、融合、扩展和重排序逻辑
- **修改建议**：拆分为独立函数（`preprocess_query`, `retrieve_documents`, `fuse_results`, `expand_context`, `rerank_documents`），遵循单一职责原则

**fusion.py**
- **问题**：`WeightedFusion` 类与 `VectorRetriever`/`BM25Retriever` 耦合（第20行）
- **修改建议**：通过依赖注入解耦，改为接受 `List[Dict]` 而非具体检索器实例

**child_chunk_builder.py**
- **问题**：硬编码拆分策略优先级（第40行），缺乏扩展性
- **修改建议**：实现策略模式，允许配置多种拆分策略（如按子项/段落/句子）

**parent_chunk_builder.py**
- **问题**：`_make_chunk_id` 使用自增计数器（第80行），分布式环境下不安全
- **修改建议**：改用UUID或Snowflake ID生成器

---

#### 2. 性能瓶颈

**eval_standalone.py**
- **问题**：`build_local_bm25` 全量加载文档（第50行），内存占用高
- **修改建议**：实现分页加载+增量索引，使用 `numpy` 稀疏矩阵存储BM25权重

**eval_standalone.py**
- **问题**：`parent_context_expand` 全局锁（第120行）导致线程争用
- **修改建议**：使用线程本地缓存 + 异步构建parent映射表

**child_chunk_builder.py**
- **问题**：正则表达式拆分句子效率低（第90行）
- **修改建议**：集成 `spaCy` 或 `jieba` 分词器，优化句子边界检测

---

#### 3. 潜在 Bug / 边界条件

**eval_standalone.py**
- **问题**：`local_bm25_search` 过滤分数为0结果（第70行），可能丢失有效结果
- **修改建议**：移除 `scores[idx] > 0` 条件，或改为 `scores[idx] >= -1e-6`

**fusion.py**
- **问题**：`_compute_boost` 未处理空文本（第70行）
- **修改建议**：增加 `if not text: return 0.0` 检查

**parent_chunk_builder.py**
- **问题**：`_make_chunk_id` 哈希冲突风险（第80行）
- **修改建议**：使用 `hashlib.md5` 替代内置 `hash`

**query_rewriter.py**
- **问题**：`_normalize_article_numbers` 未处理转换失败（第80行）
- **修改建议**：添加 `try-except` 捕获转换异常

---

#### 4. eval脚本与生产管线的逻辑差异

**eval_standalone.py vs fusion.py**
- **问题**：加权融合逻辑不一致（第180行 vs 第100行）
  - eval版本：法条查询特殊降权（`chunk_type in ("pdf_law_child", "pdf_law_parent")`）
  - 生产版本：无此逻辑
- **修改建议**：将法条检测逻辑提取到公共模块 `app.pipeline.fusion.utils`

**eval_standalone.py vs preprocessor.py**
- **问题**：同义词扩展实现重复（第100行 vs 第40行）
- **修改建议**：统一使用 `preprocessor.py` 的 `_expand_synonyms` 方法

---

#### 5. 代码重复 / 可抽象复用

**eval_standalone.py & fusion.py**
- **问题**：RRF融合逻辑重复（第150行 vs 第20行）
- **修改建议**：提取到 `app.pipeline.fusion.rrf_fusion`

**eval_standalone.py & query_rewriter.py**
- **问题**：口语规范化逻辑重复（第110行 vs 第70行）
- **修改建议**：统一使用 `query_rewriter._colloquial_to_formal`

**child_chunk_builder.py & parent_chunk_builder.py**
- **问题**：元数据构建逻辑重复（第130行 vs 第70行）
- **修改建议**：提取公共函数 `build_chunk_metadata`

---

#### 6. 可维护性 / 可读性问题

**eval_standalone.py**
- **问题**：`search_one` 函数过长（200行），嵌套层级深
- **修改建议**：拆分为5个独立函数，添加流程图注释

**fusion.py**
- **问题**：`WeightedFusion.merge` 方法复杂（100行），Boost/Penalty计算耦合
- **修改建议**：拆分为 `_apply_weights`, `_apply_boosts`, `_apply_penalties` 三个方法

**query_rewriter.py**
- **问题**：`_init_rules` 方法硬编码配置源（第30行）
- **修改建议**：使用 `pydantic` 配置类统一管理规则来源

---

#### 7. 安全 / 资源泄漏问题

**eval_standalone.py**
- **问题**：`_get_client` 未显式关闭HTTP连接（第130行）
- **修改建议**：使用 `httpx.Client(timeout=60)` 的上下文管理器

**eval_standalone.py**
- **问题**：`_fetch_all_docs` 无分页大小限制（第40行）
- **修改建议**：添加 `max_page_size=10000`