#!/usr/bin/env python
"""
同步 policy_chunks_export.json 中清洗后的 law_name 到 Milvus 向量数据库

两种策略:
  策略一 (--strategy smart): 查询现有向量 → 仅更新 law_name → 批 upsert 回写（保留向量，免重嵌入）
  策略二 (--strategy rebuild): 删 collection → 重建 → 全文重嵌入重入（安全但慢，~8000次嵌入）

用法:
  python sync_law_name_to_milvus.py --strategy smart   # 推荐：快，保留向量
  python sync_law_name_to_milvus.py --strategy rebuild # 备选：慢但彻底
  python sync_law_name_to_milvus.py --dry-run           # 仅对比差异，不写库
"""

import sys
import json
import time
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from config import settings

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
CHUNKS_PATH = Path(__file__).parent / "data" / "eval_questions" / "policy_chunks_export.json"
COLLECTION = "policy"
BATCH_SIZE = 100  # 每批查询 / upsert 的实体数
MILVUS_TIMEOUT = 120


# ---------------------------------------------------------------------------
# HTTP 客户端
# ---------------------------------------------------------------------------
def _get_client() -> httpx.Client:
    """创建并返回同步 httpx 客户端，连接 Milvus REST API"""
    headers = {"Content-Type": "application/json"}
    if settings.milvus_token:
        headers["Authorization"] = f"Bearer {settings.milvus_token}"
    return httpx.Client(
        base_url=settings.milvus_uri.rstrip("/"),  # .rstrip 方法的作用是：去除字符串末尾指定的字符（此处去除尾随斜杠）
        headers=headers,
        timeout=MILVUS_TIMEOUT,
    )


def _base_payload() -> Dict:
    """构建 Milvus REST API 请求的基础负载字典（包含库名和集合名）"""
    return {
        "collectionName": COLLECTION,  # ★ 硬编码 policy 集合，确保只操作目标集合
        "dbName": settings.milvus_database,
    }


def _post(client: httpx.Client, endpoint: str, payload: Dict):
    """
    向 Milvus REST API 发送 POST 请求并处理响应。
    .post 方法的作用是：向指定 URL 发送 HTTP POST 请求并携带 JSON 负载
    .json 方法的作用是：将 HTTP 响应体中的 JSON 内容解析为 Python 字典
    .raise_for_status 方法的作用是：若 HTTP 状态码非 2xx 则抛出异常
    """
    response = client.post(endpoint, json=payload)  # .post 方法的作用是：向 Milvus REST 端点发送 POST 请求，json=payload 将字典序列化为 JSON
    response.raise_for_status()  # .raise_for_status 方法的作用是：检查 HTTP 响应状态码，非 2xx 时抛出 HTTPError 异常
    body = response.json()  # .json 方法的作用是：将 HTTP 响应体的 JSON 字符串反序列化为 Python 字典对象
    if body.get("code") != 0:
        raise RuntimeError(f"Milvus error (code={body.get('code')}): {body.get('message', body)}")
    return body.get("data", {})  # .get 方法的作用是：安全获取字典中 "data" 键的值，若键不存在则返回空字典 {}


# ---------------------------------------------------------------------------
# 核心逻辑
# ---------------------------------------------------------------------------
def load_id_law_map() -> Dict[str, str]:
    """
    从 policy_chunks_export.json 中加载 chunk_id → law_name 映射表。
    .get 方法的作用是：安全获取字典中指定键的值，键不存在时返回默认值
    """
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        chunks_data = json.load(f)  # .load 方法的作用是：从文件流中读取 JSON 文本并将其反序列化为 Python 字典对象

    id_law_map = {}
    for chunk in chunks_data.get("chunks", []):  # .get 方法的作用是：安全获取字典中 "chunks" 键的值，若键不存在则返回空列表
        chunk_id = chunk.get("id", "")  # .get 方法的作用是：安全获取字典中 "id" 键的值，若键不存在则返回空字符串
        law_name = chunk.get("law_name", "")  # .get 方法的作用是：安全获取字典中 "law_name" 键的值，若键不存在则返回空字符串
        if chunk_id and law_name:
            id_law_map[chunk_id] = law_name

    print(f"从 JSON 加载了 {len(id_law_map)} 条 id → law_name 映射")
    return id_law_map


def count_milvus_entities(client: httpx.Client) -> int:
    """
    分页统计 Milvus Collection 中实体总数。
    策略: 逐页查询仅取 id 字段（轻量），累加计数，避免 offset 过大和响应体过大。
    """
    total = 0
    offset = 0
    page_size = 10000
    while True:
        payload = _base_payload()
        payload.update({
            "filter": "id != \"\"",
            "limit": page_size,
            "offset": offset,
            "outputFields": ["id"],  # 只取 id 字段，最小化每页响应体积
        })
        response = _post(client, "/v2/vectordb/entities/query", payload)
        if not isinstance(response, list):
            break
        total += len(response)
        if len(response) < page_size:
            break
        offset += page_size
    return total


