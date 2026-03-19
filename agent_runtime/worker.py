import json, time, uuid, signal, sys, structlog
from agent_runtime.agent_loop import AgentLoop
from agent_runtime.vm.pool import VMPool
from agent_runtime.vm.sandbox import SandboxSession
from control_plane.session_manager import SessionManager
from control_plane.billing import UsageMeter
from shared.redis_client import get_redis, TaskQueue
from shared.database import TaskStore
from shared.observability import setup_logging, ACTIVE_SESSIONS
logger = structlog.get_logger()

class AgentWorker:
    def __init__(self):
        self.redis = get_redis()
        self.vm_pool = VMPool()
        self.session_mgr = SessionManager()
        self.task_store = TaskStore()
        self.billing = UsageMeter()
        self.running = True
        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)

    def _shutdown(self, *_):
        self.running = False
        self.vm_pool.cleanup_all()
        sys.exit(0)

    def run(self):
        setup_logging()
        logger.info("worker_started")
        while self.running:
            result = self.redis.brpop("agent:worker_queue", timeout=5)
            if not result: continue
            _, raw = result
            self._handle(json.loads(raw))

    def _handle(self, assignment):
        task_id = assignment["task_id"]
        tenant_id = assignment["tenant_id"]
        tenant_config = assignment.get("tenant_config", {})
        session_id = str(uuid.uuid4())
        sandbox = SandboxSession(self.vm_pool)
        t0 = time.time()
        try:
            self.task_store.update_task_status(task_id, "running")
            vm = sandbox.start(session_id, tenant_id)
            self.session_mgr.create_session(session_id, tenant_id, task_id,
                container_id=sandbox.container_info.get("container_id"))
            ACTIVE_SESSIONS.labels(tenant_id=tenant_id).inc()

            task = self.task_store.get_task(task_id)
            if not task: raise RuntimeError(f"Task {task_id} not found")

            agent = AgentLoop(task_id, tenant_id, tenant_config, vm, session_id)
            result = agent.run(task["instruction"])

            self.task_store.update_task_status(task_id, result["status"],
                result=json.dumps(result.get("messages", [])), error=result.get("error"),
                total_steps=result["steps"], total_tokens=result["total_tokens"])

            self.billing.record(tenant_id, tokens=result["total_tokens"],
                vm_seconds=int(time.time()-t0), actions=result["steps"], screenshots=result["steps"])
            logger.info("task_complete", task_id=task_id, status=result["status"], steps=result["steps"])
        except Exception as e:
            logger.exception("task_failed", task_id=task_id)
            self.task_store.update_task_status(task_id, "failed", error=str(e))
        finally:
            sandbox.stop()
            self.session_mgr.end_session(session_id)
            ACTIVE_SESSIONS.labels(tenant_id=tenant_id).dec()
            TaskQueue().mark_done(task_id)

if __name__ == "__main__":
    AgentWorker().run()
