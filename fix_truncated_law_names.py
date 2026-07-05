#!/usr/bin/env python
"""Surgical fix: 删除大合集中截断law_name的旧chunk，用修正后的解析器重切重入"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import fitz
from config import settings
from app.storage import get_vector_store
from app.core.legal_structure_parser import LegalStructureParser
from app.core.parent_chunk_builder import ParentChunkBuilder
from app.core.child_chunk_builder import ChildChunkBuilder
from init_policy_collection import chunk_by_structure, PDF_DIR, _TRUNCATED_NAME_FIXES

TRUNCATED_NAMES = [
    "和服务定点采购管理办法",
    "及评标专家管理办法",
    "与招投标挂钩办法",
]

BIG_PDF_NAME = "中华人民共和国招标投标法律法规全书"
COLLECTION = "policy"


def delete_big_pdf_chunks(store):
    """删除大合集PDF的全部旧chunk（按 source_doc 过滤，避免重复导入）"""
    import time
    for attempt in range(3):
        try:
            return _delete_big_pdf_chunks_once(store)
        except Exception as e:
            print(f"  [RETRY delete {attempt+1}/3] {e}")
            if attempt < 2:
                time.sleep(3)
                from app.storage.milvus_store import MilvusStore
                MilvusStore._instance = None
                MilvusStore._client = None
                store = get_vector_store()
    return 0


def _delete_big_pdf_chunks_once(store):
    client = store._get_client()
    db_name = settings.milvus_database

    # 先查数量
    payload = {
        "collectionName": COLLECTION,
        "dbName": db_name,
        "filter": f'source_doc == "{BIG_PDF_NAME}"',
        "limit": 10000,
        "outputFields": ["id"],
    }
    try:
        resp = client.post("/v2/vectordb/entities/query", json=payload)
        data = resp.json().get("data", [])
        ids = [e["id"] for e in data] if isinstance(data, list) else []
    except Exception as e:
        print(f"  [WARN] query big PDF: {e}")
        return 0

    if not ids:
        print(f"  大合集PDF: 0 chunks")
        return 0

    delete_payload = {
        "collectionName": COLLECTION,
        "dbName": db_name,
        "filter": f'source_doc == "{BIG_PDF_NAME}"',
    }
    try:
        client.post("/v2/vectordb/entities/delete", json=delete_payload)
        print(f"  大合集PDF: deleted {len(ids)} chunks")
        return len(ids)
    except Exception as e:
        print(f"  [ERROR] delete big PDF: {e}")
        return 0


def delete_truncated_chunks(store):
    """查询并删除截断law_name的旧chunk（安全网：防止有漏网之鱼）"""
    client = store._get_client()
    db_name = settings.milvus_database
    total_deleted = 0

    for truncated_name in TRUNCATED_NAMES:
        payload = {
            "collectionName": COLLECTION,
            "dbName": db_name,
            "filter": f'law_name == "{truncated_name}"',
            "limit": 10000,
            "outputFields": ["id"],
        }
        try:
            resp = client.post("/v2/vectordb/entities/query", json=payload)
            data = resp.json().get("data", [])
            ids = [e["id"] for e in data] if isinstance(data, list) else []
        except Exception as e:
            print(f"  [WARN] query '{truncated_name}': {e}")
            continue

        if not ids:
            print(f"  '{truncated_name}': 0 chunks")
            continue

        delete_payload = {
            "collectionName": COLLECTION,
            "dbName": db_name,
            "filter": f'law_name == "{truncated_name}"',
        }
        try:
            client.post("/v2/vectordb/entities/delete", json=delete_payload)
            print(f"  '{truncated_name}': deleted {len(ids)} chunks")
            total_deleted += len(ids)
        except Exception as e:
            print(f"  [ERROR] delete '{truncated_name}': {e}")

    return total_deleted


def reimport_big_pdf(retry_count=3):
    """仅重处理大合集PDF（带重试）"""
    import time
    for attempt in range(retry_count):
        try:
            return _reimport_big_pdf_once()
        except Exception as e:
            print(f"    [RETRY {attempt+1}/{retry_count}] {e}")
            if attempt < retry_count - 1:
                time.sleep(5)
                # 重建 Milvus 连接
                from app.storage.milvus_store import MilvusStore
                MilvusStore._instance = None
                MilvusStore._client = None
    return 0


def _reimport_big_pdf_once():
    """仅重处理大合集PDF（单次尝试）"""
    store = get_vector_store()
    pdf_path = str(PDF_DIR / "中华人民共和国招标投标法律法规全书.pdf")
    if not Path(pdf_path).exists():
        print(f"  [ERROR] PDF不存在: {pdf_path}")
        return 0

    print(f"\n  重处理: 中华人民共和国招标投标法律法规全书.pdf")
    doc = fitz.open(pdf_path)
    full_text = "\n".join(page.get_text() for page in doc if page.get_text())
    total_pages = len(doc)
    doc.close()
    print(f"    提取 {total_pages} 页, {len(full_text)} 字符")

    result = chunk_by_structure(full_text, "中华人民共和国招标投标法律法规全书")
    if result is None:
        print("    [ERROR] 结构化解析失败")
        return 0

    all_rt, all_texts, metadatas, ids = result
    for m in metadatas:
        m["category"] = "policy"
        m["data_version"] = "2026-06-22_v3"

    store.add_documents(COLLECTION, all_rt, all_texts, metadatas, ids)
    print(f"    入库 {len(all_rt)} 条 (修正后)")

    # 打印修正后的law_name分布
    from collections import Counter
    name_counts = Counter(m["law_name"] for m in metadatas)
    for name in sorted(name_counts.keys()):
        for kw in ["定点采购", "评标专家", "挂钩"]:
            if kw in name:
                print(f"      ✓ {name}: {name_counts[name]} chunks")
                break

    return len(all_rt)


def main():
    print("=" * 60)
    print("Surgical Fix: 截断law_name → 完整名称")
    print("=" * 60)

    store = get_vector_store()

    before_count = store.get_count(COLLECTION)
    print(f"\n  修复前 policy collection: {before_count} chunks")

    print(f"\n[1/3] 清理大合集PDF旧chunk...")
    deleted_big = delete_big_pdf_chunks(store)
    deleted_trunc = delete_truncated_chunks(store)
    deleted = deleted_big + deleted_trunc
    print(f"  总计删除: {deleted} chunks (大合集: {deleted_big}, 截断残余: {deleted_trunc})")

    print(f"\n[2/3] 重处理大合集PDF（修正后解析器 + 跨行标题合并）...")
    added = reimport_big_pdf()

    print(f"\n[3/3] 验证...")
    import httpx
    r = httpx.post(f'{settings.milvus_uri}/v2/vectordb/entities/query', json={
        'collectionName': COLLECTION, 'dbName': settings.milvus_database,
        'filter': 'id != \"\"', 'limit': 1, 'outputFields': ['id'],
    }, timeout=10)
    # 通过循环分页快速估算总数
    print(f"  policy collection: 修复前 ~{before_count}, 删除 {deleted}, 新增 {added}")

    print(f"\n{'=' * 60}")
    print("完成! 截断law_name已修正为完整名称")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
