#!/usr/bin/env python
"""
eval_benchmark_v2 生成器 —— 从 policy_chunks_export.json 生成 1000 个 QA 对

分布:
  pdf_law_parent:      420 (single-chunk)
  pdf_law_child:        80 (single-chunk)
  pdf_case_paragraph:  200 (single-chunk, 实务段落归并)
  policy_doc:           50 (single-chunk)
  opinion_news:         80 (single-chunk)
  cross_chunk:         100 (adjacent parent pair)

难度: easy 40% / medium 40% / hard 20%

用法:
  python gen_eval_benchmark_v2.py              # 全量生成
  python gen_eval_benchmark_v2.py --dry-run    # 仅预览抽样分布
  python gen_eval_benchmark_v2.py --total 100  # 限制生成数量（测试用）
  python gen_eval_benchmark_v2.py --resume     # 从断点继续
"""

import sys
import json
import random
import time
import argparse
import hashlib
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from openai import OpenAI

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
CHUNKS_PATH = Path(__file__).parent / "data" / "eval_questions" / "policy_chunks_export.json"
OUTPUT_PATH = Path(__file__).parent / "data" / "eval_questions" / "eval_benchmark_v2.json"
PROGRESS_PATH = Path(__file__).parent / "data" / "eval_questions" / ".qa_gen_progress_v2.json"

# API 配置 — 从 config.yaml 读取当前 provider（由 llm.provider 字段控制）
# 如需切换，修改 config.yaml 的 llm.provider 即可

# 生成参数
BATCH_SIZE = 8          # 每批发送的 chunk 数
MAX_RETRIES = 3         # 每批最多重试次数
RETRY_DELAY = 3         # 重试间隔 (秒)
BATCH_DELAY = 1.5       # 批次间间隔 (秒)

# QA 分布
DISTRIBUTION = {
    "pdf_law_parent":      420,
    "pdf_law_child":        80,
    "pdf_case_paragraph":  200,
    "pdf_law_sliding":       0,
    "policy_doc":           50,
    "opinion_news":         80,
    "cross_chunk":         100,
}
TOTAL_TARGET = 930

DIFFICULTY_RATIOS = {"easy": 0.40, "medium": 0.40, "hard": 0.20}

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def short_hash(text: str, length: int = 8) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:length]

def pick_difficulty(idx: int, total: int) -> str:
    """按 easy/medium/hard = 40/40/20 分配难度"""
    p = idx / max(total, 1)
    if p < 0.40:
        return "easy"
    elif p < 0.80:
        return "medium"
    else:
        return "hard"

def load_chunks() -> List[dict]:
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["chunks"]

def validate_qa(qa: dict) -> List[str]:
    """验证一个 QA 对，返回错误列表（空列表 = 通过）"""
    errors = []
    for field in ["id", "question", "answer", "source_chunks", "chunk_type",
                   "span", "article_id", "law_name", "difficulty"]:
        if field not in qa:
            errors.append(f"缺少字段: {field}")
    if "source_chunks" in qa:
        if not isinstance(qa["source_chunks"], list) or len(qa["source_chunks"]) == 0:
            errors.append("source_chunks 必须是非空列表")
    if "difficulty" in qa and qa["difficulty"] not in ("easy", "medium", "hard"):
        errors.append(f"无效难度值: {qa['difficulty']}")
    if "span" in qa and qa["span"] not in ("single", "cross"):
        errors.append(f"无效 span 值: {qa['span']}")
    return errors

