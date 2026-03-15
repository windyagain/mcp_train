import React, { useEffect, useState } from "react";

type Tool = {
  id: number;
  name: string;
  description: string;
  schema_json: any;
};

type AgentStep = {
  type: string;
  content: string;
  tool_name?: string;
};

type AgentResponse = {
  conversation_id: number;
  final_answer: string;
  steps: AgentStep[];
};

type McpServer = {
  id: number;
  name: string;
  command: string;
  args: string[];
  cwd: string | null;
  enabled: boolean;
  last_tools_json?: string | null;
};

type Page = "agent" | "config";

const API_BASE = "http://127.0.0.1:8000";

export const App: React.FC = () => {
  const [activePage, setActivePage] = useState<Page>("agent");

  const [tools, setTools] = useState<Tool[]>([]);
  const [newToolName, setNewToolName] = useState("get_weather_2");
  const [newToolDesc, setNewToolDesc] = useState("另一个示例天气工具");
  const [newToolSchema, setNewToolSchema] = useState(
    JSON.stringify(
      {
        type: "object",
        properties: {
          city: { type: "string", description: "城市名称" },
          date: { type: "string", description: "日期 YYYY-MM-DD" }
        },
        required: ["city"]
      },
      null,
      2
    )
  );

  const [question, setQuestion] = useState(
    "帮我查一下北京今天(2026-03-15)的天气，然后用自然语言总结。"
  );
  const [agentResp, setAgentResp] = useState<AgentResponse | null>(null);
  const [streamSteps, setStreamSteps] = useState<AgentStep[]>([]);
  const [streamFinal, setStreamFinal] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [mcpServers, setMcpServers] = useState<McpServer[]>([]);
  const [newMcpName, setNewMcpName] = useState("internal");
  const [newMcpCommand, setNewMcpCommand] = useState("python");
  const [newMcpArgs, setNewMcpArgs] = useState(
    '["-m", "app.internal_mcp_server"]'
  );
  const [newMcpCwd, setNewMcpCwd] = useState(
    "/Users/pxy/PycharmProjects/mcp_train"
  );

  const renderStepContent = (s: AgentStep) => {
    const isImage =
      s.type === "observation" &&
      typeof s.content === "string" &&
      (s.content.startsWith("/static/") ||
        s.content.startsWith("http://") ||
        s.content.startsWith("https://"));

    if (isImage) {
      const src = s.content.startsWith("/static/")
        ? `${API_BASE}${s.content}`
        : s.content;
      return (
        <div style={{ marginTop: "4px" }}>
          <div style={{ fontSize: "11px", color: "#64748b", marginBottom: "4px" }}>
            截图预览：
          </div>
          <img
            src={src}
            alt={s.tool_name ?? "screenshot"}
            style={{
              maxWidth: "100%",
              maxHeight: 240,
              borderRadius: 8,
              border: "1px solid #1e293b",
              background: "#020617"
            }}
          />
        </div>
      );
    }

    return <span>{s.content}</span>;
  };

  const fetchTools = async () => {
    const resp = await fetch(`${API_BASE}/api/tools/`);
    const data = await resp.json();
    setTools(data);
  };

  const fetchMcpServers = async () => {
    const resp = await fetch(`${API_BASE}/api/mcp-servers/`);
    const data = await resp.json();
    setMcpServers(data);
  };

  useEffect(() => {
    fetchTools().catch(console.error);
    fetchMcpServers().catch(console.error);
  }, []);

  const handleCreateTool = async () => {
    try {
      const schema = JSON.parse(newToolSchema);
      await fetch(`${API_BASE}/api/tools/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newToolName,
          description: newToolDesc,
          schema_json: schema,
          implementation_type: "builtin"
        })
      });
      await fetchTools();
      alert("工具已创建");
    } catch (e) {
      alert("Schema JSON 解析失败，请检查格式");
    }
  };

  const handleDeleteTool = async (id: number) => {
    if (!confirm("确认删除这个工具？")) return;
    await fetch(`${API_BASE}/api/tools/${id}`, { method: "DELETE" });
    await fetchTools();
  };

  const handleCreateMcpServer = async () => {
    try {
      const args = JSON.parse(newMcpArgs);
      await fetch(`${API_BASE}/api/mcp-servers/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: newMcpName,
          command: newMcpCommand,
          args,
          cwd: newMcpCwd,
          enabled: true
        })
      });
      await fetchMcpServers();
      alert("MCP server 已创建，可点击下方刷新查看其工具列表");
    } catch (e) {
      console.error(e);
      alert("Args 不是合法的 JSON 数组，请检查格式");
    }
  };

  const handleRefreshMcpTools = async (id: number) => {
    await fetch(`${API_BASE}/api/mcp-servers/${id}/refresh-tools`, {
      method: "POST"
    });
    await fetchMcpServers();
  };

  const handleDeleteMcpServer = async (id: number) => {
    if (!confirm("确认删除这个 MCP server？")) return;
    await fetch(`${API_BASE}/api/mcp-servers/${id}`, { method: "DELETE" });
    await fetchMcpServers();
  };

  const handleAskSync = async () => {
    setLoading(true);
    setAgentResp(null);
    setStreamSteps([]);
    setStreamFinal(null);
    try {
      const resp = await fetch(`${API_BASE}/api/agent/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: question,
          max_steps: 4,
          model_id: "Pro/MiniMaxAI/MiniMax-M2.5"
        })
      });
      const data = await resp.json();
      setAgentResp(data);
    } catch (e) {
      console.error(e);
      alert("请求失败，请检查后端是否已启动");
    } finally {
      setLoading(false);
    }
  };

  const handleAskStream = async () => {
    setLoading(true);
    setAgentResp(null);
    setStreamSteps([]);
    setStreamFinal(null);
    try {
      const resp = await fetch(`${API_BASE}/api/agent/chat-stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: question,
          max_steps: 4,
          model_id: "Pro/MiniMaxAI/MiniMax-M2.5"
        })
      });

      if (!resp.body) {
        throw new Error("Stream body is null");
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";

        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data:")) continue;
          const jsonStr = line.replace(/^data:\s*/, "");
          try {
            const evt = JSON.parse(jsonStr) as any;
            if (evt.event === "meta") continue;
            if (evt.event === "step") {
              const step: AgentStep = {
                type: evt.type,
                content: evt.content,
                tool_name: evt.tool_name
              };
              setStreamSteps(prev => [...prev, step]);
            }
            if (evt.event === "done") {
              setStreamFinal(evt.final_answer ?? null);
            }
          } catch (e) {
            console.error("parse stream event error:", e, line);
          }
        }
      }
    } catch (e) {
      console.error(e);
      alert("流式请求失败，请检查后端是否已启动");
    } finally {
      setLoading(false);
    }
  };

  const renderConfigPage = () => (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1.1fr 1.1fr",
        gap: "24px",
        alignItems: "flex-start"
      }}
    >
      {/* 工具配置 */}
      <div
        style={{
          background: "rgba(15,23,42,0.9)",
          borderRadius: "16px",
          padding: "16px",
          border: "1px solid rgba(148,163,184,0.3)"
        }}
      >
        <h3 style={{ marginBottom: 8, fontSize: 18 }}>工具配置（MCP 风格）</h3>
        <p
          style={{
            fontSize: 12,
            color: "#94a3b8",
            marginBottom: 12
          }}
        >
          配置内置工具的 JSON Schema，后端会将其以 MCP 形式暴露给 Agent。
        </p>

        <div style={{ marginBottom: 8 }}>
          <label style={{ fontSize: 13 }}>工具名称</label>
          <input
            value={newToolName}
            onChange={e => setNewToolName(e.target.value)}
            style={{
              width: "100%",
              padding: "6px 8px",
              borderRadius: 8,
              border: "1px solid #475569",
              background: "#020617",
              color: "white",
              marginTop: 4
            }}
          />
        </div>

        <div style={{ marginBottom: 8 }}>
          <label style={{ fontSize: 13 }}>工具描述</label>
          <input
            value={newToolDesc}
            onChange={e => setNewToolDesc(e.target.value)}
            style={{
              width: "100%",
              padding: "6px 8px",
              borderRadius: 8,
              border: "1px solid #475569",
              background: "#020617",
              color: "white",
              marginTop: 4
            }}
          />
        </div>

        <div style={{ marginBottom: 8 }}>
          <label style={{ fontSize: 13 }}>参数 JSON Schema</label>
          <textarea
            value={newToolSchema}
            onChange={e => setNewToolSchema(e.target.value)}
            rows={10}
            style={{
              width: "100%",
              padding: 8,
              borderRadius: 8,
              border: "1px solid #475569",
              background: "#020617",
              color: "#e5e7eb",
              fontFamily: "monospace",
              fontSize: 12,
              marginTop: 4
            }}
          />
        </div>

        <button
          onClick={handleCreateTool}
          style={{
            padding: "8px 12px",
            borderRadius: 999,
            border: "none",
            background: "linear-gradient(135deg,#22c55e,#0ea5e9,#6366f1)",
            color: "white",
            fontSize: 13,
            cursor: "pointer"
          }}
        >
          保存工具 Schema
        </button>

        <hr style={{ borderColor: "#1e293b", margin: "16px 0" }} />

        <h4 style={{ fontSize: 14, marginBottom: 6 }}>当前工具列表</h4>
        <div
          style={{
            maxHeight: 260,
            overflow: "auto",
            fontSize: 12,
            borderRadius: 8,
            border: "1px solid #1e293b",
            padding: 8,
            background: "#020617"
          }}
        >
          {tools.map(t => (
            <div
              key={t.id}
              style={{
                paddingBottom: 6,
                marginBottom: 6,
                borderBottom: "1px solid #1e293b",
                display: "flex",
                justifyContent: "space-between",
                gap: 8
              }}
            >
              <div>
                <div style={{ fontWeight: 600 }}>{t.name}</div>
                <div style={{ color: "#94a3b8" }}>{t.description}</div>
              </div>
              <button
                onClick={() => handleDeleteTool(t.id)}
                style={{
                  alignSelf: "center",
                  fontSize: 11,
                  padding: "4px 8px",
                  borderRadius: 999,
                  border: "1px solid #dc2626",
                  background: "transparent",
                  color: "#fecaca",
                  cursor: "pointer"
                }}
              >
                删除
              </button>
            </div>
          ))}
          {tools.length === 0 && (
            <div style={{ color: "#64748b" }}>暂无工具</div>
          )}
        </div>
      </div>

      {/* MCP Server 管理 */}
      <div
        style={{
          background: "rgba(15,23,42,0.9)",
          borderRadius: "16px",
          padding: "16px",
          border: "1px solid rgba(148,163,184,0.3)"
        }}
      >
        <h3 style={{ marginBottom: 8, fontSize: 18 }}>
          MCP Server 管理（本地 npx / internal）
        </h3>
        <p
          style={{
            fontSize: 12,
            color: "#94a3b8",
            marginBottom: 12
          }}
        >
          配置本地 MCP server（internal、server-time、server-filesystem
          等），后端会作为 MCP client 调用它们。
        </p>

        <div style={{ marginBottom: 8 }}>
          <label style={{ fontSize: 13 }}>
            名称（如 internal / server-time）
          </label>
          <input
            value={newMcpName}
            onChange={e => setNewMcpName(e.target.value)}
            style={{
              width: "100%",
              padding: "6px 8px",
              borderRadius: 8,
              border: "1px solid #475569",
              background: "#020617",
              color: "white",
              marginTop: 4
            }}
          />
        </div>

        <div style={{ marginBottom: 8 }}>
          <label style={{ fontSize: 13 }}>command（如 python / npx）</label>
          <input
            value={newMcpCommand}
            onChange={e => setNewMcpCommand(e.target.value)}
            style={{
              width: "100%",
              padding: "6px 8px",
              borderRadius: 8,
              border: "1px solid #475569",
              background: "#020617",
              color: "white",
              marginTop: 4
            }}
          />
        </div>

        <div style={{ marginBottom: 8 }}>
          <label style={{ fontSize: 13 }}>
            args JSON（如 ["-m","app.internal_mcp_server"] 或
            ["-y","@modelcontextprotocol/server-time"]）
          </label>
          <textarea
            value={newMcpArgs}
            onChange={e => setNewMcpArgs(e.target.value)}
            rows={3}
            style={{
              width: "100%",
              padding: 8,
              borderRadius: 8,
              border: "1px solid #475569",
              background: "#020617",
              color: "#e5e7eb",
              fontFamily: "monospace",
              fontSize: 12,
              marginTop: 4
            }}
          />
        </div>

        <div style={{ marginBottom: 8 }}>
          <label style={{ fontSize: 13 }}>工作目录 cwd（可选）</label>
          <input
            value={newMcpCwd}
            onChange={e => setNewMcpCwd(e.target.value)}
            style={{
              width: "100%",
              padding: "6px 8px",
              borderRadius: 8,
              border: "1px solid #475569",
              background: "#020617",
              color: "white",
              marginTop: 4
            }}
          />
        </div>

        <button
          onClick={handleCreateMcpServer}
          style={{
            padding: "8px 12px",
            borderRadius: 999,
            border: "none",
            background: "linear-gradient(135deg,#22c55e,#0ea5e9,#6366f1)",
            color: "white",
            fontSize: 13,
            cursor: "pointer"
          }}
        >
          保存 MCP Server
        </button>

        <h4 style={{ fontSize: 14, margin: "12px 0 6px" }}>
          当前 MCP Server 列表
        </h4>
        <div
          style={{
            maxHeight: 320,
            overflow: "auto",
            fontSize: 12,
            borderRadius: 8,
            border: "1px solid #1e293b",
            padding: 8,
            background: "#020617"
          }}
        >
          {mcpServers.map(s => (
            <div
              key={s.id}
              style={{
                paddingBottom: 6,
                marginBottom: 6,
                borderBottom: "1px solid #1e293b"
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  gap: 8
                }}
              >
                <div>
                  <div style={{ fontWeight: 600 }}>
                    {s.name} {s.enabled ? "" : "(disabled)"}
                  </div>
                  <div style={{ color: "#94a3b8" }}>
                    {s.command} {JSON.stringify(s.args)}
                  </div>
                  <div style={{ color: "#64748b" }}>cwd: {s.cwd || "-"}</div>
                </div>
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 4
                  }}
                >
                  <button
                    onClick={() => handleRefreshMcpTools(s.id)}
                    style={{
                      fontSize: 11,
                      padding: "4px 8px",
                      borderRadius: 999,
                      border: "1px solid #475569",
                      background: "transparent",
                      color: "#e5e7eb",
                      cursor: "pointer"
                    }}
                  >
                    刷新 tools/list
                  </button>
                  <button
                    onClick={() => handleDeleteMcpServer(s.id)}
                    style={{
                      fontSize: 11,
                      padding: "4px 8px",
                      borderRadius: 999,
                      border: "1px solid #dc2626",
                      background: "transparent",
                      color: "#fecaca",
                      cursor: "pointer"
                    }}
                  >
                    删除
                  </button>
                </div>
              </div>
              {s.last_tools_json && (
                <details style={{ marginTop: 4 }}>
                  <summary
                    style={{
                      cursor: "pointer",
                      color: "#22c55e",
                      outline: "none"
                    }}
                  >
                    查看 tools/list JSON
                  </summary>
                  <pre
                    style={{
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-all",
                      marginTop: 4,
                      background: "#020617",
                      borderRadius: 8,
                      padding: 8,
                      border: "1px solid #1e293b"
                    }}
                  >
                    {JSON.stringify(
                      JSON.parse(s.last_tools_json),
                      null,
                      2
                    )}
                  </pre>
                </details>
              )}
            </div>
          ))}
          {mcpServers.length === 0 && (
            <div style={{ color: "#64748b" }}>暂无 MCP server</div>
          )}
        </div>
      </div>
    </div>
  );

  const renderAgentPage = () => (
    <div
      style={{
        background: "rgba(15,23,42,0.9)",
        borderRadius: "16px",
        padding: "16px",
        border: "1px solid rgba(148,163,184,0.3)"
      }}
    >
      <h3 style={{ marginBottom: 8, fontSize: 18 }}>
        ReAct Agent 调用 MCP 工具
      </h3>
      <p
        style={{
          fontSize: 12,
          color: "#94a3b8",
          marginBottom: 12
        }}
      >
        后端会：1）把工具 Schema 作为 MCP server 暴露；2）Agent 侧作为 MCP
        client 获取工具列表；3）模型按 ReAct 模式输出 JSON 步骤；4）后端执行工具、把
        observation 继续喂给模型。
      </p>

      <textarea
        value={question}
        onChange={e => setQuestion(e.target.value)}
        rows={4}
        style={{
          width: "100%",
          padding: 8,
          borderRadius: 8,
          border: "1px solid #475569",
          background: "#020617",
          color: "#e5e7eb",
          marginBottom: 8,
          fontSize: 13
        }}
      />

      <button
        onClick={handleAskStream}
        disabled={loading}
        style={{
          padding: "8px 12px",
          borderRadius: 999,
          border: "none",
          background:
            "linear-gradient(135deg,#f97316,#ec4899,#6366f1)",
          color: "white",
          fontSize: 13,
          cursor: "pointer",
          opacity: loading ? 0.7 : 1
        }}
      >
        {loading ? "流式推理中..." : "让 Agent 解决这个问题（流式）"}
      </button>

      <button
        onClick={handleAskSync}
        disabled={loading}
        style={{
          marginLeft: 8,
          padding: "8px 12px",
          borderRadius: 999,
          border: "1px solid #475569",
          background: "transparent",
          color: "#e5e7eb",
          fontSize: 13,
          cursor: "pointer",
          opacity: loading ? 0.7 : 1
        }}
      >
        同步调用一次性返回（对比用）
      </button>

      {(streamSteps.length > 0 || streamFinal) && (
        <div
          style={{
            marginTop: 16,
            padding: 12,
            borderRadius: 12,
            background: "#020617",
            border: "1px solid #1e293b",
            fontSize: 13
          }}
        >
          <div style={{ marginBottom: 8, fontWeight: 600 }}>
            ReAct 步骤（流式，按到达顺序）：
          </div>
          <ol style={{ paddingLeft: 18, marginBottom: 8 }}>
            {streamSteps.map((s, idx) => (
              <li key={idx} style={{ marginBottom: 4 }}>
                <span
                  style={{
                    display: "inline-block",
                    minWidth: 72,
                    color:
                      s.type === "action"
                        ? "#f97316"
                        : s.type === "observation"
                        ? "#22c55e"
                        : s.type === "final"
                        ? "#eab308"
                        : "#60a5fa",
                    fontWeight: 600
                  }}
                >
                  {s.type}
                </span>
                {s.tool_name && (
                  <span
                    style={{ color: "#a855f7", marginRight: 4 }}
                  >
                    [{s.tool_name}]
                  </span>
                )}
                {renderStepContent(s)}
              </li>
            ))}
          </ol>

          {streamFinal && (
            <div
              style={{
                marginTop: 8,
                paddingTop: 8,
                borderTop: "1px solid #1e293b"
              }}
            >
              <div
                style={{ fontWeight: 600, marginBottom: 4 }}
              >
                最终回答：
              </div>
              <div>{streamFinal}</div>
            </div>
          )}
        </div>
      )}

      {streamSteps.length === 0 && !streamFinal && agentResp && (
        <div
          style={{
            marginTop: 16,
            padding: 12,
            borderRadius: 12,
            background: "#020617",
            border: "1px solid #1e293b",
            fontSize: 13
          }}
        >
          <div style={{ marginBottom: 8, fontWeight: 600 }}>
            ReAct 步骤（同步接口结果）：
          </div>
          <ol style={{ paddingLeft: 18, marginBottom: 8 }}>
            {agentResp.steps.map((s, idx) => (
              <li key={idx} style={{ marginBottom: 4 }}>
                <span
                  style={{
                    display: "inline-block",
                    minWidth: 72,
                    color:
                      s.type === "action"
                        ? "#f97316"
                        : s.type === "observation"
                        ? "#22c55e"
                        : s.type === "final"
                        ? "#eab308"
                        : "#60a5fa",
                    fontWeight: 600
                  }}
                >
                  {s.type}
                </span>
                {s.tool_name && (
                  <span
                    style={{ color: "#a855f7", marginRight: 4 }}
                  >
                    [{s.tool_name}]
                  </span>
                )}
                {renderStepContent(s)}
              </li>
            ))}
          </ol>

          <div
            style={{
              marginTop: 8,
              paddingTop: 8,
              borderTop: "1px solid #1e293b"
            }}
          >
            <div
              style={{ fontWeight: 600, marginBottom: 4 }}
            >
              最终回答：
            </div>
            <div>{agentResp.final_answer}</div>
          </div>
        </div>
      )}
    </div>
  );

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
        background: "#0f172a",
        color: "white",
        padding: "24px"
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 16
        }}
      >
        <h2 style={{ fontSize: 24 }}>MCP ReAct Demo（FastAPI + React）</h2>
        <div
          style={{
            display: "inline-flex",
            borderRadius: 999,
            border: "1px solid #1f2937",
            background: "#020617",
            overflow: "hidden"
          }}
        >
          <button
            onClick={() => setActivePage("agent")}
            style={{
              padding: "6px 14px",
              fontSize: 13,
              border: "none",
              cursor: "pointer",
              color: activePage === "agent" ? "#0f172a" : "#e5e7eb",
              background:
                activePage === "agent"
                  ? "linear-gradient(135deg,#f97316,#ec4899,#6366f1)"
                  : "transparent"
            }}
          >
            ReAct 对话
          </button>
          <button
            onClick={() => setActivePage("config")}
            style={{
              padding: "6px 14px",
              fontSize: 13,
              border: "none",
              cursor: "pointer",
              color: activePage === "config" ? "#0f172a" : "#e5e7eb",
              background:
                activePage === "config"
                  ? "linear-gradient(135deg,#22c55e,#0ea5e9,#6366f1)"
                  : "transparent"
            }}
          >
            工具 & MCP 配置
          </button>
        </div>
      </div>

      {activePage === "config" ? renderConfigPage() : renderAgentPage()}
    </div>
  );
};