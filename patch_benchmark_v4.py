#!/usr/bin/env python
"""补丁脚本：为 eval_benchmark_v4.json 补充缺失的 QA 对"""
import sys, json, random, time
from pathlib import Path
from collections import defaultdict
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).parent))
from config import settings

CHUNKS_PATH = Path(__file__).parent / "data" / "eval_questions" / "policy_chunks_export.json"
OUTPUT_PATH = Path(__file__).parent / "data" / "eval_questions" / "eval_benchmark_v4.json"

GEN_MODEL = "GLM-4.1V-Thinking-FlashX"
BATCH_SIZE = 5
MAX_RETRIES = 3
RETRY_DELAY = 3
BATCH_DELAY = 1.5

# 需要补充的数量
NEED_CASE = 27
NEED_CROSS = 18

SYSTEM_PROMPT_SINGLE = """你是一个企业级RAG系统评测集构建专家。你的任务是基于给定的知识库Chunk生成高质量的问答对，用于评测检索系统的召回和排序能力。

## 输出格式
严格输出 JSON 数组，每个元素包含以下字段：
{
  "question": "模拟真实用户自然语言问题",
  "expected_chunk_id": "该问题最核心答案所在的精确chunk_id",
  "acceptable_chunk_ids": ["其他同样正确的chunk_id", "..."],
  "answer": "用简短的一句话给出标准答案",
  "difficulty": "easy|medium|hard"
}

## 生成要求
1. **真实口吻**：问题要像用户日常提问，禁止直接使用Chunk标题或拼接关键词。
2. **精准锚定**：每一个问题都必须包含足够的唯一区分信息，确保人类能够区分于其他类似条款。
3. **无幻觉**：所有问题和答案必须严格基于提供的Chunk内容，不得引入外部知识。
4. 每个片段生成一个问答对。"""

SYSTEM_PROMPT_CROSS = """你是一个企业级RAG系统评测集构建专家。请为以下相邻法律条款对生成跨条款问答对。

## 输出格式
严格输出 JSON 数组：
[{
  "question": "需要两个片段信息才能回答的问题",
  "expected_chunk_id": "第一个片段的chunk_id",
  "acceptable_chunk_ids": ["第二个片段的chunk_id"],
  "answer": "综合两个片段的完整答案",
  "difficulty": "easy|medium|hard"
}]

## 要求
1. 问题需要两个片段信息才能完整回答
2. 无幻觉，严格基于提供的Chunk内容
3. 每个片段对生成一个问答对。"""


def load_chunks():
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["chunks"]


def extract_json(content):
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:]) if len(lines) > 1 else content
        if content.endswith("```"):
            content = content[:-3]
    try:
        result = json.loads(content)
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            return [result]
        return None
    except json.JSONDecodeError:
        import re
        objects = re.findall(r'\{(?:[^{}]|\{[^{}]*\})*\}', content)
        if objects:
            try:
                return [json.loads(obj) for obj in objects]
            except json.JSONDecodeError:
                pass
    return None


