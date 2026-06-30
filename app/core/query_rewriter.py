"""统一查询改写器 — 队友3层规则 + 你的jieba口语映射，纯规则零API调用"""
import re
import json
from pathlib import Path
from typing import List, Tuple, Optional

from app.core.legal_entity_registry import is_protected_entity


class QueryRewriter:
    """统一查询改写器（单例）"""

    _instance: Optional["QueryRewriter"] = None

    def __new__(cls) -> "QueryRewriter":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_rules()
        return cls._instance

    def _init_rules(self) -> None:
        from config import settings

        self.enable_colloquial = settings.qr_colloquial_to_formal
        self.enable_redundancy = settings.qr_redundancy_removal
        self.enable_synonym = settings.qr_synonym_expansion

        # ── 第一层：标点规范化 ──
        self.punctuation_map = {
            "？": "?", "！": "!", "；": ";", "：": ":",
            "，": ",", "。": ".", "、": ",", "（": "(",
            "）": ")", "“": '"', "”": '"', "《": "<", "》": ">",
        }

        # ── 第二层：冗余短语（按长度降序匹配） ──
        self.redundant_phrases = sorted([
            "我想问一下", "我想请问", "我想知道", "请问一下",
            "帮我查一下", "帮我看看", "我想了解一下", "麻烦问一下",
            "能不能告诉我", "可以告诉我", "请问您", "请问你",
        ], key=len, reverse=True)

        self.redundancy_patterns = [
            r"(请问){2,}", r"(你好){2,}", r"(那个){2,}",
            r"(这个){2,}", r"就是+", r"那个", r"这个", r"然后",
        ]

        # ── 第三层：口语→书面语（YAML映射 + JSON字典合并） ──
        # 从 YAML 配置读取（队友的数据）
        yaml_mappings = {}
        try:
            from app.core.config_loader import config_loader
            yaml_mappings.update(config_loader.get("query_rewriter.colloquial_mappings", {}))
        except Exception:
            pass

        # 从本地 JSON 文件读取（你的数据）
        json_path = Path(__file__).parent.parent.parent / "data" / "colloquial_map.json"
        json_mappings = {}
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                json_mappings = json.load(f)

        # 合并：YAML 优先（可覆盖 JSON），按长度降序
        merged = {}
        merged.update(json_mappings)
        merged.update(yaml_mappings)
        self.colloquial_mappings: List[Tuple[str, str]] = sorted(
            merged.items(), key=lambda x: len(x[0]), reverse=True
        )

        # ── 第四层：行业同义词（口语 → 标准术语） ──
        synonym_mappings = {
            "串标": "串通投标", "围标": "串通投标", "陪标": "串通投标",
            "挂靠": "借用资质", "借资质": "借用资质", "买标": "串通投标", "卖标": "串通投标",
            "打分": "评标", "打分办法": "评标办法", "评分标准": "评标办法", "评标方式": "评标办法",
            "拦标价": "招标控制价", "最高限价": "招标控制价", "底价": "招标控制价",
            "保函": "投标保证金",
            "资格": "资格条件", "资质": "资格条件",
            "招投标法": "招标投标法", "招标法": "招标投标法", "投标法": "招标投标法",
            "采购法": "政府采购法", "民法典": "中华人民共和国民法典",
            "招标方": "招标人", "投标方": "投标人", "采购方": "采购人",
            "供应商": "投标人", "业主": "招标人", "甲方": "招标人", "乙方": "投标人",
            "罚款": "处罚", "受罚": "承担法律责任", "惩罚": "处罚",
            "截标": "投标截止", "开标会": "开标", "评标会": "评标", "交标": "递交投标文件",
        }
        # YAML 中的同义词可覆盖默认
        try:
            from app.core.config_loader import config_loader
            synonym_mappings.update(config_loader.get("query_rewriter.synonym_mappings", {}))
        except Exception:
            pass
        self.synonym_mappings: List[Tuple[str, str]] = sorted(
            synonym_mappings.items(), key=lambda x: len(x[0]), reverse=True
        )

    def rewrite(self, question: str) -> str:
        """执行改写管道：标点规范 → 条款号规范化 → 冗余精简 → 口语转书面语 → 同义词替换"""
        if not question or not isinstance(question, str):
            return question or ""

        result = question

        # 0. 标点规范化（始终执行）
        result = self._normalize_punctuation(result)

        # 0.5 条款号规范化：中文数字 → 阿拉伯数字（始终执行，避免"第三十七条"和"第37条"不一致）
        result = self._normalize_article_numbers(result)

        # 如果包含法规名称，跳过后续改写（保护专有名词不被改坏）
        # 使用统一实体注册中心检测
        if is_protected_entity(result):
            return result

        # 1. 冗余精简
        if self.enable_redundancy:
            result = self._remove_redundancy(result)

        # 2. 口语转书面语
        if self.enable_colloquial:
            result = self._colloquial_to_formal(result)

        # 3. 同义词扩展 —— 已禁用（最易造成语义漂移，改为仅做口语规范化 + 实体识别）
        # if self.enable_synonym:
        #     result = self._expand_synonyms(result)

        # 4. 清理多余空格
        result = re.sub(r"\s+", " ", result).strip()

        if not result:
            return question

        if result != question:
            print(f"   [Rewrite] {question[:60]}... -> {result[:60]}...")

        return result

    def _normalize_punctuation(self, text: str) -> str:
        for cn, en in self.punctuation_map.items():
            text = text.replace(cn, en)
        return text

    def _normalize_article_numbers(self, text: str) -> str:
        """将条款号中的中文数字统一转为阿拉伯数字。

        覆盖: 第X条 / 第X款 / 第X项 / 第X章 / 第X节
        数字范围: 一～九、十、百、千（如"第一百二十三条"→"第123条"）
        """
        from app.utils.chinese_number import chinese_number_converter
        result = text
        cn_num = r'[一二三四五六七八九十百千]+'
        for suffix in ['条', '款', '项', '章', '节']:
            for match in re.finditer(rf'第({cn_num}){suffix}', result):
                chinese = match.group(1)
                arabic = chinese_number_converter.to_arabic(chinese)
                if arabic != chinese:
                    result = result.replace(f'第{chinese}{suffix}', f'第{arabic}{suffix}')
        return result

    def _remove_redundancy(self, text: str) -> str:
        result = text
        for phrase in self.redundant_phrases:
            while phrase in result:
                result = result.replace(phrase, "")
        for pattern in self.redundancy_patterns:
            try:
                result = re.sub(pattern, "", result)
            except re.error:
                continue
        result = re.sub(r"([?!。，,；;：:])\1+", r"\1", result)
        return result

    def _colloquial_to_formal(self, text: str) -> str:
        """词边界感知的口语→书面语替换。
        多字词直接替换；单字词仅当作为独立 jieba token 时才替换。
        """
        import jieba
        result = text
        for colloquial, formal in self.colloquial_mappings:
            if len(colloquial) >= 2 and colloquial in result:
                result = result.replace(colloquial, formal)

        single_chars = {c: f for c, f in self.colloquial_mappings if len(c) == 1}
        if single_chars and result:
            tokens = list(jieba.cut(result))
            new_tokens = [single_chars.get(t, t) for t in tokens]
            result = "".join(new_tokens)
        return result

    def _expand_synonyms(self, text: str) -> str:
        """同义词替换 —— 追加标准术语，同时保留原始口语词"""
        result = text
        for oral, standard in self.synonym_mappings:
            if oral in result and standard not in result:
                result = result.replace(oral, f"{oral} {standard}")
        return result

    def is_enabled(self) -> bool:
        return self.enable_colloquial or self.enable_redundancy or self.enable_synonym


# 全局单例
query_rewriter = QueryRewriter()
