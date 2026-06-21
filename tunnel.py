"""SSH隧道 — 3端口转发 + 断线自动重连.

转发:
  19531 → Milvus
  8001  → Reranker
  8002  → Embedding
"""
import socket
import sys
import threading
import time

import paramiko

REMOTE_HOST = "47.117.173.99"
SSH_PORT = 22
SSH_USER = "admin"

FORWARDS = [
    (19531, "127.0.0.1", 19531, "Milvus"),
    (8001, "127.0.0.1", 8001, "Reranker"),
    (8002, "127.0.0.1", 8002, "Embedding"),
]

RECONNECT_DELAY = 5  # 断线后等待秒数再重连


def fwd(src, dst):
    """双向转发数据"""
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except (OSError, EOFError):
        pass
    finally:
        try:
            src.close()
        except OSError:
            pass
        try:
            dst.close()
        except OSError:
            pass


def start_forward(client, local_port, remote_host, remote_port, label):
    """在SSH连接上创建一个转发"""
    def handler():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", local_port))
        sock.listen(5)
        print(f"[tunnel] {label}: 127.0.0.1:{local_port} -> {remote_host}:{remote_port}")
        sys.stdout.flush()
        while True:
            try:
                conn, addr = sock.accept()
            except OSError:
                break
            try:
                chan = client.get_transport().open_channel(
                    "direct-tcpip", (remote_host, remote_port), addr
                )
                if chan is None:
                    conn.close()
                    continue
            except Exception:
                conn.close()
                continue
            threading.Thread(target=fwd, args=(conn, chan), daemon=True).start()
            threading.Thread(target=fwd, args=(chan, conn), daemon=True).start()

    threading.Thread(target=handler, daemon=True).start()


def connect_ssh(password):
    """建立SSH连接"""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=REMOTE_HOST,
        port=SSH_PORT,
        username=SSH_USER,
        password=password,
        timeout=10,
        banner_timeout=10,
    )
    return client


def main():
    if len(sys.argv) < 2:
        print("用法: python tunnel.py <密码>")
        sys.exit(1)

    password = sys.argv[1]

    while True:
        try:
            print(f"[tunnel] 连接 {SSH_USER}@{REMOTE_HOST}:{SSH_PORT} ...")
            sys.stdout.flush()
            client = connect_ssh(password)
            print(f"[tunnel] SSH已连接")
            sys.stdout.flush()

            for local_port, remote_host, remote_port, label in FORWARDS:
                start_forward(client, local_port, remote_host, remote_port, label)

            # 阻塞直到连接断开
            client.get_transport().is_alive()  # 等一阵再开始心跳
            while client.get_transport().is_alive():
                time.sleep(5)
            print("[tunnel] 连接断开，准备重连...")
        except Exception as e:
            print(f"[tunnel] 连接失败: {e}")

        print(f"[tunnel] {RECONNECT_DELAY}s后重连...")
        sys.stdout.flush()
        time.sleep(RECONNECT_DELAY)


if __name__ == "__main__":
    main()
