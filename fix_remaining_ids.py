"""修复 eval benchmark 中剩余的 19 个 LLM 幻造 chunk_id"""
import json, sys, re
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.storage.milvus_store import MilvusStore

store = MilvusStore()
all_docs = store.get_all_documents("policy")
milvus_ids = set(d["id"] for d in all_docs)

# Build lookup: (law_name, article_id) -> [ids]
by_law_art = defaultdict(list)
for d in all_docs:
    ln = d.get("law_name", "")
    aid = d.get("article_id", "")
    if ln and aid:
        by_law_art[(ln, aid)].append(d["id"])

# Build suffix lookup
suffix_map = defaultdict(list)
for mid in milvus_ids:
    parts = mid.rsplit("_", 3)
    if len(parts) >= 3:
        suffix_map["_".join(parts[-3:])].append(mid)

with open("data/eval_questions/eval_benchmark_v5.json", "r", encoding="utf-8") as f:
    data = json.load(f)

fixed = 0
for qa in data["qa_pairs"]:
    eid = qa.get("expected_chunk_id", "")
    if eid in milvus_ids:
        continue

    law_name = qa.get("law_name", "")
    article_id = str(qa.get("article_id", ""))
    question = qa.get("question", "")

    # Strategy 1: match by (law_name, article_id)
    if law_name and article_id:
        candidates = by_law_art.get((law_name, article_id), [])
        if len(candidates) == 1:
            qa["expected_chunk_id"] = candidates[0]
            fixed += 1
            continue
        elif len(candidates) > 1:
            # Pick the one with shortest ID (cleanest)
            qa["expected_chunk_id"] = min(candidates, key=len)
            fixed += 1
            continue

    # Strategy 2: suffix match
    parts = eid.rsplit("_", 3)
    if len(parts) >= 3:
        suffix = "_".join(parts[-3:])
        matches = suffix_map.get(suffix, [])
        if len(matches) == 1:
            qa["expected_chunk_id"] = matches[0]
            fixed += 1
            continue

    # Strategy 3: extract article_id from question
    q_article = None
    m = re.search(r'第(\d+)条', question)
    if m:
        q_article = m.group(1)
    m = re.search(r'第([一二三四五六七八九十百千]+)条', question)
    if m:
        cn_map = {'一':'1','二':'2','三':'3','四':'4','五':'5','六':'6','七':'7','八':'8','九':'9','十':'10'}
        q_article = str(sum(int(cn_map.get(c, 0)) for c in m.group(1)))

    if q_article and law_name:
        candidates = by_law_art.get((law_name, q_article), [])
        if len(candidates) == 1:
            qa["expected_chunk_id"] = candidates[0]
            fixed += 1
            continue
        elif len(candidates) > 1:
            qa["expected_chunk_id"] = min(candidates, key=len)
            fixed += 1
            continue

    print(f"  UNFIXED: {qa['id']} expected={eid[:60]} q={question[:60]}")

# Save
with open("data/eval_questions/eval_benchmark_v5.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# Verify
with open("data/eval_questions/eval_benchmark_v5.json", "r", encoding="utf-8") as f:
    verify = json.load(f)
remaining = sum(1 for qa in verify["qa_pairs"]
                if qa.get("expected_chunk_id", "") not in milvus_ids)
print(f"Fixed: {fixed}, Remaining: {remaining}")
