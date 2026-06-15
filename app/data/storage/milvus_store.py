"""Milvus向量数据库客户端 — REST API v2（同步）"""

import json
import hashlib
from typing import List, Dict, Optional

import httpx
import numpy as np

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
        """兼容旧接口，返回 self（Milvus 不需要 LangChain wrapper）"""
        return self

    def get_raw_collection(self, name: str):
        """兼容旧接口"""
        return self

    def add_documents(self, collection: str, texts: List[str],
                      metadatas: List[Dict], ids: List[str]):
        """批量写入文档（自动生成向量并 upsert）"""
        if not texts:
            return
        from app.data.embedding import EmbeddingService
        embeddings = EmbeddingService().embed_batch(texts)
        rows = []
        for text, meta, doc_id, vec in zip(texts, metadatas, ids, embeddings):
            row = self._build_row(doc_id, text, meta)
            row[settings.milvus_dense_field] = vec
            rows.append(row)
        count = self.upsert(collection, rows)
        print(f"[Milvus] Added {count} documents to '{collection}'")

    def rebuild_from_excel(self, collection: str, excel_path: str,
                           text_builder_func):
        """从 Excel 重建集合（兼容 ChromaStore.rebuild_from_excel）"""
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

        texts, metadatas, ids = [], [], []
        for i, record in enumerate(data):
            text = text_builder_func(record)
            if text and len(text) > 5:
                texts.append(text)
                clean_record = {k: (str(v) if v is not None else "") for k, v in record.items()}
                metadatas.append(clean_record)
                ids.append(f"{collection}_{i}")

        # 确保集合存在
        self._ensure_collection(collection)

        # 清空旧数据（删除后重建集合）
        self.delete_collection(collection)
        self._ensure_collection(collection)

        self.add_documents(collection, texts, metadatas, ids)
        print(f"[Milvus] Rebuilt '{collection}' with {len(texts)} documents")

    def _ensure_collection(self, collection: str):
        """确保 collection 存在，不存在则创建"""
        try:
            payload = self._base_payload(collection)
            self._post("/v2/vectordb/collections/describe", payload)
        except Exception:
            self.create_collection(collection)

    def search(self, collection: str, query: str, top_k: int = 10) -> List[Dict]:
        """向量检索，返回统一格式（兼容 ChromaStore.search）"""
        from app.data.embedding import EmbeddingService
        query_vec = EmbeddingService().embed_query(query)
        results = self.search_dense(collection, query_vec, top_k)
        from app.data.schema.metadata import normalize_chunks
        return normalize_chunks(results)

    def get_all_documents(self, collection: str) -> List[Dict]:
        """获取集合全部文档"""
        try:
            results = self.query(collection, "", limit=10000)
            return results
        except Exception as e:
            print(f"[Milvus] get_all_documents error: {e}")
            return []

    def get_count(self, collection: str) -> int:
        try:
            payload = self._base_payload(collection)
            resp = self._post("/v2/vectordb/collections/describe", payload)
            # describe 返回 collection info，用 query 统计
            q_payload = self._base_payload(collection)
            q_payload["filter"] = "id != \"\""
            q_payload["limit"] = 1
            q_payload["outputFields"] = ["id"]
            result = self._post("/v2/vectordb/entities/query", q_payload)
            return len(result) if isinstance(result, list) else 0
        except Exception:
            # fallback: 用 query 扫描计数
            try:
                results = self.query(collection, "", limit=100000)
                return len(results)
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
        """密集向量 ANN 搜索"""
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
        """BM25 关键词搜索（Milvus 内置 BM25 函数）"""
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
              limit: int) -> List[Dict]:
        """标量过滤查询"""
        payload = self._base_payload(collection)
        payload.update({
            "filter": scalar_filter if scalar_filter else "id != \"\"",
            "limit": limit,
            "outputFields": settings.milvus_output_fields,
        })
        response = self._post("/v2/vectordb/entities/query", payload)
        return [self._entity_to_doc(entity) for entity in response]

    def get_by_ids(self, collection: str, document_ids: List[str]) -> List[Dict]:
        """按主键批量获取"""
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
        """批量插入/更新"""
        payload = self._base_payload(collection)
        payload["data"] = rows
        response = self._post("/v2/vectordb/entities/upsert", payload)
        return response.get("upsertCount", len(rows)) if isinstance(response, dict) else len(rows)

    def create_collection(self, collection: str) -> None:
        """创建集合（含完整 schema + 索引）"""
        schema = {
            "autoId": False,
            "enableDynamicField": True,
            "fields": [
                self._varchar_field("id", 512, is_primary=True),
                self._varchar_field("content", 65535, enable_analyzer=True),
                self._varchar_field("title", 2048),
                self._varchar_field("source", 2048),
                self._varchar_field("law_name", 1024),
                self._varchar_field("article_id", 128),
                self._varchar_field("chunk_type", 64),
                self._varchar_field("parent_id", 512),
                self._varchar_field("project_name", 1024),
                self._varchar_field("supplier", 1024),
                self._varchar_field("region", 128),
                self._varchar_field("publish_date", 64),
                self._varchar_field("category", 256),
                self._varchar_field("data_version", 128),
                self._varchar_field("metadata", 65535),
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
                    "name": "content_bm25",
                    "type": "BM25",
                    "inputFieldNames": [settings.milvus_content_field],
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
        """解析搜索响应，统一为内部格式"""
        if not response:
            return []
        # 响应可能是嵌套列表 [[...]] 或单层列表 [...]
        hits = response[0] if (isinstance(response, list) and response
                               and isinstance(response[0], list)) else response
        results = []
        for hit in hits:
            doc = self._entity_to_doc(hit, hit.get("distance"))
            results.append(doc)
        return results

    def _entity_to_doc(self, entity: Dict, score: Optional[float] = None) -> Dict:
        """将 Milvus 实体转为内部文档格式"""
        data = dict(entity)
        doc_id = data.pop("id", data.pop(settings.milvus_primary_field, ""))
        content = data.pop("content", data.pop(settings.milvus_content_field, ""))
        data.pop("distance", None)
        data.pop("dense_vector", None)
        data.pop("sparse_vector", None)

        # 解析 metadata JSON 字段
        raw_meta = data.pop("metadata", None)
        if isinstance(raw_meta, str):
            try:
                raw_meta = json.loads(raw_meta)
            except json.JSONDecodeError:
                raw_meta = {"raw": raw_meta}
        if isinstance(raw_meta, dict):
            data.update(raw_meta)

        return {
            "id": str(doc_id),
            "text": content,
            "metadata": data,
            "score": float(score) if score is not None else 0.0,
        }

    def _build_row(self, doc_id: str, text: str, metadata: Dict) -> Dict:
        """构建 upsert 行数据（不含向量，向量由 embedding 批量生成后注入）"""
        row = {
            "id": doc_id,
            "content": text,
            "title": str(metadata.get("title", metadata.get("source", ""))),
            "source": str(metadata.get("source", "")),
            "law_name": str(metadata.get("law_name", "")),
            "article_id": str(metadata.get("article_id", "")),
            "chunk_type": str(metadata.get("chunk_type", "")),
            "parent_id": str(metadata.get("parent_id", "")),
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

    @staticmethod
    def _escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')
