from fastapi import FastAPI
from contextlib import asynccontextmanager
from control_plane.scheduler import AgentScheduler
from shared.observability import setup_logging
import threading, structlog
logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    t = threading.Thread(target=AgentScheduler().run_loop, daemon=True)
    t.start()
    logger.info("control_plane_started")
    yield

app = FastAPI(title="Control Plane", version="1.0.0", lifespan=lifespan)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "control-plane"}
