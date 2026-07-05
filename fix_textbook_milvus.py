"""Update textbook chunk_type in Milvus: pdf_case_structured -> pdf_textbook_structured"""
import httpx

MILVUS_URL = "http://localhost:19531"
COLLECTION = "policy_v9"
DB = "panxin_dev"

def post(endpoint, payload):
    r = httpx.post(f"{MILVUS_URL}{endpoint}", json=payload, timeout=120)
    r.raise_for_status()
    body = r.json()
    return body.get("data", body)


# Step 1: Find textbook chunk IDs
print("Step 1: Finding textbook chunks...")
offset = 0
page = 5000
ids = []
while True:
    data = post("/v2/vectordb/entities/query", {
        "collectionName": COLLECTION, "dbName": DB,
        "filter": 'law_name like "%法律解读与风险防范实务%"',
        "limit": page, "offset": offset,
        "outputFields": ["id", "chunk_type"],
    })
    if not isinstance(data, list) or not data:
        break
    for e in data:
        if e.get("chunk_type") == "pdf_case_structured":
            ids.append(e["id"])
    if len(data) < page:
        break
    offset += page

print(f"  Found {len(ids)} textbook chunks with pdf_case_structured")

if not ids:
    print("No textbook chunks to update!")
    exit(0)

# Step 2: Test one entity first
print("\nStep 2: Testing entity structure...")
test = post("/v2/vectordb/entities/get", {
    "collectionName": COLLECTION, "dbName": DB,
    "id": [ids[0]],
})
if test and isinstance(test, list):
    e = test[0]
    print(f"  Fields: {list(e.keys())}")
    has_dense = "dense_vector" in e
    print(f"  Has dense_vector: {has_dense}")
    print(f"  Current chunk_type: {e.get('chunk_type')}")
else:
    print("  ERROR: Cannot get entity!")
    exit(1)

# Step 3: Batch update
print(f"\nStep 3: Updating {len(ids)} entities...")
batch_size = 10
updated = 0
for i in range(0, len(ids), batch_size):
    batch = ids[i:i + batch_size]
    entities = post("/v2/vectordb/entities/get", {
        "collectionName": COLLECTION, "dbName": DB,
        "id": batch,
    })
    if not isinstance(entities, list):
        continue

    for e in entities:
        e["chunk_type"] = "pdf_textbook_structured"

    post("/v2/vectordb/entities/upsert", {
        "collectionName": COLLECTION, "dbName": DB,
        "data": entities,
    })
    updated += len(entities)
    if updated % 100 == 0:
        print(f"  {updated}/{len(ids)}...")

print(f"  Done! Updated {updated} entities")

# Step 4: Verify
print("\nStep 4: Verifying...")
verify = post("/v2/vectordb/entities/query", {
    "collectionName": COLLECTION, "dbName": DB,
    "filter": 'chunk_type == "pdf_textbook_structured"',
    "limit": 1,
    "outputFields": ["id", "chunk_type"],
})
if verify and isinstance(verify, list) and verify:
    print(f"  OK: Found pdf_textbook_structured entity: {verify[0].get('id','')}")

# Also check count
count_check = post("/v2/vectordb/entities/query", {
    "collectionName": COLLECTION, "dbName": DB,
    "filter": 'chunk_type == "pdf_textbook_structured"',
    "limit": 10000,
    "outputFields": ["id"],
})
if isinstance(count_check, list):
    print(f"  Total pdf_textbook_structured: {len(count_check)}")
print("Done!")
