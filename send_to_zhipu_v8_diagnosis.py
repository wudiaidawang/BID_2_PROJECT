#!/usr/bin/env python3
"""发送 V8 评测结果 + 检索策略 + miss 样本到智谱，获取完整诊断报告"""
import json, httpx, os, sys, yaml

# ── 1. 读取 V8 评测报告（摘要）──
with open('E:/BID_3_PROJECT_langchain/data/eval_questions/v8/v8_recall_report.md', 'r', encoding='utf-8') as f:
    report_md = f.read()[:8000]

# ── 2. 读取 miss 样本 ──
with open('E:/BID_3_PROJECT_langchain/data/eval_questions/v8/v8_recall_report.misses.json', 'r', encoding='utf-8') as f:
    misses = json.load(f)

# ── 3. 读取关键代码 ──
code_files = {}
base = 'E:/BID_3_PROJECT_langchain'
for fpath in [
    'eval_standalone.py',
    'app/pipeline/fusion.py',
    'app/pipeline/retrievers.py',
    'app/pipeline/rerankers.py',
    'app/pipeline/expanders.py',
    'app/core/legal_entity_registry.py',
    'app/core/query_rewriter.py',
    'app/core/parent_chunk_builder.py',
    'app/core/child_chunk_builder.py',
]:
    full = f'{base}/{fpath}'
    if os.path.exists(full):
        with open(full, 'r', encoding='utf-8') as f:
            code_files[fpath] = f.read()
        print(f'  Read {fpath}: {len(code_files[fpath])} chars')

# ── 4. 读取 config.yaml 检索相关部分 ──
with open(f'{base}/config.yaml', 'r', encoding='utf-8') as f:
    full_cfg = f.read()
# extract retrieval section only
import re
cfg_section = re.search(r'(# -+\s*\n# 5\. 检索配置.*?)(?=# -+\s*\n# \d+\.)', full_cfg, re.DOTALL)
retrieval_config = cfg_section.group(1) if cfg_section else full_cfg[2800:3800]
reranker_section = re.search(r'(# -+\s*\n# 4\. Reranker.*?)(?=# -+\s*\n# \d+\.)', full_cfg, re.DOTALL)
reranker_config = reranker_section.group(1) if reranker_section else ""

# ── 5. Miss 统计分析 ──
from collections import Counter
miss_by_type = Counter(m.get('type','?') for m in misses)
miss_by_qtype = Counter(m.get('question_type','?') for m in misses)
miss_by_diff = Counter(m.get('retrieval_difficulty','?') for m in misses)
miss_by_span = Counter(m.get('span','?') for m in misses)

# 统计 top1 miss 到哪个 chunk
top1_ids = [m.get('top1_id','') for m in misses if m.get('top1_id')]
top1_counter = Counter(top1_ids)
recurring_top1 = top1_counter.most_common(10)

# 相似 miss 聚类（相同 question 文本的变体）
question_counts = Counter(m.get('question','') for m in misses)
dup_questions = [(q, c) for q, c in question_counts.most_common(15) if c >= 2]

stats = f'''## Miss 详细统计 (共 {len(misses)} 条 / 3146 题, R@5=88.8%)

### 按 chunk_type
{json.dumps(dict(miss_by_type), ensure_ascii=False, indent=2)}

### 按 question_type
{json.dumps(dict(miss_by_qtype), ensure_ascii=False, indent=2)}

### 按 retrieval_difficulty
{json.dumps(dict(miss_by_diff), ensure_ascii=False, indent=2)}

### 按 span
{json.dumps(dict(miss_by_span), ensure_ascii=False, indent=2)}

### 高频 miss top1 目标 (说明这些 chunk 被错误召回最多)
{json.dumps(recurring_top1, ensure_ascii=False, indent=2)}

### 重复 miss 问题 (相同问题多次 miss)
{json.dumps(dup_questions, ensure_ascii=False, indent=2)}
'''

