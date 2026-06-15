"""
Parent Context Retriever (ParentContextRetriever)

检索后处理：
  retrieve child → attach parent → dedup by article → return

用法：
  expander = ParentContextRetriever(chroma_store)
  enriched = expander.expand(search_results)
"""
import re
from typing import List, Dict, Optional, Set

from config import settings


class ParentContextRetriever:
    """
    检索后上下文扩展器。

    对检索结果中 chunk_type="child" 的结果，
    从 ChromaDB 查询其 parent chunk，附加完整法条内容。
    """

    def __init__(self, chroma_store):
        self._store = chroma_store
        self._enabled = settings.legal_parent_context_enabled
        # 缓存 parent chunks，按 collection 分组
        self._parent_cache: Dict[str, Dict[str, Dict]] = {}

    @property
    def enabled(self) -> bool:
        return self._enabled

    def expand(self, results: List[Dict],
               collection: str = "regulations") -> List[Dict]:
        """
        对检索结果进行 parent context 扩展。

        流程:
        1. 收集 child results 的 parent_id
        2. 批量查询 parent chunks
        3. 附加 parent_content
        4. 按 article_id 去重

        返回: 扩展后的结果列表（含 parent_content 字段）
        """
        if not self._enabled or not results:
            return results

        # 分离 child 和 non-child 结果
        child_results = []
        non_child_results = []

        for r in results:
            meta = r.get("metadata", {}) or r.get("data", {})
            if meta.get("chunk_type") == "child":
                child_results.append(r)
            else:
                non_child_results.append(r)

        if not child_results:
            return results  # 没有 child，无需扩展

        # 批量查询 parents
        parent_ids = self._collect_parent_ids(child_results)
        parents = self._batch_get_parents(parent_ids, collection)

        # 附加 parent content 并去重
        enriched = list(non_child_results)
        seen_articles: Set[str] = set()

        # 记录已处理的 article（non-child 结果也算）
        for r in non_child_results:
            meta = r.get("metadata", {}) or r.get("data", {})
            article_id = str(meta.get("article_id", ""))
            if article_id:
                seen_articles.add(article_id)

        for child in child_results:
            meta = child.get("metadata", {}) or child.get("data", {})
            article_id = str(meta.get("article_id", ""))
            parent_id = meta.get("parent_id", "")

            # 去重：同一法条只保留最高分
            if article_id and article_id in seen_articles:
                continue
            if article_id:
                seen_articles.add(article_id)

            # 查询 parent chunk
            parent = parents.get(parent_id)
            if parent:
                child["parent_content"] = parent.get("text", "")
                child["parent_metadata"] = parent.get("metadata", {})
            else:
                child["parent_content"] = child.get("text", "")

            enriched.append(child)

        # 按分数重新排序
        enriched.sort(key=lambda x: x.get("score", 0), reverse=True)

        return enriched

    def _collect_parent_ids(self, child_results: List[Dict]) -> Set[str]:
        """收集所有需要查询的 parent_id"""
        ids = set()
        for r in child_results:
            data = r.get("data") or r.get("metadata", {})
            pid = data.get("parent_id", "")
            if pid:
                ids.add(pid)
        return ids

    def _batch_get_parents(self, parent_ids: Set[str],
                           collection: str) -> Dict[str, Dict]:
        """批量从 ChromaDB 查询 parent chunks"""
        if not parent_ids:
            return {}

        # 先从缓存读取
        if collection not in self._parent_cache:
            self._load_parent_cache(collection)

        cached = self._parent_cache.get(collection, {})
        missing = parent_ids - set(cached.keys())

        # 缓存缺失时，逐个查询
        if missing:
            self._query_missing_parents(missing, collection)

        return {
            pid: self._parent_cache.get(collection, {}).get(pid, {})
            for pid in parent_ids
        }

    def _load_parent_cache(self, collection: str):
        """预加载所有 parent chunks 到缓存"""
        try:
            all_docs = self._store.get_all_documents(collection)
        except Exception:
            self._parent_cache[collection] = {}
            return

        cache = {}
        for doc in all_docs:
            meta = doc.get("metadata", {})
            if meta.get("chunk_type") == "parent":
                cache[doc["id"]] = doc

        self._parent_cache[collection] = cache
        parent_count = len(cache)
        if parent_count > 0:
            print(f"[ParentContext] Cached {parent_count} parents from '{collection}'")

    def _query_missing_parents(self, missing_ids: Set[str], collection: str):
        """查询缓存中缺失的 parent chunks"""
        try:
            col = self._store.get_collection(collection)
            result = col.get(ids=list(missing_ids))
        except Exception:
            return

        if result and result.get("ids"):
            cache = self._parent_cache.setdefault(collection, {})
            for i, doc_id in enumerate(result["ids"]):
                cache[doc_id] = {
                    "id": doc_id,
                    "text": result["documents"][i] if result.get("documents") else "",
                    "metadata": result["metadatas"][i] if result.get("metadatas") else {},
                }

    def invalidate_cache(self, collection: str = None):
        """使缓存失效（知识库更新后调用）"""
        if collection:
            self._parent_cache.pop(collection, None)
        else:
            self._parent_cache.clear()
