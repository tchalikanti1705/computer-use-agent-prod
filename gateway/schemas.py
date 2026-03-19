from pydantic import BaseModel
from typing import Optional

class CreateTenantRequest(BaseModel):
    name: str
    email: str
    allowed_domains: list[str] = ["google.com", "wikipedia.org", "example.com"]
    max_concurrent_sessions: int = 3
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"

class TenantResponse(BaseModel):
    id: str
    name: str
    email: str
    api_key: str
    is_active: bool

class CreateTaskRequest(BaseModel):
    instruction: str
    callback_url: Optional[str] = None
    timeout_seconds: int = 600
    require_human_approval: bool = False

class TaskResponse(BaseModel):
    id: str
    tenant_id: str
    status: str
    instruction: str
    created_at: str

class TaskStatusResponse(BaseModel):
    id: str
    status: str
    total_steps: int = 0
    total_tokens: int = 0
    result: Optional[str] = None
    error: Optional[str] = None
