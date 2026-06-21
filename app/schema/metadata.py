"""
统一 Chunk Schema

三层解耦:
  retrieval_text — Embedding + BM25 输入（含 header/law_name/article_id，不展示）
  text           — 用户展示 + 最终回答引用（纯原文，无任何编码前缀）
  metadata       — 过滤 / 评测 / Citation / Agent 扩展（scalar 字段 + JSON blob）

Schema 设计原则:
  1. embed(retrieval_text)  — 绝不 embed(text + metadata)
  2. text 绝不拼接 chunk_type、法规名、条号等前缀
  3. id 稳定可复现，不含随机 UUID
  4. chunk_hash 用于查重与版本追踪
"""

from typing import Dict, List

# ── Schema 版本 ──
SCHEMA_VERSION = "2.0"

# ── chunk_type 完整枚举 ──
CHUNK_TYPES = {
    "bid_project":          "招标项目记录 (bids collection)",
    "regulation_parent":    "法规结构化父chunk，短法条 (regulations)",
    "regulation_child":     "法规结构化子chunk (regulations)",
    "regulation_sliding":   "法规滑动窗口chunk (regulations)",
    "policy_doc":           "政策文件记录 (policy)",
    "opinion_news":         "舆情新闻记录 (policy)",
    "pdf_law_parent":       "PDF法律条文父chunk (policy)",
    "pdf_law_child":        "PDF法律条文子chunk (policy)",
    "pdf_law_sliding":      "PDF法律条文滑动窗口 (policy)",
    "pdf_case_sliding":     "PDF案例分析滑动窗口 (policy)",
}

# ── 规范字段定义 ──

CANONICAL_FIELDS: Dict[str, str] = {
    # ── 主键 ──
    "id":           "稳定可复现 chunk ID，含语义信息（如 parent_价格法_10_174_6852）",

    # ── 正文（解耦）──
    "retrieval_text": "★ Embedding + BM25 输入（含 header_injection），不展示给用户",
    "text":           "★ 用户展示 + 最终回答引用的纯原文，无任何前缀污染",

    # ── 识别与溯源 ──
    "title":        "人类可读标题",
    "source_doc":   "来源文件名或 URL",
    "chunk_type":   "chunk 类型标识，见 CHUNK_TYPES 枚举",
    "chunk_order":  "源内排序（0, 1, 2... 或 article_id 或 article_id_childN）",
    "chunk_hash":   "MD5(text) 前12位，查重与版本追踪",
    "token_count":  "text 字符数，上下文预算估算",

    # ── 法条定位（非法律类为空字符串）──
    "law_name":     "法律名称（如 '中华人民共和国招标投标法'）",
    "chapter":      "章节名（如 '第三章 投标'）",
    "article":      "法条中文编号（如 '第二十七条'）",
    "article_id":   "法条阿拉伯数字编号（如 '27'）",
    "parent_id":    "child 指向的 parent chunk_id；非 child 为空",

    # ── 业务字段 ──
    "project_name": "招标项目名称（bids 专用）",
    "supplier":     "中标人/供应商",
    "region":       "省份",
    "publish_date": "发布日期",
    "category":     "数据子类别",

    # ── 版本管理 ──
    "data_version": "导入批次号（如 '2026-06-18_v1'）",

    # ── 扩展 ──
    "metadata":     "JSON blob，不入 embedding，可扩展任意字段",

    # ── 运行时字段（非入库）──
    "score":                "检索得分（检索阶段填充）",
    "parent_content":       "完整法条内容（检索后由 ParentExpander 填充，非入库字段）",
    "collection":           "所属 Milvus collection",
    "source_type":          "数据来源分类（运行时推演: bid/regulation/policy/opinion/case）",
}

# ── 字段别名映射 ──

FIELD_ALIASES: Dict[str, str] = {
    "doc_title":    "law_name",
    "article_num":  "article_id",
    "type":         "chunk_type",
    "data":         "metadata",
    "winner":       "supplier",
    "source":       "source_doc",
    "content":      "retrieval_text",
    "chunk_index":  "chunk_order",
    "项目名称":      "project_name",
    "中标人":        "supplier",
    "省份":          "region",
    "发布时间":      "publish_date",
    "类别":          "category",
}


def normalize_chunk(chunk: Dict) -> Dict:
    """规范化 chunk 字段，确保 retrieval_text / text / metadata 三层就位"""
    # 1. 统一 metadata
    meta = chunk.get("metadata") or chunk.get("data") or {}
    chunk["metadata"] = meta

    # 2. 应用别名
    for old_key, new_key in FIELD_ALIASES.items():
        if old_key in meta and new_key not in meta:
            meta[new_key] = meta[old_key]
        if old_key in chunk and new_key not in chunk:
            chunk[new_key] = chunk[old_key]

    # 3. 确保 retrieval_text 和 text 都有值
    if not chunk.get("retrieval_text"):
        chunk["retrieval_text"] = chunk.get("text", "")
    if not chunk.get("text"):
        chunk["text"] = chunk.get("retrieval_text", "")

    # 4. chunk_type 推断
    if not meta.get("chunk_type"):
        if meta.get("parent_id"):
            meta["chunk_type"] = "child"
        elif meta.get("article_id"):
            meta["chunk_type"] = "parent"
        else:
            meta["chunk_type"] = "sliding"

    return chunk


def normalize_chunks(chunks: List[Dict]) -> List[Dict]:
    """批量规范化"""
    return [normalize_chunk(c) for c in chunks]


def infer_source_type(collection: str, metadata: dict) -> str:
    """运行时推演 source_type，不入库、不重新向量化。

    三级分类（法条原文 vs 解读手册 vs 案例舆情）：
      bid                     → "bid"
      regulation_parent       → "regulation_article"   法条原文（结构化父块）
      regulation_child        → "regulation_article"   法条原文（结构化子块）
      regulation_sliding      → "regulation_article"   法条原文（滑动窗口）
      pdf_law_*               → "regulation_article"   法条原文（PDF 法律）
      pdf_case_sliding        → "regulation_case"      案例解读
      opinion_news            → "regulation_opinion"   舆情
      policy_doc              → "regulation_policy"    政策文件
    """
    ct = str(metadata.get("chunk_type", ""))

    # bids 类（按业务字段判断）
    if metadata.get("project_name") or metadata.get("supplier"):
        return "bid"
    if ct == "bid_project":
        return "bid"

    # regulation 子类
    if ct.startswith("pdf_case_"):
        return "regulation_case"
    if ct == "opinion_news" or str(metadata.get("category", "")) == "opinion":
        return "regulation_opinion"
    if ct == "policy_doc":
        return "regulation_policy"
    # pdf_law_*, regulation_*, sliding, parent, child, 及其他 → 法条原文
    if collection == "panxin_bid_rag_v1" or ct.startswith("regulation_") or ct.startswith("pdf_law_") or metadata.get("law_name"):
        return "regulation_article"
    # fallback
    return "regulation_article"
