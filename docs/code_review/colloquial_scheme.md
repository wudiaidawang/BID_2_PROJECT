# 招投标NLP口语转书面语模块改进方案

## 1. 分层Pipeline设计

### 1.1 管道架构
```
输入文本 → 预处理 → 核心改写 → 后处理 → 输出文本
```

### 1.2 详细分层
1. **输入验证层**：检查文本有效性，处理空值
2. **预处理层**：
   - 标点符号规范化
   - 条款号规范化（中文数字转阿拉伯数字）
   - 法规名称保护
3. **核心改写层**：
   - 冗余短语移除
   - 口语转书面语映射
   - 行业同义词替换
4. **后处理层**：
   - 空格清理
   - 特殊格式处理
   - 输出验证

## 2. 招投标领域专用映射表

### 2.1 映射表结构设计
```json
{
  "colloquial_mappings": {
    "招标流程": {
      "口语表达": ["招标", "投标", "开标", "评标", "定标"],
      "标准术语": "招标流程"
    },
    "投标行为": {
      "口语表达": ["串标", "围标", "陪标", "挂靠", "买标", "卖标"],
      "标准术语": "串通投标"
    },
    "金额相关": {
      "口语表达": ["保证金", "保函", "押金", "定金"],
      "标准术语": "投标保证金"
    },
    "资质相关": {
      "口语表达": ["资格", "资质", "资信", "资格条件"],
      "标准术语": "资格条件"
    },
    "时间相关": {
      "口语表达": ["截标", "开标会", "评标会", "交标"],
      "标准术语": "投标截止"
    },
    "处罚相关": {
      "口语表达": ["罚款", "受罚", "惩罚", "处罚"],
      "标准术语": "处罚"
    },
    "人员相关": {
      "口语表达": ["招标方", "投标方", "采购方", "供应商", "业主", "甲方", "乙方"],
      "标准术语": ["招标人", "投标人", "采购人", "投标人", "招标人", "招标人", "投标人"]
    }
  },
  "synonym_mappings": {
    "串标": ["围标", "陪标", "买标", "卖标"],
    "挂靠": ["借用资质"],
    "拦标价": ["最高限价", "底价"],
    "打分": ["评标", "评分标准"],
    "截标": ["投标截止"]
  }
}
```

### 2.2 映射表实现
```python
# data/tender_colloquial_map.json
{
  "招标流程": {
    "口语表达": ["招标", "投标", "开标", "评标", "定标"],
    "标准术语": "招标流程"
  },
  "投标行为": {
    "口语表达": ["串标", "围标", "陪标", "挂靠", "买标", "卖标"],
    "标准术语": "串通投标"
  },
  "金额相关": {
    "口语表达": ["保证金", "保函", "押金", "定金"],
    "标准术语": "投标保证金"
  },
  "资质相关": {
    "口语表达": ["资格", "资质", "资信", "资格条件"],
    "标准术语": "资格条件"
  },
  "时间相关": {
    "口语表达": ["截标", "开标会", "评标会", "交标"],
    "标准术语": "投标截止"
  },
  "处罚相关": {
    "口语表达": ["罚款", "受罚", "惩罚", "处罚"],
    "标准术语": "处罚"
  },
  "人员相关": {
    "口语表达": ["招标方", "投标方", "采购方", "供应商", "业主", "甲方", "乙方"],
    "标准术语": ["招标人", "投标人", "采购人", "投标人", "招标人", "招标人", "投标人"]
  }
}
```

## 3. 可落地Python代码

