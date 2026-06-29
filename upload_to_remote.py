"""Upload all app files + run ingestion on remote"""
import paramiko, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HOST = "47.117.173.99"
USER = "admin"
PASS = "090903"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=22, username=USER, password=PASS, timeout=10)
print("SSH OK")

files = [
    ("init_policy_collection.py", "data_pan/init_policy_collection.py"),
    ("config.py", "data_pan/config.py"),
    ("app/__init__.py", "data_pan/app/__init__.py"),
    ("app/core/__init__.py", "data_pan/app/core/__init__.py"),
    ("app/core/config_loader.py", "data_pan/app/core/config_loader.py"),
    ("app/core/legal_structure_parser.py", "data_pan/app/core/legal_structure_parser.py"),
    ("app/core/appendix_detector.py", "data_pan/app/core/appendix_detector.py"),
    ("app/core/parent_chunk_builder.py", "data_pan/app/core/parent_chunk_builder.py"),
    ("app/core/child_chunk_builder.py", "data_pan/app/core/child_chunk_builder.py"),
    ("app/core/model_client.py", "data_pan/app/core/model_client.py"),
    ("app/core/embedding.py", "data_pan/app/core/embedding.py"),
    ("app/storage/__init__.py", "data_pan/app/storage/__init__.py"),
    ("app/storage/milvus_store.py", "data_pan/app/storage/milvus_store.py"),
    ("app/storage/chroma_store.py", "data_pan/app/storage/chroma_store.py"),
    ("app/utils/__init__.py", "data_pan/app/utils/__init__.py"),
    ("app/utils/chinese_number.py", "data_pan/app/utils/chinese_number.py"),
    ("app/schema/__init__.py", "data_pan/app/schema/__init__.py"),
    ("app/schema/metadata.py", "data_pan/app/schema/metadata.py"),
    # 上传 config.yaml（远程无此文件，默认走 chroma）
    ("config.yaml", "data_pan/config.yaml"),
]

dirs = set()
for _, remote in files:
    d = os.path.dirname("/home/admin/group_three_5_11/" + remote)
    if d:
        dirs.add(d)
ssh.exec_command("mkdir -p " + " ".join('"' + d + '"' for d in dirs))

sftp = ssh.open_sftp()
for local, remote in files:
    sftp.put(local, "/home/admin/group_three_5_11/" + remote)
    print("  OK: " + local)
sftp.close()
print(str(len(files)) + " files uploaded")

# Upload and run export script
for local, remote in [
    ("export_policy_chunks.py", "data_pan/export_policy_chunks.py"),
]:
    sftp.put(local, "/home/admin/group_three_5_11/" + remote)
    print("  OK: " + local)

PY = "/home/admin/group_three_5_11/test_llm/.venv/bin/python3"
stdin, stdout, stderr = ssh.exec_command(
    "cd /home/admin/group_three_5_11/data_pan && " + PY + " init_policy_collection.py",
    timeout=600)

print("")
print("=== 入库结果 ===")
out = stdout.read().decode(errors='replace')
print(out[-3000:])
err = stderr.read().decode(errors='replace')[:1000]
if err.strip():
    print("=== ERR ===")
    print(err[-500:])

ssh.close()
