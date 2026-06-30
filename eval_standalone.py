#!/usr/bin/env python3
"""Standalone V6 召回评测 — 本地 jieba BM25 + 远程 Embedding/Reranker + 各阶段分解，N 并发"""

import json, re, sys, threading, time, os
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

EVAL_PATH = Path(__file__).parent / "data" / "eval_questions" / "v7" / "v7_benchmark.jsonl"
OUTPUT_PATH = Path(__file__).parent / "data" / "eval_questions" / "v7" / "v7_recall_report.md"

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


# ── Parent Context 扩展（与生产管线 app/pipeline/expanders.py 对齐）──
_parent_map: dict = {}  # doc_id → full entity (含 chapter_context, parent_id 等)


def build_parent_map():
    """从 BM25 已拉取的文档构建 parent 查找表"""
    global _parent_map
    if _parent_map:
        return
    for d in _bm25_docs:
        did = str(d.get("id", ""))
        if did:
            _parent_map[did] = d
    print(f"[ParentExpand] Lookup map ready: {len(_parent_map)} docs")


def _get_field(doc: dict, key: str) -> str:
    """优先顶层字段，其次从 metadata/data 嵌套中取（兼容实体原始格式）"""
    val = doc.get(key, "")
    if val:
        return str(val)
    meta = doc.get("metadata") or doc.get("data", {})
    return str(meta.get(key, "")) if meta else ""


def parent_context_expand(results: list) -> list:
    """Child chunk → 查找 parent，注入 parent_content。（不去重，保留全部候选项供 reranker 精排）"""
    if not _parent_map:
        build_parent_map()

    enriched = []
    for r in results:
        r = dict(r)  # 浅拷贝，避免污染上游 fused 列表
        chapter_context = _get_field(r, "chapter_context")
        chunk_type = _get_field(r, "chunk_type")

        if chapter_context:
            r["parent_content"] = chapter_context
        elif chunk_type.endswith("_child"):
            parent_id = _get_field(r, "parent_id")
            parent_entity = _parent_map.get(parent_id) if parent_id else None
            if parent_entity:
                parent_doc = _entity_to_doc(parent_entity)
                r["parent_content"] = parent_doc.get("text", "")
            else:
                r["parent_content"] = r.get("text", "")

        enriched.append(r)

    enriched.sort(key=lambda x: x.get("score", 0), reverse=True)
    return enriched


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
                "title", "source_doc", "chapter_context"):
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
    results = []
    for did, score in sorted_ids:
        if did in result_map:
            result_map[did]["score"] = score
            results.append(result_map[did])
    return results


# ── Query 预处理（精简版，与生产管线 app/pipeline/preprocessor.py + query_rewriter.py 对齐）──
COLLOQUIAL_MAP = {
    "搞": "进行", "得": "应当", "能": "可以", "能不能": "是否可以",
    "规矩": "原则", "好处": "财物", "啥时候": "何时", "啥时间": "何时",
    "几天": "几日内", "多少天": "多少日内", "多长时间": "多久",
    "最少": "至少", "几家": "几个", "改": "修改", "退": "退还",
    "签": "订立", "哪儿": "何处", "哪里": "何处", "咋": "如何",
    "干": "实施", "弄": "进行", "咋整": "如何处理", "晚到": "逾期",
    "交": "提交", "拆成": "拆分", "行不行": "是否可行", "有没有": "是否存在",
    "行": "可以", "罚": "处罚", "用了": "采用", "收": "收取", "定": "确定",
    "找": "提出", "替": "代替", "小段": "标段", "发": "发布", "看": "踏勘",
    "给": "予以", "说": "说明", "知道": "知悉", "选": "确定", "谁": "何人",
    "包": "转包", "该找谁": "应向何人提出", "多少钱": "多少金额",
    "花多少": "金额多少", "超了": "超过", "要不要": "是否需要",
    "可不": "是否", "最晚": "最迟", "该不该": "是否应当", "算不算": "是否属于",
    "有什么": "有哪些", "还要不要": "是否还需要", "能直接": "是否可以直接",
    "能不能不": "是否可以免于", "可不可以": "是否可以", "最多": "不得超过",
    "啥时候提": "何时提出", "咋办": "如何处理", "有啥": "有何",
    "多久": "多长时间", "没了": "丧失", "归谁": "由谁",
}
COLLOQUIAL_SORTED = sorted(COLLOQUIAL_MAP.keys(), key=len, reverse=True)

