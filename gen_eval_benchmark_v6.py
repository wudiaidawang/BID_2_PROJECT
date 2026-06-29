#!/usr/bin/env python
"""
V6 Benchmark 生成器 — 真实用户风格 QA 对

与 V5 的核心区别:
  1. 禁止 Chunk 改写 — 不根据原文微调生成问题
  2. 减少专有名词 — 模拟真实用户不知道完整标题/编号
  3. 多样化表达 — 同义词、口语、场景化
  4. 按 Chunk Type 差异化策略 — opinion_news 少生成, policy_doc 多生成
  5. 目标: 逼近真实用户 Query 分布，而非追求高 Recall

用法:
  python gen_eval_benchmark_v6.py
  python gen_eval_benchmark_v6.py --dry-run
  python gen_eval_benchmark_v6.py --total 200
"""

import sys
import json
import random
import time
import argparse
from pathlib import Path
from typing import List, Dict, Optional
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from openai import OpenAI

# ── 配置 ──
CHUNKS_PATH = Path(__file__).parent / "data" / "eval_questions" / "chunks" / "current_chunks.json"
OUTPUT_PATH = Path(__file__).parent / "data" / "eval_questions" / "v6" / "v6_benchmark.json"
PROGRESS_PATH = Path(__file__).parent / "data" / "eval_questions" / "v6" / ".qa_gen_progress_v6.json"
PROMPT_PATH = Path(__file__).parent / "data" / "eval_questions" / "prompts" / "v6_prompt.md"

BATCH_SIZE = 3
MAX_RETRIES = 3
RETRY_DELAY = 3
BATCH_DELAY = 1.5

GEN_MODEL = "GLM-4.1V-Thinking-FlashX"

# 每个 chunk 生成问题数量的范围 (按类型)
QUESTIONS_PER_CHUNK = {
    "policy_doc": (4, 6),
    "pdf_case_paragraph": (3, 5),
    "pdf_case_sliding": (3, 5),
    "pdf_law_parent": (2, 4),
    "opinion_news": (1, 2),
}

# Chunk 采样上限 (按类型, 控制总量)
CHUNK_SAMPLE_CAP = {
    "policy_doc": 228,        # 全部
    "pdf_case_paragraph": 200,
    "pdf_case_sliding": 78,   # 全部
    "pdf_law_parent": 200,
    "opinion_news": 100,
}

