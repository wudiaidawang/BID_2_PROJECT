"""诊断 Milvus sparse_vector 中文检索的有效边界

对 10 种不同 query 类型逐一测 BM25 命中数，量化内置 n-gram 分析器
在自然语言问句上的失效范围，为 BM25 本地化改造提供证据。

需在服务器上运行: python3 test_bm25_sparse_analysis.py
依赖: 127.0.0.1:19531 (Milvus REST API)
"""
import json, urllib.request

BASE = "http://localhost:19531/v2/vectordb/entities/search"

QUERIES = [
    ("短词-招标", "招标"),
    ("短词-投标", "投标"),
    ("短词-政府采购", "政府采购"),
    ("短词-道路客运", "道路客运"),
    ("短语-招标投标法", "招标投标法"),
    ("短语-道路客运班线", "道路客运班线"),
    ("短语-道路客运班线经营许可", "道路客运班线经营许可"),
    ("问句-短", "道路客运班线经营许可期限多久"),
    ("问句-长", "在招标投标过程中出现投标文件附有招标人无法接受的条件时评标委员会应如何处理"),
    ("问句-有专名", "根据《水利工程建设项目重要设备材料采购招标投标管理办法》，使用本项目资金购置的哪些设备属于重要设备"),
]

for label, q in QUERIES:
    payload = json.dumps({
        "collectionName": "policy", "dbName": "panxin_dev",
        "data": [q],
        "annsField": "sparse_vector",
        "limit": 20,
        "outputFields": ["id", "law_name", "article_id"],
        "searchParams": {"metricType": "BM25", "params": {}},
    }).encode()
    req = urllib.request.Request(BASE, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
        data = result.get("data", [])
        if isinstance(data, list) and data and isinstance(data[0], list):
            hits = data[0]
        else:
            hits = data
    print(f"[{label}] hits={len(hits):>3}  query={q[:50]}")
    if hits:
        top = hits[0]
        print(f"  top1: score={top.get('distance',0):.2f}  law={top.get('law_name','?')[:40]}")
