"""
Merge 5 manual QA CSV files into standard eval benchmark JSON format.

CSV issue: headers use escaped underscores (qa\_id instead of qa_id).
This is a LaTeX artifact — the backslash before underscore in the CSV headers
is CSV-escaped text, not a literal backslash. Python's csv module reads them
as-is, so we need to strip backslashes from header names.
"""

import csv
import json
import re
import os
from collections import OrderedDict

CSV_DIR = "data/eval_questions"
OUTPUT_FILE = os.path.join(CSV_DIR, "eval_benchmark_manual_v1.json")

# Table 3 (7803442) and Table 5 (8088479) overlap on qa_0700-0723.
# Table 5 has more detailed entries (3-chunk vs 2-chunk in some cases), so prefer it.
PREFERRED_TABLE = "table-1781758088479.csv"

FILES = [
    "table-1781758055503.csv",   # qa_0000-0100: bid_project, single
    "table-1781757779947.csv",   # qa_0500-0599: regulation_parent, single/double
    "table-1781757795609.csv",   # qa_0600-0649: pdf_case_sliding + regulation_sliding, single
    "table-1781757803442.csv",   # qa_0700-0723: regulation parent-child, multi-chunk
    "table-1781758088479.csv",   # qa_0700-0781: regulation parent-child, multi-chunk (PREFERRED)
]


def clean_escapes(s: str) -> str:
    """Strip LaTeX-style escapes: \\_ -> _, \\[ -> [, \\] -> ]."""
    s = s.replace("\\_", "_")
    s = s.replace("\\[", "[")
    s = s.replace("\\]", "]")
    return s


def parse_expected_chunk_ids(raw: str) -> list:
    """Parse expected_chunk_ids from CSV string to proper JSON array.

    Input:  \\[parent_招标投标法_37_xxx, parent_招标投标法_37_xxx_child0]
    Output: ["parent_招标投标法_37_xxx", "parent_招标投标法_37_xxx_child0"]
    """
    raw = clean_escapes(raw).strip()
    # Remove outer brackets (may still have literal [ ] after clean_escapes)
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    elif raw.startswith("[") and not raw.endswith("]"):
        # Handle case where only leading bracket was escaped: \\[...]
        raw = raw[1:]
    if raw.endswith("]"):
        raw = raw[:-1]
    # Split by comma, handling potential spaces
    items = [item.strip() for item in raw.split(",") if item.strip()]
    return items


def read_csv(filepath: str) -> list:
    """Read a single CSV and return list of normalized QA dicts."""
    rows = []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        # Read first line to detect and fix escaped underscores
        first_line = f.readline()
        f.seek(0)
        # csv.Sniffer would choke on BOM + escaped underscores, so use DictReader directly
        reader = csv.DictReader(f)
        for row in reader:
            # Build normalized row with fixed keys and cleaned values
            normalized = {}
            for key, value in row.items():
                clean_key = clean_escapes(key).strip()
                clean_value = clean_escapes(value).strip() if value else ""
                normalized[clean_key] = clean_value

            # Parse expected_chunk_ids into JSON array
            raw_ids = normalized.get("expected_chunk_ids", "[]")
            normalized["expected_chunk_ids"] = parse_expected_chunk_ids(raw_ids)

            # Convert chunk_count to int
            try:
                normalized["chunk_count"] = int(normalized.get("chunk_count", "1"))
            except (ValueError, TypeError):
                normalized["chunk_count"] = len(normalized["expected_chunk_ids"])

            rows.append(normalized)

    return rows


def main():
    # Read all files
    all_qa = OrderedDict()  # qa_id -> qa_dict

    for fname in FILES:
        filepath = os.path.join(CSV_DIR, fname)
        if not os.path.exists(filepath):
            print(f"SKIP (not found): {fname}")
            continue

        rows = read_csv(filepath)
        print(f"{fname}: {len(rows)} rows")

        for row in rows:
            qa_id = row.get("qa_id", "")
            if not qa_id:
                print(f"  WARN: row without qa_id in {fname}, skipping")
                continue

            # Dedup: prefer entries from PREFERRED_TABLE
            if qa_id in all_qa:
                if fname == PREFERRED_TABLE:
                    all_qa[qa_id] = row  # override with preferred
                    print(f"  OVERRIDE: {qa_id} (from preferred table)")
                else:
                    print(f"  SKIP duplicate: {qa_id} (already from preferred table)")
            else:
                all_qa[qa_id] = row

    # Sort by qa_id
    sorted_qa = sorted(all_qa.values(), key=lambda x: x["qa_id"])

    # Build output
    by_chunk_count = {}
    by_chunk_type = {}
    for qa in sorted_qa:
        cc = str(qa["chunk_count"])
        by_chunk_count[cc] = by_chunk_count.get(cc, 0) + 1

        ct = qa.get("chunk_type", "unknown")
        by_chunk_type[ct] = by_chunk_type.get(ct, 0) + 1

    output = {
        "benchmark_name": "eval_benchmark_manual_v1",
        "description": "手动整理的招投标领域问答对，覆盖法规/案例/招标项目，含 expected_chunk_ids 用于检索评估",
        "total_qa_pairs": len(sorted_qa),
        "stats": {
            "total": len(sorted_qa),
            "by_chunk_count": by_chunk_count,
            "by_chunk_type": by_chunk_type,
        },
        "qa_pairs": sorted_qa,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nTotal unique QA pairs: {len(sorted_qa)}")
    print(f"By chunk_count: {by_chunk_count}")
    print(f"By chunk_type: {by_chunk_type}")
    print(f"Written to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
