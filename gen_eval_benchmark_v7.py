#!/usr/bin/env python
"""
V7 Benchmark 生成器 — 三级递进评测体系

Stage 1 (canonical): Chunk → Canonical QA (v7.0_prompt)
Stage 2 (natural):   Canonical QA → Natural Query (v7.1_prompt)
Stage 3 (robust):    Natural QA → Raw Search Query (v7.2_prompt)

输出: 统一 JSONL，含 benchmark_level 和 rewrite_group

用法:
  python gen_eval_benchmark_v7.py --stage 1          # 仅跑 Canonical
  python gen_eval_benchmark_v7.py --stage 2          # 仅跑 Natural 改写
  python gen_eval_benchmark_v7.py --stage 3          # 仅跑 Robust 改写
  python gen_eval_benchmark_v7.py                    # 全量三阶段
  python gen_eval_benchmark_v7.py --dry-run          # 预览抽样分布
  python gen_eval_benchmark_v7.py --total 100        # 小规模测试
"""

import sys, json, random, time, argparse, re
from pathlib import Path
from typing import List, Dict, Optional
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from openai import OpenAI

# ── 路径配置 ──
PROJ = Path(__file__).parent
CHUNKS_PATH = PROJ / "data" / "eval_questions" / "chunks" / "current_chunks.json"
PROMPTS_DIR = PROJ / "data" / "eval_questions" / "prompts"
OUTPUT_DIR = PROJ / "data" / "eval_questions" / "v8"
PROGRESS_DIR = OUTPUT_DIR

GEN_MODEL = "glm-4.5-air"

# ── 采样参数 ──
CHUNK_SAMPLE_CAP = {
    "pdf_law_parent": 200,
    "pdf_law_child": 80,
    "policy_doc": 149,          # 全取
    "pdf_case_paragraph": 200,
    "pdf_case_sliding": 78,     # 全取
    "opinion_news": 100,
}

QUESTIONS_PER_CHUNK = {
    "pdf_law_parent": (3, 5),
    "pdf_law_child": (2, 3),
    "policy_doc": (5, 7),
    "pdf_case_paragraph": (4, 6),
    "pdf_case_sliding": (4, 6),
    "opinion_news": (2, 3),
}

BATCH_SIZE = 6          # 每批 LLM 调用的 chunk 数
REWRITE_BATCH = 8       # 每批 LLM 调用的 QA 数
MAX_RETRIES = 3
RETRY_DELAY = 3
BATCH_DELAY = 1.5

VALID_QUESTION_TYPES = (
    "scenario_judgment", "condition_check", "procedure",
    "responsibility", "definition", "comparison",
    "case_reasoning", "announcement_interpretation",
)
VALID_RETRIEVAL_DIFFICULTIES = ("direct", "synonym", "scenario", "cross_reference")
VALID_SPANS = ("single", "cross_chunk", "cross_doc")


