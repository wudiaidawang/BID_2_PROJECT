#!/usr/bin/env python3
"""为高频 miss chunk 注入领域/主题/关键词 header，重新入库 Milvus"""
import json, re, sys, time
import httpx

MILVUS_URL = "http://localhost:19531"
MODEL_URL = "http://localhost:8210"
COLLECTION = "policy_v9"
DB = "panxin_dev"
OUTPUT_FIELDS = [
    "retrieval_text", "text", "title", "source_doc",
    "law_name", "article_id", "chunk_type", "parent_id",
    "chunk_order", "chunk_hash", "token_count",
    "project_name", "supplier", "region", "publish_date",
    "category", "data_version", "metadata",
]

# ── 领域/主题/关键词 映射 ──
# Key: (law_name, article_id)  Value: {domain, topic, keywords}
DOMAIN_TOPIC_MAP = {
    # ── 建设工程 ──
    ("工程建设项目施工招标投标办法", "23"): {
        "domain": "建设工程", "topic": "招标文件实质性内容",
        "keywords": ["实质性要求", "招标文件", "投标文件"],
    },
    ("工程建设项目施工招标投标办法", "37"): {
        "domain": "建设工程", "topic": "投标文件接收与投标保证金",
        "keywords": ["投标文件", "投标保证金", "联合体投标"],
    },
    ("工程建设项目施工招标投标办法", "54"): {
        "domain": "建设工程", "topic": "标底使用与中标候选人",
        "keywords": ["标底", "中标候选人", "评标报告"],
    },
    ("工程建设项目施工招标投标办法", "76"): {
        "domain": "建设工程", "topic": "评标委员会违规处罚",
        "keywords": ["评标委员会", "违规行为", "处罚"],
    },
    ("工程建设项目施工招标投标办法", "14"): {
        "domain": "建设工程", "topic": "招标终止与文件退还",
        "keywords": ["招标终止", "招标文件", "退还"],
    },
    ("工程建设项目施工招标投标办法", "43"): {
        "domain": "建设工程", "topic": "联合体投标与资格预审",
        "keywords": ["联合体", "资格预审", "增减成员"],
    },
    ("工程建设项目货物招标投标办法", "15"): {
        "domain": "建设工程", "topic": "资格预审与招标文件",
        "keywords": ["资格预审", "招标文件", "潜在投标人"],
    },
    # ── 房屋建筑 ──
    ("房屋建筑和市政基础设施工程施工招标投标管理办法", "16"): {
        "domain": "房屋建筑", "topic": "招标文件编制与资格预审",
        "keywords": ["招标文件", "资格预审", "投标申请人"],
    },
    # ── 电子招标投标 ──
    ("电子招标投标办法", "43"): {
        "domain": "电子招标投标", "topic": "公共服务平台职能",
        "keywords": ["公共服务平台", "评标结果", "串通投标"],
    },
    # ── 机电产品国际招标 ──
    ("进一步规范机电产品国际招标投标活动有关规定", "15"): {
        "domain": "机电产品国际招标", "topic": "评标初步评审",
        "keywords": ["初步评审", "投标文件", "价格评价"],
    },
    ("进一步规范机电产品国际招标投标活动有关规定", "13"): {
        "domain": "机电产品国际招标", "topic": "招标公告内容要求",
        "keywords": ["招标公告", "评标方法", "信息发布"],
    },
    ("进一步规范机电产品国际招标投标活动有关规定", "31"): {
        "domain": "机电产品国际招标", "topic": "重新评标与招标公告",
        "keywords": ["重新评标", "评标专家", "招标公告"],
    },
    ("进一步规范机电产品国际招标投标活动有关规定", "11"): {
        "domain": "机电产品国际招标", "topic": "自行招标与招标机构",
        "keywords": ["自行招标", "招标机构", "招标公告"],
    },
    ("进一步规范机电产品国际招标投标活动有关规定", "32"): {
        "domain": "机电产品国际招标", "topic": "联合体投标与备选方案",
        "keywords": ["联合体", "备选方案", "商务技术条款"],
    },
    ("进一步规范机电产品国际招标投标活动有关规定", "20"): {
        "domain": "机电产品国际招标", "topic": "评标方法与备选方案",
        "keywords": ["评标方法", "备选方案", "招标文件内容"],
    },
    ("机电产品国际招标评标专家及专家库管理办法", "99"): {
        "domain": "机电产品国际招标", "topic": "招标代理违规行为",
        "keywords": ["招标代理", "违规行为", "评标专家"],
    },
    # ── 政府采购 ──
    ("政府采购货物和服务招标投标管理办法", "56"): {
        "domain": "政府采购", "topic": "评标报告与中标人确定",
        "keywords": ["评标报告", "中标候选人", "采购人"],
    },
    # ── 招标投标法实施条例 ──
    ("中华人民共和国招标投标法实施条例", "53"): {
        "domain": "招标投标", "topic": "串通投标处理与保证金",
        "keywords": ["串通投标", "投标保证金", "招标代理"],
    },
    ("中华人民共和国招标投标法实施条例", "82"): {
        "domain": "招标投标", "topic": "政府采购货物服务例外",
        "keywords": ["政府采购", "货物服务招标", "特别规定"],
    },
    ("中华人民共和国招标投标法实施条例", "25"): {
        "domain": "招标投标", "topic": "标底与投标保证金有效期",
        "keywords": ["标底", "投标保证金", "有效期"],
    },
    ("国家对潜在投标人或者投标人的资格条件有规定", "54"): {
        "domain": "招标投标", "topic": "标底使用与中标候选人",
        "keywords": ["标底", "中标候选人", "评标委员会"],
    },
    # ── 道路运输 ──
    ("道路旅客运输班线经营权招标投标办法", "30"): {
        "domain": "道路运输", "topic": "评标委员会组成与专家条件",
        "keywords": ["评标委员会", "评标专家", "资格条件"],
    },
    # ── 铁路工程 ──
    ("铁路工程建设项目招标投标管理办法", "32"): {
        "domain": "铁路工程", "topic": "评标委员会行为规范",
        "keywords": ["评标委员会", "违规行为", "澄清说明"],
    },
    # ── 公共资源交易 ──
    ("公共资源交易平台公共资源交易平台管理暂行办法", "47"): {
        "domain": "公共资源交易", "topic": "评标专家确定与平台整合",
        "keywords": ["评标专家", "平台整合", "必要性"],
    },
    # ── 教科书 ──
    ("招标投标法律解读与风险防范实务", "0263"): {
        "domain": "招标投标", "topic": "招标文件禁止性内容",
        "keywords": ["招标文件", "不合理条件", "排斥投标人"],
    },
    ("招标投标法律解读与风险防范实务", "0887"): {
        "domain": "招标投标", "topic": "投标无效与串通投标后果",
        "keywords": ["投标无效", "串通投标", "弄虚作假"],
    },
    ("招标投标法律解读与风险防范实务", "0048"): {
        "domain": "招标投标", "topic": "投标人资格要求",
        "keywords": ["投标人资格", "资质要求", "政府采购"],
    },
    # ── V14 全量补齐（44 条，覆盖 56 miss）──
    # 建设工程
    ("工程建设项目施工招标投标办法", "35"): {
        "domain": "建设工程", "topic": "投标无效与串通投标认定",
        "keywords": ["投标无效", "串通投标", "弄虚作假"],
    },
    ("工程建设项目施工招标投标办法", "88"): {
        "domain": "建设工程", "topic": "投诉处理程序",
        "keywords": ["投诉", "异议", "招标投标活动"],
    },
    ("工程建设项目货物招标投标办法", "21"): {
        "domain": "建设工程", "topic": "标包划分与招标文件内容",
        "keywords": ["标包", "招标文件", "实质性要求"],
    },
    ("工程建设项目勘察设计招标投标办法", "12"): {
        "domain": "建设工程", "topic": "招标文件收费与发售",
        "keywords": ["招标文件", "收费", "发售期限"],
    },
    ("公路工程建设项目评标工作细则", "4"): {
        "domain": "建设工程", "topic": "评标工作保密要求",
        "keywords": ["评标", "保密", "评标委员会"],
    },
    ("公路养护工程施工招标投标管理暂行规定", "19"): {
        "domain": "建设工程", "topic": "招标文件修改与违规认定",
        "keywords": ["招标文件", "修改时限", "违规行为"],
    },
    ("水利工程建设项目招标投标审计办法", "7"): {
        "domain": "建设工程", "topic": "审计范围与执行解释",
        "keywords": ["审计", "招标投标", "执行时间"],
    },
    ("水利工程建设项目招标投标审计办法", "20"): {
        "domain": "建设工程", "topic": "招标投标行为审计重点",
        "keywords": ["审计重点", "招标投标", "行为规范"],
    },
    ("房屋建筑和市政基础设施工程施工招标投标管理办法", "22"): {
        "domain": "建设工程", "topic": "投标人资格条件",
        "keywords": ["资格条件", "潜在投标人", "资质要求"],
    },
    ("民政部工程建设项目招标投标管理办法", "7"): {
        "domain": "建设工程", "topic": "资格预审评审",
        "keywords": ["资格预审", "评审委员会", "投标人"],
    },
    # 政府采购
    ("政府采购货物和服务招标投标管理办法", "39"): {
        "domain": "政府采购", "topic": "评标委员会成员回避",
        "keywords": ["评标委员会", "回避", "利益冲突"],
    },
    ("政府采购货物和服务招标投标管理办法", "61"): {
        "domain": "政府采购", "topic": "评标委员会行为规范",
        "keywords": ["评标委员会", "澄清说明", "投标文件"],
    },
    ("政府采购货物和服务招标投标管理办法", "71"): {
        "domain": "政府采购", "topic": "评标委员会违规处罚",
        "keywords": ["评标委员会", "违规行为", "处罚"],
    },
    ("政府采购货物和服务招标投标管理办法", "77"): {
        "domain": "政府采购", "topic": "采购人违规处罚",
        "keywords": ["采购人", "违规处罚", "法律责任"],
    },
    ("政府采购非招标采购方式管理办法", "22"): {
        "domain": "政府采购", "topic": "供应商履约验收",
        "keywords": ["履约验收", "供应商", "采购人"],
    },
    ("中华人民共和国政府采购法", "51"): {
        "domain": "政府采购", "topic": "供应商询问质疑处理",
        "keywords": ["询问", "质疑", "采购代理机构"],
    },
    ("中华人民共和国政府采购法实施条例", "11"): {
        "domain": "政府采购", "topic": "采购人禁止行为",
        "keywords": ["采购人", "禁止行为", "政府采购"],
    },
    ("中华人民共和国政府采购法实施条例", "21"): {
        "domain": "政府采购", "topic": "资格预审与中标人确定",
        "keywords": ["资格预审", "中标人", "资格审查"],
    },
    ("中华人民共和国政府采购法实施条例", "42"): {
        "domain": "政府采购", "topic": "采购代理机构违规处罚",
        "keywords": ["采购代理机构", "倾向性说明", "专家抽取"],
    },
    ("《中华人民共和国政府采购法实施条例》等有关法", "15"): {
        "domain": "政府采购", "topic": "采购信息发布与资格预审",
        "keywords": ["采购信息", "资格预审", "采购需求"],
    },
    ("《中华人民共和国政府采购法实施条例》等有关法", "22"): {
        "domain": "政府采购", "topic": "资格预审公告内容",
        "keywords": ["资格预审", "公告内容", "政府采购"],
    },
    ("政府购买服务管理办法", "26"): {
        "domain": "政府采购", "topic": "承接主体义务与购买主体限制",
        "keywords": ["承接主体", "购买主体", "事业单位"],
    },
    ("政府购买服务管理办法", "33"): {
        "domain": "政府采购", "topic": "事业单位购买服务改革",
        "keywords": ["事业单位", "购买服务", "改革目标"],
    },
    ("国有金融企业集中采购管理暂行规定", "29"): {
        "domain": "政府采购", "topic": "采购当事人违规追责",
        "keywords": ["采购当事人", "追责", "集中采购"],
    },
    ("交通运输部部属单位政府采购管理办法", "44"): {
        "domain": "政府采购", "topic": "采购后续工作与询价方式",
        "keywords": ["采购后续", "询价方式", "政府采购"],
    },
    ("中央国家机关政府采购中心货物和服务定点采购管理办法", "14"): {
        "domain": "政府采购", "topic": "供应商禁止行为",
        "keywords": ["供应商", "禁止行为", "定点采购"],
    },
    # 招标投标
    ("中华人民共和国招标投标法", "32"): {
        "domain": "招标投标", "topic": "否决所有投标的条件",
        "keywords": ["否决投标", "评标委员会", "投标人"],
    },
    ("中华人民共和国招标投标法实施条例", "11"): {
        "domain": "招标投标", "topic": "招标代理机构职责",
        "keywords": ["招标代理", "串通投标", "义务"],
    },
    ("中华人民共和国招标投标法实施条例", "44"): {
        "domain": "招标投标", "topic": "评标专家确定方式",
        "keywords": ["评标专家", "专家库", "随机抽取"],
    },
    ("标法》《中华人民共和国招标投标法实施条例》等法", "41"): {
        "domain": "招标投标", "topic": "禁止投标行为与串通投标",
        "keywords": ["禁止行为", "串通投标", "法律责任"],
    },
    ("系统工程综合评标专家库管理办法", "12"): {
        "domain": "招标投标", "topic": "评标专家条件与义务",
        "keywords": ["评标专家", "资格条件", "专家义务"],
    },
    # 机电产品国际招标
    ("进一步规范机电产品国际招标投标活动有关规定", "38"): {
        "domain": "机电产品国际招标", "topic": "投标文件撤回与备选方案",
        "keywords": ["投标文件", "撤回", "备选方案"],
    },
    ("机电产品国际招标评标专家及专家库管理办法", "83"): {
        "domain": "机电产品国际招标", "topic": "投诉材料要求",
        "keywords": ["投诉", "证明材料", "评标专家"],
    },
    # 铁路工程
    ("铁路工程建设项目招标投标管理办法", "19"): {
        "domain": "铁路工程", "topic": "招标终止与保证金处理",
        "keywords": ["招标终止", "保证金", "异常低价"],
    },
    ("铁路工程建设项目招标投标管理办法", "59"): {
        "domain": "铁路工程", "topic": "电子招标与基本原则",
        "keywords": ["电子招标", "基本原则", "公共资源交易"],
    },
    # 民航
    ("民航专业工程建设项目招标投标管理办法", "28"): {
        "domain": "民航工程", "topic": "联合体投标与资格预审变更",
        "keywords": ["联合体", "资格预审", "成员变更"],
    },
    ("民航专业工程建设项目招标投标管理办法", "36"): {
        "domain": "民航工程", "topic": "专家确定方式与随机抽取",
        "keywords": ["专家", "随机抽取", "评标"],
    },
    # 通信工程
    ("通信工程建设项目招标投标管理办法", "13"): {
        "domain": "通信工程", "topic": "实质性要求与条件标明",
        "keywords": ["实质性要求", "招标文件", "条件"],
    },
    ("通信工程建设项目评标专家及评标专家库管理办法", "11"): {
        "domain": "通信工程", "topic": "评标专家回避情形",
        "keywords": ["评标专家", "回避", "利益关系"],
    },
    # 电子招标投标
    ("电子招标投标办法", "46"): {
        "domain": "电子招标投标", "topic": "行政监督部门职责",
        "keywords": ["行政监督", "电子招标", "监督职责"],
    },
    # 公共资源交易
    ("公共资源交易平台公共资源交易平台管理暂行办法", "7"): {
        "domain": "公共资源交易", "topic": "平台整合背景与规则",
        "keywords": ["平台整合", "运行规则", "必要性"],
    },
    # 道路运输
    ("中华人民共和国道路运输条例", "50"): {
        "domain": "道路运输", "topic": "投标无效行为认定",
        "keywords": ["投标无效", "违规行为", "行政处罚"],
    },
    # 其他
    ("明确或实际投标人报名数量未达到招标公告中规定", "41"): {
        "domain": "招标投标", "topic": "政府部门招投标职责分工",
        "keywords": ["政府部门", "职责", "招标投标"],
    },
    ("监督处理中华人民共和国行政处罚法", "25"): {
        "domain": "招标投标", "topic": "违规投标处理与处罚",
        "keywords": ["行政处罚", "弄虚作假", "串通投标"],
    },
}


