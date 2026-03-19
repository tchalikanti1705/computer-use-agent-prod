from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uuid
from datetime import datetime
from gateway.auth import get_current_tenant, create_jwt_token
from gateway.middleware import rate_limiter
from gateway.schemas import *
from shared.database import TenantStore, TaskStore
from shared.redis_client import TaskQueue, SessionState, EventBus
from shared.observability import setup_logging, TASKS_SUBMITTED
import structlog
logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("gateway_starting")
    yield

app = FastAPI(title="Computer User Agent API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}

@app.post("/api/v1/tenants", response_model=TenantResponse)
async def create_tenant(req: CreateTenantRequest):
    data = {"id": str(uuid.uuid4()), "api_key": f"cua_{uuid.uuid4().hex}",
            "name": req.name, "email": req.email, "is_active": True,
            "allowed_domains": req.allowed_domains,
            "max_concurrent_sessions": req.max_concurrent_sessions,
            "llm_provider": req.llm_provider, "llm_model": req.llm_model}
    TenantStore().create_tenant(data)
    return TenantResponse(**data)

@app.post("/api/v1/auth/token")
async def get_token(tenant: dict = Depends(get_current_tenant)):
    return {"access_token": create_jwt_token(tenant["id"]), "token_type": "bearer"}

@app.post("/api/v1/tasks", response_model=TaskResponse)
async def create_task(req: CreateTaskRequest, tenant: dict = Depends(get_current_tenant)):
    await rate_limiter.check(tenant["id"])
    active = SessionState().count_tenant_sessions(tenant["id"])
    max_s = tenant.get("config", {}).get("max_concurrent_sessions", 3)
    if active >= max_s:
        raise HTTPException(429, f"Session limit reached ({max_s})")
    data = {"id": str(uuid.uuid4()), "tenant_id": tenant["id"],
            "instruction": req.instruction, "callback_url": req.callback_url,
            "timeout_seconds": req.timeout_seconds,
            "require_human_approval": req.require_human_approval, "status": "pending"}
    TaskStore().create_task(data)
    TaskQueue().enqueue(data["id"], tenant["id"])
    TASKS_SUBMITTED.labels(tenant_id=tenant["id"]).inc()
    return TaskResponse(id=data["id"], tenant_id=tenant["id"], status="pending",
                        instruction=req.instruction, created_at=datetime.utcnow().isoformat())

@app.get("/api/v1/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str, tenant: dict = Depends(get_current_tenant)):
    task = TaskStore().get_task(task_id)
    if not task or task.get("tenant_id") != tenant["id"]:
        raise HTTPException(404, "Task not found")
    return TaskStatusResponse(id=task["id"], status=task["status"],
                               result=task.get("result"), error=task.get("error"))

@app.websocket("/ws/stream/{session_id}")
async def ws_stream(ws: WebSocket, session_id: str):
    await ws.accept()
    ps = EventBus().subscribe(f"session:{session_id}")
    try:
        for msg in ps.listen():
            if msg["type"] == "message":
                await ws.send_text(msg["data"])
    except WebSocketDisconnect:
        ps.unsubscribe()
    finally:
        ps.close()
