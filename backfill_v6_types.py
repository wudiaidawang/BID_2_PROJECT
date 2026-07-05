#!/usr/bin/env python
"""V6 回填 — 为已生成的 QA 补充 question_type 和 retrieval_difficulty 字段"""

import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from openai import OpenAI

PROGRESS_PATH = Path(__file__).parent / "data" / "eval_questions" / "v6" / ".qa_gen_progress_v6.json"
BACKUP_PATH = Path(__file__).parent / "data" / "eval_questions" / "v6" / ".qa_gen_progress_v6.json.bak"

VALID_TYPES = (
    "scenario_judgment", "condition_check", "procedure",
    "responsibility", "definition", "comparison",
    "case_reasoning", "announcement_interpretation",
)
VALID_DIFFICULTIES = ("direct", "synonym", "scenario", "cross_reference")

CLASSIFY_PROMPT = """你是一名 RAG Benchmark 标注工程师。请为给定的问答对标注 question_type 和 retrieval_difficulty。

## 题型 (question_type)
1. scenario_judgment: 给业务场景，问后果/是否合规/如何处理
2. condition_check: 问某操作的前提条件、适用范围、触发门槛
3. procedure: 问具体操作流程、步骤、时间节点
4. responsibility: 问哪个部门/角色负责什么事
5. definition: 问某概念/术语的含义
6. comparison: 问两个概念/方式/情形的区别
7. case_reasoning: 根据案例情景推断结论
8. announcement_interpretation: 对公告/新闻信息的理解和推断

## 检索难度 (retrieval_difficulty)
- direct: 问题与原文仍有明显关键词重叠，BM25即可命中
- synonym: 核心概念用了同义词或口语表达，需要Embedding语义匹配
- scenario: 问题描述业务场景而非直接提法条，需要理解场景与法条对应关系
- cross_reference: 需要关联多处信息才能定位正确答案

## 输出格式
严格输出 JSON 数组，每个元素添加 question_type 和 retrieval_difficulty:
[{
  "id": "qa_v6_0001",
  "question_type": "scenario_judgment",
  "retrieval_difficulty": "scenario"
}]

按输入顺序输出。"""


def main():
    # 加载
    with open(PROGRESS_PATH, "r", encoding="utf-8") as f:
        progress = json.load(f)

    qas = progress.get("generated_qas", [])
    print(f"已加载 {len(qas)} 个 QA")

    # 检查哪些需要回填
    need_backfill = [q for q in qas if "question_type" not in q or "retrieval_difficulty" not in q]
    print(f"需要回填: {len(need_backfill)}")

    if not need_backfill:
        print("全部已标注，无需回填")
        return

    # 备份
    import shutil
    shutil.copy(PROGRESS_PATH, BACKUP_PATH)
    print(f"已备份: {BACKUP_PATH}")

    # 初始化客户端
    from config import settings
    client = OpenAI(
        base_url=settings.llm_api_url.replace("/chat/completions", ""),
        api_key=settings.llm_api_key,
    )

    BATCH_SIZE = 20
    total = len(need_backfill)

    for batch_start in range(0, total, BATCH_SIZE):
        batch = need_backfill[batch_start:batch_start + BATCH_SIZE]
        bn = batch_start // BATCH_SIZE + 1
        total_bn = (total - 1) // BATCH_SIZE + 1

        # 构建输入
        items = []
        for q in batch:
            items.append({
                "id": q["id"],
                "question": q["question"],
                "answer": q.get("answer", "")[:200],
                "chunk_type": q.get("chunk_type", ""),
            })

        user_msg = f"请为以下 {len(items)} 个问答对标注:\n\n" + json.dumps(items, ensure_ascii=False, indent=2)

        success = False
        for attempt in range(3):
            try:
                resp = client.chat.completions.create(
                    model="GLM-4.1V-Thinking-FlashX",
                    messages=[
                        {"role": "system", "content": CLASSIFY_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                    temperature=0.3,
                    max_tokens=4096,
                    timeout=300,
                    extra_body={"thinking": {"type": "enabled"}},
                )
                content = resp.choices[0].message.content
                if not content:
                    content = getattr(resp.choices[0].message, "reasoning_content", "")

                # 解析
                import re
                content = content.strip()
                md = re.search(r'```(?:json)?\s*\n?(.*?)```', content, re.DOTALL)
                if md:
                    content = md.group(1).strip()
                try:
                    results = json.loads(content)
                except json.JSONDecodeError:
                    m = re.search(r'\[.*\]', content, re.DOTALL)
                    if m:
                        results = json.loads(m.group())
                    else:
                        raise

                if isinstance(results, dict):
                    results = [results]

                # 回填
                result_map = {r["id"]: r for r in results}
                filled = 0
                for q in batch:
                    r = result_map.get(q["id"], {})
                    qt = r.get("question_type", "")
                    rd = r.get("retrieval_difficulty", "")
                    if qt in VALID_TYPES:
                        q["question_type"] = qt
                        filled += 1
                    if rd in VALID_DIFFICULTIES:
                        q["retrieval_difficulty"] = rd
                        filled += 1

                print(f"  批次 {bn}/{total_bn}: {filled}/{len(batch)*2} 字段回填成功")
                success = True
                break
            except Exception as e:
                print(f"  批次 {bn} 失败 (attempt {attempt+1}): {e}")
                time.sleep(3)

        if not success:
            print(f"  批次 {bn} 全部重试失败，跳过")

        # 保存进度
        with open(PROGRESS_PATH, "w", encoding="utf-8") as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)
        time.sleep(1.5)

    # 最终统计
    missing = sum(1 for q in progress["generated_qas"]
                  if "question_type" not in q or "retrieval_difficulty" not in q)
    print(f"\n回填完成: {len(progress['generated_qas'])} QA, {missing} 仍未标注")


if __name__ == "__main__":
    main()