def _post(endpoint, payload):
    r = httpx.post(f"{MILVUS_URL}{endpoint}", json=payload, timeout=120)
    r.raise_for_status()
    body = r.json()
    if body.get("code") != 0:
        raise RuntimeError(f"Milvus error code={body.get('code')}: {body.get('message', '')}")
    return body.get("data", body)


def embed(texts):
    r = httpx.post(f"{MODEL_URL}/embed", json={"texts": texts}, timeout=30)
    r.raise_for_status()
    return r.json()["embeddings"]


def _get_field(entity: dict, key: str) -> str:
    """优先顶层，fallback metadata"""
    val = entity.get(key, "")
    if val:
        return str(val)
    meta = entity.get("metadata", {})
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            return ""
    if isinstance(meta, dict):
        return str(meta.get(key, ""))
    return ""


def build_enriched_header(law_name: str, article_id: str, chapter: str,
                          article_text: str,
                          enrichment: dict | None = None) -> str:
    """构建带 domain/topic/keywords 的新 header"""
    if enrichment is None:
        enrichment = DOMAIN_TOPIC_MAP.get((law_name, article_id))
    parts = [f"《{law_name}》"]
    if enrichment:
        parts.append(f"领域：{enrichment['domain']}")
        parts.append(f"主题：{enrichment['topic']}")
        parts.append(f"关键词：{','.join(enrichment['keywords'])}")
    if chapter and chapter != "前言/附则":
        parts.append(chapter)
    parts.append(article_text)
    return "\n".join(parts)


