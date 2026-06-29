"""Milvus向量数据库客户端 — REST API v2（同步）"""

import json
from typing import List, Dict, Optional

import httpx

from config import settings


class MilvusStore:
    """Milvus REST v2 客户端，接口与 ChromaStore 兼容"""

    _instance = None
    _client: httpx.Client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if settings.milvus_token:
                headers["Authorization"] = f"Bearer {settings.milvus_token}"
            self._client = httpx.Client(
                base_url=settings.milvus_uri.rstrip("/"),
                headers=headers,
                timeout=settings.milvus_timeout,
            )
            print(f"[Milvus] Connected to {settings.milvus_uri}, db={settings.milvus_database}")
        return self._client

    # ═════════════════════════════════════════════════════════════
    # Public API — 兼容 ChromaStore 接口
    # ═════════════════════════════════════════════════════════════

    def get_collection(self, name: str):
        return self

    def get_raw_collection(self, name: str):
        return self

    def add_documents(self, collection: str, retrieval_texts: List[str],
                      texts: List[str], metadatas: List[Dict], ids: List[str]):
        if not retrieval_texts:
            return
        self._ensure_collection(collection)
        from app.core.embedding import EmbeddingService
        batch_size = 50
        total = 0
        for i in range(0, len(retrieval_texts), batch_size):
            batch_rt = retrieval_texts[i:i + batch_size]
            batch_texts = texts[i:i + batch_size]
            batch_metas = metadatas[i:i + batch_size]
            batch_ids = ids[i:i + batch_size]
            # ★ embed(retrieval_text) 不污染语义
            embeddings = EmbeddingService().embed_batch(batch_rt)
            rows = []
            for rt, txt, meta, doc_id, vec in zip(batch_rt, batch_texts, batch_metas, batch_ids, embeddings):
                row = self._build_row(doc_id, rt, txt, meta)
                row[settings.milvus_dense_field] = vec
                rows.append(row)
            self.upsert(collection, rows)
            total += len(rows)
            print(f"[Milvus] Batch {i // batch_size + 1}: {total}/{len(retrieval_texts)} documents")
        print(f"[Milvus] Added {total} documents to '{collection}'")

    def rebuild_from_excel(self, collection: str, excel_path: str,
                           text_builder_func, extra_metadata: Dict = None):
        from pathlib import Path
        import pandas as pd
        import numpy as np

        if not Path(excel_path).exists():
            print(f"[Milvus] File not found: {excel_path}")
            return

        df = pd.read_excel(excel_path)

        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].dt.strftime('%Y-%m-%d')
            df[col] = df[col].replace({np.nan: None})

        data = df.to_dict('records')
        if not data:
            print("[Milvus] Warning: Excel file is empty.")
            return

        retrieval_texts, texts, metadatas, ids = [], [], [], []
        for i, record in enumerate(data):
            result = text_builder_func(record)
            if isinstance(result, tuple):
                rt, txt = result
            else:
                rt = txt = result  # backward compat
            if rt and len(rt) > 5:
                retrieval_texts.append(rt)
                texts.append(txt)
                clean_record = {k: (str(v) if v is not None else "") for k, v in record.items()}
                if extra_metadata:
                    clean_record.update(extra_metadata)
                metadatas.append(clean_record)
                ids.append(f"{collection}_{i}")

        self._ensure_collection(collection)
        existing = self.get_count(collection)
        if existing > 0:
            print(f"[Milvus] '{collection}' 已有 {existing} 条数据，跳过重建 (安全模式)")
            return

        self.add_documents(collection, retrieval_texts, texts, metadatas, ids)
        print(f"[Milvus] Rebuilt '{collection}' with {len(retrieval_texts)} documents")

    def _ensure_collection(self, collection: str):
        try:
            payload = self._base_payload(collection)
            self._post("/v2/vectordb/collections/describe", payload)
        except Exception:
            self.create_collection(collection)

    def search(self, collection: str, query: str, top_k: int = 10,
               query_vec: List[float] = None) -> List[Dict]:
        if query_vec is None:
            from app.core.embedding import EmbeddingService
            query_vec = EmbeddingService().embed_query(query)
        results = self.search_dense(collection, query_vec, top_k)
        from app.schema.metadata import normalize_chunks
        return normalize_chunks(results)

    def get_all_documents(self, collection: str) -> List[Dict]:
        """分页获取 collection 全部文档。

        策略: 先轻量查询拿所有 ID（outputFields=["id"]），再按 ID 批量
        取完整文档（每批 50 条）。避免 offset+全字段查询在文本较大的
        collection 上触发 Milvus "query results exceed the limit size" 错误。
        """
        # Step 1: 轻量取所有 ID
        all_ids = []
        offset = 0
        page_size = 10000
        try:
            while True:
                payload = self._base_payload(collection)
                payload.update({
                    "filter": "id != \"\"",
                    "limit": page_size,
                    "offset": offset,
                    "outputFields": ["id"],
                })
                response = self._post("/v2/vectordb/entities/query", payload)
                if not isinstance(response, list) or not response:
                    break
                all_ids.extend([e["id"] for e in response])
                if len(response) < page_size:
                    break
                offset += page_size
        except Exception as e:
            print(f"[Milvus] get_all_documents ID fetch error: {e}")
            return []

        # Step 2: 按 ID 分批取完整文档
        results = []
        batch_size = 50
        for i in range(0, len(all_ids), batch_size):
            batch_ids = all_ids[i:i + batch_size]
            docs = self.get_by_ids(collection, batch_ids)
            results.extend(docs)
        return results

    def get_count(self, collection: str) -> int:
        """分页累加获取 collection 真实文档总数。

        之前的 bug: limit=1 导致 len(result) 永远 ≤ 1。
        修复: 分页查询，只用 outputFields=["id"] 避免文本字段过大导致
        Milvus "query results exceed the limit size" 错误。
        每页 10000 条，累加至不足一页为止。
        """
        try:
            total = 0
            offset = 0
            page_size = 10000
            while True:
                payload = self._base_payload(collection)
                payload.update({
                    "filter": "id != \"\"",
                    "limit": page_size,
                    "offset": offset,
                    "outputFields": ["id"],  # 只取 id，最小化响应体积
                })
                response = self._post("/v2/vectordb/entities/query", payload)
                if not isinstance(response, list):
                    break
                total += len(response)
                if len(response) < page_size:
                    break
                offset += page_size
            return total
        except Exception:
            return 0

    def delete_collection(self, collection: str):
        try:
            self._post("/v2/vectordb/collections/drop",
                       {"collectionName": collection, "dbName": settings.milvus_database})
            print(f"[Milvus] Deleted collection '{collection}'")
        except Exception as e:
            print(f"[Milvus] delete_collection error: {e}")

    # ═════════════════════════════════════════════════════════════
    # Milvus 专用 API
    # ═════════════════════════════════════════════════════════════

    def search_dense(self, collection: str, query_vector: List[float],
                     top_k: int, scalar_filter: str = "") -> List[Dict]:
        payload = self._base_payload(collection)
        payload.update({
            "data": [query_vector],
            "annsField": settings.milvus_dense_field,
            "limit": top_k,
            "outputFields": settings.milvus_output_fields,
            "searchParams": {"metric_type": settings.milvus_metric_type},
        })
        if scalar_filter:
            payload["filter"] = scalar_filter
        response = self._post("/v2/vectordb/entities/search", payload)
        return self._parse_search_response(response)

    def search_keyword(self, collection: str, query: str,
                       top_k: int, scalar_filter: str = "") -> List[Dict]:
        payload = self._base_payload(collection)
        payload.update({
            "data": [query],
            "annsField": settings.milvus_sparse_field,
            "limit": top_k,
            "outputFields": settings.milvus_output_fields,
            "searchParams": {"metricType": "BM25", "params": {}},
        })
        if scalar_filter:
            payload["filter"] = scalar_filter
        response = self._post("/v2/vectordb/entities/search", payload)
        return self._parse_search_response(response)

    def query(self, collection: str, scalar_filter: str,
              limit: int, offset: int = 0) -> List[Dict]:
        payload = self._base_payload(collection)
        payload.update({
            "filter": scalar_filter if scalar_filter else "id != \"\"",
            "limit": limit,
            "offset": offset,
            "outputFields": settings.milvus_output_fields,
        })
        response = self._post("/v2/vectordb/entities/query", payload)
        return [self._entity_to_doc(entity) for entity in response]

    def get_by_ids(self, collection: str, document_ids: List[str]) -> List[Dict]:
        if not document_ids:
            return []
        payload = self._base_payload(collection)
        payload.update({
            "id": document_ids,
            "outputFields": settings.milvus_output_fields,
        })
        response = self._post("/v2/vectordb/entities/get", payload)
        return [self._entity_to_doc(entity) for entity in response]

    def upsert(self, collection: str, rows: List[Dict]) -> int:
        payload = self._base_payload(collection)
        payload["data"] = rows
        response = self._post("/v2/vectordb/entities/upsert", payload)
        return response.get("upsertCount", len(rows)) if isinstance(response, dict) else len(rows)

    def create_collection(self, collection: str) -> None:
        schema = {
            "autoId": False,
            "enableDynamicField": True,
            "fields": [
                # ── 主键 ──
                self._varchar_field("id", 512, is_primary=True),
                # ── 文本（解耦）──
                self._varchar_field("retrieval_text", 65535, enable_analyzer=True),
                self._varchar_field("text", 65535),
                # ── 识别与溯源 ──
                self._varchar_field("title", 2048),
                self._varchar_field("source_doc", 2048),
                self._varchar_field("chunk_type", 64),
                self._varchar_field("chunk_order", 32),
                self._varchar_field("chunk_hash", 64),
                self._varchar_field("token_count", 16),
                # ── 法条定位 ──
                self._varchar_field("law_name", 1024),
                self._varchar_field("article_id", 128),
                self._varchar_field("parent_id", 512),
                # ── 业务字段 ──
                self._varchar_field("project_name", 1024),
                self._varchar_field("supplier", 1024),
                self._varchar_field("region", 128),
                self._varchar_field("publish_date", 64),
                self._varchar_field("category", 256),
                self._varchar_field("data_version", 128),
                # ── 扩展 ──
                self._varchar_field("metadata", 65535),
                # ── 向量 ──
                {
                    "fieldName": settings.milvus_dense_field,
                    "dataType": "FloatVector",
                    "elementTypeParams": {"dim": str(settings.embedding_dimension)},
                },
                {
                    "fieldName": settings.milvus_sparse_field,
                    "dataType": "SparseFloatVector",
                },
            ],
            "functions": [
                {
                    "name": "retrieval_bm25",
                    "type": "BM25",
                    "inputFieldNames": ["retrieval_text"],
                    "outputFieldNames": [settings.milvus_sparse_field],
                    "params": {},
                }
            ],
        }
        index_params = [
            {
                "fieldName": settings.milvus_dense_field,
                "metricType": settings.milvus_metric_type,
                "indexName": settings.milvus_dense_field,
                "indexType": "HNSW",
                "params": {
                    "M": settings.milvus_hnsw_m,
                    "efConstruction": settings.milvus_hnsw_ef_construction,
                },
            },
            {
                "fieldName": settings.milvus_sparse_field,
                "metricType": "BM25",
                "indexName": settings.milvus_sparse_field,
                "indexType": "SPARSE_INVERTED_INDEX",
                "params": {
                    "inverted_index_algo": "DAAT_MAXSCORE",
                    "bm25_k1": settings.milvus_bm25_k1,
                    "bm25_b": settings.milvus_bm25_b,
                },
            },
        ]
        payload = self._base_payload(collection)
        payload.update({"schema": schema, "indexParams": index_params})
        self._post("/v2/vectordb/collections/create", payload)
        print(f"[Milvus] Created collection '{collection}' (dim={settings.embedding_dimension})")

    # ═════════════════════════════════════════════════════════════
    # Internal helpers
    # ═════════════════════════════════════════════════════════════

    def _base_payload(self, collection: str) -> Dict:
        return {
            "collectionName": collection,
            "dbName": settings.milvus_database,
        }

    def _post(self, endpoint: str, payload: Dict):
        client = self._get_client()
        response = client.post(endpoint, json=payload)
        response.raise_for_status()
        body = response.json()
        if body.get("code") != 0:
            raise RuntimeError(f"Milvus error (code={body.get('code')}): {body.get('message', body)}")
        return body.get("data", {})

    def _parse_search_response(self, response) -> List[Dict]:
        if not response:
            return []
        hits = response[0] if (isinstance(response, list) and response
                               and isinstance(response[0], list)) else response
        results = []
        for hit in hits:
            doc = self._entity_to_doc(hit, hit.get("distance"))
            results.append(doc)
        return results

    def _entity_to_doc(self, entity: Dict, score: Optional[float] = None) -> Dict:
        """将 Milvus 实体转为规范文档 Dict。

        之前的 bug: 除 id/retrieval_text/text 外的所有字段（含 chunk_type/law_name/
        article_id 等关键字段）全部嵌套在 metadata 子字典中，导致调用方直接访问
        doc["chunk_type"] 返回空。gen_eval_benchmark_v2.py 的抽样逻辑依赖这些
        顶层字段做 chunk 分类，因此导出后 QA 生成完全失败。

        修复: 将 CANONICAL_FIELDS 定义的关键字段同时保留在顶层和 metadata 子字典中，
        既支持 doc["chunk_type"] 也支持 doc["metadata"]["chunk_type"]，向后兼容。
        """
        data = dict(entity)
        doc_id = data.pop("id", data.pop(settings.milvus_primary_field, ""))
        retrieval_text = data.pop("retrieval_text", data.pop(settings.milvus_content_field, ""))
        text = data.pop("text", data.pop(settings.milvus_text_field, retrieval_text))
        data.pop("distance", None)
        data.pop("dense_vector", None)
        data.pop("sparse_vector", None)

        # 解析 JSON metadata blob，合并到 data
        raw_meta = data.pop("metadata", None)
        if isinstance(raw_meta, str):
            try:
                raw_meta = json.loads(raw_meta)
            except json.JSONDecodeError:
                raw_meta = {"raw": raw_meta}
        if isinstance(raw_meta, dict):
            data.update(raw_meta)

        # 已知关键字段 — 同时保留在顶层和 metadata 子字典中（向后兼容）
        KNOWN_KEYS = (
            "title", "source_doc", "chunk_type", "chunk_order", "chunk_hash",
            "token_count", "law_name", "article_id", "parent_id",
            "project_name", "supplier", "region", "publish_date",
            "category", "data_version",
        )
        doc = {
            "id": str(doc_id),
            "retrieval_text": retrieval_text,
            "text": text,
            "score": float(score) if score is not None else 0.0,
        }
        meta_out = {}
        for key in KNOWN_KEYS:
            val = str(data.pop(key, "")) if data.get(key) is not None else ""
            doc[key] = val
            meta_out[key] = val

        # 剩余未知字段合并到 metadata 子字典
        if data:
            meta_out.update(data)
        doc["metadata"] = meta_out

        return doc

    def _truncate_text(self, text: str, max_bytes: int = 65000) -> str:
        """Truncate text to fit within max_bytes UTF-8 bytes (Milvus VarChar limit)"""
        encoded = text.encode('utf-8')
        if len(encoded) <= max_bytes:
            return text
        return encoded[:max_bytes].decode('utf-8', errors='ignore')

    def _build_row(self, doc_id: str, retrieval_text: str, text: str,
                   metadata: Dict) -> Dict:
        import hashlib
        retrieval_text = self._truncate_text(retrieval_text)
        text = self._truncate_text(text)
        # 稳定 hash（基于纯文本 content，不含 header）
        chunk_hash = hashlib.md5(text.encode('utf-8')).hexdigest()[:12]
        # 简易 token 估算（中文 ≈ 字符数，英文 ≈ 词数）
        token_count = str(len(text))
        row = {
            "id": doc_id,
            "retrieval_text": retrieval_text,
            "text": text,
            "title": str(metadata.get("title", metadata.get("source_doc", metadata.get("source", "")))),
            "source_doc": str(metadata.get("source_doc", metadata.get("source", ""))),
            "law_name": str(metadata.get("law_name", "")),
            "article_id": str(metadata.get("article_id", "")),
            "chunk_type": str(metadata.get("chunk_type", "")),
            "parent_id": str(metadata.get("parent_id", "")),
            "chunk_order": str(metadata.get("chunk_order", metadata.get("chunk_index", ""))),
            "chunk_hash": chunk_hash,
            "token_count": token_count,
            "project_name": str(metadata.get("project_name", metadata.get("项目名称", ""))),
            "supplier": str(metadata.get("supplier", metadata.get("中标人", ""))),
            "region": str(metadata.get("region", metadata.get("省份", ""))),
            "publish_date": str(metadata.get("publish_date", metadata.get("发布时间", ""))),
            "category": str(metadata.get("category", metadata.get("类别", ""))),
            "data_version": str(metadata.get("data_version", "")),
            "metadata": json.dumps(metadata, ensure_ascii=False),
        }
        return row

    @staticmethod
    def _varchar_field(name: str, max_length: int,
                       is_primary: bool = False,
                       enable_analyzer: bool = False) -> Dict:
        field = {
            "fieldName": name,
            "dataType": "VarChar",
            "elementTypeParams": {"max_length": max_length},
        }
        if is_primary:
            field["isPrimary"] = True
        if enable_analyzer:
            field["elementTypeParams"]["enable_analyzer"] = True
            field["elementTypeParams"]["enable_match"] = True
        return field
