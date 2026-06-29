# ian_V4 / R3_weighted_dense_heavy — Weighted 调参

## 改动内容

1. `config.yaml`: `fusion_strategy: "weighted"`
2. `fusion.py`: `_get_dynamic_weights()` 改为从 config.yaml 读取权重（之前硬编码）
3. balanced 权重: `[0.65, 0.35]` → `[0.40, 0.60]`（dense-heavy，适配 BGE-M3 1024d）

## 评测结果

| 指标 | R1（RRF + rerank 1.5x） | R3（Weighted dense-heavy） | 对比 |
|:----|:---:|:---:|:---:|
| exact_hit@5 | **82.4%** | **77.5%** | -4.9% |
| parent_hit@5 | 89.2% | 85.3% | -3.9% |
| Miss | 6/102 | 8/102 | +2 |

## 结论

**Weighted 策略在本次数据上始终不如 RRF。** 两种权重（默认 0.65/0.35、dense-heavy 0.40/0.60）均止步 77.5%。

可能原因：
- RRF 是纯排序融合，不受分数分布影响，更鲁棒
- Weighted 的 Min-Max 归一化在小数据集 / 高分集中时会压缩差异
- boost/penalty 表虽然是领域知识，但可能过度干扰了排序

## 当前最优配置

```
fusion_strategy: "rrf"        # ← 已回退
rerank: article_id boost 1.5x  # ← 保留
```

| 版本 | 策略 | exact_hit@5 |
|:---|:-----|:--------:|
| V4基线 | RRF | 74.5% |
| R1 | RRF + rerank 1.5x | **82.4%** |
| R2 | Weighted (balanced 0.65/0.35) | 77.5% |
| R3 | Weighted (balanced 0.40/0.60) | 77.5% |