def find_affected_chunks():
    """从 Milvus 找到所有需要更新的 chunk → enrichment 映射。

    非教科书: 按 chunk_id 前缀 parent_{law_name}_{article_id}_ 匹配。
    教科书:   article_id 为空，按 law_name + 关键词匹配 retrieval_text。

    Returns: dict[chunk_id] = {domain, topic, keywords}
    """
    print("查找受影响的 chunks...")

    chunk_map = {}  # chunk_id → enrichment dict

    for (law_name, article_id), enrichment in DOMAIN_TOPIC_MAP.items():
        safe_name = law_name.replace(" ", "").replace("/", "_")[:20]
        is_textbook = "法律解读与风险防范实务" in law_name

        if is_textbook:
            keywords = enrichment.get("keywords", [])
            data = _post("/v2/vectordb/entities/query", {
                "collectionName": COLLECTION, "dbName": DB,
                "filter": f'law_name == "{law_name}"',
                "limit": 200,
                "outputFields": ["id", "retrieval_text", "chunk_order"],
            })
            if isinstance(data, list):
                matched = []
                for e in data:
                    rt = e.get("retrieval_text", "")
                    hits = sum(1 for kw in keywords if kw in rt)
                    if hits >= 2:
                        matched.append(e["id"])
                        chunk_map[e["id"]] = enrichment
                if matched:
                    print(f"  {law_name[:25]} [教科书] 第{article_id}节 → {len(matched)} chunks")
                else:
                    print(f"  {law_name[:25]} [教科书] 第{article_id}节 → 未匹配! 关键词={keywords}")
        else:
            prefix = f"parent_{safe_name}_{article_id}_"
            data = _post("/v2/vectordb/entities/query", {
                "collectionName": COLLECTION, "dbName": DB,
                "filter": f'id like "{prefix}%"',
                "limit": 100,
                "outputFields": ["id"],
            })
            if isinstance(data, list):
                for e in data:
                    chunk_map[e["id"]] = enrichment
                if data:
                    print(f"  {law_name[:25]} 第{article_id}条 → {len(data)} chunks")

    return chunk_map


