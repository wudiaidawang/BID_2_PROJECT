#!/usr/bin/env python
"""
eval_benchmark_v5 生成器 — 基于 V4.2 章上下文 Chunk 生成 2500 QA 对

V4.2 变化:
  - child chunk 已淘汰，所有法条以完整文本参与检索
  - 检索单元: pdf_law_parent（完整法条）
  - 上下文父块: 整章拼接（chapter_context），检索命中后注入 parent_content

QA 分布:
  - 70% 单Chunk (1750)
  - 20% 父子Chunk (500)  — 需要法条+章上下文才能完整回答
  - 10% 跨Chunk (250)   — 相邻法条关联问题

30% 题目必须显式包含: 法规名称 / 法规简称 / 行业术语 / 专项监管对象

用法:
  python gen_eval_benchmark_v5.py
  python gen_eval_benchmark_v5.py --dry-run
  python gen_eval_benchmark_v5.py --total 100
"""

import sys
import json
import random
import time
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from openai import OpenAI

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
CHUNKS_PATH = Path(__file__).parent / "data" / "eval_questions" / "policy_chunks_export_v5.json"
OUTPUT_PATH = Path(__file__).parent / "data" / "eval_questions" / "eval_benchmark_v5.json"
PROGRESS_PATH = Path(__file__).parent / "data" / "eval_questions" / ".qa_gen_progress_v5.json"

BATCH_SIZE = 5
CROSS_BATCH_SIZE = 4
PARENT_CHILD_BATCH_SIZE = 4
MAX_RETRIES = 3
RETRY_DELAY = 3
BATCH_DELAY = 1.5

GEN_MODEL = "GLM-4.1V-Thinking-FlashX"

TOTAL_TARGET = 2500

# 70% / 20% / 10%
SINGLE_COUNT = int(TOTAL_TARGET * 0.70)   # 1750
PARENT_CHILD_COUNT = int(TOTAL_TARGET * 0.20)  # 500
CROSS_COUNT = TOTAL_TARGET - SINGLE_COUNT - PARENT_CHILD_COUNT  # 250

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def load_chunks() -> List[dict]:
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["chunks"]


def build_chapter_contexts(parent_chunks: List[dict]) -> Dict[str, str]:
    """本地重建章上下文: 按 (law_name, chapter) 分组拼接法条"""
    groups = defaultdict(list)
    for c in parent_chunks:
        law = c.get("law_name", "")
        chapter = c.get("chapter", "")
        groups[(law, chapter)].append(c)

    contexts = {}
    for (law, chapter), group in groups.items():
        group.sort(key=lambda x: int(x.get("article_id", 0) or 0))
        parts = []
        for p in group:
            header_parts = [f"《{law}》"]
            if chapter:
                header_parts.append(chapter)
            header_parts.append(p.get("article_id", ""))
            header = "\n".join(header_parts)
            parts.append(f"{header}\n{p.get('text', '')}")
        ctx = "\n\n".join(parts)
        for p in group:
            contexts[p["id"]] = ctx
    return contexts


def validate_qa(qa: dict) -> List[str]:
    errors = []
    required = ["id", "question", "expected_chunk_id", "type", "category",
                "difficulty", "expected_source_type", "expected_answer_text"]
    for field in required:
        if field not in qa:
            errors.append(f"缺少字段: {field}")
    if "acceptable_chunk_ids" not in qa:
        errors.append("缺少字段: acceptable_chunk_ids")
    valid_types = ("pdf_law_parent", "pdf_case_paragraph", "policy_doc",
                   "opinion_news", "cross_chunk", "parent_child")
    if qa.get("type") not in valid_types:
        errors.append(f"无效 type: {qa.get('type')}")
    return errors


