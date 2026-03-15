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
        # 发送请求（initialize）
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

        # -------- tools/call 测试 --------
        req2 = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "get_weather", "arguments": {"city": "Beijing"}}
        }
        body2 = json.dumps(req2).encode()
        header2 = f"Content-Length: {len(body2)}\r\n\r\n".encode()

        print("\nSending tools/call get_weather...")
        proc.stdin.write(header2 + body2)
        proc.stdin.flush()

        ready2, _, _ = select.select([proc.stdout], [], [], 8.0)
        if not ready2:
            print("TIMEOUT! No tools/call response in 8 seconds")
            print("Stderr:", proc.stderr.read().decode())
            return

        line2 = proc.stdout.readline()
        print(f"Raw response line: {line2!r}")
        if not line2:
            print("Empty response for tools/call!")
            print("Stderr:", proc.stderr.read().decode())
            return

        decoded2 = line2.decode().strip()
        if ":" not in decoded2:
            print(f"Invalid header: {decoded2!r}")
            return

        length2 = int(decoded2.split(":")[1].strip())
        print(f"Content-Length: {length2}")
        empty2 = proc.stdout.readline()
        print(f"Empty line: {empty2!r}")
        body2_data = proc.stdout.read(length2)
        print(f"Body: {body2_data.decode()}")

    finally:
        proc.kill()


if __name__ == "__main__":
    test()