def rebuild_and_upsert(chunk_map: dict):
    """重建 retrieval_text + 重新 embedding + upsert

    Args:
        chunk_map: dict[chunk_id] = {domain, topic, keywords}
    """
    chunk_ids = list(chunk_map.keys())
    print(f"\n重建 {len(chunk_ids)} 个 chunks...")

    batch_size = 5
    updated = 0

    for i in range(0, len(chunk_ids), batch_size):
        batch = chunk_ids[i:i + batch_size]

        # 1. 获取完整 entity
        entities = _post("/v2/vectordb/entities/get", {
            "collectionName": COLLECTION, "dbName": DB,
            "id": batch,
        })
        if not isinstance(entities, list):
            continue

        # 2. 重建每个 entity 的 retrieval_text
        texts_to_embed = []
        for e in entities:
            chunk_id = e.get("id", "")
            enrichment = chunk_map.get(chunk_id)
            if not enrichment:
                continue

            law_name = _get_field(e, "law_name")
            article_id = _get_field(e, "article_id")
            chapter = _get_field(e, "chapter")
            parent_id = _get_field(e, "parent_id")
            chunk_type = _get_field(e, "chunk_type")
            chunk_order = _get_field(e, "chunk_order")
            text = e.get("text", "")
            old_retrieval = e.get("retrieval_text", "")

            # 构建 article_text
            article_text = _get_field(e, "article") or ""
            if not article_text:
                lines = old_retrieval.split("[SEP]")[0].strip().split("\n")
                if lines:
                    article_text = lines[-1]

            # 构建新 header（直接传 enrichment 而非查表）
            new_header = build_enriched_header(
                law_name, article_id, chapter, article_text, enrichment)

            # child chunk: 保留 [子N: ...] 后缀
            if chunk_type.endswith("_child") or parent_id:
                old_header = old_retrieval.split("[SEP]")[0].strip() if "[SEP]" in old_retrieval else ""
                child_suffix = ""
                m = re.search(r'\[子\d+[：:][^\]]*\]', old_header)
                if m:
                    child_suffix = " " + m.group(0)
                else:
                    child_suffix = f" [子{chunk_order}]"
                new_retrieval = f"{new_header}{child_suffix}\n[SEP]\n{text}"
            else:
                new_retrieval = f"{new_header}\n[SEP]\n{text}"

            if "领域：" not in old_retrieval:
                e["retrieval_text"] = new_retrieval
                texts_to_embed.append(new_retrieval)
            else:
                e["retrieval_text"] = old_retrieval

        if not texts_to_embed:
            continue

        # 3. 重新 embedding
        try:
            vectors = embed(texts_to_embed)
        except Exception as ex:
            print(f"  Embed error: {ex}")
            continue

        # 4. 更新 dense_vector
        vec_idx = 0
        for e in entities:
            if "领域：" in e.get("retrieval_text", "") and vec_idx < len(vectors):
                e["dense_vector"] = vectors[vec_idx]
                vec_idx += 1

        # 5. Upsert
        entities_to_upsert = [e for e in entities if "领域：" in e.get("retrieval_text", "")]
        if entities_to_upsert:
            _post("/v2/vectordb/entities/upsert", {
                "collectionName": COLLECTION, "dbName": DB,
                "data": entities_to_upsert,
            })
            updated += len(entities_to_upsert)

            for e in entities_to_upsert:
                eid = e.get("id", "")[:50]
                enr = chunk_map.get(e.get("id", ""), {})
                print(f"  [OK] {eid} → {enr.get('domain', '')}/{enr.get('topic', '')}")

        if updated % 20 == 0 and updated > 0:
            print(f"  [{updated}/{len(chunk_ids)}]...")

        time.sleep(0.1)

    return updated


