"""Chroma向量数据库客户端"""

import chromadb
from chromadb.utils import embedding_functions
from typing import List, Dict, Callable
import pandas as pd
from pathlib import Path
from config import settings


class ChromaStore:
    """Chroma向量数据库客户端（单例模式）"""
    
    _instance = None
    _client = None
    _collections = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def _get_client(self):
        if self._client is None:
            self._client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
            print(f"Chroma client initialized, persist dir: {settings.chroma_persist_dir}")
        return self._client
    
    def _get_embedding_function(self):
        return embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=settings.embedding_model
        )
    
    def get_collection(self, name: str):
        if name not in self._collections:
            client = self._get_client()
            try:
                collection = client.get_collection(name)
            except:
                collection = client.create_collection(
                    name=name, embedding_function=self._get_embedding_function()
                )
            self._collections[name] = collection
        return self._collections[name]
    
    def add_documents(self, collection: str, texts: List[str], metadatas: List[Dict], ids: List[str]):
        if not texts:
            return
        collection_obj = self.get_collection(collection)
        batch_size = 100
        for i in range(0, len(texts), batch_size):
            collection_obj.add(
                documents=texts[i:i+batch_size],
                metadatas=metadatas[i:i+batch_size],
                ids=ids[i:i+batch_size]
            )
        print(f"Added {len(texts)} documents to '{collection}'")
    
    def search(self, collection: str, query: str, top_k: int = 10) -> List[Dict]:
        collection_obj = self.get_collection(collection)
        results = collection_obj.query(query_texts=[query], n_results=top_k)
        documents = []
        if results and results.get('documents') and results['documents'][0]:
            for i, doc in enumerate(results['documents'][0]):
                metadata = results['metadatas'][0][i] if results.get('metadatas') else {}
                doc_id = results['ids'][0][i] if results.get('ids') else str(i)
                distance = results['distances'][0][i] if results.get('distances') else 0
                score = 1 / (1 + distance)
                documents.append({
                    "id": doc_id, "text": doc, "metadata": metadata,
                    "score": score,
                })
        # 规范化：确保统一 schema（同时设置 data 用于过渡期兼容）
        from app.schema.metadata import normalize_chunks
        return normalize_chunks(documents)
    
    def get_all_documents(self, collection: str) -> List[Dict]:
        collection_obj = self.get_collection(collection)
        try:
            results = collection_obj.get()
            documents = []
            if results and results.get('ids'):
                for i, doc_id in enumerate(results['ids']):
                    doc = {
                        "id": doc_id,
                        "text": results['documents'][i] if results.get('documents') else "",
                        "metadata": results['metadatas'][i] if results.get('metadatas') else {}
                    }
                    documents.append(doc)
            return documents
        except Exception as e:
            print(f"Get all documents error: {e}")
            return []
    
    def get_count(self, collection: str) -> int:
        try:
            return self.get_collection(collection).count()
        except:
            return 0
    
    def get_by_ids(self, collection: str, document_ids: List[str]) -> List[Dict]:
        """按主键批量获取（兼容 MilvusStore 接口）"""
        if not document_ids:
            return []
        col = self.get_collection(collection)
        try:
            result = col.get(ids=document_ids)
            docs = []
            if result and result.get("ids"):
                for i, doc_id in enumerate(result["ids"]):
                    docs.append({
                        "id": doc_id,
                        "text": result["documents"][i] if result.get("documents") else "",
                        "metadata": result["metadatas"][i] if result.get("metadatas") else {},
                    })
            return docs
        except Exception:
            return []

    def get_raw_collection(self, name: str):
        """兼容 MilvusStore 接口"""
        return self.get_collection(name)

    def delete_collection(self, collection: str):
        if collection in self._collections:
            del self._collections[collection]
        try:
            self._get_client().delete_collection(collection)
            print(f"Deleted collection '{collection}'")
        except:
            pass

    def rebuild_from_excel(self, collection: str, excel_path: str, text_builder_func: Callable):
        if not Path(excel_path).exists():
            print(f"File not found: {excel_path}")
            return

        import pandas as pd
        import numpy as np

        # 1. 读取 Excel
        df = pd.read_excel(excel_path)

        # 2. 【核心修复】清洗元数据：Chroma 不支持 Timestamp
        for col in df.columns:
            # 如果是日期时间类型，转为字符串 YYYY-MM-DD
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].dt.strftime('%Y-%m-%d')
            # 将所有 NaN 或不可识别的空值统一转为 None 或空字符串，避免报错
            df[col] = df[col].replace({np.nan: None})

        data = df.to_dict('records')
        if not data:
            print("Warning: Excel file is empty.")
            return

        texts, metadatas, ids = [], [], []
        for i, record in enumerate(data):
            # 调用外部传入的构建函数生成文本
            text = text_builder_func(record)
            if text and len(text) > 5:  # 稍微降低门槛，确保数据能进去
                texts.append(text)
                # 再次确保 record 中的值没有非法对象（二次保险）
                clean_record = {k: (str(v) if v is not None else "") for k, v in record.items()}
                metadatas.append(clean_record)
                ids.append(f"{collection}_{i}")

        # 3. 重建
        self.delete_collection(collection)
        self.add_documents(collection, texts, metadatas, ids)
        print(f"Rebuilt '{collection}' with {len(texts)} documents")