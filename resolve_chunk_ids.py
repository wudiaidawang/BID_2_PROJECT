"""
Resolve CSV placeholder chunk IDs (parent_招标投标法_37_xxx) to
actual Milvus chunk IDs (parent_中华人民共和国招标投标法_37_174_2233).

Strategy:
  1. Build a lookup from actual chunks: key = (chunk_type, source_doc, article_id/chunk_order)
  2. For each CSV placeholder, match by substring on abbreviated name → full name
  3. Replace _xxx suffix with actual suffix from matching chunk
"""

import json
import re
from collections import defaultdict

JSONL_PATH = "data/raw/all_chunks.jsonl"
QA_PATH = "data/eval_questions/eval_benchmark_manual_v1.json"
OUTPUT_PATH = "data/eval_questions/eval_benchmark_manual_v1.json"

# Known abbreviation → full name mappings
ABBREV_MAP = {
    "招标投标法": "中华人民共和国招标投标法",
    "价格法": "中华人民共和国价格法",
    "政府采购法": "中华人民共和国政府采购法",
    "公证法": "中华人民共和国公证法",
    "招标投标法实施条例": "中华人民共和国招标投标法实施条例",
}


def load_actual_chunks():
    """Build lookup tables from actual Milvus chunks.

    Returns:
      parent_lookup: {(law_name, article_id): actual_parent_id}
      child_lookup: {(parent_law_name, article_id, child_idx): actual_child_id}
      pdf_lookup: {(case_name, chunk_order): actual_id}
      reg_lookup: {(doc_name, chunk_order): actual_id}
    """
    parent_lookup = {}   # (law_name, article_id) -> id
    child_lookup = {}    # (law_name, article_id, child_idx) -> id
    pdf_lookup = {}      # (case_name, chunk_order) -> id
    reg_lookup = {}      # (doc_name, chunk_order) -> id

    with open(JSONL_PATH, "r", encoding="utf-8") as f:
        for line in f:
            chunk = json.loads(line)
            cid = chunk["id"]
            ct = chunk.get("chunk_type", "")
            co = chunk.get("chunk_order", "")
            sd = chunk.get("source_doc", "")

            if ct == "regulation_parent":
                # ID format: parent_中华人民共和国招标投标法_37_174_2233
                parts = cid.split("_", 2)  # ["parent", "中华人民共和国招标投标法", "37_174_2233"]
                if len(parts) >= 3:
                    law_name = parts[1]
                    article_str = parts[2]
                    # article_id is the first segment after law name
                    article_id = article_str.split("_")[0]
                    parent_lookup[(law_name, article_id)] = cid

            elif ct == "regulation_child":
                # ID format: parent_中华人民共和国公证法_100_1460_3359_child0
                match = re.match(r"parent_(.+?)_(\d+)_\d+_\d+_child(\d+)", cid)
                if match:
                    law_name = match.group(1)
                    article_id = match.group(2)
                    child_idx = int(match.group(3))
                    child_lookup[(law_name, article_id, child_idx)] = cid

            elif ct == "pdf_case_sliding":
                # ID format: pdf_串通投标、受贿案_0_2701
                parts = cid.split("_", 2)  # ["pdf", "串通投标、受贿案", "0_2701"]
                if len(parts) >= 3:
                    case_name = parts[1]
                    chunk_idx = parts[2].split("_")[0]
                    pdf_lookup[(case_name, chunk_idx)] = cid

            elif ct == "regulation_sliding":
                # ID format: reg_招标投标法律解读与风险防范实务_0_2126
                parts = cid.split("_", 2)  # ["reg", "招标投标法律解读与风险防范实务", "0_2126"]
                if len(parts) >= 3:
                    doc_name = parts[1]
                    chunk_idx = parts[2].split("_")[0]
                    reg_lookup[(doc_name, chunk_idx)] = cid

    return parent_lookup, child_lookup, pdf_lookup, reg_lookup


def parse_placeholder(ph: str):
    """Parse a placeholder ID like 'parent_招标投标法_37_xxx' into components.

    Returns dict with: prefix, name, article/chunk_num, child_idx (optional), is_child
    """
    # Remove _xxx suffix first
    ph = ph.replace("_xxx", "")

    # Check for child suffix
    child_match = re.match(r"(.+)_child(\d+)$", ph)
    child_idx = None
    if child_match:
        ph = child_match.group(1)
        child_idx = int(child_match.group(2))

    # Parse prefix_name_num
    # Format: {prefix}_{name}_{num}
    # prefix is one of: parent, pdf, reg
    parts = ph.split("_", 2)
    if len(parts) < 3:
        return None

    prefix = parts[0]
    name = parts[1]
    num = parts[2]  # article_id or chunk_order

    return {
        "prefix": prefix,
        "name": name,
        "num": num,
        "child_idx": child_idx,
        "is_child": child_idx is not None,
    }


