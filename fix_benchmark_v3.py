#!/usr/bin/env python
"""Fix benchmark: 截断law_name的chunk ID → 新ID + opinion/policy law_name同步 → v3"""
import json
import re
import sys
import time
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from app.storage.milvus_store import MilvusStore

QA_PATH = "data/eval_questions/eval_benchmark_v2.json"
OUT_PATH = "data/eval_questions/eval_benchmark_v3.json"

OLD_TO_NEW_LAW = {
    "和服务定点采购管理办法": "中央国家机关政府采购中心货物和服务定点采购管理办法",
    "及评标专家管理办法": "铁路建设工程评标专家库及评标专家管理办法",
    "与招投标挂钩办法": "铁路建设工程质量安全事故与招投标挂钩办法",
}

COLLECTION = "policy"


def get_store():
    """获取 MilvusStore 实例（重置连接）"""
    MilvusStore._instance = None
    MilvusStore._client = None
    return MilvusStore()


def find_new_chunk_ids(store):
    """对每个截断law_name，从Milvus查出 旧article_id→新chunk_id 的映射"""
    id_map = {}

    for old_name, new_name in OLD_TO_NEW_LAW.items():
        # 获取该law_name的所有chunk
        all_docs = []
        try:
            # 用分页查询获取所有
            client = store._get_client()
            offset = 0
            page_size = 5000
            while True:
                payload = store._base_payload(COLLECTION)
                payload.update({
                    "filter": f'law_name == "{new_name}"',
                    "limit": page_size,
                    "offset": offset,
                    "outputFields": ["id", "article_id", "chunk_type"],
                })
                resp = store._post("/v2/vectordb/entities/query", payload)
                if not isinstance(resp, list) or not resp:
                    break
                all_docs.extend(resp)
                if len(resp) < page_size:
                    break
                offset += page_size
        except Exception as e:
            print(f"  [WARN] query '{new_name}': {e}")
            continue

        if not all_docs:
            print(f"  [WARN] No chunks for '{new_name}'")
            continue

        # 建立 (article_id, chunk_type) → [new_ids] 映射
        new_by_key = defaultdict(list)
        for doc in all_docs:
            art_id = str(doc.get("article_id", ""))
            ctype = str(doc.get("chunk_type", ""))
            if art_id:
                new_by_key[(art_id, ctype)].append(doc["id"])

        print(f"  '{new_name}': {len(all_docs)} chunks, {len(new_by_key)} unique keys")
        id_map[old_name] = dict(new_by_key)  # (article_id, type) → list of IDs

    return id_map


def parse_old_chunk_id(chunk_id: str) -> dict:
    """从旧chunk ID提取 article_id 和 chunk_type"""
    info = {"article_id": "", "chunk_type": "", "old_law_name": ""}
    cid = str(chunk_id)

    if cid.startswith("parent_"):
        rest = cid[7:]
        if "_child" in rest:
            info["chunk_type"] = "pdf_law_child"
            rest = re.sub(r'_child\d+$', '', rest)
        else:
            info["chunk_type"] = "pdf_law_parent"
        parts = rest.rsplit('_', 3)
        if len(parts) >= 4:
            info["old_law_name"] = parts[0]
            info["article_id"] = parts[1]
    return info


def fix_truncated_questions(qa_pairs, id_map):
    """修复截断law_name的题目：替换source_chunks中的旧ID"""
    fixed_count = 0
    unfixed = []

    for qa in qa_pairs:
        new_chunks = []
        for sc in qa.get("source_chunks", []):
            old_info = parse_old_chunk_id(sc)
            old_name = old_info["old_law_name"]
            article_id = old_info["article_id"]
            chunk_type = old_info["chunk_type"]

            if old_name in id_map and article_id:
                key = (article_id, chunk_type)
                candidates = id_map[old_name].get(key, [])
                if candidates:
                    # 取第一个未使用的候选ID
                    chosen = None
                    for cid in candidates:
                        if cid not in new_chunks:
                            chosen = cid
                            break
                    if chosen:
                        new_chunks.append(chosen)
                        fixed_count += 1
                        continue

            new_chunks.append(sc)
            if old_name in OLD_TO_NEW_LAW:
                unfixed.append({"qa_id": qa["id"], "old_id": sc, "article_id": article_id})

        qa["source_chunks"] = new_chunks

    return fixed_count, unfixed


