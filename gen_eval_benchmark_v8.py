#!/usr/bin/env python3
"""
V8 QA 生成器 — 为 pdf_case_structured 生成 Benchmark QA

用法:
  python gen_eval_benchmark_v8.py                    # 全量生成
  python gen_eval_benchmark_v8.py --total 50          # 小规模测试
  python gen_eval_benchmark_v8.py --dry-run           # 仅预览
  python gen_eval_benchmark_v8.py --merge             # 合并到旧 benchmark
"""

import sys, json, random, time, argparse, re
from pathlib import Path
from typing import List, Dict, Optional
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from openai import OpenAI

PROJ = Path(__file__).parent
CHUNKS_PATH = PROJ / "data" / "eval_questions" / "chunks" / "current_chunks.json"
PROMPT_PATH = PROJ / "data" / "eval_questions" / "prompts" / "v8.0_prompt.md"
OUTPUT_DIR = PROJ / "data" / "eval_questions" / "v9"
PROGRESS_PATH = OUTPUT_DIR / ".qa_gen_progress_v9_canonical.json"

GEN_MODEL = "glm-4.5-air"
BATCH_SIZE = 3
MAX_RETRIES = 3
RETRY_DELAY = 3
BATCH_DELAY = 1.5

QUESTIONS_PER_CHUNK = (3, 5)  # pdf_case_structured 内容充实，多生成几个
TARGET_CHUNKS = 200  # 采样数量
SAMPLE_SEED = 42

VALID_QUESTION_TYPES = (
    "scenario_judgment", "condition_check", "procedure",
    "responsibility", "definition", "comparison",
    "case_reasoning", "announcement_interpretation",
)
VALID_RETRIEVAL_DIFFICULTIES = ("direct", "synonym", "scenario", "cross_reference")
VALID_SPANS = ("single", "cross_chunk", "cross_doc")


def load_prompt():
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def load_chunks():
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["chunks"]