def call_llm(client, model, system_prompt, user_prompt):
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=16384,
                timeout=300,
                extra_body={"thinking": {"type": "enabled"}},
            )
            content = resp.choices[0].message.content
            if not content:
                content = getattr(resp.choices[0].message, "reasoning_content", "")
            return content
        except Exception as e:
            print(f"  LLM 调用失败 (尝试 {attempt+1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
    return None


def find_cross_pairs(parent_chunks, used_ids, needed_count):
    by_law = defaultdict(list)
    for c in parent_chunks:
        law = c.get("law_name", "")
        aid = c.get("article_id", "")
        if law and aid and c["id"] not in used_ids:
            try:
                by_law[law].append((int(aid), c))
            except (ValueError, TypeError):
                pass
    pairs = []
    seen = set()
    for law, chunks in by_law.items():
        chunks.sort(key=lambda x: x[0])
        for i in range(len(chunks) - 1):
            aid_a, c_a = chunks[i]
            aid_b, c_b = chunks[i + 1]
            if aid_a < aid_b and aid_b - aid_a <= 2:
                key = (c_a["id"], c_b["id"])
                if key not in seen:
                    seen.add(key)
                    pairs.append((c_a, c_b))
    random.seed(42)
    random.shuffle(pairs)
    return pairs[:needed_count]


def main():
    print("=" * 50)
    print(f"补丁生成: case_paragraph x{NEED_CASE}, cross_chunk x{NEED_CROSS}")
    print("=" * 50)

    # 加载已有的 used IDs
    with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
        existing = json.load(f)
    used_ids = set()
    for q in existing["qa_pairs"]:
        used_ids.add(q.get("expected_chunk_id", ""))
        for cid in q.get("acceptable_chunk_ids", []):
            used_ids.add(cid)
    print(f"已有 {len(existing['qa_pairs'])} QA, {len(used_ids)} 个已用 chunk")

    # 初始化 LLM
    api_key = settings.llm_api_key
    api_url = settings.llm_api_url
    base_url = api_url.replace("/chat/completions", "")
    client = OpenAI(base_url=base_url, api_key=api_key)
    model = GEN_MODEL

    # 加载 chunks
    chunks = load_chunks()
    by_type = defaultdict(list)
    for c in chunks:
        by_type[c.get("chunk_type", "")].append(c)

    new_qas = []
    qa_counter = len(existing["qa_pairs"])

    # --- pdf_case_paragraph ---
    print(f"\n[pdf_case_paragraph] 需要 {NEED_CASE} 条...")
    case_chunks = [c for c in by_type.get("pdf_case_paragraph", []) if c["id"] not in used_ids]
    random.seed(42)
    random.shuffle(case_chunks)
    case_chunks = case_chunks[:NEED_CASE]
    print(f"  可用 {len(case_chunks)} 个未使用的 chunk")

    for batch_start in range(0, len(case_chunks), BATCH_SIZE):
        batch = case_chunks[batch_start:batch_start + BATCH_SIZE]
        bn = batch_start // BATCH_SIZE + 1
        total_bn = (len(case_chunks) - 1) // BATCH_SIZE + 1
        print(f"  批次 {bn}/{total_bn} ({len(batch)} chunks)...", end=" ", flush=True)

        # 构建 prompt
        parts = []
        for i, c in enumerate(batch):
            text = c.get("text", "") or c.get("retrieval_text", "")
            if len(text) > 1200:
                text = text[:1200] + "..."
            parts.append(
                f"### 片段 {i+1}\n"
                f"- chunk_id: {c['id']}\n"
                f"- 来源: {c.get('source_doc','未知')}\n"
                f"- 文本:\n```\n{text}\n```"
            )
        prompt = f"请为以下 {len(batch)} 个案例段落各生成一个问答对。\n\n" + "\n---\n".join(parts) + "\n\n请输出 JSON 数组。"

        content = call_llm(client, model, SYSTEM_PROMPT_SINGLE, prompt)
        if not content:
            print("FAIL (无响应)")
            continue

        qa_list = extract_json(content)
        if not qa_list:
            print(f"FAIL (解析失败): {content[:200]}")
            continue

        for i, qa in enumerate(qa_list):
            if i >= len(batch):
                break
            c = batch[i]
            qid = f"qa_v4_{qa_counter + 1:04d}"
            qa_counter += 1
            expected_id = str(qa.get("expected_chunk_id", c["id"]))
            acceptable = qa.get("acceptable_chunk_ids", [])
            if not isinstance(acceptable, list):
                acceptable = []
            acceptable = [cid for cid in acceptable if cid != expected_id]

            new_qas.append({
                "id": qid,
                "question": str(qa.get("question", "")).strip(),
                "answer": str(qa.get("answer", "")).strip(),
                "source_chunks": [expected_id] + acceptable,
                "expected_chunk_id": expected_id,
                "acceptable_chunk_ids": acceptable,
                "type": "pdf_case_paragraph",
                "category": "案例",
                "sub_category": "法律案例",
                "chunk_type": "pdf_case_paragraph",
                "span": "single",
                "article_id": str(c.get("article_id", "")),
                "law_name": c.get("source_doc", "") or "",
                "difficulty": qa.get("difficulty", "medium"),
                "expected_source_type": "案例",
                "expected_answer_text": str(qa.get("answer", "")).strip(),
                "is_regulatory_strict": False,
            })
            used_ids.add(expected_id)
            for cid in acceptable:
                used_ids.add(cid)
        print(f"OK (+{min(len(qa_list), len(batch))})")
        time.sleep(BATCH_DELAY)

    # --- cross_chunk ---
    print(f"\n[cross_chunk] 需要 {NEED_CROSS} 条...")
    parent_chunks = by_type.get("pdf_law_parent", [])
    pairs = find_cross_pairs(parent_chunks, used_ids, NEED_CROSS)
    print(f"  找到 {len(pairs)} 对可用")

    for batch_start in range(0, len(pairs), BATCH_SIZE):
        batch = pairs[batch_start:batch_start + BATCH_SIZE]
        bn = batch_start // BATCH_SIZE + 1
        total_bn = (len(pairs) - 1) // BATCH_SIZE + 1
        print(f"  批次 {bn}/{total_bn} ({len(batch)} pairs)...", end=" ", flush=True)

        parts = []
        for i, (c_a, c_b) in enumerate(batch):
            text_a = c_a.get("text", "") or c_a.get("retrieval_text", "")
            text_b = c_b.get("text", "") or c_b.get("retrieval_text", "")
            if len(text_a) > 800: text_a = text_a[:800] + "..."
            if len(text_b) > 800: text_b = text_b[:800] + "..."
            parts.append(
                f"### 片段对 {i+1}\n"
                f"- 法律: {c_a.get('law_name','')}\n"
                f"- 条款 {c_a.get('article_id','')} (id: {c_a['id']}):\n```\n{text_a}\n```\n"
                f"- 条款 {c_b.get('article_id','')} (id: {c_b['id']}):\n```\n{text_b}\n```"
            )
        prompt = f"请为以下 {len(batch)} 对条款各生成一个跨条款问答对。\n\n" + "\n---\n".join(parts) + "\n\n请输出 JSON 数组。"

        content = call_llm(client, model, SYSTEM_PROMPT_CROSS, prompt)
        if not content:
            print("FAIL (无响应)")
            continue

        qa_list = extract_json(content)
        if not qa_list:
            print(f"FAIL (解析失败): {content[:200]}")
            continue

        for i, qa in enumerate(qa_list):
            if i >= len(batch):
                break
            c_a, c_b = batch[i]
            qid = f"qa_v4_{qa_counter + 1:04d}"
            qa_counter += 1
            expected_id = str(qa.get("expected_chunk_id", c_a["id"]))
            acceptable = qa.get("acceptable_chunk_ids", [])
            if not isinstance(acceptable, list):
                acceptable = []
            if c_b["id"] not in acceptable:
                acceptable.append(c_b["id"])
            acceptable = [cid for cid in acceptable if cid != expected_id]

            new_qas.append({
                "id": qid,
                "question": str(qa.get("question", "")).strip(),
                "answer": str(qa.get("answer", "")).strip(),
                "source_chunks": [expected_id] + acceptable,
                "expected_chunk_id": expected_id,
                "acceptable_chunk_ids": acceptable,
                "type": "cross_chunk",
                "category": "法规原文",
                "sub_category": "其他法规",
                "chunk_type": "pdf_law_parent",
                "span": "cross",
                "article_id": f"{c_a.get('article_id','')},{c_b.get('article_id','')}",
                "law_name": c_a.get("law_name", "") or "",
                "difficulty": qa.get("difficulty", "medium"),
                "expected_source_type": "法规原文",
                "expected_answer_text": str(qa.get("answer", "")).strip(),
                "is_regulatory_strict": True,
            })
        print(f"OK (+{min(len(qa_list), len(batch))})")
        time.sleep(BATCH_DELAY)

    # 合并保存
    print(f"\n补丁生成完成: {len(new_qas)} 条新 QA")
    all_qas = existing["qa_pairs"] + new_qas
    # 重新编号
    for i, qa in enumerate(all_qas):
        qa["id"] = f"qa_v4_{i+1:04d}"

    by_type = defaultdict(int)
    by_diff = defaultdict(int)
    by_span = defaultdict(int)
    for qa in all_qas:
        by_type[qa.get("type", qa.get("chunk_type", "unknown"))] += 1
        by_diff[qa.get("difficulty", "unknown")] += 1
        by_span[qa.get("span", "unknown")] += 1

    output = {
        "version": "v4",
        "description": "基于 policy collection chunks 生成的召回评估问答集 (1000题)",
        "total": len(all_qas),
        "stats": {
            "by_chunk_type": dict(by_type),
            "by_difficulty": dict(by_diff),
            "by_span": dict(by_span),
        },
        "qa_pairs": all_qas,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n最终: {len(all_qas)} QA 对")
    print(f"按类型: {json.dumps(dict(by_type), ensure_ascii=False)}")
    print(f"按难度: {json.dumps(dict(by_diff), ensure_ascii=False)}")
    print(f"输出: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
