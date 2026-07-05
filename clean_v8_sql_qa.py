#!/usr/bin/env python3
"""
清洗 V8 Canonical QA 中的 SQL 类问题（计数/数值/日期型），
从进度文件中剔除，并清理对应的 completed_ids 以便重新生成。
"""
import json, re, sys
from pathlib import Path

PROJ = Path(__file__).parent
PROGRESS_PATH = PROJ / "data" / "eval_questions" / "v8" / ".qa_gen_progress_v8_canonical.json"

# ── SQL 类检测规则 ──
def is_sql_type(answer: str, question: str) -> tuple[bool, str]:
    """返回 (is_sql, reason)"""
    ans = answer.strip()
    qt = question.strip()

    # 1. 纯数字
    if re.match(r'^\d+(\.\d+)?[万亿千百十]?[元个项条名次级类种家分人日天月年倍号度%％块只台座处篇章节期次批]$', ans):
        return True, f"纯数值: {ans}"
    if re.match(r'^\d+(\.\d+)?$', ans):
        return True, f"纯数字: {ans}"

    # 2. 纯日期
    if re.match(r'^\d{4}年\d{1,2}月\d{1,2}日$', ans):
        return True, f"纯日期: {ans}"
    if re.match(r'^\d{4}-\d{2}-\d{2}$', ans):
        return True, f"纯日期: {ans}"
    if re.match(r'^\d{4}年\d{1,2}月$', ans):
        return True, f"纯日期: {ans}"

    # 3. 计数型描述（"16项政策措施", "8级", "100分"）
    if re.match(r'^\d+[项条个名次级类种家分元万元亿元]$', ans):
        return True, f"计数: {ans}"
    if re.match(r'^\d+[项条个名次级类种家分]', ans) and len(ans) <= 10:
        return True, f"计数描述: {ans}"

    # 4. Question 本身是计数/日期问法
    count_patterns = [
        r'多少[项条个名次级类种家]', r'多少[金额分数]', r'几[项条个名次级类种家]',
        r'最高多少', r'最低多少', r'什么时间', r'什么时候', r'哪一天',
        r'哪年', r'哪月', r'共计多少', r'总共多少',
    ]
    for pat in count_patterns:
        if re.search(pat, qt):
            return True, f"问题计数型: {re.search(pat, qt).group()}"

    return False, ""


def clean_progress():
    with open(PROGRESS_PATH, "r", encoding="utf-8") as f:
        p = json.load(f)

    qas = p["generated_qas"]
    completed_ids = set(p["completed_ids"])

    removed = []
    kept = []
    affected_chunks = set()

    for qa in qas:
        is_sql, reason = is_sql_type(qa.get("answer", ""), qa.get("question", ""))
        if is_sql:
            removed.append((qa, reason))
            affected_chunks.add(qa.get("expected_chunk_id", ""))
        else:
            kept.append(qa)

    # 对于受影响chunk，检查是否还有其他QA覆盖
    chunk_qa_count = {}
    for qa in kept:
        cid = qa.get("expected_chunk_id", "")
        chunk_qa_count[cid] = chunk_qa_count.get(cid, 0) + 1

    # 如果某个chunk的所有QA都被移除了，从completed_ids中移除
    ids_to_remove = []
    for cid in affected_chunks:
        if chunk_qa_count.get(cid, 0) == 0:
            ids_to_remove.append(cid)

    new_completed = [cid for cid in completed_ids if cid not in ids_to_remove]

    # ── 统计 ──
    print(f"原始 QA: {len(qas)}")
    print(f"保留: {len(kept)}")
    print(f"剔除: {len(removed)}")
    print(f"chunk 完全失去覆盖需重生成: {len(ids_to_remove)}")
    print(f"completed_ids: {len(completed_ids)} → {len(new_completed)}")

    # 按原因分类
    from collections import Counter
    reasons = Counter(r for _, r in removed)
    print(f"\n剔除原因分布:")
    for r, c in reasons.most_common():
        print(f"  {r}: {c}")

    # ── 样本 ──
    print(f"\n--- 被剔除样本 (前10) ---")
    for qa, reason in removed[:10]:
        print(f"  [{reason}] Q: {qa['question'][:60]}")
        print(f"  A: {qa['answer'][:60]}")
        print()

    # ── 写回 ──
    # 备份
    backup_path = PROGRESS_PATH.with_suffix(".json.bak")
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False, indent=2)
    print(f"备份: {backup_path}")

    p["generated_qas"] = kept
    p["completed_ids"] = new_completed

    with open(PROGRESS_PATH, "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False, indent=2)
    print(f"写回: {PROGRESS_PATH}")
    print(f"\n清洗完成: {len(qas)} → {len(kept)} QA, {len(ids_to_remove)} chunks 需重新生成")


if __name__ == "__main__":
    if not PROGRESS_PATH.exists():
        print(f"错误: 进度文件不存在 {PROGRESS_PATH}")
        sys.exit(1)
    clean_progress()
