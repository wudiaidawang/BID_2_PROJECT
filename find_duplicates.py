"""精准去重 — 基于 ID 后缀匹配找 law_name 截断的重复"""
import json, sys, re
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.storage.milvus_store import MilvusStore

store = MilvusStore()

print("[1/4] Fetching all policy parent chunks...")
docs = store.get_all_documents("policy")
parents = [d for d in docs if d.get("chunk_type") == "pdf_law_parent"]
print(f"  parent chunks: {len(parents)}")

# 从 ID 提取后缀: parent_xxx_99_1234_5678 -> 99_1234_5678
# law_name 可能含 _，所以用 rsplit 从右边取最后3段
def id_suffix(chunk_id):
    parts = chunk_id.rsplit("_", 3)
    if len(parts) >= 3:
        return "_".join(parts[-3:])  # article_id_pos_hash
    return chunk_id

def id_law_name(chunk_id):
    """提取 ID 中的 law_name 部分"""
    parts = chunk_id.rsplit("_", 3)
    if len(parts) >= 4:
        # 去掉 "parent_" 前缀
        return parts[0].replace("parent_", "", 1) if parts[0].startswith("parent_") else parts[0]
    return ""

# 按 ID 后缀分组（相同后缀 = 同一法条的同一位置）
print("[2/4] Grouping by ID suffix (last 3 segments)...")
by_suffix = defaultdict(list)
for d in parents:
    cid = d["id"]
    suffix = id_suffix(cid)
    by_suffix[suffix].append(d)

# 找出同后缀但不同 law_name 的组
dup_groups = []
for suffix, chunks in by_suffix.items():
    ids = [c["id"] for c in chunks]
    unique_ids = set(ids)
    if len(unique_ids) > 1:
        law_names = set(id_law_name(cid) for cid in unique_ids)
        if len(law_names) > 1:
            dup_groups.append({
                "suffix": suffix,
                "law_names": sorted(law_names),
                "ids": sorted(unique_ids),
            })

print(f"  Groups with same suffix but different law_names: {len(dup_groups)}")

# 分类：截断关系 vs 完全不同的law
print("[3/4] Classifying duplicates...")
truncation_groups = []
different_law_groups = []

for g in dup_groups:
    ln_list = g["law_names"]
    # 检查是否有截断关系（一个 law_name 包含另一个）
    has_truncation = False
    for i, a in enumerate(ln_list):
        for b in ln_list[i+1:]:
            if a in b or b in a:
                has_truncation = True
                break
        if has_truncation:
            break

    if has_truncation:
        truncation_groups.append(g)
    else:
        different_law_groups.append(g)

print(f"  Filename truncation duplicates: {len(truncation_groups)}")
print(f"  Different source (cross-law cross-ref): {len(different_law_groups)}")

# 对截断组，保留包含关系中的较长的
ids_to_delete = []
for g in truncation_groups:
    ids = sorted(g["ids"], key=lambda x: (len(id_law_name(x)), len(x)), reverse=True)
    # keep longest law_name, shortest ID as tiebreaker
    ids_to_delete.extend(ids[1:])

print(f"  IDs to delete (truncation fix): {len(ids_to_delete)}")

# 展示前20组截断重复
print("\n[4/4] Truncation examples (top 20):")
for g in truncation_groups[:20]:
    ids = sorted(g["ids"], key=lambda x: len(id_law_name(x)), reverse=True)
    print(f"\n  suffix={g['suffix']}")
    print(f"    KEEP: {ids[0]}")
    for did in ids[1:]:
        print(f"    DEL:  {did}")

# 也展示不同 law cross-ref 的前10组
if different_law_groups:
    print(f"\n=== Cross-law reference examples (first 10) ===")
    for g in different_law_groups[:10]:
        print(f"\n  suffix={g['suffix']}")
        for cid in sorted(g["ids"]):
            print(f"    {cid}")

# 导出
output = Path(__file__).parent / "data" / "eval_questions" / "duplicate_chunks.json"
with open(output, "w", encoding="utf-8") as f:
    json.dump({
        "truncation_groups": len(truncation_groups),
        "different_law_groups": len(different_law_groups),
        "total_to_delete": len(ids_to_delete),
        "ids_to_delete": ids_to_delete,
    }, f, ensure_ascii=False, indent=2)

print(f"\n\n导出: {output}")
print(f"待删除 {len(ids_to_delete)} 条 (截断重复)")
