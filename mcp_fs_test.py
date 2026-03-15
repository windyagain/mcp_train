# mcp_fs_test.py
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    """
    使用官方 MCP SDK 连接 filesystem server
    """

    # 配置 server 启动参数
    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "/Users/pxy/Desktop"],
        env=None,
    )

    # 建立 stdio 连接
    async with stdio_client(server_params) as (read, write):
        # 创建会话
        async with ClientSession(read, write) as session:
            # 初始化
            await session.initialize()

            # 列出工具
            print(">>> 调用 tools/list")
            tools = await session.list_tools()
            print("可用工具:")
            for tool in tools.tools:
                print(f"- {tool.name}: {tool.description}")

            # 调用 list_directory
            print("\n>>> 调用 list_directory")
            result = await session.call_tool(
                "list_directory",
                {"path": "/Users/pxy/Desktop"},
            )
            print(f"目录内容:")
            for content in result.content:
                if content.type == "text":
                    print(content.text)


if __name__ == "__main__":


