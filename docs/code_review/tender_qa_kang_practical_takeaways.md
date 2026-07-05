# KANG 项目实用建议：能学什么、能用什么

> 模型: glm-4.5-flash | Token: prompt=2330, completion=4096

---

# tender-qa-rag-KANG 项目实用建议

## 1. 可直接借鉴的设计（按投入产出比排序）

### 1.1 Quick Response 预分类器（投入产出比最高）
**移植价值**：实现简单，效果立竿见影，能显著提升用户体验
**具体移植方案**：
```python
# 在现有项目入口处添加快速响应分类器
from typing import Optional
from pydantic import BaseModel

class QuickResponse(BaseModel):
    intent: Optional[str] = None
    response: Optional[str] = None

def quick_response_classifier(query: str) -> QuickResponse:
    # 使用轻量级模型或规则判断社交意图
    if any(greeting in query.lower() for greeting in ["你好", "hi", "hello"]):
        return QuickResponse(intent="greeting", response="您好！我是招投标法规智能助手，很高兴为您服务。")
    # 添加更多社交意图判断...
    return QuickResponse()

# 在主入口调用
def process_query(query: str):
    quick_resp = quick_response_classifier(query)
    if quick_resp.response:
        return quick_resp.response
    # 否则进入正常检索流程
    return normal_rag_pipeline(query)
```

### 1.2 统一模型抽象层
**移植价值**：提高代码复用性，便于切换模型和添加新模型
**具体移植方案**：
```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any
import openai
from transformers import AutoTokenizer, AutoModelForCausalLM

class BaseChatModel(ABC):
    @abstractmethod
    def generate(self, messages: List[Dict[str, str]], **kwargs) -> str:
        pass
    
    @abstractmethod
    def generate_structured(self, messages: List[Dict[str, str]], schema: Dict, **kwargs) -> Dict:
        pass

class OpenAIModel(BaseChatModel):
    def __init__(self, model_name="gpt-3.5-turbo"):
        self.client = openai.OpenAI()
        self.model_name = model_name
    
    def generate(self, messages: List[Dict[str, str]], **kwargs) -> str:
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            **kwargs
        )
        return response.choices[0].message.content

class HuggingFaceModel(BaseChatModel):
    def __init__(self, model_name, device="cuda", max_new_tokens=512):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(model_name).to(device)
        self.device = device
        self.max_new_tokens = max_new_tokens
    
    def generate(self, messages: List[Dict[str, str]], **kwargs) -> str:
        # 实现本地模型调用逻辑
        pass
```

### 1.3 Self-RAG 循环检索机制
**移植价值**：解决当前检索一次性导致的信息不足问题
**具体移植方案**：
```python
def self_rag_retrieve(query: str, initial_results: List[Dict], max_rounds=2) -> List[Dict]:
    results = initial_results
    for round_num in range(max_rounds):
        # 评估当前结果质量
        assessment = assess_retrieval_quality(query, results)
        
        if assessment.sufficient:
            break
            
        # 根据评估结果生成新的查询
        refined_query = refine_query_based_on_assessment(query, results, assessment)
        
        # 执行新的检索
        new_results = retrieve_with_query(refined_query)
        
        # 融合新旧结果
        results = merge_and_deduplicate(results + new_results)
    
    return results

def assess_retrieval_quality(query: str, results: List[Dict]) -> RetrievalAssessment:
    # 使用模型评估检索结果是否足够回答问题
    prompt = f"""
    问题: {query}
    检索结果: {results}
    请评估这些检索结果是否足够回答上述问题。
    如果足够，请回复"sufficient"；如果不足，请指出缺少哪些关键信息。
    """
    response = chat_model.generate([{"role": "user", "content": prompt}])
    return parse_assessment(response)
```

