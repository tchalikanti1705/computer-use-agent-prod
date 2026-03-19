from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import uuid

class TaskStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"

class TenantCreate(BaseModel):
    name: str
    email: str
    allowed_domains: list[str] = Field(default_factory=lambda: ["google.com", "wikipedia.org", "example.com"])
    max_concurrent_sessions: int = 3
    llm_provider: LLMProvider = LLMProvider.OPENAI
    llm_model: str = "gpt-4o"

class Tenant(TenantCreate):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    api_key: str = Field(default_factory=lambda: f"cua_{uuid.uuid4().hex}")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True

class TaskCreate(BaseModel):
    instruction: str
    callback_url: Optional[str] = None
    timeout_seconds: int = 600
    require_human_approval: bool = False

class Task(TaskCreate):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    status: TaskStatus = TaskStatus.PENDING
    session_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    error: Optional[str] = None
    total_steps: int = 0
    total_tokens: int = 0

class Session(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    task_id: str
    container_id: Optional[str] = None
    container_name: Optional[str] = None
    status: str = "creating"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity: datetime = Field(default_factory=datetime.utcnow)

class ActionLog(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    step_number: int
    action_type: str
    action_payload: dict = Field(default_factory=dict)
    screenshot_key: Optional[str] = None
    tokens_used: int = 0
    safety_approved: bool = True
    safety_reason: Optional[str] = None
    duration_ms: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class UsageRecord(BaseModel):
    tenant_id: str
    session_id: str
    tokens_used: int = 0
    vm_seconds: int = 0
    actions_count: int = 0
    screenshots_count: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class WSMessage(BaseModel):
    type: str
    session_id: str
    data: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