# ── System Prompt — 从 prompts/v6_prompt.md 读取 ──
def _load_system_prompt() -> str:
    """从 markdown 文件中提取 System Prompt（``` 代码块内的内容）"""
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        text = f.read()
    import re
    m = re.search(r'```\n(.*?)```', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    raise RuntimeError(f"未在 {PROMPT_PATH} 中找到 System Prompt 代码块")


# ── 工具函数 ──
def load_chunks() -> List[dict]:
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["chunks"]


def sample_chunks(chunks: List[dict], total_limit: Optional[int] = None):
    """按类型分层抽样"""
    by_type = defaultdict(list)
    for c in chunks:
        ct = c.get("chunk_type", "other")
        by_type[ct].append(c)

    random.seed(42)

    sampled = {}
    for ct, cap in CHUNK_SAMPLE_CAP.items():
        pool = by_type.get(ct, [])
        n = min(cap, len(pool))
        if total_limit:
            n = min(n, max(1, int(total_limit * n / 2000)))
        sampled[ct] = random.sample(pool, n) if n else []

    # 打印分布
    total = sum(len(v) for v in sampled.values())
    total_qa = 0
    for ct, items in sampled.items():
        lo, hi = QUESTIONS_PER_CHUNK.get(ct, (1, 2))
        est = len(items) * (lo + hi) // 2
        total_qa += est
        print(f"  {ct}: {len(items)} chunks, 预计 {est} QA ({lo}-{hi}/chunk)")

    print(f"  总计: {total} chunks, 预计 ~{total_qa} QA")
    return sampled


VALID_QUESTION_TYPES = (
    "scenario_judgment", "condition_check", "procedure",
    "responsibility", "definition", "comparison",
    "case_reasoning", "announcement_interpretation",
)
VALID_RETRIEVAL_DIFFICULTIES = ("direct", "synonym", "scenario", "cross_reference")


def validate_qa(qa: dict) -> List[str]:
    errors = []
    for field in ["question", "expected_chunk_id", "answer", "question_type", "retrieval_difficulty"]:
        if field not in qa:
            errors.append(f"缺少字段: {field}")
    if qa.get("question_type") not in VALID_QUESTION_TYPES:
        errors.append(f"无效 question_type: {qa.get('question_type')}")
    if qa.get("retrieval_difficulty") not in VALID_RETRIEVAL_DIFFICULTIES:
        errors.append(f"无效 retrieval_difficulty: {qa.get('retrieval_difficulty')}")
    return errors


# ── 生成器 ──
class V6QAGenerator:
    def __init__(self, total_limit: Optional[int] = None):
        self.total_limit = total_limit
        self._init_client()
        self.progress = self._load_progress()
        self.system_prompt = _load_system_prompt()

    def _init_client(self):
        from config import settings
        api_key = settings.llm_api_key
        api_url = settings.llm_api_url
        base_url = api_url.replace("/chat/completions", "")
        if not api_key:
            raise RuntimeError("LLM_API_KEY 未设置")
        self._model = GEN_MODEL
        self.client = OpenAI(base_url=base_url, api_key=api_key)

    def _load_progress(self) -> dict:
        if PROGRESS_PATH.exists():
            with open(PROGRESS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"completed_ids": [], "generated_qas": []}

    def _save_progress(self):
        PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(PROGRESS_PATH, "w", encoding="utf-8") as f:
            json.dump(self.progress, f, ensure_ascii=False, indent=2)

    def _call_llm(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        for attempt in range(MAX_RETRIES):
            try:
                resp = self.client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.8,
                    max_tokens=8192,
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

    def _extract_json(self, content: str) -> Optional[list]:
        content = content.strip()
        # 去掉 markdown 代码块标记
        import re
        md_match = re.search(r'```(?:json)?\s*\n?(.*?)```', content, re.DOTALL)
        if md_match:
            content = md_match.group(1).strip()
        elif content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:]) if len(lines) > 1 else content
            if content.endswith("```"):
                content = content[:-3].strip()
        try:
            result = json.loads(content)
            if isinstance(result, list):
                return result
            if isinstance(result, dict):
                return [result]
        except json.JSONDecodeError:
            pass
        # 找最后一个有效 JSON 数组
        matches = list(re.finditer(r'\[.*\]', content, re.DOTALL))
        for m in reversed(matches):
            try:
                result = json.loads(m.group())
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                continue
        # 逐个提取 JSON 对象
        objects = re.findall(r'\{(?:[^{}]|\{[^{}]*\})*\}', content)
        if objects:
            try:
                return [json.loads(obj) for obj in objects]
            except json.JSONDecodeError:
                pass
        return None

    def _infer_category(self, chunk: dict) -> str:
        ct = chunk.get("chunk_type", "")
        if ct == "pdf_law_parent":
            return "法规原文"
        elif ct in ("pdf_case_paragraph", "pdf_case_sliding"):
            return "案例"
        elif ct == "policy_doc":
            return "政策文件"
        elif ct == "opinion_news":
            return "观点新闻"
        return "其他"

    def _build_prompt(self, chunks: List[dict]) -> str:
        descriptions = []
        for i, c in enumerate(chunks):
            text = c.get("text", "") or c.get("retrieval_text", "")
            if len(text) > 1024:
                text = text[:1024] + "..."
            law = c.get("law_name", "") or c.get("source_doc", "") or ""
            title = c.get("title", "") or ""
            aid = c.get("article_id", "")
            ct = c.get("chunk_type", "")

            lo, hi = QUESTIONS_PER_CHUNK.get(ct, (1, 2))

            meta_parts = []
            if law:
                meta_parts.append(f"law: {law}")
            if title:
                meta_parts.append(f"title: {title}")
            if aid:
                meta_parts.append(f"article: {aid}")
            meta = ", ".join(meta_parts) if meta_parts else "无"

            descriptions.append(
                f"### Chunk {i+1}\n"
                f"- id: {c.get('id')}\n"
                f"- type: {ct}\n"
                f"- meta: {meta}\n"
                f"- 生成 {lo}-{hi} 个问题\n"
                f"- text:\n```\n{text}\n```"
            )

        return (
            f"为以下 {len(chunks)} 个 Chunk 生成问答对。\n\n"
            + "\n---\n".join(descriptions) +
            "\n\n按 Chunk 顺序输出 JSON 数组。每个 Chunk 生成指定数量的问题。"
        )

    def generate_batch(self, chunks: List[dict], qa_idx: int) -> List[dict]:
        if not chunks:
            return []
        content = self._call_llm(self.system_prompt, self._build_prompt(chunks))
        if not content:
            return []
        qa_list = self._extract_json(content)
        if not qa_list:
            print(f"  JSON 解析失败，原始: {content[:200]}")
            return []

        results = []
        for qa in qa_list:
            if qa is None:
                continue

            # 强制使用真实 chunk_id，不信任 LLM 返回的
            llm_cid = str(qa.get("expected_chunk_id", ""))
            matched_chunk = None
            for c in chunks:
                if str(c.get("id", "")) == llm_cid:
                    matched_chunk = c
                    break

            if matched_chunk is None:
                # 无法匹配，跳过
                continue

            expected_id = str(matched_chunk.get("id", ""))
            acceptable = qa.get("acceptable_chunk_ids", [])
            if not isinstance(acceptable, list):
                acceptable = []
            acceptable = [cid for cid in acceptable if cid != expected_id]

            qa_idx += 1
            results.append({
                "id": f"qa_v6_{qa_idx:04d}",
                "question": str(qa.get("question", "")).strip(),
                "answer": str(qa.get("answer", "")).strip(),
                "source_chunks": [expected_id] + acceptable,
                "expected_chunk_id": expected_id,
                "acceptable_chunk_ids": acceptable,
                "type": matched_chunk.get("chunk_type", ""),
                "category": self._infer_category(matched_chunk),
                "chunk_type": matched_chunk.get("chunk_type", ""),
                "span": "single",
                "law_name": matched_chunk.get("law_name", "") or matched_chunk.get("source_doc", "") or "",
                "title": matched_chunk.get("title", "") or "",
                "question_type": qa.get("question_type", "scenario_judgment"),
                "retrieval_difficulty": qa.get("retrieval_difficulty", "synonym"),
                "expected_source_type": self._infer_category(matched_chunk),
                "expected_answer_text": str(qa.get("answer", "")).strip(),
            })

        return results

    def run(self):
        print("=" * 60)
        print("V6 Benchmark 生成器 — 真实用户风格")
        print("=" * 60)

        # 1. 加载
        print("\n[1/4] 加载 chunks...")
        chunks = load_chunks()
        print(f"  已加载 {len(chunks)} 个 chunks")

        # 2. 抽样
        print("\n[2/4] 抽样...")
        sampled = sample_chunks(chunks, total_limit=self.total_limit)

        # 3. 生成
        print(f"\n[3/4] 生成 QA 对 (模型: {GEN_MODEL})...")
        all_qas = list(self.progress.get("generated_qas", []))
        completed_ids = set(self.progress.get("completed_ids", []))

        for ct in ["policy_doc", "pdf_case_paragraph", "pdf_case_sliding",
                    "pdf_law_parent", "opinion_news"]:
            items = sampled.get(ct, [])
            if not items:
                continue
            remaining = [c for c in items if c.get("id") not in completed_ids]
            if not remaining:
                print(f"  [{ct}] 全部已完成，跳过")
                continue

            lo, hi = QUESTIONS_PER_CHUNK.get(ct, (1, 2))
            print(f"\n  [{ct}] {len(remaining)} chunks ({lo}-{hi} QA/chunk)...")

            for batch_start in range(0, len(remaining), BATCH_SIZE):
                batch = remaining[batch_start:batch_start + BATCH_SIZE]
                bn = batch_start // BATCH_SIZE + 1
                total_bn = (len(remaining) - 1) // BATCH_SIZE + 1
                print(f"    批次 {bn}/{total_bn} ({len(batch)} chunks)...", end=" ", flush=True)

                new_qas = self.generate_batch(batch, len(all_qas))
                if new_qas:
                    all_qas.extend(new_qas)
                    for nq in new_qas:
                        completed_ids.add(nq["expected_chunk_id"])
                    self.progress["generated_qas"] = all_qas
                    self.progress["completed_ids"] = list(completed_ids)
                    self._save_progress()
                    print(f"OK (+{len(new_qas)}, total {len(all_qas)})")
                else:
                    print("FAIL")
                time.sleep(BATCH_DELAY)

        # 4. 验证与保存
        print(f"\n[4/4] 验证与保存...")
        valid_qas = []
        invalid_count = 0
        for qa in all_qas:
            errors = validate_qa(qa)
            if errors:
                invalid_count += 1
                if invalid_count <= 5:
                    print(f"  无效: {qa.get('id')} - {errors}")
            else:
                valid_qas.append(qa)
        print(f"  有效: {len(valid_qas)}, 无效: {invalid_count}")

        # 重新编号
        for i, qa in enumerate(valid_qas):
            qa["id"] = f"qa_v6_{i+1:04d}"

        # 统计
        by_type = defaultdict(int)
        by_qtype = defaultdict(int)
        by_rdiff = defaultdict(int)
        for qa in valid_qas:
            by_type[qa.get("chunk_type", "unknown")] += 1
            by_qtype[qa.get("question_type", "unknown")] += 1
            by_rdiff[qa.get("retrieval_difficulty", "unknown")] += 1

        output = {
            "version": "v6",
            "description": "真实用户风格 RAG 召回评测问答集 — 禁止Chunk改写、减少专有名词、模拟真实表达",
            "total": len(valid_qas),
            "stats": {
                "by_chunk_type": dict(by_type),
                "by_question_type": dict(by_qtype),
                "by_retrieval_difficulty": dict(by_rdiff),
            },
            "qa_pairs": valid_qas,
        }

        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"\n{'=' * 60}")
        print(f"V6 生成完成!")
        print(f"  总数: {len(valid_qas)}")
        print(f"  按chunk_type: {json.dumps(dict(by_type), ensure_ascii=False)}")
        print(f"  按question_type: {json.dumps(dict(by_qtype), ensure_ascii=False)}")
        print(f"  按retrieval_difficulty: {json.dumps(dict(by_rdiff), ensure_ascii=False)}")
        print(f"  输出: {OUTPUT_PATH}")
        print(f"{'=' * 60}")


def main():
    parser = argparse.ArgumentParser(description="V6 Benchmark 生成器 — 真实用户风格")
    parser.add_argument("--dry-run", action="store_true", help="仅预览抽样分布")
    parser.add_argument("--total", type=int, default=None, help="限制总数（测试用）")
    parser.add_argument("--resume", action="store_true", help="从断点继续")
    args = parser.parse_args()

    if not CHUNKS_PATH.exists():
        print(f"错误: chunks 文件不存在: {CHUNKS_PATH}")
        sys.exit(1)

    if args.dry_run:
        chunks = load_chunks()
        print(f"Chunks 总数: {len(chunks)}")
        sample_chunks(chunks, total_limit=args.total)
        return

    if not args.resume and PROGRESS_PATH.exists():
        PROGRESS_PATH.unlink()

    generator = V6QAGenerator(total_limit=args.total)
    generator.run()


if __name__ == "__main__":
    main()
