# ian_V4 / R4_ef128 — 加 ef=128

## 改动内容

```yaml
milvus:
  search_ef: 128        # 新增，之前未配置（Milvus使用默认ef=top_k）
  # vector_recall: 100   # 未改（保持在50）
  # bm25_recall: 50
```

fusion_strategy: rrf（与R1相同）
rerank: article_id 1.5x boost（与R1相同）

## 评测结果

| 指标 | R1（RRF+rerank 1.5x） | R4（+ef=128） | 变化 |
|:----|:---:|:---:|:---:|
| exact_hit@5 | 82.4%（84/102） | **82.4%**（84/102） | 无变化 |
| parent_hit@5 | 89.2% | 89.2% | 无变化 |
| Miss | 6/102 | 6/102 | 无变化 |

## 结论

ef=128 未带来提升。剩余6个miss不是召回深度问题：

- 3个 law_name 截断 → 入库侧问题
- 3个 跨法混淆 → 正确法律不在top5候选中（ef和召回池不是瓶颈）

## 当前最优配置

```
fusion_strategy: "rrf"
rerank article_id boost: 1.5x
milvus search_ef: 128
vector_recall: 50
bm25_recall: 50
```

## 版本汇总

| 版本 | 改动 | exact_hit@5 | miss |
|:----|:----|:--------:|:----:|
| V4基线 | RRF | 74.5% | 13 |
| R1 | RRF + rerank 1.5x | **82.4%** | 6 |
| R2 | Weighted (0.65/0.35) | 77.5% | 8 |
| R3 | Weighted (0.40/0.60) | 77.5% | 8 |
| R4 | + ef=128 | 82.4% | 6 |
