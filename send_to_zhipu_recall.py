#!/usr/bin/env python3
"""发送 miss 样本 + chunk 内容 + 关键代码到智谱，获取召回优化建议"""
import json, httpx, os, sys

# ---- 读取 miss samples ----
samples_path = 'E:/BID_3_PROJECT_langchain/data/eval_questions/v7/v7_miss_samples_chunks.json'
with open(samples_path, 'r', encoding='utf-8') as f:
    samples = json.load(f)

# ---- 读取关键代码 ----
base = 'E:/BID_3_PROJECT_langchain'
code_files = {}
for fpath in ['app/pipeline/fusion.py', 'app/pipeline/retrievers.py', 'app/pipeline/preprocessor.py',
              'app/pipeline/rerankers.py', 'app/pipeline/expanders.py',
              'app/core/legal_entity_registry.py', 'app/core/query_rewriter.py']:
    with open(f'{base}/{fpath}', 'r', encoding='utf-8') as f:
        code_files[fpath] = f.read()

# ---- 统计摘要 ----
stats = '''## Miss 分布统计 (共884条 / 4906题, R@5=82.0%)

### 按 chunk_type
pdf_law_parent: 304 (34.4%) — 法条父块丢失最严重
pdf_case_paragraph: 241 (27.3%)
pdf_law_child: 189 (21.4%)
policy_doc: 77 (8.7%)
pdf_case_sliding: 70 (7.9%)
opinion_news: 3 (0.3%)

### 按 question_type
scenario_judgment: 248, condition_check: 212, procedure: 128, definition: 112
responsibility: 90, case_reasoning: 35, announcement_interpretation: 30, comparison: 29

### 按 difficulty
synonym: 729 (82.5%) — 同义词改写导致丢失占绝对多数
direct: 145 (16.4%)
scenario: 10

### 按 span
single: 544 (61.5%) — 单chunk内能直接找到答案但仍miss
cross_chunk: 277 (31.3%) — 需要跨chunk
cross_doc: 63 (7.1%)

### 各阶段 Recall (全程4906题)
Dense only: 69.7% → BM25 only: 70.6% → Fused: 71.0% → Parent: 71.0% → Reranker: 82.0%
'''

# ---- 构建 prompt ----
prompt = f'''你是 RAG 检索系统专家。我正在优化一个招投标法规智能问答系统的召回率。

## 当前系统架构
- Dense Retrieval: BGE-M3 embedding (1024维), 从 Milvus 召回 top-50
- BM25: 本地 jieba 分词, 召回 top-50
- Fusion: Weighted Fusion (Min-Max 归一化 + 动态权重 + 法条实体 Boost)
- Expansion: Parent Context (child chunk 查找 parent 补充完整法条)
- Reranker: BGE-Reranker-v2-M3 精排至 top-5
- Query Rewrite: 口语→书面语 + 法条号规范化 + 法规名保护（同义词扩展已禁用）

## 评测数据
评测集: 4906 题, 按 ID 匹配评测
最终 Recall@5 = 82.0%
未命中: 884 题

## Miss 统计摘要
{stats}

## 30条 Miss 样本（含 expected chunk 和 top-1 实际返回的chunk内容）
{json.dumps(samples[:30], ensure_ascii=False, indent=2)}

## 关键代码文件

### fusion.py (加权融合核心)
<file>app/pipeline/fusion.py</file>
<code>
{code_files['app/pipeline/fusion.py']}
</code>

### retrievers.py (双路召回)
<file>app/pipeline/retrievers.py</file>
<code>
{code_files['app/pipeline/retrievers.py']}
</code>

### rerankers.py (精排)
<file>app/pipeline/rerankers.py</file>
<code>
{code_files['app/pipeline/rerankers.py']}
</code>

### expanders.py (Parent扩展)
<file>app/pipeline/expanders.py</file>
<code>
{code_files['app/pipeline/expanders.py']}
</code>

### legal_entity_registry.py (法条实体识别)
<file>app/core/legal_entity_registry.py</file>
<code>
{code_files['app/core/legal_entity_registry.py']}
</code>

### query_rewriter.py (查询改写)
<file>app/core/query_rewriter.py</file>
<code>
{code_files['app/core/query_rewriter.py']}
</code>

### preprocessor.py (预处理)
<file>app/pipeline/preprocessor.py</file>
<code>
{code_files['app/pipeline/preprocessor.py']}
</code>

---

## 请诊断并给出提高召回率的建议

请重点关注:
1. 为什么 synonym (同义词改写) 类问题占 miss 的 82.5%？query改写层有没有问题？
2. pdf_law_child 的 Recall@5 仅 55% — 法条子片段为什么最难召回？Parent expansion 为什么零贡献？
3. Weighted Fusion 后 recall 从 BM25 的 70.6% 降到 71.0%（基本没提升），融合策略有什么问题？
4. single span (单chunk可答) 占 miss 的 61.5% — 这些应该最容易命中但反而丢了，根因是什么？
5. 对比现有的 miss case 样本，expected chunk 和 top1 chunk 之间有什么规律性差异？
6. 给出 3-5 条可落地的提高召回率的改造建议，按优先级排序。

请用中文回答，每条建议给出具体方向，不要泛泛而谈。'''

print(f'Prompt length: {len(prompt)} chars')

# ---- 调用智谱 ----
api_key = os.environ.get('ZHIPU_API_KEY', '')
if not api_key:
    api_key = os.environ.get('ZHIPU_KEY', '')
if not api_key:
    print('ERROR: ZHIPU_API_KEY not set')
    print('Trying to read from .env...')
    env_path = 'E:/BID_3_PROJECT_langchain/.env'
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('ZHIPU') and '=' in line:
                    key, val = line.split('=', 1)
                    if 'API' in key or 'KEY' in key:
                        api_key = val.strip().strip('"').strip("'")
                        break
    if not api_key:
        print('Still no key found')
        sys.exit(1)

print(f'Using API key: {api_key[:8]}...')

payload = {
    'model': 'glm-4.5-flash',
    'messages': [
        {'role': 'system', 'content': '你是 RAG 检索系统专家，请认真分析数据并给出具体建议。'},
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
print()

# 保存
out_path = 'E:/BID_3_PROJECT_langchain/docs/code_review/recall_improvement_zhipu.md'
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(f'# 智谱召回优化建议\n\n')
    f.write(f'Token usage: {usage}\n\n---\n\n')
    f.write(content)
print(f'Saved to {out_path}')
print()
print('=' * 60)
print(content)
