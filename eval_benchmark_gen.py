#!/usr/bin/env python
"""
评测集自动生成器 —— Chunk → QA 模式

流程:
  1. 从 Milvus 分页导出所有 chunks (3 个 collection)
  2. 按 chunk_type 分层抽样
  3. LLM 基于真实 chunk 的 text 生成 QA 对
  4. expected_chunk_ids 直接从入参获取，不反查
  5. 输出 eval_benchmark_v1.json

生成类型:
  - single (1 chunk) — 事实型问答
  - double (2 chunks) — 对比/关联型问答
  - multi  (3 chunks) — 综合型问答

用法:
  python eval_benchmark_gen.py                    # 全量生成
  python eval_benchmark_gen.py --dry-run          # 预览抽样分布
  python eval_benchmark_gen.py --total 100        # 限制总数
"""

import sys
import json
import random
import hashlib
import argparse
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Optional

sys.path.insert(0, str(Path(__file__).parent))

from config import settings
from app.storage import get_vector_store

OUTPUT_PATH = Path(__file__).parent / "data" / "eval_questions" / "eval_benchmark_v1.json"

# 每种 chunk_type 最少抽样数
MIN_PER_TYPE = {
    "bid_project": 10,
    "regulation_parent": 8,
    "regulation_child": 5,
    "regulation_sliding": 3,
    "policy_doc": 5,
    "opinion_news": 8,
    "pdf_law_parent": 5,
    "pdf_law_child": 3,
    "pdf_law_sliding": 2,
    "pdf_case_sliding": 2,
}

# 问题类型配比
QA_TYPE_RATIO = {"single": 0.5, "double": 0.3, "multi": 0.2}


# ═══════════════════════════════════════════════════════════════
# Step 1: 导出 Milvus chunks
# ═══════════════════════════════════════════════════════════════

def export_all_chunks() -> List[Dict]:
    """从 3 个 Milvus collection 导出所有 chunks"""
    store = get_vector_store()
    all_chunks = []
    for coll in ["bids", "regulations", "policy"]:
        print(f"[导出] {coll} ...")
        try:
            chunks = store.get_all_documents(coll)
            for c in chunks:
                c["_collection"] = coll
            all_chunks.extend(chunks)
            print(f"  -> {len(chunks)} chunks")
        except Exception as e:
            print(f"  -> ERROR: {e}")
    return all_chunks


# ═══════════════════════════════════════════════════════════════
# Step 2: 分层抽样
# ═══════════════════════════════════════════════════════════════

def sample_chunks(chunks: List[Dict], max_total: int = 200) -> List[Dict]:
    """按 chunk_type 分层抽样"""
    by_type = defaultdict(list)
    for c in chunks:
        ct = c.get("metadata", {}).get("chunk_type", "unknown")
        by_type[ct].append(c)

    print("\n[抽样分布]")
    for ct in sorted(by_type.keys()):
        print(f"  {ct}: {len(by_type[ct])} total")

    # 按 MIN_PER_TYPE 抽样，剩余配额按比例分配
    sampled = []
    used_quota = 0
    for ct, min_n in MIN_PER_TYPE.items():
        pool = by_type.get(ct, [])
        n = min(min_n, len(pool))
        if pool:
            sampled.extend(random.sample(pool, n))
            used_quota += n

    remaining_quota = max_total - used_quota
    if remaining_quota > 0:
        # 按比例从剩余池中分配
        remaining_pools = {}
        for ct, pool in by_type.items():
            already = sum(1 for s in sampled
                         if s.get("metadata", {}).get("chunk_type") == ct)
            leftover = [c for c in pool if c not in sampled]
            if leftover:
                remaining_pools[ct] = leftover

        total_leftover = sum(len(p) for p in remaining_pools.values())
        if total_leftover > 0:
            for ct, pool in remaining_pools.items():
                extra = max(0, int(remaining_quota * len(pool) / total_leftover))
                extra = min(extra, len(pool))
                if extra > 0:
                    sampled.extend(random.sample(pool, extra))

    print(f"\n[抽样结果] {len(sampled)} chunks")
    for ct in sorted(by_type.keys()):
        n = sum(1 for s in sampled
                if s.get("metadata", {}).get("chunk_type") == ct)
        if n > 0:
            print(f"  {ct}: {n}")

    return sampled


# ═══════════════════════════════════════════════════════════════
# Step 3: LLM 生成 QA 对
# ═══════════════════════════════════════════════════════════════

def _llm_generate(prompt: str) -> Optional[str]:
    """调用 LLM 生成"""
    import httpx

    headers = {"Authorization": f"Bearer {settings.llm_api_key}",
               "Content-Type": "application/json"}
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": "你是一个专业的招投标领域评测集生成专家。只输出 JSON，不要任何解释。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
    }

    try:
        base_url = settings.llm_api_url.rstrip('/')
        if not base_url.endswith("/chat/completions"):
            url = f"{base_url}/chat/completions"
        else:
            url = base_url

        with httpx.Client(timeout=120) as client:
            resp = client.post(url, json=payload, headers=headers)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        print(f"  LLM error: {resp.status_code}")
        return None
    except Exception as e:
        print(f"  LLM exception: {e}")
        return None


