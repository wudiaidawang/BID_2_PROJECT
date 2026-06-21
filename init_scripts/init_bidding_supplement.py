"""招标补充信息入库 'bidding_supplement' collection"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import settings
from app.storage import get_vector_store

EXCEL_PATH = Path(__file__).parent.parent / 'raw' / 'bidding_supplement.xlsx'


def build_text(record: dict) -> str:
    parts = [
        str(record.get('项目名称', '')),
        str(record.get('招标人', '')),
        str(record.get('招标人联系人', '')),
        str(record.get('招标人联系方式', '')),
        str(record.get('招标代理机构', '')),
        str(record.get('招标代理机构联系人', '')),
        str(record.get('中标人', '')),
        str(record.get('中标金额（元）', '')),
        str(record.get('项目地点', '')),
        str(record.get('发布时间', '')),
    ]
    return ' '.join([p for p in parts if p and str(p).lower() != 'nan'])


def main():
    print('=' * 60)
    print('初始化招标补充库 (bidding_supplement)')
    client = get_vector_store()
    if EXCEL_PATH.exists():
        client.rebuild_from_excel('bidding_supplement', str(EXCEL_PATH), build_text)
    else:
        print(f'警告: {EXCEL_PATH} 不存在')
    print(f"Bidding Supplement库: {client.get_count('bidding_supplement')} 条")


if __name__ == '__main__':
    main()
