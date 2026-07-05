"""
上下文扩展器 —— ParentContextExpander (法律) + NoopExpander (通用)

法律路径: child chunk → 查询 parent → 相邻法条上下文扩展 → 按 article_id 去重
通用路径: 直通，不做任何处理
"""

from typing import List, Dict, Set, Tuple

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
        self._article_index: Dict[Tuple[str, str], Dict[int, Dict]] = {}
        self._index_built = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def expand(self, results: List[Dict],
               collection: str = "regulations") -> List[Dict]:
        if not self._enabled or not results:
            return results

        # V4.2: 上移一级 — 章上下文为主要路径，旧 child→parent 为兼容路径
        enriched: List[Dict] = []
        seen_articles: Set[str] = set()
        child_fallbacks: List[Dict] = []

        for r in results:
            meta = r.get("metadata") or r.get("data", {})
            article_id = str(meta.get("article_id", ""))
            chapter_context = meta.get("chapter_context", "")

            if article_id and article_id in seen_articles:
                continue

            if chapter_context:
                # 新路径: 章上下文直接注入
                r["parent_content"] = chapter_context
                if article_id:
                    seen_articles.add(article_id)
                enriched.append(r)
            elif str(meta.get("chunk_type", "")).endswith("_child"):
                # 兼容路径: 旧 child chunk → 查找 parent
                child_fallbacks.append(r)
            else:
                if article_id:
                    seen_articles.add(article_id)
                enriched.append(r)

        # 处理旧格式 child chunks —— 相邻法条上下文扩展
        if child_fallbacks:
            parent_ids = self._collect_parent_ids(child_fallbacks)
            parents = self._batch_get_parents(parent_ids, collection)
            self._ensure_article_index(collection)

            for child in child_fallbacks:
                meta = child.get("metadata") or child.get("data", {})
                article_id = str(meta.get("article_id", ""))
                parent_id = meta.get("parent_id", "")

                if article_id and article_id in seen_articles:
                    continue
                if article_id:
                    seen_articles.add(article_id)

                parent = parents.get(parent_id)
                if parent:
                    law_name = parent.get("law_name", "") or meta.get("law_name", "")
                    chapter = (parent.get("metadata", {}).get("chapter", "")
                               or parent.get("chapter", "")
                               or meta.get("chapter", ""))
                    current_text = parent.get("text", "")
                    child["parent_content"] = self._get_adjacent_context(
                        law_name, chapter, article_id, current_text
                    )
                else:
                    child["parent_content"] = child.get("text", "")
                enriched.append(child)

        enriched.sort(key=lambda x: x.get("score", 0), reverse=True)
        return enriched

    def _ensure_article_index(self, collection: str):
        """构建法条邻接索引 —— 按 (law_name, chapter) 分组，article_id 排序。

        仅包含 parent chunk（parent_id 为空），排除 child/sliding。
        索引结构: {(law_name, chapter): {article_id_int: doc}}
        """
        if self._index_built:
            return
        all_docs = self._store.get_all_documents(collection)
        index: Dict[Tuple[str, str], Dict[int, Dict]] = {}

        for doc in all_docs:
            meta = doc.get("metadata", {})
            parent_id = meta.get("parent_id", doc.get("parent_id", ""))
            if parent_id:
                continue
            law_name = meta.get("law_name", doc.get("law_name", ""))
            chapter = meta.get("chapter", doc.get("chapter", ""))
            article_id_str = meta.get("article_id", doc.get("article_id", ""))

            if not law_name or not article_id_str:
                continue
            try:
                aid = int(article_id_str)
            except ValueError:
                continue

            key = (law_name, chapter)
            if key not in index:
                index[key] = {}
            index[key][aid] = doc

        self._article_index = index
        self._index_built = True

    def _get_adjacent_context(self, law_name: str, chapter: str,
                              article_id: str, current_text: str) -> str:
        """构建相邻法条上下文，格式:

        【上一条】第X条
        <前一条全文>

        ===== 当前命中 =====
        【当前条文】第Y条
        <当前全文>

        【下一条】第Z条
        <下一条全文>

        约束: 同法规 + 同章节，跨法规跨章节不拼接。
        """
        try:
            aid = int(article_id)
        except ValueError:
            return current_text

        group = self._article_index.get((law_name, chapter), {})
        if not group:
            return current_text

        sorted_ids = sorted(group.keys())
        try:
            pos = sorted_ids.index(aid)
        except ValueError:
            return current_text

        prev_id = sorted_ids[pos - 1] if pos > 0 else None
        next_id = sorted_ids[pos + 1] if pos < len(sorted_ids) - 1 else None

        # 当前条文标签（优先用 parent 原本的中文条号）
        current_label = f"第{article_id}条"
        if aid in group:
            current_article = group[aid].get("metadata", {}).get("article", "")
            if current_article:
                current_label = current_article

        parts: List[str] = []

        if prev_id is not None:
            prev_doc = group[prev_id]
            prev_article = prev_doc.get("metadata", {}).get("article", f"第{prev_id}条")
            parts.append(f"【上一条】{prev_article}\n{prev_doc.get('text', '')}")

        parts.append(f"===== 当前命中 =====\n【当前条文】{current_label}\n{current_text}")

        if next_id is not None:
            next_doc = group[next_id]
            next_article = next_doc.get("metadata", {}).get("article", f"第{next_id}条")
            parts.append(f"【下一条】{next_article}\n{next_doc.get('text', '')}")

        return "\n\n".join(parts)

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
        self._article_index.clear()
        self._index_built = False
