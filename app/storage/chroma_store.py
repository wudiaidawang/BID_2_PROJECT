"""Chroma向量数据库客户端 — LangChain langchain_chroma.Chroma 封装"""

import chromadb
from typing import List, Dict, Callable
import pandas as pd
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document

from config import settings


class ChromaStore:
    """Chroma向量数据库客户端（单例模式），底层使用 langchain_chroma.Chroma"""

    _instance = None
    _client = None
    _collections = {}       # langchain_chroma.Chroma 实例缓存
    _raw_collections = {}   # 原生 chromadb Collection 缓存（供底层操作）

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
        """返回 LangChain HuggingFaceEmbeddings，供 Chroma 构造"""
        from app.core.embedding import EmbeddingService
        return EmbeddingService()._get_embeddings()

    def _get_raw_collection(self, name: str):
        """获取原生 chromadb Collection（用于底层操作）"""
        if name not in self._raw_collections:
            client = self._get_client()
            try:
                collection = client.get_collection(name)
            except Exception:
                collection = client.create_collection(
                    name=name,
                    embedding_function=chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction(
                        model_name=settings.embedding_model
                    )
                )
            self._raw_collections[name] = collection
        return self._raw_collections[name]

    def get_raw_collection(self, name: str):
        """获取原生 chromadb Collection（供底层操作如 get_all, count, get-by-id）"""
        return self._get_raw_collection(name)

    def get_collection(self, name: str) -> Chroma:
        """获取 langchain_chroma.Chroma 实例"""
        if name not in self._collections:
            self._collections[name] = Chroma(
                collection_name=name,
                embedding_function=self._get_embedding_function(),
                persist_directory=settings.chroma_persist_dir,
            )
        return self._collections[name]

    def add_documents(self, collection: str, texts: List[str],
                      metadatas: List[Dict], ids: List[str]):
        """批量写入文档"""
        if not texts:
            return
        docs = [
            Document(page_content=text, metadata=meta, id=doc_id)
            for text, meta, doc_id in zip(texts, metadatas, ids)
        ]
        vectorstore = self.get_collection(collection)
        # Chroma.add_documents 支持批量，一次传入所有 docs
        vectorstore.add_documents(docs)
        print(f"Added {len(texts)} documents to '{collection}'")

    def search(self, collection: str, query: str, top_k: int = 10) -> List[Dict]:
        """向量检索，返回统一格式"""
        vectorstore = self.get_collection(collection)
        results = vectorstore.similarity_search_with_score(query, k=top_k)

        documents = []
        for doc, score in results:
            md = doc.metadata or {}
            documents.append({
                "id": md.get("id", doc.id or ""),
                "text": doc.page_content,
                "metadata": md,
                "score": score,
            })
        from app.schema.metadata import normalize_chunks
        return normalize_chunks(documents)

    def get_all_documents(self, collection: str) -> List[Dict]:
        """获取集合全部文档"""
        raw = self._get_raw_collection(collection)
        try:
            results = raw.get()
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
            return self._get_raw_collection(collection).count()
        except Exception:
            return 0

    def delete_collection(self, collection: str):
        if collection in self._collections:
            del self._collections[collection]
        if collection in self._raw_collections:
            del self._raw_collections[collection]
        try:
            self._get_client().delete_collection(collection)
            print(f"Deleted collection '{collection}'")
        except Exception:
            pass

    def rebuild_from_excel(self, collection: str, excel_path: str,
                           text_builder_func: Callable):
        if not Path(excel_path).exists():
            print(f"File not found: {excel_path}")
            return

        import pandas as pd
        import numpy as np

        df = pd.read_excel(excel_path)

        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].dt.strftime('%Y-%m-%d')
            df[col] = df[col].replace({np.nan: None})

        data = df.to_dict('records')
        if not data:
            print("Warning: Excel file is empty.")
            return

        texts, metadatas, ids = [], [], []
        for i, record in enumerate(data):
            text = text_builder_func(record)
            if text and len(text) > 5:
                texts.append(text)
                clean_record = {k: (str(v) if v is not None else "") for k, v in record.items()}
                metadatas.append(clean_record)
                ids.append(f"{collection}_{i}")

        self.delete_collection(collection)
        self.add_documents(collection, texts, metadatas, ids)
        print(f"Rebuilt '{collection}' with {len(texts)} documents")