REDUNDANT_PHRASES = [
    "我想问一下", "我想请问", "我想知道", "请问一下",
    "帮我查一下", "帮我看看", "我想了解一下", "麻烦问一下",
    "能不能告诉我", "可以告诉我", "请问您", "请问你",
    "请告诉我", "请帮我查", "我想咨询", "想了解",
    "咨询一下", "问一下", "请问", "想问",
]

SYNONYMS = {
    "投标人": ["供应商", "潜在投标人", "投标方"],
    "排斥": ["限制", "排除", "歧视"],
    "处罚": ["罚款", "处分", "惩戒"],
    "没收": ["不予退还", "不退还"],
    "禁止": ["不得", "不允许", "严禁"],
    "透露": ["泄露", "泄漏", "泄密"],
    "保证金": ["投标保证金", "履约保证金"],
    "撤回": ["撤销", "收回"],
    "分包": ["转包", "分包人"],
    "废标": ["流标", "无效投标"],
    "围标": ["串标", "串通投标"],
    "指定": ["标明", "要求", "限定"],
    "品牌": ["厂家", "制造商", "生产商"],
    "资质": ["资格", "资信"],
}
DEFINITION_PATTERNS = [
    "是什么", "什么是", "的定义", "定义是",
    "什么意思", "指的是", "是指", "指的是什么",
    "概念", "含义", "如何理解",
]


def _colloquial_replace_safe(text: str) -> str:
    """词边界感知的口语→书面语替换。
    多字口语词直接替换（不易误伤复合词）；
    单字口语词仅当作为独立 jieba token 时才替换，避免"交易"→"提交易"。
    """
    result = text
    # 多字词（2+ chars）：直接替换，按长度降序
    for cw in COLLOQUIAL_SORTED:
        if len(cw) >= 2 and cw in result:
            result = result.replace(cw, COLLOQUIAL_MAP[cw])

    # 单字词：仅当作为独立 token 时才替换
    single_chars = {k: v for k, v in COLLOQUIAL_MAP.items() if len(k) == 1}
    if single_chars and result:
        tokens = list(jieba.cut(result))
        new_tokens = [single_chars.get(t, t) for t in tokens]
        result = "".join(new_tokens)

    return result


def preprocess_query(query: str) -> str:
    """精简版查询预处理：冗余去除 → 口语规范化 → 同义词扩展（定义类跳过）"""
    if not query:
        return query

    q = query.strip()

    # 1. 冗余去除
    for phrase in REDUNDANT_PHRASES:
        q = q.replace(phrase, "", 1)
        if phrase.startswith(q[:min(len(phrase), len(q))]):
            break
    q = q.strip()

    # 2. 口语→书面语（词边界感知）
    q = _colloquial_replace_safe(q)

    # 3. 同义词扩展（定义类问题跳过）
    is_definition = any(pat in q for pat in DEFINITION_PATTERNS)
    if not is_definition:
        expanded = q
        for term, syns in SYNONYMS.items():
            if term in q:
                for s in syns:
                    if s not in expanded:
                        expanded += " " + s
            else:
                for s in syns:
                    if s in q:
                        if term not in expanded:
                            expanded += " " + term
                        break
        q = expanded

    return q


# ── Weighted Fusion（对齐生产管线 app/pipeline/fusion.py WeightedFusion）──

KEYWORD_HEAVY_PATTERNS = [
    r"第\d+条", r"编号|标段|资质|建造师|注册资本",
    r"限价|保证金|资格条件",
]

SEMANTIC_HEAVY_PATTERNS = [
    r"什么是|是什么|定义|解释|含义|概念|意思",
    r"如何|怎么|怎样|步骤|流程|操作|办理",
    r"背景|原因|目的|意义|解读|分析",
    r"区别|不同|对比|比较",
    r"串通|围标|陪标|挂靠",
    r"投标人|招标人|评标",
]

# ── 法规实体检测从统一注册中心导入 ──
from app.core.legal_entity_registry import detect_regulation_entity


