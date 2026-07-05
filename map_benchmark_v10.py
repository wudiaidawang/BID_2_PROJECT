#!/usr/bin/env python3
"""将 v8 benchmark 的 chunk ID 从 policy_v9 映射到 policy_v10"""

import json, sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, '/home/admin/group_three_5_11/data_pan')
from app.storage import get_vector_store

s = get_vector_store()
v9_docs = s.get_all_documents("policy_v9")
v10_docs = s.get_all_documents("policy_v10")
print(f"V9: {len(v9_docs)} docs, V10: {len(v10_docs)} docs")

def make_key(doc):
    meta = doc.get("metadata", {})
    return (
        meta.get("law_name", doc.get("law_name", "")),
        meta.get("article_id", doc.get("article_id", "")),
        meta.get("chunk_type", doc.get("chunk_type", "")),
        meta.get("chunk_order", doc.get("chunk_order", "")),
    )

# V9: id → doc
v9_by_id = {}
v9_by_key = {}
for d in v9_docs:
    v9_by_id[d["id"]] = d
    v9_by_key[make_key(d)] = d

# V10: key → doc
v10_by_key = {}
for d in v10_docs:
    k = make_key(d)
    if k not in v10_by_key:
        v10_by_key[k] = d

# Load benchmark
bench_path = "/home/admin/eval_v10/data/eval_questions/v8/v8_canonical.jsonl"
items = []
with open(bench_path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            items.append(json.loads(line))
print(f"Benchmark: {len(items)} questions")

# Map
mapped = 0
unmapped = 0
unmapped_by_type = defaultdict(int)
unmapped_samples = []

for qa in items:
    eid = qa.get("expected_chunk_id", "")
    if not eid:
        unmapped += 1
        continue

    v9_doc = v9_by_id.get(eid)
    if not v9_doc:
        unmapped += 1
        unmapped_by_type["v9_id_not_found"] += 1
        continue

    k = make_key(v9_doc)
    v10_doc = v10_by_key.get(k)

    if not v10_doc:
        # 宽松匹配: 仅用 (law_name, article_id, chunk_type), chunk_order 忽略
        law, aid, ct, _ = k
        candidates = [(kk, vv) for kk, vv in v10_by_key.items()
                      if kk[0] == law and kk[1] == aid and kk[2] == ct]
        if len(candidates) == 1:
            v10_doc = candidates[0][1]
        elif len(candidates) > 1:
            # 多头匹配: 用公共前缀长度选最相似的
            v9_text = v9_doc.get("text", "")
            best, best_score = None, 0
            for ck, cd in candidates:
                ct_text = cd.get("text", "")
                common = sum(1 for a, b in zip(v9_text, ct_text) if a == b)
                if common > best_score:
                    best_score = common
                    best = cd
            if best:
                v10_doc = best
            else:
                unmapped += 1
                unmapped_by_type[f"multi_{ct}"] += 1
                if len(unmapped_samples) < 15:
                    unmapped_samples.append(("multi", eid, ct, law[:40]))
                continue
        else:
            unmapped += 1
            unmapped_by_type[f"no_{ct}"] += 1
            if len(unmapped_samples) < 15:
                unmapped_samples.append(("no_match", eid, ct, law[:40]))
            continue

    qa["expected_chunk_id"] = v10_doc["id"]
    mapped += 1

    # Map acceptable_chunk_ids
    new_accept = []
    for aid_old in (qa.get("acceptable_chunk_ids") or []):
        v9_acc = v9_by_id.get(aid_old)
        if v9_acc:
            ak = make_key(v9_acc)
            v10_acc = v10_by_key.get(ak)
            if v10_acc:
                new_accept.append(v10_acc["id"])
    qa["acceptable_chunk_ids"] = new_accept

print(f"\nMapped: {mapped}, Unmapped: {unmapped}")
print(f"Match rate: {mapped/(mapped+unmapped)*100:.1f}%")
print(f"\nUnmapped by reason:")
for k, v in sorted(unmapped_by_type.items(), key=lambda x: -x[1]):
    print(f"  {k}: {v}")
print(f"\nSample unmapped:")
for s in unmapped_samples:
    print(f"  {s}")

# Save
out_path = "/home/admin/eval_v10/data/eval_questions/v8/v8_canonical_v10.jsonl"
with open(out_path, "w", encoding="utf-8") as f:
    for item in items:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")
print(f"\nSaved: {out_path} ({len(items)} questions)")