# ═══════════════════════════════════════════════════════════════
# 策略一：Smart Upsert（查询现有向量 → 更新 law_name → 回写）
# ═══════════════════════════════════════════════════════════════

def strategy_smart_upsert(client: httpx.Client, id_law_map: Dict[str, str],
                          dry_run: bool = False):
    """
    策略一：智能增量更新。

    流程:
      1. 分批从 Milvus 查询现有实体（含 law_name + 向量字段）
      2. 对比 JSON 中的 law_name，仅标记有变化的实体
      3. 对有变化的实体，更新 law_name 字段，保留原有向量
      4. 批 upsert 回 Milvus（主键 id 匹配，覆盖更新）

    优势: 不需要重新嵌入文本，只批量回写标量字段，速度快。
    前提: Milvus Collection 必须存在且包含现有实体。
    """
    json_ids = set(id_law_map.keys())  # .keys 方法的作用是：返回字典所有键的视图对象，set() 转为集合便于快速查重
    print(f"\n{'=' * 60}")
    print(f"策略一: Smart Upsert (保留向量，仅更新 law_name)")
    print(f"{'=' * 60}")

    milvus_count = count_milvus_entities(client)
    print(f"Milvus '{COLLECTION}' 当前实体数: {milvus_count}")

    # 第一步: 分页获取 Milvus 中所有实体 ID
    print("\n[1/3] 获取 Milvus 全量 ID 列表...")
    all_milvus_ids = []
    offset = 0
    page_size = 10000
    while True:
        payload = _base_payload()
        payload.update({
            "filter": "id != \"\"",
            "limit": page_size,
            "offset": offset,
            "outputFields": ["id"],  # 仅取主键 ID，减少数据传输量
        })
        response = _post(client, "/v2/vectordb/entities/query", payload)
        if not isinstance(response, list) or not response:
            break
        all_milvus_ids.extend([e["id"] for e in response])  # e["id"] 通过字典键获取每个实体的主键 ID 字符串
        if len(response) < page_size:
            break
        offset += page_size
    print(f"  Milvus 共有 {len(all_milvus_ids)} 个实体")

    # 计算交集: 仅在 JSON 中有映射且在 Milvus 中存在的 ID
    milvus_id_set = set(all_milvus_ids)
    target_ids = sorted(json_ids & milvus_id_set)  # & 集合交集运算，找出两边都存在的 ID
    missing_in_milvus = json_ids - milvus_id_set  # 差集：JSON 有但 Milvus 没有的 ID
    extra_in_milvus = milvus_id_set - json_ids  # 差集：Milvus 有但 JSON 没有的 ID
    print(f"  交集 (待检查): {len(target_ids)}")
    print(f"  JSON 有但 Milvus 无: {len(missing_in_milvus)}")
    print(f"  Milvus 有但 JSON 无: {len(extra_in_milvus)}")

    # 第二步: 分批查询完整实体（含向量字段 + 全部标量字段），对比并更新
    print(f"\n[2/3] 分批查询实体并对比 law_name...")
    # ★ 稀疏向量（BM25 函数生成）不可直接 GET 读取，回写时由函数自动从 retrieval_text 重新生成
    # ★ 必须查询全部标量字段，因为 upsert 会完整覆盖实体行
    output_fields = [
        "id", "retrieval_text", "text",
        "law_name", "article_id", "parent_id",
        "title", "source_doc", "chunk_type", "chunk_order", "chunk_hash", "token_count",
        "project_name", "supplier", "region", "publish_date", "category", "data_version",
        "metadata",
        settings.milvus_dense_field,  # 稠密向量字段——保留以回写，避免重嵌入
    ]

    updated_count = 0
    unchanged_count = 0
    not_found_count = 0
    upsert_batch = []  # 收集需要回写的实体

    for batch_start in range(0, len(target_ids), BATCH_SIZE):
        batch_ids = target_ids[batch_start:batch_start + BATCH_SIZE]

        # ★ 用 /v2/vectordb/entities/get 精确按 ID 获取实体（含向量）
        get_payload = _base_payload()
        get_payload.update({
            "id": batch_ids,  # ★ 按主键 ID 列表精确查询，Milvus REST v2 的 get 端点支持批量 ID
            "outputFields": output_fields,  # 指定返回字段，包含向量字段以保留嵌入
        })
        entities = _post(client, "/v2/vectordb/entities/get", get_payload)

        if not isinstance(entities, list):
            print(f"    批次 {batch_start//BATCH_SIZE+1}: 查询返回异常类型 {type(entities)}")
            not_found_count += len(batch_ids)
            continue

        # 构建 Milvus 返回的 id → entity 快速查找表
        milvus_by_id = {}
        for entity in entities:
            eid = entity.get("id", "")  # .get 方法的作用是：安全获取实体中主键 id 的值
            if eid:
                milvus_by_id[eid] = entity  # 构建 id -> 实体字典，用于 O(1) 查找

        for chunk_id in batch_ids:
            new_law = id_law_map.get(chunk_id, "")  # .get 方法的作用是：从 JSON 映射表中获取 chunk_id 对应的新 law_name
            entity = milvus_by_id.get(chunk_id)  # .get 方法的作用是：从 Milvus 返回结果中查找对应实体

            if entity is None:
                not_found_count += 1
                continue

            old_law = entity.get("law_name", "")  # .get 方法的作用是：安全获取实体当前存储的 law_name 值
            if old_law == new_law:
                unchanged_count += 1
                continue

            # ★ 修改 law_name，保留原始向量字段
            entity["law_name"] = new_law
            upsert_batch.append(entity)
            updated_count += 1

        # 第三步: 每收集满一批就回写
        if len(upsert_batch) >= BATCH_SIZE:
            if not dry_run:
                _upsert_entities(client, upsert_batch)
            upsert_batch.clear()
            print(f"    已处理 {min(batch_start + BATCH_SIZE, len(target_ids))}/{len(target_ids)}, "
                  f"变更: {updated_count}")

        time.sleep(0.2)  # 温和限速，避免压垮 Milvus

    # 第三步（收尾）: 回写最后一批
    if upsert_batch and not dry_run:
        _upsert_entities(client, upsert_batch)
        print(f"    最终批次回写完成")

    print(f"\n  结果: 更新 {updated_count} 条, 无变化 {unchanged_count} 条, 未找到 {not_found_count} 条")
    if dry_run:
        print(f"  [DRY-RUN] 未实际写入，以上为模拟结果")
    return updated_count