# ---------------------------------------------------------------------------
# 抽样逻辑
# ---------------------------------------------------------------------------
def sample_chunks(chunks: List[dict], total_limit: Optional[int] = None):
    by_type = defaultdict(list)
    for c in chunks:
        ct = c.get("chunk_type", "other")
        by_type[ct].append(c)

    random.seed(42)

    def _limit(n: int) -> int:
        if total_limit:
            return max(1, int(n * total_limit / TOTAL_TARGET))
        return n

    # ── 单Chunk 抽样 ──
    # 按类型比例分配 1750 个
    parent_chunks = by_type.get("pdf_law_parent", [])
    case_chunks = by_type.get("pdf_case_paragraph", [])
    policy_docs = by_type.get("policy_doc", [])
    opinions = by_type.get("opinion_news", [])

    total_non_cross = len(parent_chunks) + len(case_chunks) + len(policy_docs) + len(opinions)
    n_single = _limit(SINGLE_COUNT)

    def _proportional_sample(pool, total_pool, target):
        n = max(1, int(target * len(pool) / total_pool))
        return random.sample(pool, min(n, len(pool)))

    single_samples = {}
    single_samples["pdf_law_parent"] = _proportional_sample(parent_chunks, total_non_cross, n_single)
    single_samples["pdf_case_paragraph"] = _proportional_sample(case_chunks, total_non_cross, n_single)
    single_samples["policy_doc"] = _proportional_sample(policy_docs, total_non_cross, n_single)
    single_samples["opinion_news"] = _proportional_sample(opinions, total_non_cross, n_single)

    actual_single = sum(len(v) for v in single_samples.values())
    # 补足差额
    shortfall = n_single - actual_single
    big_pool = parent_chunks
    if shortfall > 0:
        selected_ids = {c["id"] for items in single_samples.values() for c in items}
        extra = random.sample([c for c in big_pool if c["id"] not in selected_ids],
                              min(shortfall, len(big_pool) - len(selected_ids)))
        single_samples["pdf_law_parent"].extend(extra)

    # ── 父子Chunk 抽样 ──
    # 只从有章上下文的 parent 中挑选
    parents_with_chapter = [c for c in parent_chunks if c.get("chapter", "")]
    n_pc = _limit(PARENT_CHILD_COUNT)
    n_pc = min(n_pc, len(parents_with_chapter))
    pc_samples = random.sample(parents_with_chapter, n_pc)

    # ── 跨Chunk 抽样 ──
    by_law = defaultdict(list)
    for c in parent_chunks:
        law = c.get("law_name", "")
        aid = c.get("article_id", "")
        if law and aid:
            try:
                by_law[law].append((int(aid), c))
            except (ValueError, TypeError):
                pass
    cross_pairs = []
    seen = set()
    for law, articles in by_law.items():
        articles.sort(key=lambda x: x[0])
        for i in range(len(articles) - 1):
            aid_a, c_a = articles[i]
            aid_b, c_b = articles[i + 1]
            if aid_b - aid_a <= 2:
                key = (c_a["id"], c_b["id"])
                if key not in seen:
                    seen.add(key)
                    cross_pairs.append((c_a, c_b))
    random.shuffle(cross_pairs)
    n_cross = _limit(CROSS_COUNT)
    cross_pairs = cross_pairs[:n_cross]

    return single_samples, pc_samples, cross_pairs


# ---------------------------------------------------------------------------
# QA 生成 Prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT_SINGLE = """你是一名资深法规评测工程师。

请根据给定的法规 Chunk 生成高质量问答对，用于检索增强生成（RAG）系统评测。

## 输出格式
严格输出 JSON 数组，每个元素包含以下字段：
{
  "question": "模拟真实用户自然语言问题",
  "expected_chunk_id": "该问题唯一正确的 chunk_id",
  "acceptable_chunk_ids": ["其他也可接受的 chunk_id"],
  "answer": "用简洁准确的一句话给出标准答案",
  "difficulty": "easy|medium|hard"
}

## 生成要求

1. 问题必须模拟真实用户提问习惯，不要照抄法条原文。

2. 优先生成用户实际会搜索的问题，而不是考试题或法条复述题。

