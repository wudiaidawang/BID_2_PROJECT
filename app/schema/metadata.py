"""
统一 Chunk Metadata Schema

所有 pipeline 阶段只认这套字段。
入库时按此 schema 写入，检索时按此 schema 读取。
"""

from typing import Dict, List

# ── 规范字段定义 ──────────────────────────────────────────────
# 每个字段的含义、来源、消费者

CANONICAL_FIELDS: Dict[str, str] = {
    # ── 文档归属 ──
    "source":      "PDF 文件名或数据源标识（如 '中华人民共和国招标投标法律法规全书.pdf'）",
    "collection":  "ChromaDB 集合名：'regulations' | 'bids'",

    # ── 法条定位（非法律类 chunk 为空字符串）──
    "law_name":    "法律名称（如 '中华人民共和国招标投标法'）",
    "chapter":     "章节名（如 '第三章 投标'）",
    "article":     "法条中文编号（如 '第二十七条'）",
    "article_id":  "法条阿拉伯数字编号（如 '27'）",

    # ── Chunk 结构 ──
    "chunk_type":  "'parent' | 'child' | 'sliding'",
    "parent_id":   "child 指向的 parent chunk_id；parent/sliding 为空字符串",

    # ── 正文（两类字段，职责分离）──
    # text:      embedding 文本（含 header_injection），用于检索
    # content:   原始法条/段落正文（不含 header），用于生成
    "text":        "embedding 文本（可能含 header_injection）",
    "content":     "原始正文（生成时用）",
    "parent_content": "完整法条内容（检索后由 ParentExpander 填充，非入库字段）",

    # ── 通用标记 ──
    "page_index":  "PDF 页码（0-based）",
    "total_pages": "PDF 总页数",

    # ── 运行时字段（非入库）──
    "score":       "检索得分（检索阶段填充）",
    "id":          "ChromaDB 文档 ID",
}

# ── 字段别名映射：旧字段 → 规范字段 ──────────────────────────
# 用于兼容已入库的旧数据和旧代码引用

FIELD_ALIASES: Dict[str, str] = {
    "doc_title":   "law_name",
    "article_num": "article_id",
    "type":        "chunk_type",
    "data":        "metadata",     # "data" 和 "metadata" 是同一个东西
    "winner":      "supplier",
    "项目名称":     "project_name",
    "中标人":       "supplier",
}


def normalize_chunk(chunk: Dict) -> Dict:
    """
    将任意格式的 chunk 规范化为统一 schema。

    规则：
    1. 确保 'metadata' 和 'data' 同时存在（兼容过渡期）
    2. 在 metadata 内应用 FIELD_ALIASES（旧字段 → 新字段）
    3. 保证核心字段有默认值
    """
    # 1. 统一 metadata/data
    meta = chunk.get("metadata") or chunk.get("data") or {}
    chunk["metadata"] = meta
    chunk["data"] = meta  # 过渡期兼容

    # 2. 应用别名
    for old_key, new_key in FIELD_ALIASES.items():
        if old_key in meta and new_key not in meta:
            meta[new_key] = meta[old_key]
        # 也检查顶层
        if old_key in chunk and new_key not in chunk:
            chunk[new_key] = chunk[old_key]

    # 3. 保证 chunk_type 有值
    if not meta.get("chunk_type"):
        # 从 parent_id 推断
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
