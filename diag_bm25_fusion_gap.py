#!/usr/bin/env python3
"""诊断：BM25 top30 命中 but Fusion top30 未命中 — 导出全部样本（跳过 reranker）"""
import json, sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from eval_standalone import (
    build_local_bm25, build_parent_map, preprocess_variants,
    milvus_dense, local_bm25_search, embed,
    weighted_fusion, DENSE_RECALL, BM25_RECALL, STAGE_POOL, TOP_K
)
import httpx

PATH = Path("data/eval_questions/v8/v8_canonical.jsonl")
OUT = Path("data/eval_questions/v8/v8_bm25_hit_fusion_miss.json")

_client = httpx.Client(transport=httpx.HTTPTransport(proxy=None), timeout=httpx.Timeout(60))

print("Warming up...")
build_local_bm25()
build_parent_map()

items = []
with open(PATH, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            items.append(json.loads(line))
print(f"评测集: {len(items)} 题\n")

bm25_hit_fusion_miss = []
stage_stats = {"bm25_pool": 0, "fused_pool": 0, "bm25_only": 0, "fusion_only": 0, "both": 0, "neither": 0}
weight_breakdown = defaultdict(int)  # 统计各类权重的丢失比例

for idx, qa in enumerate(items):
    q = qa["question"]
    expected = qa.get("expected_chunk_id", "")
    target_ids = {expected} | set(qa.get("acceptable_chunk_ids", []))

    try:
        base_q, expanded_q = preprocess_variants(q)

        # 多路 Dense + BM25
        all_dense = {}
        all_bm25 = {}
        for query_text in [base_q] + ([expanded_q] if expanded_q and expanded_q != base_q else []):
            vec = embed([query_text])[0]
            for r in milvus_dense(vec, DENSE_RECALL):
                did = r.get("id", "")
                if did not in all_dense or r.get("score", 0) > all_dense[did].get("score", 0):
                    all_dense[did] = r
            for r in local_bm25_search(query_text, BM25_RECALL):
                did = r.get("id", "")
                if did not in all_bm25 or r.get("score", 0) > all_bm25[did].get("score", 0):
                    all_bm25[did] = r

        dense_r = list(all_dense.values())
        bm25_r = list(all_bm25.values())
        fused_r = weighted_fusion(dense_r, bm25_r, base_q, DENSE_RECALL)

    except Exception as e:
        continue

    bm25_pool_hit = any(r.get("id") in target_ids for r in bm25_r[:STAGE_POOL])
    fused_pool_hit = any(r.get("id") in target_ids for r in fused_r[:STAGE_POOL])

    if bm25_pool_hit:
        stage_stats["bm25_pool"] += 1
    if fused_pool_hit:
        stage_stats["fused_pool"] += 1

    if bm25_pool_hit and fused_pool_hit:
        stage_stats["both"] += 1
    elif bm25_pool_hit and not fused_pool_hit:
        stage_stats["bm25_only"] += 1
        # 详细分析
        bm25_target = next(({"rank": i+1, "score": r.get("score", 0),
                              "text": r.get("retrieval_text", r.get("text", ""))[:200]}
                             for i, r in enumerate(bm25_r) if r.get("id") in target_ids), None)
        dense_target = next(({"rank": i+1, "score": r.get("score", 0)}
                              for i, r in enumerate(dense_r) if r.get("id") in target_ids), None)
        fused_target = next(({"rank": i+1, "score": r.get("score", 0)}
                              for i, r in enumerate(fused_r) if r.get("id") in target_ids), None)

        fused_top5 = [{"id": r.get("id", "")[:60], "score": round(r.get("score", 0), 4),
                        "type": r.get("chunk_type", ""),
                        "text": r.get("retrieval_text", r.get("text", ""))[:80]}
                       for r in fused_r[:5]]

        from eval_standalone import _get_dynamic_weights
        bw, dw = _get_dynamic_weights(q)
        weight_breakdown[f"{bw:.2f}/{dw:.2f}"] += 1

        bm25_hit_fusion_miss.append({
            "question": q,
            "expected_id": expected[:80],
            "qa_type": qa.get("chunk_type", qa.get("type", "?")),
            "question_type": qa.get("question_type", "?"),
            "span": qa.get("span", "single"),
            "bm25_weight": bw, "dense_weight": dw,
            "bm25_target": bm25_target,
            "dense_target": dense_target,
            "fused_target": fused_target,
            "fused_top5": fused_top5,
        })
    elif not bm25_pool_hit and fused_pool_hit:
        stage_stats["fusion_only"] += 1
    else:
        stage_stats["neither"] += 1

    if (idx + 1) % 200 == 0:
        print(f"  [{idx+1}/{len(items)}] bm25_only={stage_stats['bm25_only']}  fusion_only={stage_stats['fusion_only']}")

# ── 输出 ──
print(f"\n{'='*60}")
print(f"BM25 vs Fusion Pool@30 对比 (n={len(items)})")
print(f"{'='*60}")
print(f"  BM25 Pool@30 命中:    {stage_stats['bm25_pool']} ({stage_stats['bm25_pool']/len(items)*100:.1f}%)")
print(f"  Fusion Pool@30 命中:  {stage_stats['fused_pool']} ({stage_stats['fused_pool']/len(items)*100:.1f}%)")
print(f"  两者都命中:            {stage_stats['both']}")
print(f"  ★ BM25命中 Fusion丢失: {stage_stats['bm25_only']} ({stage_stats['bm25_only']/len(items)*100:.1f}%)")
print(f"  Fusion命中 BM25丢失:   {stage_stats['fusion_only']} ({stage_stats['fusion_only']/len(items)*100:.1f}%)")
print(f"  都不命中:              {stage_stats['neither']}")

by_type = defaultdict(int)
for r in bm25_hit_fusion_miss:
    by_type[r["qa_type"]] += 1
print("\n丢失样本 chunk_type 分布:")
for t, c in sorted(by_type.items(), key=lambda x: -x[1]):
    print(f"  {t}: {c}")

print("\n丢失样本 权重分布:")
for w, c in sorted(weight_breakdown.items(), key=lambda x: -x[1]):
    print(f"  BM25={w.split('/')[0]} Dense={w.split('/')[1]}: {c}")

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(bm25_hit_fusion_miss, f, ensure_ascii=False, indent=2)
print(f"\n导出 {len(bm25_hit_fusion_miss)} 条 → {OUT}")
