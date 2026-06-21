#!/usr/bin/env python
"""初始化招标库"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import settings
from app.storage import get_vector_store


def build_text_for_bid(record: dict):
    """构建检索文本，返回 (retrieval_text, text)"""
    parts = [
        str(record.get("项目名称", "")),
        str(record.get("中标人", "")),
        str(record.get("中标金额", "")),
        str(record.get("省份", "")),
        str(record.get("市区", "")),
        str(record.get("发布时间", "")),
        str(record.get("类别", ""))
    ]
    rt = " ".join([p for p in parts if p and str(p).lower() != "nan"])
    return rt, rt  # bid 数据 retrieval_text = text（无 header 注入）


def main():
    print("=" * 60)
    print("初始化招标库")
    print("=" * 60)
    print("注意：法规库请运行 python init_policy_collection.py")
    print("=" * 60)

    client = get_vector_store()

    print("\n重建招标库...")
    if Path(settings.data_path_bids).exists():
        client.rebuild_from_excel("bids", settings.data_path_bids, build_text_for_bid,
                                  extra_metadata={
                                      "chunk_type": "bid_project",
                                      "data_version": "2026-06-18_v1",
                                      "source_doc": "bid_data.xlsx",
                                  })
    else:
        print(f"  警告: {settings.data_path_bids} 不存在")

    # 创建供应商画像视图（SQLite VIEW，自动与主表同步）
    _create_supplier_profile_view()

    print("\n" + "=" * 60)
    print(f"初始化完成!")
    print(f"  招标库: {client.get_count('bids')} 条")
    print("=" * 60)
    print("\n提示: 请运行 python init_policy_collection.py 导入法规库")


def _create_supplier_profile_view():
    """在 SQLite 中创建供应商画像视图，用于企业资质类查询"""
    import sqlite3
    try:
        conn = sqlite3.connect(settings.db_path)
        conn.execute("DROP VIEW IF EXISTS supplier_profile")
        conn.execute("""
            CREATE VIEW supplier_profile AS
            SELECT
                supplier,
                COUNT(*) AS total_bids,
                SUM(amount) AS total_amount,
                ROUND(AVG(amount), 2) AS avg_amount,
                COUNT(DISTINCT category) AS category_count,
                GROUP_CONCAT(DISTINCT category) AS categories,
                COUNT(DISTINCT city) AS city_count,
                MAX(publish_date) AS latest_bid_date,
                MIN(publish_date) AS earliest_bid_date
            FROM bids
            GROUP BY supplier
        """)
        conn.commit()
        conn.close()
        print(f"  供应商画像视图已创建")
    except Exception as e:
        print(f"  警告: 创建供应商画像视图失败: {e}")


if __name__ == "__main__":
    main()