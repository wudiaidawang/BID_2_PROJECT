#!/usr/bin/env python
"""PDF知识库初始化 - Parent-Child 结构化切块"""
import sys
import json
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent))

import fitz
from app.data.storage import get_vector_store
from config import settings
from app.data.legal_structure_parser import LegalStructureParser
from app.data.parent_chunk_builder import ParentChunkBuilder
from app.data.child_chunk_builder import ChildChunkBuilder

PDF_FILES = [
    {
        "path": "./data/pdfs/招标投标法律解读与风险防范实务.pdf",
        "name": "招标投标法律解读与风险防范实务",
        "author": "白如银",
        "chunk_size": 500,
        "overlap": 200,
        "chunk_mode": "sliding"       # 非法律条文，使用滑动窗口
    },
    {
        "path": "./data/pdfs/中华人民共和国招标投标法律法规全书.pdf",
        "name": "中华人民共和国招标投标法律法规全书",
        "author": "中国法制出版社",
        "chunk_size": 500,
        "overlap": 200,
        "chunk_mode": "law_article"   # 法律法规条文，使用结构化切块
    }
]

MANUAL_EVAL_PATH = "./data/manual_eval_set.json"


def sliding_window_chunk(text: str, chunk_size: int = 500, overlap: int = 100,
                         source_label: str = "") -> List[str]:
    """滑动窗口切块（用于非法律条文类 PDF）

    每个 chunk 前注入来源标签作为上下文锚点，
    使检索结果可追溯来源，避免语义漂浮。
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        if end < len(text):
            for sep in ['。', '\n', '；', '！', '？']:
                last_sep = text.rfind(sep, start, end)
                if last_sep > start + chunk_size // 2:
                    end = last_sep + 1
                    break

        chunk = text[start:end].strip()
        if chunk:
            if source_label:
                chunk = f"【{source_label}】\n{chunk}"
            chunks.append(chunk)

        start = end - overlap if end < len(text) else end

    return chunks


def extract_full_text_from_pdf(pdf_path: str) -> tuple:
    """提取PDF全文，返回 (full_text, total_pages)"""
    if not Path(pdf_path).exists():
        raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")

    doc = fitz.open(pdf_path)
    full_text_parts = []
    total_pages = len(doc)

    for page_num, page in enumerate(doc):
        page_text = page.get_text()
        if page_text:
            full_text_parts.append(page_text)

    doc.close()

    full_text = "\n".join(full_text_parts)
    print(f"  提取了 {total_pages} 页，共 {len(full_text)} 字符")

    return full_text, total_pages


def load_manual_eval_set() -> List[Dict]:
    """加载手工整理的评估集"""
    if not Path(MANUAL_EVAL_PATH).exists():
        return []

    with open(MANUAL_EVAL_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def chunk_by_structure(full_text: str, pdf_name: str) -> tuple:
    """
    使用 Parent-Child 结构化切块管道。

    管道: LegalStructureParser → ParentChunkBuilder → ChildChunkBuilder

    返回: (searchable_chunks, all_metadatas, all_ids, stats)
      - searchable_chunks: 用于检索的 chunks（短 parents + children）
      - 同时返回 parents 用于单独入库（供 ParentContextRetriever 查询）
    """
    # Step 1: 解析法律结构
    parser = LegalStructureParser()
    documents = parser.parse(full_text, pdf_name)
    doc_stats = parser.get_statistics(documents)

    print(f"  [统计] 解析结果: {doc_stats['law_count']} 部法律, "
          f"{doc_stats['chapter_count']} 章, {doc_stats['article_count']} 条")
    for name in doc_stats.get("law_names", [])[:5]:
        print(f"    - {name}")

    if doc_stats["article_count"] == 0:
        print("  [警告] 未解析到法条，回退到滑动窗口切块")
        return None

    # Step 2: 构建 Parent Chunks
    parent_builder = ParentChunkBuilder(source=pdf_name, header_injection=True)
    parents = parent_builder.build(documents)
    print(f"  [Parent] Parent chunks: {len(parents)} 条")

    # Step 3: 构建 Child Chunks
    child_builder = ChildChunkBuilder()
    searchable_parents, children = child_builder.build_all(parents)
    print(f"  [Child] Child chunks: {len(children)} 条 (来自长法条)")
    print(f"  [Parent] 可检索 Parent chunks: {len(searchable_parents)} 条 (短法条)")

    # 组装入库数据
    all_chunks = []
    all_metadatas = []
    all_ids = []

    # 入库可检索的 parents（短法条）
    for i, p in enumerate(searchable_parents):
        all_chunks.append(p["content"])
        all_metadatas.append(p["metadata"])
        all_ids.append(p["chunk_id"])

    # 入库 children
    for i, c in enumerate(children):
        all_chunks.append(c["content"])
        all_metadatas.append(c["metadata"])
        all_ids.append(c["chunk_id"])

    # 同时入库 parent-only chunks（仅供 ParentContextRetriever 查询，不参与检索）
    # 这些是长法条的完整内容
    parent_only_chunks = []
    parent_only_metadatas = []
    parent_only_ids = []

    # 找出不在 searchable_parents 中的 parents（即被拆分了的长法条）
    searchable_ids = {p["chunk_id"] for p in searchable_parents}
    for p in parents:
        if p["chunk_id"] not in searchable_ids:
            parent_only_chunks.append(p["content"])
            parent_only_metadatas.append(p["metadata"])
            parent_only_ids.append(p["chunk_id"])

    stats = {
        "law_count": doc_stats["law_count"],
        "chapter_count": doc_stats["chapter_count"],
        "article_count": doc_stats["article_count"],
        "parent_count": len(parents),
        "child_count": len(children),
        "searchable_parent_count": len(searchable_parents),
        "total_searchable": len(all_chunks),
    }

    return {
        "searchable_chunks": all_chunks,
        "searchable_metadatas": all_metadatas,
        "searchable_ids": all_ids,
        "parent_only_chunks": parent_only_chunks,
        "parent_only_metadatas": parent_only_metadatas,
        "parent_only_ids": parent_only_ids,
        "stats": stats,
    }


def process_pdf_to_store(pdf_config: Dict, client):
    """处理PDF并入Chroma（路由到滑动窗口或结构化切块）"""
    pdf_path = pdf_config["path"]
    pdf_name = pdf_config["name"]
    author = pdf_config.get("author", "")
    chunk_mode = pdf_config.get("chunk_mode", "sliding")
    chunk_size = pdf_config.get("chunk_size", 500)
    overlap = pdf_config.get("overlap", 100)

    print(f"\n处理: {pdf_name} (模式: {chunk_mode})")

    if not Path(pdf_path).exists():
        print(f"  跳过：文件不存在 -> {pdf_path}")
        return

    full_text, total_pages = extract_full_text_from_pdf(pdf_path)
    if not full_text or len(full_text) < 100:
        print(f"  跳过：文本内容不足")
        return

    if chunk_mode == "law_article":
        # ── 结构化切块管道 ──
        result = chunk_by_structure(full_text, pdf_name)

        if result is None:
            # 解析失败，回退到滑动窗口
            print("  [警告] 回退到滑动窗口切块")
            chunks = sliding_window_chunk(full_text, chunk_size, overlap, source_label=pdf_name)
            metadatas = []
            ids = []
            for i, chunk in enumerate(chunks):
                metadatas.append({
                    "source": pdf_name, "author": author,
                    "chunk_index": i, "total_pages": total_pages,
                    "type": "pdf_regulation"
                })
                ids.append(f"reg_{pdf_name}_{i}_{hash(chunk) % 10000}")
            client.add_documents("regulations", chunks, metadatas, ids)
            print(f"  已入库 {len(chunks)} 条到 regulations 库 (滑动窗口)")
            return

        stats = result["stats"]
        print(f"  [统计] 入库统计: {stats['total_searchable']} 条可检索 "
              f"({stats['searchable_parent_count']} parents + {stats['child_count']} children)")

        # 入库可检索 chunks
        if result["searchable_chunks"]:
            client.add_documents(
                "regulations",
                result["searchable_chunks"],
                result["searchable_metadatas"],
                result["searchable_ids"]
            )
            print(f"  [完成] 已入库 {len(result['searchable_chunks'])} 条可检索 chunk")

        # 入库 parent-only chunks（仅供上下文扩展查询）
        if result["parent_only_chunks"]:
            client.add_documents(
                "regulations",
                result["parent_only_chunks"],
                result["parent_only_metadatas"],
                result["parent_only_ids"]
            )
            print(f"  [完成] 已入库 {len(result['parent_only_chunks'])} 条 parent chunk (长法条完整内容)")

    else:
        # ── 滑动窗口切块（非法律条文类 PDF）──
        chunks = sliding_window_chunk(full_text, chunk_size, overlap, source_label=pdf_name)
        print(f"  切块: {len(chunks)} 条")

        if not chunks:
            print(f"  警告：无有效chunk")
            return

        metadatas = []
        ids = []
        for i, chunk in enumerate(chunks):
            metadatas.append({
                "source": pdf_name,
                "author": author,
                "chunk_index": i,
                "total_pages": total_pages,
                "type": "pdf_regulation"
            })
            ids.append(f"reg_{pdf_name}_{i}_{hash(chunk) % 10000}")

        client.add_documents("regulations", chunks, metadatas, ids)
        print(f"  已入库 {len(chunks)} 条到 regulations 库")


def main():
    print("=" * 60)
    print("PDF知识库初始化工具 (Parent-Child 结构化切块)")
    print("=" * 60)
    print("策略：法律法规 → Parent-Child 结构切块")
    print("      法律解读 → 滑动窗口切块")
    print("=" * 60)

    client = get_vector_store()

    print("\n[清理] 清空现有 regulations 库...")
    client.delete_collection("regulations")
    print("[完成] Regulations 库已清空（BM25 索引将在下次检索时重建）")

    for pdf_config in PDF_FILES:
        process_pdf_to_store(pdf_config, client)

    print("\n" + "=" * 60)
    print("[完成] 初始化完成!")
    print(f"  Regulations库总计: {client.get_count('regulations')} 条")
    print("=" * 60)

    eval_dir = Path("./data/eval_questions")
    if eval_dir.exists():
        json_files = sorted(eval_dir.glob("*.json"))
        total = 0
        for jf in json_files:
            with open(jf, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                total += len(data)
        if total:
            print(f"\n[评估] 评估集: {total} 条 (来自 {eval_dir}/)")
        else:
            print(f"\n[提示] 提示：如需评估准确率，请将问答 .json 文件放入:")
            print(f"  {eval_dir}/")
            print(f"  格式参考: {eval_dir}/template.json")
    else:
        print(f"\n[提示] 提示：评估集目录不存在，请创建: {eval_dir}/")


if __name__ == "__main__":
    main()
