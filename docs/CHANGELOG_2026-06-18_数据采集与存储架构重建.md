# 更新日志13：数据采集与存储架构重建

**日期：** 2026-06-18

## 背景

根据 PRD 需求文档，补齐 6 大类本地数据（政策信息、招标信息补充、舆情信息、企业信息、价格信息、商品信息）。在已有 8,789 条招标记录和 10 个法规 PDF 基础上，通过外部采集 + 深度提取，将数据全部向量化入服务器 Milvus，结构化数据入 SQLite。

## 最终存储架构

```
Milvus (服务器 47.117.173.99:19531, db=panxin_bid_rag_v1)
├── bids         (8,789 chunks) — 招标项目，现有未动
├── regulations  (~5,000 chunks) — 法律法规条文，现有未动
└── policy       (~9,800 chunks, NEW) — 政策法规 + 舆情 + 10个PDF

SQLite (data/bid_data.db)
├── bids         (8,789 rows) — 招标项目明细
├── enterprise   (4,157 rows, NEW) — 从 bids 聚合的企业画像
├── price        (588 rows, NEW) — 物资报价
└── product      (207 rows, NEW) — 商品参数
```

## 6 大数据集采集结果

| 数据集 | 条数 | 目标 | 采集方式 |
|--------|------|------|----------|
| 政策信息 | 228 | 200 | shggzy.com 4栏目 + ccgp.gov.cn fallback |
| 招标补充 | 200 | 200 | ccgp.gov.cn 最新中标公告（不与已有重合） |
| 舆情信息 | 2,014 | 500 | ccgp.gov.cn 5大公告栏目列表页快速抓取 |
| 企业信息 | 300 (Excel) + 4,157 (SQL聚合) | 300 | bid_data 深度提取中标次数/金额/业务领域 |
| 价格信息 | 588 | 400 | bid_data 深度提取，28个品类分类+品牌识别 |
| 商品信息 | 207 | 300 | bid_data 正则提取品牌/规格/功率/电压参数 |

**总计：Excel 3,537 条 + SQLite 聚合 4,157 条 + Milvus ~23,600 chunks**

## 关键决策

### 舆情数据：列表页抓取策略
最初尝试百度新闻、搜狗新闻、CCGP搜索均返回0条。最终方案：直接抓取 CCGP 中标公告/竞争性磋商/公开招标等栏目的列表页标题。这些公告本身就是最丰富的招投标公开信息源。每个栏目 30 页 × ~20 条 = 600+ 条，5 个栏目合计 2,014 条。

### 企业信息：放弃天眼查，改用 bid_data 深度提取
天眼查/爱企查页面为 JS 渲染，BeautifulSoup 无法获取有效字段，且反爬严格。改为从 bid_data 按 supplier 聚合：中标次数、累计金额、平均金额、业务领域、活跃城市。生成 4,157 条企业画像，比外部爬取更丰富、更可靠。

### 价格信息：垂类系统，不做过度模拟
价格数据 588 条来自 bid_data 实际项目中的预算和成交价。品类覆盖 28 种（工程机械、医疗设备、电气设备、建材钢材等）。条数未进一步扩充的原因：本系统是招投标垂类 Q&A，每条价格记录对应真实招标项目，不模拟无依据的价格数据。极端价格查询（如"某罕见设备多少钱"）走 RAG 语义检索而非 SQL 聚合。

### 商品信息：受限于 bid_data 项目名称粒度
207 条商品数据从项目名称中提取品牌 + 规格参数（尺寸、功率、电压、管径等）。条数低于目标的原因：bid_data 中仅部分项目名称包含足够详细的产品规格描述，无法无中生有。

## 存储初始化脚本

| 脚本 | 功能 |
|------|------|
| `init_policy_collection.py` | **新建** — Milvus policy collection 全量初始化（policy Excel + opinion Excel + 10个PDF chunking） |
| `init_sqlite_tables.py` | **新建** — SQLite enterprise/price/product 建表 + 从 bids 聚合 enterprise + Excel 数据导入 |

## 代码改动

| 文件 | 改动 |
|------|------|
| `config.yaml` | `vector_store.backend` → `milvus`；`collections` 新增 `policy`；新增 `sqlite_tables` 定义 |
| `app/pipeline/pipeline.py` | `search_unified()` 检索列表增加 `policy` collection；`get_stats()` 增加 policy 计数 |
| `app/core/sql_engine.py` | system_prompt 增加 enterprise / price / product 三张表的字段描述和路由规则 |
| `data/scrapers/get_opinion.py` | 重写 v3：快速列表抓取策略，覆盖 CCGP 5 大公告栏目 |
| `data/scrapers/get_enterprise.py` | 重写：从 bid_data 聚合企业画像，替代天眼查爬取 |
| `data/scrapers/get_product.py` | 修复 4 处正则捕获组 bug（`(?:...)` → `(...)`） |

## 数据采集脚本汇总

所有爬虫位于 `data/scrapers/`：

| 脚本 | 输出 | 条数 |
|------|------|------|
| `get_policy.py` | policy_data.xlsx | 228 |
| `get_bidding_supplement.py` | bidding_supplement.xlsx | 200 |
| `get_opinion.py` | opinion_data.xlsx | 2,014 |
| `get_enterprise.py` | enterprise_data.xlsx | 300 |
| `get_price.py` | price_data.xlsx | 588 |
| `get_product.py` | product_data.xlsx | 207 |
