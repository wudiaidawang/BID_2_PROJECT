"""
法律结构感知解析器 (LegalStructureParser)

将 PDF 原始文本解析为结构化法律文档：
  LawDocument → ChapterInfo → ArticleInfo

核心原则：按"第XX条"切块，禁止跨条切分。
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from app.utils.chinese_number import chinese_number_converter


# ── 正则模式 ──────────────────────────────────────────────
CHAPTER_PATTERN = re.compile(
    r'第([一二三四五六七八九十百千\d]+)章\s*(.*)'
)
ARTICLE_HEADER_PATTERN = re.compile(
    r'第([一二三四五六七八九十百千\d]+)条[^\n]*'
)
# 匹配任何 "第X条" 用于边界检测
ARTICLE_BOUNDARY_PATTERN = re.compile(
    r'第[一二三四五六七八九十百千\d]+条'
)

# 子项匹配: （一）（二）... 或 (一)(二)...
SUBSECTION_PATTERN = re.compile(r'[（(]([一二三四五六七八九十\d]+)[）)]')

# 文档标题模式 — 匹配中国法律命名规范
# 注意: Python 3 的 \w 默认匹配 Unicode 汉字，必须用 [a-zA-Z0-9_] 替代
DOC_TITLE_PATTERNS = [
    # 中华人民共和国X法 / 中华人民共和国X条例 / 中华人民共和国X办法
    re.compile(r'^中华人民共和国.+[法条例办法]$'),
    # 关于...的通知/意见/函/规定
    re.compile(r'^关于.{4,}[通知意见函规定]$'),
    # X法 / X条例 / X办法 / X细则 / X规定 / X通知 / X暂行办法 / X实施办法
    # 上限 16：过长的匹配多为正文行被误判（如"...采用综合评分法"）
    re.compile(r'^[^\s，。；！？、：（）\(\)\da-zA-Z0-9_]{2,16}(暂行|实施)?(法|条例|办法|细则|规定|通知)$'),
]

# 标题内禁止关键词（用于排除明显非标题的行）
TITLE_BLACKLIST = [
    # 结构标识 — 法条、目录行不是法律标题
    # "条" 不在黑名单中：ARTICLE_BOUNDARY_PATTERN 已拦截 "第X条"，
    # 而 "条例" 是合法的标题后缀（如 "政府采购法实施条例"）
    '第', '款', '节',
    # 按"第X项/第X目"格式排除（不影响标题中含"项目""条目"的字）
    '目录', '索引', '附录', '前言', '编写说明',
    '出版', 'ISBN', 'CIP',
    # 常见法律正文动词 — 只排除独立成句的情况
    '违反', '不得', '应当', '可以', '必须',
]


# ── 数据结构 ──────────────────────────────────────────────

@dataclass
class ArticleInfo:
    """单条法条"""
    article_id: int
    article_text: str          # "第二十七条"
    title_hint: str = ""       # 【适用范围】等，括号内提示
    content: str = ""          # 完整法条正文
    subsections: List[str] = field(default_factory=list)


@dataclass
class ChapterInfo:
    """章节"""
    chapter_id: int
    chapter_text: str          # "第一章 总则"
    articles: List[ArticleInfo] = field(default_factory=list)


@dataclass
class LawDocument:
    """单部法律"""
    law_name: str
    chapters: List[ChapterInfo] = field(default_factory=list)
    preamble: List[ArticleInfo] = field(default_factory=list)  # 附则等归入 preamble


# ── 解析器 ────────────────────────────────────────────────

class LegalStructureParser:
    """法律文本结构化解析器"""

    # 需要排除的目录/前言行关键词
    TOC_KEYWORDS = ['目录', '编辑出版说明', '前言', '编写说明', '出版说明']

    # 附则章的名称模式
    SUPPLEMENTARY_NAMES = ['附则', '附 则', '补则']

    def __init__(self):
        self._cn = chinese_number_converter

    # ── 公共入口 ──────────────────────────────────────────

    def parse(self, text: str, pdf_name: str = "") -> List[LawDocument]:
        """
        解析 PDF 全文，返回法律文档列表。

        步骤:
        1. 按文档标题切分多个法律
        2. 对每个法律解析章-条结构
        """
        if not text:
            return []

        documents = self._split_by_document_title(text)
        result = []

        for doc_title, doc_content in documents:
            if self._should_skip(doc_title):
                continue
            law_doc = self._parse_single_law(doc_title, doc_content)
            if law_doc and law_doc.chapters:
                result.append(law_doc)

        return result

    # ── 文档切分 ──────────────────────────────────────────

    def _split_by_document_title(self, text: str) -> List[Tuple[str, str]]:
        """按文档标题将混合文本切分为独立法律"""
        lines = text.split('\n')
        documents = []
        current_doc = {"title": "", "lines": []}
        found_first_title = False

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            if self._is_document_title(stripped):
                # 跳过目录等伪标题
                if self._should_skip(stripped):
                    continue

                # 清理标题噪声（PDF 提取残留的破折号、编号等）
                clean_title = self._clean_title(stripped)

                if found_first_title and current_doc["lines"]:
                    content = '\n'.join(current_doc["lines"])
                    if len(content) > 200:
                        documents.append((current_doc["title"], content))
                elif not found_first_title:
                    found_first_title = True

                current_doc = {"title": clean_title, "lines": []}
            elif found_first_title:
                current_doc["lines"].append(stripped)

        # 保存最后一个文档
        if found_first_title and current_doc["lines"]:
            content = '\n'.join(current_doc["lines"])
            if len(content) > 200:
                documents.append((current_doc["title"], content))

        return documents

    def _is_document_title(self, line: str) -> bool:
        """判断是否为文档标题（严格模式）"""
        # 先清理 PDF 噪声，再检查长度（避免 "--XX办法" 因前缀占位被拒）
        cleaned = self._clean_title(line)
        if len(cleaned) < 8 or len(cleaned) > 40:
            return False
        if re.match(r'^\d+$', cleaned):
            return False
        # 排除结构标识
        if CHAPTER_PATTERN.match(cleaned):
            return False
        if ARTICLE_BOUNDARY_PATTERN.match(cleaned):
            return False
        # 排除含黑名单词的行
        for kw in TITLE_BLACKLIST:
            if kw in cleaned:
                return False
        # 排除 TOC 关键词
        for kw in self.TOC_KEYWORDS:
            if kw in cleaned:
                return False
        for pattern in DOC_TITLE_PATTERNS:
            if pattern.search(cleaned):
                return True
        return False

    def _should_skip(self, title: str) -> bool:
        """判断是否应跳过此文档"""
        for kw in self.TOC_KEYWORDS:
            if kw in title:
                return True
        return False

    @staticmethod
    def _clean_title(title: str) -> str:
        """清理 PDF 提取残留的标题噪声（破折号、编号前缀等）"""
        # 去掉前导噪声: --, ——, —, -, §, 数字编号等
        cleaned = title.lstrip('-—－#§0123456789.、 \t')
        # 如果清理后为空或太短，返回原标题
        if len(cleaned) < 4:
            return title
        return cleaned

    # ── 单部法律解析 ──────────────────────────────────────

    def _parse_single_law(self, law_name: str, content: str) -> LawDocument:
        """解析单部法律的章-条结构"""
        law = LawDocument(law_name=law_name)

        # 去除目录块（"目 录" 到第一个 "第X章" 之间的内容）
        content = self._remove_toc_block(content)

        # 按 "第X章" 切分
        chapter_blocks = self._split_by_chapter(content)

        for ch_text, ch_title, articles_text in chapter_blocks:
            chapter = self._parse_chapter(ch_text, ch_title, articles_text)
            if chapter:
                law.chapters.append(chapter)

        return law

    def _remove_toc_block(self, content: str) -> str:
        """去掉目录块（目录行到第一个第X章之间的内容）"""
        lines = content.split('\n')
        toc_start = -1
        first_chapter = -1

        for i, line in enumerate(lines):
            stripped = line.strip()
            if toc_start < 0 and ('目' in stripped and '录' in stripped and len(stripped) < 10):
                toc_start = i
            if CHAPTER_PATTERN.search(stripped):
                first_chapter = i
                break

        if toc_start >= 0 and first_chapter > toc_start:
            # 删除目录行到第一个章之间的内容（保留章之后的内容）
            return '\n'.join(lines[first_chapter:])

        return content

    def _split_by_chapter(self, content: str) -> List[Tuple[str, str, str]]:
        """
        按 "第X章" 切分。

        返回: [(chapter_number_text, chapter_title, articles_text), ...]
        """
        # 使用正向前瞻按 "第X章" 切分
        parts = re.split(r'(第[一二三四五六七八九十百千\d]+章[^\n]*)', content)

        result = []
        i = 0
        # 跳过第一个空段
        while i < len(parts) and not CHAPTER_PATTERN.search(parts[i]):
            i += 1

        while i < len(parts):
            header = parts[i].strip()
            body = parts[i + 1].strip() if i + 1 < len(parts) else ""
            i += 2

            match = CHAPTER_PATTERN.search(header)
            if match:
                ch_num = match.group(1)
                ch_name = header
                result.append((ch_num, ch_name, body))

        return result

    def _parse_chapter(self, ch_num_text: str, ch_title: str,
                       articles_text: str) -> Optional[ChapterInfo]:
        """解析单个章节内的法条"""
        ch_id = self._to_int(ch_num_text)

        # 检查是否为附则（特殊处理，放在 preamble 或章节末尾）
        is_supplementary = any(
            kw in ch_title for kw in self.SUPPLEMENTARY_NAMES
        )

        chapter = ChapterInfo(
            chapter_id=ch_id,
            chapter_text=ch_title
        )

        articles = self._split_by_article(articles_text)
        for art_header, art_content in articles:
            art_info = self._parse_article(art_header, art_content)
            if art_info and len(art_info.content) >= 10:
                chapter.articles.append(art_info)

        if not chapter.articles:
            return None

        return chapter

    def _split_by_article(self, text: str) -> List[Tuple[str, str]]:
        """
        按 "第X条" 切分文章，返回 [(article_header, article_body), ...]

        使用正向前瞻确保不跨条切分。
        """
        if not text:
            return []

        # 找到第一个 "第X条"
        first_match = ARTICLE_BOUNDARY_PATTERN.search(text)
        if not first_match:
            return []

        # 去掉第一个法条之前的内容（章标题介绍文字）
        text = text[first_match.start():]

        # 按 "第X条" 边界切分（正向前瞻）
        parts = re.split(
            r'(第[一二三四五六七八九十百千\d]+条[^\n]*)',
            text
        )

        result = []
        i = 0
        while i < len(parts):
            if ARTICLE_HEADER_PATTERN.match(parts[i].strip()):
                header = parts[i].strip()
                body = parts[i + 1].strip() if i + 1 < len(parts) else ""
                i += 2
                result.append((header, body))
            else:
                i += 1

        return result

    def _parse_article(self, header: str, content: str) -> Optional[ArticleInfo]:
        """解析单条法条"""
        match = ARTICLE_HEADER_PATTERN.search(header)
        if not match:
            return None

        art_num_text = match.group(1)
        art_id = self._to_int(art_num_text)
        art_text = match.group(0).strip()

        # 提取标题提示：【xxx】
        title_hint = ""
        hint_match = re.search(r'【([^】]+)】', header)
        if hint_match:
            title_hint = hint_match.group(1)

        # 组合完整法条内容
        full_content = f"{art_text}\n{content}" if content else art_text

        # 提取子项 (一)(二)...
        subsections = self._extract_subsections(content)

        return ArticleInfo(
            article_id=art_id,
            article_text=art_text,
            title_hint=title_hint,
            content=full_content,
            subsections=subsections
        )

    def _extract_subsections(self, content: str) -> List[str]:
        """提取法条内的子项"""
        if not content:
            return []

        # 按 （一）（二）... 分割
        parts = SUBSECTION_PATTERN.split(content)
        if len(parts) <= 1:
            return []

        subsections = []
        i = 1
        while i < len(parts):
            num = parts[i]
            body = parts[i + 1].strip() if i + 1 < len(parts) else ""
            i += 2
            subsections.append(f"({num}) {body}")

        return subsections

    # ── 工具 ──────────────────────────────────────────────

    def _to_int(self, num_text: str) -> int:
        """将中文或阿拉伯数字文本转为整数"""
        num_text = num_text.strip()
        if num_text.isdigit():
            return int(num_text)
        arabic_str = self._cn.to_arabic(num_text)
        try:
            return int(arabic_str)
        except (ValueError, TypeError):
            return 0

    # ── 调试/统计 ──────────────────────────────────────────

    def get_statistics(self, documents: List[LawDocument]) -> dict:
        """生成解析统计信息"""
        total_chapters = 0
        total_articles = 0
        total_subsections = 0

        for doc in documents:
            total_chapters += len(doc.chapters)
            for ch in doc.chapters:
                total_articles += len(ch.articles)
                for art in ch.articles:
                    total_subsections += len(art.subsections)

        return {
            "law_count": len(documents),
            "chapter_count": total_chapters,
            "article_count": total_articles,
            "subsection_count": total_subsections,
            "law_names": [d.law_name for d in documents],
        }
