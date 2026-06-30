### 优先级1：Recall下降原因分析（查询改写过度导致语义漂移）

#### 1.1 口语转书面语过度替换（`query_rewriter.py`）
**文件修改**：`query_rewriter.py`（第50-80行）  
**修改方法**：
```python
# 增加边界检查和意图保留机制
def rewrite_query(query):
    # 1. 保留礼貌用语标记
    if query.startswith(("请问", "我想")):
        query = f"[POLITE]{query}"  # 标记但不删除
    
    # 2. 同义词扩展增加语义校验
    if "围标" in query:
        query = query.replace("围标", "围标[串通投标]")  # 保留原词+扩展词
    
    # 3. 单字词替换增加边界检查
    if "交易" in query:
        # 仅在词边界替换
        query = re.sub(r'(?<!\w)交易(?!\w)', '提交易', query)
    
    return query
```
**预期效果**：减少语义漂移，保留用户意图线索，召回率提升5-8%  
**风险**：标记增加查询长度可能影响检索效率；语义校验增加计算延迟（约10ms）

#### 1.2 融合策略缺陷（`fusion.py`）
**文件修改**：`fusion.py`（第30行、第80行）  
**修改方法**：
```python
# 1. 调整RRF k值
RRF_K = 15  # 从60改为15

# 2. 动态权重计算
def calculate_weights(query_type):
    if query_type == "regulations":
        return (0.60, 0.40)  # 法规集合侧重语义
    else:
        return (0.75, 0.25)  # 其他集合侧重关键词

# 3. 增强Boost规则
def apply_boost(result, query):
    boost = 1.0
    if query in result["content"] and result["chunk_type"] == "law":
        boost *= 1.5  # 法规关键词匹配增强
    return boost
```
**预期效果**：融合结果相关性提升，NDCG@10提升0.15  
**风险**：动态权重需要历史数据支持，初期可能不稳定；复杂规则增加维护成本

#### 1.3 Parent Context扩展问题（`

---

### ② Hybrid设计问题整改建议

#### 1. 固定权重分配
- **文件**：`fusion.py`
- **行号**：权重返回的行（约第150-180行）
- **怎么改**：
  - 实现动态权重调整机制，基于历史查询效果和集合特性
  - 添加权重配置管理器，支持按查询类型、集合类型动态调整
  - 示例修改：
    ```python
    class AdaptiveWeightManager:
        def get_weights(self, query_type, collection_type):
            # 基于历史效果和集合特性动态计算权重
            if collection_type == "regulations":
                return (0.80, 0.20)  # 法规更注重关键词匹配
            elif collection_type == "bids":
                return (0.50, 0.50)  # 招标更注重语义理解
            return (0.75, 0.25)  # 默认值
    ```
- **预期效果**：提高融合效果，适应不同查询类型和集合特性
- **风险**：需要历史数据支持，可能引入新的偏差，需要A/B测试验证

#### 2. RRF与WeightedFusion割裂
- **文件**：`fusion.py`
- **行号**：融合策略选择逻辑（约第200-250行）
- **怎么改**：
  - 实现混合策略，允许RRF和WeightedFusion同时使用
  - 添加融合效果评估机制，基于NDCG、MRR等指标
  - 示例修改：
    ```python
    class HybridFusion:
        def __init__(self):
            self.rrf_weight = 0.5
            self.weighted_weight = 0.5
            self.performance_tracker = PerformanceTracker()
        
        def fuse(self, results):
            # 同时执行RRF和WeightedFusion
            rrf_results = self.rrf_fuse(results)
            weighted_results = self.weighted_fuse(results)
            # 根据历史效果调整权重
            self.adjust_weights()
            # 加权合并结果
            return self.merge_results(rrf_results, weighted_results)
    ```
- **预期效果**：提高融合效果，自动选择最优策略组合
- **风险**：增加系统复杂度，需要额外的计算资源和评估机制