def _upsert_entities(client: httpx.Client, entities: List[Dict]) -> int:
    """
    将实体列表批量 upsert 回 Milvus。
    /v2/vectordb/entities/upsert 端点: 按主键 id 匹配，存在则覆盖全部字段，不存在则新建。
    .get 方法的作用是：从返回的字典中获取 "upsertCount" 字段表示实际更新的行数
    """
    payload = _base_payload()
    payload["data"] = entities  # ★ data 字段承载完整的实体数组，每个实体必须包含向量字段
    result = _post(client, "/v2/vectordb/entities/upsert", payload)
    if isinstance(result, dict):
        return result.get("upsertCount", len(entities))  # .get 方法的作用是：安全获取 upsertCount 字段，不存在时默认返回实体数
    return len(entities)


# ═══════════════════════════════════════════════════════════════
# 策略二：Rebuild（删库重建，最安全但最慢）
# ═══════════════════════════════════════════════════════════════

def strategy_rebuild(client: httpx.Client, id_law_map: Dict[str, str],
                     dry_run: bool = False):
    """
    策略二：完全重建。

    流程:
      1. 从 JSON 读取全部 chunk（含清洗后的 law_name）
      2. 删除 Milvus 中现有 "policy" Collection
      3. 重新创建 Collection（含 Schema + 索引）
      4. 逐批嵌入 retrieval_text 并插入

    优势: 最彻底的清洗，确保 Milvus 状态与 JSON 完全一致。
    劣势: 需要重新嵌入全部文本（~8000+ 条），耗时较长。
    """
    print(f"\n{'=' * 60}")
    print(f"策略二: Rebuild (删库 → 重建 → 全文重嵌入)")
    print(f"{'=' * 60}")

    # 1. 从 JSON 中加载全部 chunk 数据
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        chunks_data = json.load(f)  # .load 方法的作用是：从文件流中反序列化 JSON 文本为 Python 字典

    all_chunks = chunks_data.get("chunks", [])  # .get 方法的作用是：安全获取 chunks 列表，不存在则返回空列表
    print(f"JSON 共 {len(all_chunks)} 个 chunk")

    if dry_run:
        print("[DRY-RUN] 不执行删库和重建操作")
        # 统计 law_name 分布
        name_counts = defaultdict(int)
        for c in all_chunks:
            name_counts[c.get("law_name", "(空)")] += 1  # .get 方法的作用是：安全获取 chunk 的 law_name，不存在时返回 "(空)"
        print(f"不同 law_name 数: {len(name_counts)}")
        for name, cnt in sorted(name_counts.items(), key=lambda x: -x[1])[:10]:
            print(f"  {cnt:5d}  {name[:70]}")
        return

    # 2. 删除现有 Collection
    print(f"\n[1/4] 删除现有 Collection '{COLLECTION}'...")
    try:
        drop_payload = _base_payload()
        _post(client, "/v2/vectordb/collections/drop", drop_payload)
        print(f"  已删除 '{COLLECTION}'")
    except Exception as e:
        print(f"  删除失败（可能不存在）: {e}")

    # 3. 重新创建 Collection（复用现有 MilvusStore 逻辑）
    print(f"\n[2/4] 重新创建 Collection...")
    from app.storage.milvus_store import MilvusStore
    store = MilvusStore()  # 单例模式，复用已有连接
    store.create_collection(COLLECTION)
    time.sleep(2)  # Milvus 建索引需要短暂等待

    # 4. 重新嵌入并插入全部 chunk
    print(f"\n[3/4] 重新嵌入并插入 {len(all_chunks)} 个 chunk...")
    from app.core.embedding import EmbeddingService

    embedding_service = EmbeddingService()  # 单例 BGE 嵌入模型
    batch_size = 200
    total_inserted = 0

    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i:i + batch_size]

        retrieval_texts = []
        texts = []
        metadatas = []
        ids = []

        for chunk in batch:
            rt = chunk.get("retrieval_text", chunk.get("text", ""))  # .get 方法的作用是：安全获取检索文本，回退到 text 字段
            txt = chunk.get("text", rt)  # .get 方法的作用是：安全获取原始文本，不存在时使用检索文本
            cid = chunk.get("id", "")  # .get 方法的作用是：安全获取 chunk 主键 ID

            if not cid or not rt:
                continue

            retrieval_texts.append(rt)
            texts.append(txt)
            # ★ 使用清洗后的 law_name
            metadatas.append({
                "law_name": chunk.get("law_name", ""),
                "article_id": str(chunk.get("article_id", "")),
                "chunk_type": chunk.get("chunk_type", ""),
                "source_doc": chunk.get("source_doc", chunk.get("law_name", "")),
                "title": chunk.get("source_doc", chunk.get("law_name", "")),
                "parent_id": chunk.get("parent_id", ""),
                "chunk_order": str(chunk.get("chunk_order", "")),
                "category": chunk.get("category", ""),
                "data_version": chunk.get("data_version", ""),
            })
            ids.append(cid)

        if not retrieval_texts:
            continue

        # ★ embed_batch 方法的作用是：对一批文本调用 BGE 模型生成稠密向量（一次前向传播批量编码）
        embeddings = embedding_service.embed_batch(retrieval_texts)

        rows = []
        for rt, txt, meta, doc_id, vec in zip(retrieval_texts, texts, metadatas, ids, embeddings):
            row = store._build_row(doc_id, rt, txt, meta)
            row[settings.milvus_dense_field] = vec  # ★ 将 BGE 编码的稠密向量赋值给实体行
            rows.append(row)

        store.upsert(COLLECTION, rows)  # .upsert 方法的作用是：按主键 id 插入或覆盖实体到 Milvus
        total_inserted += len(rows)
        print(f"  批次 {i // batch_size + 1}: {total_inserted}/{len(all_chunks)}")

    # 5. 加载 Collection 到内存（启用搜索）
    print(f"\n[4/4] 加载 Collection 到内存...")
    load_payload = _base_payload()
    _post(client, "/v2/vectordb/collections/load", load_payload)
    print(f"  已触发加载命令")

    final_count = count_milvus_entities(client)
    print(f"\n  重建完成! Milvus 最终实体数: {final_count}")


# ═══════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="同步 policy_chunks_export.json 中清洗后的 law_name 到 Milvus"
    )
    parser.add_argument(
        "--strategy", choices=["smart", "rebuild"], default="smart",
        help="同步策略: smart=保留向量仅更新标量(推荐), rebuild=删库重建(最慢)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="仅对比差异不实际写入 Milvus"
    )
    args = parser.parse_args()

    # 1. 加载 JSON 映射
    id_law_map = load_id_law_map()
    if not id_law_map:
        print("错误: policy_chunks_export.json 中没有有效数据")
        sys.exit(1)

    # 2. 连接 Milvus
    print(f"\n连接 Milvus: {settings.milvus_uri}, db={settings.milvus_database}")
    client = _get_client()

    # 3. 执行策略
    if args.strategy == "smart":
        strategy_smart_upsert(client, id_law_map, dry_run=args.dry_run)
    elif args.strategy == "rebuild":
        strategy_rebuild(client, id_law_map, dry_run=args.dry_run)

    # 4. 关闭连接
    client.close()  # .close 方法的作用是：关闭 httpx 客户端连接，释放底层 TCP 套接字资源
    print("\n完成。")


if __name__ == "__main__":
    main()
