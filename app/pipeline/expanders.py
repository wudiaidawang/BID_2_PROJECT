"""
上下文扩展器 —— ParentContextExpander (法律) + NoopExpander (通用)

法律路径: child chunk → 查询 parent → 附加 parent_content → 按 article_id 去重
通用路径: 直通，不做任何处理
"""

from typing import List, Dict, Set

from app.storage.chroma_store import ChromaStore
from app.schema.metadata import normalize_chunk
from config import settings


class NoopExpander:
    """空扩展器 —— 通用检索路径，不做 parent 扩展"""

    @property
    def enabled(self) -> bool:
        return False

    def expand(self, results: List[Dict], collection: str = "") -> List[Dict]:
        return results


class ParentContextExpander:
    """
    Parent Context 扩展器 —— 法律检索路径专用。

    对检索结果中 chunk_type="child" 的结果，
    从 ChromaDB 查询其 parent chunk，附加完整法条内容 (parent_content)，
    按 article_id 去重。
    """

    def __init__(self, chroma_store: ChromaStore = None):
        self._store = chroma_store or ChromaStore()
        self._enabled = settings.legal_parent_context_enabled
        self._parent_cache: Dict[str, Dict[str, Dict]] = {}

    @property
    def enabled(self) -> bool:
        return self._enabled

    def expand(self, results: List[Dict],
               collection: str = "regulations") -> List[Dict]:
        if not self._enabled or not results:
            return results

        # 分离 child 和 non-child
        child_results = []
        non_child_results = []
        for r in results:
            meta = r.get("metadata") or r.get("data", {})
            if meta.get("chunk_type") == "child":
                child_results.append(r)
            else:
                non_child_results.append(r)

        if not child_results:
            return results

        # 批量查询 parents
        parent_ids = self._collect_parent_ids(child_results)
        parents = self._batch_get_parents(parent_ids, collection)

        # 附加 parent_content 并去重
        enriched = list(non_child_results)
        seen_articles: Set[str] = set()

        for r in non_child_results:
            meta = r.get("metadata") or r.get("data", {})
            aid = str(meta.get("article_id", ""))
            if aid:
                seen_articles.add(aid)

        for child in child_results:
            meta = child.get("metadata") or child.get("data", {})
            article_id = str(meta.get("article_id", ""))
            parent_id = meta.get("parent_id", "")

            if article_id and article_id in seen_articles:
                continue
            if article_id:
                seen_articles.add(article_id)

            parent = parents.get(parent_id)
            if parent:
                child["parent_content"] = parent.get("text", "")
                child["parent_metadata"] = parent.get("metadata", {})
            else:
                child["parent_content"] = child.get("text", "")

            enriched.append(child)

        enriched.sort(key=lambda x: x.get("score", 0), reverse=True)
        return enriched

    def _collect_parent_ids(self, child_results: List[Dict]) -> Set[str]:
        ids = set()
        for r in child_results:
            meta = r.get("metadata") or r.get("data", {})
            pid = meta.get("parent_id", "")
            if pid:
                ids.add(pid)
        return ids

    def _batch_get_parents(self, parent_ids: Set[str],
                           collection: str) -> Dict[str, Dict]:
        if not parent_ids:
            return {}

        if collection not in self._parent_cache:
            self._load_parent_cache(collection)

        cached = self._parent_cache.get(collection, {})
        missing = parent_ids - set(cached.keys())

        if missing:
            self._query_missing(missing, collection)

        cache = self._parent_cache.get(collection, {})
        return {pid: cache.get(pid, {}) for pid in parent_ids}

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
        if cache:
            print(f"[ParentExpander] Cached {len(cache)} parents from '{collection}'")

    def _query_missing(self, missing_ids: Set[str], collection: str):
        try:
            col = self._store.get_raw_collection(collection)
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
        if collection:
            self._parent_cache.pop(collection, None)
        else:
            self._parent_cache.clear()