#### 3. Boost规则过于简单
- **文件**：`fusion.py`
- **行号**：Boost规则实现（约第100-140行）
- **怎么改**：
  - 实现多维度Boost规则，考虑语义相似度、权威性、用户偏好
  - 添加Boost规则配置管理器
  - 示例修改：
    ```python
    class AdvancedBoostRule:
        def calculate_boost(self, query, result):
            boost = 1.0
            # 语义相似度Boost
            semantic_sim = self.calculate_semantic_similarity(query, result)
            boost += semantic_sim * 0.3
            # 权威性Boost（法规层级）
            authority_boost = self.get_authority_boost(result)
            boost += authority_boost * 0.2
            # 用户偏好Boost
            user_pref_boost = self.get_user_preference_boost(query, result)
            boost += user_pref_boost * 0.1
            return boost
    ```
- **预期效果**：提高结果相关性，考虑更多维度的影响
- **风险**：规则复杂度增加，可能引入新的偏差，需要仔细调参

### ③ Rewrite设计问题整改建议

#### 1. 同义词扩展歧义
- **文件**：`preprocessor.py`
- **行号**：同义词扩展逻辑（约第50-80行）
- **怎么改**：
  - 添加语义强度标记和验证机制
  - 实现同义词扩展后的语义一致性检查
  - 示例修改：
    ```python
    class SemanticAwareSynonymExpander:
        def __init__(self):
            self.synonym_strength = {
                "围标": {"串标": 0.9, "串通投标": 0.8},  # 语义强度0-1
                "资质": {"资格": 0.7, "资信": 0.5}
            }
        
        def expand(self, word):
            expansions = []
            for synonym, strength in self.synonym_strength.get(word, {}).items():
                if strength > 0.7:  # 高强度同义词
                    expansions.append(synonym)
            return expansions
        
        def validate_semantic_consistency(self, original, expanded):
            # 使用语义模型验证一致性
            return self.semantic_model.similarity(original, expanded) > 0.8
    ```
- **预期效果**：减少歧义，提高改写质量
- **风险**：需要额外的语义模型支持，可能增加计算开销

#### 2. 冗余去除粗暴
- **文件**：`preprocessor.py`
- **行号**：冗余去除逻辑（约第90-120行）
- **怎么改**：
  - 实现上下文感知的冗余去除
  - 添加礼貌用语保留机制
  - 示例修改：
    ```python
    class ContextAwareRedundancyRemover:
        def __init__(self):
            self.pleasantry_patterns = ["请问", "我想知道", "麻烦告诉我"]
            self.context_important_words = ["这个", "那个", "上述"]
        
        def remove_redundancy(self, query, context):
            # 保留礼貌用语
            for pattern in self.pleasantry_patterns:
                if pattern in query:
                    return query  # 保留原始查询
            
            # 检查上下文重要词
            for word in self.context_important_words:
                if word in query:
                    # 保留上下文相关部分
                    return self.preserve_context_relevant(query, context)
            
            # 正常冗余去除
            return self.normal_remove(query)
    ```
- **预期效果**：保留重要意图，提高查询质量
- **风险**：规则复杂度增加，可能引入新的问题

#### 3. 条款号规范化缺陷
- **文件**：`preprocessor.py`
- **行号**：条款号处理逻辑（约第130-160行）
- **怎么改**：
  - 扩展条款号匹配规则，覆盖多种变体
  - 完善中文数字转换，支持大数
  - 示例修改：
    ```python
    class ClauseNumberNormalizer:
        def __init__(self):
            self.patterns = [
                r"第(\d+)条",
                r"第(\d+)款",
                r"第(\d+)项",
                r"第([一二三四五六七八九十百千万]+)条"
            ]
        
        def normalize(self, text):
            for pattern in self.patterns:
                matches = re.findall(pattern, text)
                for match in matches:
                    # 处理中文数字
                    if any(char in match for char in "一二三四五六七八九十百千万"):
                        arabic = self.chinese_to_arabic(match)
                        text = text.replace(match, str(arabic))
                    # 统一为"第X条"格式
                    text = re.sub(pattern, f"第{match}条", text)
            return text
        
        def chinese_to_arabic(self, chinese_num):
            # 实现中文数字到阿拉伯数字的转换
            conversion_map = {"一": 1, "二": 2, "十": 10, "百": 100, "千": 1000, "万": 10000}
            # 实现转换逻辑
            return sum(conversion_map.get(char, 0) for char in chinese_num)
    ```
- **预期效果**：提高条款号识别准确率，支持多种格式
- **风险**：规则复杂度增加，可能引入新的匹配问题

### ④ Parent Context问题整改建议

#### 1. 新旧路径冲突
