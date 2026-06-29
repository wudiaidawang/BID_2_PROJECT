"""修复 eval_benchmark_v5.json 中的错误 chunk ID — LLM 篡改了 ID 的 law_name 截断"""
import json, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.storage.milvus_store import MilvusStore

BENCHMARK_PATH = Path("data/eval_questions/eval_benchmark_v5.json")

# 1. Load all Milvus IDs and build suffix index
print("[1] Building Milvus ID suffix index...")
store = MilvusStore()
all_docs = store.get_all_documents("policy")
milvus_ids = set(d["id"] for d in all_docs)
print(f"  {len(milvus_ids)} Milvus IDs")

# Build suffix -> full ID map
suffix_map = defaultdict(list)
for mid in milvus_ids:
    parts = mid.rsplit("_", 3)
    if len(parts) >= 3:
        suffix = "_".join(parts[-3:])
        suffix_map[suffix].append(mid)

print(f"  {len(suffix_map)} unique suffixes")

# 2. Load benchmark
print("[2] Loading benchmark...")
with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

qas = data["qa_pairs"]
fixed_count = 0
still_broken = 0

for qa in qas:
    eid = qa.get("expected_chunk_id", "")
    fixed = False

    # Skip if already correct
    if eid in milvus_ids:
        continue

    # Try suffix matching
    parts = eid.rsplit("_", 3)
    if len(parts) >= 3:
        suffix = "_".join(parts[-3:])
        matches = suffix_map.get(suffix, [])
        if len(matches) == 1:
            qa["expected_chunk_id"] = matches[0]
            fixed_count += 1
            fixed = True

    # Also fix acceptable_chunk_ids
    new_acceptable = []
    for aid in qa.get("acceptable_chunk_ids", []):
        if aid in milvus_ids:
            new_acceptable.append(aid)
        else:
            aparts = aid.rsplit("_", 3)
            if len(aparts) >= 3:
                asuffix = "_".join(aparts[-3:])
                amatches = suffix_map.get(asuffix, [])
                if len(amatches) == 1:
                    new_acceptable.append(amatches[0])
                # else: drop unresolvable
    qa["acceptable_chunk_ids"] = new_acceptable

    if not fixed:
        still_broken += 1

print(f"  Fixed: {fixed_count}")
print(f"  Still broken (no unique suffix match): {still_broken}")

# 3. Save fixed benchmark
backup = BENCHMARK_PATH.with_suffix(".json.bak")
print(f"[3] Saving...")
# Backup
import shutil
shutil.copy2(BENCHMARK_PATH, backup)
print(f"  Backup: {backup}")

with open(BENCHMARK_PATH, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"  Fixed benchmark saved: {BENCHMARK_PATH}")

# 4. Verify
with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
    verify = json.load(f)
remaining = sum(1 for qa in verify["qa_pairs"]
                if qa.get("expected_chunk_id", "") not in milvus_ids)
print(f"\n[Verify] Still-missing expected IDs after fix: {remaining}")