3. 问题应尽量体现法规名称、业务场景、行业术语、监管对象等信息。

4. 充分利用 law_name、chapter、article_id 等 Metadata 构造问题，不要仅依据正文内容提问。

5. 问题应能唯一定位到当前 Chunk 所包含的信息。

6. 不要出现：
   * "根据本条规定"
   * "依据上述内容"
   * "该条款指出"
   * "文中提到"
   * "第几条规定什么"
   等依赖上下文的问题。

7. 如果法规属于行业专项法规，应尽量体现行业特征词。

例如：
法规：《收费公路管理条例》
不要生成：收费期限是多少？
应生成：收费公路收费期限最长可以设定多久？

法规：《道路客运班线经营管理规定》
不要生成：许可期限多久？
应生成：道路客运班线经营许可的有效期限是多久？

法规：《定点采购管理办法》
不要生成：供应商如何确定？
应生成：定点采购项目中供应商应如何确定？

8. 答案必须严格依据当前 Chunk 内容生成，不允许补充法规外知识。

9. 答案应简洁准确，保留关键条件、主体、期限、金额、比例等要素。

10. 如果当前 Chunk 信息不足以形成独立问答，则返回 null。

11. 每个片段生成一个问答对。"""

SYSTEM_PROMPT_PARENT_CHILD = """你是一名资深法规评测工程师。

请根据给定的法条 Chunk 及其所在章上下文，生成需要同时参考法条原文和章级别上下文才能完整回答的问题。

## 输出格式
严格输出 JSON 数组，每个元素包含以下字段：
{
  "question": "模拟真实用户自然语言问题（需要法条+章上下文才能完整回答）",
  "expected_chunk_id": "核心法条的 chunk_id",
  "acceptable_chunk_ids": [],
  "answer": "综合法条和章上下文给出完整答案",
  "difficulty": "easy|medium|hard"
}

## 生成要求

1. 问题必须模拟真实用户提问习惯，不要照抄法条原文。
2. 问题应该需要理解该法条在整章中的位置、与其他法条的关系，或需要章级别的背景信息才能完整回答。
3. 充分利用 law_name、chapter、article_id 等 Metadata 构造问题。
4. 问题应能唯一定位到当前 Chunk 所包含的信息。
5. 禁止出现"根据本条规定""依据上述内容"等依赖上下文的问题。
6. 答案必须严格依据提供的内容，不允许补充法规外知识。
7. 答案应简洁准确，保留关键条件、主体、期限等要素。
8. 每个片段生成一个问答对。"""

SYSTEM_PROMPT_CROSS = """你是一名资深法规评测工程师。

请根据给定的两个相邻法条 Chunk，生成需要同时参考两个法条才能回答的问题。

## 输出格式
严格输出 JSON 数组，每个元素包含以下字段：
{
  "question": "模拟真实用户自然语言问题（需要两个法条的信息才能完整回答）",
  "expected_chunk_id": "第一个法条（主）的 chunk_id",
  "acceptable_chunk_ids": ["第二个法条的 chunk_id"],
  "answer": "综合两个法条信息给出完整答案",
  "difficulty": "easy|medium|hard"
}

