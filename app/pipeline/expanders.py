"""
上下文扩展器 —— ParentContextExpander (法律) + NoopExpander (通用)

法律路径: child chunk → 查询 parent → 附加 parent_content → 按 article_id 去重
通用路径: 直通，不做任何处理
"""

from typing import List, Dict, Set

from app.storage import get_vector_store
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

    def __init__(self, store=None):
        self._store = store or get_vector_store()
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
            if str(meta.get("chunk_type", "")).endswith("_child"):
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

            # 即使是 article_id 已被 parent 覆盖，child 也保留自身 ID 参与 rerank
            if article_id and article_id in seen_articles:
                parent = parents.get(parent_id)
                if parent:
                    child["parent_content"] = parent.get("text", "")
                enriched.append(child)
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

        cache = self._parent_cache.setdefault(collection, {})
        missing = parent_ids - set(cache.keys())

        if missing:
            self._query_missing(missing, collection)

        return {pid: cache.get(pid, {}) for pid in parent_ids}

    def _query_missing(self, missing_ids: Set[str], collection: str):
        try:
            docs = self._store.get_by_ids(collection, list(missing_ids))
        except Exception:
            return

        if docs:
            cache = self._parent_cache.setdefault(collection, {})
            for doc in docs:
                cache[doc["id"]] = doc

    def invalidate_cache(self, collection: str = None):
        if collection:
            self._parent_cache.pop(collection, None)
        else:
            self._parent_cache.clear()
