# mcp_client.py
import json
import os
import subprocess
import asyncio
import threading
from typing import Any, Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .models import McpServer

# 线程池用于同步调用（避免 asyncio 事件循环冲突）
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="mcp_")


def _sync_mcp_call(server: McpServer, method: str, params: Dict = None, timeout: int = 30) -> Dict:
    """
    同步方式调用 MCP server，避免与 FastAPI 的事件循环冲突
    """
    args: List[str] = json.loads(server.args_json or "[]")
    project_root = server.cwd or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 构建请求
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or {}
    }
    body = json.dumps(req).encode()
    header = f"Content-Length: {len(body)}\r\n\r\n".encode()

    # 启动进程
    proc = subprocess.Popen(
        [server.command] + args,
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
        proc.stdin.close()

        # 读取响应（带超时）
        import select

        # 等待 stdout 可读
        ready, _, _ = select.select([proc.stdout], [], [], timeout)
        if not ready:
            raise TimeoutError(f"No response in {timeout}s")

        # 读取 header
        line = proc.stdout.readline()
        if not line:
            stderr = proc.stderr.read().decode()
            raise EOFError(f"Server closed connection. Stderr: {stderr}")

        decoded = line.decode().strip()
        if ":" not in decoded:
            raise ValueError(f"Invalid header: {decoded!r}")

        length = int(decoded.split(":")[1].strip())

        # 读取空行
        proc.stdout.readline()

        # 读取 body
        body_data = proc.stdout.read(length)

        return json.loads(body_data.decode())

    finally:
        proc.kill()
        proc.wait()


async def mcp_list_tools(server: McpServer) -> List[Dict[str, Any]]:
    # internal server 用同步方式（避免 asyncio 冲突）
    if server.name == "internal":
        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(_executor, _sync_mcp_call, server, "tools/list")

        tools = resp.get("result", {}).get("tools", [])
        return [
            {
                "name": t["name"],
                "description": t.get("description", ""),
                "input_schema": t.get("input_schema") or t.get("inputSchema", {}),
            }
            for t in tools
        ]

    # 其他 server 用 SDK（假设它们是真正的外部进程，不会有事件循环冲突）
    return await _mcp_list_tools_sdk(server)


async def mcp_call_tool(server: McpServer, name: str, arguments: Dict[str, Any]) -> Tuple[bool, str]:
    # internal server 用同步方式
    if server.name == "internal":
        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(
            _executor, _sync_mcp_call, server, "tools/call",
            {"name": name, "arguments": arguments}
        )

        if "error" in resp:
            return False, resp["error"].get("message", "Unknown error")

        content = resp.get("result", {}).get("content", [])
        texts = [c["text"] for c in content if c.get("type") == "text"]
        return True, "\n".join(texts) if texts else str(resp)

    # 其他 server 用 SDK
    return await _mcp_call_tool_sdk(server, name, arguments)


# SDK 实现（用于外部 server）
async def _mcp_list_tools_sdk(server: McpServer) -> List[Dict[str, Any]]:
    args: List[str] = json.loads(server.args_json or "[]")
    project_root = server.cwd or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    env = os.environ.copy()
    env["PYTHONPATH"] = project_root

    params = StdioServerParameters(
        command=server.command,
        args=args,
        env=env,
    )

    original_cwd = os.getcwd()
    os.chdir(project_root)

    try:
        async with asyncio.timeout(10.0):
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools_result = await session.list_tools()

                    return [
                        {
                            "name": tool.name,
                            "description": getattr(tool, "description", ""),
                            "input_schema": getattr(tool, "input_schema", None)
                                            or getattr(tool, "inputSchema", {}),
                        }
                        for tool in tools_result.tools
                    ]
    finally:
        os.chdir(original_cwd)


async def _mcp_call_tool_sdk(server: McpServer, name: str, arguments: Dict[str, Any]) -> Tuple[bool, str]:
    args: List[str] = json.loads(server.args_json or "[]")
    project_root = server.cwd or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    env = os.environ.copy()
    env["PYTHONPATH"] = project_root

    params = StdioServerParameters(
        command=server.command,
        args=args,
        env=env,
    )

    original_cwd = os.getcwd()
    os.chdir(project_root)

    try:
        async with asyncio.timeout(10.0):
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(name, arguments)

                    texts = [
                        c.text for c in result.content
                        if getattr(c, "type", None) == "text"
                    ]
                    content_str = "\n".join(texts) if texts else str(result)
                    return True, content_str
    except Exception as e:
        return False, f"MCP error: {e}"
    finally:
        os.chdir(original_cwd)