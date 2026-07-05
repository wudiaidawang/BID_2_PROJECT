# 智谱: 法律文本同质化切块方案 (v2 — 含真实chunk数据)

Token: {'completion_tokens': 2128, 'completion_tokens_details': {'reasoning_tokens': 0}, 'prompt_tokens': 11319, 'prompt_tokens_details': {'cached_tokens': 4}, 'total_tokens': 13447}

---

# 招投标法规智能问答系统优化建议

## 1. 同质化问题深度分析

是的，header 重复确实是主要问题，但更深层次的原因是：

**内容结构高度相似**：从提供的样本可以看出，pdf_law_child 的同质化不仅体现在 header 上，更体现在内容结构上。例如：
- 大量 chunk 以"第四十七条 本办法自2008年5月1日起施行"开头
- 许多 chunk 包含类似的行政公文用语，如"各省、自治区、直辖市..."
- 子条款间的区分度低，尤其是连续的子条款（一）（二）（三）部分

**实体密度低**：统计显示 pdf_law_child 平均每 chunk 只有 3.3 个实体关键词，7% 的 chunk 完全没有实体关键词，这进一步降低了区分度。

**长文本稀释效应**：虽然平均长度 319 字不算特别长，但对于法律文本这种高结构化内容，重复的开头和格式化表达会显著稀释语义差异。

## 2. retrieval_text 格式优化建议

不建议完全去掉 header，但可以优化格式：

**方案一：差异化 header**
```python
# 为 child chunk 生成差异化 header
def _make_child_header(self, parent_header, child_index, child_content):
    # 提取前20个字符作为 child 特征
    content_preview = child_content[:20].replace("\n", "")
    return f"{parent_header} [子{child_index+1}: {content_preview}...]"
```

**方案二：header 与正文分离嵌入**
```python
# retrieval_text = header + [SEP] + 正文
retrieval_text = f"{header}\n{settings.SEP_TOKEN}\n{seg}"
```

**方案三：位置加权嵌入**
```python
# 对正文部分进行位置加权，减少 header 影响
weighted_text = (header * 0.3 + seg * 0.7) if len(seg) > 100 else header + " " + seg
```

## 3. 切块策略问题分析

当前切块策略确实存在问题：

**子条款切分不彻底**：从样本看，同一个法条下的多个子条款（一）（二）（三）被切分成不同 child，但这些子条款往往有共同的开头和结构，导致相似度高。

**句子边界切分不适合法律文本**：法律文本的句子往往较长，按句子切分会导致语义不完整，且增加相似度。

**建议改进方案**：
```python
def _split_by_legal_subsections(self, content: str) -> List[str]:
    """按法律子条款拆分，保留完整语义单元"""
    # 匹配 (一) (二) (三) 或 1. 2. 3. 等格式
    pattern = re.compile(r'(?<=\n|^)([（(][一二三四五六七八九十\d]+[）)]\s*|[一二三四五六七八九十\d]+\.\s*)')
    
    matches = list(pattern.finditer(content))
    if len(matches) < 2:
        return [content]
    
    segments = []
    start = 0
    for i, match in enumerate(matches):
        end = matches[i+1].start() if i+1 < len(matches) else len(content)
        segment = content[start:end].strip()
        if len(segment) > 30:  # 过滤掉空段落
            segments.append(segment)
        start = match.start()
    
    return segments
```

## 4. 检索层面同质化处理

**Maximal Marginal Relevance (MMR)**
```python
def mmr_rerank(self, query: str, docs: List[Dict], lambda_param: float = 0.5):
    """MMR 重排，增加结果多样性"""
    selected = [docs[0]]
    remaining = docs[1:]
    
    while remaining:
        scores = []
        for doc in remaining:
            # 计算与 query 的相似度
            sim_query = self.similarity(query, doc["text"])
            # 计算与已选文档的最小相似度
            sim_selected = max(self.similarity(doc["text"], s["text"]) for s in selected)
            # MMR 公式
            score = lambda_param * sim_query - (1 - lambda_param) * sim_selected
            scores.append(score)
        
        # 选择得分最高的文档
        best_idx = np.argmax(scores)
        selected.append(remaining[best_idx])
        remaining.pop(best_idx)
    
    return selected
```

