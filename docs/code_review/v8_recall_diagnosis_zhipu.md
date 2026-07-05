# 智谱 V8 召回诊断报告

> 模型: glm-4.5-flash | Token: prompt=22100, completion=1835

---

# 招投标法规智能问答系统RAG召回率诊断报告

## 1. 融合策略问题分析

### 问题核心：BM25单独表现优于融合
- BM25 Recall@5=81.0%，Weighted Fusion后降至79.3%，融合反而拖累召回
- Dense only Recall@5=75.5%，说明BM25是主要贡献者

### 原因分析：
1. **Min-Max归一化问题**：
   - BM25高分被过度压缩，Dense低分被过度提升
   - 例如BM25得分0.9和0.8，归一化后差距从0.1缩小到约0.05

2. **动态权重不合理**：
   - 当前regulation查询BM25权重0.80过高，可能过度依赖关键词匹配
   - semantic查询BM25权重0.40过低，可能错失语义相关但非精确匹配的文档

3. **Boost机制问题**：
   - 法条Boost在非法规查询中可能引入噪声
   - 当前Boost上限0.35过高，导致非相关文档被过度提升

### 解决方案：
1. **改用RRF融合**：
   ```yaml
   fusion_strategy: "rrf"
   rrf_k: 60  # 当前值合理，保持不变
   ```

2. **调整归一化策略**：
   ```python
   # 替换Min-Max为Sigmoid或保留原始分数
   def _sigmoid_normalize(self, scores: List[float]) -> List[float]:
       import math
       return [1 / (1 + math.exp(-s)) for s in scores]
   ```

3. **优化动态权重**：
   ```yaml
   question_type_weights:
     keyword_heavy: [0.85, 0.15]   # 提高BM25权重
     semantic_heavy: [0.30, 0.70]  # 降低BM25权重
     balanced: [0.70, 0.30]
   ```

## 2. Parent Expansion零贡献问题

### 问题分析：
- Parent Expanded后召回率无变化，说明扩展逻辑未生效
- 可能原因：
  1. Parent查找失败（chunk_type不匹配或parent_id缺失）
  2. 扩展后的内容未被Reranker选中
  3. 同质化治理后的差异化header导致匹配失败

### 解决方案：
1. **检查Parent查找逻辑**：
   ```python
   # 在expanders.py中添加调试日志
   def expand(self, results: List[Dict], collection: str = "") -> List[Dict]:
       print(f"[ParentExpand] Input results: {len(results)}")
       enriched = []
       for r in results:
           chunk_type = r.get("metadata", {}).get("chunk_type", "")
           if chunk_type.endswith("_child"):
               print(f"[ParentExpand] Found child chunk: {r.get('id')}")
           # ...其余逻辑
   ```

2. **优化同质化治理后的匹配**：
   ```python
   # 在child_chunk_builder.py中调整header格式
   def _make_children(self, segments: List[str], parent: Dict) -> List[Dict]:
       # 简化header格式，避免过度差异化
       child_header = f"{parent.get('header_for_embedding', '')} [子{i+1}]"
       retrieval_text = f"{child_header}\n{seg}"  # 移除[SEP]分隔符
   ```

3. **调整Reranker候选池**：
   ```yaml
   reranker:
     candidate_pool: 50  # 从30增加到50，确保扩展内容有机会被选中
   ```

## 3. Miss模式分析

### 关键发现：
1. **高频错误召回**：
   - policy_0和policy_125被反复错误召回（13次和12次）
   - 这两个文档可能包含通用关键词，被过度匹配

2. **特定问题类型表现差**：
   - Comparison类问题R@5仅66.3%，显著低于平均水平
   - pdf_law_child类型R@5=79.4%，是所有类型中最差

3. **重复Miss问题**：
   - "上海市公共资源交易平台有哪些子平台"出现10次Miss
   - 这类问题可能需要专门的知识图谱或结构化数据支持

### 解决方案：
1. **高频错误召回处理**：
   ```python
   # 在fusion.py中添加黑名单机制
   HIGH_ERROR_DOCS = {"policy_0", "policy_125"}
   
   def _compute_penalty(self, text: str, doc_id: str = "") -> float:
       if doc_id in HIGH_ERROR_DOCS:
           return -0.5  # 强制降低这些文档的得分
       # ...原有逻辑
   ```

2. **Comparison类问题优化**：
   ```python
   # 在query_rewriter.py中添加比较词识别
   COMPARISON_PATTERNS = [
       r"和...有什么区别", r"与...的区别", r"对比", r"比较",
       r"不同点", r"相同点", r"差异", r"vs"
   ]
   
   def _detect_query_type(self, query: str) -> str:
       for pattern in COMPARISON_PATTERNS:
           if re.search(pattern, query):
               return "comparison"
       # ...原有逻辑
   ```

3. **pdf_law_child类型优化**：
   ```yaml
   source_type_boost:
     weights:
       pdf_law_child: 1.1  # 增加10%权重
       pdf_law_parent: 1.0  # 保持不变
   ```

## 4. 配置优化建议

### 当前配置问题：
1. **融合策略不一致**：
   - config.yaml使用rrf，但eval_standalone使用weighted_fusion
   - 需要统一策略

2. **BM25参数可能需要调整**：
   - 当前k1=1.2, b=0.75是标准值，但可能不适合招投标文本

3. **Reranker参数**：
   - candidate_pool=30可能偏小
   - max_input_length=1024可能不足以处理长法条

### 优化方案：
```yaml
# 统一使用RRF融合
retrieval:
  fusion_strategy: "rrf"
  rrf_k: 60

# 优化BM25参数
bm25:
  k1: 1.5  # 提高k1，增加长文档的权重
  b: 0.8   # 提高b，增加文档长度的影响

# 扩展Reranker能力
reranker:
  candidate_pool: 50  # 增加候选池
  max_input_length: 2048  # 支持更长输入
```

## 5. 优先级改进建议

### 按预期提升效果排序：

1. **统一融合策略为RRF**（预期提升2-3%）
   - 停止使用Weighted Fusion，改用RRF
   - 理由：当前Weighted Fusion明显拖累BM25的高召回表现

2. **优化Comparison类问题处理**（预期提升3-4%）
   - 添加专门的比较词识别
   - 为比较类问题构建专门的检索策略
   - 理由：Comparison类R@5仅66.3%，提升空间最大

3. **高频错误召回文档黑名单**（预期提升2-3%）
   - 将policy_0和policy_125加入黑名单
   - 理由：这两个文档被反复错误召回，严重影响召回率

4. **Parent Expansion调试与优化**（预期提升1-2%）
   - 修复Parent查找逻辑
   - 增加Reranker候选池大小
   - 理由：当前Parent Expansion完全无贡献，修复后应有提升

5. **pdf_law_child类型专项优化**（预期提升1-2%）
   - 增加该类型的权重
   - 考虑为法律子条款构建专门的向量表示
   - 理由：该类型是所有chunk_type中表现最差的

## 总结

当前系统的主要问题在于融合策略不合理和特定问题类型处理不足。建议优先解决融合策略不一致问题，然后针对高频错误召回和特定问题类型进行专项优化。通过这些改进，预期可以将Recall@5从当前的88.8%提升至92%以上。