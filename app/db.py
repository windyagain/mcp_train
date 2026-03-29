from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase


DB_PATH = Path(__file__).resolve().parent.parent / "mcp_demo.sqlite3"
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"


class Base(DeclarativeBase):
    pass


engine = create_async_engine(DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    from sqlalchemy import select
    from .models import Tool, McpServer  # noqa: F401
    import json
    import sys

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 内置几个示例工具：get_weather / http_get_text / browser_screenshot
    async with AsyncSessionLocal() as session:
        # get_weather：基于 wttr.in 的天气查询
        result = await session.execute(select(Tool).where(Tool.name == "get_weather"))
        if not result.scalar_one_or_none():
            schema_weather = {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，例如“北京”或“London”",
                    },
                    "date": {
                        "type": "string",
                        "description": "日期，格式 YYYY-MM-DD（目前会被忽略，仅根据城市查询当前天气）",
                    },
                },
                "required": ["city"],
            }
            session.add(
                Tool(
                    name="get_weather",
                    description="查询某个城市的当前天气，内部调用 wttr.in，与 curl \"wttr.in/London?format=3\" 类似",
                    schema_json=json.dumps(schema_weather, ensure_ascii=False),
                    implementation_type="builtin",
                )
            )

        # http_get_text：拉取一个 URL 的文本内容
        result = await session.execute(
            select(Tool).where(Tool.name == "http_get_text")
        )
        if not result.scalar_one_or_none():
            schema_http = {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "要抓取的 HTTP URL",
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "返回文本的最大长度，默认为 2000",
                    },
                },
                "required": ["url"],
            }
            session.add(
                Tool(
                    name="http_get_text",
                    description="对指定 URL 执行 HTTP GET，并返回前几 KB 的文本内容",
                    schema_json=json.dumps(schema_http, ensure_ascii=False),
                    implementation_type="builtin",
                )
            )

        # browser_screenshot：浏览器截图工具（Playwright）
        result = await session.execute(
            select(Tool).where(Tool.name == "browser_screenshot")
        )
        if not result.scalar_one_or_none():
            schema_shot = {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "需要截图的页面 URL",
                    },
                    "width": {
                        "type": "integer",
                        "description": "视口宽度，默认为 1280",
                    },
                    "height": {
                        "type": "integer",
                        "description": "视口高度，默认为 720",
                    },
                },
                "required": ["url"],
            }
            session.add(
                Tool(
                    name="browser_screenshot",
                    description="使用 Playwright 对指定 URL 进行浏览器截图，返回 PNG 的 base64 data URL（data:image/png;base64,...）",
                    schema_json=json.dumps(schema_shot, ensure_ascii=False),
                    implementation_type="builtin",
                )
            )

        # 默认写入 internal MCP server（统一走 MCP 调用链）
        result = await session.execute(
            select(McpServer).where(McpServer.name == "internal")
        )
        if not result.scalar_one_or_none():
            session.add(
                McpServer(
                    name="internal",
                    command=sys.executable,
                    args_json=json.dumps(["-m", "app.internal_mcp_server"], ensure_ascii=False),
                    cwd=str(Path(__file__).resolve().parent.parent),
                    enabled=True,
                )
            )

        await session.commit()


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session

