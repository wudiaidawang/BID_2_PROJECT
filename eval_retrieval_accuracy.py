#!/usr/bin/env python
"""二分类架构评估脚本 —— is_sql 网关准确率 + 统一检索 Top-K 召回率"""

import asyncio
import sys
import json
import hashlib
import os
import numpy as np
from pathlib import Path

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

sys.path.insert(0, str(Path(__file__).parent))

from app.core.retriever import HybridRetriever
from app.core.router import BinaryRouter
from app.core.embedding import EmbeddingService

EVAL_DIR = "./data/eval_questions"
HIT_THRESHOLD = 0.70  # 余弦相似度命中阈值


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


def load_eval_set() -> list:
    eval_dir = Path(EVAL_DIR)
    if not eval_dir.exists():
        print(f"[ERROR] Eval dir not found: {EVAL_DIR}")
        return []
    json_files = sorted(eval_dir.glob("*.json"))
    eval_set = []
    for jf in json_files:
        with open(jf, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            eval_set.extend(data)
        print(f"  Loaded {jf.name}: {len(data) if isinstance(data, list) else 1} items")
    return eval_set


async def evaluate():
    print("=" * 60)
    print("Eval: Binary Gateway + Unified Retrieval (Embedding-based)")
    print("=" * 60)

    eval_set = load_eval_set()
    if not eval_set:
        print("[ERROR] No eval set found")
        return

    eval_fingerprint = hashlib.md5(
        json.dumps(eval_set, ensure_ascii=False).encode()
    ).hexdigest()[:8]

    test_limit = len(eval_set)
    print(f"\nEval set: {test_limit} items")
    print(f"Fingerprint: {eval_fingerprint}")
    print(f"Hit threshold: cosine ≥ {HIT_THRESHOLD}\n")

    router = BinaryRouter()
    retriever = HybridRetriever()
    emb_service = EmbeddingService()

    sql_routed = 0
    sql_correct = 0
    hits_at_k = {1: 0, 3: 0, 5: 0}
    total_evaluable = 0
    # 用 embedding 评估的计数器
    total_embed_eval = 0
    hits_embed_at_k = {1: 0, 3: 0, 5: 0}
    detailed_misses = []

    # 预计算 expected_answer embedding（仅对有 expected_answer 的用例）
    answers = [c.get("expected_answer", "") for c in eval_set]
    has_embed_eval = any(a and len(a.strip()) >= 2 for a in answers)
    if has_embed_eval:
        answer_embs = emb_service.model.encode(answers, show_progress_bar=False)

    for i, case in enumerate(eval_set, 1):
        question = case["question"]
        expected_answer = case.get("expected_answer", "")
        expected_keywords = case.get("expected_answer_contains", [])

        if i % 10 == 0 or i == test_limit:
            print(f"  Progress: {i}/{test_limit}")

        # 1. 二分类网关判定
        route = await router.route(question)

        expected_is_sql = case.get("expected_type") == "sql"
        actual_is_sql = route["is_sql"]
        if actual_is_sql:
            sql_routed += 1
            if expected_is_sql:
                sql_correct += 1
        else:
            if not expected_is_sql:
                sql_correct += 1

        # 跳过无可评估依据的用例
        has_answer = expected_answer and len(expected_answer.strip()) >= 2
        has_keywords = bool(expected_keywords)
        if not has_answer and not has_keywords:
            continue
        total_evaluable += 1

        # 2. 统一混合检索
        results = retriever.search_unified(query=question, top_k=5)

        if not results:
            detailed_misses.append({
                "question": question,
                "answer": expected_answer or str(expected_keywords),
                "top1_preview": "no results",
                "max_sim": 0.0,
                "type": case.get("expected_type", "?")
            })
            continue

        # 3a. Keyword 命中评估（优先，有 expected_answer_contains 时使用）
        if has_keywords:
            hit_at_1 = False
            hit_at_3 = False
            hit_at_5 = False
            best_hit = 0

            for rank, r in enumerate(results[:5], 1):
                text = r.get("parent_content") or r.get("text", "")
                matched = sum(1 for kw in expected_keywords if kw in text)
                hit_rate = matched / len(expected_keywords) if expected_keywords else 0
                best_hit = max(best_hit, hit_rate)

                if hit_rate >= 0.5:  # 至少一半关键词命中
                    if rank == 1:
                        hit_at_1 = True
                    if rank <= 3:
                        hit_at_3 = True
                    if rank <= 5:
                        hit_at_5 = True
                    break

            if hit_at_1:
                hits_at_k[1] += 1
            if hit_at_3:
                hits_at_k[3] += 1
            if hit_at_5:
                hits_at_k[5] += 1

            if not hit_at_1:
                detailed_misses.append({
                    "question": question,
                    "answer": str(expected_keywords),
                    "top1_preview": results[0].get("text", "")[:200] if results else "no results",
                    "max_sim": round(best_hit, 3),
                    "type": case.get("expected_type", "?")
                })

        # 3b. Embedding 相似度验证（有 expected_answer 时使用）
        if has_answer and has_embed_eval:
            total_embed_eval += 1
            ans_emb = answer_embs[i - 1]
            best_sim = 0.0
            hit_embed = False

            for rank, r in enumerate(results[:5], 1):
                text_emb = emb_service.model.encode(
                    [r.get("text", "")[:500]], show_progress_bar=False
                )[0]
                sim = _cosine_sim(ans_emb, text_emb)
                best_sim = max(best_sim, sim)

                if sim >= HIT_THRESHOLD:
                    if rank == 1:
                        hits_embed_at_k[1] += 1
                    if rank <= 3:
                        hits_embed_at_k[3] += 1
                    if rank <= 5:
                        hits_embed_at_k[5] += 1
                    hit_embed = True
                    break

            if not hit_embed and not has_keywords:
                detailed_misses.append({
                    "question": question,
                    "answer": expected_answer,
                    "top1_preview": results[0].get("text", "")[:200] if results else "no results",
                    "max_sim": round(best_sim, 3),
                    "type": case.get("expected_type", "?")
                })

    # ── 输出结果 ──
    print("\n" + "=" * 60)
    print("RESULTS")
    print(f"Fingerprint: {eval_fingerprint}")
    print(f"Mode: Binary Gateway + Unified Search + Embedding Eval (thresh={HIT_THRESHOLD})")
    print("=" * 60)

    gateway_acc = sql_correct / test_limit * 100 if test_limit else 0
    print(f"\n[Gateway] is_sql Classification Accuracy:")
    print(f"  Accuracy: {gateway_acc:.1f}% ({sql_correct}/{test_limit})")
    print(f"  SQL-routed (misclassified): {sql_routed}/{test_limit}")

    eval_mode = "Keyword" if total_evaluable > 0 and not has_embed_eval else \
                "Embedding" if total_embed_eval > 0 else "Keyword"
    print(f"\n[Unified Retrieval] Top-K Recall (mode: {eval_mode}, evaluable: {total_evaluable}):")
    for k in [1, 3, 5]:
        accuracy = hits_at_k[k] / total_evaluable * 100 if total_evaluable else 0
        print(f"  Top-{k}: {accuracy:.1f}% ({hits_at_k[k]}/{total_evaluable})")

    if total_embed_eval > 0:
        print(f"\n[Embedding Eval Subset] ({total_embed_eval} items, thresh={HIT_THRESHOLD}):")
        for k in [1, 3, 5]:
            accuracy = hits_embed_at_k[k] / total_embed_eval * 100 if total_embed_eval else 0
            print(f"  Top-{k}: {accuracy:.1f}% ({hits_embed_at_k[k]}/{total_embed_eval})")

    # 按类型分组统计
    type_stats = {}
    for case in eval_set:
        t = case.get("expected_type", "unknown")
        if t not in type_stats:
            type_stats[t] = {"total": 0, "missed": 0}
        type_stats[t]["total"] += 1
    for m in detailed_misses:
        t = m.get("type", "unknown")
        if t in type_stats:
            type_stats[t]["missed"] += 1
    print(f"\n[By Type] Miss rate:")
    for t, s in sorted(type_stats.items()):
        rate = s["missed"] / s["total"] * 100 if s["total"] else 0
        print(f"  {t}: {rate:.1f}% missed ({s['missed']}/{s['total']})")

    if detailed_misses:
        print(f"\n[Missed Examples] ({len(detailed_misses)} total, showing first 8):")
        for i, fail in enumerate(detailed_misses[:8]):
            q = fail['question'][:70]
            a = str(fail.get('answer', ''))[:80]
            print(f"  {i + 1}. Q: {q}")
            print(f"     Expected: {a}")
            print(f"     Score: {fail.get('max_sim', 'N/A')} | Top-1: {str(fail.get('top1_preview', ''))[:100]}")

    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(evaluate())