# ---------------------------------------------------------------------------
# 抽样逻辑
# ---------------------------------------------------------------------------
def sample_chunks(chunks: List[dict], dry_run: bool = False, total_limit: Optional[int] = None):
    """
    按分布抽样，返回:
      - sampled: {chunk_type: [chunk_dict, ...]}  (cross_chunk 除外)
      - cross_pairs: [(chunk_a, chunk_b), ...]
      - all_sampled_chunks: [chunk_dict, ...] (所有被选中参与生成的 chunk)
    """
    # 按类型分组
    by_type = defaultdict(list)
    for c in chunks:
        ct = c.get("chunk_type", "other")
        by_type[ct].append(c)

    random.seed(42)  # 可复现

    sampled = {}
    stats = {}

    # --- pdf_law_parent ---
    parent_chunks = by_type.get("pdf_law_parent", [])
    # 按 law_name 分组，按比例抽样
    by_law = defaultdict(list)
    for c in parent_chunks:
        law = c.get("law_name", "") or "(未知)"
        by_law[law].append(c)

    n_parent = DISTRIBUTION["pdf_law_parent"]
    if total_limit:
        n_parent = max(1, int(n_parent * total_limit / TOTAL_TARGET))

    parent_sample = []
    law_counts = {}
    remaining = n_parent
    law_names = sorted(by_law.keys(), key=lambda l: len(by_law[l]), reverse=True)
    for law in law_names:
        if remaining <= 0:
            break
        # 按比例分配，但至少保证每个法律至少有 1 条
        pool = by_law[law]
        if len(law_names) == 1:
            n = remaining
        else:
            ratio = len(pool) / len(parent_chunks)
            n = max(1, min(remaining, int(n_parent * ratio)))
        n = min(n, len(pool), remaining)
        chosen = random.sample(pool, n)
        parent_sample.extend(chosen)
        law_counts[law] = n
        remaining -= n

    sampled["pdf_law_parent"] = parent_sample
    stats["pdf_law_parent"] = {"total": n_parent, "actual": len(parent_sample), "by_law": law_counts}

    # --- pdf_law_child ---
    child_chunks = by_type.get("pdf_law_child", [])
    n_child = DISTRIBUTION["pdf_law_child"]
    if total_limit:
        n_child = max(1, int(n_child * total_limit / TOTAL_TARGET))
    # 去重：每个 parent_id 只选一个 child，保证问题多样性
    by_parent = defaultdict(list)
    for c in child_chunks:
        pid = c.get("parent_id", c.get("id", ""))
        by_parent[pid].append(c)
    # 随机选 N 个不同的 parent，每个取一个 child
    parent_ids = list(by_parent.keys())
    random.shuffle(parent_ids)
    child_sample = []
    for pid in parent_ids:
        if len(child_sample) >= n_child:
            break
        child_sample.append(random.choice(by_parent[pid]))
    sampled["pdf_law_child"] = child_sample
    stats["pdf_law_child"] = {"total": n_child, "actual": len(child_sample)}

    # --- pdf_case_paragraph (实务段落归并，替代旧 pdf_case_sliding) ---
    case_chunks = by_type.get("pdf_case_paragraph", [])
    n_case = DISTRIBUTION["pdf_case_paragraph"]
    if total_limit:
        n_case = max(1, int(n_case * total_limit / TOTAL_TARGET))
    # 按 source_doc 分组，保证案例多样性
    by_case = defaultdict(list)
    for c in case_chunks:
        src = c.get("source_doc", "") or "(未知案例)"
        by_case[src].append(c)
    case_sample = []
    remaining = n_case
    case_names = sorted(by_case.keys(), key=lambda k: len(by_case[k]), reverse=True)
    for name in case_names:
        if remaining <= 0:
            break
        pool = by_case[name]
        n = max(1, min(remaining, int(n_case * len(pool) / len(case_chunks))))
        n = min(n, len(pool), remaining)
        case_sample.extend(random.sample(pool, n))
        remaining -= n
    sampled["pdf_case_paragraph"] = case_sample
    stats["pdf_case_paragraph"] = {"total": n_case, "actual": len(case_sample), "by_case": {k: len([c for c in case_sample if c.get("source_doc")==k]) for k in case_names}}

    # --- pdf_law_sliding ---
    sliding_chunks = by_type.get("pdf_law_sliding", [])
    n_sliding = DISTRIBUTION["pdf_law_sliding"]
    if total_limit:
        n_sliding = max(1, int(n_sliding * total_limit / TOTAL_TARGET))
    sliding_sample = random.sample(sliding_chunks, min(n_sliding, len(sliding_chunks)))
    sampled["pdf_law_sliding"] = sliding_sample
    stats["pdf_law_sliding"] = {"total": n_sliding, "actual": len(sliding_sample)}

    # --- policy_doc ---
    policy_docs = by_type.get("policy_doc", [])
    n_policy_doc = DISTRIBUTION["policy_doc"]
    if total_limit:
        n_policy_doc = max(1, int(n_policy_doc * total_limit / TOTAL_TARGET))
    policy_doc_sample = random.sample(policy_docs, min(n_policy_doc, len(policy_docs)))
    sampled["policy_doc"] = policy_doc_sample
    stats["policy_doc"] = {"total": n_policy_doc, "actual": len(policy_doc_sample)}

    # --- opinion_news ---
    opinions = by_type.get("opinion_news", [])
    n_opinion = DISTRIBUTION["opinion_news"]
    if total_limit:
        n_opinion = max(1, int(n_opinion * total_limit / TOTAL_TARGET))
    opinion_sample = random.sample(opinions, min(n_opinion, len(opinions)))
    sampled["opinion_news"] = opinion_sample
    stats["opinion_news"] = {"total": n_opinion, "actual": len(opinion_sample)}

    # --- cross_chunk: 相邻 parent 对 ---
    cross_pairs = _find_cross_pairs(parent_chunks)
    n_cross = DISTRIBUTION["cross_chunk"]
    if total_limit:
        n_cross = max(1, int(n_cross * total_limit / TOTAL_TARGET))
    random.shuffle(cross_pairs)
    cross_pairs = cross_pairs[:n_cross]
    stats["cross_chunk"] = {"total": n_cross, "actual": len(cross_pairs)}

    if dry_run:
        return stats

    # 汇总所有被选中的 chunk（用于进度跟踪）
    all_selected = []
    for ct in ["pdf_law_parent", "pdf_law_child", "pdf_case_paragraph", "pdf_law_sliding", "policy_doc", "opinion_news"]:
        all_selected.extend(sampled.get(ct, []))
    # cross_chunk 的 chunks 也在 parent_sample 里，不需重复

    return sampled, cross_pairs, all_selected


