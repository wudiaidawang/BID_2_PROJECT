#!/usr/bin/env python3
"""轻量诊断：逐题 Dense vs BM25 Pool@30 对比"""

import json, time
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx, numpy as np, jieba
from rank_bm25 import BM25Okapi

MILVUS_URL = "http://localhost:19531"
MODEL_URL = "http://localhost:8210"
COLLECTION = "policy_v9"
DB = "panxin_dev"
WORKERS = 3
TOP_K = 30

EVAL_PATH = Path("/home/admin/eval_v11/data/eval_questions/v9/v9_canonical.jsonl")
OUT_PATH = Path("/home/admin/eval_v11/data/eval_questions/v12/dense_bm25_per_question.json")


def _post_milvus(endpoint, payload):
    r = httpx.post(f"{MILVUS_URL}{endpoint}", json=payload, timeout=60)
    r.raise_for_status()
    body = r.json()
    return body.get("data", body)


def chinese_tokenize(text):
    return [w for w in jieba.cut(str(text)) if w.strip()]


def embed_query(text):
    r = httpx.post(f"{MODEL_URL}/embed", json={"texts": [text]}, timeout=30)
    return r.json()["embeddings"][0]


# ── Load eval set ──
items = []
with open(EVAL_PATH, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            items.append(json.loads(line))
print(f"Loaded {len(items)} questions")

# ── Build BM25 index (matching eval_standalone.py) ──
print("Fetching all documents from Milvus...")
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
print(f"  IDs: {len(all_ids)}")

all_docs_raw = []
batch_size = 50
for i in range(0, len(all_ids), batch_size):
    batch_ids = all_ids[i:i + batch_size]
    data = _post_milvus("/v2/vectordb/entities/get", {
        "collectionName": COLLECTION, "dbName": DB,
        "id": batch_ids,
    })
    all_docs_raw.extend(data if isinstance(data, list) else [])

all_docs = []
for doc in all_docs_raw:
    d = {
        "id": doc.get("id", ""),
        "text": doc.get("text", ""),
        "retrieval_text": doc.get("retrieval_text", ""),
        "chunk_type": doc.get("chunk_type", ""),
        "law_name": doc.get("law_name", ""),
        "article_id": str(doc.get("article_id", "")),
    }
    all_docs.append(d)

bm25_texts = [d.get("retrieval_text", d.get("text", "")) for d in all_docs]
bm25_tokenized = [chinese_tokenize(t) for t in bm25_texts]
bm25_index = BM25Okapi(bm25_tokenized)
print(f"BM25 ready: {len(all_docs)} docs")


# ── Search per question ──
def search_one(item):
    q = item.get("question", "")
    target_ids = set()
    target_ids.add(item.get("expected_chunk_id", ""))
    for aid in item.get("acceptable_chunk_ids", []):
        target_ids.add(aid)
    target_ids.discard("")

    try:
        q_vec = embed_query(q)
    except Exception:
        q_vec = None
    qtokens = chinese_tokenize(q)

    # Dense search
    dense_rank, dense_pool = 99, False
    if q_vec:
        try:
            resp = _post_milvus("/v2/vectordb/entities/search", {
                "collectionName": COLLECTION, "dbName": DB,
                "data": [q_vec],
                "annsField": "dense_vector",
                "limit": TOP_K,
                "outputFields": ["id"],
                "searchParams": {"metric_type": "COSINE"},
            })
            dense_ids = [r.get("id", "") for r in (resp if isinstance(resp, list) else [])]
            for rank, did in enumerate(dense_ids, 1):
                if did in target_ids:
                    dense_rank = rank
                    dense_pool = True
                    break
        except Exception:
            pass

    # BM25 search
    bm25_rank, bm25_pool = 99, False
    try:
        bm25_scores = bm25_index.get_scores(qtokens)
        bm25_top = list(np.argsort(bm25_scores)[-TOP_K:][::-1])
        for rank, idx in enumerate(bm25_top, 1):
            did = all_docs[idx].get("id", "")
            if did in target_ids:
                bm25_rank = rank
                bm25_pool = True
                break
    except Exception:
        pass

    # Collect extra info for analysis
    return {
        "question": q,
        "expected_id": item.get("expected_chunk_id", ""),
        "span": item.get("span", ""),
        "type": item.get("chunk_type", item.get("type", "")),
        "question_type": item.get("question_type", ""),
        "retrieval_difficulty": item.get("retrieval_difficulty", ""),
        "law_name": item.get("law_name", ""),
        "dense_rank": dense_rank,
        "bm25_rank": bm25_rank,
        "dense_pool": dense_pool,
        "bm25_pool": bm25_pool,
    }


# ── Run ──
results = []
start = time.time()
with ThreadPoolExecutor(max_workers=WORKERS) as ex:
    futures = {ex.submit(search_one, item): i for i, item in enumerate(items)}
    for f in as_completed(futures):
        results.append(f.result())
        if len(results) % 200 == 0:
            elapsed = int(time.time() - start)
            print(f"  [{len(results)}/{len(items)}] {elapsed}s")

elapsed = int(time.time() - start)
print(f"Done in {elapsed}s ({elapsed/60:.1f}m)")

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"Saved: {OUT_PATH}")
