"""Download benchmark from remote and show sample"""
import paramiko, json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("47.117.173.99", port=22, username="admin", password="090903", timeout=10)

sftp = ssh.open_sftp()
sftp.get("/home/admin/group_three_5_11/data_pan/data/eval_questions/eval_benchmark_v4.json",
         "data/eval_questions/eval_benchmark_v4.json")
sftp.close()
ssh.close()
print("下载完成")

with open("data/eval_questions/eval_benchmark_v4.json", "r", encoding="utf-8") as f:
    d = json.load(f)

print(f"总题数: {len(d['qa_pairs'])}")
print("\n前5题:")
for q in d['qa_pairs'][:5]:
    print(f"  [{q['chunk_type']}] {q['question'][:70]}")
    print(f"    expected={q['expected_chunk_id']}, span={q['span']}")
print("\n按类型分布:")
from collections import Counter
ct = Counter(q['chunk_type'] for q in d['qa_pairs'])
for t, c in ct.most_common():
    print(f"  {t}: {c}")