def _find_cross_pairs(parent_chunks: List[dict]) -> List[Tuple[dict, dict]]:
    """查找同法律下相邻 article_id 的 parent chunk 对"""
    by_law = defaultdict(list)
    for c in parent_chunks:
        law = c.get("law_name", "")
        aid = c.get("article_id", "")
        if law and aid:
            try:
                by_law[law].append((int(aid), c))
            except (ValueError, TypeError):
                pass

    pairs = []
    seen_pairs = set()
    for law, chunks in by_law.items():
        chunks.sort(key=lambda x: x[0])
        for i in range(len(chunks) - 1):
            aid_a, c_a = chunks[i]
            aid_b, c_b = chunks[i + 1]
            # 必须是不同的 article_id，且相邻（间隔 ≤ 2，允许条款合并的情况）
            if aid_a < aid_b and aid_b - aid_a <= 2:
                key = (c_a["id"], c_b["id"])
                if key not in seen_pairs:
                    seen_pairs.add(key)
                    pairs.append((c_a, c_b))

    return pairs


# ---------------------------------------------------------------------------
# QA 生成
# ---------------------------------------------------------------------------
class QAGenerator:
    def __init__(self, total_limit: Optional[int] = None):
        self.total_limit = total_limit
        self.client = self._init_client()
        self.progress = self._load_progress()

    def _init_client(self):
        from config import settings
        api_key = settings.llm_api_key
        api_url = settings.llm_api_url
        base_url = api_url.replace("/chat/completions", "")
        if not api_key:
            raise RuntimeError(f"LLM_API_KEY 未设置（provider={settings.llm_provider}）")
        self._model = settings.llm_model
        return OpenAI(base_url=base_url, api_key=api_key)

    def _load_progress(self) -> dict:
        if PROGRESS_PATH.exists():
            with open(PROGRESS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"completed_batches": [], "generated_qas": [], "total_generated": 0}

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
                    max_tokens=4096,
                    timeout=120,
                    extra_body={"thinking": {"type": "disabled"}},
                )
                content = resp.choices[0].message.content
                # GLM-4.5 思考模式可能 content 为空，回退到 reasoning_content
                if not content:
                    content = getattr(resp.choices[0].message, "reasoning_content", "")
                return content
            except Exception as e:
                print(f"  LLM 调用失败 (尝试 {attempt+1}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
        return None

    def generate_single_chunk_batch(self, chunks: List[dict], chunk_type: str,
                                     start_idx: int) -> List[dict]:
        """为一组同类型 chunk 生成 single-span QA 对"""
        if not chunks:
            return []

        # 构建 prompt
        chunk_descriptions = []
        for i, c in enumerate(chunks):
            text = c.get("text", "")
            # 截断过长文本
            if len(text) > 1200:
                text = text[:1200] + "..."
            cid = c.get("id", "")
            law = c.get("law_name", "") or c.get("source_doc", "") or "未知"
            aid = c.get("article_id", "") or "N/A"
            chunk_descriptions.append(
                f"### 片段 {i+1}\n"
                f"- chunk_id: {cid}\n"
                f"- 法律/来源: {law}\n"
                f"- 条款号: {aid}\n"
                f"- 文本内容:\n```\n{text}\n```"
            )

        system_prompt = (
            "你是一个法律知识检索评测问答对生成专家。你的任务是根据给定的法律条文或案例片段，"
            "生成可用于检索系统召回率评测的问答对。\n\n"
            "核心要求：\n"
            "1. 问题必须能够从给定文本片段中找到答案（答案限定在该片段中）\n"
            "2. 问题的措辞不应直接照搬原文，需要换一种问法，模拟真实用户的提问方式\n"
            "3. 答案要简洁准确，直接摘录文本中的关键信息\n"
            "4. 每个片段生成一个问答对\n\n"
            "难度标准：\n"
            "- easy: 直接事实型，问题明确指出条款或概念，答案可以直接从文中摘录\n"
            "- medium: 需要理解和概括，提问用口语化方式，答案需要对原文进行一定归纳\n"
            "- hard: 需要推理或综合，问题涉及多个条件、例外情况或隐含关系\n\n"
            "输出格式：严格输出 JSON 数组，不要任何额外文字。每个元素包含：\n"
            '{"question": "...", "answer": "...", "difficulty": "easy|medium|hard"}'
        )

        user_prompt = (
            f"请为以下 {len(chunks)} 个{chunk_type}类型的法律文本片段各生成一个问答对。\n"
            f"这些片段属于不同难度级别，请根据文本内容的复杂度自行判断难度。\n\n"
            + "\n---\n".join(chunk_descriptions) +
            "\n\n请输出 JSON 数组，按片段顺序排列。"
        )

        content = self._call_llm(system_prompt, user_prompt)
        if not content:
            return []

        return self._parse_qa_response(content, chunks, chunk_type, "single", start_idx)

    def generate_cross_chunk_batch(self, pairs: List[Tuple[dict, dict]], start_idx: int) -> List[dict]:
        """为相邻 parent chunk 对生成 cross-span QA 对"""
        if not pairs:
            return []

        pair_descriptions = []
        for i, (c_a, c_b) in enumerate(pairs):
            law = c_a.get("law_name", "") or "未知"
            aid_a = c_a.get("article_id", "")
            aid_b = c_b.get("article_id", "")
            text_a = c_a.get("text", "")
            text_b = c_b.get("text", "")
            if len(text_a) > 800:
                text_a = text_a[:800] + "..."
            if len(text_b) > 800:
                text_b = text_b[:800] + "..."

            pair_descriptions.append(
                f"### 片段对 {i+1}\n"
                f"- 法律: {law}\n"
                f"- 条款 {aid_a} (chunk_id: {c_a.get('id')}):\n```\n{text_a}\n```\n"
                f"- 条款 {aid_b} (chunk_id: {c_b.get('id')}):\n```\n{text_b}\n```"
            )

        system_prompt = (
            "你是一个法律知识检索评测问答对生成专家。你的任务是生成需要同时参考两个相关法律条文"
            "才能回答的问题，用于测试检索系统的跨片段召回能力。\n\n"
            "核心要求：\n"
            "1. 问题必须需要两个片段的信息才能完整回答\n"
            "2. 问题可以是比较、条件关系、程序前后衔接、定义+例外等类型\n"
            "3. 答案要明确指出各片段提供的信息\n"
            "4. 每个片段对生成一个问答对\n\n"
            "难度标准：\n"
            "- easy: 两个片段信息的简单组合\n"
            "- medium: 需要理解两个片段之间的关系\n"
            "- hard: 需要深层推理或对比分析\n\n"
            "输出格式：严格输出 JSON 数组。每个元素包含：\n"
            '{"question": "...", "answer": "...", "difficulty": "easy|medium|hard"}'
        )

        user_prompt = (
            f"请为以下 {len(pairs)} 对相邻法律条款各生成一个跨条款问答对。\n\n"
            + "\n---\n".join(pair_descriptions) +
            "\n\n请输出 JSON 数组，按片段对顺序排列。"
        )

        content = self._call_llm(system_prompt, user_prompt)
        if not content:
            return []

        return self._parse_cross_qa_response(content, pairs, start_idx)

    def _parse_qa_response(self, content: str, chunks: List[dict],
                            chunk_type: str, span: str, start_idx: int) -> List[dict]:
        """解析 LLM 返回的 QA JSON 数组"""
        # 提取 JSON 数组
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:]) if len(lines) > 1 else content
            if content.endswith("```"):
                content = content[:-3]

        try:
            qa_list = json.loads(content)
        except json.JSONDecodeError:
            # 尝试提取 [...] 部分
            import re
            match = re.search(r'\[.*\]', content, re.DOTALL)
            if match:
                try:
                    qa_list = json.loads(match.group())
                except json.JSONDecodeError:
                    print(f"  JSON 解析失败，原始响应: {content[:300]}")
                    return []
            else:
                print(f"  未找到 JSON 数组，原始响应: {content[:300]}")
                return []

        if not isinstance(qa_list, list):
            return []

        results = []
        for i, qa in enumerate(qa_list):
            if i >= len(chunks):
                break
            chunk = chunks[i]
            qid = f"qa_v2_{start_idx + i + 1:04d}"
            results.append({
                "id": qid,
                "question": str(qa.get("question", "")).strip(),
                "answer": str(qa.get("answer", "")).strip(),
                "source_chunks": [chunk.get("id", "")],
                "chunk_type": chunk_type,
                "span": span,
                "article_id": str(chunk.get("article_id", "")),
                "law_name": chunk.get("law_name", "") or chunk.get("source_doc", "") or "",
                "difficulty": qa.get("difficulty", "medium"),
            })
        return results

    def _parse_cross_qa_response(self, content: str, pairs: List[Tuple[dict, dict]],
                                  start_idx: int) -> List[dict]:
        """解析交叉片段 QA 响应"""
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:]) if len(lines) > 1 else content
            if content.endswith("```"):
                content = content[:-3]

        try:
            qa_list = json.loads(content)
        except json.JSONDecodeError:
            import re
            match = re.search(r'\[.*\]', content, re.DOTALL)
            if match:
                try:
                    qa_list = json.loads(match.group())
                except json.JSONDecodeError:
                    print(f"  JSON 解析失败，原始响应: {content[:300]}")
                    return []
            else:
                print(f"  未找到 JSON 数组，原始响应: {content[:300]}")
                return []

        if not isinstance(qa_list, list):
            return []

        results = []
        for i, qa in enumerate(qa_list):
            if i >= len(pairs):
                break
            c_a, c_b = pairs[i]
            qid = f"qa_v2_cross_{start_idx + i + 1:04d}"
            results.append({
                "id": qid,
                "question": str(qa.get("question", "")).strip(),
                "answer": str(qa.get("answer", "")).strip(),
                "source_chunks": [c_a.get("id", ""), c_b.get("id", "")],
                "chunk_type": "pdf_law_parent",
                "span": "cross",
                "article_id": f"{c_a.get('article_id','')},{c_b.get('article_id','')}",
                "law_name": c_a.get("law_name", "") or "",
                "difficulty": qa.get("difficulty", "medium"),
            })
        return results

    def run(self):
        print("=" * 60)
        print("eval_benchmark_v2 生成器")
        print("=" * 60)

        # 1. 加载与抽样
        print("\n[1/4] 加载 chunks...")
        chunks = load_chunks()
        print(f"  已加载 {len(chunks)} 个 chunks")

        print("\n[2/4] 抽样...")
        result = sample_chunks(chunks, total_limit=self.total_limit)
        if isinstance(result, dict):  # dry-run
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

        sampled, cross_pairs, _ = result
        total_to_gen = sum(len(v) for v in sampled.values()) + len(cross_pairs)
        print(f"  待生成 QA 数: {total_to_gen}")
        for ct, items in sorted(sampled.items()):
            print(f"    {ct}: {len(items)}")
        print(f"    cross_chunk: {len(cross_pairs)}")

        # 2. 检查已有进度
        completed_ids = set()
        for qa in self.progress.get("generated_qas", []):
            completed_ids.add(qa.get("id", ""))
        if completed_ids:
            print(f"\n  已有进度: {len(completed_ids)} 个 QA 已生成，将跳过")

        # 3. 生成 single-chunk QA
        print(f"\n[3/4] 生成 QA 对...")
        all_qas = list(self.progress.get("generated_qas", []))
        qa_counter = len(all_qas)

        for ct in ["pdf_law_parent", "pdf_law_child", "pdf_case_paragraph", "pdf_law_sliding", "policy_doc", "opinion_news"]:
            items = sampled.get(ct, [])
            if not items:
                continue

            # 过滤已完成的
            remaining = [c for c in items if c.get("id") not in completed_ids]
            if not remaining:
                print(f"  [{ct}] 全部已完成，跳过")
                continue

            print(f"\n  [{ct}] 生成 {len(remaining)} 个 QA ({len(items)-len(remaining)} 已完成)...")

            for batch_start in range(0, len(remaining), BATCH_SIZE):
                batch = remaining[batch_start:batch_start + BATCH_SIZE]
                print(f"    批次 {batch_start//BATCH_SIZE + 1}/{(len(remaining)-1)//BATCH_SIZE + 1}"
                      f" ({len(batch)} chunks)...", end=" ", flush=True)

                new_qas = self.generate_single_chunk_batch(batch, ct, qa_counter)
                if new_qas:
                    all_qas.extend(new_qas)
                    qa_counter += len(new_qas)
                    self.progress["generated_qas"] = all_qas
                    self.progress["total_generated"] = len(all_qas)
                    self._save_progress()
                    print(f"✓ 生成 {len(new_qas)} 条 (总计 {len(all_qas)})")
                else:
                    print("✗ 失败")

                time.sleep(BATCH_DELAY)

        # 4. 生成 cross-chunk QA
        if cross_pairs:
            remaining_pairs = [p for p in cross_pairs
                             if p[0].get("id") not in completed_ids]
            if remaining_pairs:
                print(f"\n  [cross_chunk] 生成 {len(remaining_pairs)} 个 QA...")
                cross_batch_size = 5
                for batch_start in range(0, len(remaining_pairs), cross_batch_size):
                    batch = remaining_pairs[batch_start:batch_start + cross_batch_size]
                    print(f"    批次 {batch_start//cross_batch_size + 1}/"
                          f"{(len(remaining_pairs)-1)//cross_batch_size + 1}"
                          f" ({len(batch)} pairs)...", end=" ", flush=True)

                    new_qas = self.generate_cross_chunk_batch(batch, qa_counter)
                    if new_qas:
                        all_qas.extend(new_qas)
                        qa_counter += len(new_qas)
                        self.progress["generated_qas"] = all_qas
                        self.progress["total_generated"] = len(all_qas)
                        self._save_progress()
                        print(f"✓ 生成 {len(new_qas)} 条 (总计 {len(all_qas)})")
                    else:
                        print("✗ 失败")

                    time.sleep(BATCH_DELAY)

        # 5. 验证与保存
        print(f"\n[4/4] 验证与保存...")
        valid_qas = []
        invalid_count = 0
        for qa in all_qas:
            errors = validate_qa(qa)
            if errors:
                invalid_count += 1
                if invalid_count <= 5:
                    print(f"  无效 QA: {qa.get('id')} - {errors}")
            else:
                valid_qas.append(qa)

        print(f"  有效: {len(valid_qas)}, 无效: {invalid_count}")

        # ID 重排序
        for i, qa in enumerate(valid_qas):
            qa["id"] = f"qa_v2_{i+1:04d}"

        # 统计
        stats = self._compute_stats(valid_qas)

        output = {
            "version": "v2",
            "description": "基于 policy collection chunks 生成的召回评估问答集",
            "total": len(valid_qas),
            "stats": stats,
            "qa_pairs": valid_qas,
        }

        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"\n{'=' * 60}")
        print(f"生成完成!")
        print(f"  总数: {len(valid_qas)}")
        print(f"  按类型: {json.dumps(stats.get('by_chunk_type', {}), ensure_ascii=False)}")
        print(f"  按难度: {json.dumps(stats.get('by_difficulty', {}), ensure_ascii=False)}")
        print(f"  按 span: {json.dumps(stats.get('by_span', {}), ensure_ascii=False)}")
        print(f"  输出: {OUTPUT_PATH}")
        print(f"{'=' * 60}")

        # 清理进度文件
        if PROGRESS_PATH.exists():
            PROGRESS_PATH.unlink()

    def _compute_stats(self, qas: List[dict]) -> dict:
        by_type = defaultdict(int)
        by_difficulty = defaultdict(int)
        by_span = defaultdict(int)
        by_law = defaultdict(int)

        for qa in qas:
            by_type[qa.get("chunk_type", "unknown")] += 1
            by_difficulty[qa.get("difficulty", "unknown")] += 1
            by_span[qa.get("span", "unknown")] += 1
            law = qa.get("law_name", "") or "(未知)"
            # 截断过长的法律名
            by_law[law[:30]] += 1

        return {
            "by_chunk_type": dict(by_type),
            "by_difficulty": dict(by_difficulty),
            "by_span": dict(by_span),
            "by_law_name": dict(by_law),
        }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="eval_benchmark_v2 生成器")
    parser.add_argument("--dry-run", action="store_true", help="仅预览抽样分布")
    parser.add_argument("--total", type=int, default=None, help="限制总数（测试用）")
    parser.add_argument("--resume", action="store_true", help="从断点继续")
    args = parser.parse_args()

    if not CHUNKS_PATH.exists():
        print(f"错误: chunks 文件不存在: {CHUNKS_PATH}")
        print("请先运行 python -c \"from app.storage.milvus_store import MilvusStore; ...\" 导出")
        sys.exit(1)

    if args.dry_run:
        chunks = load_chunks()
        stats = sample_chunks(chunks, dry_run=True, total_limit=args.total)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return

    # 如需重新开始，删除进度文件
    if not args.resume and PROGRESS_PATH.exists():
        PROGRESS_PATH.unlink()

    generator = QAGenerator(total_limit=args.total)
    generator.run()


if __name__ == "__main__":
    main()
