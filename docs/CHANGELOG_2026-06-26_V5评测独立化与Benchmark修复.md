# CHANGELOG 2026-06-26 — V5 召回评测独立化

## 召回率计算修复
- 修复 `eval_retrieval_v5.py` 中 Recall@1/@3/@5 全相同的 bug：`if hit_rank >= 1` → `if/elif/elif/else` 分支

## Benchmark 脏数据修复 (670+ 错误 ID)
- **根因**: LLM 生成 QA 时篡改了 chunk_id 中的 law_name（不遵守 20 字符截断规则）
- `fix_eval_benchmark_ids.py`: 后缀匹配修复 44 条
- `fix_remaining_ids.py`: (law_name, article_id) 匹配修复 10 条
- `gen_eval_benchmark_v5.py`: 三种生成方法全部改为直接取 chunk.get("id")，不信任 LLM 返回
- 最终验证：2174 条 expected_chunk_id 全部有效

## 服务器端独立评测
- 编写 `eval_standalone.py`：纯 httpx + numpy，零项目依赖
- 直连 localhost:8210 (embedding+reranker) + localhost:19531 (Milvus)
- RRF 融合 + BGE-Reranker 精排，3 并发 ThreadPoolExecutor
- 部署到 `47.117.173.99:~/eval_v5/`，screen:eval_v5 运行
- 2174 题，3 并发，约 1 秒/题，ETA 40 分钟

## 新增文件
- `eval_standalone.py` — 独立评测脚本
- `fix_eval_benchmark_ids.py` — Benchmark ID 修复（后缀匹配）
- `fix_remaining_ids.py` — 剩余 ID 修复（法条名+条号匹配）
- `find_duplicates.py` — 精准去重分析（最终确认无需要删除的重复 chunk）
