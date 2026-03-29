import asyncio
import json
from typing import Any, Dict, List, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .mcp_client import mcp_call_tool as mcp_call_tool_remote, mcp_list_tools
from .models import McpServer, Tool


async def list_tools(session: AsyncSession) -> List[Dict[str, Any]]:
    """Return MCP-style tool list, each with JSONSchema parameters.

    由两部分组成：
    - 内置 builtin 工具（当前项目里直接实现的）
    - 外部 MCP server 暴露的工具（通过 tools/list 动态获取）
    """
    tools: List[Dict[str, Any]] = []
    seen_names = set()

    # 1) Tool 表内置工具统一映射到 internal 前缀，保证可路由到 MCP server
    result = await session.execute(select(Tool).where(Tool.implementation_type == "builtin"))
    for tool in result.scalars():
        schema = json.loads(tool.schema_json)
        full_name = tool.name if "/" in tool.name else f"internal/{tool.name}"
        if full_name in seen_names:
            continue
        seen_names.add(full_name)
        tools.append(
            {
                "name": full_name,
                "description": tool.description,
                "input_schema": schema,
            }
        )

    # 2) 外部 MCP server 工具（只做简单合并，不做去重）
    #    为了性能优先使用数据库里缓存的 last_tools_json，只在缺失时主动去拉一次。
    result = await session.execute(
        select(McpServer).where(McpServer.enabled.is_(True))
    )
    dirty = False
    for server in result.scalars():
        try:
            if server.last_tools_json:
                tool_list = json.loads(server.last_tools_json)
            else:
                tool_list = await mcp_list_tools(server)
                server.last_tools_json = json.dumps(tool_list, ensure_ascii=False)
                dirty = True

            for t in tool_list:
                full_name = f"{server.name}/{t.get('name')}"
                if full_name in seen_names:
                    continue
                seen_names.add(full_name)
                tools.append(
                    {
                        "name": full_name,
                        "description": t.get("description", ""),
                        "input_schema": t.get("input_schema") or {},
                    }
                )
        except Exception:
            # 某个 server 调不通时，忽略它
            continue

    if dirty:
        await session.commit()

    return tools


async def call_tool(
    session: AsyncSession, name: str, arguments: Dict[str, Any]
) -> Tuple[bool, str]:
    """
    MCP-server 风格的工具调度。
    在这里把工具名映射到具体实现：
    - 一切通过 MCP server（包括 internal MCP server）调用
    - 不再回退到本地 Python 实现，失败就是失败
    """

    # 1) 统一按 MCP server/tool_name 形式路由
    if "/" not in name:
        return (
            False,
            f"Unknown tool: {name}. Expected MCP tool name format: <server_name>/<tool_name>",
        )

    # 2) MCP server 工具，命名约定："{server_name}/{tool_name}"
    server_name, tool_name = name.split("/", 1)
    result = await session.execute(
        select(McpServer).where(
            McpServer.enabled.is_(True), McpServer.name == server_name
        )
    )
    server = result.scalar_one_or_none()
    if server:
        try:
            ok, text = await asyncio.wait_for(
                mcp_call_tool_remote(server, tool_name, arguments),
                timeout=30,
            )
            return ok, text
        except Exception as e:
            if isinstance(e, asyncio.TimeoutError):
                return False, f"MCP error ({server_name}): TimeoutError after 30s"
            return False, f"MCP error ({server_name}): {type(e).__name__}: {e}"

    # 3) 兜底：未知工具
    return False, f"Unknown tool: {name}"