### 1.4 混合检索策略（向量+BM25）
**移植价值**：解决同义词miss问题，提高召回率
**具体移植方案**：
```python
class HybridRetriever:
    def __init__(self, vector_store, bm25 retriever, fusion_method="rrf"):
        self.vector_store = vector_store
        self.bm25_retriever = bm25_retriever
        self.fusion_method = fusion_method
    
    def retrieve(self, query: str, top_k=10) -> List[Dict]:
        # 向量检索
        vector_results = self.vector_store.search(query, top_k=top_k)
        
        # BM25检索
        bm25_results = self.bm25_retriever.get_scores(query)
        
        # 结果融合
        if self.fusion_method == "rrf":
            return self.reciprocal_rank_fusion(vector_results, bm25_results, top_k)
        else:
            return self.weighted_average(vector_results, bm25_results, top_k)
    
    def reciprocal_rank_fusion(self, vector_results, bm25_results, top_k):
        # 实现RRF融合算法
        fused_scores = {}
        for rank, doc in enumerate(vector_results):
            doc_id = doc["id"]
            fused_scores[doc_id] = fused_scores.get(doc_id, 0) + 1/(60 + rank)
        
        for rank, doc in enumerate(bm25_results):
            doc_id = doc["id"]
            fused_scores[doc_id] = fused_scores.get(doc_id, 0) + 1/(60 + rank)
        
        # 按融合分数排序
        sorted_docs = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
        return [doc for doc, _ in sorted_docs[:top_k]]
```

### 1.5 ChildTask DAG 调度器（投入产出比最低）
**移植价值**：解决复杂问题分解，但实现复杂度较高
**具体移植方案**：
```python
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
import asyncio
from enum import Enum

class TaskStatus(Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"

@dataclass
class ChildTask:
    id: str
    category: str
    query: str
    depends_on: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict] = None
    error: Optional[str] = None

class TaskDAGScheduler:
    def __init__(self):
        self.tasks: Dict[str, ChildTask] = {}
        self.graph: Dict[str, List[str]] = {}
    
    def add_task(self, task: ChildTask):
        self.tasks[task.id] = task
        for dep in task.depends_on:
            if dep not in self.graph:
                self.graph[dep] = []
            self.graph[dep].append(task.id)
    
    async def execute(self, task_executor):
        # 初始化任务状态
        for task in self.tasks.values():
            if not task.depends_on:
                task.status = TaskStatus.READY
        
        # 执行循环
        while True:
            ready_tasks = [t for t in self.tasks.values() if t.status == TaskStatus.READY]
            if not ready_tasks:
                break
                
            # 并发执行就绪任务
            tasks = []
            for task in ready_tasks:
                task.status = TaskStatus.RUNNING
                tasks.append(self._execute_task(task, task_executor))
            
            await asyncio.gather(*tasks)
    
    async def _execute_task(self, task: ChildTask, task_executor):
        try:
            result = await task_executor(task)
            task.result = result
            task.status = TaskStatus.COMPLETED
            
            # 更新依赖此任务的其他任务
            for dependent_id in self.graph.get(task.id, []):
                dependent = self.tasks[dependent_id]
                if all(self.tasks[dep_id].status == TaskStatus.COMPLETED 
                      for dep_id in dependent.depends_on):
                    dependent.status = TaskStatus.READY
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
```

## 2. 不建议照搬的设计

### 2.1 四进程架构
**原因**：
- 当前项目规模可能不需要如此复杂的进程隔离
- 进程间通信会增加系统复杂度和延迟
- 投入产出比低，维护成本高

**替代方案**：
保持现有的单进程架构，通过模块化设计实现关注点分离，使用依赖注入管理组件间关系。

### 2.2 LangGraph 状态机
**原因**：
- 对于当前项目，LangGraph的学习曲线较陡
- 增加了额外的依赖和复杂性
- 当前业务逻辑可能不需要如此复杂的状态管理

**替代方案**：
使用简单的状态管理类或状态机库，如Python内置的enum或轻量级状态机库。

### 2.3 完整的问题分解机制
**原因**：
- 实现复杂度高，需要大量调试和优化
- 当前项目的主要痛点是召回率问题，而非问题理解
- 可能引入不必要的复杂性

