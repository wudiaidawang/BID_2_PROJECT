#!/usr/bin/env python3
"""发送 tender-qa-rag-KANG 项目代码到智谱，获取项目解读报告"""
import json, httpx, os, sys

base = 'E:/BID_3_PROJECT_langchain/tender-qa-rag-KANG/tender-qa-rag-KANG'

# ---- 读取架构文档 ----
with open(f'{base}/PROJECT_STRUCTURE.md', 'r', encoding='utf-8') as f:
    project_structure = f.read()

with open(f'{base}/change_log.txt', 'r', encoding='utf-8') as f:
    change_log = f.read()

# ---- 读取关键代码文件 ----
code_files = {}
key_files = [
    # 入口
    'main.py',
    # Agent 层核心
    'agent_layer/api.py',
    'agent_layer/app.py',
    'agent_layer/bootstrap.py',
    'agent_layer/schemas.py',
    'agent_layer/config.py',
    'agent_layer/models.py',
    'agent_layer/model_concurrency.py',
    'agent_layer/local_llm.py',
    'agent_layer/checkpoint.py',
    'agent_layer/errors.py',
    # 问题分解
    'agent_layer/question_decomposition/chain.py',
    'agent_layer/question_decomposition/prompts.py',
    # 对话
    'agent_layer/conversation/quick_classifier.py',
    'agent_layer/conversation/quick_responses.py',
    'agent_layer/conversation/fallback_messages.py',
    # 检索适配
    'agent_layer/retrieval/adapter.py',
    'agent_layer/retrieval/client.py',
    'agent_layer/retrieval/pipeline.py',
    'agent_layer/retrieval/chinese_number.py',
    # SQL
    'agent_layer/sql/gateway.py',
    'agent_layer/sql/validator.py',
    'agent_layer/sql/catalog.py',
    'agent_layer/sql/schemas.py',
    # 工作流
    'agent_layer/workflows/policy.py',
    'agent_layer/workflows/policy_graph.py',
    'agent_layer/workflows/data_domain.py',
    'agent_layer/workflows/general.py',
    'agent_layer/workflows/self_rag.py',
    'agent_layer/workflows/common.py',
    'agent_layer/workflows/analysis.py',
    # 领域
    'agent_layer/domains/tender.py',
    'agent_layer/domains/company.py',
    'agent_layer/domains/price.py',
    'agent_layer/domains/product.py',
    'agent_layer/domains/public_opinion.py',
    # 适配器
    'agent_layer/adapters/base.py',
    # 评测
    'agent_layer/evaluation/decomposition.py',
    'agent_layer/evaluation/retrieval.py',
    'agent_layer/evaluation/sql.py',
    # 知识库层
    'knowledge_base_layer/api.py',
    'knowledge_base_layer/service.py',
    'knowledge_base_layer/bootstrap.py',
    'knowledge_base_layer/config.py',
    'knowledge_base_layer/embeddings.py',
    'knowledge_base_layer/rebuild.py',
    # 检索
    'knowledge_base_layer/retrieval/milvus.py',
    'knowledge_base_layer/retrieval/retriever.py',
    'knowledge_base_layer/retrieval/fusion.py',
    'knowledge_base_layer/retrieval/parent_context.py',
    'knowledge_base_layer/retrieval/reranker.py',
    'knowledge_base_layer/retrieval/store.py',
    # 摄入
    'knowledge_base_layer/ingestion/pdf.py',
    'knowledge_base_layer/ingestion/normalizer.py',
    'knowledge_base_layer/ingestion/pipeline.py',
    # 后端层
    'app_backend_layer/api.py',
    'app_backend_layer/config.py',
    'app_backend_layer/api_routes/chat.py',
    'app_backend_layer/api_routes/sessions.py',
    'app_backend_layer/history/history_db.py',
    # 前端层
    'app_frontend_layer/app.py',
    'app_frontend_layer/api_client.py',
    'app_frontend_layer/config.py',
    # 公共
    'common/logger.py',
    'common/api_contracts/agent_api.py',
    'common/api_contracts/backend_api.py',
    'common/api_contracts/knowledge_base_api.py',
]

for fpath in key_files:
    full = f'{base}/{fpath}'
    if os.path.exists(full):
        with open(full, 'r', encoding='utf-8') as f:
            code_files[fpath] = f.read()
    else:
        print(f'WARNING: not found: {fpath}')

# ---- 统计摘要 ----
total_files = len(code_files)
total_lines = sum(len(c.split('\n')) for c in code_files.values())
print(f'Collected {total_files} files, {total_lines} total lines')

