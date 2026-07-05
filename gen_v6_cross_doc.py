#!/usr/bin/env python
"""V6 跨文档题目生成 — 从不同法律/文件中配对生成跨文档QA"""

import sys, json, random, re, time
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
from openai import OpenAI

CHUNKS_PATH = Path(__file__).parent / "data" / "eval_questions" / "chunks" / "current_chunks.json"
PROGRESS_PATH = Path(__file__).parent / "data" / "eval_questions" / "v6" / ".qa_gen_progress_v6.json"

GEN_MODEL = "GLM-4.1V-Thinking-FlashX"
TARGET = 100
BATCH_SIZE = 2
MAX_RETRIES = 3

SYSTEM_PROMPT = """你是RAG Benchmark工程师。根据两个不同法律/文件的Chunk，判断能否生成跨文档问答对。

## 判断标准
两个Chunk需有逻辑关联：对比、互补、程序衔接、上下位法、法条+案例等。不相关则返回空数组。

## 生成要求
1. 问题需两个Chunk信息才能完整回答
2. 模拟真实用户口吻，不用法条号，不用"根据XX法"
3. 不加角色前缀

## 输出格式
严格输出JSON数组，用双引号，最后一项不加逗号:
[{
  "question": "问题",
  "expected_chunk_id": "主Chunk的id",
  "acceptable_chunk_ids": ["辅Chunk的id"],
  "answer": "综合答案",
  "question_type": "comparison|procedure|scenario_judgment|condition_check",
  "retrieval_difficulty": "cross_reference"
}]

不相关输出: []"""


def load_chunks():
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["chunks"]


def build_pairs(chunks, n=200):
    """从不同 law_name 随机配对，优先同领域"""
    by_law = defaultdict(list)
    for c in chunks:
        law = c.get("law_name", "") or c.get("source_doc", "") or "__unknown__"
        by_law[law].append(c)

    laws = list(by_law.keys())
    print(f"  法律/文件: {len(laws)}")

    pairs = []
    seen = set()
    random.seed(42)
    attempts = 0

    while len(pairs) < n and attempts < n * 10:
        attempts += 1
        l1, l2 = random.sample(laws, 2)
        if not by_law[l1] or not by_law[l2]:
            continue
        c1 = random.choice(by_law[l1])
        c2 = random.choice(by_law[l2])
        key = tuple(sorted([c1["id"], c2["id"]]))
        if key in seen:
            continue
        seen.add(key)
        pairs.append((c1, c2))

    return pairs


def extract_json(content: str):
    content = content.strip()
    # 去 markdown 代码块
    m = re.search(r'```(?:json)?\s*\n?(.*?)```', content, re.DOTALL)
    if m:
        content = m.group(1).strip()
    elif content.startswith("```"):
        content = content[3:].strip()
        if content.endswith("```"):
            content = content[:-3].strip()
    # 尝试直接解析
    try:
        r = json.loads(content)
        return r if isinstance(r, list) else [r]
    except json.JSONDecodeError:
        pass
    # 尝试提取 JSON 数组
    for m in re.finditer(r'\[.*\]', content, re.DOTALL):
        try:
            r = json.loads(m.group())
            if isinstance(r, list):
                return r
        except json.JSONDecodeError:
            continue
    # 逐个提取对象
    objs = re.findall(r'\{(?:[^{}]|\{[^{}]*\})*\}', content)
    if objs:
        result = []
        for o in objs:
            try:
                result.append(json.loads(o))
            except json.JSONDecodeError:
                pass
        return result if result else None
    return None


def main():
    print("=" * 60)
    print("V6 跨文档题目生成器")
    print("=" * 60)

    chunks = load_chunks()
    print(f"\n[1/4] Chunks: {len(chunks)}")

    pairs = build_pairs(chunks)
    print(f"[2/4] 配对: {len(pairs)}")

    with open(PROGRESS_PATH, "r", encoding="utf-8") as f:
        progress = json.load(f)
    existing = progress.get("generated_qas", [])
    max_idx = len(existing)

    from config import settings
    client = OpenAI(
        base_url=settings.llm_api_url.replace("/chat/completions", ""),
        api_key=settings.llm_api_key,
    )

    print(f"[3/4] 生成 (模型: {GEN_MODEL})...")
    gen = 0
    skipped = 0

    for bs in range(0, len(pairs), BATCH_SIZE):
        if gen >= TARGET:
            break
        batch = pairs[bs:bs + BATCH_SIZE]
        bn = bs // BATCH_SIZE + 1

        descs = []
        for i, (c1, c2) in enumerate(batch):
            t1 = (c1.get("text", "") or c1.get("retrieval_text", ""))[:600]
            t2 = (c2.get("text", "") or c2.get("retrieval_text", ""))[:600]
            descs.append(
                f"配对{i+1}:\n"
                f"A(id:{c1['id']}) [{c1.get('law_name','') or c1.get('source_doc','')[:30]}]: {t1}\n"
                f"B(id:{c2['id']}) [{c2.get('law_name','') or c2.get('source_doc','')[:30]}]: {t2}"
            )

        user_msg = "判断以下配对是否相关，相关则生成跨文档问答对:\n\n" + "\n---\n".join(descs)

        success = False
        for attempt in range(MAX_RETRIES):
            try:
                resp = client.chat.completions.create(
                    model=GEN_MODEL,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                    temperature=0.7, max_tokens=8192, timeout=300,
                    extra_body={"thinking": {"type": "enabled"}},
                )
                content = resp.choices[0].message.content
                if not content:
                    content = getattr(resp.choices[0].message, "reasoning_content", "")
                if not content:
                    print(f"  批次 {bn}: 空响应")
                    break

                qa_list = extract_json(content)
                if qa_list is None:
                    print(f"  批次 {bn}: JSON解析失败: {content[:200]}")
                    break

                # 过滤有效QA
                added = 0
                for qa in qa_list:
                    if not isinstance(qa, dict):
                        continue
                    if gen >= TARGET:
                        break
                    max_idx += 1
                    qa["id"] = f"qa_v6_{max_idx:04d}"
                    qa.setdefault("question_type", "comparison")
                    qa.setdefault("retrieval_difficulty", "cross_reference")
                    qa["span"] = "cross_doc"
                    existing.append(qa)
                    gen += 1
                    added += 1

                progress["generated_qas"] = existing
                with open(PROGRESS_PATH, "w", encoding="utf-8") as f:
                    json.dump(progress, f, ensure_ascii=False, indent=2)

                print(f"  批次 {bn}: +{added} (累计 {gen}/{TARGET})")
                success = True
                break
            except Exception as e:
                print(f"  批次 {bn} 异常: {str(e)[:150]}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(5)

        if not success:
            skipped += len(batch)
        time.sleep(1.5)

    print(f"\n[4/4] 完成: 生成 {gen}, 跳过 ~{skipped} 对")
    print(f"  总 QA: {len(existing)}")


if __name__ == "__main__":
    main()
