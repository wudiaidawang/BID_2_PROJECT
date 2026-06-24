"""
SearchPipeline — 检索管线编排器

管线阶段: preprocess → retrieve → fuse → merge → expand → rerank
每阶段有独立断路器（circuit breaker），阶段失败时可跳过而非崩溃。

断路器模式:
  "fail_close" — 失败立即抛出异常（核心路径：preprocess, retrieve）
  "fail_open"  — 失败时跳过该阶段，输入直通输出（非核心：fusion, expand, rerank）
"""

import time
from typing import List, Dict, Optional, Callable

from app.pipeline.preprocessor import QueryPreprocessor
from app.pipeline.retrievers import VectorRetriever, BM25Retriever, ServerBM25Retriever
from app.pipeline.fusion import RRFFusion, WeightedFusion
from app.pipeline.expanders import ParentContextExpander, NoopExpander
from app.pipeline.rerankers import BgeReranker
from app.storage import get_vector_store
from config import settings


# ═══════════════════════════════════════════════════════════════════
# 阶段追踪器
# ═══════════════════════════════════════════════════════════════════

class StageTracer:
    """管线阶段追踪 —— 打印每阶段输入/输出/耗时"""

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
                count_str = f" ({data})"  # 字符串 hint 直接展示
            elif isinstance(data, list):
                count_str = f" (in: {len(data)})"
        header = f"[Pipeline] >> Stage: {name}{count_str}"
        print(header)
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


# ═══════════════════════════════════════════════════════════════════
# 阶段执行器（断路器）
# ═══════════════════════════════════════════════════════════════════

class StageRunner:
    """带断路器的阶段执行器"""

    def __init__(self, stage_name: str, tracer: StageTracer):
        self.name = stage_name
        self.tracer = tracer
        cfg = settings.pipeline_stage_config(stage_name)
        self.enabled = cfg["enabled"]
        self.breaker = cfg["circuit_breaker"]  # "fail_close" | "fail_open"

    def run(self, fn: Callable, input_data, **kwargs):
        """
        执行阶段。

        - enabled=False → 跳过，输入直通
        - 执行成功 → 返回结果
        - 执行失败 + fail_open → 跳过，输入直通（断路器断开）
        - 执行失败 + fail_close → 异常上抛
        """
        if not self.enabled:
            self.tracer.skip(self.name)
            return input_data

        start_ts = self.tracer.start(self.name, input_data)
        try:
            result = fn(input_data, **kwargs) if kwargs else fn(input_data)
            self.tracer.done(self.name, result, start_ts)
            return result
        except Exception as e:
            self.tracer.fail(self.name, str(e)[:120], self.breaker)
            if self.breaker == "fail_open":
                return input_data  # 直通
            raise


# ═══════════════════════════════════════════════════════════════════
# SearchPipeline 编排器
# ═══════════════════════════════════════════════════════════════════

