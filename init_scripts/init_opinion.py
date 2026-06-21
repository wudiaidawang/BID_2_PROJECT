"""舆情数据入库 'opinion' collection"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import settings
from app.storage import get_vector_store

EXCEL_PATH = Path(__file__).parent.parent / 'raw' / 'opinion_data.xlsx'


def build_text(record: dict) -> str:
    parts = [
        str(record.get('舆情标题', '')),
        str(record.get('舆情内容', '')),
        str(record.get('新闻来源', '')),
        str(record.get('发布时间', '')),
    ]
    return ' '.join([p for p in parts if p and str(p).lower() != 'nan'])


def main():
    print('=' * 60)
    print('初始化舆情库 (opinion)')
    client = get_vector_store()
    if EXCEL_PATH.exists():
        client.rebuild_from_excel('opinion', str(EXCEL_PATH), build_text)
    else:
        print(f'警告: {EXCEL_PATH} 不存在')
    print(f"Opinion库: {client.get_count('opinion')} 条")


if __name__ == '__main__':
    main()
