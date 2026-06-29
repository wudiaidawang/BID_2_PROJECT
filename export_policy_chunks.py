"""Export all chunks from Milvus policy_v4 to JSON"""
import httpx, json, os

uri = "http://127.0.0.1:19531"
db = "panxin_dev"
collection = "policy_v4"

all_data = []
offset = 0
while True:
    r = httpx.post(uri + "/v2/vectordb/entities/query",
        json={"collectionName": collection, "dbName": db,
              "filter": 'id != ""', "limit": 10000, "offset": offset,
              "outputFields": ["*"]}, timeout=30)
    data = r.json().get("data", [])
    if not data:
        break
    all_data.extend(data)
    if len(data) < 10000:
        break
    offset += 10000
    print(f"  fetched {len(all_data)}...")

output = {"total": len(all_data), "chunks": all_data}
os.makedirs("data/eval_questions", exist_ok=True)
with open("data/eval_questions/policy_chunks_export.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"Exported {len(all_data)} chunks to data/eval_questions/policy_chunks_export.json")
