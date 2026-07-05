"""Recall evaluation V3 — 四级命中体系: parent / exact / soft / cosine.

Primary:  parent_hit (父块命中) — same article_id+law_name, regulation-type chunk
Secondary: exact_hit (精确 chunk 匹配) — data quality indicator
Soft:     semantic equiv (法条 vs 解读同条) — reported separately, NOT counted as Miss
Cosine:   cosine ≥ 0.85 (语义相近但 ID 不同) — fallback hit, NOT counted as Miss
"""
import asyncio
import json
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from app.core.model_client import remote_embed

QA_PATH = "data/eval_questions/eval_benchmark_v4.json"
TOP_K = 5
COSINE_THRESHOLD = 0.85
COLLECTIONS = ["policy"]


def _adapt_v2_qa(qa: dict) -> dict:
    """将 eval_benchmark 格式转为评测脚本内部格式"""
    return {
        "qa_id": qa["id"],
        "question": qa["question"],
        "expected_chunk_ids": qa.get("source_chunks", []),
        "chunk_count": len(qa.get("source_chunks", [])),
        "category": qa.get("chunk_type", "unknown"),
    }


def load_qa_pairs():
    with open(QA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    # v2 格式: 返回适配后的 QA 列表
    return [_adapt_v2_qa(q) for q in data["qa_pairs"]]


# ═══════════════════════════════════════════════════════════════
# Phase 1: Batch resolve expected chunk metadata
# ═══════════════════════════════════════════════════════════════

def resolve_expected_chunks(qa_pairs, store):
    """Batch-query Milvus for all expected_chunk_ids → parent/article info + retrieval_text.
    Falls back to parsing IDs for metadata encoded in chunk ID format.
    """
    all_ids = set()
    for qa in qa_pairs:
        all_ids.update(qa["expected_chunk_ids"])

    result = {}
    unresolved = list(all_ids)

    # Try Milvus lookup first
    for collection in COLLECTIONS:
        if not unresolved:
            break
        try:
            docs = store.get_by_ids(collection, unresolved)
            for doc in docs:
                meta = doc.get("metadata", {})
                result[doc["id"]] = {
                    "parent_id": str(meta.get("parent_id", "")),
                    "article_id": str(meta.get("article_id", "")),
                    "law_name": str(meta.get("law_name", "")),
                    "chunk_type": str(meta.get("chunk_type", "")),
                    "retrieval_text": str(doc.get("retrieval_text", "")),
                }
        except Exception as e:
            print(f"  [WARN] get_by_ids on '{collection}': {e}")
            continue
        unresolved = [cid for cid in unresolved if cid not in result]

    # Parse unresolved IDs for encoded metadata
    if unresolved:
        parsed_count = 0
        for cid in unresolved:
            info = _parse_chunk_id(cid)
            if info["article_id"] or info["chunk_type"]:
                parsed_count += 1
            result[cid] = info
        print(f"  [INFO] {len(unresolved)}/{len(all_ids)} IDs not in Milvus; parsed {parsed_count} from ID format")

    return result


def _parse_chunk_id(chunk_id: str) -> dict:
    """Parse article_id, law_name, chunk_type from chunk ID format.

    Formats:
      parent_{law_name}_{article_id}_{chunk_order}_{hash}  →  parent chunk
      parent_{law_name}_{article_id}_{chunk_order}_{hash}_child{N}  →  child chunk
      reg_{source}_{article_id}_{chunk_order}  →  regulation sliding
      pdf_law_{name}_{i}_{hash}  →  PDF law sliding
      pdf_case_{name}_{i}_{hash}  →  PDF case sliding
      opinion_{N}  →  opinion news
      policy_{N}  →  policy doc
      bids_{N}  →  bid project
    """
    import re
    info = {"parent_id": "", "article_id": "", "law_name": "", "chunk_type": ""}
    cid = str(chunk_id)

    # parent chunk: parent_{safe_name}_{article_id}_{counter}_{hash}[_child{N}]
    if cid.startswith("parent_"):
        rest = cid[7:]
        # Remove _child suffix if present
        rest = re.sub(r'_child\d+$', '', rest)
        # Format: safe_name_articleId_counter_hash (4 components from right)
        parts = rest.rsplit('_', 3)
        if len(parts) >= 4:
            info["law_name"] = parts[0]
            info["article_id"] = parts[1]
            info["chunk_type"] = "pdf_law_parent" if "_child" not in cid else "pdf_law_child"

    # regulation sliding: reg_{source}_{article_id}_{chunk_order}
    elif cid.startswith("reg_"):
        rest = cid[4:]
        parts = rest.rsplit('_', 2)
        if len(parts) >= 3:
            info["chunk_type"] = "regulation_sliding"
            info["article_id"] = parts[1]

    # pdf sliding
    elif cid.startswith("pdf_law_"):
        info["chunk_type"] = "pdf_law_sliding"
    elif cid.startswith("pdf_case_"):
        info["chunk_type"] = "pdf_case_sliding"
    elif cid.startswith("pdf_"):
        info["chunk_type"] = "pdf_case_sliding"   # 旧格式 pdf_{name}_{number}（实务案例滑动窗口）
    elif cid.startswith("opinion_"):
        info["chunk_type"] = "opinion_news"
    elif cid.startswith("policy_"):
        info["chunk_type"] = "policy_doc"
    elif cid.startswith("bids_"):
        info["chunk_type"] = "bid_project"

    return info


# ═══════════════════════════════════════════════════════════════
# Phase 1.5: Pre-compute expected chunk embeddings
# ═══════════════════════════════════════════════════════════════

def precompute_expected_embeddings(id_resolution: dict, batch_size: int = 200) -> dict:
    """Batch-encode retrieval_text for all expected chunks → {chunk_id: np.array}."""
    chunk_ids = []
    texts = []
    for cid, info in id_resolution.items():
        rt = info.get("retrieval_text", "")
        if rt:
            chunk_ids.append(cid)
            texts.append(rt)

    if not texts:
        return {}

    print(f"  Pre-computing embeddings for {len(texts)} expected chunks...")
    embeddings_map = {}

    for i in range(0, len(texts), batch_size):
        batch_ids = chunk_ids[i:i + batch_size]
        batch_texts = texts[i:i + batch_size]
        try:
            vecs = remote_embed(batch_texts, timeout=300)
            for cid, vec in zip(batch_ids, vecs):
                embeddings_map[cid] = np.array(vec, dtype=np.float32)
        except Exception as e:
            print(f"  [WARN] embed batch {i//batch_size}: {e}")
            continue
        if (i + batch_size) % 600 == 0 or (i + batch_size) >= len(texts):
            print(f"    ... {min(i + batch_size, len(texts))}/{len(texts)}")

    return embeddings_map


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors."""
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


# ═══════════════════════════════════════════════════════════════
# Phase 2: Hit classification
# ═══════════════════════════════════════════════════════════════

def _derive_source_type(chunk_type: str) -> str:
    """Derive source_type from chunk_type string (for expected chunks)."""
    if not chunk_type:
        return "unknown"
    if chunk_type.startswith("pdf_case_"):
        return "regulation_case"
    if chunk_type in ("opinion_news",):
        return "regulation_opinion"
    if chunk_type in ("policy_doc",):
        return "regulation_policy"
    # regulation_*, pdf_law_*, sliding, parent, child → 法条原文
    return "regulation_article"


def classify_hit(retrieved_chunk, expected_id, expected_info):
    """Classify a retrieved chunk against one expected chunk.

    Returns: "exact" | "parent" | "soft" | None

    parent: same article_id+law_name + same source_type (法条↔法条)
    soft:   same article_id+law_name + different source_type (法条↔解读/案例)
    """
    ret_id = retrieved_chunk.get("id", "")

    # Level 1: exact ID match
    if ret_id == expected_id:
        return "exact"

    exp_article = expected_info.get("article_id", "")
    exp_law = expected_info.get("law_name", "")
    ret_meta = retrieved_chunk.get("metadata", {})
    ret_article = str(ret_meta.get("article_id", ""))
    ret_law = str(ret_meta.get("law_name", ""))

    # Article-level matching (有 article_id 的结构化法条)
    if exp_article and exp_law:
        if ret_article != exp_article or ret_law != exp_law:
            return None

        exp_st = _derive_source_type(expected_info.get("chunk_type", ""))
        ret_st = retrieved_chunk.get("source_type", "")

        if exp_st == ret_st:
            return "parent"   # 同一来源类型 → 权威匹配
        else:
            return "soft"     # 不同来源类型 → 语义等价（如法条 vs 案例解读）

    # Document-level matching (无 article_id 但有 law_name: policy_doc / opinion_news / pdf_case)
    if not exp_article and exp_law:
        if ret_law == exp_law:
            return "parent"   # 同文档 → 父块匹配
        return None

    return None


# ═══════════════════════════════════════════════════════════════
# Phase 3: Core evaluation
# ═══════════════════════════════════════════════════════════════


def _eval_one(qa: dict, pipeline, id_resolution: dict,
              expected_embeddings: dict) -> dict:
    """处理单条 QA：检索 + 命中分类（线程安全）"""
    qid = qa["qa_id"]
    question = qa["question"]
    expected_ids = qa["expected_chunk_ids"]
    chunk_count = qa["chunk_count"]
    category = qa.get("category", "unknown")
    first_info = id_resolution.get(expected_ids[0], {})
    exp_st = _derive_source_type(first_info.get("chunk_type", ""))

    # Search
    try:
        results = pipeline.search_unified(question, top_k=TOP_K)
    except Exception as e:
        print(f"  ERROR [{qid}]: {e}")
        results = []

    retrieved = results[:TOP_K]
    retrieved_ids = [r.get("id", "") for r in retrieved]

    # Batch-encode retrieved texts for cosine fallback
    ret_embeddings = []
    if expected_embeddings:
        ret_texts = [r.get("retrieval_text", r.get("text", "")) for r in retrieved]
        if any(ret_texts):
            try:
                vecs = remote_embed(ret_texts, timeout=60)
                ret_embeddings = [np.array(v, dtype=np.float32) for v in vecs]
            except Exception:
                ret_embeddings = []

    # Per-expected-chunk best hit level
    per_expected = {}
    for eid in expected_ids:
        einfo = id_resolution.get(eid, {"parent_id": "", "article_id": "", "law_name": "", "chunk_type": ""})
        einfo = dict(einfo)
        einfo["chunk_id"] = eid
        best_level = None
        best_rank = None

        for rank, r in enumerate(retrieved, 1):
            level = classify_hit(r, eid, einfo)
            if level == "exact":
                best_level = "exact"; best_rank = rank; break
            if level == "parent" and best_level != "exact":
                best_level = "parent"; best_rank = rank
            if level == "soft" and best_level is None:
                best_level = "soft"; best_rank = rank

        if best_level is None and ret_embeddings and eid in expected_embeddings:
            exp_vec = expected_embeddings[eid]
            for rank, r_vec in enumerate(ret_embeddings, 1):
                if _cosine(exp_vec, r_vec) >= COSINE_THRESHOLD:
                    best_level = "cosine"; best_rank = rank
                    break

        per_expected[eid] = {"best": best_level, "rank": best_rank}

    # Aggregate per question
    best_levels = [v["best"] for v in per_expected.values()]
    has_exact = "exact" in best_levels
    has_parent = has_exact or "parent" in best_levels
    has_cosine = "cosine" in best_levels
    has_any_hit = has_parent or has_cosine
    has_only_soft = not has_parent and not has_cosine and "soft" in best_levels
    total_found = sum(1 for l in best_levels if l in ("exact", "parent"))

    first_ph_rank = 0
    if has_parent:
        first_ph_rank = min(
            (v["rank"] for v in per_expected.values()
             if v["best"] in ("exact", "parent")), default=0)

    first_eh_rank = 0
    if has_exact:
        first_eh_rank = min(
            (v["rank"] for v in per_expected.values()
             if v["best"] == "exact"), default=0)

    first_ch_rank = 0
    if has_cosine:
        first_ch_rank = min(
            (v["rank"] for v in per_expected.values()
             if v["best"] == "cosine"), default=0)

    recall_k = total_found / len(expected_ids) if expected_ids else 0.0
    mrr = 1.0 / first_ph_rank if first_ph_rank > 0 else 0.0

    return {
        "qid": qid, "question": question, "expected_ids": expected_ids,
        "chunk_count": chunk_count, "category": category, "exp_st": exp_st,
        "has_exact": has_exact, "has_parent": has_parent,
        "has_cosine": has_cosine, "has_any_hit": has_any_hit,
        "has_only_soft": has_only_soft,
        "first_ph_rank": first_ph_rank, "first_eh_rank": first_eh_rank,
        "first_ch_rank": first_ch_rank, "total_found": total_found,
        "recall_k": recall_k, "mrr": mrr,
        "retrieved_ids": retrieved_ids,
    }


async def evaluate(qa_pairs, id_resolution, expected_embeddings=None):
    from app.pipeline.pipeline import SearchPipeline

    pipeline = SearchPipeline()
    if expected_embeddings is None:
        expected_embeddings = {}

    # 预热：单条搜索触发 BM25 索引构建 + 文档缓存，避免后续并行时竞态
    print("  Warming up BM25 indices...")
    pipeline.search_unified("测试", top_k=1)
    print("  Warm-up done")

    # Accumulators
    parent_hit1 = 0; parent_hit5 = 0
    exact_hit1 = 0; exact_hit5 = 0
    cosine_hit1 = 0; cosine_hit5 = 0
    recall_sum = 0.0; mrr_sum = 0.0
    soft_only = 0; miss_count = 0; total = 0

    by_cc = defaultdict(lambda: {"t":0,"ph1":0,"ph5":0,"eh1":0,"eh5":0,"ch1":0,"ch5":0,"rs":0.0,"mrr":0.0,"soft":0,"miss":0})
    by_cat = defaultdict(lambda: {"t":0,"ph1":0,"ph5":0,"eh1":0,"eh5":0,"ch1":0,"ch5":0,"rs":0.0,"mrr":0.0,"soft":0,"miss":0})
    by_st = defaultdict(lambda: {"t":0,"ph1":0,"ph5":0,"eh1":0,"eh5":0,"ch1":0,"ch5":0,"rs":0.0,"mrr":0.0,"soft":0,"miss":0})

    soft_hits = []
    cosine_hits_list = []
    misses = []

    start = time.time()
    n_total = len(qa_pairs)
    completed = 0

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(_eval_one, qa, pipeline, id_resolution, expected_embeddings): i
            for i, qa in enumerate(qa_pairs)
        }
        for future in as_completed(futures):
            r = future.result()
            qid = r["qid"]; question = r["question"]
            chunk_count = r["chunk_count"]; category = r["category"]
            exp_st = r["exp_st"]; expected_ids = r["expected_ids"]
            cc_key = str(chunk_count)

            total += 1; completed += 1
            recall_sum += r["recall_k"]; mrr_sum += r["mrr"]

            if r["has_parent"]:
                parent_hit5 += 1
                if r["first_ph_rank"] == 1:
                    parent_hit1 += 1
            if r["has_exact"]:
                exact_hit5 += 1
                if r["first_eh_rank"] == 1:
                    exact_hit1 += 1
            if r["has_cosine"]:
                cosine_hit5 += 1
                if r["first_ch_rank"] == 1:
                    cosine_hit1 += 1

            if r["has_only_soft"]:
                soft_only += 1
                soft_hits.append({
                    "qa_id": qid, "question": question[:80],
                    "category": category, "chunk_count": chunk_count,
                    "expected": expected_ids,
                    "retrieved": r["retrieved_ids"],
                })
            elif not r["has_parent"] and r["has_cosine"]:
                cosine_hits_list.append({
                    "qa_id": qid, "question": question[:80],
                    "category": category, "chunk_count": chunk_count,
                    "expected": expected_ids,
                    "retrieved": r["retrieved_ids"],
                })
            elif not r["has_any_hit"]:
                miss_count += 1
                misses.append({
                    "qa_id": qid, "question": question[:80],
                    "chunk_count": chunk_count, "category": category,
                    "expected": expected_ids,
                    "retrieved": r["retrieved_ids"],
                })

            for d in [by_cc[cc_key], by_cat[category], by_st[exp_st]]:
                d["t"] += 1; d["rs"] += r["recall_k"]; d["mrr"] += r["mrr"]
                if r["has_parent"]:
                    if r["first_ph_rank"] == 1: d["ph1"] += 1
                    d["ph5"] += 1
                if r["has_exact"]:
                    if r["first_eh_rank"] == 1: d["eh1"] += 1
                    d["eh5"] += 1
                if r["has_cosine"]:
                    if r["first_ch_rank"] == 1: d["ch1"] += 1
                    d["ch5"] += 1
                if r["has_only_soft"]: d["soft"] += 1
                if not r["has_any_hit"]: d["miss"] += 1

            if completed % 50 == 0:
                elapsed = time.time() - start
                abs_recall = (total - miss_count) / total * 100 if total else 0
                print(f"  [{completed}/{n_total}] 绝对召回率: {abs_recall:.1f}% "
                      f"parent_hit@5: {parent_hit5}/{total}={parent_hit5/total*100:.1f}% "
                      f"exact_hit@5: {exact_hit5}/{total}={exact_hit5/total*100:.1f}% "
                      f"cosine: {cosine_hit5} soft: {soft_only} miss: {miss_count} ({elapsed:.0f}s)")

    elapsed = time.time() - start
    print(f"  Done in {elapsed:.0f}s ({elapsed/total:.2f}s/query)")

    # Build report
    def pct(n, d): return f"{n}/{d} = {n/d*100:.1f}%" if d else "N/A"
    def avg(n, d): return f"{n/d:.4f}" if d else "N/A"

    t = total
    report = {
        "benchmark": "eval_benchmark_v4",
        "pipeline": "full (BM25+Vector+RRF+Reranker+source_type_boost, embed-once+parallel-colls+3-parallel-qa)",
        "total_evaluated": t,
        "top_k": TOP_K,
        "cosine_threshold": COSINE_THRESHOLD,
        "overall": {
            "_absolute": "绝对召回率 — 任意命中（exact/parent/soft/cosine 任一个即算命中）",
            "absolute_recall": pct(total - miss_count, t),
            "_primary": "parent_hit — 父块命中（同一法条/文章）",
            "parent_hit@1": pct(parent_hit1, t),
            "parent_hit@5": pct(parent_hit5, t),
            "recall@5 (parent)": avg(recall_sum, t),
            "mrr (parent)": avg(mrr_sum, t),
            "_secondary": "exact_hit — 精确 chunk ID 匹配（数据质量指标）",
            "exact_hit@1": pct(exact_hit1, t),
            "exact_hit@5": pct(exact_hit5, t),
            "_cosine": f"cosine_hit — 余弦 ≥ {COSINE_THRESHOLD}（语义相近但ID不同），不计入Miss",
            "cosine_hit@1": pct(cosine_hit1, t),
            "cosine_hit@5": pct(cosine_hit5, t),
            "_soft": "soft_hit — 语义等价（同条但不同源），不计入 Miss",
            "soft_hits_only": f"{soft_only}/{t} = {soft_only/t*100:.1f}%",
            "_miss": "true miss — 无任何命中",
            "misses": f"{miss_count}/{t} = {miss_count/t*100:.1f}%",
        },
        "parent_resolution": {
            "total_unique_chunks": len(id_resolution),
            "with_parent_id": sum(1 for v in id_resolution.values() if v["parent_id"]),
            "with_article_id": sum(1 for v in id_resolution.values() if v["article_id"]),
            "with_retrieval_text": sum(1 for v in id_resolution.values() if v.get("retrieval_text")),
            "no_article_or_parent": sum(1 for v in id_resolution.values() if not v["article_id"] and not v["parent_id"]),
        },
        "by_chunk_count": {},
        "by_category": {},
        "by_source_type": {},
        "soft_hits": soft_hits,
        "cosine_hits": cosine_hits_list,
        "misses": misses,
    }

    for label, source in [("by_chunk_count", by_cc), ("by_category", by_cat), ("by_source_type", by_st)]:
        for key in sorted(source.keys()):
            d = source[key]; n = d["t"]
            report[label][key] = {
                "count": n,
                "parent_hit@1": pct(d["ph1"], n),
                "parent_hit@5": pct(d["ph5"], n),
                "exact_hit@1": pct(d["eh1"], n),
                "exact_hit@5": pct(d["eh5"], n),
                "cosine_hit@1": pct(d["ch1"], n),
                "cosine_hit@5": pct(d["ch5"], n),
                "recall@5": avg(d["rs"], n),
                "mrr": avg(d["mrr"], n),
                "soft_only": f"{d['soft']}/{n}",
                "miss": f"{d['miss']}/{n}",
            }

    return report


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

async def main():
    from app.storage.milvus_store import MilvusStore

    print("Loading QA pairs (regulation-only, bid_project → SQL)...")
    qa_pairs = load_qa_pairs()
    print(f"  Total: {len(qa_pairs)} (bid_project excluded)")

    print("\nResolving expected chunk metadata from Milvus...")
    store = MilvusStore()
    id_resolution = resolve_expected_chunks(qa_pairs, store)
    print(f"  Resolved {len(id_resolution)} unique chunk IDs")
    with_article = sum(1 for v in id_resolution.values() if v["article_id"])
    with_parent = sum(1 for v in id_resolution.values() if v["parent_id"])
    with_rt = sum(1 for v in id_resolution.values() if v.get("retrieval_text"))
    print(f"  With article_id: {with_article}, With parent_id: {with_parent}, With retrieval_text: {with_rt}")

    # Pre-compute embeddings for cosine fallback
    print("\nPre-computing expected chunk embeddings...")
    expected_embeddings = precompute_expected_embeddings(id_resolution)
    print(f"  Embeddings: {len(expected_embeddings)}")

    print(f"\nRunning evaluation V2 (top_k={TOP_K}, cosine_threshold={COSINE_THRESHOLD})...")
    report = await evaluate(qa_pairs, id_resolution, expected_embeddings)

    print("\n" + "=" * 60)
    print("RECALL EVALUATION V2 — 四级命中体系")
    print("=" * 60)
    for metric, value in report["overall"].items():
        if metric.startswith("_"):
            print(f"\n  [{value}]")
        else:
            print(f"  {metric}: {value}")

    print(f"\n--- Parent Resolution ---")
    for k, v in report["parent_resolution"].items():
        print(f"  {k}: {v}")

    print(f"\n--- By chunk_count ---")
    for key, vals in report["by_chunk_count"].items():
        print(f"  chunk_count={key} (n={vals['count']}):")
        print(f"    parent_hit@1={vals['parent_hit@1']}  parent_hit@5={vals['parent_hit@5']}")
        print(f"    exact_hit@1={vals['exact_hit@1']}  exact_hit@5={vals['exact_hit@5']}")
        print(f"    cosine_hit@1={vals['cosine_hit@1']}  cosine_hit@5={vals['cosine_hit@5']}")
        print(f"    recall@5={vals['recall@5']}  mrr={vals['mrr']}")
        print(f"    soft_only={vals['soft_only']}  miss={vals['miss']}")

    print(f"\n--- By category ---")
    for key, vals in sorted(report["by_category"].items()):
        print(f"  {key} (n={vals['count']}):")
        print(f"    parent_hit@5={vals['parent_hit@5']}  exact_hit@5={vals['exact_hit@5']}")
        print(f"    cosine_hit@5={vals['cosine_hit@5']}")
        print(f"    soft_only={vals['soft_only']}  miss={vals['miss']}")

    print(f"\n--- By source_type ---")
    for key, vals in sorted(report["by_source_type"].items()):
        print(f"  {key} (n={vals['count']}):")
        print(f"    parent_hit@5={vals['parent_hit@5']}  exact_hit@5={vals['exact_hit@5']}")
        print(f"    cosine_hit@5={vals['cosine_hit@5']}")
        print(f"    soft_only={vals['soft_only']}  miss={vals['miss']}")

    print(f"\n--- Soft Hits ({len(report['soft_hits'])}): Not counted as Miss ---")
    for sh in report["soft_hits"][:10]:
        print(f"  {sh['qa_id']}: {sh['question'][:60]}")
        print(f"    expected: {sh['expected']}")
        print(f"    retrieved: {sh['retrieved']}")

    print(f"\n--- Cosine Hits ({len(report['cosine_hits'])}): Cosine ≥ {COSINE_THRESHOLD} ---")
    for ch in report["cosine_hits"][:10]:
        print(f"  {ch['qa_id']}: {ch['question'][:60]}")
        print(f"    expected: {ch['expected']}")
        print(f"    retrieved: {ch['retrieved']}")

    print(f"\n--- Misses ({len(report['misses'])}): True misses ---")
    for m in report["misses"][:10]:
        print(f"  {m['qa_id']}: {m['question'][:60]}")
        print(f"    expected: {m['expected']}")
        print(f"    retrieved: {m['retrieved']}")

    report_path = "data/QA_report/eval_recall_report_v4.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nSaved: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
