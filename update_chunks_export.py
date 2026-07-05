#!/usr/bin/env python3
"""更新 current_chunks.json：移除旧的 pdf_case_paragraph，加入新的 pdf_case_structured"""
import sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.storage import get_vector_store

COLLECTION = "policy_v9"
CHUNKS_PATH = Path(__file__).parent / "data" / "eval_questions" / "chunks" / "current_chunks.json"
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

def main():
    print("Loading current_chunks.json...")
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    old_total = len(data["chunks"])
    old_case_para = [c for c in data["chunks"] if c.get("chunk_type") == "pdf_case_paragraph"]
    print(f"Old total: {old_total}, pdf_case_paragraph: {len(old_case_para)}")

    # Remove old pdf_case_paragraph
    data["chunks"] = [c for c in data["chunks"] if c.get("chunk_type") != "pdf_case_paragraph"]

    # Query new pdf_case_structured chunks from Milvus
    client = get_vector_store()
    print("Querying pdf_case_structured chunks...")

    new_chunks_raw = []
    offset = 0
    page_size = 50
    while True:
        batch = client.query(COLLECTION,
                             'chunk_type == "pdf_case_structured"',
                             limit=page_size, offset=offset)
        if not batch:
            break
        new_chunks_raw.extend(batch)
        offset += page_size
        print(f"  {len(new_chunks_raw)}...")
        if len(batch) < page_size:
            break

    print(f"Got {len(new_chunks_raw)} pdf_case_structured chunks")

    # Format
    new_chunks = []
    for d in new_chunks_raw:
        chunk = {
            "chunk_id": d.get("id", ""),
            "chunk_type": _get_field(d, "chunk_type"),
            "retrieval_text": d.get("retrieval_text", ""),
            "text": d.get("text", ""),
            "law_name": _get_field(d, "law_name"),
            "article_id": _get_field(d, "article_id"),
            "parent_id": _get_field(d, "parent_id"),
            "parent_content": "",
            "source_doc": _get_field(d, "source_doc"),
            "category": _get_field(d, "category"),
            "data_version": _get_field(d, "data_version"),
            "chunk_order": _get_field(d, "chunk_order"),
            "title": _get_field(d, "title"),
            "chapter": _get_field(d, "chapter"),
            "section": _get_field(d, "section"),
            "case_ref": _get_field(d, "case_ref"),
            "segment_type": _get_field(d, "segment_type"),
            "related_chunks": [],
        }
        new_chunks.append(chunk)

    data["chunks"].extend(new_chunks)
    data["total"] = len(data["chunks"])
    data["version"] = "2026-07-04_v3"
    data["description"] = f"Replaced {len(old_case_para)} pdf_case_paragraph with {len(new_chunks)} pdf_case_structured. Total: {len(data['chunks'])} chunks"

    # Backup
    import shutil
    shutil.copy2(CHUNKS_PATH, BAK_PATH)
    print(f"Backed up to {BAK_PATH}")

    # Save
    with open(CHUNKS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"Saved {len(data['chunks'])} chunks (removed {len(old_case_para)} old, added {len(new_chunks)} new)")

if __name__ == "__main__":
    main()
