#!/usr/bin/env python
"""初始化招标库"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import settings
from app.storage.chroma_store import ChromaStore


# init_db.py

# init_db.py

def build_text_for_bid(record: dict) -> str:
    """构建检索文本（必须使用 Excel 里的中文表头）"""
    parts = [
        str(record.get("项目名称", "")),
        str(record.get("中标人", "")),
        str(record.get("中标金额", "")),
        str(record.get("省份", "")),
        str(record.get("市区", "")),
        str(record.get("发布时间", "")),
        str(record.get("类别", ""))
    ]
    # 过滤掉无效字符
    res = " ".join([p for p in parts if p and str(p).lower() != "nan"])
    return res


def main():
    print("=" * 60)
    print("初始化招标库")
    print("=" * 60)
    print("注意：法规库请运行 python init_pdf.py")
    print("=" * 60)

    client = ChromaStore()

    print("\n重建招标库...")
    if Path(settings.data_path_bids).exists():
        client.rebuild_from_excel("bids", settings.data_path_bids, build_text_for_bid)
    else:
        print(f"  警告: {settings.data_path_bids} 不存在")

    print("\n" + "=" * 60)
    print(f"初始化完成!")
    print(f"  Bids库: {client.get_count('bids')} 条")
    print("=" * 60)
    print("\n提示: 请运行 python init_pdf.py 导入法规库")


if __name__ == "__main__":
    main()