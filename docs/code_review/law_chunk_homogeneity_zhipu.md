# 智谱: 法律文本同质化切块方案

Token: {'completion_tokens': 1910, 'completion_tokens_details': {'reasoning_tokens': 0}, 'prompt_tokens': 510, 'prompt_tokens_details': {'cached_tokens': 4}, 'total_tokens': 2420}

---

# 招投标法规RAG系统优化方案

针对pdf_law_child类别召回率低的问题，我将提供一套具体的优化方案，从数据预处理、切块策略、检索增强和后处理四个维度进行改进。

## 一、数据预处理优化

### 1. 实体增强标记
- **方案**：对业务关键词进行特殊标记，增强区分度
- **实施**：
  ```python
  def mark_entities(text):
      entities = ["应当", "依法", "不得", "采购人", "供应商", "招标", "投标", "中标"]
      for entity in entities:
          text = text.replace(entity, f"[ENTITY]{entity}[/ENTITY]")
      return text
  ```
- **效果**：提升BM25对关键实体匹配的权重

### 2. 前缀处理优化
- **方案**：分离元数据与内容，避免前缀稀释
- **实施**：
  ```python
  def split_metadata(text):
      if "/" in text and "第" in text:
          parts = text.split("/", 1)
              metadata = parts[0].strip()
              content = parts[1].strip()
              return {
                  "metadata": metadata,
                  "content": content,
                  "full_text": text
              }
      return {"content": text, "full_text": text}
  ```

## 二、切块策略重构

### 1. 混合切块策略
- **方案**：结合语义切块与固定长度切块，保留上下文
- **实施**：
  ```python
  def hybrid_chunking(text, chunk_size=300, overlap=50):
      # 语义边界检测
      semantic_breaks = detect_semantic_breaks(text)
      
      chunks = []
      start = 0
      for break_point in semantic_breaks:
          if break_point - start > chunk_size:
              # 在语义边界处切块
              chunk = text[start:break_point]
              chunks.append(chunk)
              start = break_point - overlap
          else:
              # 超过chunk_size则强制切块
              chunk = text[start:start+chunk_size]
              chunks.append(chunk)
              start += chunk_size - overlap
      
      # 处理剩余文本
      if start < len(text):
          chunks.append(text[start:])
      
      return chunks
  ```

### 2. 层级化切块结构
- **方案**：保留父子关系但增加中间层级
- **实施**：
  ```
  law_parent (法条)
    ├── law_section (法条节)
    │   ├── child_semantic1 (语义块1)
    │   └── child_semantic2 (语义块2)
    └── law_detail (法条细节)
        ├── child_detail1 (细节块1)
        └── child_detail2 (细节块2)
  ```

### 3. 差异化切块
- **方案**：根据内容复杂度动态调整切块大小
- **实施**：
  ```python
  def adaptive_chunking(text):
      # 计算文本复杂度
      complexity = calculate_complexity(text)
      
      if complexity > 0.7:  # 高复杂度文本
          return semantic_chunking(text, chunk_size=200, overlap=30)
      elif complexity > 0.4:  # 中等复杂度
          return semantic_chunking(text, chunk_size=300, overlap=50)
      else:  # 低复杂度文本
          return fixed_chunking(text, chunk_size=400, overlap=100)
  ```

## 三、检索增强策略

### 1. 多路检索融合
- **方案**：结合BM25、Dense和Hybrid检索
- **实施**：
  ```python
  def multi_modal_search(query, index):
      # BM25检索
      bm25_results = index.bm25_search(query, k=50)
      
      # Dense检索
      dense_results = index.dense_search(query, k=50)
      
      # Hybrid检索（使用元数据增强）
      hybrid_results = index.hybrid_search(
          query, 
          metadata_boost={"law_name": 1.5, "article_id": 1.3}, 
          k=50
      )
      
      # RRF融合
      rrf_results = reciprocal_rank_fusion(
          [bm25_results, dense_results, hybrid_results], 
          k=60
      )
      
      return rrf_results[:10]
  ```