def resolve_id(placeholder: str, parent_lookup, child_lookup, pdf_lookup, reg_lookup):
    """Resolve a single placeholder to actual chunk ID."""
    parsed = parse_placeholder(placeholder)
    if not parsed:
        return None, "parse_failed"

    name = parsed["name"]
    num = parsed["num"]
    prefix = parsed["prefix"]

    # Try exact match first, then abbreviated match
    if prefix == "parent":
        if parsed["is_child"]:
            # Look up child
            for (law_name, article_id, child_idx), cid in child_lookup.items():
                if article_id == num and child_idx == parsed["child_idx"]:
                    # Name matching: abbreviated → full
                    if law_name == name or name in law_name or law_name in name:
                        return cid, "child_exact"
                    # Try abbreviation map
                    full = ABBREV_MAP.get(name, "")
                    if full and full == law_name:
                        return cid, "child_abbrev"
                    if full and full in law_name:
                        return cid, "child_partial"
            return None, "child_not_found"

        else:
            # Look up parent
            for (law_name, article_id), cid in parent_lookup.items():
                if article_id == num:
                    if law_name == name or name in law_name or law_name in name:
                        return cid, "parent_exact"
                    full = ABBREV_MAP.get(name, "")
                    if full and full == law_name:
                        return cid, "parent_abbrev"
                    if full and full in law_name:
                        return cid, "parent_partial"
            return None, "parent_not_found"

    elif prefix == "pdf":
        for (case_name, chunk_idx), cid in pdf_lookup.items():
            if chunk_idx == num:
                if case_name == name or name in case_name or case_name in name:
                    return cid, "pdf_exact"
        return None, "pdf_not_found"

    elif prefix == "reg":
        for (doc_name, chunk_idx), cid in reg_lookup.items():
            if chunk_idx == num:
                if doc_name == name or name in doc_name or doc_name in name:
                    return cid, "reg_exact"
        return None, "reg_not_found"

    return None, "unknown_prefix"


def resolve_parent_placeholder(name: str, article_id: str, parent_lookup: dict):
    """Resolve a parent placeholder to actual parent chunk ID."""
    full = ABBREV_MAP.get(name, "")
    for (law_name, aid), cid in parent_lookup.items():
        if aid == article_id:
            if law_name == name or name in law_name or law_name in name:
                return cid, law_name
            if full and (full == law_name or full in law_name):
                return cid, law_name
    return None, None


def resolve_child_placeholder(full_law_name: str, article_id: str, child_idx: int, child_lookup: dict):
    """Resolve a child placeholder using the already-resolved parent's full law name."""
    key = (full_law_name, article_id, child_idx)
    if key in child_lookup:
        return child_lookup[key]
    return None


