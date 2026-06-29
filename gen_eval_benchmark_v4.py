#!/usr/bin/env python
"""
eval_benchmark_v4 生成器 —— 基于 policy_chunks_export.json 生成 1000 个 QA 对

分布 (按原计划比例缩放到1000):
  pdf_law_parent:      452
  pdf_law_child:        86
  pdf_case_paragraph:  215
  policy_doc:           54
  opinion_news:         86
  cross_chunk:         107

输出格式包含完整字段：question / expected_chunk_id / acceptable_chunk_ids / type /
  category / sub_category / difficulty / expected_source_type / expected_answer_text / is_regulatory_strict

用法:
  python gen_eval_benchmark_v4.py              # 全量生成
  python gen_eval_benchmark_v4.py --dry-run    # 仅预览抽样分布
  python gen_eval_benchmark_v4.py --total 100  # 限制生成数量（测试用）
  python gen_eval_benchmark_v4.py --resume     # 从断点继续
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
CHUNKS_PATH = Path(__file__).parent / "data" / "eval_questions" / "policy_chunks_export.json"
OUTPUT_PATH = Path(__file__).parent / "data" / "eval_questions" / "eval_benchmark_v4.json"
PROGRESS_PATH = Path(__file__).parent / "data" / "eval_questions" / ".qa_gen_progress_v4.json"

BATCH_SIZE = 6
CROSS_BATCH_SIZE = 5
MAX_RETRIES = 3
RETRY_DELAY = 3
BATCH_DELAY = 1.5

# 生成模型：优先从 settings 读取（config.yaml/.env），默认 deepseek-chat
from config import settings
GEN_MODEL = settings.llm_model or "deepseek-chat"
print(f"[Benchmark] 使用生成模型: {GEN_MODEL}")

TOTAL_TARGET = 50  # ★ 先小批量试生成，成功后扩大

# 原计划分布 (930) 等比缩放到 1000
ORIGINAL_DIST = {
    "pdf_law_parent":      420,
    "pdf_law_child":        80,
    "pdf_case_paragraph":  200,
    "policy_doc":           50,
    # opinion_news 已排除：仅 51 字标题无正文，无法支撑问答
    "cross_chunk":         100,
}
ORIGINAL_TOTAL = sum(ORIGINAL_DIST.values())  # = 850
SCALE = TOTAL_TARGET / ORIGINAL_TOTAL

DISTRIBUTION = {k: max(1, round(v * SCALE)) for k, v in ORIGINAL_DIST.items()}
# 修正舍入误差
diff = TOTAL_TARGET - sum(DISTRIBUTION.values())
if diff != 0:
    DISTRIBUTION["pdf_law_parent"] += diff

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def load_chunks() -> List[dict]:
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["chunks"]


def validate_qa(qa: dict) -> List[str]:
    errors = []
    required = ["id", "question", "expected_chunk_id", "type", "category",
                "difficulty", "expected_source_type", "expected_answer_text", "is_regulatory_strict"]
    for field in required:
        if field not in qa:
            errors.append(f"缺少字段: {field}")
    if "acceptable_chunk_ids" not in qa:
        errors.append("缺少字段: acceptable_chunk_ids")
    if "difficulty" in qa and qa["difficulty"] not in ("easy", "medium", "hard"):
        errors.append(f"无效难度值: {qa['difficulty']}")
    if "type" in qa and qa["type"] not in ("pdf_law_parent", "pdf_law_child",
        "pdf_case_paragraph", "policy_doc", "cross_chunk"):
        errors.append(f"无效 type 值: {qa['type']}")
    return errors


# ---------------------------------------------------------------------------
# 抽样逻辑
# ---------------------------------------------------------------------------
def sample_chunks(chunks: List[dict], dry_run: bool = False,
                  total_limit: Optional[int] = None):
    by_type = defaultdict(list)
    for c in chunks:
        ct = c.get("chunk_type", "other")
        by_type[ct].append(c)

    random.seed(42)

    sampled = {}
    stats = {}

    def _limit(n: int) -> int:
        if total_limit:
            return max(1, int(n * total_limit / TOTAL_TARGET))
        return n

    # --- pdf_law_parent ---
    parent_chunks = by_type.get("pdf_law_parent", [])
    by_law = defaultdict(list)
    for c in parent_chunks:
        law = c.get("law_name", "") or "(未知)"
        by_law[law].append(c)

    n_parent = _limit(DISTRIBUTION["pdf_law_parent"])
    parent_sample = []
    law_counts = {}
    remaining = n_parent
    law_names = sorted(by_law.keys(), key=lambda l: len(by_law[l]), reverse=True)
    # 第一轮：按比例分配（向下取整）
    allocated = []
    for law in law_names:
        pool = by_law[law]
        ratio = len(pool) / len(parent_chunks) if parent_chunks else 0
        n = max(1, int(n_parent * ratio))
        n = min(n, len(pool))
        allocated.append((law, pool, n))
        chosen = random.sample(pool, n)
        parent_sample.extend(chosen)
        law_counts[law] = n
    # 第二轮：补足差额，从最大的 pool 开始补
    shortfall = n_parent - len(parent_sample)
    for law, pool, _ in sorted(allocated, key=lambda x: len(x[1]), reverse=True):
        if shortfall <= 0:
            break
        already = law_counts[law]
        can_add = min(shortfall, len(pool) - already)
        if can_add > 0:
            # 从未选中的里面补选
            selected_ids = {c["id"] for c in parent_sample}
            candidates = [c for c in pool if c["id"] not in selected_ids]
            extra = random.sample(candidates, min(can_add, len(candidates)))
            parent_sample.extend(extra)
            law_counts[law] += len(extra)
            shortfall -= len(extra)

    sampled["pdf_law_parent"] = parent_sample
    stats["pdf_law_parent"] = {"total": n_parent, "actual": len(parent_sample)}

    # --- pdf_law_child ---
    child_chunks = by_type.get("pdf_law_child", [])
    n_child = _limit(DISTRIBUTION["pdf_law_child"])
    by_parent = defaultdict(list)
    for c in child_chunks:
        pid = c.get("parent_id", c.get("id", ""))
        by_parent[pid].append(c)
    parent_ids = list(by_parent.keys())
    random.shuffle(parent_ids)
    child_sample = []
    for pid in parent_ids:
        if len(child_sample) >= n_child:
            break
        child_sample.append(random.choice(by_parent[pid]))
    sampled["pdf_law_child"] = child_sample
    stats["pdf_law_child"] = {"total": n_child, "actual": len(child_sample)}

    # --- pdf_case_paragraph ---
    case_chunks = by_type.get("pdf_case_paragraph", [])
    n_case = _limit(DISTRIBUTION["pdf_case_paragraph"])
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
        n = max(1, min(remaining, int(n_case * len(pool) / max(len(case_chunks), 1))))
        n = min(n, len(pool), remaining)
        case_sample.extend(random.sample(pool, n))
        remaining -= n
    sampled["pdf_case_paragraph"] = case_sample
    stats["pdf_case_paragraph"] = {"total": n_case, "actual": len(case_sample)}

    # --- policy_doc（只对正文 >= 100 字的出题） ---
    policy_all = by_type.get("policy_doc", [])
    policy_docs = [c for c in policy_all if len(c.get("text", c.get("retrieval_text", ""))) >= 100]
    n_pd = _limit(DISTRIBUTION["policy_doc"])
    pd_sample = random.sample(policy_docs, min(n_pd, len(policy_docs)))
    sampled["policy_doc"] = pd_sample
    stats["policy_doc"] = {"total": n_pd, "actual": len(pd_sample), "available": len(policy_docs), "filtered": len(policy_all) - len(policy_docs)}

    # --- opinion_news：排除出题（仅 51 字标题无正文，无法支撑问答） ---

    # --- cross_chunk ---
    cross_pairs = _find_cross_pairs(parent_chunks)
    n_cross = _limit(DISTRIBUTION["cross_chunk"])
    random.shuffle(cross_pairs)
    cross_pairs = cross_pairs[:n_cross]
    stats["cross_chunk"] = {"total": n_cross, "actual": len(cross_pairs)}

    if dry_run:
        return stats

    all_selected = []
    for ct in ["pdf_law_parent", "pdf_law_child", "pdf_case_paragraph", "policy_doc"]:
        all_selected.extend(sampled.get(ct, []))
    return sampled, cross_pairs, all_selected


def _find_cross_pairs(parent_chunks: List[dict]) -> List[Tuple[dict, dict]]:
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
    return pairs


# ---------------------------------------------------------------------------
# QA 生成
# ---------------------------------------------------------------------------
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
2. **精准锚定——避免泛化关键词（极其重要）**：
   知识库中大量Chunk都包含相同的通用术语（如"评审专家""投诉处理""招标人""投标人""保证金"等）。
   如果一个问题只由这些高频通用词组成，检索系统将无法区分应该返回哪个具体Chunk。
   你生成的每一个问题都必须包含足够的**唯一区分信息**，确保人类能够仅凭问题内容就判断出它指向的是哪个具体Chunk。
   - 对于法规类Chunk：问题中必须嵌入该法规的**唯一情境**或**具体数字/条件/法条号**。
   - 对于案例类Chunk：问题应包含该案例的**核心事实特征**。
   - 对于政策/解读类Chunk：问题应指向该文档**特有的观点、说明或具体解释对象**。
   - 禁止使用仅由"名词+通用动词"构成的问题。
3. **难度分布**：
   - easy: 答案直接包含在单个Chunk内，问题与原文高度相似。
   - medium: 答案在单个Chunk内，但需要简单语义转换或推理。
   - hard: 需要综合信息、进行否定/条件判断或对比。
4. **无幻觉**：所有问题和答案必须严格基于提供的Chunk内容，不得引入外部知识。
5. 每个片段生成一个问答对。"""

