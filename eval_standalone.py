#!/usr/bin/env python3
"""Standalone V6 召回评测 — 本地 jieba BM25 + 远程 Embedding/Reranker + 各阶段分解，N 并发"""

import json, sys, threading, time, os
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from pathlib import Path

import httpx
import numpy as np
import jieba
from rank_bm25 import BM25Okapi

# ── 服务地址（服务器本地）──
MILVUS_URL = "http://localhost:19531"
MODEL_URL = "http://localhost:8210"
DB = "panxin_dev"
COLLECTION = "policy"
DENSE_FIELD = "dense_vector"
OUTPUT_FIELDS = [
    "retrieval_text", "text", "title", "source_doc",
    "law_name", "article_id", "chunk_type", "parent_id",
    "chunk_order", "chunk_hash", "token_count",
    "project_name", "supplier", "region", "publish_date",
    "category", "data_version", "metadata",
]
RRF_K = 60
TOP_K = 5
DENSE_RECALL = 50
BM25_RECALL = 50
RERANK_POOL = 30
WORKERS = 3

EVAL_PATH = Path(__file__).parent / "v6_benchmark.json"
OUTPUT_PATH = Path(__file__).parent / "v6_report.md"

_lock = threading.Lock()
_thread_local = threading.local()

# ── 本地 jieba BM25（替代 Milvus 内置 BM25）──
_bm25_index: BM25Okapi | None = None
_bm25_docs: list = []  # 完整文档列表，供 BM25 命中后返回


def chinese_tokenize(text: str) -> list:
    """jieba 中文分词，与生产管线 app/pipeline/retrievers.py 一致"""
    if not text:
        return []
    return [w for w in jieba.cut(str(text)) if w.strip()]


def _fetch_all_docs() -> list:
    """从 Milvus 分页拉取 policy collection 全部文档"""
    all_ids = []
    offset = 0
    page = 10000
    while True:
        data = _post_milvus("/v2/vectordb/entities/query", {
            "collectionName": COLLECTION, "dbName": DB,
            "filter": "id != \"\"",
            "limit": page, "offset": offset,
            "outputFields": ["id"],
        })
        if not isinstance(data, list) or not data:
            break
        all_ids.extend([e["id"] for e in data])
        if len(data) < page:
            break
        offset += page

    docs = []
    batch_size = 50
    for i in range(0, len(all_ids), batch_size):
        batch_ids = all_ids[i:i + batch_size]
        data = _post_milvus("/v2/vectordb/entities/get", {
            "collectionName": COLLECTION, "dbName": DB, "id": batch_ids,
        })
        docs.extend(data if isinstance(data, list) else [])
    return docs


def build_local_bm25():
    """拉取全部文档，构建 jieba BM25 索引（全局单例）"""
    global _bm25_index, _bm25_docs
    if _bm25_index is not None:
        return
    print("[BM25] Fetching all documents from Milvus...")
    _bm25_docs = _fetch_all_docs()
    texts = [_entity_to_doc(d).get("retrieval_text", _entity_to_doc(d).get("text", "")) for d in _bm25_docs]
    tokenized = [chinese_tokenize(t) for t in texts]
    _bm25_index = BM25Okapi(tokenized)
    print(f"[BM25] Local jieba index ready: {len(_bm25_docs)} docs")


def local_bm25_search(query: str, top_k: int = 50) -> list:
    """本地 jieba BM25 检索，返回 List[doc_dict]"""
    if _bm25_index is None:
        build_local_bm25()
    tokenized = chinese_tokenize(query)
    scores = _bm25_index.get_scores(tokenized)
    top_indices = np.argsort(scores)[-top_k:][::-1]
    results = []
    for idx in top_indices:
        if scores[idx] > 0 and idx < len(_bm25_docs):
            doc = _entity_to_doc(_bm25_docs[idx], float(scores[idx]))
            results.append(doc)
    return results


def _get_client():
    if not hasattr(_thread_local, "client"):
        _thread_local.client = httpx.Client(timeout=httpx.Timeout(60))
    return _thread_local.client


def embed(texts):
    r = _get_client().post(f"{MODEL_URL}/embed", json={"texts": texts})
    r.raise_for_status()
    return r.json()["embeddings"]


def rerank(query, documents, top_k=5):
    r = _get_client().post(f"{MODEL_URL}/rerank", json={
        "query": query, "documents": documents, "top_k": top_k,
    })
    r.raise_for_status()
    return r.json()["results"]


def _post_milvus(endpoint, payload):
    r = _get_client().post(f"{MILVUS_URL}{endpoint}", json=payload)
    r.raise_for_status()
    body = r.json()
    if body.get("code") != 0:
        raise RuntimeError(f"Milvus error code={body.get('code')}: {body.get('message','')}")
    return body.get("data", {})


