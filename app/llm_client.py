import os
from typing import Any, Dict, List

import httpx


SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
SILICONFLOW_DEFAULT_KEY = (
    "sk-hbxoxotmmfsnsbcsvmeryrbjvfdqltpicciktjrjkspdhfxo"
)


async def call_llm_with_tools(
    model: str,
    messages: List[Dict[str, str]],
    tools: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    使用硅基流动的 OpenAI 兼容接口，并让模型按约定的 JSON 输出 ReAct 步骤。
    这里不直接用 OpenAI 的 tools 协议，而是把工具列表塞到 system prompt 里，
    让模型严格输出一个 JSON。
    """
    # 本地 demo：如果环境变量没配，就用写死在代码里的 key
    api_key = os.getenv("SILICONFLOW_API_KEY") or SILICONFLOW_DEFAULT_KEY

    system_prompt = (
        "你是一个 ReAct agent，按照以下 JSON 协议思考和调用工具。\n"
        "工具列表为：\n"
        f"{tools}\n\n"
        "你有两种输出模式，**每次调用只能选择其中一种**：\n"
        "1）单步模式：输出一个 JSON 对象，例如：\n"
        '{"type": "thought", "content": "..."}\n'
        "或：\n"
        '{"type": "action", "content": "调用工具", '
        '"tool_name": "server-filesystem/read_text_file", '
        '"tool_input": {"path": "~/USER.md"}}\n'
        "或：\n"
        '{"type": "final", "content": "最终回答"}\n\n'
        "2）多步计划模式：输出一个 JSON 数组，每个元素是一个步骤，例如：\n"
        '[\n'
        '  {"type": "action", "content": "读取用户指定文件内容", '
        '"tool_name": "server-filesystem/read_text_file", '
        '"tool_input": {"path": "~/USER.md"}},\n'
        '  {"type": "action", "content": "删除指定文件", '
        '"tool_name": "server-filesystem/delete_file", '
        '"tool_input": {"path": "~/TOOLS.md"}},\n'
        '  {"type": "final", "content": "总结两步操作的结果"}\n'
        ']\n\n'
        "注意：\n"
        "- 无论哪种模式，**只允许输出合法 JSON（对象或数组），不要输出任何额外文字、注释或 XML 标签**。\n"
        "- 如果任务需要多步推理，但每一步都依赖上一轮的 observation，就使用单步模式逐步推理；\n"
        "  如果任务步骤固定且独立（例如先读文件再删文件），可以使用多步计划模式一次性给出全部步骤。\n"
    )

    full_messages = [{"role": "system", "content": system_prompt}] + messages

    # 调用 chat/completions
    # timeout 设置长一点，避免复杂 ReAct 场景下读超时
    async with httpx.AsyncClient(base_url=SILICONFLOW_BASE_URL, timeout=180) as client:
        resp = await client.post(
            "/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": full_messages,
                "temperature": 0.2,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    content = data["choices"][0]["message"]["content"]
    # 让调用方自己去 json.loads，方便错误处理
    return {"raw": data, "content": content}


