from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ToolCreate(BaseModel):
    name: str
    description: str
    # 注意：这里是前端传入的 JSON，对应数据库里会被转成字符串存储
    schema_json: Dict[str, Any]
    implementation_type: str = "builtin"


class ToolRead(ToolCreate):
    id: int
    # 数据库里是 Text（字符串），返回给前端也保持字符串，避免 FastAPI 校验报错
    schema_json: str

    class Config:
        from_attributes = True


class McpServerCreate(BaseModel):
    name: str
    command: str
    args: List[str] = []
    cwd: Optional[str] = None
    enabled: bool = True


class McpServerRead(McpServerCreate):
    id: int
    last_tools_json: Optional[str] = None

    class Config:
        from_attributes = True


class ChatMessage(BaseModel):
    role: str  # user / assistant / tool
    content: str
    tool_name: Optional[str] = None


class AgentRequest(BaseModel):
    conversation_id: Optional[int] = None
    message: str
    max_steps: int = 3
    model_id: str = "Pro/MiniMaxAI/MiniMax-M2.5"


class AgentStep(BaseModel):
    type: str  # thought / action / observation / final
    content: str
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None


class AgentResponse(BaseModel):
    conversation_id: int
    final_answer: str
    steps: List[AgentStep]


