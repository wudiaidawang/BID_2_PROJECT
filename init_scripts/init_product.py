"""商品信息入库 'product' collection"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import settings
from app.storage import get_vector_store

EXCEL_PATH = Path(__file__).parent.parent / 'raw' / 'product_data.xlsx'


def build_text(record: dict) -> str:
    parts = [
        str(record.get('物资名称', '')),
        str(record.get('品牌', '')),
        str(record.get('产品类型', '')),
        str(record.get('产品参数', '')),
        str(record.get('供应商名称', '')),
        str(record.get('报价', '')),
        str(record.get('供应商地址', '')),
    ]
    return ' '.join([p for p in parts if p and str(p).lower() != 'nan'])


def main():
    print('=' * 60)
    print('初始化商品信息库 (product)')
    client = get_vector_store()
    if EXCEL_PATH.exists():
        client.rebuild_from_excel('product', str(EXCEL_PATH), build_text)
    else:
        print(f'警告: {EXCEL_PATH} 不存在')
    print(f"Product库: {client.get_count('product')} 条")


if __name__ == '__main__':
    main()
