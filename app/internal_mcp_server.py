import asyncio
import json
import os
import sys
from typing import Any, Dict

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Support running as a script: `python app/internal_mcp_server.py`
try:
    from .internal_tools_impl import (
        tool_browser_screenshot,
        tool_get_weather,
        tool_http_get_text,
    )
except ImportError:
    from app.internal_tools_impl import (
        tool_browser_screenshot,
        tool_get_weather,
        tool_http_get_text,
    )


TOOLS: Dict[str, Dict[str, Any]] = {
    "get_weather": {
        "description": "查询城市当前天气（内部 MCP server 示例，调用 wttr.in）",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名称，例如“北京”或“London”"},
                "date": {
                    "type": "string",
                    "description": "可选日期字符串，返回文案中会带上",
                },
            },
            "required": ["city"],
        },
    },
    "http_get_text": {
        "description": "HTTP GET 文本内容并截断返回",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "要抓取的 URL"},
                "max_chars": {
                    "type": "integer",
                    "description": "返回的最大字符数，默认 2000",
                },
            },
            "required": ["url"],
        },
    },
    "browser_screenshot": {
        "description": "使用 Playwright 对页面截图，返回 /static/screenshots/xxx.png",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "需要截图的页面 URL"},
                "width": {"type": "integer", "description": "视口宽度，默认 1280"},
                "height": {"type": "integer", "description": "视口高度，默认 720"},
            },
            "required": ["url"],
        },
    },
}


async def handle_request(payload: Dict[str, Any]) -> Dict[str, Any] | None:
    method = payload.get("method")
    req_id = payload.get("id")

    print(f"[internal_mcp_server] recv method={method} id={req_id}", file=sys.stderr)

    # Notifications (no id) should not receive responses.
    if req_id is None:
        return None

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "serverInfo": {"name": "internal", "version": "0.1"},
            },
        }

    if method == "ping":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {},
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {"name": name, **meta} for name, meta in TOOLS.items()
                ]
            },
        }

    if method == "tools/call":
        params = payload.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            if name == "get_weather":
                text = await tool_get_weather(
                    city=args.get("city", "北京"),
                    date=args.get("date"),
                )
            elif name == "http_get_text":
                text = await tool_http_get_text(
                    url=args.get("url"),
                    max_chars=int(args.get("max_chars", 2000)),
                )
            elif name == "browser_screenshot":
                text = await tool_browser_screenshot(
                    url=args.get("url"),
                    width=int(args.get("width", 1280)),
                    height=int(args.get("height", 720)),
                )
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Unknown tool {name}"},
                }

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {"type": "text", "text": text}
                    ]
                },
            }
        except Exception as e:  # noqa: BLE001
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": str(e)},
            }

    # 简单忽略 initialize/ping 等其它方法
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Unknown method {method}"},
    }


async def main() -> None:
    """
    极简 MCP server：
    - 从 stdin 读取带 Content-Length 头的 JSON-RPC 请求
    - 调用本地工具实现
    - 将响应写回 stdout
    """
    loop = asyncio.get_event_loop()

    reader = asyncio.StreamReader()
    reader_protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: reader_protocol, sys.stdin)

    write_transport, write_protocol = await loop.connect_write_pipe(
        asyncio.streams.FlowControlMixin, sys.stdout
    )
    writer = asyncio.StreamWriter(write_transport, write_protocol, reader, loop)

    while True:
        # 读 header
        headers: Dict[str, str] = {}
        while True:
            line = await reader.readline()
            if not line:
                return
            line_str = line.decode("utf-8").strip()
            if not line_str:
                break
            if ":" in line_str:
                k, v = line_str.split(":", 1)
                headers[k.strip().lower()] = v.strip()
        length = int(headers.get("content-length", "0"))
        if length <= 0:
            continue
        body = await reader.readexactly(length)
        payload = json.loads(body.decode("utf-8"))

        resp = await handle_request(payload)
        if resp is None:
            continue
        resp_bytes = json.dumps(resp, ensure_ascii=False).encode("utf-8")
        header = f"Content-Length: {len(resp_bytes)}\r\n\r\n".encode("utf-8")
        writer.write(header + resp_bytes)
        await writer.drain()


if __name__ == "__main__":
    asyncio.run(main())
