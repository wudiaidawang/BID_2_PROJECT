#!/usr/bin/env python
"""用预留评估集测试检索准确率（支持意图路由）"""

import asyncio
import sys
import json
import hashlib
import os
from pathlib import Path
from collections import defaultdict

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

sys.path.insert(0, str(Path(__file__).parent))

from app.core.retriever import HybridRetriever
from app.core.router import IntentRouter

EVAL_DIR = "./data/eval_questions"
LEGACY_EVAL_PATH = "./data/pdf_eval_set.json"


def load_eval_set() -> list:
    """加载评估集：优先从 eval_questions/ 目录合并所有 JSON 文件，其次回退到旧路径"""
    eval_dir = Path(EVAL_DIR)
    if eval_dir.exists():
        json_files = sorted(eval_dir.glob("*.json"))
        eval_set = []
        for jf in json_files:
            with open(jf, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                eval_set.extend(data)
            print(f"  Loaded {jf.name}: {len(data) if isinstance(data, list) else 1} items")
        if eval_set:
            return eval_set

    # fallback
    if Path(LEGACY_EVAL_PATH).exists():
        with open(LEGACY_EVAL_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)

    return []


async def evaluate_heldout():
    print("=" * 60)
    print("Retrieval Accuracy Evaluation (with Intent Router)")
    print("=" * 60)

    eval_set = load_eval_set()
    if not eval_set:
        print(f"[ERROR] No eval set found")
        print(f"Put your .json files in {EVAL_DIR}/")
        return

    eval_fingerprint = hashlib.md5(
        json.dumps(eval_set, ensure_ascii=False).encode()
    ).hexdigest()[:8]

    print(f"\nEval set: {len(eval_set)} items")
    print(f"Fingerprint: {eval_fingerprint}")

    test_limit = len(eval_set)
    print(f"Test count: {test_limit} (all)\n")

    retriever = HybridRetriever()
    router = IntentRouter()

    # overall stats
    hits_at_k = {1: 0, 3: 0, 5: 0}
    # per-intent stats
    intent_hits = defaultdict(lambda: {1: 0, 3: 0, 5: 0})
    intent_total = defaultdict(int)
    detailed_results = []

    for i, case in enumerate(eval_set, 1):
        question = case["question"]
        expected_answer = case["expected_answer"]

        if i % 5 == 0 or i == test_limit:
            print(f"  Progress: {i}/{test_limit}")

        # routing: use source field if available, else fallback to keyword router
        source = case.get("source", "")
        if "SQL" in source or "Database" in source:
            intent = "statistics"
            collection = "bids"
        elif "法规" in source or "法律" in source or "PDF" in source:
            intent = "regulations"
            collection = "regulations"
        else:
            route = router.route(question)
            intent = route["intent"]
            collection = route["collection"]

        results = retriever.search(
            query=question,
            collection=collection,
            top_k=5
        )

        expected_keywords = extract_keywords_from_answer(expected_answer)
        if not expected_keywords:
            continue

        intent_total[intent] += 1

        hit_at_1 = False
        hit_at_3 = False
        hit_at_5 = False

        if results:
            for rank, r in enumerate(results[:5], 1):
                text = r.get("text", "")
                if any(kw in text for kw in expected_keywords[:3]):
                    if rank == 1:
                        hit_at_1 = True
                    if rank <= 3:
                        hit_at_3 = True
                    if rank <= 5:
                        hit_at_5 = True

        if hit_at_1:
            hits_at_k[1] += 1
            intent_hits[intent][1] += 1
        if hit_at_3:
            hits_at_k[3] += 1
            intent_hits[intent][3] += 1
        if hit_at_5:
            hits_at_k[5] += 1
            intent_hits[intent][5] += 1

        if not hit_at_1:
            detailed_results.append({
                "question": question,
                "intent": intent,
                "collection": collection,
                "expected_keywords": expected_keywords[:3],
                "top1_preview": results[0].get("text", "")[:100] if results else "no results"
            })

    # results
    print("\n" + "=" * 60)
    print("OVERALL RESULTS")
    print(f"Fingerprint: {eval_fingerprint}")
    print(f"Mode: Hybrid Search (Vector + BM25 + RRF) with Intent Router")
    print("=" * 60)
    for k in [1, 3, 5]:
        accuracy = hits_at_k[k] / test_limit * 100
        print(f"  Top-{k}: {accuracy:.1f}% ({hits_at_k[k]}/{test_limit})")

    # per-intent breakdown
    print("\n" + "-" * 40)
    print("Per-Intent Breakdown:")
    for intent in sorted(intent_total.keys()):
        total = intent_total[intent]
        top1 = intent_hits[intent][1]
        top3 = intent_hits[intent][3]
        top5 = intent_hits[intent][5]
        print(f"  [{intent}] ({total} items):")
        print(f"    Top-1: {top1}/{total} ({top1/total*100:.1f}%)")
        print(f"    Top-3: {top3}/{total} ({top3/total*100:.1f}%)")
        print(f"    Top-5: {top5}/{total} ({top5/total*100:.1f}%)")
    print("=" * 60)

    if detailed_results:
        print("\nMissed Examples (Top-1):")
        for i, fail in enumerate(detailed_results[:5]):
            print(f"  {i + 1}. [{fail['intent']}] {fail['question'][:60]}...")
            print(f"     Expected: {fail['expected_keywords']}")
            print(f"     Got:      {fail['top1_preview']}...")


def extract_keywords_from_answer(answer: str) -> list:
    """从答案中提取关键词用于验证"""
    import re
    # 提取中文词
    words = re.findall(r'[\u4e00-\u9fa5]{2,}', answer[:150])
    # 去重并取前5个
    keywords = list(dict.fromkeys(words))[:5]
    return keywords


if __name__ == "__main__":
    asyncio.run(evaluate_heldout())