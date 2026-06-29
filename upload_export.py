"""Upload export script to remote and run it"""
import paramiko, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("47.117.173.99", port=22, username="admin", password="090903", timeout=10)

sftp = ssh.open_sftp()
sftp.put("export_policy_chunks.py", "/home/admin/group_three_5_11/data_pan/export_policy_chunks.py")
sftp.close()
print("export script uploaded")

PY = "/home/admin/group_three_5_11/test_llm/.venv/bin/python3"
stdin, stdout, stderr = ssh.exec_command(
    "cd /home/admin/group_three_5_11/data_pan && " + PY + " export_policy_chunks.py",
    timeout=300)

print(stdout.read().decode(errors='replace'))
err = stderr.read().decode(errors='replace')[:500]
if err.strip():
    print("ERR:", err)

# Download the exported file
sftp = ssh.open_sftp()
sftp.get("/home/admin/group_three_5_11/data_pan/data/eval_questions/policy_chunks_export.json",
         "data/eval_questions/policy_chunks_export.json")
sftp.close()
print("Downloaded policy_chunks_export.json")

ssh.close()
