from shared.redis_client import TaskQueue, get_redis
from shared.database import TaskStore, TenantStore
import json, time, structlog
logger = structlog.get_logger()

class AgentScheduler:
    def __init__(self):
        self.queue = TaskQueue()
        self.task_store = TaskStore()
        self.tenant_store = TenantStore()
        self.redis = get_redis()

    def schedule_next(self) -> dict | None:
        task_info = self.queue.dequeue()
        if not task_info: return None
        tenant = self.tenant_store.get_tenant(task_info["tenant_id"])
        if not tenant:
            self.queue.mark_done(task_info["task_id"])
            return None
        assignment = {"task_id": task_info["task_id"], "tenant_id": task_info["tenant_id"],
                      "tenant_config": tenant.get("config", {})}
        self.redis.lpush("agent:worker_queue", json.dumps(assignment))
        self.task_store.update_task_status(task_info["task_id"], "queued")
        logger.info("task_scheduled", task_id=task_info["task_id"])
        return assignment

    def run_loop(self):
        logger.info("scheduler_started")
        while True:
            if not self.schedule_next():
                time.sleep(1)