def generate_single_qa(chunk: Dict) -> Optional[Dict]:
    """基于单个 chunk 生成 QA 对"""
    text = chunk.get("text", "")
    meta = chunk.get("metadata", {})
    chunk_type = meta.get("chunk_type", "")
    source = meta.get("source_doc", meta.get("source", ""))
    law_name = meta.get("law_name", "")
    article = meta.get("article", "")

    if len(text) < 50:
        return None

    context = f"[来源] {source}"
    if law_name:
        context += f"\n[法规] {law_name} {article}"

    prompt = f"""请基于以下参考内容生成 1 个问答对。

{context}

【参考内容】
{text[:2000]}

【要求】
1. 问题必须能用参考内容回答
2. 答案简洁准确，可摘录原文关键句
3. 问题类型：事实型（是什么/规定是什么/金额多少/谁中标等）

输出 JSON 格式：
{{"question": "...", "answer": "..."}}
"""
    result = _llm_generate(prompt)
    if not result:
        return None

    try:
        result = result.strip()
        if result.startswith("```"):
            result = result.split("\n", 1)[1].rsplit("\n```", 1)[0]
        qa = json.loads(result)
        qa["expected_chunk_ids"] = [chunk["id"]]
        qa["chunk_count"] = 1
        qa["chunk_type"] = chunk_type
        return qa
    except json.JSONDecodeError:
        return None


def generate_double_qa(chunks: List[Dict]) -> Optional[Dict]:
    """基于 2 个 chunk 生成对比/关联 QA 对"""
    if len(chunks) < 2:
        return None

    chunk_a, chunk_b = chunks[0], chunks[1]
    text_a, text_b = chunk_a.get("text", ""), chunk_b.get("text", "")
    meta_a, meta_b = chunk_a.get("metadata", {}), chunk_b.get("metadata", {})

    if len(text_a) < 30 or len(text_b) < 30:
        return None

    context = f"""[参考内容A]
来源: {meta_a.get('source_doc', '')}
法规: {meta_a.get('law_name', '')} {meta_a.get('article', '')}
{text_a[:1500]}

[参考内容B]
来源: {meta_b.get('source_doc', '')}
法规: {meta_b.get('law_name', '')} {meta_b.get('article', '')}
{text_b[:1500]}"""

    prompt = f"""请基于以下两段参考内容生成 1 个对比或关联问答对。

{context}

【要求】
1. 问题需要综合两段内容才能完整回答
2. 适合对比型（A和B有什么不同）或关联型（A规定下B如何处理）
3. 答案简洁准确

输出 JSON 格式：
{{"question": "...", "answer": "..."}}
"""
    result = _llm_generate(prompt)
    if not result:
        return None

    try:
        result = result.strip()
        if result.startswith("```"):
            result = result.split("\n", 1)[1].rsplit("\n```", 1)[0]
        qa = json.loads(result)
        qa["expected_chunk_ids"] = [chunk_a["id"], chunk_b["id"]]
        qa["chunk_count"] = 2
        qa["chunk_type"] = f"{meta_a.get('chunk_type', '')}+{meta_b.get('chunk_type', '')}"
        return qa
    except json.JSONDecodeError:
        return None


def generate_multi_qa(chunks: List[Dict]) -> Optional[Dict]:
    """基于 3 个 chunk 生成综合 QA 对"""
    if len(chunks) < 3:
        return None

    context_parts = []
    ids = []
    types = []
    for i, c in enumerate(chunks[:3]):
        meta = c.get("metadata", {})
        ids.append(c["id"])
        types.append(meta.get("chunk_type", ""))
        context_parts.append(
            f"[参考内容{i+1}]\n来源: {meta.get('source_doc', '')}\n"
            f"法规: {meta.get('law_name', '')} {meta.get('article', '')}\n"
            f"{c.get('text', '')[:1000]}"
        )

    prompt = f"""请基于以下三段参考内容生成 1 个综合问答对。

{chr(10).join(context_parts)}

【要求】
1. 问题需要综合三段内容才能完整回答
2. 适合"总结...的要求"或"对比...的异同"或"在...情况下应如何"
3. 答案简洁准确

输出 JSON 格式：
{{"question": "...", "answer": "..."}}
"""
    result = _llm_generate(prompt)
    if not result:
        return None

    try:
        result = result.strip()
        if result.startswith("```"):
            result = result.split("\n", 1)[1].rsplit("\n```", 1)[0]
        qa = json.loads(result)
        qa["expected_chunk_ids"] = ids
        qa["chunk_count"] = 3
        qa["chunk_type"] = "+".join(types)
        return qa
    except json.JSONDecodeError:
        return None


# ═══════════════════════════════════════════════════════════════
# Step 4: 主流程
# ═══════════════════════════════════════════════════════════════

