"""企业信息入库 'enterprise' collection"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import settings
from app.storage import get_vector_store

EXCEL_PATH = Path(__file__).parent.parent / 'raw' / 'enterprise_data.xlsx'


def build_text(record: dict) -> str:
    parts = [
        str(record.get('企业名称', '')),
        str(record.get('法定代表人', '')),
        str(record.get('注册资本（万元）', '')),
        str(record.get('企业类型', '')),
        str(record.get('经营范围', '')),
        str(record.get('地址', '')),
        str(record.get('所在省份', '')),
        str(record.get('所在市区', '')),
        str(record.get('统一社会信用代码', '')),
    ]
    return ' '.join([p for p in parts if p and str(p).lower() != 'nan'])


def main():
    print('=' * 60)
    print('初始化企业信息库 (enterprise)')
    client = get_vector_store()
    if EXCEL_PATH.exists():
        client.rebuild_from_excel('enterprise', str(EXCEL_PATH), build_text)
    else:
        print(f'警告: {EXCEL_PATH} 不存在')
    print(f"Enterprise库: {client.get_count('enterprise')} 条")


if __name__ == '__main__':
    main()
