#!/usr/bin/env python3
"""部署 V16 eval 脚本到服务器并启动 screen 会话"""
import paramiko, os, sys

HOST = "47.117.173.99"
USER = "admin"
PASS = "090903"
VENV_PY = "/home/admin/group_three_5_11/model_service/.venv/bin/python"
REMOTE_DIR = "/home/admin/group_three_5_11/data_pan"

LOCAL_FILES = [
    ("eval_standalone.py", "eval_standalone.py"),
    ("app/core/legal_entity_registry.py", "app/core/legal_entity_registry.py"),
    ("data/eval_questions/v9/v9_canonical.jsonl", "data/eval_questions/v9/v9_canonical.jsonl"),
]

print("Connecting...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=22, username=USER, password=PASS, timeout=15)
sftp = ssh.open_sftp()

# Create directories recursively
dirs_to_create = [
    REMOTE_DIR,
    f"{REMOTE_DIR}/app",
    f"{REMOTE_DIR}/app/core",
    f"{REMOTE_DIR}/data",
    f"{REMOTE_DIR}/data/eval_questions",
    f"{REMOTE_DIR}/data/eval_questions/v9",
    f"{REMOTE_DIR}/data/eval_questions/v16",
]
for d in dirs_to_create:
    try:
        sftp.stat(d)
    except FileNotFoundError:
        cmd = f"mkdir -p {d}"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        stdout.read()
        stderr.read()
        print(f"  mkdir {d}")

# Upload files
for local_rel, remote_rel in LOCAL_FILES:
    local_path = os.path.join("E:/BID_3_PROJECT_langchain", local_rel)
    remote_path = f"{REMOTE_DIR}/{remote_rel}"
    size_mb = os.path.getsize(local_path) / 1024 / 1024
    print(f"Upload {local_rel} ({size_mb:.1f}MB)...")
    sftp.put(local_path, remote_path)
    print(f"  Done")

sftp.close()

# Verify
stdin, stdout, stderr = ssh.exec_command(f"ls -la {REMOTE_DIR}/ && echo --- && ls -la {REMOTE_DIR}/data/eval_questions/v9/")
print(stdout.read().decode())

# Start eval in screen (V16)
cmd_eval = f"cd {REMOTE_DIR} && screen -S eval_v16 -dm bash -c \"{VENV_PY} -u eval_standalone.py 2>&1 | tee eval_v16.log\""
stdin, stdout, stderr = ssh.exec_command(cmd_eval)
print(f"Eval screen: {stdout.read().decode()} {stderr.read().decode()}")

# Show screen list
stdin, stdout, stderr = ssh.exec_command("screen -ls 2>&1")
print(stdout.read().decode())

print("\nDone. Commands to check:")
print(f"  ssh admin@{HOST}")
print(f"  screen -r eval_v16")
print(f"  tail -f {REMOTE_DIR}/eval_v16.log")
print(f"  cat {REMOTE_DIR}/data/eval_questions/v16/v16_recall_report.md")

ssh.close()
