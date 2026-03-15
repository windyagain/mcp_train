import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..mcp_client import mcp_list_tools
from ..models import McpServer
from ..schemas import McpServerCreate, McpServerRead


router = APIRouter()


@router.get("/", response_model=List[McpServerRead])
async def list_mcp_servers(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(McpServer))
    return list(result.scalars())


@router.post("/", response_model=McpServerRead)
async def create_mcp_server(
    payload: McpServerCreate, session: AsyncSession = Depends(get_session)
):
    server = McpServer(
        name=payload.name,
        command=payload.command,
        args_json=json.dumps(payload.args or [], ensure_ascii=False),
        cwd=payload.cwd,
        enabled=payload.enabled,
    )
    session.add(server)
    await session.commit()
    await session.refresh(server)
    return server


@router.post("/{server_id}/refresh-tools", response_model=McpServerRead)
async def refresh_mcp_server_tools(
    server_id: int, session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(McpServer).where(McpServer.id == server_id)
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")

    resp = await mcp_list_tools(server)
    server.last_tools_json = json.dumps(resp, ensure_ascii=False)
    await session.commit()
    await session.refresh(server)
    return server


@router.delete("/{server_id}")
async def delete_mcp_server(
    server_id: int, session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(McpServer).where(McpServer.id == server_id)
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="MCP server not found")
    await session.delete(server)
    await session.commit()
    return {"ok": True}