class SearchPipeline:
    """检索管线编排器 —— 每阶段独立断路器 + 全程可观测"""

    def __init__(self):
        self.tracer = StageTracer()

        # ── 阶段1: 预处理器 ──
        self.preprocessor = QueryPreprocessor(
            enable_synonym_expansion=settings.query_expansion_enabled
        )

        # ── 阶段2: 检索器 ──
        self._store = get_vector_store()
        self.vector = VectorRetriever(self._store)
        self.bm25 = ServerBM25Retriever(self._store)

        # ── 阶段3: 融合策略 ──
        self.rrf = RRFFusion()
        self.weighted = WeightedFusion(self.vector, self.bm25)

        # ── 阶段4: 上下文扩展 ──
        self.parent_expander = ParentContextExpander(self._store)
        self.noop_expander = NoopExpander()

        # ── 阶段5: 精排器 ──
        self.reranker = BgeReranker()

        # ── 缓存 ──
        self._all_docs_cache: Dict[str, List[Dict]] = {}

        print(f"[SearchPipeline] 6-stage pipeline ready "
              f"(tracing={'ON' if self.tracer.enabled else 'OFF'})")

    # ═════════════════════════════════════════════════════════════
    # 公开接口
    # ═════════════════════════════════════════════════════════════

    def search_unified(self, query: str, top_k: int = 5) -> List[Dict]:
        """统一跨库检索 —— regulations + bids + policy 三库"""
        if not query:
            return []

        # ── Stage 1: Preprocess ──
        normalized = StageRunner("preprocess", self.tracer).run(
            lambda q: self.preprocessor.process(q), query
        )

        # ── Stage 2: Retrieve + Fuse per collection ──
        def _search_both(normalized_q):
            all_candidates = []
            for collection in [c["name"] for c in settings.collections]:
                try:
                    col_results = self._retrieve_and_fuse(
                        normalized_q, query, collection, top_k * 3
                    )
                    all_candidates.extend(col_results)
                except Exception as e:
                    print(f"  [Pipeline] collection '{collection}' error: {e}")
                    continue
            if not all_candidates:
                raise RuntimeError("All collections returned empty")
            return all_candidates

        all_candidates = StageRunner("retrieve", self.tracer).run(
            _search_both, normalized
        )

        if not all_candidates:
            return []

        # ── Stage 3: Merge cross-collection ──
        merged = StageRunner("merge", self.tracer).run(
            self._merge_and_dedup, all_candidates
        )

        # ── Stage 4: Expand (parent context) ──
        expanded = StageRunner("expand", self.tracer).run(
            lambda m: self.parent_expander.expand(m, "policy"), merged
        )

        # ── Stage 5: Rerank ──
        reranked = StageRunner("rerank", self.tracer).run(
            lambda e: self._do_rerank(query, e, top_k), expanded
        )

        return reranked

    def search(self, query: str, collection: str, top_k: int = 5) -> List[Dict]:
        """单库检索 —— 供 Agent 工具调用"""
        if not query:
            return []

        # ── Stage 1: Preprocess ──
        normalized = StageRunner("preprocess", self.tracer).run(
            lambda q: self.preprocessor.process(q), query
        )

        # ── Stage 2: Retrieve + Fuse ──
        def _search_single(normalized_q):
            return self._retrieve_and_fuse(normalized_q, query, collection, top_k * 3)

        fused = StageRunner("retrieve", self.tracer).run(
            _search_single, normalized
        )

        # ── Stage 3: Expand (only if regulations) ──
        if collection == "regulations":
            fused = StageRunner("expand", self.tracer).run(
                lambda f: self.parent_expander.expand(f, collection), fused
            )

        # ── Stage 4: Rerank ──
        return StageRunner("rerank", self.tracer).run(
            lambda f: self._do_rerank(query, f, top_k), fused
        )

    # ═════════════════════════════════════════════════════════════
    # 内部方法
    # ═════════════════════════════════════════════════════════════

    def _retrieve_and_fuse(self, normalized: str, original: str,
                           collection: str, top_k: int) -> List[Dict]:
        """对单个 collection 执行 vector + BM25 召回 + 融合"""
        # Vector 召回
        vec_results = self.vector.search(normalized, collection,
                                         settings.vector_recall)

        # BM25 召回 —— 走服务端 Milvus sparse_vector
        bm25_results = self.bm25.search(normalized, collection,
                                        settings.bm25_recall)

        # 融合（带断路器）—— 输入 = vec + bm25 候选数
        fusion_input_hint = f"vec:{len(vec_results)} + bm25:{len(bm25_results)}"
        fusion_strategy = settings.fusion_strategy
        if fusion_strategy in ("weighted", "smart"):
            fused = StageRunner("fusion", self.tracer).run(
                lambda _: self.weighted.merge(original, collection,
                                              vec_results, bm25_results, top_k),
                fusion_input_hint
            )
        else:
            fused = StageRunner("fusion", self.tracer).run(
                lambda _: self.rrf.merge(vec_results, bm25_results, k=settings.rrf_k)[:top_k],
                fusion_input_hint
            )

        # 标注 source_type（运行时字段，用于 reranker 权重提升）
        from app.schema.metadata import infer_source_type
        for r in fused:
            r["source_type"] = infer_source_type(collection, r)  # 传完整 chunk，兼容扁平/嵌套结构

        return fused if fused else (vec_results[:top_k])

    def _merge_and_dedup(self, candidates: List[Dict]) -> List[Dict]:
        """跨库合并 + 去重（按 id）"""
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
        """BGE Reranker 精排 —— 远程优先，零本地加载"""
        if len(candidates) <= 1:
            return candidates[:top_k]

        if not settings.reranker_enabled:
            return candidates[:top_k]

        documents = []
        for d in candidates[:settings.reranker_candidate_pool]:
            doc_text = d.get("parent_content") or d.get("retrieval_text", d.get("text", ""))
            documents.append(doc_text[:settings.reranker_max_input_length])

        indices = self.reranker.rerank(query, documents, top_k)
        reranked = [candidates[i] for i in indices if i < len(candidates)]

        # ── source_type 权重提升 (post-rerank score boost) ──
        if settings.source_type_boost_enabled:
            weights = settings.source_type_weights
            for r in reranked:
                boost = weights.get(r.get("source_type", ""), 1.0)
                if boost != 1.0:
                    r["score"] = r.get("score", 0.0) * boost
            reranked.sort(key=lambda x: x.get("score", 0), reverse=True)

        # ── 条款号精确匹配 boost ──
        query_article = self._extract_query_article_id(query)
        if query_article:
            ARTICLE_BOOST = 1.2
            for r in reranked:
                aid = str(r.get("metadata", {}).get("article_id", ""))
                if aid and aid == query_article:
                    r["score"] = r.get("score", 0.0) * ARTICLE_BOOST
            reranked.sort(key=lambda x: x.get("score", 0), reverse=True)

        return reranked[:top_k]

    def _extract_query_article_id(self, query: str) -> str:
        """从 query 中提取条款号（统一为阿拉伯数字），用于后处理 boost"""
        from app.utils.chinese_number import chinese_number_converter
        return chinese_number_converter.extract_article_number(query)

    def _get_all_docs(self, collection: str) -> List[Dict]:
        """获取 collection 全部文档（带缓存）"""
        if collection not in self._all_docs_cache:
            self._all_docs_cache[collection] = self._store.get_all_documents(collection)
        return self._all_docs_cache[collection]

    def get_stats(self) -> dict:
        stats = {}
        for c in settings.collections:
            stats[c["name"]] = self._store.get_count(c["name"])
        return stats

    def invalidate_cache(self):
        """清空缓存"""
        self._all_docs_cache.clear()
        self.parent_expander.invalidate_cache()