### 3.1 改进后的QueryRewriter类
```python
import re
import json
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
import jieba

class TenderQueryRewriter:
    """招投标领域专用查询改写器（单例）"""

    _instance: Optional["TenderQueryRewriter"] = None

    def __new__(cls) -> "TenderQueryRewriter":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_rules()
        return cls._instance

    def _init_rules(self) -> None:
        # 加载配置
        from config import settings
        self.enable_colloquial = settings.qr_colloquial_to_formal
        self.enable_redundancy = settings.qr_redundancy_removal
        self.enable_synonym = settings.qr_synonym_expansion

        # 法规名称保护列表
        self._protected_names = [
            "中华人民共和国招标投标法", "招标投标法", "中华人民共和国政府采购法",
            "政府采购法", "中华人民共和国民法典", "民法典", "中华人民共和国合同法",
            "招标投标法实施条例", "政府采购法实施条例",
            "工程建设项目招标投标管理办法", "招标拍卖挂牌出让国有土地使用权规定",
            "建设工程质量管理条例", "建筑工程施工许可管理办法",
            "工程建设项目施工招标投标办法", "评标委员会和评标办法暂行规定",
            "电子招标投标办法", "必须招标的工程项目规定",
            "招标投标条例", "采购法", "合同法",
        ]
        self._protected_names = sorted(self._protected_names, key=len, reverse=True)

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

        # ── 第三层：招投标领域口语→书面语映射 ──
        self._load_colloquial_mappings()

        # ── 第四层：招投标领域同义词 ──
        self._load_synonym_mappings()

    def _load_colloquial_mappings(self) -> None:
        """加载招投标领域口语映射表"""
        yaml_mappings = {}
        try:
            from app.core.config_loader import config_loader
            yaml_mappings.update(config_loader.get("query_rewriter.colloquial_mappings", {}))
        except Exception:
            pass

        # 从本地 JSON 文件读取
        json_path = Path(__file__).parent.parent.parent / "data" / "tender_colloquial_map.json"
        json_mappings = {}
        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                json_mappings = json.load(f)

        # 合并映射表
        merged = {}
        merged.update(json_mappings)
        merged.update(yaml_mappings)
        
        # 转换为列表并按长度降序排序
        self.colloquial_mappings: List[Tuple[str, str]] = []
        for category, data in merged.items():
            for phrase in data["口语表达"]:
                self.colloquial_mappings.append((phrase, data["标准术语"]))
        
        self.colloquial_mappings = sorted(
            self.colloquial_mappings, key=lambda x: len(x[0]), reverse=True
        )

    def _load_synonym_mappings(self) -> None:
        """加载招投标领域同义词映射表"""
        default_synonyms = {
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

        # 尝试从YAML加载
        yaml_synonyms = {}
        try:
            from app.core.config_loader import config_loader
            yaml_synonyms = config_loader.get("query_rewriter.synonym_mappings", {})
        except Exception:
            pass

        # 合并同义词映射
        merged_synonyms = {}
        merged_synonyms.update(default_synonyms)
        merged_synonyms.update(yaml_synonyms)
        
        self.synonym_mappings: List[Tuple[str, str]] = sorted(
            merged_synonyms.items(), key=lambda x: len(x[0]), reverse=True
        )

    def rewrite(self, question: str) -> str:
        """执行改写管道：标点规范 → 条款号规范化 → 冗余精简 → 口语转书面语 → 同义词替换"""
        if not question or not isinstance(question, str):
            return question or ""

        result = question

        # 0. 标点规范化（始终执行）
        result = self._normalize_punctuation(result)

        # 0.5 条款号规范化（始终执行）
        result = self._normalize_article_numbers(result)

        # 如果包含法规名称，跳过后续改写
        if self._contains_protected_name(result):
            return result

        # 1. 冗余精简
        if self.enable_redundancy:
            result = self._remove_redundancy(result)

        # 2. 口语转书面语
        if self.enable_colloquial:
            result = self._colloquial_to_formal(result)

        # 3. 同义词替换
        if self.enable_synonym:
            result = self._expand_synonyms(result)

        # 4. 清理多余空格
        result = re.sub(r"\s+", " ", result).strip()

        if not result:
            return question

        if result != question:
            print(f"   [Rewrite] {question[:60]}... -> {result[:60]}...")

        return result

    def _contains_protected_name(self, text: str) -> bool:
        """检查文本中是否包含法规名称"""
        for name in self._protected_names:
            if name in text:
                return True
        return False

    def _normalize_punctuation(self, text: str) -> str:
        for cn, en in self.punctuation_map.items():
            text = text.replace(cn, en)
        return text

    def _normalize_article_numbers(self, text: str) -> str:
        """将条款号中的中文数字统一转为阿拉伯数字"""
        from app.utils.chinese_number import chinese_number_converter
        result = text
        for match in re.finditer(r'第([一二三四五六七八九十百千]+)条', text):
            chinese = match.group(1)
            arabic = chinese_number_converter.to_arabic(chinese)
            if arabic != chinese:
                result = result.replace(f"第{chinese}条", f"第{arabic}条")
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
        """招投标领域口语转书面语替换"""
        import jieba
        result = text
        
        # 多字词直接替换
        for colloquial, formal in self.colloquial_mappings:
            if len(colloquial) >= 2 and colloquial in result:
                result = result.replace(colloquial, formal)

        # 单字词处理
        single_chars = {c: f for c, f in self.colloquial_mappings if len(c) == 1}
        if single_chars and result:
            tokens = list(jieba.cut(result))
            new_tokens = [single_chars.get(t, t) for t in tokens]
            result = "".join(new_tokens)
        return result

    def _expand_synonyms(self, text: str) -> str:
        """招投标领域同义词替换"""
        result = text
        for oral, standard in self.synonym_mappings:
            if oral in result:
                result = result.replace(oral, standard)
        return result

    def is_enabled(self) -> bool:
        return self.enable_colloquial or self.enable_redundancy or self.enable_synonym


# 全局单例
tender_query_rewriter = TenderQueryRewriter()
```

