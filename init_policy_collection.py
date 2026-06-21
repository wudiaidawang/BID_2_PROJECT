#!/usr/bin/env python
"""
初始化 Milvus policy collection
数据来源: policy_data.xlsx + opinion_data.xlsx + 全部10个PDF
category 字段区分: "policy" (政策法规) / "opinion" (舆情新闻)
"""

import hashlib
import sys
import json
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent))

import fitz
import pandas as pd
from config import settings
from app.storage import get_vector_store
from app.core.legal_structure_parser import LegalStructureParser
from app.core.parent_chunk_builder import ParentChunkBuilder
from app.core.child_chunk_builder import ChildChunkBuilder

RAW_DIR = Path(__file__).parent / "data" / "raw"
PDF_DIR = Path(__file__).parent / "data" / "pdfs"

# 10个PDF全部处理
PDF_CONFIGS = [
    # 法律条文类 → 结构化Parent-Child切块
    {"path": "中华人民共和国招标投标法律法规全书.pdf", "name": "中华人民共和国招标投标法律法规全书", "author": "中国法制出版社", "mode": "law_article"},
    {"path": "中华人民共和国政府采购法实施条例.pdf", "name": "中华人民共和国政府采购法实施条例", "author": "", "mode": "law_article"},
    {"path": "政府采购货物和服务招标投标管理办法.pdf", "name": "政府采购货物和服务招标投标管理办法", "author": "", "mode": "law_article"},
    {"path": "工程建设项目施工招标投标办法.pdf", "name": "工程建设项目施工招标投标办法", "author": "", "mode": "law_article"},
    # 法律解读/案例类 → 滑动窗口切块（实务使用段落归并）
    {"path": "招标投标法律解读与风险防范实务.pdf", "name": "招标投标法律解读与风险防范实务", "author": "白如银", "mode": "paragraph"},
    {"path": "串通投标、受贿案.pdf", "name": "串通投标、受贿案", "author": "", "mode": "sliding"},
    {"path": "运输服务公司串通投标不正当竞争纠纷案.pdf", "name": "运输服务公司串通投标不正当竞争纠纷案", "author": "", "mode": "sliding"},
    {"path": "建设工程施工合同纠纷案.pdf", "name": "建设工程施工合同纠纷案", "author": "", "mode": "sliding"},
    {"path": "非国家工作人员行贿案.pdf", "name": "非国家工作人员行贿案", "author": "", "mode": "sliding"},
    {"path": "建工集团公司建设工程施工合同纠纷案.pdf", "name": "建工集团公司建设工程施工合同纠纷案", "author": "", "mode": "sliding"},
]


def sliding_window_chunk(text: str, chunk_size: int = 500, overlap: int = 100,
                         source_label: str = "") -> List[str]:
    """滑动窗口切块（案例、解读类PDF）"""
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


def chunk_by_paragraphs(full_text: str, pdf_name: str,
                       target_chars: int = 500, min_para_chars: int = 50) -> List[str]:
    """段落归并切块（案例/解读类PDF，替代滑动窗口）

    流程: \\n\\n分自然段 → 过滤短段 → 相邻段归并至 ~500字
    检索文本注入书名头: 《pdf_name》\\n{chunk}
    """
    paragraphs = [p.strip() for p in full_text.split('\n\n') if len(p.strip()) > min_para_chars]
    print(f"      有效段落: {len(paragraphs)}")

    chunks = []
    current = ""
    for p in paragraphs:
        if len(current) + len(p) < target_chars:
            current = (current + "\n\n" + p).strip() if current else p
        else:
            if current:
                chunks.append(current)
            current = p
    if current:
        chunks.append(current)

    print(f"      归并后: {len(chunks)} chunks, "
          f"size min={min(len(c) for c in chunks)}, "
          f"max={max(len(c) for c in chunks)}, "
          f"avg={sum(len(c) for c in chunks)//len(chunks):.0f}")
    return chunks


