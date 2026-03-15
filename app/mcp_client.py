import json
import os
import sys
from typing import Any, Dict, List, Tuple

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .models import McpServer


def _resolve_server_command(server: McpServer) -> tuple[str, List[str]]:
    """
    Resolve command/args for MCP server.
    For the built-in "internal" server, always use the current venv's Python
    and module invocation to avoid dependency/import issues.
    """
    if server.name == "internal":
        return sys.executable, ["-u", "-m", "app.internal_mcp_server"]

    args: List[str] = json.loads(server.args_json or "[]")
    return server.command, args


async def mcp_list_tools(server: McpServer) -> List[Dict[str, Any]]:
    command, args = _resolve_server_command(server)

    # 关键：获取项目根目录（mcp_train 目录）
    project_root = server.cwd or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 设置环境变量，让子进程能找到 app 包
    env = os.environ.copy()
    env["PYTHONPATH"] = project_root

    params = StdioServerParameters(
        command=command,
        args=args,
        env=env,
    )

    # 切换到项目根目录
    original_cwd = os.getcwd()
    os.chdir(project_root)

    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_result = await session.list_tools()

                simplified: List[Dict[str, Any]] = []
                for tool in tools_result.tools:
                    input_schema = getattr(tool, "input_schema", None) or getattr(
                        tool, "inputSchema", {}
                    )
                    simplified.append(
                        {
                            "name": tool.name,
                            "description": getattr(tool, "description", ""),
                            "input_schema": input_schema or {},
                        }
                    )
                return simplified
    finally:
        os.chdir(original_cwd)


async def mcp_call_tool(
        server: McpServer, name: str, arguments: Dict[str, Any]
) -> Tuple[bool, str]:
    command, args = _resolve_server_command(server)

    project_root = server.cwd or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = os.environ.copy()
    env["PYTHONPATH"] = project_root

    params = StdioServerParameters(
        command=command,
        args=args,
        env=env,
    )

    original_cwd = os.getcwd()
    os.chdir(project_root)

    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                try:
                    result = await session.call_tool(name, arguments)
                except Exception as e:
                    return False, f"MCP error: {e}"

                texts: List[str] = []
                for c in result.content:
                    if getattr(c, "type", None) == "text":
                        t = getattr(c, "text", "")
                        if t:
                            texts.append(t)
                content_str = "\n".join(texts) if texts else str(result)
                return True, content_str
    finally:
        os.chdir(original_cwd)