**替代方案**：
先实现简单的问题分类，根据实际需求逐步增加问题分解的复杂度。

## 3. ReActAgent 改造路径

### 渐进式升级方案

#### 第一阶段：添加问题分类能力
```python
class EnhancedReActAgent:
    def __init__(self):
        self.query_classifier = QueryClassifier()
        self.simple_agent = SimpleReActAgent()
        self.decomposition_agent = TaskDecompositionAgent()
    
    async def run(self, query: str):
        # 1. 问题分类
        query_type = self.query_classifier.classify(query)
        
        if query_type == "simple":
            # 简单问题直接使用现有ReActAgent
            return await self.simple_agent.run(query)
        elif query_type == "complex":
            # 复杂问题进入分解流程
            return await self.decomposition_agent.run(query)
        else:
            # 默认处理
            return await self.simple_agent.run(query)
```

#### 第二阶段：实现简单问题分解
```python
class TaskDecompositionAgent:
    def __init__(self):
        self.subtask_generator = SubtaskGenerator()
        self.subtask_executor = SubtaskExecutor()
    
    async def run(self, query: str):
        # 1. 生成子任务
        subtasks = await self.subtask_generator.generate(query)
        
        # 2. 执行子任务（简单串行执行）
        results = []
        for subtask in subtasks:
            result = await self.subtask_executor.execute(subtask)
            results.append(result)
        
        # 3. 融合结果
        return self.merge_results(results)
```

#### 第三阶段：实现DAG调度
```python
class DAGTaskDecompositionAgent:
    def __init__(self):
        self.task_generator = TaskGenerator()
        self.dag_scheduler = TaskDAGScheduler()
        self.result_merger = ResultMerger()
    
    async def run(self, query: str):
        # 1. 生成任务图
        tasks = await self.task_generator.generate(query)
        dag = self.build_dag(tasks)
        
        # 2. 执行DAG
        results = await self.dag_scheduler.execute(dag, self.execute_task)
        
        # 3. 融合结果
        return self.result_merger.merge(results)
    
    def build_dag(self, tasks):
        # 构建任务依赖图
        dag = TaskDAGScheduler()
        for task in tasks:
            dag.add_task(task)
        return dag
    
    async def execute_task(self, task):
        # 执行单个任务
        if task.type == "retrieval":
            return await self.execute_retrieval(task)
        elif task.type == "reasoning":
            return await self.execute_reasoning(task)
        # 其他任务类型...
```

## 4. Self-RAG 循环检索嵌入方案

### 在现有5阶段管线中嵌入Self-RAG

```python
class EnhancedRetrievalPipeline:
    def __init__(self):
        self.original_pipeline = OriginalRetrievalPipeline()
        self.assessor = RetrievalQualityAssessor()
        self.query_refiner = QueryRefiner()
    
    async def run(self, query: str):
        # 第一阶段：初始检索
        initial_results = await self.original_pipeline.run(query)
        
        # 评估检索质量
        assessment = await self.assessor.assess(query, initial_results)
        
        if assessment.sufficient:
            return initial_results
        
        # 第二阶段：基于评估结果改进查询
        refined_query = await self.query_refiner.refine(query, initial_results, assessment)
        
        # 第三阶段：使用改进的查询再次检索
        additional_results = await self.original_pipeline.run(refined_query)
        
        # 第四阶段：融合结果
        final_results = self.fuse_results(initial_results, additional_results)
        
        return final_results
```

### 具体实现组件