def chunk_by_structure(full_text: str, pdf_name: str):
    """Parent-Child结构化切块（法律条文类PDF）"""
    parser = LegalStructureParser()
    documents = parser.parse(full_text, pdf_name)
    doc_stats = parser.get_statistics(documents)

    print(f"    解析: {doc_stats['law_count']}部法律, {doc_stats['chapter_count']}章, {doc_stats['article_count']}条")
    if doc_stats["article_count"] == 0:
        return None

    parent_builder = ParentChunkBuilder(source=pdf_name, header_injection=True,
                                        chunk_type="pdf_law_parent")
    parents = parent_builder.build(documents)

    child_builder = ChildChunkBuilder(chunk_type="pdf_law_child")
    searchable_parents, children = child_builder.build_all(parents)

    all_rt, all_texts, all_metadatas, all_ids = [], [], [], []

    for p in searchable_parents:
        all_rt.append(p["retrieval_text"])
        all_texts.append(p["text"])
        all_metadatas.append(p["metadata"])
        all_ids.append(p["chunk_id"])

    for c in children:
        all_rt.append(c["retrieval_text"])
        all_texts.append(c["text"])
        all_metadatas.append(c["metadata"])
        all_ids.append(c["chunk_id"])

    # 长法条的parent-only chunks
    searchable_ids = {p["chunk_id"] for p in searchable_parents}
    for p in parents:
        if p["chunk_id"] not in searchable_ids:
            all_rt.append(p["retrieval_text"])
            all_texts.append(p["text"])
            all_metadatas.append(p["metadata"])
            all_ids.append(p["chunk_id"])

    return all_rt, all_texts, all_metadatas, all_ids


def extract_pdf_text(pdf_path: str) -> tuple:
    """提取PDF全文"""
    if not Path(pdf_path).exists():
        raise FileNotFoundError(f"PDF不存在: {pdf_path}")
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    parts = []
    for page in doc:
        t = page.get_text()
        if t:
            parts.append(t)
    doc.close()
    full_text = "\n".join(parts)
    print(f"    提取 {total_pages} 页, {len(full_text)} 字符")
    return full_text, total_pages