def _entity_to_doc(entity, score=None):
    d = dict(entity)
    doc = {
        "id": str(d.get("id", "")),
        "retrieval_text": d.get("retrieval_text", ""),
        "text": d.get("text", ""),
        "score": float(score) if score is not None else 0.0,
    }
    for key in ("law_name", "article_id", "chunk_type", "parent_id",
                "title", "source_doc"):
        doc[key] = str(d.get(key, ""))
    return doc


def milvus_dense(vector, top_k=50):
    payload = {
        "collectionName": COLLECTION, "dbName": DB,
        "data": [vector],
        "annsField": DENSE_FIELD,
        "limit": top_k,
        "outputFields": OUTPUT_FIELDS,
        "searchParams": {"metric_type": "COSINE"},
    }
    data = _post_milvus("/v2/vectordb/entities/search", payload)
    if not data:
        return []
    hits = data[0] if isinstance(data[0], list) else data
    return [_entity_to_doc(h, h.get("distance")) for h in hits]


def rrf_fusion(dense_results, bm25_results, k=60):
    scores = {}
    result_map = {}
    for rank, r in enumerate(dense_results, 1):
        did = r.get("id", "")
        scores[did] = scores.get(did, 0) + 1.0 / (k + rank)
        result_map[did] = r
    for rank, r in enumerate(bm25_results, 1):
        did = r.get("id", "")
        scores[did] = scores.get(did, 0) + 1.0 / (k + rank)
        if did not in result_map:
            result_map[did] = r
    sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [result_map[did] for did, _ in sorted_ids if did in result_map]


def search_one(query, top_k=5):
    """检索并返回 (final_results, dense_results, bm25_results, fused_results)"""
    vec = embed([query])[0]
    dense = milvus_dense(vec, DENSE_RECALL)
    bm25 = local_bm25_search(query, BM25_RECALL)
    fused = rrf_fusion(dense, bm25, RRF_K)

    pool = fused[:RERANK_POOL]
    docs_for_rerank = [r.get("text", "")[:1024] for r in pool]
    if docs_for_rerank:
        reranked = rerank(query, docs_for_rerank, top_k)
        results = []
        for rr in reranked:
            idx = rr["index"]
            if idx < len(pool):
                r = dict(pool[idx])
                r["score"] = rr["score"]
                results.append(r)
        return results[:top_k], dense, bm25, fused
    return fused[:top_k], dense, bm25, fused


