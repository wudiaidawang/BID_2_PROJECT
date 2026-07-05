#!/usr/bin/env python3
"""向智谱追问：针对本项目（BID_3_PROJECT_langchain）的开发者，KANG 项目有什么能学能用的"""
import json, httpx, os, sys, yaml

# 读取智谱上轮的报告
with open('E:/BID_3_PROJECT_langchain/docs/code_review/tender_qa_kang_zhipu_report.md', 'r', encoding='utf-8') as f:
    prev_report = f.read()

# 读取 KANG 项目的关键差异点（简要摘要）
kang_summary = '''
## tender-qa-rag-KANG 与我当前项目 (BID_3_PROJECT_langchain) 的关键差异

### KANG 项目有但我方没有的：
1. **问题分解 (Question Decomposition)**：将复杂问题拆成 ChildTask DAG，支持多步推理和并行执行
2. **LangGraph 状态机**：Policy 工作流用 StateGraph 建模，支持 checkpoint 持久化和条件路由
3. **Self-RAG 循环检索**：检索→评估→不够再检索→再评估，而非一次检索完事
4. **ChildTask DAG 调度器**：异步并发执行独立子任务，依赖任务自动等待
5. **统一模型抽象**：OpenAI API + 本地 HuggingFace 都走 BaseChatModel 接口
6. **Quick Response 预分类**：社交闲聊走快响通道，秒回
7. **四进程架构**：Knowledge Base / Agent / Backend / Frontend 各跑各的
8. **数据领域工作流**：SQL + Website 双源，缺一个不崩，mark 为 unsolved 继续

### 我方项目 (BID_3_PROJECT_langchain) 的特点：
1. **5 阶段检索管线**：预处理 → 双路召回 → 跨库融合 → Parent 扩展 → Reranker 精排
2. **3 种 Router 模式**：Binary / Intent / Planner + 新的 Auto 模式
3. **ReActAgent**：Thought→Action→Observation 循环（但比较简单）
4. **法条实体注册中心**：LegalEntityRegistry + Boost
5. **口语→书面语 + 同义词扩展**：Query Rewriter 三层改写
6. **独立的召回评测体系**：V6/V7 评测，1000+ 题
7. **ChromaDB**（本地文件存储）而非 Milvus

### 我的背景：
- 我在做一个招投标法规智能问答系统
- 当前 R@5 召回率 82%，主要痛点是同义词改写导致的 miss（占 82.5%）
- 现有 ReActAgent 比较简单，没有真正的问题分解和 DAG 调度
- 没有 Self-RAG 循环检索机制
- 检索是一次性的，不会根据结果质量动态调整
'''

prompt = f'''你之前已经对 tender-qa-rag-KANG 项目做了全面解读。现在请针对一位具体的开发者给出实用建议。

## 上轮解读报告回顾
{prev_report[:3000]}

## 该开发者的当前项目情况
{kang_summary}

## 请回答以下问题：

### 1. 哪些设计可以直接借鉴到现有项目？
具体到代码层面，哪些模式/模块可以移植过来。给出 3-5 个最值得借鉴的设计，按投入产出比排序。

### 2. 哪些设计不建议照搬？
KANG 项目中的哪些设计在当前项目场景下可能不适用或过度设计，为什么？

### 3. 如果要引入"问题分解 + DAG 调度"，当前项目的 ReActAgent 怎么改造？
给出具体的改造路径，不要泛泛而谈。当前项目已有 ReActAgent（Thought→Action→Observation 循环），怎么渐进式升级？

### 4. Self-RAG 循环检索在当前检索管线中怎么嵌入？
当前是 5 阶段一次性管线，怎么加入"检索→评估→再检索"的循环而不推倒重来？

### 5. 短期可落地的前 3 个改进建议
针对当前 R@5=82%、同义词 miss 占 82.5% 的痛点，结合 KANG 项目的设计思想，给出 3 条近期可落地的具体改进方案。

请用中文，给出具体、可操作的答案。'''

# ---- 获取 API key ----
api_key = os.environ.get('ZHIPU_API_KEY', '') or os.environ.get('ZHIPU_KEY', '')
if not api_key:
    cfg_path = 'E:/BID_3_PROJECT_langchain/config.yaml'
    if os.path.exists(cfg_path):
        with open(cfg_path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
        api_key = cfg.get('llm', {}).get('providers', {}).get('zhipu', {}).get('api_key', '')

print(f'Prompt length: {len(prompt)} chars')

payload = {
    'model': 'glm-4.5-flash',
    'messages': [
        {'role': 'system', 'content': '你是 RAG 系统和 AI Agent 架构的专家，擅长给出具体、可落地的工程建议。请用中文回答。'},
        {'role': 'user', 'content': prompt}
    ],
    'max_tokens': 4096,
    'temperature': 0.3,
    'thinking': {'type': 'disabled'}
}

print('Sending to Zhipu...')
r = httpx.post(
    'https://open.bigmodel.cn/api/paas/v4/chat/completions',
    headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
    json=payload,
    timeout=300
)

resp = r.json()
if 'error' in resp:
    print(f'API ERROR: {resp["error"]}')
    sys.exit(1)

content = resp['choices'][0]['message']['content']
usage = resp.get('usage', {})
print(f'Tokens: prompt={usage.get("prompt_tokens")}, completion={usage.get("completion_tokens")}')

out_path = 'E:/BID_3_PROJECT_langchain/docs/code_review/tender_qa_kang_practical_takeaways.md'
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(f'# KANG 项目实用建议：能学什么、能用什么\n\n')
    f.write(f'> 模型: glm-4.5-flash | Token: prompt={usage.get("prompt_tokens")}, completion={usage.get("completion_tokens")}\n\n---\n\n')
    f.write(content)
print(f'Saved to {out_path}')
print()
print('=' * 60)
print(content)
