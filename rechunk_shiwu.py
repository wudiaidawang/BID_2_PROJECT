"""重新切分《招标投标法律解读与风险防范实务》——段落归并切法.

旧: sliding_window_chunk(500, 200) → chunk_type=pdf_case_sliding，无结构化字段
新: \n\n 分自然段 → 过滤 <50字 → 归并相邻段至 ~500字 → chunk_type=pdf_case_paragraph，带 law_name

删除旧 chunks → 重新 embedding → 入库 Milvus.
"""
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import fitz
from app.storage import get_vector_store
from app.core.embedding import EmbeddingService

PDF_PATH = "data/pdfs/招标投标法律解读与风险防范实务.pdf"
PDF_NAME = "招标投标法律解读与风险防范实务"
COLLECTION = "policy"
TARGET_CHARS = 500
MIN_PARA_CHARS = 50
DATA_VERSION = "2026-06-21_v2"


def extract_text(pdf_path):
    print(f"[1/5] 提取 PDF: {pdf_path}")
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    full_text = "\n".join(page.get_text() for page in doc if page.get_text())
    doc.close()
    print(f"      {total_pages} 页, {len(full_text)} 字符")
    return full_text


def chunk_by_paragraphs(text):
    """按双换行切自然段 → 过滤短段 → 归并至 ~500 字"""
    print(f"[2/5] 段落归并切块 (target={TARGET_CHARS}字, min={MIN_PARA_CHARS}字)")

    paragraphs = [p.strip() for p in text.split('\n\n') if len(p.strip()) > MIN_PARA_CHARS]
    print(f"      有效段落数: {len(paragraphs)}")

    chunks = []
    current = ""
    for p in paragraphs:
        if len(current) + len(p) < TARGET_CHARS:
            current = (current + "\n\n" + p).strip() if current else p
        else:
            if current:
                chunks.append(current)
            current = p
    if current:
        chunks.append(current)

    print(f"      归并后 chunk 数: {len(chunks)}")
    sizes = [len(c) for c in chunks]
    print(f"      大小: min={min(sizes)}, max={max(sizes)}, avg={sum(sizes)//len(sizes):.0f}")
    return chunks


def delete_old_chunks(client):
    """删除旧的 pdf_case_sliding chunks"""
    print(f"[3/5] 删除旧 chunks (source_doc='{PDF_NAME}', chunk_type='pdf_case_sliding')")

    filter_expr = f'source_doc == "{PDF_NAME}" and chunk_type == "pdf_case_sliding"'

    try:
        # 先查询旧 chunks 数量
        existing = client.query(COLLECTION, filter_expr, limit=10000)
        old_count = len(existing)
        print(f"      旧 chunks: {old_count} 条")

        if old_count == 0:
            print("      无需删除")
            return

        # 分批删除 (Milvus delete by filter)
        old_ids = [e["id"] for e in existing]
        batch_size = 100
        deleted = 0
        for i in range(0, len(old_ids), batch_size):
            batch = old_ids[i:i + batch_size]
            id_filter = ", ".join(f'"{eid}"' for eid in batch)
            client._post("/v2/vectordb/entities/delete", {
                "collectionName": COLLECTION,
                "dbName": client._base_payload(COLLECTION).get("dbName", ""),
                "filter": f"id in [{id_filter}]",
            })
            deleted += len(batch)
        print(f"      已删除 {deleted} 条")
    except Exception as e:
        print(f"      [WARN] 删除失败: {e}")


def build_retrieval_text(chunk, idx):
    """构建检索文本 — 注入书名作为 header"""
    return f"《{PDF_NAME}》\n{chunk}"


def import_new_chunks(client, chunks):
    """Embedding + 入库"""
    print(f"[4/5] Embedding + 入库 {len(chunks)} chunks ...")

    embed_service = EmbeddingService()
    batch_size = 32
    total = 0

    for batch_start in range(0, len(chunks), batch_size):
        batch = chunks[batch_start:batch_start + batch_size]
        rts = [build_retrieval_text(c, batch_start + i) for i, c in enumerate(batch)]
        embeddings = embed_service.embed_batch(rts)

        for i, chunk in enumerate(batch):
            idx = batch_start + i
            chunk_id = f"pdf_{PDF_NAME}_para_{idx:04d}"
            chunk_hash = hashlib.md5(chunk.encode()).hexdigest()[:8]

            metadata = {
                "source_doc": PDF_NAME,
                "chunk_type": "pdf_case_paragraph",
                "chunk_order": str(idx),
                "chunk_hash": chunk_hash,
                "law_name": PDF_NAME,          # ★ 关键: 使 parent-level 匹配生效
                "article_id": "",               # 无条款号，留空
                "category": "policy",
                "data_version": DATA_VERSION,
                "token_count": str(len(chunk)),
            }

            client.add_documents(
                COLLECTION,
                [rts[i]],
                [chunk],
                [metadata],
                [chunk_id],
            )
        total += len(batch)
        print(f"      {total}/{len(chunks)} ...")

    print(f"      入库完成: {total} 条")


def main():
    print("=" * 60)
    print(f"重新切分: {PDF_NAME}")
    print("=" * 60)

    text = extract_text(PDF_PATH)
    chunks = chunk_by_paragraphs(text)

    client = get_vector_store()
    delete_old_chunks(client)
    import_new_chunks(client, chunks)

    # 验证
    remaining = client.query(COLLECTION, f'source_doc == "{PDF_NAME}"', limit=5)
    print(f"\n[5/5] 验证: 当前 {PDF_NAME} 的 chunks (sample):")
    for r in remaining:
        print(f"      {r['id']}  type={r.get('chunk_type', '?')}")

    print(f"\n{'=' * 60}")
    print("[完成]")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