**法律文本专用多样性策略**
```python
def legal_diversity_rerank(self, query: str, docs: List[Dict]):
    """针对法律文本的多样性重排"""
    # 按法条号分组
    article_groups = {}
    for doc in docs:
        article_id = doc.get("metadata", {}).get("article_id", "")
        if article_id not in article_groups:
            article_groups[article_id] = []
        article_groups[article_id].append(doc)
    
    # 每组选最优，然后合并
    diverse_docs = []
    for article_id, group in article_groups.items():
        # 在同一法条内按原始分数排序
        group_sorted = sorted(group, key=lambda x: x.get("score", 0), reverse=True)
        diverse_docs.append(group_sorted[0])
    
    # 重新排序
    return sorted(diverse_docs, key=lambda x: x.get("score", 0), reverse=True)
```

## 5. 无需重新 embedding 的快速方案

**方案一：检索文本预处理**
```python
def preprocess_retrieval_text(self, text: str, chunk_type: str):
    """针对不同 chunk 类型预处理检索文本"""
    if chunk_type == "pdf_law_child":
        # 移除重复的 header 部分
        lines = text.split("\n")
        if len(lines) > 1 and "第" in lines[0] and "条" in lines[0]:
            # 保留 header 但缩短
            header = lines[0][:30] + "..."
            return "\n".join([header] + lines[1:])
    return text
```

**方案二：查询扩展优化**
```python
def legal_query_rewrite(self, query: str):
    """针对法律查询的扩展策略"""
    # 识别法条号
    article_pattern = re.compile(r'第[一二三四五六七八九十百零\d]+条')
    article_match = article_pattern.search(query)
    
    if article_match:
        # 如果查询包含法条号，扩展为法条号+上下文
        article = article_match.group(0)
        return f"{article} {query}"
    
    # 识别法规名称
    for law_name in get_protected_names():
        if law_name in query and len(law_name) >= 4:
            return f"{law_name} {query}"
    
    return query
```

**方案三：融合策略调整**
```python
def law_child_fusion(self, dense_results, bm25_results, query):
    """专门针对 pdf_law_child 的融合策略"""
    # 检测是否为法规查询
    is_law_query = detect_regulation_entity(query)
    
    if is_law_query:
        # 法规查询：降低 child chunk 的权重
        for r in dense_results:
            if r.get("metadata", {}).get("chunk_type") == "pdf_law_child":
                r["score"] *= 0.7
        for r in bm25_results:
            if r.get("metadata", {}).get("chunk_type") == "pdf_law_child":
                r["score"] *= 0.7
    
    # 正常融合
    return self.rrf_fusion(dense_results, bm25_results)
```

## 6. 具体改造建议（按投入产出比排序）

### 高投入产出比方案

**1. 优化 child chunk 的 retrieval_text 格式**
- 将 header 缩短并添加 child 索引
- 在 header 和正文间添加特殊分隔符
- 实施成本：低（只需修改预处理代码）
- 预期提升：R@5 可提升 5-8%

**2. 实施法律文本专用多样性重排**
- 开发针对法律文本的 MMR 或分组重排策略
- 实施成本：中（需开发新算法）
- 预期提升：R@5 可提升 7-10%

### 中等投入产出比方案

**3. 改进法律文本切块策略**
- 优先按子条款（一）（二）（三）拆分，而非段落
- 增加子条款间的语义区分度
- 实施成本：中（需重新处理现有数据）
- 预期提升：R@5 可提升 8-12%

**4. 查询扩展优化**
- 针对法律查询的特殊扩展策略
- 识别法条号和法规名称
- 实施成本：低（修改查询处理逻辑）
- 预期提升：R@5 可提升 3-6%

### 低投入产出比方案

**5. 法律实体增强检索**
- 使用法律实体注册表增强 BM25 查询
- 对法律实体进行特殊加权
- 实施成本：中（需维护实体表和修改检索逻辑）
- 预期提升：R@5 可提升 4-7%

## 实施建议

1. **短期（1-2周）**：实施方案1和4，快速提升性能
2. **中期（1个月）**：实施方案2和5，进一步提升检索质量
3. **长期（2-3个月）**：重新处理数据，实施方案3，从根本上解决同质化问题

这些方案可以组合实施，建议先从方案1开始，因为它实施简单且效果明显，然后再逐步实施其他方案。