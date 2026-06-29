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