SYSTEM_PROMPT_CROSS = """你是一个企业级RAG系统评测集构建专家。你的任务是生成需要同时参考两个相关法律条文才能回答的问题，用于测试检索系统的跨片段召回能力。

## 输出格式
严格输出 JSON 数组，每个元素包含以下字段：
{
  "question": "模拟真实用户自然语言问题（需要两个片段的信息才能完整回答）",
  "expected_chunk_id": "第一个片段（主）的精确chunk_id",
  "acceptable_chunk_ids": ["第二个片段的chunk_id", "其他可接受chunk_id"],
  "answer": "综合两个片段信息给出完整答案",
  "difficulty": "easy|medium|hard"
}

## 生成要求
1. **真实口吻**：问题要像用户日常提问，禁止直接使用Chunk标题或拼接关键词。
2. **精准锚定**：每一个问题都必须包含足够的唯一区分信息，确保能区分于其他类似条款。
3. **跨片段必需**：问题必须需要两个片段的信息才能完整回答（可以是对比、条件关系、程序前后衔接、定义+例外等）。
4. **难度标准**：
   - easy: 两个片段信息的简单组合
   - medium: 需要理解两个片段之间的关系
   - hard: 需要深层推理或对比分析
5. **无幻觉**：所有问题和答案必须严格基于提供的Chunk内容。
6. 每个片段对生成一个问答对。"""


