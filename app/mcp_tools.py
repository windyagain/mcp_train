import json
from typing import Any, Dict, List, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .internal_tools_impl import (
    tool_browser_screenshot,
    tool_get_weather,
    tool_http_get_text,
)
from .mcp_client import mcp_call_tool as mcp_call_tool_remote, mcp_list_tools
from .models import McpServer, Tool


async def list_tools(session: AsyncSession) -> List[Dict[str, Any]]:
    """Return MCP-style tool list, each with JSONSchema parameters.

    由两部分组成：
    - 内置 builtin 工具（当前项目里直接实现的）
    - 外部 MCP server 暴露的工具（通过 tools/list 动态获取）
    """
    tools: List[Dict[str, Any]] = []

    # 1) 内置工具
    result = await session.execute(select(Tool).where(Tool.implementation_type == "builtin"))
    for tool in result.scalars():
        schema = json.loads(tool.schema_json)
        tools.append(
            {
                "name": tool.name,
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
                # 给 name 加上 server 前缀，避免和本地工具冲突，例如 "time/getTime"
                full_name = f"{server.name}/{t.get('name')}"
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

    # 1) 如果是内置工具名称，转发到名为 "internal" 的 MCP server
    internal_builtin_names = {"get_weather", "http_get_text", "browser_screenshot"}
    if name in internal_builtin_names:
        result = await session.execute(
            select(McpServer).where(
                McpServer.enabled.is_(True), McpServer.name == "internal"
            )
        )
        internal_server = result.scalar_one_or_none()
        if internal_server:
            ok, text = await mcp_call_tool_remote(internal_server, name, arguments)
            return ok, text
        return False, f'Internal MCP server "internal" not configured or disabled'

    # 2) 外部 MCP server 工具，命名约定："{server_name}/{tool_name}"
    if "/" in name:
        server_name, tool_name = name.split("/", 1)
        result = await session.execute(
            select(McpServer).where(
                McpServer.enabled.is_(True), McpServer.name == server_name
            )
        )
        server = result.scalar_one_or_none()
        if server:
            ok, text = await mcp_call_tool_remote(server, tool_name, arguments)
            return ok, text

    # 3) 兜底：未知工具
    return False, f"Unknown tool: {name}"


async def _tool_get_weather(arguments: Dict[str, Any]) -> str:
    """
    真实调用 wttr.in 的天气工具，等价于：
    curl "wttr.in/London?format=3"
    """
    city = arguments.get("city", "London")
    date = arguments.get("date")
    return await tool_get_weather(city=city, date=date)


async def _tool_http_get_text(arguments: Dict[str, Any]) -> str:
    """
    通用 HTTP GET 文本工具：拉取一个 URL 的文本内容（前几 KB）
    """
    url = arguments.get("url")
    max_chars = int(arguments.get("max_chars", 2000))
    return await tool_http_get_text(url=url, max_chars=max_chars)


async def _tool_browser_screenshot(arguments: Dict[str, Any]) -> str:
    """
    真实浏览器截图工具：
    - 使用 Playwright 启动 headless Chromium 打开页面
    - 截图为 PNG，保存到本地 static/screenshots 目录
    - 返回可访问的 URL（例如 /static/screenshots/xxx.png）
    """
    url = arguments.get("url")
    width = int(arguments.get("width", 1280))
    height = int(arguments.get("height", 720))
    return await tool_browser_screenshot(url=url, width=width, height=height)


