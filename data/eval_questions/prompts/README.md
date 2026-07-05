# Prompt 工程记录

每次 Benchmark QA 生成使用的提示词，在这里做版本化管理。

## 命名规则

`{版本}_prompt.md` — 与 Benchmark 版本一一对应。

## 使用方式

生成脚本自动读取对应版本的 prompt 文件，不硬编码在代码里。

```
prompts/v6_prompt.md  ←  gen_eval_benchmark_v6.py 自动读取
prompts/v7_prompt.md  ←  gen_eval_benchmark_v7.py 自动读取（未来）
```

## 版本索引

| 文件 | Benchmark | 核心改进 |
|------|-----------|---------|
| v6_prompt.md | V6 真实用户风格 | 禁止Chunk改写、减少专有名词、模拟多角色、业务场景化、按Chunk Type差异化、禁止角色前缀和法条号 |
| v7.0_prompt.md | V7.0 Canonical Benchmark | 标准书面语，精准语义匹配，LLM输出7字段(含span)，后处理补id/chunk_type/law_name/benchmark_level/rewrite_group |
| v7.1_prompt.md | V7.1 Natural Query | 基于Canonical改写，轻度口语化+同义词替换，其余字段不变 |
| v7.2_prompt.md | V7.2 Raw Search | 基于Canonical改写，加入搜索噪声+短句+省略，评测Query Rewrite鲁棒性 |

### V7 三级递进体系

```
Chunks → [v7.0] → Canonical (benchmark_level: canonical)
                → [v7.1] → Natural   (benchmark_level: natural)
                → [v7.2] → Raw Search (benchmark_level: robust)
```

Natural 和 Raw Search 均独立基于 Canonical 改写，避免错误传播。
三套通过 `rewrite_group` 关联，合并为统一数据集（JSONL），按 `benchmark_level` 分组评测。
