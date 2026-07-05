#!/usr/bin/env python3
"""
结构化重切《招标投标法律解读与风险防范实务》

旧: chunk_by_paragraphs() → chunk_type=pdf_case_paragraph (~500字段落归并)
新: 章→节→相关案例 结构解析 → chunk_type=pdf_case_structured (完整语义单元)

切块边界:
  一级: 第X章 — 章级话题
  二级: 第X节 — 节级话题
  三级: 相关案例X-Y — 案例边界
  辅助: 一、/（一）— 对大段落进一步切分

用法:
  python init_scripts/rechunk_case_book.py             # 全量执行
  python init_scripts/rechunk_case_book.py --dry-run   # 仅分析，不写库
"""

import sys, re, hashlib, argparse
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from collections import defaultdict

# 支持本地和服务器两种环境
_LOCAL_ROOT = str(Path(__file__).parent.parent)
_SERVER_ROOT = "/home/admin/group_three_5_11/data_pan"
sys.path.insert(0, _LOCAL_ROOT)
if Path(_SERVER_ROOT).exists():
    sys.path.insert(0, _SERVER_ROOT)

import fitz
from app.storage import get_vector_store
from app.core.embedding import EmbeddingService

PDF_NAME = "招标投标法律解读与风险防范实务"

def _find_pdf():
    """自动查找 PDF，兼容本地和服务器路径"""
    candidates = [
        Path(__file__).parent.parent / "data" / "pdfs" / f"{PDF_NAME}.pdf",
        Path("/home/admin/group_three_5_11/data_pan/data/pdfs") / f"{PDF_NAME}.pdf",
        Path("data/pdfs") / f"{PDF_NAME}.pdf",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    raise FileNotFoundError(f"找不到 PDF: {PDF_NAME}")

PDF_PATH = _find_pdf()
COLLECTION = "policy_v9"
DATA_VERSION = "2026-07-04_v3"
CHUNK_TYPE = "pdf_case_structured"

MIN_CHUNK = 80
MAX_CHUNK = 1800
EMBED_BATCH = 32


# ── PDF 提取 ──

def extract_text(pdf_path: str) -> str:
    print(f"[1/5] 提取 PDF: {pdf_path}")
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    parts = [page.get_text() for page in doc if page.get_text()]
    doc.close()
    full_text = "\n".join(parts)
    print(f"      {total_pages} 页, {len(full_text)} 字符")
    return full_text


# ── 结构解析 ──

def _split_large(text: str, max_chars: int = MAX_CHUNK) -> List[str]:
    """对过长段落按子节（一、/（一）/1.）进一步切分"""
    # 找所有子节标记
    sub_pattern = r'(?:^|\n)(?=(?:（[一二三四五六七八九十\d]+）|[一二三四五六七八九十]+、)\s*)'
    parts = re.split(sub_pattern, text, flags=re.MULTILINE)

    result = []
    for part in parts:
        part = part.strip()
        if not part or len(part) < MIN_CHUNK:
            continue
        if len(part) <= max_chars:
            result.append(part)
        else:
            # 仍然过长，按 \n\n 强制切分
            paras = [p.strip() for p in part.split('\n\n') if p.strip()]
            current = ""
            for p in paras:
                if len(current) + len(p) < max_chars:
                    current = (current + "\n\n" + p).strip() if current else p
                else:
                    if current and len(current) >= MIN_CHUNK:
                        result.append(current)
                    current = p
            if current and len(current) >= MIN_CHUNK:
                result.append(current)
    return result


def _is_heading_list(text: str) -> bool:
    """检测是否为纯目录/标题列表（无实质内容）"""
    lines = text.strip().split('\n')
    # 超过 60% 的行匹配标题模式则视为标题列表
    heading_pat = re.compile(r'^[（(]?[一二三四五六七八九十\d]+[）)]?\s*[^\n]{0,50}$')
    heading_lines = sum(1 for line in lines if heading_pat.match(line.strip()))
    return len(lines) > 0 and heading_lines / len(lines) > 0.6


def _post_process(chunks: List[Dict]) -> List[Dict]:
    """后处理: 合并过小chunk、合并标题列表、过滤碎屑"""
    # Pass 1: 合并标题列表到下一个 chunk
    merged = []
    for ch in chunks:
        if merged and _is_heading_list(merged[-1]['text']):
            # 将标题列表合并到当前 chunk
            ch['text'] = merged[-1]['text'] + "\n\n" + ch['text']
            ch['case_ref'] = merged[-1]['case_ref'] or ch['case_ref']
            merged.pop()
        merged.append(ch)

    # Pass 2: 合并过小的 chunk (MIN_CHUNK 以下)
    result = []
    for ch in merged:
        if result and len(ch['text']) < MIN_CHUNK:
            result[-1]['text'] += "\n\n" + ch['text']
            result[-1]['case_ref'] = result[-1]['case_ref'] or ch['case_ref']
        else:
            result.append(ch)

    # Pass 3: 过滤仍然过小的孤立 chunk
    result = [c for c in result if len(c['text']) >= MIN_CHUNK]

    return result


def chunk_by_structure(full_text: str) -> List[Dict]:
    """
    解析文档结构，按语义单元切块。

    层级: 章 → 节 → 案例边界
    返回: [{text, chapter, section, case_ref, segment_type}, ...]
    """
    print(f"[2/5] 结构化解析...")

    # 定位正文起点（跳过前言/目录）
    first_ch = re.search(r'第[一二三四五六七八九十百]+章\s', full_text)
    if not first_ch:
        print("  [WARN] 未找到章节结构")
        return []
    body = full_text[first_ch.start():]
    print(f"      正文起点: char {first_ch.start()}")

    # ── 第一步: 按章切分 ──
    ch_matches = list(re.finditer(r'(?:^|\n)(第[一二三四五六七八九十百]+章[^\n]*)', body, re.MULTILINE))

    all_chunks: List[Dict] = []

    for chi, ch_m in enumerate(ch_matches):
        ch_start = ch_m.start()
        ch_end = ch_matches[chi + 1].start() if chi + 1 < len(ch_matches) else len(body)
        ch_text = body[ch_start:ch_end].strip()
        ch_name = ch_m.group(1).strip()

        # ── 第二步: 按节切分 ──
        sec_matches = list(re.finditer(r'(?:^|\n)(第[一二三四五六七八九十百]+节[^\n]*)', ch_text, re.MULTILINE))

        if not sec_matches:
            # 无节结构 → 按案例边界直接切
            chunks = _split_section_by_case(ch_text, ch_name, ch_name)
            all_chunks.extend(chunks)
            continue

        for si, sec_m in enumerate(sec_matches):
            sec_start = sec_m.start()
            sec_end = sec_matches[si + 1].start() if si + 1 < len(sec_matches) else len(ch_text)
            sec_text = ch_text[sec_start:sec_end].strip()
            sec_name = sec_m.group(1).strip()

            # 章头文字（第一个节之前）
            if si == 0 and sec_start > 0:
                pre_text = ch_text[:sec_start].strip()
                if pre_text and len(pre_text) > MIN_CHUNK:
                    _add_chunk(all_chunks, pre_text, ch_name, ch_name, "", "legal_exposition")

            # ── 第三步: 按案例边界切分 ──
            chunks = _split_section_by_case(sec_text, ch_name, sec_name)
            all_chunks.extend(chunks)

        # 章尾文字（最后一个节之后）
        if sec_matches and sec_matches[-1].end() < len(ch_text):
            tail_text = ch_text[sec_matches[-1].end():].strip()
            if tail_text and len(tail_text) > MIN_CHUNK:
                _add_chunk(all_chunks, tail_text, ch_name, ch_name, "", "legal_exposition")

    # ── 后处理 ──
    all_chunks = _post_process(all_chunks)

    # 统计
    print(f"      解析: {len(set(c['chapter'] for c in all_chunks))} 章, "
          f"{len(set(c['section'] for c in all_chunks))} 节, "
          f"{len([c for c in all_chunks if c['case_ref']])} 案例, "
          f"{len(all_chunks)} chunks")

    return all_chunks


def _split_section_by_case(sec_text: str, ch_name: str, sec_name: str) -> List[Dict]:
    """在节内按案例标记切分"""
    chunks: List[Dict] = []

    # 查找所有案例标记
    case_matches = list(re.finditer(r'(?:^|\n)(相关案例\d+-\d+[^\n]*)', sec_text, re.MULTILINE))

    if not case_matches:
        # 无案例 → 整个节作为一个或多个 chunk
        _add_chunk(chunks, sec_text, ch_name, sec_name, "", "legal_exposition")
        return chunks

    # 第一个案例之前的文本 → legal_exposition
    pre_text = sec_text[:case_matches[0].start()].strip()
    if pre_text and len(pre_text) > MIN_CHUNK:
        _add_chunk(chunks, pre_text, ch_name, sec_name, "", "legal_exposition")

    # 每个案例
    for ci, cm in enumerate(case_matches):
        c_start = cm.start()
        c_end = case_matches[ci + 1].start() if ci + 1 < len(case_matches) else len(sec_text)
        case_text = sec_text[c_start:c_end].strip()
        case_ref = cm.group(1).strip()

        # 案例后的"实务建议"类文本 → 合并到案例 chunk
        _add_chunk(chunks, case_text, ch_name, sec_name, case_ref, "case_analysis")

    return chunks


def _add_chunk(chunks: List[Dict], text: str, chapter: str, section: str,
               case_ref: str, seg_type: str):
    """添加 chunk，对过大的自动切分"""
    text = text.strip()
    if not text or len(text) < MIN_CHUNK:
        return

    if len(text) <= MAX_CHUNK:
        chunks.append({
            'text': text,
            'chapter': chapter,
            'section': section,
            'case_ref': case_ref,
            'segment_type': seg_type,
        })
    else:
        for sub in _split_large(text):
            chunks.append({
                'text': sub,
                'chapter': chapter,
                'section': section,
                'case_ref': case_ref,
                'segment_type': seg_type,
            })


# ── Milvus 操作 ──

def delete_old_chunks(client):
    """删除旧的 pdf_case_paragraph chunks"""
    print(f"[3/5] 删除旧 chunks (source_doc='{PDF_NAME}', chunk_type='pdf_case_paragraph')")

    filter_expr = f'source_doc == "{PDF_NAME}" and chunk_type == "pdf_case_paragraph"'
    existing = client.query(COLLECTION, filter_expr, limit=10000)
    old_count = len(existing)
    print(f"      旧 chunks: {old_count} 条")

    if old_count == 0:
        print("      无需删除")
        return

    old_ids = [e["id"] for e in existing]
    batch_size = 100
    deleted = 0
    db_name = client._base_payload(COLLECTION).get("dbName", "")

    for i in range(0, len(old_ids), batch_size):
        batch = old_ids[i:i + batch_size]
        id_filter = ", ".join(f'"{eid}"' for eid in batch)
        client._post("/v2/vectordb/entities/delete", {
            "collectionName": COLLECTION,
            "dbName": db_name,
            "filter": f"id in [{id_filter}]",
        })
        deleted += len(batch)
    print(f"      已删除 {deleted} 条")


def build_metadata(chunk: Dict, idx: int) -> Dict:
    """构建 chunk metadata"""
    chunk_hash = hashlib.md5(chunk['text'].encode()).hexdigest()[:8]
    return {
        "source_doc": PDF_NAME,
        "chunk_type": CHUNK_TYPE,
        "chunk_order": str(idx),
        "chunk_hash": chunk_hash,
        "law_name": PDF_NAME,
        "article_id": "",
        "chapter": chunk['chapter'],
        "section": chunk['section'],
        "case_ref": chunk['case_ref'],
        "segment_type": chunk['segment_type'],
        "category": "policy",
        "data_version": DATA_VERSION,
        "token_count": str(len(chunk['text'])),
    }


def build_retrieval_text(chunk: Dict) -> str:
    """构建检索文本，注入结构化 header"""
    seg_label = {"legal_exposition": "法律论述", "case_analysis": "案例分析", "summary": "实务总结"}
    seg_cn = seg_label.get(chunk['segment_type'], chunk['segment_type'])

    parts = [f"《{PDF_NAME}》"]
    if chunk['section']:
        parts.append(f"【{chunk['section']}】")
    if chunk['case_ref']:
        parts.append(f"【{chunk['case_ref']}】")
    parts.append(f"【{seg_cn}】")
    parts.append(chunk['text'])

    return "\n".join(parts)


def import_new_chunks(client, chunks: List[Dict]):
    """Embedding + 入库"""
    print(f"[4/5] Embedding + 入库 {len(chunks)} chunks ...")

    embed_service = EmbeddingService()
    total = 0

    for batch_start in range(0, len(chunks), EMBED_BATCH):
        batch = chunks[batch_start:batch_start + EMBED_BATCH]

        rts = [build_retrieval_text(ch) for ch in batch]
        embeddings = embed_service.embed_batch(rts)

        for i, chunk in enumerate(batch):
            idx = batch_start + i
            chunk_id = f"pdf_{PDF_NAME}_struct_{idx:04d}"
            meta = build_metadata(chunk, idx)
            meta["chunk_id"] = chunk_id  # 冗余存一份 id

            client.add_documents(
                COLLECTION,
                [rts[i]],
                [chunk['text']],
                [meta],
                [chunk_id],
            )
        total += len(batch)
        print(f"      {total}/{len(chunks)} ...")

    print(f"      入库完成: {total} 条")


def print_stats(chunks: List[Dict]):
    """打印切块统计"""
    sizes = [len(c['text']) for c in chunks]
    by_type = defaultdict(int)
    by_section = defaultdict(int)
    for c in chunks:
        by_type[c['segment_type']] += 1
        by_section[c['section']] += 1

    print(f"\n{'=' * 60}")
    print(f"切块统计")
    print(f"{'=' * 60}")
    print(f"  Total chunks:      {len(chunks)}")
    print(f"  Text size:         min={min(sizes)}, max={max(sizes)}, "
          f"avg={sum(sizes)//len(sizes):.0f}, median={sorted(sizes)[len(sizes)//2]}")
    print(f"  Segment types:     {dict(by_type)}")
    print(f"  案例 chunks:        {len([c for c in chunks if c['case_ref']])}")

    print(f"\n  Top sections (by chunk count):")
    for sec, cnt in sorted(by_section.items(), key=lambda x: -x[1])[:10]:
        print(f"    {sec[:60]}: {cnt}")

    # 显示样本
    print(f"\n  样本 chunks:")
    for i, c in enumerate(chunks):
        if i >= 5:
            break
        print(f"    [{c['segment_type'][:6]}] {c.get('case_ref','')[:30]} | "
              f"{c['text'][:80].replace(chr(10), ' ')}...")


def main():
    parser = argparse.ArgumentParser(description="结构化重切实务案例PDF")
    parser.add_argument("--dry-run", action="store_true", help="仅分析结构，不入库")
    args = parser.parse_args()

    if not Path(PDF_PATH).exists():
        print(f"[ERROR] PDF 不存在: {PDF_PATH}")
        sys.exit(1)

    full_text = extract_text(PDF_PATH)
    chunks = chunk_by_structure(full_text)
    print_stats(chunks)

    if args.dry_run:
        print(f"\n[Dry-run] 未写入 Milvus。确认无误后运行: python init_scripts/rechunk_case_book.py")
        return

    client = get_vector_store()

    # ★ 安全: 先插入新 chunk，验证成功后再删旧
    import_new_chunks(client, chunks)

    # 验证新 chunk 入库成功
    verify = client.query(COLLECTION,
                          f'source_doc == "{PDF_NAME}" and chunk_type == "{CHUNK_TYPE}"',
                          limit=5)
    if not verify:
        print("[ERROR] 新 chunk 入库验证失败，保留旧数据，未删除。")
        sys.exit(1)

    delete_old_chunks(client)

    # 验证
    remaining = client.query(COLLECTION,
                             f'source_doc == "{PDF_NAME}" and chunk_type == "{CHUNK_TYPE}"',
                             limit=5)
    print(f"\n[5/5] 验证: {PDF_NAME} 结构化 chunks (sample):")
    for r in remaining:
        rid = r.get('id', r.get('chunk_id', '?'))
        rct = r.get('chunk_type', '?')
        seg = r.get('segment_type', '?')
        print(f"      {rid}  type={rct}  seg={seg}")

    total_new = len(client.query(COLLECTION,
                                 f'source_doc == "{PDF_NAME}"',
                                 limit=10000))
    print(f"\n  当前该文档总 chunk 数: {total_new}")

    print(f"\n{'=' * 60}")
    print("[完成]")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