def pair_chunks(sampled: List[Dict]) -> tuple:
    """为 double/multi QA 找有语义关联的 chunk 对/组"""
    # 按 source_doc + law_name 分组
    groups = defaultdict(list)
    for c in sampled:
        meta = c.get("metadata", {})
        key = meta.get("law_name") or meta.get("source_doc") or meta.get("chunk_type", "")
        groups[key].append(c)

    # 构建 pairs 和 triples
    pairs = []
    triples = []
    for key, group in groups.items():
        if len(group) >= 3:
            # 取前3个作为 triple
            random.shuffle(group)
            triples.append(group[:3])
        elif len(group) == 2:
            pairs.append(group[:2])

    # 如果同源不够，跨源随机配对
    if len(pairs) < len(sampled) * QA_TYPE_RATIO["double"] // 2:
        shuffled = list(sampled)
        random.shuffle(shuffled)
        for i in range(0, len(shuffled) - 1, 2):
            pairs.append([shuffled[i], shuffled[i + 1]])

    if len(triples) < 3:
        shuffled = list(sampled)
        random.shuffle(shuffled)
        for i in range(0, len(shuffled) - 2, 3):
            triples.append(shuffled[i:i + 3])

    return pairs, triples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只预览抽样分布")
    parser.add_argument("--total", type=int, default=200, help="最大抽样数")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    args = parser.parse_args()

    random.seed(args.seed)
    print("=" * 60)
    print("评测集自动生成器 (Chunk → QA)")
    print("=" * 60)

    # Step 1: 导出
    print("\n[Step 1/4] 导出 Milvus chunks ...")
    all_chunks = export_all_chunks()
    if not all_chunks:
        print("ERROR: 未导出任何 chunk，请检查 Milvus 连接")
        return
    print(f"  总计: {len(all_chunks)} chunks")

    # Step 2: 抽样
    print(f"\n[Step 2/4] 分层抽样 (max={args.total}) ...")
    sampled = sample_chunks(all_chunks, args.total)

    if args.dry_run:
        print("\n[Dry-run 完成] 预览抽样分布如上")
        return

    # Step 3: 配对 + 生成 QA
    print(f"\n[Step 3/4] 生成 QA 对 ...")
    pairs, triples = pair_chunks(sampled)

    n_single = int(len(sampled) * QA_TYPE_RATIO["single"])
    n_double = min(int(len(sampled) * QA_TYPE_RATIO["double"]), len(pairs))
    n_multi = min(int(len(sampled) * QA_TYPE_RATIO["multi"]), len(triples))

    print(f"  计划: single={n_single}, double={n_double}, multi={n_multi}")

    qa_pairs = []
    idx = 0

    # Single chunk QA
    single_pool = sampled[:n_single]
    for i, chunk in enumerate(single_pool):
        print(f"  single {i+1}/{n_single}: {chunk['id'][:60]} ...", end=" ")
        qa = generate_single_qa(chunk)
        if qa:
            qa["id"] = f"qa_{idx:04d}"
            qa_pairs.append(qa)
            idx += 1
            print("OK")
        else:
            print("SKIP")

    # Double chunk QA
    for i, pair in enumerate(pairs[:n_double]):
        print(f"  double {i+1}/{n_double}: {pair[0]['id'][:40]} + {pair[1]['id'][:40]} ...", end=" ")
        qa = generate_double_qa(pair)
        if qa:
            qa["id"] = f"qa_{idx:04d}"
            qa_pairs.append(qa)
            idx += 1
            print("OK")
        else:
            print("SKIP")

    # Multi chunk QA
    for i, triple in enumerate(triples[:n_multi]):
        print(f"  multi  {i+1}/{n_multi}: {triple[0]['id'][:40]} + 2 ...", end=" ")
        qa = generate_multi_qa(triple)
        if qa:
            qa["id"] = f"qa_{idx:04d}"
            qa_pairs.append(qa)
            idx += 1
            print("OK")
        else:
            print("SKIP")

    # Step 4: 输出
    print(f"\n[Step 4/4] 输出 ...")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    output = {
        "benchmark_name": "eval_benchmark_v1",
        "schema_version": "2.0",
        "created_at": __import__('datetime').datetime.now().isoformat(),
        "total_qa_pairs": len(qa_pairs),
        "stats": {
            "single": sum(1 for q in qa_pairs if q["chunk_count"] == 1),
            "double": sum(1 for q in qa_pairs if q["chunk_count"] == 2),
            "multi": sum(1 for q in qa_pairs if q["chunk_count"] == 3),
            "by_chunk_type": {},
        },
        "qa_pairs": qa_pairs,
    }

    # 统计 chunk_type 分布
    for qa in qa_pairs:
        ct = qa.get("chunk_type", "unknown")
        output["stats"]["by_chunk_type"][ct] = output["stats"]["by_chunk_type"].get(ct, 0) + 1

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"[完成] 生成 {len(qa_pairs)} 个 QA 对")
    print(f"  输出: {OUTPUT_PATH}")
    print(f"  分布: single={output['stats']['single']}, "
          f"double={output['stats']['double']}, multi={output['stats']['multi']}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