def load_eval_set():
    with open(EVAL_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("qa_pairs", [])


def _get_rank(result_list, target_ids, top_k=5):
    """返回 target 在 result_list 中的首次命中 rank (1-based)，否则 0"""
    for rank, r in enumerate(result_list[:top_k], 1):
        if r.get("id", "") in target_ids:
            return rank
    return 0


def eval_one(qa):
    question = qa["question"]
    expected_id = qa.get("expected_chunk_id", "")
    acceptable_ids = qa.get("acceptable_chunk_ids", [])
    if not isinstance(acceptable_ids, list):
        acceptable_ids = []
    target_ids = {expected_id} | set(acceptable_ids) if expected_id else set(acceptable_ids)

    qa_type = qa.get("type", qa.get("chunk_type", "unknown"))
    span = qa.get("span", "single")
    question_type = qa.get("question_type", "unknown")
    retrieval_difficulty = qa.get("retrieval_difficulty", "unknown")

    try:
        final_results, dense_results, bm25_results, fused_results = search_one(question, TOP_K)
    except Exception as e:
        return {
            "final_rank": 0, "dense_rank": 0, "bm25_rank": 0, "fused_rank": 0,
            "qa_type": qa_type, "span": span,
            "question_type": question_type, "retrieval_difficulty": retrieval_difficulty,
            "miss_info": {
                "question": question[:100],
                "expected_id": expected_id[:60],
                "error": str(e)[:120],
            },
        }

    dense_rank = _get_rank(dense_results, target_ids)
    bm25_rank = _get_rank(bm25_results, target_ids)
    fused_rank = _get_rank(fused_results, target_ids)

    if not final_results:
        return {
            "final_rank": 0, "dense_rank": dense_rank, "bm25_rank": bm25_rank, "fused_rank": fused_rank,
            "qa_type": qa_type, "span": span,
            "question_type": question_type, "retrieval_difficulty": retrieval_difficulty,
            "miss_info": {
                "question": question[:100],
                "expected_id": expected_id[:60],
                "results": "NO RESULTS",
            },
        }

    final_rank = _get_rank(final_results, target_ids)

    if final_rank == 0:
        return {
            "final_rank": 0, "dense_rank": dense_rank, "bm25_rank": bm25_rank, "fused_rank": fused_rank,
            "qa_type": qa_type, "span": span,
            "question_type": question_type, "retrieval_difficulty": retrieval_difficulty,
            "miss_info": {
                "question": question[:100],
                "expected_id": expected_id[:60],
                "law_name": qa.get("law_name", "")[:40],
                "span": span,
                "type": qa_type,
                "question_type": question_type,
                "retrieval_difficulty": retrieval_difficulty,
                "top1_id": final_results[0].get("id", "")[:60] if final_results else "",
            },
        }
    return {
        "final_rank": final_rank, "dense_rank": dense_rank, "bm25_rank": bm25_rank, "fused_rank": fused_rank,
        "qa_type": qa_type, "span": span,
        "question_type": question_type, "retrieval_difficulty": retrieval_difficulty,
        "miss_info": None,
    }


def evaluate():
    print("=" * 60)
    print(f"V6 Standalone Recall Eval — {WORKERS} workers (local jieba BM25)")
    print("=" * 60)

    # 预热本地 BM25 索引
    build_local_bm25()

    eval_set = load_eval_set()
    total = len(eval_set)
    print(f"Eval set: {total} items\n")

    def _make_stat():
        return {"total": 0, "hits": {1: 0, 3: 0, 5: 0}}

    # 各阶段独立统计
    stage_names = ["dense", "bm25", "fused", "final"]
    stage_hits = {s: {1: 0, 3: 0, 5: 0} for s in stage_names}
    by_type = defaultdict(_make_stat)
    by_span = defaultdict(_make_stat)
    by_qtype = defaultdict(_make_stat)
    by_rdiff = defaultdict(_make_stat)
    misses = []
    completed = 0
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(eval_one, qa): idx for idx, qa in enumerate(eval_set)}

        for future in as_completed(futures):
            r = future.result()
            final_rank = r["final_rank"]
            dense_rank = r["dense_rank"]
            bm25_rank = r["bm25_rank"]
            fused_rank = r["fused_rank"]
            qa_type = r["qa_type"]
            span = r["span"]
            qtype = r["question_type"]
            rdiff = r["retrieval_difficulty"]

            with _lock:
                completed += 1
                by_type[qa_type]["total"] += 1
                by_span[span]["total"] += 1
                by_qtype[qtype]["total"] += 1
                by_rdiff[rdiff]["total"] += 1

                # 汇总各阶段 hit
                for stage, rank_val in [("dense", dense_rank), ("bm25", bm25_rank),
                                         ("fused", fused_rank), ("final", final_rank)]:
                    if rank_val == 1:
                        stage_hits[stage][1] += 1; stage_hits[stage][3] += 1; stage_hits[stage][5] += 1
                    elif rank_val in (2, 3):
                        stage_hits[stage][3] += 1; stage_hits[stage][5] += 1
                    elif rank_val in (4, 5):
                        stage_hits[stage][5] += 1

                # final 维度统计（与旧版兼容）
                if final_rank == 1:
                    for d in [by_type[qa_type], by_span[span], by_qtype[qtype], by_rdiff[rdiff]]:
                        d["hits"][1] += 1; d["hits"][3] += 1; d["hits"][5] += 1
                elif final_rank in (2, 3):
                    for d in [by_type[qa_type], by_span[span], by_qtype[qtype], by_rdiff[rdiff]]:
                        d["hits"][3] += 1; d["hits"][5] += 1
                elif final_rank in (4, 5):
                    for d in [by_type[qa_type], by_span[span], by_qtype[qtype], by_rdiff[rdiff]]:
                        d["hits"][5] += 1
                else:
                    misses.append(r.get("miss_info"))

                if completed % 50 == 0 or completed == total:
                    elapsed = time.time() - t0
                    eta = elapsed / completed * (total - completed) if completed else 0
                    print(f"  [{completed}/{total}] {completed/total*100:.0f}%  "
                          f"R@1={stage_hits['final'][1]}  R@5={stage_hits['final'][5]}  "
                          f"{elapsed:.0f}s  ETA {eta:.0f}s")

    # ── 输出 ──
    print("\n" + "=" * 60)
    print("RESULTS — Chunk ID Recall")
    print(f"Total: {total}")
    print("=" * 60)

    print(f"\n## 各阶段召回率对比")
    print(f"| 阶段 | Recall@1 | Recall@3 | Recall@5 |")
    print(f"|------|----------|----------|----------|")
    stage_labels = {"dense": "Dense only", "bm25": "BM25 (jieba)", "fused": "RRF fused", "final": "Reranker final"}
    for s in stage_names:
        r1 = stage_hits[s][1] / total * 100 if total else 0
        r3 = stage_hits[s][3] / total * 100 if total else 0
        r5 = stage_hits[s][5] / total * 100 if total else 0
        print(f"| {stage_labels[s]} | {r1:.1f}% | {r3:.1f}% | {r5:.1f}% |")

    def _print_section(title, data):
        print(f"\n## {title}")
        for key in sorted(data.keys()):
            s = data[key]; n = s["total"]
            r1 = s['hits'][1]/n*100 if n else 0
            r3 = s['hits'][3]/n*100 if n else 0
            r5 = s['hits'][5]/n*100 if n else 0
            print(f"  {key}: {n}题, R@1={r1:.1f}%, R@3={r3:.1f}%, R@5={r5:.1f}%")

    _print_section("按 chunk_type (final)", by_type)
    _print_section("按 question_type (final)", by_qtype)
    _print_section("按 retrieval_difficulty (final)", by_rdiff)
    _print_section("按 span (final)", by_span)

    if misses:
        print(f"\n## Miss 样本 (前 20 / 共 {len(misses)})")
        for i, m in enumerate(misses[:20]):
            if m:
                print(f"  {i+1}. [{m.get('question_type','')}][{m.get('retrieval_difficulty','')}] {m['question'][:80]}")
                print(f"     expected: {m['expected_id'][:70]}")
                print(f"     top1: {m.get('top1_id','')[:70]}")

    # ── 写报告 ──
    _write_report(total, stage_hits, by_type, by_qtype, by_rdiff, by_span, misses)
    print(f"\n报告已输出: {OUTPUT_PATH}")


