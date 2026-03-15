# MCP ReAct Demo (FastAPI + React)

This project is a minimal end-to-end demo of a ReAct-style agent that:
1. Lists tools in MCP format.
2. Lets an LLM pick tool calls.
3. Executes tools (built-in or external MCP servers).
4. Streams steps to a React UI via SSE.

It includes a backend (FastAPI) and frontend (Vite + React).

## Features

- ReAct-style agent with streaming SSE (`/api/agent/chat-stream`).
- Built-in tools:
  - `get_weather` (via `wttr.in`)
  - `http_get_text`
  - `browser_screenshot` (Playwright, outputs `/static/screenshots/*.png`)
- External MCP server integration over stdio (`mcp` SDK).
- Tool and MCP server configuration stored in SQLite.

## Architecture

```mermaid
flowchart LR
  UI[React UI (Vite)] -->|HTTP/SSE| API[FastAPI]
  API -->|ReAct loop| LLM[LLM API (SiliconFlow)]
  API -->|tools/list| DB[(SQLite)]
  API -->|tools/call| BUILTIN[Built-in tools]
  API -->|tools/call| MCP[MCP stdio servers]
  MCP -->|stdio JSON-RPC| INTERNAL[internal_mcp_server.py]
  BUILTIN -->|network| EXT[wttr.in / HTTP targets]
```

## Project Structure

- `app/`
  - `main.py` FastAPI app
  - `routers/` API routes
    - `agent.py` ReAct + streaming SSE
    - `tools.py` tool CRUD
    - `mcp_servers.py` MCP server CRUD
  - `mcp_client.py` MCP stdio client (SDK)
  - `mcp_tools.py` tool dispatch (builtin + MCP)
  - `internal_mcp_server.py` internal MCP server (stdio)
  - `internal_tools_impl.py` tool implementations
  - `db.py` SQLite + init
  - `models.py`, `schemas.py`
- `frontend/` Vite + React UI
- `static/` static files (screenshots)
- `mcp_demo.sqlite3` SQLite DB (created on first run)

## Prerequisites

- Python 3.11+
- Node.js 18+
- macOS/Linux (Playwright support)

## Backend Setup

```bash
cd /Users/pxy/PycharmProjects/mcp_train
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install
```

### Environment Variables

The backend uses SiliconFlow OpenAI-compatible API:

```bash
export SILICONFLOW_API_KEY="your_key_here"
```

If not set, the code currently falls back to a hardcoded key in `app/llm_client.py`.

## Frontend Setup

```bash
cd /Users/pxy/PycharmProjects/mcp_train/frontend
npm install
```

## Run (Development)

### Backend

```bash
cd /Users/pxy/PycharmProjects/mcp_train
uvicorn app.main:create_app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd /Users/pxy/PycharmProjects/mcp_train/frontend
npm run dev
```

Open the UI at:
- `http://localhost:5173`

Backend API:
- `http://localhost:8000`

## API Endpoints

- `GET /api/tools` list tools
- `POST /api/tools` create tool (schema stored in DB)
- `DELETE /api/tools/{id}`
- `GET /api/mcp-servers` list MCP servers
- `POST /api/mcp-servers` create MCP server
- `POST /api/mcp-servers/{id}/refresh-tools` refresh MCP tool list
- `DELETE /api/mcp-servers/{id}`
- `POST /api/agent/chat` synchronous ReAct
- `POST /api/agent/chat-stream` streaming SSE

### SSE Example

```bash
curl -N 'http://127.0.0.1:8000/api/agent/chat-stream' \
  -H 'Content-Type: application/json' \
  --data-raw '{
    "message":"Check Beijing weather for 2026-03-15 and summarize.",
    "max_steps":4,
    "model_id":"Pro/MiniMaxAI/MiniMax-M2.5"
  }'
```

SSE events:
- `meta`: conversation id
- `step`: `thought` / `action` / `observation` / `final`
- `done`: final answer

## Built-in Tools (Behavior)

- `get_weather`
  - Uses `https://wttr.in/<city>?format=3`
  - `date` is accepted but currently ignored by the tool (it is echoed in output only)
- `http_get_text`
  - HTTP GET, returns a truncated text payload
- `browser_screenshot`
  - Uses Playwright headless Chromium
  - Saves PNG in `static/screenshots/`
  - Returns `/static/screenshots/<file>.png`

## MCP Servers

MCP servers are configured via `/api/mcp-servers` and stored in `mcp_demo.sqlite3`.
The internal MCP server uses stdio (`app/internal_mcp_server.py`) and exposes:

- `get_weather`
- `http_get_text`
- `browser_screenshot`

For external MCP servers, configure:

- `command`
- `args` (JSON array)
- `cwd` (optional)
- `enabled`

The backend will call `tools/list` and `tools/call` over stdio using the official `mcp` SDK.

## Troubleshooting

- If `browser_screenshot` fails, ensure Playwright is installed:
  ```bash
  python -m playwright install
  ```
- If the internal MCP server fails to start, ensure `python` points to the venv.
- If the LLM call fails, check `SILICONFLOW_API_KEY`.
- SQLite DB file: `mcp_demo.sqlite3`

## Notes

This repo is a demo and keeps logic intentionally simple. It is a good baseline
for experimenting with ReAct-style tool calling and MCP integration.
