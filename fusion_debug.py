#!/usr/bin/env python3
"""Fusion Debug — 打印前 N 条查询的各阶段详情"""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from eval_standalone import (
    search_one, build_local_bm25, build_parent_map,
    weighted_fusion, parent_context_expand, preprocess_variants,
    milvus_dense, local_bm25_search, rerank,
    DENSE_RECALL, BM25_RECALL, RERANK_POOL, TOP_K
)

N = int(sys.argv[1]) if len(sys.argv) > 1 else 20

# 预热
build_local_bm25()
build_parent_map()

# 加载评测集
eval_path = Path("data/eval_questions/v8/v8_canonical.jsonl")
items = []
with open(eval_path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            items.append(json.loads(line))

print(f"评测集: {len(items)} 题, 打印前 {N} 条\n")

for idx, qa in enumerate(items[:N]):
    q = qa["question"]
    expected = qa.get("expected_chunk_id", "")
    qtype = qa.get("chunk_type", qa.get("type", "?"))
    span = qa.get("span", "single")

    print(f"{'='*80}")
    print(f"[{idx+1}/{N}] [{qtype}][{span}] {q[:100]}")
    print(f"  expected: {expected[:80]}")

    base_q, expanded_q = preprocess_variants(q)
    print(f"  base_q: {base_q[:120]}")
    if expanded_q and expanded_q != base_q:
        print(f"  expanded_q: {expanded_q[:120]}")

    try:
        final, dense_r, bm25_r, fused_r, expanded_r = search_one(q, TOP_K)
    except Exception as e:
        print(f"  ERROR: {e}")
        continue

    print(f"  Dense hits: {len(dense_r)} | BM25 hits: {len(bm25_r)} | Fused: {len(fused_r)} | Expanded: {len(expanded_r)} | Final: {len(final)}")

    # 检查 fused 中有多少 child
    child_in_fused = [r for r in fused_r if r.get("chunk_type", "").endswith("_child")]
    if child_in_fused:
        print(f"  [FUSED] child chunks in pool: {len(child_in_fused)}")
        for c in child_in_fused[:3]:
            pid = c.get("parent_id", "")[:60]
            print(f"    - {c['id'][:70]} score={c.get('score',0):.4f} parent_id={pid}")

    # 检查 expanded 中是否新增了 parent chunk
    fused_ids = {r.get("id") for r in fused_r}
    new_in_expanded = [r for r in expanded_r if r.get("id") not in fused_ids]
    if new_in_expanded:
        print(f"  [EXPAND] ★ New candidates added: {len(new_in_expanded)}")
        for r in new_in_expanded[:5]:
            print(f"    + {r['id'][:80]} type={r.get('chunk_type','?')} score={r.get('score',0):.4f}")
    else:
        print(f"  [EXPAND] No new candidates added")

    # 最终命中情况
    target_ids = {expected} | set(qa.get("acceptable_chunk_ids", []))
    hit_ranks = []
    for rank, r in enumerate(final, 1):
        if r.get("id") in target_ids:
            hit_ranks.append(rank)
    if hit_ranks:
        print(f"  [HIT] rank={hit_ranks}")
    else:
        top1 = final[0] if final else None
        print(f"  [MISS] top1={top1['id'][:70] if top1 else 'NONE'} (expected={expected[:60]})")
        # 检查 target 是否在 fused 池中
        in_fused = any(expected == r.get("id") for r in fused_r)
        in_dense = any(expected == r.get("id") for r in dense_r)
        in_bm25 = any(expected == r.get("id") for r in bm25_r)
        print(f"    target在 Dense:{'Y' if in_dense else 'N'} BM25:{'Y' if in_bm25 else 'N'} Fused:{'Y' if in_fused else 'N'}")

    print()
