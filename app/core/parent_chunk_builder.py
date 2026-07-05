"""
Parent Chunk 构建器 (ParentChunkBuilder)

将 LegalStructureParser 输出的结构化法律文档转换为 parent chunks。
一个法条 = 一个 parent chunk，保留完整内容，禁止任何截断。
"""
from typing import List, Dict

from app.core.legal_structure_parser import LawDocument, ChapterInfo, ArticleInfo


class ParentChunkBuilder:
    """将结构化法律文档转为 parent chunks。

    domain_topic_map: 可选, Dict[(law_name, article_id), Dict]
        为特定法规-条款注入领域/主题/关键词到 header 中，
        解决不同法规相似条文的向量混淆问题。
        格式: {(law_name, str(aid)): {"domain": "...", "topic": "...", "keywords": [...]}}
    """

    def __init__(self, source: str = "", header_injection: bool = True,
                 chunk_type: str = "parent",
                 domain_topic_map: dict | None = None):
        self.source = source
        self.header_injection = header_injection
        self.chunk_type = chunk_type
        self.domain_topic_map = domain_topic_map or {}
        self._counter = 0

    def build(self, documents: List[LawDocument]) -> List[Dict]:
        """构建所有 parent chunks"""
        all_parents = []
        for doc in documents:
            parents = self._build_for_law(doc)
            all_parents.extend(parents)
        return all_parents

    def _build_for_law(self, law: LawDocument) -> List[Dict]:
        """为单部法律构建 parent chunks"""
        parents = []

        # 处理 preamble（如附则等）
        for art in law.preamble:
            chunk = self._build_parent(law.law_name, "前言/附则", art)
            if chunk:
                parents.append(chunk)

        # 处理各章节
        for ch in law.chapters:
            for art in ch.articles:
                chunk = self._build_parent(law.law_name, ch.chapter_text, art)
                if chunk:
                    parents.append(chunk)

        return parents

    def _build_parent(self, law_name: str, chapter: str,
                      art: ArticleInfo) -> Dict:
        """构建单个 parent chunk —— retrieval_text / text 解耦"""
        content = art.content
        chunk_id = self._make_chunk_id(law_name, art.article_id, content)

        full_header = self._make_header(law_name, chapter, art.article_text, str(art.article_id))

        # 短法条使用紧凑 header，减少 embedding 稀释
        if len(content) < 200:
            embedding_header = self._make_compact_header(law_name, chapter, art.article_text, str(art.article_id))
        else:
            embedding_header = full_header

        # retrieval_text = header + [SEP] + 正文 → 参与向量化和 BM25
        retrieval_text = f"{embedding_header}\n[SEP]\n{content}" if self.header_injection else content
        # text = 原始正文 → 用户展示，无 header 污染
        text = content

        return {
            "chunk_id": chunk_id,
            "chunk_type": self.chunk_type,
            "parent_id": "",
            "law_name": law_name,
            "chapter": chapter,
            "article": art.article_text,
            "article_id": art.article_id,
            "retrieval_text": retrieval_text,
            "text": text,
            "header_for_embedding": full_header,   # 完整 header（供 child chunks 继承）
            "raw_content": content,                # 不含 header 的原始法条内容
            "metadata": {
                "source_doc": self.source,
                "law_name": law_name,
                "chapter": chapter,
                "article": art.article_text,
                "article_id": art.article_id,
                "chunk_type": self.chunk_type,
                "chunk_order": str(art.article_id),
                "parent_id": "",
            }
        }

    def _make_chunk_id(self, law_name: str, article_id: int, content: str = "") -> str:
        """生成唯一 chunk ID（使用自增计数器保证唯一性）"""
        safe_name = law_name.replace(" ", "").replace("/", "_")[:20]
        self._counter += 1
        content_hash = abs(hash(content)) % 10000
        return f"parent_{safe_name}_{article_id}_{self._counter}_{content_hash}"

    def _make_header(self, law_name: str, chapter: str,
                     article_text: str, article_id: str = "") -> str:
        """生成层级 header 字符串用于 embedding 注入"""
        parts = [f"《{law_name}》"]
        # 领域/主题/关键词 enrichment（仅匹配的 law-article 对启用）
        enrichment = self.domain_topic_map.get((law_name, article_id))
        if enrichment:
            parts.append(f"领域：{enrichment['domain']}")
            parts.append(f"主题：{enrichment['topic']}")
            parts.append(f"关键词：{','.join(enrichment['keywords'])}")
        if chapter:
            parts.append(chapter)
        parts.append(article_text)
        return "\n".join(parts)

    def _make_compact_header(self, law_name: str, chapter: str,
                             article_text: str, article_id: str = "") -> str:
        """生成紧凑 header —— 用于短法条，减少 embedding 稀释"""
        short_name = law_name.replace("中华人民共和国", "").replace("法律法规全书", "法规全书")
        parts = [f"《{short_name}》"]
        enrichment = self.domain_topic_map.get((law_name, article_id))
        if enrichment:
            parts.append(f"领域：{enrichment['domain']}")
            parts.append(f"主题：{enrichment['topic']}")
        if chapter:
            parts.append(chapter)
        parts.append(article_text)
        return " / ".join(parts)
