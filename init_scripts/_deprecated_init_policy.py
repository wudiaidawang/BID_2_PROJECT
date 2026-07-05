"""
将政策法规数据导入 ChromaDB 'policy' collection
来源: data/raw/policy_data.xlsx
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config import settings
from app.storage import get_vector_store

EXCEL_PATH = Path(__file__).parent.parent / 'raw' / 'policy_data.xlsx'


def build_text(record: dict) -> str:
    parts = [
        str(record.get('政策标题', '')),
        str(record.get('发布机构', '')),
        str(record.get('发布日期', '')),
        str(record.get('法规分类', '')),
        str(record.get('正文摘要', '')),
    ]
    return ' '.join([p for p in parts if p and str(p).lower() != 'nan'])


def main():
    print('=' * 60)
    print('初始化政策法规库 (policy)')
    print('=' * 60)

    client = get_vector_store()

    if EXCEL_PATH.exists():
        client.rebuild_from_excel('policy', str(EXCEL_PATH), build_text)
    else:
        print(f'警告: {EXCEL_PATH} 不存在，请先运行 data/scrapers/get_policy.py')

    print(f"\nPolicy库: {client.get_count('policy')} 条")
    print('=' * 60)


if __name__ == '__main__':
    main()
