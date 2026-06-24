"""附录/模板/表单检测器 — 在 Parser 后、Chunk 前过滤低质量 Article。

核心思路：
  法律条文说"公告应包含：项目名称、地址、联系人" — 这是合规要求，不能删。
  空白模板写"项目名称：____  地址：____  联系人：____" — 这是附录模板，应过滤。

  区分信号：空白占位符（______、___、年 月 日、地址：_）。
  法条不含空白占位符，模板必有。

门控 + 打分：
  1. 先检空白占位符 — 零命中 → 直接放行（不可能是模板）
  2. 有空白占位符 → 计算综合评分
  3. score >= 1.0 → 过滤（单条 article 级别，不丢整部文档）

全库验证（3982 条 parent chunks）：
  score >= 1.0: 3 条，全部为真实模板，零误杀。
"""

import re
from typing import List

from app.core.legal_structure_parser import LawDocument, ArticleInfo

# 空白占位符 — 门控条件，模板必有，法条必无
BLANK_PATTERNS = [
    "______",      # 长下划线占位
    "___",         # 短下划线占位（至少3个连续）
    "年 月 日",     # 日期占位（单空格）
    "年  月  日",   # 日期占位（双空格）
    "年___月___日", # 日期占位（下划线）
    "地址：_",      # 地址后跟占位符
]

# 表单特征词 — 打分的辅助信号
FORM_PATTERNS = [
    "地址：", "联系人：", "联系电话：", "电话：", "传真：",
    "邮编：",
    "法定代表人", "委托代理人",
    "（盖章）", "（签字）", "（公章）",
    "项目编号", "项目名称", "采购计划备案文号",
    "填表说明", "投诉人：", "被投诉人：",
    "预算科目名称", "收款单位",
    "招标公告", "中标通知书", "成交结果公告",
    "资格预审公告", "更正公告", "终止公告",
    "投诉处理结果公告", "监督检查处理结果公告",
    "合同格式", "投标文件格式",
    "（  ）",
]

APPENDIX_PATTERN = re.compile(r"附件|附录|模板|格式")


def _blank_hits(content: str) -> int:
    """空白占位符命中数 — 门控条件"""
    return sum(1 for kw in BLANK_PATTERNS if kw in content)


def _appendix_score(content: str) -> float:
    """
    综合评分。前置条件：blank_hits > 0。
    score = form_score × min(len/400, 4) × (1.3 if 含附件|附录|模板|格式 else 1.0)
    """
    if _blank_hits(content) == 0:
        return 0.0

    form_score = sum(1 for kw in FORM_PATTERNS if kw in content) / max(len(content), 1) * 200
    if form_score == 0:
        return 0.0

    len_factor = min(len(content) / 400, 4)
    boost = 1.3 if APPENDIX_PATTERN.search(content) else 1.0
    return form_score * len_factor * boost


def _is_appendix(art: ArticleInfo) -> bool:
    return _appendix_score(art.content) >= 1.0


def remove_appendix_articles(documents: List[LawDocument]) -> List[LawDocument]:
    """移除命中规则的附录 article，只移除单条，不丢整部文档"""
    result = []
    for doc in documents:
        for ch in doc.chapters:
            ch.articles = [art for art in ch.articles if not _is_appendix(art)]
        doc.preamble = [art for art in doc.preamble if not _is_appendix(art)]
        doc.chapters = [ch for ch in doc.chapters if ch.articles]
        if doc.chapters or doc.preamble:
            result.append(doc)
    return result


def get_detection_report(documents: List[LawDocument]) -> str:
    """生成检测报告"""
    lines = []
    total = 0
    filtered = 0
    for doc in documents:
        for ch in doc.chapters:
            for art in ch.articles:
                total += 1
                s = _appendix_score(art.content)
                if s >= 1.0:
                    filtered += 1
                    lines.append(
                        f"  [FILTERED] 《{doc.law_name}》第{art.article_id}条 "
                        f"score={s:.1f} blank={_blank_hits(art.content)} len={len(art.content)}"
                    )
        for art in doc.preamble:
            total += 1
            s = _appendix_score(art.content)
            if s >= 1.0:
                filtered += 1
                lines.append(
                    f"  [FILTERED] 《{doc.law_name}》preamble "
                    f"score={s:.1f} blank={_blank_hits(art.content)} len={len(art.content)}"
                )
    lines.insert(0, f"附录检测: 过滤 {filtered} 条, 保留 {total - filtered} 条")
    return "\n".join(lines)