def sample_chunks(chunks, total_limit=None):
    """只采样 pdf_case_structured"""
    pool = [c for c in chunks if c.get("chunk_type") == "pdf_case_structured"]
    random.seed(SAMPLE_SEED)

    # 按 segment_type 分层采样
    by_seg = defaultdict(list)
    for c in pool:
        by_seg[c.get("segment_type", "other")].append(c)

    sampled = []
    for seg_type, items in by_seg.items():
        n = min(len(items), TARGET_CHUNKS // len(by_seg))
        if total_limit:
            n = min(n, total_limit // len(by_seg))
        sampled.extend(random.sample(items, max(1, n)))

    random.shuffle(sampled)
    if total_limit:
        sampled = sampled[:total_limit]

    print(f"  采样: {len(sampled)} chunks (from {len(pool)} total)")
    for seg_type in sorted(by_seg.keys()):
        n = sum(1 for c in sampled if c.get("segment_type") == seg_type)
        print(f"    {seg_type}: {n}")
    return sampled


class V8QAGenerator:
    def __init__(self, total_limit=None, dry_run=False):
        self.total_limit = total_limit
        self.dry_run = dry_run
        self._init_client()
        self.progress = self._load_progress()

    def _init_client(self):
        from config import settings
        api_key = settings.llm_api_key
        api_url = settings.llm_api_url
        base_url = api_url.replace("/chat/completions", "")
        if not api_key:
            raise RuntimeError("LLM_API_KEY 未设置")
        self.client = OpenAI(base_url=base_url, api_key=api_key)

    def _load_progress(self):
        if PROGRESS_PATH.exists():
            with open(PROGRESS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"completed_ids": [], "generated_qas": []}

    def _save_progress(self):
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(PROGRESS_PATH, "w", encoding="utf-8") as f:
            json.dump(self.progress, f, ensure_ascii=False, indent=2)

    def _call_llm(self, system_prompt, user_prompt):
        for attempt in range(MAX_RETRIES):
            try:
                resp = self.client.chat.completions.create(
                    model=GEN_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.4,
                    max_tokens=8192,
                    timeout=300,
                    extra_body={"thinking": {"type": "disabled"}},
                )
                content = resp.choices[0].message.content
                if not content:
                    content = getattr(resp.choices[0].message, "reasoning_content", "")
                return content
            except Exception as e:
                print(f"  LLM 失败 (尝试 {attempt+1}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
        return None

    def _extract_json(self, content):
        if not content:
            return None
        content = content.strip()

        # 1. Extract from markdown code blocks (handle both ```json and ```)
        for pat in [r'```(?:json)?\s*\n?(.*?)```', r'```\s*\n?(.*?)```']:
            md_match = re.search(pat, content, re.DOTALL)
            if md_match:
                inner = md_match.group(1).strip()
                if inner:
                    content = inner
                    break

        # 2. Direct parse
        try:
            result = json.loads(content)
            if isinstance(result, list):
                return [r for r in result if isinstance(r, dict)]
            elif isinstance(result, dict):
                return [result]
        except json.JSONDecodeError:
            pass

        # 3. Find outermost array by bracket counting (skip brackets in strings)
        best = None
        for m in re.finditer(r'\[', content):
            depth = 0
            in_str = False
            escape = False
            start = m.start()
            for i in range(start, len(content)):
                c = content[i]
                if escape:
                    escape = False
                    continue
                if c == '\\':
                    escape = True
                    continue
                if c == '"':
                    in_str = not in_str
                    continue
                if in_str:
                    continue
                if c == '[':
                    depth += 1
                elif c == ']':
                    depth -= 1
                    if depth == 0:
                        candidate = content[start:i+1]
                        try:
                            result = json.loads(candidate)
                            if isinstance(result, list):
                                result = [r for r in result if isinstance(r, dict)]
                                if result and (best is None or len(result) > len(best)):
                                    best = result
                        except json.JSONDecodeError:
                            pass
                        break

        # 4. Last resort: try to fix truncated JSON (missing closing ])
        if best is None:
            best = self._repair_truncated(content)

        return best

    def _repair_truncated(self, content):
        """Try to repair truncated JSON by adding missing closing brackets"""
        # Remove markdown artifacts
        content = re.sub(r'```\w*', '', content)
        content = content.strip()

        # Find the start of the array
        arr_start = content.find('[')
        if arr_start < 0:
            return None
        content = content[arr_start:]

        # Count open brackets/braces in strings-aware way
        stack = []
        in_str = False
        escape = False
        for c in content:
            if escape:
                escape = False
                continue
            if c == '\\':
                escape = True
                continue
            if c == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if c in '[{':
                stack.append(c)
            elif c == ']':
                if stack and stack[-1] == '[':
                    stack.pop()
            elif c == '}':
                if stack and stack[-1] == '{':
                    stack.pop()

        if not stack:
            return None  # Already balanced, but direct parse failed

        # Close remaining structures
        repair = content
        for c in reversed(stack):
            repair += '}' if c == '{' else ']'

        try:
            result = json.loads(repair)
            if isinstance(result, list):
                result = [r for r in result if isinstance(r, dict)]
                if result:
                    return result
        except json.JSONDecodeError:
            pass

        return None

    def _normalize(self, raw, mapping, default):
        raw = raw.strip().lower().replace(" ", "_")
        if "," in raw:
            raw = raw.split(",")[0].strip()
        return mapping.get(raw, default)

    def _validate_and_fix(self, qa, chunks):
        if qa is None:
            return None
        llm_cid = str(qa.get("expected_chunk_id", ""))
        matched = None
        for c in chunks:
            if str(c.get("chunk_id", "")) == llm_cid:
                matched = c
                break
        if matched is None:
            return None

        acceptable = qa.get("acceptable_chunk_ids", [])
        if not isinstance(acceptable, list):
            acceptable = []
        acceptable = [str(cid) for cid in acceptable if str(cid) != str(matched["chunk_id"])]

        span = qa.get("span", "single")
        if span not in VALID_SPANS:
            span = "single"
        if span == "single":
            acceptable = []

        qtype_map = {
            "scenario": "scenario_judgment", "scenario_judgment": "scenario_judgment",
            "condition": "condition_check", "condition_check": "condition_check",
            "procedure": "procedure", "responsibility": "responsibility",
            "definition": "definition", "comparison": "comparison",
            "case_reasoning": "case_reasoning",
            "announcement": "announcement_interpretation",
            "announcement_interpretation": "announcement_interpretation",
        }
        rdiff_map = {
            "easy": "direct", "direct": "direct",
            "medium": "synonym", "synonym": "synonym",
            "hard": "scenario", "scenario": "scenario",
            "cross_reference": "cross_reference",
        }

        return {
            "id": "",
            "rewrite_group": "",
            "benchmark_level": "canonical",
            "chunk_type": matched.get("chunk_type", ""),
            "law_name": matched.get("law_name", ""),
            "question": str(qa.get("question", "")).strip(),
            "expected_chunk_id": matched["chunk_id"],
            "acceptable_chunk_ids": acceptable,
            "answer": str(qa.get("answer", "")).strip(),
            "question_type": self._normalize(qa.get("question_type", ""), qtype_map, "scenario_judgment"),
            "retrieval_difficulty": self._normalize(qa.get("retrieval_difficulty", ""), rdiff_map, "synonym"),
            "span": span,
        }

    def _build_user_prompt(self, chunks):
        descriptions = []
        for i, c in enumerate(chunks):
            ct = c.get("chunk_type", "")
            text = c.get("text", "") or c.get("retrieval_text", "")
            if len(text) > 1500:
                text = text[:1500] + "..."

            seg = c.get("segment_type", "")
            case_ref = c.get("case_ref", "")
            chapter = c.get("chapter", "")
            section = c.get("section", "")

            meta_extra = f"segment_type: {seg}"
            if case_ref:
                meta_extra += f"\n- case_ref: {case_ref}"
            if chapter:
                meta_extra += f"\n- chapter: {chapter}"
            if section:
                meta_extra += f"\n- section: {section}"

            lo, hi = QUESTIONS_PER_CHUNK

            descriptions.append(
                f"### Chunk {i+1}\n"
                f"- id: {c.get('chunk_id')}\n"
                f"- type: {ct}\n"
                f"- {meta_extra}\n"
                f"- law_name: {c.get('law_name', '')}\n"
                f"- 生成 {lo}-{hi} 个问题\n"
                f"- text:\n```\n{text}\n```"
            )

        return (
            f"为以下 {len(chunks)} 个 Chunk 生成问答对。\n\n"
            + "\n---\n".join(descriptions) +
            "\n\n直接输出 JSON 数组，禁止输出任何推理过程、解释文字或 Markdown 标题。\n"
            "answer 字段必须从 Chunk 文本中提取实质性内容，不得为空字符串。answer 为空则视为无效 QA。"
        )

    def run(self):
        prompt = load_prompt()
        print(f"Prompt: {len(prompt)} chars")

        chunks = load_chunks()
        print(f"Loaded {len(chunks)} total chunks")

        sampled = sample_chunks(chunks, total_limit=self.total_limit)
        if self.dry_run:
            print("\n[Dry-run] 采样完成，未生成 QA。")
            return

        lo, hi = QUESTIONS_PER_CHUNK
        est_total = len(sampled) * (lo + hi) // 2
        print(f"预计生成 {est_total} QA")

        all_qas = list(self.progress.get("generated_qas", []))
        completed_ids = set(self.progress.get("completed_ids", []))

        jsonl_path = OUTPUT_DIR / "v9_canonical.jsonl"
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)

        # Write existing progress to file if starting fresh
        if not all_qas and jsonl_path.exists():
            jsonl_path.unlink()

        remaining = [c for c in sampled if c.get("chunk_id") not in completed_ids]
        print(f"Remaining: {len(remaining)}")

        total_batches = (len(remaining) - 1) // BATCH_SIZE + 1
        for bi in range(0, len(remaining), BATCH_SIZE):
            batch = remaining[bi:bi + BATCH_SIZE]
            bn = bi // BATCH_SIZE + 1
            print(f"  批次 {bn}/{total_batches}...", end=" ", flush=True)

            content = self._call_llm(prompt, self._build_user_prompt(batch))
            if not content:
                print("FAIL (LLM)")
                self._save_progress()
                continue

            qa_list = self._extract_json(content)
            if not qa_list:
                print(f"FAIL (parse) raw: {content[:100]}")
                self._save_progress()
                continue

            batch_valid = 0
            for qa in qa_list:
                fixed = self._validate_and_fix(qa, batch)
                if fixed:
                    all_qas.append(fixed)
                    with open(jsonl_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps(fixed, ensure_ascii=False) + "\n")
                    batch_valid += 1
                    completed_ids.add(fixed["expected_chunk_id"])

            self.progress["generated_qas"] = all_qas
            self.progress["completed_ids"] = list(completed_ids)
            self._save_progress()
            print(f"OK (+{batch_valid})")
            time.sleep(BATCH_DELAY)

        # Finalize: assign IDs
        valid = [q for q in all_qas if q.get("question") and q.get("expected_chunk_id")]
        for i, qa in enumerate(valid):
            qa["id"] = f"qa_v9_{i+1:06d}"
            qa["rewrite_group"] = qa["id"]

        with open(jsonl_path, "w", encoding="utf-8") as f:
            for qa in valid:
                f.write(json.dumps(qa, ensure_ascii=False) + "\n")

        self._print_stats(valid, "V9 Canonical")
        print(f"保存: {jsonl_path} ({len(valid)} 条)")

    def _print_stats(self, qas, label):
        by_type = defaultdict(int)
        by_qtype = defaultdict(int)
        for qa in qas:
            by_type[qa.get("chunk_type", "?")] += 1
            by_qtype[qa.get("question_type", "?")] += 1
        print(f"\n{'='*60}")
        print(f"{label} — {len(qas)} QA")
        print(f"  chunk_type: {dict(by_type)}")
        print(f"  question_type: {dict(by_qtype)}")


# ── Merge logic: replace old pdf_case_paragraph entries with new pdf_case_structured ──

def merge_with_old_benchmark(new_qa_path: str):
    """将新生成的 QA 替换旧 benchmark 中的 pdf_case_paragraph 条目"""
    old_bench_path = PROJ / "data" / "eval_questions" / "v8" / "v8_canonical.jsonl"
    merged_path = OUTPUT_DIR / "v9_canonical.jsonl"

    if not old_bench_path.exists():
        print(f"旧 benchmark 不存在: {old_bench_path}，跳过合并")
        return

    # Load new QA
    new_qas = []
    nqp = Path(new_qa_path)
    if nqp.exists():
        with open(nqp, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    new_qas.append(json.loads(line))
    print(f"新 QA: {len(new_qas)} 条 (pdf_case_structured)")

    # Load old QA, filter out pdf_case_paragraph
    old_qas = []
    removed = 0
    with open(old_bench_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            qa = json.loads(line)
            if qa.get("chunk_type") == "pdf_case_paragraph":
                removed += 1
                continue
            old_qas.append(qa)
    print(f"旧 QA: {len(old_qas)} 条 (移除了 {removed} 条 pdf_case_paragraph)")

    # Merge and renumber
    merged = old_qas + new_qas
    for i, qa in enumerate(merged):
        qa["id"] = f"qa_v9_{i+1:06d}"
        qa["rewrite_group"] = qa["id"]

    with open(merged_path, "w", encoding="utf-8") as f:
        for qa in merged:
            f.write(json.dumps(qa, ensure_ascii=False) + "\n")

    print(f"合并完成: {merged_path} ({len(merged)} 条)")

    # Stats
    by_type = defaultdict(int)
    for qa in merged:
        by_type[qa.get("chunk_type", "?")] += 1
    print("  chunk_type 分布:")
    for ct, cnt in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"    {ct}: {cnt}")


def main():
    parser = argparse.ArgumentParser(description="V8 QA 生成器 — pdf_case_structured 专用")
    parser.add_argument("--total", type=int, default=None, help="限制采样 chunk 数")
    parser.add_argument("--dry-run", action="store_true", help="仅预览采样")
    parser.add_argument("--merge", action="store_true", help="合并新 QA 到旧 benchmark（先运行生成，再加 --merge）")
    args = parser.parse_args()

    if args.merge:
        merge_with_old_benchmark(str(OUTPUT_DIR / "v9_canonical.jsonl"))
        return

    if not CHUNKS_PATH.exists():
        print(f"错误: chunks 文件不存在: {CHUNKS_PATH}")
        sys.exit(1)

    gen = V8QAGenerator(total_limit=args.total, dry_run=args.dry_run)
    gen.run()


if __name__ == "__main__":
    main()
