"""
SearchPipeline — LCEL Runnable 链编排

5 阶段管线: preprocess → retrieve → merge → expand → rerank
每阶段使用 RunnableLambda + with_fallbacks() 实现断路器模式。
"""

import time
from typing import List, Dict, Callable

from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_core.runnables.base import Runnable

from app.pipeline.preprocessor import QueryPreprocessor
from app.pipeline.retrievers import VectorRetriever, BM25Retriever
from app.pipeline.fusion import RRFFusion, WeightedFusion
from app.pipeline.expanders import ParentContextExpander, NoopExpander
from app.pipeline.rerankers import BgeReranker
from app.storage.chroma_store import ChromaStore
from config import settings


class StageTracer:
    """管线阶段追踪"""

    def __init__(self):
        self.enabled = settings.pipeline_tracing_enabled
        self.show_counts = settings.pipeline_tracing_show_counts
        self.show_timing = settings.pipeline_tracing_show_timing

    def _count(self, data) -> int:
        if isinstance(data, list):
            return len(data)
        if isinstance(data, str):
            return len(data)
        return 1

    def start(self, name: str, data=None):
        if not self.enabled:
            return None
        count_str = ""
        if self.show_counts and data is not None:
            if isinstance(data, str):
                count_str = f" ({data})"
            elif isinstance(data, list):
                count_str = f" (in: {len(data)})"
        print(f"[Pipeline] >> Stage: {name}{count_str}")
        return time.time() if self.show_timing else None

    def done(self, name: str, data=None, start_ts=None):
        if not self.enabled:
            return
        parts = []
        if self.show_counts and data is not None:
            if isinstance(data, list):
                parts.append(f"out: {len(data)}")
        if self.show_timing and start_ts is not None:
            elapsed = int((time.time() - start_ts) * 1000)
            parts.append(f"{elapsed}ms")
        detail = f" ({', '.join(parts)})" if parts else ""
        print(f"[Pipeline] OK Stage: {name} done{detail}")

    def skip(self, name: str, reason: str = "disabled"):
        if self.enabled:
            print(f"[Pipeline] -- Stage: {name} SKIPPED ({reason})")

    def fail(self, name: str, error: str, breaker_action: str):
        if self.enabled:
            print(f"[Pipeline] !! Stage: {name} FAILED: {error} -- circuit breaker: {breaker_action}")