## 生成要求
1. 问题必须模拟真实用户提问习惯。
2. 问题应需要两个法条的信息才能完整回答（对比、条件关系、程序衔接、定义+例外等）。
3. 充分利用 law_name、article_id 等 Metadata 构造问题。
4. 禁止出现"根据本条规定"等依赖上下文的问题。
5. 答案必须严格依据提供的内容。
6. 每个片段对生成一个问答对。"""


# ---------------------------------------------------------------------------
# QA 生成器
# ---------------------------------------------------------------------------
class QAGenerator:
    def __init__(self, total_limit: Optional[int] = None):
        self.total_limit = total_limit
        self._init_client()
        self.progress = self._load_progress()
        self.chapter_contexts = {}

    def _init_client(self):
        from config import settings
        api_key = settings.llm_api_key
        api_url = settings.llm_api_url
        base_url = api_url.replace("/chat/completions", "")
        if not api_key:
            raise RuntimeError(f"LLM_API_KEY 未设置")
        self._model = GEN_MODEL
        self.client = OpenAI(base_url=base_url, api_key=api_key)

    def _load_progress(self) -> dict:
        if PROGRESS_PATH.exists():
            with open(PROGRESS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"completed_ids": [], "generated_qas": [], "total_generated": 0,
                "single_done": 0, "pc_done": 0, "cross_done": 0}

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

    def _extract_json(self, content: str) -> Optional[list]:
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
        except json.JSONDecodeError:
            import re
            match = re.search(r'\[.*\]', content, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
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
        elif ct == "pdf_case_paragraph":
            return "案例"
        elif ct == "policy_doc":
            return "政策文件"
        elif ct == "opinion_news":
            return "观点新闻"
        return "其他"

    def _infer_sub_category(self, chunk: dict) -> str:
        law = chunk.get("law_name", "") or chunk.get("source_doc", "") or ""
        ct = chunk.get("chunk_type", "")
        if ct == "pdf_law_parent":
            if "招标" in law or "投标" in law:
                return "招投标法"
            elif "政府采购" in law:
                return "政府采购法"
            else:
                return "其他法规"
        elif ct == "pdf_case_paragraph":
            return "法律案例"
        elif ct == "policy_doc":
            return "政策文件"
        elif ct == "opinion_news":
            return "舆情新闻"
        return "其他"

    def _build_single_prompt(self, chunks: List[dict]) -> str:
        descriptions = []
        for i, c in enumerate(chunks):
            text = c.get("text", "") or c.get("retrieval_text", "")
            if len(text) > 1200:
                text = text[:1200] + "..."
            law = c.get("law_name", "") or c.get("source_doc", "") or "未知"
            chapter = c.get("chapter", "") or "无章节"
            aid = c.get("article_id", "") or "N/A"
            ct = c.get("chunk_type", "")
            descriptions.append(
                f"### 片段 {i+1}\n"
                f"- chunk_id: {c.get('id')}\n"
                f"- law_name: {law}\n"
                f"- chapter: {chapter}\n"
                f"- article_id: {aid}\n"
                f"- chunk_type: {ct}\n"
                f"- 文本内容:\n```\n{text}\n```"
            )

        type_desc = {
            "pdf_law_parent": "法规原文完整法条",
            "pdf_case_paragraph": "案例段落",
            "policy_doc": "政策文件",
            "opinion_news": "观点新闻",
        }
        ct_val = chunks[0].get("chunk_type", "") if chunks else ""
        td = type_desc.get(ct_val, ct_val)

        return (
            f"请为以下 {len(chunks)} 个{td}各生成一个问答对。\n\n"
            + "\n---\n".join(descriptions) +
            "\n\n请输出 JSON 数组，按片段顺序排列。"
        )

    def _build_pc_prompt(self, chunks: List[dict]) -> str:
        descriptions = []
        for i, c in enumerate(chunks):
            text = c.get("text", "") or c.get("retrieval_text", "")
            if len(text) > 1000:
                text = text[:1000] + "..."
            law = c.get("law_name", "") or "未知"
            chapter = c.get("chapter", "") or "无章节"
            aid = c.get("article_id", "") or "N/A"
            cc = self.chapter_contexts.get(c.get("id"), "")
            if len(cc) > 2000:
                cc = cc[:2000] + "..."
            descriptions.append(
                f"### 法条 {i+1}\n"
                f"- chunk_id: {c.get('id')}\n"
                f"- law_name: {law}\n"
                f"- chapter: {chapter}\n"
                f"- article_id: {aid}\n"
                f"- 法条原文:\n```\n{text}\n```\n"
                f"- 所在章的完整上下文:\n```\n{cc}\n```"
            )

        return (
            f"请为以下 {len(chunks)} 个法条各生成一个需要法条+章上下文才能完整回答的问答对。\n\n"
            + "\n---\n".join(descriptions) +
            "\n\n请输出 JSON 数组，按片段顺序排列。"
        )

    def _build_cross_prompt(self, pairs: List[Tuple[dict, dict]]) -> str:
        descriptions = []
        for i, (c_a, c_b) in enumerate(pairs):
            law = c_a.get("law_name", "") or "未知"
            aid_a = c_a.get("article_id", "")
            aid_b = c_b.get("article_id", "")
            text_a = c_a.get("text", "") or c_a.get("retrieval_text", "")
            text_b = c_b.get("text", "") or c_b.get("retrieval_text", "")
            if len(text_a) > 800:
                text_a = text_a[:800] + "..."
            if len(text_b) > 800:
                text_b = text_b[:800] + "..."
            descriptions.append(
                f"### 法条对 {i+1}\n"
                f"- 法律: {law}\n"
                f"- 法条 {aid_a} (chunk_id: {c_a.get('id')}):\n```\n{text_a}\n```\n"
                f"- 法条 {aid_b} (chunk_id: {c_b.get('id')}):\n```\n{text_b}\n```"
            )
        return (
            f"请为以下 {len(pairs)} 对相邻法条各生成一个跨法条问答对。\n\n"
            + "\n---\n".join(descriptions) +
            "\n\n请输出 JSON 数组，按片段对顺序排列。"
        )

    def generate_single_batch(self, chunks: List[dict], start_idx: int) -> List[dict]:
        if not chunks:
            return []
        content = self._call_llm(SYSTEM_PROMPT_SINGLE, self._build_single_prompt(chunks))
        if not content:
            return []
        qa_list = self._extract_json(content)
        if not qa_list:
            print(f"  JSON 解析失败，原始响应: {content[:300]}")
            return []

        results = []
        for i, qa in enumerate(qa_list):
            if qa is None:
                continue
            if i >= len(chunks):
                break
            chunk = chunks[i]
            qid = f"qa_v5_{start_idx + i + 1:04d}"
            # ★ 不信任 LLM 返回的 chunk_id（可能被截断/篡改），强制使用真实 ID
            expected_id = str(chunk.get("id", ""))
            acceptable = qa.get("acceptable_chunk_ids", [])
            if not isinstance(acceptable, list):
                acceptable = []
            acceptable = [cid for cid in acceptable if cid != expected_id]

            results.append({
                "id": qid,
                "question": str(qa.get("question", "")).strip(),
                "answer": str(qa.get("answer", "")).strip(),
                "source_chunks": [expected_id] + acceptable,
                "expected_chunk_id": expected_id,
                "acceptable_chunk_ids": acceptable,
                "type": chunk.get("chunk_type", ""),
                "category": self._infer_category(chunk),
                "sub_category": self._infer_sub_category(chunk),
                "chunk_type": chunk.get("chunk_type", ""),
                "span": "single",
                "article_id": str(chunk.get("article_id", "")),
                "law_name": chunk.get("law_name", "") or chunk.get("source_doc", "") or "",
                "difficulty": qa.get("difficulty", "medium"),
                "expected_source_type": self._infer_category(chunk),
                "expected_answer_text": str(qa.get("answer", "")).strip(),
                "is_regulatory_strict": chunk.get("chunk_type") == "pdf_law_parent",
            })
        return results

    def generate_pc_batch(self, chunks: List[dict], start_idx: int) -> List[dict]:
        if not chunks:
            return []
        content = self._call_llm(SYSTEM_PROMPT_PARENT_CHILD, self._build_pc_prompt(chunks))
        if not content:
            return []
        qa_list = self._extract_json(content)
        if not qa_list:
            print(f"  JSON 解析失败，原始响应: {content[:300]}")
            return []

        results = []
        for i, qa in enumerate(qa_list):
            if qa is None:
                continue
            if i >= len(chunks):
                break
            chunk = chunks[i]
            qid = f"qa_v5_pc_{start_idx + i + 1:04d}"
            # ★ 不信任 LLM 返回的 chunk_id，强制使用真实 ID
            expected_id = str(chunk.get("id", ""))
            acceptable = qa.get("acceptable_chunk_ids", [])
            if not isinstance(acceptable, list):
                acceptable = []

            results.append({
                "id": qid,
                "question": str(qa.get("question", "")).strip(),
                "answer": str(qa.get("answer", "")).strip(),
                "source_chunks": [expected_id] + acceptable,
                "expected_chunk_id": expected_id,
                "acceptable_chunk_ids": acceptable,
                "type": "parent_child",
                "category": "法规原文",
                "sub_category": self._infer_sub_category(chunk),
                "chunk_type": "pdf_law_parent",
                "span": "parent_child",
                "article_id": str(chunk.get("article_id", "")),
                "law_name": chunk.get("law_name", "") or "",
                "difficulty": qa.get("difficulty", "medium"),
                "expected_source_type": "法规原文",
                "expected_answer_text": str(qa.get("answer", "")).strip(),
                "is_regulatory_strict": True,
            })
        return results

    def generate_cross_batch(self, pairs: List[Tuple[dict, dict]], start_idx: int) -> List[dict]:
        if not pairs:
            return []
        content = self._call_llm(SYSTEM_PROMPT_CROSS, self._build_cross_prompt(pairs))
        if not content:
            return []
        qa_list = self._extract_json(content)
        if not qa_list:
            print(f"  JSON 解析失败，原始响应: {content[:300]}")
            return []

        results = []
        for i, qa in enumerate(qa_list):
            if i >= len(pairs):
                break
            c_a, c_b = pairs[i]
            qid = f"qa_v5_cross_{start_idx + i + 1:04d}"
            # ★ 不信任 LLM 返回的 chunk_id，强制使用真实 ID
            expected_id = str(c_a.get("id", ""))
            acceptable = qa.get("acceptable_chunk_ids", [])
            if not isinstance(acceptable, list):
                acceptable = []
            if c_b.get("id", "") not in acceptable:
                acceptable.append(c_b.get("id", ""))
            acceptable = [cid for cid in acceptable if cid != expected_id]

            results.append({
                "id": qid,
                "question": str(qa.get("question", "")).strip(),
                "answer": str(qa.get("answer", "")).strip(),
                "source_chunks": [expected_id] + acceptable,
                "expected_chunk_id": expected_id,
                "acceptable_chunk_ids": acceptable,
                "type": "cross_chunk",
                "category": "法规原文",
                "sub_category": self._infer_sub_category(c_a),
                "chunk_type": "pdf_law_parent",
                "span": "cross",
                "article_id": f"{c_a.get('article_id','')},{c_b.get('article_id','')}",
                "law_name": c_a.get("law_name", "") or "",
                "difficulty": qa.get("difficulty", "medium"),
                "expected_source_type": "法规原文",
                "expected_answer_text": str(qa.get("answer", "")).strip(),
                "is_regulatory_strict": True,
            })
        return results

    def run(self):
        print("=" * 60)
        print("eval_benchmark_v5 生成器 (2500 QA pairs, V4.2)")
        print("=" * 60)

        # 1. 加载
        print("\n[1/5] 加载 chunks...")
        chunks = load_chunks()
        print(f"  已加载 {len(chunks)} 个 chunks")

        # 重建章上下文
        parent_chunks = [c for c in chunks if c.get("chunk_type") == "pdf_law_parent"]
        self.chapter_contexts = build_chapter_contexts(parent_chunks)
        print(f"  章上下文: {len(set(self.chapter_contexts.values()))} 章")

        # 2. 抽样
        print("\n[2/5] 抽样...")
        single_samples, pc_samples, cross_pairs = sample_chunks(chunks, total_limit=self.total_limit)

        total_single = sum(len(v) for v in single_samples.values())
        print(f"  单Chunk: {total_single}")
        for ct, items in sorted(single_samples.items()):
            print(f"    {ct}: {len(items)}")
        print(f"  父子Chunk: {len(pc_samples)}")
        print(f"  跨Chunk: {len(cross_pairs)}")

        # 3. 生成
        print(f"\n[3/5] 生成 QA 对...")
        all_qas = list(self.progress.get("generated_qas", []))
        qa_counter = len(all_qas)
        completed_ids = set(self.progress.get("completed_ids", []))

        # 3a. 单Chunk
        for ct in ["pdf_law_parent", "pdf_case_paragraph", "policy_doc", "opinion_news"]:
            items = single_samples.get(ct, [])
            if not items:
                continue
            remaining = [c for c in items if c.get("id") not in completed_ids]
            if not remaining:
                print(f"  [{ct}] 全部已完成，跳过")
                continue

            print(f"\n  [{ct}] 生成 {len(remaining)} 个单Chunk QA...")
            for batch_start in range(0, len(remaining), BATCH_SIZE):
                batch = remaining[batch_start:batch_start + BATCH_SIZE]
                bn = batch_start // BATCH_SIZE + 1
                total_bn = (len(remaining) - 1) // BATCH_SIZE + 1
                print(f"    批次 {bn}/{total_bn} ({len(batch)} chunks)...", end=" ", flush=True)

                new_qas = self.generate_single_batch(batch, qa_counter)
                if new_qas:
                    all_qas.extend(new_qas)
                    qa_counter += len(new_qas)
                    for nq in new_qas:
                        completed_ids.add(nq["expected_chunk_id"])
                    self.progress["generated_qas"] = all_qas
                    self.progress["completed_ids"] = list(completed_ids)
                    self._save_progress()
                    print(f"OK ({len(all_qas)} total)")
                else:
                    print("FAIL")
                time.sleep(BATCH_DELAY)

        # 3b. 父子Chunk
        if pc_samples:
            remaining_pc = [c for c in pc_samples if c.get("id") not in completed_ids]
            if remaining_pc:
                print(f"\n  [parent_child] 生成 {len(remaining_pc)} 个父子Chunk QA...")
                for batch_start in range(0, len(remaining_pc), PARENT_CHILD_BATCH_SIZE):
                    batch = remaining_pc[batch_start:batch_start + PARENT_CHILD_BATCH_SIZE]
                    bn = batch_start // PARENT_CHILD_BATCH_SIZE + 1
                    total_bn = (len(remaining_pc) - 1) // PARENT_CHILD_BATCH_SIZE + 1
                    print(f"    批次 {bn}/{total_bn} ({len(batch)} chunks)...", end=" ", flush=True)

                    new_qas = self.generate_pc_batch(batch, qa_counter)
                    if new_qas:
                        all_qas.extend(new_qas)
                        qa_counter += len(new_qas)
                        for nq in new_qas:
                            completed_ids.add(nq["expected_chunk_id"])
                        self.progress["generated_qas"] = all_qas
                        self.progress["completed_ids"] = list(completed_ids)
                        self._save_progress()
                        print(f"OK ({len(all_qas)} total)")
                    else:
                        print("FAIL")
                    time.sleep(BATCH_DELAY)

        # 3c. 跨Chunk
        if cross_pairs:
            remaining_cross = [p for p in cross_pairs
                               if p[0].get("id") not in completed_ids]
            if remaining_cross:
                print(f"\n  [cross_chunk] 生成 {len(remaining_cross)} 个跨Chunk QA...")
                for batch_start in range(0, len(remaining_cross), CROSS_BATCH_SIZE):
                    batch = remaining_cross[batch_start:batch_start + CROSS_BATCH_SIZE]
                    bn = batch_start // CROSS_BATCH_SIZE + 1
                    total_bn = (len(remaining_cross) - 1) // CROSS_BATCH_SIZE + 1
                    print(f"    批次 {bn}/{total_bn} ({len(batch)} pairs)...", end=" ", flush=True)

                    new_qas = self.generate_cross_batch(batch, qa_counter)
                    if new_qas:
                        all_qas.extend(new_qas)
                        qa_counter += len(new_qas)
                        for nq in new_qas:
                            completed_ids.add(nq["expected_chunk_id"])
                        self.progress["generated_qas"] = all_qas
                        self.progress["completed_ids"] = list(completed_ids)
                        self._save_progress()
                        print(f"OK ({len(all_qas)} total)")
                    else:
                        print("FAIL")
                    time.sleep(BATCH_DELAY)

        # 4. 验证
        print(f"\n[4/5] 验证...")
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
            qa["id"] = f"qa_v5_{i+1:04d}"

        # 5. 统计与保存
        print(f"\n[5/5] 保存...")
        by_type = defaultdict(int)
        by_diff = defaultdict(int)
        by_span = defaultdict(int)
        for qa in valid_qas:
            by_type[qa.get("type", qa.get("chunk_type", "unknown"))] += 1
            by_diff[qa.get("difficulty", "unknown")] += 1
            by_span[qa.get("span", "unknown")] += 1

        output = {
            "version": "v5",
            "description": "基于 V4.2 章上下文检索结构的召回评估问答集 (2500题, 70/20/10)",
            "total": len(valid_qas),
            "stats": {
                "by_chunk_type": dict(by_type),
                "by_difficulty": dict(by_diff),
                "by_span": dict(by_span),
            },
            "qa_pairs": valid_qas,
        }

        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"\n{'=' * 60}")
        print(f"生成完成!")
        print(f"  总数: {len(valid_qas)}")
        print(f"  按类型: {json.dumps(dict(by_type), ensure_ascii=False)}")
        print(f"  按难度: {json.dumps(dict(by_diff), ensure_ascii=False)}")
        print(f"  按 span: {json.dumps(dict(by_span), ensure_ascii=False)}")
        print(f"  输出: {OUTPUT_PATH}")
        print(f"{'=' * 60}")

        # PROGRESS_PATH.unlink()  # 保留进度文件以支持 resume


def main():
    parser = argparse.ArgumentParser(description="eval_benchmark_v5 生成器 (2500题)")
    parser.add_argument("--dry-run", action="store_true", help="仅预览抽样分布")
    parser.add_argument("--total", type=int, default=None, help="限制总数（测试用）")
    parser.add_argument("--resume", action="store_true", help="从断点继续")
    args = parser.parse_args()

    if not CHUNKS_PATH.exists():
        print(f"错误: chunks 文件不存在: {CHUNKS_PATH}")
        print("请先导出 policy_chunks_export_v5.json")
        sys.exit(1)

    if args.dry_run:
        chunks = load_chunks()
        parent_chunks = [c for c in chunks if c.get("chunk_type") == "pdf_law_parent"]
        chapter_contexts = build_chapter_contexts(parent_chunks)
        print(f"Chunks: {len(chunks)}")
        print(f"章上下文: {len(set(chapter_contexts.values()))} 章")
        single_samples, pc_samples, cross_pairs = sample_chunks(chunks, total_limit=args.total)
        total_single = sum(len(v) for v in single_samples.values())
        print(f"\n抽样 (目标: {args.total or 2500}):")
        print(f"  单Chunk: {total_single}")
        for ct, items in sorted(single_samples.items()):
            print(f"    {ct}: {len(items)}")
        print(f"  父子Chunk: {len(pc_samples)}")
        print(f"  跨Chunk: {len(cross_pairs)}")
        return

    if not args.resume and PROGRESS_PATH.exists():
        PROGRESS_PATH.unlink()

    generator = QAGenerator(total_limit=args.total)
    generator.run()


if __name__ == "__main__":
    main()
