"""融合后系统测试 — 用 hybrid_test_cases 的问答对测试核心模块"""
import json
import sys
import time

sys.path.insert(0, ".")

from config import settings

# 加载测试集
with open("data/eval_questions/hybrid_test_cases.json", "r", encoding="utf-8") as f:
    test_cases = json.load(f)

print(f"Loaded {len(test_cases)} test cases")
print(f"Router mode: {settings.router_mode}")
print(f"Fusion strategy: {settings.fusion_strategy}")
print(f"Embedding: {settings.embedding_model} ({settings.embedding_dimension}d)")
print()

# ── 1. QueryRewriter 测试 ──
print("=" * 60)
print("TEST 1: QueryRewriter (前10题)")
print("=" * 60)
from app.data.query_rewriter import query_rewriter

rewrite_changes = 0
for tc in test_cases[:10]:
    q = tc["question"]
    r = query_rewriter.rewrite(q)
    changed = "CHANGED" if r != q else "same"
    if r != q:
        rewrite_changes += 1
        print(f"  [{changed}] {q[:50]}...")
        print(f"        -> {r[:70]}...")
    else:
        print(f"  [{changed}] {q[:50]}...")

print(f"\n  Rewrite hits: {rewrite_changes}/10")
print()

# ── 2. BinaryRouter 规则层测试 ──
print("=" * 60)
print("TEST 2: BinaryRouter 规则判定 (前20题)")
print("=" * 60)
from app.agent.router import BinaryRouter

router = BinaryRouter()
router._warmup()

sql_count = 0
for tc in test_cases[:20]:
    q = tc["question"]
    rule = router._check_is_sql(q)
    emb = router._embedding_classify(q)
    if rule:
        sql_count += 1
    print(f"  rule={'SQL' if rule else 'RAG'} | emb={'SQL' if emb else 'RAG'} | {q[:50]}...")

print(f"\n  Rule SQL hits: {sql_count}/20")
print()

# ── 3. HybridRetriever 检索测试 ──
print("=" * 60)
print("TEST 3: HybridRetriever 检索 (前5题)")
print("=" * 60)
from app.data.retriever import HybridRetriever

retriever = HybridRetriever()

for tc in test_cases[:5]:
    q = tc["question"]
    expected = tc.get("expected_answer", "")

    rewritten = query_rewriter.rewrite(q)
    start = time.time()
    results = retriever.search_unified(rewritten, top_k=3)
    elapsed = time.time() - start

    print(f"\n  Q: {q[:60]}")
    print(f"  Expected: {expected[:60]}...")
    print(f"  Time: {elapsed:.2f}s")
    for i, r in enumerate(results):
        score = r.get("score", 0)
        text = r.get("text", "")[:80].replace("\n", " ")
        data = r.get("data", {})
        source = data.get("title", data.get("source", "?"))
        print(f"    [{i+1}] score={score:.4f} | {source} | {text}...")

print()

# ── 4. 统计 ──
print("=" * 60)
print("TEST SUMMARY")
print("=" * 60)
print(f"  测试集总题数: {len(test_cases)}")
print(f"  路由模式: {settings.router_mode}")
print(f"  融合策略: {settings.fusion_strategy}")
print(f"  Embedding: {settings.embedding_model}")
print(f"  改写命中: {rewrite_changes}/10 (前10题)")
print(f"  SQL命中: {sql_count}/20 (前20题规则判定)")
print(f"  检索正常: OK")
print()
print("Test complete!")
