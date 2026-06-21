"""价格信息入库 'price' collection (覆盖已有的空 prices collection)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import settings
from app.storage import get_vector_store

EXCEL_PATH = Path(__file__).parent.parent / 'raw' / 'price_data.xlsx'


def build_text(record: dict) -> str:
    parts = [
        str(record.get('物资名称', '')),
        str(record.get('供应商名称', '')),
        str(record.get('报价', '')),
        str(record.get('供应商地址', '')),
        str(record.get('所在省份', '')),
        str(record.get('所在市区', '')),
        str(record.get('联系人', '')),
        str(record.get('联系方式', '')),
    ]
    return ' '.join([p for p in parts if p and str(p).lower() != 'nan'])


def main():
    print('=' * 60)
    print('初始化价格信息库 (price)')
    client = get_vector_store()
    if EXCEL_PATH.exists():
        client.rebuild_from_excel('price', str(EXCEL_PATH), build_text)
    else:
        print(f'警告: {EXCEL_PATH} 不存在')
    print(f"Price库: {client.get_count('price')} 条")


if __name__ == '__main__':
    main()
