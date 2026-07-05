#!/usr/bin/env python
"""V5 召回评测 —— 纯 chunk ID 匹配，4线程并行"""

import sys
import json
import os
import threading
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

sys.path.insert(0, str(Path(__file__).parent))

from app.core.retriever import HybridRetriever

EVAL_PATH = Path(__file__).parent / "data" / "eval_questions" / "v5_benchmark.json"
OUTPUT_PATH = Path(__file__).parent / "data" / "QA_report" / "v5_report.md"

_lock = threading.Lock()
_thread_local = threading.local()


def _get_retriever():
    if not hasattr(_thread_local, 'retriever'):
        _thread_local.retriever = HybridRetriever()
    return _thread_local.retriever


def load_eval_set() -> list:
    with open(EVAL_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("qa_pairs", [])


def eval_one(qa):
    """评估单个 QA，返回 (hit_rank, qa_type, span, miss_dict_or_None)"""
    question = qa["question"]
    expected_id = qa.get("expected_chunk_id", "")
    acceptable_ids = qa.get("acceptable_chunk_ids", [])
    if not isinstance(acceptable_ids, list):
        acceptable_ids = []
    target_ids = {expected_id} | set(acceptable_ids) if expected_id else set(acceptable_ids)

    qa_type = qa.get("type", qa.get("chunk_type", "unknown"))
    span = qa.get("span", "single")

    retriever = _get_retriever()
    results = retriever.search_unified(query=question, top_k=5)

    if not results:
        return 0, qa_type, span, {
            "question": question[:100],
            "expected_id": expected_id[:60],
            "results": "NO RESULTS",
        }

    result_ids = [r.get("id", "") for r in results[:5]]

    hit_rank = 0
    for rank, rid in enumerate(result_ids, 1):
        if rid in target_ids:
            hit_rank = rank
            break

    if hit_rank == 0:
        return 0, qa_type, span, {
            "question": question[:100],
            "expected_id": expected_id[:60],
            "law_name": qa.get("law_name", "")[:40],
            "span": span,
            "type": qa_type,
            "top1_id": result_ids[0][:60] if result_ids else "",
        }

    return hit_rank, qa_type, span, None


def evaluate():
    print("=" * 60)
    print("V5 Recall Eval — Chunk ID Matching (4 workers)")
    print("=" * 60)

    eval_set = load_eval_set()
    if not eval_set:
        print("[ERROR] No eval set found")
        return
    total = len(eval_set)
    print(f"\nEval set: {total} items")

    hits_at_k = {1: 0, 3: 0, 5: 0}
    by_type = defaultdict(lambda: {"total": 0, "hits": {1: 0, 3: 0, 5: 0}})
    by_span = defaultdict(lambda: {"total": 0, "hits": {1: 0, 3: 0, 5: 0}})
    misses = []
    completed = 0
    import time as _time; _t0 = _time.time()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(eval_one, qa): idx for idx, qa in enumerate(eval_set)}

        for future in as_completed(futures):
            hit_rank, qa_type, span, miss_info = future.result()

            with _lock:
                completed += 1
                by_type[qa_type]["total"] += 1
                by_span[span]["total"] += 1

                if hit_rank == 1:
                    hits_at_k[1] += 1
                    hits_at_k[3] += 1
                    hits_at_k[5] += 1
                    by_type[qa_type]["hits"][1] += 1
                    by_type[qa_type]["hits"][3] += 1
                    by_type[qa_type]["hits"][5] += 1
                    by_span[span]["hits"][1] += 1
                    by_span[span]["hits"][3] += 1
                    by_span[span]["hits"][5] += 1
                elif hit_rank <= 3:
                    hits_at_k[3] += 1
                    hits_at_k[5] += 1
                    by_type[qa_type]["hits"][3] += 1
                    by_type[qa_type]["hits"][5] += 1
                    by_span[span]["hits"][3] += 1
                    by_span[span]["hits"][5] += 1
                elif hit_rank <= 5:
                    hits_at_k[5] += 1
                    by_type[qa_type]["hits"][5] += 1
                    by_span[span]["hits"][5] += 1
                else:
                    misses.append(miss_info)

                if completed % 50 == 0 or completed == total:
                    elapsed = _time.time() - _t0
                    eta = elapsed / completed * (total - completed) if completed else 0
                    print(f"  Progress: {completed}/{total} ({completed/total*100:.0f}%) "
                          f"hits@1={hits_at_k[1]}/hits@5={hits_at_k[5]} "
                          f"elapsed={elapsed:.0f}s eta={eta:.0f}s")

    # ── 输出 ──
    print("\n" + "=" * 60)
    print("RESULTS — Chunk ID Recall")
    print(f"Total: {total}")
    print("=" * 60)

    print(f"\n## 整体召回率")
    for k in [1, 3, 5]:
        rate = hits_at_k[k] / total * 100 if total else 0
        print(f"  Recall@{k}: {rate:.1f}% ({hits_at_k[k]}/{total})")

    print(f"\n## 按 chunk_type")
    for ct in sorted(by_type.keys()):
        stats = by_type[ct]
        n = stats["total"]
        r5 = stats["hits"][5] / n * 100 if n else 0
        r1 = stats["hits"][1] / n * 100 if n else 0
        print(f"  {ct}: {n}题, Recall@1={r1:.1f}%, Recall@5={r5:.1f}%")

    print(f"\n## 按 span")
    for sp in sorted(by_span.keys()):
        stats = by_span[sp]
        n = stats["total"]
        r5 = stats["hits"][5] / n * 100 if n else 0
        r1 = stats["hits"][1] / n * 100 if n else 0
        print(f"  {sp}: {n}题, Recall@1={r1:.1f}%, Recall@5={r5:.1f}%")

    if misses:
        print(f"\n## Miss 样本 (前 20 / 共 {len(misses)})")
        for i, m in enumerate(misses[:20]):
            print(f"  {i+1}. [{m.get('type','')}][{m.get('span','')}] {m['question'][:80]}")
            print(f"     expected: {m['expected_id'][:70]}")
            print(f"     top1: {m['top1_id'][:70]}")

    _write_report(total, hits_at_k, by_type, by_span, misses)
    print(f"\n报告已输出: {OUTPUT_PATH}")