### 3.2 改进后的QueryPreprocessor类
```python
import re
from typing import List, Dict, Set

from app.core.tender_query_rewriter import tender_query_rewriter

# ── 招投标领域同义词对（用于 BM25 查询扩展）──
TENDER_SYNONYMS: Dict[str, List[str]] = {
    "投标人": ["供应商", "潜在投标人", "投标方"],
    "排斥": ["限制", "排除", "歧视"],
    "处罚": ["罚款", "处分", "惩戒"],
    "没收": ["不予退还", "不退还"],
    "禁止": ["不得", "不允许", "严禁"],
    "透露": ["泄露", "泄漏", "泄密"],
    "保证金": ["投标保证金", "履约保证金"],
    "撤回": ["撤销", "收回"],
    "分包": ["转包", "分包人"],
    "废标": ["流标", "无效投标"],
    "围标": ["串标", "串通投标"],
    "指定": ["标明", "要求", "限定"],
    "品牌": ["厂家", "制造商", "生产商"],
    "资质": ["资格", "资信"],
    "招标控制价": ["拦标价", "最高限价", "底价"],
    "评标": ["打分", "评分标准"],
    "投标截止": ["截标"]
}

# ── 定义类问题模式 ──
DEFINITION_PATTERNS = [
    "是什么", "什么是", "的定义", "定义是",
    "什么意思", "指的是", "是指", "指的是什么",
    "概念", "含义", "如何理解",
]


class TenderQueryPreprocessor:
    """招投标领域专用查询预处理器"""

    def __init__(self, enable_synonym_expansion: bool = True):
        self.enable_synonyms = enable_synonym_expansion
        self._definition_patterns_cache = self._compile_patterns()

    def _compile_patterns(self) -> Set[str]:
        """预编译定义类问题模式"""
        return set(DEFINITION_PATTERNS)

    def process(self, query: str) -> str:
        """
        预处理管线：
        1. 口语→书面语（TenderQueryRewriter）
        2. 同义词扩展（BM25 召回增强）—— 定义类问题跳过
        """
        if not query:
            return ""

        # Step 1: 归一化
        normalized = tender_query_rewriter.rewrite(query)

        # Step 2: 同义词扩展（定义类问题跳过）
        if self.enable_synonyms and not self._is_definition_query(query):
            normalized = self._expand_synonyms(normalized)

        return normalized

    def _is_definition_query(self, query: str) -> bool:
        """检测是否为定义/概念解释类问题"""
        return any(pat in query for pat in self._definition_patterns_cache)

    def _expand_synonyms(self, query: str) -> str:
        """招投标领域双向同义词扩展"""
        expanded = query
        for term, synonyms in TENDER_SYNONYMS.items():
            if term in query:
                for syn in synonyms:
                    if syn not in expanded:
                        expanded += " " + syn
            else:
                for syn in synonyms:
                    if syn in query:
                        if term not in expanded:
                            expanded += " " + term"
                        break
        return expanded


# 模块级快捷函数
_tender_preprocessor = TenderQueryPreprocessor()

def preprocess_tender_query(query: str) -> str:
    return _tender_preprocessor.process(query)
```

## 4. 集成方式

### 4.1 配置集成
```python
# config/settings.py
class Settings:
    # 查询改写器配置
    qr_colloquial_to_formal = True
    qr_redundancy_removal = True
    qr_synonym_expansion = True
    
    # 招投标领域特定配置
    tender_domain_enabled = True