def _write_report(total, stage_hits, by_type, by_qtype, by_rdiff, by_span, misses):
    lines = [
        "# V6 召回评测报告 — Chunk ID 匹配（本地 jieba BM25）",
        "",
        f"**评测集**: v6_benchmark.json, {total} 题",
        "**评测方式**: 纯 chunk ID 匹配（expected_chunk_id / acceptable_chunk_ids）",
        "**BM25**: 本地 jieba 分词（与生产管线一致），替代 Milvus 内置字符 n-gram",
        "",
        "## 各阶段召回率对比",
        "",
        "| 阶段 | Recall@1 | Recall@3 | Recall@5 |",
        "|------|----------|----------|----------|",
    ]
    stage_labels = {"dense": "Dense only", "bm25": "BM25 (jieba)", "fused": "RRF fused", "final": "Reranker final"}
    for s in ["dense", "bm25", "fused", "final"]:
        sh = stage_hits[s]
        r1 = sh[1] / total * 100 if total else 0
        r3 = sh[3] / total * 100 if total else 0
        r5 = sh[5] / total * 100 if total else 0
        lines.append(f"| {stage_labels[s]} | {r1:.1f}% | {r3:.1f}% | {r5:.1f}% |")
    lines.append("")

    # final/reranker 整体
    final_hits = stage_hits["final"]
    lines += [
        "## 最终召回率 (Reranker 后)",
        "",
        "| 指标 | 命中 | 总数 | 比率 |",
        "|------|------|------|------|",
    ]
    for k in [1, 3, 5]:
        rate = final_hits[k] / total * 100 if total else 0
        lines.append(f"| Recall@{k} | {final_hits[k]} | {total} | **{rate:.1f}%** |")
    lines.append("")

    def _write_section(title, data):
        lines.append(f"## {title}")
        lines.append("")
        lines.append("| 类型 | 题数 | Recall@1 | Recall@3 | Recall@5 |")
        lines.append("|------|------|----------|----------|----------|")
        for key in sorted(data.keys()):
            s = data[key]; n = s["total"]
            r1 = s["hits"][1]/n*100 if n else 0
            r3 = s["hits"][3]/n*100 if n else 0
            r5 = s["hits"][5]/n*100 if n else 0
            lines.append(f"| {key} | {n} | {r1:.1f}% | {r3:.1f}% | **{r5:.1f}%** |")
        lines.append("")

    _write_section("按 chunk_type", by_type)
    _write_section("按 question_type (题型)", by_qtype)
    _write_section("按 retrieval_difficulty (检索难度)", by_rdiff)
    _write_section("按 span", by_span)

    # ── 交叉分析: chunk_type × question_type ──
    lines.append("## 交叉分析: chunk_type × question_type")
    lines.append("")
    lines.append("| chunk_type \\ question_type | " + " | ".join(sorted(by_qtype.keys())) + " |")
    lines.append("|" + "---|" * (len(by_qtype) + 1))
    # 待实现: 需要逐题数据

    if misses:
        lines += [f"## Miss 样本", "", f"共 {len(misses)} 条 (R@5 仍未命中):", ""]
        for i, m in enumerate(misses[:30]):
            if m:
                lines.append(f"{i+1}. [{m.get('question_type','?')}][{m.get('retrieval_difficulty','?')}] {m['question'][:100]}")
                lines.append(f"   - expected: `{m['expected_id'][:80]}`")
                lines.append(f"   - top1: `{m.get('top1_id', '')[:80]}`")
                lines.append("")
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    evaluate()
