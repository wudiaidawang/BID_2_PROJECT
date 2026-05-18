#!/usr/bin/env python
"""准确率测试脚本 - 验证Top-5准确率是否达到92%"""

import asyncio
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.core.retriever import HybridRetriever
from app.core.router import IntentRouter


MANUAL_EVAL_PATH = "./data/manual_eval_set.json"
EVAL_QUESTIONS_DIR = "./data/eval_questions"


def load_eval_cases() -> list:
    """加载评估用例：优先从 eval_questions/ 目录合并所有 JSON 文件，其次回退到旧路径"""
    eval_dir = Path(EVAL_QUESTIONS_DIR)
    if eval_dir.exists():
        json_files = sorted(eval_dir.glob("*.json"))
        cases = []
        for jf in json_files:
            with open(jf, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                cases.extend(data)
        if cases:
            return cases

    if Path(MANUAL_EVAL_PATH).exists():
        with open(MANUAL_EVAL_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)

    return []


async def evaluate():
    print("=" * 60)
    print("准确率测试")
    print("=" * 60)

    test_cases = load_eval_cases()
    if not test_cases:
        print(f"\n错误: 未找到评估用例")
        print(f"请将问答 .json 文件放入 {EVAL_QUESTIONS_DIR}/ 目录下")
        return

    print(f"\n加载评估集: {len(test_cases)} 条")
    
    retriever = HybridRetriever()
    router = IntentRouter()
    
    correct = 0
    total = len(test_cases)
    failed = []
    
    for i, case in enumerate(test_cases, 1):
        question = case.get("question", "")
        expected_answer = case.get("expected_answer", "")
        
        print(f"\n[{i}/{total}] 测试: {question[:50]}...")
        
        # 意图识别
        route = router.route(question)
        
        # 检索
        results = retriever.search(
            query=question,
            collection=route["collection"],
            top_k=5
        )
        
        # 验证（简化的关键词匹配，实际可用更复杂的评估）
        found = False
        for j, r in enumerate(results):
            text = r.get("text", "")
            # 检查答案中的关键词是否在检索结果中
            keywords = expected_answer.split()[:3] if expected_answer else []
            if keywords and all(kw in text for kw in keywords):
                found = True
                print(f"  ✅ 第{j+1}位命中")
                break
            elif not keywords and j == 0:
                found = True
                break
        
        if found:
            correct += 1
        else:
            print(f"  ❌ 未命中")
            failed.append(question)
    
    accuracy = correct / total * 100
    
    print("\n" + "=" * 60)
    print(f"测试结果:")
    print(f"  总用例: {total}")
    print(f"  正确: {correct}")
    print(f"  准确率: {accuracy:.1f}%")
    print(f"  目标: 92%")
    print(f"  {'✅ 达标' if accuracy >= 92 else '❌ 未达标'}")
    print("=" * 60)
    
    if failed:
        print(f"\n失败用例 ({len(failed)}):")
        for q in failed[:10]:
            print(f"  - {q[:60]}...")


if __name__ == "__main__":
    asyncio.run(evaluate())
# 1. 安装Python 3.9+
python --version

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动Redis（需要先安装Redis）
redis-server
# 1. 创建目录
mkdir -p data/pdfs

# 2. 放置Excel文件
#    data/bid_data.xlsx（你的8000+条招标数据）

# 3. 放置PDF
#    data/pdfs/招标投标法律解读与风险防范实务.pdf
#    data/pdfs/中华人民共和国招标投标法律法规全书.pdf

# 4. 创建手工评估集（可选）
#    data/manual_eval_set.json
# 初始化招标库和价格库
python init_db.py

# 初始化PDF法规库
python init_pdf.py
python main.py
# 测试法规问答
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "招标法第三条是什么"}'

# 测试招标问答
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "紫蓬镇项目中标价是多少"}'

# 健康检查
curl http://localhost:8000/api/v1/health
[
  {
    "question": "招标投标活动中，哪些行为属于串通投标？",
    "expected_answer": "串通投标 投标人之间 招标人与投标人"
  },
  {
    "question": "投标保证金的比例是多少？",
    "expected_answer": "投标保证金 不得超过 估算价 2%"
  }
]