def _detect_query_type(query: str) -> str:
    """检测查询类型: keyword_heavy / semantic_heavy / balanced"""
    for pattern in KEYWORD_HEAVY_PATTERNS:
        if re.search(pattern, query):
            return "keyword_heavy"
    for pattern in SEMANTIC_HEAVY_PATTERNS:
        if re.search(pattern, query):
            return "semantic_heavy"
    return "balanced"


def _get_dynamic_weights(query: str) -> tuple:
    """根据查询类型返回 (bm25_weight, dense_weight)"""
    qtype = _detect_query_type(query)
    has_regulation = detect_regulation_entity(query)

    if has_regulation:
        return (0.80, 0.20)  # 法条/法规名 → BM25 最重
    if qtype == "keyword_heavy":
        return (0.75, 0.25)
    elif qtype == "semantic_heavy":
        return (0.40, 0.60)
    return (0.65, 0.35)


def _min_max_normalize(scores: list) -> list:
    if not scores:
        return []
    mn, mx = min(scores), max(scores)
    if mx == mn:
        return [0.5] * len(scores)
    return [(s - mn) / (mx - mn) for s in scores]


def weighted_fusion(dense_results, bm25_results, query, top_k=50):
    """加权融合：Min-Max 归一化 + 动态权重 + 基于查询类型选择性 Boost

    对齐生产管线 WeightedFusion.merge()，但对 eval 场景简化 Boost 逻辑。
    """
    if not dense_results:
        return bm25_results[:top_k]
    if not bm25_results:
        return dense_results[:top_k]

    bm25_w, dense_w = _get_dynamic_weights(query)
    qtype = _detect_query_type(query)
    has_reg = detect_regulation_entity(query)

    # Min-Max 归一化
    dense_scores = [r.get("score", 0) for r in dense_results]
    bm25_scores = [r.get("score", 0) for r in bm25_results]
    dense_norm = _min_max_normalize(dense_scores)
    bm25_norm = _min_max_normalize(bm25_scores)

    merged = {}
    for i, r in enumerate(dense_results):
        did = r.get("id", "")
        base = dense_w * (dense_norm[i] if i < len(dense_norm) else 0)
        # 法条/法规查询: Dense 结果中的 child/parent chunk 降权 (BM25 更可靠)
        chunk_type = r.get("chunk_type", "")
        if has_reg and chunk_type in ("pdf_law_child", "pdf_law_parent"):
            base *= 0.8
        merged[did] = dict(r, score=base)

    for i, r in enumerate(bm25_results):
        did = r.get("id", "")
        base = bm25_w * (bm25_norm[i] if i < len(bm25_norm) else 0)
        # 法条匹配 Boost: BM25 结果中含 article_id 或法条号 → 额外加分
        text = r.get("retrieval_text", r.get("text", ""))
        if has_reg and re.search(r"第[一二三四五六七八九十百零\d]+条", text):
            base += 0.10
        if did in merged:
            if base > merged[did]["score"]:
                merged[did] = dict(r, score=base)
        else:
            merged[did] = dict(r, score=base)

    sorted_results = sorted(merged.values(), key=lambda x: x["score"], reverse=True)
    return sorted_results[:top_k]


def search_one(query, top_k=5):
    """预处理 + 5阶段检索"""
    processed = preprocess_query(query)
    vec = embed([processed])[0]
    dense = milvus_dense(vec, DENSE_RECALL)
    bm25 = local_bm25_search(processed, BM25_RECALL)
    fused = weighted_fusion(dense, bm25, processed, DENSE_RECALL)
    expanded = parent_context_expand(fused)

    pool = expanded[:RERANK_POOL]
    docs_for_rerank = [
        r.get("parent_content") or r.get("retrieval_text") or r.get("text", "")
        for r in pool
    ]
    docs_for_rerank = [d[:1024] for d in docs_for_rerank]
    if docs_for_rerank:
        reranked = rerank(query, docs_for_rerank, top_k)
        results = []
        for rr in reranked:
            idx = rr["index"]
            if idx < len(pool):
                r = dict(pool[idx])
                r["score"] = rr["score"]
                results.append(r)
        return results[:top_k], dense, bm25, fused, expanded
    return expanded[:top_k], dense, bm25, fused, expanded


