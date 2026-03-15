import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import Tool
from ..schemas import ToolCreate, ToolRead


router = APIRouter()


@router.get("/", response_model=List[ToolRead])
async def list_all_tools(
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Tool))
    return list(result.scalars())


@router.post("/", response_model=ToolRead)
async def create_tool(
    payload: ToolCreate,
    session: AsyncSession = Depends(get_session),
):
    tool = Tool(
        name=payload.name,
        description=payload.description,
        schema_json=json.dumps(payload.schema_json, ensure_ascii=False),
        implementation_type=payload.implementation_type,
    )
    session.add(tool)
    await session.commit()
    await session.refresh(tool)
    return tool


@router.delete("/{tool_id}")
async def delete_tool(
    tool_id: int,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Tool).where(Tool.id == tool_id))
    tool = result.scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    await session.delete(tool)
    await session.commit()
    return {"ok": True}