### 2. 查询增强
- **方案**：针对法律文本特点增强查询
- **实施**：
  ```python
  def legal_query_expansion(query):
      # 法律同义词扩展
      synonyms = {
          "采购": ["招标", "投标", "采购", "政府采购"],
          "供应商": ["投标人", "供应商", "承包商"],
          "招标人": ["采购人", "招标单位", "招标机构"]
      }
      
      expanded_terms = set([query])
      for term, synonym_list in synonyms.items():
          if term in query:
              expanded_terms.update(synonym_list)
      
      # 构建增强查询
      enhanced_query = " OR ".join(f'"{term}"' for term in expanded_terms)
      return enhanced_query
  ```

### 3. 元数据加权检索
- **方案**：在检索时对元数据进行加权
- **实施**：
  ```python
  def weighted_bm25(query, doc, metadata):
      # 基础BM25分数
      base_score = bm25_score(query, doc)
      
      # 元数据加权
      metadata_score = 0
      if query.lower() in metadata.get("law_name", "").lower():
          metadata_score += 0.3
      if query.lower() in metadata.get("article_id", "").lower():
          metadata_score += 0.2
      
      return base_score + metadata_score
  ```

## 四、后处理优化

### 1. 重排序模型
- **方案**：使用法律领域微调的重排序模型
- **实施**：
  ```python
  from transformers import AutoModelForSequenceClassification, AutoTokenizer
  
  def legal_reranker(query, candidates):
      model = AutoModelForSequenceClassification.from_pretrained("legal-reranker-model")
      tokenizer = AutoTokenizer.from_pretrained("legal-reranker-model")
      
      scores = []
      for candidate in candidates:
          inputs = tokenizer(query, candidate, return_tensors="pt", truncation=True)
          outputs = model(**inputs)
          score = outputs.logits[0].item()
          scores.append(score)
      
      # 按分数排序
      sorted_candidates = [x for _, x in sorted(zip(scores, candidates), reverse=True)]
      return sorted_candidates
  ```

### 2. 去重与多样性增强
- **方案**：确保返回结果多样化且不重复
- **实施**：
  ```python
  def deduplicate_and_diversify(results, diversity_threshold=0.7):
      # 基于元数据去重
      unique_results = {}
      for result in results:
          key = (result.metadata["law_name"], result.metadata["article_id"])
          if key not in unique_results:
              unique_results[key] = result
      
      # 多样性增强
      diverse_results = []
      seen_articles = set()
      
      for result in unique_results.values():
          article_id = result.metadata["article_id"]
          if article_id not in seen_articles or len(diverse_results) < 3:
              diverse_results.append(result)
              seen_articles.add(article_id)
          elif len(diverse_results) < 5:
              diverse_results.append(result)
      
      return diverse_results
  ```

## 五、实施路线图

1. **第一阶段（1-2周）**：
   - 实施数据预处理优化（实体增强、前缀处理）
   - 评估改进效果

2. **第二阶段（2-3周）**：
   - 实施混合切块策略
   - 重新构建索引
   - 测试召回率变化

3. **第三阶段（3-4周）**：
   - 实施多路检索融合
   - 开发查询增强功能
   - 优化元数据加权

4. **第四阶段（4-5周）**：
   - 部署重排序模型
   - 实施去重与多样性增强
   - 全面评估系统性能

## 六、预期效果

通过以上优化，预期pdf_law_child类别的R@5可以从55%提升至85%以上，具体表现为：
- Dense检索命中率从82%提升至90%
- BM25检索命中率从87%提升至92%
- 双路都丢失的比例从8%降至3%以下
- 平均排名从9提升至3以内

这套方案针对法律文本的同质化特点，通过精细化的切块策略、多维度检索增强和针对性后处理，有效解决了细粒度法律文本的召回难题。