def load_eval_set():
    """V7 JSONL 格式: 每行一个 JSON 对象"""
    items = []
    with open(EVAL_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


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

    qa_type = qa.get("chunk_type", qa.get("type", "unknown"))
    span = qa.get("span", "single")
    question_type = qa.get("question_type", "unknown")
    retrieval_difficulty = qa.get("retrieval_difficulty", "unknown")
    benchmark_level = qa.get("benchmark_level", "unknown")
    law_name = qa.get("law_name", "")

    try:
        final_results, dense_results, bm25_results, fused_results, expanded_results = search_one(question, TOP_K)
    except Exception as e:
        return {
            "final_rank": 0, "dense_rank": 0, "bm25_rank": 0, "fused_rank": 0, "expanded_rank": 0,
            "qa_type": qa_type, "span": span,
            "question_type": question_type, "retrieval_difficulty": retrieval_difficulty,
            "benchmark_level": benchmark_level,
            "miss_info": {
                "question": question[:100],
                "expected_id": expected_id[:60],
                "error": str(e)[:120],
            },
        }

    dense_rank = _get_rank(dense_results, target_ids)
    bm25_rank = _get_rank(bm25_results, target_ids)
    fused_rank = _get_rank(fused_results, target_ids)
    expanded_rank = _get_rank(expanded_results, target_ids)

    if not final_results:
        return {
            "final_rank": 0, "dense_rank": dense_rank, "bm25_rank": bm25_rank, "fused_rank": fused_rank, "expanded_rank": expanded_rank,
            "qa_type": qa_type, "span": span,
            "question_type": question_type, "retrieval_difficulty": retrieval_difficulty,
            "benchmark_level": benchmark_level,
            "miss_info": {
                "question": question[:100],
                "expected_id": expected_id[:60],
                "results": "NO RESULTS",
            },
        }

    final_rank = _get_rank(final_results, target_ids)

    if final_rank == 0:
        return {
            "final_rank": 0, "dense_rank": dense_rank, "bm25_rank": bm25_rank, "fused_rank": fused_rank, "expanded_rank": expanded_rank,
            "qa_type": qa_type, "span": span,
            "question_type": question_type, "retrieval_difficulty": retrieval_difficulty,
            "benchmark_level": benchmark_level,
            "miss_info": {
                "question": question[:100],
                "expected_id": expected_id[:60],
                "law_name": law_name[:40],
                "span": span,
                "type": qa_type,
                "question_type": question_type,
                "retrieval_difficulty": retrieval_difficulty,
                "top1_id": final_results[0].get("id", "")[:60] if final_results else "",
            },
        }
    return {
        "final_rank": final_rank, "dense_rank": dense_rank, "bm25_rank": bm25_rank, "fused_rank": fused_rank, "expanded_rank": expanded_rank,
        "qa_type": qa_type, "span": span,
        "question_type": question_type, "retrieval_difficulty": retrieval_difficulty,
        "benchmark_level": benchmark_level,
        "miss_info": None,
    }


def evaluate():
    print("=" * 60)
    print(f"V6 Standalone Recall Eval — {WORKERS} workers (local jieba BM25)")
    print("=" * 60)

    # 预热本地 BM25 索引和 Parent 查找表
    build_local_bm25()
    build_parent_map()

    eval_set = load_eval_set()
    total = len(eval_set)
    print(f"Eval set: {total} items\n")

    def _make_stat():
        return {"total": 0, "hits": {1: 0, 3: 0, 5: 0}}

    # 各阶段独立统计
    stage_names = ["dense", "bm25", "fused", "expanded", "final"]
    stage_hits = {s: {1: 0, 3: 0, 5: 0} for s in stage_names}
    by_type = defaultdict(_make_stat)
    by_span = defaultdict(_make_stat)
    by_qtype = defaultdict(_make_stat)
    by_rdiff = defaultdict(_make_stat)
    by_blevel = defaultdict(_make_stat)
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
            expanded_rank = r["expanded_rank"]
            qa_type = r["qa_type"]
            span = r["span"]
            qtype = r["question_type"]
            rdiff = r["retrieval_difficulty"]
            blevel = r.get("benchmark_level", "unknown")

            with _lock:
                completed += 1
                by_type[qa_type]["total"] += 1
                by_span[span]["total"] += 1
                by_qtype[qtype]["total"] += 1
                by_rdiff[rdiff]["total"] += 1
                by_blevel[blevel]["total"] += 1

                # 汇总各阶段 hit
                for stage, rank_val in [("dense", dense_rank), ("bm25", bm25_rank),
                                         ("fused", fused_rank), ("expanded", expanded_rank),
                                         ("final", final_rank)]:
                    if rank_val == 1:
                        stage_hits[stage][1] += 1; stage_hits[stage][3] += 1; stage_hits[stage][5] += 1
                    elif rank_val in (2, 3):
                        stage_hits[stage][3] += 1; stage_hits[stage][5] += 1
                    elif rank_val in (4, 5):
                        stage_hits[stage][5] += 1

                # final 维度统计（与旧版兼容）
                if final_rank == 1:
                    for d in [by_type[qa_type], by_span[span], by_qtype[qtype], by_rdiff[rdiff], by_blevel[blevel]]:
                        d["hits"][1] += 1; d["hits"][3] += 1; d["hits"][5] += 1
                elif final_rank in (2, 3):
                    for d in [by_type[qa_type], by_span[span], by_qtype[qtype], by_rdiff[rdiff], by_blevel[blevel]]:
                        d["hits"][3] += 1; d["hits"][5] += 1
                elif final_rank in (4, 5):
                    for d in [by_type[qa_type], by_span[span], by_qtype[qtype], by_rdiff[rdiff], by_blevel[blevel]]:
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
    stage_labels = {"dense": "Dense only", "bm25": "BM25 (jieba)", "fused": "Weighted fused", "expanded": "Parent expanded", "final": "Reranker final"}
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

    _print_section("按 benchmark_level (final)", by_blevel)
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
    _write_report(total, stage_hits, by_type, by_qtype, by_rdiff, by_span, by_blevel, misses)
    print(f"\n报告已输出: {OUTPUT_PATH}")


def _write_report(total, stage_hits, by_type, by_qtype, by_rdiff, by_span, by_blevel, misses):
    lines = [
        "# V7 召回评测报告 — Chunk ID 匹配（加权融合 + 法条Boost）",
        "",
        f"**评测集**: v7_benchmark.jsonl, {total} 题 (canonical + natural + robust)",
        "**评测方式**: 纯 chunk ID 匹配（expected_chunk_id / acceptable_chunk_ids）",
        "**融合策略**: Weighted Fusion（Min-Max 归一化 + 动态权重 + 法条检测 Boost）",
        "**BM25**: 本地 jieba 分词",
        "",
        "## 各阶段召回率对比",
        "",
        "| 阶段 | Recall@1 | Recall@3 | Recall@5 |",
        "|------|----------|----------|----------|",
    ]
    stage_labels = {"dense": "Dense only", "bm25": "BM25 (jieba)", "fused": "Weighted fused", "expanded": "Parent expanded", "final": "Reranker final"}
    for s in stage_labels:
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

    _write_section("按 benchmark_level (改写层次)", by_blevel)
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
        for i, m in enumerate(misses):
            if m:
                lines.append(f"{i+1}. [{m.get('question_type','?')}][{m.get('retrieval_difficulty','?')}] {m['question'][:100]}")
                lines.append(f"   - expected: `{m['expected_id'][:80]}`")
                lines.append(f"   - top1: `{m.get('top1_id', '')[:80]}`")
                lines.append(f"   - law: `{m.get('law_name', '')[:60]}`")
                lines.append(f"   - type: `{m.get('type', '')}` | span: `{m.get('span', '')}`")
                lines.append("")
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # 保存完整 miss 数据为 JSON 便于分析
    import json as _json
    _json_path = OUTPUT_PATH.with_suffix(".misses.json")
    with open(_json_path, "w", encoding="utf-8") as f:
        _json.dump(misses, f, ensure_ascii=False, indent=2)
    print(f"\nMiss JSON saved: {_json_path} ({len(misses)} entries)")


if __name__ == "__main__":
    evaluate()