# ── Prompt 加载 ──
def _load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    m = re.search(r'```\n(.*?)```', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    # 如果整个文件就是 prompt（没有代码块包裹）
    if text.strip():
        return text.strip()
    raise RuntimeError(f"未在 {path} 中找到 System Prompt")


# ── 工具 ──
def load_chunks() -> List[dict]:
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["chunks"]


def sample_chunks(chunks: List[dict], total_limit: Optional[int] = None):
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

    total = sum(len(v) for v in sampled.values())
    print("  抽样分布:")
    for ct, items in sampled.items():
        lo, hi = QUESTIONS_PER_CHUNK.get(ct, (1, 2))
        est = len(items) * (lo + hi) // 2
        print(f"    {ct}: {len(items)} chunks, 预计 {est} QA ({lo}-{hi}/chunk)")
    print(f"    总计: {total} chunks")
    return sampled


def prepare_cross_chunk_batch(chunks: List[dict], sampled: dict, count: int) -> List[dict]:
    """从已抽样chunk中构建跨chunk对（同law_name不同chunk_id）"""
    by_law = defaultdict(list)
    all_sampled = []
    for items in sampled.values():
        all_sampled.extend(items)

    for c in all_sampled:
        ln = c.get("law_name", "")
        if ln:
            by_law[ln].append(c)

    pairs = []
    for ln, group in by_law.items():
        if len(group) >= 2:
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    if group[i]["chunk_id"] != group[j]["chunk_id"]:
                        pairs.append((group[i], group[j]))
                        if len(pairs) >= count:
                            break
                if len(pairs) >= count:
                    break
        if len(pairs) >= count:
            break

    return pairs[:count]


def prepare_cross_doc_batch(chunks: List[dict], sampled: dict, count: int) -> List[dict]:
    """从已抽样chunk中构建跨类型对（不同source_doc）"""
    by_source = defaultdict(list)
    all_sampled = []
    for items in sampled.values():
        all_sampled.extend(items)

    for c in all_sampled:
        sd = c.get("source_doc", "")
        if sd:
            by_source[sd].append(c)

    sources = list(by_source.keys())
    pairs = []
    for i in range(len(sources)):
        for j in range(i + 1, len(sources)):
            if by_source[sources[i]] and by_source[sources[j]]:
                pairs.append((by_source[sources[i]][0], by_source[sources[j]][0]))
                if len(pairs) >= count:
                    break
        if len(pairs) >= count:
            break

    return pairs[:count]


# ── 生成器 ──
class V7QAGenerator:
    def __init__(self, total_limit: Optional[int] = None, stage: int = 1):
        self.total_limit = total_limit
        self.stage = stage
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

    def _progress_path(self) -> Path:
        suffix = {1: "canonical", 2: "natural", 3: "robust"}[self.stage]
        return PROGRESS_DIR / f".qa_gen_progress_v8_{suffix}.json"

    def _output_path(self) -> Path:
        suffix = {1: "canonical", 2: "natural", 3: "robust"}[self.stage]
        return OUTPUT_DIR / f"v8_{suffix}.jsonl"

    def _load_progress(self) -> dict:
        pp = self._progress_path()
        if pp.exists():
            with open(pp, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"completed_ids": [], "generated_qas": []}

    def _save_progress(self):
        PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
        with open(self._progress_path(), "w", encoding="utf-8") as f:
            json.dump(self.progress, f, ensure_ascii=False, indent=2)

    def _call_llm(self, system_prompt: str, user_prompt: str) -> Optional[str]:
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
                print(f"  LLM 调用失败 (尝试 {attempt+1}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
        return None

    def _extract_json(self, content: str) -> Optional[list]:
        content = content.strip()

        # 1. Try code blocks
        md_match = re.search(r'```(?:json)?\s*\n?(.*?)```', content, re.DOTALL)
        if md_match:
            content = md_match.group(1).strip()

        if not content:
            return None

        # 2. Direct JSON parse
        try:
            result = json.loads(content)
            if isinstance(result, list):
                result = [r for r in result if isinstance(r, dict)]
                if result:
                    return result
            elif isinstance(result, dict):
                return [result]
        except json.JSONDecodeError:
            pass

        # 3. Find outermost [...] from RIGHT (LLM puts JSON after reasoning)
        #    Count brackets to find valid arrays
        best_result = None
        for start_m in re.finditer(r'\[', content):
            depth = 0
            start = start_m.start()
            for i in range(start, len(content)):
                if content[i] == '[':
                    depth += 1
                elif content[i] == ']':
                    depth -= 1
                    if depth == 0:
                        candidate = content[start:i+1]
                        try:
                            result = json.loads(candidate)
                            if isinstance(result, list):
                                result = [r for r in result if isinstance(r, dict)]
                                if result:
                                    if best_result is None or len(candidate) > len(json.dumps(best_result, ensure_ascii=False)):
                                        best_result = result
                        except json.JSONDecodeError:
                            pass
                        break
        if best_result:
            return best_result

        # 4. Fallback: individual JSON objects (dicts only)
        objects = re.findall(r'\{(?:[^{}]|\{[^{}]*\})*\}', content)
        if objects:
            parsed = []
            for obj in objects:
                try:
                    item = json.loads(obj)
                    if isinstance(item, dict):
                        parsed.append(item)
                except json.JSONDecodeError:
                    continue
            if parsed:
                return parsed

        return None

    # ━━━ Stage 1: Canonical QA 生成 ━━━
    def _build_canonical_user_prompt(self, chunks: List[dict]) -> str:
        descriptions = []
        for i, c in enumerate(chunks):
            ct = c.get("chunk_type", "")
            text = c.get("text", "") or c.get("retrieval_text", "")
            if len(text) > 1200:
                text = text[:1200] + "..."

            parent_info = ""
            if c.get("parent_content"):
                parent_info = f"\n- parent_content: {c['parent_content'][:500]}"

            lo, hi = QUESTIONS_PER_CHUNK.get(ct, (1, 2))

            descriptions.append(
                f"### Chunk {i+1}\n"
                f"- id: {c.get('chunk_id')}\n"
                f"- type: {ct}\n"
                f"- law_name: {c.get('law_name', '')}\n"
                f"- article_id: {c.get('article_id', '')}{parent_info}\n"
                f"- 生成 {lo}-{hi} 个问题\n"
                f"- text:\n```\n{text}\n```"
            )

        return (
            f"为以下 {len(chunks)} 个 Chunk 生成问答对。\n\n"
            + "\n---\n".join(descriptions) +
            "\n\n⚠️ 直接输出 JSON 数组，禁止输出任何推理过程、解释文字或 Markdown 标题。\n"
            "⚠️ answer 字段必须从 Chunk 文本中提取实质性内容，不得为空字符串。answer 为空则视为无效 QA。"
        )

    def _build_cross_user_prompt(self, chunk_pairs: List[tuple], span_type: str) -> str:
        """构建跨chunk或跨文档的用户prompt"""
        descriptions = []
        for i, (c1, c2) in enumerate(chunk_pairs):
            t1 = c1.get("chunk_type", "")
            t2 = c2.get("chunk_type", "")
            text1 = (c1.get("text", "") or c1.get("retrieval_text", ""))[:600]
            text2 = (c2.get("text", "") or c2.get("retrieval_text", ""))[:600]

            descriptions.append(
                f"### Cross Pair {i+1} (span: {span_type})\n"
                f"- Chunk A id: {c1.get('chunk_id')} | type: {t1} | law: {c1.get('law_name','')}\n"
                f"- Chunk A text:\n```\n{text1}\n```\n"
                f"- Chunk B id: {c2.get('chunk_id')} | type: {t2} | law: {c2.get('law_name','')}\n"
                f"- Chunk B text:\n```\n{text2}\n```"
            )

        label = "cross_chunk（同一法规/文档内关联）" if span_type == "cross_chunk" else "cross_doc（跨类型关联，如法规+案例、法规+公告）"

        return (
            f"生成 {len(chunk_pairs)} 个 {label} 问答对。\n"
            f"每个问题需要 Chunk A 和 Chunk B 的信息才能完整回答。\n"
            f"expected_chunk_id 填 Chunk A 的 id，acceptable_chunk_ids 填 Chunk B 的 id。\n\n"
            + "\n---\n".join(descriptions) +
            "\n\n⚠️ 直接输出 JSON 数组，禁止输出任何推理过程、解释文字或 Markdown 标题。\n"
            "⚠️ answer 字段必须综合 Chunk A 和 Chunk B 的内容给出实质性答案，不得为空。"
        )

    def _normalize_qtype(self, raw: str) -> str:
        """标准化 question_type"""
        raw = raw.strip().lower().replace(" ", "_")
        if "," in raw:
            raw = raw.split(",")[0].strip()
        mapping = {
            "scenario": "scenario_judgment", "scenario_judgment": "scenario_judgment",
            "condition": "condition_check", "condition_check": "condition_check",
            "procedure": "procedure", "responsibility": "responsibility",
            "definition": "definition", "comparison": "comparison",
            "case_reasoning": "case_reasoning",
            "announcement": "announcement_interpretation",
            "announcement_interpretation": "announcement_interpretation",
        }
        return mapping.get(raw, "scenario_judgment")

    def _normalize_rdiff(self, raw: str) -> str:
        """标准化 retrieval_difficulty"""
        raw = raw.strip().lower().replace(" ", "_")
        mapping = {
            "easy": "direct", "direct": "direct",
            "medium": "synonym", "synonym": "synonym",
            "hard": "scenario", "scenario": "scenario",
            "cross_reference": "cross_reference",
        }
        return mapping.get(raw, "synonym")

    def _validate_and_fix(self, qa: dict, chunks: List[dict]) -> Optional[dict]:
        """验证并修正 LLM 输出的 QA"""
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

        return {
            "id": "",          # 后处理填充
            "rewrite_group": "",
            "benchmark_level": "canonical",
            "chunk_type": matched.get("chunk_type", ""),
            "law_name": matched.get("law_name", ""),
            "question": str(qa.get("question", "")).strip(),
            "expected_chunk_id": matched["chunk_id"],
            "acceptable_chunk_ids": acceptable,
            "answer": str(qa.get("answer", "")).strip(),
            "question_type": self._normalize_qtype(qa.get("question_type", "")),
            "retrieval_difficulty": self._normalize_rdiff(qa.get("retrieval_difficulty", "")),
            "span": span,
        }

    def _generate_single_chunks(self, chunks: List[dict], prompt: str) -> List[dict]:
        """为 single chunk 生成 QA（每批增量写入 JSONL）"""
        results = []
        total_batches = (len(chunks) - 1) // BATCH_SIZE + 1
        jsonl_path = self._output_path()
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        for bi in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[bi:bi + BATCH_SIZE]
            bn = bi // BATCH_SIZE + 1
            print(f"    批次 {bn}/{total_batches}...", end=" ", flush=True)

            content = self._call_llm(prompt, self._build_canonical_user_prompt(batch))
            if not content:
                print("FAIL (LLM)")
                continue

            qa_list = self._extract_json(content)
            if not qa_list:
                print(f"FAIL (parse) raw: {content[:120]}")
                continue

            batch_valid = 0
            for qa in qa_list:
                fixed = self._validate_and_fix(qa, batch)
                if fixed:
                    results.append(fixed)
                    # 增量写入 JSONL
                    with open(jsonl_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps(fixed, ensure_ascii=False) + "\n")
                    batch_valid += 1

            print(f"OK (+{batch_valid})")
            time.sleep(BATCH_DELAY)

        return results

    def _generate_cross(self, pairs: List[tuple], span_type: str, prompt: str) -> List[dict]:
        """为跨chunk/doc对生成 QA（每批增量写入 JSONL）"""
        results = []
        total_batches = (len(pairs) - 1) // BATCH_SIZE + 1
        jsonl_path = self._output_path()
        for bi in range(0, len(pairs), BATCH_SIZE):
            batch = pairs[bi:bi + BATCH_SIZE]
            bn = bi // BATCH_SIZE + 1
            print(f"    cross {span_type} 批次 {bn}/{total_batches}...", end=" ", flush=True)

            content = self._call_llm(prompt, self._build_cross_user_prompt(batch, span_type))
            if not content:
                print("FAIL (LLM)")
                continue

            qa_list = self._extract_json(content)
            batch_valid = 0
            if qa_list:
                all_chunks_in_batch = []
                seen_ids = set()
                for c1, c2 in batch:
                    for c in (c1, c2):
                        cid = c.get("chunk_id", "")
                        if cid not in seen_ids:
                            all_chunks_in_batch.append(c)
                            seen_ids.add(cid)
                for qa in qa_list:
                    fixed = self._validate_and_fix(qa, all_chunks_in_batch)
                    if fixed:
                        fixed["span"] = span_type
                        results.append(fixed)
                        # 增量写入 JSONL
                        with open(jsonl_path, "a", encoding="utf-8") as f:
                            f.write(json.dumps(fixed, ensure_ascii=False) + "\n")
                        batch_valid += 1

            print(f"OK ({batch_valid})" if qa_list else "FAIL (parse)")
            time.sleep(BATCH_DELAY)

        return results

    def run_stage1(self):
        """Stage 1: 生成 Canonical Benchmark"""
        prompt = _load_prompt("v7.0_prompt.md")
        print(f"Prompt: {len(prompt)} chars")

        chunks = load_chunks()
        print(f"Loaded {len(chunks)} chunks")

        sampled = sample_chunks(chunks, total_limit=self.total_limit)
        all_chunks = []
        for items in sampled.values():
            all_chunks.extend(items)

        # 预估 QA 总数
        est_total = 0
        for ct, items in sampled.items():
            lo, hi = QUESTIONS_PER_CHUNK.get(ct, (1, 2))
            est_total += len(items) * (lo + hi) // 2
        cross_count = max(1, int(est_total * 0.15))
        cross_doc_count = max(1, int(est_total * 0.05))
        print(f"  预计 single QA: {est_total}, cross_chunk: {cross_count}, cross_doc: {cross_doc_count}")

        all_qas = list(self.progress.get("generated_qas", []))
        completed_ids = set(self.progress.get("completed_ids", []))

        # ── Single chunk QA ──
        for ct in ["policy_doc", "pdf_case_paragraph", "pdf_case_sliding",
                    "pdf_law_parent", "pdf_law_child", "opinion_news"]:
            items = sampled.get(ct, [])
            if not items:
                continue
            remaining = [c for c in items if c.get("chunk_id") not in completed_ids]
            if not remaining:
                print(f"  [{ct}] 全部已完成")
                continue

            print(f"\n  [{ct}] {len(remaining)} chunks...")
            new_qas = self._generate_single_chunks(remaining, prompt)
            if new_qas:
                all_qas.extend(new_qas)
                for nq in new_qas:
                    completed_ids.add(nq["expected_chunk_id"])
                self.progress["generated_qas"] = all_qas
                self.progress["completed_ids"] = list(completed_ids)
                self._save_progress()
            print(f"    小计: {len(all_qas)} QA")

        # ── Cross chunk QA (15%) ──
        print(f"\n  [cross_chunk] 生成...")
        cross_pairs = prepare_cross_chunk_batch(chunks, sampled, cross_count)
        if cross_pairs:
            new_qas = self._generate_cross(cross_pairs, "cross_chunk", prompt)
            if new_qas:
                all_qas.extend(new_qas)
                self.progress["generated_qas"] = all_qas
                self._save_progress()

        # ── Cross doc QA (5%) ──
        print(f"\n  [cross_doc] 生成...")
        cross_doc_pairs = prepare_cross_doc_batch(chunks, sampled, cross_doc_count)
        if cross_doc_pairs:
            new_qas = self._generate_cross(cross_doc_pairs, "cross_doc", prompt)
            if new_qas:
                all_qas.extend(new_qas)
                self.progress["generated_qas"] = all_qas
                self._save_progress()

        # ── 后处理 ──
        valid = []
        for qa in all_qas:
            if qa.get("question") and qa.get("expected_chunk_id"):
                valid.append(qa)
        for i, qa in enumerate(valid):
            qa["id"] = f"qa_v8_{i+1:06d}"
            qa["rewrite_group"] = qa["id"]

        self._save_jsonl(valid)
        self._print_stats(valid, "V7 Canonical")

    # ━━━ Stage 2 & 3: 改写 ━━━
    def _build_rewrite_user_prompt(self, qas: List[dict], natural_map: dict = None) -> str:
        items = []
        for i, qa in enumerate(qas):
            rg = qa.get('rewrite_group')
            parts = [
                f"### QA {i+1}",
                f"- rewrite_group: {rg}",
                f"- question (Canonical): {qa['question']}",
            ]
            if natural_map and rg in natural_map:
                parts.append(f"- Natural 版本 (已使用，请避免雷同): {natural_map[rg]}")
            parts.append(f"- expected_chunk_id: {qa['expected_chunk_id']}")
            parts.append(f"- answer: {qa['answer'][:200]}")
            items.append("\n".join(parts))

        note = ""
        if natural_map:
            note = "\n每个 QA 提供了 Canonical 原版和 Natural 改写版。你的任务是产出与两者都不同的 Robust 版本——更短、更关键词化，不要重复 Natural 的口语风格。\n"
        return (
            f"改写以下 {len(qas)} 个问题的 question。只输出 question 和 rewrite_group，其余字段不变。{note}\n"
            + "\n---\n".join(items) +
            "\n\n⚠️ 直接输出 JSON 数组，禁止输出任何推理过程、解释文字或 Markdown 标题。\n"
            "输出格式: [{\"rewrite_group\": \"...\", \"question\": \"改写后的搜索Query\"}]"
        )

    def run_rewrite_stage(self, stage: int):
        """Stage 2/3: 改写已有 QA，增量保存"""
        prompt_file = {2: "v7.1_prompt.md", 3: "v7.2_prompt.md"}[stage]
        level = {2: "natural", 3: "robust"}[stage]
        label = {2: "V7 Natural", 3: "V7 Robust"}[stage]
        in_level = {2: "canonical", 3: "canonical"}[stage]
        in_file = {2: "canonical", 3: "canonical"}[stage]

        prompt = _load_prompt(prompt_file)

        input_path = OUTPUT_DIR / f"v8_{in_file}.jsonl"
        if not input_path.exists():
            print(f"错误: 输入文件不存在 {input_path}，请先运行上一步")
            return

        input_qas = []
        with open(input_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    input_qas.append(json.loads(line))
        print(f"已加载 {len(input_qas)} 条 {in_level} QA")

        # Stage 3: 加载 Natural 版本用于参考（避免雷同）
        natural_map = {}
        if stage == 3:
            natural_path = OUTPUT_DIR / "v8_natural.jsonl"
            if natural_path.exists():
                with open(natural_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            nq = json.loads(line)
                            rg = nq.get("rewrite_group", "")
                            if rg:
                                natural_map[rg] = nq.get("question", "")
                print(f"已加载 {len(natural_map)} 条 Natural 版本作为参考")
            else:
                print("警告: Natural 版本不存在，将仅基于 Canonical 改写")

        completed_groups = set(self.progress.get("completed_groups", []))
        remaining = [q for q in input_qas if q.get("rewrite_group") not in completed_groups]

        if self.total_limit:
            remaining = remaining[:self.total_limit]

        if not remaining:
            print("  全部已完成")
            return

        # 增量输出路径
        out_path = self._output_path()
        # 加载已有输出（断点续跑）
        all_qas = []
        if out_path.exists():
            with open(out_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        all_qas.append(json.loads(line))

        total_batches = (len(remaining) - 1) // REWRITE_BATCH + 1

        for bi in range(0, len(remaining), REWRITE_BATCH):
            batch = remaining[bi:bi + REWRITE_BATCH]
            bn = bi // REWRITE_BATCH + 1
            print(f"  批次 {bn}/{total_batches}...", end=" ", flush=True)

            content = self._call_llm(prompt, self._build_rewrite_user_prompt(batch, natural_map if stage == 3 else None))
            if not content:
                print("FAIL")
                self.progress["completed_groups"] = list(completed_groups)
                self._save_progress()
                continue

            rewritten = self._extract_json(content)
            if not rewritten:
                print(f"FAIL (parse)")
                self.progress["completed_groups"] = list(completed_groups)
                self._save_progress()
                continue

            group_map = {q["rewrite_group"]: q for q in batch}
            matched = 0
            for rw in rewritten:
                rg = rw.get("rewrite_group", "")
                if rg in group_map:
                    orig = group_map[rg]
                    new_qa = dict(orig)
                    new_qa["question"] = str(rw.get("question", orig["question"])).strip()
                    new_qa["benchmark_level"] = level
                    all_qas.append(new_qa)
                    # 增量写入输出文件
                    with open(out_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps(new_qa, ensure_ascii=False) + "\n")
                    completed_groups.add(rg)
                    matched += 1

            self.progress["completed_groups"] = list(completed_groups)
            self._save_progress()
            print(f"OK ({matched})")
            time.sleep(BATCH_DELAY)

        self._print_stats(all_qas, label)

        # 合并到统一 JSONL
        self._merge_all_levels()

    def _save_jsonl(self, qas: List[dict]):
        out_path = self._output_path()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            for qa in qas:
                f.write(json.dumps(qa, ensure_ascii=False) + "\n")
        print(f"  保存: {out_path} ({len(qas)} 条)")

    def _merge_all_levels(self):
        """合并 canonical + natural + robust 到统一 JSONL"""
        merged_path = OUTPUT_DIR / "v8_benchmark.jsonl"
        all_qas = []
        seen = set()

        for level, file_suffix in [("canonical", "canonical"), ("natural", "natural"), ("robust", "robust")]:
            fp = OUTPUT_DIR / f"v8_{file_suffix}.jsonl"
            if fp.exists():
                with open(fp, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            qa = json.loads(line)
                            key = (qa.get("rewrite_group", ""), qa.get("benchmark_level", ""))
                            if key not in seen:
                                all_qas.append(qa)
                                seen.add(key)

        with open(merged_path, "w", encoding="utf-8") as f:
            for qa in all_qas:
                f.write(json.dumps(qa, ensure_ascii=False) + "\n")
        print(f"  合并: {merged_path} ({len(all_qas)} 条)")

    def _print_stats(self, qas: List[dict], label: str):
        by_type = defaultdict(int)
        by_qtype = defaultdict(int)
        by_rdiff = defaultdict(int)
        by_span = defaultdict(int)
        by_level = defaultdict(int)
        for qa in qas:
            by_type[qa.get("chunk_type", "?")] += 1
            by_qtype[qa.get("question_type", "?")] += 1
            by_rdiff[qa.get("retrieval_difficulty", "?")] += 1
            by_span[qa.get("span", "?")] += 1
            by_level[qa.get("benchmark_level", "?")] += 1

        print(f"\n{'='*60}")
        print(f"{label} — 统计")
        print(f"{'='*60}")
        print(f"  Total: {len(qas)}")
        print(f"  chunk_type: {dict(by_type)}")
        print(f"  question_type: {dict(by_qtype)}")
        print(f"  retrieval_difficulty: {dict(by_rdiff)}")
        print(f"  span: {dict(by_span)}")
        if len(by_level) > 1:
            print(f"  benchmark_level: {dict(by_level)}")

    # ━━━ Supplement: 针对性补充 ━━━
    def run_supplement(self):
        """针对性补充缺口 chunk 的 QA，批量增量保存不怕中断"""
        prompt = _load_prompt("v7.0_prompt.md")
        manifest_path = OUTPUT_DIR / ".supplement_manifest.json"
        if not manifest_path.exists():
            print("错误: 未找到 supplement manifest")
            return

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        # 加载补充进度
        sp_path = OUTPUT_DIR / ".supplement_progress.json"
        if sp_path.exists():
            with open(sp_path, "r", encoding="utf-8") as f:
                sp = json.load(f)
        else:
            sp = {"completed_indices": [], "new_qa_count": 0}

        completed_set = set(sp["completed_indices"])
        remaining_items = [m for i, m in enumerate(manifest) if i not in completed_set]
        total_needed = sum(m["needed"] for m in remaining_items)
        print(f"加载 {len(manifest)} 个待补充 chunk，已完成 {len(completed_set)}，剩余 {total_needed} QA")

        # 加载现有 JSONL
        jsonl_path = self._output_path()
        existing_count = 0
        if jsonl_path.exists():
            with open(jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        existing_count += 1

        new_in_run = 0

        # 按 chunk_type 分组批量处理
        by_ct = defaultdict(list)
        for i, m in enumerate(manifest):
            if i not in completed_set:
                by_ct[m["chunk"]["chunk_type"]].append((i, m))

        for ct, indexed_items in by_ct.items():
            total_batches = (len(indexed_items) - 1) // BATCH_SIZE + 1
            print(f"\n  [{ct}] {len(indexed_items)} chunks...")
            for bi in range(0, len(indexed_items), BATCH_SIZE):
                batch = indexed_items[bi:bi + BATCH_SIZE]
                bn = bi // BATCH_SIZE + 1
                batch_items = [m for _, m in batch]
                print(f"    批次 {bn}/{total_batches}...", end=" ", flush=True)

                batch_chunks = [m["chunk"] for m in batch_items]
                batch_existing_qs = set()
                for m in batch_items:
                    batch_existing_qs.update(m["existing_questions"])

                # 加载当前所有已有 question
                all_existing_qs = set()
                if jsonl_path.exists():
                    with open(jsonl_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    qa = json.loads(line)
                                    all_existing_qs.add(qa.get("question", ""))
                                except json.JSONDecodeError:
                                    pass

                valid_new = 0
                empty_retries = 0
                fail_reason = ""
                user_prompt = self._build_supplement_user_prompt(batch_items)

                while empty_retries < 3:
                    content = self._call_llm(prompt, user_prompt)
                    if not content:
                        fail_reason = "LLM"
                        break

                    qa_list = self._extract_json(content)
                    if not qa_list:
                        fail_reason = "parse"
                        break

                    valid_new = 0
                    has_empty = False
                    for qa in qa_list:
                        fixed = self._validate_and_fix(qa, batch_chunks)
                        if fixed:
                            q_text = fixed["question"]
                            if not fixed["answer"] or len(fixed["answer"].strip()) < 3:
                                has_empty = True
                                continue
                            if q_text not in all_existing_qs and q_text not in batch_existing_qs:
                                fixed["id"] = f"qa_v8_{existing_count + new_in_run + 1:06d}"
                                fixed["rewrite_group"] = fixed["id"]
                                with open(jsonl_path, "a", encoding="utf-8") as f:
                                    f.write(json.dumps(fixed, ensure_ascii=False) + "\n")
                                all_existing_qs.add(q_text)
                                valid_new += 1

                    if has_empty and empty_retries < 2:
                        empty_retries += 1
                        user_prompt = user_prompt + f"\n\n【重试第{empty_retries}次】上轮有 QA 的 answer 为空。必须从 Chunk 原文摘录答案，每条 answer 至少15字。"
                        time.sleep(1)
                        continue
                    break

                if fail_reason:
                    print(f"FAIL ({fail_reason})", end=" ")
                elif valid_new == 0:
                    print(f"FAIL (empty after {empty_retries} retries)", end=" ")

                new_in_run += valid_new
                for idx, _ in batch:
                    sp["completed_indices"].append(idx)
                sp["new_qa_count"] = sp.get("new_qa_count", 0) + valid_new
                self._save_supplement_progress(sp_path, sp)
                print(f"OK (+{valid_new}) 累计新增: {new_in_run}")
                time.sleep(BATCH_DELAY)

        # 最终重编号
        all_qas = []
        if jsonl_path.exists():
            with open(jsonl_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        all_qas.append(json.loads(line))
        for i, qa in enumerate(all_qas):
            qa["id"] = f"qa_v8_{i+1:06d}"
            if not qa.get("rewrite_group"):
                qa["rewrite_group"] = qa["id"]

        with open(jsonl_path, "w", encoding="utf-8") as f:
            for qa in all_qas:
                f.write(json.dumps(qa, ensure_ascii=False) + "\n")

        self._print_stats(all_qas, "V7 Canonical (补充后)")
        print(f"\n  原有: {existing_count}, 新增: {new_in_run}, 合并: {len(all_qas)}")

        # 清理进度文件
        if sp_path.exists():
            sp_path.unlink()

    def _save_supplement_progress(self, sp_path, sp):
        """保存补充进度"""
        sp_path.parent.mkdir(parents=True, exist_ok=True)
        with open(sp_path, "w", encoding="utf-8") as f:
            json.dump(sp, f, ensure_ascii=False)

    def _build_supplement_user_prompt(self, items: List[dict]) -> str:
        """构建补充生成的 user prompt，包含已有 QA 防止重复"""
        descriptions = []
        for i, m in enumerate(items):
            c = m["chunk"]
            ct = c.get("chunk_type", "")
            text = (c.get("text", "") or c.get("retrieval_text", ""))[:1200]
            needed = m["needed"]
            existing = m["existing_questions"]

            parent_info = ""
            if c.get("parent_content"):
                parent_info = f"\n- parent_content: {c['parent_content'][:500]}"

            existing_str = "\n".join(f"  {j+1}. {q}" for j, q in enumerate(existing))

            descriptions.append(
                f"### Chunk {i+1}\n"
                f"- id: {c.get('chunk_id')}\n"
                f"- type: {ct}\n"
                f"- law_name: {c.get('law_name', '')}\n"
                f"- article_id: {c.get('article_id', '')}{parent_info}\n"
                f"- text:\n```\n{text}\n```\n"
                f"### 已有问题 (禁止重复):\n{existing_str}\n"
                f"### 需要补充: {needed} 个与已有问题不同角度的新问题"
            )

        return (
            f"为以下 {len(items)} 个 Chunk 补充生成问答对。\n"
            f"每个 Chunk 需补充指定数量的新问题。新问题必须从不同角度出发，严格禁止与已有问题重复。\n\n"
            + "\n---\n".join(descriptions) +
            "\n\n⚠️ 直接输出 JSON 数组，禁止输出任何推理过程、解释文字或 Markdown 标题。\n"
            "⚠️ answer 是必填字段，必须从 Chunk text 中摘录至少15字的具体原文内容。answer 为空字符串的 QA 直接作废，整批重做。\n"
            "⚠️ question 不得与已有问题语义相同或高度相似。"
        )

    def run(self):
        if self.stage == 1 and self.total_limit == -1:
            print("=" * 60)
            print("V7 Stage 1 — Canonical 针对性补充")
            print("=" * 60)
            self.run_supplement()
        elif self.stage == 1:
            print("=" * 60)
            print("V7 Stage 1 — Canonical Benchmark 生成")
            print("=" * 60)
            self.run_stage1()
        elif self.stage in (2, 3):
            label = {2: "Natural Query 改写", 3: "Raw Search Query 改写"}[self.stage]
            print("=" * 60)
            print(f"V7 Stage {self.stage} — {label}")
            print("=" * 60)
            self.run_rewrite_stage(self.stage)


def main():
    parser = argparse.ArgumentParser(description="V7 Benchmark 三级递进生成器")
    parser.add_argument("--stage", type=int, choices=[1, 2, 3], default=1,
                        help="1=Canonical, 2=Natural, 3=Robust")
    parser.add_argument("--dry-run", action="store_true", help="仅预览抽样分布")
    parser.add_argument("--total", type=int, default=None, help="限制 QA 数量（测试用）")
    parser.add_argument("--resume", action="store_true", help="从断点继续")
    parser.add_argument("--supplement", action="store_true", help="针对性补充缺口 chunk QA")
    args = parser.parse_args()

    if args.supplement:
        manifest = PROGRESS_DIR / ".supplement_manifest.json"
        if not manifest.exists():
            print("错误: 先运行主生成脚本产生已有 QA，再运行补充")
            sys.exit(1)
        # total_limit=-1 triggers supplement mode
        generator = V7QAGenerator(total_limit=-1, stage=1)
        generator.run()
        return

    if not CHUNKS_PATH.exists():
        print(f"错误: chunks 文件不存在: {CHUNKS_PATH}")
        print("请先运行: python export_chunks.py")
        sys.exit(1)

    if args.dry_run:
        chunks = load_chunks()
        print(f"Chunks 总数: {len(chunks)}")
        sample_chunks(chunks, total_limit=args.total)
        return

    if not args.resume:
        gp = V7QAGenerator(total_limit=args.total, stage=args.stage)
        pp = gp._progress_path()
        if pp.exists():
            pp.unlink()

    generator = V7QAGenerator(total_limit=args.total, stage=args.stage)
    generator.run()


if __name__ == "__main__":
    main()