class SearchPipeline:
    """检索管线编排器 — LCEL Runnable 链"""

    def __init__(self):
        self.tracer = StageTracer()

        self.preprocessor = QueryPreprocessor(
            enable_synonym_expansion=settings.query_expansion_enabled
        )

        self._store = ChromaStore()
        self.vector = VectorRetriever(self._store)
        self.bm25 = BM25Retriever()

        self.rrf = RRFFusion()
        self.weighted = WeightedFusion(self.vector, self.bm25)

        self.parent_expander = ParentContextExpander(self._store)
        self.noop_expander = NoopExpander()

        self.reranker = BgeReranker()

        self._all_docs_cache: Dict[str, List[Dict]] = {}

        # 构建 LCEL 链
        self._unified_chain = self._build_unified_chain()
        self._single_chain = self._build_single_chain()

        print(f"[SearchPipeline] LCEL chains ready "
              f"(tracing={'ON' if self.tracer.enabled else 'OFF'})")

    # ═════════════════════════════════════════════════════════════
    # LCEL Chain 构建
    # ═════════════════════════════════════════════════════════════

    def _make_stage(self, name: str, fn: Callable,
                    breaker: str = "fail_open") -> Runnable:
        """创建带断路器的阶段 Runnable"""
        cfg = settings.pipeline_stage_config(name)
        if not cfg["enabled"]:
            return RunnableLambda(lambda x: x)

        def wrapped(input_data):
            self.tracer.start(name, input_data)
            try:
                result = fn(input_data)
                self.tracer.done(name, result)
                return result
            except Exception as e:
                self.tracer.fail(name, str(e)[:120], breaker)
                if breaker == "fail_open":
                    return input_data
                raise

        return RunnableLambda(wrapped)

    def _build_unified_chain(self) -> Runnable:
        """跨库检索链: preprocess → retrieve → merge → expand → rerank"""
        def preprocess_fn(state: Dict) -> Dict:
            query = state["query"]
            normalized = self.preprocessor.process(query)
            return {**state, "normalized": normalized}

        def retrieve_fn(state: Dict) -> Dict:
            normalized = state["normalized"]
            query = state["query"]
            top_k = state.get("top_k", 5)
            all_candidates = []
            for collection in ["regulations", "bids"]:
                try:
                    col_results = self._retrieve_and_fuse(
                        normalized, query, collection, top_k * 3
                    )
                    all_candidates.extend(col_results)
                except Exception as e:
                    print(f"  [Pipeline] collection '{collection}' error: {e}")
                    continue
            if not all_candidates:
                raise RuntimeError("Both collections returned empty")
            return {**state, "candidates": all_candidates}

        def merge_fn(state: Dict) -> Dict:
            merged = self._merge_and_dedup(state["candidates"])
            return {**state, "merged": merged}

        def expand_fn(state: Dict) -> Dict:
            expanded = self.parent_expander.expand(
                state["merged"], "regulations"
            )
            return {**state, "expanded": expanded}

        def rerank_fn(state: Dict) -> List[Dict]:
            query = state["query"]
            top_k = state.get("top_k", 5)
            try:
                return self._do_rerank(query, state["expanded"], top_k)
            except Exception:
                return state["expanded"][:top_k]

        chain = (
            RunnableLambda(preprocess_fn)
            | self._make_stage("retrieve", retrieve_fn, "fail_close")
            | self._make_stage("merge", merge_fn, "fail_open")
            | self._make_stage("expand", expand_fn, "fail_open")
            | RunnableLambda(rerank_fn)
        )
        return chain

    def _build_single_chain(self) -> Runnable:
        """单库检索链: preprocess → retrieve → (expand) → rerank"""
        def preprocess_fn(state: Dict) -> Dict:
            query = state["query"]
            normalized = self.preprocessor.process(query)
            return {**state, "normalized": normalized}

        def retrieve_fn(state: Dict) -> Dict:
            normalized = state["normalized"]
            query = state["query"]
            collection = state.get("collection", "regulations")
            top_k = state.get("top_k", 5)
            fused = self._retrieve_and_fuse(
                normalized, query, collection, top_k * 3
            )
            return {**state, "candidates": fused, "collection": collection}

        def maybe_expand_fn(state: Dict) -> Dict:
            collection = state.get("collection", "")
            if collection == "regulations":
                expanded = self.parent_expander.expand(
                    state["candidates"], collection
                )
                return {**state, "expanded": expanded}
            return {**state, "expanded": state["candidates"]}

        def rerank_fn(state: Dict) -> List[Dict]:
            query = state["query"]
            top_k = state.get("top_k", 5)
            try:
                return self._do_rerank(query, state["expanded"], top_k)
            except Exception:
                return state["expanded"][:top_k]

        chain = (
            RunnableLambda(preprocess_fn)
            | self._make_stage("retrieve", retrieve_fn, "fail_close")
            | self._make_stage("expand", maybe_expand_fn, "fail_open")
            | RunnableLambda(rerank_fn)
        )
        return chain

    # ═════════════════════════════════════════════════════════════
    # 公开接口
    # ═════════════════════════════════════════════════════════════

    def search_unified(self, query: str, top_k: int = 5) -> List[Dict]:
        """统一跨库检索 — LCEL 链执行"""
        if not query:
            return []
        state = {"query": query, "top_k": top_k}
        return self._unified_chain.invoke(state)

    def search(self, query: str, collection: str, top_k: int = 5) -> List[Dict]:
        """单库检索 — LCEL 链执行"""
        if not query:
            return []
        state = {"query": query, "collection": collection, "top_k": top_k}
        return self._single_chain.invoke(state)

    # ═════════════════════════════════════════════════════════════
    # 内部方法
    # ═════════════════════════════════════════════════════════════

    def _retrieve_and_fuse(self, normalized: str, original: str,
                           collection: str, top_k: int) -> List[Dict]:
        """单库 vector + BM25 召回 + 融合"""
        all_docs = self._get_all_docs(collection)
        if not all_docs:
            return self.vector.search(normalized, collection, top_k)

        vec_results = self.vector.search(normalized, collection,
                                         settings.vector_recall)
        bm25_results = self.bm25.search(normalized, collection, all_docs,
                                        settings.bm25_recall)

        fusion_strategy = settings.fusion_strategy
        if fusion_strategy in ("weighted", "smart"):
            fused =  self.weighted.merge(original, collection,
                                          vec_results, bm25_results, top_k)
        else:
            fused = self.rrf.merge(vec_results, bm25_results,
                                   k=settings.rrf_k)[:top_k]

        return fused if fused else (vec_results[:top_k])

    def _merge_and_dedup(self, candidates: List[Dict]) -> List[Dict]:
        """跨库合并 + 按 id 去重"""
        candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
        seen = set()
        deduped = []
        for c in candidates:
            cid = c.get("id") or str(hash(c.get("text", "")))
            if cid not in seen:
                seen.add(cid)
                deduped.append(c)
        return deduped

    def _do_rerank(self, query: str, candidates: List[Dict],
                   top_k: int) -> List[Dict]:
        """BGE Reranker 精排"""
        if len(candidates) <= 1:
            return candidates[:top_k]

        model = self.reranker._get_model()
        if model is None:
            return candidates[:top_k]

        documents = []
        for d in candidates[:settings.reranker_candidate_pool]:
            doc_text = d.get("parent_content") or d.get("text", "")
            documents.append(doc_text[:settings.reranker_max_input_length])

        indices = self.reranker.rerank(query, documents, top_k)
        return [candidates[i] for i in indices if i < len(candidates)]

    def _get_all_docs(self, collection: str) -> List[Dict]:
        if collection not in self._all_docs_cache:
            self._all_docs_cache[collection] = self._store.get_all_documents(collection)
        return self._all_docs_cache[collection]

    def get_stats(self) -> dict:
        return {
            "bids": self._store.get_count("bids"),
            "regulations": self._store.get_count("regulations"),
        }

    def invalidate_cache(self):
        self._all_docs_cache.clear()
        self.parent_expander.invalidate_cache()
