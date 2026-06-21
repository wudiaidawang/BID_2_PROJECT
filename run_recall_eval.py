"""Recall evaluation: compare retrieved chunk IDs against expected_chunk_ids.

Metrics: Hit@1, Hit@5, Recall@5, MRR, per-chunk_count and per-category breakdown.

Runs dense vector search across all 3 collections, merges by score.
"""

import json
import sys
import time
from collections import defaultdict
from app.storage.milvus_store import MilvusStore

QA_PATH = "data/eval_questions/eval_benchmark_manual_v1.json"
TOP_K = 5
COLLECTIONS = ["bids", "regulations", "policy"]


def load_qa_pairs():
    with open(QA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["qa_pairs"], data.get("stats", {})


def search_all(store, question: str, top_k: int):
    """Search across all collections and merge by score."""
    all_results = []
    for coll in COLLECTIONS:
        try:
            results = store.search(coll, question, top_k=top_k)
            for r in results:
                all_results.append(r)
        except Exception as e:
            print(f"  WARN: search {coll} failed: {e}")
    # Sort by score descending, dedup by id
    all_results.sort(key=lambda x: x.get("score", 0), reverse=True)
    seen = set()
    merged = []
    for r in all_results:
        rid = r.get("id", "")
        if rid and rid not in seen:
            seen.add(rid)
            merged.append(rid)
    return merged[:top_k]


def evaluate(qa_pairs):
    store = MilvusStore()

    # Per-metric accumulators
    hit1 = 0
    hit5 = 0
    total_recall_sum = 0.0  # sum of |retrieved ∩ expected| / |expected|
    mrr_sum = 0.0
    total = 0

    # Breakdowns
    by_cc = defaultdict(lambda: {"total": 0, "hit1": 0, "hit5": 0, "recall_sum": 0.0, "mrr_sum": 0.0})
    by_cat = defaultdict(lambda: {"total": 0, "hit1": 0, "hit5": 0, "recall_sum": 0.0, "mrr_sum": 0.0})

    # Log misses
    misses = []

    start = time.time()
    for i, qa in enumerate(qa_pairs):
        question = qa["question"]
        expected = set(qa["expected_chunk_ids"])
        chunk_count = qa["chunk_count"]
        category = qa.get("category", "unknown")

        # Search
        retrieved_ids = search_all(store, question, TOP_K)

        # Compute metrics
        retrieved_set = set(retrieved_ids)
        intersection = expected & retrieved_set
        hit = len(intersection) > 0
        recall_k = len(intersection) / len(expected) if expected else 0.0

        # MRR: 1 / rank of first hit (rank from 1)
        first_rank = 0
        for rank, rid in enumerate(retrieved_ids, 1):
            if rid in expected:
                first_rank = rank
                break
        mrr = 1.0 / first_rank if first_rank > 0 else 0.0

        # Accumulate
        if hit:
            if retrieved_ids and retrieved_ids[0] in expected:
                hit1 += 1
            hit5 += 1
        total_recall_sum += recall_k
        mrr_sum += mrr
        total += 1

        # Breakdowns
        cc_key = str(chunk_count)
        for d in [by_cc[cc_key], by_cat[category]]:
            d["total"] += 1
            d["recall_sum"] += recall_k
            d["mrr_sum"] += mrr
        if retrieved_ids and retrieved_ids[0] in expected:
            by_cc[cc_key]["hit1"] += 1
            by_cat[category]["hit1"] += 1
        if hit:
            by_cc[cc_key]["hit5"] += 1
            by_cat[category]["hit5"] += 1

        if not hit:
            misses.append({
                "qa_id": qa["qa_id"],
                "question": question[:80],
                "chunk_count": chunk_count,
                "category": category,
                "expected": sorted(expected),
                "retrieved": retrieved_ids,
            })

        if (i + 1) % 50 == 0:
            elapsed = time.time() - start
            print(f"  Progress: {i+1}/{len(qa_pairs)} ({elapsed:.1f}s)")

    elapsed = time.time() - start
    print(f"  Done in {elapsed:.1f}s ({elapsed/total:.2f}s per query)\n")

    # Build report
    report = {
        "total_evaluated": total,
        "top_k": TOP_K,
        "overall": {
            "Hit@1": f"{hit1}/{total} = {hit1/total*100:.1f}%",
            "Hit@5": f"{hit5}/{total} = {hit5/total*100:.1f}%",
            "Recall@5": f"{total_recall_sum/total:.4f}",
            "MRR": f"{mrr_sum/total:.4f}",
        },
        "by_chunk_count": {},
        "by_category": {},
    }

    for label, source in [("by_chunk_count", by_cc), ("by_category", by_cat)]:
        for key in sorted(source.keys()):
            d = source[key]
            t = d["total"]
            report[label][key] = {
                "count": t,
                "Hit@1": f"{d['hit1']}/{t} = {d['hit1']/t*100:.1f}%" if t else "N/A",
                "Hit@5": f"{d['hit5']}/{t} = {d['hit5']/t*100:.1f}%" if t else "N/A",
                "Recall@5": f"{d['recall_sum']/t:.4f}" if t else "N/A",
                "MRR": f"{d['mrr_sum']/t:.4f}" if t else "N/A",
            }

    return report, misses


def main():
    print("Loading QA pairs...")
    qa_pairs, stats = load_qa_pairs()
    print(f"  Total: {len(qa_pairs)}")
    print(f"  Stats: {json.dumps(stats, ensure_ascii=False)}")
    print()

    print(f"Running evaluation (top_k={TOP_K})...")
    report, misses = evaluate(qa_pairs)

    print("=" * 60)
    print("RECALL EVALUATION REPORT")
    print("=" * 60)
    for metric, value in report["overall"].items():
        print(f"  {metric}: {value}")

    print("\n--- By chunk_count ---")
    for key, vals in report["by_chunk_count"].items():
        print(f"  chunk_count={key} (n={vals['count']}):")
        print(f"    Hit@1={vals['Hit@1']}, Hit@5={vals['Hit@5']}, Recall@5={vals['Recall@5']}, MRR={vals['MRR']}")

    print("\n--- By category ---")
    for key, vals in report["by_category"].items():
        print(f"  {key} (n={vals['count']}):")
        print(f"    Hit@1={vals['Hit@1']}, Hit@5={vals['Hit@5']}, Recall@5={vals['Recall@5']}, MRR={vals['MRR']}")

    if misses:
        print(f"\n--- Misses ({len(misses)} questions with 0 hits) ---")
        for m in misses[:15]:
            print(f"  {m['qa_id']}: {m['question'][:60]}...")
            print(f"    expected: {m['expected'][:3]}")
            print(f"    retrieved: {m['retrieved'][:5]}")

    # Save full report
    report["misses"] = misses
    report_path = "data/eval_questions/eval_recall_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nFull report saved to: {report_path}")


if __name__ == "__main__":
    main()