def _write_report(total, hits_at_k, by_type, by_span, misses):
    lines = []
    lines.append(f"# V5 召回评测报告 — Chunk ID 匹配")
    lines.append(f"")
    lines.append(f"**评测集**: v5_benchmark.json, {total} 题")
    lines.append(f"**评测方式**: 纯 chunk ID 匹配（expected_chunk_id / acceptable_chunk_ids）")
    lines.append(f"")
    lines.append(f"## 整体召回率")
    lines.append(f"")
    lines.append(f"| 指标 | 命中 | 总数 | 比率 |")
    lines.append(f"|------|------|------|------|")
    for k in [1, 3, 5]:
        rate = hits_at_k[k] / total * 100 if total else 0
        lines.append(f"| Recall@{k} | {hits_at_k[k]} | {total} | **{rate:.1f}%** |")
    lines.append(f"")
    lines.append(f"## 按 chunk_type")
    lines.append(f"")
    lines.append(f"| 类型 | 题数 | Recall@1 | Recall@3 | Recall@5 |")
    lines.append(f"|------|------|----------|----------|----------|")
    for ct in sorted(by_type.keys()):
        stats = by_type[ct]
        n = stats["total"]
        r1 = stats["hits"][1] / n * 100 if n else 0
        r3 = stats["hits"][3] / n * 100 if n else 0
        r5 = stats["hits"][5] / n * 100 if n else 0
        lines.append(f"| {ct} | {n} | {r1:.1f}% | {r3:.1f}% | **{r5:.1f}%** |")
    lines.append(f"")
    lines.append(f"## 按 span")
    lines.append(f"")
    lines.append(f"| 类型 | 题数 | Recall@1 | Recall@3 | Recall@5 |")
    lines.append(f"|------|------|----------|----------|----------|")
    for sp in sorted(by_span.keys()):
        stats = by_span[sp]
        n = stats["total"]
        r1 = stats["hits"][1] / n * 100 if n else 0
        r3 = stats["hits"][3] / n * 100 if n else 0
        r5 = stats["hits"][5] / n * 100 if n else 0
        lines.append(f"| {sp} | {n} | {r1:.1f}% | {r3:.1f}% | **{r5:.1f}%** |")
    lines.append(f"")
    if misses:
        lines.append(f"## Miss 详情")
        lines.append(f"")
        lines.append(f"共 {len(misses)} 条 miss:")
        lines.append(f"")
        for i, m in enumerate(misses[:30]):
            lines.append(f"{i+1}. [{m.get('type','')}][{m.get('span','')}] {m['question'][:100]}")
            lines.append(f"   - expected: `{m['expected_id'][:80]}`")
            lines.append(f"   - top1: `{m.get('top1_id', '')[:80]}`")
            lines.append(f"")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    evaluate()
