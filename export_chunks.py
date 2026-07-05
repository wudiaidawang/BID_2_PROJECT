#!/usr/bin/env python3
"""导出 policy_v9 全部 chunk 到 current_chunks.json（包含新的 pdf_case_structured）"""
import sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.storage import get_vector_store

COLLECTION = "policy_v9"
OUT_PATH = Path(__file__).parent / "data" / "eval_questions" / "chunks" / "current_chunks.json"
BAK_PATH = Path(__file__).parent / "data" / "eval_questions" / "chunks" / "current_chunks.json.bak3"

def _get_field(doc, key):
    val = doc.get(key, "")
    if val:
        return str(val)
    meta = doc.get("metadata") or doc.get("data", {})
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            return ""
    if isinstance(meta, dict):
        return str(meta.get(key, ""))
    return ""

def export():
    client = get_vector_store()
    print("Querying all documents...")

    # Paginate to get all docs
    all_docs = []
    offset = 0
    page_size = 200
    while True:
        batch = client.query(COLLECTION, "id != \"\"", limit=page_size, offset=offset)
        if not batch:
            break
        all_docs.extend(batch)
        offset += page_size
        print(f"  {len(all_docs)} docs...")
        if len(batch) < page_size:
            break

    print(f"Total: {len(all_docs)} docs")

    # Count by chunk_type
    from collections import Counter
    type_counts = Counter()
    for d in all_docs:
        ct = _get_field(d, "chunk_type")
        type_counts[ct] += 1
    print("By chunk_type:")
    for ct, cnt in type_counts.most_common():
        print(f"  {ct}: {cnt}")

    # Format
    chunks = []
    for d in all_docs:
        chunk = {
            "chunk_id": d.get("id", ""),
            "chunk_type": _get_field(d, "chunk_type"),
            "retrieval_text": d.get("retrieval_text", ""),
            "text": d.get("text", ""),
            "law_name": _get_field(d, "law_name"),
            "article_id": _get_field(d, "article_id"),
            "parent_id": _get_field(d, "parent_id"),
            "parent_content": "",  # eval 脚本自行构建
            "source_doc": _get_field(d, "source_doc"),
            "category": _get_field(d, "category"),
            "data_version": _get_field(d, "data_version"),
            "chunk_order": _get_field(d, "chunk_order"),
            "title": _get_field(d, "title"),
            "related_chunks": [],
        }
        chunks.append(chunk)

    # Backup old file
    if OUT_PATH.exists():
        import shutil
        shutil.copy2(OUT_PATH, BAK_PATH)
        print(f"Backed up to {BAK_PATH}")

    output = {
        "version": "2026-07-04_v3",
        "total": len(chunks),
        "description": f"policy_v9 export with pdf_case_structured replacing pdf_case_paragraph ({len(chunks)} chunks)",
        "chunks": chunks,
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)

    print(f"Saved {len(chunks)} chunks to {OUT_PATH}")

if __name__ == "__main__":
    export()