def sync_opinion_policy_law_name(qa_pairs, store):
    """为 opinion/policy 题目在 QA 级别添加 law_name 字段"""
    # 收集所有 opinion/policy chunk ID
    op_ids = set()
    for qa in qa_pairs:
        if qa.get("chunk_type") in ("opinion_news", "policy_doc"):
            op_ids.update(qa.get("source_chunks", []))

    if not op_ids:
        return 0

    # 批量查 Milvus
    id_to_law = {}
    id_list = list(op_ids)
    batch_size = 100
    for i in range(0, len(id_list), batch_size):
        batch = id_list[i:i + batch_size]
        try:
            docs = store.get_by_ids(COLLECTION, batch)
            for doc in docs:
                meta = doc.get("metadata", {})
                law = meta.get("law_name", "") or meta.get("title", "")
                if law:
                    id_to_law[doc["id"]] = law
        except Exception as e:
            print(f"  [WARN] get_by_ids batch {i//batch_size}: {e}")
            continue

    # 更新 QA
    synced = 0
    for qa in qa_pairs:
        if qa.get("chunk_type") in ("opinion_news", "policy_doc"):
            first_sc = qa["source_chunks"][0] if qa.get("source_chunks") else ""
            if first_sc in id_to_law:
                qa["law_name"] = id_to_law[first_sc]
                synced += 1

    return synced


def main():
    print("=" * 60)
    print("Fix Benchmark: v2 → v3")
    print("=" * 60)

    with open(QA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    qa_pairs = data["qa_pairs"]
    print(f"\n[1/4] 加载 v2 benchmark: {len(qa_pairs)} 题")

    print(f"\n[2/4] 从 Milvus 查询新 chunk ID 映射...")
    store = get_store()
    id_map = find_new_chunk_ids(store)

    print(f"\n[3/4] 修复截断law_name的 source_chunks...")
    store = get_store()  # 刷新连接
    fixed_count, unfixed = fix_truncated_questions(qa_pairs, id_map)
    print(f"  修复: {fixed_count} IDs")
    if unfixed:
        print(f"  未修复: {len(unfixed)} IDs")
        for u in unfixed[:5]:
            print(f"    {u['qa_id']}: article={u['article_id']}")

    print(f"\n[4/4] 同步 opinion/policy 的 law_name...")
    store = get_store()  # 刷新连接
    synced = sync_opinion_policy_law_name(qa_pairs, store)
    print(f"  同步: {synced} 题")

    # 写入 v3
    data["version"] = "v3"
    data["note"] = "v3: 修正截断law_name(3个→完整名称) + opinion/policy同步law_name字段"
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nSaved: {OUT_PATH}")
    print(f"Total: {len(qa_pairs)} QA pairs")

    # 验证
    print(f"\n--- 验证 ---")
    truncated_count = 0
    for qa in qa_pairs:
        for sc in qa.get("source_chunks", []):
            for old in OLD_TO_NEW_LAW:
                if old in sc:
                    truncated_count += 1
                    break
    print(f"  残余截断ID: {truncated_count}")

    op_with_law = sum(1 for qa in qa_pairs
                      if qa.get("chunk_type") in ("opinion_news", "policy_doc")
                      and qa.get("law_name"))
    op_total = sum(1 for qa in qa_pairs
                   if qa.get("chunk_type") in ("opinion_news", "policy_doc"))
    print(f"  opinion/policy 有 law_name: {op_with_law}/{op_total}")


if __name__ == "__main__":
    main()