def verify(chunk_map: dict):
    """验证更新结果"""
    print("\n验证更新结果...")
    # 按 law_name 分组取样
    sample_ids = list(chunk_map.keys())[:10]
    if not sample_ids:
        return
    entities = _post("/v2/vectordb/entities/get", {
        "collectionName": COLLECTION, "dbName": DB,
        "id": sample_ids,
    })
    if isinstance(entities, list):
        for e in entities:
            rt = e.get("retrieval_text", "")[:120]
            has_enrich = "领域：" in rt
            enr = chunk_map.get(e.get("id", ""), {})
            print(f"  {'[OK]' if has_enrich else '[MISS]'} {e.get('id', '')[:60]} → {enr.get('domain', '')}/{enr.get('topic', '')}")
            if has_enrich:
                header_part = rt.split("[SEP]")[0] if "[SEP]" in rt else rt[:120]
                print(f"    Header: {header_part[:100]}")


if __name__ == "__main__":
    print("=" * 60)
    print("Header 领域/主题Enrichment — 高频 Miss Chunk 修复")
    print(f"映射条目: {len(DOMAIN_TOPIC_MAP)}")
    print("=" * 60)

    chunk_map = find_affected_chunks()
    if not chunk_map:
        print("未找到受影响的 chunk！")
        sys.exit(1)

    print(f"\n共 {len(chunk_map)} 个 chunks 需要更新")

    updated = rebuild_and_upsert(chunk_map)
    print(f"\n完成: 更新了 {updated} 个 chunks")

    verify(chunk_map)
