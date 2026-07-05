#!/usr/bin/env python3
"""Parent Expansion 贡献度诊断 — 统计 parent 实际新增、进 Top30、进 Top5、改变命中"""
import json, sys, random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from eval_standalone import (
    search_one, build_local_bm25, build_parent_map,
    DENSE_RECALL, BM25_RECALL, RERANK_POOL, TOP_K
)

SAMPLE = int(sys.argv[1]) if len(sys.argv) > 1 else 500

# 预热
print("Warming up...")
build_local_bm25()
build_parent_map()

# 加载评测集，随机采样
eval_path = Path("data/eval_questions/v8/v8_canonical.jsonl")
items = []
with open(eval_path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            items.append(json.loads(line))

random.seed(42)
sample = random.sample(items, min(SAMPLE, len(items)))
print(f"采样 {len(sample)}/{len(items)} 题\n")

# ── 统计 ──
stats = {
    "total": 0,
    "queries_with_child_in_fused": 0,   # fused 池中有 child
    "parents_added_total": 0,           # expander 新增 parent 总数
    "parents_added_queries": 0,         # 至少新增 1 个 parent 的 query 数
    "parents_in_top30_total": 0,         # 新增 parent 进入 top 30 的数量
    "parents_in_top5_total": 0,          # 新增 parent 进入 top 5 的数量
    "parents_saved_hit": 0,             # 新增 parent 就是 target（改变了命中）
    "parents_saved_hit_details": [],
}

for idx, qa in enumerate(sample):
    q = qa["question"]
    expected = qa.get("expected_chunk_id", "")
    target_ids = {expected} | set(qa.get("acceptable_chunk_ids", []))

    try:
        final, dense_r, bm25_r, fused_r, expanded_r = search_one(q, TOP_K)
    except Exception as e:
        continue

    stats["total"] += 1

    # fused 池的 ID 集合
    fused_ids = {r.get("id") for r in fused_r}
    fused_pool_ids = {r.get("id") for r in fused_r[:RERANK_POOL]}

    # expanded 新增的 ID（不在 fused 中的）
    expanded_ids = {r.get("id") for r in expanded_r}
    new_ids = expanded_ids - fused_ids
    new_candidates = [r for r in expanded_r if r.get("id") in new_ids]

    # 检查 fused 中有没有 child
    has_child = any(r.get("chunk_type", "").endswith("_child") for r in fused_r)
    if has_child:
        stats["queries_with_child_in_fused"] += 1

    if new_candidates:
        stats["parents_added_total"] += len(new_candidates)
        stats["parents_added_queries"] += 1

        # 多少进入了 top 30
        top30_ids = {r.get("id") for r in expanded_r[:RERANK_POOL]}
        in_top30 = [c for c in new_candidates if c.get("id") in top30_ids]
        stats["parents_in_top30_total"] += len(in_top30)

        # 多少进入了 top 5 (final)
        final_ids = {r.get("id") for r in final}
        in_top5 = [c for c in new_candidates if c.get("id") in final_ids]
        stats["parents_in_top5_total"] += len(in_top5)

        # 新增的 parent 是否就是 target
        for c in new_candidates:
            if c.get("id") in target_ids:
                # 检查 target 是否在 fused 中（如果已经在，就不是 expansion 救回来的）
                was_in_fused = any(c.get("id") in fused_ids for c_id in [c.get("id")])
                # Actually check if target was in fused at all
                target_in_fused = bool(target_ids & fused_ids)
                target_in_fused_top30 = bool(target_ids & fused_pool_ids)

                stats["parents_saved_hit"] += 1
                stats["parents_saved_hit_details"].append({
                    "question": q[:80],
                    "target": expected[:60],
                    "target_in_fused": target_in_fused,
                    "target_in_fused_top30": target_in_fused_top30,
                })

    if (idx + 1) % 100 == 0:
        print(f"  [{idx+1}/{len(sample)}] ...")

# ── 输出 ──
print(f"\n{'='*60}")
print(f"Parent Expansion 贡献度诊断 (n={stats['total']})")
print(f"{'='*60}")
print(f"  fused 池中有 child 的 query: {stats['queries_with_child_in_fused']} ({stats['queries_with_child_in_fused']/stats['total']*100:.1f}%)")
print(f"  至少新增 1 个 parent 的 query: {stats['parents_added_queries']} ({stats['parents_added_queries']/stats['total']*100:.1f}%)")
print(f"  总共新增 parent 候选: {stats['parents_added_total']}")
print(f"  新增 parent 进入 Top30: {stats['parents_in_top30_total']}")
print(f"  新增 parent 进入 Top5: {stats['parents_in_top5_total']}")
print(f"  新增 parent 就是 target (救了命中): {stats['parents_saved_hit']}")
print()

if stats["parents_saved_hit_details"]:
    print("  救回的命中详情:")
    for d in stats["parents_saved_hit_details"]:
        in_f = "Y" if d["target_in_fused"] else "N"
        in_f30 = "Y" if d["target_in_fused_top30"] else "N"
        print(f"    Q: {d['question']}")
        print(f"    target: {d['target']}  |  在fused:{in_f}  在fused_top30:{in_f30}")
        print()

# 推算全量影响
total_eval = 3146
if stats["parents_saved_hit"] > 0:
    projected = stats["parents_saved_hit"] / stats["total"] * total_eval
    print(f"  推算全量可能救回: ~{projected:.0f} 条 (R@5 提升约 {projected/total_eval*100:.1f}%)")
else:
    print(f"  ★ Parent Expansion 未能救回任何 miss — 新增的 parent 都不是 target")
