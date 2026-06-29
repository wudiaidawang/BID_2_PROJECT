#!/usr/bin/env python
"""修复 V6 标注: 补全缺失 + 修正 LLM 拼写错误"""

import json
import re
import time
import sys
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent))
from openai import OpenAI
from config import settings

PROGRESS = Path(__file__).parent / "data" / "eval_questions" / "v6" / ".qa_gen_progress_v6.json"

# 类型映射: 修正 LLM 拼写错误
QTYPE_FIX = {
    "scene_judgment": "scenario_judgment",
    "scenario": "scenario_judgment",
    "condition": "condition_check",
    "compare": "comparison",
}
RDIFF_FIX = {
    "directonym": "synonym",
    "scene": "scenario",
}

VALID_QTYPES = {
    "scenario_judgment", "condition_check", "procedure",
    "responsibility", "definition", "comparison",
    "case_reasoning", "announcement_interpretation",
}
VALID_RDIFFS = {"direct", "synonym", "scenario", "cross_reference"}

CLASSIFY_PROMPT = """你是一名RAG Benchmark标注工程师。为每个QA标注question_type和retrieval_difficulty。

question_type (8选1):
1. scenario_judgment — 给业务场景问后果/合规/处理
2. condition_check — 问前提条件/适用范围/触发门槛
3. procedure — 问操作流程/步骤/时间节点
4. responsibility — 问部门/角色职责
5. definition — 问概念/术语含义
6. comparison — 问两个概念/方式的区别
7. case_reasoning — 根据案例推理结论
8. announcement_interpretation — 对公告/新闻的解读

retrieval_difficulty (4选1):
- direct — 与原文仍有明显关键词重叠，BM25可命中
- synonym — 核心概念用了同义词/口语表达，需语义匹配
- scenario — 描述业务场景而非直接提法条，需理解场景对应关系
- cross_reference — 需关联多处信息才能定位

输出JSON数组: [{"id":"...", "question_type":"...", "retrieval_difficulty":"..."}]"""


def fix_existing(qas):
    """修正已有标注中的拼写错误"""
    fixed = 0
    for q in qas:
        qt = q.get("question_type", "")
        rd = q.get("retrieval_difficulty", "")
        if qt in QTYPE_FIX:
            q["question_type"] = QTYPE_FIX[qt]
            fixed += 1
        elif qt and qt not in VALID_QTYPES:
            q.pop("question_type", None)
            fixed += 1
        if rd in RDIFF_FIX:
            q["retrieval_difficulty"] = RDIFF_FIX[rd]
            fixed += 1
        elif rd and rd not in VALID_RDIFFS:
            q.pop("retrieval_difficulty", None)
            fixed += 1
    return fixed


def backfill_missing(qas):
    """用 LLM 补全缺失的标注"""
    need = [(i, q) for i, q in enumerate(qas)
            if "question_type" not in q or "retrieval_difficulty" not in q]
    if not need:
        return 0

    client = OpenAI(
        base_url=settings.llm_api_url.replace("/chat/completions", ""),
        api_key=settings.llm_api_key,
    )

    filled = 0
    BATCH = 25
    for bs in range(0, len(need), BATCH):
        batch = need[bs:bs + BATCH]
        items = [{
            "id": q["id"],
            "question": q["question"][:150],
            "answer": q.get("answer", "")[:100],
            "chunk_type": q.get("chunk_type", ""),
        } for _, q in batch]

        for attempt in range(3):
            try:
                resp = client.chat.completions.create(
                    model="GLM-4.1V-Thinking-FlashX",
                    messages=[
                        {"role": "system", "content": CLASSIFY_PROMPT},
                        {"role": "user", "content": json.dumps(items, ensure_ascii=False)},
                    ],
                    temperature=0.2, max_tokens=4096, timeout=300,
                    extra_body={"thinking": {"type": "enabled"}},
                )
                content = resp.choices[0].message.content or ""
                if not content:
                    content = getattr(resp.choices[0].message, "reasoning_content", "")

                # 提取 JSON
                md = re.search(r'```(?:json)?\s*\n?(.*?)```', content, re.DOTALL)
                if md:
                    content = md.group(1)
                m = re.search(r'\[.*\]', content, re.DOTALL)
                results = json.loads(m.group()) if m else json.loads(content)
                if isinstance(results, dict):
                    results = [results]

                result_map = {r["id"]: r for r in results}
                batch_filled = 0
                for idx, q in batch:
                    r = result_map.get(q["id"], {})
                    qt = r.get("question_type", "")
                    rd = r.get("retrieval_difficulty", "")
                    if qt and qt in VALID_QTYPES:
                        qas[idx]["question_type"] = qt
                        batch_filled += 1
                    if rd and rd in VALID_RDIFFS:
                        qas[idx]["retrieval_difficulty"] = rd
                        batch_filled += 1

                filled += batch_filled
                remaining = sum(1 for q in qas if "question_type" not in q)
                print(f"  批次 {bs // BATCH + 1}: +{batch_filled} (剩余 {remaining})")
                break
            except Exception as e:
                print(f"  批次 {bs // BATCH + 1} 失败: {str(e)[:120]}")
                if attempt < 2:
                    time.sleep(5)
        time.sleep(1.5)

    return filled


def main():
    print("=" * 60)
    print("V6 标注修复工具")
    print("=" * 60)

    # 加载
    with open(PROGRESS, "r", encoding="utf-8") as f:
        data = json.load(f)

    qas = data["generated_qas"]
    print(f"总 QA: {len(qas)}")

    # Step 1: 修正拼写错误
    fixed = fix_existing(qas)
    print(f"\n[1] 修正拼写错误: {fixed} 处")

    # Step 2: 补全缺失
    missing = sum(1 for q in qas if "question_type" not in q or "retrieval_difficulty" not in q)
    print(f"[2] 缺失标注: {missing}")
    if missing > 0:
        filled = backfill_missing(qas)
        print(f"  新标注: {filled}")

    # 保存
    with open(PROGRESS, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 最终统计
    qt = Counter(q.get("question_type", "?") for q in qas)
    rd = Counter(q.get("retrieval_difficulty", "?") for q in qas)
    ct = Counter(q.get("chunk_type", "?") for q in qas)
    sp = Counter(q.get("span", "?") for q in qas)

    remaining = sum(1 for q in qas if "question_type" not in q)
    print(f"\n{'=' * 60}")
    print(f"最终: {len(qas)} QA, 未标注: {remaining}")
    print(f"\nchunk_type:")
    for k, v in ct.most_common():
        print(f"  {k}: {v}")
    print(f"\nquestion_type:")
    for k, v in qt.most_common():
        print(f"  {k}: {v}")
    print(f"\nretrieval_difficulty:")
    for k, v in rd.most_common():
        print(f"  {k}: {v}")
    print(f"\nspan:")
    for k, v in sp.most_common():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
