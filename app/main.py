from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routers import agent, mcp_servers, tools
from .db import init_db


def create_app() -> FastAPI:
    app = FastAPI(title="MCP ReAct Demo")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(tools.router, prefix="/api/tools", tags=["tools"])
    app.include_router(agent.router, prefix="/api/agent", tags=["agent"])
    app.include_router(
        mcp_servers.router, prefix="/api/mcp-servers", tags=["mcp_servers"]
    )

    # 挂载静态文件目录，用于浏览器截图等
    static_dir = Path(__file__).resolve().parent.parent / "static"
    (static_dir / "screenshots").mkdir(parents=True, exist_ok=True)
    app.mount(
        "/static",
        StaticFiles(directory=str(static_dir)),
        name="static",
    )

    @app.on_event("startup")
    async def on_startup():
        await init_db()

    return app


app = create_app()