```python
class RetrievalQualityAssessor:
    def __init__(self, model):
        self.model = model
    
    async def assess(self, query: str, results: List[Dict]) -> Assessment:
        prompt = f"""
        问题: {query}
        检索结果: {results}
        请评估这些检索结果是否足够回答上述问题。
        评估维度:
        1. 相关性: 结果是否与问题相关
        2. 完整性: 是否覆盖了问题的所有方面
        3. 时效性: 信息是否是最新的
        4. 权威性: 信息来源是否可靠
        
        请给出评估结果，包括:
        - 是否足够回答问题 (sufficient/insufficient)
        - 缺失的关键信息 (如有时)
        - 改进建议 (如有时)
        """
        
        response = await self.model.generate(prompt)
        return self.parse_assessment(response)
    
    def parse_assessment(self, response: str) -> Assessment:
        # 解析模型输出，返回结构化评估结果
        pass

class QueryRefiner:
    def __init__(self, model):
        self.model = model
    
    async def refine(self, original_query: str, results: List[Dict], assessment: Assessment) -> str:
        prompt = f"""
        原始查询: {original_query}
        检索结果: {results}
        评估结果: {assessment}
        
        根据评估结果，请改进查询以获取更相关的信息。
        改进方向:
        1. 添加缺失的关键词
        2. 使用更精确的术语
        3. 调整查询焦点
        
        请返回改进后的查询。
        """
        
        response = await self.model.generate(prompt)
        return response.strip()
```

## 5. 短期可落地的前3个改进建议

### 5.1 实施混合检索策略（解决同义词miss问题）
**具体步骤**：
1. 集成BM25检索器到现有ChromaDB存储
2. 实现向量检索和BM25检索的RRF融合算法
3. 添加检索结果质量评估机制
4. 根据评估结果动态调整融合权重

**预期效果**：R@5召回率从82%提升至88-90%
**实施周期**：2-3周

```python
# 实现示例
class HybridRetrievalSystem:
    def __init__(self, chroma_db, bm25_index):
        self.chroma_db = chroma_db
        self.bm25_index = bm25_index
        self.vector_weight = 0.6  # 可调整
        self.bm25_weight = 0.4
    
    def search(self, query: str, top_k=10):
        # 向量检索
        vector_results = self.chroma_db.query(query, n_results=top_k)
        
        # BM25检索
        bm25_results = self.bm25_index.search(query, k=top_k)
        
        # 融合结果
        fused_results = self.fuse_results(vector_results, bm25_results)
        
        # 评估融合结果质量
        quality = self.assess_quality(query, fused_results)
        
        # 根据质量调整权重（动态调整）
        if quality < 0.7:  # 质量较低，增加BM25权重
            self.vector_weight = 0.5
            self.bm25_weight = 0.5
            fused_results = self.fuse_results(vector_results, bm25_results)
        
        return fused_results[:top_k]
```

### 5.2 实施Self-RAG循环检索机制（解决信息不足问题）
**具体步骤**：
1. 设计检索结果质量评估指标
2. 实现查询改进算法
3. 在现有检索管线中添加循环逻辑
4. 设置最大循环次数避免无限循环

**预期效果**：答案准确率提升15-20%，减少"信息不足"的情况
**实施周期**：3-4周

```python
class SelfRAGRetriever:
    def __init__(self, base_retriever, max_rounds=2):
        self.base_retriever = base_retriever
        self.max_rounds = max_rounds
        self.quality_threshold = 0.75
    
    async def retrieve(self, query: str):
        results = []
        current_query = query
        
        for round_num in range(self.max_rounds):
            # 执行检索
            round_results = await self.base_retriever.retrieve(current_query)
            results.extend(round_results)
            
            # 评估结果质量
            quality = await self.assess_quality(query, results)
            
            if quality >= self.quality_threshold:
                break
                
            # 改进查询
            current_query = await self.refine_query(query, results, quality)
        
        # 去重和排序
        return self.deduplicate_and_rank(results)
    
    async def assess_quality(self, query: str, results: List[Dict]) -> float:
        # 实现质量评估逻辑
        pass
    
    async def refine_query(self, original_query: str, results: List[Dict], quality: float) -> str:
        # 实现查询改进逻辑
        pass
```

### 5.3 实施快速响应预分类器（提升用户体验）
**具体步骤**：
1. 收集和分析用户常见社交意图
2. 实现轻量级分类器（规则+小模型）
3. 为每种意图设计标准回复
4. 在系统入口集成