# ---- 构建 prompt ----
code_sections = []
for fpath in key_files:
    if fpath in code_files:
        code_sections.append(f'### {fpath}\n```python\n{code_files[fpath]}\n```\n')

code_block = '\n'.join(code_sections)

prompt = f'''你是一位资深的 AI 系统架构师和代码审查专家。请对以下招投标智能问答系统项目进行全面解读，并出具一份详细的项目解读报告。

## 项目概述

项目名: ai-bidding-agent (招投标智能问答系统)
作者: Wang Qingkang
技术栈: Python 3.13+, FastAPI, LangChain/LangGraph, Milvus, Streamlit, Sentence Transformers

## 架构文档

### PROJECT_STRUCTURE.md
{project_structure}

## 完整源代码

{code_block}

## 变更日志 (展示项目演进历史)

{change_log}

---

## 请出具一份全面的项目解读报告，要求：

### 1. 总体架构评价
- 四层架构 (Knowledge Base / Agent / Backend / Frontend) 的设计合理性
- 各层职责划分是否清晰
- 层间通信和 API 契约设计如何

### 2. Agent 层深度分析
- 问题分解 (Question Decomposition) 机制的设计思路和巧妙之处
- ChildTask DAG 调度器的并发执行模型
- Policy Self-RAG + LangGraph 状态机的设计
- 模型抽象层 (OpenAI 兼容 + 本地 HuggingFace) 的统一设计
- 快速响应 (Quick Response) 预分类器的设计

### 3. 知识库层分析
- Milvus 向量存储 + BM25 混合检索的设计
- Parent Context 扩展机制
- Reranker 精排设计
- PDF 摄入和分块策略

### 4. 代码质量评估
- 类型安全 (Pydantic 模型使用)
- 错误处理策略 (fail-fast vs recoverable)
- 依赖注入和可测试性
- 代码组织和模块化

### 5. 项目演进分析
- 从 change_log 分析项目迭代方向
- 识别架构决策的关键转折点
- 评价重构的质量和方向

### 6. 亮点与不足
- 列出项目中值得学习的 5-8 个设计亮点
- 指出 5-8 个潜在问题或改进空间

### 7. 综合评价
- 技术难度评级 (1-10)
- 工程成熟度评级 (1-10)
- 适合什么场景使用
- 如果要继续改进，优先做什么

请用中文回答，给出具体、有深度的分析，不要泛泛而谈。报告要体现对现代 RAG 系统和 Agent 架构的深入理解。'''

print(f'Prompt length: {len(prompt)} chars')

# ---- 调用智谱 ----
api_key = os.environ.get('ZHIPU_API_KEY', '')
if not api_key:
    api_key = os.environ.get('ZHIPU_KEY', '')
if not api_key:
    print('Trying to read from .env...')
    env_path = 'E:/BID_3_PROJECT_langchain/.env'
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('ZHIPU') and '=' in line:
                    key, val = line.split('=', 1)
                    if 'API' in key or 'KEY' in key:
                        api_key = val.strip().strip('"').strip("'")
                        break
    # try config.yaml
    import yaml
    cfg_path = 'E:/BID_3_PROJECT_langchain/config.yaml'
    if os.path.exists(cfg_path):
        with open(cfg_path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
        api_key = cfg.get('llm', {}).get('providers', {}).get('zhipu', {}).get('api_key', '')
    if not api_key:
        print('ERROR: ZHIPU_API_KEY not set')
        sys.exit(1)

print(f'Using API key: {api_key[:8]}...')

# 根据 prompt 长度选模型
if len(prompt) > 80000:
    model = 'glm-4.5-flash'  # 长上下文用 flash 更快
else:
    model = 'glm-4.5-flash'

payload = {
    'model': model,
    'messages': [
        {'role': 'system', 'content': '你是一位资深的 AI 系统架构师和代码审查专家，擅长分析 RAG 系统和 Agent 架构。请用中文给出深度分析。'},
        {'role': 'user', 'content': prompt}
    ],
    'max_tokens': 8192,
    'temperature': 0.3,
    'thinking': {'type': 'disabled'}
}

print(f'Sending to Zhipu ({model}), prompt={len(prompt)} chars...')
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
print()

# 保存
out_path = 'E:/BID_3_PROJECT_langchain/docs/code_review/tender_qa_kang_zhipu_report.md'
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(f'# 智谱解读报告: ai-bidding-agent (tender-qa-rag-KANG)\n\n')
    f.write(f'> 模型: {model} | Token: prompt={usage.get("prompt_tokens")}, completion={usage.get("completion_tokens")}\n\n---\n\n')
    f.write(content)
print(f'Saved to {out_path}')
print()
print('=' * 60)
print(content)
