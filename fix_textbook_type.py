#!/usr/bin/env python3
"""更新教科书 chunk_type: pdf_case_structured → pdf_textbook_structured (Milvus metadata only)"""

import httpx, sys

MILVUS_URL = "http://localhost:19531"
COLLECTION = "policy_v9"
DB = "panxin_dev"


def _post(endpoint, payload):
    r = httpx.post(f"{MILVUS_URL}{endpoint}", json=payload, timeout=120)
    r.raise_for_status()
    body = r.json()
    return body.get("data", body)


# Step 1: Find all textbook chunks
print("Finding textbook chunks...")
offset = 0
page = 10000
textbook_ids = []
while True:
    data = _post("/v2/vectordb/entities/query", {
        "collectionName": COLLECTION, "dbName": DB,
        "filter": 'chunk_type == "pdf_case_structured" and law_name like "%法律解读与风险防范实务%"',
        "limit": page, "offset": offset,
        "outputFields": ["id"],
    })
    if not isinstance(data, list) or not data:
        break
    textbook_ids.extend([e["id"] for e in data])
    if len(data) < page:
        break
    offset += page

print(f"Found {len(textbook_ids)} textbook chunks")

if not textbook_ids:
    print("No textbook chunks found!")
    sys.exit(1)

# Step 2: Fetch full entities with vectors, update chunk_type, upsert
from app.core.embedding import EmbeddingService  # won't work standalone

# Actually, we can't easily get the dense_vector back via REST get
# Alternative: re-embed and upsert

# Let's use a different approach — get entities and modify in-place
batch_size = 10
updated = 0
for i in range(0, len(textbook_ids), batch_size):
    batch = textbook_ids[i:i + batch_size]
    # Get full entity
    entities = _post("/v2/vectordb/entities/get", {
        "collectionName": COLLECTION, "dbName": DB,
        "id": batch,
    })
    if not isinstance(entities, list):
        continue

    # Upsert with modified chunk_type
    for e in entities:
        e["chunk_type"] = "pdf_textbook_structured"

    _post("/v2/vectordb/entities/upsert", {
        "collectionName": COLLECTION, "dbName": DB,
        "data": entities,
    })
    updated += len(entities)
    if updated % 100 == 0:
        print(f"  Updated {updated}/{len(textbook_ids)}...")

print(f"Done. Updated {updated} chunks.")
