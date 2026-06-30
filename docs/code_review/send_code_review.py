#!/usr/bin/env python3
"""逐个发送项目文件给 LLM 做 Retriever 系统审查"""

import httpx
import sys
from pathlib import Path

API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
API_KEY = "125b34503d904708a175cc2de913a2a5.NHYrWPurkiScu00m"
MODEL = "glm-4.5-air"

PROMPT = """这是我整个 Retriever。

请不要修改代码。

请只找：

① Recall下降原因
② Hybrid设计问题
③ Rewrite设计问题
④ Parent Context问题
⑤ RRF是否合理
⑥ Rerank是否合理
⑦ Query Routing建议
⑧ 有没有工程隐患
⑨ 有没有论文创新点可以加强
⑩ 给出优先级排序。"""

# 待审查文件（按管线顺序）
FILES = [
    "app/core/query_rewriter.py",
    "app/pipeline/preprocessor.py",
    "app/core/embedding.py",
    "app/pipeline/retrievers.py",
    "app/pipeline/fusion.py",
    "app/pipeline/expanders.py",
    "app/pipeline/rerankers.py",
    "app/pipeline/pipeline.py",
    "app/core/child_chunk_builder.py",
    "app/core/parent_chunk_builder.py",
    "app/core/retriever.py",
    "app/core/router.py",
    "eval_standalone.py",
]


def send_file(path: str, index: int, total: int) -> str:
    """发送单个文件给 LLM 审查"""
    fpath = Path(path)
    if not fpath.exists():
        return f"❌ File not found: {path}"

    code = fpath.read_text(encoding="utf-8")
    content = f"[{index}/{total}] {path}\n\n```python\n{code}\n```"

    r = httpx.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": content},
            ],
            "temperature": 0.3,
            "max_tokens": 4096,
        },
        timeout=180,
    )
    data = r.json()
    if "choices" in data:
        return data["choices"][0]["message"]["content"]
    else:
        return f"❌ API Error: {data}"


def main():
    total = len(FILES)
    all_results = []

    print(f"# Retriever 系统审查 — {total} 个文件")
    print(f"模型: {MODEL}")
    print()

    for i, f in enumerate(FILES, 1):
        fname = Path(f).name
        print(f"\n{'='*60}")
        print(f"[{i}/{total}] 发送: {f} ...")
        result = send_file(f, i, total)
        all_results.append((f, result))
        print(result[:300])
        if i < total:
            print("(等待 2s...)")
            import time
            time.sleep(2)

    # 写入汇总报告
    out = Path(__file__).parent / "code_review_retriever.md"
    with open(out, "w", encoding="utf-8") as f:
        f.write("# Retriever 系统审查报告\n\n")
        f.write(f"模型: {MODEL}\n")
        f.write(f"文件数: {total}\n\n")
        f.write("---\n\n")
        for path, result in all_results:
            f.write(f"## {Path(path).name}\n\n")
            f.write(result)
            f.write("\n\n---\n\n")
    print(f"\n\n✅ 审查完成，报告: {out}")


if __name__ == "__main__":
    main()
