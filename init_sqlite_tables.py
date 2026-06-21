#!/usr/bin/env python
"""
初始化 SQLite 表: enterprise, price, product
+ 从 bids 表聚合生成 enterprise 数据
+ 追加 CnOpenData 清洗数据到 bids（如果文件存在）
"""

import sys
import sqlite3
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
from config import settings

RAW_DIR = Path(__file__).parent / "data" / "raw"


def create_tables(conn):
    """创建 enterprise / price / product 三张表"""
    print("\n[1/4] 创建表结构...")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS enterprise (
            id              TEXT PRIMARY KEY,
            company_name    TEXT NOT NULL,
            role            TEXT DEFAULT '中标单位',
            bid_count       INTEGER DEFAULT 0,
            total_amount    REAL DEFAULT 0,
            avg_amount      REAL DEFAULT 0,
            province        TEXT,
            city            TEXT,
            industry        TEXT,
            clients         TEXT,
            categories      TEXT,
            latest_bid_date TEXT,
            earliest_bid_date TEXT,
            updated_at      TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS price (
            id              TEXT PRIMARY KEY,
            material_name   TEXT NOT NULL,
            brand           TEXT,
            supplier        TEXT,
            category        TEXT,
            budget_price    REAL,
            bid_price       REAL,
            unit            TEXT,
            province        TEXT,
            city            TEXT,
            collect_date    TEXT,
            source_url      TEXT,
            search_keyword  TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS product (
            id              TEXT PRIMARY KEY,
            product_name    TEXT NOT NULL,
            brand           TEXT,
            product_type    TEXT,
            supplier        TEXT,
            spec_params     TEXT,
            province        TEXT,
            city            TEXT,
            collect_date    TEXT,
            source_url      TEXT,
            search_keyword  TEXT
        )
    """)

    conn.commit()
    print("  表 enterprise / price / product 已就绪")


def populate_enterprise_from_bids(conn):
    """从 bids 表聚合生成企业画像"""
    print("\n[2/4] 从 bids 聚合 enterprise 数据...")

    # 检查 bids 是否有 winner/supplier 字段
    cols = [c[1] for c in conn.execute("PRAGMA table_info(bids)").fetchall()]
    print(f"  bids 表字段: {cols}")

    existing = conn.execute("SELECT COUNT(*) FROM enterprise").fetchone()[0]
    if existing > 0:
        print(f"  enterprise 已有 {existing} 条数据，跳过聚合 (安全模式)")
        return

    # 按 supplier 聚合 (bids表实际字段: project_name, category, publish_date, amount, supplier, city)
    sql = """
        INSERT OR REPLACE INTO enterprise
            (id, company_name, role, bid_count, total_amount, avg_amount,
             province, city, industry, categories,
             latest_bid_date, earliest_bid_date, updated_at)
        SELECT
            hex(randomblob(8)),
            TRIM(supplier),
            '中标单位',
            COUNT(*),
            SUM(COALESCE(amount, 0)),
            ROUND(AVG(COALESCE(amount, 0)), 2),
            '',
            GROUP_CONCAT(DISTINCT COALESCE(city, '')),
            MAX(category),
            GROUP_CONCAT(DISTINCT COALESCE(category, '')),
            MAX(publish_date),
            MIN(publish_date),
            datetime('now')
        FROM bids
        WHERE supplier IS NOT NULL AND supplier != ''
        GROUP BY TRIM(supplier)
    """
    conn.execute(sql)
    conn.commit()
    cnt = conn.execute("SELECT COUNT(*) FROM enterprise").fetchone()[0]
    print(f"  已生成 {cnt} 条企业画像")


def populate_price_from_excel(conn):
    """从 price_data.xlsx 导入价格数据"""
    print("\n[3/4] 导入价格数据...")
    price_path = RAW_DIR / "price_data.xlsx"
    if not price_path.exists():
        print(f"  [跳过] {price_path} 不存在")
        return

    df = pd.read_excel(price_path)
    print(f"  读取 {len(df)} 条")

    rows = []
    for _, row in df.iterrows():
        r = row.to_dict()
        # 解析金额字段
        bid_price = None
        budget_price = None
        if '报价_预算' in r and r['报价_预算']:
            bp = str(r['报价_预算']).replace('元', '').replace(',', '').strip()
            try:
                budget_price = float(bp)
            except ValueError:
                pass
        if '报价_中标价' in r and r['报价_中标价']:
            bp2 = str(r['报价_中标价']).replace('元', '').replace(',', '').strip()
            try:
                bid_price = float(bp2)
            except ValueError:
                pass

        rows.append({
            "id": str(uuid.uuid4()),
            "material_name": str(r.get('物资名称', '')),
            "brand": str(r.get('品牌', '')),
            "supplier": str(r.get('供应商名称', '')),
            "category": str(r.get('产品分类', '')),
            "budget_price": budget_price,
            "bid_price": bid_price,
            "province": str(r.get('所在省份', '')),
            "city": str(r.get('所在市区', '')),
            "collect_date": str(r.get('采集时间', '')),
            "source_url": str(r.get('来源网站', '')),
            "search_keyword": str(r.get('搜索关键词', '')),
        })

    existing = conn.execute("SELECT COUNT(*) FROM price").fetchone()[0]
    if existing > 0:
        print(f"  price 已有 {existing} 条数据，跳过导入 (安全模式)")
        return
    pd.DataFrame(rows).to_sql("price", conn, if_exists="append", index=False)
    conn.commit()
    print(f"  入库 {len(rows)} 条")


def populate_product_from_excel(conn):
    """从 product_data.xlsx 导入商品数据"""
    print("\n[4/4] 导入商品数据...")
    prod_path = RAW_DIR / "product_data.xlsx"
    if not prod_path.exists():
        print(f"  [跳过] {prod_path} 不存在")
        return

    df = pd.read_excel(prod_path)
    print(f"  读取 {len(df)} 条")

    rows = []
    for _, row in df.iterrows():
        r = row.to_dict()
        rows.append({
            "id": str(uuid.uuid4()),
            "product_name": str(r.get('物资名称', '')),
            "brand": str(r.get('品牌', '')),
            "product_type": str(r.get('产品类型', '')),
            "supplier": str(r.get('供应商名称', '')),
            "spec_params": str(r.get('产品参数', '')),
            "province": str(r.get('所在省份', '')),
            "city": str(r.get('所在市区', '')),
            "collect_date": str(r.get('采集时间', '')),
            "source_url": str(r.get('来源网站', '')),
            "search_keyword": str(r.get('搜索关键词', '')),
        })

    existing = conn.execute("SELECT COUNT(*) FROM product").fetchone()[0]
    if existing > 0:
        print(f"  product 已有 {existing} 条数据，跳过导入 (安全模式)")
        return
    pd.DataFrame(rows).to_sql("product", conn, if_exists="append", index=False)
    conn.commit()
    print(f"  入库 {len(rows)} 条")


def main():
    print("=" * 60)
    print("SQLite 表结构初始化 + 数据导入")
    print("=" * 60)

    db_path = settings.db_path
    print(f"数据库: {db_path}")
    conn = sqlite3.connect(db_path)

    # Step 1: 建表
    create_tables(conn)

    # Step 2: enterprise 从 bids 聚合
    populate_enterprise_from_bids(conn)

    # Step 3: price 从 Excel
    populate_price_from_excel(conn)

    # Step 4: product 从 Excel
    populate_product_from_excel(conn)

    # ── 验证 ──
    print(f"\n{'=' * 60}")
    print("验证: 各表行数")
    for t in ['bids', 'enterprise', 'price', 'product']:
        try:
            cnt = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"  {t}: {cnt} 行")
        except Exception as e:
            print(f"  {t}: 不存在 ({e})")

    conn.close()
    print(f"\n{'=' * 60}")
    print("SQLite 初始化完成")


if __name__ == "__main__":
    main()
