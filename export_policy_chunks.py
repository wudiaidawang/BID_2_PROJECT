"""Export all chunks from Milvus policy_v4 to JSON (两阶段：先取ID，再按ID批量取完整数据)"""
import httpx, json, os

uri = "http://127.0.0.1:19531"
db = "panxin_dev"
collection = "policy_v6"

# Phase 1: get all IDs
all_ids = []
offset = 0
while True:
    r = httpx.post(uri + "/v2/vectordb/entities/query",
        json={"collectionName": collection, "dbName": db,
              "filter": 'id != ""', "limit": 10000, "offset": offset,
              "outputFields": ["id"]}, timeout=30)
    data = r.json().get("data", [])
    if not data:
        break
    all_ids.extend([d["id"] for d in data])
    offset += 10000
    if len(data) < 10000:
        break
    print(f"  IDs fetched: {len(all_ids)}...")

# Phase 2: fetch full data by ID batches
all_data = []
batch_size = 50
for i in range(0, len(all_ids), batch_size):
    batch_ids = all_ids[i:i + batch_size]
    r = httpx.post(uri + "/v2/vectordb/entities/get",
        json={"collectionName": collection, "dbName": db,
              "id": batch_ids,
              "outputFields": ["id", "retrieval_text", "text", "chunk_type", "law_name",
                              "article_id", "parent_id", "source_doc", "title", "metadata",
                              "category", "data_version", "chunk_order"]}, timeout=30)
    data = r.json().get("data", [])
    all_data.extend(data)

    if (i // batch_size) % 20 == 0:
        print(f"  fetched {len(all_data)}/{len(all_ids)}...")

output = {"total": len(all_data), "chunks": all_data}
os.makedirs("data/eval_questions/ian", exist_ok=True)
with open("data/eval_questions/ian/ian_policy_chunks_export.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"Exported {len(all_data)} chunks to data/eval_questions/ian/ian_policy_chunks_export.json")