# ── 构建 Prompt ──
prompt = f'''你是 RAG 检索系统专家。我正在优化一个招投标法规智能问答系统的召回率。以下是 V8 评测的完整数据和系统配置，请出具一份全面诊断报告。

## 1. V8 评测结果摘要

{report_md}

## 2. Miss 统计

{stats}

## 3. 前 50 条 Miss 详情

{json.dumps(misses[:50], ensure_ascii=False, indent=2)}

## 4. 当前检索配置

### Reranker 配置
```yaml
{reranker_config}
```

### 检索配置
```yaml
{retrieval_config}
```

## 5. 关键代码

### eval_standalone.py (评测脚本，包含 WeightedFusion 实现)
```python
{code_files['eval_standalone.py'][:8000]}
```

### app/pipeline/fusion.py (生产管线 Fusion)
```python
{code_files['app/pipeline/fusion.py'][:6000]}
```

### app/pipeline/retrievers.py (双路召回)
```python
{code_files['app/pipeline/retrievers.py'][:4000]}
```

### app/pipeline/rerankers.py (精排)
```python
{code_files['app/pipeline/rerankers.py'][:3000]}
```

### app/pipeline/expanders.py (Parent扩展)
```python
{code_files['app/pipeline/expanders.py'][:3000]}
```

### app/core/legal_entity_registry.py (法条实体识别)
```python
{code_files['app/core/legal_entity_registry.py'][:4000]}
```

### app/core/query_rewriter.py (查询改写)
```python
{code_files['app/core/query_rewriter.py'][:3000]}
```

### app/core/child_chunk_builder.py (Child构建 — 刚做同质化治理)
```python
{code_files['app/core/child_chunk_builder.py']}
```

---

## 诊断要求

请深入分析并回答以下问题：

### 1. 融合策略问题 (最紧急)
- BM25 单独 Recall@5=81.0%，Weighted Fusion 后降至 79.3%。融合反而拖累了召回。
- 为什么 BM25 的高分结果在融合阶段被稀释了？
- 动态权重 (regulation: 0.80/0.20, keyword: 0.75/0.25, semantic: 0.40/0.60, default: 0.65/0.35) 是否合理？
- Min-Max 归一化是否导致 BM25 的绝对高分被压低？

### 2. Parent Expansion 零贡献问题
- Fusion 后 79.3%，Parent Expanded 后仍是 79.3%，完全无变化。
- 是 Parent Lookup 没找到父块？还是扩展后的 chunk 没有被 Reranker 选中？
- child_chunk_builder 刚做了同质化治理 (差异化 header + [SEP]分隔)，对扩展逻辑有什么影响？

### 3. Miss 模式分析
- 大量重复 miss: policy_0, policy_125 被反复错误召回作为 top1
- "上海市公共资源交易平台有哪些子平台" 类问题反复 miss
- pdf_law_child 虽然从 V7 的 55% 提升到 79.4%，仍是所有类型最差
- Comparison 类问题 R@5 仅 66.3%，为什么这么低？

### 4. 配置优化建议
- RRF vs Weighted：当前 config.yaml 设的是 rrf，但 eval_standalone 用的是 weighted_fusion。应该统一哪个？
- BM25 参数 (k1=1.2, b=0.75) 是否需要调整？
- Reranker candidate_pool=30，max_input_length=1024 是否需要调整？

### 5. 优先级建议
- 给出 3-5 条可落地改进建议，按 Recall 提升预期排序
- 每条建议给出具体参数调整方案

请用中文回答，数据驱动，不要泛泛而谈。'''

print(f'Prompt length: {len(prompt)} chars')

# ── 获取 API key ──
api_key = os.environ.get('ZHIPU_API_KEY', '') or os.environ.get('ZHIPU_KEY', '')
if not api_key:
    cfg_path = 'E:/BID_3_PROJECT_langchain/config.yaml'
    with open(cfg_path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)
    api_key = cfg.get('llm', {}).get('providers', {}).get('zhipu', {}).get('api_key', '')
    if not api_key:
        print('ERROR: ZHIPU_API_KEY not set')
        sys.exit(1)

# 长 prompt 用 flash 模型
payload = {
    'model': 'glm-4.5-flash',
    'messages': [
        {'role': 'system', 'content': '你是 RAG 检索系统专家和数据分析师。请基于数据给出具体、可操作的诊断建议。用中文回答。'},
        {'role': 'user', 'content': prompt}
    ],
    'max_tokens': 8192,
    'temperature': 0.3,
    'thinking': {'type': 'disabled'}
}

print(f'Sending to Zhipu, prompt={len(prompt)} chars...')
r = httpx.post(
    'https://open.bigmodel.cn/api/paas/v4/chat/completions',
    headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
    json=payload,
    timeout=600
)

resp = r.json()
if 'error' in resp:
    print(f'API ERROR: {resp["error"]}')
    sys.exit(1)

content = resp['choices'][0]['message']['content']
usage = resp.get('usage', {})
print(f'Tokens: prompt={usage.get("prompt_tokens")}, completion={usage.get("completion_tokens")}')

out_path = 'E:/BID_3_PROJECT_langchain/docs/code_review/v8_recall_diagnosis_zhipu.md'
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(f'# 智谱 V8 召回诊断报告\n\n')
    f.write(f'> 模型: glm-4.5-flash | Token: prompt={usage.get("prompt_tokens")}, completion={usage.get("completion_tokens")}\n\n---\n\n')
    f.write(content)
print(f'Saved to {out_path}')
print()
print('=' * 60)
print(content)