def main():
    print("Loading actual chunks...")
    parent_lookup, child_lookup, pdf_lookup, reg_lookup = load_actual_chunks()
    print(f"  parent chunks: {len(parent_lookup)}")
    print(f"  child chunks: {len(child_lookup)}")
    print(f"  pdf_case chunks: {len(pdf_lookup)}")
    print(f"  reg_sliding chunks: {len(reg_lookup)}")

    print("Loading QA pairs...")
    with open(QA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    resolved = 0
    unresolved = 0
    unchanged = 0
    stats = defaultdict(int)

    for qa in data["qa_pairs"]:
        new_ids = []

        def is_placeholder(cid: str) -> bool:
            """Check if a chunk ID contains _xxx placeholder (anywhere in string)."""
            return "_xxx" in cid

        # Pass 1: Build knowledge of resolved parents
        # Key insight: a parent might already be resolved (from a previous run)
        # or still be a placeholder. Extract (article_id, full_law_name) from both.
        parent_info = {}  # article_id -> full_law_name
        for cid in qa["expected_chunk_ids"]:
            if is_placeholder(cid):
                continue  # placeholder, skip for now
            if cid.startswith("bids_") or cid.startswith("pdf_") or cid.startswith("reg_"):
                continue  # not a parent chunk

            # Extract full law name and article_id from resolved parent ID
            # Format: parent_中华人民共和国招标投标法_37_38_4507
            match = re.match(r"parent_(.+?)_(\d+)_\d+_\d+$", cid)
            if match:
                law_name = match.group(1)
                article_id = match.group(2)
                parent_info[article_id] = law_name

        # Also resolve any remaining parent placeholders (not child)
        for cid in qa["expected_chunk_ids"]:
            if not is_placeholder(cid) or "_child" in cid:
                continue
            parsed = parse_placeholder(cid)
            if not parsed or parsed["prefix"] != "parent":
                continue
            actual_id, full_name = resolve_parent_placeholder(
                parsed["name"], parsed["num"], parent_lookup
            )
            if actual_id:
                parent_info[parsed["num"]] = full_name

        # Pass 2: resolve all IDs
        for cid in qa["expected_chunk_ids"]:
            if not is_placeholder(cid):
                new_ids.append(cid)
                unchanged += 1
                continue

            parsed = parse_placeholder(cid)
            if not parsed:
                new_ids.append(cid)
                unresolved += 1
                continue

            prefix = parsed["prefix"]
            num = parsed["num"]

            if prefix == "parent" and parsed["is_child"]:
                # Look up child using full law name from resolved parent
                full_law_name = parent_info.get(num)
                if full_law_name:
                    actual = resolve_child_placeholder(
                        full_law_name, num, parsed["child_idx"], child_lookup
                    )
                    if actual:
                        new_ids.append(actual)
                        resolved += 1
                        stats["child_resolved"] += 1
                    else:
                        # Child doesn't exist (article too short to split).
                        # The parent alone covers the full content — skip this placeholder.
                        stats["child_not_found_skipped"] += 1
                        print(f"  SKIP child (no children for this article): {cid} "
                              f"(parent covers all content)")
                else:
                    new_ids.append(cid)
                    unresolved += 1
                    stats["child_no_parent"] += 1
                    print(f"  UNRESOLVED child (no parent info): {cid}")

            elif prefix == "parent":
                # Parent placeholder — try to resolve
                actual_id, _ = resolve_parent_placeholder(
                    parsed["name"], num, parent_lookup
                )
                if actual_id:
                    new_ids.append(actual_id)
                    resolved += 1
                    stats["parent_resolved"] += 1
                else:
                    new_ids.append(cid)
                    unresolved += 1
                    stats["parent_not_found"] += 1
                    print(f"  UNRESOLVED parent: {cid}")

            elif prefix == "pdf":
                actual, reason = resolve_id(cid, parent_lookup, child_lookup, pdf_lookup, reg_lookup)
                if actual:
                    new_ids.append(actual)
                    resolved += 1
                else:
                    new_ids.append(cid)
                    unresolved += 1
                    print(f"  UNRESOLVED pdf: {cid}")
                stats[reason] += 1

            elif prefix == "reg":
                actual, reason = resolve_id(cid, parent_lookup, child_lookup, pdf_lookup, reg_lookup)
                if actual:
                    new_ids.append(actual)
                    resolved += 1
                else:
                    new_ids.append(cid)
                    unresolved += 1
                    print(f"  UNRESOLVED reg: {cid}")
                stats[reason] += 1

            else:
                new_ids.append(cid)
                unresolved += 1

        qa["expected_chunk_ids"] = new_ids
        qa["chunk_count"] = len(new_ids)

    # Update stats
    by_chunk_count = defaultdict(int)
    for qa in data["qa_pairs"]:
        by_chunk_count[str(qa["chunk_count"])] += 1
    data["stats"]["by_chunk_count"] = dict(by_chunk_count)

    print(f"\nResolution results:")
    print(f"  Resolved: {resolved}")
    print(f"  Unresolved: {unresolved}")
    print(f"  Unchanged (bids): {unchanged}")
    print(f"  By reason: {dict(stats)}")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nWritten to: {OUTPUT_PATH}")

    # Show a few resolved examples
    print("\n=== Sample resolutions ===")
    for qa in data["qa_pairs"]:
        if qa["qa_id"] in ("qa_0700", "qa_0715", "qa_0746", "qa_0781", "qa_0600"):
            print(f"\n{qa['qa_id']}:")
            for cid in qa["expected_chunk_ids"]:
                marker = " (UNRESOLVED)" if cid.endswith("_xxx") else ""
                print(f"  {cid}{marker}")


if __name__ == "__main__":
    main()
