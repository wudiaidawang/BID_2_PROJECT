"""
Child Chunk 构建器 (ChildChunkBuilder)

仅当 parent chunk 超长时拆分。
拆分优先级: （一）（二）子项 → 自然段落 → 句子边界
继承 parent metadata，注入 header 信息。
"""
import re
from typing import List, Dict

from config import settings


class ChildChunkBuilder:
    """将超长 parent chunks 拆分为 child chunks"""

    def __init__(self, chunk_type: str = "child"):
        self.threshold = settings.legal_child_split_threshold
        self.target_size = settings.legal_child_target_size
        self.overlap = settings.legal_child_overlap
        self.header_enabled = settings.legal_header_injection_enabled
        self.chunk_type = chunk_type

    def build(self, parents: List[Dict]) -> List[Dict]:
        """为所有 parent chunks 生成 child chunks"""
        all_children = []
        for parent in parents:
            children = self._build_for_parent(parent)
            all_children.extend(children)
        return all_children

    def build_all(self, parents: List[Dict]) -> tuple:
        """
        同时返回 parents 和 children。
        短法条（不需要拆分的 parent）也作为可检索 chunk 返回。
        """
        searchable_parents = []
        all_children = []

        for parent in parents:
            raw = parent.get("raw_content", "")
            if len(raw) <= self.threshold:
                # 短法条：parent 自身可直接检索
                searchable_parents.append(parent)
            else:
                # 长法条：拆分为 children
                children = self._build_for_parent(parent)
                if children:
                    all_children.extend(children)
                else:
                    # 拆分失败，降级：parent 自身参与检索
                    searchable_parents.append(parent)

        return searchable_parents, all_children

    def _build_for_parent(self, parent: Dict) -> List[Dict]:
        """为单个 parent 构建 child chunks"""
        raw = parent.get("raw_content", "")
        if len(raw) <= self.threshold:
            return []

        # 按优先级尝试拆分
        for strategy in [self._split_by_subsections,
                         self._split_by_paragraphs,
                         self._split_by_sentences]:
            segments = strategy(raw)
            if len(segments) > 1:
                return self._make_children(segments, parent)

        # 无法拆分：返回空，由调用方降级处理
        return []

    # ── 拆分策略 ──────────────────────────────────────────

    def _split_by_subsections(self, content: str) -> List[str]:
        """按 （一）（二）（三）子项拆分"""
        pattern = re.compile(r'[（(]([一二三四五六七八九十\d]+)[）)]')

        # 找到所有子项边界
        matches = list(pattern.finditer(content))
        if len(matches) < 2:
            return [content]  # 只有一个或没有子项，不拆分

        segments = []
        # 第一个子项之前的内容作为第一段
        first_cut = matches[0].start()
        if first_cut > 10:
            segments.append(content[:first_cut].strip())

        for j, m in enumerate(matches):
            start = m.start()
            end = matches[j + 1].start() if j + 1 < len(matches) else len(content)
            segment = content[start:end].strip()
            if len(segment) > 20:
                segments.append(segment)

        # 如果拆分后段数太少或某段太长，合并结果
        if len(segments) <= 1:
            return [content]

        # 对仍然太长的子段递归合并
        return self._merge_long_segments(segments, self.target_size)

    def _split_by_paragraphs(self, content: str) -> List[str]:
        """按自然段落（双换行）拆分"""
        paragraphs = re.split(r'\n\s*\n', content)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        if len(paragraphs) <= 1:
            return [content]

        # 合并短段落
        merged = []
        current = ""
        for p in paragraphs:
            if len(current) + len(p) < self.target_size:
                current = current + "\n\n" + p if current else p
            else:
                if current:
                    merged.append(current)
                current = p
        if current:
            merged.append(current)

        return merged if len(merged) > 1 else [content]

    def _split_by_sentences(self, content: str) -> List[str]:
        """按句子边界拆分（最后手段），带 overlap"""
        # 在句子结束符处切分
        sentences = re.split(r'(?<=[。；！？])', content)
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) <= 1:
            # 按逗号进一步拆分
            sentences = re.split(r'(?<=[，,])', content)
            sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) <= 1:
            return [content]

        # 组装成目标大小的块，带 overlap
        chunks = []
        current = ""
        for s in sentences:
            if len(current) + len(s) < self.target_size:
                current = current + s if current else s
            else:
                if current:
                    chunks.append(current)
                # overlap: 保留上一段末尾部分作为上下文
                if chunks and self.overlap > 0:
                    prev = chunks[-1]
                    overlap_text = prev[-self.overlap:] if len(prev) > self.overlap else prev
                    current = overlap_text + s
                else:
                    current = s
        if current:
            chunks.append(current)

        return chunks if len(chunks) > 1 else [content]

    # ── 辅助 ──────────────────────────────────────────────

    def _merge_long_segments(self, segments: List[str],
                             max_size: int) -> List[str]:
        """合并过短的段，拆分过长的段"""
        result = []
        current = ""
        for seg in segments:
            if len(seg) > max_size * 2:
                # 仍然太长，先保存 current，再递归拆分该段
                if current:
                    result.append(current)
                    current = ""
                sub_segments = self._split_by_paragraphs(seg)
                result.extend(sub_segments)
            elif len(current) + len(seg) < max_size:
                current = current + "\n" + seg if current else seg
            else:
                if current:
                    result.append(current)
                current = seg
        if current:
            result.append(current)
        return result if result else segments

    def _make_children(self, segments: List[str], parent: Dict) -> List[Dict]:
        """为拆分后的段构建 child chunk 对象 —— retrieval_text / text 解耦"""
        children = []
        parent_id = parent["chunk_id"]
        header = parent.get("header_for_embedding", "")

        for i, seg in enumerate(segments):
            if len(seg) < 20:
                continue

            chunk_id = f"{parent_id}_child{i}"

            # retrieval_text = header + 子块内容 → 参与向量化和 BM25
            retrieval_text = f"{header}\n{seg}" if (self.header_enabled and header) else seg
            # text = 子块原文 → 用户展示
            text = seg

            children.append({
                "chunk_id": chunk_id,
                "chunk_type": self.chunk_type,
                "parent_id": parent_id,
                "law_name": parent["law_name"],
                "chapter": parent["chapter"],
                "article": parent["article"],
                "article_id": parent["article_id"],
                "retrieval_text": retrieval_text,
                "text": text,
                "raw_content": seg,
                "header_for_embedding": header,
                "metadata": {
                    "source_doc": parent["metadata"].get("source_doc", ""),
                    "law_name": parent["law_name"],
                    "chapter": parent["chapter"],
                    "article": parent["article"],
                    "article_id": parent["article_id"],
                    "chunk_type": self.chunk_type,
                    "chunk_order": f"{parent['article_id']}_child{i}",
                    "parent_id": parent_id,
                }
            })

        return children
