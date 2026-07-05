#!/bin/bash
source ~/group_three_5_11/data_pan/.venv/bin/activate
echo "=== Installing pymupdf (mirror) ==="
pip install pymupdf -i https://pypi.tuna.tsinghua.edu.cn/simple 2>&1
echo "=== Verify ==="
python -c "import fitz; print('fitz OK, version:', fitz.version)"
echo "=== DONE ==="
