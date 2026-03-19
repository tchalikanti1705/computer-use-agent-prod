import structlog
from prometheus_client import Counter, Histogram, Gauge

def setup_logging(log_level: str = "INFO"):
    structlog.configure(processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ])

TASKS_SUBMITTED = Counter("agent_tasks_submitted_total", "Tasks submitted", ["tenant_id"])
TASKS_COMPLETED = Counter("agent_tasks_completed_total", "Tasks completed", ["tenant_id", "status"])
AGENT_STEPS = Counter("agent_steps_total", "Agent steps executed", ["tenant_id"])
ACTIVE_SESSIONS = Gauge("agent_active_sessions", "Active sessions", ["tenant_id"])
LLM_LATENCY = Histogram("agent_llm_latency_seconds", "LLM latency", ["provider", "model"])
ACTION_LATENCY = Histogram("agent_action_latency_seconds", "Action latency", ["action_type"])
SAFETY_BLOCKS = Counter("agent_safety_blocks_total", "Safety blocks", ["tenant_id", "reason"])
VM_POOL_SIZE = Gauge("agent_vm_pool_size", "VM pool size")
