"""Install jieba on remote, then run baseline eval"""
import paramiko, io, sys, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("47.117.173.99", port=22, username="admin", password="090903", timeout=10)
PY = "/home/admin/group_three_5_11/test_llm/.venv/bin/python3"

print("1. 安装 jieba rank_bm25...")
ssh.exec_command("nohup " + PY + " -m pip install jieba rank_bm25 > /tmp/pip_install3.log 2>&1 &")
time.sleep(60)

stdin, stdout, stderr = ssh.exec_command(PY + " -c 'import jieba, rank_bm25; print(\"OK\")' 2>&1")
result = stdout.read().decode(errors='replace').strip()
if "OK" in result:
    print("  安装成功")
else:
    print("  安装失败:", result[:200])
    # 看日志
    stdin2, stdout2, stderr2 = ssh.exec_command("tail -5 /tmp/pip_install3.log")
    print("  日志:", stdout2.read().decode(errors='replace')[:300])
    ssh.close()
    sys.exit(1)

print("2. 跑评测（142题）...")
ssh.exec_command("pkill -f run_recall_eval_full 2>/dev/null; sleep 1")
stdin, stdout, stderr = ssh.exec_command(
    "cd /home/admin/group_three_5_11/data_pan && nohup " + PY +
    " run_recall_eval_full.py > /tmp/eval_final2.log 2>&1 & echo PID:$!")
pid = stdout.read().decode().strip()
print("  PID:", pid)

# 等待完成（约3分钟）
for sec in [60, 120, 180, 240]:
    time.sleep(sec)
    stdin2, stdout2, stderr2 = ssh.exec_command("ps aux | grep run_recall_eval_full | grep -v grep")
    if not stdout2.read().decode().strip():
        break

print("3. 结果:")
stdin3, stdout3, stderr3 = ssh.exec_command(
    "grep -E 'parent_hit|exact_hit|miss|total|Done|soft|By type|by_category|regulation_article|policy_doc|pdf_case|opinion' /tmp/eval_final2.log 2>/dev/null")
print(stdout3.read().decode(errors='replace')[:2000])

# 看完整输出最后30行
print("\n--- 最后30行 ---")
stdin4, stdout4, stderr4 = ssh.exec_command("tail -30 /tmp/eval_final2.log")
print(stdout4.read().decode(errors='replace'))

ssh.close()