def load_policy_collection(client):
    """核心: 创建 policy collection 并导入全部数据"""
    print("=" * 60)
    print("[Milvus] 初始化 policy collection")
    print("=" * 60)

    # ── Step 1: 导入 policy_data.xlsx ──
    policy_path = RAW_DIR / "policy_data.xlsx"
    if policy_path.exists():
        print(f"\n[1/3] 导入政策数据: {policy_path}")
        df = pd.read_excel(policy_path)
        print(f"  读取 {len(df)} 条")

        def build_policy_text(record):
            parts = [
                str(record.get('政策标题', '')),
                str(record.get('发布机构', '')),
                str(record.get('正文摘要', '')),
                str(record.get('法规分类', '')),
            ]
            return ' '.join([p for p in parts if p and str(p).lower() != 'nan'])

        retrieval_texts, texts, metas, ids = [], [], [], []
        for i, row in df.iterrows():
            record = row.to_dict()
            rt = build_policy_text(record)
            if rt and len(rt) > 5:
                retrieval_texts.append(rt)
                texts.append(rt)  # Excel 数据 retrieval_text = text（无 header 注入）
                clean = {k: (str(v) if pd.notna(v) else "") for k, v in record.items()}
                clean["category"] = "policy"
                clean["chunk_type"] = "policy_doc"
                clean["data_version"] = "2026-06-18_v1"
                clean["source_doc"] = "policy_data.xlsx"
                clean["chunk_order"] = str(i)
                metas.append(clean)
                ids.append(f"policy_{i}")
        client.add_documents("policy", retrieval_texts, texts, metas, ids)
        print(f"  入库 {len(retrieval_texts)} 条 (category=policy)")

    # ── Step 2: 导入 opinion_data.xlsx ──
    opinion_path = RAW_DIR / "opinion_data.xlsx"
    if opinion_path.exists():
        print(f"\n[2/3] 导入舆情数据: {opinion_path}")
        df = pd.read_excel(opinion_path)
        print(f"  读取 {len(df)} 条")

        def build_opinion_text(record):
            parts = [
                str(record.get('舆情标题', '')),
                str(record.get('舆情内容', '')),
                str(record.get('新闻来源', '')),
                str(record.get('搜索关键词', '')),
            ]
            return ' '.join([p for p in parts if p and str(p).lower() != 'nan'])

        retrieval_texts, texts, metas, ids = [], [], [], []
        for i, row in df.iterrows():
            record = row.to_dict()
            rt = build_opinion_text(record)
            if rt and len(rt) > 5:
                retrieval_texts.append(rt)
                texts.append(rt)  # Excel 数据 retrieval_text = text
                clean = {k: (str(v) if pd.notna(v) else "") for k, v in record.items()}
                clean["category"] = "opinion"
                clean["chunk_type"] = "opinion_news"
                clean["data_version"] = "2026-06-18_v1"
                clean["source_doc"] = "opinion_data.xlsx"
                clean["chunk_order"] = str(i)
                metas.append(clean)
                ids.append(f"opinion_{i}")
        client.add_documents("policy", retrieval_texts, texts, metas, ids)
        print(f"  入库 {len(retrieval_texts)} 条 (category=opinion)")

    # ── Step 3: 导入全部10个PDF ──
    print(f"\n[3/3] 导入PDF法规 ({len(PDF_CONFIGS)} 个文件)")
    for cfg in PDF_CONFIGS:
        pdf_path = str(PDF_DIR / cfg["path"])
        print(f"\n  处理: {cfg['name']} (模式: {cfg['mode']})")

        if not Path(pdf_path).exists():
            print(f"    [跳过] 文件不存在")
            continue

        try:
            full_text, total_pages = extract_pdf_text(pdf_path)
            if not full_text or len(full_text) < 100:
                print(f"    [跳过] 文本不足")
                continue

            if cfg["mode"] == "law_article":
                result = chunk_by_structure(full_text, cfg["name"])
                if result is None:
                    # 回退滑动窗口
                    chunks = sliding_window_chunk(full_text, 500, 200, source_label=cfg["name"])
                    rts, txts, metas, ids = [], [], [], []
                    for i, chunk in enumerate(chunks):
                        rts.append(chunk)
                        txts.append(chunk)
                        metas.append({
                            "source_doc": cfg["name"], "author": cfg.get("author", ""),
                            "chunk_order": str(i), "total_pages": total_pages,
                            "chunk_type": "pdf_law_sliding", "category": "policy",
                            "data_version": "2026-06-18_v1",
                        })
                        ids.append(f"pdf_{cfg['name']}_{i}_{hash(chunk) % 10000}")
                    client.add_documents("policy", rts, txts, metas, ids)
                    print(f"    入库 {len(chunks)} 条 (滑动窗口回退)")
                else:
                    all_rt, all_texts, metadatas, ids = result
                    for m in metadatas:
                        m["category"] = "policy"
                        m["data_version"] = "2026-06-18_v1"
                    client.add_documents("policy", all_rt, all_texts, metadatas, ids)
                    print(f"    入库 {len(all_rt)} 条 (结构化)")
            elif cfg["mode"] == "paragraph":
                # ★ 段落归并切块 — 实务类PDF专用
                chunks = chunk_by_paragraphs(full_text, cfg["name"])
                rts, txts, metas, ids = [], [], [], []
                for i, chunk in enumerate(chunks):
                    chunk_hash = hashlib.md5(chunk.encode()).hexdigest()[:8]
                    rts.append(f"《{cfg['name']}》\n{chunk}")     # 检索文本注入书名
                    txts.append(chunk)                             # 纯原文
                    metas.append({
                        "source_doc": cfg["name"],
                        "chunk_type": "pdf_case_paragraph",
                        "chunk_order": str(i),
                        "chunk_hash": chunk_hash,
                        "law_name": cfg["name"],                   # ★ parent级匹配关键
                        "article_id": "",
                        "category": "policy",
                        "data_version": "2026-06-22_v2",
                        "token_count": str(len(chunk)),
                    })
                    ids.append(f"pdf_{cfg['name']}_para_{i:04d}")
                client.add_documents("policy", rts, txts, metas, ids)
                print(f"    入库 {len(chunks)} 条 (段落归并)")
            else:
                chunks = sliding_window_chunk(full_text, 500, 200, source_label=cfg["name"])
                rts, txts, metas, ids = [], [], [], []
                for i, chunk in enumerate(chunks):
                    rts.append(chunk)
                    txts.append(chunk)
                    metas.append({
                        "source_doc": cfg["name"], "author": cfg.get("author", ""),
                        "chunk_order": str(i), "total_pages": total_pages,
                        "chunk_type": "pdf_case_sliding", "category": "policy",
                        "data_version": "2026-06-18_v1",
                    })
                    ids.append(f"pdf_{cfg['name']}_{i}_{hash(chunk) % 10000}")
                client.add_documents("policy", rts, txts, metas, ids)
                print(f"    入库 {len(chunks)} 条 (滑动窗口)")

        except Exception as e:
            print(f"    [ERROR] {e}")

    print(f"\n{'=' * 60}")
    print(f"[完成] Policy 库总计: {client.get_count('policy')} 条")
    print(f"{'=' * 60}")


def main():
    print("=" * 60)
    print("Milvus Policy Collection 初始化")
    print("=" * 60)

    client = get_vector_store()

    # ★ 安全模式: 不清空已有数据，仅确保 collection 存在 + 增量导入
    load_policy_collection(client)


if __name__ == "__main__":
    main()
