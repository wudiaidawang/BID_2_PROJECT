"""ViewSchema 注册表 — 替代硬编码在 Prompt 中的 schema"""

from app.data.sql.schemas import ViewSchema


def build_default_schema_catalog() -> dict[str, ViewSchema]:
    """构建默认 schema 目录（bids 表 + supplier_profile 视图）"""
    schemas = [
        ViewSchema(
            name="bids",
            description="招标项目明细表。按项目名称、类别、时间、地区、中标人等信息查询具体项目。",
            columns={
                "project_name": "项目名称",
                "category": "采购类别（工程/货物/服务/学校/政府/医院/监理/施工/设计/咨询/土地/勘察/项目评估/招标代理/项目管理）",
                "publish_date": "公告发布日期（YYYY-MM-DD）",
                "amount": "中标金额（元）",
                "supplier": "中标人/供应商名称",
                "city": "所在市区",
            },
        ),
        ViewSchema(
            name="supplier_profile",
            description="供应商画像视图（已预聚合）。按供应商维度查询中标统计、排名、能力评估。",
            columns={
                "supplier": "中标人/供应商名称",
                "total_bids": "累计中标次数",
                "total_amount": "累计中标总金额（元）",
                "avg_amount": "平均中标金额（元）",
                "category_count": "涉及项目种类数（去重）",
                "categories": "涉及项目类别列表（逗号分隔）",
                "city_count": "覆盖城市数（去重）",
                "latest_bid_date": "最近中标日期（YYYY-MM-DD）",
                "earliest_bid_date": "最早中标日期（YYYY-MM-DD）",
            },
        ),
    ]
    return {schema.name: schema for schema in schemas}
