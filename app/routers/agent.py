import json
from typing import AsyncGenerator, List, Optional, Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..llm_client import call_llm_with_tools
from ..mcp_tools import list_tools, call_tool
from ..models import Conversation, Message
from ..schemas import AgentRequest, AgentResponse, AgentStep


router = APIRouter()


def _extract_json_from_text(text: str) -> Optional[Any]:
    """
    尝试从 LLM 返回的文本里“鲁棒地”提取 JSON：
    - 去掉代码块 ```json ... ```
    - 如果前后有解释性文字，截取第一个 { 到 最后一个 } 之间的内容
    - 如果依然解析失败，返回 None
    """
    t = text.strip()

    # 去掉代码块包裹
    if t.startswith("```"):
        lines = t.splitlines()
        # 去掉首行 ``` 或 ```json
        if lines:
            if lines[0].startswith("```"):
                lines = lines[1:]
        # 去掉末尾 ```
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()

    # 直接尝试整体解析（可能是对象或数组）
    try:
        return json.loads(t)
    except Exception:
        pass

    # 尝试从中间截取 {...} 片段
    start = t.find("{")
    end = t.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = t[start : end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            return None

    return None


@router.post("/chat", response_model=AgentResponse)
async def agent_chat(
    payload: AgentRequest,
    session: AsyncSession = Depends(get_session),
):
    # 1. 会话创建/获取
    if payload.conversation_id is None:
        conv = Conversation(title="Demo 会话")
        session.add(conv)
        await session.flush()
        conversation_id = conv.id
    else:
        conversation_id = payload.conversation_id

    # 保存用户消息
    user_msg = Message(
        conversation_id=conversation_id,
        role="user",
        content=payload.message,
    )
    session.add(user_msg)
    await session.flush()

    # 2. ReAct 循环
    tools = await list_tools(session)
    steps: List[AgentStep] = []

    # 简化：只传当前用户问题和过去一步工具 observation
    history_messages = [
        {"role": "user", "content": payload.message},
    ]

    final_answer = ""

    for _ in range(payload.max_steps):
        llm_resp = await call_llm_with_tools(
            model=payload.model_id,
            messages=history_messages,
            tools=tools,
        )
        parsed = _extract_json_from_text(llm_resp["content"])
        if parsed is None:
            # LLM 输出不符合 JSON 时的兜底：直接把原始内容当成最终回答
            final_answer = llm_resp["content"]
            steps.append(AgentStep(type="final", content=final_answer))
            break

        # 兼容单步对象和多步数组
        if isinstance(parsed, dict):
            parsed_steps = [parsed]
        elif isinstance(parsed, list):
            parsed_steps = parsed
        else:
            final_answer = llm_resp["content"]
            steps.append(AgentStep(type="final", content=final_answer))
            break

        # 依次执行当前轮的所有步骤（plan-and-execute）
        for raw_step in parsed_steps:
            step = AgentStep(
                type=raw_step.get("type", "thought"),
                content=raw_step.get("content", ""),
                tool_name=raw_step.get("tool_name"),
                tool_input=raw_step.get("tool_input"),
            )
            steps.append(step)

            if step.type == "final":
                final_answer = step.content
                break

            if step.type == "action" and step.tool_name:
                ok, obs = await call_tool(
                    session, step.tool_name, step.tool_input or {}
                )
                obs_step = AgentStep(
                    type="observation",
                    content=obs,
                    tool_name=step.tool_name,
                )
                steps.append(obs_step)
                # 让 LLM 继续基于 observation 推理
                history_messages.append(
                    {
                        "role": "assistant",
                        "content": json.dumps(raw_step, ensure_ascii=False),
                    }
                )
                history_messages.append(
                    {
                        "role": "user",
                        "content": f"工具 {step.tool_name} 的返回：{obs}",
                    }
                )
            else:
                # thought 类型，直接继续对话
                history_messages.append(
                    {"role": "assistant", "content": step.content}
                )

        if final_answer:
            break

    if not final_answer:
        final_answer = steps[-1].content if steps else "没有得到有效回答。"

    # 保存最终 assistant 消息
    assistant_msg = Message(
        conversation_id=conversation_id,
        role="assistant",
        content=final_answer,
    )
    session.add(assistant_msg)
    await session.commit()

    return AgentResponse(
        conversation_id=conversation_id,
        final_answer=final_answer,
        steps=steps,
    )


@router.post("/chat-stream")
async def agent_chat_stream(
    payload: AgentRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    流式 ReAct 接口：
    - 使用 SSE（text/event-stream）
    - 每一步 thought / action / observation / final 作为一个事件推送到前端
    - 事件格式：data: {"type": "...", "content": "...", "conversation_id": 1}\n\n
    """

    # 会话创建/获取（和同步版保持一致）
    if payload.conversation_id is None:
        conv = Conversation(title="Demo 会话")
        session.add(conv)
        await session.flush()
        conversation_id = conv.id
    else:
        conversation_id = payload.conversation_id

    user_msg = Message(
        conversation_id=conversation_id,
        role="user",
        content=payload.message,
    )
    session.add(user_msg)
    await session.flush()

    tools = await list_tools(session)

    history_messages = [
        {"role": "user", "content": payload.message},
    ]

    async def event_generator() -> AsyncGenerator[str, None]:
        nonlocal history_messages
        final_answer = ""

        # 先推送一个 meta 事件，告知会话 ID
        meta = {
            "event": "meta",
            "conversation_id": conversation_id,
        }
        yield f"data: {json.dumps(meta, ensure_ascii=False)}\n\n"

        for _ in range(payload.max_steps):
            llm_resp = await call_llm_with_tools(
                model=payload.model_id,
                messages=history_messages,
                tools=tools,
            )
            parsed = _extract_json_from_text(llm_resp["content"])
            if parsed is None:
                # 解析失败时，直接把原始内容当成 final
                final_answer = llm_resp["content"]
                step = AgentStep(type="final", content=final_answer)
                event = {
                    "event": "step",
                    "conversation_id": conversation_id,
                    **step.model_dump(),
                }
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                break

            if isinstance(parsed, dict):
                parsed_steps = [parsed]
            elif isinstance(parsed, list):
                parsed_steps = parsed
            else:
                final_answer = llm_resp["content"]
                step = AgentStep(type="final", content=final_answer)
                event = {
                    "event": "step",
                    "conversation_id": conversation_id,
                    **step.model_dump(),
                }
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                break

            for raw_step in parsed_steps:
                step = AgentStep(
                    type=raw_step.get("type", "thought"),
                    content=raw_step.get("content", ""),
                    tool_name=raw_step.get("tool_name"),
                    tool_input=raw_step.get("tool_input"),
                )

                event = {
                    "event": "step",
                    "conversation_id": conversation_id,
                    **step.model_dump(),
                }
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

                if step.type == "final":
                    final_answer = step.content
                    break

                if step.type == "action" and step.tool_name:
                    ok, obs = await call_tool(
                        session, step.tool_name, step.tool_input or {}
                    )
                    obs_step = AgentStep(
                        type="observation",
                        content=obs,
                        tool_name=step.tool_name,
                    )
                    obs_event = {
                        "event": "step",
                        "conversation_id": conversation_id,
                        **obs_step.model_dump(),
                    }
                    yield f"data: {json.dumps(obs_event, ensure_ascii=False)}\n\n"

                    history_messages.append(
                        {
                            "role": "assistant",
                            "content": json.dumps(raw_step, ensure_ascii=False),
                        }
                    )
                    history_messages.append(
                        {
                            "role": "user",
                            "content": f"工具 {step.tool_name} 的返回：{obs}",
                        }
                    )
                else:
                    history_messages.append(
                        {"role": "assistant", "content": step.content}
                    )

            if final_answer:
                break

        # 结束前保存最终回答到 DB
        if not final_answer:
            final_answer = "对话结束，没有得到有效回答。"
        assistant_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=final_answer,
        )
        session.add(assistant_msg)
        await session.commit()

        done_event = {
            "event": "done",
            "conversation_id": conversation_id,
            "final_answer": final_answer,
        }
        yield f"data: {json.dumps(done_event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


