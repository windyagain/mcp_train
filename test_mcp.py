# test_mcp_simple.py
import json
import subprocess
import sys
import os

project_root = "/Users/pxy/PycharmProjects/mcp_train"


def test():
    # 构建请求
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"}
        }
    }

    body = json.dumps(req).encode()
    header = f"Content-Length: {len(body)}\r\n\r\n".encode()

    print(f"Sending: {header.decode()}{body.decode()}")
    print("-" * 50)

    # 启动服务器
    proc = subprocess.Popen(
        [sys.executable, "-u", "-m", "app.internal_mcp_server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=project_root,
        env={**os.environ, "PYTHONPATH": project_root},
        bufsize=0,  # 无缓冲
    )

    try:
        # 发送请求
        proc.stdin.write(header + body)
        proc.stdin.flush()

        print("Waiting for response...")

        # 设置超时
        import select
        import time

        # 等待可读（最多5秒）
        ready, _, _ = select.select([proc.stdout], [], [], 5.0)
        if not ready:
            print("TIMEOUT! No response in 5 seconds")
            print("Stderr:", proc.stderr.read().decode())
            return

        # 读取第一行（Content-Length）
        line = proc.stdout.readline()
        print(f"Raw response line: {line!r}")

        if not line:
            print("Empty response!")
            print("Stderr:", proc.stderr.read().decode())
            return

        # 解析长度
        decoded = line.decode().strip()
        if ":" not in decoded:
            print(f"Invalid header: {decoded!r}")
            return

        length = int(decoded.split(":")[1].strip())
        print(f"Content-Length: {length}")

        # 读取空行
        empty = proc.stdout.readline()
        print(f"Empty line: {empty!r}")

        # 读取 body
        body_data = proc.stdout.read(length)
        print(f"Body: {body_data.decode()}")

    finally:
        proc.kill()


if __name__ == "__main__":
    test()