class QAGenerator:
    def __init__(self, total_limit: Optional[int] = None):
        self.total_limit = total_limit
        self._init_client()
        self.progress = self._load_progress()

    def _init_client(self):
        from config import settings
        api_key = settings.llm_api_key
        api_url = settings.llm_api_url
        base_url = api_url.replace("/chat/completions", "")
        if not api_key:
            raise RuntimeError(f"LLM_API_KEY 未设置（provider={settings.llm_provider}）")
        self._model = GEN_MODEL
        self._api_key = api_key
        self._base_url = base_url
        self.client = OpenAI(base_url=base_url, api_key=api_key)

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
                    max_tokens=16384,
                    timeout=300,
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
                return [result]  # 单个对象包装为列表
            return None
        except json.JSONDecodeError:
            import re
            # 尝试提取完整 JSON 数组
            match = re.search(r'\[.*\]', content, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            # 尝试修复截断的 JSON：补全最后不完整的对象
            # 找到最后一个完整的对象（以 }, 结尾或 } 结尾后跟 ]）
            truncated = re.search(r'\[(.*)', content, re.DOTALL)
            if truncated:
                inner = truncated.group(1)
                # 尝试逐个提取完整对象
                objects = re.findall(r'\{(?:[^{}]|\{[^{}]*\})*\}', inner)
                if objects:
                    try:
                        items = [json.loads(obj) for obj in objects]
                        return items
                    except json.JSONDecodeError:
                        pass
        return None

    def _infer_category(self, chunk: dict) -> str:
        ct = chunk.get("chunk_type", "")
        if ct in ("pdf_law_parent", "pdf_law_child"):
            return "法规原文"
        elif ct == "pdf_case_paragraph":
            return "案例"
        elif ct == "policy_doc":
            return "政策文件"
        elif ct == "opinion_news":
            return "观点新闻"
        return "其他"

    def _infer_source_type(self, chunk: dict) -> str:
        ct = chunk.get("chunk_type", "")
        if ct in ("pdf_law_parent", "pdf_law_child"):
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
        source = chunk.get("source_doc", "") or ""
        ct = chunk.get("chunk_type", "")
        # 简化归类
        if ct in ("pdf_law_parent", "pdf_law_child"):
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

    def _is_regulatory_strict(self, chunk: dict) -> bool:
        ct = chunk.get("chunk_type", "")
        return ct in ("pdf_law_parent", "pdf_law_child")

    def _build_single_prompt(self, chunks: List[dict], chunk_type: str) -> str:
        descriptions = []
        for i, c in enumerate(chunks):
            text = c.get("text", "") or c.get("retrieval_text", "")
            if len(text) > 1200:
                text = text[:1200] + "..."
            cid = c.get("id", "")
            law = c.get("law_name", "") or c.get("source_doc", "") or "未知"
            aid = c.get("article_id", "") or "N/A"
            descriptions.append(
                f"### 片段 {i+1}\n"
                f"- chunk_id: {cid}\n"
                f"- 法律/来源: {law}\n"
                f"- 条款号: {aid}\n"
                f"- 类别: {chunk_type}\n"
                f"- 文本内容:\n```\n{text}\n```"
            )

        type_desc = {
            "pdf_law_parent": "法规原文父级Chunk（完整法条）",
            "pdf_law_child": "法规原文子级Chunk（法条的子句片段）",
            "pdf_case_paragraph": "案例段落Chunk",
            "policy_doc": "政策文件Chunk",
            "opinion_news": "观点新闻Chunk",
        }.get(chunk_type, chunk_type)

        return (
            f"请为以下 {len(chunks)} 个{type_desc}各生成一个问答对。\n\n"
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
                f"### 片段对 {i+1}\n"
                f"- 法律: {law}\n"
                f"- 条款 {aid_a} (chunk_id: {c_a.get('id')}):\n```\n{text_a}\n```\n"
                f"- 条款 {aid_b} (chunk_id: {c_b.get('id')}):\n```\n{text_b}\n```"
            )
        return (
            f"请为以下 {len(pairs)} 对相邻法律条款各生成一个跨条款问答对。\n\n"
            + "\n---\n".join(descriptions) +
            "\n\n请输出 JSON 数组，按片段对顺序排列。"
        )

    def generate_single_batch(self, chunks: List[dict], chunk_type: str,
                               start_idx: int) -> List[dict]:
        if not chunks:
            return []
        content = self._call_llm(SYSTEM_PROMPT_SINGLE, self._build_single_prompt(chunks, chunk_type))
        if not content:
            return []
        qa_list = self._extract_json(content)
        if not qa_list:
            print(f"  JSON 解析失败，原始响应: {content[:300]}")
            return []

        results = []
        for i, qa in enumerate(qa_list):
            if i >= len(chunks):
                break
            chunk = chunks[i]
            qid = f"qa_v4_{start_idx + i + 1:04d}"
            expected_id = str(qa.get("expected_chunk_id", ""))
            if not expected_id:
                expected_id = chunk.get("id", "")
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
                "type": chunk_type,
                "category": self._infer_category(chunk),
                "sub_category": self._infer_sub_category(chunk),
                "chunk_type": chunk_type,
                "span": "single",
                "article_id": str(chunk.get("article_id", "")),
                "law_name": chunk.get("law_name", "") or chunk.get("source_doc", "") or "",
                "difficulty": qa.get("difficulty", "medium"),
                "expected_source_type": self._infer_source_type(chunk),
                "expected_answer_text": str(qa.get("answer", "")).strip(),
                "is_regulatory_strict": self._is_regulatory_strict(chunk),
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
            qid = f"qa_v4_cross_{start_idx + i + 1:04d}"
            expected_id = str(qa.get("expected_chunk_id", "")) or c_a.get("id", "")
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
                "category": self._infer_category(c_a),
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
        print("eval_benchmark_v4 生成器 (1000 QA pairs)")
        print("=" * 60)

        print(f"\n  分布: {json.dumps(DISTRIBUTION, ensure_ascii=False)}")

        # 1. 加载
        print("\n[1/4] 加载 chunks...")
        chunks = load_chunks()
        print(f"  已加载 {len(chunks)} 个 chunks")

        # 2. 抽样
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

        # 检查进度（用 chunk_id 追踪，因为 QA id 与 chunk id 不同）
        completed_ids = set()
        for qa in self.progress.get("generated_qas", []):
            completed_ids.add(qa.get("expected_chunk_id", ""))
            for aid in qa.get("acceptable_chunk_ids", []):
                completed_ids.add(aid)
        if completed_ids:
            print(f"\n  已完成的 chunk 数: {len(completed_ids)}（已有 {len(self.progress.get('generated_qas', []))} 个 QA）")

        # 3. 生成 single-chunk QA
        print(f"\n[3/4] 生成 QA 对...")
        all_qas = list(self.progress.get("generated_qas", []))
        qa_counter = len(all_qas)

        for ct in ["pdf_law_parent", "pdf_law_child", "pdf_case_paragraph", "policy_doc"]:
            # opinion_news 已排除出题
            items = sampled.get(ct, [])
            if not items:
                continue
            remaining = [c for c in items if c.get("id") not in completed_ids]
            if not remaining:
                print(f"  [{ct}] 全部已完成，跳过")
                continue

            print(f"\n  [{ct}] 生成 {len(remaining)} 个 QA ({len(items)-len(remaining)} 已完成)...")

            for batch_start in range(0, len(remaining), BATCH_SIZE):
                batch = remaining[batch_start:batch_start + BATCH_SIZE]
                bn = batch_start // BATCH_SIZE + 1
                total_bn = (len(remaining) - 1) // BATCH_SIZE + 1
                print(f"    批次 {bn}/{total_bn} ({len(batch)} chunks)...", end=" ", flush=True)

                new_qas = self.generate_single_batch(batch, ct, qa_counter)
                if new_qas:
                    all_qas.extend(new_qas)
                    for idx in range(len(new_qas)):
                        self.progress["generated_qas"] = all_qas
                        self.progress["total_generated"] = len(all_qas)
                        self._save_progress()
                    qa_counter += len(new_qas)
                    print(f"  OK (+{len(new_qas)}, {len(all_qas)} total)")
                else:
                    print("  FAIL")

                time.sleep(BATCH_DELAY)

        # 4. cross-chunk
        if cross_pairs:
            remaining_pairs = [p for p in cross_pairs
                               if p[0].get("id") not in completed_ids]
            if remaining_pairs:
                print(f"\n  [cross_chunk] 生成 {len(remaining_pairs)} 个 QA...")
                for batch_start in range(0, len(remaining_pairs), CROSS_BATCH_SIZE):
                    batch = remaining_pairs[batch_start:batch_start + CROSS_BATCH_SIZE]
                    bn = batch_start // CROSS_BATCH_SIZE + 1
                    total_bn = (len(remaining_pairs) - 1) // CROSS_BATCH_SIZE + 1
                    print(f"    批次 {bn}/{total_bn} ({len(batch)} pairs)...", end=" ", flush=True)

                    new_qas = self.generate_cross_batch(batch, qa_counter)
                    if new_qas:
                        all_qas.extend(new_qas)
                        qa_counter += len(new_qas)
                        self.progress["generated_qas"] = all_qas
                        self.progress["total_generated"] = len(all_qas)
                        self._save_progress()
                        print(f"OK ({len(all_qas)} total)")
                    else:
                        print("FAIL")

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

        # 重新编号
        for i, qa in enumerate(valid_qas):
            qa["id"] = f"qa_v4_{i+1:04d}"

        # 统计
        by_type = defaultdict(int)
        by_diff = defaultdict(int)
        by_span = defaultdict(int)
        for qa in valid_qas:
            by_type[qa.get("type", qa.get("chunk_type", "unknown"))] += 1
            by_diff[qa.get("difficulty", "unknown")] += 1
            by_span[qa.get("span", "unknown")] += 1

        output = {
            "version": "v4",
            "description": "基于 policy collection chunks 生成的召回评估问答集 (1000题, 增强提示词)",
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

        if PROGRESS_PATH.exists():
            PROGRESS_PATH.unlink()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="eval_benchmark_v4 生成器 (1000题)")
    parser.add_argument("--dry-run", action="store_true", help="仅预览抽样分布")
    parser.add_argument("--total", type=int, default=None, help="限制总数（测试用）")
    parser.add_argument("--resume", action="store_true", help="从断点继续")
    args = parser.parse_args()

    if not CHUNKS_PATH.exists():
        print(f"错误: chunks 文件不存在: {CHUNKS_PATH}")
        print("请先导出 policy_chunks_export.json")
        sys.exit(1)

    if args.dry_run:
        chunks = load_chunks()
        stats = sample_chunks(chunks, dry_run=True, total_limit=args.total)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return

    if not args.resume and PROGRESS_PATH.exists():
        PROGRESS_PATH.unlink()

    generator = QAGenerator(total_limit=args.total)
    generator.run()


if __name__ == "__main__":
    main()
